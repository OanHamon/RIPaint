"""Modes de jeu : chacun impose ses probabilités d'objets et retouche quelques réglages
pour donner à la partie une vraie personnalité (rythme, dangerosité, vitesse…).

Le mode "classic" garde les réglages de l'utilisateur ; "random" tire un mode thématique
à partir de la seed (générateur à part : la seed garde le même sens pour le reste).
"""

from __future__ import annotations

import random
from dataclasses import dataclass, field, replace

from engine8bit import palette

from .settings import ITEM_KINDS, Settings

CLASSIC = "classic"
RANDOM = "random"


@dataclass(frozen=True)
class Mode:
    key: str
    name: str                 # affiché dans la vidéo (anglais, police 8-bit)
    label: str                # affiché dans l'interface (français)
    pitch: str                # une phrase : ce qui fait le caractère du mode
    color: tuple
    weights: dict             # objets absents = jamais
    overrides: dict = field(default_factory=dict)


MODES = [
    Mode("kaboom", "KABOOM", "Kaboom", "que des bombes et des fusils : ça explose de partout",
         palette.ORANGE,
         {"bomb": 60, "gun": 40},
         {"item_interval": 3.0, "max_items": 4, "bomb_fuse": 1.1, "bomb_radius": 22}),
    Mode("gogopaint", "GOGO PAINT", "Gogo Paint",
         "pluie de rouleaux, seaux et pinceaux, vies illimitées : on peint, on ne se tue pas",
         palette.MAGENTA,
         {"roller": 35, "bucket": 30, "brush": 20, "potion": 15},
         {"item_interval": 2.0, "max_items": 5, "roller_duration": 6.5, "lives": 0}),
    Mode("blizzard", "BLIZZARD", "Blizzard", "la glace fige tout le monde, les fusils finissent le travail",
         palette.SKY,
         {"ice": 45, "gun": 35, "boots": 20},
         {"item_interval": 3.5, "ice_duration": 2.6}),
    Mode("turbo", "TURBO", "Turbo", "bottes, rouleaux et aimants, les cubes foncent de plus en plus vite",
         palette.YELLOW,
         {"boots": 45, "roller": 30, "magnet": 25},
         {"item_interval": 3.0, "cube_speed": 60.0, "speed_ramp": 2.3, "boots_factor": 1.9}),
    Mode("titans", "TITANS", "Titans", "les potions durent longtemps : des géants qui balaient l'arène",
         palette.PURPLE,
         {"potion": 50, "brush": 30, "roller": 20},
         {"item_interval": 3.5, "potion_duration": 9.0, "brush_radius": 36}),
    Mode("lootrain", "LOOT RAIN", "Pluie d'objets", "tous les objets tombent sans arrêt, aimants en bonus",
         palette.GREEN_LIGHT,
         {"magnet": 20, "gun": 12, "brush": 12, "potion": 12, "bomb": 12, "roller": 12, "bucket": 12,
          "ice": 8, "boots": 12, "hourglass": 6},
         {"item_interval": 1.2, "max_items": 8, "max_hourglasses": 2}),
    Mode("suddendeath", "SUDDEN DEATH", "Mort subite", "une seule vie : le premier touché est K.O.",
         palette.RED,
         {"gun": 30, "bomb": 25, "brush": 25, "bucket": 20},
         {"lives": 1, "item_interval": 3.0, "speed_ramp": 2.0}),
]

BY_KEY = {m.key: m for m in MODES}
# Choix proposés dans l'interface : (valeur du réglage, libellé)
CHOICES = [(CLASSIC, "classique"), (RANDOM, "aléatoire")] + [(m.key, m.label.lower()) for m in MODES]


def resolve(seed: int, settings: Settings) -> Mode | None:
    """Mode de la partie (None = classique, réglages de l'utilisateur)."""
    if settings.mode == RANDOM:
        return random.Random(seed * 7919 + 101).choice(MODES)
    return BY_KEY.get(settings.mode)


def apply(settings: Settings, mode: Mode | None) -> Settings:
    """Copie des réglages avec les probabilités et retouches du mode."""
    if mode is None:
        return settings
    probs = {f"prob_{k}": float(mode.weights.get(k, 0)) for k in ITEM_KINDS}
    return replace(settings, **probs, **mode.overrides)
