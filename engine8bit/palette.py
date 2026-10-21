"""Palette limitée inspirée de la NES. Toutes les couleurs du rendu viennent d'ici."""

BLACK = (0, 0, 0)
WHITE = (252, 252, 252)
GREY_LIGHT = (188, 188, 188)
GREY = (124, 124, 124)
GREY_DARK = (60, 60, 68)

NAVY = (0, 0, 88)
NAVY_DARK = (8, 8, 40)
FLOOR_A = (20, 20, 32)
FLOOR_B = (30, 30, 46)

RED_DARK = (168, 16, 0)
RED = (248, 56, 0)
RED_LIGHT = (248, 120, 88)

BLUE_DARK = (0, 0, 188)
BLUE = (0, 120, 248)
BLUE_LIGHT = (60, 188, 252)

YELLOW_DARK = (172, 124, 0)
YELLOW = (248, 184, 0)
YELLOW_LIGHT = (248, 216, 120)

GREEN_DARK = (0, 120, 0)
GREEN = (0, 184, 0)
GREEN_LIGHT = (88, 216, 84)

MAGENTA = (248, 88, 248)
PURPLE = (104, 68, 252)
BROWN = (136, 72, 0)
SKY = (164, 228, 252)
ORANGE = (248, 152, 56)
ORANGE_LIGHT = (252, 196, 140)
ORANGE_DARK = (168, 76, 0)
PURPLE_DARK = (60, 24, 156)
PURPLE_LIGHT = (164, 140, 252)
PINK_DARK = (168, 0, 120)
PINK_LIGHT = (252, 168, 228)
CYAN_DARK = (0, 120, 136)
CYAN = (0, 216, 216)
CYAN_LIGHT = (152, 252, 240)
BROWN_LIGHT = (200, 128, 64)

# Thèmes d'arène (sols toujours sombres : la peinture reste lisible)
LAVA_A = (44, 12, 8)
LAVA_B = (64, 20, 12)
LAVA_GLOW = (120, 36, 8)
ICE_A = (16, 32, 52)
ICE_B = (24, 46, 70)
ICE_BG = (8, 20, 44)
SPACE_A = (6, 6, 14)
SPACE_B = (12, 10, 24)
JUNGLE_A = (10, 32, 16)
JUNGLE_B = (16, 44, 22)
JUNGLE_BG = (6, 22, 10)
SAND_A = (48, 34, 18)
SAND_B = (62, 46, 26)
SAND_BG = (36, 22, 10)
NEON_A = (10, 4, 22)
NEON_B = (18, 8, 36)
OCEAN_A = (4, 22, 44)
OCEAN_B = (8, 32, 60)
OCEAN_BG = (2, 12, 30)
CANDY_A = (40, 12, 40)
CANDY_B = (54, 20, 56)
CANDY_BG = (28, 6, 30)

# Couleurs des équipes : (foncé, peinture, clair)
TEAMS = {
    "RED": (RED_DARK, RED, RED_LIGHT),
    "BLUE": (BLUE_DARK, BLUE, BLUE_LIGHT),
    "YELLOW": (YELLOW_DARK, YELLOW, YELLOW_LIGHT),
    "GREEN": (GREEN_DARK, GREEN, GREEN_LIGHT),
    # couleurs supplémentaires (bataille royale, PaintCup) : utilisées au-delà de 4 cubes
    "ORANGE": (ORANGE_DARK, ORANGE, ORANGE_LIGHT),
    "PURPLE": (PURPLE_DARK, PURPLE, PURPLE_LIGHT),
    "PINK": (PINK_DARK, MAGENTA, PINK_LIGHT),
    "CYAN": (CYAN_DARK, CYAN, CYAN_LIGHT),
}
PRIMARY_TEAMS = ["RED", "BLUE", "YELLOW"]
FOURTH_TEAM = "GREEN"
EXTRA_TEAMS = ["ORANGE", "PURPLE", "PINK", "CYAN"]
