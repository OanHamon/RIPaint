"""Surface logique et zones de sécurité.

Tout le rendu se fait sur une surface de LOGICAL_W x LOGICAL_H pixels, agrandie
ensuite d'un facteur SCALE en "nearest neighbor" (1080x1920 pour la vidéo).
"""

import math
from dataclasses import dataclass

LOGICAL_W = 135
LOGICAL_H = 240
SCALE = 8
FPS = 60
OUTPUT_W = LOGICAL_W * SCALE  # 1080
OUTPUT_H = LOGICAL_H * SCALE  # 1920


@dataclass
class SafeZone:
    """Zone de sécurité exprimée en pixels de la vidéo finale, convertie en
    pixels logiques (arrondi vers l'extérieur pour rester prudent)."""

    top_px: int = 130
    bottom_px: int = 400
    right_px: int = 140
    left_px: int = 0

    @property
    def top(self) -> int:
        return math.ceil(self.top_px / SCALE)

    @property
    def bottom(self) -> int:
        return math.ceil(self.bottom_px / SCALE)

    @property
    def right(self) -> int:
        return math.ceil(self.right_px / SCALE)

    @property
    def left(self) -> int:
        return math.ceil(self.left_px / SCALE)

    def rect(self):
        """(x, y, w, h) de la zone utilisable, en pixels logiques."""
        x = self.left
        y = self.top
        return x, y, LOGICAL_W - self.right - x, LOGICAL_H - self.bottom - y


def fit_window_scale(screen_h: int, margin: int = 140) -> int:
    """Plus grand facteur entier qui fait tenir la surface logique à l'écran."""
    return max(1, (screen_h - margin) // LOGICAL_H)
