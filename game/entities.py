"""Entités de la partie (données uniquement ; la logique est dans physics/items/battle)."""

from dataclasses import dataclass, field


@dataclass
class Cube:
    idx: int
    team: str
    cx: float
    cy: float
    dx: float
    dy: float
    base_size: int
    size: int = 0
    stun: int = 0            # images restantes d'étourdissement
    slow: int = 0            # images restantes de ralentissement
    potion: int = 0          # images restantes de potion
    big: bool = False
    resize_anim: int = 0     # images restantes de l'animation grandir/rétrécir
    resize_from: int = 0
    resize_to: int = 0
    kb_x: float = 0.0        # vitesse de recul (coup de pinceau)
    kb_y: float = 0.0
    items: int = 0
    last_pos: tuple = (0.0, 0.0)
    still_frames: int = 0

    def __post_init__(self):
        if not self.size:
            self.size = self.base_size

    @property
    def half(self) -> float:
        return self.size / 2

    def rect(self) -> tuple[int, int, int, int]:
        """(x0, y0, x1, y1) en cases entières, x1/y1 exclus."""
        x0 = int(round(self.cx - self.half))
        y0 = int(round(self.cy - self.half))
        return x0, y0, x0 + self.size, y0 + self.size

    @property
    def active(self) -> bool:
        return self.stun <= 0


@dataclass
class Item:
    kind: str
    x: int                   # centre
    y: int
    spawn_frame: int
    size: int = 9

    def rect(self):
        h = self.size // 2
        return self.x - h, self.y - h, self.x - h + self.size, self.y - h + self.size


@dataclass
class Aim:
    shooter: int
    target: int
    frames_left: int
    total: int


@dataclass
class Bullet:
    owner: int
    x: float
    y: float
    dx: float
    dy: float
    alive: bool = True
    trail: list = field(default_factory=list)   # positions récentes (visuel)


@dataclass
class Swipe:
    owner: int
    theta: float             # direction centrale de l'arc (radians)
    frame: int = 0
    duration: int = 14
    hit: set = field(default_factory=set)
    painted_upto: float = 0.0


@dataclass
class Particle:
    x: float
    y: float
    vx: float
    vy: float
    color: tuple
    life: int
    max_life: int
    gravity: float = 0.0
    layer: int = 0           # 0 = arène, 1 = écran


@dataclass
class Popup:
    text: str
    color: tuple
    start: int
    duration: int
    anchor: str = "top"      # "top" ou "bottom" de l'arène
