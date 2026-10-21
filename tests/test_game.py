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
    assert b.total_frames == 62 * FPS                     # toujours > 1 min (rémunération TikTok)
    legacy = run(5, only("gun", tiktok_rewards=False, teaser=False, intro_duration=5.0, outro_duration=5.0))
    assert legacy.total_frames == 60 * FPS


def test_hourglass_cap_and_duration():
    s = only("hourglass", max_hourglasses=2, item_interval=2.0)
    b = run(8, s)
    assert b.hourglasses_spawned <= 2
    assert b.total_frames == (62 + 3 * b.hourglasses_taken) * FPS


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
    s = Settings(item_interval=0.5, max_items=3, escalation=False)
    run(13, s, check=lambda b: (len(b.items) <= 3) or pytest.fail("trop d'objets"))
    s = Settings(item_interval=0.5, max_items=3)                       # escalade : jusqu'à 3 de plus
    run(13, s, check=lambda b: (len(b.items) <= b.max_items_now() <= 6) or pytest.fail("trop d'objets"))


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
    s = only("gun", item_interval=1.0, max_items=4, lives=0)    # sans vies : personne n'est K.O.
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
    s0 = b.intro_start
    assert by_name["count"] == [s0, s0 + 60, s0 + 120]          # 3-2-1 après le teaser
    assert by_name["go"] == [s0 + 180] == [b.battle_start]
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
    from game.layout import RIGHT_TOLERANCE
    b = Battle(5, Settings())
    L = b.layout
    assert L.hud_y >= L.safe.top
    assert abs((L.arena_x + b.W / 2) - 135 / 2) <= 1                 # arène centrée sur l'écran
    assert L.arena_x + b.W + 2 <= L.safe_x1 + RIGHT_TOLERANCE       # presque rien sous les boutons
    assert L.scores_y + 20 <= L.safe_y1
    old = Battle(5, Settings(arena_centered=False)).layout          # ancienne mise en page intacte
    assert (old.arena_x, old.arena_w) == (4, 108)


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
        b = Battle(60, only("gun", item_interval=999, obstacles=0))
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
    from game.physics import OBSTACLE
    assert ((band == cube.idx) | (band == OBSTACLE)).all()


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


@pytest.mark.parametrize("kind", ["bomb", "roller", "bucket", "ice", "magnet", "boots"])
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


def test_speed_ramps_up_until_end_of_base_timer():
    b = Battle(100, Settings(speed_ramp=1.6))
    while b.frame < b.battle_start:
        b.step()
    assert abs(b.speed_multiplier() - 1.0) < 1e-9
    base = round(b.settings.battle_duration * FPS)
    b.frame = b.battle_start + base // 2
    assert abs(b.speed_multiplier() - 1.3) < 0.01
    b.frame = b.battle_start + base + 300          # temps bonus des sabliers : vitesse max
    assert abs(b.speed_multiplier() - 1.6) < 1e-9
    assert abs(Battle(100, Settings(speed_ramp=1.0)).speed_multiplier() - 1.0) < 1e-9


def test_speed_up_announced_twice():
    b = run(101, Settings(speed_ramp=1.6))
    assert sum(e.name == "speed_up" for e in b.events) == 2
    assert sum(t == "SPEED UP!" for _, _, t in b.subtitles) == 2


def test_cubes_really_go_faster_at_the_end():
    b = Battle(102, only("gun", item_interval=999, speed_ramp=2.0))
    def travelled(frames):
        dist = 0.0
        for _ in range(frames):
            before = [(c.cx, c.cy) for c in b.cubes]
            b.step()
            dist += sum(math.hypot(c.cx - x, c.cy - y) for c, (x, y) in zip(b.cubes, before))
        return dist
    while b.frame < b.battle_start + 10:
        b.step()
    early = travelled(60)
    while b.frame < b.battle_end - 70:
        b.step()
    late = travelled(60)
    assert late > 1.7 * early


def test_boots_make_cube_faster():
    from game import items
    from game.entities import Item
    b = Battle(103, only("boots", item_interval=999, speed_ramp=1.0))
    while b.frame < b.battle_start + 5:
        b.step()
    fast, normal = b.cubes[0], b.cubes[1]
    items.pickup(b, fast, Item("boots", fast.cx, fast.cy, 0))
    assert fast.boots > 0 and any(e.name == "pickup_boots" for e in b.events)
    start = {c.idx: (c.cx, c.cy) for c in b.cubes}
    path = {c.idx: 0.0 for c in b.cubes}
    for _ in range(30):
        before = {c.idx: (c.cx, c.cy) for c in b.cubes}
        b.step()
        for c in b.cubes:
            path[c.idx] += math.hypot(c.cx - before[c.idx][0], c.cy - before[c.idx][1])
    assert path[fast.idx] > 1.5 * path[normal.idx]
    for _ in range(round(b.settings.boots_duration * FPS)):
        b.step()
    assert fast.boots == 0 and any(e.name == "boots_end" for e in b.events)


@pytest.mark.parametrize("kind", ["gun", "brush", "bomb", "ice", "bucket"])
def test_hit_by_opponent_item_triggers_hit_animation(kind):
    s = only(kind, item_interval=1.5, max_items=4)
    hits = set()

    def check(b):
        for c in b.cubes:
            if c.hit_anim > 0:
                hits.add(c.idx)
                assert c.hit_anim <= 24

    b = run(110, s, check=check)
    assert hits, "aucune animation de coup déclenchée"
    r = Renderer(b)
    surf = pygame.Surface((135, 240))
    for c in b.cubes:
        c.hit_anim = 20
    r.draw(surf)


def test_bullet_still_faster_than_fastest_cube():
    s = Settings()
    assert s.bullet_speed > s.cube_speed * s.speed_ramp * s.boots_factor * 0.9



# ---- Obstacles -------------------------------------------------------------------------

@pytest.mark.parametrize("count", [0, 1, 2, 3, 4, 6])
def test_obstacles_count_symmetry_and_corridors(count):
    from game.physics import OBSTACLE
    for seed in range(20):
        b = Battle(seed, Settings(obstacles=count, map="generated"))
        assert len(b.obstacles) <= count
        if count <= 3:
            assert len(b.obstacles) == count
        else:
            assert len(b.obstacles) >= 2
        margin = 2 * b.settings.cube_size + 2
        for x0, y0, x1, y1 in b.obstacles:
            assert x0 >= margin and y0 >= margin and x1 <= b.W - margin and y1 <= b.H - margin
            assert (b.grid[y0:y1, x0:x1] == OBSTACLE).all()
            for c in b.cubes:                              # aucun cube ne démarre dessus
                cx0, cy0, cx1, cy1 = c.rect()
                assert not (x0 < cx1 and x1 > cx0 and y0 < cy1 and y1 > cy0)
        xs = sorted((o[0] + o[2]) / 2 for o in b.obstacles)
        assert all(abs(a + z - b.W) < 1.01 for a, z in zip(xs, reversed(xs)))   # miroir gauche/droite


def test_no_obstacles_means_same_game_as_before():
    a = run(321, Settings(obstacles=0, map="generated"))
    assert a.obstacles == [] and a.paintable == a.W * a.H


@pytest.mark.parametrize("seed", [7, 42, 1234])
def test_obstacles_never_painted_never_entered(seed):
    from game.physics import OBSTACLE

    def check(b):
        for x0, y0, x1, y1 in b.obstacles:
            assert (b.grid[y0:y1, x0:x1] == OBSTACLE).all()
            for c in b.cubes:
                ox = min(c.cx + c.half, x1) - max(c.cx - c.half, x0)
                oy = min(c.cy + c.half, y1) - max(c.cy - c.half, y0)
                assert min(ox, oy) < 1.5, "cube dans un obstacle"
        assert sum(b.percentages()) <= 100.0 + 1e-9

    b = run(seed, Settings(obstacles=6, item_interval=1.5, max_items=5), check=check)
    assert any(e.name.startswith("bounce") for e in b.events)


def test_bullet_splats_on_obstacle():
    from game import items
    from game.entities import Bullet
    b = Battle(9, Settings(obstacles=2))
    x0, y0, x1, y1 = b.obstacles[0]
    cy = (y0 + y1) / 2
    for c in b.cubes:                                       # personne sur la trajectoire
        c.cx, c.cy = b.W / 2, 4 + c.half
    bullet = Bullet(0, 2.0, cy, 1.0, 0.0)
    b.bullets.append(bullet)
    for _ in range(60):
        items.update_bullets(b)
    assert not b.bullets and any(e.name == "splat" for e in b.events)
    assert bullet.x < x0 + 1                                # la balle s'arrête devant l'obstacle
    # sa traînée (pas les gouttelettes de l'éclaboussure) ne continue pas derrière
    assert all(x < x0 + 1 for x, _ in bullet.trail)


def test_obstacles_option_saved_from_settings():
    assert Settings().obstacles == 3



# ---- Vies et K.O. ----------------------------------------------------------------------

def _two_cubes(lives=3, seed=120):
    b = Battle(seed, only("gun", item_interval=999, lives=lives, duel_lives=lives, obstacles=0, players=2))
    while b.frame < b.battle_start + 5:
        b.step()
    return b, b.cubes[0], b.cubes[1]


def test_lives_lost_on_hits_with_invulnerability():
    from game import items
    b, a, v = _two_cubes()
    assert v.lives == 3
    items.damage(b, v)
    assert v.lives == 2 and v.invuln > 0
    items.damage(b, v)                       # encore invulnérable : pas de vie perdue
    assert v.lives == 2
    v.invuln = 0
    items.damage(b, v)
    assert v.lives == 1 and not v.dead
    assert sum(e.name == "hurt" for e in b.events) == 2


def test_knock_out_slides_then_stops_and_stops_painting():
    from game import items
    b, a, v = _two_cubes()
    v.lives = 1
    items.damage(b, v)
    assert v.dead and not v.active
    assert any(e.name == "ko" for e in b.events)
    assert any(t.endswith("K.O.!") for _, _, t in b.subtitles)
    speeds = []
    for _ in range(150):
        before = (v.cx, v.cy)
        painted_before = int((b.grid == v.idx).sum())
        b.step()
        speeds.append(math.hypot(v.cx - before[0], v.cy - before[1]))
        assert int((b.grid == v.idx).sum()) <= painted_before     # ne peint plus
    assert max(speeds[:10]) > 0.5                                  # glisse au début (après le ralenti)...
    assert speeds[-1] < 0.05                                       # ... puis s'arrête
    assert max(speeds[60:]) < max(speeds[:10])                     # en ralentissant


def test_dead_cube_not_targeted_and_cannot_pick_up():
    from game import items
    from game.entities import Item
    b, a, v = _two_cubes()
    v.lives = 1
    items.damage(b, v)
    assert items.nearest_opponent(b, a) is None
    b.items.append(Item("potion", v.cx, v.cy, -100))
    items.check_pickups(b)
    assert b.items and v.items == 0


def test_zero_lives_means_nobody_dies():
    b = run(130, only("gun", item_interval=1.0, max_items=4, lives=0))
    assert not any(c.dead for c in b.cubes)
    assert not any(e.name in ("hurt", "ko") for e in b.events)


def test_full_game_with_lives_renders_and_finishes():
    seen_dead = []
    b = run(131, only("bomb", item_interval=1.0, max_items=4, lives=1),
            check=lambda b: seen_dead.extend(c.idx for c in b.cubes if c.dead))
    assert seen_dead and b.result is not None
    r = Renderer(b)
    r.draw(pygame.Surface((135, 240)))


def test_ice_and_wave_also_cost_a_life():
    from game import items
    from game.entities import Item
    b, a, v = _two_cubes()
    items.pickup(b, a, Item("ice", a.cx, a.cy, 0))
    assert v.lives == 2 and a.lives == 3
    b2, a2, v2 = _two_cubes(seed=121)
    v2.cx, v2.cy = a2.cx + 30 if a2.cx < b2.W / 2 else a2.cx - 30, a2.cy
    items.pickup(b2, a2, Item("bucket", a2.cx, a2.cy, 0))
    w = b2.waves[0]
    for _ in range(200):
        items.update_waves(b2)
    assert (v2.lives == 2) == (v2.idx in w.hit)



def test_ice_cannot_finish_off_a_cube():
    from game import items
    from game.entities import Item
    b, a, v = _two_cubes()
    v.lives = 1
    items.pickup(b, a, Item("ice", a.cx, a.cy, 0))
    assert v.lives == 1 and not v.dead and v.frozen > 0


# ---- Modes de jeu ----------------------------------------------------------------------

from game import modes  # noqa: E402


def test_classic_mode_keeps_user_settings():
    s = Settings(prob_gun=7, lives=4)
    b = Battle(11, s)
    assert b.mode is None and b.settings is s
    assert run(11, Settings()).subtitles == run(11, Settings(mode="classic")).subtitles


def test_mode_overrides_do_not_touch_user_settings():
    s = Settings(mode="suddendeath", lives=4)
    b = Battle(11, s)
    assert b.settings.lives == 1 and b.settings.prob_ice == 0
    assert s.lives == 4 and s.prob_ice == 20


@pytest.mark.parametrize("mode", modes.MODES, ids=lambda m: m.key)
def test_each_mode_only_spawns_its_items_and_finishes(mode):
    seen = set()
    from game.physics import OBSTACLE

    def check(b):
        seen.update(i.kind for i in b.items)
        for c in b.cubes:
            x0, y0, x1, y1 = c.rect()
            assert -1 <= x0 and x1 <= b.W + 1 and -1 <= y0 and y1 <= b.H + 1
            for ox0, oy0, ox1, oy1 in b.obstacles:
                ox = min(c.cx + c.half, ox1) - max(c.cx - c.half, ox0)
                oy = min(c.cy + c.half, oy1) - max(c.cy - c.half, oy0)
                assert min(ox, oy) < 1.5, "cube dans un obstacle"

    for seed in (3, 77):
        b = run(seed, Settings(mode=mode.key, obstacles=4), check=check)
        assert b.result is not None and b.mode is mode
        assert (b.grid != OBSTACLE).sum() == b.paintable
    allowed = {k for k, w in mode.weights.items() if w > 0}
    assert seen and seen <= allowed


def test_mode_shown_in_intro_subtitle_and_renders():
    b = Battle(5, Settings(mode="kaboom"))
    assert b.subtitles[0][2].startswith("KABOOM MODE!")
    r = Renderer(b)
    surf = pygame.Surface((135, 240))
    for _ in range(b.battle_start + 5):
        b.step()
        r.draw(surf)


def test_random_mode_depends_on_seed_only():
    s = Settings(mode="random")
    picked = [modes.resolve(seed, s).key for seed in range(60)]
    assert picked == [modes.resolve(seed, s).key for seed in range(60)]
    assert set(picked) == set(modes.BY_KEY)
    assert Battle(8, s).mode is modes.resolve(8, s)


def test_mode_names_fit_in_arena():
    from engine8bit import font
    b = Battle(1, Settings())
    for m in modes.MODES:
        assert all(font.text_width(line, 2) <= b.W for line in font.wrap(m.name, b.W, 2))
        assert set(m.weights) <= set(ITEM_KINDS)
        assert all(hasattr(Settings, k) for k in m.overrides)


def test_mode_saved_in_settings():
    assert Settings.from_dict(Settings(mode="turbo").to_dict()).mode == "turbo"


def _spawn_gaps(settings, seed=4):
    b, times = Battle(seed, settings), []
    last = b.next_spawn
    while not b.done:
        b.step()
        if b.next_spawn != last:
            times.append(last)
            last = b.next_spawn
    return np.diff(times), b


def test_item_ramp_one_keeps_constant_interval():
    gaps, b = _spawn_gaps(Settings())
    assert set(gaps) == {b.interval}


def test_item_ramp_speeds_up_drops_until_end_of_timer():
    gaps, b = _spawn_gaps(Settings(item_interval=4.0, item_ramp=0.5))
    assert gaps[0] >= 220 and gaps[-1] <= 135          # ~4 s au début -> ~2 s à la fin
    assert all(x >= y for x, y in zip(gaps, gaps[1:]))


@pytest.mark.parametrize("mode", [m for m in modes.MODES if m.key != "escalation"], ids=lambda m: m.key)
def test_mode_sets_speed_and_drop_rhythm_and_video_stays_over_a_minute(mode):
    b = Battle(3, Settings(mode=mode.key, battle_duration=20, speed_ramp=1.0, item_interval=9, item_ramp=1.0))
    for key in ("speed_ramp", "item_interval", "item_ramp"):
        assert key in mode.overrides
    assert b.interval == round(mode.overrides["item_interval"] * FPS)
    assert b.total_frames >= 62 * FPS                     # la règle des > 1 min prime sur le mode
    if "battle_duration" in mode.overrides:
        assert b.base_battle_frames == round(mode.overrides["battle_duration"] * FPS)
    assert "s · vitesse ×" in modes.summary(b.settings)


def test_escalation_is_only_a_mode():
    assert not Settings().escalation
    for m in modes.MODES:
        assert Battle(3, Settings(mode=m.key, escalation=True)).settings.escalation == (m.key == "escalation")
    b = Battle(3, Settings(mode="escalation"))
    b.frame = b.battle_start + b.base_battle_frames
    assert b.spawn_interval_now() == max(45, round(b.interval * 0.28))
    assert b.max_items_now() == b.settings.max_items + 3


def test_sudden_death_keeps_one_life_in_duel():
    b = Battle(3, Settings(mode="suddendeath", players=2))
    assert b.start_lives == 1 and all(c.lives == 1 for c in b.cubes)

# ---- Cœur et cube K.O. qui rapetisse --------------------------------------------------------

def test_heart_gives_one_life_with_a_cap():
    from game import items
    from game.entities import Item
    b, a, v = _two_cubes()
    v.lives = 2
    items.pickup(b, v, Item("heart", v.cx, v.cy, 0))
    assert v.lives == 3 and v.life_gained > 0
    assert any(e.name == "pickup_heart" for e in b.events)
    assert any(t.endswith("+1 LIFE!") for _, _, t in b.subtitles)
    for _ in range(5):
        items.pickup(b, v, Item("heart", v.cx, v.cy, 0))
    assert v.lives == 3 + b.settings.max_bonus_lives          # plafond : 2 vies bonus


def test_no_hearts_without_lives():
    b = run(140, only("heart", item_interval=1.0, lives=0))
    assert not any(e.name == "spawn" for e in b.events)


def test_dead_cube_greys_and_shrinks():
    from game import items
    b, a, v = _two_cubes()
    size0 = v.size
    v.lives = 1
    items.damage(b, v)
    assert v.dead
    for _ in range(60):
        b.step()
    assert v.size == round(size0 * items.DEATH_SCALE)
    r = Renderer(b)
    surf = pygame.Surface((135, 240))
    r.draw(surf)
    x0, y0, x1, y1 = v.rect()
    px = surf.get_at((b.layout.arena_x + x0 + 2, b.layout.arena_y + y1 - 3))[:3]
    from engine8bit import palette
    assert px in (palette.GREY, palette.GREY_LIGHT, palette.GREY_DARK, palette.BLACK)


def test_dead_big_cube_shrinks_from_potion_size():
    from game import items
    from game.entities import Item
    b, a, v = _two_cubes()
    items.pickup(b, v, Item("potion", v.cx, v.cy, 0))
    for _ in range(30):
        b.step()
    assert v.big and v.size == 2 * v.base_size
    v.lives = 1
    v.invuln = 0
    items.damage(b, v)
    for _ in range(60):
        b.step()
    assert v.dead and not v.big and v.size == round(2 * v.base_size * items.DEATH_SCALE)



def test_duel_gets_more_lives():
    duel = Battle(150, Settings(players=2))
    assert duel.start_lives == 4 and all(c.lives == 4 for c in duel.cubes)
    trio = Battle(150, Settings(players=3))
    assert trio.start_lives == 3 and all(c.lives == 3 for c in trio.cubes)
    assert Battle(150, Settings(players=2, duel_lives=5)).start_lives == 5
    assert Battle(150, Settings(players=2, lives=0)).start_lives == 0       # vies désactivées
