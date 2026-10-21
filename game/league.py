"""Ligue : classement des concurrents conservé d'une vidéo à l'autre.

Chaque vidéo générée (pas l'aperçu) compte comme une « journée » : le gagnant marque une
victoire. Le classement est affiché à la fin de la vidéo (« LEAGUE DAY 12 »).
Une ligue par variante : league.json pour les couleurs, league_<variante>.json pour les autres.
"""

import json
from pathlib import Path

from . import variants
from .settings import ROOT

LEAGUE_PATH = ROOT / "league.json"


def path_for(variant: str = variants.COLORS) -> Path:
    return LEAGUE_PATH if variant == variants.COLORS else ROOT / f"league_{variant}.json"


def teams(variant: str = variants.COLORS) -> list[str]:
    return [c.name for c in variants.BY_KEY.get(variant, variants.BY_KEY[variants.COLORS]).competitors]


def empty(variant: str = variants.COLORS) -> dict:
    return {"day": 0, "wins": {team: 0 for team in teams(variant)}}


def load(path: Path | None = None, variant: str = variants.COLORS) -> dict:
    path = path or path_for(variant)
    data = empty(variant)
    if path.exists():
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
            data["day"] = max(0, int(raw.get("day", 0)))
            for team in data["wins"]:
                data["wins"][team] = max(0, int(raw.get("wins", {}).get(team, 0)))
        except (OSError, ValueError, AttributeError):
            pass
    return data


def save(data: dict, path: Path | None = None, variant: str = variants.COLORS) -> None:
    (path or path_for(variant)).write_text(json.dumps(data, indent=2), encoding="utf-8")


def reset(path: Path | None = None, variant: str = variants.COLORS) -> None:
    save(empty(variant), path, variant)


def with_result(data: dict, winner_team: str | None) -> dict:
    """Nouvelle journée : +1 jour, +1 victoire au gagnant (rien en cas d'égalité)."""
    new = {"day": data["day"] + 1, "wins": dict(data["wins"])}
    if winner_team is not None:
        new["wins"][winner_team] = new["wins"].get(winner_team, 0) + 1
    return new


def standings(data: dict) -> list[tuple[str, int]]:
    order = {team: i for i, team in enumerate(data["wins"])}
    return sorted(data["wins"].items(), key=lambda kv: (-kv[1], order.get(kv[0], 99)))
