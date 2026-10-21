"""Formats de vidéo : la règle du jeu elle-même (course à la peinture, combat, 2 contre 2,
bataille royale…), en plus du mode (qui ne règle que les objets et le rythme).

Un format peut :
  - couper la peinture (combat : seuls les dégâts comptent) ;
  - changer la condition de victoire (« paint » : la plus grande surface ; « survival » : le
    dernier camp debout, puis le plus de vies) ;
  - former des équipes (2 contre 2 : même couleur, pas de tirs amis, score commun) ;
  - imposer le nombre et la taille des cubes, les vies, les objets ;
  - activer la « tempête » : une zone qui rétrécit et blesse les cubes restés dehors ;
  - finir la partie dès qu'il ne reste qu'un camp (la vidéo dure alors moins longtemps).

« classic » est le jeu d'origine. « random » tire un format long (selon la seed, ou via le
garde-fou anti-répétition de game/variety.py qui évite d'enchaîner deux fois le même).
"""

from __future__ import annotations

import random
from dataclasses import dataclass, field, replace

from engine8bit import palette

from .settings import ITEM_KINDS, Settings

CLASSIC = "classic"
RANDOM = "random"
PAINT = "paint"
SURVIVAL = "survival"


@dataclass(frozen=True)
class Format:
    key: str
    name: str                     # affiché dans la vidéo (anglais, police 8-bit)
    label: str                    # affiché dans l'interface (français)
    pitch: str                    # une phrase pour l'interface
    color: tuple
    paint: bool = True            # les cubes peignent l'arène
    win: str = PAINT              # PAINT ou SURVIVAL
    team_size: int = 1            # 2 = équipes de deux (2 contre 2)
    players: tuple | None = None  # (min, max) de cubes imposé, sinon le réglage « Joueurs »
    weights: dict | None = None   # objets imposés (le mode ne s'applique pas)
    overrides: dict = field(default_factory=dict)
    storm: float = 0.0            # début de la tempête (part du chrono, 0 = pas de tempête)
    early_end: bool = False       # la partie s'arrête quand il ne reste qu'un camp
    use_mode: bool = True         # le mode de jeu (KABOOM, TURBO…) s'applique
    short: bool = False           # pensé pour les vidéos courtes (< 1 minute)
    hook: str = ""                # accroche propre au format (sinon les accroches du réglage)


FORMATS = [
    Format(CLASSIC, "PAINT RACE", "course à la peinture",
           "la couleur qui couvre le plus de surface gagne (le jeu d'origine)", palette.YELLOW),
    Format("duo", "2 VS 2", "2 contre 2",
           "deux équipes de deux cubes de la même couleur, score commun, pas de tirs amis",
           palette.CYAN, team_size=2, players=(4, 4), hook="PICK A TEAM!"),
    Format("combat", "FIGHT!", "combat",
           "pas de peinture : les objets font des dégâts, le dernier cube debout gagne",
           palette.RED, paint=False, win=SURVIVAL, use_mode=False, storm=0.7, early_end=True,
           weights={"gun": 28, "brush": 20, "bomb": 22, "bucket": 8, "ice": 6, "boots": 8, "potion": 8,
                    "heart": 10},
           overrides={"lives": 6, "duel_lives": 6, "item_interval": 2.6, "item_ramp": 0.6, "max_items": 4,
                      "speed_ramp": 1.6, "max_hourglasses": 0, "comeback": 0.4},
           hook="WHO SURVIVES?"),
    Format("royale", "BATTLE ROYALE", "bataille royale",
           "combat à 6-8 petits cubes, sans peinture, 4 vies, une tempête qui rétrécit : le dernier debout gagne",
           palette.PURPLE_LIGHT, paint=False, win=SURVIVAL, players=(6, 8), use_mode=False, storm=0.65,
           early_end=True,
           weights={"gun": 24, "brush": 16, "bomb": 18, "bucket": 8, "ice": 6, "boots": 10, "potion": 8,
                    "heart": 10},
           overrides={"cube_size": 9, "lives": 4, "duel_lives": 0, "item_interval": 3.0, "item_ramp": 0.7,
                      "max_items": 4, "speed_ramp": 1.5, "max_hourglasses": 0, "brush_radius": 22,
                      "bomb_radius": 15, "comeback": 0.3},
           hook="ONLY ONE SURVIVES!"),
    Format("sprint", "SPEED RUN", "sprint (court)",
           "course à la peinture express à 2 ou 3 cubes, objets simples : vidéo courte",
           palette.GREEN_LIGHT, players=(2, 3), use_mode=False, short=True,
           weights={"roller": 35, "bucket": 25, "boots": 25, "potion": 15},
           overrides={"battle_duration": 26.0, "tiktok_rewards": False, "item_interval": 2.5, "item_ramp": 0.8,
                      "max_items": 3, "speed_ramp": 1.5, "lives": 0},
           hook="30 SECONDS. GO!"),
    Format("duel", "1V1 DUEL", "duel (court)",
           "combat à deux, sans peinture, 3 vies : le premier K.O. perd. Vidéo courte",
           palette.ORANGE, paint=False, win=SURVIVAL, players=(2, 2), use_mode=False, storm=0.5, early_end=True,
           short=True,
           weights={"gun": 34, "brush": 24, "bomb": 22, "boots": 10, "heart": 10},
           overrides={"lives": 3, "duel_lives": 3, "battle_duration": 30.0, "tiktok_rewards": False,
                      "item_interval": 1.6, "item_ramp": 0.7, "max_items": 3, "speed_ramp": 1.6,
                      "max_hourglasses": 0},
           hook="1V1. WHO WINS?"),
]

BY_KEY = {f.key: f for f in FORMATS}
# Choix proposés dans l'interface : (valeur du réglage, libellé)
CHOICES = [(RANDOM, "aléatoire")] + [(f.key, f.label) for f in FORMATS]
# Tirage « random » sans garde-fou : formats longs uniquement, avec leur poids
LONG_WEIGHTS = {CLASSIC: 40, "duo": 18, "combat": 22, "royale": 20}
SHORT_WEIGHTS = {"sprint": 40, "duel": 35, CLASSIC: 25}


def resolve(seed: int, settings: Settings) -> Format:
    key = getattr(settings, "format", CLASSIC)
    if key == RANDOM:
        rng = random.Random(seed * 3571 + 61)
        keys = list(LONG_WEIGHTS)
        return BY_KEY[rng.choices(keys, weights=[LONG_WEIGHTS[k] for k in keys])[0]]
    return BY_KEY.get(key, BY_KEY[CLASSIC])


def players_for(seed: int, fmt: Format, settings: Settings) -> int:
    """Nombre de cubes imposé par le format (0 = le réglage décide)."""
    if getattr(settings, "lineup", None):
        return len(settings.lineup)
    if fmt.players is None:
        return 0
    lo, hi = fmt.players
    if lo <= settings.players <= hi:
        return settings.players
    return random.Random(seed * 8191 + 3).randint(lo, hi)


def apply(settings: Settings, fmt: Format, seed: int) -> Settings:
    """Copie des réglages avec les objets et retouches du format (après le mode)."""
    changes = dict(fmt.overrides)
    if fmt.weights is not None:
        changes.update({f"prob_{k}": float(fmt.weights.get(k, 0)) for k in ITEM_KINDS})
        changes["escalation"] = False
    n = players_for(seed, fmt, settings)
    if n and n != settings.players:
        changes["players"] = n
    s = replace(settings, **changes) if changes else settings      # course classique : réglages intacts
    if s.extra_lives and fmt.early_end:
        # vies ajoutées par le garde-fou quand la partie finirait trop tôt (vidéo < 1 minute)
        s = replace(s, lives=s.lives + s.extra_lives,
                    duel_lives=s.duel_lives + s.extra_lives if s.duel_lives else 0)
    # durée visée par le garde-fou (vidéos courtes / longues de durées différentes)
    if s.target_duration > 0:
        from .battle import fixed_frames_seconds
        fixed = fixed_frames_seconds(s)
        s = replace(s, battle_duration=max(12.0, s.target_duration - fixed),
                    tiktok_rewards=s.target_duration >= s.min_video_duration)
    return s
