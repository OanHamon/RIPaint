"""Logo « RIPaint » dessiné dans la police pixel 5x7 du moteur, peint lettre par lettre.

Deux tailles : `big` (1 pixel = 2 caractères pleins, avec ombre portée) pour l'écran de
démarrage, `compact` (1 pixel = un demi-caractère) pour l'en-tête.
"""

import random

from rich.text import Text

from . import theme

# Majuscules reprises de engine8bit/font.py ; minuscules dessinées dans le même style.
GLYPHS = {
    "R": ["####.", "#...#", "#...#", "####.", "#.#..", "#..#.", "#...#"],
    "I": [".###.", "..#..", "..#..", "..#..", "..#..", "..#..", ".###."],
    "P": ["####.", "#...#", "#...#", "####.", "#....", "#....", "#...."],
    "a": [".....", ".....", ".###.", "....#", ".####", "#...#", ".####"],
    "i": ["..#..", ".....", ".##..", "..#..", "..#..", "..#..", ".###."],
    "n": [".....", ".....", "####.", "#...#", "#...#", "#...#", "#...#"],
    "t": [".#...", ".#...", "####.", ".#...", ".#...", ".#..#", "..##."],
}
WORD = "RIPaint"
_TEAM_CYCLE = list(theme.TEAMS.values())

W = len(WORD) * 6 - 1
H = 7
BIG_WIDTH = (W + 1) * 2
COMPACT_WIDTH = W

# pixels[(x, y)] = (couleur peinture, couleur claire)
PIXELS: dict[tuple[int, int], tuple[str, str]] = {}
for _i, _ch in enumerate(WORD):
    _dark, _paint, _light = _TEAM_CYCLE[_i % len(_TEAM_CYCLE)]
    for _y, _row in enumerate(GLYPHS[_ch]):
        for _x, _c in enumerate(_row):
            if _c == "#":
                PIXELS[(_i * 6 + _x, _y)] = (_paint, _light)

# Ordre d'apparition : balayage gauche -> droite avec éclaboussures aléatoires
_rng = random.Random(7)
THRESHOLD = {p: 0.08 + 0.62 * p[0] / W + 0.3 * _rng.random() for p in PIXELS}


def _pixel_color(p, reveal: float, shine: float | None) -> tuple[str, str] | None:
    """(caractères, couleur) d'un pixel du logo, ou None s'il est encore sec."""
    paint, light = PIXELS[p]
    t = THRESHOLD[p]
    if reveal >= t:
        if shine is not None and abs((p[0] - p[1] * 0.6) - shine) < 1.6:
            return "██", light
        return "██", paint
    if reveal >= t - 0.08:
        return "▓▓", paint
    return "░░", theme.GREY_DARK


def big(reveal: float = 1.0, shine: float | None = None) -> Text:
    """Logo grand format. `reveal` 0..1 peint le logo, `shine` (colonne) fait passer un reflet."""
    text = Text(no_wrap=True)
    for y in range(H + 1):
        for x in range(W + 1):
            if (x, y) in PIXELS:
                chars, color = _pixel_color((x, y), reveal, shine)
                text.append(chars, style=color)
            elif (x - 1, y - 1) in PIXELS and reveal >= THRESHOLD[(x - 1, y - 1)]:
                text.append("██", style=theme.BLACK)
            else:
                text.append("  ")
        if y < H:
            text.append("\n")
    return text


def compact() -> Text:
    """Logo demi-hauteur (W x 4 caractères) : chaque caractère porte deux pixels."""
    text = Text(no_wrap=True)
    for row in range(0, H + 1, 2):
        for x in range(W):
            top = PIXELS.get((x, row))
            bottom = PIXELS.get((x, row + 1))
            if top and bottom:
                if top[0] == bottom[0]:
                    text.append("█", style=top[0])
                else:
                    text.append("▀", style=f"{top[0]} on {bottom[0]}")
            elif top:
                text.append("▀", style=top[0])
            elif bottom:
                text.append("▄", style=bottom[0])
            else:
                text.append(" ")
        if row + 2 <= H:
            text.append("\n")
    return text
