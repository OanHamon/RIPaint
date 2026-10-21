"""Export d'une partie en MP4 1080x1920 / 60 fps (H.264 + AAC), image par image.

Le rendu ne dépend pas de la vitesse du PC : chaque image est calculée puis envoyée à
ffmpeg, qui l'agrandit x8 sans lissage. La piste audio est assemblée au sample près à
partir des événements sonores de la simulation, puis multiplexée avec la vidéo.
"""

import json
import os
import random
import subprocess
import wave
import zlib
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

import imageio_ffmpeg
import numpy as np
import pygame

from audio.mixer import render_track, to_int16_stereo
from audio.sfx import build_bank
from audio.synth import SAMPLE_RATE
from engine8bit.display import FPS, LOGICAL_H, LOGICAL_W, OUTPUT_H, OUTPUT_W
from game import league, modes, variants
from game.battle import Battle
from game.render import Renderer
from game.settings import ROOT, Settings

from .srt import write_srt

NO_WINDOW = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0


class Cancelled(Exception):
    pass


@dataclass
class ExportResult:
    path: Path
    seed: int
    frames: int
    duration: float
    n_cubes: int
    hourglasses: int
    summary: str
    srt_path: Path | None = None
    mode: str = ""                  # nom du mode de jeu ("" = classique)


def ffmpeg_exe() -> str:
    return imageio_ffmpeg.get_ffmpeg_exe()


def parse_seed(text) -> int | None:
    """Seed saisie par l'utilisateur : nombre, ou texte converti en nombre. Vide -> None."""
    if text is None:
        return None
    text = str(text).strip()
    if not text:
        return None
    try:
        return int(text)
    except ValueError:
        return zlib.crc32(text.encode("utf-8"))


def random_seed() -> int:
    return random.SystemRandom().randrange(1, 1_000_000_000)


_FORBIDDEN = set('<>:"/\\|?*')


def safe_filename(text: str, limit: int = 140) -> str:
    """Texte utilisable dans un nom de fichier Windows (le « ? » et les autres caractères
    interdits sont retirés, les espaces multiples réduits)."""
    cleaned = "".join(" " if (ch in _FORBIDDEN or ord(ch) < 32) else ch for ch in text)
    cleaned = " ".join(cleaned.split()).strip(" .")
    return cleaned[:limit].rstrip(" .")


def video_filename(settings: Settings, stamp: str, seed: int, mode: str = "") -> str:
    """<date> - <légende TikTok> - [<mode> - ]seed<seed>.mp4"""
    caption = safe_filename(settings.caption_text())
    if not caption:
        tag = f"_{mode}" if mode else ""
        return f"{stamp}_cube-battle{tag}_seed{seed}.mp4"
    tag = f"{safe_filename(mode)} - " if mode else ""
    return f"{stamp} - {caption} - {tag}seed{seed}.mp4"


def output_dir(settings: Settings) -> Path:
    d = Path(settings.output_dir)
    if not d.is_absolute():
        d = ROOT / d
    d.mkdir(parents=True, exist_ok=True)
    return d


def _write_wav(path: Path, mono) -> None:
    pcm = to_int16_stereo(mono)
    with wave.open(str(path), "wb") as w:
        w.setnchannels(2)
        w.setsampwidth(2)
        w.setframerate(SAMPLE_RATE)
        w.writeframes(pcm.tobytes())


AAC_CEILING = 10 ** (-1 / 20)     # crête maximale tolérée après encodage : -1 dBFS


def _decoded_peak(path: Path) -> float:
    """Crête réelle (flottante, donc au-delà de 1.0 si dépassement) de l'audio encodé, lue sur les
    canaux d'origine (pas de conversion mono, qui fausserait le niveau)."""
    raw = subprocess.run([ffmpeg_exe(), "-hide_banner", "-loglevel", "error", "-i", str(path),
                          "-f", "f32le", "-"], capture_output=True, creationflags=NO_WINDOW).stdout
    data = np.frombuffer(raw, dtype=np.float32)
    return float(np.abs(data).max()) if len(data) else 0.0


def _run(cmd, err_path: Path) -> None:
    with open(err_path, "wb") as err:
        proc = subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=err, creationflags=NO_WINDOW)
    if proc.returncode != 0:
        raise RuntimeError("ffmpeg a échoué :\n" + err_path.read_text(errors="replace")[-2000:])


def export_video(seed: int, settings: Settings, out_dir: Path | None = None, progress=None,
                 cancel=None) -> ExportResult:
    """Calcule et encode une partie. `progress(frame, total)` est appelé régulièrement ;
    `cancel()` peut renvoyer True pour interrompre."""
    out_dir = out_dir or output_dir(settings)
    # date de création en tête du nom : les vidéos se trient naturellement par date
    stamp = datetime.now().strftime("%Y-%m-%d_%Hh%Mm%Ss")
    mode = modes.resolve(seed, settings)
    variant = variants.resolve(settings)
    tag = " ".join(t for t in ("" if variant.key == variants.COLORS else variant.key, mode.key if mode else "") if t)
    final = out_dir / video_filename(settings, stamp, seed, tag)
    tmp_video = final.with_name(final.stem + ".video.tmp.mp4")
    tmp_audio = final.with_name(final.stem + ".audio.tmp.wav")
    err_log = final.with_name(final.stem + ".ffmpeg.log")

    temp_files: list[Path] = []
    battle = Battle(seed, settings)
    # ligue : le résultat est connu d'avance (partie pré-simulée), on affiche le classement à jour
    new_league = None
    if settings.league and battle.final is not None:
        r = battle.final["result"]
        winner = battle.cubes[r.winner].team if r.winner is not None else None
        new_league = league.with_result(league.load(variant=battle.variant.key), winner)
        battle.league = {"day": new_league["day"], "standings": league.standings(new_league)}
    renderer = Renderer(battle)
    surf = pygame.Surface((LOGICAL_W, LOGICAL_H))

    vf = (f"scale={OUTPUT_W}:{OUTPUT_H}:flags=neighbor:out_color_matrix=bt709:out_range=tv,"
          f"format=yuv420p")
    cmd = [ffmpeg_exe(), "-hide_banner", "-loglevel", "error", "-y",
           "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{LOGICAL_W}x{LOGICAL_H}", "-r", str(FPS), "-i", "-",
           "-vf", vf, "-c:v", "libx264", "-preset", settings.x264_preset, "-crf", str(settings.crf),
           "-tune", "animation", "-profile:v", "high", "-g", str(FPS * 2),
           "-colorspace", "bt709", "-color_primaries", "bt709", "-color_trc", "bt709", "-color_range", "tv",
           "-an", str(tmp_video)]
    try:
        with open(err_log, "wb") as err:
            proc = subprocess.Popen(cmd, stdin=subprocess.PIPE, stdout=subprocess.DEVNULL, stderr=err,
                                    creationflags=NO_WINDOW)
            try:
                while not battle.done:
                    battle.step()
                    renderer.draw(surf)
                    proc.stdin.write(pygame.image.tobytes(surf, "RGB"))
                    if progress and battle.frame % 15 == 0:
                        progress(battle.frame + 1, battle.total_frames)
                    if cancel and battle.frame % 30 == 0 and cancel():
                        raise Cancelled()
                proc.stdin.close()
                code = proc.wait()
            except BaseException:
                proc.kill()
                proc.wait()
                raise
        if code != 0:
            raise RuntimeError("ffmpeg a échoué :\n" + err_log.read_text(errors="replace")[-2000:])

        total = battle.total_frames
        music_vol = settings.music_volume if settings.music_on() else 0.0
        mono = render_track(battle.events, total, build_bank(settings.aim_duration), seed,
                            settings.master_volume, music_vol, settings.paint_sound, FPS)
        # encodage AAC puis contrôle de la crête APRÈS encodage : l'AAC peut ajouter quelques dB
        # de dépassement sur des transitoires très secs ; si besoin on réencode un peu moins fort
        tmp_aac = final.with_name(final.stem + ".audio.tmp.m4a")
        temp_files.append(tmp_aac)
        gain = 1.0
        for _ in range(4):
            _write_wav(tmp_audio, mono * gain)
            _run([ffmpeg_exe(), "-hide_banner", "-loglevel", "error", "-y", "-i", str(tmp_audio),
                  "-c:a", "aac", "-b:a", "256k", "-ar", str(SAMPLE_RATE), str(tmp_aac)], err_log)
            peak = _decoded_peak(tmp_aac)
            if peak <= AAC_CEILING:
                break
            gain *= AAC_CEILING / peak * 0.98

        summary = battle.result_text
        meta = {"seed": seed, "generator": "cube_battle", "result": summary,
                "mode": mode.key if mode else modes.CLASSIC, "settings": battle.settings.to_dict()}
        if new_league is not None:
            meta["league_day"] = new_league["day"]
        _run([ffmpeg_exe(), "-hide_banner", "-loglevel", "error", "-y",
              "-i", str(tmp_video), "-i", str(tmp_aac),
              "-map", "0:v:0", "-map", "1:a:0", "-c:v", "copy", "-c:a", "copy",
              "-movflags", "+faststart",
              "-metadata", f"title={settings.caption_text() or f'Cube Battle #{seed}'}",
              "-metadata", "comment=" + json.dumps(meta, ensure_ascii=False),
              str(final)], err_log)

        if new_league is not None:
            league.save(new_league, variant=battle.variant.key)   # seulement une fois la vidéo réussie
        if settings.caption_file and settings.caption_text():
            # légende exacte (avec « ? ») prête à coller dans TikTok
            final.with_suffix(".txt").write_text(settings.caption_text() + "\n", encoding="utf-8")
        srt_path = None
        if settings.export_srt:
            srt_path = final.with_suffix(".srt")
            write_srt(srt_path, battle.subtitles, FPS, total)
        if progress:
            progress(total, total)
        return ExportResult(final, seed, total, total / FPS, len(battle.cubes), battle.hourglasses_taken,
                            summary, srt_path, mode.name if mode else "")
    finally:
        for p in (tmp_video, tmp_audio, err_log, *temp_files):
            try:
                p.unlink()
            except OSError:
                pass


def seeds_for_batch(count: int, settings: Settings) -> list[int]:
    """Seed fixée -> seed, seed+1, ... ; sinon seeds aléatoires toutes différentes."""
    base = parse_seed(settings.seed)
    if base is not None:
        return [base + i for i in range(count)]
    seeds: list[int] = []
    while len(seeds) < count:
        s = random_seed()
        if s not in seeds:
            seeds.append(s)
    return seeds
