"""Vérifie des vidéos générées : format, durée, synchro audio/vidéo, niveau audio,
rendu pixel-perfect et différences entre vidéos.

    python tools/verify_video.py videos/combat_*.mp4
"""

import glob
import json
import re
import subprocess
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from engine8bit.display import FPS, LOGICAL_H, LOGICAL_W, OUTPUT_H, OUTPUT_W  # noqa: E402
from output.exporter import NO_WINDOW, ffmpeg_exe  # noqa: E402

SR = 48000


def _ff(args, binary=False):
    p = subprocess.run([ffmpeg_exe(), "-hide_banner", *args], capture_output=True, creationflags=NO_WINDOW)
    return p.stdout if binary else p.stderr.decode("utf-8", "replace")


def probe(path: Path) -> dict:
    info = _ff(["-i", str(path)])
    out = {}
    m = re.search(r"Duration: (\d+):(\d+):([\d.]+)", info)
    out["container_duration"] = int(m[1]) * 3600 + int(m[2]) * 60 + float(m[3]) if m else None
    v = re.search(r"Video: (\w+).*?, (\d+)x(\d+).*?, ([\d.]+) fps", info)
    if v:
        out.update(vcodec=v[1], width=int(v[2]), height=int(v[3]), fps=float(v[4]))
    a = re.search(r"Audio: (\w+).*?, (\d+) Hz, (\w+)", info)
    if a:
        out.update(acodec=a[1], sample_rate=int(a[2]), channels=a[3])
    meta = _ff(["-i", str(path), "-f", "ffmetadata", "-"], binary=True).decode("utf-8", "replace")
    for line in meta.splitlines():
        if line.startswith("comment="):
            raw = re.sub(r"\\(.)", r"\1", line[len("comment="):])
            try:
                out["meta"] = json.loads(raw)
            except json.JSONDecodeError:
                pass
    return out


def count_frames(path: Path) -> int:
    txt = _ff(["-i", str(path), "-map", "0:v:0", "-c", "copy", "-f", "null", "-"])
    found = re.findall(r"frame=\s*(\d+)", txt)
    return int(found[-1]) if found else 0


def decode_audio(path: Path) -> np.ndarray:
    """Audio décodé en flottant (les dépassements au-delà de 0 dBFS restent visibles) ; on garde,
    pour chaque instant, le canal le plus fort (pas de conversion mono, qui change le niveau)."""
    raw = _ff(["-i", str(path), "-map", "0:a:0", "-ar", str(SR), "-f", "f32le", "-"], binary=True)
    data = np.frombuffer(raw, dtype=np.float32).reshape(-1, 2)
    return data[np.arange(len(data)), np.abs(data).argmax(axis=1)]


def decode_small(path: Path, seconds: float, start: float = 0.0) -> np.ndarray:
    """Images réduites à la taille logique (moyenne de chaque bloc 8x8)."""
    vf = f"scale={LOGICAL_W}:{LOGICAL_H}:flags=area"
    raw = _ff(["-ss", f"{start}", "-i", str(path), "-t", f"{seconds}", "-vf", vf, "-f", "rawvideo",
               "-pix_fmt", "rgb24", "-"], binary=True)
    return np.frombuffer(raw, dtype=np.uint8).reshape(-1, LOGICAL_H, LOGICAL_W, 3)


def decode_full_frame(path: Path, t: float) -> np.ndarray:
    raw = _ff(["-ss", f"{t}", "-i", str(path), "-frames:v", "1", "-f", "rawvideo", "-pix_fmt", "rgb24", "-"],
              binary=True)
    return np.frombuffer(raw, dtype=np.uint8).reshape(OUTPUT_H, OUTPUT_W, 3)


def expected_frames(meta: dict) -> tuple[int, int]:
    """Re-simule la partie à partir de la seed et des réglages enregistrés dans le MP4."""
    from game.battle import Battle
    from game.settings import ITEM_KINDS, Settings
    data = dict(meta["settings"])
    for kind in ITEM_KINDS:   # vidéo d'une version antérieure : objets inexistants à l'époque
        data.setdefault(f"prob_{kind}", 0)
    data.setdefault("speed_ramp", 1.0)     # pas d'accélération progressive avant cette option
    data.setdefault("obstacles", 0)        # pas d'obstacles avant cette option
    data.setdefault("map", "generated")    # avant les cartes : obstacles placés au hasard
    data.setdefault("escalation", False)   # avant le mode escalade
    data.setdefault("death_shrink", False) # avant les cubes K.O. qui rapetissent
    data.setdefault("arena_centered", False)   # ancienne mise en page (arène dans la zone sûre)
    data.setdefault("lives", 0)                # pas de vies avant cette option
    for key, legacy in (("teaser", False), ("tiktok_rewards", False), ("comeback", 0.0), ("slowmo", False),
                        ("league", False)):
        data.setdefault(key, legacy)           # options de rétention absentes des anciennes vidéos
    b = Battle(int(meta["seed"]), Settings.from_dict(data))
    while not b.done:
        b.step()
    return b.total_frames, b.hourglasses_taken, b.battle_start


def onset(audio: np.ndarray, t0: float, t1: float) -> float:
    seg = np.abs(audio[int(t0 * SR):int(t1 * SR)])
    if not len(seg) or seg.max() <= 0:
        return float("nan")
    idx = int(np.argmax(seg > 0.25 * seg.max()))
    return t0 + idx / SR


def verify(path: Path) -> dict:
    path = Path(path)
    r = {"file": path.name, "checks": {}}
    info = probe(path)
    r["info"] = {k: v for k, v in info.items() if k != "meta"}
    c = r["checks"]
    c["résolution 1080x1920"] = (info.get("width"), info.get("height")) == (OUTPUT_W, OUTPUT_H)
    c["60 fps"] = abs(info.get("fps", 0) - FPS) < 0.01
    c["H.264 + AAC"] = info.get("vcodec") == "h264" and info.get("acodec") == "aac"

    frames = count_frames(path)
    vdur = frames / FPS
    audio = decode_audio(path)
    adur = len(audio) / SR
    r["video_duration"] = round(vdur, 3)
    r["audio_duration"] = round(adur, 3)
    c["durées audio = vidéo (±1 image)"] = abs(adur - vdur) <= 1 / FPS + 0.03

    meta = info.get("meta")
    if meta:
        exp, hg, go_frame_expected = expected_frames(meta)
        r["expected_duration"] = exp / FPS
        r["hourglasses"] = hg
        r["seed"] = meta["seed"]
        intro = go_frame_expected / FPS                # instant du « GO » (après teaser + 3-2-1)
        c[f"durée attendue ({exp / FPS:.0f} s, dont {hg} sablier(s))"] = frames == exp
        if meta["settings"].get("tiktok_rewards"):
            c["plus d'une minute (rémunération TikTok)"] = vdur > 60.0
    else:
        intro = 5.0
        c["métadonnées présentes"] = False

    peak = float(np.max(np.abs(audio))) if len(audio) else 0
    r["peak_dbfs"] = round(20 * np.log10(max(peak, 1e-9)), 2)
    c["pas de saturation (crête < 0 dBFS)"] = peak < 0.999

    # Synchro : bip du "GO" dans l'audio vs changement d'image "1" -> "GO !" dans la vidéo
    t_audio = onset(audio, intro - 0.4, intro + 0.4)
    small = decode_small(path, intro + 0.5)
    diffs = np.abs(small[1:].astype(np.int16) - small[:-1].astype(np.int16)).mean(axis=(1, 2, 3))
    lo, hi = int((intro - 0.4) * FPS), int((intro + 0.4) * FPS)
    go_frame = lo + 1 + int(np.argmax(diffs[lo:hi]))
    t_video = go_frame / FPS
    r["go_audio_s"] = round(t_audio, 4)
    r["go_video_s"] = round(t_video, 4)
    r["sync_offset_ms"] = round((t_audio - t_video) * 1000, 1)
    c["synchro audio/vidéo (écart < 1 image)"] = abs(t_audio - t_video) <= 1 / FPS + 0.002

    # Pixel-perfect : chaque bloc 8x8 doit être (quasi) uniforme
    full = decode_full_frame(path, min(30.0, vdur / 2)).astype(np.int16)
    blocks = full.reshape(LOGICAL_H, 8, LOGICAL_W, 8, 3)
    spread = (blocks.max(axis=(1, 3)) - blocks.min(axis=(1, 3))).max(axis=-1)
    r["blocs_8x8_uniformes_pct"] = round(float((spread <= 24).mean() * 100), 2)
    c["rendu pixel-perfect (blocs 8x8 nets)"] = r["blocs_8x8_uniformes_pct"] >= 97
    r["ok"] = all(c.values())
    return r


def compare(paths) -> dict:
    """Vérifie que les vidéos sont bien différentes (seed et contenu)."""
    frames = [decode_small(Path(p), 0.05, 20.0)[0].astype(np.int16) for p in paths]
    out = {}
    for i in range(len(paths)):
        for j in range(i + 1, len(paths)):
            out[f"{Path(paths[i]).name} vs {Path(paths[j]).name}"] = round(float(np.abs(frames[i] - frames[j]).mean()), 2)
    return out


def main(argv=None) -> int:
    argv = argv if argv is not None else sys.argv[1:]
    paths = []
    for a in argv:
        paths += glob.glob(a) or [a]
    if not paths:
        paths = sorted(glob.glob(str(ROOT / "videos" / "*.mp4")))
    missing = [p for p in paths if not Path(p).is_file()]
    for p in missing:
        print(f"Fichier introuvable : {p}")
    paths = [p for p in paths if Path(p).is_file()]
    if not paths:
        print("Aucune vidéo à vérifier.")
        return 1
    all_ok = True
    seeds = []
    for p in paths:
        r = verify(Path(p))
        seeds.append(r.get("seed"))
        all_ok &= r["ok"]
        print(f"\n=== {r['file']} ===")
        print(f"  seed {r.get('seed')} | vidéo {r['video_duration']} s | audio {r['audio_duration']} s | "
              f"crête {r['peak_dbfs']} dBFS | GO audio {r['go_audio_s']} s / vidéo {r['go_video_s']} s "
              f"(écart {r['sync_offset_ms']} ms) | blocs nets {r['blocs_8x8_uniformes_pct']} %")
        for name, ok in r["checks"].items():
            print(f"  [{'OK' if ok else 'ÉCHEC'}] {name}")
    if len(paths) > 1:
        print("\n=== Différences entre vidéos (image à 20 s, écart moyen par pixel) ===")
        distinct = len(set(seeds)) == len(seeds)
        print(f"  [{'OK' if distinct else 'ÉCHEC'}] seeds toutes différentes : {seeds}")
        all_ok &= distinct
        for k, v in compare(paths).items():
            ok = v > 5
            all_ok &= ok
            print(f"  [{'OK' if ok else 'ÉCHEC'}] {k} : {v}")
    print("\nRÉSULTAT GLOBAL :", "OK" if all_ok else "ÉCHEC")
    return 0 if all_ok else 1


if __name__ == "__main__":
    sys.exit(main())
