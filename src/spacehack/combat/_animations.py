"""Combat animations — visual effects for ship-to-ship battles.

All functions here render directly to a tcod console and present
the context. They are called from the main combat loop to give
the player visual feedback for laser shots, explosions, and target
highlighting.
"""

from __future__ import annotations

import math
import time

import tcod.event

from .. import world
from ._types import EnemyInstance
from ..data.weapons import find_weapon

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _responsive_sleep(seconds: float) -> None:
    """Sleep while polling SDL events to keep the window responsive."""
    end = time.monotonic() + seconds
    while time.monotonic() < end:
        for _ in tcod.event.get():
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

# Floating damage popup: how many extra frames the number keeps
# drifting up + fading after the impact flash. 2 flash frames + this
# many = total popup lifetime (~0.45s at 0.05s/frame).
_DAMAGE_POPUP_FRAMES: int = 7

# Damage popup colors: orange-red for hull damage, cyan for shield
# strip. Kept module-level so callers and the drawing helper agree.
_COLOR_DAMAGE_HULL: tuple[int, int, int] = (255, 140, 70)
_COLOR_DAMAGE_SHIELDS: tuple[int, int, int] = (120, 220, 255)


# Damage text shorthand: (label, color). ``None`` = no popup (miss).
DamagePopup = tuple[str, tuple[int, int, int]] | None


def _damage_popup_for(
    damage: int, strip: int, is_strip: bool,
) -> DamagePopup:
    """Build a damage popup tuple for a resolved hit, or ``None``.

    Shield-strip hits (EMP) show the stripped amount in cyan; hull
    damage shows in orange-red. A hit that did nothing (e.g. an EMP
    against a shieldless target) shows no popup. Single factory so
    the player-fire and enemy-fire call sites can't drift apart.
    """
    if is_strip and strip > 0:
        return (f"-{strip}", _COLOR_DAMAGE_SHIELDS)
    if damage > 0:
        return (f"-{damage}", _COLOR_DAMAGE_HULL)
    return None


def _draw_damage_popup(
    console,
    target_pos: world.Position,
    damage: DamagePopup,
    age: int,
    cam_x: int,
    cam_y: int,
    view_w: int,
    view_h: int,
    region_x: int = 0,
    region_y: int = 0,
) -> None:
    """Draw one frame of a floating damage number at ``target_pos``.

    The text starts one row above the impact cell (so it doesn't
    cover the impact star), climbs one row every 2 frames, and fades
    toward dim grey as ``age`` grows toward the popup lifetime.
    Cells outside the viewport are silently skipped so camera-edge
    targets never crash tcod. ``damage`` is ``(text, color)``;
    ``None`` draws nothing (a miss).
    """
    if damage is None:
        return
    text, color = damage
    tx = target_pos.x - cam_x
    ty = target_pos.y - 1 - age // 2 - cam_y
    if not (0 <= tx < view_w and 0 <= ty < view_h):
        return
    frac = max(0.0, 1.0 - age / (2 + _DAMAGE_POPUP_FRAMES))
    fg = tuple(int(c * frac + 70 * (1 - frac)) for c in color)
    console.print(x=region_x + tx, y=region_y + ty, string=text, fg=fg)


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
    crash the tcod context.
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
    """Recolor the targeted enemy's own glyph to bright gold.

    Replaces the old bracket-marker reticle (``>`` / ``<`` / ``^`` / ``v``
    printed one cell outside the footprint) which overwrote adjacent
    enemy ship glyphs when enemies stood close together.

    The new approach paints the enemy's own ``char`` in bright gold
    over a dark-gold background, directly on the enemy's footprint
    tiles. This only touches the enemy's own cells — never overlaps
    neighbors — and works for any ship size (1x1 scouts, 2x2+
    larger ships). Cells outside the viewport are silently skipped
    so camera-edge targets never crash tcod.

    Color is gold ``(255, 220, 100)`` with a dark-gold background
    ``(60, 45, 20)``, matching the existing HUD's gold/weapon
    palette cue so the highlight reads as an existing UI affordance.
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
) -> None:
    """Draw a range-accuracy line from player to target, colored by weapon range bands.

    Delegates to :func:`_draw_range_colored_line` after resolving
    the weapon spec — shared by both ship and ground combat.

    Each cell along a Bresenham line is colored based on its distance
    from the player and the selected weapon's range profile:

      * **Green** — within ``max_range // 2`` (close-bonus zone)
      * **Yellow** — within ``max_range`` (normal range)
      * **Orange** — within ``min_range`` (too-close penalty, if min_range > 0)
      * **Red** — beyond ``max_range`` (dist penalty active)

    When ``color_override`` is set, all cells use that color instead
    (e.g. solid red when LOS is blocked).

    The line updates immediately when the player switches weapons.    Uses ``~`` (tilde) as the line character so it's visible but
    doesn't fully obscure glyphs underneath. Tilde is a safe
    choice for CP437-based tilesets (``CHARMAP_TCOD``)."""
    try:
        ws = find_weapon(weapon_id)
    except KeyError:
        return

    _draw_range_colored_line(
        console,
        player_pos, target_pos,
        ws.max_range, ws.min_range,
        cam_x, cam_y, view_w, view_h,
        region_x, region_y,
        color_override=color_override,
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
) -> None:
    """Draw a range-accuracy line from player to target, colored by
    distance from the player and the weapon's range profile.

    This is the core drawing logic extracted from
    :func:`_paint_range_line` so both ship combat and ground combat
    can share it with different weapon catalog lookups.

    * **Green** — within ``max_range // 2`` (close-bonus zone)
    * **Yellow** — within ``max_range`` (normal range)
    * **Orange** — within ``min_range`` (too-close penalty)
    * **Red** — beyond ``max_range`` (dist penalty active)

    When ``color_override`` is set, all cells use that color instead
    (e.g. solid red ``(255, 60, 60)`` when LOS is blocked).
    """
    half_range = weapon_max_range // 2
    has_min_range = weapon_min_range > 0

    _GREEN = (100, 235, 115)
    _YELLOW = (255, 220, 80)
    _ORANGE = (255, 160, 60)
    _RED = (255, 80, 80)

    for bx, by in _bresenham_line(
        player_pos.x, player_pos.y,
        target_pos.x, target_pos.y,
    ):
        # Skip the target's own cell — the highlight/bg handles that
        if bx == target_pos.x and by == target_pos.y:
            continue

        sx = bx - cam_x
        sy = by - cam_y
        if not (0 <= sx < view_w and 0 <= sy < view_h):
            continue

        if color_override is not None:
            color = color_override
        else:
            dist = math.hypot(bx - player_pos.x, by - player_pos.y)
            if dist <= half_range:
                color = _GREEN
            elif dist <= weapon_max_range:
                color = _YELLOW
            elif has_min_range and dist <= weapon_min_range:
                color = _ORANGE
            else:
                color = _RED

        console.print(
            x=region_x + sx, y=region_y + sy,
            string="~",
            fg=color,
        )


# ---------------------------------------------------------------------------
# Frame rendering
# ---------------------------------------------------------------------------


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
    flee_chance: int | None = None,
    player_mode: str = "FIRING",
) -> None:
    """Render the base world view + HUD + message log during an animation."""
    from ..engine import SCREEN_WIDTH, SCREEN_HEIGHT
    from .. import hud as _hud
    from .. import message_log as _ml
    console.clear()
    world.render_world_view(
        console, game_map,
        region_x=0, region_y=0,
        region_w=view_w, region_h=view_h,
        camera_x=cam_x, camera_y=cam_y,
    )
    # Targeted-enemy reticle — painted AFTER the world view so the
    # gold recolor sits on top of the enemy char.
    _tgt = _resolve_target(enemies, target_idx)
    if _tgt is not None:
        _paint_target_highlight(
            console, cam_x, cam_y, view_w, view_h, 0, 0, _tgt,
        )
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
        flee_chance=flee_chance,
    )
    _ml.render_message_log(
        console, log,
        screen_width=SCREEN_WIDTH,
        screen_height=SCREEN_HEIGHT,
    )
    context.present(console)


# ---------------------------------------------------------------------------
# Animation sequences
# ---------------------------------------------------------------------------


def _animate_laser_shot(
    console,
    context,
    game_map: world.GameMap,
    shooter_pos: world.Position,
    target_pos: world.Position,
    is_hit: bool,
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
    damage: DamagePopup = None,
) -> None:
    """Animate a laser beam from shooter to target over 4 frames.

    Draws a bright line of characters along the Bresenham path from
    shooter to target, then (if ``is_hit``) two impact-flash frames
    at the target position. When ``damage`` is a ``(text, color)``
    tuple (i.e. a hit that dealt damage), the number floats up and
    fades out over the flash + ``_DAMAGE_POPUP_FRAMES`` frames.
    """
    cells = list(_bresenham_line(
        shooter_pos.x, shooter_pos.y,
        target_pos.x, target_pos.y,
    ))
    # Make sure the end cell is included
    if not cells or cells[-1] != (target_pos.x, target_pos.y):
        cells.append((target_pos.x, target_pos.y))

    # Beam frames: brighten over 4 frames
    for frame in range(4):
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
        # Draw beam on top
        brightness = min(255, 130 + frame * 30)
        color = (brightness, brightness - 20, 100 + frame * 20)
        for i, (bx, by) in enumerate(cells):
            sx = bx - cam_x
            sy = by - cam_y
            if 0 <= sx < view_w and 0 <= sy < view_h:
                if i == len(cells) - 1:
                    char = "*"
                elif i == 0:
                    char = "+"
                else:
                    # Alternate beam chars along the path
                    char = "=" if i % 2 == 0 else "-"
                console.print(x=sx, y=sy, string=char, fg=color)
        context.present(console)
        _responsive_sleep(0.05)

    # Impact flash (if hit): two quick bright pulses at target,
    # with the damage number riding on top from the first frame.
    if is_hit:
        for flash in range(2):
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
            tx = target_pos.x - cam_x
            ty = target_pos.y - cam_y
            if 0 <= tx < view_w and 0 <= ty < view_h:
                fg = (255, 255, 255) if flash == 0 else (255, 200, 100)
                console.print(x=tx, y=ty, string="*", fg=fg)
            if damage is not None:
                _draw_damage_popup(
                    console, target_pos, damage, age=flash,
                    cam_x=cam_x, cam_y=cam_y,
                    view_w=view_w, view_h=view_h,
                )
            context.present(console)
            _responsive_sleep(0.06)

    # Damage number drift + fade frames after the impact. Ages 0-1
    # were the flash frames above, so the drift starts at age 2.
    if is_hit and damage is not None:
        for _age in range(_DAMAGE_POPUP_FRAMES):
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
            _draw_damage_popup(
                console, target_pos, damage, age=2 + _age,
                cam_x=cam_x, cam_y=cam_y,
                view_w=view_w, view_h=view_h,
            )
            context.present(console)
            _responsive_sleep(0.05)


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
    flee_chance: int | None = None,
) -> None:
    """Animate an expanding explosion at ``center_pos`` (5 rings).

    Each frame paints one more concentric ring outward so the effect
    reads as a growing bright flash. Mirrors ``__main__._animate_jump``.
    """
    for rings in range(len(_COMBAT_EXPLOSION_RINGS)):
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
        # Draw explosion rings (manhattan distance)
        for ring_idx in range(min(rings + 1, len(_COMBAT_EXPLOSION_RINGS))):
            r_char, r_fg = _COMBAT_EXPLOSION_RINGS[ring_idx]
            dist = ring_idx + 1  # 1-indexed manhattan radius
            for dy in range(-dist, dist + 1):
                for dx in range(-dist, dist + 1):
                    if abs(dx) + abs(dy) != dist:
                        continue
                    sx = center_pos.x + dx - cam_x
                    sy = center_pos.y + dy - cam_y
                    if 0 <= sx < view_w and 0 <= sy < view_h:
                        console.print(x=sx, y=sy, string=r_char, fg=r_fg)
        context.present(console)
        _responsive_sleep(0.07)

    # One frame of white flash
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
    cx = center_pos.x - cam_x
    cy = center_pos.y - cam_y
    for dy in range(-4, 5):
        for dx in range(-4, 5):
            sy = cy + dy
            sx = cx + dx
            if 0 <= sx < view_w and 0 <= sy < view_h:
                if abs(dx) + abs(dy) <= 3:
                    bg = (255, 255, 255)
                    console.print(x=sx, y=sy, string=" ", fg=(255, 255, 255), bg=bg)
    context.present(console)
    _responsive_sleep(0.08)

    # Brief void to let the flash settle
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
    _responsive_sleep(0.04)
