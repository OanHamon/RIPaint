"""Mini-séquenceur chiptune : génère la musique de fond à partir d'une seed et d'un style.

4 voix façon NES : mélodie (carré), arpège (carré fin), basse (triangle), batterie (bruit).
Chaque style a sa gamme, son tempo, ses progressions d'accords, ses timbres, son motif de
basse et de batterie (et parfois un swing). Dans un style, tempo, tonalité, progression et
mélodie varient encore selon la seed : deux vidéos n'ont jamais exactement la même musique.

La piste alterne deux sections (A, puis B avec une autre mélodie) et se termine par une
section plus intense (charleston doublé, basse plus serrée) pendant les dernières secondes.
"""

from __future__ import annotations

import random
from dataclasses import dataclass

import numpy as np

from .synth import SAMPLE_RATE, adsr, midi_to_freq, n_samples, osc, tone

MINOR = [0, 2, 3, 5, 7, 8, 10]
MAJOR = [0, 2, 4, 5, 7, 9, 11]
DORIAN = [0, 2, 3, 5, 7, 9, 10]
MIXOLYDIAN = [0, 2, 4, 5, 7, 9, 10]
PHRYGIAN = [0, 1, 3, 5, 7, 8, 10]
HARMONIC = [0, 2, 3, 5, 7, 8, 11]

# Progressions en degrés de la gamme (0 = tonique)
MINOR_PROGS = [
    [0, 5, 2, 6],   # i VI III VII
    [0, 6, 5, 4],   # i VII VI v
    [0, 3, 6, 2],   # i iv VII III
    [5, 6, 0, 0],   # VI VII i i
    [0, 5, 3, 4],   # i VI iv v
]
MAJOR_PROGS = [[0, 4, 5, 3], [0, 3, 4, 4], [0, 5, 3, 4], [3, 4, 0, 0], [0, 1, 3, 4]]
MODAL_PROGS = [[0, 3, 0, 3], [0, 6, 0, 6], [0, 1, 0, 6], [0, 3, 6, 3]]

# Motifs rythmiques de la mélodie (1 = note, 0 = silence)
RHYTHMS = {
    "drive": [[1, 0, 1, 0, 1, 0, 0, 1, 0, 1, 1, 0, 1, 0, 0, 0],
              [1, 0, 0, 1, 0, 0, 1, 0, 1, 0, 1, 0, 1, 1, 0, 0],
              [1, 1, 0, 1, 0, 1, 0, 0, 1, 0, 0, 1, 0, 1, 0, 0]],
    "bounce": [[1, 0, 1, 1, 0, 1, 0, 0, 1, 0, 1, 1, 0, 0, 1, 0],
               [1, 0, 0, 0, 1, 0, 1, 0, 1, 0, 0, 0, 1, 1, 1, 0]],
    "sparse": [[1, 0, 0, 0, 0, 0, 1, 0, 0, 0, 1, 0, 0, 0, 0, 0],
               [1, 0, 0, 1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1, 0, 0]],
    "busy": [[1, 1, 1, 0, 1, 1, 0, 1, 1, 0, 1, 1, 1, 0, 1, 0],
             [1, 0, 1, 1, 1, 0, 1, 1, 0, 1, 1, 0, 1, 1, 1, 1]],
}


@dataclass(frozen=True)
class Style:
    key: str
    label: str                # interface (français)
    scale: tuple
    progs: tuple
    bpms: tuple
    rhythm: str
    lead: tuple               # (onde, rapport cyclique)
    bass: str                 # « eighths », « octaves », « gallop », « walk », « long », « sixteenths »
    drums: str                # « rock », « four », « half », « break », « shuffle », « none »
    swing: float = 0.0        # 0 = droit, 0.33 = ternaire
    arp: float = 0.1          # volume de l'arpège (0 = sans)
    key_center: int = 57      # tonique autour de A3


STYLES = [
    Style("battle", "chiptune bataille", tuple(MINOR), tuple(map(tuple, MINOR_PROGS)), (140, 145, 150, 155, 160),
          "drive", ("square", 0.5), "octaves", "rock"),
    Style("happy", "joyeux", tuple(MAJOR), tuple(map(tuple, MAJOR_PROGS)), (124, 128, 132, 136),
          "bounce", ("square", 0.25), "eighths", "four", key_center=60),
    Style("chill", "chill", tuple(DORIAN), tuple(map(tuple, MODAL_PROGS)), (84, 88, 92, 96),
          "sparse", ("triangle", 0.5), "long", "half", swing=0.3, arp=0.06),
    Style("boss", "boss final", tuple(HARMONIC), tuple(map(tuple, MINOR_PROGS)), (165, 170, 176),
          "busy", ("square", 0.125), "sixteenths", "rock", key_center=52),
    Style("funk", "funk", tuple(MIXOLYDIAN), tuple(map(tuple, MODAL_PROGS)), (108, 112, 116, 120),
          "bounce", ("square", 0.25), "walk", "shuffle", swing=0.2, key_center=55),
    Style("turbo", "turbo", tuple(PHRYGIAN), tuple(map(tuple, MODAL_PROGS)), (172, 176, 180),
          "drive", ("square", 0.5), "gallop", "break", arp=0.08, key_center=54),
    Style("spooky", "mystère", tuple(HARMONIC), ((0, 5, 0, 4), (0, 1, 0, 4), (0, 3, 1, 4)), (96, 100, 104),
          "sparse", ("square", 0.125), "long", "half", arp=0.12, key_center=50),
]
BY_KEY = {s.key: s for s in STYLES}
AUTO = "auto"
RANDOM = "random"
CHOICES = [(AUTO, "auto (selon le mode)"), (RANDOM, "aléatoire")] + [(s.key, s.label) for s in STYLES]
# Style « auto » : celui qui colle au mode / au format, sinon un style tiré selon la seed
MODE_STYLES = {"kaboom": "boss", "gogopaint": "happy", "blizzard": "spooky", "turbo": "turbo",
               "titans": "boss", "lootrain": "funk", "escalation": "battle", "suddendeath": "boss"}
FORMAT_STYLES = {"combat": "boss", "duel": "turbo", "royale": "battle", "sprint": "turbo"}


def resolve_style(seed: int, settings, mode=None, fmt=None) -> str:
    key = getattr(settings, "music_style", AUTO)
    if key in BY_KEY:
        return key
    rng = random.Random(seed * 5023 + 71)
    if key == AUTO:
        if mode is not None and mode.key in MODE_STYLES and rng.random() < 0.7:
            return MODE_STYLES[mode.key]
        if fmt is not None and fmt.key in FORMAT_STYLES and rng.random() < 0.7:
            return FORMAT_STYLES[fmt.key]
    return rng.choice(STYLES).key


def _degree_to_semitone(scale, deg: int) -> int:
    return scale[deg % 7] + 12 * (deg // 7)


def _chord(scale, root_deg: int) -> list[int]:
    return [_degree_to_semitone(scale, root_deg + k) for k in (0, 2, 4)]


def _place(buf: np.ndarray, sig: np.ndarray, start: int):
    end = min(len(buf), start + len(sig))
    if end > start:
        buf[start:end] += sig[:end - start]


def _drum_kit():
    kick = tone("triangle", 160, 0.09, f_end=45, vol=1.0, a=0.001, d=0.05, s=0.3, r=0.03)
    n = n_samples(0.08)
    snare = (osc("noise", 7000, n, seed=21) * adsr(n, 0.001, 0.03, 0.3, 0.04)).astype(np.float32)
    n = n_samples(0.025)
    hat = (osc("noise", 16000, n, seed=22) * adsr(n, 0.0005, 0.01, 0.2, 0.01)).astype(np.float32)
    return kick, snare, hat


def _section(style: Style, rng: random.Random, key: int, prog, step: float, bars: int, intense: bool,
             melody_seed: int) -> np.ndarray:
    step_n = n_samples(step)
    swing_n = int(step_n * style.swing * 0.5)
    total = step_n * 16 * bars + swing_n + 1
    lead = np.zeros(total, dtype=np.float32)
    arp = np.zeros(total, dtype=np.float32)
    bass = np.zeros(total, dtype=np.float32)
    drums = np.zeros(total, dtype=np.float32)
    kick, snare, hat = _drum_kit()
    mel = random.Random(melody_seed)
    rhythm = mel.choice(RHYTHMS[style.rhythm])
    melody_deg = 7 + mel.randint(0, 4)
    wave, duty = style.lead
    scale = style.scale

    for bar in range(bars):
        root_deg = prog[bar % len(prog)]
        chord = _chord(scale, root_deg)
        bar_start = bar * 16 * step_n
        variation = bar % 4 == 3 or intense
        for s in range(16):
            t0 = bar_start + s * step_n + (swing_n if s % 2 == 1 else 0)
            # Basse
            b = style.bass
            semi = None
            if b == "octaves" and s % 2 == 0:
                semi = chord[0] + (12 if s % 4 == 2 else 0)
            elif b == "eighths" and s % 2 == 0:
                semi = chord[0] if s % 8 < 4 else chord[2] - 12
            elif b == "long" and s % 8 == 0:
                semi = chord[0]
            elif b == "walk" and s % 4 == 0:
                semi = [chord[0], chord[1], chord[2], chord[1] + 12][(s // 4) % 4]
            elif b == "gallop" and s % 4 in (0, 2, 3):
                semi = chord[0]
            elif b == "sixteenths":
                semi = chord[0] + (12 if s % 8 == 6 else 0)
            if intense and semi is None and s % 2 == 0:
                semi = chord[0]
            if semi is not None:
                length = step * (7.5 if b == "long" else 1.8 if b != "sixteenths" else 0.9)
                _place(bass, tone("triangle", midi_to_freq(key - 12 + semi), length, vol=0.55, a=0.002, d=0.02,
                                  s=0.9, r=0.02), t0)
            # Arpège
            if style.arp > 0:
                semi = chord[s % 3] + 12
                _place(arp, tone("square", midi_to_freq(key + semi), step * 0.9, vol=style.arp, duty=0.125,
                                 a=0.001, d=0.02, s=0.6, r=0.01), t0)
            # Batterie
            d = style.drums
            if d == "rock":
                if s in (0, 8) or (variation and s == 10):
                    _place(drums, kick * 0.6, t0)
                if s in (4, 12):
                    _place(drums, snare * 0.28, t0)
                if s % 2 == 0 or intense:
                    _place(drums, hat * 0.12, t0)
            elif d == "four":
                if s % 4 == 0:
                    _place(drums, kick * 0.6, t0)
                if s in (4, 12):
                    _place(drums, snare * 0.25, t0)
                if s % 4 == 2 or (intense and s % 2 == 1):
                    _place(drums, hat * 0.16, t0)
            elif d == "half":
                if s == 0 or (variation and s == 6):
                    _place(drums, kick * 0.5, t0)
                if s == 8:
                    _place(drums, snare * 0.22, t0)
                if s % 4 == 0 or (intense and s % 2 == 0):
                    _place(drums, hat * 0.1, t0)
            elif d == "break":
                if s in (0, 6, 10) or (variation and s == 14):
                    _place(drums, kick * 0.6, t0)
                if s in (4, 12):
                    _place(drums, snare * 0.3, t0)
                _place(drums, hat * (0.12 if s % 2 == 0 else 0.07), t0)
            elif d == "shuffle":
                if s in (0, 10):
                    _place(drums, kick * 0.6, t0)
                if s in (4, 12):
                    _place(drums, snare * 0.25, t0)
                if s % 2 == 0 or intense:
                    _place(drums, hat * 0.12, t0)
            # Mélodie : marche aléatoire sur les notes de l'accord / de la gamme
            if rhythm[s] and (variation or s < 12):
                if mel.random() < 0.6:
                    target = [x for x in range(melody_deg - 3, melody_deg + 4)
                              if _degree_to_semitone(scale, x) % 12 in [c % 12 for c in chord]]
                    melody_deg = mel.choice(target) if target else melody_deg
                else:
                    melody_deg += mel.choice([-1, 1])
                melody_deg = max(5, min(13, melody_deg))
                length = step * (2 if rhythm[(s + 1) % 16] == 0 else 1) * 0.95
                f = midi_to_freq(key + _degree_to_semitone(scale, melody_deg))
                vol = 0.2 if wave == "square" else 0.32
                _place(lead, tone(wave, f, length, vol=vol, duty=duty, a=0.002, d=0.04, s=0.6, r=0.02,
                                  vibrato=0.006, vib_rate=5.5), t0)

    mix = lead + arp + bass * 0.9 + drums
    return mix[:step_n * 16 * bars]


def _parts(seed: int, style_key: str):
    style = BY_KEY.get(style_key, BY_KEY["battle"])
    rng = random.Random(seed * 7919 + 17)
    bpm = rng.choice(style.bpms)
    key = style.key_center + rng.randint(-4, 4)
    prog = rng.choice(style.progs)
    prog_b = rng.choice(style.progs)
    step = 60.0 / bpm / 4  # double-croche
    return style, rng, key, prog, prog_b, step


def make_loop(seed: int, style: str = "battle") -> np.ndarray:
    """Boucle de 8 mesures (section A) : sert à l'aperçu en temps réel."""
    st, rng, key, prog, _, step = _parts(seed, style)
    mix = _section(st, rng, key, prog, step, 8, False, seed * 31 + 1)
    peak = float(np.max(np.abs(mix))) or 1.0
    return (mix / peak * 0.8).astype(np.float32)


def music_track(seed: int, dur: float, fade_out: float = 0.3, style: str = "battle",
                final_seconds: float = 8.0) -> np.ndarray:
    """A A B A … sur `dur` secondes, section intense sur les `final_seconds` dernières secondes."""
    st, rng, key, prog, prog_b, step = _parts(seed, style)
    a = _section(st, rng, key, prog, step, 8, False, seed * 31 + 1)
    b = _section(st, rng, key, prog_b, step, 8, False, seed * 31 + 2)
    fin = _section(st, rng, key, prog, step, 8, True, seed * 31 + 3)
    n = n_samples(dur)
    bar = len(a) // 8
    # la section finale commence sur une mesure entière
    start_fin = max(0, (n - n_samples(final_seconds)) // bar * bar)
    order = [a, a, b, a]
    parts, length, k = [], 0, 0
    while length < start_fin:
        parts.append(order[k % len(order)])
        length += len(parts[-1])
        k += 1
    body = np.concatenate(parts)[:start_fin] if parts else np.zeros(0, dtype=np.float32)
    n_fin = n - len(body)
    reps = n_fin // len(fin) + 1
    track = np.concatenate([body, np.tile(fin, reps)[:n_fin]]).astype(np.float32)
    peak = float(np.max(np.abs(track))) or 1.0
    track = track / peak * 0.8
    fo = min(n, n_samples(fade_out))
    if fo:
        track[-fo:] *= np.linspace(1, 0, fo)
    return track.astype(np.float32)


__all__ = ["make_loop", "music_track", "resolve_style", "STYLES", "SAMPLE_RATE"]
