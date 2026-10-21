"""Cartes dessinées et mode escalade."""

import math

import pygame
import pytest

from engine8bit.display import FPS
from game import maps
from game.battle import Battle
from game.render import Renderer
from game.settings import Settings


def finish(b):
    while not b.done:
        b.step()
    return b


def quick(**kw):
    return Settings(teaser=False, league=False, **kw)


def test_random_map_choice_is_deterministic_and_varied():
    names = [Battle(s, quick()).map_name for s in range(120)]
    assert names == [Battle(s, quick()).map_name for s in range(120)]
    assert set(names) == set(maps.MAP_NAMES)


@pytest.mark.parametrize("name", maps.MAP_NAMES)
def test_every_map_is_valid_and_playable(name):
    for seed in range(4):
        b = Battle(seed, quick(map=name, players=4))
        assert b.map_name == name
        for x0, y0, x1, y1 in b.obstacles:
            assert 0 <= x0 < x1 <= b.W and 0 <= y0 < y1 <= b.H
            for c in b.cubes:                                  # aucun départ sur / contre un obstacle
                assert not (x0 - 2 < c.cx + c.half and c.cx - c.half < x1 + 2
                            and y0 - 2 < c.cy + c.half and c.cy - c.half < y1 + 2)
    # une partie complète : jamais dans un obstacle, jamais bloqué
    window = {}

    def check(b):
        for c in b.cubes:
            for o in b.obstacles:
                ox = min(c.cx + c.half, o[2]) - max(c.cx - c.half, o[0])
                oy = min(c.cy + c.half, o[3]) - max(c.cy - c.half, o[1])
                assert min(ox, oy) < 1.5
        if b.phase != "battle" or b.slowmo:
            return
        for c in b.cubes:
            if c.idx in window:
                s0, far, st = window[c.idx]
                window[c.idx] = (s0, max(far, math.hypot(c.cx - s0[0], c.cy - s0[1])), st or c.immobile)
        if (b.frame - b.battle_start) % 60 == 0:
            for c in b.cubes:
                if c.idx in window and not window[c.idx][2]:
                    assert window[c.idx][1] > 8, "cube bloqué"
                window[c.idx] = ((c.cx, c.cy), 0.0, c.immobile)

    b = Battle(11, quick(map=name, players=4))
    while not b.done:
        b.step()
        check(b)


def test_maps_scale_with_arena_and_flip():
    rects = maps.MAPS["ZIGZAG"]
    flipped = maps._scaled(rects, maps.DESIGN_W, maps.DESIGN_H, True, False)
    assert flipped[0] == (maps.DESIGN_W - rects[0][2], rects[0][1], maps.DESIGN_W - rects[0][0], rects[0][3])
    big = maps._scaled(rects, 2 * maps.DESIGN_W, 2 * maps.DESIGN_H, False, False)
    assert big[0] == tuple(2 * v for v in rects[0])


def test_escalation_ramps_spawns_items_and_speed():
    b = Battle(20, quick(mode="escalation"))
    while b.frame < b.battle_start + 10:
        b.step()
    early = (b.spawn_interval_now(), b.max_items_now(), b.intensity())
    while b.frame < b.battle_end - 5:
        b.step()
    late = (b.spawn_interval_now(), b.max_items_now(), b.intensity())
    assert early[0] == 5 * FPS and late[0] < 2 * FPS
    assert early[1] == 3 and late[1] == 6
    assert early[2] < 0.01 and late[2] > 0.95
    off = Battle(20, quick(escalation=False))
    off.frame = off.battle_end - 5
    assert off.intensity() == 0 and off.spawn_interval_now() == 5 * FPS


def test_escalation_means_more_war_at_the_end():
    def late_spawns(esc):
        total = 0
        for seed in range(6):
            b = finish(Battle(seed, quick(escalation=esc)))
            total += sum(1 for e in b.events if e.name == "spawn" and e.frame > b.battle_end - 10 * FPS)
        return total
    assert late_spawns(True) > 2 * late_spawns(False)


def test_impact_effects_grow_with_time():
    from game import items
    b = Battle(21, quick(mode="escalation"))
    while b.frame < b.battle_start + 30:
        b.step()
    c = b.cubes[1]
    items.impact(b, c, 1.0, 0.0)
    early = (len(b.slashes), b.impact, max(s.length for s in b.slashes))
    b.slashes.clear()
    b.impact = 0
    b.frame = b.battle_end - 10
    items.impact(b, c, 1.0, 0.0)
    late = (len(b.slashes), b.impact, max(s.length for s in b.slashes))
    assert late[0] > early[0] and late[1] > early[1] and late[2] > early[2]
    assert any(e.name == "slash" for e in b.events)
    off = Battle(21, quick(escalation=False))
    items.impact(off, off.cubes[1], 1.0, 0.0)
    assert not off.slashes and off.impact == 0


def test_render_with_impact_frames():
    b = Battle(22, quick())
    r = Renderer(b)
    surf = pygame.Surface((135, 240))
    while not b.done:
        b.step()
        if b.impact or b.slashes or b.frame % 9 == 0:
            r.draw(surf)
