"""Bataille de cubes 8-bit - générateur de vidéos TikTok.

  python main.py                       demande quelle interface ouvrir
  python main.py --terminal            application terminal RIPaint
  python main.py --gui                 panneau de contrôle (fenêtre)
  python main.py --generate 5          génère 5 vidéos (seeds aléatoires)
  python main.py --generate 1 --seed 1234
  python main.py --generate 5 --all-random   partie et apparence tirées au hasard pour chaque vidéo
  python main.py --preview [--seed 1234]
  python main.py --week                prépare la semaine (vidéos + planning pour TikTok Studio)
  python main.py --week --start 2026-10-26 --days 7 --times "12:30,19:00"
"""

import argparse
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")


def _generate(count: int, seed_text: str | None, machine: bool, all_random: bool = False,
              week: dict | None = None) -> int:
    """Génère `count` vidéos. `week` : {"start", "days", "times"} -> une vidéo par créneau de
    publication, dans « videos/Semaine du … », avec planning.html / planning.csv."""
    from game import cup as paintcup
    from game import settings as cfg
    from game import variety
    from output import planning
    from output.exporter import (NO_WINDOW, ensure_cup, export_video, ffmpeg_exe, output_dir, plan_for,
                                 seeds_for_batch)

    try:
        sys.stdout.reconfigure(errors="replace")   # emojis des légendes dans une console Windows
    except (AttributeError, ValueError):
        pass
    settings = cfg.load()
    # restes temporaires d'une génération annulée
    for pattern in ("*.tmp.mp4", "*.tmp.wav", "*.tmp.m4a", "*.ffmpeg.log"):
        for leftover in output_dir(settings).glob(pattern):
            try:
                leftover.unlink()
            except OSError:
                pass
    if all_random:
        # « Tout aléatoire » : format, mode, joueurs, concurrents, thème, carte et musique tirés
        # pour chaque vidéo (avec le garde-fou), sans modifier les réglages enregistrés
        for key, value in variety.ALL_RANDOM.items():
            setattr(settings, key, value)
    settings.seed = seed_text or ""   # seed uniquement si passée explicitement (--seed)
    videos_dir = output_dir(settings)
    slots, target_dir, week_rows = [], videos_dir, []
    if week is not None:
        start = planning.parse_start(week.get("start", settings.week_start))
        slots = planning.week_slots(start, week.get("days", settings.week_days),
                                    week.get("times", settings.week_times))
        count = len(slots)
        target_dir = planning.week_folder(videos_dir, start)
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

        # garde-fou : historique des vidéos déjà faites -> choix de celle-ci ; PaintCup : prochain match
        history = variety.load_history()
        cup_state = ensure_cup(settings, seed)
        video_settings, plan, slot = plan_for(seed, settings, history, cup_state)
        if not machine:
            say(f"Vidéo {i}/{len(seeds)} - seed {seed}" + (f"  [{variety.describe(plan)}]" if plan else ""))
        try:
            res = export_video(seed, video_settings, out_dir=target_dir, progress=progress, plan=plan,
                               recent_captions=[v.get("caption_id") for v in history["videos"]],
                               cup_state=cup_state, cup_slot=slot)
        except Exception as exc:  # on continue avec les vidéos suivantes
            errors += 1
            say(f"ERROR {seed} {exc!r}" if machine else f"  ERREUR : {exc}")
            continue
        # seulement une fois la vidéo réussie : historique, coupe
        variety.save_history(variety.record(history, {**plan, "seed": seed, "caption_id": res.caption_id,
                                                      "duration": round(res.duration, 1)}))
        if cup_state is not None and slot is not None:
            paintcup.save(cup_state)
        # catalogue de toutes les vidéos (format, mode, thème… et la seed pour rejouer)
        when = slots[i - 1] if week is not None else None
        row = planning.catalogue_row(res, when)
        planning.append_catalogue(videos_dir, row)
        if week is not None:
            cover = target_dir / "_couvertures" / f"{i:02d}.jpg"
            if planning.make_cover(res.path, cover, ffmpeg_exe(), NO_WINDOW):
                row["_cover"] = f"_couvertures/{cover.name}"
            week_rows.append(row)
            planning.write_planning(target_dir, week_rows)       # à jour même si on annule en route
        if machine:
            say(f"DONE {i} {len(seeds)} {res.path}")
            say("RESULT " + json.dumps({"path": str(res.path), "seed": seed, "duration": res.duration,
                                        "cubes": res.n_cubes, "summary": res.summary,
                                        "mode": res.mode, "details": res.details, "caption": res.caption,
                                        "cup": plan.get("cup", "")}, ensure_ascii=False))
        else:
            say(f"  -> {res.path.name}  ({res.details}, {res.duration:.0f} s, {res.n_cubes} cubes, {res.summary})")
            say(f"     légende : {res.caption}")
    if week is not None and week_rows:
        page = target_dir / "planning.html"
        say(f"WEEK {page}" if machine else f"Planning de la semaine : {page}")
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
    parser.add_argument("--all-random", action="store_true",
                        help="partie et apparence tirées au hasard pour chaque vidéo")
    parser.add_argument("--week", action="store_true",
                        help="prépare la semaine : une vidéo par créneau + planning pour TikTok Studio")
    parser.add_argument("--start", help="premier jour de la semaine (AAAA-MM-JJ, défaut : demain)")
    parser.add_argument("--days", type=int, help="nombre de jours (TikTok Studio : 10 au maximum)")
    parser.add_argument("--times", help="heures de publication, ex. \"12:30,19:00\"")
    parser.add_argument("--progress", action="store_true", help=argparse.SUPPRESS)  # sortie pour l'interface
    ui = parser.add_mutually_exclusive_group()
    ui.add_argument("--terminal", action="store_true", help="ouvre l'application terminal")
    ui.add_argument("--gui", action="store_true", help="ouvre le panneau de contrôle (fenêtre)")
    args = parser.parse_args(argv)

    if args.week:
        week = {k: v for k, v in (("start", args.start), ("days", args.days), ("times", args.times))
                if v is not None}
        return _generate(0, args.seed, args.progress, args.all_random, week=week)
    if args.generate:
        return _generate(max(1, args.generate), args.seed, args.progress, args.all_random)
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
