"""Sprites 8-bit des objets et effets, dessinés en ASCII."""

import pygame

from engine8bit import palette
from engine8bit.sprites import sprite

K = palette.BLACK
COLORS = {
    "K": palette.BLACK,
    "W": palette.WHITE,
    "G": palette.GREY_LIGHT,
    "D": palette.GREY,
    "B": palette.BROWN,
    "P": palette.MAGENTA,
    "M": palette.PURPLE,
    "Y": palette.YELLOW_LIGHT,
    "O": palette.YELLOW,
    "S": palette.SKY,
    "R": palette.RED,
}

GUN = (
    ".........",
    ".KKKKKKKK",
    "KWWGGGGGK",
    "KGGGGGDDK",
    "KGDBKKKK.",
    "KBBK.....",
    "KBBK.....",
    "KBBK.....",
    ".KK......",
)

BRUSH = (
    "......KKK",
    ".....KBBK",
    "....KBBK.",
    "...KGGK..",
    "..KGGK...",
    ".KPPPK...",
    "KPPPK....",
    "KPPK.....",
    ".KK......",
)

POTION = (
    "...KKK...",
    "...KBK...",
    "...KSK...",
    "..KSSSK..",
    ".KSPPPSK.",
    "KPPPPPPPK",
    "KPWPPPPPK",
    ".KPPPPPK.",
    "..KKKKK..",
)

HOURGLASS = (
    "KKKKKKKKK",
    "KBBBBBBBK",
    ".KOOOOOK.",
    "..KOOOK..",
    "...KOK...",
    "..KSOSK..",
    ".KSOOOSK.",
    "KBBBBBBBK",
    "KKKKKKKKK",
)

STAR = (
    ".Y.",
    "YWY",
    ".Y.",
)

CROWN = (
    "O.O.O",
    "OOOOO",
    "OYOYO",
)

SLOW = (
    "S...S",
    ".S.S.",
    "..S..",
)

ITEM_SPRITES = {"gun": GUN, "brush": BRUSH, "potion": POTION, "hourglass": HOURGLASS}


def item_sprite(kind: str) -> pygame.Surface:
    return sprite(ITEM_SPRITES[kind], COLORS)


def star() -> pygame.Surface:
    return sprite(STAR, COLORS)


def crown() -> pygame.Surface:
    return sprite(CROWN, COLORS)


def slow_icon() -> pygame.Surface:
    return sprite(SLOW, COLORS)


def draw_cube(surf: pygame.Surface, x: int, y: int, size: int, team: str, look=(0.0, 0.0),
              stunned: bool = False, flash: bool = False) -> None:
    """Cube 8-bit : contour noir, corps clair, ombre foncée, reflet, yeux qui regardent
    dans la direction du mouvement (croix si assommé)."""
    dark, mid, light = palette.TEAMS[team]
    body = palette.WHITE if flash else light
    pygame.draw.rect(surf, K, (x, y, size, size))
    if size <= 2:
        return
    pygame.draw.rect(surf, dark, (x + 1, y + 1, size - 2, size - 2))
    shade = max(1, size // 7)
    pygame.draw.rect(surf, body, (x + 1, y + 1, size - 2 - shade, size - 2 - shade))
    surf.set_at((x + 1, y + 1), palette.WHITE)
    if size >= 10:
        pygame.draw.rect(surf, palette.WHITE, (x + 1, y + 1, 2, 1))
        pygame.draw.rect(surf, palette.WHITE, (x + 1, y + 1, 1, 2))
    # yeux
    e = max(1, round(size / 6))
    cx = x + size // 2
    cy = y + size // 2 - e // 2 - (1 if size >= 10 else 0)
    ox = int(round(look[0] * max(1, e // 2)))
    oy = int(round(look[1] * max(1, e // 2)))
    gap = max(1, size // 7)
    left = cx - gap - e + 1 + ox
    right = cx + gap - (0 if size % 2 else 1) + ox
    top = cy - e // 2 + oy
    if stunned:
        for ex in (left, right):
            if e == 1:
                surf.set_at((ex, top), K)
            else:
                pygame.draw.line(surf, K, (ex, top), (ex + e, top + e))
                pygame.draw.line(surf, K, (ex + e, top), (ex, top + e))
    else:
        pygame.draw.rect(surf, K, (left, top, e, e + (1 if size >= 10 else 0)))
        pygame.draw.rect(surf, K, (right, top, e, e + (1 if size >= 10 else 0)))
