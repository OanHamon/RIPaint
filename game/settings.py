"""Réglages de l'application, sauvegardés dans config.json à la racine du projet."""

import json
from dataclasses import asdict, dataclass, field, fields
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CONFIG_PATH = ROOT / "config.json"

CONFIG_VERSION = 6

# Les nouveaux objets sont ajoutés À LA FIN : l'ordre compte pour le tirage (sens des seeds).
ITEM_KINDS = ["gun", "brush", "potion", "hourglass", "bomb", "roller", "bucket", "ice", "magnet", "boots",
              "heart"]
ITEM_LABELS = {"gun": "Fusil", "brush": "Gros pinceau", "potion": "Potion", "hourglass": "Sablier",
               "bomb": "Bombe", "roller": "Rouleau", "bucket": "Seau arc-en-ciel", "ice": "Glace",
               "magnet": "Aimant", "boots": "Bottes", "heart": "Cœur (+1 vie)"}

# Phrases d'accroche affichées dans la vidéo (en anglais)
DEFAULT_HOOKS = [
    "PICK YOUR COLOR!",
    "WHO WILL WIN?",
    "BET ON A CUBE!",
    "COMMENT YOUR COLOR!",
    "WHICH COLOR WINS?",
    "WILL YOUR CUBE WIN?",
    "WHO PAINTS THE MOST?",
]
OLD_FRENCH_HOOKS = [
    "CHOISIS TA COULEUR !",
    "QUI VA GAGNER ?",
    "PARIE SUR UN CUBE !",
    "COMMENTE TA COULEUR !",
    "QUELLE COULEUR GAGNE ?",
    "TON CUBE VA GAGNER ?",
    "QUI PEINT LE PLUS ?",
]


@dataclass
class Settings:
    # Objets : poids (0-100), normalisés à l'usage
    prob_gun: float = 25
    prob_brush: float = 25
    prob_potion: float = 25
    prob_hourglass: float = 25
    prob_bomb: float = 20
    prob_roller: float = 20
    prob_bucket: float = 20
    prob_ice: float = 20
    prob_magnet: float = 20
    prob_boots: float = 20
    prob_heart: float = 15
    item_interval: float = 5.0        # secondes entre deux apparitions
    max_items: int = 3                # objets présents simultanément
    max_hourglasses: int = 3          # sabliers par partie
    hourglass_bonus: float = 3.0      # secondes ajoutées par sablier

    # Effets des objets
    aim_duration: float = 0.3
    bullet_speed: float = 170.0       # px logiques / s
    stun_duration: float = 5.0
    brush_radius: int = 30
    slow_duration: float = 3.0
    slow_factor: float = 0.45
    potion_duration: float = 5.0
    potion_scale: int = 2
    bomb_fuse: float = 1.5            # secondes avant l'explosion
    bomb_radius: int = 18
    roller_duration: float = 5.0
    roller_width: float = 2.8         # largeur de la traînée (x la taille du cube)
    bucket_width: float = 1.6         # épaisseur de la vague (x la taille du cube)
    ice_duration: float = 2.0
    magnet_duration: float = 4.0
    magnet_speed: float = 70.0        # px logiques / s
    boots_duration: float = 5.0
    boots_factor: float = 1.8         # multiplicateur de vitesse des bottes

    # Partie
    intro_duration: float = 3.0       # compte à rebours 3-2-1
    battle_duration: float = 50.0     # durée minimale de bataille (allongée si besoin, voir tiktok_rewards)
    outro_duration: float = 7.0       # FIN + révélation des scores + gagnant + retour au début (boucle)

    # Rétention des spectateurs
    teaser: bool = True               # 0,8 s de l'arène finale en ouverture, puis « rembobinage »
    hide_final_scores: float = 5.0    # secondes de fin où les % sont cachés (« ??% ») ; 0 = jamais
    comeback: float = 0.5             # probabilité qu'un objet apparaisse près du cube en dernière place
    lead_announce: bool = True        # « RED LEADS! » quand le leader change
    slowmo: bool = True               # ralenti sur les K.O. et les explosions
    nicknames: bool = True            # surnoms des cubes (« RED BLAZE »)
    league: bool = True               # classement des couleurs conservé d'une vidéo à l'autre
    tiktok_rewards: bool = True       # vidéo toujours > 1 min (Creator Rewards Program)
    min_video_duration: float = 62.0  # durée minimale visée quand tiktok_rewards est actif
    players: int = 0                  # 0 = aléatoire (2 à 4), sinon 2, 3 ou 4
    cube_size: int = 13
    arena_centered: bool = True       # arène centrée sur l'écran (False = ancienne mise en page)
    lives: int = 3                    # vies par cube (0 = illimitées)
    max_bonus_lives: int = 2          # vies gagnées avec les cœurs au-delà du départ
    death_shrink: bool = True         # un cube K.O. se grise et rapetisse
    map: str = "random"               # « random », un nom de carte, ou « generated » (obstacles au hasard)
    escalation: bool = True           # plus le temps passe, plus c'est la guerre (objets, vitesse, effets)
    obstacles: int = 3                # petits blocs fixes dans l'arène (0 = aucun)
    speed_ramp: float = 1.8           # vitesse de base x1 au GO -> x speed_ramp à la fin du chrono
    cube_speed: float = 54.0          # px logiques / s

    # Génération
    video_count: int = 1
    seed: str = ""
    export_srt: bool = True
    output_dir: str = "videos"
    crf: int = 18
    x264_preset: str = "medium"

    # Audio
    master_volume: float = 0.9
    music_volume: float = 0.6
    music_enabled: bool = True
    paint_sound: bool = False

    # Zones de sécurité TikTok (pixels de la vidéo 1080x1920)
    safe_top: int = 130
    safe_bottom: int = 400
    safe_right: int = 140

    hooks: list = field(default_factory=lambda: list(DEFAULT_HOOKS))
    config_version: int = CONFIG_VERSION

    def item_weights(self) -> dict[str, float]:
        return {k: max(0.0, float(getattr(self, f"prob_{k}"))) for k in ITEM_KINDS}

    def item_percentages(self) -> dict[str, float]:
        w = self.item_weights()
        total = sum(w.values())
        return {k: (v / total * 100 if total > 0 else 0.0) for k, v in w.items()}

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> "Settings":
        s = cls()
        known = {f.name: f for f in fields(cls)}
        for key, value in data.items():
            if key not in known:
                continue
            default = getattr(s, key)
            try:
                if isinstance(default, bool):
                    value = bool(value)
                elif isinstance(default, int):
                    value = int(value)
                elif isinstance(default, float):
                    value = float(value)
                elif isinstance(default, str):
                    value = str(value)
                elif isinstance(default, list):
                    value = [str(v) for v in value] or list(default)
            except (TypeError, ValueError):
                continue
            setattr(s, key, value)
        return s

    def music_on(self) -> bool:
        return self.music_enabled and self.music_volume > 0


def migrate(data: dict) -> dict:
    """Met à jour un config.json d'une version précédente (les valeurs restées aux anciens
    défauts prennent les nouveaux défauts ; celles modifiées par l'utilisateur sont gardées)."""
    data = dict(data)
    if int(data.get("config_version", 1)) < 2:
        for key, old_default in (("cube_size", 7), ("brush_radius", 20)):
            if data.get(key) == old_default:
                data.pop(key)
    if int(data.get("config_version", 1)) < 4:
        for key, old_default in (("cube_size", 11), ("brush_radius", 26)):
            if data.get(key) == old_default:
                data.pop(key)
    if int(data.get("config_version", 1)) < 5:
        for key, old_default in (("cube_speed", 42.0), ("speed_ramp", 1.6), ("bullet_speed", 110.0)):
            if data.get(key) == old_default:
                data.pop(key)
    if int(data.get("config_version", 1)) < 6:
        for key, old_default in (("intro_duration", 5.0), ("outro_duration", 5.0)):
            if data.get(key) == old_default:
                data.pop(key)
    if int(data.get("config_version", 1)) < 3 and data.get("hooks") == OLD_FRENCH_HOOKS:
        data.pop("hooks")       # accroches par défaut en français -> nouvelles accroches anglaises
    data["config_version"] = CONFIG_VERSION
    return data


def load(path: Path = CONFIG_PATH) -> Settings:
    if path.exists():
        try:
            return Settings.from_dict(migrate(json.loads(path.read_text(encoding="utf-8"))))
        except (OSError, json.JSONDecodeError):
            pass
    return Settings()


def save(settings: Settings, path: Path = CONFIG_PATH) -> None:
    path.write_text(json.dumps(settings.to_dict(), indent=2, ensure_ascii=False), encoding="utf-8")
