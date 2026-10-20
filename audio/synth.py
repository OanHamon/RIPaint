"""Briques de base du synthé : oscillateurs, enveloppes ADSR, filtres simples.

Tous les signaux sont des tableaux numpy float32 mono, à SAMPLE_RATE Hz.
"""

import numpy as np

SAMPLE_RATE = 48000

_NOTE_INDEX = {"C": 0, "C#": 1, "DB": 1, "D": 2, "D#": 3, "EB": 3, "E": 4, "F": 5,
               "F#": 6, "GB": 6, "G": 7, "G#": 8, "AB": 8, "A": 9, "A#": 10, "BB": 10, "B": 11}


def n_samples(dur: float) -> int:
    return max(0, int(round(dur * SAMPLE_RATE)))


def midi_to_freq(m: float) -> float:
    return 440.0 * 2 ** ((m - 69) / 12)


def note(name: str) -> float:
    """'A4' -> 440.0 ; 'C#5', 'Eb3'..."""
    name = name.upper()
    letter = name[:-1]
    octave = int(name[-1])
    return midi_to_freq(12 * (octave + 1) + _NOTE_INDEX[letter])


def semis(freq: float, st: float) -> float:
    return freq * 2 ** (st / 12)


def sweep(f0: float, f1: float, n: int, curve: str = "exp") -> np.ndarray:
    if n <= 0:
        return np.zeros(0)
    if curve == "lin":
        return np.linspace(f0, f1, n)
    return np.geomspace(max(f0, 1.0), max(f1, 1.0), n)


def osc(wave: str, freq, n: int, duty: float = 0.5, seed: int = 0) -> np.ndarray:
    """Oscillateur. `freq` : scalaire ou tableau (pour les glissandos).
    wave : square, triangle, saw, sine, noise (bruit "NES" échantillonné-bloqué)."""
    if n <= 0:
        return np.zeros(0, dtype=np.float32)
    f = np.full(n, float(freq)) if np.isscalar(freq) else np.asarray(freq, dtype=np.float64)
    phase = np.cumsum(f) / SAMPLE_RATE
    frac = phase % 1.0
    if wave == "square":
        out = np.where(frac < duty, 1.0, -1.0)
    elif wave == "triangle":
        out = 1.0 - 4.0 * np.abs(frac - 0.5)
        out = np.round(out * 7.5) / 7.5  # triangle quantifié 4 bits, façon NES
    elif wave == "saw":
        out = 2.0 * frac - 1.0
    elif wave == "sine":
        out = np.sin(2 * np.pi * phase)
    elif wave == "noise":
        idx = np.floor(phase).astype(np.int64)
        rng = np.random.default_rng(seed)
        vals = rng.choice(np.array([-1.0, 1.0]), size=int(idx[-1]) + 2)
        out = vals[idx]
    else:
        raise ValueError(wave)
    return out.astype(np.float32)


def adsr(n: int, a: float = 0.005, d: float = 0.05, s: float = 0.7, r: float = 0.05) -> np.ndarray:
    """Enveloppe ADSR sur n échantillons (le relâchement occupe la fin)."""
    na, nd, nr = n_samples(a), n_samples(d), n_samples(r)
    total = na + nd + nr
    if total > n and total > 0:
        k = n / total
        na, nd, nr = int(na * k), int(nd * k), int(nr * k)
    ns = max(0, n - na - nd - nr)
    env = np.concatenate([
        np.linspace(0, 1, na, endpoint=False),
        np.linspace(1, s, nd, endpoint=False),
        np.full(ns, s),
        np.linspace(s, 0, nr),
    ])
    if len(env) < n:
        env = np.pad(env, (0, n - len(env)))
    return env[:n].astype(np.float32)


def tone(wave: str = "square", f: float = 440.0, dur: float = 0.1, f_end: float | None = None,
         vol: float = 0.5, a: float = 0.003, d: float = 0.04, s: float = 0.7, r: float = 0.04,
         duty: float = 0.5, vibrato: float = 0.0, vib_rate: float = 6.0, curve: str = "exp",
         seed: int = 0) -> np.ndarray:
    n = n_samples(dur)
    freq = sweep(f, f_end, n, curve) if f_end is not None else np.full(n, f)
    if vibrato:
        t = np.arange(n) / SAMPLE_RATE
        freq = freq * (1 + vibrato * np.sin(2 * np.pi * vib_rate * t))
    return (osc(wave, freq, n, duty, seed) * adsr(n, a, d, s, r) * vol).astype(np.float32)


def silence(dur: float) -> np.ndarray:
    return np.zeros(n_samples(dur), dtype=np.float32)


def concat(*parts) -> np.ndarray:
    return np.concatenate([np.asarray(p, dtype=np.float32) for p in parts])


def overlay(*parts_with_offsets) -> np.ndarray:
    """overlay((sig, offset_s), (sig2, offset_s2), ...) -> somme."""
    length = max(n_samples(off) + len(sig) for sig, off in parts_with_offsets)
    out = np.zeros(length, dtype=np.float32)
    for sig, off in parts_with_offsets:
        o = n_samples(off)
        out[o:o + len(sig)] += sig
    return out


def lowpass(sig: np.ndarray, k: int) -> np.ndarray:
    """Passe-bas grossier par moyenne glissante (k échantillons)."""
    if k <= 1:
        return sig
    kernel = np.ones(k, dtype=np.float32) / k
    return np.convolve(sig, kernel, mode="same").astype(np.float32)


def arpeggio(freqs, step: float, wave: str = "square", vol: float = 0.4, duty: float = 0.5,
             r: float = 0.02) -> np.ndarray:
    return concat(*[tone(wave, f, step, vol=vol, duty=duty, a=0.002, d=0.02, s=0.8, r=r) for f in freqs])


def fade(sig: np.ndarray, fade_in: float = 0.0, fade_out: float = 0.0) -> np.ndarray:
    sig = sig.copy()
    fi, fo = min(len(sig), n_samples(fade_in)), min(len(sig), n_samples(fade_out))
    if fi:
        sig[:fi] *= np.linspace(0, 1, fi)
    if fo:
        sig[-fo:] *= np.linspace(1, 0, fo)
    return sig
