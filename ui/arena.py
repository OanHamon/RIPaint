"""Mini bataille de cubes dans le terminal : décor animé de l'atelier.

Même principe que les vidéos : des cubes rebondissent et peignent le sol, la couleur qui
couvre le plus de surface gagne la manche. Rendu en demi-blocs (pixels carrés).
"""

import math
import random

from rich.segment import Segment
from rich.style import Style
from textual.strip import Strip
from textual.widget import Widget

from . import theme

TEAM_NAMES = list(theme.TEAMS)
CUBE = 3                 # côté d'un cube, en pixels
ROUND_SECONDS = 28.0
ANNOUNCE_SECONDS = 2.5
FPS = 20


class _Cube:
    def __init__(self, team: int, x: float, y: float, angle: float):
        self.team = team
        self.x, self.y = x, y
        self.vx, self.vy = math.cos(angle), math.sin(angle)


class Arena(Widget):
    DEFAULT_CSS = """
    Arena { height: 1fr; min-height: 6; }
    """

    def __init__(self, *, id: str | None = None):
        super().__init__(id=id)
        self.rng = random.Random()
        self.turbo = False
        self.round_no = 0
        self.paint: list[list[int]] = []
        self.counts: list[int] = []
        self.cubes: list[_Cube] = []
        self.elapsed = 0.0
        self.message = ""
        self.message_left = 0.0
        self.pw = self.ph = 0
        self._styles: dict[tuple, Style] = {}

    def on_mount(self) -> None:
        self.set_interval(1 / FPS, self._tick)

    def on_resize(self) -> None:
        self.new_round(keep_number=True)

    # ---- Simulation ------------------------------------------------------------------------

    def new_round(self, keep_number: bool = False) -> None:
        self.pw = self.size.width
        self.ph = max(0, (self.size.height - 1) * 2)
        if not keep_number or self.round_no == 0:
            self.round_no += 1
        self.paint = [[-1] * self.pw for _ in range(self.ph)]
        self.counts = [0] * len(TEAM_NAMES)
        self.elapsed = 0.0
        self.cubes = []
        if self.pw < CUBE * 4 or self.ph < CUBE * 3:
            return
        n = self.rng.choice((2, 3, 3, 4))
        for team in range(n):
            self.cubes.append(_Cube(team,
                                    self.rng.uniform(0, self.pw - CUBE),
                                    self.rng.uniform(0, self.ph - CUBE),
                                    self.rng.uniform(0, math.tau)))

    def announce(self, text: str, seconds: float = ANNOUNCE_SECONDS) -> None:
        self.message = text
        self.message_left = seconds

    def _paint_disc(self, cx: int, cy: int, r: int, team: int) -> None:
        for y in range(max(0, cy - r), min(self.ph, cy + r + 1)):
            for x in range(max(0, cx - r), min(self.pw, cx + r + 1)):
                if (x - cx) ** 2 + (y - cy) ** 2 <= r * r + r:
                    self._set(x, y, team)

    def _set(self, x: int, y: int, team: int) -> None:
        old = self.paint[y][x]
        if old != team:
            if old >= 0:
                self.counts[old] -= 1
            self.counts[team] += 1
            self.paint[y][x] = team

    def _step(self) -> None:
        speed = 0.9
        for c in self.cubes:
            c.x += c.vx * speed
            c.y += c.vy * speed * 0.9
            if c.x < 0 or c.x > self.pw - CUBE:
                c.vx = -c.vx
                c.x = min(max(c.x, 0), self.pw - CUBE)
            if c.y < 0 or c.y > self.ph - CUBE:
                c.vy = -c.vy
                c.y = min(max(c.y, 0), self.ph - CUBE)
            if self.rng.random() < 0.01:   # petit changement de cap, comme un rebond sur un cube
                a = math.atan2(c.vy, c.vx) + self.rng.uniform(-0.8, 0.8)
                c.vx, c.vy = math.cos(a), math.sin(a)
            ix, iy = int(c.x), int(c.y)
            for y in range(iy, min(self.ph, iy + CUBE)):
                for x in range(ix, min(self.pw, ix + CUBE)):
                    self._set(x, y, c.team)
            if self.rng.random() < 0.004:  # gros pinceau
                self._paint_disc(ix + 1, iy + 1, self.rng.randint(4, 7), c.team)

    def _tick(self) -> None:
        if not self.cubes:
            if self.size.width and self.size.height:
                self.new_round(keep_number=True)
            return
        dt = 1 / FPS
        if self.message_left > 0:
            self.message_left -= dt
            if self.message_left <= 0 and self.elapsed >= ROUND_SECONDS:
                self.message = ""
                self.new_round()
        else:
            for _ in range(3 if self.turbo else 1):
                self._step()
            self.elapsed += dt * (3 if self.turbo else 1)
            if self.elapsed >= ROUND_SECONDS:
                self.announce(self.winner_text())
        self.refresh()

    def ranking(self) -> list[tuple[int, float]]:
        total = max(1, self.pw * self.ph)
        teams = [c.team for c in self.cubes]
        return sorted(((t, self.counts[t] / total * 100) for t in teams), key=lambda r: -r[1])

    def winner_text(self) -> str:
        rank = self.ranking()
        if not rank:
            return ""
        if len(rank) > 1 and round(rank[0][1], 1) == round(rank[1][1], 1):
            return " TIE! "
        return f" {TEAM_NAMES[rank[0][0]]} WINS! {rank[0][1]:.1f}% "

    # ---- Rendu -----------------------------------------------------------------------------

    def _style(self, fg: str, bg: str | None = None, bold: bool = False) -> Style:
        key = (fg, bg, bold)
        style = self._styles.get(key)
        if style is None:
            style = self._styles[key] = Style(color=fg, bgcolor=bg, bold=bold)
        return style

    def _color(self, x: int, y: int, cube_px: dict) -> str:
        team = cube_px.get((x, y))
        if team is not None:
            return theme.TEAMS[TEAM_NAMES[team]][2]
        team = self.paint[y][x]
        if team >= 0:
            return theme.TEAMS[TEAM_NAMES[team]][1]
        return theme.FLOOR_B if ((x // 4) + (y // 4)) % 2 else theme.FLOOR_A

    def render_line(self, y: int) -> Strip:
        width = self.size.width
        if y == self.size.height - 1:
            return self._scoreboard(width)
        if 2 * y + 1 >= self.ph or width != self.pw:
            return Strip.blank(width)
        cube_px = {}
        for c in self.cubes:
            ix, iy = int(c.x), int(c.y)
            if iy <= 2 * y + 1 and iy + CUBE > 2 * y:
                for px in range(ix, ix + CUBE):
                    for py in range(iy, iy + CUBE):
                        cube_px[(px, py)] = c.team
        segments = []
        run_style, run_len = None, 0
        for x in range(width):
            style = self._style(self._color(x, 2 * y, cube_px), self._color(x, 2 * y + 1, cube_px))
            if style is run_style:
                run_len += 1
                continue
            if run_len:
                segments.append(Segment("▀" * run_len, run_style))
            run_style, run_len = style, 1
        if run_len:
            segments.append(Segment("▀" * run_len, run_style))
        strip = Strip(segments, width)
        if self.message and y == (self.size.height - 1) // 2:
            msg = self.message[:width]
            left = (width - len(msg)) // 2
            winner = next((n for n in TEAM_NAMES if n in msg), None)
            bg = theme.TEAMS[winner][1] if winner else theme.WHITE
            overlay = Strip([Segment(msg, self._style(theme.BLACK, bg, bold=True))], len(msg))
            strip = Strip.join([strip.crop(0, left), overlay, strip.crop(left + len(msg), width)])
        return strip

    def _scoreboard(self, width: int) -> Strip:
        bg = theme.FLOOR_A
        scores = []
        for team, pct in sorted(self.ranking(), key=lambda r: r[0]):
            name = TEAM_NAMES[team]
            scores.append(Segment(" ■ ", self._style(theme.TEAMS[name][1], bg)))
            scores.append(Segment(f"{name} {pct:.1f}%", self._style(theme.GREY_LIGHT, bg)))
        left = max(0.0, ROUND_SECONDS - self.elapsed)
        timer = Segment(f" 0:{int(math.ceil(left)):02d} ", self._style(theme.YELLOW_LIGHT, bg, bold=True))
        head = Segment(f" MANCHE {self.round_no} ", self._style(theme.GREY, bg))
        # ce qui ne tient pas saute en premier : l'intitulé, puis le chrono
        for parts in ([head, *scores], scores):
            used = sum(s.cell_length for s in parts)
            if used + timer.cell_length <= width:
                pad = Segment(" " * (width - used - timer.cell_length), self._style(bg, bg))
                return Strip([*parts, pad, timer], width)
        return Strip(scores).crop(0, width).extend_cell_length(width, self._style(bg, bg))
