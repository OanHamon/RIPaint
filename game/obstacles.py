"""Obstacles de l'arène : petits blocs fixes, disposés en miroir gauche/droite.

Ils sont tirés avec leur propre générateur aléatoire (dérivé de la seed) : avec 0 obstacle,
la partie est strictement identique à celle d'une version sans obstacles.
"""

import random

# (largeur, hauteur) possibles, en pixels logiques
SHAPES = [(8, 8), (10, 10), (16, 6), (6, 16), (20, 6), (6, 20), (12, 8)]


def _overlap(a, b, gap: float) -> bool:
    return a[0] < b[2] + gap and a[2] > b[0] - gap and a[1] < b[3] + gap and a[3] > b[1] - gap


def make_obstacles(seed: int, count: int, cube_size: int, w: int, h: int) -> list[tuple[int, int, int, int]]:
    """Renvoie une liste de rectangles (x0, y0, x1, y1), x1/y1 exclus, en coordonnées d'arène.
    Couloir d'au moins 2 largeurs de cube vers les murs (un cube grossi par la potion y passe)
    et d'au moins 1 largeur + 6 px entre deux obstacles (un cube normal y passe largement)."""
    if count <= 0:
        return []
    rng = random.Random(seed * 7907 + 3)
    margin = 2 * cube_size + 2
    gap = cube_size + 6
    placed: list[tuple[int, int, int, int]] = []

    def fits(r) -> bool:
        if r[0] < margin or r[1] < margin or r[2] > w - margin or r[3] > h - margin:
            return False
        return not any(_overlap(r, o, gap) for o in placed)

    pairs, centre = divmod(count, 2)
    for _ in range(pairs):
        for _ in range(300):
            ow, oh = rng.choice(SHAPES)
            x0 = rng.randint(margin, max(margin, w // 2 - ow - gap // 2))
            y0 = rng.randint(margin, max(margin, h - margin - oh))
            left = (x0, y0, x0 + ow, y0 + oh)
            right = (w - left[2], y0, w - left[0], y0 + oh)       # symétrique gauche/droite
            if fits(left) and fits(right) and not _overlap(left, right, gap):
                placed += [left, right]
                break
    if centre:
        for _ in range(300):
            ow, oh = rng.choice(SHAPES)
            x0 = (w - ow) // 2
            y0 = rng.randint(margin, max(margin, h - margin - oh))
            r = (x0, y0, x0 + ow, y0 + oh)
            if fits(r):
                placed.append(r)
                break
    return placed
