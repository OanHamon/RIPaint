import json

import numpy as np

from audio.mixer import MixPolicy, SoundEvent, render_track
from audio.music import make_loop
from audio.sfx import META, build_bank
from audio.synth import SAMPLE_RATE
from engine8bit import font
from game import settings as cfg
from output.srt import to_srt


def test_font_supports_all_default_texts():
    texts = cfg.DEFAULT_HOOKS + ["RED WINS! 45.3%", "TIE!", "+3S", "BLUE: BRUSH!", "(MORE ITEMS)", "END!", "0123456789"]
    for t in texts:
        for ch in t:
            assert font.supported(ch), ch


def test_wrap_balanced_and_punctuation():
    lines = font.wrap("CHOISIS TA COULEUR !", 100)
    assert len(lines) == 2 and lines[-1].endswith("!") and lines[-1] != "!"
    for line in lines:
        assert font.text_width(line) <= 100


def test_bank_complete_and_clean():
    bank = build_bank(0.3)
    assert set(META) <= set(bank)
    for name, sig in bank.items():
        assert sig.dtype == np.float32 and len(sig) > 0, name
        assert np.isfinite(sig).all(), name
        assert np.abs(sig).max() < 2.5, name
    assert abs(len(bank["aim"]) / SAMPLE_RATE - 0.3) < 0.01


def test_music_loop_varies_with_seed():
    a, b = make_loop(1), make_loop(2)
    assert len(a) > SAMPLE_RATE * 5
    assert len(a) != len(b) or not np.allclose(a, b)


def test_policy_limits_and_ducks_repetitions():
    p = MixPolicy(max_voices=8)
    gains = [p.admit("bounce0", 0.01 * i, 0.05) for i in range(10)]
    admitted = [g for g in gains if g is not None]
    assert admitted[0] > admitted[-1]          # atténuation progressive
    assert len(admitted) < 10                  # rafale coupée
    p = MixPolicy(max_voices=2)
    assert p.admit("spawn", 0, 1) and p.admit("cube_hit", 0, 1)
    assert p.admit("stun", 0, 1) is None        # plus de voix libre pour un son secondaire
    assert p.admit("victory", 0, 1) is not None  # un son important passe toujours


def test_render_track_length_and_peak():
    bank = build_bank(0.3)
    events = [SoundEvent(f, "bounce0") for f in range(0, 600, 7)]
    events += [SoundEvent(300, "go"), SoundEvent(300, "music_start"), SoundEvent(900, "music_stop"),
               SoundEvent(900, "buzzer"), SoundEvent(950, "victory")]
    out = render_track(events, 1200, bank, 7, master_volume=1.0, music_volume=1.0)
    assert len(out) == 1200 * SAMPLE_RATE // 60
    peak = np.abs(out).max()
    assert 0.7 < peak <= 10 ** (-2 / 20) + 1e-4
    half = render_track(events, 1200, bank, 7, master_volume=0.5, music_volume=1.0)
    assert abs(np.abs(half).max() - peak / 2) < 1e-3


def test_srt_format():
    txt = to_srt([(0, 300, "QUI VA GAGNER ?"), (300, 348, "GO !"), (3600, 3900, "ROUGE GAGNE !")], 60)
    assert "00:00:00,000 --> 00:00:05,000\nQUI VA GAGNER ?" in txt
    assert "00:00:05,000 --> 00:00:05,800\nGO !" in txt
    assert txt.startswith("1\n") and "\n3\n" in txt


def test_settings_roundtrip(tmp_path):
    s = cfg.Settings(prob_gun=0, item_interval=7.5, seed="abc", hooks=["SALUT !"])
    p = tmp_path / "c.json"
    cfg.save(s, p)
    s2 = cfg.load(p)
    assert s2.to_dict() == s.to_dict()
    assert s2.item_percentages()["gun"] == 0
    p.write_text(json.dumps({"prob_gun": "oops", "unknown": 1, "max_items": "4"}), encoding="utf-8")
    s3 = cfg.load(p)
    assert s3.prob_gun == cfg.Settings().prob_gun and s3.max_items == 4


def test_percentages_normalized():
    s = cfg.Settings(**{f"prob_{k}": 0 for k in cfg.ITEM_KINDS})
    s.prob_gun, s.prob_brush, s.prob_hourglass = 50, 50, 100
    p = s.item_percentages()
    assert abs(sum(p.values()) - 100) < 1e-9
    assert p["potion"] == 0 and abs(p["hourglass"] - 50) < 1e-9


def test_old_config_migrates_to_bigger_cubes(tmp_path):
    p = tmp_path / "c.json"
    p.write_text(json.dumps({"cube_size": 7, "brush_radius": 20, "max_items": 4}), encoding="utf-8")
    s = cfg.load(p)
    assert s.cube_size == cfg.Settings().cube_size == 13
    assert s.brush_radius == 30 and s.max_items == 4
    p.write_text(json.dumps({"cube_size": 9}), encoding="utf-8")   # valeur choisie par l'utilisateur : gardée
    assert cfg.load(p).cube_size == 9
    p.write_text(json.dumps({"cube_size": 7, "config_version": 2}), encoding="utf-8")
    assert cfg.load(p).cube_size == 7


def test_french_default_hooks_migrate_to_english(tmp_path):
    p = tmp_path / "c.json"
    p.write_text(json.dumps({"hooks": cfg.OLD_FRENCH_HOOKS, "config_version": 2}), encoding="utf-8")
    assert cfg.load(p).hooks == cfg.DEFAULT_HOOKS
    p.write_text(json.dumps({"hooks": ["MES PROPRES PHRASES !"], "config_version": 2}), encoding="utf-8")
    assert cfg.load(p).hooks == ["MES PROPRES PHRASES !"]     # phrases personnalisées : gardées


def test_previous_defaults_upgrade_to_13px_cubes(tmp_path):
    p = tmp_path / "c.json"
    p.write_text(json.dumps({"cube_size": 11, "brush_radius": 26, "config_version": 3}), encoding="utf-8")
    s = cfg.load(p)
    assert s.cube_size == 13 and s.brush_radius == 30 and s.speed_ramp == 1.8


def test_previous_speeds_upgrade_to_faster_defaults(tmp_path):
    p = tmp_path / "c.json"
    p.write_text(json.dumps({"cube_speed": 42.0, "speed_ramp": 1.6, "bullet_speed": 110.0,
                             "config_version": 4}), encoding="utf-8")
    s = cfg.load(p)
    assert (s.cube_speed, s.speed_ramp, s.bullet_speed) == (54.0, 1.8, 170.0)
    p.write_text(json.dumps({"speed_ramp": 1.3, "config_version": 4}), encoding="utf-8")
    assert cfg.load(p).speed_ramp == 1.3          # valeur choisie dans le panneau : gardée
