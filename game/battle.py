"""Simulation complète d'une partie, image par image (60 images/s, pas fixe, déterministe).

La simulation ne joue aucun son et ne dessine rien : elle produit un état (lu par
render.py) et des listes d'événements sonores et de sous-titres horodatés.
"""

import math
import random
from dataclasses import dataclass, replace

import numpy as np

from audio.mixer import SoundEvent
from audio.sfx import BOUNCE_VARIANTS
from engine8bit import palette
from engine8bit.display import FPS

from audio import music
from . import items as item_logic
from . import formats, modes, physics, themes, variants
from .entities import Cube, Particle, Popup
from .layout import make_layout
from . import maps
from .scenario import make_scenario, random_direction
from .settings import Settings

TICK_ZONE = 5 * FPS
STUCK_CHECK = 30

# Déroulé d'une vidéo (en images)
TEASER_FRAMES = 36          # arène finale montrée en ouverture (« WHO WINS? »)
REWIND_FRAMES = 12          # « rembobinage » vers le début de la partie
END_FRAMES = 30             # « END! »
REVEAL_FRAMES = 150         # révélation des scores un par un, avec roulement de tambour
LOOP_FRAMES = 30            # retour à l'image d'ouverture (la vidéo boucle sans couture)
SLOWMO_FRAMES = 30          # ralenti : 0,5 s de vidéo à demi-vitesse
FOLLOW_TAP = 84             # image (depuis le début du 3-2-1) où la main appuie sur « + »
FOLLOW_BOX_H = 30           # hauteur de l'encadré « FOLLOW FOR MORE! » (en haut de l'arène)
LEAD_COOLDOWN = 360         # au moins 6 s entre deux « X LEADS! »
LEAD_MARGIN = 0.03          # nouvelle tête annoncée seulement avec 3 points d'avance
LEAD_START_DELAY = 240      # pas d'annonce de leader pendant les 4 premières secondes
NICKNAMES = ["BLAZE", "FROST", "TURBO", "NINJA", "ROCKY", "PIXEL", "COMET", "SPIKE", "BOLT", "NOVA",
             "VIPER", "ZIGGY", "MANGO", "ROCKET", "SHADOW", "BLITZ", "LUNA", "MAX", "TANK", "DUKE"]
# Killcam : zoom + ralenti sur un cube à une vie quand un coup fatal arrive sur lui
KILLCAM_FRAMES = 84         # durée du ralenti « avant le coup » (images de vidéo)
KILLCAM_RATE = 3            # la partie n'avance qu'une image sur 3 pendant la killcam
KILLCAM_MAX = 3             # au plus 3 killcams par vidéo (sinon le ralenti lasse)
KILLCAM_COOLDOWN = 4 * FPS
# Tempête (formats « survie ») : la zone sûre rétrécit et blesse les cubes restés dehors
STORM_MIN = 0.38            # taille finale de la zone (part de l'arène)
STORM_TICK = 72             # une blessure toutes les 1,2 s hors de la zone
END_DELAY = 90              # fin anticipée : 1,5 s après le dernier K.O.


@dataclass
class Ranked:
    idx: int                 # cube représentant du camp (le premier de l'équipe)
    team: str
    cells: int
    pct: float
    items: int
    alive: bool = True
    lives: int = 0
    label: str = ""          # texte affiché au classement (« 41.2% », « 3 HP », « K.O. »)
    score: float = 0.0       # longueur de la barre de classement (0 à 1)


@dataclass
class Result:
    ranking: list            # list[Ranked], du premier au dernier
    winner: int | None       # index du cube gagnant, None si égalité
    tied: list               # index des cubes à égalité parfaite (si égalité)
    by_items: bool           # départagé au nombre d'objets ramassés


def fixed_frames_seconds(settings: Settings) -> float:
    """Durée de la vidéo hors bataille (teaser, compte à rebours, fin), en secondes."""
    start = (TEASER_FRAMES + REWIND_FRAMES if settings.teaser else 0) + round(settings.intro_duration * FPS)
    return (start + round(settings.outro_duration * FPS)) / FPS


def default_battle_frames(settings: Settings) -> int:
    """Durée de la bataille hors sabliers : battle_duration, allongée si besoin pour que la
    vidéo dépasse toujours 1 minute (tiktok_rewards)."""
    frames = round(settings.battle_duration * FPS)
    if settings.tiktok_rewards:
        start = (TEASER_FRAMES + REWIND_FRAMES if settings.teaser else 0) + round(settings.intro_duration * FPS)
        need = round(settings.min_video_duration * FPS) - start - round(settings.outro_duration * FPS)
        frames = max(frames, need)
    return frames


def video_seconds(settings: Settings) -> tuple[float, float]:
    """Durée de la vidéo (sans sablier, avec tous les sabliers possibles), en secondes."""
    start = (TEASER_FRAMES + REWIND_FRAMES if settings.teaser else 0) + round(settings.intro_duration * FPS)
    base = (start + default_battle_frames(settings) + round(settings.outro_duration * FPS)) / FPS
    return base, base + settings.max_hourglasses * settings.hourglass_bonus


class Battle:
    def __init__(self, seed: int, settings: Settings, battle_frames: int | None = None):
        self.seed = seed
        # format (règle du jeu) puis mode (objets, rythme) ; certains formats ignorent le mode
        self.fmt = formats.resolve(seed, settings)
        self.mode = modes.resolve(seed, settings) if self.fmt.use_mode else None
        settings = modes.apply(settings, self.mode)
        settings = formats.apply(settings, self.fmt, seed)
        self.settings = settings
        self.theme = themes.resolve(seed, settings)
        self.music_style = music.resolve_style(seed, settings, self.mode, self.fmt)
        self.paints = self.fmt.paint
        self.survival = self.fmt.win == formats.SURVIVAL
        self.layout = make_layout(settings.safe_top, settings.safe_bottom, settings.safe_right,
                                  settings.arena_centered)
        self.W, self.H = self.layout.arena_w, self.layout.arena_h
        # obstacles d'abord (générateur à part), puis les cubes qui les évitent
        self.map_name, self.obstacles = maps.build(seed, settings, self.W, self.H)
        strict = getattr(settings, "map", "generated") != "generated"
        # animation « abonne-toi » : aucun cube ne démarre sous l'encadré du haut de l'arène
        reserved = 4 + FOLLOW_BOX_H + 12 + settings.cube_size / 2 if (settings.follow_prompt and strict) else 0
        self.scenario = make_scenario(seed, settings, self.W, self.H, self.obstacles,
                                      strict=strict, top_reserved=reserved)
        self.rng = self.scenario.rng
        self.fx = random.Random(seed * 31 + 7)        # aléatoire purement visuel
        # la variante remplace les couleurs tirées par le scénario (positions et seed inchangées)
        self.variant = variants.resolve(settings, seed)
        slots = [c.team for c in self.scenario.cubes]
        # camps : un cube par camp, ou des équipes (2 contre 2 : les cubes 0 et 2 contre 1 et 3)
        n_sides = max(1, len(slots) // max(1, self.fmt.team_size))
        lineup = [variants.BY_NAME[n] for n in settings.lineup if n in variants.BY_NAME]
        picked = lineup if len(lineup) == n_sides else self.variant.pick(seed, slots[:n_sides])
        self.competitors = [picked[i % n_sides] for i in range(len(slots))]
        self.side_of = [i % n_sides for i in range(len(slots))]
        self.sides = [[i for i in range(len(slots)) if self.side_of[i] == s] for s in range(n_sides)]
        if settings.cup_label:
            self.hook = "WHO WINS THE CUP?" if "FINAL" == settings.cup_label.split(" ")[0] else "TOP 2 GO THROUGH!"
        elif self.fmt.hook:
            self.hook = self.variant.adapt(self.fmt.hook)
        else:
            self.hook = self.variant.adapt(self.scenario.hook)
        self.grid = np.full((self.H, self.W), -1, dtype=np.int8)
        self.cubes = [Cube(i, self.competitors[i].name, c.x, c.y, c.dx, c.dy, settings.cube_size)
                      for i, c in enumerate(self.scenario.cubes)]
        # en duel (2 cubes), un K.O. laisse un seul cube repeindre toute l'arène : plus de vies
        self.start_lives = max(0, settings.lives)
        if len(self.cubes) == 2 and settings.lives > 0 and settings.duel_lives > 0:
            self.start_lives = settings.duel_lives
        for c in self.cubes:
            c.last_pos = (c.cx, c.cy)
            c.lives = self.start_lives
        for x0, y0, x1, y1 in self.obstacles:
            self.grid[y0:y1, x0:x1] = physics.OBSTACLE
        self.paintable = int((self.grid != physics.OBSTACLE).sum())   # cases qui comptent pour le score
        self.items = []
        self.aims = []
        self.bullets = []
        self.swipes = []
        self.bombs = []
        self.waves = []
        self.shake = 0
        self.particles: list[Particle] = []
        self.popups: list[Popup] = []
        self.events: list[SoundEvent] = []
        self.subtitles: list[tuple[int, int, str]] = []
        self.bonus_anims: list[int] = []
        self.timer_flash = 0
        self.hourglasses_spawned = 0
        self.hourglasses_taken = 0
        self.pair_cooldown: dict[tuple[int, int], int] = {}
        self.bounce_sound_at: dict[int, int] = {}      # dernier son de rebond par cube
        self.next_tick: int | None = None
        self.tick_parity = 0
        self.result: Result | None = None
        self.result_text = ""
        self.slowmo = 0
        self.flash = 0
        self.slashes = []                       # traits de coups (mode escalade)
        self.impact = 0                         # images d'impact noir et blanc restantes
        self.shake_amp = 1
        self.leader: int | None = None          # leader « officiel » (porte la couronne)
        self.last_lead_frame = -10 ** 6
        self.crown_jump: tuple | None = None    # (ancien leader, nouveau, image) pour l'animation
        self.lead_changes = 0
        self.league: dict | None = None         # classement de la ligue (fourni par l'export)
        self.cup: dict | None = None            # état de la PaintCup (fourni par l'export)
        names = random.Random(seed * 13 + 5).sample(NICKNAMES, len(self.cubes))
        # en équipes, les surnoms distinguent les deux cubes d'une même couleur
        show = settings.nicknames and (self.variant.nicknames or self.fmt.team_size > 1)
        self.nicknames = names if show else [""] * len(self.cubes)
        # killcam, tempête, fin anticipée, journal de la partie (pour la légende)
        self.slowmo_rate = 2
        self.cam_target: int | None = None
        self.cam_level = 0.0
        self.cam_hold = 0
        self.killcams = 0
        self.last_killcam = -10 ** 6
        self.killcam_victims: list[int] = []
        self.storm_rect: tuple | None = None
        self.ended_early = False
        self.ko_log: list[tuple[int, int]] = []
        self.pickup_log: dict[str, int] = {}
        self.timeline: list[list[int]] = []     # valeur de chaque camp, une fois par seconde

        self.frame = -1
        self.intro_start = (TEASER_FRAMES + REWIND_FRAMES) if settings.teaser else 0
        self.battle_start = self.intro_start + round(settings.intro_duration * FPS)
        self.outro_frames = round(settings.outro_duration * FPS)
        self.new_outro = self.outro_frames >= END_FRAMES + REVEAL_FRAMES + LOOP_FRAMES + 90
        if battle_frames is None:
            battle_frames = default_battle_frames(settings)
        self.base_battle_frames = battle_frames
        self.battle_end = self.battle_start + battle_frames
        self.storm_start = self.battle_start + round(self.fmt.storm * battle_frames) if self.fmt.storm else None
        self.storm_end = self.battle_start + round(0.92 * battle_frames)
        self.interval = max(1, round(settings.item_interval * FPS))
        self.next_spawn = self.battle_start + self.interval
        self.counts = np.zeros(len(self.cubes), dtype=np.int64)

        self.band = self.band_lines()
        parts = []
        if settings.cup_label:
            parts.append(f"PAINTCUP {settings.cup_label}!")
        if self.fmt.key != formats.CLASSIC:
            parts.append(self.fmt.name if self.fmt.name.endswith("!") else self.fmt.name + "!")
        if self.mode is not None:
            parts.append(f"{self.mode.name} MODE!")
        self.subtitle(0, self.battle_start, " ".join(parts + [self.hook]))
        if settings.teaser:
            self.subtitle(0, TEASER_FRAMES, "WHO WINS?")

        # Partie simulée à l'avance (même seed, même durée) : sert au teaser d'ouverture,
        # à la boucle de fin et à la ligue. La simulation étant déterministe et relative au GO,
        # l'arène finale est exactement celle de la vraie partie.
        self.final = None
        if settings.teaser or settings.league or settings.cup_label:
            pre = Battle(seed, replace(settings, teaser=False, league=False, cup_label=""), battle_frames)
            while not pre.done:
                pre.step()
            self.final = {
                "grid": pre.grid.copy(),
                "cubes": [(c.cx, c.cy, c.size, c.dead) for c in pre.cubes],
                "result": pre.result,
                "percentages": pre.percentages(),
                "duration": (self.battle_start + (pre.battle_end - pre.battle_start) + self.outro_frames) / FPS,
            }

    # ---- Utilitaires ---------------------------------------------------------------------

    @property
    def total_frames(self) -> int:
        return self.battle_end + self.outro_frames

    @property
    def done(self) -> bool:
        return self.frame + 1 >= self.total_frames

    @property
    def phase(self) -> str:
        if self.frame < self.intro_start:
            return "teaser"
        if self.frame < self.battle_start:
            return "intro"
        if self.frame < self.battle_end:
            return "battle"
        return "outro"

    def remaining_seconds(self) -> float:
        if self.frame < self.battle_start:
            return (self.battle_end - self.battle_start) / FPS
        return max(0.0, (self.battle_end - self.frame) / FPS)

    def scores_hidden(self) -> bool:
        """Pourcentages cachés (« ??% ») : teaser, dernières secondes et début de la fin."""
        if self.phase == "teaser":
            return True
        hide = round(self.settings.hide_final_scores * FPS)
        if hide <= 0:
            return False
        if self.phase == "battle":
            # formats « survie » : les vies restent visibles (le suspense, c'est qui tombe)
            return not self.survival and self.battle_end - self.frame <= hide
        return self.phase == "outro"

    def intensity(self) -> float:
        """Mode escalade : 0 au GO -> 1 à la fin du chrono de base (montée progressive, au carré)."""
        if not self.settings.escalation or self.frame < self.battle_start:
            return 0.0
        t = min(1.0, (self.frame - self.battle_start) / max(1, self.base_battle_frames))
        return t * t

    def max_items_now(self) -> int:
        return self.settings.max_items + (round(3 * self.intensity()) if self.settings.escalation else 0)

    def spawn_interval_now(self) -> int:
        """Images avant le prochain objet. Escalade : toutes les 5 s au début, ~1,4 s à la fin.
        Sinon : interval au GO -> interval x item_ramp à la fin du chrono de base (linéaire)."""
        if self.settings.escalation:
            return max(45, round(self.interval * (1 - 0.72 * self.intensity())))
        base = max(1, self.base_battle_frames)
        t = min(1.0, max(0.0, (self.frame - self.battle_start) / base))
        return max(1, round(self.interval * (1.0 + (self.settings.item_ramp - 1.0) * t)))

    def trigger_slowmo(self) -> None:
        if self.settings.slowmo and self.slowmo == 0 and self.phase == "battle":
            self.slowmo = SLOWMO_FRAMES
            self.slowmo_rate = 2
            self.flash = 3
            self.emit("slowmo")

    def band_lines(self) -> list[str]:
        """Bandeau du compte à rebours : coupe, format et mode (le plus important d'abord)."""
        lines = []
        if self.settings.cup_label:
            lines.append(self.settings.cup_label)
        elif self.fmt.key != formats.CLASSIC:
            lines.append(self.fmt.name)
        if self.mode is not None:
            lines.append(self.mode.name)
        return lines[:2]

    def allies(self, i: int, j: int) -> bool:
        """Même camp (le cube lui-même ou son coéquipier en 2 contre 2) : pas de dégâts entre eux."""
        return self.side_of[i] == self.side_of[j]

    def side_counts(self) -> list[int]:
        return [int(sum(self.counts[i] for i in side)) for side in self.sides]

    def side_lives(self) -> list[int]:
        return [sum(self.cubes[i].lives for i in side if not self.cubes[i].dead) for side in self.sides]

    def side_values(self) -> list[int]:
        """Ce qui fait gagner chaque camp : la peinture, ou les vies dans les formats « survie »."""
        return self.side_lives() if self.survival else self.side_counts()

    def standing(self, c: Cube) -> int:
        """Valeur du camp d'un cube (le plus faible reçoit le coup de pouce des objets)."""
        return self.side_values()[self.side_of[c.idx]]

    def alive_sides(self) -> set[int]:
        return {self.side_of[c.idx] for c in self.cubes if not c.dead}

    def percentages(self) -> list[float]:
        return [float(c) / self.paintable * 100 for c in self.counts]

    def side_percentages(self) -> list[float]:
        return [float(c) / self.paintable * 100 for c in self.side_counts()]

    # ---- Killcam ---------------------------------------------------------------------------

    def start_killcam(self, victim: Cube) -> None:
        """Un coup qui peut éliminer `victim` arrive : zoom sur lui et ralenti marqué, avant l'impact."""
        self.slowmo = KILLCAM_FRAMES
        self.slowmo_rate = KILLCAM_RATE
        self.cam_target = victim.idx
        self.cam_hold = KILLCAM_FRAMES + 12
        self.killcams += 1
        self.last_killcam = self.frame
        self.killcam_victims.append(victim.idx)
        self.emit("slowmo")

    def on_knock_out(self, cube: Cube) -> None:
        cube.ko_frame = self.frame
        self.ko_log.append((self.frame, cube.idx))
        if self.settings.killcam and self.settings.slowmo and self.phase == "battle":
            # on reste sur le cube éliminé le temps de le voir griser et rapetisser
            self.cam_target = cube.idx
            self.cam_hold = max(self.cam_hold, 54)
            if self.slowmo > 0:
                self.slowmo = max(self.slowmo, 36)
                return
        self.trigger_slowmo()

    def _threatened(self, c: Cube) -> bool:
        """Un coup capable d'éliminer `c` arrive-t-il dans les prochaines images ?"""
        s = self.settings
        for bl in self.bullets:
            if self.allies(bl.owner, c.idx):
                continue
            vx, vy = c.cx - bl.x, c.cy - bl.y
            along = vx * bl.dx + vy * bl.dy
            across = abs(vx * bl.dy - vy * bl.dx)
            speed = s.bullet_speed / FPS
            if 0 < along < speed * 24 and across <= c.half + 1 and c.invuln * speed < along:
                return True
        for bomb in self.bombs:
            radius = s.bomb_radius * self.cubes[bomb.owner].base_size / 11
            if (not self.allies(bomb.owner, c.idx) and bomb.frames_left <= 26 and c.invuln < bomb.frames_left
                    and math.hypot(c.cx - bomb.x, c.cy - bomb.y) <= radius + c.half):
                return True
        for sw in self.swipes:
            owner = self.cubes[sw.owner]
            radius = s.brush_radius * owner.size / owner.base_size
            if (not self.allies(sw.owner, c.idx) and c.idx not in sw.hit and c.invuln == 0
                    and math.hypot(c.cx - owner.cx, c.cy - owner.cy) <= radius + c.half):
                return True
        for w in self.waves:
            along, across = (c.cx, c.cy) if w.horizontal else (c.cy, c.cx)
            gap = abs(along - w.origin) - w.dist
            if (not self.allies(w.owner, c.idx) and c.idx not in w.hit and c.invuln == 0
                    and abs(across - w.band) <= w.half + c.half and 0 < gap < 30):
                return True
        if self.storm_rect is not None and c.invuln == 0:
            x0, y0, x1, y1 = self.storm_rect
            outside = not (x0 <= c.cx <= x1 and y0 <= c.cy <= y1)
            if outside and STORM_TICK - (self.frame - self.storm_start) % STORM_TICK <= 20:
                return True
        return False

    def _watch_threats(self) -> None:
        s = self.settings
        if (not (s.killcam and s.slowmo) or s.lives <= 0 or self.slowmo > 0 or self.killcams >= KILLCAM_MAX
                or self.frame - self.last_killcam < KILLCAM_COOLDOWN):
            return
        for c in self.cubes:
            if not c.dead and c.lives == 1 and self._threatened(c):
                self.start_killcam(c)
                return

    def _update_camera(self) -> None:
        if self.cam_hold > 0:
            self.cam_hold -= 1
            self.cam_level = min(1.0, self.cam_level + 0.12)
        elif self.cam_level > 0:
            self.cam_level = max(0.0, self.cam_level - 0.06)
            if self.cam_level == 0:
                self.cam_target = None

    # ---- Tempête ---------------------------------------------------------------------------

    def _storm(self, f: int) -> None:
        if self.storm_start is None or f < self.storm_start:
            return
        if f == self.storm_start:
            self.popup("STORM IS COMING!", palette.PURPLE_LIGHT, duration=90)
            self.emit("speed_up")
        k = min(1.0, (f - self.storm_start) / max(1, self.storm_end - self.storm_start))
        scale = 1 - (1 - STORM_MIN) * k
        w, h = self.W * scale, self.H * scale
        self.storm_rect = ((self.W - w) / 2, (self.H - h) / 2, (self.W + w) / 2, (self.H + h) / 2)
        # plus qu'un camp debout : la tempête l'épargne (c'est le gagnant)
        if (f - self.storm_start) % STORM_TICK == STORM_TICK - 1 and len(self.alive_sides()) > 1:
            x0, y0, x1, y1 = self.storm_rect
            for c in self.cubes:
                if not c.dead and not (x0 <= c.cx <= x1 and y0 <= c.cy <= y1) and c.invuln == 0:
                    c.hit_anim = item_logic.HIT_ANIM
                    self.sparkle(self.layout.arena_x + c.cx, self.layout.arena_y + c.cy, palette.PURPLE_LIGHT, 8)
                    item_logic.damage(self, c)

    def _check_last_standing(self, f: int) -> None:
        if not self.fmt.early_end or self.ended_early or len(self.sides) < 2:
            return
        if len(self.alive_sides()) <= 1:
            # dernier debout : victoire tout de suite (la durée > 1 min est assurée par le
            # garde-fou, qui donne plus de vies si la partie pré-simulée finit trop tôt)
            self.ended_early = True
            self.battle_end = min(self.battle_end, f + END_DELAY)
            self.popup("LAST ONE STANDING!", palette.YELLOW_LIGHT, duration=80)

    def speed_multiplier(self) -> float:
        """Accélération progressive : x1 au GO, x speed_ramp à la fin du chrono de base
        (le temps ajouté par les sabliers reste à la vitesse maximale)."""
        base = max(1, self.base_battle_frames)
        t = min(1.0, max(0.0, (self.frame - self.battle_start) / base))
        return 1.0 + (self.settings.speed_ramp - 1.0) * t

    def emit(self, name: str, gain: float = 1.0, frame: int | None = None) -> None:
        self.events.append(SoundEvent(self.frame if frame is None else frame, name, gain))

    def subtitle(self, start: int, end: int, text: str) -> None:
        self.subtitles.append((start, end, text))

    def popup(self, text: str, color, duration: int = 84, anchor: str = "top") -> None:
        self.popups.append(Popup(text, color, self.frame, duration, anchor))
        self.subtitle(self.frame, self.frame + duration, text)

    def sparkle(self, x: float, y: float, color, n: int) -> None:
        for _ in range(n):
            a = self.fx.uniform(0, 2 * math.pi)
            sp = self.fx.uniform(15, 45)
            life = self.fx.randint(10, 22)
            self.particles.append(Particle(x, y, math.cos(a) * sp, math.sin(a) * sp, color, life, life))

    def splat(self, x: float, y: float, idx: int, r: float) -> None:
        """Explosion de peinture : disque + gouttelettes (compte dans le score)."""
        physics.paint_disc(self.grid, x, y, r, idx)
        for _ in range(self.rng.randint(4, 7)):
            a = self.rng.uniform(0, 2 * math.pi)
            d = self.rng.uniform(r, r + 5)
            physics.paint_disc(self.grid, x + math.cos(a) * d, y + math.sin(a) * d, self.rng.choice([1, 1.5, 2]), idx)
        color = variants.colors(self.cubes[idx].team)[1]
        light = variants.colors(self.cubes[idx].team)[2]
        for k in range(16):
            a = self.fx.uniform(0, 2 * math.pi)
            sp = self.fx.uniform(20, 70)
            life = self.fx.randint(12, 26)
            self.particles.append(Particle(self.layout.arena_x + x, self.layout.arena_y + y,
                                           math.cos(a) * sp, math.sin(a) * sp, light if k % 3 == 0 else color,
                                           life, life))

    # ---- Boucle principale ---------------------------------------------------------------

    def step(self) -> None:
        self.frame += 1
        f = self.frame
        skip = False
        if f < self.intro_start:
            if f == TEASER_FRAMES:
                self.emit("rewind")
        elif f < self.battle_start:
            self._intro(f)
        elif f < self.battle_end:
            if f == self.battle_start:
                self._start_battle()
            if self.slowmo > 0:
                # ralenti : la partie n'avance qu'une image sur deux (une sur trois pendant une
                # killcam) ; le chrono, lui, continue
                self.slowmo -= 1
                skip = self.slowmo % self.slowmo_rate != 0
                if self.slowmo == 0:
                    self.slowmo_rate = 2
            if skip:
                self._ticks(f)
            else:
                self._battle(f)
        else:
            if self.result is None:
                self._finish()
            self._outro(f)
        if not skip:
            self._update_particles()
        self._update_camera()
        if self.flash > 0:
            self.flash -= 1
        if self.impact > 0:
            self.impact -= 1
        if self.slashes:
            self.slashes = [s for s in self.slashes if self.frame - s.start < s.life]
        if self.shake == 0:
            self.shake_amp = 1
        if self.timer_flash > 0:
            self.timer_flash -= 1
        if self.shake > 0:
            self.shake -= 1

    def _intro(self, f: int) -> None:
        if self.settings.follow_prompt:
            if f == self.intro_start:
                self.subtitle(f, self.battle_start, "FOLLOW FOR MORE!")
            if f == self.intro_start + FOLLOW_TAP:
                self.emit("follow_tap")
        if (self.battle_start - f) % FPS == 0:
            n = (self.battle_start - f) // FPS
            self.emit("count")
            self.subtitle(f, f + FPS, str(n))

    def _start_battle(self) -> None:
        self.emit("go")
        self.emit("music_start")
        self.emit("paint_start")
        self.subtitle(self.frame, self.frame + 48, "GO!")
        for c in self.cubes:
            self._paint_under(c)

    def _battle(self, f: int) -> None:
        s = self.settings
        if f >= self.next_spawn:
            item_logic.try_spawn(self)
            self.next_spawn += self.spawn_interval_now()

        for c in self.cubes:
            if c.stun > 0:
                c.stun -= 1
                if c.stun == 0:
                    self.emit("wake")
                    self.sparkle(self.layout.arena_x + c.cx, self.layout.arena_y + c.cy - c.half,
                                 palette.YELLOW_LIGHT, 6)
            if c.slow > 0:
                c.slow -= 1
            item_logic.update_resize(self, c)
            item_logic.update_cube_timers(self, c)

        ramp = self.speed_multiplier() * (1 + 0.35 * self.intensity())
        base = self.base_battle_frames
        if s.speed_ramp > 1.05 and f - self.battle_start in (base // 3, 2 * base // 3):
            self.popup("SPEED UP!", palette.WHITE, duration=72)
            self.emit("speed_up")
        for c in self.cubes:
            speed = s.cube_speed * ramp * (s.slow_factor if c.slow > 0 else 1.0)
            if c.boots > 0:
                speed *= s.boots_factor
            if physics.move(c, speed, self.W, self.H, self.obstacles):
                physics.jitter(c, self.rng)
                # pas plus d'un « bip » toutes les 8 images par cube (zigzag dans un couloir étroit)
                if f - self.bounce_sound_at.get(c.idx, -999) >= 8:
                    self.bounce_sound_at[c.idx] = f
                    self.emit(f"bounce{self.fx.randrange(BOUNCE_VARIANTS)}")

        for pair in physics.resolve_collisions(self.cubes, self.W, self.H, obstacles=self.obstacles):
            if f - self.pair_cooldown.get(pair, -999) > 12:
                self.emit("cube_hit")
                a, b = self.cubes[pair[0]], self.cubes[pair[1]]
                self.sparkle(self.layout.arena_x + (a.cx + b.cx) / 2, self.layout.arena_y + (a.cy + b.cy) / 2,
                             palette.WHITE, 4)
                if self.survival:
                    self._stomp(a, b)
            self.pair_cooldown[pair] = f

        for c in self.cubes:
            if c.active:
                self._paint_under(c)

        item_logic.update_magnets(self)
        item_logic.check_pickups(self)
        item_logic.update_aims(self)
        item_logic.update_bullets(self)
        item_logic.update_swipes(self)
        item_logic.update_bombs(self)
        item_logic.update_waves(self)
        self._storm(f)
        self._watch_threats()
        self._check_last_standing(f)

        if (f - self.battle_start) % STUCK_CHECK == 0 and f > self.battle_start:
            for c in self.cubes:
                if c.active and c.slow <= 0 and c.resize_anim <= 0:
                    moved = math.hypot(c.cx - c.last_pos[0], c.cy - c.last_pos[1])
                    if moved < 2.0:
                        c.dx, c.dy = random_direction(self.rng)
                c.last_pos = (c.cx, c.cy)

        self._ticks(f)
        self.counts = np.bincount(self.grid[self.grid >= 0].ravel(), minlength=len(self.cubes))
        if (f - self.battle_start) % FPS == 0:
            self.timeline.append(self.side_values())
        self._lead(f)

    def _stomp(self, a: Cube, b: Cube) -> None:
        """Formats « survie » : un cube géant (potion) ou lancé (bottes) blesse celui qu'il percute."""
        if self.allies(a.idx, b.idx):
            return
        for hitter, victim in ((a, b), (b, a)):
            if hitter.active and (hitter.big or hitter.boots > 0) and not victim.dead and victim.invuln == 0 \
                    and not (victim.big and not hitter.big):
                victim.hit_anim = item_logic.HIT_ANIM
                vx, vy = victim.cx - hitter.cx, victim.cy - hitter.cy
                d = math.hypot(vx, vy) or 1.0
                victim.kb_x, victim.kb_y = vx / d * item_logic.KNOCKBACK_SPEED, vy / d * item_logic.KNOCKBACK_SPEED
                hitter.hits += 1
                self.popup("STOMP!", variants.colors(hitter.team)[2], duration=50,
                           anchor="bottom" if victim.cy < self.H / 2 else "top")
                self.emit("brush_hit")
                item_logic.damage(self, victim)
                return

    def _lead(self, f: int) -> None:
        """Annonce « X LEADS! » quand un autre camp prend nettement la tête (pas pendant les
        dernières secondes, où les scores sont cachés). Formats « survie » : pas de leader."""
        if self.survival:
            return
        counts = np.array(self.side_counts())
        top = int(counts.max())
        if top <= 0 or int((counts == top).sum()) != 1:
            return
        leader = int(counts.argmax())
        if self.leader is None:
            self.leader = leader
            return
        if leader == self.leader or self.scores_hidden() or f - self.battle_start < LEAD_START_DELAY:
            return
        margin = int(counts[leader] - counts[self.leader])
        if margin < LEAD_MARGIN * self.paintable or f - self.last_lead_frame < LEAD_COOLDOWN:
            return
        self.crown_jump = (self.sides[self.leader][0], self.sides[leader][0], f)
        self.leader = leader
        self.last_lead_frame = f
        self.lead_changes += 1
        if self.settings.lead_announce:
            c = self.cubes[self.sides[leader][0]]
            self.popup(f"{c.team} LEADS!", variants.colors(c.team)[2], duration=72)
            self.emit("lead_change")

    def _paint_under(self, c: Cube) -> None:
        x0, y0, x1, y1 = c.rect()
        physics.paint_rect(self.grid, x0, y0, x1, y1, c.idx)
        if c.roller > 0:
            physics.paint_disc(self.grid, c.cx, c.cy, item_logic.paint_size(self, c), c.idx)

    def _ticks(self, f: int) -> None:
        remaining = self.battle_end - f
        if remaining > TICK_ZONE:
            self.next_tick = None
            return
        if self.next_tick is None or f >= self.next_tick:
            self.emit("tick" if self.tick_parity == 0 else "tock")
            self.tick_parity ^= 1
            self.next_tick = f + max(6, round(30 * remaining / TICK_ZONE) + 6)

    def _finish(self) -> None:
        f = self.frame
        self.emit("buzzer")
        self.emit("music_stop")
        self.emit("paint_stop")
        self.items.clear()
        self.aims.clear()
        self.bullets.clear()
        self.swipes.clear()
        self.bombs.clear()
        self.waves.clear()
        self.counts = np.bincount(self.grid[self.grid >= 0].ravel(), minlength=len(self.cubes))
        self.result = compute_result(self.cubes, self.counts, self.paintable, self.sides,
                                     self.fmt.win, max(1, self.start_lives), self.paints)
        r = self.result
        if self.new_outro:
            # END! -> révélation des scores (du dernier au premier, roulement de tambour) -> gagnant
            reveal = f + END_FRAMES
            win_at = reveal + REVEAL_FRAMES
            self.emit("drumroll", frame=reveal)
            slot = REVEAL_FRAMES / len(self.cubes)
            for k in range(len(self.cubes)):
                self.emit("reveal_ding", frame=reveal + round(slot * k + slot * 0.75))
            self.subtitle(reveal, win_at, "RESULTS...")
        else:
            win_at = f + 54
        if r.winner is not None:
            self.emit("victory", frame=win_at)
            w = r.ranking[0]
            text = f"{w.team} WINS! {w.label}"
        else:
            self.emit("draw", frame=win_at)
            text = "TIE! " + " / ".join(self.cubes[i].team for i in r.tied)
        self.result_text = text
        self.subtitle(win_at if self.new_outro else f + 30, self.total_frames, text)

    def _outro(self, f: int) -> None:
        r = self.result
        start = END_FRAMES + REVEAL_FRAMES if self.new_outro else 30
        end = self.total_frames - (LOOP_FRAMES if self.new_outro else 0)
        if start <= f - self.battle_end and f < end and f % 2 == 0:
            colors = ([variants.colors(self.cubes[r.winner].team)[1], variants.colors(self.cubes[r.winner].team)[2],
                       palette.WHITE] if r.winner is not None else [palette.GREY_LIGHT, palette.WHITE])
            x = self.fx.uniform(self.layout.safe_x0, self.layout.safe_x1)
            life = self.fx.randint(80, 140)
            self.particles.append(Particle(x, self.layout.safe.top - 2, self.fx.uniform(-8, 8),
                                           self.fx.uniform(15, 35), self.fx.choice(colors), life, life,
                                           gravity=6, layer=1))

    def _update_particles(self) -> None:
        alive = []
        for p in self.particles:
            p.x += p.vx / FPS
            p.y += p.vy / FPS
            p.vy += p.gravity / FPS
            p.vx *= 0.97 if p.layer == 0 else 1.0
            p.vy *= 0.97 if p.layer == 0 else 1.0
            p.life -= 1
            if p.life > 0:
                alive.append(p)
        self.particles = alive


def fmt_pct(p: float) -> str:
    return f"{p:.1f}%"


def compute_result(cubes: list[Cube], counts, total_cells: int, sides: list | None = None,
                   win: str = formats.PAINT, start_lives: int = 1, paints: bool = True) -> Result:
    """Classement des camps. « paint » : la plus grande surface (départage aux objets ramassés).
    « survival » : les camps encore debout d'abord (le plus de vies), puis les éliminés du plus
    tardif au plus précoce ; la peinture (ou les coups portés, sans peinture) départage."""
    sides = sides or [[i] for i in range(len(cubes))]
    ranked = []
    for side in sides:
        idx = side[0]
        cells = int(sum(counts[i] for i in side))
        alive = any(not cubes[i].dead for i in side)
        lives = sum(cubes[i].lives for i in side if not cubes[i].dead)
        r = Ranked(idx, cubes[idx].team, cells, cells / total_cells * 100, sum(cubes[i].items for i in side),
                   alive, lives)
        r.ko = max(cubes[i].ko_frame for i in side) if not alive else 10 ** 9
        r.hits = sum(cubes[i].hits for i in side)
        ranked.append(r)
    if win == formats.SURVIVAL:
        def key(r):
            return (-int(r.alive), -r.lives, -r.ko, -(r.cells if paints else r.hits), -r.items)
        ranked.sort(key=lambda r: (*key(r), r.idx))
        full = max(1, start_lives * max(len(s) for s in sides))
        for r in ranked:
            r.label = f"{r.lives} HP" if r.alive else "K.O."
            r.score = r.lives / full if r.alive else 0.04
        best = [r for r in ranked if key(r) == key(ranked[0])]
        if len(best) == 1:
            return Result(ranked, ranked[0].idx, [], False)
        return Result(ranked, None, [r.idx for r in best], False)
    ranked.sort(key=lambda r: (-r.cells, -r.items, r.idx))
    top_pct = max(r.pct for r in ranked) or 1.0
    for r in ranked:
        r.label = fmt_pct(r.pct)
        r.score = r.pct / top_pct
    top = ranked[0].cells
    tied = [r for r in ranked if r.cells == top]
    if len(tied) == 1:
        return Result(ranked, ranked[0].idx, [], False)
    best_items = max(r.items for r in tied)
    best = [r for r in tied if r.items == best_items]
    if len(best) == 1:
        return Result(ranked, best[0].idx, [], True)
    return Result(ranked, None, [r.idx for r in best], False)
