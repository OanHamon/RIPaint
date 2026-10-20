"""Objets : apparition, ramassage et effets (Fusil, Gros pinceau, Potion, Sablier, Bombe,
Rouleau, Seau arc-en-ciel, Glace, Aimant)."""

from __future__ import annotations

import math
from typing import TYPE_CHECKING

from engine8bit import palette

from . import physics
from .entities import Aim, Bomb, Bullet, Cube, Item, Swipe, Wave
from .settings import ITEM_KINDS

if TYPE_CHECKING:
    from .battle import Battle

SPAWN_ANIM = 36            # images de clignotement avant de pouvoir être ramassé
WALL_MARGIN = 9            # distance minimale au mur (centre de l'objet)
# Textes affichés dans la vidéo (en anglais)
ITEM_NAMES = {"gun": "GUN", "brush": "BRUSH", "potion": "POTION", "hourglass": "TIMER",
              "bomb": "BOMB", "roller": "ROLLER", "bucket": "RAINBOW", "ice": "ICE", "magnet": "MAGNET",
              "boots": "BOOTS"}
BOMB_KNOCKBACK = 190.0
WAVE_SPEED = 3.0           # px logiques par image
KNOCKBACK_SPEED = 150.0
RESIZE_FRAMES = 24


def nearest_opponent(b: "Battle", cube: Cube) -> Cube | None:
    others = [c for c in b.cubes if c.idx != cube.idx]
    if not others:
        return None
    return min(others, key=lambda c: ((c.cx - cube.cx) ** 2 + (c.cy - cube.cy) ** 2, c.idx))


# ---- Apparition ------------------------------------------------------------------------

def try_spawn(b: "Battle") -> None:
    s = b.settings
    if len(b.items) >= s.max_items:
        return
    weights = s.item_weights()
    if b.hourglasses_spawned >= s.max_hourglasses:
        weights["hourglass"] = 0.0
    if sum(weights.values()) <= 0:
        return
    kind = b.rng.choices(ITEM_KINDS, weights=[weights[k] for k in ITEM_KINDS])[0]
    for _ in range(80):
        x = b.rng.randint(WALL_MARGIN, b.W - WALL_MARGIN - 1)
        y = b.rng.randint(WALL_MARGIN, b.H - WALL_MARGIN - 1)
        item = Item(kind, x, y, b.frame)
        ix0, iy0, ix1, iy1 = item.rect()
        clear = True
        for c in b.cubes:
            x0, y0, x1, y1 = c.rect()
            if ix0 < x1 + 6 and ix1 > x0 - 6 and iy0 < y1 + 6 and iy1 > y0 - 6:
                clear = False
                break
        if clear:
            for other in b.items:
                ox0, oy0, ox1, oy1 = other.rect()
                if ix0 < ox1 + 3 and ix1 > ox0 - 3 and iy0 < oy1 + 3 and iy1 > oy0 - 3:
                    clear = False
                    break
        if clear:
            b.items.append(item)
            if kind == "hourglass":
                b.hourglasses_spawned += 1
            b.emit("spawn")
            b.sparkle(b.layout.arena_x + x, b.layout.arena_y + y, palette.WHITE, 8)
            return


# ---- Ramassage -------------------------------------------------------------------------

def check_pickups(b: "Battle") -> None:
    for item in list(b.items):
        if b.frame - item.spawn_frame < SPAWN_ANIM:
            continue
        ix0, iy0, ix1, iy1 = item.rect()
        for c in b.cubes:
            if not c.active:
                continue
            x0, y0, x1, y1 = c.rect()
            if ix0 + 1 < x1 and ix1 - 1 > x0 and iy0 + 1 < y1 and iy1 - 1 > y0:
                b.items.remove(item)
                pickup(b, c, item)
                break


def pickup(b: "Battle", cube: Cube, item: Item) -> None:
    s = b.settings
    cube.items += 1
    b.emit(f"pickup_{item.kind}")
    light = palette.TEAMS[cube.team][2]
    # le texte s'affiche du côté de l'arène opposé au cube, pour ne pas cacher l'action
    anchor = "bottom" if cube.cy < b.H / 2 else "top"
    b.popup(f"{cube.team}: {ITEM_NAMES[item.kind]}!", light, anchor=anchor)
    b.sparkle(b.layout.arena_x + item.x, b.layout.arena_y + item.y, light, 10)

    if item.kind == "gun":
        target = nearest_opponent(b, cube)
        if target is not None:
            frames = max(0, round(s.aim_duration * 60))
            b.aims.append(Aim(cube.idx, target.idx, frames, frames))
            if frames:
                b.emit("aim")
    elif item.kind == "brush":
        target = nearest_opponent(b, cube)
        if target is not None and (target.cx, target.cy) != (cube.cx, cube.cy):
            theta = math.atan2(target.cy - cube.cy, target.cx - cube.cx)
        else:
            theta = math.atan2(cube.dy, cube.dx)
        b.swipes.append(Swipe(cube.idx, theta))
        b.emit("whoosh")
    elif item.kind == "potion":
        cube.potion = round(s.potion_duration * 60)
        if not cube.big:
            cube.big = True
            start_resize(cube, cube.base_size * max(1, s.potion_scale))
            b.emit("grow")
    elif item.kind == "hourglass":
        bonus = round(s.hourglass_bonus * 60)
        b.battle_end += bonus
        b.hourglasses_taken += 1
        b.timer_flash = 60
        b.bonus_anims.append(b.frame)
        b.emit("time_plus")
        b.subtitle(b.frame, b.frame + 60, f"+{s.hourglass_bonus:g}S")
    elif item.kind == "bomb":
        frames = max(1, round(s.bomb_fuse * 60))
        b.bombs.append(Bomb(cube.idx, item.x, item.y, frames, frames))
        b.emit("bomb_drop")
    elif item.kind == "roller":
        cube.roller = round(s.roller_duration * 60)
    elif item.kind == "bucket":
        start_wave(b, cube)
        b.emit("wave")
    elif item.kind == "ice":
        frames = round(s.ice_duration * 60)
        for c in b.cubes:
            if c.idx != cube.idx:
                c.frozen = frames
                c.kb_x = c.kb_y = 0.0
                b.sparkle(b.layout.arena_x + c.cx, b.layout.arena_y + c.cy, palette.SKY, 10)
        b.emit("freeze")
    elif item.kind == "magnet":
        cube.magnet = round(s.magnet_duration * 60)
        b.emit("magnet")
    elif item.kind == "boots":
        cube.boots = round(s.boots_duration * 60)


def start_resize(cube: Cube, new_size: int) -> None:
    cube.resize_from = cube.size
    cube.resize_to = new_size
    cube.resize_anim = RESIZE_FRAMES


def update_resize(b: "Battle", cube: Cube) -> None:
    if cube.potion > 0:
        cube.potion -= 1
        if cube.potion == 0 and cube.big:
            cube.big = False
            start_resize(cube, cube.base_size)
            b.emit("shrink")
    if cube.resize_anim > 0:
        cube.resize_anim -= 1
        # clignotement 8-bit entre l'ancienne et la nouvelle taille (façon champignon)
        flick = (cube.resize_anim // 4) % 2 == 1
        cube.size = cube.resize_from if (flick and cube.resize_anim > 0) else cube.resize_to


# ---- Fusil -----------------------------------------------------------------------------

def update_aims(b: "Battle") -> None:
    for aim in list(b.aims):
        aim.frames_left -= 1
        if aim.frames_left > 0:
            continue
        b.aims.remove(aim)
        shooter, target = b.cubes[aim.shooter], b.cubes[aim.target]
        vx, vy = target.cx - shooter.cx, target.cy - shooter.cy
        d = math.hypot(vx, vy) or 1.0
        dx, dy = vx / d, vy / d
        start = shooter.half + 1
        b.bullets.append(Bullet(shooter.idx, shooter.cx + dx * start, shooter.cy + dy * start, dx, dy))
        b.emit("shot")
        b.sparkle(b.layout.arena_x + shooter.cx + dx * start, b.layout.arena_y + shooter.cy + dy * start,
                  palette.WHITE, 5)


def update_bullets(b: "Battle") -> None:
    speed = b.settings.bullet_speed / 60
    steps = max(1, math.ceil(speed / 0.5))
    step = speed / steps
    for bullet in b.bullets:
        if not bullet.alive:
            continue
        for _ in range(steps):
            bullet.x += bullet.dx * step
            bullet.y += bullet.dy * step
            if not (0 <= bullet.x < b.W and 0 <= bullet.y < b.H):
                bullet.x = min(max(bullet.x, 0), b.W - 1)
                bullet.y = min(max(bullet.y, 0), b.H - 1)
                b.splat(bullet.x, bullet.y, bullet.owner, 6)
                b.emit("splat")
                bullet.alive = False
                break
            ix, iy = int(bullet.x), int(bullet.y)
            physics.paint_rect(b.grid, ix - 1, iy - 1, ix + 1, iy + 1, bullet.owner)
            hit = None
            for c in b.cubes:
                if c.idx == bullet.owner:
                    continue
                if abs(bullet.x - c.cx) <= c.half + 0.5 and abs(bullet.y - c.cy) <= c.half + 0.5:
                    hit = c
                    break
            if hit is not None:
                b.splat(hit.cx, hit.cy, bullet.owner, 6 + hit.half)
                hit.stun = round(b.settings.stun_duration * 60)
                hit.kb_x = hit.kb_y = 0.0
                b.emit("bullet_hit")
                b.emit("stun", frame=b.frame + 6)
                bullet.alive = False
                break
        bullet.trail.append((bullet.x, bullet.y))
        del bullet.trail[:-6]
    b.bullets = [x for x in b.bullets if x.alive]


# ---- Gros pinceau ----------------------------------------------------------------------

def update_swipes(b: "Battle") -> None:
    s = b.settings
    for sw in list(b.swipes):
        owner = b.cubes[sw.owner]
        radius = s.brush_radius * owner.size / owner.base_size
        sw.frame += 1
        p = min(1.0, sw.frame / sw.duration)
        a_from = -math.pi / 2 + math.pi * sw.painted_upto
        a_to = -math.pi / 2 + math.pi * p
        physics.paint_sector(b.grid, owner.cx, owner.cy, radius, sw.theta, a_from - 0.02, a_to, owner.idx)
        sw.painted_upto = p
        for c in b.cubes:
            if c.idx == owner.idx or c.idx in sw.hit:
                continue
            vx, vy = c.cx - owner.cx, c.cy - owner.cy
            dist = math.hypot(vx, vy)
            if dist > radius + c.half:
                continue
            rel = (math.atan2(vy, vx) - sw.theta + math.pi) % (2 * math.pi) - math.pi
            margin = math.atan2(c.half, max(dist, 1.0))
            if -math.pi / 2 - margin <= rel <= a_to + margin:
                sw.hit.add(c.idx)
                if dist > 1e-6:
                    kx, ky = vx / dist, vy / dist
                else:
                    kx, ky = math.cos(sw.theta), math.sin(sw.theta)
                c.kb_x, c.kb_y = kx * KNOCKBACK_SPEED, ky * KNOCKBACK_SPEED
                c.slow = round(s.slow_duration * 60)
                b.emit("brush_hit")
                b.emit("slow", frame=b.frame + 8)
                b.sparkle(b.layout.arena_x + c.cx, b.layout.arena_y + c.cy, palette.TEAMS[owner.team][1], 8)
        if sw.frame >= sw.duration:
            b.swipes.remove(sw)


# ---- Bombe -----------------------------------------------------------------------------

def update_bombs(b: "Battle") -> None:
    s = b.settings
    for bomb in list(b.bombs):
        bomb.frames_left -= 1
        elapsed = bomb.total - bomb.frames_left
        if bomb.frames_left > 0:
            if elapsed >= bomb.next_tick:
                b.emit("bomb_tick")
                bomb.next_tick = elapsed + max(5, bomb.frames_left // 4)
            continue
        b.bombs.remove(bomb)
        radius = s.bomb_radius * b.cubes[bomb.owner].base_size / 11
        b.splat(bomb.x, bomb.y, bomb.owner, radius)
        for c in b.cubes:
            if c.idx == bomb.owner:
                continue
            vx, vy = c.cx - bomb.x, c.cy - bomb.y
            dist = math.hypot(vx, vy)
            if dist <= radius + c.half:
                if dist > 1e-6:
                    kx, ky = vx / dist, vy / dist
                else:
                    a = b.rng.uniform(0, 2 * math.pi)
                    kx, ky = math.cos(a), math.sin(a)
                c.kb_x, c.kb_y = kx * BOMB_KNOCKBACK, ky * BOMB_KNOCKBACK
        ax, ay = b.layout.arena_x + bomb.x, b.layout.arena_y + bomb.y
        b.sparkle(ax, ay, palette.YELLOW_LIGHT, 14)
        b.sparkle(ax, ay, palette.WHITE, 10)
        b.shake = 12
        b.emit("explosion")


# ---- Rouleau / Glace / Aimant (minuteurs par cube) ---------------------------------------

def update_cube_timers(b: "Battle", cube: Cube) -> None:
    if cube.roller > 0:
        cube.roller -= 1
        if cube.roller == 0:
            b.emit("roller_end")
    if cube.frozen > 0:
        cube.frozen -= 1
        if cube.frozen == 0:
            b.emit("thaw")
            b.sparkle(b.layout.arena_x + cube.cx, b.layout.arena_y + cube.cy, palette.WHITE, 8)
    if cube.magnet > 0:
        cube.magnet -= 1
    if cube.boots > 0:
        cube.boots -= 1
        if cube.boots == 0:
            b.emit("boots_end")


def paint_size(b: "Battle", cube: Cube) -> float:
    """Rayon de la traînée d'un cube qui a le rouleau."""
    return cube.size * b.settings.roller_width / 2


def update_magnets(b: "Battle") -> None:
    holders = [c for c in b.cubes if c.magnet > 0]
    if not holders:
        return
    step = b.settings.magnet_speed / 60
    for item in b.items:
        h = min(holders, key=lambda c: ((c.cx - item.x) ** 2 + (c.cy - item.y) ** 2, c.idx))
        vx, vy = h.cx - item.x, h.cy - item.y
        dist = math.hypot(vx, vy)
        if dist <= step:
            item.x, item.y = h.cx, h.cy
        elif dist > 0:
            item.x += vx / dist * step
            item.y += vy / dist * step


# ---- Seau arc-en-ciel ------------------------------------------------------------------

def start_wave(b: "Battle", cube: Cube) -> None:
    """La vague part du cube et traverse l'arène dans la direction (horizontale ou verticale)
    où elle recouvre le plus de peinture adverse."""
    half = max(2.0, cube.base_size * b.settings.bucket_width / 2)
    g = b.grid
    rows = g[max(0, int(cube.cy - half)):int(cube.cy + half) + 1, :]
    cols = g[:, max(0, int(cube.cx - half)):int(cube.cx + half) + 1]
    gain_h = int(((rows >= 0) & (rows != cube.idx)).sum() + (rows < 0).sum() // 2)
    gain_v = int(((cols >= 0) & (cols != cube.idx)).sum() + (cols < 0).sum() // 2)
    horizontal = gain_h >= gain_v
    if horizontal:
        b.waves.append(Wave(cube.idx, True, cube.cy, cube.cx, half))
    else:
        b.waves.append(Wave(cube.idx, False, cube.cx, cube.cy, half))


def update_waves(b: "Battle") -> None:
    for w in list(b.waves):
        length = b.W if w.horizontal else b.H
        d0, d1 = w.dist, w.dist + WAVE_SPEED
        w.dist = d1
        a0, a1 = int(w.band - w.half), int(w.band + w.half) + 1
        for lo, hi in ((w.origin - d1, w.origin - d0), (w.origin + d0, w.origin + d1)):
            lo_i, hi_i = int(math.floor(lo)), int(math.ceil(hi))
            if w.horizontal:
                physics.paint_rect(b.grid, lo_i, a0, hi_i, a1, w.owner)
            else:
                physics.paint_rect(b.grid, a0, lo_i, a1, hi_i, w.owner)
        if w.origin - d1 <= 0 and w.origin + d1 >= length:
            b.waves.remove(w)
