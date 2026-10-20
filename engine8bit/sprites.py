"""Sprites définis en texte ASCII : un caractère = un pixel, '.' = transparent."""

from functools import lru_cache

import numpy as np
import pygame


def from_ascii(rows: tuple[str, ...], colors: dict) -> pygame.Surface:
    h = len(rows)
    w = max(len(r) for r in rows)
    rgba = np.zeros((h, w, 4), dtype=np.uint8)
    for y, row in enumerate(rows):
        for x, ch in enumerate(row):
            if ch != "." and ch in colors:
                rgba[y, x] = (*colors[ch], 255)
    return pygame.image.frombuffer(rgba.tobytes(), (w, h), "RGBA").copy()


@lru_cache(maxsize=256)
def cached(rows: tuple[str, ...], colors_items: tuple) -> pygame.Surface:
    return from_ascii(rows, dict(colors_items))


def sprite(rows, colors: dict) -> pygame.Surface:
    """Version mise en cache de from_ascii."""
    return cached(tuple(rows), tuple(sorted(colors.items())))


def scaled(surf: pygame.Surface, factor: int) -> pygame.Surface:
    """Agrandissement entier sans lissage."""
    if factor == 1:
        return surf
    return pygame.transform.scale(surf, (surf.get_width() * factor, surf.get_height() * factor))
