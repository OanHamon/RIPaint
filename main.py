"""Bataille de cubes 8-bit - générateur de vidéos TikTok.

  python main.py                       demande quelle interface ouvrir
  python main.py --terminal            application terminal RIPaint
  python main.py --gui                 panneau de contrôle (fenêtre)
  python main.py --generate 5          génère 5 vidéos (seeds aléatoires)
  python main.py --generate 1 --seed 1234
  python main.py --preview [--seed 1234]
"""

import argparse
import json
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
            say("RESULT " + json.dumps({"path": str(res.path), "seed": seed, "duration": res.duration,
                                        "cubes": res.n_cubes, "summary": res.summary}, ensure_ascii=False))
        else:
            say(f"  -> {res.path.name}  ({res.duration:.0f} s, {res.n_cubes} cubes, {res.summary})")
    return 1 if errors else 0


def _ask_interface() -> str:
    """Petit menu au lancement : 'terminal' ou 'gui'. Sans console (pythonw) : fenêtre."""
    if sys.stdin is None or not sys.stdin.isatty():
        return "gui" if sys.stdout is None else "terminal"
    from rich.console import Console
    console = Console(highlight=False)
    console.print()
    console.print("  [bold #f83800]R[/][bold #0078f8]I[/][bold #f8b800]P[/][bold #00b800]a[/]"
                  "[bold #f83800]i[/][bold #0078f8]n[/][bold #f8b800]t[/]  [#7c7c7c]· choisis ton interface[/]")
    console.print()
    console.print("  [bold #080828 on #f8b800] 1 [/]  Terminal   [#7c7c7c]application plein écran dans ce terminal (par défaut)[/]")
    console.print("  [bold #080828 on #bcbcbc] 2 [/]  Fenêtre    [#7c7c7c]panneau de contrôle classique[/]")
    console.print()
    while True:
        try:
            answer = console.input("  [#f8b800]›[/] Choix [1/2] : ").strip().lower()
        except (EOFError, KeyboardInterrupt):
            return "quit"
        if answer in ("", "1", "t", "terminal"):
            return "terminal"
        if answer in ("2", "f", "g", "gui", "fenetre", "fenêtre", "ui"):
            return "gui"


def _open_gui() -> None:
    """Ouvre le panneau tkinter ; depuis une console Windows, il est détaché (la console se ferme)."""
    pythonw = Path(sys.executable).with_name("pythonw.exe")
    if os.name == "nt" and sys.stdout is not None and pythonw.exists():
        import subprocess
        subprocess.Popen([str(pythonw), str(ROOT / "main.py"), "--gui"], cwd=str(ROOT),
                         creationflags=subprocess.DETACHED_PROCESS)
        return
    from ui.control_panel import run_panel
    run_panel()


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Générateur de vidéos 'Bataille de cubes' 8-bit")
    parser.add_argument("--generate", type=int, metavar="X", help="génère X vidéos")
    parser.add_argument("--preview", action="store_true", help="aperçu temps réel (sans enregistrement)")
    parser.add_argument("--seed", help="seed à utiliser (sinon aléatoire)")
    parser.add_argument("--progress", action="store_true", help=argparse.SUPPRESS)  # sortie pour l'interface
    ui = parser.add_mutually_exclusive_group()
    ui.add_argument("--terminal", action="store_true", help="ouvre l'application terminal")
    ui.add_argument("--gui", action="store_true", help="ouvre le panneau de contrôle (fenêtre)")
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
    if args.gui:
        from ui.control_panel import run_panel
        run_panel()
        return 0
    choice = "terminal" if args.terminal else _ask_interface()
    if choice == "gui":
        _open_gui()
    elif choice == "terminal":
        from ui.app import run_app
        run_app()
    return 0


if __name__ == "__main__":
    sys.exit(main())
