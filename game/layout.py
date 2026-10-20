"""Mise en page de l'écran (pixels logiques) en respectant les zones de sécurité."""

from dataclasses import dataclass

from engine8bit.display import LOGICAL_H, LOGICAL_W, SafeZone

WALL = 2


@dataclass
class Layout:
    safe: SafeZone
    hud_y: int            # haut de la zone chrono / accroche
    arena_x: int          # coin haut-gauche de l'intérieur de l'arène
    arena_y: int
    arena_w: int
    arena_h: int
    scores_y: int         # haut de la zone des scores
    safe_x0: int
    safe_x1: int          # bord droit (exclu) de la zone sûre
    safe_y1: int          # bas (exclu) de la zone sûre

    @property
    def safe_cx(self) -> int:
        return (self.safe_x0 + self.safe_x1) // 2

    @property
    def safe_w(self) -> int:
        return self.safe_x1 - self.safe_x0


def make_layout(safe_top: int = 130, safe_bottom: int = 400, safe_right: int = 140) -> Layout:
    safe = SafeZone(safe_top, safe_bottom, safe_right)
    x0, x1 = safe.left, LOGICAL_W - safe.right
    y0, y1 = safe.top, LOGICAL_H - safe.bottom
    margin = 2
    hud_y = y0 + 1
    hud_h = 18                      # chrono x2 (14 px) + contour
    scores_h = 21                   # barre empilée + pourcentages
    outer_x0, outer_x1 = x0 + margin, x1 - margin
    outer_y0 = hud_y + hud_h + 1
    outer_y1 = y1 - scores_h - 2
    arena_w = (outer_x1 - outer_x0 - 2 * WALL) // 2 * 2
    arena_h = (outer_y1 - outer_y0 - 2 * WALL) // 2 * 2
    arena_w = max(40, arena_w)
    arena_h = max(40, arena_h)
    arena_x = outer_x0 + WALL + ((outer_x1 - outer_x0 - 2 * WALL) - arena_w) // 2
    arena_y = outer_y0 + WALL
    scores_y = arena_y + arena_h + WALL + 3
    return Layout(safe, hud_y, arena_x, arena_y, arena_w, arena_h, scores_y, x0, x1, y1)
