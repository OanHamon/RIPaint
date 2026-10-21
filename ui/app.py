"""Application terminal RIPaint : écran de démarrage animé, puis l'atelier de génération.

L'aperçu et la génération tournent dans des processus séparés (python main.py ...) :
l'interface reste fluide et pygame/ffmpeg n'écrivent jamais dans le terminal.
"""

import asyncio
import json
import os
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

from rich.text import Text
from textual import on, work
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical, VerticalScroll
from textual.screen import ModalScreen, Screen
from textual.theme import Theme
from textual.widget import Widget
from textual.widgets import Footer, Input, Label, RichLog, Static

from game import modes
from game.battle import video_seconds
from game import settings as cfg
from game.settings import ITEM_KINDS, ITEM_LABELS

from . import logo, theme
from .arena import Arena
from .widgets import LABEL_W, Choice, PixelSlider, Row, Stepper, Toggle

os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")

ROOT = cfg.ROOT
MAIN = ROOT / "main.py"
NO_WINDOW = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0
TAGLINE = "batailles de cubes 8-bit  ·  vidéos TikTok 1080×1920 · 60 fps"
PLAYER_CHOICES = [(0, "aléatoire"), (2, "2 joueurs"), (3, "3 joueurs"), (4, "4 joueurs")]
TEAM_WORDS = {name: colors[1] for name, colors in theme.TEAMS.items()}

# Réglages modifiables depuis l'interface ; les autres clés de config.json sont préservées.
MANAGED = [f"prob_{k}" for k in ITEM_KINDS] + [
    "mode", "players", "cube_size", "lives", "obstacles", "speed_ramp", "item_interval", "item_ramp", "max_items", "max_hourglasses", "master_volume", "music_volume",
    "music_enabled", "video_count", "seed", "export_srt"]
# Compteurs qu'un mode peut imposer : ils affichent alors la valeur du mode
LOCKABLE = ["cube_size", "lives", "obstacles", "speed_ramp", "item_interval", "item_ramp", "max_items",
            "max_hourglasses"]


def python_exe() -> str:
    exe = Path(sys.executable)
    if exe.name.lower() == "pythonw.exe":
        console = exe.with_name("python.exe")
        if console.exists():
            return str(console)
    return str(exe)


def videos_dir(settings: cfg.Settings) -> Path:
    d = Path(settings.output_dir)
    return d if d.is_absolute() else ROOT / d


def count_videos(settings: cfg.Settings) -> int:
    d = videos_dir(settings)
    return sum(1 for p in d.glob("combat_*.mp4") if ".tmp" not in p.name) if d.is_dir() else 0


def fmt_clock(seconds: float) -> str:
    seconds = max(0, int(seconds))
    return f"{seconds // 60}:{seconds % 60:02d}"


def team_text(text: str, base: str = theme.WHITE) -> Text:
    """Texte avec les noms d'équipes colorés."""
    t = Text(text, style=base)
    for word, color in TEAM_WORDS.items():
        t.highlight_words([word], style=f"bold {color}")
    return t


def paint_bar(frac: float, width: int, color: str) -> Text:
    frac = min(1.0, max(0.0, frac))
    filled = frac * width
    full = int(filled)
    text = Text("█" * full, style=color)
    if full < width:
        ch = " ▏▎▍▌▋▊▉"[int((filled - full) * 8)]
        if ch != " ":
            text.append(ch, style=f"{color} on {theme.FLOOR_A}")
            full += 1
        text.append(" " * (width - full), style=f"on {theme.FLOOR_A}")
    return text


# ---- Vérifications au démarrage -----------------------------------------------------------

def _check_settings() -> str:
    cfg.load()
    return "config.json" if cfg.CONFIG_PATH.exists() else "valeurs par défaut"


def _check_engine() -> str:
    import pygame
    import game.battle  # noqa: F401  (moteur + règles du jeu)
    return f"pygame {pygame.version.ver}"


def _check_audio() -> str:
    import numpy
    from audio.synth import SAMPLE_RATE
    return f"numpy {numpy.__version__} · {SAMPLE_RATE} Hz"


def _check_encoder() -> str:
    import imageio_ffmpeg
    imageio_ffmpeg.get_ffmpeg_exe()
    return f"ffmpeg {imageio_ffmpeg.get_ffmpeg_version()}"


def _check_output() -> str:
    s = cfg.load()
    d = videos_dir(s)
    d.mkdir(parents=True, exist_ok=True)
    n = count_videos(s)
    return f"{s.output_dir}/ · {n} vidéo{'s' if n > 1 else ''}"


CHECKS = [
    ("Réglages", _check_settings),
    ("Moteur 8-bit", _check_engine),
    ("Synthèse audio", _check_audio),
    ("Encodeur vidéo", _check_encoder),
    ("Dossier de sortie", _check_output),
]


class SplashScreen(Screen):
    """Le logo se peint, le moteur se charge, puis on entre dans l'atelier."""

    BINDINGS = [
        Binding("enter,space,escape", "skip", show=False),
        Binding("q", "app.quit", show=False),
    ]
    REVEAL = (0.15, 1.35)       # peinture du logo (début, fin) en secondes
    SHINE = (1.35, 2.0)         # reflet
    TYPE = (0.7, 1.7)           # accroche tapée lettre à lettre
    CHECK_START, CHECK_STEP = 0.5, 0.22
    LINE_W = 52

    def compose(self) -> ComposeResult:
        with Vertical(id="splash"):
            yield Static(id="splash-logo")
            yield Static(id="splash-tagline")
            yield Static(id="splash-checks")
            yield Static(id="splash-hint")

    def on_mount(self) -> None:
        self.t0 = time.perf_counter()
        self.results: list[tuple[bool, str] | None] = [None] * len(CHECKS)
        self.skipping = False
        self.ready_at: float | None = None
        self.leaving = False
        self.set_interval(1 / 30, self._tick)
        self._run_checks()

    @work(thread=True)
    def _run_checks(self) -> None:
        for i, (_label, fn) in enumerate(CHECKS):
            try:
                self.results[i] = (True, fn())
            except Exception as exc:  # dépendance absente, ffmpeg introuvable...
                self.results[i] = (False, f"{type(exc).__name__} : {exc}")

    def _t(self) -> float:
        return 99.0 if self.skipping else time.perf_counter() - self.t0

    @staticmethod
    def _phase(t: float, span: tuple[float, float]) -> float:
        return min(1.0, max(0.0, (t - span[0]) / (span[1] - span[0])))

    def _tick(self) -> None:
        if self.leaving:
            return
        t = self._t()
        frame = int((time.perf_counter() - self.t0) * 12)

        # Logo
        if self.size.width >= logo.BIG_WIDTH + 4:
            shine = None
            if self.SHINE[0] <= t < self.SHINE[1]:
                shine = -4 + self._phase(t, self.SHINE) * (logo.W + 10)
            self.query_one("#splash-logo", Static).update(logo.big(self._phase(t, self.REVEAL), shine))
        else:
            self.query_one("#splash-logo", Static).update(logo.compact())

        # Accroche
        n = int(self._phase(t, self.TYPE) * len(TAGLINE))
        tagline = Text(TAGLINE[:n], style=theme.GREY_LIGHT)
        if n < len(TAGLINE) and t >= self.TYPE[0]:
            tagline.append("▌", style=theme.YELLOW)
        self.query_one("#splash-tagline", Static).update(tagline)

        # Chargement
        lines = Text()
        all_done = True
        for i, (label, _fn) in enumerate(CHECKS):
            shown_at = self.CHECK_START + i * self.CHECK_STEP
            res = self.results[i]
            done = res is not None and t >= shown_at + self.CHECK_STEP
            all_done &= done
            if i:
                lines.append("\n")
            if t < shown_at:
                lines.append(" " * self.LINE_W)
                continue
            detail = res[1] if done else "chargement…"
            if done and res[0]:
                lines.append(" ✓ ", style=f"bold {theme.GREEN_LIGHT}")
            elif done:
                lines.append(" ✗ ", style=f"bold {theme.RED}")
            else:
                lines.append(f" {theme.SPINNER[frame % len(theme.SPINNER)]} ", style=theme.YELLOW)
            lines.append(label + " ", style=theme.WHITE)
            room = self.LINE_W - 3 - len(label) - 2
            detail = detail if len(detail) <= room - 2 else detail[:room - 3] + "…"
            lines.append("·" * (room - len(detail)), style=theme.GREY_DARK)
            lines.append(" " + detail, style=theme.GREY_LIGHT if done and res[0] else
                         (theme.RED_LIGHT if done else theme.GREY))
        self.query_one("#splash-checks", Static).update(lines)

        hint = self.query_one("#splash-hint", Static)
        failed = [CHECKS[i][0] for i, r in enumerate(self.results) if r and not r[0]]
        if all_done and t >= self.SHINE[1]:
            if failed:
                hint.update(Text.assemble(
                    ("Éléments manquants : ", f"bold {theme.RED}"), (", ".join(failed), theme.RED_LIGHT),
                    ("\n\npython -m pip install -r requirements.txt", f"bold {theme.WHITE}"),
                    ("\n\nENTRÉE continuer quand même  ·  Q quitter", theme.GREY)))
                return
            if self.ready_at is None:
                self.ready_at = time.perf_counter()
            hint.update(Text("PRÊT", style=f"bold {theme.GREEN_LIGHT}"))
            if self.skipping or time.perf_counter() - self.ready_at > 0.5:
                self._enter()
        else:
            hint.update(Text("ENTRÉE pour passer", style=theme.GREY_DARK))

    def action_skip(self) -> None:
        if self.skipping and all(self.results):
            self._enter()
        self.skipping = True

    def _enter(self) -> None:
        if not self.leaving:
            self.leaving = True
            self.app.switch_screen(MainScreen())


# ---- Atelier ------------------------------------------------------------------------------

class SettingsColumn(VerticalScroll, can_focus=False, inherit_bindings=False):
    """Colonne des réglages : flèches haut/bas changent de ligne au lieu de faire défiler."""


class Journal(RichLog, can_focus=False):
    pass


class RunStatus(Widget):
    """État de la génération : badge, barre de la vidéo en cours, barre totale, temps."""

    DEFAULT_CSS = "RunStatus { height: 4; }"

    BADGES = {
        "idle": ("PRÊT", theme.BLACK, theme.GREEN_LIGHT),
        "run": ("RENDU", theme.BLACK, theme.YELLOW),
        "done": ("TERMINÉ", theme.BLACK, theme.GREEN_LIGHT),
        "cancel": ("ANNULÉ", theme.WHITE, theme.GREY_DARK),
        "error": ("ERREUR", theme.WHITE, theme.RED),
    }

    def __init__(self, *, id: str | None = None):
        super().__init__(id=id)
        self.phase = "idle"
        self.message = ""
        self.index = 0
        self.total = 1
        self.pct = 0
        self.started = 0.0
        self.ended = 0.0

    def on_mount(self) -> None:
        self.set_interval(1 / 10, self._spin)

    def _spin(self) -> None:
        if self.phase == "run":
            self.refresh()

    def set_state(self, phase: str, message: str = "") -> None:
        self.phase, self.message = phase, message
        if phase != "run":
            self.ended = time.perf_counter()
        self.refresh()

    def start(self, total: int) -> None:
        self.index, self.total, self.pct = 1, total, 0
        self.started = time.perf_counter()
        self.set_state("run", "démarrage…")

    def progress(self, index: int, total: int, pct: int) -> None:
        self.index, self.total, self.pct = index, total, pct
        self.message = f"vidéo {index} / {total}"
        self.refresh()

    @property
    def overall(self) -> float:
        return ((self.index - 1) + self.pct / 100) / max(1, self.total)

    def render(self) -> Text:
        width = self.size.width
        label, fg, bg = self.BADGES[self.phase]
        text = Text()
        if self.phase == "run":
            spin = theme.SPINNER[int(time.perf_counter() * 10) % len(theme.SPINNER)]
            text.append(f" {spin} {label} ", style=f"bold {fg} on {bg}")
        else:
            text.append(f" {label} ", style=f"bold {fg} on {bg}")
        text.append("  ")
        text.append_text(team_text(self.message, theme.GREY_LIGHT))
        text.append("\n\n")

        active = self.phase != "idle"
        bar_w = max(10, width - 20)
        video_frac = 1.0 if self.phase == "done" else (self.pct / 100 if active else 0)
        total_frac = 1.0 if self.phase == "done" else (self.overall if active else 0)
        text.append(" vidéo ", style=theme.GREY)
        text.append_text(paint_bar(video_frac, bar_w, theme.YELLOW))
        text.append(f" {video_frac * 100:3.0f} %", style=theme.WHITE)
        text.append(f"  {self.index}/{self.total}" if active else "", style=theme.GREY)
        text.append("\n total ", style=theme.GREY)
        text.append_text(paint_bar(total_frac, bar_w, theme.GREEN_LIGHT))
        text.append(f" {total_frac * 100:3.0f} %", style=theme.WHITE)
        if active:
            end = time.perf_counter() if self.phase == "run" else self.ended
            elapsed = end - self.started
            info = f"  {fmt_clock(elapsed)}"
            if self.phase == "run" and total_frac > 0.02:
                info += f" · reste ~{fmt_clock(elapsed * (1 - total_frac) / total_frac)}"
            text.append(info, style=theme.GREY)
        return text


class ConfirmQuit(ModalScreen[bool]):
    BINDINGS = [
        Binding("o,y,enter", "answer(True)", show=False),
        Binding("n,escape,q", "answer(False)", show=False),
    ]

    def compose(self) -> ComposeResult:
        with Vertical(id="dialog"):
            yield Static(Text("Génération en cours", style=f"bold {theme.YELLOW}"))
            yield Static(Text("Quitter maintenant annule la vidéo en cours de rendu.", style=theme.GREY_LIGHT))
            yield Static(Text.assemble((" O ", f"bold {theme.BLACK} on {theme.RED}"), ("  annuler et quitter     ", theme.WHITE),
                                       (" N ", f"bold {theme.BLACK} on {theme.GREY_LIGHT}"), ("  rester", theme.WHITE)),
                         id="dialog-keys")

    def action_answer(self, value: bool) -> None:
        self.dismiss(value)


class MainScreen(Screen):
    BINDINGS = [
        Binding("g", "generate", "Générer"),
        Binding("p", "preview", "Aperçu"),
        Binding("escape", "cancel", "Annuler"),
        Binding("o", "open_folder", "Vidéos"),
        Binding("c", "open_config", "config.json"),
        Binding("r", "reload", "Recharger"),
        Binding("q", "request_quit", "Quitter"),
        Binding("up", "app.focus_previous", show=False),
        Binding("down", "app.focus_next", show=False),
    ]

    def __init__(self) -> None:
        super().__init__()
        self.s = cfg.load()
        self.proc: asyncio.subprocess.Process | None = None
        self.cancelled = False
        self._save_timer = None
        self._loading = False

    # ---- Construction ----------------------------------------------------------------------

    def compose(self) -> ComposeResult:
        s = self.s
        with Horizontal(id="top"):
            yield Static(logo.compact(), id="top-logo")
            with Vertical(id="top-info"):
                yield Static(Text.assemble(("BATAILLE DE CUBES 8-BIT", f"bold {theme.WHITE}"),
                                           ("  ·  générateur de vidéos TikTok", theme.GREY)))
                yield Static(Text("1080×1920 · 60 fps · H.264 + AAC · musique et bruitages générés",
                                  style=theme.GREY))
                yield Static(id="top-stats")
        with Horizontal(id="body"):
            with SettingsColumn(id="left"):
                with Vertical(classes="panel", id="p-game"):
                    yield Choice("Mode", modes.CHOICES, s.mode, id="mode")
                    yield Static(id="mode-info")
                    yield Choice("Joueurs", PLAYER_CHOICES, s.players if s.players in (2, 3, 4) else 0,
                                 id="players")
                    yield Stepper("Taille des cubes", s.cube_size, 5, 16, 1, "{:g} px", id="cube_size")
                    yield Stepper("Vies par cube", s.lives, 0, 5, 1, "{:g}", "0 = illimitées", id="lives")
                    yield Stepper("Obstacles", s.obstacles, 0, 4, 1, "{:g}", "blocs dans l'arène",
                                  id="obstacles")
                    yield Stepper("Vitesse finale", s.speed_ramp, 1.0, 3.0, 0.1, "×{:.1f}",
                                  "accélération jusqu'à la fin", id="speed_ramp")
                with Vertical(classes="panel", id="p-items"):
                    for kind in ITEM_KINDS:
                        yield PixelSlider(ITEM_LABELS[kind], getattr(s, f"prob_{kind}"),
                                          theme.ITEM_COLORS[kind], note_width=12, id=f"prob_{kind}")
                with Vertical(classes="panel", id="p-spawn"):
                    yield Stepper("Intervalle", s.item_interval, 0.5, 30, 0.5, "{:g} s",
                                  "entre deux objets", id="item_interval")
                    yield Stepper("Rythme final", s.item_ramp, 0.3, 2.0, 0.1, "×{:.1f}",
                                  "intervalle à la fin", id="item_ramp")
                    yield Stepper("Objets max", s.max_items, 1, 10, 1, "{:g}", "en même temps", id="max_items")
                    yield Stepper("Sabliers max", s.max_hourglasses, 0, 10, 1, "{:g}", "par partie",
                                  id="max_hourglasses")
                with Vertical(classes="panel", id="p-sound"):
                    yield PixelSlider("Volume général", round(s.master_volume * 100), theme.GREEN_LIGHT,
                                      unit=" %", id="master_volume")
                    yield PixelSlider("Volume musique", round(s.music_volume * 100), theme.BLUE_LIGHT,
                                      unit=" %", id="music_volume")
                    yield Toggle("Musique de fond", s.music_enabled, id="music_enabled")
                with Vertical(classes="panel", id="p-gen"):
                    yield Stepper("Nombre de vidéos", s.video_count, 1, 500, 1, "{:g}", id="video_count")
                    with Horizontal(id="seed-row"):
                        yield Label("  " + "Seed".ljust(LABEL_W), id="seed-label")
                        yield Input(value=s.seed, placeholder="aléatoire", id="seed", max_length=40)
                    yield Toggle("Sous-titres .srt", s.export_srt, id="export_srt")
                    yield Static(id="gen-info")
            with Vertical(id="right"):
                with Vertical(classes="panel", id="p-arena"):
                    yield Arena(id="arena")
                    yield RunStatus(id="run")
                with Vertical(classes="panel", id="p-log"):
                    yield Journal(id="log", markup=False, wrap=True, max_lines=500, min_width=20)
        yield Footer()

    def on_mount(self) -> None:
        titles = {
            "p-game": ("PARTIE", ""),
            "p-items": ("OBJETS", "probabilité d'apparition"),
            "p-spawn": ("APPARITION", ""),
            "p-sound": ("SON", ""),
            "p-gen": ("GÉNÉRATION", ""),
            "p-arena": ("ATELIER", ""),
            "p-log": ("JOURNAL", ""),
        }
        for pid, (title, subtitle) in titles.items():
            panel = self.query_one(f"#{pid}")
            panel.border_title = f" {title} "
            if subtitle:
                panel.border_subtitle = f" {subtitle} "
        self.refresh_derived()
        self.refresh_stats()
        self.log_line("●", "Atelier prêt. G pour générer, P pour un aperçu en direct.", theme.BLUE_LIGHT)
        self.query_one("#mode").focus()

    # ---- Réglages --------------------------------------------------------------------------

    def collect(self) -> cfg.Settings:
        s = self.s
        s.mode = self.query_one("#mode", Choice).value
        s.players = self.query_one("#players", Choice).value
        s.cube_size = int(self.query_one("#cube_size", Stepper).value)
        s.lives = int(self.query_one("#lives", Stepper).value)
        s.obstacles = int(self.query_one("#obstacles", Stepper).value)
        s.speed_ramp = round(self.query_one("#speed_ramp", Stepper).value, 2)
        for kind in ITEM_KINDS:
            setattr(s, f"prob_{kind}", float(self.query_one(f"#prob_{kind}", PixelSlider).value))
        s.item_interval = float(self.query_one("#item_interval", Stepper).value)
        s.item_ramp = round(self.query_one("#item_ramp", Stepper).value, 2)
        s.max_items = int(self.query_one("#max_items", Stepper).value)
        s.max_hourglasses = int(self.query_one("#max_hourglasses", Stepper).value)
        s.master_volume = self.query_one("#master_volume", PixelSlider).value / 100
        s.music_volume = self.query_one("#music_volume", PixelSlider).value / 100
        s.music_enabled = self.query_one("#music_enabled", Toggle).value
        s.video_count = int(self.query_one("#video_count", Stepper).value)
        s.seed = self.query_one("#seed", Input).value.strip()
        s.export_srt = self.query_one("#export_srt", Toggle).value
        return s

    def push_settings(self) -> None:
        """Met les widgets aux valeurs de self.s sans déclencher d'enregistrement."""
        s = self.s
        self._loading = True
        try:
            self.query_one("#mode", Choice).set_value(s.mode, notify=False)
            self.query_one("#players", Choice).set_value(s.players if s.players in (2, 3, 4) else 0, notify=False)
            for name in ("cube_size", "lives", "obstacles", "speed_ramp"):
                self.query_one(f"#{name}", Stepper).set_value(getattr(s, name), notify=False)
            for kind in ITEM_KINDS:
                self.query_one(f"#prob_{kind}", PixelSlider).set_value(getattr(s, f"prob_{kind}"), notify=False)
            self.query_one("#item_interval", Stepper).set_value(s.item_interval, notify=False)
            self.query_one("#item_ramp", Stepper).set_value(s.item_ramp, notify=False)
            self.query_one("#max_items", Stepper).set_value(s.max_items, notify=False)
            self.query_one("#max_hourglasses", Stepper).set_value(s.max_hourglasses, notify=False)
            self.query_one("#master_volume", PixelSlider).set_value(s.master_volume * 100, notify=False)
            self.query_one("#music_volume", PixelSlider).set_value(s.music_volume * 100, notify=False)
            self.query_one("#music_enabled", Toggle).set_value(s.music_enabled, notify=False)
            self.query_one("#video_count", Stepper).set_value(s.video_count, notify=False)
            self.query_one("#seed", Input).value = s.seed
            self.query_one("#export_srt", Toggle).set_value(s.export_srt, notify=False)
        finally:
            self._loading = False

    @on(Row.Changed)
    @on(Input.Changed, "#seed")
    def on_setting_changed(self) -> None:
        if self._loading:
            return
        self.collect()
        self.refresh_derived()
        if self._save_timer is not None:
            self._save_timer.stop()
        self._save_timer = self.set_timer(0.4, self.save_now)

    def save_now(self) -> None:
        """Enregistre les réglages de l'interface en conservant les clés avancées de config.json."""
        self._save_timer = None
        self.collect()
        disk = cfg.load()
        for name in MANAGED:
            setattr(disk, name, getattr(self.s, name))
        try:
            cfg.save(disk)
        except OSError as exc:
            self.log_line("✗", f"Impossible d'enregistrer config.json : {exc}", theme.RED)
            return
        self.s = disk

    def refresh_derived(self) -> None:
        s = self.s
        mode = modes.BY_KEY.get(s.mode)
        # un mode impose ses probabilités : les notes montrent celles qui seront vraiment utilisées
        shown = modes.apply(s, mode)
        weights, pcts = shown.item_weights(), shown.item_percentages()
        unit = "réel" if mode is None else "mode"
        for kind in ITEM_KINDS:
            slider = self.query_one(f"#prob_{kind}", PixelSlider)
            if s.mode == modes.RANDOM:
                slider.note = "selon mode"
            else:
                slider.note = "jamais" if weights[kind] <= 0 else f"{pcts[kind]:5.1f} % {unit}"
            # les jauges suivent le mode ; les valeurs de l'utilisateur reviennent en classique
            slider.override = None if mode is None else weights[kind]
        for name in LOCKABLE:
            locked = mode is not None and name in mode.overrides
            self.query_one(f"#{name}", Stepper).override = getattr(shown, name) if locked else None
        items, spawn = self.query_one("#p-items"), self.query_one("#p-spawn")
        if s.mode == modes.CLASSIC:
            items.border_subtitle = " probabilité d'apparition "
            spawn.border_subtitle = ""
            pitch = Text("  réglages ci-dessous, objets au choix\n  " + modes.summary(s), style=theme.GREY)
        elif mode is None:
            items.border_subtitle = " tirées avec le mode "
            spawn.border_subtitle = " selon le mode "
            pitch = Text("  un mode différent à chaque vidéo", style=theme.GREY)
        else:
            items.border_subtitle = f" imposées par {mode.label} "
            spawn.border_subtitle = f" imposée par {mode.label} "
            pitch = Text("  " + mode.pitch, style=theme.GREY_LIGHT)
            pitch.append("\n  " + modes.summary(shown), style=f"bold {theme.YELLOW}")
        self.query_one("#mode-info", Static).update(pitch)

        # durée selon le mode (aléatoire : du mode le plus court au plus long)
        variants = [modes.apply(s, m) for m in modes.MODES] if s.mode == modes.RANDOM else [shown]
        spans = [video_seconds(v) for v in variants]
        base, longest = round(min(a for a, _ in spans)), round(max(b for _, b in spans))
        duration = f"{base:g} s" if longest == base else f"{base:g} – {longest:g} s"
        files = ".mp4 + .srt" if s.export_srt else ".mp4"
        info = Text()
        for i, (k, v) in enumerate((("Durée par vidéo", duration), ("Sortie", f"{s.output_dir}/  {files}"))):
            if i:
                info.append("\n")
            info.append("  " + k.ljust(LABEL_W), style=theme.GREY)
            info.append(v, style=theme.GREY_LIGHT)
        self.query_one("#gen-info", Static).update(info)

        run = self.query_one(RunStatus)
        if run.phase != "run":
            n = s.video_count
            what = f"{n} vidéo{'s' if n > 1 else ''}"
            if s.seed:
                seed_txt = f"seed {s.seed}" if n == 1 else f"seeds {s.seed}, +1, +2…"
            else:
                seed_txt = "seeds aléatoires"
            if run.phase == "idle":
                run.set_state("idle", f"{what} à générer · {seed_txt}")

    def refresh_stats(self) -> None:
        n = count_videos(self.s)
        self.query_one("#top-stats", Static).update(Text.assemble(
            ("Dossier ", theme.GREY), (f"{self.s.output_dir}/", theme.YELLOW_LIGHT),
            (f"  ·  {n} vidéo{'s' if n > 1 else ''}", theme.GREY_LIGHT)))

    # ---- Journal ---------------------------------------------------------------------------

    def log_line(self, icon: str, message: str | Text, color: str) -> None:
        line = Text(datetime.now().strftime("%H:%M:%S "), style=theme.GREY_DARK)
        line.append(f"{icon} ", style=f"bold {color}")
        line.append_text(message if isinstance(message, Text) else team_text(message, theme.GREY_LIGHT))
        self.query_one(Journal).write(line)

    # ---- Actions ---------------------------------------------------------------------------

    @property
    def running(self) -> bool:
        return self.proc is not None

    def check_action(self, action: str, parameters: tuple) -> bool | None:
        if action == "cancel":
            return self.running
        if action in ("generate", "reload"):
            return None if self.running else True
        return True

    def action_generate(self) -> None:
        if self.running:
            return
        if self._save_timer is not None:
            self._save_timer.stop()
        self.save_now()
        s = self.s
        cmd = [python_exe(), str(MAIN), "--generate", str(s.video_count), "--progress"]
        if s.seed:
            cmd += ["--seed", s.seed]
        self.run_generation(cmd, s.video_count)

    @work(exclusive=True, group="generate")
    async def run_generation(self, cmd: list[str], total: int) -> None:
        run, arena = self.query_one(RunStatus), self.query_one(Arena)
        env = dict(os.environ, PYTHONIOENCODING="utf-8", PYTHONUNBUFFERED="1")
        try:
            proc = await asyncio.create_subprocess_exec(
                *cmd, cwd=str(ROOT), stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.STDOUT,
                env=env, creationflags=NO_WINDOW)
        except OSError as exc:
            self.log_line("✗", f"Impossible de lancer la génération : {exc}", theme.RED)
            run.set_state("error", "lancement impossible")
            return
        self.proc, self.cancelled = proc, False
        self.refresh_bindings()
        run.start(total)
        arena.turbo = True
        self.log_line("▶", f"Génération de {total} vidéo{'s' if total > 1 else ''}…", theme.YELLOW)
        done, errors, tail = 0, 0, []
        try:
            async for raw in proc.stdout:
                line = raw.decode("utf-8", "replace").rstrip()
                kind, _, rest = line.partition(" ")
                if kind == "PROGRESS":
                    i, n, pct = (int(x) for x in rest.split())
                    run.progress(i, n, pct)
                elif kind == "DONE":
                    done += 1
                elif kind == "RESULT":
                    info = json.loads(rest)
                    msg = team_text(f"{Path(info['path']).name}  ", theme.WHITE)
                    if info.get("mode"):
                        msg.append(f"{info['mode']} · ", style=f"bold {theme.YELLOW}")
                    msg.append(f"{info['duration']:.0f} s · {info['cubes']} cubes · ", style=theme.GREY)
                    msg.append_text(team_text(info["summary"], theme.GREY_LIGHT))
                    self.log_line("✓", msg, theme.GREEN_LIGHT)
                    arena.announce(f" {info['summary']} ")
                    self.refresh_stats()
                elif kind == "ERROR":
                    errors += 1
                    self.log_line("✗", f"seed {rest}", theme.RED)
                elif line.strip():
                    tail = (tail + [line])[-12:]
            code = await proc.wait()
        finally:
            self.proc = None
            arena.turbo = False
            self.refresh_bindings()

        plural = "s" if done > 1 else ""
        if self.cancelled:
            run.set_state("cancel", f"{done} vidéo{plural} terminée{plural} avant l'annulation")
            self.log_line("■", "Génération annulée.", theme.GREY_LIGHT)
        elif errors or code != 0:
            run.set_state("error", f"{done} vidéo{plural} OK · {max(errors, 1)} erreur(s)")
            if not errors:
                for line in tail[-6:]:
                    self.log_line("│", Text(line, style=theme.RED_LIGHT), theme.RED)
            self.notify(f"{max(errors, 1)} erreur(s), voir le journal.", title="Génération", severity="error")
        else:
            run.set_state("done", f"{done} vidéo{plural} dans {self.s.output_dir}/ · O pour ouvrir le dossier")
            self.log_line("★", f"Terminé : {done} vidéo{plural} prête{plural}.", theme.YELLOW)
            self.notify(f"{done} vidéo{plural} prête{plural} dans {self.s.output_dir}/", title="Génération terminée")
        self.refresh_stats()

    def action_cancel(self) -> None:
        if self.proc is not None:
            self.cancelled = True
            try:
                self.proc.terminate()
            except ProcessLookupError:
                pass

    def action_preview(self) -> None:
        self.save_now()
        cmd = [python_exe(), str(MAIN), "--preview"]
        if self.s.seed:
            cmd += ["--seed", self.s.seed]
        self.log_line("▶", "Aperçu lancé · ESPACE pause · R nouvelle partie · S zones · ÉCHAP fermer",
                      theme.BLUE_LIGHT)
        self.run_preview(cmd)

    @work(group="preview")
    async def run_preview(self, cmd: list[str]) -> None:
        try:
            proc = await asyncio.create_subprocess_exec(
                *cmd, cwd=str(ROOT), stdout=asyncio.subprocess.DEVNULL, stderr=asyncio.subprocess.PIPE,
                creationflags=NO_WINDOW)
        except OSError as exc:
            self.log_line("✗", f"Aperçu impossible : {exc}", theme.RED)
            return
        _, err = await proc.communicate()
        if proc.returncode:
            lines = [ln for ln in err.decode("utf-8", "replace").splitlines() if ln.strip()]
            self.log_line("✗", f"L'aperçu s'est arrêté : {lines[-1] if lines else proc.returncode}", theme.RED)
        else:
            self.log_line("●", "Aperçu fermé.", theme.GREY)

    def action_open_folder(self) -> None:
        d = videos_dir(self.s)
        d.mkdir(parents=True, exist_ok=True)
        _open_path(d)
        self.log_line("●", f"Dossier ouvert : {d}", theme.GREY)

    def action_open_config(self) -> None:
        self.save_now()
        _open_path(cfg.CONFIG_PATH)
        self.log_line("●", "config.json ouvert (accroches, durées, vitesses…). R pour recharger après modification.",
                      theme.BLUE_LIGHT)

    def action_reload(self) -> None:
        if self.running:
            return
        self.s = cfg.load()
        self.push_settings()
        self.refresh_derived()
        self.refresh_stats()
        self.log_line("●", "Réglages rechargés depuis config.json.", theme.BLUE_LIGHT)

    def action_request_quit(self) -> None:
        if not self.running:
            self.save_now()
            self.app.exit()
            return

        def answered(quit_: bool | None) -> None:
            if quit_:
                self.action_cancel()
                self.save_now()
                self.app.exit()

        self.app.push_screen(ConfirmQuit(), answered)

    def on_unmount(self) -> None:
        self.action_cancel()


def _open_path(path: Path) -> None:
    if os.name == "nt":
        os.startfile(str(path))
    else:
        subprocess.Popen(["xdg-open", str(path)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


# ---- Application --------------------------------------------------------------------------

CSS = f"""
Screen {{ background: {theme.NAVY_DARK}; }}

#splash {{ align: center middle; width: 100%; height: 100%; }}
#splash > Static {{ width: 100%; height: auto; text-align: center; }}
#splash-logo {{ margin-bottom: 1; }}
#splash-tagline {{ margin-bottom: 2; }}
#splash-hint {{ margin-top: 2; }}

#top {{ height: 4; margin: 1 2 0 2; }}
#top-logo {{ width: {logo.COMPACT_WIDTH + 2}; }}
#top-info {{ padding-left: 2; border-left: tall {theme.GREY_DARK}; }}
#body {{ height: 1fr; margin: 0 1; }}
#left {{ width: 67; scrollbar-size-vertical: 1; }}
#right {{ width: 1fr; }}
#top-info > Static, RunStatus {{ text-wrap: nowrap; text-overflow: ellipsis; }}
Screen.-narrow #left {{ width: 54; }}
Screen.-short #p-log {{ height: 7; }}

.panel {{
    border: round {theme.GREY_DARK};
    border-title-color: {theme.YELLOW};
    border-title-style: bold;
    border-subtitle-color: {theme.GREY};
    border-subtitle-align: right;
    padding: 0 1;
    height: auto;
    margin: 1 1 0 0;
}}
.panel:focus-within {{ border: round {theme.YELLOW}; }}
#p-arena {{ height: 1fr; border: round {theme.GREY_DARK}; }}
#p-log {{ height: 11; margin: 1 1 1 0; }}
#run {{ margin-top: 1; }}

#seed-row {{ height: 1; }}
#seed-label {{ width: {LABEL_W + 2}; color: {theme.GREY_LIGHT}; }}
#seed-row:focus-within #seed-label {{ color: {theme.YELLOW}; text-style: bold; }}
#seed {{ height: 1; width: 24; border: none; padding: 0 1; background: {theme.FLOOR_B}; }}
#seed:focus {{ background: {theme.GREY_DARK}; }}
#gen-info {{ margin-top: 1; }}
#mode-info {{ height: auto; margin-bottom: 1; }}

Journal {{ background: {theme.NAVY_DARK}; scrollbar-size-vertical: 1; overflow-x: hidden; }}

ConfirmQuit {{ align: center middle; background: {theme.BLACK} 60%; }}
#dialog {{ width: 62; height: auto; padding: 1 2; border: round {theme.RED}; background: {theme.FLOOR_A}; }}
#dialog > Static {{ margin-bottom: 1; }}
#dialog-keys {{ margin: 1 0 0 0; }}

Footer {{ background: {theme.FLOOR_A}; }}
"""


class RIPaintApp(App):
    TITLE = "RIPaint"
    CSS = CSS
    ENABLE_COMMAND_PALETTE = False
    HORIZONTAL_BREAKPOINTS = [(0, "-narrow"), (120, "-wide")]
    VERTICAL_BREAKPOINTS = [(0, "-short"), (36, "-tall")]
    BINDINGS = [Binding("ctrl+c", "quit_any", show=False, priority=True)]

    def on_mount(self) -> None:
        self.register_theme(Theme(
            name="ripaint", primary=theme.YELLOW, secondary=theme.BLUE_LIGHT, accent=theme.MAGENTA,
            foreground=theme.WHITE, background=theme.NAVY_DARK, surface=theme.FLOOR_A, panel=theme.FLOOR_B,
            success=theme.GREEN_LIGHT, warning=theme.ORANGE, error=theme.RED, dark=True,
            variables={
                "footer-background": theme.FLOOR_A,
                "footer-key-foreground": theme.YELLOW,
                "footer-description-foreground": theme.GREY_LIGHT,
                "input-selection-background": f"{theme.BLUE} 50%",
                "block-cursor-background": theme.YELLOW,
                "block-cursor-foreground": theme.BLACK,
            }))
        self.theme = "ripaint"
        self.push_screen(SplashScreen())

    def action_quit_any(self) -> None:
        if isinstance(self.screen, MainScreen):
            self.screen.action_request_quit()
        else:
            self.exit()


def run_app() -> None:
    RIPaintApp().run()
