"""Réglages de l'application, sauvegardés dans config.json à la racine du projet."""

import json
from dataclasses import asdict, dataclass, field, fields
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CONFIG_PATH = ROOT / "config.json"

ITEM_KINDS = ["gun", "brush", "potion", "hourglass"]
ITEM_LABELS = {"gun": "Fusil", "brush": "Gros pinceau", "potion": "Potion", "hourglass": "Sablier"}

DEFAULT_HOOKS = [
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
    item_interval: float = 5.0        # secondes entre deux apparitions
    max_items: int = 3                # objets présents simultanément
    max_hourglasses: int = 3          # sabliers par partie
    hourglass_bonus: float = 3.0      # secondes ajoutées par sablier

    # Effets des objets
    aim_duration: float = 0.3
    bullet_speed: float = 110.0       # px logiques / s
    stun_duration: float = 5.0
    brush_radius: int = 20
    slow_duration: float = 3.0
    slow_factor: float = 0.45
    potion_duration: float = 5.0
    potion_scale: int = 2

    # Partie
    intro_duration: float = 5.0
    battle_duration: float = 50.0
    outro_duration: float = 5.0
    cube_size: int = 7
    cube_speed: float = 42.0          # px logiques / s

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


def load(path: Path = CONFIG_PATH) -> Settings:
    if path.exists():
        try:
            return Settings.from_dict(json.loads(path.read_text(encoding="utf-8")))
        except (OSError, json.JSONDecodeError):
            pass
    return Settings()


def save(settings: Settings, path: Path = CONFIG_PATH) -> None:
    path.write_text(json.dumps(settings.to_dict(), indent=2, ensure_ascii=False), encoding="utf-8")
