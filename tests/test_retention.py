"""Tests des fonctions de rétention : teaser, boucle, durée TikTok, suspense, ligue..."""

import math

import numpy as np
import pygame
import pytest

from engine8bit.display import FPS
from game import league
from game.battle import (END_FRAMES, LEAD_START_DELAY, REVEAL_FRAMES, REWIND_FRAMES, TEASER_FRAMES,
                         Battle)
from game.render import Renderer
from game.settings import ITEM_KINDS, Settings


def finish(b):
    while not b.done:
        b.step()
    return b


@pytest.mark.parametrize("seed", [1, 2, 3])
def test_teaser_shows_exactly_the_real_ending(seed):
    b = finish(Battle(seed, Settings()))
    assert np.array_equal(b.final["grid"], b.grid)
    assert [round(p, 6) for p in b.final["percentages"]] == [round(p, 6) for p in b.percentages()]
    assert b.final["result"].winner == b.result.winner


def test_video_loops_last_frame_equals_first():
    b = Battle(4, Settings())
    r = Renderer(b)
    surf = pygame.Surface((135, 240))
    b.step()
    r.draw(surf)
    first = pygame.surfarray.array3d(surf).copy()
    finish(b)
    r.draw(surf)
    assert np.array_equal(first, pygame.surfarray.array3d(surf))


@pytest.mark.parametrize("seed", range(8))
def test_always_more_than_one_minute_for_tiktok_rewards(seed):
    s = Settings(**{f"prob_{k}": 0 for k in ITEM_KINDS})       # aucun sablier : cas le plus court
    s.prob_gun = 10
    b = Battle(seed, s)
    assert b.total_frames / FPS >= 62.0
    assert b.total_frames / FPS > 60.0


def test_rewards_off_keeps_short_battle():
    b = Battle(5, Settings(tiktok_rewards=False))
    assert b.base_battle_frames == 50 * FPS


def test_timeline_teaser_countdown_go():
    b = finish(Battle(6, Settings()))
    assert b.intro_start == TEASER_FRAMES + REWIND_FRAMES
    assert b.battle_start == b.intro_start + 3 * FPS
    names = {e.name: e.frame for e in b.events if e.name in ("rewind", "go", "drumroll", "victory", "draw")}
    assert names["rewind"] == TEASER_FRAMES
    assert names["go"] == b.battle_start
    assert names["drumroll"] == b.battle_end + END_FRAMES
    assert names.get("victory", names.get("draw")) == b.battle_end + END_FRAMES + REVEAL_FRAMES
    dings = [e.frame for e in b.events if e.name == "reveal_ding"]
    assert len(dings) == len(b.cubes)
    assert any(t == "WHO WINS?" for _, _, t in b.subtitles)


def test_scores_hidden_only_at_the_end():
    b = Battle(7, Settings())
    seen = {"teaser": set(), "battle_early": set(), "battle_late": set()}
    while not b.done:
        b.step()
        if b.phase == "teaser":
            seen["teaser"].add(b.scores_hidden())
        elif b.phase == "battle":
            key = "battle_late" if b.battle_end - b.frame <= 5 * FPS else "battle_early"
            seen[key].add(b.scores_hidden())
    assert seen == {"teaser": {True}, "battle_early": {False}, "battle_late": {True}}


def test_lead_announcements_respect_delay_and_hidden_zone():
    for seed in range(5):
        b = finish(Battle(seed, Settings(teaser=False, league=False)))
        for e in b.events:
            if e.name == "lead_change":
                assert e.frame - b.battle_start >= LEAD_START_DELAY
                assert b.battle_end - e.frame > 5 * FPS
        assert sum(t.endswith("LEADS!") for _, _, t in b.subtitles) == b.lead_changes


def test_comeback_spawns_items_near_last_cube():
    def near_ratio(comeback):
        near = total = 0
        for seed in range(6):
            b = Battle(seed, Settings(comeback=comeback, item_interval=1.0, max_items=6, teaser=False,
                                      league=False, lives=0))
            seen = set()
            while not b.done:
                b.step()
                for it in b.items:
                    if id(it) in seen:
                        continue
                    seen.add(id(it))
                    last = min(b.cubes, key=lambda c: (int(b.counts[c.idx]), c.idx))
                    total += 1
                    near += math.hypot(it.x - last.cx, it.y - last.cy) <= 40
        return near / total
    assert near_ratio(1.0) > near_ratio(0.0) + 0.15


def test_slowmo_on_ko_and_explosion_only_when_enabled():
    s = Settings(**{f"prob_{k}": 0 for k in ITEM_KINDS})
    s.prob_bomb, s.item_interval, s.max_items, s.lives = 100, 1.0, 4, 1
    on = finish(Battle(8, s))
    assert any(e.name == "slowmo" for e in on.events)
    s.slowmo = False
    off = finish(Battle(8, s))
    assert not any(e.name == "slowmo" for e in off.events)


def test_nicknames_unique_and_deterministic():
    a, b = Battle(9, Settings()), Battle(9, Settings())
    assert a.nicknames == b.nicknames and len(set(a.nicknames)) == len(a.cubes)
    assert Battle(9, Settings(nicknames=False)).nicknames == [""] * len(a.cubes)


def test_league_progression(tmp_path):
    path = tmp_path / "league.json"
    data = league.load(path)
    assert data["day"] == 0
    data = league.with_result(data, "RED")
    data = league.with_result(data, "BLUE")
    data = league.with_result(data, "RED")
    data = league.with_result(data, None)                     # égalité : journée sans vainqueur
    league.save(data, path)
    again = league.load(path)
    assert again["day"] == 4
    assert league.standings(again)[0] == ("RED", 2)
    league.reset(path)
    assert league.load(path)["day"] == 0


def test_render_every_phase_without_error():
    b = Battle(10, Settings())
    b.league = {"day": 3, "standings": [("RED", 2), ("BLUE", 1), ("YELLOW", 0), ("GREEN", 0)]}
    r = Renderer(b)
    surf = pygame.Surface((135, 240))
    while not b.done:
        b.step()
        if b.frame % 5 == 0 or b.phase in ("teaser", "outro"):
            r.draw(surf)


def test_follow_prompt_tap_sound_subtitle_and_free_band():
    from game.battle import FOLLOW_BOX_H, FOLLOW_TAP
    b = Battle(30, Settings(players=4))
    while b.frame < b.battle_start:
        b.step()
    taps = [e.frame for e in b.events if e.name == "follow_tap"]
    assert taps == [b.intro_start + FOLLOW_TAP]
    assert any(t == "FOLLOW FOR MORE!" for _, _, t in b.subtitles)
    for seed in range(40):                                  # aucun cube caché par l'encadré
        bb = Battle(seed, Settings(players=4, teaser=False, league=False))
        assert all(c.cy - c.half - 12 >= 4 + FOLLOW_BOX_H for c in bb.cubes)
    off = Battle(30, Settings(follow_prompt=False))
    while off.frame < off.battle_start:
        off.step()
    assert not any(e.name == "follow_tap" for e in off.events)


def test_follow_prompt_renders_every_frame():
    b = Battle(31, Settings())
    r = Renderer(b)
    surf = pygame.Surface((135, 240))
    while b.frame < b.battle_start + 2:
        b.step()
        r.draw(surf)
