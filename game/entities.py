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
    frozen: int = 0          # images restantes de gel (objet Glace)
    roller: int = 0          # images restantes de rouleau
    magnet: int = 0          # images restantes d'aimant
    boots: int = 0           # images restantes de bottes (vitesse augmentée)
    hit_anim: int = 0        # images restantes de l'animation « touché » (purement visuelle)
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
    def immobile(self) -> bool:
        """Assommé ou gelé : ne bouge plus, ne peint plus, ne ramasse plus."""
        return self.stun > 0 or self.frozen > 0

    @property
    def active(self) -> bool:
        return not self.immobile


@dataclass
class Item:
    kind: str
    x: float                 # centre (flottant : l'aimant peut déplacer l'objet)
    y: float
    spawn_frame: int
    size: int = 9

    def rect(self):
        h = self.size // 2
        x0, y0 = int(round(self.x)) - h, int(round(self.y)) - h
        return x0, y0, x0 + self.size, y0 + self.size


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
class Bomb:
    owner: int
    x: float
    y: float
    frames_left: int
    total: int
    next_tick: int = 0


@dataclass
class Wave:
    owner: int
    horizontal: bool         # True : la vague parcourt une bande horizontale (de gauche à droite)
    band: float              # coordonnée du centre de la bande (y si horizontale, x sinon)
    origin: float            # point de départ le long de la bande
    half: float              # demi-épaisseur
    dist: float = 0.0        # distance parcourue de chaque côté
    hit: set = field(default_factory=set)


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
