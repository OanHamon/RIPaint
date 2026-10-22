"""Nom de fichier = description TikTok, catalogue et planning de la semaine."""

from datetime import date, datetime
from pathlib import Path
from types import SimpleNamespace

from output import planning


def test_filename_is_the_caption_with_lookalikes():
    cap = "Decided by 1.8% at the buzzer 😳 Who's your pick? 👇 #paintrace #whowillwin #fyp"
    name = planning.tiktok_filename(cap)
    assert name == "Decided by 1.8% at the buzzer 😳 Who's your pick？ 👇 #paintrace #whowillwin #fyp"
    assert not any(ch in name for ch in '<>:"/\|?*')
    assert planning.tiktok_filename("New arena: Space") == "New arena： Space"
    assert "#" in name and "seed" not in name


def test_long_caption_drops_hashtags_not_words():
    cap = "x" * 120 + " #aaaaaaaaaa #bbbbbbbbbb #cccccccccc #dddddddddd"
    name = planning.tiktok_filename(cap)
    assert len(name) <= planning.NAME_LIMIT and name.startswith("x" * 120) and "#aaaaaaaaaa" in name


def test_unique_stem_adds_a_hashtag_then_a_number(tmp_path):
    stem = "Pick your cube #fyp"
    assert planning.unique_stem(tmp_path, stem) == stem
    (tmp_path / f"{stem}.mp4").write_bytes(b"")
    second = planning.unique_stem(tmp_path, stem)
    assert second.startswith(stem + " #") and second != stem


def test_week_slots_and_parsing():
    start = planning.parse_start("", today=date(2026, 10, 22))
    assert start == date(2026, 10, 23)
    assert planning.parse_start("26/10/2026") == date(2026, 10, 26)
    assert planning.parse_times("19h, 12:30;19:00") == [(12, 30), (19, 0)]
    slots = planning.week_slots(date(2026, 10, 26), 7, ["12:30", "19:00"])
    assert len(slots) == 14 and slots[0] == datetime(2026, 10, 26, 12, 30) and slots[-1] == datetime(2026, 11, 1, 19, 0)


def _fake_result(folder: Path, name: str, seed: int):
    path = folder / name
    return SimpleNamespace(path=path, caption=name[:-4], n_cubes=3, duration=71.0, summary="RED WINS! 40%",
                           seed=seed, meta={"format_name": "Course", "mode_name": "", "theme_name": "Espace",
                                            "variant_name": "couleurs", "map": "Cross", "music": "turbo",
                                            "length": "long", "league_day": 4, "cup": ""})


def test_catalogue_and_planning_files(tmp_path):
    rows = []
    for i, when in enumerate(planning.week_slots(date(2026, 10, 26), 1, ["12:30", "19:00"])):
        res = _fake_result(tmp_path, f"Video {i} 👇 #fyp.mp4", 100 + i)
        row = planning.catalogue_row(res, when)
        planning.append_catalogue(tmp_path, row)
        rows.append(row)
    cat = (tmp_path / planning.CATALOGUE_NAME).read_text(encoding="utf-8-sig").splitlines()
    assert cat[0].startswith("publication;fichier") and len(cat) == 3
    assert "Course" in cat[1] and "101" in cat[2] and "Espace" in cat[1]
    page = planning.write_planning(tmp_path, rows)
    text = page.read_text(encoding="utf-8")
    assert "Copier la légende" in text and "Video 0 👇 #fyp" in text and "12:30" in text and "Lundi 26/10" in text
    assert (tmp_path / "planning.csv").exists()
