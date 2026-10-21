"""Garde-fou anti-répétition : choisit le contenu de chaque vidéo d'un lot en évitant de
refaire ce qui vient d'être publié.

TikTok écarte de sa rémunération les contenus « répétitifs » (vidéos quasi identiques).
Chaque vidéo générée est notée dans history.json (format, mode, thème, musique, variante,
nombre de cubes, carte, durée, légende). Pour la suivante, chaque réglage laissé sur
« aléatoire » est tiré avec des poids qui s'effondrent pour les valeurs vues récemment :
jamais deux fois de suite la même, et rarement la même dans les 4-5 dernières vidéos.

Durées variées : environ 85 % des vidéos dépassent 1 minute (rémunération) avec une durée
qui change d'une vidéo à l'autre (62 à ~95 s) ; les autres sont des vidéos courtes
(30 à 50 s) avec un format simple (sprint, duel…). Jamais deux courtes de suite.
"""

from __future__ import annotations

import json
import math
import random
from dataclasses import replace
from pathlib import Path

from audio import music
from . import formats, maps, modes, themes, variants
from .settings import ROOT, Settings

HISTORY_PATH = ROOT / "history.json"
KEEP = 80                     # vidéos gardées dans l'historique
WINDOW = 6                    # vidéos récentes pénalisées
PENALTY = 0.12                # poids multiplié par PENALTY ** (récence) pour une valeur déjà vue
LONG_RANGE = (62.0, 96.0, 70.0)   # (min, max, le plus fréquent) des vidéos longues, en secondes
SHORT_RANGE = (30.0, 50.0)
# Bouton « Tout aléatoire » : toute la partie et toute l'apparence tirées pour chaque vidéo
ALL_RANDOM = {"format": formats.RANDOM, "mode": modes.RANDOM, "players": 0, "variant": variants.RANDOM,
              "theme": themes.RANDOM, "map": "random", "music_style": music.RANDOM}


def load_history(path: Path | None = None) -> dict:
    path = path or HISTORY_PATH
    data = {"count": 0, "videos": []}
    if path.exists():
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
            data["count"] = max(0, int(raw.get("count", 0)))
            data["videos"] = [v for v in raw.get("videos", []) if isinstance(v, dict)][-KEEP:]
        except (OSError, ValueError, AttributeError):
            pass
    return data


def save_history(data: dict, path: Path | None = None) -> None:
    (path or HISTORY_PATH).write_text(json.dumps(data, indent=1, ensure_ascii=False), encoding="utf-8")


def record(data: dict, plan: dict) -> dict:
    """Ajoute une vidéo réussie à l'historique."""
    return {"count": data["count"] + 1, "videos": (data["videos"] + [plan])[-KEEP:]}


def weighted_pick(rng: random.Random, options: dict, recent: list, avoid_last: bool = True):
    """Tire une clé de `options` ({valeur: poids}) en pénalisant les valeurs de `recent`
    (de la plus ancienne à la plus récente). La dernière valeur est exclue s'il y a le choix."""
    window = recent[-WINDOW:]
    weights = {}
    for key, w in options.items():
        if w <= 0:
            continue
        hits = sum((i + 1) / len(window) for i, v in enumerate(window) if v == key)
        weights[key] = w * PENALTY ** hits
    if avoid_last and window and len(weights) > 1:
        weights.pop(window[-1], None)
    if not weights:
        return next(iter(options))
    keys = list(weights)
    return rng.choices(keys, weights=[weights[k] for k in keys])[0]


def is_short_slot(count: int, long_share: float) -> bool:
    """Vidéo courte ? Réparties régulièrement : la part des courtes reste exactement 1 - long_share
    (avec 85 % : une courte toutes les 6-7 vidéos, jamais deux de suite)."""
    short = max(0.0, min(0.5, 1.0 - long_share))
    return math.floor(short * (count + 1)) > math.floor(short * count)


def plan_video(settings: Settings, history: dict, rng: random.Random, allow_short: bool = True) -> dict:
    """Choix concrets pour la prochaine vidéo (seulement pour les réglages sur « aléatoire »)."""
    videos = history["videos"]

    def recent(key):
        return [v.get(key) for v in videos]

    plan = {}
    short = settings.duration_mix and allow_short and is_short_slot(history["count"], settings.long_share)
    plan["length"] = "short" if short else "long"
    if not settings.variety:
        # sans garde-fou : les réglages « aléatoire » sont tirés par la partie elle-même (selon la seed)
        if short and settings.format == formats.RANDOM:
            plan["format"] = weighted_pick(rng, formats.SHORT_WEIGHTS, [], avoid_last=False)
        if settings.duration_mix:
            plan["target_duration"] = round(rng.uniform(*SHORT_RANGE) if short else rng.triangular(*LONG_RANGE), 1)
        return plan

    # format
    if settings.format == formats.RANDOM:
        pool = formats.SHORT_WEIGHTS if short else formats.LONG_WEIGHTS
        plan["format"] = weighted_pick(rng, pool, recent("format"))
    else:
        plan["format"] = settings.format
    fmt = formats.BY_KEY.get(plan["format"], formats.BY_KEY[formats.CLASSIC])

    # mode (seulement si le format l'utilise)
    if fmt.use_mode and settings.mode == modes.RANDOM:
        plan["mode"] = weighted_pick(rng, {m.key: 1.0 for m in modes.MODES} | {modes.CLASSIC: 1.5},
                                     recent("mode"))
    elif fmt.use_mode:
        plan["mode"] = settings.mode

    if settings.theme == themes.RANDOM:
        plan["theme"] = weighted_pick(rng, {t.key: 1.0 for t in themes.THEMES}, recent("theme"))
    if settings.variant == variants.RANDOM:
        plan["variant"] = weighted_pick(rng, {v.key: 1.0 for v in variants.VARIANTS}, recent("variant"))
    if settings.map == "random":
        plan["map"] = weighted_pick(rng, {name: 1.0 for name in maps.MAP_NAMES}, recent("map"))
    if settings.players == 0 and fmt.players is None:
        plan["players"] = weighted_pick(rng, {2: 1.0, 3: 1.2, 4: 1.0} if not short else {2: 1.5, 3: 1.0},
                                        recent("players"))
    if settings.music_style in (music.AUTO, music.RANDOM):
        mode = modes.BY_KEY.get(plan.get("mode", ""))
        options = {s.key: 1.0 for s in music.STYLES}
        if settings.music_style == music.AUTO:
            for preferred in (music.MODE_STYLES.get(mode.key) if mode else None, music.FORMAT_STYLES.get(fmt.key)):
                if preferred:
                    options[preferred] += 2.5
        plan["music_style"] = weighted_pick(rng, options, recent("music_style"))

    if settings.duration_mix:
        if short:
            plan["target_duration"] = round(rng.uniform(*SHORT_RANGE), 1)
        else:
            lo, hi, mode_ = LONG_RANGE
            plan["target_duration"] = round(rng.triangular(lo, hi, mode_), 1)
    return plan


def apply(settings: Settings, plan: dict) -> Settings:
    """Réglages de la vidéo : ceux de l'utilisateur, avec les choix du plan."""
    keys = ("format", "mode", "theme", "variant", "map", "players", "music_style", "target_duration")
    return replace(settings, **{k: plan[k] for k in keys if k in plan})


def describe(plan: dict) -> str:
    """Résumé lisible (journal de l'interface)."""
    parts = [plan.get("format", ""), plan.get("mode", ""), plan.get("theme", ""), plan.get("variant", ""),
             plan.get("music_style", "")]
    text = " · ".join(p for p in parts if p and p != "classic")
    if plan.get("target_duration"):
        text += f" · ~{plan['target_duration']:.0f} s"
    return text
