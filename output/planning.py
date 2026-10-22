"""Publication : nom de fichier = description TikTok, catalogue des vidéos, planning de la semaine.

TikTok Studio reprend le NOM DU FICHIER comme description à l'import : on nomme donc chaque
vidéo exactement comme sa légende (accroche, question, emojis, #hashtags), sans date ni seed.
Windows interdit quelques caractères (? : * " < > | / \\) : ils sont remplacés par des
caractères identiques à l'œil (« ？ », « ： »…), que TikTok affiche normalement.
La seed, la date et le contenu de chaque vidéo sont notés dans le catalogue (catalogue.csv)
et dans les métadonnées du MP4 : on peut toujours rejouer une partie.
"""

from __future__ import annotations

import csv
import html
import json
import subprocess
from datetime import date, datetime, timedelta
from pathlib import Path

CATALOGUE_NAME = "catalogue.csv"
LOOKALIKE = {"?": "？", ":": "：", "/": "∕", "\\": "⧵", "*": "＊", '"': "＂", "<": "‹", ">": "›", "|": "｜"}
NAME_LIMIT = 150                   # caractères : reste sous la limite de 260 des chemins Windows
EXTRA_TAGS = ["paintrace", "pixelart", "8bit", "satisfying", "cubes", "minigame", "colors", "gaming"]
DAYS_FR = ["Lundi", "Mardi", "Mercredi", "Jeudi", "Vendredi", "Samedi", "Dimanche"]
COLUMNS = ["publication", "fichier", "dossier", "légende", "format", "mode", "thème", "concurrents", "carte",
           "cubes", "musique", "durée (s)", "longueur", "résultat", "ligue (jour)", "coupe", "seed", "généré le"]


# ---- Nom de fichier = description TikTok -----------------------------------------------------

def tiktok_filename(caption: str, limit: int = NAME_LIMIT) -> str:
    """Légende -> nom de fichier (sans extension) : caractères interdits remplacés par des sosies,
    hashtags retirés en partant de la fin si c'est trop long (jamais de mot coupé)."""
    text = "".join(LOOKALIKE.get(ch, ch) for ch in caption if ord(ch) >= 32)
    words = text.split()
    while len(" ".join(words)) > limit and sum(w.startswith("#") for w in words) > 1:
        last = max(i for i, w in enumerate(words) if w.startswith("#"))
        words.pop(last)
    text = " ".join(words)
    if len(text) > limit:
        text = text[:limit].rsplit(" ", 1)[0]
    return text.rstrip(" .")


def unique_stem(folder: Path, stem: str) -> str:
    """Nom libre dans le dossier : si la légende existe déjà, on ajoute un hashtag de plus
    (la description reste naturelle), sinon un numéro."""
    def free(s):
        return not any((folder / f"{s}{ext}").exists() for ext in (".mp4", ".txt", ".srt"))
    if free(stem):
        return stem
    present = {w.lstrip("#").lower() for w in stem.split() if w.startswith("#")}
    for tag in EXTRA_TAGS:
        if tag not in present:
            candidate = f"{stem} #{tag}"
            if len(candidate) <= NAME_LIMIT + 12 and free(candidate):
                return candidate
    k = 2
    while not free(f"{stem} ({k})"):
        k += 1
    return f"{stem} ({k})"


# ---- Catalogue de toutes les vidéos ------------------------------------------------------------

def catalogue_row(result, scheduled: datetime | None = None) -> dict:
    m = result.meta or {}
    return {
        "publication": scheduled.strftime("%Y-%m-%d %H:%M") if scheduled else "",
        "fichier": result.path.name, "dossier": result.path.parent.name, "légende": result.caption,
        "format": m.get("format_name", ""), "mode": m.get("mode_name", ""), "thème": m.get("theme_name", ""),
        "concurrents": m.get("variant_name", ""), "carte": m.get("map", ""), "cubes": result.n_cubes,
        "musique": m.get("music", ""), "durée (s)": round(result.duration), "longueur": m.get("length", ""),
        "résultat": result.summary, "ligue (jour)": m.get("league_day", ""), "coupe": m.get("cup", ""),
        "seed": result.seed, "généré le": datetime.now().strftime("%Y-%m-%d %H:%M"),
    }


def append_catalogue(videos_dir: Path, row: dict) -> Path:
    """Ajoute une ligne à videos/catalogue.csv (lisible dans Excel, emojis compris)."""
    path = videos_dir / CATALOGUE_NAME
    new = not path.exists()
    with open(path, "a", newline="", encoding="utf-8-sig" if new else "utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=COLUMNS, delimiter=";")
        if new:
            writer.writeheader()
        writer.writerow({k: row.get(k, "") for k in COLUMNS})
    return path


# ---- Semaine ------------------------------------------------------------------------------------

def parse_times(times) -> list[tuple[int, int]]:
    """« 12:30, 19:00 » ou ["12:30", "19h"] -> [(12, 30), (19, 0)] (triées, sans doublon)."""
    if isinstance(times, str):
        times = times.replace(";", ",").split(",")
    out = set()
    for t in times:
        t = str(t).strip().lower().replace("h", ":")
        if not t:
            continue
        hh, _, mm = t.partition(":")
        try:
            h, m = int(hh), int(mm or 0)
        except ValueError:
            continue
        if 0 <= h < 24 and 0 <= m < 60:
            out.add((h, m))
    return sorted(out) or [(12, 30), (19, 0)]


def parse_start(text: str | None, today: date | None = None) -> date:
    """Premier jour : « 2026-10-26 », « 26/10/2026 », ou vide = demain."""
    today = today or date.today()
    text = (text or "").strip()
    for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%d/%m"):
        try:
            d = datetime.strptime(text, fmt).date()
            return d.replace(year=today.year) if fmt == "%d/%m" else d
        except ValueError:
            continue
    return today + timedelta(days=1)


def week_slots(start: date, days: int, times) -> list[datetime]:
    """Créneaux de publication : chaque jour, aux heures données."""
    hours = parse_times(times)
    return [datetime(d.year, d.month, d.day, h, m)
            for d in (start + timedelta(days=i) for i in range(max(1, days))) for h, m in hours]


def week_folder(videos_dir: Path, start: date) -> Path:
    folder = videos_dir / f"Semaine du {start:%Y-%m-%d}"
    folder.mkdir(parents=True, exist_ok=True)
    return folder


def make_cover(video: Path, out: Path, ffmpeg: str, no_window: int = 0) -> bool:
    """Image de couverture (l'ouverture « WHO WINS? »), en petit pour le planning."""
    out.parent.mkdir(parents=True, exist_ok=True)
    proc = subprocess.run([ffmpeg, "-hide_banner", "-loglevel", "error", "-y", "-ss", "0.3", "-i", str(video),
                           "-frames:v", "1", "-vf", "scale=270:480:flags=neighbor", str(out)],
                          capture_output=True, creationflags=no_window)
    return proc.returncode == 0 and out.exists()


def write_planning(folder: Path, rows: list[dict]) -> Path:
    """planning.csv (tableur) + planning.html (à ouvrir dans le navigateur : couverture,
    jour, heure, fichier, bouton « copier la légende », case « programmée »)."""
    with open(folder / "planning.csv", "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=COLUMNS, delimiter=";")
        writer.writeheader()
        for row in rows:
            writer.writerow({k: row.get(k, "") for k in COLUMNS})
    page = folder / "planning.html"
    page.write_text(_planning_html(folder, rows), encoding="utf-8")
    return page


def _planning_html(folder: Path, rows: list[dict]) -> str:
    e = html.escape
    cards = []
    last_day = None
    for i, r in enumerate(rows):
        when = datetime.strptime(r["publication"], "%Y-%m-%d %H:%M") if r.get("publication") else None
        day = when.date() if when else None
        if day != last_day:
            label = f"{DAYS_FR[day.weekday()]} {day:%d/%m}" if day else "Sans date"
            cards.append(f'<h2>{e(label)}</h2>')
            last_day = day
        cover = r.get("_cover", "")
        tags = " · ".join(x for x in (r.get("format"), r.get("mode"), r.get("thème"), r.get("concurrents"),
                                      r.get("carte"), f'{r.get("cubes")} cubes', r.get("musique"),
                                      f'{r.get("durée (s)")} s') if x and x != " cubes")
        cards.append(f'''
<div class="card" data-id="{e(r["fichier"])}">
  <img src="{e(cover)}" alt="" loading="lazy">
  <div class="body">
    <div class="top"><span class="time">{e(when.strftime("%H:%M") if when else "")}</span>
      <label class="done"><input type="checkbox"> programmée</label></div>
    <p class="caption" id="c{i}">{e(r["légende"])}</p>
    <div class="actions"><button onclick="copyCap({i}, this)">Copier la légende</button>
      <a href="{e(r["fichier"])}">Ouvrir la vidéo</a></div>
    <p class="file">{e(r["fichier"])}</p>
    <p class="meta">{e(tags)}</p>
    <p class="meta faint">seed {e(str(r.get("seed", "")))} · {e(r.get("résultat", ""))}</p>
  </div>
</div>''')
    first = rows[0].get("publication", "") if rows else ""
    title = f"Planning TikTok — {folder.name}"
    return f'''<!doctype html>
<html lang="fr"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>{e(title)}</title>
<style>
:root {{ --bg:#10101c; --card:#1b1b2b; --line:#2c2c44; --text:#f2f2f6; --muted:#9a9ab0; --accent:#f8b800; --ok:#58d854; }}
* {{ box-sizing:border-box; }}
body {{ margin:0; background:var(--bg); color:var(--text); font:15px/1.45 "Segoe UI",system-ui,sans-serif; }}
main {{ max-width:980px; margin:0 auto; padding:24px 16px 60px; }}
h1 {{ font-size:22px; margin:0 0 6px; }} h2 {{ font-size:16px; color:var(--accent); margin:28px 0 10px; }}
.intro {{ color:var(--muted); margin:0 0 8px; }}
.card {{ display:flex; gap:16px; background:var(--card); border:1px solid var(--line); border-radius:10px;
        padding:12px; margin-bottom:12px; }}
.card.isdone {{ opacity:.45; }}
.card img {{ width:108px; height:192px; object-fit:cover; border-radius:6px; image-rendering:pixelated; flex:none;
            background:#000; }}
.body {{ flex:1; min-width:0; }}
.top {{ display:flex; justify-content:space-between; align-items:center; }}
.time {{ font-size:20px; font-weight:700; color:var(--accent); }}
.caption {{ margin:6px 0 10px; font-size:16px; overflow-wrap:anywhere; }}
.actions {{ display:flex; gap:10px; flex-wrap:wrap; align-items:center; }}
button {{ background:var(--accent); color:#10101c; border:0; border-radius:6px; padding:7px 12px; font-weight:700;
         cursor:pointer; }}
button.copied {{ background:var(--ok); }}
a {{ color:var(--text); }}
.file, .meta {{ color:var(--muted); font-size:13px; margin:6px 0 0; overflow-wrap:anywhere; }}
.faint {{ opacity:.7; }}
.done {{ color:var(--muted); font-size:14px; cursor:pointer; }}
@media (max-width:560px) {{ .card {{ flex-direction:column; }} .card img {{ width:100%; height:auto; aspect-ratio:9/16; }} }}
</style></head><body><main>
<h1>{e(title)}</h1>
<p class="intro">{len(rows)} vidéo(s), à partir du {e(first)}. Dans TikTok Studio (sur ordinateur) : importe la vidéo,
la description est déjà remplie avec le nom du fichier ; sinon, colle-la avec « Copier la légende ».
Choisis « Programmer » et la date/heure indiquées (jusqu'à 10 jours à l'avance).</p>
{"".join(cards)}
</main>
<script>
function copyCap(i, btn) {{
  const text = document.getElementById("c" + i).textContent;
  const done = () => {{ btn.textContent = "Copiée ✓"; btn.classList.add("copied");
                        setTimeout(() => {{ btn.textContent = "Copier la légende"; btn.classList.remove("copied"); }}, 1500); }};
  if (navigator.clipboard) navigator.clipboard.writeText(text).then(done, done); else done();
}}
const KEY = "planning:" + {json.dumps(folder.name)};
let state = {{}};
try {{ state = JSON.parse(localStorage.getItem(KEY) || "{{}}"); }} catch (e) {{}}
document.querySelectorAll(".card").forEach(card => {{
  const box = card.querySelector("input");
  const id = card.dataset.id;
  box.checked = !!state[id]; card.classList.toggle("isdone", box.checked);
  box.addEventListener("change", () => {{
    state[id] = box.checked; card.classList.toggle("isdone", box.checked);
    try {{ localStorage.setItem(KEY, JSON.stringify(state)); }} catch (e) {{}}
  }});
}});
</script></body></html>
'''
