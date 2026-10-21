import numpy as np
import pygame
import pytest

from engine8bit import font, palette
from engine8bit.display import LOGICAL_W
from game import art, league, variants
from game.battle import Battle
from game.render import Renderer
from game.settings import Settings

FAST = dict(teaser=False, league=False)


def test_registry_is_consistent():
    names = [c.name for v in variants.VARIANTS for c in v.competitors]
    assert len(names) == len(set(names))
    for v in variants.VARIANTS:
        families = {c.family for c in v.competitors}
        assert len(families) >= 4, f"{v.key} : il faut au moins 4 familles pour une partie à 4"
        for c in v.competitors:
            assert len(c.colors) == 3
            for rows in (c.skin, c.trail):
                assert all(ch in variants.PIXELS for row in rows for ch in row), c.name
            # « FRANCE: BOMB! » / « FRANCE LEADS! » tiennent sur l'écran
            assert font.text_width(f"{c.name}: MAGNET!") <= LOGICAL_W, c.name


@pytest.mark.parametrize("seed", range(8))
def test_colors_variant_is_the_original_game(seed):
    b = Battle(seed, Settings(**FAST))
    assert b.variant.key == variants.COLORS
    assert all(c.team in palette.TEAMS for c in b.cubes)


@pytest.mark.parametrize("seed", range(8))
def test_countries_keep_the_seed_meaning(seed):
    base = Battle(seed, Settings(**FAST))
    b = Battle(seed, Settings(variant="countries", **FAST))
    assert [(c.cx, c.cy, c.dx, c.dy) for c in b.cubes] == [(c.cx, c.cy, c.dx, c.dy) for c in base.cubes]
    picked = b.competitors
    assert len({c.family for c in picked}) == len(picked)            # jamais deux rouges
    assert [c.team for c in b.cubes] == [c.name for c in picked]
    assert b.competitors == Battle(seed, Settings(variant="countries", **FAST)).competitors
    assert "COLOR" not in b.hook
    assert b.nicknames == [""] * len(b.cubes)


def test_countries_vary_with_seed():
    s = Settings(variant="countries", players=4, **FAST)
    rosters = {tuple(c.name for c in variants.resolve(s).pick(seed, ["RED"] * 4)) for seed in range(10)}
    assert len(rosters) > 3


def test_unknown_variant_falls_back_to_colors():
    assert variants.resolve(Settings(variant="nope")).key == variants.COLORS


@pytest.mark.parametrize("pattern", [True, False])
def test_paint_uses_trail_pattern_or_solid_color(pattern):
    b = Battle(3, Settings(variant="countries", players=2, paint_pattern=pattern, **FAST))
    r = Renderer(b)
    for k, c in enumerate(b.cubes):
        colors = {tuple(px) for px in r.paint[k].reshape(-1, 3)}
        if pattern:
            assert len(colors) > 1
        else:
            assert colors == {variants.colors(c.team)[1]}


def test_country_battle_renders():
    b = Battle(5, Settings(variant="countries", players=4, **FAST))
    r = Renderer(b)
    surf = pygame.Surface((135, 240))
    while b.frame < b.battle_start + 600:
        b.step()
    r.draw(surf)
    arena = pygame.surfarray.array3d(surf)
    assert arena.any()
    for size in (5, 9, 13, 30):                  # du mini-cube du score au cube du gagnant
        art.draw_cube(surf, 2, 2, size, b.cubes[0].team)


def test_skin_shading_does_not_overflow():
    img = art.skin_body("JAPAN", 11, 1)
    arr = pygame.surfarray.array3d(img)
    assert tuple(arr[0, 0]) == palette.WHITE              # coin haut-gauche : blanc intact
    assert tuple(arr[10, 0]) == tuple(np.array(palette.WHITE) * 3 // 5)   # bord droit : ombré


def test_one_league_per_variant(tmp_path, monkeypatch):
    monkeypatch.setattr(league, "ROOT", tmp_path)
    monkeypatch.setattr(league, "LEAGUE_PATH", tmp_path / "league.json")
    assert league.path_for("countries") == tmp_path / "league_countries.json"
    data = league.with_result(league.load(variant="countries"), "FRANCE")
    league.save(data, variant="countries")
    assert league.standings(league.load(variant="countries"))[0] == ("FRANCE", 1)
    assert league.load()["day"] == 0                      # la ligue des couleurs n'a pas bougé
    assert "FRANCE" not in league.load()["wins"]
