"""Mini-séquenceur chiptune : génère une boucle de musique de fond à partir d'une seed.

4 voix façon NES : mélodie (carré 50 %), arpège (carré 12,5 %), basse (triangle), batterie (bruit).
Tempo, tonalité, progression d'accords et mélodie varient selon la seed.
"""

import random

import numpy as np

from .synth import SAMPLE_RATE, midi_to_freq, n_samples, osc, adsr, tone

# Progressions en degrés de la gamme mineure naturelle (0 = tonique)
PROGRESSIONS = [
    [0, 5, 2, 6],   # i VI III VII
    [0, 6, 5, 4],   # i VII VI v
    [0, 3, 6, 2],   # i iv VII III
    [5, 6, 0, 0],   # VI VII i i
    [0, 5, 3, 4],   # i VI iv v
]
MINOR = [0, 2, 3, 5, 7, 8, 10]


def _degree_to_semitone(deg: int) -> int:
    return MINOR[deg % 7] + 12 * (deg // 7)


def _chord(root_deg: int) -> list[int]:
    return [_degree_to_semitone(root_deg + k) for k in (0, 2, 4)]


def _place(buf: np.ndarray, sig: np.ndarray, start: int):
    end = min(len(buf), start + len(sig))
    if end > start:
        buf[start:end] += sig[:end - start]


def make_loop(seed: int) -> np.ndarray:
    rng = random.Random(seed * 7919 + 17)
    bpm = rng.choice([128, 132, 136, 140, 144, 150])
    key = 57 + rng.randint(-4, 4)  # tonique autour de A3
    prog = rng.choice(PROGRESSIONS)
    bars = 8
    step = 60.0 / bpm / 4  # double-croche
    step_n = n_samples(step)
    total = step_n * 16 * bars
    lead = np.zeros(total, dtype=np.float32)
    arp = np.zeros(total, dtype=np.float32)
    bass = np.zeros(total, dtype=np.float32)
    drums = np.zeros(total, dtype=np.float32)

    kick = tone("triangle", 160, 0.09, f_end=45, vol=1.0, a=0.001, d=0.05, s=0.3, r=0.03)
    n = n_samples(0.08)
    snare = (osc("noise", 7000, n, seed=21) * adsr(n, 0.001, 0.03, 0.3, 0.04)).astype(np.float32)
    n = n_samples(0.025)
    hat = (osc("noise", 16000, n, seed=22) * adsr(n, 0.0005, 0.01, 0.2, 0.01)).astype(np.float32)

    # Motif rythmique de la mélodie (1 = note, 0 = silence), choisi par la seed
    rhythms = [
        [1, 0, 1, 0, 1, 0, 0, 1, 0, 1, 1, 0, 1, 0, 0, 0],
        [1, 0, 0, 1, 0, 0, 1, 0, 1, 0, 1, 0, 1, 1, 0, 0],
        [1, 1, 0, 1, 0, 1, 0, 0, 1, 0, 0, 1, 0, 1, 0, 0],
    ]
    rhythm = rng.choice(rhythms)
    melody_deg = 7 + rng.randint(0, 4)

    for bar in range(bars):
        root_deg = prog[bar % len(prog)]
        chord = _chord(root_deg)
        bar_start = bar * 16 * step_n
        variation = bar >= 4
        for s in range(16):
            t0 = bar_start + s * step_n
            # Basse : croches sur la fondamentale, octave sur les contretemps
            if s % 2 == 0:
                semi = chord[0] + (12 if s % 4 == 2 else 0)
                f = midi_to_freq(key - 12 + semi)
                _place(bass, tone("triangle", f, step * 1.8, vol=0.55, a=0.002, d=0.02, s=0.9, r=0.02), t0)
            # Arpège rapide discret
            semi = chord[s % 3] + 12
            _place(arp, tone("square", midi_to_freq(key + semi), step * 0.9, vol=0.1, duty=0.125,
                             a=0.001, d=0.02, s=0.6, r=0.01), t0)
            # Batterie
            if s in (0, 8) or (variation and s == 10):
                _place(drums, kick * 0.6, t0)
            if s in (4, 12):
                _place(drums, snare * 0.28, t0)
            if s % 2 == 0:
                _place(drums, hat * 0.12, t0)
            # Mélodie : marche aléatoire sur les notes de l'accord / de la gamme
            if rhythm[s] and (variation or s < 12):
                if rng.random() < 0.6:
                    target = [d for d in range(melody_deg - 3, melody_deg + 4)
                              if _degree_to_semitone(d) % 12 in [c % 12 for c in chord]]
                    melody_deg = rng.choice(target) if target else melody_deg
                else:
                    melody_deg += rng.choice([-1, 1])
                melody_deg = max(5, min(13, melody_deg))
                length = step * (2 if rhythm[(s + 1) % 16] == 0 else 1) * 0.95
                f = midi_to_freq(key + _degree_to_semitone(melody_deg))
                _place(lead, tone("square", f, length, vol=0.2, duty=0.5, a=0.002, d=0.04, s=0.6, r=0.02,
                                  vibrato=0.006, vib_rate=5.5), t0)

    mix = lead + arp + bass * 0.9 + drums
    peak = float(np.max(np.abs(mix))) or 1.0
    return (mix / peak * 0.8).astype(np.float32)


def music_track(seed: int, dur: float, fade_out: float = 0.3) -> np.ndarray:
    """Répète la boucle sur `dur` secondes, avec un court fondu de sortie."""
    loop = make_loop(seed)
    n = n_samples(dur)
    reps = n // len(loop) + 1
    track = np.tile(loop, reps)[:n].copy()
    fo = min(n, n_samples(fade_out))
    if fo:
        track[-fo:] *= np.linspace(1, 0, fo)
    return track


__all__ = ["make_loop", "music_track", "SAMPLE_RATE"]
