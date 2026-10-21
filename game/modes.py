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
         {"bomb": 55, "gun": 37, "heart": 8},
         {"speed_ramp": 1.8, "item_interval": 3.0, "item_ramp": 0.5, "max_items": 4,
          "bomb_fuse": 1.1, "bomb_radius": 22}),
    Mode("gogopaint", "GOGO PAINT", "Gogo Paint",
         "pluie de rouleaux, seaux et pinceaux, vies illimitées : on peint, on ne se tue pas",
         palette.MAGENTA,
         {"roller": 35, "bucket": 30, "brush": 20, "potion": 15},
         {"speed_ramp": 1.6, "item_interval": 2.0, "item_ramp": 0.7, "max_items": 5,
          "roller_duration": 6.5, "lives": 0}),
    Mode("blizzard", "BLIZZARD", "Blizzard",
         "partie glaciale et lente : la glace fige tout le monde, les fusils achèvent",
         palette.SKY,
         {"ice": 42, "gun": 32, "boots": 18, "heart": 8},
         {"battle_duration": 55.0, "speed_ramp": 1.5, "cube_speed": 48.0, "item_interval": 3.5, "item_ramp": 1.0,
          "ice_duration": 2.6}),
    Mode("turbo", "TURBO", "Turbo", "bottes, rouleaux et aimants, les cubes foncent de plus en plus vite",
         palette.YELLOW,
         {"boots": 45, "roller": 30, "magnet": 25},
         {"speed_ramp": 2.3, "cube_speed": 60.0, "item_interval": 3.0, "item_ramp": 0.6,
          "boots_factor": 1.9}),
    Mode("titans", "TITANS", "Titans", "des géants lents aux potions de 9 s qui balaient l'arène",
         palette.PURPLE,
         {"potion": 50, "brush": 30, "roller": 20},
         {"battle_duration": 60.0, "speed_ramp": 1.4, "item_interval": 4.0, "item_ramp": 1.0,
          "potion_duration": 9.0, "brush_radius": 36}),
    Mode("lootrain", "LOOT RAIN", "Pluie d'objets", "tous les objets tombent sans arrêt, aimants en bonus",
         palette.GREEN_LIGHT,
         {"magnet": 20, "gun": 12, "brush": 12, "potion": 12, "bomb": 12, "roller": 12, "bucket": 12,
          "ice": 8, "boots": 12, "hourglass": 6, "heart": 8},
         {"speed_ramp": 1.8, "item_interval": 1.2, "item_ramp": 0.8, "max_items": 8,
          "max_hourglasses": 2}),
    Mode("escalation", "ALL-OUT WAR", "Escalade",
         "plus le temps passe, plus c'est la guerre : objets, vitesse et coups de plus en plus violents",
         palette.WHITE,
         {"gun": 25, "brush": 25, "potion": 25, "hourglass": 25, "bomb": 20, "roller": 20, "bucket": 20,
          "ice": 20, "magnet": 20, "boots": 20, "heart": 15},
         {"escalation": True}),
    Mode("suddendeath", "SUDDEN DEATH", "Mort subite", "une seule vie : le premier touché est K.O.",
         palette.RED,
         {"gun": 30, "bomb": 25, "brush": 25, "bucket": 20},
         {"speed_ramp": 2.0, "item_interval": 3.0, "item_ramp": 0.6, "lives": 1,
          "duel_lives": 0}),
]

BY_KEY = {m.key: m for m in MODES}
# Choix proposés dans l'interface : (valeur du réglage, libellé)
CHOICES = [(CLASSIC, "classique"), (RANDOM, "aléatoire")] + [(m.key, m.label.lower()) for m in MODES]


def resolve(seed: int, settings: Settings) -> Mode | None:
    """Mode de la partie (None = classique, réglages de l'utilisateur)."""
    if settings.mode == RANDOM:
        return random.Random(seed * 7919 + 101).choice(MODES)
    return BY_KEY.get(settings.mode)


def summary(settings: Settings) -> str:
    """Temps, ratio de vitesse et rythme des bonus, sur une ligne (réglages déjà appliqués)."""
    from engine8bit.display import FPS
    from .battle import default_battle_frames
    start = settings.item_interval
    if settings.escalation:
        end = max(45 / FPS, start * 0.28)
    else:
        end = start * settings.item_ramp
    drops = f"bonus toutes les {start:g} s"
    if abs(end - start) >= 0.05:
        drops += f" → {round(end, 1):g} s"
    seconds = round(default_battle_frames(settings) / FPS)
    return f"{seconds:g} s · vitesse ×{settings.speed_ramp:g} · {drops}"


def apply(settings: Settings, mode: Mode | None) -> Settings:
    """Copie des réglages avec les probabilités et retouches du mode."""
    if mode is None:
        return settings
    probs = {f"prob_{k}": float(mode.weights.get(k, 0)) for k in ITEM_KINDS}
    # l'escalade est un mode à part : elle ne s'ajoute jamais aux autres
    return replace(settings, **probs, **{"escalation": False, **mode.overrides})
