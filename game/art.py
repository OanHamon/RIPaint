"""Sprites 8-bit des objets et effets, dessinés en ASCII."""

from functools import lru_cache

import numpy as np
import pygame

from engine8bit import palette
from engine8bit.sprites import sprite

from . import variants

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
    "N": palette.GREY_DARK,
    "V": palette.GREEN,
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

BOMB = (
    "......KY.",
    ".....K...",
    "...KKKK..",
    "..KNNNNK.",
    ".KNWNNNNK",
    ".KNNNNNNK",
    ".KNNNNNNK",
    "..KNNNNK.",
    "...KKKK..",
)

ROLLER = (
    "KKKKKKKK.",
    "KWWWWWWK.",
    "KSSSSSSK.",
    "KKKKKKKK.",
    ".......K.",
    "....KKKK.",
    "....KBK..",
    "....KBK..",
    "....KKK..",
)

BUCKET = (
    ".KKKKKKK.",
    "K.......K",
    "KKKKKKKKK",
    "KRRRRRRRK",
    ".KOOOOOK.",
    ".KVVVVVK.",
    ".KSSSSSK.",
    "..KMMMK..",
    "..KKKKK..",
)

ICE = (
    "KKKKKKKKK",
    "KWWWSSSSK",
    "KWSSSSSSK",
    "KWSSWSSSK",
    "KSSWSSSSK",
    "KSSSSSWSK",
    "KSSSSWSSK",
    "KSSSSSSSK",
    "KKKKKKKKK",
)

MAGNET = (
    "KKKK.KKKK",
    "KGGK.KGGK",
    "KRRK.KRRK",
    "KRRK.KRRK",
    "KRRKKKRRK",
    "KRRRRRRRK",
    ".KRRRRRK.",
    "..KKKKK..",
    ".........",
)

BOOTS = (
    "..KKKK...",
    "W.KRRK...",
    "WWKRRK...",
    ".WKRRK...",
    "..KRRRKK.",
    "..KRRRRRK",
    "..KRRRRRK",
    "..KGGGGGK",
    "..KKKKKKK",
)

HEART = (
    ".KK...KK.",
    "KRRK.KRRK",
    "KRWRKRRRK",
    "KRWRRRRRK",
    "KRRRRRRRK",
    ".KRRRRRK.",
    "..KRRRK..",
    "...KRK...",
    "....K....",
)

HAND = (
    "...KK.....",
    "..KWWK....",
    "..KWWK....",
    "..KWWKKKK.",
    "KKKWWWWWWK",
    "KWKWWWWWWK",
    "KWWWWWWWWK",
    ".KWWWWWWWK",
    "..KWWWWWK.",
    "...KKKKK..",
)

MINI_ROLLER = (
    "KKKKK",
    "KWWWK",
    "KKKKK",
    "..K..",
)

MINI_MAGNET = (
    "R.R",
    "R.R",
    "RRR",
)

ITEM_SPRITES = {"gun": GUN, "brush": BRUSH, "potion": POTION, "hourglass": HOURGLASS, "bomb": BOMB,
                "roller": ROLLER, "bucket": BUCKET, "ice": ICE, "magnet": MAGNET,
                "boots": BOOTS, "heart": HEART}


def item_sprite(kind: str) -> pygame.Surface:
    return sprite(ITEM_SPRITES[kind], COLORS)


def star() -> pygame.Surface:
    return sprite(STAR, COLORS)


def crown() -> pygame.Surface:
    return sprite(CROWN, COLORS)


def slow_icon() -> pygame.Surface:
    return sprite(SLOW, COLORS)


def hand() -> pygame.Surface:
    return sprite(HAND, COLORS)


def roller_icon() -> pygame.Surface:
    return sprite(MINI_ROLLER, COLORS)


def magnet_icon() -> pygame.Surface:
    return sprite(MINI_MAGNET, COLORS)


@lru_cache(maxsize=256)
def skin_body(team: str, inner: int, shade: int) -> pygame.Surface:
    """Motif du concurrent (drapeau…) agrandi sans lissage sur le corps du cube, avec
    l'ombre en bas à droite assombrie comme sur un cube uni."""
    img = pygame.transform.scale(sprite(variants.BY_NAME[team].skin, variants.PIXELS), (inner, inner))
    arr = pygame.surfarray.pixels3d(img)
    edge = np.zeros((inner, inner), dtype=bool)          # surfarray : indices (x, y)
    edge[inner - shade:, :] = True
    edge[:, inner - shade:] = True
    arr[edge] = arr[edge].astype(np.uint16) * 3 // 5
    del arr
    return img


def draw_cube(surf: pygame.Surface, x: int, y: int, size: int, team: str, look=(0.0, 0.0),
              stunned: bool = False, flash: bool = False, frozen: bool = False,
              hurt: bool = False, dead: bool = False) -> None:
    """Cube 8-bit : contour noir, corps clair, ombre foncée, reflet, yeux qui regardent
    dans la direction du mouvement (croix si assommé)."""
    dark, mid, light = variants.colors(team)
    if dead:                                        # K.O. : cube grisé
        dark, mid, light = palette.GREY_DARK, palette.GREY, palette.GREY_LIGHT
    body = palette.WHITE if flash else (mid if dead else light)
    pygame.draw.rect(surf, K, (x, y, size, size))
    if size <= 2:
        return
    shade = max(1, size // 7)
    competitor = variants.BY_NAME.get(team)
    if competitor and competitor.skin and not dead and not flash:
        surf.blit(skin_body(team, size - 2, shade), (x + 1, y + 1))
    else:
        pygame.draw.rect(surf, dark, (x + 1, y + 1, size - 2, size - 2))
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
    gap = max(1, size // 6)
    left = cx - gap - e + 1 + ox
    right = cx + gap - (0 if size % 2 else 1) + ox
    top = cy - e // 2 + oy
    if stunned:
        g = 1 if (dead and size >= 20) else 0       # croix plus grandes pour un gros cube K.O.
        for ex in (left, right):
            if e == 1 and not g:
                surf.set_at((ex, top), K)
            else:
                pygame.draw.line(surf, K, (ex - g, top - g), (ex + e + g, top + e + g))
                pygame.draw.line(surf, K, (ex + e + g, top - g), (ex - g, top + e + g))
    elif hurt:
        # yeux plissés (aïe !)
        pygame.draw.rect(surf, K, (left - (1 if e > 1 else 0), top + e // 2, e + (1 if e > 1 else 0), 1))
        pygame.draw.rect(surf, K, (right, top + e // 2, e + (1 if e > 1 else 0), 1))
    else:
        pygame.draw.rect(surf, K, (left, top, e, e + (1 if size >= 10 else 0)))
        pygame.draw.rect(surf, K, (right, top, e, e + (1 if size >= 10 else 0)))
    if frozen:
        # bloc de glace : trame bleu pâle sur le corps, contour glacé et reflets blancs
        for py in range(y + 1, y + size - 1):
            for px in range(x + 1 + (py - y) % 2, x + size - 1, 2):
                surf.set_at((px, py), palette.SKY)
        pygame.draw.rect(surf, palette.SKY, (x - 1, y - 1, size + 2, size + 2), 1)
        surf.set_at((x + size - 2, y + 1), palette.WHITE)
        surf.set_at((x + 1, y + size - 2), palette.WHITE)
