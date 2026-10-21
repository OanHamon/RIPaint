"""PaintCup : un tournoi de 8 à 16 cubes joué sur plusieurs vidéos (une vidéo = un match).

Chaque tour répartit les cubes encore en lice en matchs de 3 ou 4 ; les 2 premiers de chaque
match passent au tour suivant, les autres sont éliminés. Quand il en reste 4 ou moins : la
finale, dont le gagnant est sacré champion. Exemple à 16 : 4 matchs (huitièmes) -> 2 demi-
finales -> finale = 7 épisodes. Un classement général est tenu (tour atteint, points :
3 pour le 1er d'un match, 2 pour le 2e, 1 pour le 3e).

L'état est enregistré dans cup.json ; quand la coupe est finie, la génération suivante en
démarre une nouvelle (PaintCup #2…).
"""

from __future__ import annotations

import json
import random
from pathlib import Path

from . import variants
from .settings import ROOT

CUP_PATH = ROOT / "cup.json"
MIN_SIZE, MAX_SIZE = 8, 16
POINTS = [3, 2, 1, 0]


def split(names: list[str]) -> list[list[str]]:
    """Matchs équilibrés de 3 ou 4 cubes (4 ou moins : un seul match, la finale)."""
    n = len(names)
    if n <= 4:
        return [list(names)]
    count = -(-n // 4)
    sizes = [n // count + (1 if k < n % count else 0) for k in range(count)]
    out, i = [], 0
    for size in sizes:
        out.append(names[i:i + size])
        i += size
    return out


def round_name(n_players: int, n_matches: int) -> str:
    if n_matches == 1:
        return "FINAL"
    if n_matches == 2:
        return "SEMI-FINAL"
    return f"ROUND OF {n_players}"


def new_cup(variant_key: str, size: int, seed: int, number: int = 1) -> dict:
    variant = variants.BY_KEY.get(variant_key, variants.BY_KEY[variants.COLORS])
    pool = [c.name for c in variant.competitors]
    size = max(2, min(MAX_SIZE, size, len(pool)))
    rng = random.Random(seed)
    players = rng.sample(pool, size)
    cup = {"number": number, "variant": variant.key, "players": players, "rounds": [], "champion": None,
           "points": {p: 0 for p in players}, "reached": {p: 0 for p in players}, "episodes": 0}
    _add_round(cup, players)
    return cup


def _add_round(cup: dict, players: list[str]) -> None:
    matches = split(players)
    cup["rounds"].append({"name": round_name(len(players), len(matches)),
                          "matches": [{"lineup": m, "ranking": None} for m in matches]})


def next_match(cup: dict) -> tuple[int, int] | None:
    """(tour, match) du prochain match à jouer, None si la coupe est finie."""
    if cup.get("champion"):
        return None
    for ri, rnd in enumerate(cup["rounds"]):
        for mi, match in enumerate(rnd["matches"]):
            if match["ranking"] is None:
                return ri, mi
    return None


def label(cup: dict, ri: int, mi: int) -> str:
    """« SEMI-FINAL 1/2 », « FINAL », « ROUND OF 16 3/4 »."""
    rnd = cup["rounds"][ri]
    n = len(rnd["matches"])
    return rnd["name"] if n == 1 else f"{rnd['name']} {mi + 1}/{n}"


def record(cup: dict, ri: int, mi: int, ranking: list[str]) -> dict:
    """Enregistre le classement d'un match ; crée le tour suivant quand tous sont joués.
    Renvoie {"qualified": [...], "eliminated": [...], "champion": nom|None, "next": libellé}."""
    rnd = cup["rounds"][ri]
    match = rnd["matches"][mi]
    match["ranking"] = list(ranking)
    cup["episodes"] = cup.get("episodes", 0) + 1
    for k, name in enumerate(ranking):
        cup["points"][name] = cup["points"].get(name, 0) + POINTS[min(k, len(POINTS) - 1)]
        cup["reached"][name] = max(cup["reached"].get(name, 0), ri + 1)
    if rnd["name"] == "FINAL":
        cup["champion"] = ranking[0]
        cup["reached"][ranking[0]] = ri + 2
        return {"qualified": [], "eliminated": ranking[1:], "champion": ranking[0], "next": "",
                "podium": ranking[:3]}
    qualified, eliminated = ranking[:2], ranking[2:]
    if all(m["ranking"] is not None for m in rnd["matches"]):
        through = [n for m in rnd["matches"] for n in m["ranking"][:2]]
        random.Random(len(through) * 97 + ri).shuffle(through)       # nouveaux tirages au sort
        _add_round(cup, through)
    nxt = next_match(cup)
    return {"qualified": qualified, "eliminated": eliminated, "champion": None,
            "next": ("NEXT: " + label(cup, *nxt)) if nxt else ""}


def standings(cup: dict) -> list[tuple[str, int, int]]:
    """Classement général : (nom, tour atteint, points), du meilleur au moins bon."""
    order = {p: i for i, p in enumerate(cup["players"])}
    rows = [(p, cup["reached"].get(p, 0), cup["points"].get(p, 0)) for p in cup["players"]]
    # finale jouée : ses participants sont classés selon leur place en finale
    final = cup["rounds"][-1]["matches"][0] if cup["rounds"][-1]["name"] == "FINAL" else None
    podium = {n: k for k, n in enumerate(final["ranking"])} if final and final["ranking"] else {}
    return sorted(rows, key=lambda r: (podium.get(r[0], 99), -r[1], -r[2], order[r[0]]))


def status(cup: dict, name: str) -> tuple[str, str]:
    """Où en est un concurrent : (« champion » | « finalist » | « through » | « alive » | « out », tour)."""
    for rnd in reversed(cup["rounds"]):
        for match in rnd["matches"]:
            if name not in match["lineup"]:
                continue
            ranking = match["ranking"]
            if ranking is None:
                return "alive", rnd["name"]
            place = ranking.index(name)
            if rnd["name"] == "FINAL":
                return ("champion", rnd["name"]) if place == 0 else ("finalist", f"{place + 1}e en finale")
            return ("through", rnd["name"]) if place < 2 else ("out", rnd["name"])
    return "alive", ""


def total_episodes(n: int) -> int:
    players, total = n, 0
    while True:
        matches = split(list(range(players)))
        total += len(matches)
        if len(matches) == 1:
            return total
        players = 2 * len(matches)


def load(path: Path | None = None) -> dict | None:
    path = path or CUP_PATH
    if not path.exists():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) and data.get("rounds") else None
    except (OSError, ValueError):
        return None


def save(cup: dict, path: Path | None = None) -> None:
    (path or CUP_PATH).write_text(json.dumps(cup, indent=1, ensure_ascii=False), encoding="utf-8")


def reset(path: Path | None = None) -> None:
    try:
        (path or CUP_PATH).unlink()
    except OSError:
        pass


def summary(cup: dict | None) -> str:
    """Une ligne pour l'interface."""
    if cup is None:
        return "aucune coupe en cours (la prochaine génération en démarre une)"
    if cup.get("champion"):
        return f"PaintCup #{cup['number']} terminée : champion {cup['champion']}"
    nxt = next_match(cup)
    done = cup.get("episodes", 0)
    total = total_episodes(len(cup["players"]))
    current = cup["rounds"][nxt[0]]["matches"]
    left = sum(len(m["lineup"]) if m["ranking"] is None else 2 for m in current)
    return (f"PaintCup #{cup['number']} · {len(cup['players'])} cubes · épisode {done + 1}/{total} : "
            f"{label(cup, *nxt)} · {left} en lice")
