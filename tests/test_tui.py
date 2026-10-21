"""Interface terminal : démarrage, réglages au clavier, enregistrement de config.json."""

import asyncio
import functools
import json

import pytest

from game import settings as cfg
from ui import app as tui
from ui.arena import Arena
from ui.widgets import PixelSlider, Stepper, Toggle


@pytest.fixture
def config(tmp_path, monkeypatch):
    path = tmp_path / "config.json"
    data = cfg.Settings().to_dict()
    data["hooks"] = ["ACCROCHE PERSO"]
    path.write_text(json.dumps(data), encoding="utf-8")
    monkeypatch.setattr(cfg, "CONFIG_PATH", path)
    monkeypatch.setattr(cfg, "load", functools.partial(cfg.load, path=path))
    monkeypatch.setattr(cfg, "save", functools.partial(cfg.save, path=path))
    return path


async def _to_main(pilot):
    await pilot.press("enter")
    for _ in range(100):
        await pilot.pause(0.05)
        if isinstance(pilot.app.screen, tui.MainScreen):
            await pilot.pause(0.3)          # le temps du montage (focus initial)
            return pilot.app.screen
        await pilot.press("enter")
    raise AssertionError("l'écran principal ne s'est pas ouvert")


@pytest.mark.parametrize("size", [(130, 42), (80, 24)])
def test_boot_and_edit_settings(config, size):
    async def run():
        app = tui.RIPaintApp()
        async with app.run_test(size=size) as pilot:
            screen = await _to_main(pilot)
            assert screen.focused is screen.query_one("#players")
            gun = screen.query_one("#prob_gun", PixelSlider)
            gun.focus()
            await pilot.pause()
            await pilot.press("right", "right", "shift+left")
            assert gun.value == 25 + 2 - 10
            await pilot.press("down", "home")
            assert screen.query_one("#prob_brush", PixelSlider).value == 0
            assert screen.query_one("#prob_brush", PixelSlider).note == "jamais"
            screen.query_one("#max_items", Stepper).action_nudge(2)
            screen.query_one("#players").action_nudge(2)        # aléatoire -> 2 -> 3 joueurs
            screen.query_one("#speed_ramp", Stepper).action_nudge(-3)
            screen.query_one("#export_srt", Toggle).action_toggle()
            await pilot.pause(0.6)          # enregistrement différé
            await pilot.press("q")
    asyncio.run(run())

    saved = json.loads(config.read_text(encoding="utf-8"))
    assert saved["prob_gun"] == 17
    assert saved["prob_brush"] == 0
    assert saved["max_items"] == 5
    assert saved["players"] == 3
    assert saved["speed_ramp"] == 1.5
    assert saved["export_srt"] is False
    assert saved["hooks"] == ["ACCROCHE PERSO"]   # clés avancées préservées


def test_arena_renders_any_size():
    async def run():
        from textual.app import App

        class Host(App):
            def compose(self):
                yield Arena()

        for size in [(20, 4), (60, 20), (7, 3)]:
            async with Host().run_test(size=size) as pilot:
                await pilot.pause(0.3)
                arena = pilot.app.query_one(Arena)
                for y in range(arena.size.height):
                    assert arena.render_line(y).cell_length == arena.size.width
    asyncio.run(run())


def test_paint_bar_width():
    for frac in (0, 0.33, 0.5, 0.999, 1, 1.5):
        assert tui.paint_bar(frac, 17, "#ffffff").cell_len == 17
