"""Tests anti-répétition : thèmes, formats, killcam, musiques, garde-fou, légendes, PaintCup."""

import random
from collections import Counter

import numpy as np
import pygame
import pytest

from audio import music
from engine8bit.display import FPS
from game import captions, cup, formats, themes, variants, variety
from game import settings as cfg
from game.battle import END_DELAY, KILLCAM_MAX, Battle
from game.render import Renderer
from game.settings import Settings


def finish(b, draw_every=0):
    r = Renderer(b) if draw_every else None
    surf = pygame.Surface((135, 240))
    while not b.done:
        b.step()
        if r and b.frame % draw_every == 0:
            r.draw(surf)
    return b


@pytest.mark.parametrize("theme", [t.key for t in themes.THEMES])
def test_each_theme_renders_and_loops_seamlessly(theme):
    b = Battle(4, Settings(theme=theme))
    r = Renderer(b)
    surf = pygame.Surface((135, 240))
    b.step()
    r.draw(surf)
    first = pygame.surfarray.array3d(surf).copy()
    while not b.done:
        b.step()
        if b.frame % 40 == 0:
            r.draw(surf)
    r.draw(surf)
    assert np.array_equal(first, pygame.surfarray.array3d(surf))   # l'ambiance animée boucle aussi


def test_theme_is_visual_only():
    a = finish(Battle(8, Settings(theme="classic")))
    b = finish(Battle(8, Settings(theme="lava")))
    assert np.array_equal(a.grid, b.grid)


def test_random_theme_depends_on_seed():
    keys = {themes.resolve(seed, Settings(theme="random")).key for seed in range(40)}
    assert len(keys) >= 6


@pytest.mark.parametrize("fmt", [f.key for f in formats.FORMATS])
def test_each_format_matches_its_teaser_and_renders(fmt):
    for seed in (1, 2):
        b = finish(Battle(seed, Settings(format=fmt, theme="random", variant="random")), draw_every=13)
        assert np.array_equal(b.final["grid"], b.grid)               # teaser = vraie fin (killcam, fin anticipée)
        assert b.final["result"].winner == b.result.winner
        if formats.BY_KEY[fmt].win == formats.SURVIVAL:
            assert any(not c.dead for c in b.cubes)                    # jamais zéro survivant
            assert b.result.ranking[0].alive


def test_duo_has_two_teams_and_no_friendly_fire():
    for seed in range(1, 5):
        b = Battle(seed, Settings(format="duo", lives=3))
        assert len(b.cubes) == 4 and len(b.sides) == 2
        assert b.cubes[0].team == b.cubes[2].team != b.cubes[1].team == b.cubes[3].team
        assert b.allies(0, 2) and not b.allies(0, 1)
        finish(b)
        assert len(b.result.ranking) == 2


def test_royale_has_six_to_eight_small_cubes():
    counts = set()
    for seed in range(8):
        b = Battle(seed, Settings(format="royale", variant="countries"))
        counts.add(len(b.cubes))
        assert all(c.base_size == 9 for c in b.cubes)
        assert len({c.team for c in b.cubes}) == len(b.cubes)
    assert counts <= {6, 7, 8} and len(counts) >= 2


@pytest.mark.parametrize("fmt", ["combat", "royale"])
def test_fight_formats_do_not_paint_and_end_right_after_last_ko(fmt):
    for seed in range(1, 5):
        b = finish(Battle(seed, Settings(format=fmt, players=3)))
        assert not b.paints and b.survival and int((b.grid >= 0).sum()) >= 0
        if b.ended_early:                                              # victoire immédiate du dernier
            assert len(b.alive_sides()) == 1
            assert b.battle_end == b.ko_log[-1][0] + END_DELAY
            assert not any("VICTORY LAP" in text for _, _, text in b.subtitles)


@pytest.mark.parametrize("fmt", ["combat", "royale"])
def test_long_fight_videos_get_extra_lives_to_stay_over_one_minute(fmt):
    from output.exporter import keep_over_a_minute, simulated_seconds
    for seed in range(8):
        s = keep_over_a_minute(seed, Settings(format=fmt, target_duration=62.0), {})
        assert simulated_seconds(seed, s) >= 62.0
        b = finish(Battle(seed, s))
        assert b.total_frames / FPS >= 62.0


def test_killcam_zooms_before_ko_and_is_capped():
    seen = 0
    for seed in range(1, 6):
        b = Battle(seed, Settings(format="royale"))
        zoomed = False
        while not b.done:
            b.step()
            zoomed |= b.cam_level > 0.9
        assert b.killcams <= KILLCAM_MAX
        seen += b.killcams
        assert zoomed == (b.killcams > 0 or bool(b.ko_log))
    assert seen > 0
    off = finish(Battle(2, Settings(format="royale", killcam=False)))
    assert off.killcams == 0


@pytest.mark.parametrize("style", [s.key for s in music.STYLES])
def test_music_styles_are_generated_and_different(style):
    track = music.music_track(42, 20, style=style)
    assert len(track) == music.SAMPLE_RATE * 20 and 0.5 < float(np.abs(track).max()) <= 0.81
    other = music.music_track(42, 20, style="battle" if style != "battle" else "happy")
    assert not np.allclose(track, other)


def test_variety_never_repeats_twice_in_a_row_and_keeps_85_percent_long():
    s = Settings.from_dict(cfg.FRESH)
    s.variant = "random"
    h = {"count": 0, "videos": []}
    plans = []
    for i in range(60):
        plan = variety.plan_video(s, h, random.Random(i))
        h = variety.record(h, plan)
        plans.append(plan)
    lengths = [p["length"] for p in plans]
    assert abs(lengths.count("short") / len(lengths) - 0.15) < 0.02
    assert not any(a == b == "short" for a, b in zip(lengths, lengths[1:]))
    for key in ("format", "theme", "variant", "music_style"):
        seq = [p.get(key) for p in plans]
        assert not any(a == b for a, b in zip(seq, seq[1:])), key
        assert len(Counter(seq)) >= 4
    for p in plans:
        if p["length"] == "long":
            assert p["target_duration"] >= 62
        else:
            assert 30 <= p["target_duration"] <= 50 and formats.BY_KEY[p["format"]].key in formats.SHORT_WEIGHTS


@pytest.mark.parametrize("fmt", ["classic", "duo", "combat", "royale", "sprint", "duel"])
def test_planned_durations_are_respected(fmt):
    from output.exporter import keep_over_a_minute
    for target in (35.0, 75.0):
        s = keep_over_a_minute(5, Settings(format=fmt, target_duration=target), {})
        b = finish(Battle(5, s))
        seconds = b.total_frames / FPS
        if target >= 62:
            assert seconds >= 62
        else:
            assert seconds <= target + 3 * 3 + 1                      # sabliers éventuels


def test_captions_vary_and_never_name_the_winner():
    texts = set()
    for seed in range(8):
        b = finish(Battle(seed, Settings(format=random.Random(seed).choice(["classic", "combat", "duo"]),
                                         variant="countries")))
        text, hid = captions.make(b, ["paintrace", "satisfying"], [], random.Random(seed))
        texts.add(text.split("#")[0])
        if b.result.winner is not None:
            assert b.cubes[b.result.winner].team.lower() not in text.lower()
        assert "#paintrace" in text and text.count("#") <= 5
    assert len(texts) >= 6


def test_caption_filename_part_is_short_and_clean():
    part = captions.title_part("Decided by 0.4% at the buzzer 😳 Who's your pick? 👇 #fyp #paintrace " * 3)
    assert len(part) <= 60 and "#" not in part and all(ord(ch) < 0x2000 for ch in part)


@pytest.mark.parametrize("size", [8, 10, 12, 16])
def test_paintcup_runs_to_a_champion(size):
    c = cup.new_cup("countries", size, 7)
    assert len(c["players"]) == size
    episodes = 0
    while (slot := cup.next_match(c)) is not None:
        lineup = c["rounds"][slot[0]]["matches"][slot[1]]["lineup"]
        assert 3 <= len(lineup) <= 4 or c["rounds"][slot[0]]["name"] == "FINAL"
        info = cup.record(c, *slot, list(lineup))
        assert len(info["qualified"]) == (0 if info["champion"] else 2)
        episodes += 1
    assert episodes == cup.total_episodes(size)
    assert c["champion"] and cup.standings(c)[0][0] == c["champion"]


def test_paintcup_lineup_is_used_by_the_battle():
    lineup = ["FRANCE", "JAPAN", "BRAZIL"]
    b = Battle(3, Settings(lineup=lineup, players=3, cup_label="SEMI-FINAL 1/2", variant="countries"))
    assert [c.team for c in b.cubes] == lineup
    assert "PAINTCUP SEMI-FINAL 1/2!" in b.subtitles[0][2]
    assert b.final is not None


def test_colors_variant_cap_and_new_variants():
    assert len(variants.BY_KEY["colors"].competitors) == 8
    for key in ("fruits", "animals", "planets"):
        v = variants.BY_KEY[key]
        picked = v.pick(5, ["RED", "BLUE", "YELLOW", "GREEN"])
        assert len({c.family for c in picked}) == 4


def test_all_random_button_draws_every_setting_per_video():
    s = Settings(format="classic", mode="kaboom", players=3, variant="colors", theme="classic", map="CROSS",
                 music_style="battle")
    for key, value in variety.ALL_RANDOM.items():
        assert hasattr(s, key)
        setattr(s, key, value)
    h = {"count": 0, "videos": []}
    seen = {k: set() for k in ("format", "theme", "variant", "music_style", "map")}
    for i in range(12):
        plan = variety.plan_video(s, h, random.Random(i))
        h = variety.record(h, plan)
        for k in seen:
            seen[k].add(plan.get(k))
    assert all(len(v) >= 4 for v in seen.values()), seen


def test_migration_adds_variety_without_touching_user_choices(tmp_path):
    p = tmp_path / "config.json"
    p.write_text('{"mode": "escalation", "config_version": 7}', encoding="utf-8")
    s = cfg.load(p)
    assert s.mode == "escalation" and s.format == "random" and s.theme == "random"
    assert cfg.load(tmp_path / "absent.json").format == "random"
