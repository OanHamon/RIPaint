"""Tirage d'un scénario à partir d'une seed.

Toute la partie est déterminée par (seed, réglages) : on utilise un générateur
random.Random(seed) qui continue d'être consommé par la simulation (objets, perturbations).
"""

import math
import random
from dataclasses import dataclass, field

from engine8bit import palette

from .settings import Settings

MIN_AXIS_ANGLE = math.radians(20)  # évite les trajectoires presque horizontales/verticales


@dataclass
class CubeStart:
    team: str
    x: float          # centre, coordonnées arène
    y: float
    dx: float         # direction unitaire
    dy: float


@dataclass
class Scenario:
    seed: int
    cubes: list[CubeStart]
    hook: str
    rng: random.Random = field(repr=False)


def random_direction(rng: random.Random) -> tuple[float, float]:
    a = rng.uniform(MIN_AXIS_ANGLE, math.pi / 2 - MIN_AXIS_ANGLE)
    a += rng.choice([0, 0.5, 1.0, 1.5]) * math.pi
    return math.cos(a), math.sin(a)


def make_scenario(seed: int, settings: Settings, arena_w: int, arena_h: int) -> Scenario:
    rng = random.Random(seed)
    n = rng.randint(2, 4)            # toujours tiré, pour que la seed garde le même sens
    if settings.players in (2, 3, 4):
        n = settings.players
    if n == 4:
        teams = palette.PRIMARY_TEAMS + [palette.FOURTH_TEAM]
        rng.shuffle(teams)
    else:
        teams = rng.sample(palette.PRIMARY_TEAMS, n)
    size = settings.cube_size
    margin = size + 4
    min_dist = size * 3.5
    cubes: list[CubeStart] = []
    for team in teams:
        for _ in range(500):
            x = rng.uniform(margin, arena_w - margin)
            y = rng.uniform(margin, arena_h - margin)
            if all(math.hypot(x - c.x, y - c.y) >= min_dist for c in cubes):
                break
        dx, dy = random_direction(rng)
        cubes.append(CubeStart(team, x, y, dx, dy))
    hooks = [h for h in settings.hooks if h.strip()] or ["CHOISIS TA COULEUR !"]
    hook = rng.choice(hooks)
    return Scenario(seed, cubes, hook, rng)
