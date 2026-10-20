"""Dessin d'une image de la partie sur la surface logique 135x240."""

import math

import numpy as np
import pygame

from engine8bit import font, palette
from engine8bit.display import FPS, LOGICAL_H, LOGICAL_W

from . import art
from .battle import Battle, fmt_pct
from .items import SPAWN_ANIM
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

    # ---- Image complète ------------------------------------------------------------------

    def draw(self, surf: pygame.Surface, show_safe_zone: bool = False) -> None:
        b = self.b
        surf.blit(self.background, (0, 0))
        self._arena(surf)
        self._waves(surf)
        self._magnet_lines(surf)
        self._items(surf)
        self._bombs(surf)
        self._swipes(surf)
        self._aims(surf)
        self._bullets(surf)
        self._cubes(surf)
        self._particles(surf, 0)
        if b.phase == "intro":
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
            surf.scroll(dx, dy)
        if show_safe_zone:
            self._safe_zone(surf)

    # ---- Arène ---------------------------------------------------------------------------

    def _arena(self, surf):
        g = self.b.grid
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
        leader = None
        if b.phase == "battle" and len(b.counts) and b.counts.max() > 0:
            top = b.counts.max()
            if (b.counts == top).sum() == 1:
                leader = int(b.counts.argmax())
        for c in sorted(b.cubes, key=lambda c: (c.size, c.idx)):
            x0, y0, _, _ = c.rect()
            x, y = L.arena_x + x0, L.arena_y + y0
            moving = b.phase == "battle" and c.active
            look = (c.dx, c.dy) if moving else (0.0, 0.0)
            flash = c.stun > 0 and c.stun > round(b.settings.stun_duration * FPS) - 8
            art.draw_cube(surf, x, y, c.size, c.team, look, stunned=c.stun > 0, flash=flash,
                          frozen=c.frozen > 0)
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
            if leader == c.idx:
                cr = art.crown()
                surf.blit(cr, (x + c.size // 2 - 2, top_y - 3))

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
        font.draw(surf, text, L.safe_cx, L.hud_y, color, 2, "center")
        for start in b.bonus_anims:
            age = b.frame - start
            if 0 <= age < 60 and not (age > 40 and age % 4 < 2):
                y = L.hud_y + 4 - age // 6
                w = font.text_width(text, 2)
                font.draw(surf, f"+{b.settings.hourglass_bonus:g}S", L.safe_cx + w // 2 + 2, max(L.safe.top, y),
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
        total = b.W * b.H
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

    def _intro(self, surf):
        b, L = self.b, self.L
        lines = font.wrap(b.hook, L.safe_w - 2)
        h = len(lines) * 10 + 2
        pygame.draw.rect(surf, palette.BLACK, (L.safe_x0, L.hud_y - 1, L.safe_w, h + 1))
        pygame.draw.rect(surf, palette.YELLOW, (L.safe_x0, L.hud_y - 1, L.safe_w, h + 1), 1)
        color = palette.YELLOW_LIGHT if (b.frame // 30) % 2 == 0 else palette.WHITE
        for i, line in enumerate(lines):
            font.draw(surf, line, L.safe_cx, L.hud_y + 1 + i * 10, color, 1, "center")
        remaining = b.battle_start - b.frame
        n = math.ceil(remaining / FPS)
        age = FPS - (remaining - (n - 1) * FPS)
        scale = 7 if age < 5 else 6
        cy = L.arena_y + b.H // 2 - (7 * scale) // 2
        font.draw(surf, str(n), L.arena_x + b.W // 2, cy, palette.YELLOW_LIGHT, scale, "center")

    def _go(self, surf):
        b, L = self.b, self.L
        age = b.frame - b.battle_start
        if age > 36 and age % 4 < 2:
            return
        scale = 5 if age < 5 else 4
        cy = L.arena_y + b.H // 2 - (7 * scale) // 2
        font.draw(surf, "GO !", L.arena_x + b.W // 2, cy, palette.GREEN_LIGHT, scale, "center")

    def _outro(self, surf):
        b, L = self.b, self.L
        age = b.frame - b.battle_end
        cx = L.safe_cx
        if age < 30:
            font.draw(surf, "0", L.safe_cx, L.hud_y, palette.RED, 2, "center")
            if age % 6 < 4:
                font.draw(surf, "FIN !", L.arena_x + b.W // 2, L.arena_y + b.H // 2 - 14, palette.RED, 4, "center")
            return
        surf.blit(self.shade, (0, 0))
        r = b.result
        t = age - 30
        # panneau noir uni (déroulé vertical rapide) pour une lisibilité parfaite
        border = palette.TEAMS[b.cubes[r.winner].team][2] if r.winner is not None else palette.WHITE
        px, py = L.arena_x - WALL, L.safe.top + 20
        pw, ph_full = b.W + 2 * WALL, L.arena_y + b.H + WALL - py
        ph = min(ph_full, 8 + t * 24)
        pygame.draw.rect(surf, palette.BLACK, (px, py + (ph_full - ph) // 2, pw, ph))
        pygame.draw.rect(surf, border, (px, py + (ph_full - ph) // 2, pw, ph), 1)
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
            if t >= 14:
                color = palette.WHITE if (t // 12) % 2 == 0 else palette.YELLOW_LIGHT
                font.draw(surf, "GAGNE !", cx, y, color, 2, "center")
            y += 20
            if t >= 22:
                font.draw(surf, fmt_pct(r.ranking[0].pct), cx, y, palette.YELLOW_LIGHT, 2, "center")
            y += 20
            if r.by_items and t >= 26:
                font.draw(surf, "(+ D'OBJETS)", cx, y, palette.GREY_LIGHT, 1, "center")
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
                font.draw(surf, "ÉGALITÉ !", cx, y, palette.WHITE, 2, "center")
            y += 20
            if t >= 16:
                font.draw(surf, fmt_pct(r.ranking[0].pct), cx, y, palette.YELLOW_LIGHT, 2, "center")
            y += 20
            others = [x for x in r.ranking if x.idx not in r.tied]
        y += 2
        for k, rk in enumerate(others):
            if t >= 34 + k * 8:
                place = r.ranking.index(rk) + 1
                font.draw(surf, f"{place}. {rk.team} {fmt_pct(rk.pct)}", cx, y, palette.TEAMS[rk.team][2], 1, "center")
            y += 10

    def _safe_zone(self, surf):
        L = self.L
        over = pygame.Surface((LOGICAL_W, LOGICAL_H), pygame.SRCALPHA)
        red = (255, 0, 0, 70)
        over.fill(red, (0, 0, LOGICAL_W, L.safe.top))
        over.fill(red, (0, L.safe_y1, LOGICAL_W, LOGICAL_H - L.safe_y1))
        over.fill(red, (L.safe_x1, L.safe.top, LOGICAL_W - L.safe_x1, L.safe_y1 - L.safe.top))
        surf.blit(over, (0, 0))
