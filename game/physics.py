"""Déplacements, rebonds et collisions (boîtes alignées sur les axes), peinture du sol."""

import math
import random

import numpy as np

from .entities import Cube

DT = 1 / 60
KB_DECAY = 0.88                 # amortissement par image de la vitesse de recul
MIN_COMPONENT = math.sin(math.radians(20))
BOUNCE_JITTER = math.radians(6)


def keep_diagonal(dx: float, dy: float) -> tuple[float, float]:
    """Garde un angle d'au moins 20° avec les axes (pas de trajectoire collée à un mur)."""
    sx = 1.0 if dx >= 0 else -1.0
    sy = 1.0 if dy >= 0 else -1.0
    ax, ay = abs(dx), abs(dy)
    if ax < MIN_COMPONENT:
        ax = MIN_COMPONENT
        ay = math.sqrt(1 - ax * ax)
    elif ay < MIN_COMPONENT:
        ay = MIN_COMPONENT
        ax = math.sqrt(1 - ay * ay)
    return sx * ax, sy * ay


def jitter(cube: Cube, rng: random.Random) -> None:
    """Légère variation d'angle à chaque rebond pour éviter les trajectoires répétitives."""
    a = math.atan2(cube.dy, cube.dx) + rng.uniform(-BOUNCE_JITTER, BOUNCE_JITTER)
    cube.dx, cube.dy = keep_diagonal(math.cos(a), math.sin(a))


def clamp(cube: Cube, w: int, h: int) -> tuple[bool, bool]:
    """Remet le cube dans l'arène. Renvoie (touche mur gauche/droite, touche haut/bas)
    uniquement si la direction a dû être inversée."""
    hx = hy = False
    half = cube.half
    if cube.cx - half < 0:
        cube.cx = half
        cube.kb_x = abs(cube.kb_x) * 0.5
        if cube.dx < 0:
            cube.dx = -cube.dx
            hx = True
    elif cube.cx + half > w:
        cube.cx = w - half
        cube.kb_x = -abs(cube.kb_x) * 0.5
        if cube.dx > 0:
            cube.dx = -cube.dx
            hx = True
    if cube.cy - half < 0:
        cube.cy = half
        cube.kb_y = abs(cube.kb_y) * 0.5
        if cube.dy < 0:
            cube.dy = -cube.dy
            hy = True
    elif cube.cy + half > h:
        cube.cy = h - half
        cube.kb_y = -abs(cube.kb_y) * 0.5
        if cube.dy > 0:
            cube.dy = -cube.dy
            hy = True
    return hx, hy


def move(cube: Cube, speed: float, w: int, h: int) -> bool:
    """Avance d'une image. Renvoie True si le cube a rebondi sur un mur."""
    v = 0.0 if cube.immobile else speed
    cube.cx += cube.dx * v * DT + cube.kb_x * DT
    cube.cy += cube.dy * v * DT + cube.kb_y * DT
    cube.kb_x *= KB_DECAY
    cube.kb_y *= KB_DECAY
    if abs(cube.kb_x) < 0.5:
        cube.kb_x = 0.0
    if abs(cube.kb_y) < 0.5:
        cube.kb_y = 0.0
    hx, hy = clamp(cube, w, h)
    return (hx or hy) and not cube.immobile


def resolve_collisions(cubes: list[Cube], w: int, h: int, iterations: int = 4) -> list[tuple[int, int]]:
    """Sépare les cubes qui se chevauchent le long de l'axe de moindre pénétration et
    renvoie les directions vers l'extérieur (vitesse constante). Un cube assommé ou gelé est immobile."""
    collided: list[tuple[int, int]] = []
    for _ in range(iterations):
        any_overlap = False
        for i in range(len(cubes)):
            for j in range(i + 1, len(cubes)):
                a, b = cubes[i], cubes[j]
                ox = a.half + b.half - abs(a.cx - b.cx)
                oy = a.half + b.half - abs(a.cy - b.cy)
                if ox <= 1e-6 or oy <= 1e-6:
                    continue
                any_overlap = True
                wa = 0.0 if a.immobile else 1.0
                wb = 0.0 if b.immobile else 1.0
                if wa + wb == 0:
                    wa = wb = 1.0
                sa = wa / (wa + wb)
                if ox < oy:
                    s = -1.0 if (a.cx, a.idx) < (b.cx, b.idx) else 1.0
                    a.cx += s * ox * sa
                    b.cx -= s * ox * (1 - sa)
                    if not a.immobile:
                        a.dx = s * abs(a.dx)
                    if not b.immobile:
                        b.dx = -s * abs(b.dx)
                else:
                    s = -1.0 if (a.cy, a.idx) < (b.cy, b.idx) else 1.0
                    a.cy += s * oy * sa
                    b.cy -= s * oy * (1 - sa)
                    if not a.immobile:
                        a.dy = s * abs(a.dy)
                    if not b.immobile:
                        b.dy = -s * abs(b.dy)
                if (i, j) not in collided:
                    collided.append((i, j))
        for c in cubes:
            clamp(c, w, h)
        if not any_overlap:
            break
    return collided


# ---- Peinture -------------------------------------------------------------------------

def paint_rect(grid: np.ndarray, x0: int, y0: int, x1: int, y1: int, idx: int) -> None:
    h, w = grid.shape
    x0, y0 = max(0, x0), max(0, y0)
    x1, y1 = min(w, x1), min(h, y1)
    if x1 > x0 and y1 > y0:
        grid[y0:y1, x0:x1] = idx


def disc_mask(grid_shape, cx: float, cy: float, r: float):
    h, w = grid_shape
    x0, x1 = max(0, int(math.floor(cx - r))), min(w, int(math.ceil(cx + r)) + 1)
    y0, y1 = max(0, int(math.floor(cy - r))), min(h, int(math.ceil(cy + r)) + 1)
    if x1 <= x0 or y1 <= y0:
        return None
    yy, xx = np.mgrid[y0:y1, x0:x1]
    mask = (xx + 0.5 - cx) ** 2 + (yy + 0.5 - cy) ** 2 <= r * r
    return (slice(y0, y1), slice(x0, x1)), mask


def paint_disc(grid: np.ndarray, cx: float, cy: float, r: float, idx: int) -> None:
    res = disc_mask(grid.shape, cx, cy, r)
    if res is None:
        return
    sl, mask = res
    grid[sl][mask] = idx


def paint_sector(grid: np.ndarray, cx: float, cy: float, r: float, theta: float,
                 a_from: float, a_to: float, idx: int) -> None:
    """Peint les cases du disque de rayon r dont l'angle relatif à theta est dans [a_from, a_to]."""
    res = disc_mask(grid.shape, cx, cy, r)
    if res is None:
        return
    sl, mask = res
    yy, xx = np.mgrid[sl[0], sl[1]]
    ang = np.arctan2(yy + 0.5 - cy, xx + 0.5 - cx) - theta
    ang = (ang + np.pi) % (2 * np.pi) - np.pi
    mask &= (ang >= a_from) & (ang <= a_to)
    grid[sl][mask] = idx
