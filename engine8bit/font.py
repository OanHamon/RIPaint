"""Police pixel 5x7 dessinée dans le code (création originale, aucune licence tierce).

Rendu avec contour noir d'un pixel logique pour la lisibilité sur n'importe quel fond.
Les minuscules sont converties en majuscules.
"""

from functools import lru_cache

import numpy as np
import pygame

from . import palette

GLYPH_W = 5
GLYPH_H = 7
ADVANCE = GLYPH_W + 1
LINE_H = GLYPH_H + 3

_RAW = {
    "A": [".###.", "#...#", "#...#", "#####", "#...#", "#...#", "#...#"],
    "B": ["####.", "#...#", "#...#", "####.", "#...#", "#...#", "####."],
    "C": [".###.", "#...#", "#....", "#....", "#....", "#...#", ".###."],
    "D": ["####.", "#...#", "#...#", "#...#", "#...#", "#...#", "####."],
    "E": ["#####", "#....", "#....", "####.", "#....", "#....", "#####"],
    "F": ["#####", "#....", "#....", "####.", "#....", "#....", "#...."],
    "G": [".###.", "#...#", "#....", "#.###", "#...#", "#...#", ".####"],
    "H": ["#...#", "#...#", "#...#", "#####", "#...#", "#...#", "#...#"],
    "I": [".###.", "..#..", "..#..", "..#..", "..#..", "..#..", ".###."],
    "J": ["..###", "...#.", "...#.", "...#.", "...#.", "#..#.", ".##.."],
    "K": ["#...#", "#..#.", "#.#..", "##...", "#.#..", "#..#.", "#...#"],
    "L": ["#....", "#....", "#....", "#....", "#....", "#....", "#####"],
    "M": ["#...#", "##.##", "#.#.#", "#.#.#", "#...#", "#...#", "#...#"],
    "N": ["#...#", "#...#", "##..#", "#.#.#", "#..##", "#...#", "#...#"],
    "O": [".###.", "#...#", "#...#", "#...#", "#...#", "#...#", ".###."],
    "P": ["####.", "#...#", "#...#", "####.", "#....", "#....", "#...."],
    "Q": [".###.", "#...#", "#...#", "#...#", "#.#.#", "#..#.", ".##.#"],
    "R": ["####.", "#...#", "#...#", "####.", "#.#..", "#..#.", "#...#"],
    "S": [".####", "#....", "#....", ".###.", "....#", "....#", "####."],
    "T": ["#####", "..#..", "..#..", "..#..", "..#..", "..#..", "..#.."],
    "U": ["#...#", "#...#", "#...#", "#...#", "#...#", "#...#", ".###."],
    "V": ["#...#", "#...#", "#...#", "#...#", "#...#", ".#.#.", "..#.."],
    "W": ["#...#", "#...#", "#...#", "#.#.#", "#.#.#", "#.#.#", ".#.#."],
    "X": ["#...#", "#...#", ".#.#.", "..#..", ".#.#.", "#...#", "#...#"],
    "Y": ["#...#", "#...#", ".#.#.", "..#..", "..#..", "..#..", "..#.."],
    "Z": ["#####", "....#", "...#.", "..#..", ".#...", "#....", "#####"],
    "É": ["...#.", "..#..", "#####", "#....", "####.", "#....", "#####"],
    "È": [".#...", "..#..", "#####", "#....", "####.", "#....", "#####"],
    "Ê": ["..#..", ".#.#.", "#####", "#....", "####.", "#....", "#####"],
    "À": [".#...", "..#..", ".###.", "#...#", "#####", "#...#", "#...#"],
    "Â": ["..#..", ".#.#.", ".###.", "#...#", "#####", "#...#", "#...#"],
    "Ç": [".###.", "#...#", "#....", "#...#", ".###.", "..#..", ".##.."],
    "Ù": [".#...", "..#..", "#...#", "#...#", "#...#", "#...#", ".###."],
    "Ô": ["..#..", ".#.#.", ".###.", "#...#", "#...#", "#...#", ".###."],
    "Î": ["..#..", ".#.#.", ".###.", "..#..", "..#..", "..#..", ".###."],
    "0": [".###.", "#...#", "#..##", "#.#.#", "##..#", "#...#", ".###."],
    "1": ["..#..", ".##..", "..#..", "..#..", "..#..", "..#..", ".###."],
    "2": [".###.", "#...#", "....#", "...#.", "..#..", ".#...", "#####"],
    "3": ["#####", "...#.", "..#..", "...#.", "....#", "#...#", ".###."],
    "4": ["...#.", "..##.", ".#.#.", "#..#.", "#####", "...#.", "...#."],
    "5": ["#####", "#....", "####.", "....#", "....#", "#...#", ".###."],
    "6": ["..##.", ".#...", "#....", "####.", "#...#", "#...#", ".###."],
    "7": ["#####", "....#", "...#.", "..#..", ".#...", ".#...", ".#..."],
    "8": [".###.", "#...#", "#...#", ".###.", "#...#", "#...#", ".###."],
    "9": [".###.", "#...#", "#...#", ".####", "....#", "...#.", ".##.."],
    " ": [".....", ".....", ".....", ".....", ".....", ".....", "....."],
    "!": ["..#..", "..#..", "..#..", "..#..", "..#..", ".....", "..#.."],
    "?": [".###.", "#...#", "....#", "...#.", "..#..", ".....", "..#.."],
    ".": [".....", ".....", ".....", ".....", ".....", ".....", "..#.."],
    ",": [".....", ".....", ".....", ".....", ".....", "..#..", ".#..."],
    ":": [".....", "..#..", ".....", ".....", ".....", "..#..", "....."],
    ";": [".....", "..#..", ".....", ".....", ".....", "..#..", ".#..."],
    "-": [".....", ".....", ".....", ".###.", ".....", ".....", "....."],
    "+": [".....", "..#..", "..#..", "#####", "..#..", "..#..", "....."],
    "%": ["##..#", "##..#", "...#.", "..#..", ".#...", "#..##", "#..##"],
    "/": ["....#", "....#", "...#.", "..#..", ".#...", "#....", "#...."],
    "'": ["..#..", "..#..", ".#...", ".....", ".....", ".....", "....."],
    "(": ["...#.", "..#..", ".#...", ".#...", ".#...", "..#..", "...#."],
    ")": [".#...", "..#..", "...#.", "...#.", "...#.", "..#..", ".#..."],
    "#": [".#.#.", ".#.#.", "#####", ".#.#.", "#####", ".#.#.", ".#.#."],
    "=": [".....", ".....", "#####", ".....", "#####", ".....", "....."],
    "<": ["...#.", "..#..", ".#...", "#....", ".#...", "..#..", "...#."],
    ">": [".#...", "..#..", "...#.", "....#", "...#.", "..#..", ".#..."],
    "*": [".....", "#.#.#", ".###.", "#####", ".###.", "#.#.#", "....."],
    '"': [".#.#.", ".#.#.", ".....", ".....", ".....", ".....", "....."],
    "x": [".....", ".....", "#...#", ".#.#.", "..#..", ".#.#.", "#...#"],
}

GLYPHS = {
    ch: np.array([[c == "#" for c in row] for row in rows], dtype=bool)
    for ch, rows in _RAW.items()
}
_FALLBACK = GLYPHS["?"]


def normalize(text: str) -> str:
    out = []
    for ch in text:
        if ch in GLYPHS:
            out.append(ch)
        elif ch.upper() in GLYPHS:
            out.append(ch.upper())
        else:
            out.append("?")
    return "".join(out)


def supported(ch: str) -> bool:
    return ch in GLYPHS or ch.upper() in GLYPHS


def text_width(text: str, scale: int = 1) -> int:
    """Largeur en pixels logiques, contour compris."""
    if not text:
        return 0
    return (len(text) * ADVANCE - 1) * scale + 2


def max_chars(width: int, scale: int = 1) -> int:
    return max(1, (width - 2 + scale) // (ADVANCE * scale))


def _words(paragraph: str) -> list[str]:
    """Mots, en gardant la ponctuation isolée (" !", " ?", " :") attachée au mot précédent."""
    words: list[str] = []
    for w in paragraph.split(" "):
        if words and w and all(ch in "!?:;." for ch in w):
            words[-1] += " " + w
        else:
            words.append(w)
    return words


def wrap(text: str, width: int, scale: int = 1, balanced: bool = True) -> list[str]:
    """Découpe le texte en lignes tenant dans `width` pixels logiques.
    Avec `balanced`, un texte sur deux lignes est coupé en deux moitiés équilibrées."""
    limit = max_chars(width, scale)
    lines: list[str] = []
    for paragraph in text.split("\n"):
        words = _words(paragraph)
        if balanced and len(paragraph) > limit and len(words) > 1:
            best = None
            for i in range(1, len(words)):
                a, b = " ".join(words[:i]), " ".join(words[i:])
                if len(a) <= limit and len(b) <= limit:
                    score = max(len(a), len(b))
                    if best is None or score < best[0]:
                        best = (score, a, b)
            if best:
                lines += [best[1], best[2]]
                continue
        current = ""
        for word in words:
            candidate = word if not current else current + " " + word
            if len(candidate) <= limit:
                current = candidate
            else:
                if current:
                    lines.append(current)
                while len(word) > limit:
                    lines.append(word[:limit])
                    word = word[limit:]
                current = word
        lines.append(current)
    return lines


@lru_cache(maxsize=512)
def render(text: str, color=palette.WHITE, scale: int = 1, outline=palette.BLACK) -> pygame.Surface:
    """Rend une ligne de texte avec contour noir (surface avec transparence)."""
    text = normalize(text)
    n = len(text)
    gw = n * ADVANCE - 1 if n else 1
    mask = np.zeros((GLYPH_H, gw), dtype=bool)
    for i, ch in enumerate(text):
        g = GLYPHS.get(ch, _FALLBACK)
        mask[:, i * ADVANCE:i * ADVANCE + GLYPH_W] |= g
    if scale > 1:
        mask = np.repeat(np.repeat(mask, scale, axis=0), scale, axis=1)
    h, w = mask.shape
    padded = np.zeros((h + 2, w + 2), dtype=bool)
    padded[1:-1, 1:-1] = mask
    border = np.zeros_like(padded)
    for dy in (-1, 0, 1):
        for dx in (-1, 0, 1):
            border[1 + dy:h + 1 + dy, 1 + dx:w + 1 + dx] |= mask
    rgba = np.zeros((h + 2, w + 2, 4), dtype=np.uint8)
    if outline is not None:
        rgba[border] = (*outline, 255)
    rgba[padded] = (*color, 255)
    surf = pygame.image.frombuffer(rgba.tobytes(), (w + 2, h + 2), "RGBA")
    return surf.copy()


def draw(surface: pygame.Surface, text: str, x: int, y: int, color=palette.WHITE,
         scale: int = 1, align: str = "left", outline=palette.BLACK) -> pygame.Rect:
    """Dessine une ligne. `align` : left / center / right par rapport à x."""
    img = render(text, tuple(color), scale, None if outline is None else tuple(outline))
    w = img.get_width()
    if align == "center":
        x = x - w // 2
    elif align == "right":
        x = x - w
    return surface.blit(img, (int(x), int(y)))


def draw_block(surface: pygame.Surface, text: str, cx: int, y: int, width: int,
               color=palette.WHITE, scale: int = 1, outline=palette.BLACK) -> int:
    """Dessine un texte multi-lignes centré sur cx ; renvoie la hauteur utilisée."""
    lines = wrap(text, width, scale)
    line_h = GLYPH_H * scale + 2 + scale
    for i, line in enumerate(lines):
        draw(surface, line, cx, y + i * line_h, color, scale, "center", outline)
    return len(lines) * line_h
