"""Mixage : règles anti-cacophonie communes au rendu hors-ligne (vidéo) et au temps réel (aperçu).

- nombre de voix simultanées limité ; au-delà, seuls les sons importants passent ;
- les sons d'un même groupe joués en rafale (rebonds...) sont atténués progressivement ;
- piste finale : limiteur doux puis normalisation à -1 dBFS, puis volume général.
"""

from dataclasses import dataclass

import numpy as np

from .music import make_loop, music_track
from .sfx import META, paint_bed
from .synth import SAMPLE_RATE

MAX_VOICES = 8
IMPORTANT_PRIORITY = 7       # ces sons passent même si toutes les voix sont prises
BURST_WINDOW = 0.6           # fenêtre (s) pour compter les répétitions d'un groupe
PEAK_DBFS = -2.0             # marge pour les dépassements inter-échantillons de l'encodage AAC
MUSIC_LEVEL = 0.45           # niveau de la musique sous les bruitages (à volume musique = 100 %)
PAINT_LEVEL = 0.05
LIVE_HEADROOM = 0.55

SPECIAL = {"music_start", "music_stop", "paint_start", "paint_stop"}


@dataclass
class SoundEvent:
    frame: int
    name: str
    gain: float = 1.0


class MixPolicy:
    def __init__(self, max_voices: int = MAX_VOICES):
        self.max_voices = max_voices
        self.active: list[tuple[float, int]] = []          # (fin, priorité)
        self.history: dict[str, list[float]] = {}

    def admit(self, name: str, t: float, duration: float) -> float | None:
        """Renvoie le gain à appliquer, ou None si le son doit être ignoré."""
        meta = META.get(name)
        if meta is None:
            return None
        self.active = [(end, p) for end, p in self.active if end > t]
        recent = [x for x in self.history.get(meta.group, []) if t - x < BURST_WINDOW]
        self.history[meta.group] = recent
        gain = meta.gain
        if meta.priority < IMPORTANT_PRIORITY:
            # atténuation des sons répétitifs : -20 % par répétition récente, plancher 30 %
            gain *= max(0.3, 0.8 ** len(recent))
            if len(self.active) >= self.max_voices:
                return None
            if meta.priority <= 1 and len(recent) >= 6:
                return None
        recent.append(t)
        self.active.append((t + duration, meta.priority))
        return gain


def soft_limit(x: np.ndarray, threshold: float = 0.7) -> np.ndarray:
    a = np.abs(x)
    over = a > threshold
    y = x.copy()
    y[over] = np.sign(x[over]) * (threshold + (1 - threshold) * np.tanh((a[over] - threshold) / (1 - threshold)))
    return y


def normalize(x: np.ndarray, peak_dbfs: float = PEAK_DBFS) -> np.ndarray:
    peak = float(np.max(np.abs(x))) if len(x) else 0.0
    if peak < 1e-9:
        return x
    return (x * (10 ** (peak_dbfs / 20) / peak)).astype(np.float32)


def render_track(events: list[SoundEvent], total_frames: int, bank: dict, music_seed: int,
                 master_volume: float = 1.0, music_volume: float = 0.5, paint_sound: bool = False,
                 fps: int = 60, music_style: str = "battle") -> np.ndarray:
    """Construit la piste audio mono (float32) au sample près, synchronisée sur les images."""
    spf = SAMPLE_RATE // fps
    total = total_frames * spf
    out = np.zeros(total, dtype=np.float32)
    policy = MixPolicy()
    marks: dict[str, int] = {}
    for ev in sorted(events, key=lambda e: e.frame):
        start = ev.frame * spf
        if ev.name in SPECIAL:
            marks[ev.name] = start
            continue
        sig = bank.get(ev.name)
        if sig is None or start >= total:
            continue
        gain = policy.admit(ev.name, ev.frame / fps, len(sig) / SAMPLE_RATE)
        if gain is None:
            continue
        end = min(total, start + len(sig))
        out[start:end] += sig[:end - start] * gain * ev.gain

    if music_volume > 0 and "music_start" in marks:
        s = marks["music_start"]
        e = marks.get("music_stop", total)
        if e > s:
            track = music_track(music_seed, (e - s) / SAMPLE_RATE, style=music_style)
            out[s:e] += track[:e - s] * MUSIC_LEVEL * music_volume
    if paint_sound and "paint_start" in marks:
        s = marks["paint_start"]
        e = marks.get("paint_stop", total)
        if e > s:
            out[s:e] += paint_bed((e - s) / SAMPLE_RATE)[:e - s] * PAINT_LEVEL

    # léger adoucissement des fronts d'ondes carrées (limite les dépassements à l'encodage AAC)
    out = np.convolve(out, np.array([0.25, 0.5, 0.25], dtype=np.float32), mode="same")
    out = normalize(soft_limit(out))
    return (out * float(np.clip(master_volume, 0.0, 1.0))).astype(np.float32)


def to_int16_stereo(mono: np.ndarray) -> np.ndarray:
    pcm = np.clip(mono, -1.0, 1.0)
    pcm = (pcm * 32767).astype(np.int16)
    return np.ascontiguousarray(np.stack([pcm, pcm], axis=1))


class LivePlayer:
    """Lecture temps réel via pygame.mixer (pour l'aperçu)."""

    def __init__(self, bank: dict, music_seed: int, master_volume: float, music_volume: float,
                 paint_sound: bool = False, music_style: str = "battle"):
        import pygame
        self.pg = pygame
        self.policy = MixPolicy()
        self.master = float(np.clip(master_volume, 0, 1))
        self.music_volume = music_volume
        pygame.mixer.set_num_channels(MAX_VOICES + 6)
        pygame.mixer.set_reserved(2)
        self.music_channel = pygame.mixer.Channel(0)
        self.paint_channel = pygame.mixer.Channel(1)
        self.sounds = {k: pygame.sndarray.make_sound(to_int16_stereo(v)) for k, v in bank.items()}
        self.music = pygame.sndarray.make_sound(to_int16_stereo(make_loop(music_seed, music_style)))
        self.paint = pygame.sndarray.make_sound(to_int16_stereo(paint_bed(2.0))) if paint_sound else None

    def handle(self, ev: SoundEvent, t: float):
        if ev.name == "music_start" and self.music_volume > 0:
            self.music_channel.set_volume(MUSIC_LEVEL * self.music_volume * self.master * LIVE_HEADROOM)
            self.music_channel.play(self.music, loops=-1)
        elif ev.name == "music_stop":
            self.music_channel.fadeout(300)
        elif ev.name == "paint_start" and self.paint:
            self.paint_channel.set_volume(PAINT_LEVEL * self.master)
            self.paint_channel.play(self.paint, loops=-1)
        elif ev.name == "paint_stop":
            self.paint_channel.stop()
        else:
            snd = self.sounds.get(ev.name)
            if snd is None:
                return
            gain = self.policy.admit(ev.name, t, snd.get_length())
            if gain is None:
                return
            ch = self.pg.mixer.find_channel(META[ev.name].priority >= IMPORTANT_PRIORITY)
            if ch is not None:
                ch.set_volume(min(1.0, gain * ev.gain * self.master * LIVE_HEADROOM * 1.6))
                ch.play(snd)

    def stop(self):
        self.pg.mixer.stop()
