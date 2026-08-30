"""Combat animations — shared visual effects for space and ground combat.

This module owns the renderer-neutral primitives shared by every combat
effect: framebuffer presentation, line-of-sight helpers, explosion ring
drawing, native floating combat text (hit / MISS / GLANCE numbers drawn
as Pygame text, not bitmap cells), target highlighting, and the ship-kill
explosion. The per-weapon shot animators (beam, bolt, missile, tracer,
grenade, melee) live in :mod:`combat._shot_animations`.

All functions render directly to a project framebuffer and present the
context through the shared Pygame runtime.
"""

from __future__ import annotations

import math
import time
from dataclasses import dataclass, field

from .. import world
from ._types import EnemyInstance
from ..data.weapons import find_weapon
from .. import animation_timing
from ..hud import range_band_color


def _present(context, console) -> None:
    """Present combat animation frames through the active renderer."""
    from ..pygame_combat import present as _pygame_present

    _pygame_present(context, console)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _responsive_sleep(seconds: float) -> None:
    """Sleep while polling SDL events to keep the window responsive."""
    end = time.monotonic() + seconds
    while time.monotonic() < end:
        # Drain queued SDL input during animation frames so keys do not
        # bleed into the next turn. The shared runtime owns the same queue.
        try:
            import pygame
            pygame.event.get()
        except ModuleNotFoundError:
            pass
        remaining = end - time.monotonic()
        if remaining > 0:
            time.sleep(min(remaining, 0.01))


def _bresenham_line(
    x0: int, y0: int, x1: int, y1: int,
):
    """Yield cells on a line from (x0,y0) to (x1,y1), EXCLUDING start cell."""
    dx = abs(x1 - x0)
    dy = -abs(y1 - y0)
    sig_x = 1 if x0 < x1 else -1
    sig_y = 1 if y0 < y1 else -1
    err = dx + dy
    cx, cy = x0, y0
    while (cx, cy) != (x1, y1):
        e2 = 2 * err
        if e2 >= dy:
            err += dy
            cx += sig_x
        if e2 <= dx:
            err += dx
            cy += sig_y
        yield (cx, cy)


def _has_los(
    game_map,
    from_x: int, from_y: int,
    to_x: int, to_y: int,
) -> bool:
    """Check line of sight — True if no walls block the path.

    Walks ``_bresenham_line`` between the two points (excluding
    start and end cells) and returns ``False`` if any intermediate
    cell is unwalkable (a wall, obstacle, etc.).
    """
    for _bx, _by in _bresenham_line(from_x, from_y, to_x, to_y):
        if not game_map.is_walkable(_bx, _by):
            return False
    return True


# Explosion ring glyphs — same pattern as __main__'s _animate_jump.
# Expanding bright flash from centre outward.
_COMBAT_EXPLOSION_RINGS: tuple[tuple[str, tuple[int, int, int]], ...] = (
    ("*", (255, 200, 100)),   # inner core - warm gold
    ("+", (255, 255, 150)),   # ring 1      - bright yellow
    ("o", (255, 255, 200)),   # ring 2      - white-yellow
    ("O", (200, 200, 255)),   # ring 3      - pale blue-white
    ("#", (180, 180, 255)),   # ring 4      - dimmer edge
)

# ---------------------------------------------------------------------------
# Native floating combat text (pygame-rendered, not bitmap cells)
# ---------------------------------------------------------------------------

# Floating number lifetimes (frames). The label is queued during the shot's
# impact/burst frames and keeps drifting up + fading afterwards.
_DAMAGE_POPUP_FRAMES: int = 8
_MISS_POPUP_FRAMES: int = 6

# Popup colors: orange-red for hull damage, cyan for shield strip, pale
# gold for glancing hits, grey for misses. Kept module-level so callers
# and the drawing helper agree.
_COLOR_DAMAGE_HULL: tuple[int, int, int] = (255, 140, 70)
_COLOR_DAMAGE_SHIELDS: tuple[int, int, int] = (120, 220, 255)
_COLOR_DAMAGE_GLANCE: tuple[int, int, int] = (235, 205, 150)
_COLOR_MISS: tuple[int, int, int] = (170, 170, 185)

# Damage text shorthand: (label, color). ``None`` = no popup (a hit that
# did nothing, e.g. an EMP against a shieldless target).
DamagePopup = tuple[str, tuple[int, int, int]] | None

# A rolled miss floats "MISS" instead of a damage number. Identity of the
# label text is how animators tell a miss from a hit.
_MISS_POPUP: DamagePopup = ("MISS", _COLOR_MISS)


def _damage_popup_for(
    damage: int, strip: int, is_strip: bool,
    *, glancing: bool = False,
) -> DamagePopup:
    """Build a damage popup tuple for a resolved hit, or ``None``.

    EMP shield-strip hits show the stripped amount in cyan; glancing
    hits (halved by the target's piloting) are prefixed ``GLANCE`` in
    pale gold; all other hits show TOTAL damage dealt (hull + shields
    absorbed) in orange-red, so the floating number always matches the
    total the log reports. A hit that did nothing (e.g. an EMP against
    a shieldless target) shows no popup. Single factory so the
    player-fire and enemy-fire call sites can't drift apart.
    """
    if is_strip and strip > 0:
        return (f"-{strip}", _COLOR_DAMAGE_SHIELDS)
    total = damage + strip
    if total > 0:
        if glancing:
            return (f"GLANCE -{total}", _COLOR_DAMAGE_GLANCE)
        return (f"-{total}", _COLOR_DAMAGE_HULL)
    return None


def _is_miss(damage: DamagePopup) -> bool:
    """Whether a popup is the MISS label (a rolled miss, not a hit)."""
    return damage is not None and damage[0] == "MISS"


def _popup_lifetime(damage: DamagePopup) -> int:
    """Frame lifetime for a popup — misses linger shorter than hits."""
    return _MISS_POPUP_FRAMES if _is_miss(damage) else _DAMAGE_POPUP_FRAMES


@dataclass
class _CombatEffects:
    """Ephemeral per-frame native combat effects (floating text + glows).

    Single module-level mutable global (guardrail: one dataclass, not
    scattered globals). Presentation-only — nothing here is saved.
    """

    floaters: list = field(default_factory=list)
    glows: list = field(default_factory=list)


_effects: _CombatEffects | None = None


def active_floaters() -> tuple:
    """Return the current frame's native floating texts, then clear them.

    The overlay builders call this exactly once per presented frame; the
    consume-on-read semantics guarantee a frame with no active shot never
    re-draws a stale damage number.
    """
    holder = _effects
    if holder is None:
        return ()
    result = tuple(holder.floaters)
    holder.floaters = []
    return result


def active_glows() -> tuple:
    """Return the current frame's light glows, then clear them.

    Consume-on-read like :func:`active_floaters`; a frame with no active
    effect never re-draws a stale glow.
    """
    holder = _effects
    if holder is None:
        return ()
    result = tuple(holder.glows)
    holder.glows = []
    return result


def _set_floaters(floaters) -> None:
    """Queue the floating texts for the next presented frame."""
    global _effects
    if _effects is None:
        _effects = _CombatEffects()
    _effects.floaters = list(floaters)


def _set_glows(glows) -> None:
    """Queue light glows for the next presented frame."""
    global _effects
    if _effects is None:
        _effects = _CombatEffects()
    _effects.glows = list(glows)


def _floater_for(
    target_pos: world.Position,
    popup: DamagePopup,
    age: int,
    lifetime: int,
    *,
    cam_x: int,
    cam_y: int,
    view_w: int,
    view_h: int,
    region_x: int = 0,
    region_y: int = 0,
):
    """Build one viewport-relative FloatingText frame, or ``None``.

    ``None`` popup (a hit with no result) draws nothing. The text starts
    one row above the target cell so it never covers the impact flash.
    Off-viewport targets return ``None`` — the renderer silently skips
    camera-edge shots instead of crashing.
    """
    from ..pygame_overlay import FloatingText

    if popup is None:
        return None
    text, color = popup
    tx = region_x + target_pos.x - cam_x
    ty = region_y + target_pos.y - 1 - cam_y
    if not (0 <= tx < view_w and 0 <= ty < view_h):
        return None
    return FloatingText(
        text=text, x=tx, y=ty, color=color,
        age=age, lifetime=lifetime,
    )


def _set_frame_floater(
    target_pos: world.Position,
    damage: DamagePopup,
    age: int,
    lifetime: int,
    *,
    cam_x: int,
    cam_y: int,
    view_w: int,
    view_h: int,
    region_x: int = 0,
    region_y: int = 0,
) -> None:
    """Queue the native floating text for the current animation frame."""
    floater = _floater_for(
        target_pos, damage, age, lifetime,
        cam_x=cam_x, cam_y=cam_y,
        view_w=view_w, view_h=view_h,
        region_x=region_x, region_y=region_y,
    )
    _set_floaters([floater] if floater is not None else [])


# ---------------------------------------------------------------------------
# Shared projectile/effect drawing primitives
# ---------------------------------------------------------------------------


def _draw_path_glyph(
    console,
    cell: tuple[int, int],
    char: str,
    color: tuple[int, int, int],
    *,
    cam_x: int,
    cam_y: int,
    view_w: int,
    view_h: int,
    region_x: int = 0,
    region_y: int = 0,
) -> None:
    """Paint one projectile/effect glyph if its cell is inside the viewport."""
    sx = region_x + cell[0] - cam_x
    sy = region_y + cell[1] - cam_y
    if 0 <= sx < view_w and 0 <= sy < view_h:
        console.print(x=sx, y=sy, string=char, fg=color)


def _draw_explosion_rings(
    console,
    center: tuple[int, int],
    ring_count: int,
    *,
    cam_x: int,
    cam_y: int,
    view_w: int,
    view_h: int,
    region_x: int = 0,
    region_y: int = 0,
) -> None:
    """Paint ``ring_count`` concentric explosion rings at ``center``."""
    for ring_idx in range(min(ring_count, len(_COMBAT_EXPLOSION_RINGS))):
        r_char, r_fg = _COMBAT_EXPLOSION_RINGS[ring_idx]
        dist = ring_idx + 1  # 1-indexed manhattan radius
        for dy in range(-dist, dist + 1):
            for dx in range(-dist, dist + 1):
                if abs(dx) + abs(dy) != dist:
                    continue
                _draw_path_glyph(
                    console, (center[0] + dx, center[1] + dy),
                    r_char, r_fg,
                    cam_x=cam_x, cam_y=cam_y,
                    view_w=view_w, view_h=view_h,
                    region_x=region_x, region_y=region_y,
                )


def _draw_flash(
    console,
    center: tuple[int, int],
    *,
    cam_x: int,
    cam_y: int,
    view_w: int,
    view_h: int,
    region_x: int = 0,
    region_y: int = 0,
) -> None:
    """Paint a white-hot flash block (manhattan radius 3) at ``center``."""
    cx = region_x + center[0] - cam_x
    cy = region_y + center[1] - cam_y
    for dy in range(-4, 5):
        for dx in range(-4, 5):
            sx = cx + dx
            sy = cy + dy
            if 0 <= sx < view_w and 0 <= sy < view_h:
                if abs(dx) + abs(dy) <= 3:
                    console.print(
                        x=sx, y=sy, string=" ",
                        fg=(255, 255, 255), bg=(255, 255, 255),
                    )


# ---------------------------------------------------------------------------
# Target highlighting
# ---------------------------------------------------------------------------


def _resolve_target(enemies: list, target_idx: int | None):
    """Return the live targeted enemy, or ``None`` if no valid target.

    Centralizes the
        ``target_idx is not None and 0 <= target_idx < len(enemies)``
    guard plus the ``alive`` check so the two combat-render call
    sites can't drift out of sync. Returns ``None`` instead of
    raising — the highlight helper is purely visual and the right
    move for an invalid target is to skip painting rather than
    crash the presentation context.
    """
    if target_idx is None or not (0 <= target_idx < len(enemies)):
        return None
    candidate = enemies[target_idx]
    if not getattr(candidate, "alive", True):
        return None
    return candidate


def _paint_target_highlight(
    console,
    cam_x: int,
    cam_y: int,
    view_w: int,
    view_h: int,
    region_x: int,
    region_y: int,
    enemy,
) -> None:
    """Recolor the targeted enemy's glyphs to bright gold.

    Paints the enemy's own ``char`` over its footprint tiles so the
    highlight never overlaps neighbors; cells off-view are skipped.
    """
    color_gold = (255, 220, 100)
    bg_gold = (60, 45, 20)
    sx = enemy.pos.x - cam_x
    sy = enemy.pos.y - cam_y
    w = max(1, getattr(enemy, "width", 1))
    h = max(1, getattr(enemy, "height", 1))

    for dy in range(h):
        cy = sy + dy
        if not (0 <= cy < view_h):
            continue
        for dx in range(w):
            cx = sx + dx
            if not (0 <= cx < view_w):
                continue
            console.print(
                x=region_x + cx, y=region_y + cy,
                string=enemy.char,
                fg=color_gold,
                bg=bg_gold,
            )


def _paint_range_line(
    console,
    player_pos: world.Position,
    target_pos: world.Position,
    weapon_id: str,
    cam_x: int,
    cam_y: int,
    view_w: int,
    view_h: int,
    region_x: int = 0,
    region_y: int = 0,
    *,
    color_override: tuple[int, int, int] | None = None,
    game_map: world.GameMap | None = None,
    max_range: int | None = None,
    min_range: int | None = None,
) -> None:
    """Draw a range-accuracy line from player to target, colored by the
    weapon's range bands (green/yellow/orange/red by distance). Shared
    by ship and ground combat; ``color_override`` forces one color.
    ``max_range``/``min_range`` override the catalog values so the
    Focus trait's doubled range bands paint correctly."""
    try:
        ws = find_weapon(weapon_id)
    except KeyError:
        return

    _draw_range_colored_line(
        console,
        player_pos, target_pos,
        max_range if max_range is not None else ws.max_range,
        min_range if min_range is not None else ws.min_range,
        cam_x, cam_y, view_w, view_h,
        region_x, region_y,
        color_override=color_override,
        game_map=game_map,
    )


# ---------------------------------------------------------------------------
# Shared drawing primitives (reused by ground combat)
# ---------------------------------------------------------------------------


def _draw_range_colored_line(
    console,
    player_pos: world.Position,
    target_pos: world.Position,
    weapon_max_range: int,
    weapon_min_range: int,
    cam_x: int,
    cam_y: int,
    view_w: int,
    view_h: int,
    region_x: int = 0,
    region_y: int = 0,
    *,
    color_override: tuple[int, int, int] | None = None,
    game_map: world.GameMap | None = None,
) -> None:
    """Draw a range-accuracy line from player to target, colored by
    distance and the weapon's range profile; ``color_override`` forces
    one color for every cell."""
    for bx, by in _bresenham_line(
        player_pos.x, player_pos.y,
        target_pos.x, target_pos.y,
    ):
        _paint_range_cell(
            console, bx, by,
            player_pos, target_pos,
            weapon_max_range, weapon_min_range,
            cam_x, cam_y, view_w, view_h, region_x, region_y,
            color_override=color_override,
            game_map=game_map,
        )


def _paint_range_cell(
    console,
    bx: int,
    by: int,
    player_pos: world.Position,
    target_pos: world.Position,
    weapon_max_range: int,
    weapon_min_range: int,
    cam_x: int,
    cam_y: int,
    view_w: int,
    view_h: int,
    region_x: int,
    region_y: int,
    *,
    color_override: tuple[int, int, int] | None = None,
    game_map: world.GameMap | None = None,
) -> None:
    """Paint one range-line cell, skipping off-view or occluded cells."""
    if bx == target_pos.x and by == target_pos.y:
        return
    if game_map is not None and game_map.entity_at(bx, by) is not None:
        return
    sx = bx - cam_x
    sy = by - cam_y
    if not (0 <= sx < view_w and 0 <= sy < view_h):
        return
    if color_override is not None:
        color = color_override
    else:
        dist = math.hypot(bx - player_pos.x, by - player_pos.y)
        color = range_band_color(dist, weapon_max_range, weapon_min_range)
    console.print(
        x=region_x + sx, y=region_y + sy,
        string="~",
        fg=color,
    )


# ---------------------------------------------------------------------------
# Frame rendering
# ---------------------------------------------------------------------------


def _paint_combat_hud(
    console,
    player_state: dict,
    enemies: list[EnemyInstance],
    target_idx: int,
    player_mode: str = "FIRING",
    *,
    active_weapons: list[bool] | None = None,
    weapon_list: tuple = (),
    evade_bonus: int | None = None,
    hit_chances: dict[str, int] | None = None,
) -> None:
    """Paint the combat HUD panel via the shared renderer."""
    from ..engine import SCREEN_WIDTH, SCREEN_HEIGHT
    from .. import hud as _hud
    _hud.render_combat_hud(
        console,
        screen_width=SCREEN_WIDTH,
        screen_height=SCREEN_HEIGHT,
        player_state=player_state,
        enemies=enemies,
        target_idx=target_idx,
        player_mode=player_mode,
        active_weapons=active_weapons,
        weapon_list=weapon_list,
        evade_bonus=evade_bonus,
        hit_chances=hit_chances,
    )


def _render_anim_frame(
    console,
    context,
    game_map: world.GameMap,
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
    player_mode: str = "FIRING",
) -> None:
    """Render the base world view + HUD + message log during an animation."""
    console.clear()
    world.render_world_view(
        console, game_map, region_x=0, region_y=0, region_w=view_w, region_h=view_h, camera_x=cam_x, camera_y=cam_y,
    )
    # Targeted-enemy reticle — painted AFTER the world view so the
    # gold recolor sits on top of the enemy char.
    _tgt = _resolve_target(enemies, target_idx)
    if _tgt is not None:
        _paint_target_highlight(console, cam_x, cam_y, view_w, view_h, 0, 0, _tgt)
    _paint_combat_hud(
        console, player_state, enemies, target_idx, player_mode,
        active_weapons=active_weapons, weapon_list=weapon_list, evade_bonus=evade_bonus, hit_chances=hit_chances,
    )
    # The message band is painted natively by pygame_combat.present from
    # ctx.log via the shared log_band_rows builder — no cell capture.
    _present(context, console)


# ---------------------------------------------------------------------------
# Explosion animation (ship kills)
# ---------------------------------------------------------------------------


def _explosion_frame(
    console,
    context,
    game_map: world.GameMap,
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
) -> None:
    """Render one explosion frame (base view + HUD + log)."""
    _render_anim_frame(
        console, context, game_map,
        cam_x, cam_y, view_w, view_h,
        player_state, enemies, target_idx, log,
        weapon_list=weapon_list,
        active_weapons=active_weapons,
        evade_bonus=evade_bonus,
        hit_chances=hit_chances,
    )


_EXPLOSION_GLOW_COLOR = (255, 200, 100)
_EXPLOSION_GLOW_RADIUS = 3
_EXPLOSION_GLOW_LIFETIME = 3


def _queue_explosion_glow(
    center_pos: world.Position,
    ring: int,
    cam_x: int,
    cam_y: int,
) -> None:
    """Queue a ``LightGlow`` at the explosion centre for one frame.

    The glow grows with the explosion ring count so the flash reads as
    expanding light, not a static blob.
    """
    from ..pygame_overlay import LightGlow

    glow = LightGlow(
        x=center_pos.x - cam_x,
        y=center_pos.y - cam_y,
        color=_EXPLOSION_GLOW_COLOR,
        radius=_EXPLOSION_GLOW_RADIUS + ring,
        age=0,
        lifetime=_EXPLOSION_GLOW_LIFETIME,
    )
    _set_glows([glow])


def _animate_explosion(
    console,
    context,
    game_map: world.GameMap,
    center_pos: world.Position,
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
) -> None:
    """Animate an expanding explosion at ``center_pos`` (5 rings)."""
    for rings in range(len(_COMBAT_EXPLOSION_RINGS)):
        _explosion_frame(console, context, game_map, cam_x, cam_y, view_w, view_h, player_state, enemies, target_idx, log, weapon_list=weapon_list, active_weapons=active_weapons, evade_bonus=evade_bonus, hit_chances=hit_chances)
        _draw_explosion_rings(
            console, (center_pos.x, center_pos.y), rings + 1,
            cam_x=cam_x, cam_y=cam_y, view_w=view_w, view_h=view_h,
        )
        _queue_explosion_glow(center_pos, rings, cam_x, cam_y)
        _present(context, console)
        _responsive_sleep(animation_timing.EXPLOSION_RING)
    _explosion_frame(console, context, game_map, cam_x, cam_y, view_w, view_h, player_state, enemies, target_idx, log, weapon_list=weapon_list, active_weapons=active_weapons, evade_bonus=evade_bonus, hit_chances=hit_chances)
    _draw_flash(
        console, (center_pos.x, center_pos.y),
        cam_x=cam_x, cam_y=cam_y, view_w=view_w, view_h=view_h,
    )
    _queue_explosion_glow(center_pos, len(_COMBAT_EXPLOSION_RINGS), cam_x, cam_y)
    _present(context, console)
    _responsive_sleep(animation_timing.EXPLOSION_FLASH)
    _explosion_frame(console, context, game_map, cam_x, cam_y, view_w, view_h, player_state, enemies, target_idx, log, weapon_list=weapon_list, active_weapons=active_weapons, evade_bonus=evade_bonus, hit_chances=hit_chances)
    _responsive_sleep(animation_timing.EXPLOSION_SETTLE)
