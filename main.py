"""Bataille de cubes 8-bit - générateur de vidéos TikTok.

  python main.py                       ouvre le panneau de contrôle
  python main.py --generate 5          génère 5 vidéos (seeds aléatoires)
  python main.py --generate 1 --seed 1234
  python main.py --preview [--seed 1234]
"""

import argparse
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")


def _generate(count: int, seed_text: str | None, machine: bool) -> int:
    from game import settings as cfg
    from output.exporter import export_video, output_dir, seeds_for_batch

    settings = cfg.load()
    # restes temporaires d'une génération annulée
    for pattern in ("*.tmp.mp4", "*.tmp.wav", "*.tmp.m4a", "*.ffmpeg.log"):
        for leftover in output_dir(settings).glob(pattern):
            try:
                leftover.unlink()
            except OSError:
                pass
    settings.seed = seed_text or ""   # seed uniquement si passée explicitement (--seed)
    seeds = seeds_for_batch(count, settings)

    def say(line: str) -> None:
        print(line, flush=True)

    errors = 0
    for i, seed in enumerate(seeds, 1):
        last_pct = [-1]

        def progress(frame, total, i=i):
            pct = int(frame * 100 / max(1, total))
            if machine:
                say(f"PROGRESS {i} {len(seeds)} {pct}")
            elif pct != last_pct[0] and pct % 10 == 0:
                say(f"  vidéo {i}/{len(seeds)} : {pct} %")
            last_pct[0] = pct

        if not machine:
            say(f"Vidéo {i}/{len(seeds)} - seed {seed}")
        try:
            res = export_video(seed, settings, progress=progress)
        except Exception as exc:  # on continue avec les vidéos suivantes
            errors += 1
            say(f"ERROR {seed} {exc!r}" if machine else f"  ERREUR : {exc}")
            continue
        if machine:
            say(f"DONE {i} {len(seeds)} {res.path}")
        else:
            say(f"  -> {res.path.name}  ({res.duration:.0f} s, {res.n_cubes} cubes, {res.summary})")
    return 1 if errors else 0


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Générateur de vidéos 'Bataille de cubes' 8-bit")
    parser.add_argument("--generate", type=int, metavar="X", help="génère X vidéos")
    parser.add_argument("--preview", action="store_true", help="aperçu temps réel (sans enregistrement)")
    parser.add_argument("--seed", help="seed à utiliser (sinon aléatoire)")
    parser.add_argument("--progress", action="store_true", help=argparse.SUPPRESS)  # sortie pour le panneau
    args = parser.parse_args(argv)

    if args.generate:
        return _generate(max(1, args.generate), args.seed, args.progress)
    if args.preview:
        from game import settings as cfg
        from output.exporter import parse_seed
        from output.preview import run_preview
        settings = cfg.load()
        seed = parse_seed(args.seed)
        run_preview(settings, seed)
        return 0
    from ui.control_panel import run_panel
    run_panel()
    return 0


if __name__ == "__main__":
    sys.exit(main())
