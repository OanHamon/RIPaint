"""Panneau de contrôle (fenêtre) : thème sombre, une page par sujet, la génération toujours visible.

Pages : Vidéo (ce qui s'affronte et comment), Variété (garde-fou anti-répétition, durées,
légendes, rétention), PaintCup (tournoi), Objets (probabilités, apparition, réglages fins),
Son & export. En bas : nombre de vidéos, Générer, Aperçu, progression et journal.

L'aperçu et la génération tournent dans des processus séparés (python main.py ...),
ce qui garde le panneau réactif et évite tout conflit entre tkinter et pygame.
"""

import json
import os
import queue
import subprocess
import sys
import threading
import tkinter as tk
from pathlib import Path
from tkinter import messagebox, ttk

from audio import music
from game import cup as paintcup
from game import formats, league, modes, themes, variants, variety
from game import settings as cfg
from game.maps import MAP_NAMES
from game.settings import ITEM_KINDS, ITEM_LABELS

ROOT = cfg.ROOT
MAIN = ROOT / "main.py"
NO_WINDOW = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0
PLAYER_CHOICES = {0: "Aléatoire (2 à 4)", 2: "2 joueurs", 3: "3 joueurs", 4: "4 joueurs"}
MAP_CHOICES = {"random": "Aléatoire (toutes)", **{name: name for name in MAP_NAMES},
               "generated": "Obstacles au hasard"}

# Couleurs du thème sombre (reprises de la palette du jeu)
BG = "#11131a"
SIDEBAR = "#0b0d13"
CARD = "#1a1e29"
CARD_HI = "#232838"
LINE = "#2c3245"
TEXT = "#e9ebf3"
MUTED = "#8b91a8"
ACCENT = "#f8b800"
ACCENT_HI = "#ffd24d"
GREEN = "#58d854"
RED = "#f83800"
BLUE = "#3cbcfc"
LOGO = [("R", "#f83800"), ("I", "#0078f8"), ("P", "#f8b800"), ("a", "#00b800"), ("i", "#f83800"),
        ("n", "#0078f8"), ("t", "#f8b800")]
FONT = ("Segoe UI", 10)
FONT_SMALL = ("Segoe UI", 9)
FONT_BOLD = ("Segoe UI Semibold", 10)
FONT_TITLE = ("Segoe UI Semibold", 13)
FONT_LOGO = ("Segoe UI Black", 22)

PAGES = [("video", "🎬  Vidéo"), ("variety", "🎲  Variété"), ("cup", "🏆  PaintCup"),
         ("items", "🧰  Objets"), ("sound", "🔊  Son & export")]


SCALE = 1.0          # facteur d'affichage Windows (125 %, 150 %…), fixé par run_panel


def px(n: float) -> int:
    """Taille en pixels adaptée au facteur d'affichage (les polices, en points, le sont déjà)."""
    return int(round(n * SCALE))


def pretty(name: str) -> str:
    """« FRANCE » -> « France » ; les sigles courts restent en majuscules (USA, UK)."""
    return name if len(name) <= 3 else name.title()


def round_fr(name: str) -> str:
    """Nom d'un tour de la PaintCup en français (la vidéo garde l'anglais)."""
    if name == "FINAL":
        return "Finale"
    if name == "SEMI-FINAL":
        return "Demi-finales"
    if name.startswith("ROUND OF "):
        return f"1er tour ({name[9:]} cubes)"
    return name.title()


def python_exe() -> str:
    exe = Path(sys.executable)
    if exe.name.lower() == "pythonw.exe":
        console = exe.with_name("python.exe")
        if console.exists():
            return str(console)
    return str(exe)


def init_scale(root: tk.Tk) -> None:
    global SCALE
    SCALE = max(1.0, root.winfo_fpixels("1i") / 96)


def setup_style(root: tk.Tk) -> None:
    style = ttk.Style(root)
    style.theme_use("clam")
    root.configure(bg=BG)
    style.configure(".", background=BG, foreground=TEXT, fieldbackground=CARD_HI, bordercolor=LINE,
                    lightcolor=CARD, darkcolor=CARD, troughcolor=CARD_HI, focuscolor=ACCENT, font=FONT)
    style.configure("Card.TFrame", background=CARD)
    style.configure("TFrame", background=BG)
    style.configure("TLabel", background=CARD, foreground=TEXT)
    style.configure("Muted.TLabel", background=CARD, foreground=MUTED, font=FONT_SMALL)
    style.configure("Title.TLabel", background=BG, foreground=TEXT, font=FONT_TITLE)
    style.configure("Sub.TLabel", background=BG, foreground=MUTED, font=FONT_SMALL)
    style.configure("Bar.TLabel", background=SIDEBAR, foreground=MUTED, font=FONT_SMALL)
    style.configure("TCheckbutton", background=CARD, foreground=TEXT, indicatorbackground=CARD_HI,
                    indicatorforeground=ACCENT, focuscolor=CARD)
    style.map("TCheckbutton", background=[("active", CARD)], indicatorbackground=[("selected", ACCENT)],
              indicatorforeground=[("selected", BG)])
    style.configure("TCombobox", fieldbackground=CARD_HI, background=CARD_HI, foreground=TEXT, arrowcolor=ACCENT,
                    bordercolor=LINE, padding=4)
    style.map("TCombobox", fieldbackground=[("readonly", CARD_HI)], foreground=[("readonly", TEXT)],
              selectbackground=[("readonly", CARD_HI)], selectforeground=[("readonly", TEXT)])
    style.configure("TSpinbox", fieldbackground=CARD_HI, background=CARD_HI, foreground=TEXT, arrowcolor=ACCENT,
                    bordercolor=LINE, padding=3)
    style.configure("TEntry", fieldbackground=CARD_HI, foreground=TEXT, bordercolor=LINE, padding=4,
                    insertcolor=TEXT)
    style.configure("Horizontal.TScale", background=ACCENT, troughcolor=CARD_HI, bordercolor=CARD,
                    lightcolor=ACCENT, darkcolor=ACCENT_HI, sliderlength=px(16))
    style.map("Horizontal.TScale", background=[("active", ACCENT_HI)])
    style.configure("Vertical.TScrollbar", background=CARD_HI, troughcolor=BG, bordercolor=BG, arrowcolor=MUTED,
                    lightcolor=CARD_HI, darkcolor=CARD_HI)
    style.configure("Horizontal.TProgressbar", background=ACCENT, troughcolor=CARD_HI, bordercolor=SIDEBAR,
                    lightcolor=ACCENT, darkcolor=ACCENT, thickness=10)
    style.configure("Treeview", background=CARD_HI, fieldbackground=CARD_HI, foreground=TEXT, bordercolor=LINE,
                    rowheight=22)
    style.configure("Treeview.Heading", background=CARD, foreground=MUTED, bordercolor=LINE, relief="flat")
    style.map("Treeview", background=[("selected", LINE)])
    # classement de la PaintCup : grandes lignes lisibles
    style.configure("Cup.Treeview", background=CARD_HI, fieldbackground=CARD_HI, foreground=TEXT,
                    font=("Segoe UI", 11), rowheight=px(30), borderwidth=0)
    style.configure("Cup.Treeview.Heading", background=CARD, foreground=ACCENT, font=("Segoe UI Semibold", 10),
                    relief="flat", padding=(px(6), px(6)))
    style.map("Cup.Treeview.Heading", background=[("active", CARD)])
    root.option_add("*TCombobox*Listbox.background", CARD_HI)
    root.option_add("*TCombobox*Listbox.foreground", TEXT)
    root.option_add("*TCombobox*Listbox.selectBackground", ACCENT)
    root.option_add("*TCombobox*Listbox.selectForeground", BG)
    root.option_add("*TCombobox*Listbox.font", FONT)


class FlatButton(tk.Label):
    """Bouton plat (couleurs du thème, survol), sans les bordures grises de Windows."""

    def __init__(self, parent, text, command, bg=CARD_HI, fg=TEXT, hover=LINE, font=FONT_BOLD, padx=14, pady=7):
        super().__init__(parent, text=text, bg=bg, fg=fg, font=font, padx=padx, pady=pady, cursor="hand2")
        self.colors = (bg, fg, hover)
        self.command = command
        self.enabled = True
        self.bind("<Button-1>", lambda _e: self.enabled and self.command())
        self.bind("<Enter>", lambda _e: self.enabled and self.config(bg=self.colors[2]))
        self.bind("<Leave>", lambda _e: self.config(bg=self.colors[0]))

    def set_enabled(self, enabled: bool):
        self.enabled = enabled
        bg, fg, _ = self.colors
        self.config(fg=fg if enabled else MUTED, bg=bg, cursor="hand2" if enabled else "arrow")


class Switch(tk.Frame):
    """Interrupteur (pastille qui glisse) + libellé : plus lisible qu'une petite case à cocher."""

    def __init__(self, parent, text, variable: tk.BooleanVar, command=None, bg=CARD):
        super().__init__(parent, bg=bg, cursor="hand2")
        self.var, self.command = variable, command
        w, h = px(34), px(18)
        self.canvas = tk.Canvas(self, width=w, height=h, bg=bg, highlightthickness=0, cursor="hand2")
        self.canvas.pack(side="left", padx=(0, px(8)))
        self.label = tk.Label(self, text=text, bg=bg, fg=TEXT, font=FONT, cursor="hand2")
        self.label.pack(side="left")
        for widget in (self, self.canvas, self.label):
            widget.bind("<Button-1>", self.toggle)
        variable.trace_add("write", lambda *_: self.draw())
        self.draw()

    def toggle(self, _event=None):
        self.var.set(not self.var.get())
        if self.command:
            self.command()

    def draw(self):
        c = self.canvas
        c.delete("all")
        w, h = int(c["width"]), int(c["height"])
        on = bool(self.var.get())
        fill = ACCENT if on else LINE
        r = h // 2
        c.create_oval(0, 0, h, h, fill=fill, outline=fill)
        c.create_oval(w - h, 0, w, h, fill=fill, outline=fill)
        c.create_rectangle(r, 0, w - r, h, fill=fill, outline=fill)
        x = w - h + 2 if on else 2
        c.create_oval(x, 2, x + h - 4, h - 2, fill=BG if on else MUTED, outline="")


class ScrollPage(ttk.Frame):
    """Page qui défile à la molette si elle dépasse la fenêtre (petits écrans, affichage 150 %)."""

    def __init__(self, parent):
        super().__init__(parent)
        self.canvas = tk.Canvas(self, bg=BG, highlightthickness=0)
        self.bar = ttk.Scrollbar(self, orient="vertical", command=self.canvas.yview)
        self.inner = ttk.Frame(self.canvas)
        self.window = self.canvas.create_window(0, 0, window=self.inner, anchor="nw")
        self.canvas.configure(yscrollcommand=self.bar.set)
        self.canvas.pack(side="left", fill="both", expand=True)
        self.bar.pack(side="right", fill="y")
        self.inner.bind("<Configure>", lambda _e: self.canvas.configure(scrollregion=self.canvas.bbox("all")))
        self.canvas.bind("<Configure>", lambda e: self.canvas.itemconfigure(self.window, width=e.width))
        self.canvas.bind("<Enter>", lambda _e: self.canvas.bind_all("<MouseWheel>", self._wheel))
        self.canvas.bind("<Leave>", lambda _e: self.canvas.unbind_all("<MouseWheel>"))

    def _wheel(self, event):
        if self.inner.winfo_height() > self.canvas.winfo_height():
            self.canvas.yview_scroll(int(-event.delta / 120), "units")


class ControlPanel:
    def __init__(self, root: tk.Tk):
        self.root = root
        self.s = cfg.load()
        self.proc: subprocess.Popen | None = None
        self.lines: queue.Queue = queue.Queue()
        self._save_job = None
        self._cancelled = False

        root.title("RIPaint - Bataille de cubes 8-bit")
        w = min(px(1080), int(root.winfo_screenwidth() * 0.94))
        h = min(px(760), int(root.winfo_screenheight() * 0.88))
        root.geometry(f"{w}x{h}")
        root.minsize(min(w, px(860)), min(h, px(600)))
        root.protocol("WM_DELETE_WINDOW", self.on_close)
        setup_style(root)

        root.columnconfigure(1, weight=1)
        root.rowconfigure(0, weight=1)
        self._sidebar()
        self.content = ttk.Frame(root, padding=(px(22), px(18), px(10), px(8)))
        self.content.grid(row=0, column=1, sticky="nsew")
        self.content.columnconfigure(0, weight=1)
        self.content.rowconfigure(1, weight=1)
        self._action_bar()

        self.pages = {}
        builders = {"video": self._page_video, "variety": self._page_variety, "cup": self._page_cup,
                    "items": self._page_items, "sound": self._page_sound}
        for key, _ in PAGES:
            frame = ScrollPage(self.content)
            builders[key](frame.inner)
            self.pages[key] = frame
        self.show("video")
        self.on_change(save=False)

    # ---- Structure -----------------------------------------------------------------------

    def _sidebar(self):
        side = tk.Frame(self.root, bg=SIDEBAR, width=px(210))
        side.grid(row=0, column=0, rowspan=2, sticky="nsw")
        side.grid_propagate(False)
        logo = tk.Frame(side, bg=SIDEBAR)
        logo.pack(anchor="w", padx=20, pady=(22, 0))
        for ch, color in LOGO:
            tk.Label(logo, text=ch, fg=color, bg=SIDEBAR, font=FONT_LOGO).pack(side="left")
        tk.Label(side, text="vidéos TikTok de batailles\nde cubes 8-bit", fg=MUTED, bg=SIDEBAR, font=FONT_SMALL,
                 justify="left").pack(anchor="w", padx=22, pady=(0, 22))
        self.nav = {}
        for key, label in PAGES:
            btn = tk.Label(side, text=label, anchor="w", fg=MUTED, bg=SIDEBAR, font=("Segoe UI Semibold", 11),
                           padx=22, pady=10, cursor="hand2")
            btn.pack(fill="x")
            btn.bind("<Button-1>", lambda _e, k=key: self.show(k))
            self.nav[key] = btn
        self.side_info = tk.Label(side, text="", fg=MUTED, bg=SIDEBAR, font=FONT_SMALL, justify="left",
                                  wraplength=px(170))
        self.side_info.pack(side="bottom", anchor="w", padx=20, pady=16)

    def show(self, key: str):
        for k, frame in self.pages.items():
            frame.grid_forget()
        self.pages[key].grid(row=1, column=0, sticky="nsew")
        for k, btn in self.nav.items():
            active = k == key
            btn.config(fg=ACCENT if active else MUTED, bg=CARD if active else SIDEBAR)
        if key == "cup":
            self._refresh_cup()
        if key == "variety":
            self._refresh_history()

    def _header(self, parent, title: str, subtitle: str):
        ttk.Label(parent, text=title, style="Title.TLabel").pack(anchor="w")
        ttk.Label(parent, text=subtitle, style="Sub.TLabel", wraplength=px(760), justify="left").pack(
            anchor="w", pady=(0, px(12)))

    def _card(self, parent, title: str | None = None, side: str | None = None) -> ttk.Frame:
        outer = ttk.Frame(parent, style="Card.TFrame", padding=(px(16), px(12)))
        if side:
            outer.pack(side=side, fill="both", expand=True, padx=(0, px(12)) if side == "left" else 0,
                       pady=(0, px(12)))
        else:
            outer.pack(fill="x", pady=(0, px(12)))
        if title:
            ttk.Label(outer, text=title.upper(), foreground=ACCENT, font=("Segoe UI Semibold", 9)).grid(
                row=0, column=0, columnspan=3, sticky="w", pady=(0, 8))
        outer.columnconfigure(2, weight=1)
        return outer

    def _row_combo(self, card, row, label, choices: dict, value, help_text: str = "", width=26):
        ttk.Label(card, text=label).grid(row=row, column=0, sticky="w", pady=5, padx=(0, 14))
        var = tk.StringVar(value=choices.get(value, next(iter(choices.values()))))
        combo = ttk.Combobox(card, textvariable=var, values=list(choices.values()), state="readonly", width=width)
        combo.grid(row=row, column=1, sticky="w", pady=5)
        combo.bind("<<ComboboxSelected>>", lambda _e: self.on_change())
        info = ttk.Label(card, text=help_text, style="Muted.TLabel", wraplength=px(360), justify="left")
        info.grid(row=row, column=2, sticky="w", padx=(14, 0))
        return var, info

    def _row_spin(self, card, row, label, var, lo, hi, inc, help_text=""):
        ttk.Label(card, text=label).grid(row=row, column=0, sticky="w", pady=4, padx=(0, 14))
        ttk.Spinbox(card, from_=lo, to=hi, increment=inc, textvariable=var, width=8).grid(
            row=row, column=1, sticky="w", pady=4)
        if help_text:
            ttk.Label(card, text=help_text, style="Muted.TLabel").grid(row=row, column=2, sticky="w", padx=(14, 0))
        var.trace_add("write", lambda *_: self.on_change())

    def _check(self, card, row, label, var, help_text=""):
        Switch(card, label, var, self.on_change).grid(row=row, column=0, columnspan=2, sticky="w", pady=px(4))
        if help_text:
            ttk.Label(card, text=help_text, style="Muted.TLabel", wraplength=px(360), justify="left").grid(
                row=row, column=2, sticky="w", padx=(px(14), 0))

    def _action_bar(self):
        bar = tk.Frame(self.root, bg=SIDEBAR)
        bar.grid(row=1, column=1, sticky="ew")
        bar.columnconfigure(4, weight=1)
        tk.Label(bar, text="Vidéos à générer", fg=MUTED, bg=SIDEBAR, font=FONT_SMALL).grid(
            row=0, column=0, padx=(22, 6), pady=(14, 4), sticky="w")
        self.count = tk.IntVar(value=self.s.video_count)
        spin = ttk.Spinbox(bar, from_=1, to=500, increment=1, textvariable=self.count, width=6)
        spin.grid(row=1, column=0, padx=(22, 6), pady=(0, 14), sticky="w")
        self.count.trace_add("write", lambda *_: self.on_change())
        self.btn_generate = FlatButton(bar, "▶  GÉNÉRER", self.generate, bg=ACCENT, fg=BG, hover=ACCENT_HI,
                                       font=("Segoe UI Black", 11), padx=22, pady=9)
        self.btn_generate.grid(row=0, column=1, rowspan=2, padx=6)
        # même génération, mais partie et apparence tirées au hasard pour chaque vidéo
        # (format, mode, joueurs, concurrents, thème, carte, musique), réglages enregistrés intacts
        self.btn_random = FlatButton(bar, "🎲  TOUT ALÉATOIRE", lambda: self.generate(all_random=True),
                                     bg=CARD_HI, fg=ACCENT, hover=LINE, font=("Segoe UI Black", 10),
                                     padx=16, pady=9)
        self.btn_random.grid(row=0, column=2, rowspan=2, padx=6)
        self.btn_preview = FlatButton(bar, "Aperçu", self.preview, bg=CARD, fg=TEXT, hover=CARD_HI)
        self.btn_preview.grid(row=0, column=3, rowspan=2, padx=6)
        mid = tk.Frame(bar, bg=SIDEBAR)
        mid.grid(row=0, column=4, rowspan=2, sticky="ew", padx=14)
        mid.columnconfigure(0, weight=1)
        self.progress = ttk.Progressbar(mid, maximum=100)
        self.progress.grid(row=0, column=0, sticky="ew", pady=(14, 4))
        self.status = tk.Label(mid, text="Prêt.", fg=MUTED, bg=SIDEBAR, font=FONT_SMALL, anchor="w",
                               justify="left", wraplength=px(380))
        self.status.grid(row=1, column=0, sticky="ew")
        self.btn_cancel = FlatButton(bar, "Annuler", self.cancel, bg=CARD, fg=TEXT, hover=CARD_HI)
        self.btn_cancel.grid(row=0, column=5, rowspan=2, padx=6)
        self.btn_cancel.set_enabled(False)
        FlatButton(bar, "📁  Vidéos", self.open_folder, bg=CARD, fg=TEXT, hover=CARD_HI).grid(
            row=0, column=6, rowspan=2, padx=(6, 22))

    # ---- Pages ---------------------------------------------------------------------------

    def _page_video(self, page):
        s = self.s
        self._header(page, "Vidéo", "Ce qui s'affronte, avec quelle règle, dans quel décor. "
                                    "« Aléatoire » change à chaque vidéo (sans répétition, voir Variété).")
        card = self._card(page, "Partie")
        self.format, self.format_info = self._row_combo(card, 1, "Format", dict(formats.CHOICES), s.format)
        self.mode, self.mode_info = self._row_combo(card, 2, "Mode", dict(modes.CHOICES), s.mode)
        self.players, _ = self._row_combo(card, 3, "Joueurs", PLAYER_CHOICES,
                                          s.players if s.players in (2, 3, 4) else 0,
                                          "imposé par certains formats (2 contre 2, bataille royale…)")
        card = self._card(page, "Apparence")
        self.variant, _ = self._row_combo(card, 1, "Concurrents", dict(variants.CHOICES), s.variant,
                                          "couleurs, pays (drapeaux), fruits, animaux, planètes")
        self.theme, _ = self._row_combo(card, 2, "Thème d'arène", dict(themes.CHOICES), s.theme,
                                        "sol, fond, obstacles et ambiance animée (neige, braises…)")
        self.map, _ = self._row_combo(card, 3, "Carte", MAP_CHOICES, s.map, "disposition des obstacles")
        self.music_style, _ = self._row_combo(card, 4, "Musique", dict(music.CHOICES), s.music_style,
                                              "composée par le code à chaque vidéo (7 styles)")
        self.paint_pattern = tk.BooleanVar(value=s.paint_pattern)
        self._check(card, 5, "Traînée aux motifs du concurrent", self.paint_pattern,
                    "la peinture reprend le drapeau / le motif")
        self.summary = ttk.Label(page, text="", style="Sub.TLabel", wraplength=px(700), justify="left")
        self.summary.pack(anchor="w")

    def _page_variety(self, page):
        s = self.s
        self._header(page, "Variété", "Pour la rémunération TikTok : des vidéos qui ne se ressemblent pas, "
                                      "et la plupart au-dessus d'une minute.")
        row = ttk.Frame(page)
        row.pack(fill="both", expand=True)
        card = self._card(row, "Anti-répétition", side="left")
        self.variety = tk.BooleanVar(value=s.variety)
        self._check(card, 1, "Garde-fou anti-répétition", self.variety)
        ttk.Label(card, text="Retient les dernières vidéos (history.json) et évite de refaire le même "
                             "format, thème, mode, musique ou légende.", style="Muted.TLabel",
                  wraplength=px(330), justify="left").grid(row=2, column=0, columnspan=3, sticky="w", pady=(0, 8))
        self.duration_mix = tk.BooleanVar(value=s.duration_mix)
        self._check(card, 3, "Durées variées", self.duration_mix)
        self.long_share = tk.DoubleVar(value=round(s.long_share * 100))
        line = ttk.Frame(card, style="Card.TFrame")
        line.grid(row=4, column=0, columnspan=3, sticky="w")
        ttk.Label(line, text="Vidéos de plus d'1 min").pack(side="left")
        ttk.Scale(line, from_=70, to=100, variable=self.long_share, length=px(150),
                  command=lambda _v: self._round(self.long_share)).pack(side="left", padx=10)
        self.long_label = ttk.Label(line, text="", foreground=ACCENT, font=FONT_BOLD)
        self.long_label.pack(side="left")
        self.long_share.trace_add("write", lambda *_: self.on_change())
        ttk.Label(card, text="Les longues durent 62 à ~95 s ; les autres sont courtes (30-50 s) "
                             "avec un format simple (sprint, duel).", style="Muted.TLabel", wraplength=px(330),
                  justify="left").grid(row=5, column=0, columnspan=3, sticky="w", pady=(2, 8))
        self.caption_auto = tk.BooleanVar(value=s.caption_auto)
        self._check(card, 6, "Légende écrite d'après la partie", self.caption_auto)
        ttk.Label(card, text="K.O., remontée, photo finish… sans jamais dévoiler le gagnant.",
                  style="Muted.TLabel").grid(row=7, column=0, columnspan=3, sticky="w")
        ttk.Label(card, text="DERNIÈRES VIDÉOS", foreground=ACCENT, font=("Segoe UI Semibold", 9)).grid(
            row=8, column=0, columnspan=3, sticky="w", pady=(14, 4))
        self.history_label = ttk.Label(card, text="", style="Muted.TLabel", justify="left", wraplength=px(340))
        self.history_label.grid(row=9, column=0, columnspan=3, sticky="w")

        card = self._card(row, "Rétention (regarder jusqu'au bout)", side="right")
        self.flags = {}
        options = [
            ("killcam", "Zoom + ralenti avant une élimination"),
            ("tiktok_rewards", "Toujours plus d'1 minute (sans durées variées)"),
            ("teaser", "Teaser : la fin montrée en ouverture"),
            ("hide_scores", "Cacher les % à la fin"),
            ("comeback", "Coup de pouce au dernier"),
            ("lead_announce", "Annoncer les changements de leader"),
            ("slowmo", "Ralenti sur les K.O. et les explosions"),
            ("nicknames", "Surnoms des cubes"),
            ("league", "Ligue entre les vidéos"),
            ("follow_prompt", "Animation « abonne-toi »"),
        ]
        values = {"hide_scores": s.hide_final_scores > 0, "comeback": s.comeback > 0}
        for r, (key, label) in enumerate(options, start=1):
            var = tk.BooleanVar(value=values.get(key, getattr(s, key, True)))
            self.flags[key] = var
            Switch(card, label, var, self.on_change).grid(row=r, column=0, columnspan=3, sticky="w", pady=px(3))
        self.league_label = ttk.Label(card, text="", style="Muted.TLabel")
        self.league_label.grid(row=len(options) + 1, column=0, columnspan=2, sticky="w", pady=(8, 0))
        FlatButton(card, "Remettre la ligue à zéro", self.reset_league, font=FONT_SMALL, padx=10, pady=4).grid(
            row=len(options) + 2, column=0, sticky="w", pady=(6, 0))

    def _page_cup(self, page):
        s = self.s
        self._header(page, "PaintCup", "Un tournoi de 8 à 16 cubes sur plusieurs vidéos : chaque vidéo est un "
                                       "match, les 2 premiers passent, les autres sont éliminés.")
        card = self._card(page, "Tournoi")
        self.cup = tk.BooleanVar(value=s.cup)
        self._check(card, 1, "Jouer la PaintCup", self.cup,
                    "chaque vidéo générée joue le match suivant (format, thème, musique varient quand même)")
        self.cup_size = tk.IntVar(value=s.cup_size)
        self._row_spin(card, 2, "Participants", self.cup_size, 8, 16, 1,
                       "pour la prochaine coupe ; concurrents : réglage « Concurrents » (pays par défaut)")
        self.cup_status = ttk.Label(card, text="", foreground=ACCENT, font=FONT_BOLD, wraplength=px(640),
                                    justify="left")
        self.cup_status.grid(row=3, column=0, columnspan=3, sticky="w", pady=(10, 4))
        FlatButton(card, "Nouvelle coupe", self.reset_cup, font=FONT_SMALL, padx=10, pady=4).grid(
            row=4, column=0, sticky="w", pady=(4, 0))
        row = ttk.Frame(page)
        row.pack(fill="both", expand=True)
        card = self._card(row, "Classement général", side="left")
        card.columnconfigure(0, weight=1)
        cols = ("rank", "name", "status", "points")
        self.cup_table = ttk.Treeview(card, columns=cols, show="headings", height=16, style="Cup.Treeview",
                                      selectmode="none")
        for col, text, w, anchor in zip(cols, ("#", "Concurrent", "Statut", "Pts"), (44, 170, 230, 56),
                                        ("center", "w", "w", "center")):
            self.cup_table.heading(col, text=text, anchor=anchor)
            self.cup_table.column(col, width=px(w), minwidth=px(w), anchor=anchor, stretch=col == "status")
        for tag, color in (("champion", ACCENT), ("finalist", ACCENT_HI), ("through", GREEN), ("alive", TEXT),
                           ("out", MUTED)):
            self.cup_table.tag_configure(tag, foreground=color)
        self.cup_table.tag_configure("odd", background=CARD)
        self.cup_table.grid(row=1, column=0, columnspan=3, sticky="nsew")
        card = self._card(row, "Matchs", side="right")
        self.cup_matches = ttk.Frame(card, style="Card.TFrame")
        self.cup_matches.grid(row=1, column=0, columnspan=3, sticky="nsew")

    def _page_items(self, page):
        s = self.s
        self._header(page, "Objets", "Probabilités et rythme des objets (un mode ou un format peut les imposer).")
        row = ttk.Frame(page)
        row.pack(fill="both", expand=True)
        card = self._card(row, "Probabilité des objets", side="left")
        self.prob_vars, self.pct_labels = {}, {}
        for r, kind in enumerate(ITEM_KINDS, start=1):
            var = tk.DoubleVar(value=getattr(s, f"prob_{kind}"))
            self.prob_vars[kind] = var
            ttk.Label(card, text=ITEM_LABELS[kind], width=15).grid(row=r, column=0, sticky="w")
            ttk.Scale(card, from_=0, to=100, variable=var, length=px(170),
                      command=lambda _v, k=kind: self._round(self.prob_vars[k])).grid(row=r, column=1, padx=6, pady=2)
            lbl = ttk.Label(card, width=13, style="Muted.TLabel")
            lbl.grid(row=r, column=2, sticky="w")
            self.pct_labels[kind] = lbl
            var.trace_add("write", lambda *_: self.on_change())
        card = self._card(row, "Apparition et réglages fins", side="right")
        self.interval = tk.DoubleVar(value=s.item_interval)
        self.max_items = tk.IntVar(value=s.max_items)
        self.max_hourglasses = tk.IntVar(value=s.max_hourglasses)
        self.item_ramp = tk.DoubleVar(value=s.item_ramp)
        self.cube_size = tk.IntVar(value=s.cube_size)
        self.speed_ramp = tk.DoubleVar(value=s.speed_ramp)
        self.lives = tk.IntVar(value=s.lives)
        self.duel_lives = tk.IntVar(value=s.duel_lives)
        self.obstacles = tk.IntVar(value=s.obstacles)
        self._row_spin(card, 1, "Intervalle (s)", self.interval, 1, 30, 0.5)
        self._row_spin(card, 2, "Objets max", self.max_items, 1, 10, 1)
        self._row_spin(card, 3, "Sabliers max", self.max_hourglasses, 0, 10, 1)
        self._row_spin(card, 4, "Rythme final (×)", self.item_ramp, 0.3, 2.0, 0.1)
        self._row_spin(card, 5, "Taille des cubes", self.cube_size, 5, 16, 1)
        self._row_spin(card, 6, "Vitesse finale (×)", self.speed_ramp, 1.0, 3.0, 0.1)
        self._row_spin(card, 7, "Vies par cube", self.lives, 0, 5, 1, "0 = illimitées")
        self._row_spin(card, 8, "Vies en duel", self.duel_lives, 1, 6, 1)
        self._row_spin(card, 9, "Obstacles", self.obstacles, 0, 4, 1, "carte « au hasard »")

    def _page_sound(self, page):
        s = self.s
        self._header(page, "Son & export", "Volumes, fichiers produits et légende fixe.")
        card = self._card(page, "Son")
        self.master = tk.DoubleVar(value=round(s.master_volume * 100))
        self.music = tk.DoubleVar(value=round(s.music_volume * 100))
        self.music_on = tk.BooleanVar(value=s.music_enabled)
        self.vol_labels = {}
        for r, (label, var) in enumerate((("Volume général", self.master), ("Volume musique", self.music)), start=1):
            ttk.Label(card, text=label).grid(row=r, column=0, sticky="w", padx=(0, 14))
            ttk.Scale(card, from_=0, to=100, variable=var, length=px(240),
                      command=lambda _v, v=var: self._round(v)).grid(row=r, column=1, sticky="w", pady=3)
            lbl = ttk.Label(card, width=6, foreground=ACCENT)
            lbl.grid(row=r, column=2, sticky="w")
            self.vol_labels[label] = (lbl, var)
            var.trace_add("write", lambda *_: self.on_change())
        self._check(card, 3, "Musique de fond", self.music_on)
        card = self._card(page, "Export")
        self.seed = tk.StringVar(value=s.seed)
        ttk.Label(card, text="Seed (optionnelle)").grid(row=1, column=0, sticky="w", padx=(0, 14))
        ttk.Entry(card, textvariable=self.seed, width=20).grid(row=1, column=1, sticky="w", pady=4)
        ttk.Label(card, text="vide = aléatoire", style="Muted.TLabel").grid(row=1, column=2, sticky="w", padx=14)
        self.seed.trace_add("write", lambda *_: self.on_change())
        self.srt = tk.BooleanVar(value=s.export_srt)
        self._check(card, 2, "Sous-titres .srt", self.srt)
        self.caption = tk.StringVar(value=s.caption)
        self.hashtags = tk.StringVar(value=" ".join("#" + h.lstrip("#") for h in s.hashtags))
        ttk.Label(card, text="Légende fixe").grid(row=3, column=0, sticky="w")
        ttk.Entry(card, textvariable=self.caption, width=44).grid(row=3, column=1, columnspan=2, sticky="w", pady=4)
        ttk.Label(card, text="Hashtags").grid(row=4, column=0, sticky="w")
        ttk.Entry(card, textvariable=self.hashtags, width=44).grid(row=4, column=1, columnspan=2, sticky="w", pady=4)
        ttk.Label(card, text="Légende fixe : utilisée si « légende écrite d'après la partie » est décochée. "
                             "Les 2 premiers hashtags restent sur toutes les vidéos.", style="Muted.TLabel",
                  wraplength=px(560), justify="left").grid(row=5, column=0, columnspan=3, sticky="w")
        for var in (self.caption, self.hashtags):
            var.trace_add("write", lambda *_: self.on_change())
        FlatButton(card, "Réglages avancés (config.json)…", self.open_config, font=FONT_SMALL, padx=10,
                   pady=4).grid(row=6, column=0, columnspan=2, sticky="w", pady=(10, 0))

    # ---- Utilitaires ---------------------------------------------------------------------

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

    @staticmethod
    def _key(choices, label, default):
        return next((k for k, text in choices if text == label), default)

    # ---- Réglages ------------------------------------------------------------------------

    def collect(self) -> cfg.Settings:
        s = self.s
        s.format = self._key(formats.CHOICES, self.format.get(), formats.CLASSIC)
        s.mode = self._key(modes.CHOICES, self.mode.get(), modes.CLASSIC)
        s.players = self._key(PLAYER_CHOICES.items(), self.players.get(), 0)
        s.variant = self._key(variants.CHOICES, self.variant.get(), variants.COLORS)
        s.theme = self._key(themes.CHOICES, self.theme.get(), themes.RANDOM)
        s.map = self._key(MAP_CHOICES.items(), self.map.get(), "random")
        s.music_style = self._key(music.CHOICES, self.music_style.get(), music.AUTO)
        s.paint_pattern = self.paint_pattern.get()
        s.variety = self.variety.get()
        s.duration_mix = self.duration_mix.get()
        s.long_share = min(1.0, max(0.7, self._get(self.long_share, 85) / 100))
        s.caption_auto = self.caption_auto.get()
        f = {k: bool(v.get()) for k, v in self.flags.items()}
        s.killcam = f["killcam"]
        s.tiktok_rewards = f["tiktok_rewards"]
        s.teaser = f["teaser"]
        s.hide_final_scores = 5.0 if f["hide_scores"] else 0.0
        s.comeback = 0.5 if f["comeback"] else 0.0
        s.lead_announce = f["lead_announce"]
        s.slowmo = f["slowmo"]
        s.nicknames = f["nicknames"]
        s.league = f["league"]
        s.follow_prompt = f["follow_prompt"]
        s.cup = self.cup.get()
        s.cup_size = min(16, max(8, int(self._get(self.cup_size, s.cup_size))))
        for kind, var in self.prob_vars.items():
            setattr(s, f"prob_{kind}", float(round(self._get(var, 0))))
        s.item_interval = max(0.5, float(self._get(self.interval, s.item_interval)))
        s.max_items = max(1, int(self._get(self.max_items, s.max_items)))
        s.max_hourglasses = max(0, int(self._get(self.max_hourglasses, s.max_hourglasses)))
        s.item_ramp = round(min(2.0, max(0.3, float(self._get(self.item_ramp, s.item_ramp)))), 2)
        s.cube_size = min(16, max(5, int(self._get(self.cube_size, s.cube_size))))
        s.speed_ramp = round(min(3.0, max(1.0, float(self._get(self.speed_ramp, s.speed_ramp)))), 2)
        s.lives = min(5, max(0, int(self._get(self.lives, s.lives))))
        s.duel_lives = min(6, max(1, int(self._get(self.duel_lives, s.duel_lives))))
        s.obstacles = min(4, max(0, int(self._get(self.obstacles, s.obstacles))))
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
        if not hasattr(self, "vol_labels"):
            return
        s = self.collect()
        fmt = formats.BY_KEY.get(s.format)
        self.format_info.config(text=fmt.pitch if fmt else "un format différent à chaque vidéo "
                                                            "(course, combat, 2 contre 2, bataille royale)")
        mode = modes.BY_KEY.get(s.mode)
        if fmt is not None and not fmt.use_mode:
            self.mode_info.config(text=f"ignoré par le format « {fmt.label} » (il a ses propres objets)")
        elif s.mode == modes.CLASSIC:
            self.mode_info.config(text="objets selon la page Objets · " + modes.summary(s))
        elif mode is None:
            self.mode_info.config(text="un mode différent tiré pour chaque vidéo")
        else:
            self.mode_info.config(text=mode.pitch + " · " + modes.summary(modes.apply(s, mode)))
        shown = modes.apply(s, mode)
        pcts, weights = shown.item_percentages(), shown.item_weights()
        for kind, lbl in self.pct_labels.items():
            if s.mode == modes.RANDOM:
                lbl.config(text="selon le mode")
            elif weights[kind] <= 0:
                lbl.config(text="jamais")
            else:
                lbl.config(text=f"{pcts[kind]:.1f} % {'réel' if mode is None else 'mode'}")
        for lbl, var in self.vol_labels.values():
            lbl.config(text=f"{round(self._get(var, 0))} %")
        self.long_label.config(text=f"{round(self._get(self.long_share, 85))} %")
        n = s.video_count
        short = max(0, round(n * (1 - s.long_share))) if s.duration_mix else 0
        what = f"{n} vidéo{'s' if n > 1 else ''}"
        if s.cup:
            what += " · PaintCup"
        if s.duration_mix:
            what += f" · ≈{short} courte{'s' if short > 1 else ''}, le reste > 1 min"
        self.summary.config(text=("Prochaine génération : " + what + (" · garde-fou actif" if s.variety else "")))
        self.side_info.config(text=self._side_text())
        self._refresh_league()
        if save:
            if self._save_job:
                self.root.after_cancel(self._save_job)
            self._save_job = self.root.after(400, self.save)

    def _side_text(self) -> str:
        d = self.videos_dir()
        n = sum(1 for p in d.glob("*.mp4") if ".tmp" not in p.name) if d.is_dir() else 0
        h = variety.load_history()
        return f"{n} vidéo{'s' if n > 1 else ''} dans le dossier\n{h['count']} générée{'s' if h['count'] > 1 else ''} au total"

    def save(self):
        self._save_job = None
        try:
            cfg.save(self.collect())
        except OSError as exc:
            self.status.config(text=f"Impossible d'enregistrer la config : {exc}")

    # ---- Ligue, coupe, historique -------------------------------------------------------

    def _refresh_league(self):
        data = league.load(variant=self.s.variant if self.s.variant in variants.BY_KEY else variants.COLORS)
        if data["day"] == 0:
            self.league_label.config(text="Ligue : aucune journée jouée")
        else:
            team, wins = league.standings(data)[0]
            self.league_label.config(text=f"Ligue : jour {data['day']}, en tête {team} ({wins} V)")

    def reset_league(self):
        if messagebox.askyesno("Ligue", "Remettre le classement de la ligue à zéro (jour 0) ?"):
            league.reset(variant=self.s.variant if self.s.variant in variants.BY_KEY else variants.COLORS)
            self._refresh_league()

    def _refresh_cup(self):
        state = paintcup.load()
        self.cup_status.config(text=paintcup.summary(state))
        self.cup_table.delete(*self.cup_table.get_children())
        for child in self.cup_matches.winfo_children():
            child.destroy()
        if state is None:
            ttk.Label(self.cup_matches, text="Les matchs apparaîtront ici dès la première vidéo de coupe.",
                      style="Muted.TLabel").pack(anchor="w")
            return
        labels = {"champion": "🏆  Champion", "through": "✔  qualifié · {}", "alive": "en lice · {}",
                  "out": "✖  éliminé · {}", "finalist": "🥈  {}"}
        for k, (name, _reached, points) in enumerate(paintcup.standings(state), start=1):
            kind, where = paintcup.status(state, name)
            text = labels[kind].format(round_fr(where) if kind != "finalist" else where)
            tags = (kind, "odd") if k % 2 else (kind,)
            self.cup_table.insert("", "end", values=(k, pretty(name), text, points), tags=tags)
        self.cup_table.configure(height=max(8, len(state["players"])))
        # matchs, tour par tour : joués (qui passe) ou à jouer
        nxt = paintcup.next_match(state)
        for ri, rnd in enumerate(state["rounds"]):
            ttk.Label(self.cup_matches, text=round_fr(rnd["name"]), foreground=ACCENT, font=FONT_BOLD).pack(
                anchor="w", pady=(px(8) if ri else 0, px(2)))
            for mi, match in enumerate(rnd["matches"]):
                line = ttk.Frame(self.cup_matches, style="Card.TFrame")
                line.pack(anchor="w", fill="x", pady=px(1))
                if match["ranking"] is None:
                    upcoming = nxt == (ri, mi)
                    names = ", ".join(pretty(n) for n in match["lineup"])
                    ttk.Label(line, text=f"{mi + 1}.  ").pack(side="left")
                    if upcoming:
                        ttk.Label(line, text="▶ ", foreground=ACCENT, font=FONT_BOLD).pack(side="left")
                    ttk.Label(line, text=names, foreground=TEXT if upcoming else MUTED).pack(side="left")
                    continue
                cut = 1 if rnd["name"] == "FINAL" else 2
                ttk.Label(line, text=f"{mi + 1}.  ").pack(side="left")
                for k, n in enumerate(match["ranking"]):
                    ttk.Label(line, text=pretty(n) + ("" if k == len(match["ranking"]) - 1 else ",  "),
                              foreground=GREEN if k < cut else MUTED,
                              font=FONT_BOLD if k < cut else FONT).pack(side="left")

    def reset_cup(self):
        if messagebox.askyesno("PaintCup", "Abandonner la coupe en cours ? La prochaine génération en "
                                           "démarrera une nouvelle."):
            paintcup.reset()
            self._refresh_cup()

    def _refresh_history(self):
        h = variety.load_history()
        lines = []
        for v in reversed(h["videos"][-6:]):
            parts = [v.get("format", ""), v.get("mode", ""), v.get("theme", ""), v.get("music_style", "")]
            dur = f"{v['duration']:.0f} s" if v.get("duration") else ""
            lines.append("• " + " · ".join(p for p in parts + [dur] if p and p != "classic"))
        self.history_label.config(text="\n".join(lines) or "aucune vidéo pour l'instant")

    # ---- Actions -------------------------------------------------------------------------

    def preview(self):
        self.save()
        cmd = [python_exe(), str(MAIN), "--preview"]
        seed = self.seed.get().strip()
        if seed:
            cmd += ["--seed", seed]
        subprocess.Popen(cmd, cwd=str(ROOT), creationflags=NO_WINDOW)
        self.status.config(text="Aperçu lancé (ÉCHAP pour fermer, R pour une nouvelle partie).")

    def generate(self, all_random: bool = False):
        if self.proc is not None:
            return
        self.save()
        s = self.s
        cmd = [python_exe(), str(MAIN), "--generate", str(s.video_count), "--progress"]
        if all_random:
            cmd.append("--all-random")
        if s.seed:
            cmd += ["--seed", s.seed]
        env = dict(os.environ, PYTHONIOENCODING="utf-8", PYTHONUNBUFFERED="1")
        self.proc = subprocess.Popen(cmd, cwd=str(ROOT), stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                     text=True, encoding="utf-8", errors="replace", env=env,
                                     creationflags=NO_WINDOW)
        self.total = s.video_count
        self.done_paths: list[str] = []
        self.errors: list[str] = []
        self.last_caption = ""
        self.progress["value"] = 0
        what = " (tout aléatoire)" if all_random else ""
        self.status.config(text=f"Vidéo 1 / {self.total}{what} : démarrage…", fg=TEXT)
        self.btn_generate.set_enabled(False)
        self.btn_random.set_enabled(False)
        self.btn_cancel.set_enabled(True)
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
                extra = f"  ·  dernière légende : {self.last_caption}" if self.last_caption else ""
                self.status.config(text=f"Vidéo {i} / {n} : {pct} %{extra}")
            elif parts[0] == "DONE" and len(parts) == 4:
                self.done_paths.append(parts[3])
            elif parts[0] == "RESULT":
                try:
                    info = json.loads(line[len("RESULT "):])
                    self.last_caption = info.get("caption", "")[:90]
                except ValueError:
                    pass
            elif parts[0] == "ERROR":
                self.errors.append(line)
            elif line.strip() and "Traceback" in line:
                self.errors.append(line)
        if finished:
            self._finished()
        else:
            self.root.after(100, self._poll)

    def _finished(self):
        cancelled = self._cancelled
        self._cancelled = False
        self.proc = None
        self.btn_generate.set_enabled(True)
        self.btn_random.set_enabled(True)
        self.btn_cancel.set_enabled(False)
        n = len(self.done_paths)
        self.on_change(save=False)
        if cancelled:
            self.status.config(text=f"Génération annulée ({n} vidéo(s) terminée(s)).", fg=MUTED)
        elif self.errors:
            self.status.config(text=f"{n} vidéo(s), {len(self.errors)} erreur(s) : {self.errors[0][:200]}", fg=RED)
        else:
            self.progress["value"] = 100
            self.status.config(text=f"Terminé : {n} vidéo(s) dans « {self.s.output_dir} ». Légende de chaque "
                                    f"vidéo dans le .txt à côté.", fg=GREEN)

    def cancel(self):
        if self.proc is not None:
            self._cancelled = True
            self.proc.terminate()

    def videos_dir(self) -> Path:
        d = Path(self.s.output_dir)
        return d if d.is_absolute() else ROOT / d

    def open_folder(self):
        d = self.videos_dir()
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
    if os.name == "nt":
        try:                                       # texte net sur les écrans à 125 % / 150 %
            import ctypes
            ctypes.windll.shcore.SetProcessDpiAwareness(1)
        except (AttributeError, OSError):
            pass
    root = tk.Tk()
    init_scale(root)
    ControlPanel(root)
    root.mainloop()
