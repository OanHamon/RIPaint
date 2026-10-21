"""Banque de bruitages du jeu, entièrement synthétisés.

Chaque son a des métadonnées de mixage : priorité (0-10, plus haut = plus important),
gain de base et groupe (les sons d'un même groupe joués en rafale sont atténués).
"""

from dataclasses import dataclass

import numpy as np

from .synth import (arpeggio, concat, lowpass, note, osc, overlay, semis, silence, sweep,
                    tone, n_samples, adsr, fade)

BOUNCE_VARIANTS = 7


@dataclass(frozen=True)
class SoundMeta:
    priority: int
    gain: float
    group: str


META: dict[str, SoundMeta] = {}


def _meta(name, priority, gain, group=None):
    META[name] = SoundMeta(priority, gain, group or name)


for _i in range(BOUNCE_VARIANTS):
    _meta(f"bounce{_i}", 1, 0.32, "bounce")
_meta("cube_hit", 3, 0.6)
_meta("spawn", 4, 0.45)
_meta("pickup_gun", 7, 0.7, "pickup")
_meta("pickup_brush", 7, 0.7, "pickup")
_meta("pickup_potion", 7, 0.7, "pickup")
_meta("pickup_hourglass", 7, 0.7, "pickup")
_meta("aim", 7, 0.5)
_meta("shot", 8, 0.8)
_meta("bullet_hit", 8, 0.9)
_meta("splat", 8, 0.75)
_meta("stun", 5, 0.5)
_meta("wake", 5, 0.5)
_meta("whoosh", 8, 0.75)
_meta("brush_hit", 8, 0.8)
_meta("slow", 5, 0.5)
_meta("grow", 7, 0.6)
_meta("shrink", 6, 0.55)
_meta("time_plus", 9, 0.8)
_meta("count", 9, 0.7)
_meta("go", 10, 0.9)
_meta("tick", 9, 0.55, "tick")
_meta("tock", 9, 0.55, "tick")
_meta("buzzer", 10, 0.9)
_meta("victory", 10, 0.85)
_meta("draw", 10, 0.85)
for _k in ("bomb", "roller", "bucket", "ice", "magnet"):
    _meta(f"pickup_{_k}", 7, 0.7, "pickup")
_meta("bomb_drop", 6, 0.6)
_meta("bomb_tick", 6, 0.45)
_meta("explosion", 9, 0.95)
_meta("roller_end", 5, 0.45)
_meta("wave", 8, 0.75)
_meta("freeze", 8, 0.7)
_meta("thaw", 5, 0.5)
_meta("magnet", 7, 0.55)
_meta("pickup_boots", 7, 0.7, "pickup")
_meta("boots_end", 5, 0.45)
_meta("speed_up", 9, 0.7)
_meta("hurt", 7, 0.55)
_meta("rewind", 9, 0.6)
_meta("drumroll", 9, 0.7)
_meta("reveal_ding", 9, 0.6, "reveal")
_meta("lead_change", 8, 0.6)
_meta("slowmo", 8, 0.6)
_meta("slash", 8, 0.6)
_meta("pickup_heart", 7, 0.7, "pickup")
_meta("ko", 9, 0.8)


def _noise(dur, rate, vol, a=0.001, d=0.05, s=0.3, r=0.05, seed=1, rate_end=None):
    n = n_samples(dur)
    freq = sweep(rate, rate_end, n) if rate_end else np.full(n, rate)
    return (osc("noise", freq, n, seed=seed) * adsr(n, a, d, s, r) * vol).astype(np.float32)


def _jingle(notes, step, wave="square", duty=0.5, vol=0.5, bass=None):
    lead = arpeggio([note(x) for x in notes], step, wave, vol, duty)
    if bass:
        b = arpeggio([note(x) for x in bass], step * len(notes) / len(bass), "triangle", vol * 0.9)
        return overlay((lead, 0), (b, 0))
    return lead


def build_bank(aim_duration: float = 0.3) -> dict[str, np.ndarray]:
    bank: dict[str, np.ndarray] = {}

    # Rebond mur : bip court, hauteur variable selon la variante
    for i in range(BOUNCE_VARIANTS):
        f = semis(note("E6"), (i - BOUNCE_VARIANTS // 2) * 1.5)
        bank[f"bounce{i}"] = tone("square", f, 0.045, f_end=f * 0.8, duty=0.25, vol=0.5,
                                  a=0.001, d=0.02, s=0.4, r=0.02)

    # Collision entre cubes : impact grave + bruit
    bank["cube_hit"] = overlay(
        (tone("triangle", 260, 0.16, f_end=70, vol=0.9, a=0.001, d=0.08, s=0.4, r=0.06), 0),
        (_noise(0.07, 3000, 0.45, d=0.03, s=0.2, r=0.03, seed=2), 0),
        (tone("square", 150, 0.06, f_end=90, duty=0.5, vol=0.25), 0),
    )

    # Apparition d'objet : petit pop scintillant
    bank["spawn"] = concat(
        tone("square", 600, 0.03, f_end=1400, duty=0.5, vol=0.4, a=0.001, r=0.01),
        arpeggio([note("C7"), note("G6"), note("E7"), note("C7")], 0.03, "square", 0.3, 0.125),
    )

    # Jingles de ramassage (un par objet)
    bank["pickup_gun"] = _jingle(["E5", "G5", "B5", "E6"], 0.05, duty=0.25, vol=0.45, bass=["E3", "B3"])
    bank["pickup_brush"] = _jingle(["C5", "E5", "G5", "C6", "E6"], 0.045, duty=0.5, vol=0.42)
    bank["pickup_potion"] = _jingle(["A4", "C5", "E5", "A5", "C6", "E6"], 0.04, duty=0.125, vol=0.45)
    bank["pickup_hourglass"] = _jingle(["G5", "D6", "G5", "D6", "G6"], 0.05, wave="triangle", vol=0.6)

    # Fusil : montée de tension pendant la visée, tir, impacts
    aim_d = max(0.05, aim_duration)
    n = n_samples(aim_d)
    freq = sweep(300, 1500, n)
    trem = 0.6 + 0.4 * np.sign(np.sin(2 * np.pi * 30 * np.arange(n) / 48000))
    bank["aim"] = (osc("square", freq, n, duty=0.25) * adsr(n, 0.01, 0.01, 1.0, 0.01) * trem * 0.35).astype(np.float32)
    bank["shot"] = overlay(
        (_noise(0.18, 9000, 0.8, d=0.06, s=0.3, r=0.1, seed=3, rate_end=1500), 0),
        (tone("square", 1400, 0.12, f_end=180, duty=0.5, vol=0.5, a=0.001, d=0.04, s=0.5, r=0.06), 0),
    )
    bank["bullet_hit"] = overlay(
        (_noise(0.28, 2500, 0.9, d=0.1, s=0.3, r=0.15, seed=4, rate_end=600), 0),
        (tone("triangle", 200, 0.25, f_end=50, vol=1.0, a=0.001, d=0.1, s=0.4, r=0.1), 0),
        (tone("square", 900, 0.08, f_end=300, duty=0.25, vol=0.3), 0),
    )
    bank["splat"] = overlay(
        (lowpass(_noise(0.3, 6000, 1.0, d=0.08, s=0.25, r=0.18, seed=5, rate_end=800), 6), 0),
        (tone("triangle", 140, 0.18, f_end=60, vol=0.7, a=0.001, d=0.08, s=0.3, r=0.08), 0),
    )

    # Étourdissement : petites étoiles qui tournent ; réveil
    stars = []
    for k in range(8):
        f = note("E6") if k % 2 == 0 else note("B6")
        stars.append(tone("triangle", f, 0.07, vol=0.55, vibrato=0.03, vib_rate=18, a=0.002, d=0.03, s=0.6, r=0.03))
    bank["stun"] = fade(concat(*stars), fade_out=0.25)
    bank["wake"] = arpeggio([note("C5"), note("G5"), note("C6")], 0.05, "square", 0.4, 0.25)

    # Gros pinceau : whoosh, impact, ralentissement
    n = n_samples(0.32)
    rate = np.concatenate([np.geomspace(800, 9000, n // 2), np.geomspace(9000, 1200, n - n // 2)])
    bank["whoosh"] = lowpass((osc("noise", rate, n, seed=6) * adsr(n, 0.08, 0.1, 0.6, 0.12) * 0.9).astype(np.float32), 3)
    bank["brush_hit"] = overlay(
        (tone("square", 520, 0.12, f_end=160, duty=0.5, vol=0.55, a=0.001, d=0.05, s=0.5, r=0.05), 0),
        (_noise(0.1, 4000, 0.5, d=0.04, s=0.2, r=0.04, seed=7), 0),
        (tone("triangle", 180, 0.15, f_end=60, vol=0.8), 0),
    )
    bank["slow"] = tone("square", 700, 0.45, f_end=140, duty=0.5, vol=0.4, a=0.005, d=0.1, s=0.7, r=0.12, vibrato=0.04, vib_rate=10)

    # Potion : grandit (montée), rétrécit (descente)
    bank["grow"] = concat(*[tone("square", semis(note("C4"), st), 0.035, duty=0.25, vol=0.45, a=0.001, r=0.005)
                            for st in (0, 7, 3, 10, 7, 14, 12, 19, 17, 24)])
    bank["shrink"] = concat(*[tone("square", semis(note("C6"), -st), 0.04, duty=0.25, vol=0.4, a=0.001, r=0.005)
                              for st in (0, 5, 3, 8, 7, 12, 10, 17)])

    # Sablier : +3s
    bank["time_plus"] = overlay(
        (concat(tone("square", note("B5"), 0.08, duty=0.5, vol=0.5), tone("square", note("E6"), 0.25, duty=0.5, vol=0.5, r=0.15)), 0),
        (concat(silence(0.08), arpeggio([note("E6"), note("G#6"), note("B6"), note("E7")], 0.035, "square", 0.25, 0.125)), 0),
    )

    # Compte à rebours
    bank["count"] = tone("square", note("A5"), 0.16, duty=0.5, vol=0.55, a=0.002, d=0.05, s=0.6, r=0.05)
    bank["go"] = overlay(
        (tone("square", note("A6"), 0.55, duty=0.5, vol=0.5, a=0.002, d=0.1, s=0.6, r=0.25), 0),
        (tone("square", note("E6"), 0.55, duty=0.25, vol=0.35, a=0.002, d=0.1, s=0.6, r=0.25), 0),
        (tone("triangle", note("A3"), 0.55, vol=0.8, r=0.25), 0),
    )

    # Tic-tac des dernières secondes
    bank["tick"] = overlay((tone("square", 2000, 0.025, duty=0.5, vol=0.5, a=0.0005, d=0.01, s=0.3, r=0.01), 0),
                           (_noise(0.02, 12000, 0.3, seed=8), 0))
    bank["tock"] = overlay((tone("square", 1300, 0.03, duty=0.5, vol=0.5, a=0.0005, d=0.01, s=0.3, r=0.01), 0),
                           (_noise(0.02, 8000, 0.3, seed=9), 0))

    # Fin : buzzer, victoire, égalité
    bank["buzzer"] = (overlay((tone("saw", 110, 0.8, vol=0.45, a=0.005, d=0.1, s=0.9, r=0.1), 0),
                              (tone("saw", 116.5, 0.8, vol=0.45, a=0.005, d=0.1, s=0.9, r=0.1), 0),
                              (tone("square", 55, 0.8, vol=0.25, a=0.005, d=0.1, s=0.9, r=0.1), 0)))
    lead = concat(*[tone("square", note(nm), dur, duty=0.5, vol=0.42, a=0.003, d=0.05, s=0.7, r=0.04)
                    for nm, dur in [("G5", 0.12), ("C6", 0.12), ("E6", 0.12), ("G6", 0.24), ("E6", 0.12),
                                    ("G6", 0.6)]])
    harmony = concat(*[tone("square", note(nm), dur, duty=0.25, vol=0.22, a=0.003, d=0.05, s=0.7, r=0.04)
                       for nm, dur in [("E5", 0.12), ("G5", 0.12), ("C6", 0.12), ("E6", 0.24), ("C6", 0.12),
                                       ("E6", 0.6)]])
    bass = concat(*[tone("triangle", note(nm), dur, vol=0.7, r=0.04)
                    for nm, dur in [("C3", 0.36), ("G3", 0.36), ("C4", 0.6)]])
    fanfare = overlay((lead, 0), (harmony, 0), (bass, 0))
    sparkle = arpeggio([note(x) for x in ("C7", "E7", "G7", "C8") * 3], 0.03, "square", 0.15, 0.125)
    bank["victory"] = overlay((fanfare, 0), (sparkle, 1.32))
    bank["draw"] = overlay(
        (concat(*[tone("square", note(nm), 0.3, duty=0.5, vol=0.4, vibrato=0.02, r=0.08)
                  for nm in ("E5", "D#5", "D5")], tone("square", note("C#5"), 0.8, duty=0.5, vol=0.4, vibrato=0.04, r=0.3)), 0),
        (concat(*[tone("triangle", note(nm), 0.3, vol=0.6) for nm in ("A2", "G#2", "G2")], tone("triangle", note("F#2"), 0.8, vol=0.6, r=0.3)), 0),
    )

    # Nouveaux objets
    bank["pickup_bomb"] = _jingle(["C4", "G3", "C4", "F#4"], 0.06, duty=0.5, vol=0.45, bass=["C2", "C2"])
    bank["pickup_roller"] = _jingle(["D5", "F#5", "A5", "D6", "A5", "D6"], 0.04, duty=0.25, vol=0.42)
    bank["pickup_bucket"] = _jingle(["C5", "E5", "G5", "B5", "D6", "F#6", "A6"], 0.03, duty=0.125, vol=0.45)
    bank["pickup_ice"] = _jingle(["E6", "B6", "E7", "B6"], 0.05, wave="triangle", vol=0.6)
    bank["pickup_magnet"] = _jingle(["G4", "D5", "G4", "D5", "G5"], 0.05, duty=0.25, vol=0.42)
    bank["bomb_drop"] = tone("triangle", 320, 0.1, f_end=110, vol=0.8, a=0.001, d=0.05, s=0.4, r=0.04)
    bank["bomb_tick"] = tone("square", 1800, 0.03, duty=0.5, vol=0.4, a=0.0005, d=0.01, s=0.5, r=0.01)
    bank["explosion"] = overlay(
        (lowpass(_noise(0.75, 3500, 1.0, d=0.15, s=0.35, r=0.45, seed=12, rate_end=180), 4), 0),
        (tone("triangle", 130, 0.55, f_end=32, vol=1.0, a=0.001, d=0.2, s=0.4, r=0.25), 0),
        (tone("square", 90, 0.25, f_end=40, duty=0.5, vol=0.3), 0),
    )
    bank["roller_end"] = tone("square", 600, 0.12, f_end=300, duty=0.25, vol=0.35)
    n = n_samples(0.6)
    bank["wave"] = overlay(
        (lowpass((osc("noise", np.geomspace(1500, 10000, n), n, seed=13) * adsr(n, 0.05, 0.1, 0.6, 0.3) * 0.6)
                 .astype(np.float32), 3), 0),
        (arpeggio([note(x) for x in ("C5", "E5", "G5", "C6", "E6", "G6", "C7", "E7")], 0.03, "square", 0.25, 0.125), 0.05),
    )
    bank["freeze"] = overlay(
        (arpeggio([note(x) for x in ("E7", "B6", "G#6", "E6", "B5", "G#5")], 0.045, "triangle", 0.6), 0),
        (lowpass(_noise(0.3, 14000, 0.35, d=0.1, s=0.3, r=0.15, seed=14), 2), 0),
    )
    bank["thaw"] = overlay(
        (_noise(0.08, 9000, 0.6, d=0.03, s=0.2, r=0.04, seed=15), 0),
        (tone("square", 800, 0.1, f_end=1600, duty=0.25, vol=0.35), 0.02),
    )
    bank["pickup_boots"] = overlay(
        (_jingle(["C5", "E5", "G5", "C6", "E6", "G6", "C7"], 0.025, duty=0.25, vol=0.42), 0),
        (_noise(0.2, 6000, 0.25, d=0.05, s=0.4, r=0.1, seed=16, rate_end=14000), 0.05),
    )
    bank["boots_end"] = tone("square", 900, 0.15, f_end=350, duty=0.25, vol=0.35)
    bank["speed_up"] = overlay(
        (concat(*[tone("square", note(x), 0.06, duty=0.5, vol=0.4, a=0.002, r=0.01)
                  for x in ("A5", "A5", "E6")], tone("square", note("A6"), 0.25, duty=0.5, vol=0.4, r=0.12)), 0),
        (tone("triangle", note("A3"), 0.43, vol=0.6, r=0.12), 0),
    )
    bank["hurt"] = concat(tone("square", note("E5"), 0.06, duty=0.5, vol=0.4, a=0.001, r=0.01),
                          tone("square", note("A#4"), 0.1, duty=0.5, vol=0.4, r=0.05))
    bank["ko"] = overlay(
        (concat(*[tone("square", note(x), 0.09, duty=0.25, vol=0.4, a=0.002, r=0.02) for x in ("G5", "E5", "C5")],
                tone("square", note("G4"), 0.35, f_end=note("C4"), duty=0.25, vol=0.4, r=0.2)), 0),
        (tone("triangle", 160, 0.3, f_end=40, vol=0.9, a=0.001, d=0.1, s=0.4, r=0.15), 0),
        (_noise(0.15, 3000, 0.4, d=0.05, s=0.3, r=0.08, seed=17), 0),
    )
    # Rembobinage (teaser -> début) : glissando descendant rapide + souffle de bande
    n = n_samples(0.22)
    bank["rewind"] = overlay(
        (osc("square", np.geomspace(2400, 300, n), n, duty=0.25) * adsr(n, 0.005, 0.05, 0.7, 0.05) * 0.35, 0),
        (lowpass(_noise(0.22, 9000, 0.3, d=0.05, s=0.6, r=0.05, seed=18, rate_end=2000), 2), 0),
    )
    # Roulement de tambour qui monte (2,4 s) pendant la révélation des scores
    roll_len = 2.4
    hits = []
    t_ = 0.0
    k = 0
    while t_ < roll_len:
        level = 0.35 + 0.65 * (t_ / roll_len)
        hits.append((_noise(0.05, 7000, 0.55 * level, a=0.0005, d=0.02, s=0.3, r=0.02, seed=30 + k % 7), t_))
        t_ += 0.075 - 0.035 * (t_ / roll_len)
        k += 1
    bank["drumroll"] = overlay(*hits)
    bank["reveal_ding"] = overlay(
        (tone("square", note("E6"), 0.25, duty=0.25, vol=0.4, a=0.001, d=0.08, s=0.4, r=0.15), 0),
        (tone("triangle", note("E5"), 0.25, vol=0.5, r=0.15), 0),
    )
    bank["lead_change"] = concat(*[tone("square", note(x), 0.07, duty=0.5, vol=0.4, a=0.002, r=0.02)
                                   for x in ("C5", "G5")], tone("square", note("C6"), 0.18, duty=0.5, vol=0.4, r=0.1))
    bank["slowmo"] = overlay(
        (tone("saw", 220, 0.5, f_end=55, vol=0.4, a=0.005, d=0.1, s=0.7, r=0.2), 0),
        (lowpass(_noise(0.5, 3000, 0.3, d=0.1, s=0.5, r=0.2, seed=19, rate_end=400), 6), 0),
    )
    n = n_samples(0.16)
    bank["slash"] = overlay(
        (osc("noise", np.geomspace(16000, 2500, n), n, seed=20) * adsr(n, 0.002, 0.04, 0.5, 0.08) * 0.7, 0),
        (tone("square", 2600, 0.08, f_end=900, duty=0.125, vol=0.25), 0),
    )
    bank["pickup_heart"] = overlay(
        (_jingle(["C5", "E5", "G5", "C6", "G5", "C6", "E6"], 0.045, wave="triangle", vol=0.6), 0),
        (_jingle(["E6", "G6", "C7"], 0.06, duty=0.125, vol=0.25), 0.18),
    )
    bank["magnet"] = tone("square", 220, 0.6, duty=0.25, vol=0.35, vibrato=0.15, vib_rate=12, r=0.15)

    return {k: np.asarray(v, dtype=np.float32) for k, v in bank.items()}


def paint_bed(dur: float) -> np.ndarray:
    """Léger souffle filtré continu (son de peinture optionnel)."""
    n = n_samples(dur)
    sig = lowpass(osc("noise", 3000, n, seed=11), 24)
    return (sig * 0.35).astype(np.float32)
