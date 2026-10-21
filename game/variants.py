"""Variantes : qui s'affronte dans l'arène (couleurs, pays…).

Une variante est une liste de concurrents. Un concurrent, c'est :
  - un nom affiché dans la vidéo (police 8-bit, court) ;
  - trois couleurs (foncée, principale, claire) pour les textes, barres et particules ;
  - une famille de couleur : deux concurrents d'une même partie n'en partagent jamais,
    pour que l'arène et le tableau des scores restent lisibles ;
  - un motif de cube (`skin`, ASCII agrandi sans lissage sur le corps du cube) ;
  - un motif de traînée (`trail`, ASCII répété sur toute l'arène : la peinture « révèle »
    le motif, qui reste donc aligné d'un coup de pinceau à l'autre).
Motifs vides = cube et peinture unis (variante « couleurs », le jeu d'origine).

Ajouter une variante (célébrités, animaux…) : écrire ses concurrents et l'ajouter à
VARIANTS. Rien d'autre à toucher : le rendu, la ligue et l'interface lisent ce registre.
"""

from __future__ import annotations

import random
from dataclasses import dataclass, field

from engine8bit import palette

COLORS = "colors"
TRAIL_SCALE = 2       # un pixel du motif de traînée = TRAIL_SCALE x TRAIL_SCALE cases de l'arène
TRAIL_TINT = 0.35     # part de la couleur principale mélangée au motif (0 = motif brut)


@dataclass(frozen=True)
class Competitor:
    name: str                 # unique toutes variantes confondues (sert aussi de clé de ligue)
    colors: tuple             # (foncée, principale, claire)
    family: str
    skin: tuple = ()          # lignes ASCII, lettres de PIXELS (vide = cube uni)
    trail: tuple = ()         # lignes ASCII, lettres de PIXELS (vide = peinture unie)


@dataclass(frozen=True)
class Variant:
    key: str
    label: str                # affiché dans l'interface (français)
    noun: str                 # remplace « COLOR » dans les accroches (« PICK YOUR COUNTRY! »)
    competitors: tuple = field(default_factory=tuple)
    nicknames: bool = True    # surnoms (« BLAZE ») : inutiles quand le nom suffit (pays, célébrités)

    def pick(self, seed: int, slots: list[str]) -> list[Competitor]:
        """Concurrents de la partie, un par cube. `slots` : couleurs tirées par le scénario
        (gardées telles quelles par la variante « couleurs », pour que les seeds ne changent pas)."""
        if self.key == COLORS:
            return [BY_NAME[t] for t in slots]
        rng = random.Random(seed * 104729 + 13)      # générateur à part : la seed garde son sens
        pool = list(self.competitors)
        rng.shuffle(pool)
        chosen, families = [], set()
        for c in pool:
            if c.family not in families:
                chosen.append(c)
                families.add(c.family)
            if len(chosen) == len(slots):
                break
        return chosen

    def adapt(self, hook: str) -> str:
        return hook.replace("COLOR", self.noun)


# Lettres des motifs
PIXELS = {
    "K": palette.BLACK,
    "W": palette.WHITE,
    "R": palette.RED,
    "B": palette.BLUE,
    "D": palette.BLUE_DARK,
    "G": palette.GREEN,
    "Y": palette.YELLOW,
    "S": palette.SKY,
    "O": palette.ORANGE,
}

# Trios (foncée, principale, claire) par famille
FAMILY_COLORS = {
    "red": palette.TEAMS["RED"],
    "blue": palette.TEAMS["BLUE"],
    "yellow": palette.TEAMS["YELLOW"],
    "green": palette.TEAMS["GREEN"],
    "white": (palette.GREY, palette.GREY_LIGHT, palette.WHITE),
    "sky": (palette.BLUE, palette.SKY, palette.SKY),
    "orange": (palette.BROWN, palette.ORANGE, palette.ORANGE_LIGHT),
}


def vstripes(*letters: str, width: int = 1) -> tuple:
    """Bandes verticales (une ligne, chaque lettre répétée `width` fois)."""
    return ("".join(ch * width for ch in letters),)


def hstripes(*letters: str, width: int = 1) -> tuple:
    """Bandes horizontales (une colonne, chaque lettre répétée `width` fois)."""
    return tuple(ch for ch in letters for _ in range(width))


def country(name: str, family: str, skin: tuple, trail: tuple | None = None) -> Competitor:
    return Competitor(name, FAMILY_COLORS[family], family, skin, skin if trail is None else trail)


COLOR_TEAMS = tuple(Competitor(team, palette.TEAMS[team], team.lower())
                    for team in palette.PRIMARY_TEAMS + [palette.FOURTH_TEAM])

COUNTRIES = (
    country("FRANCE", "blue", vstripes("B", "W", "R"), vstripes("B", "W", "R", width=2)),
    country("ITALY", "green", vstripes("G", "W", "R"), vstripes("G", "W", "R", width=2)),
    country("GERMANY", "yellow", hstripes("K", "R", "Y"), hstripes("K", "R", "R", "Y", "Y")),
    country("SPAIN", "red", hstripes("R", "Y", "Y", "R"), hstripes("R", "Y", "Y", "R")),
    country("USA", "red",
            ("DDDRRRR",
             "DWDWWWW",
             "DDDRRRR",
             "WWWWWWW",
             "RRRRRRR",
             "WWWWWWW",
             "RRRRRRR"),
            ("DWDWRRRR",
             "WDWDWWWW",
             "DWDWRRRR",
             "WDWDWWWW")),
    country("UK", "blue",
            ("WDDRDDW",
             "DWDRDWD",
             "DDWRWDD",
             "RRRRRRR",
             "DDWRWDD",
             "DWDRDWD",
             "WDDRDDW"),
            ("WDDRDDW",
             "DWDRDWD",
             "RRRRRRR",
             "DWDRDWD",
             "WDDRDDW")),
    country("JAPAN", "white",
            ("WWWWWWW",
             "WWRRRWW",
             "WRRRRRW",
             "WRRRRRW",
             "WRRRRRW",
             "WWRRRWW",
             "WWWWWWW"),
            ("WWWW",
             "WRRW",
             "WRRW",
             "WWWW")),
    country("KOREA", "white",
            ("KWWWK",
             "WRRRW",
             "WBBBW",
             "KWWWK"),
            ("WWWW",
             "WRRW",
             "WBBW",
             "WWWW")),
    country("BRAZIL", "green",
            ("GGGGGGG",
             "GGGYGGG",
             "GGYBYGG",
             "GYBBBYG",
             "GGYBYGG",
             "GGGYGGG",
             "GGGGGGG"),
            ("GGGGGG",
             "GGYYGG",
             "GYBBYG",
             "GYBBYG",
             "GGYYGG",
             "GGGGGG")),
    country("PORTUGAL", "green",
            ("GGRRR",
             "GGRRR",
             "GYYRR",
             "GGRRR",
             "GGRRR"),
            ("GGRRR",
             "GGRRR",
             "GYRRR",
             "GGRRR")),
    country("ARGENTINA", "sky",
            ("SSS",
             "WYW",
             "SSS"),
            ("SSSSSS",
             "SSSSSS",
             "WWYWWW",
             "WWWWWW")),
    country("CANADA", "red",
            ("RRWWWWWWRR",
             "RRWWRRWWRR",
             "RRWRRRRWRR",
             "RRWWRRWWRR",
             "RRWWWWWWRR"),
            ("RWWWWR",
             "RWRRWR",
             "RWRRWR",
             "RWWWWR")),
    country("MOROCCO", "red",
            ("RRRRR",
             "RRGRR",
             "RGGGR",
             "RGRGR",
             "RRRRR"),
            ("RRRRR",
             "RRGRR",
             "RGGGR",
             "RRGRR",
             "RRRRR")),
    country("SWEDEN", "blue",
            ("BBYBBBB",
             "BBYBBBB",
             "BBYBBBB",
             "YYYYYYY",
             "BBYBBBB",
             "BBYBBBB",
             "BBYBBBB"),
            ("BBYBBB",
             "BBYBBB",
             "YYYYYY",
             "BBYBBB",
             "BBYBBB")),
    country("INDIA", "orange",
            ("OOO",
             "WBW",
             "GGG"),
            ("OOOOOO",
             "OOOOOO",
             "WWWWWW",
             "WWBWWW",
             "GGGGGG",
             "GGGGGG")),
)

VARIANTS = [
    Variant(COLORS, "couleurs", "COLOR", COLOR_TEAMS),
    Variant("countries", "pays", "COUNTRY", COUNTRIES, nicknames=False),
]

BY_KEY = {v.key: v for v in VARIANTS}
BY_NAME = {c.name: c for v in VARIANTS for c in v.competitors}
# Choix proposés dans l'interface : (valeur du réglage, libellé)
CHOICES = [(v.key, v.label) for v in VARIANTS]


def resolve(settings) -> Variant:
    return BY_KEY.get(getattr(settings, "variant", COLORS), BY_KEY[COLORS])


def colors(name: str) -> tuple:
    """(foncée, principale, claire) d'un concurrent."""
    return BY_NAME[name].colors
