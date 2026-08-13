"""Per-weapon shot animations for combat.

Each weapon family gets a distinct effect:

* **laser** — an instant bright beam that snaps across the whole line
* **plasma** — a slow glowing bolt that travels cell by cell with a trail
* **missile** — a slow wobbling projectile with an exhaust trail that
  bursts on arrival (and overshoots the target on a miss)
* **kinetic** — a fast muzzle-flash + tracer that travels two cells a frame
* **explosive** — a lobbed grenade that arcs over and bursts on landing
* **melee** — a quick slash flash at the target cell

All effects run through a shared :class:`_FrameDriver` so space and
ground combat reuse identical animation code with different base-frame
renderers. Floating hit / MISS / GLANCE numbers are queued as native
Pygame text via :func:`combat._animations._set_frame_floater`.

Extracted from ``_animations.py`` so that module stays under the
project's ~1000-line guardrail.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Callable

from .. import world
from ..data.weapons import find_weapon
from ..data.ground_weapons import find_ground_weapon
from .. import animation_timing

from ._types import EnemyInstance
from ._animations import (
    _MISS_POPUP,
    _bresenham_line,
    _draw_explosion_rings,
    _draw_flash,
    _draw_path_glyph,
    _popup_lifetime,
    _present,
    _render_anim_frame,
    _responsive_sleep,
    _set_frame_floater,
    DamagePopup,
    _is_miss,
)


# ---------------------------------------------------------------------------
# Weapon animation classification
# ---------------------------------------------------------------------------


def _shot_family(weapon_id: str, *, ground: bool = False) -> str:
    """Classify a weapon's animation family from its catalog spec.

    Ship weapons classify on ``slot_type`` (energy/plasma/missile);
    ground weapons on ``damage_type`` (melee/kinetic/energy/explosive).
    Unknown ids fall back to the laser beam so presentation never
    crashes on a catalog miss.
    """
    try:
        if ground:
            return {
                "melee": "melee",
                "kinetic": "kinetic",
                "energy": "laser",
                "explosive": "explosive",
            }.get(find_ground_weapon(weapon_id).damage_type, "laser")
        return {
            "energy": "laser",
            "plasma": "plasma",
            "missile": "missile",
        }.get(find_weapon(weapon_id).slot_type, "laser")
    except KeyError:
        return "laser"


# ---------------------------------------------------------------------------
# Frame driver — space and ground share the same per-family animators
# ---------------------------------------------------------------------------


@dataclass
class _FrameDriver:
    """Bundle per-frame callbacks so the animators are renderer-neutral.

    ``base_frame`` re-renders the world + HUD + message log; ``present``
    flips the frame; ``sleep`` paces it while polling SDL input.
    """

    base_frame: Callable[[], None]
    present: Callable[[], None]
    sleep: Callable[[float], None]


def _path_cells(
    from_pos: world.Position,
    to_pos: world.Position,
) -> list[tuple[int, int]]:
    """Bresenham cells shooter→target, always including the target cell."""
    cells = list(_bresenham_line(
        from_pos.x, from_pos.y, to_pos.x, to_pos.y,
    ))
    if not cells or cells[-1] != (to_pos.x, to_pos.y):
        cells.append((to_pos.x, to_pos.y))
    return cells


# ---------------------------------------------------------------------------
# Impact + burst endings (shared by every projectile animator)
# ---------------------------------------------------------------------------


def _animate_floater_tail(
    driver: _FrameDriver,
    to_pos: world.Position,
    damage: DamagePopup,
    start_age: int,
    *,
    cam_x: int,
    cam_y: int,
    view_w: int,
    view_h: int,
    region_x: int = 0,
    region_y: int = 0,
) -> None:
    """Drift + fade frames after an impact — the floating number's tail.

    Every impact style (star flash, explosion burst, melee slash) ends
    the same way: the label keeps rising and fading for the rest of its
    lifetime. Single shared loop so the three call sites can't drift.
    """
    lifetime = _popup_lifetime(damage)
    for age in range(start_age, lifetime):
        driver.base_frame()
        _set_frame_floater(
            to_pos, damage, age=age, lifetime=lifetime,
            cam_x=cam_x, cam_y=cam_y,
            view_w=view_w, view_h=view_h,
            region_x=region_x, region_y=region_y,
        )
        driver.present()
        driver.sleep(animation_timing.DAMAGE_POPUP)


def _animate_impact(
    console,
    driver: _FrameDriver,
    to_pos: world.Position,
    damage: DamagePopup,
    cam_x: int,
    cam_y: int,
    view_w: int,
    view_h: int,
    region_x: int = 0,
    region_y: int = 0,
) -> None:
    """Impact flash + floating-text drift at the target cell.

    A hit flashes the impact star white then gold while the damage
    number floats up. A miss shows no star — only the grey ``MISS``
    label drifting off the target. ``None`` popup (hit, no result)
    draws nothing.
    """
    if damage is None:
        return
    is_miss = _is_miss(damage)
    lifetime = _popup_lifetime(damage)
    for flash in range(2):
        driver.base_frame()
        if not is_miss:
            tx = region_x + to_pos.x - cam_x
            ty = region_y + to_pos.y - cam_y
            if 0 <= tx < view_w and 0 <= ty < view_h:
                fg = (255, 255, 255) if flash == 0 else (255, 200, 100)
                console.print(x=tx, y=ty, string="*", fg=fg)
        _set_frame_floater(
            to_pos, damage, age=flash, lifetime=lifetime,
            cam_x=cam_x, cam_y=cam_y,
            view_w=view_w, view_h=view_h,
            region_x=region_x, region_y=region_y,
        )
        driver.present()
        driver.sleep(animation_timing.COMBAT_IMPACT)
    _animate_floater_tail(
        driver, to_pos, damage, 2,
        cam_x=cam_x, cam_y=cam_y,
        view_w=view_w, view_h=view_h,
        region_x=region_x, region_y=region_y,
    )


def _animate_burst(
    console,
    driver: _FrameDriver,
    center: tuple[int, int],
    to_pos: world.Position,
    damage: DamagePopup,
    cam_x: int,
    cam_y: int,
    view_w: int,
    view_h: int,
    region_x: int = 0,
    region_y: int = 0,
) -> None:
    """Small explosion burst (3 rings + flash) with a floating label.

    Used by missiles and lobbed explosives on arrival. On a miss the
    label still floats at the original target cell even when the burst
    center overshot past it.
    """
    if damage is None:
        return
    lifetime = _popup_lifetime(damage)
    for ring in range(3):
        driver.base_frame()
        _draw_explosion_rings(
            console, center, ring + 1,
            cam_x=cam_x, cam_y=cam_y,
            view_w=view_w, view_h=view_h,
            region_x=region_x, region_y=region_y,
        )
        _set_frame_floater(
            to_pos, damage, age=ring, lifetime=lifetime,
            cam_x=cam_x, cam_y=cam_y,
            view_w=view_w, view_h=view_h,
            region_x=region_x, region_y=region_y,
        )
        driver.present()
        driver.sleep(animation_timing.EXPLOSION_RING)
    driver.base_frame()
    _draw_flash(
        console, center,
        cam_x=cam_x, cam_y=cam_y,
        view_w=view_w, view_h=view_h,
        region_x=region_x, region_y=region_y,
    )
    _set_frame_floater(
        to_pos, damage, age=3, lifetime=lifetime,
        cam_x=cam_x, cam_y=cam_y,
        view_w=view_w, view_h=view_h,
        region_x=region_x, region_y=region_y,
    )
    driver.present()
    driver.sleep(animation_timing.EXPLOSION_FLASH)
    _animate_floater_tail(
        driver, to_pos, damage, 4,
        cam_x=cam_x, cam_y=cam_y,
        view_w=view_w, view_h=view_h,
        region_x=region_x, region_y=region_y,
    )


# ---------------------------------------------------------------------------
# Per-family shot animations
# ---------------------------------------------------------------------------


def _animate_beam(
    console,
    driver: _FrameDriver,
    from_pos: world.Position,
    to_pos: world.Position,
    damage: DamagePopup,
    cam_x: int,
    cam_y: int,
    view_w: int,
    view_h: int,
    region_x: int = 0,
    region_y: int = 0,
) -> None:
    """Laser: an instant beam brightening along the whole line (3 frames)."""
    cells = _path_cells(from_pos, to_pos)
    lifetime = _popup_lifetime(damage)
    for frame in range(3):
        driver.base_frame()
        brightness = min(255, 150 + frame * 40)
        color = (brightness, 95 + frame * 25, 70 + frame * 20)
        for i, (bx, by) in enumerate(cells):
            char = (
                "*" if i == len(cells) - 1 else
                "+" if i == 0 else
                ("=" if i % 2 == 0 else "-")
            )
            _draw_path_glyph(
                console, (bx, by), char, color,
                cam_x=cam_x, cam_y=cam_y,
                view_w=view_w, view_h=view_h,
                region_x=region_x, region_y=region_y,
            )
        _set_frame_floater(
            to_pos, damage, age=0, lifetime=lifetime,
            cam_x=cam_x, cam_y=cam_y,
            view_w=view_w, view_h=view_h,
            region_x=region_x, region_y=region_y,
        )
        driver.present()
        driver.sleep(animation_timing.COMBAT_BEAM)
    _animate_impact(
        console, driver, to_pos, damage,
        cam_x=cam_x, cam_y=cam_y,
        view_w=view_w, view_h=view_h,
        region_x=region_x, region_y=region_y,
    )


def _animate_plasma_bolt(
    console,
    driver: _FrameDriver,
    from_pos: world.Position,
    to_pos: world.Position,
    damage: DamagePopup,
    cam_x: int,
    cam_y: int,
    view_w: int,
    view_h: int,
    region_x: int = 0,
    region_y: int = 0,
) -> None:
    """Plasma: a glowing green bolt traveling one cell per frame."""
    cells = _path_cells(from_pos, to_pos)
    for i, (bx, by) in enumerate(cells):
        driver.base_frame()
        # Two-cell fading trail behind the bolt head
        for trail_idx in range(1, 3):
            trail_j = i - trail_idx
            if trail_j >= 0:
                fade = 1.0 - trail_idx / 3
                trail_color = (
                    int(90 * fade), int(215 * fade), int(150 * fade),
                )
                _draw_path_glyph(
                    console, cells[trail_j], "+", trail_color,
                    cam_x=cam_x, cam_y=cam_y,
                    view_w=view_w, view_h=view_h,
                    region_x=region_x, region_y=region_y,
                )
        _draw_path_glyph(
            console, (bx, by), "o", (140, 255, 180),
            cam_x=cam_x, cam_y=cam_y,
            view_w=view_w, view_h=view_h,
            region_x=region_x, region_y=region_y,
        )
        driver.present()
        driver.sleep(animation_timing.COMBAT_PROJECTILE)
    _animate_impact(
        console, driver, to_pos, damage,
        cam_x=cam_x, cam_y=cam_y,
        view_w=view_w, view_h=view_h,
        region_x=region_x, region_y=region_y,
    )


def _animate_missile(
    console,
    driver: _FrameDriver,
    from_pos: world.Position,
    to_pos: world.Position,
    damage: DamagePopup,
    cam_x: int,
    cam_y: int,
    view_w: int,
    view_h: int,
    region_x: int = 0,
    region_y: int = 0,
) -> None:
    """Missile: slow wobbling projectile with exhaust, bursting on arrival.

    On a miss the missile keeps flying three cells past the target
    before it bursts — a clean overshoot instead of a vanishing shot.
    """
    cells = _path_cells(from_pos, to_pos)
    is_miss = _is_miss(damage)
    burst_center = cells[-1]
    if is_miss and len(cells) >= 2:
        dx = cells[-1][0] - cells[-2][0]
        dy = cells[-1][1] - cells[-2][1]
        burst_center = (burst_center[0] + dx * 3, burst_center[1] + dy * 3)

    for i, (bx, by) in enumerate(cells):
        driver.base_frame()
        # Exhaust trail: two dim dots where the missile has been
        for trail_idx in range(1, 3):
            trail_j = i - trail_idx
            if trail_j >= 0:
                fade = 1.0 - trail_idx / 3
                trail_color = (
                    int(190 * fade), int(190 * fade), int(160 * fade),
                )
                char = "," if trail_idx == 1 else "."
                _draw_path_glyph(
                    console, cells[trail_j], char, trail_color,
                    cam_x=cam_x, cam_y=cam_y,
                    view_w=view_w, view_h=view_h,
                    region_x=region_x, region_y=region_y,
                )
        # Perpendicular sine wobble reads as an unguided rocket
        if i > 0:
            step_x = bx - cells[i - 1][0]
            step_y = by - cells[i - 1][1]
            if (step_x, step_y) != (0, 0):
                wobble = int(round(math.sin(i * 1.1) * 1.0))
                _draw_path_glyph(
                    console, (bx - step_y * wobble, by + step_x * wobble),
                    "=", (255, 240, 180),
                    cam_x=cam_x, cam_y=cam_y,
                    view_w=view_w, view_h=view_h,
                    region_x=region_x, region_y=region_y,
                )
        else:
            _draw_path_glyph(
                console, (bx, by), "=", (255, 240, 180),
                cam_x=cam_x, cam_y=cam_y,
                view_w=view_w, view_h=view_h,
                region_x=region_x, region_y=region_y,
            )
        driver.present()
        driver.sleep(animation_timing.COMBAT_MISSILE)
    _animate_burst(
        console, driver, burst_center, to_pos, damage,
        cam_x=cam_x, cam_y=cam_y,
        view_w=view_w, view_h=view_h,
        region_x=region_x, region_y=region_y,
    )


def _tracer_char(cells: list[tuple[int, int]], index: int) -> str:
    """Pick a direction-shaped tracer glyph for the current path cell."""
    if index == 0:
        return "*"
    px, py = cells[index - 1]
    bx, by = cells[index]
    dx, dy = bx - px, by - py
    if abs(dx) >= abs(dy):
        return "-"
    return "|"


def _animate_tracer(
    console,
    driver: _FrameDriver,
    from_pos: world.Position,
    to_pos: world.Position,
    damage: DamagePopup,
    cam_x: int,
    cam_y: int,
    view_w: int,
    view_h: int,
    region_x: int = 0,
    region_y: int = 0,
) -> None:
    """Kinetic: a muzzle flash, then a fast tracer two cells per frame."""
    cells = _path_cells(from_pos, to_pos)
    # Muzzle flash at the shooter
    driver.base_frame()
    _draw_path_glyph(
        console, (from_pos.x, from_pos.y), "*", (255, 230, 140),
        cam_x=cam_x, cam_y=cam_y,
        view_w=view_w, view_h=view_h,
        region_x=region_x, region_y=region_y,
    )
    driver.present()
    driver.sleep(animation_timing.COMBAT_PROJECTILE)
    # Tracer travels two cells per frame
    for i in range(0, len(cells), 2):
        driver.base_frame()
        _draw_path_glyph(
            console, cells[i], _tracer_char(cells, i), (255, 235, 150),
            cam_x=cam_x, cam_y=cam_y,
            view_w=view_w, view_h=view_h,
            region_x=region_x, region_y=region_y,
        )
        driver.present()
        driver.sleep(animation_timing.COMBAT_PROJECTILE)
    _animate_impact(
        console, driver, to_pos, damage,
        cam_x=cam_x, cam_y=cam_y,
        view_w=view_w, view_h=view_h,
        region_x=region_x, region_y=region_y,
    )


def _animate_grenade(
    console,
    driver: _FrameDriver,
    from_pos: world.Position,
    to_pos: world.Position,
    damage: DamagePopup,
    cam_x: int,
    cam_y: int,
    view_w: int,
    view_h: int,
    region_x: int = 0,
    region_y: int = 0,
) -> None:
    """Explosive: a lobbed grenade arcing over the line, bursting on landing."""
    cells = _path_cells(from_pos, to_pos)
    count = max(1, len(cells) - 1)
    for i, (bx, by) in enumerate(cells):
        driver.base_frame()
        # Parabolic arc: rises to ~2 cells above the line at the midpoint
        t = i / count
        arc = int(round(4 * t * (1 - t) * 2))
        _draw_path_glyph(
            console, (bx, by - arc), "o", (210, 240, 130),
            cam_x=cam_x, cam_y=cam_y,
            view_w=view_w, view_h=view_h,
            region_x=region_x, region_y=region_y,
        )
        driver.present()
        driver.sleep(animation_timing.COMBAT_MISSILE)
    _animate_burst(
        console, driver, cells[-1], to_pos, damage,
        cam_x=cam_x, cam_y=cam_y,
        view_w=view_w, view_h=view_h,
        region_x=region_x, region_y=region_y,
    )


def _animate_melee(
    console,
    driver: _FrameDriver,
    from_pos: world.Position,
    to_pos: world.Position,
    damage: DamagePopup,
    cam_x: int,
    cam_y: int,
    view_w: int,
    view_h: int,
    region_x: int = 0,
    region_y: int = 0,
) -> None:
    """Melee: a quick two-frame slash flash at the target cell."""
    lifetime = _popup_lifetime(damage)
    for frame in range(2):
        driver.base_frame()
        tx = region_x + to_pos.x - cam_x
        ty = region_y + to_pos.y - cam_y
        if 0 <= tx < view_w and 0 <= ty < view_h:
            color = (255, 255, 255) if frame == 0 else (255, 210, 120)
            console.print(x=tx, y=ty, string="X", fg=color)
        _set_frame_floater(
            to_pos, damage, age=frame, lifetime=lifetime,
            cam_x=cam_x, cam_y=cam_y,
            view_w=view_w, view_h=view_h,
            region_x=region_x, region_y=region_y,
        )
        driver.present()
        driver.sleep(animation_timing.COMBAT_MELEE)
    _animate_floater_tail(
        driver, to_pos, damage, 2,
        cam_x=cam_x, cam_y=cam_y,
        view_w=view_w, view_h=view_h,
        region_x=region_x, region_y=region_y,
    )


# Family dispatch table — same signature for every animator (guardrail:
# 3+ branch routing lives in a table, not an if/elif chain).
_FAMILY_ANIMATORS: dict[str, Callable] = {
    "laser": _animate_beam,
    "plasma": _animate_plasma_bolt,
    "missile": _animate_missile,
    "kinetic": _animate_tracer,
    "explosive": _animate_grenade,
    "melee": _animate_melee,
}


def _run_family_animation(
    console,
    driver: _FrameDriver,
    from_pos: world.Position,
    to_pos: world.Position,
    weapon_id: str,
    damage: DamagePopup,
    *,
    cam_x: int,
    cam_y: int,
    view_w: int,
    view_h: int,
    region_x: int = 0,
    region_y: int = 0,
    ground: bool = False,
) -> None:
    """Dispatch one shot to its weapon-family animator."""
    animator = _FAMILY_ANIMATORS.get(
        _shot_family(weapon_id, ground=ground), _animate_beam,
    )
    animator(
        console, driver, from_pos, to_pos, damage,
        cam_x, cam_y, view_w, view_h, region_x, region_y,
    )


# ---------------------------------------------------------------------------
# Space shot dispatcher (shared by player + enemy fire)
# ---------------------------------------------------------------------------


def _animate_weapon_shot(
    console,
    context,
    game_map: world.GameMap,
    shooter_pos: world.Position,
    target_pos: world.Position,
    weapon_id: str,
    is_hit: bool,
    damage: DamagePopup,
    cam_x: int,
    cam_y: int,
    view_w: int,
    view_h: int,
    player_state: dict,
    enemies: list[EnemyInstance],
    target_idx: int,
    log,
    *,
    weapon_list: tuple = (),
    active_weapons: list[bool] | None = None,
    evade_bonus: int | None = None,
    hit_chances: dict[str, int] | None = None,
    flee_chance: int | None = None,
) -> None:
    """Animate one ship-combat shot with a weapon-appropriate effect.

    Resolves the weapon's animation family from its catalog spec and
    plays the matching effect from shooter to target. A miss floats a
    grey ``MISS`` label at the target instead of a damage number.
    """
    def _base() -> None:
        _render_anim_frame(
            console, context, game_map,
            cam_x, cam_y, view_w, view_h,
            player_state, enemies, target_idx, log,
            weapon_list=weapon_list,
            active_weapons=active_weapons,
            evade_bonus=evade_bonus,
            hit_chances=hit_chances,
            flee_chance=flee_chance,
        )

    driver = _FrameDriver(
        base_frame=_base,
        present=lambda: _present(context, console),
        sleep=_responsive_sleep,
    )
    effective_damage = _MISS_POPUP if not is_hit else damage
    _run_family_animation(
        console, driver, shooter_pos, target_pos, weapon_id,
        effective_damage,
        cam_x=cam_x, cam_y=cam_y,
        view_w=view_w, view_h=view_h,
    )


# ---------------------------------------------------------------------------
# Ground shot dispatcher (shared by player + enemy fire)
# ---------------------------------------------------------------------------


def _animate_ground_shot(
    console,
    ctx,
    game_map: world.GameMap,
    from_pos: world.Position,
    to_pos: world.Position,
    weapon_id: str,
    is_hit: bool,
    damage: DamagePopup,
    *,
    render_callback,
) -> None:
    """Animate one ground-combat shot with a weapon-appropriate effect.

    Ground frames render through the rules module's ``render_frame``
    callback (player-centered camera), so the same per-family animators
    as ship combat are reused with a different base-frame driver.
    """
    from ._rules_ground import (
        _RENDER_WIDTH as _gw,
        _RENDER_HEIGHT as _gh,
    )

    _cam_x, _cam_y, _rx, _ry = world.camera_for_view(
        game_map, ctx.player.pos, region_w=_gw, region_h=_gh,
    )

    def _base() -> None:
        render_callback(console, ctx, game_map)

    driver = _FrameDriver(
        base_frame=_base,
        present=lambda: _present(ctx, console),
        sleep=_responsive_sleep,
    )
    effective_damage = _MISS_POPUP if not is_hit else damage
    _run_family_animation(
        console, driver, from_pos, to_pos, weapon_id,
        effective_damage,
        cam_x=_cam_x, cam_y=_cam_y,
        view_w=_gw, view_h=_gh,
        region_x=_rx, region_y=_ry,
        ground=True,
    )
