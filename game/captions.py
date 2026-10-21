"""Légendes TikTok écrites d'après la partie : chaque vidéo a une description différente.

Après la simulation, on analyse ce qui s'est passé (écart final, remontée, K.O., killcams,
objet le plus ramassé, format, thème, variante, ligue, coupe…) et on compose :
  1. une accroche tirée du fait le plus marquant, SANS dévoiler le gagnant (sinon personne
     ne regarde jusqu'au bout) ;
  2. une question / un appel à commenter, qui change aussi ;
  3. 4 à 5 hashtags : une partie fixe (tes hashtags), une partie selon le contenu.
Le garde-fou (history.json) évite de réutiliser les mêmes phrases d'une vidéo à l'autre.
"""

from __future__ import annotations

import random

# Accroches : (identifiant, condition, modèles). {n}, {kos}, {margin}… sont remplacés.
HOOKS = [
    ("cup", lambda f: bool(f["cup"]), [
        "PaintCup {cup}: {names}. Who goes through? 🏆",
        "PaintCup {cup} — only the top 2 survive this round 🏆",
        "{cup} of the PaintCup! Pick your favourite 👇",
    ]),
    ("photo", lambda f: f["margin"] is not None and f["margin"] < 2.0, [
        "Decided by {margin} at the buzzer 😳",
        "This one came down to {margin}… watch till the end 👀",
        "{margin} between first and second. Unreal.",
    ]),
    ("comeback", lambda f: f["comeback"], [
        "Don't leave before the last 10 seconds… 👀",
        "Nobody saw this comeback coming 😱",
        "Last place at half-time. Then THIS happened.",
    ]),
    ("royale", lambda f: f["format"] == "royale", [
        "{n} cubes enter. Only one survives 🏆",
        "Battle royale: {n} cubes, one storm, one winner ⚡",
        "The storm is closing in… who's your survivor? 🌪️",
    ]),
    ("combat", lambda f: f["format"] in ("combat", "duel"), [
        "No paint. Only items. Who's left standing? 💥",
        "Pure fight: {kos} K.O. in this one 💀",
        "Every hit counts in fight mode 🥊",
    ]),
    ("duo", lambda f: f["format"] == "duo", [
        "2 vs 2: teamwork or chaos? 🤝",
        "Two teams, four cubes, one winner 👇",
        "Who has the better duo? 🔥",
    ]),
    ("kos", lambda f: f["kos"] >= 2, [
        "{kos} K.O.s in one round 💀",
        "This match got brutal: {kos} knockouts 😵",
        "Count the K.O.s… we got {kos} 💥",
    ]),
    ("closecall", lambda f: f["close_calls"] > 0, [
        "That slow-mo moment… 😮‍💨",
        "Wait for the slow motion 👀",
        "One hit from elimination… 😬",
    ]),
    ("short", lambda f: f["length"] == "short", [
        "Quick one: {seconds} seconds of chaos ⚡",
        "Blink and you miss it ⚡",
        "Speed round! Pick fast 👇",
    ]),
    ("item", lambda f: f["top_item"] is not None, [
        "The {item} changed everything 👀",
        "Who used the {item} best? 🤔",
        "{item} chaos in this round 😂",
    ]),
    ("theme", lambda f: f["theme"] != "classic", [
        "Paint war on the {theme_name} map 🎨",
        "{theme_name} arena, {n} cubes, one winner",
        "New arena: {theme_name} 🔥",
    ]),
    ("league", lambda f: f["league_day"] > 0, [
        "League day {day}: will the leader hold on? 📊",
        "Day {day} of the cube league 🏆",
    ]),
    ("generic", lambda f: True, [
        "Which cube will win the PaintRace? 🎨",
        "Pick your cube before it starts 👇",
        "Oddly satisfying paint battle 🎨",
        "Who's your pick? Comment before the end 👇",
        "Place your bets 🎲",
    ]),
]

QUESTIONS = {
    "colors": ["Comment your color 👇", "Which color are you? 👇", "Team red, blue, yellow or green? 👇"],
    "countries": ["Comment your country 👇", "Which flag are you rooting for? 🌍", "Drop your country below 👇"],
    "fruits": ["Which fruit are you? 🍉", "Comment your fruit 👇", "Best fruit wins? 👇"],
    "animals": ["Which animal are you? 🐯", "Comment your animal 👇", "Pick your fighter 👇"],
    "planets": ["Which planet are you? 🪐", "Comment your planet 👇", "Pick your planet 👇"],
    "": ["Who's your pick? 👇", "Did you guess right? 👇", "Follow for the next round! 🔁"],
}

HASHTAGS = {
    "broad": ["fyp", "foryou", "viral", "foryoupage"],
    "category": ["satisfying", "oddlysatisfying", "pixelart", "8bit", "simulation"],
    "format": {"classic": ["paintrace", "whowillwin"], "duo": ["2v2", "teamwork"], "combat": ["fight", "survival"],
               "royale": ["battleroyale", "lastonestanding"], "sprint": ["speedrun", "paintrace"],
               "duel": ["1v1", "duel"]},
    "variant": {"colors": ["colors"], "countries": ["countries", "flags"], "fruits": ["fruits"],
                "animals": ["animals"], "planets": ["planets", "space"]},
}
ITEM_WORDS = {"gun": "gun", "brush": "giant brush", "potion": "potion", "hourglass": "hourglass", "bomb": "bomb",
              "roller": "roller", "bucket": "rainbow bucket", "ice": "ice", "magnet": "magnet", "boots": "boots",
              "heart": "heart"}


def analyse(b, plan: dict | None = None) -> dict:
    """Faits marquants d'une partie terminée (rien qui dévoile le gagnant)."""
    plan = plan or {}
    r = b.result
    margin = None
    if not b.survival and len(r.ranking) >= 2:
        margin = r.ranking[0].pct - r.ranking[1].pct
    comeback = False
    if b.timeline and r.winner is not None and len(b.sides) >= 2:
        mid = b.timeline[len(b.timeline) // 2]
        side = b.side_of[r.winner]
        comeback = not b.survival and mid[side] == min(mid) and b.lead_changes >= 1
    top_item = max(b.pickup_log, key=lambda k: (b.pickup_log[k], k)) if b.pickup_log else None
    survivors = {c.idx for c in b.cubes if not c.dead}
    names = [b.cubes[s[0]].team for s in b.sides]
    return {
        "format": b.fmt.key, "theme": b.theme.key, "theme_name": b.theme.name.title(),
        "variant": b.variant.key, "n": len(b.cubes), "kos": len(b.ko_log), "margin": margin,
        "comeback": comeback, "close_calls": sum(1 for v in b.killcam_victims if v in survivors),
        "top_item": ITEM_WORDS.get(top_item) if top_item else None,
        "length": plan.get("length", "long"), "seconds": round(b.total_frames / 60),
        "league_day": (b.league or {}).get("day", 0), "cup": b.settings.cup_label.title() if b.settings.cup_label else "",
        "names": " vs ".join(n.title() for n in names),
    }


def make(b, user_hashtags: list, recent_ids: list, rng: random.Random, plan: dict | None = None) -> tuple[str, str]:
    """(légende complète avec hashtags, identifiant de l'accroche utilisée)."""
    facts = analyse(b, plan)
    candidates = [(hid, texts) for hid, cond, texts in HOOKS if cond(facts)]
    # les faits les plus forts d'abord, mais une accroche récente laisse sa place
    # (la coupe garde toujours son accroche : c'est une série, on doit la reconnaître)
    fresh = [(hid, texts) for hid, texts in candidates if hid == "cup" or hid not in recent_ids[-3:]] or candidates
    strongest = fresh[:3]
    hid, texts = rng.choice(strongest[:2] if len(strongest) > 1 and rng.random() < 0.8 else strongest)
    text = rng.choice(texts)
    margin = facts["margin"] or 0.0
    hook = text.format(n=facts["n"], kos=facts["kos"], margin=f"{margin:.1f}%", item=facts["top_item"] or "item",
                       theme_name=facts["theme_name"], day=facts["league_day"], cup=facts["cup"],
                       names=facts["names"], seconds=facts["seconds"])
    question = rng.choice(QUESTIONS.get(facts["variant"]) or QUESTIONS[""])
    if b.fmt.team_size > 1 or hid == "cup":
        question = rng.choice(QUESTIONS[""])
    tags = _hashtags(facts, user_hashtags, rng)
    caption = f"{hook} {question}"
    return f"{caption} {' '.join('#' + t for t in tags)}".strip(), hid


def _hashtags(facts: dict, user_hashtags: list, rng: random.Random) -> list[str]:
    user = [h.strip().lstrip("#").replace(" ", "") for h in user_hashtags if h.strip()]
    tags = []
    # 1-2 hashtags à toi (ta « signature »), puis le contenu de la vidéo
    for h in user[:2] if user else ["paintrace"]:
        tags.append(h)
    tags.append(rng.choice(HASHTAGS["format"].get(facts["format"], ["paintrace"])))
    tags.append(rng.choice(HASHTAGS["variant"].get(facts["variant"], ["colors"])))
    tags.append(rng.choice(HASHTAGS["category"]))
    tags.append(rng.choice(HASHTAGS["broad"]))
    out = []
    for t in tags:
        if t.lower() not in [o.lower() for o in out]:
            out.append(t)
    return out[:5]


def fixed(settings) -> str:
    """Légende fixe (option « légende automatique » désactivée)."""
    return settings.caption_text()


def title_part(caption: str, limit: int = 60) -> str:
    """Partie de la légende utilisable dans un nom de fichier (sans hashtags ni emojis)."""
    words = [w for w in caption.split() if not w.startswith("#")]
    text = " ".join("".join(ch for ch in w if ord(ch) < 0x2000) for w in words)
    text = " ".join(text.split())
    if len(text) > limit:                         # Windows : chemins limités à 260 caractères
        text = text[:limit].rsplit(" ", 1)[0]
    return text.strip()

