import math

import numpy as np
import pygame
import pytest

from engine8bit.display import FPS
from game.battle import Battle, compute_result
from game.entities import Cube
from game.render import Renderer
from game.settings import ITEM_KINDS, Settings


def run(seed, settings=None, frames=None, check=None):
    b = Battle(seed, settings or Settings())
    while not b.done and (frames is None or b.frame + 1 < frames):
        b.step()
        if check:
            check(b)
    return b


def only(kind, **kw):
    s = Settings(**kw)
    for k in ITEM_KINDS:
        setattr(s, f"prob_{k}", 100 if k == kind else 0)
    return s


def test_determinism_same_seed():
    a, b = run(1234), run(1234)
    assert np.array_equal(a.grid, b.grid)
    assert [(e.frame, e.name) for e in a.events] == [(e.frame, e.name) for e in b.events]
    assert a.total_frames == b.total_frames


def test_different_seeds_differ():
    grids = [run(s, frames=1200).grid for s in (1, 2, 3)]
    assert not np.array_equal(grids[0], grids[1])
    assert not np.array_equal(grids[1], grids[2])


@pytest.mark.parametrize("seed", range(12))
def test_scenario_rules(seed):
    b = Battle(seed, Settings())
    assert 2 <= len(b.cubes) <= 4
    teams = [c.team for c in b.cubes]
    assert len(set(teams)) == len(teams)
    if len(teams) < 4:
        assert "GREEN" not in teams
    for c in b.cubes:
        ang = math.degrees(math.atan2(abs(c.dy), abs(c.dx)))
        assert 19.9 <= ang <= 70.1


@pytest.mark.parametrize("seed", [3, 17, 99, 2024])
def test_cubes_stay_inside_and_never_stuck(seed):
    window = {}   # idx -> (position au début de la fenêtre d'1 s, distance max atteinte, assommé ?)

    def check(b):
        for c in b.cubes:
            x0, y0, x1, y1 = c.rect()
            assert -1 <= x0 and x1 <= b.W + 1 and -1 <= y0 and y1 <= b.H + 1
        # pas de chevauchement durable entre cubes
        for i in range(len(b.cubes)):
            for j in range(i + 1, len(b.cubes)):
                a, c = b.cubes[i], b.cubes[j]
                ox = a.half + c.half - abs(a.cx - c.cx)
                oy = a.half + c.half - abs(a.cy - c.cy)
                assert min(ox, oy) < 2.5
        if b.phase != "battle":
            return
        for c in b.cubes:
            if c.idx in window:
                start, far, was_stunned = window[c.idx]
                window[c.idx] = (start, max(far, math.hypot(c.cx - start[0], c.cy - start[1])),
                                 was_stunned or c.immobile)
        if (b.frame - b.battle_start) % 60 == 0:
            for c in b.cubes:
                if c.idx in window:
                    _, far, was_stunned = window[c.idx]
                    if not was_stunned:
                        assert far > 8, "cube bloqué"
                window[c.idx] = ((c.cx, c.cy), 0.0, c.immobile)

    run(seed, check=check)


def test_duration_base_without_hourglass():
    b = run(5, only("gun"))
    assert b.hourglasses_taken == 0
    assert b.total_frames == 60 * FPS


def test_hourglass_cap_and_duration():
    s = only("hourglass", max_hourglasses=2, item_interval=2.0)
    b = run(8, s)
    assert b.hourglasses_spawned <= 2
    assert b.total_frames == (60 + 3 * b.hourglasses_taken) * FPS


def test_zero_probabilities_no_items():
    s = Settings(**{f"prob_{k}": 0 for k in ITEM_KINDS})
    b = run(11, s)
    assert not any(e.name == "spawn" for e in b.events)


def test_zero_probability_item_never_spawns():
    s = Settings(prob_gun=0, prob_brush=50, prob_potion=50, prob_hourglass=0, item_interval=1.0, max_items=5)
    b = run(12, s)
    names = {e.name for e in b.events}
    assert "pickup_gun" not in names and "pickup_hourglass" not in names
    assert "spawn" in names


def test_max_items_respected():
    s = Settings(item_interval=0.5, max_items=3)
    run(13, s, check=lambda b: (len(b.items) <= 3) or pytest.fail("trop d'objets"))


def test_items_not_spawned_on_cubes_or_walls():
    s = Settings(item_interval=0.5, max_items=6)
    seen = set()

    def check(b):
        for it in b.items:
            if id(it) in seen:
                continue
            seen.add(id(it))
            x0, y0, x1, y1 = it.rect()
            assert x0 >= 4 and y0 >= 4 and x1 <= b.W - 4 and y1 <= b.H - 4
            for c in b.cubes:
                cx0, cy0, cx1, cy1 = c.rect()
                assert not (x0 < cx1 and x1 > cx0 and y0 < cy1 and y1 > cy0)

    run(14, s, check=check)


def test_gun_fires_bullet_and_stuns():
    s = only("gun", item_interval=1.0, max_items=4)
    stunned = []
    run(21, s, check=lambda b: stunned.extend(c.idx for c in b.cubes if c.stun > 0))
    b = run(21, s)
    names = [e.name for e in b.events]
    assert names.count("shot") >= 1
    assert names.count("shot") == names.count("pickup_gun")
    assert ("bullet_hit" in names and stunned) or "splat" in names


def test_brush_paints_half_disc_and_knocks_back():
    s = only("brush", item_interval=1.0, max_items=4)
    b = Battle(31, s)
    cube, other = b.cubes[0], b.cubes[1]
    b.frame = b.battle_start
    cube.cx, cube.cy = b.W / 2, b.H / 2
    other.cx, other.cy = b.W / 2 + 12, b.H / 2
    from game import items
    from game.entities import Item
    items.pickup(b, cube, Item("brush", int(cube.cx), int(cube.cy), 0))
    for _ in range(20):
        items.update_swipes(b)
    painted = int((b.grid == cube.idx).sum())
    assert painted > 0.35 * math.pi * s.brush_radius ** 2   # environ un demi-disque
    assert other.slow > 0 and other.kb_x > 0                  # repoussé vers la droite et ralenti


def test_potion_grows_then_shrinks():
    s = only("potion")
    b = Battle(41, s)
    c = b.cubes[0]
    b.frame = b.battle_start
    from game import items
    from game.entities import Item
    items.pickup(b, c, Item("potion", 10, 10, 0))
    for _ in range(30):
        items.update_resize(b, c)
    assert c.size == s.cube_size * 2
    for _ in range(round(s.potion_duration * FPS) + 30):
        items.update_resize(b, c)
    assert c.size == s.cube_size and not c.big


def test_tie_break_by_items_then_draw():
    cubes = [Cube(0, "RED", 0, 0, 1, 0, 7), Cube(1, "BLUE", 0, 0, 1, 0, 7)]
    cubes[0].items, cubes[1].items = 1, 3
    r = compute_result(cubes, np.array([100, 100]), 1000)
    assert r.winner == 1 and r.by_items
    cubes[0].items = 3
    r = compute_result(cubes, np.array([100, 100]), 1000)
    assert r.winner is None and r.tied == [0, 1]
    r = compute_result(cubes, np.array([101, 100]), 1000)
    assert r.winner == 0 and not r.by_items


def test_countdown_and_end_sounds():
    b = run(77, only("gun"))   # sans sablier, le tic-tac n'est pas interrompu
    by_name = {}
    for e in b.events:
        by_name.setdefault(e.name, []).append(e.frame)
    assert by_name["count"] == [0, 60, 120, 180, 240]
    assert by_name["go"] == [300]
    assert by_name["buzzer"] == [b.battle_end]
    ticks = sorted(by_name.get("tick", []) + by_name.get("tock", []))
    assert len(ticks) >= 8 and all(b.battle_end - 300 <= t < b.battle_end for t in ticks)
    gaps = np.diff(ticks)
    assert gaps[-1] < gaps[0]                 # le tic-tac accélère


def test_render_all_phases_without_error():
    b = Battle(5, Settings())
    r = Renderer(b)
    surf = pygame.Surface((135, 240))
    while not b.done:
        b.step()
        if b.frame % 7 == 0:
            r.draw(surf, show_safe_zone=b.frame % 2 == 0)


def test_hud_inside_safe_zone():
    b = Battle(5, Settings())
    L = b.layout
    assert L.hud_y >= L.safe.top
    assert L.arena_x + b.W + 2 <= L.safe_x1
    assert L.scores_y + 20 <= L.safe_y1


@pytest.mark.parametrize("players", [2, 3, 4])
def test_players_option_forces_cube_count(players):
    for seed in range(15):
        b = Battle(seed, Settings(players=players))
        assert len(b.cubes) == players
        assert len({c.team for c in b.cubes}) == players


def test_players_random_keeps_seed_meaning():
    # en mode aléatoire, une seed donne la même partie qu'avant l'ajout de l'option
    for seed in range(10):
        a = Battle(seed, Settings(players=0))
        b = Battle(seed, Settings(players=len(a.cubes)))
        assert [(c.team, c.cx, c.cy) for c in a.cubes] == [(c.team, c.cx, c.cy) for c in b.cubes]



# ---- Nouveaux objets -------------------------------------------------------------------

def _setup(kind, seed=50):
    from game.entities import Item
    s = only(kind)
    b = Battle(seed, s)
    b.frame = b.battle_start
    cube = b.cubes[0]
    return b, s, cube, Item(kind, cube.cx, cube.cy, 0)


def test_bomb_explodes_after_fuse_and_pushes():
    from game import items
    b, s, cube, item = _setup("bomb")
    other = b.cubes[1]
    cube.cx, cube.cy = b.W / 2, b.H / 2
    other.cx, other.cy = b.W / 2 + 10, b.H / 2
    item.x, item.y = cube.cx, cube.cy
    items.pickup(b, cube, item)
    fuse = round(s.bomb_fuse * FPS)
    for _ in range(fuse - 1):
        items.update_bombs(b)
    assert b.bombs and not any(e.name == "explosion" for e in b.events)
    items.update_bombs(b)
    assert not b.bombs and any(e.name == "explosion" for e in b.events)
    assert int((b.grid == cube.idx).sum()) > 0.8 * math.pi * s.bomb_radius ** 2
    assert other.kb_x > 100 and b.shake > 0
    assert sum(e.name == "bomb_tick" for e in b.events) >= 4


def test_roller_paints_wider_trail():
    def painted(roller):
        b = Battle(60, only("gun", item_interval=999))
        while b.frame < b.battle_start:
            b.step()
        if roller:
            b.cubes[0].roller = 10 ** 6
        for _ in range(120):
            b.step()
        return int((b.grid == 0).sum())
    assert painted(True) > 1.8 * painted(False)


def test_bucket_wave_crosses_whole_arena():
    from game import items
    b, s, cube, item = _setup("bucket")
    items.pickup(b, cube, item)
    w = b.waves[0]
    for _ in range(200):
        items.update_waves(b)
    assert not b.waves
    a0, a1 = int(w.band - w.half), int(w.band + w.half) + 1
    band = b.grid[a0:a1, :] if w.horizontal else b.grid[:, a0:a1]
    assert (band == cube.idx).all()


def test_bucket_chooses_direction_with_most_enemy_paint():
    from game import items
    b, s, cube, item = _setup("bucket")
    cube.cx, cube.cy = b.W / 2, b.H / 2
    b.grid[:, :] = cube.idx
    b.grid[int(cube.cy) - 3:int(cube.cy) + 4, :] = 1      # bande horizontale adverse
    items.pickup(b, cube, item)
    assert b.waves[0].horizontal


def test_ice_freezes_opponents_then_thaws():
    b = Battle(70, only("gun", item_interval=999))
    while b.frame < b.battle_start + 30:
        b.step()
    from game import items
    from game.entities import Item
    owner = b.cubes[0]
    items.pickup(b, owner, Item("ice", owner.cx, owner.cy, 0))
    frozen_pos = {c.idx: (c.cx, c.cy) for c in b.cubes[1:]}
    frames = round(b.settings.ice_duration * FPS)
    for _ in range(frames - 2):
        b.step()
    for c in b.cubes[1:]:
        assert c.frozen > 0 and (c.cx, c.cy) == frozen_pos[c.idx]
    assert owner.frozen == 0
    for _ in range(4):
        b.step()
    assert all(c.frozen == 0 for c in b.cubes)
    assert any(e.name == "thaw" for e in b.events)


def test_magnet_attracts_items():
    from game import items
    from game.entities import Item
    b, s, cube, item = _setup("magnet")
    items.pickup(b, cube, item)
    far = Item("gun", 10, 10, -100)
    b.items.append(far)
    start = math.hypot(far.x - cube.cx, far.y - cube.cy)
    for _ in range(30):
        items.update_magnets(b)
    assert math.hypot(far.x - cube.cx, far.y - cube.cy) < start - 25


@pytest.mark.parametrize("kind", ["bomb", "roller", "bucket", "ice", "magnet"])
def test_full_game_with_each_new_item(kind):
    s = only(kind, item_interval=2.0, max_items=4)
    b = run(80, s)
    names = [e.name for e in b.events]
    assert f"pickup_{kind}" in names
    r = Renderer(b)
    r.draw(pygame.Surface((135, 240)))


def test_in_game_texts_are_english():
    b = run(90, only("gun", item_interval=1.0))
    texts = " ".join(t for _, _, t in b.subtitles)
    for french in ("GAGNE", "ÉGALITÉ", "FUSIL", "ROUGE", "BLEU", "JAUNE", "VERT", " !"):
        assert french not in texts
    assert "WINS!" in texts or "TIE!" in texts
