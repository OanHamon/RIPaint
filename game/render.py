"""Dessin d'une image de la partie sur la surface logique 135x240."""

import math

import numpy as np
import pygame

from engine8bit import font, palette
from engine8bit.display import FPS, LOGICAL_H, LOGICAL_W

from . import art
from .battle import (END_FRAMES, LOOP_FRAMES, REVEAL_FRAMES, REWIND_FRAMES, TEASER_FRAMES, Battle,
                     fmt_pct)
from .items import HIT_ANIM, SPAWN_ANIM
from .layout import WALL


def _dither(color, phase=0) -> pygame.Surface:
    """Trame en damier (une case sur deux) : assombrissement 8-bit sans sortir de la palette."""
    s = pygame.Surface((LOGICAL_W, LOGICAL_H))
    s.fill((255, 0, 255))
    s.set_colorkey((255, 0, 255))
    arr = pygame.surfarray.pixels3d(s)
    xx, yy = np.meshgrid(np.arange(LOGICAL_W), np.arange(LOGICAL_H), indexing="ij")
    mask = (xx + yy + phase) % 2 == 0
    arr[mask] = color
    del arr
    return s


class Renderer:
    def __init__(self, battle: Battle):
        self.b = battle
        L = battle.layout
        self.L = L
        W, H = battle.W, battle.H
        yy, xx = np.mgrid[0:H, 0:W]
        checker = ((xx // 6) + (yy // 6)) % 2 == 0
        self.floor = np.where(checker[..., None], np.array(palette.FLOOR_A), np.array(palette.FLOOR_B)).astype(np.uint8)
        self.lut = np.array([palette.TEAMS[c.team][1] for c in battle.cubes], dtype=np.uint8)
        self.arena = pygame.Surface((W, H))
        self.background = self._make_background()
        self.obstacle_layer = self._make_obstacles()
        self.shade = _dither(palette.BLACK)

    # ---- Fond ----------------------------------------------------------------------------

    def _make_background(self) -> pygame.Surface:
        L, b = self.L, self.b
        bg = pygame.Surface((LOGICAL_W, LOGICAL_H))
        bg.fill(palette.NAVY_DARK)
        arr = pygame.surfarray.pixels3d(bg)
        xx, yy = np.meshgrid(np.arange(LOGICAL_W), np.arange(LOGICAL_H), indexing="ij")
        arr[(xx + yy) % 8 == 0] = palette.NAVY
        del arr
        x, y = L.arena_x - WALL, L.arena_y - WALL
        w, h = b.W + 2 * WALL, b.H + 2 * WALL
        pygame.draw.rect(bg, palette.BLACK, (x - 1, y - 1, w + 2, h + 2))
        pygame.draw.rect(bg, palette.GREY_LIGHT, (x, y, w, h))
        pygame.draw.rect(bg, palette.GREY, (x + 1, y + 1, w - 2, h - 2))
        # rivets aux coins
        for cx, cy in ((x, y), (x + w - 2, y), (x, y + h - 2), (x + w - 2, y + h - 2)):
            pygame.draw.rect(bg, palette.WHITE, (cx, cy, 2, 2))
        return bg

    def _make_obstacles(self) -> pygame.Surface:
        """Blocs de pierre 8-bit : contour noir, relief clair en haut à gauche, foncé en bas
        à droite, petites briques, ombre portée d'un pixel."""
        b = self.b
        layer = pygame.Surface((b.W, b.H), pygame.SRCALPHA)
        for x0, y0, x1, y1 in b.obstacles:
            w, h = x1 - x0, y1 - y0
            pygame.draw.rect(layer, palette.NAVY_DARK, (x0 + 1, y0 + 1, w, h))          # ombre
            pygame.draw.rect(layer, palette.BLACK, (x0, y0, w, h))
            pygame.draw.rect(layer, palette.GREY, (x0 + 1, y0 + 1, w - 2, h - 2))
            pygame.draw.line(layer, palette.GREY_LIGHT, (x0 + 1, y0 + 1), (x1 - 2, y0 + 1))
            pygame.draw.line(layer, palette.GREY_LIGHT, (x0 + 1, y0 + 1), (x0 + 1, y1 - 2))
            pygame.draw.line(layer, palette.GREY_DARK, (x0 + 2, y1 - 2), (x1 - 2, y1 - 2))
            pygame.draw.line(layer, palette.GREY_DARK, (x1 - 2, y0 + 2), (x1 - 2, y1 - 2))
            for yy in range(y0 + 4, y1 - 2, 4):                                          # briques
                for xx in range(x0 + 3 + (2 if (yy - y0) % 8 else 0), x1 - 2, 5):
                    layer.set_at((xx, yy), palette.GREY_DARK)
            layer.set_at((x0 + 1, y0 + 1), palette.WHITE)
        return layer

    # ---- Image complète ------------------------------------------------------------------

    def draw(self, surf: pygame.Surface, show_safe_zone: bool = False) -> None:
        b = self.b
        if b.final is not None and b.phase == "teaser" and b.frame < TEASER_FRAMES:
            self._teaser_look(surf, b.frame)
        elif b.final is not None and b.settings.teaser and b.new_outro \
                and b.frame >= b.total_frames - LOOP_FRAMES:
            # boucle : l'écran du gagnant s'efface et laisse place à l'image d'ouverture
            tmp = pygame.Surface((LOGICAL_W, LOGICAL_H))
            self._draw_normal(tmp)
            self._teaser_look(surf, 0)
            p = (b.frame - (b.total_frames - LOOP_FRAMES) + 1) / LOOP_FRAMES
            keep = int(LOGICAL_H * (1 - p))
            if keep > 0:
                surf.blit(tmp, (0, 0), (0, 0, LOGICAL_W, keep))
                pygame.draw.line(surf, palette.WHITE, (0, keep), (LOGICAL_W - 1, keep))
        else:
            self._draw_normal(surf)
            if b.final is not None and b.phase == "teaser":
                # rembobinage : une ligne balaie l'arène finale et révèle le début de la partie
                p = (b.frame - TEASER_FRAMES + 1) / REWIND_FRAMES
                tmp = pygame.Surface((LOGICAL_W, LOGICAL_H))
                self._teaser_look(tmp, 0, title=False)
                line = int(self.L.arena_y + b.H * p)
                surf.blit(tmp, (0, line), (0, line, LOGICAL_W, self.L.arena_y + b.H - line))
                for k, color in enumerate((palette.WHITE, palette.SKY, palette.MAGENTA)):
                    pygame.draw.line(surf, color, (self.L.arena_x, line + k),
                                     (self.L.arena_x + b.W - 1, line + k))
        if show_safe_zone:
            self._safe_zone(surf)

    def _draw_normal(self, surf: pygame.Surface) -> None:
        b = self.b
        surf.blit(self.background, (0, 0))
        self._arena(surf)
        self._waves(surf)
        surf.blit(self.obstacle_layer, (self.L.arena_x, self.L.arena_y))
        self._magnet_lines(surf)
        self._items(surf)
        self._bombs(surf)
        self._swipes(surf)
        self._aims(surf)
        self._bullets(surf)
        self._cubes(surf)
        self._particles(surf, 0)
        if b.impact > 0 or b.slashes:
            self._impact_fx(surf)
        if b.flash > 0 or b.slowmo > 0:
            self._slowmo_fx(surf)
        if b.phase == "teaser":
            self._hook_banner(surf)
        elif b.phase == "intro":
            self._intro(surf)
        elif b.phase == "battle":
            self._timer(surf)
            self._popups(surf)
            if b.frame - b.battle_start < 48:
                self._go(surf)
        if b.phase != "outro" or b.frame - b.battle_end < 30:
            self._scores(surf)
        if b.phase == "outro":
            self._outro(surf)
        self._particles(surf, 1)
        if b.shake > 0:
            dx, dy = ((1, 0), (-1, 1), (0, -1), (1, 1), (-1, 0), (0, 1))[b.frame % 6]
            surf.scroll(dx * b.shake_amp, dy * b.shake_amp)

    # ---- Arène ---------------------------------------------------------------------------

    def _arena(self, surf, grid=None):
        g = self.b.grid if grid is None else grid
        rgb = self.floor.copy()
        painted = g >= 0
        rgb[painted] = self.lut[g[painted]]
        pygame.surfarray.blit_array(self.arena, rgb.transpose(1, 0, 2))
        surf.blit(self.arena, (self.L.arena_x, self.L.arena_y))

    def _items(self, surf):
        b, L = self.b, self.L
        for it in b.items:
            age = b.frame - it.spawn_frame
            img = art.item_sprite(it.kind)
            ix, iy = int(round(it.x)), int(round(it.y))
            x = L.arena_x + ix - img.get_width() // 2
            y = L.arena_y + iy - img.get_height() // 2
            if age < SPAWN_ANIM:
                r = 2 + age // 3
                if r < 12:
                    pygame.draw.rect(surf, palette.WHITE, (L.arena_x + ix - r, L.arena_y + iy - r, 2 * r + 1, 2 * r + 1), 1)
                if (age // 3) % 2 == 0:
                    surf.blit(img, (x, y))
            else:
                bob = 1 if (age // 20) % 2 else 0
                surf.blit(img, (x, y - bob))

    def _waves(self, surf):
        b, L = self.b, self.L
        rainbow = (palette.RED, palette.ORANGE, palette.YELLOW, palette.GREEN, palette.BLUE, palette.PURPLE)
        for w in b.waves:
            length = b.W if w.horizontal else b.H
            a0, a1 = int(w.band - w.half), int(w.band + w.half) + 1
            for front in (w.origin - w.dist, w.origin + w.dist):
                f = int(front)
                for k in range(-1, 2):
                    pos = f + k
                    if not 0 <= pos < length:
                        continue
                    for i, across in enumerate(range(max(0, a0 - 1), a1 + 1)):
                        color = rainbow[(i + b.frame + k) % len(rainbow)]
                        if w.horizontal and across < b.H:
                            surf.set_at((L.arena_x + pos, L.arena_y + across), color)
                        elif not w.horizontal and across < b.W:
                            surf.set_at((L.arena_x + across, L.arena_y + pos), color)

    def _magnet_lines(self, surf):
        b, L = self.b, self.L
        holders = [c for c in b.cubes if c.magnet > 0]
        if not holders or b.phase != "battle":
            return
        for it in b.items:
            h = min(holders, key=lambda c: ((c.cx - it.x) ** 2 + (c.cy - it.y) ** 2, c.idx))
            dist = max(1, int(math.hypot(h.cx - it.x, h.cy - it.y)))
            for i in range(0, dist, 3):
                if (i // 3 + b.frame // 4) % 2:
                    continue
                x = L.arena_x + it.x + (h.cx - it.x) * i / dist
                y = L.arena_y + it.y + (h.cy - it.y) * i / dist
                surf.set_at((int(x), int(y)), palette.RED if (i // 3) % 2 else palette.GREY_LIGHT)

    def _bombs(self, surf):
        b, L = self.b, self.L
        for bomb in b.bombs:
            cx, cy = L.arena_x + int(bomb.x), L.arena_y + int(bomb.y)
            radius = b.settings.bomb_radius * b.cubes[bomb.owner].base_size / 11
            period = 3 if bomb.frames_left < 30 else 8
            hot = (bomb.frames_left // period) % 2 == 0
            # zone de souffle en pointillés
            if hot:
                steps = max(12, int(radius * 2 * math.pi / 3))
                for k in range(steps):
                    a = k * 2 * math.pi / steps + b.frame * 0.05
                    px, py = int(cx + math.cos(a) * radius), int(cy + math.sin(a) * radius)
                    if L.arena_x <= px < L.arena_x + b.W and L.arena_y <= py < L.arena_y + b.H:
                        surf.set_at((px, py), palette.RED)
            img = art.item_sprite("bomb")
            surf.blit(img, (cx - img.get_width() // 2, cy - img.get_height() // 2))
            if hot:
                pygame.draw.rect(surf, palette.WHITE, (cx - 2, cy - 1, 2, 2))
                surf.set_at((cx + 2, cy - 4), palette.YELLOW_LIGHT)

    def _swipes(self, surf):
        b, L = self.b, self.L
        for sw in b.swipes:
            owner = b.cubes[sw.owner]
            radius = b.settings.brush_radius * owner.size / owner.base_size
            p = min(1.0, sw.frame / sw.duration)
            a_cur = -math.pi / 2 + math.pi * p
            a_tail = max(-math.pi / 2, a_cur - math.radians(80))
            _, mid, light = palette.TEAMS[owner.team]
            steps = max(6, int(radius * (a_cur - a_tail)))
            for i in range(steps + 1):
                a = sw.theta + a_tail + (a_cur - a_tail) * i / steps
                color = palette.WHITE if i > steps * 0.6 else light
                for rr in (radius - 1, radius):
                    px = L.arena_x + owner.cx + math.cos(a) * rr
                    py = L.arena_y + owner.cy + math.sin(a) * rr
                    surf.set_at((int(px), int(py)), color)
            a = sw.theta + a_cur
            hx = int(L.arena_x + owner.cx + math.cos(a) * radius)
            hy = int(L.arena_y + owner.cy + math.sin(a) * radius)
            pygame.draw.rect(surf, palette.BLACK, (hx - 2, hy - 2, 5, 5))
            pygame.draw.rect(surf, mid, (hx - 1, hy - 1, 3, 3))

    def _aims(self, surf):
        b, L = self.b, self.L
        for aim in b.aims:
            s, t = b.cubes[aim.shooter], b.cubes[aim.target]
            x0, y0 = L.arena_x + s.cx, L.arena_y + s.cy
            x1, y1 = L.arena_x + t.cx, L.arena_y + t.cy
            dist = max(1, int(math.hypot(x1 - x0, y1 - y0)))
            light = palette.TEAMS[s.team][2]
            for i in range(int(s.half) + 1, dist):
                if (i + b.frame) % 4 < 2:
                    x = int(x0 + (x1 - x0) * i / dist)
                    y = int(y0 + (y1 - y0) * i / dist)
                    surf.set_at((x, y), light if (b.frame // 3) % 2 else palette.WHITE)
            # viseur sur la cible
            r = int(t.half) + 2
            cx, cy = int(x1), int(y1)
            for sx, sy in ((-1, -1), (1, -1), (-1, 1), (1, 1)):
                px, py = cx + sx * r, cy + sy * r
                surf.set_at((px, py), palette.RED)
                surf.set_at((px - sx, py), palette.RED)
                surf.set_at((px, py - sy), palette.RED)

    def _bullets(self, surf):
        b, L = self.b, self.L
        for bl in b.bullets:
            light = palette.TEAMS[b.cubes[bl.owner].team][2]
            for i, (tx, ty) in enumerate(bl.trail[:-1]):
                surf.set_at((int(L.arena_x + tx), int(L.arena_y + ty)), light if i % 2 else palette.WHITE)
            x, y = int(L.arena_x + bl.x), int(L.arena_y + bl.y)
            pygame.draw.rect(surf, palette.BLACK, (x - 1, y - 1, 4, 4))
            pygame.draw.rect(surf, palette.WHITE, (x, y, 2, 2))

    def _cubes(self, surf):
        b, L = self.b, self.L
        leader = b.leader if (b.phase == "battle" and not b.scores_hidden()) else None
        jumping = b.crown_jump is not None and b.frame - b.crown_jump[2] < 15 and leader is not None
        waiting = b.phase in ("teaser", "intro")
        for c in sorted(b.cubes, key=lambda c: (c.size, c.idx)):
            x0, y0, _, _ = c.rect()
            x, y = L.arena_x + x0, L.arena_y + y0
            if waiting and ((b.frame // 5) + c.idx) % 3 == 0:
                y -= 1                                       # les cubes trépignent avant le départ
            moving = b.phase == "battle" and c.active
            look = (c.dx, c.dy) if moving else (0.0, 0.0)
            flash = c.stun > 0 and c.stun > round(b.settings.stun_duration * FPS) - 8
            if c.boots > 0 and moving:
                # traînée de « fantômes » derrière un cube chaussé de bottes
                for k, gap in enumerate((c.size * 0.9, c.size * 0.45)):
                    gx, gy = int(x - c.dx * gap), int(y - c.dy * gap)
                    color = palette.TEAMS[c.team][1] if k else palette.TEAMS[c.team][2]
                    if (b.frame + k) % 2 == 0:
                        pygame.draw.rect(surf, color, (gx, gy, c.size, c.size), 1)
            blink = c.invuln > 0 and not c.dead and c.hit_anim == 0 and (b.frame // 3) % 2 == 1
            if not blink:                                   # clignotement d'invulnérabilité
                self._draw_cube(surf, c, x, y, look, flash)
            self._lives(surf, c, x, y)
            if c.big and (b.frame // 6) % 2 == 0:
                pygame.draw.rect(surf, palette.MAGENTA, (x - 1, y - 1, c.size + 2, c.size + 2), 1)
            top_y = y - 1
            if c.stun > 0:
                st = art.star()
                for k in range(3):
                    a = b.frame * 0.18 + k * 2 * math.pi / 3
                    sx = x + c.size / 2 + math.cos(a) * (c.half + 2) - 1
                    sy = top_y - 3 + math.sin(a) * 1.5 - 1
                    surf.blit(st, (int(sx), int(sy)))
                top_y -= 5
            if c.slow > 0 and (b.frame // 8) % 2 == 0:
                icon = art.slow_icon()
                surf.blit(icon, (x + c.size // 2 - 2, top_y - 4))
                top_y -= 5
            if c.roller > 0 and (c.roller > 60 or (b.frame // 6) % 2 == 0):
                icon = art.roller_icon()
                surf.blit(icon, (x + c.size // 2 - 2, top_y - 4))
                top_y -= 5
            if c.magnet > 0 and (c.magnet > 60 or (b.frame // 6) % 2 == 0):
                icon = art.magnet_icon()
                surf.blit(icon, (x + c.size // 2 - 1, top_y - 3))
                top_y -= 4
            if leader == c.idx and not c.dead and not jumping:
                cr = art.crown()
                surf.blit(cr, (x + c.size // 2 - 2, top_y - 3))
            if waiting and b.nicknames[c.idx]:
                font.draw(surf, b.nicknames[c.idx], x + c.size // 2, max(L.arena_y + 1, y - 10),
                          palette.TEAMS[c.team][2], 1, "center")
        if jumping:
            # la couronne saute de l'ancien leader au nouveau (arc de cercle)
            old, new, start = b.crown_jump
            k = (b.frame - start) / 15
            a, n = b.cubes[old], b.cubes[new]
            x = L.arena_x + a.cx + (n.cx - a.cx) * k
            y = L.arena_y + a.cy - a.half + (n.cy - n.half - a.cy + a.half) * k - 14 * math.sin(math.pi * k)
            surf.blit(art.crown(), (int(x) - 2, int(y) - 6))

    def _lives(self, surf, c, x, y):
        """Petits points de vie sous le cube (au-dessus s'il touche le bas de l'arène)."""
        total = max(self.b.start_lives, c.lives)
        if self.b.settings.lives <= 0 or c.dead:
            return
        L = self.L
        w = total * 3 + 1
        px = x + c.size // 2 - w // 2
        py = y + c.size + 1
        if py + 4 > L.arena_y + self.b.H:
            py = y - 5
        pygame.draw.rect(surf, palette.BLACK, (px, py, w, 4))
        for k in range(total):
            if k == c.lives - 1 and c.life_gained > 0:
                color = palette.GREEN_LIGHT if (c.life_gained // 4) % 2 == 0 else palette.WHITE
            elif k < c.lives:
                color = palette.WHITE
            elif k == c.lives and c.life_lost > 0:
                color = palette.RED if (c.life_lost // 4) % 2 == 0 else palette.WHITE
            else:
                color = palette.GREY_DARK
            pygame.draw.rect(surf, color, (px + 1 + k * 3, py + 1, 2, 2))

    def _draw_cube(self, surf, c, x, y, look, flash):
        """Dessine un cube ; s'il vient d'être touché par l'objet d'un autre cube :
        écrasement/étirement élastique, flash blanc, yeux plissés et anneau d'impact."""
        if c.hit_anim <= 0:
            # K.O. : clignote entre sa couleur et le gris pendant qu'il rapetisse, puis reste gris
            grey = c.dead and self.b.settings.death_shrink and not (c.death_anim < 18 and (c.death_anim // 3) % 2 == 0)
            art.draw_cube(surf, x, y, c.size, c.team, look, stunned=c.stun > 0 or c.dead, flash=flash,
                          frozen=c.frozen > 0, dead=grey)
            return
        t = HIT_ANIM - c.hit_anim
        amp = 0.4 * (1 - t / HIT_ANIM) * math.cos(t * 0.75)
        w = max(3, round(c.size * (1 + amp)))
        h = max(3, round(c.size * (1 - amp)))
        tmp = pygame.Surface((c.size + 2, c.size + 2), pygame.SRCALPHA)
        art.draw_cube(tmp, 1, 1, c.size, c.team, look, stunned=c.stun > 0 or c.dead, flash=flash or t < 4,
                      frozen=c.frozen > 0, hurt=not c.dead, dead=c.dead)
        scaled = pygame.transform.scale(tmp, (w + 2, h + 2))
        cx, cy = x + c.size / 2, y + c.size / 2
        surf.blit(scaled, (round(cx - (w + 2) / 2), round(cy - (h + 2) / 2)))
        if t < 9 and t % 3 != 2:
            r = int(c.half) + 2 + t
            pygame.draw.rect(surf, palette.WHITE, (round(cx) - r, round(cy) - r, 2 * r, 2 * r), 1)

    def _particles(self, surf, layer):
        for p in self.b.particles:
            if p.layer != layer:
                continue
            if p.life < p.max_life * 0.3 and p.life % 2:
                continue
            x, y = int(p.x), int(p.y)
            if 0 <= x < LOGICAL_W and 0 <= y < LOGICAL_H:
                if layer == 1:
                    surf.fill(p.color, (x, y, 2, 2))
                else:
                    surf.set_at((x, y), p.color)

    # ---- HUD -----------------------------------------------------------------------------

    def _timer(self, surf):
        b, L = self.b, self.L
        rem = b.remaining_seconds()
        secs = math.ceil(rem - 1e-9)
        text = f"{secs // 60}:{secs % 60:02d}" if secs >= 60 else f"{secs}"
        color = palette.WHITE
        if rem <= 5:
            color = palette.RED if (b.frame // 10) % 2 == 0 else palette.YELLOW
        if b.timer_flash > 0:
            color = palette.GREEN_LIGHT if (b.timer_flash // 5) % 2 == 0 else palette.WHITE
        font.draw(surf, text, L.center_x, L.hud_y, color, 2, "center")
        for start in b.bonus_anims:
            age = b.frame - start
            if 0 <= age < 60 and not (age > 40 and age % 4 < 2):
                y = L.hud_y + 4 - age // 6
                w = font.text_width(text, 2)
                font.draw(surf, f"+{b.settings.hourglass_bonus:g}S", L.center_x + w // 2 + 2, max(L.safe.top, y),
                          palette.GREEN_LIGHT, 1, "left")

    def _popups(self, surf):
        b, L = self.b, self.L
        active = [p for p in b.popups if b.frame - p.start < p.duration][-2:]
        top_y = L.arena_y + 3
        bottom_y = L.arena_y + b.H - 2
        for p in reversed(active):
            age = b.frame - p.start
            lines = font.wrap(p.text, b.W)
            h = len(lines) * 10
            if p.anchor == "bottom":
                bottom_y -= h
                y = bottom_y
            else:
                y = top_y
                top_y += h
            if p.duration - age < 14 and age % 4 < 2:
                continue
            dy = max(0, 4 - age) * (1 if p.anchor == "top" else -1)
            font.draw_block(surf, p.text, L.arena_x + b.W // 2, y - dy, b.W, p.color, 1)

    def _scores(self, surf):
        b, L = self.b, self.L
        x0 = L.arena_x - WALL
        w = b.W + 2 * WALL
        y = L.scores_y
        pygame.draw.rect(surf, palette.BLACK, (x0, y, w, 7))
        pygame.draw.rect(surf, palette.GREY_DARK, (x0 + 1, y + 1, w - 2, 5))
        if b.phase == "intro" and b.map_name:
            # pendant le compte à rebours : nom de la carte à la place des pourcentages (tous à 0)
            font.draw(surf, f"MAP: {b.map_name}", L.center_x, y + 9, palette.WHITE, 1, "center")
            return
        if b.scores_hidden():
            # suspense : barre brouillée et « ??% »
            for xx in range(x0 + 1, x0 + w - 1):
                if (xx + b.frame // 2) % 6 < 3:
                    pygame.draw.line(surf, palette.GREY, (xx, y + 1), (xx, y + 5))
            n = len(b.cubes)
            slot = w / n
            for c in b.cubes:
                label = "??%"
                lw = font.text_width(label) + 6
                lx = int(x0 + slot * (c.idx + 0.5) - lw / 2)
                art.draw_cube(surf, lx, y + 10, 5, c.team)
                color = palette.TEAMS[c.team][2] if (b.frame // 8 + c.idx) % 2 else palette.WHITE
                font.draw(surf, label, lx + 5, y + 9, color)
            return
        total = b.paintable
        x = x0 + 1
        inner = w - 2
        acc = 0
        for c in b.cubes:
            acc_next = acc + int(b.counts[c.idx])
            xa = x + round(inner * acc / total)
            xb = x + round(inner * acc_next / total)
            if xb > xa:
                pygame.draw.rect(surf, palette.TEAMS[c.team][1], (xa, y + 1, xb - xa, 5))
                pygame.draw.rect(surf, palette.TEAMS[c.team][2], (xa, y + 1, xb - xa, 1))
            acc = acc_next
        pcts = b.percentages()
        n = len(b.cubes)
        slot = w / n
        for c in b.cubes:
            label = f"{round(pcts[c.idx])}%"
            lw = font.text_width(label) + 6
            cx = x0 + slot * (c.idx + 0.5)
            lx = int(cx - lw / 2)
            art.draw_cube(surf, lx, y + 10, 5, c.team)
            font.draw(surf, label, lx + 5, y + 9, palette.TEAMS[c.team][2])

    # ---- Phases --------------------------------------------------------------------------

    def _hook_banner(self, surf, frame=None):
        b, L = self.b, self.L
        frame = b.frame if frame is None else frame
        bx, bw = L.arena_x - WALL, b.W + 2 * WALL          # bandeau aligné sur l'arène
        lines = font.wrap(b.hook, bw - 2)
        h = len(lines) * 10 + 2
        pygame.draw.rect(surf, palette.BLACK, (bx, L.hud_y - 1, bw, h + 1))
        pygame.draw.rect(surf, palette.YELLOW, (bx, L.hud_y - 1, bw, h + 1), 1)
        color = palette.YELLOW_LIGHT if (frame // 30) % 2 == 0 else palette.WHITE
        for i, line in enumerate(lines):
            font.draw(surf, line, L.center_x, L.hud_y + 1 + i * 10, color, 1, "center")

    def _intro(self, surf):
        b, L = self.b, self.L
        self._hook_banner(surf)
        remaining = b.battle_start - b.frame
        n = math.ceil(remaining / FPS)
        age = FPS - (remaining - (n - 1) * FPS)
        scale = 7 if age < 5 else 6
        cy = L.arena_y + b.H // 2 - (7 * scale) // 2
        font.draw(surf, str(n), L.arena_x + b.W // 2, cy, palette.YELLOW_LIGHT, scale, "center")
        if b.mode is not None:
            # nom du mode sous le compte à rebours (sur deux lignes s'il est long)
            lines = font.wrap(b.mode.name, b.W, 2)
            y = L.arena_y + b.H // 2 + 28
            band = (L.arena_x, y - 3, b.W, len(lines) * 16 + 5)       # bandeau, comme l'accroche
            pygame.draw.rect(surf, palette.BLACK, band)
            pygame.draw.line(surf, b.mode.color, (band[0], band[1]), (band[0] + band[2] - 1, band[1]))
            pygame.draw.line(surf, b.mode.color, (band[0], band[1] + band[3] - 1),
                             (band[0] + band[2] - 1, band[1] + band[3] - 1))
            for i, line in enumerate(lines):
                font.draw(surf, line, L.arena_x + b.W // 2, y + i * 16, b.mode.color, 2, "center")

    def _teaser_look(self, surf, t, title=True):
        """Image d'ouverture : l'arène telle qu'elle sera à la fin, scores cachés, « WHO WINS? ».
        La dernière image de la vidéo est identique (t=0) : la vidéo boucle sans couture."""
        b, L = self.b, self.L
        f = b.final
        surf.blit(self.background, (0, 0))
        self._arena(surf, f["grid"])
        surf.blit(self.obstacle_layer, (L.arena_x, L.arena_y))
        for c, (cx, cy, size, dead) in sorted(zip(b.cubes, f["cubes"]), key=lambda z: (z[1][2], z[0].idx)):
            x = L.arena_x + int(round(cx - size / 2))
            y = L.arena_y + int(round(cy - size / 2))
            art.draw_cube(surf, x, y, size, c.team, stunned=dead, dead=dead)
        self._hook_banner(surf, frame=t)
        x0, w, y = L.arena_x - WALL, b.W + 2 * WALL, L.scores_y
        pygame.draw.rect(surf, palette.BLACK, (x0, y, w, 7))
        pygame.draw.rect(surf, palette.GREY_DARK, (x0 + 1, y + 1, w - 2, 5))
        slot = w / len(b.cubes)
        for c in b.cubes:
            lw = font.text_width("??%") + 6
            lx = int(x0 + slot * (c.idx + 0.5) - lw / 2)
            art.draw_cube(surf, lx, y + 10, 5, c.team)
            font.draw(surf, "??%", lx + 5, y + 9, palette.TEAMS[c.team][2])
        if title and (t // 8) % 2 == 0:
            cy = L.arena_y + b.H // 2 - 26
            pygame.draw.rect(surf, palette.BLACK, (L.arena_x + 3, cy - 4, b.W - 6, 58))
            pygame.draw.rect(surf, palette.YELLOW, (L.arena_x + 3, cy - 4, b.W - 6, 58), 1)
            font.draw(surf, "WHO", L.center_x, cy, palette.YELLOW_LIGHT, 3, "center")
            font.draw(surf, "WINS?", L.center_x, cy + 26, palette.YELLOW_LIGHT, 3, "center")

    def _impact_fx(self, surf):
        """Mode escalade : images d'impact noir et blanc (façon manga) et traits de slash."""
        b, L = self.b, self.L
        invert = False
        if b.impact > 0:
            sub = surf.subsurface((L.arena_x, L.arena_y, b.W, b.H))
            arr = pygame.surfarray.pixels3d(sub)
            bright = arr.astype(np.int16).sum(axis=2) > 150       # peinture et cubes clairs -> blanc
            invert = b.impact % 2 == 0                              # alternance positif / négatif
            if invert:
                bright = ~bright
            arr[bright] = palette.WHITE
            arr[~bright] = palette.BLACK
            del arr, sub
        core, edge = (palette.BLACK, palette.WHITE) if invert else (palette.WHITE, palette.BLACK)
        for s in b.slashes:
            age = b.frame - s.start
            if age >= s.life - 3 and age % 2:
                continue                                            # le trait s'efface en clignotant
            length = s.length * min(1.0, (age + 1) / 2) * (1 - 0.3 * age / s.life)
            ca, sa = math.cos(s.angle), math.sin(s.angle)
            x0 = L.arena_x + s.x - ca * length / 2
            y0 = L.arena_y + s.y - sa * length / 2
            x1 = L.arena_x + s.x + ca * length / 2
            y1 = L.arena_y + s.y + sa * length / 2
            pygame.draw.line(surf, edge, (x0, y0), (x1, y1), 3)
            pygame.draw.line(surf, core, (x0, y0), (x1, y1), 1)

    def _slowmo_fx(self, surf):
        """Ralenti : flash blanc au déclenchement puis cadre qui pulse autour de l'arène."""
        b, L = self.b, self.L
        if b.flash > 0:
            over = pygame.Surface((b.W, b.H))
            over.fill((255, 0, 255))
            over.set_colorkey((255, 0, 255))
            arr = pygame.surfarray.pixels3d(over)
            xx, yy = np.meshgrid(np.arange(b.W), np.arange(b.H), indexing="ij")
            arr[(xx + yy) % 2 == 0] = palette.WHITE
            del arr
            surf.blit(over, (L.arena_x, L.arena_y))
        if b.slowmo > 0 and (b.frame // 3) % 2 == 0:
            pygame.draw.rect(surf, palette.WHITE, (L.arena_x - WALL, L.arena_y - WALL, b.W + 2 * WALL,
                                                   b.H + 2 * WALL), 1)

    def _panel(self, surf, border, t):
        b, L = self.b, self.L
        px, py = L.arena_x - WALL, L.safe.top + 20
        pw, ph_full = b.W + 2 * WALL, L.arena_y + b.H + WALL - py
        ph = min(ph_full, 8 + t * 24)
        pygame.draw.rect(surf, palette.BLACK, (px, py + (ph_full - ph) // 2, pw, ph))
        pygame.draw.rect(surf, border, (px, py + (ph_full - ph) // 2, pw, ph), 1)
        return px, py, pw, ph_full

    def _reveal(self, surf, t):
        """Révélation des scores : les barres montent une à une, du dernier au premier."""
        b, L = self.b, self.L
        r = b.result
        surf.blit(self.shade, (0, 0))
        px, py, pw, ph = self._panel(surf, palette.WHITE, t)
        if t < 6:
            return
        font.draw(surf, "RESULTS", L.center_x, py + 8, palette.WHITE, 2, "center")
        n = len(r.ranking)
        slot = REVEAL_FRAMES / n
        row_h = 20
        top = py + 34 + (4 - n) * row_h // 2
        best = max(rk.pct for rk in r.ranking) or 1.0
        bar_x = px + 18
        bar_w = pw - 18 - 34
        for i, rk in enumerate(r.ranking):
            j = n - 1 - i                                   # ordre de révélation : le dernier d'abord
            start = j * slot
            prog = min(1.0, max(0.0, (t - start) / (slot * 0.75)))
            y = top + i * row_h
            art.draw_cube(surf, px + 5, y, 9, rk.team)
            pygame.draw.rect(surf, palette.GREY_DARK, (bar_x, y + 2, bar_w, 5))
            w = int(bar_w * rk.pct / best * prog)
            if w > 0:
                _, mid, light = palette.TEAMS[rk.team]
                pygame.draw.rect(surf, mid, (bar_x, y + 2, w, 5))
                pygame.draw.rect(surf, light, (bar_x, y + 2, w, 1))
            if prog >= 1.0:
                winner_flash = i == 0 and (t // 4) % 2 == 0
                color = palette.WHITE if winner_flash else palette.TEAMS[rk.team][2]
                font.draw(surf, fmt_pct(rk.pct), px + pw - 2, y + 1, color, 1, "right")
            elif t >= start:
                font.draw(surf, "?", px + pw - 4, y + 1, palette.GREY_LIGHT, 1, "right")

    def _league_table(self, surf, y, cx):
        b = self.b
        lg = b.league
        font.draw(surf, f"LEAGUE DAY {lg['day']}", cx, y, palette.WHITE, 1, "center")
        y += 11
        winner_team = b.cubes[b.result.winner].team if b.result.winner is not None else None
        for k, (team, wins) in enumerate(lg["standings"][:4]):
            color = palette.TEAMS[team][2]
            if team == winner_team and (b.frame // 6) % 2 == 0:
                color = palette.WHITE
            font.draw(surf, f"{k + 1}. {team} {wins}W", cx, y, color, 1, "center")
            y += 10

    def _go(self, surf):
        b, L = self.b, self.L
        age = b.frame - b.battle_start
        if age > 36 and age % 4 < 2:
            return
        scale = 5 if age < 5 else 4
        cy = L.arena_y + b.H // 2 - (7 * scale) // 2
        font.draw(surf, "GO!", L.arena_x + b.W // 2, cy, palette.GREEN_LIGHT, scale, "center")

    def _outro(self, surf):
        b, L = self.b, self.L
        age = b.frame - b.battle_end
        cx = L.center_x
        if age < 30:
            font.draw(surf, "0", L.center_x, L.hud_y, palette.RED, 2, "center")
            if age % 6 < 4:
                font.draw(surf, "END!", L.arena_x + b.W // 2, L.arena_y + b.H // 2 - 14, palette.RED, 4, "center")
            return
        if b.new_outro and age < END_FRAMES + REVEAL_FRAMES:
            self._reveal(surf, age - END_FRAMES)
            return
        surf.blit(self.shade, (0, 0))
        r = b.result
        t = age - (END_FRAMES + REVEAL_FRAMES if b.new_outro else 30)
        # panneau noir uni (déroulé vertical rapide) pour une lisibilité parfaite
        border = palette.TEAMS[b.cubes[r.winner].team][2] if r.winner is not None else palette.WHITE
        self._panel(surf, border, t)
        show_league = b.league is not None and t >= 120
        y = L.safe.top + 12
        if r.winner is not None:
            win = b.cubes[r.winner]
            size = min(30, 6 + t * 2)
            bounce = int(abs(math.sin(t / 10)) * 3) if t > 12 else 0
            art.draw_cube(surf, cx - size // 2, y + (30 - size) // 2 - bounce, size, win.team)
            if t > 12:
                crown = pygame.transform.scale(art.crown(), (15, 9))
                surf.blit(crown, (cx - 7, y - 9 - bounce))
            y += 36
            if t >= 8:
                font.draw(surf, win.team, cx, y, palette.TEAMS[win.team][2], 2, "center")
            y += 18
            nick = b.nicknames[win.idx]
            if nick:
                if t >= 10:
                    font.draw(surf, f'"{nick}"', cx, y - 2, palette.TEAMS[win.team][2], 1, "center")
                y += 9
            if t >= 14:
                color = palette.WHITE if (t // 12) % 2 == 0 else palette.YELLOW_LIGHT
                font.draw(surf, "WINS!", cx, y, color, 2, "center")
            y += 20
            if show_league:
                self._league_table(surf, y + 1, cx)
                return
            if t >= 22:
                font.draw(surf, fmt_pct(r.ranking[0].pct), cx, y, palette.YELLOW_LIGHT, 2, "center")
            y += 20
            if r.by_items and t >= 26:
                font.draw(surf, "(MORE ITEMS)", cx, y, palette.GREY_LIGHT, 1, "center")
                y += 10
            others = r.ranking[1:]
        else:
            tied = [b.cubes[i] for i in r.tied]
            gap = 4
            size = 22 if len(tied) <= 3 else 18
            total_w = len(tied) * size + (len(tied) - 1) * gap
            for k, c in enumerate(tied):
                s = min(size, 4 + t * 2)
                art.draw_cube(surf, cx - total_w // 2 + k * (size + gap) + (size - s) // 2, y + (size - s), s, c.team)
            y += size + 6
            if t >= 8:
                font.draw(surf, "TIE!", cx, y, palette.WHITE, 2, "center")
            y += 20
            if show_league:
                self._league_table(surf, y + 1, cx)
                return
            if t >= 16:
                font.draw(surf, fmt_pct(r.ranking[0].pct), cx, y, palette.YELLOW_LIGHT, 2, "center")
            y += 20
            others = [x for x in r.ranking if x.idx not in r.tied]
        y += 2
        for k, rk in enumerate(others):
            if t >= 34 + k * 8:
                place = r.ranking.index(rk) + 1
                label = b.nicknames[rk.idx] or rk.team
                font.draw(surf, f"{place}. {label} {fmt_pct(rk.pct)}", cx, y, palette.TEAMS[rk.team][2], 1, "center")
            y += 10

    def _safe_zone(self, surf):
        L = self.L
        over = pygame.Surface((LOGICAL_W, LOGICAL_H), pygame.SRCALPHA)
        red = (255, 0, 0, 70)
        over.fill(red, (0, 0, LOGICAL_W, L.safe.top))
        over.fill(red, (0, L.safe_y1, LOGICAL_W, LOGICAL_H - L.safe_y1))
        over.fill(red, (L.safe_x1, L.safe.top, LOGICAL_W - L.safe_x1, L.safe_y1 - L.safe.top))
        surf.blit(over, (0, 0))
