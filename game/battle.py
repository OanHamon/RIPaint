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

from . import items as item_logic
from . import physics
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
LEAD_COOLDOWN = 360         # au moins 6 s entre deux « X LEADS! »
LEAD_MARGIN = 0.03          # nouvelle tête annoncée seulement avec 3 points d'avance
LEAD_START_DELAY = 240      # pas d'annonce de leader pendant les 4 premières secondes
NICKNAMES = ["BLAZE", "FROST", "TURBO", "NINJA", "ROCKY", "PIXEL", "COMET", "SPIKE", "BOLT", "NOVA",
             "VIPER", "ZIGGY", "MANGO", "ROCKET", "SHADOW", "BLITZ", "LUNA", "MAX", "TANK", "DUKE"]


@dataclass
class Ranked:
    idx: int
    team: str
    cells: int
    pct: float
    items: int


@dataclass
class Result:
    ranking: list            # list[Ranked], du premier au dernier
    winner: int | None       # index du cube gagnant, None si égalité
    tied: list               # index des cubes à égalité parfaite (si égalité)
    by_items: bool           # départagé au nombre d'objets ramassés


class Battle:
    def __init__(self, seed: int, settings: Settings, battle_frames: int | None = None):
        self.seed = seed
        self.settings = settings
        self.layout = make_layout(settings.safe_top, settings.safe_bottom, settings.safe_right,
                                  settings.arena_centered)
        self.W, self.H = self.layout.arena_w, self.layout.arena_h
        # obstacles d'abord (générateur à part), puis les cubes qui les évitent
        self.map_name, self.obstacles = maps.build(seed, settings, self.W, self.H)
        self.scenario = make_scenario(seed, settings, self.W, self.H, self.obstacles,
                                      strict=getattr(settings, "map", "generated") != "generated")
        self.rng = self.scenario.rng
        self.fx = random.Random(seed * 31 + 7)        # aléatoire purement visuel
        self.hook = self.scenario.hook
        self.grid = np.full((self.H, self.W), -1, dtype=np.int8)
        self.cubes = [Cube(i, c.team, c.x, c.y, c.dx, c.dy, settings.cube_size)
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
        names = random.Random(seed * 13 + 5).sample(NICKNAMES, len(self.cubes))
        self.nicknames = names if settings.nicknames else [""] * len(self.cubes)

        self.frame = -1
        self.intro_start = (TEASER_FRAMES + REWIND_FRAMES) if settings.teaser else 0
        self.battle_start = self.intro_start + round(settings.intro_duration * FPS)
        self.outro_frames = round(settings.outro_duration * FPS)
        self.new_outro = self.outro_frames >= END_FRAMES + REVEAL_FRAMES + LOOP_FRAMES + 90
        if battle_frames is None:
            battle_frames = round(settings.battle_duration * FPS)
            if settings.tiktok_rewards:
                # la vidéo doit toujours dépasser 1 minute, même sans sablier
                need = round(settings.min_video_duration * FPS) - self.battle_start - self.outro_frames
                battle_frames = max(battle_frames, need)
        self.base_battle_frames = battle_frames
        self.battle_end = self.battle_start + battle_frames
        self.interval = max(1, round(settings.item_interval * FPS))
        self.next_spawn = self.battle_start + self.interval
        self.counts = np.zeros(len(self.cubes), dtype=np.int64)

        self.subtitle(0, self.battle_start, self.hook)
        if settings.teaser:
            self.subtitle(0, TEASER_FRAMES, "WHO WINS?")

        # Partie simulée à l'avance (même seed, même durée) : sert au teaser d'ouverture,
        # à la boucle de fin et à la ligue. La simulation étant déterministe et relative au GO,
        # l'arène finale est exactement celle de la vraie partie.
        self.final = None
        if settings.teaser or settings.league:
            pre = Battle(seed, replace(settings, teaser=False, league=False), battle_frames)
            while not pre.done:
                pre.step()
            self.final = {
                "grid": pre.grid.copy(),
                "cubes": [(c.cx, c.cy, c.size, c.dead) for c in pre.cubes],
                "result": pre.result,
                "percentages": pre.percentages(),
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
            return self.battle_end - self.frame <= hide
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
        """Escalade : un objet toutes les 5 s au début, toutes les ~1,4 s à la fin."""
        if not self.settings.escalation:
            return self.interval
        return max(45, round(self.interval * (1 - 0.72 * self.intensity())))

    def trigger_slowmo(self) -> None:
        if self.settings.slowmo and self.slowmo == 0 and self.phase == "battle":
            self.slowmo = SLOWMO_FRAMES
            self.flash = 3
            self.emit("slowmo")

    def percentages(self) -> list[float]:
        return [float(c) / self.paintable * 100 for c in self.counts]

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
        color = palette.TEAMS[self.cubes[idx].team][1]
        light = palette.TEAMS[self.cubes[idx].team][2]
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
                # ralenti : la partie n'avance qu'une image sur deux (le chrono, lui, continue)
                self.slowmo -= 1
                skip = self.slowmo % 2 == 1
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

        if (f - self.battle_start) % STUCK_CHECK == 0 and f > self.battle_start:
            for c in self.cubes:
                if c.active and c.slow <= 0 and c.resize_anim <= 0:
                    moved = math.hypot(c.cx - c.last_pos[0], c.cy - c.last_pos[1])
                    if moved < 2.0:
                        c.dx, c.dy = random_direction(self.rng)
                c.last_pos = (c.cx, c.cy)

        self._ticks(f)
        self.counts = np.bincount(self.grid[self.grid >= 0].ravel(), minlength=len(self.cubes))
        self._lead(f)

    def _lead(self, f: int) -> None:
        """Annonce « X LEADS! » quand un autre cube prend nettement la tête (pas pendant les
        dernières secondes, où les scores sont cachés)."""
        top = int(self.counts.max())
        if top <= 0 or int((self.counts == top).sum()) != 1:
            return
        leader = int(self.counts.argmax())
        if self.leader is None:
            self.leader = leader
            return
        if leader == self.leader or self.scores_hidden() or f - self.battle_start < LEAD_START_DELAY:
            return
        margin = int(self.counts[leader] - self.counts[self.leader])
        if margin < LEAD_MARGIN * self.paintable or f - self.last_lead_frame < LEAD_COOLDOWN:
            return
        self.crown_jump = (self.leader, leader, f)
        self.leader = leader
        self.last_lead_frame = f
        self.lead_changes += 1
        if self.settings.lead_announce:
            c = self.cubes[leader]
            self.popup(f"{c.team} LEADS!", palette.TEAMS[c.team][2], duration=72)
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
        self.result = compute_result(self.cubes, self.counts, self.paintable)
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
            text = f"{w.team} WINS! {fmt_pct(w.pct)}"
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
            colors = ([palette.TEAMS[self.cubes[r.winner].team][1], palette.TEAMS[self.cubes[r.winner].team][2],
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


def compute_result(cubes: list[Cube], counts, total_cells: int) -> Result:
    n = len(cubes)
    ranked = [Ranked(i, cubes[i].team, int(counts[i]), counts[i] / total_cells * 100, cubes[i].items)
              for i in range(n)]
    ranked.sort(key=lambda r: (-r.cells, -r.items, r.idx))
    top = ranked[0].cells
    tied = [r for r in ranked if r.cells == top]
    if len(tied) == 1:
        return Result(ranked, ranked[0].idx, [], False)
    best_items = max(r.items for r in tied)
    best = [r for r in tied if r.items == best_items]
    if len(best) == 1:
        return Result(ranked, best[0].idx, [], True)
    return Result(ranked, None, [r.idx for r in best], False)
