"""Thèmes d'arène : sol, fond, murs, obstacles et petite ambiance animée (neige, braises…).

Le thème est purement visuel : il ne change rien à la partie, donc une seed rejoue la même
bataille quel que soit le thème. Il change en revanche ce qui se voit dès la première seconde
(miniature, première image), ce qui rend deux vidéos bien moins semblables.

Ajouter un thème : écrire un Theme et l'ajouter à THEMES (le rendu et l'interface lisent ce registre).
"""

from __future__ import annotations

import random
from dataclasses import dataclass

from engine8bit import palette

CLASSIC = "classic"
RANDOM = "random"


@dataclass(frozen=True)
class Theme:
    key: str
    name: str                 # affiché pendant le compte à rebours (anglais, police 8-bit)
    label: str                # affiché dans l'interface (français)
    floor: tuple              # (case A, case B) du damier
    floor_style: str          # « checker », « tiles », « stripes », « dots », « grid »
    background: tuple         # (fond, motif du fond)
    wall: tuple               # (contour clair, intérieur, rivets)
    stone: tuple              # obstacles : (clair, principal, foncé)
    ambient: str = ""         # « snow », « embers », « stars », « bubbles », « leaves », « sparks », « sand », « hearts »
    ambient_colors: tuple = ()
    accent: tuple = palette.YELLOW   # bandeaux (accroche, nom du thème)


THEMES = [
    Theme(CLASSIC, "CLASSIC", "classique", (palette.FLOOR_A, palette.FLOOR_B), "checker",
          (palette.NAVY_DARK, palette.NAVY), (palette.GREY_LIGHT, palette.GREY, palette.WHITE),
          (palette.GREY_LIGHT, palette.GREY, palette.GREY_DARK)),
    Theme("lava", "LAVA", "volcan", (palette.LAVA_A, palette.LAVA_B), "tiles",
          (palette.BLACK, palette.LAVA_GLOW), (palette.ORANGE, palette.RED_DARK, palette.YELLOW_LIGHT),
          (palette.GREY, palette.GREY_DARK, palette.BLACK), "embers",
          (palette.ORANGE, palette.YELLOW, palette.RED), palette.ORANGE),
    Theme("ice", "ICE CAVE", "banquise", (palette.ICE_A, palette.ICE_B), "checker",
          (palette.ICE_BG, palette.BLUE_DARK), (palette.WHITE, palette.SKY, palette.WHITE),
          (palette.WHITE, palette.SKY, palette.BLUE), "snow", (palette.WHITE, palette.SKY), palette.SKY),
    Theme("space", "SPACE", "espace", (palette.SPACE_A, palette.SPACE_B), "dots",
          (palette.BLACK, palette.GREY_DARK), (palette.PURPLE_LIGHT, palette.PURPLE, palette.CYAN_LIGHT),
          (palette.GREY_LIGHT, palette.GREY_DARK, palette.BLACK), "stars",
          (palette.WHITE, palette.YELLOW_LIGHT, palette.CYAN_LIGHT), palette.PURPLE_LIGHT),
    Theme("jungle", "JUNGLE", "jungle", (palette.JUNGLE_A, palette.JUNGLE_B), "stripes",
          (palette.JUNGLE_BG, palette.GREEN_DARK), (palette.BROWN_LIGHT, palette.BROWN, palette.GREEN_LIGHT),
          (palette.BROWN_LIGHT, palette.BROWN, palette.BLACK), "leaves",
          (palette.GREEN_LIGHT, palette.GREEN, palette.YELLOW), palette.GREEN_LIGHT),
    Theme("desert", "DESERT", "désert", (palette.SAND_A, palette.SAND_B), "tiles",
          (palette.SAND_BG, palette.BROWN), (palette.YELLOW_LIGHT, palette.BROWN_LIGHT, palette.WHITE),
          (palette.YELLOW_LIGHT, palette.BROWN_LIGHT, palette.BROWN), "sand",
          (palette.YELLOW_LIGHT, palette.ORANGE_LIGHT), palette.YELLOW_LIGHT),
    Theme("neon", "NEON CITY", "néon", (palette.NEON_A, palette.NEON_B), "grid",
          (palette.BLACK, palette.PINK_DARK), (palette.MAGENTA, palette.PURPLE_DARK, palette.CYAN),
          (palette.CYAN, palette.CYAN_DARK, palette.BLACK), "sparks",
          (palette.MAGENTA, palette.CYAN, palette.WHITE), palette.MAGENTA),
    Theme("ocean", "DEEP SEA", "océan", (palette.OCEAN_A, palette.OCEAN_B), "checker",
          (palette.OCEAN_BG, palette.BLUE_DARK), (palette.CYAN_LIGHT, palette.CYAN_DARK, palette.WHITE),
          (palette.PINK_LIGHT, palette.MAGENTA, palette.PINK_DARK), "bubbles",
          (palette.CYAN_LIGHT, palette.WHITE), palette.CYAN),
    Theme("candy", "CANDY LAND", "bonbons", (palette.CANDY_A, palette.CANDY_B), "stripes",
          (palette.CANDY_BG, palette.PINK_DARK), (palette.PINK_LIGHT, palette.MAGENTA, palette.WHITE),
          (palette.WHITE, palette.PINK_LIGHT, palette.MAGENTA), "hearts",
          (palette.PINK_LIGHT, palette.WHITE), palette.PINK_LIGHT),
]

BY_KEY = {t.key: t for t in THEMES}
CHOICES = [(RANDOM, "aléatoire")] + [(t.key, t.label) for t in THEMES]


def resolve(seed: int, settings) -> Theme:
    """Thème de la partie. « random » : tiré selon la seed (générateur à part)."""
    key = getattr(settings, "theme", CLASSIC)
    if key == RANDOM:
        return random.Random(seed * 6151 + 29).choice(THEMES)
    return BY_KEY.get(key, BY_KEY[CLASSIC])
