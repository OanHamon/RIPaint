"""Cartes de l'arène : dispositions d'obstacles dessinées à la main et testées (jouables).

Chaque partie tire une carte au hasard (générateur dérivé de la seed) et l'oriente au hasard
(miroirs horizontal / vertical), ce qui donne une trentaine de variantes. Les coordonnées sont
données pour une arène de 98 x 126 et mises à l'échelle si l'arène a une autre taille.

Règles de conception (pour qu'aucun cube ne reste coincé) :
- un obstacle est soit collé à un mur, soit à au moins ~28 px des murs ;
- deux obstacles sont à au moins ~19 px l'un de l'autre (un cube de 13 px passe largement).
"""

import math
import random

from .obstacles import make_obstacles

DESIGN_W, DESIGN_H = 98, 126


def _ring(n: int, radius: float, size: int) -> list[tuple[int, int, int, int]]:
    cx, cy = DESIGN_W / 2, DESIGN_H / 2
    out = []
    for k in range(n):
        a = -math.pi / 2 + k * 2 * math.pi / n
        x, y = cx + radius * math.cos(a), cy + radius * math.sin(a)
        out.append((round(x - size / 2), round(y - size / 2), round(x + size / 2), round(y + size / 2)))
    return out


MAPS: dict[str, list[tuple[int, int, int, int]]] = {
    "OPEN": [],
    "PILLARS": [(28, 30, 36, 38), (62, 30, 70, 38), (28, 88, 36, 96), (62, 88, 70, 96)],
    "CROSS": [(35, 59, 63, 67), (45, 45, 53, 81)],
    "TEETH": [(0, 36, 10, 44), (0, 82, 10, 90), (88, 36, 98, 44), (88, 82, 98, 90), (44, 58, 54, 68)],
    "CORRIDOR": [(30, 32, 36, 94), (62, 32, 68, 94)],
    "DIAMOND": [(45, 30, 53, 38), (45, 88, 53, 96), (28, 59, 36, 67), (62, 59, 70, 67)],
    "ZIGZAG": [(28, 32, 48, 38), (50, 60, 70, 66), (28, 88, 48, 94)],
    "RING": _ring(5, 26, 7),
    "S-WALLS": [(0, 40, 40, 46), (58, 80, 98, 86)],
}
MAP_NAMES = list(MAPS)


def _scaled(rects, w: int, h: int, flip_x: bool, flip_y: bool):
    sx, sy = w / DESIGN_W, h / DESIGN_H
    out = []
    for x0, y0, x1, y1 in rects:
        if flip_x:
            x0, x1 = DESIGN_W - x1, DESIGN_W - x0
        if flip_y:
            y0, y1 = DESIGN_H - y1, DESIGN_H - y0
        r = (round(x0 * sx), round(y0 * sy), round(x1 * sx), round(y1 * sy))
        if r[2] - r[0] >= 3 and r[3] - r[1] >= 3:
            out.append(r)
    return out


def build(seed: int, settings, w: int, h: int) -> tuple[str, list[tuple[int, int, int, int]]]:
    """Renvoie (nom de la carte, obstacles). `settings.map` : « random », un nom de carte, ou
    « generated » (ancien mode : obstacles placés au hasard en miroir, `settings.obstacles`)."""
    choice = getattr(settings, "map", "generated")
    if choice == "generated":
        return "", make_obstacles(seed, settings.obstacles, settings.cube_size, w, h)
    rng = random.Random(seed * 104729 + 11)
    name = rng.choice(MAP_NAMES) if choice not in MAPS else choice
    flip_x, flip_y = rng.random() < 0.5, rng.random() < 0.5
    return name, _scaled(MAPS[name], w, h, flip_x, flip_y)
