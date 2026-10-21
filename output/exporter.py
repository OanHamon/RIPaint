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
from game import captions, cup as paintcup, league, modes, variants
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
    caption: str = ""               # légende TikTok de la vidéo (aussi dans le .txt)
    caption_id: str = ""            # accroche utilisée (garde-fou anti-répétition)
    details: str = ""               # format · mode · thème · variante · musique (journal)


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


def video_filename(settings: Settings, stamp: str, seed: int, mode: str = "", caption: str | None = None) -> str:
    """<date> - <légende TikTok> - [<mode> - ]seed<seed>.mp4 ; `caption` : légende générée pour
    cette vidéo (sans hashtags ni emojis dans le nom), sinon la légende fixe des réglages."""
    caption = safe_filename(settings.caption_text() if caption is None else captions.title_part(caption), 110)
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
                 cancel=None, plan: dict | None = None, recent_captions: list | None = None,
                 cup_state: dict | None = None, cup_slot: tuple | None = None) -> ExportResult:
    """Calcule et encode une partie. `progress(frame, total)` est appelé régulièrement ;
    `cancel()` peut renvoyer True pour interrompre. `plan` : choix du garde-fou (durée, format…) ;
    `cup_state` / `cup_slot` : match de PaintCup joué par cette vidéo (l'état est mis à jour)."""
    out_dir = out_dir or output_dir(settings)
    # date en tête du nom (sans l'heure) : les vidéos se trient par jour
    stamp = datetime.now().strftime("%Y-%m-%d")
    work = out_dir / f"_render_seed{seed}_{datetime.now().strftime('%H%M%S%f')}"
    tmp_video = work.with_name(work.name + ".video.tmp.mp4")
    tmp_audio = work.with_name(work.name + ".audio.tmp.wav")
    err_log = work.with_name(work.name + ".ffmpeg.log")

    temp_files: list[Path] = []
    battle = Battle(seed, settings)
    mode, variant = battle.mode, battle.variant
    # ligue / coupe : le résultat est connu d'avance (partie pré-simulée), on affiche le classement à jour
    new_league = None
    if cup_state is not None and cup_slot is not None and battle.final is not None:
        battle.cup = paintcup.record(cup_state, *cup_slot, [rk.team for rk in battle.final["result"].ranking])
    elif settings.league and battle.final is not None:
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
                            settings.master_volume, music_vol, settings.paint_sound, FPS, battle.music_style)
        # encodage AAC puis contrôle de la crête APRÈS encodage : l'AAC peut ajouter quelques dB
        # de dépassement sur des transitoires très secs ; si besoin on réencode un peu moins fort
        tmp_aac = work.with_name(work.name + ".audio.tmp.m4a")
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

        # légende : écrite d'après la partie (différente à chaque vidéo) ou fixe
        caption_id = ""
        if settings.caption_auto:
            caption, caption_id = captions.make(battle, settings.hashtags, recent_captions or [],
                                                random.Random(seed * 409 + 3), plan)
        else:
            caption = settings.caption_text()
        tags = [t for t in (battle.fmt.key if battle.fmt.key != "classic" else "",
                            "" if variant.key == variants.COLORS else variant.key, mode.key if mode else "",
                            battle.theme.key if battle.theme.key != "classic" else "") if t]
        final = out_dir / video_filename(settings, stamp, seed, " ".join(tags),
                                         caption if settings.caption_auto else None)

        summary = battle.result_text
        meta = {"seed": seed, "generator": "cube_battle", "result": summary,
                "mode": mode.key if mode else modes.CLASSIC, "format": battle.fmt.key, "theme": battle.theme.key,
                "music": battle.music_style, "variant": variant.key, "plan": plan or {},
                "settings": battle.settings.to_dict()}
        if new_league is not None:
            meta["league_day"] = new_league["day"]
        _run([ffmpeg_exe(), "-hide_banner", "-loglevel", "error", "-y",
              "-i", str(tmp_video), "-i", str(tmp_aac),
              "-map", "0:v:0", "-map", "1:a:0", "-c:v", "copy", "-c:a", "copy",
              "-movflags", "+faststart",
              "-metadata", f"title={caption or f'Cube Battle #{seed}'}",
              "-metadata", "comment=" + json.dumps(meta, ensure_ascii=False),
              str(final)], err_log)

        if new_league is not None:
            league.save(new_league, variant=battle.variant.key)   # seulement une fois la vidéo réussie
        if settings.caption_file and caption:
            # légende exacte (avec « ? » et emojis) prête à coller dans TikTok
            final.with_suffix(".txt").write_text(caption + "\n", encoding="utf-8")
        srt_path = None
        if settings.export_srt:
            srt_path = final.with_suffix(".srt")
            write_srt(srt_path, battle.subtitles, FPS, total)
        if progress:
            progress(total, total)
        details = " · ".join(x for x in (battle.fmt.name, mode.name if mode else "", battle.theme.name,
                                          variant.label, battle.music_style) if x)
        return ExportResult(final, seed, total, total / FPS, len(battle.cubes), battle.hourglasses_taken,
                            summary, srt_path, mode.name if mode else "", caption, caption_id, details)
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


def plan_for(seed: int, settings: Settings, history: dict, cup_state: dict | None = None):
    """Réglages concrets d'une vidéo d'un lot : match de PaintCup éventuel, puis choix du
    garde-fou anti-répétition (format, mode, thème, musique, durée…).
    Renvoie (réglages de la vidéo, plan, (tour, match) de coupe ou None)."""
    from dataclasses import replace

    from game import variety

    rng = random.Random(seed * 7 + 1)
    s = settings
    slot = None
    if settings.cup and cup_state is not None:
        slot = paintcup.next_match(cup_state)
    if slot is not None:
        lineup = cup_state["rounds"][slot[0]]["matches"][slot[1]]["lineup"]
        fmt = settings.format
        if fmt not in ("classic", "combat"):
            # une coupe se joue en course à la peinture (parfois en combat) : 3 ou 4 cubes par match
            recent = [v.get("format") for v in history["videos"]]
            fmt = variety.weighted_pick(rng, {"classic": 3.0, "combat": 1.0}, recent, avoid_last=False)
        s = replace(s, lineup=list(lineup), cup_label=paintcup.label(cup_state, *slot),
                    variant=cup_state["variant"], players=len(lineup), format=fmt)
    plan = variety.plan_video(s, history, rng, allow_short=slot is None)
    if slot is not None:
        plan["cup"] = s.cup_label
    video = variety.apply(s, plan)
    return keep_over_a_minute(seed, video, plan), plan, slot


def simulated_seconds(seed: int, settings: Settings) -> float:
    """Durée qu'aura la vidéo (partie simulée sans image ni son)."""
    from dataclasses import replace

    b = Battle(seed, replace(settings, league=False, cup_label=""))
    if b.final is not None:                       # partie déjà pré-simulée pour le teaser
        return b.final["duration"]
    while not b.done:
        b.step()
    return b.total_frames / FPS


def keep_over_a_minute(seed: int, settings: Settings, plan: dict) -> Settings:
    """Combat / bataille royale finissent dès qu'il reste un seul cube : si la partie (simulée
    d'avance) tombe sous la durée minimale d'une vidéo longue, on donne des vies en plus, puis on
    allonge un peu la durée visée, jusqu'à dépasser la minute. Le plan garde les retouches."""
    from dataclasses import replace

    from game import formats

    fmt = formats.resolve(seed, settings)
    long_video = settings.tiktok_rewards and (settings.target_duration <= 0
                                              or settings.target_duration >= settings.min_video_duration)
    if not (fmt.early_end and long_video):
        return settings
    for step in range(6):
        if simulated_seconds(seed, settings) >= settings.min_video_duration:
            break
        if step < 3:
            settings = replace(settings, extra_lives=settings.extra_lives + 2)
        else:
            settings = replace(settings, target_duration=max(settings.target_duration, 62.0) + 10)
    if settings.extra_lives:
        plan["extra_lives"] = settings.extra_lives
    if settings.target_duration:
        plan["target_duration"] = settings.target_duration
    return settings


def ensure_cup(settings: Settings, seed: int) -> dict | None:
    """Coupe en cours (créée si besoin, ou la suivante si la précédente est terminée)."""
    if not settings.cup:
        return None
    state = paintcup.load()
    if state is None or state.get("champion"):
        number = (state or {}).get("number", 0) + 1
        variant = settings.variant if settings.variant in variants.BY_KEY else "countries"
        state = paintcup.new_cup(variant, settings.cup_size, seed, number)
        paintcup.save(state)
    return state
