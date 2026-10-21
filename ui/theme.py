"""Direction artistique de l'interface terminal : la palette NES du moteur, en hexadécimal.

Valeurs recopiées depuis engine8bit/palette.py (sans l'importer, pour ne pas charger
pygame avant l'écran de démarrage).
"""

BLACK = "#000000"
WHITE = "#fcfcfc"
GREY_LIGHT = "#bcbcbc"
GREY = "#7c7c7c"
GREY_DARK = "#3c3c44"

NAVY_DARK = "#080828"
FLOOR_A = "#141420"
FLOOR_B = "#1e1e2e"

RED_DARK, RED, RED_LIGHT = "#a81000", "#f83800", "#f87858"
BLUE_DARK, BLUE, BLUE_LIGHT = "#0000bc", "#0078f8", "#3cbcfc"
YELLOW_DARK, YELLOW, YELLOW_LIGHT = "#ac7c00", "#f8b800", "#f8d878"
GREEN_DARK, GREEN, GREEN_LIGHT = "#007800", "#00b800", "#58d854"

MAGENTA = "#f858f8"
PURPLE = "#6844fc"
SKY = "#a4e4fc"
ORANGE = "#f89838"

# Équipes : (foncé, peinture, clair), dans l'ordre du jeu
TEAMS = {
    "RED": (RED_DARK, RED, RED_LIGHT),
    "BLUE": (BLUE_DARK, BLUE, BLUE_LIGHT),
    "YELLOW": (YELLOW_DARK, YELLOW, YELLOW_LIGHT),
    "GREEN": (GREEN_DARK, GREEN, GREEN_LIGHT),
}

# Couleur de chaque objet, reprise de son sprite (game/art.py)
ITEM_COLORS = {
    "gun": GREY_LIGHT, "brush": MAGENTA, "potion": "#9878f8", "hourglass": YELLOW_LIGHT,
    "bomb": ORANGE, "roller": RED_LIGHT, "bucket": GREEN_LIGHT, "ice": SKY, "magnet": RED,
    "boots": YELLOW_DARK, "heart": RED,
}

SPINNER = "⠋⠙⠹⠸⠼⠴⠦⠧⠇⠏"
