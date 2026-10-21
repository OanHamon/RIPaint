"""Aperçu temps réel dans une fenêtre pygame, avec le son, sans rien enregistrer.

Touches : ESPACE pause · R nouvelle partie · S zones de sécurité · ÉCHAP quitter.
"""

import time

import pygame

from audio.mixer import LivePlayer
from audio.sfx import build_bank
from audio.synth import SAMPLE_RATE
from engine8bit.display import FPS, LOGICAL_H, LOGICAL_W, fit_window_scale
from game.battle import Battle
from game.render import Renderer
from game.settings import Settings

from .exporter import random_seed


def run_preview(settings: Settings, seed: int | None = None) -> None:
    pygame.mixer.pre_init(SAMPLE_RATE, -16, 2, 512)
    pygame.init()
    info = pygame.display.Info()
    scale = fit_window_scale(info.current_h)
    window = pygame.display.set_mode((LOGICAL_W * scale, LOGICAL_H * scale))
    surf = pygame.Surface((LOGICAL_W, LOGICAL_H))
    bank = build_bank(settings.aim_duration)
    clock = pygame.time.Clock()
    show_safe = False

    def new_game(s):
        b = Battle(s, settings)
        music_vol = settings.music_volume if settings.music_on() else 0.0
        player = LivePlayer(bank, s, settings.master_volume, music_vol, settings.paint_sound, b.music_style)
        pygame.display.set_caption(f"Aperçu - seed {s}   [ESPACE pause | R nouvelle partie | S zones | ÉCHAP quitter]")
        return b, Renderer(b), player, 0

    current_seed = seed if seed is not None else random_seed()
    battle, renderer, player, ev_index = new_game(current_seed)
    paused = False
    acc = 0.0
    last = time.perf_counter()
    running = True
    while running:
        for e in pygame.event.get():
            if e.type == pygame.QUIT:
                running = False
            elif e.type == pygame.KEYDOWN:
                if e.key == pygame.K_ESCAPE:
                    running = False
                elif e.key == pygame.K_SPACE:
                    paused = not paused
                    if paused:
                        pygame.mixer.pause()
                    else:
                        pygame.mixer.unpause()
                elif e.key == pygame.K_r:
                    player.stop()
                    current_seed = random_seed()
                    battle, renderer, player, ev_index = new_game(current_seed)
                    paused = False
                elif e.key == pygame.K_s:
                    show_safe = not show_safe
        now = time.perf_counter()
        if not paused:
            acc += now - last
        last = now
        steps = 0
        while acc >= 1 / FPS and steps < 4 and not battle.done:
            battle.step()
            acc -= 1 / FPS
            steps += 1
            # sons dont l'image est atteinte (les événements peuvent être programmés dans le futur)
            pending = sorted(battle.events[ev_index:], key=lambda ev: ev.frame)
            due = [ev for ev in pending if ev.frame <= battle.frame]
            battle.events[ev_index:] = [ev for ev in pending if ev.frame > battle.frame]
            battle.events[ev_index:ev_index] = due
            for ev in due:
                player.handle(ev, ev.frame / FPS)
            ev_index += len(due)
        if battle.done:
            acc = 0.0
        renderer.draw(surf, show_safe)
        pygame.transform.scale(surf, window.get_size(), window)
        pygame.display.flip()
        clock.tick(FPS)
    player.stop()
    pygame.quit()
