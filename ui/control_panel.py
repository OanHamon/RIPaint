"""Panneau de contrôle : réglages, aperçu, génération en lot avec barre de progression.

L'aperçu et la génération tournent dans des processus séparés (python main.py ...),
ce qui garde le panneau réactif et évite tout conflit entre tkinter et pygame.
"""

import os
import queue
import subprocess
import sys
import threading
import tkinter as tk
from pathlib import Path
from tkinter import messagebox, ttk

from game import league
from game import settings as cfg
from game.maps import MAP_NAMES
from game.settings import ITEM_KINDS, ITEM_LABELS

ROOT = cfg.ROOT
MAIN = ROOT / "main.py"
NO_WINDOW = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0
PLAYER_CHOICES = {0: "Aléatoire (2 à 4)", 2: "2 joueurs", 3: "3 joueurs", 4: "4 joueurs"}
MAP_CHOICES = {"random": "Aléatoire (toutes)", **{name: name for name in MAP_NAMES},
               "generated": "Obstacles au hasard"}


def python_exe() -> str:
    exe = Path(sys.executable)
    if exe.name.lower() == "pythonw.exe":
        console = exe.with_name("python.exe")
        if console.exists():
            return str(console)
    return str(exe)


class ControlPanel:
    def __init__(self, root: tk.Tk):
        self.root = root
        self.s = cfg.load()
        self.proc: subprocess.Popen | None = None
        self.lines: queue.Queue = queue.Queue()
        self._save_job = None

        root.title("Bataille de cubes 8-bit - Panneau de contrôle")
        root.resizable(False, False)
        root.protocol("WM_DELETE_WINDOW", self.on_close)

        pad = {"padx": 8, "pady": 4}
        main = ttk.Frame(root, padding=10)
        main.grid(sticky="nsew")

        # --- Partie ---
        box = ttk.LabelFrame(main, text="Partie", padding=8)
        box.grid(row=0, column=0, sticky="ew", **pad)
        ttk.Label(box, text="Nombre de joueurs").grid(row=0, column=0, sticky="w")
        self.players = tk.StringVar(value=PLAYER_CHOICES[self.s.players if self.s.players in (2, 3, 4) else 0])
        combo = ttk.Combobox(box, textvariable=self.players, values=list(PLAYER_CHOICES.values()),
                             state="readonly", width=18)
        combo.grid(row=0, column=1, sticky="w", padx=6, pady=2)
        combo.bind("<<ComboboxSelected>>", lambda _e: self.on_change())
        self.cube_size = tk.IntVar(value=self.s.cube_size)
        self._spin(box, 1, "Taille des cubes (pixels)", self.cube_size, 5, 16, 1)
        self.speed_ramp = tk.DoubleVar(value=self.s.speed_ramp)
        self._spin(box, 2, "Vitesse à la fin (x)", self.speed_ramp, 1.0, 3.0, 0.1)
        ttk.Label(box, text="1.0 = vitesse constante ; 1.8 = 80 % plus rapide à la fin du chrono",
                  foreground="#666").grid(row=3, column=0, columnspan=2, sticky="w")
        ttk.Label(box, text="Carte").grid(row=6, column=0, sticky="w")
        self.map = tk.StringVar(value=MAP_CHOICES.get(self.s.map, MAP_CHOICES["random"]))
        mcombo = ttk.Combobox(box, textvariable=self.map, values=list(MAP_CHOICES.values()),
                              state="readonly", width=18)
        mcombo.grid(row=6, column=1, sticky="w", padx=6, pady=2)
        mcombo.bind("<<ComboboxSelected>>", lambda _e: self.on_change())
        self.obstacles = tk.IntVar(value=self.s.obstacles)
        self._spin(box, 4, "Obstacles (mode « au hasard »)", self.obstacles, 0, 4, 1)
        self.escalation = tk.BooleanVar(value=self.s.escalation)
        ttk.Checkbutton(box, text="Mode escalade : de plus en plus d'objets, de vitesse et d'impacts",
                        variable=self.escalation, command=self.on_change).grid(
            row=7, column=0, columnspan=2, sticky="w")
        self.lives = tk.IntVar(value=self.s.lives)
        self._spin(box, 5, "Vies par cube (0 = illimitées)", self.lives, 0, 5, 1)
        self.duel_lives = tk.IntVar(value=self.s.duel_lives)
        self._spin(box, 8, "Vies en duel (2 cubes)", self.duel_lives, 1, 6, 1)

        # --- Objets ---
        box = ttk.LabelFrame(main, text="Probabilité des objets", padding=8)
        box.grid(row=0, column=1, rowspan=2, sticky="new", **pad)
        self.prob_vars, self.pct_labels = {}, {}
        for r, kind in enumerate(ITEM_KINDS):
            var = tk.DoubleVar(value=getattr(self.s, f"prob_{kind}"))
            self.prob_vars[kind] = var
            ttk.Label(box, text=ITEM_LABELS[kind], width=13).grid(row=r, column=0, sticky="w")
            ttk.Scale(box, from_=0, to=100, variable=var, length=220,
                      command=lambda _v, k=kind: self._round(self.prob_vars[k])).grid(row=r, column=1, padx=6)
            lbl = ttk.Label(box, width=16)
            lbl.grid(row=r, column=2, sticky="w")
            self.pct_labels[kind] = lbl
            var.trace_add("write", lambda *_: self.on_change())

        # --- Rétention des spectateurs ---
        box = ttk.LabelFrame(main, text="Rétention (faire regarder jusqu'au bout)", padding=8)
        box.grid(row=2, column=1, rowspan=7, sticky="new", **pad)
        self.flags = {}
        options = [
            ("tiktok_rewards", "Toujours plus d'1 minute (rémunération TikTok)"),
            ("teaser", "Teaser : la fin montrée en ouverture, puis rembobinage"),
            ("hide_scores", "Cacher les % pendant les 5 dernières secondes"),
            ("comeback", "Coup de pouce au dernier (objets près de lui)"),
            ("lead_announce", "Annoncer les changements de leader"),
            ("slowmo", "Ralenti sur les K.O. et les explosions"),
            ("nicknames", "Surnoms des cubes (RED BLAZE…)"),
            ("league", "Ligue : classement des couleurs entre les vidéos"),
        ]
        values = {"hide_scores": self.s.hide_final_scores > 0, "comeback": self.s.comeback > 0}
        for r, (key, label) in enumerate(options):
            var = tk.BooleanVar(value=values.get(key, getattr(self.s, key, True)))
            self.flags[key] = var
            ttk.Checkbutton(box, text=label, variable=var, command=self.on_change).grid(
                row=r, column=0, columnspan=2, sticky="w")
        self.league_label = ttk.Label(box, foreground="#666")
        self.league_label.grid(row=len(options), column=0, sticky="w", pady=(4, 0))
        ttk.Button(box, text="Remettre la ligue à zéro", command=self.reset_league).grid(
            row=len(options), column=1, sticky="e", pady=(4, 0))
        self._refresh_league()

        # --- Apparition ---
        box = ttk.LabelFrame(main, text="Apparition des objets", padding=8)
        box.grid(row=2, column=0, sticky="ew", **pad)
        self.interval = tk.DoubleVar(value=self.s.item_interval)
        self.max_items = tk.IntVar(value=self.s.max_items)
        self.max_hourglasses = tk.IntVar(value=self.s.max_hourglasses)
        self._spin(box, 0, "Intervalle (secondes)", self.interval, 1, 30, 0.5)
        self._spin(box, 1, "Objets max en même temps", self.max_items, 1, 10, 1)
        self._spin(box, 2, "Sabliers max par partie", self.max_hourglasses, 0, 10, 1)

        # --- Audio ---
        box = ttk.LabelFrame(main, text="Son", padding=8)
        box.grid(row=3, column=0, sticky="ew", **pad)
        self.master = tk.DoubleVar(value=round(self.s.master_volume * 100))
        self.music = tk.DoubleVar(value=round(self.s.music_volume * 100))
        self.music_on = tk.BooleanVar(value=self.s.music_enabled)
        self.vol_labels = {}
        for r, (label, var) in enumerate((("Volume général", self.master), ("Volume musique", self.music))):
            ttk.Label(box, text=label, width=16).grid(row=r, column=0, sticky="w")
            ttk.Scale(box, from_=0, to=100, variable=var, length=200,
                      command=lambda _v, v=var: self._round(v)).grid(row=r, column=1, padx=6)
            lbl = ttk.Label(box, width=6)
            lbl.grid(row=r, column=2)
            self.vol_labels[label] = (lbl, var)
            var.trace_add("write", lambda *_: self.on_change())
        ttk.Checkbutton(box, text="Musique de fond", variable=self.music_on,
                        command=self.on_change).grid(row=2, column=0, columnspan=3, sticky="w")

        # --- Génération ---
        box = ttk.LabelFrame(main, text="Génération", padding=8)
        box.grid(row=4, column=0, sticky="ew", **pad)
        self.count = tk.IntVar(value=self.s.video_count)
        self.seed = tk.StringVar(value=self.s.seed)
        self.srt = tk.BooleanVar(value=self.s.export_srt)
        self._spin(box, 0, "Nombre de vidéos (X)", self.count, 1, 500, 1)
        ttk.Label(box, text="Seed (optionnelle)").grid(row=1, column=0, sticky="w")
        ttk.Entry(box, textvariable=self.seed, width=18).grid(row=1, column=1, sticky="w", padx=6, pady=2)
        self.seed.trace_add("write", lambda *_: self.on_change())
        ttk.Checkbutton(box, text="Exporter aussi les sous-titres (.srt, importables sur TikTok)", variable=self.srt,
                        command=self.on_change).grid(row=2, column=0, columnspan=2, sticky="w")
        self.caption = tk.StringVar(value=self.s.caption)
        self.hashtags = tk.StringVar(value=" ".join("#" + h.lstrip("#") for h in self.s.hashtags))
        ttk.Label(box, text="Légende TikTok").grid(row=3, column=0, sticky="w")
        ttk.Entry(box, textvariable=self.caption, width=34).grid(row=3, column=1, sticky="w", padx=6, pady=2)
        ttk.Label(box, text="Hashtags").grid(row=4, column=0, sticky="w")
        ttk.Entry(box, textvariable=self.hashtags, width=34).grid(row=4, column=1, sticky="w", padx=6, pady=2)
        for var in (self.caption, self.hashtags):
            var.trace_add("write", lambda *_: self.on_change())

        # --- Boutons ---
        bar = ttk.Frame(main)
        bar.grid(row=5, column=0, sticky="ew", **pad)
        self.btn_preview = ttk.Button(bar, text="Aperçu", command=self.preview)
        self.btn_preview.pack(side="left")
        self.btn_generate = ttk.Button(bar, text="Générer", command=self.generate)
        self.btn_generate.pack(side="left", padx=6)
        self.btn_cancel = ttk.Button(bar, text="Annuler", command=self.cancel, state="disabled")
        self.btn_cancel.pack(side="left")

        self.progress = ttk.Progressbar(main, length=380, maximum=100)
        self.progress.grid(row=6, column=0, sticky="ew", **pad)
        self.status = ttk.Label(main, text="Prêt.", wraplength=380)
        self.status.grid(row=7, column=0, sticky="w", **pad)

        bar2 = ttk.Frame(main)
        bar2.grid(row=8, column=0, sticky="ew", **pad)
        ttk.Button(bar2, text="Ouvrir le dossier des vidéos", command=self.open_folder).pack(side="left")
        ttk.Button(bar2, text="Réglages avancés…", command=self.open_config).pack(side="left", padx=6)

        for var in (self.interval, self.max_items, self.max_hourglasses, self.count, self.cube_size,
                    self.speed_ramp, self.obstacles, self.lives, self.duel_lives):
            var.trace_add("write", lambda *_: self.on_change())
        self.on_change(save=False)

    # ---- Widgets utilitaires -------------------------------------------------------------

    def _spin(self, parent, row, label, var, lo, hi, inc):
        ttk.Label(parent, text=label).grid(row=row, column=0, sticky="w")
        ttk.Spinbox(parent, from_=lo, to=hi, increment=inc, textvariable=var, width=8).grid(
            row=row, column=1, sticky="w", padx=6, pady=2)

    @staticmethod
    def _round(var):
        v = round(var.get())
        if v != var.get():
            var.set(v)

    @staticmethod
    def _get(var, default):
        try:
            return var.get()
        except (tk.TclError, ValueError):
            return default

    # ---- Réglages ------------------------------------------------------------------------

    def collect(self) -> cfg.Settings:
        s = self.s
        label = self.players.get()
        s.players = next((n for n, text in PLAYER_CHOICES.items() if text == label), 0)
        s.cube_size = min(16, max(5, int(self._get(self.cube_size, s.cube_size))))
        f = {k: bool(v.get()) for k, v in self.flags.items()}
        s.tiktok_rewards = f["tiktok_rewards"]
        s.teaser = f["teaser"]
        s.hide_final_scores = 5.0 if f["hide_scores"] else 0.0
        s.comeback = 0.5 if f["comeback"] else 0.0
        s.lead_announce = f["lead_announce"]
        s.slowmo = f["slowmo"]
        s.nicknames = f["nicknames"]
        s.league = f["league"]
        s.duel_lives = min(6, max(1, int(self._get(self.duel_lives, s.duel_lives))))
        s.lives = min(5, max(0, int(self._get(self.lives, s.lives))))
        s.obstacles = min(4, max(0, int(self._get(self.obstacles, s.obstacles))))
        label = self.map.get()
        s.map = next((k for k, v in MAP_CHOICES.items() if v == label), "random")
        s.escalation = bool(self.escalation.get())
        s.speed_ramp = round(min(3.0, max(1.0, float(self._get(self.speed_ramp, s.speed_ramp)))), 2)
        for kind, var in self.prob_vars.items():
            setattr(s, f"prob_{kind}", float(round(self._get(var, 0))))
        s.item_interval = max(0.5, float(self._get(self.interval, s.item_interval)))
        s.max_items = max(1, int(self._get(self.max_items, s.max_items)))
        s.max_hourglasses = max(0, int(self._get(self.max_hourglasses, s.max_hourglasses)))
        s.master_volume = self._get(self.master, 90) / 100
        s.music_volume = self._get(self.music, 60) / 100
        s.music_enabled = bool(self.music_on.get())
        s.video_count = max(1, int(self._get(self.count, 1)))
        s.seed = self.seed.get().strip()
        s.export_srt = bool(self.srt.get())
        s.caption = self.caption.get().strip()
        s.hashtags = [h.lstrip("#") for h in self.hashtags.get().replace(",", " ").split() if h.lstrip("#")]
        return s

    def on_change(self, save: bool = True):
        s = self.collect()
        pcts = s.item_percentages()
        for kind, lbl in self.pct_labels.items():
            w = s.item_weights()[kind]
            if w <= 0:
                lbl.config(text="jamais")
            else:
                lbl.config(text=f"{pcts[kind]:.1f} % réel")
        for lbl, var in self.vol_labels.values():
            lbl.config(text=f"{round(self._get(var, 0))} %")
        if save:
            if self._save_job:
                self.root.after_cancel(self._save_job)
            self._save_job = self.root.after(400, self.save)

    def save(self):
        self._save_job = None
        try:
            cfg.save(self.collect())
        except OSError as exc:
            self.status.config(text=f"Impossible d'enregistrer la config : {exc}")

    # ---- Actions -------------------------------------------------------------------------

    def preview(self):
        self.save()
        cmd = [python_exe(), str(MAIN), "--preview"]
        seed = self.seed.get().strip()
        if seed:
            cmd += ["--seed", seed]
        subprocess.Popen(cmd, cwd=str(ROOT), creationflags=NO_WINDOW)
        self.status.config(text="Aperçu lancé (ÉCHAP pour fermer, R pour une nouvelle partie).")

    def generate(self):
        if self.proc is not None:
            return
        self.save()
        s = self.s
        cmd = [python_exe(), str(MAIN), "--generate", str(s.video_count), "--progress"]
        if s.seed:
            cmd += ["--seed", s.seed]
        env = dict(os.environ, PYTHONIOENCODING="utf-8", PYTHONUNBUFFERED="1")
        self.proc = subprocess.Popen(cmd, cwd=str(ROOT), stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                     text=True, encoding="utf-8", errors="replace", env=env,
                                     creationflags=NO_WINDOW)
        self.total = s.video_count
        self.done_paths: list[str] = []
        self.errors: list[str] = []
        self.progress["value"] = 0
        self.status.config(text=f"Vidéo 1 / {self.total} : démarrage…")
        self.btn_generate.config(state="disabled")
        self.btn_cancel.config(state="normal")
        threading.Thread(target=self._reader, args=(self.proc,), daemon=True).start()
        self.root.after(100, self._poll)

    def _reader(self, proc):
        for line in proc.stdout:
            self.lines.put(line.rstrip("\n"))
        proc.wait()
        self.lines.put(None)

    def _poll(self):
        finished = False
        while True:
            try:
                line = self.lines.get_nowait()
            except queue.Empty:
                break
            if line is None:
                finished = True
                break
            parts = line.split(" ", 3)
            if parts[0] == "PROGRESS" and len(parts) == 4:
                i, n, pct = int(parts[1]), int(parts[2]), int(parts[3])
                self.progress["value"] = ((i - 1) + pct / 100) / n * 100
                self.status.config(text=f"Vidéo {i} / {n} : {pct} %")
            elif parts[0] == "DONE" and len(parts) == 4:
                self.done_paths.append(parts[3])
            elif parts[0] == "ERROR":
                self.errors.append(line)
            elif line.strip() and "Traceback" in line:
                self.errors.append(line)
        if finished:
            self._finished()
        else:
            self.root.after(100, self._poll)

    def _finished(self):
        cancelled = getattr(self, "_cancelled", False)
        self._cancelled = False
        self.proc = None
        self.btn_generate.config(state="normal")
        self.btn_cancel.config(state="disabled")
        n = len(self.done_paths)
        self._refresh_league()
        if cancelled:
            self.status.config(text=f"Génération annulée ({n} vidéo(s) terminée(s)).")
        elif self.errors:
            self.status.config(text=f"{n} vidéo(s) générée(s), {len(self.errors)} erreur(s) : {self.errors[0][:200]}")
        else:
            self.progress["value"] = 100
            self.status.config(text=f"Terminé : {n} vidéo(s) dans le dossier « {self.s.output_dir} ».")

    def _refresh_league(self):
        data = league.load()
        if data["day"] == 0:
            self.league_label.config(text="Ligue : aucune journée jouée")
        else:
            team, wins = league.standings(data)[0]
            self.league_label.config(text=f"Ligue : jour {data['day']}, en tête {team} ({wins} V)")

    def reset_league(self):
        if messagebox.askyesno("Ligue", "Remettre le classement de la ligue à zéro (jour 0) ?"):
            league.reset()
            self._refresh_league()

    def cancel(self):
        if self.proc is not None:
            self._cancelled = True
            self.proc.terminate()

    def open_folder(self):
        d = Path(self.s.output_dir)
        if not d.is_absolute():
            d = ROOT / d
        d.mkdir(parents=True, exist_ok=True)
        os.startfile(str(d)) if os.name == "nt" else subprocess.Popen(["xdg-open", str(d)])

    def open_config(self):
        self.save()
        messagebox.showinfo("Réglages avancés",
                            "Le fichier config.json va s'ouvrir.\n\nVous pouvez y modifier les phrases "
                            "d'accroche (hooks), les zones de sécurité, les durées, la vitesse des cubes…\n"
                            "Fermez puis rouvrez le panneau après modification.")
        if os.name == "nt":
            os.startfile(str(cfg.CONFIG_PATH))

    def on_close(self):
        if self.proc is not None:
            if not messagebox.askyesno("Génération en cours", "Une génération est en cours. L'annuler et quitter ?"):
                return
            self.proc.terminate()
        self.save()
        self.root.destroy()


def run_panel():
    root = tk.Tk()
    ControlPanel(root)
    root.mainloop()
