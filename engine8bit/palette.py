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

# Couleurs des équipes : (foncé, peinture, clair)
TEAMS = {
    "RED": (RED_DARK, RED, RED_LIGHT),
    "BLUE": (BLUE_DARK, BLUE, BLUE_LIGHT),
    "YELLOW": (YELLOW_DARK, YELLOW, YELLOW_LIGHT),
    "GREEN": (GREEN_DARK, GREEN, GREEN_LIGHT),
}
PRIMARY_TEAMS = ["RED", "BLUE", "YELLOW"]
FOURTH_TEAM = "GREEN"
