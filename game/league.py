"""Ligue : classement des couleurs conservé d'une vidéo à l'autre (fichier league.json).

Chaque vidéo générée (pas l'aperçu) compte comme une « journée » : le gagnant marque une
victoire. Le classement est affiché à la fin de la vidéo (« LEAGUE DAY 12 »).
"""

import json
from pathlib import Path

from engine8bit import palette

from .settings import ROOT

LEAGUE_PATH = ROOT / "league.json"
TEAMS = palette.PRIMARY_TEAMS + [palette.FOURTH_TEAM]


def empty() -> dict:
    return {"day": 0, "wins": {team: 0 for team in TEAMS}}


def load(path: Path = LEAGUE_PATH) -> dict:
    data = empty()
    if path.exists():
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
            data["day"] = max(0, int(raw.get("day", 0)))
            for team in TEAMS:
                data["wins"][team] = max(0, int(raw.get("wins", {}).get(team, 0)))
        except (OSError, ValueError, AttributeError):
            pass
    return data


def save(data: dict, path: Path = LEAGUE_PATH) -> None:
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")


def reset(path: Path = LEAGUE_PATH) -> None:
    save(empty(), path)


def with_result(data: dict, winner_team: str | None) -> dict:
    """Nouvelle journée : +1 jour, +1 victoire au gagnant (rien en cas d'égalité)."""
    new = {"day": data["day"] + 1, "wins": dict(data["wins"])}
    if winner_team is not None:
        new["wins"][winner_team] = new["wins"].get(winner_team, 0) + 1
    return new


def standings(data: dict) -> list[tuple[str, int]]:
    order = {team: i for i, team in enumerate(TEAMS)}
    return sorted(data["wins"].items(), key=lambda kv: (-kv[1], order.get(kv[0], 99)))
