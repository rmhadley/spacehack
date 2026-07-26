"""Space combat engine — turn-based ship-to-ship battles.

This is the **only module with imperative logic**; everything else
is data-driven (weapon specs, module specs, enemy specs).

CombatState tracks one encounter. The caller (_run_combat in
__main__.py) owns the event loop; combat.py provides pure
functions to resolve actions.
"""

from __future__ import annotations

import math

from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Any

import tcod.console
import tcod.context
import tcod.event

from . import character
from . import world
from . import ui
from .data.pilot_skills import PilotSkills
from .data.weapons import find_weapon
from .data.modules import find_module as find_module_spec
from .engine import RNG

from . import ship as _ship_module



class CombatPhase(Enum):
    PLAYER_TURN = auto()
    ENEMY_TURN = auto()
    VICTORY = auto()
    DEFEAT = auto()
    FLEE = auto()


class CombatMode(Enum):
    DEFAULT = auto()
    MOVING = auto()
    FIRING = auto()


@dataclass
class EnemyInstance:
    """Mutable copy of an enemy ship during combat."""
    spec_id: str
    name: str
    char: str
    fg: tuple[int, int, int]
    hull: int = 100
    max_hull: int = 100
    shields: int = 0
    max_shields: int = 0
    shields_charged: bool = False
    power_pool: int = 5
    ap_remaining: int = 3
    ap_total: int = 3
    pos: world.Position = field(default_factory=lambda: world.Position(0, 0))
    weapons: tuple[str, ...] = ()
    modules: tuple[str, ...] = ()
    weapon_ammo: dict[str, int] = field(default_factory=dict)
    pilot_gunnery: int = 20
    pilot_piloting: int = 20
    pilot_engineering: int = 10
    power_gen: int = 3
    max_power: int = 10
    cells_moved_this_turn: int = 0
    shield_regen_rate: int = 0
    alive: bool = True


def _calc_hull(ship_catalog: Any, owned_ship: Any) -> int:
    """Compute current hull HP from hull_damage_pct."""
    max_h = _calc_max_hull(ship_catalog, owned_ship)
    dmg_pct = getattr(owned_ship, 'hull_damage_pct', 0)
    return max(1, max_h * (100 - dmg_pct) // 100)


def _calc_max_hull(ship_catalog: Any, owned_ship: Any) -> int:
    base = getattr(ship_catalog, 'base_hull', 100)
    bonus = 0
    for mod_id in getattr(owned_ship, 'modules', ()) or ():
        try:
            ms = find_module_spec(mod_id)
            bonus += ms.max_hull_bonus
        except KeyError:
            pass
    return base + bonus


def _calc_hull_for_enemy(enemy_spec: Any) -> int:
    """Compute an enemy ship's max (and initial) hull HP from its ship_id + modules."""
    from . import ship as _ship_mod
    try:
        _ship_rec = _ship_mod.find_ship(enemy_spec.ship_id)
        _base_hull = _ship_rec.base_hull
    except KeyError:
        _base_hull = 100
    for mod_id in getattr(enemy_spec, 'modules', ()) or ():
        try:
            ms = find_module_spec(mod_id)
            _base_hull += ms.max_hull_bonus
        except KeyError:
            pass
    return _base_hull


def _sync_back_hull(player_state: dict, player_owned_ship: Any) -> None:
    """Persist combat hull damage back to the player's OwnedShip."""
    if player_owned_ship is None:
        return
    max_hull = player_state.get("max_hull", 100)
    current_hull = player_state.get("hull", max_hull)
    new_dmg_pct = 100 - (current_hull * 100 // max(max_hull, 1))
    player_owned_ship.hull_damage_pct = max(0, min(100, new_dmg_pct))


def _calc_power_gen(ship_catalog: Any, owned_ship: Any) -> int:
    base = getattr(ship_catalog, 'base_power_gen', 3)
    for mod_id in getattr(owned_ship, 'modules', ()) or ():
        try:
            ms = find_module_spec(mod_id)
            base += ms.power_gen_bonus
        except KeyError:
            pass
    return max(0, base)


def _calc_max_shields(ship_catalog: Any, owned_ship: Any) -> int:
    base = getattr(ship_catalog, 'base_shield_max', 0)
    for mod_id in getattr(owned_ship, 'modules', ()) or ():
        try:
            ms = find_module_spec(mod_id)
            base += ms.max_shield_bonus
        except KeyError:
            pass
    return max(0, base)


def _calc_ap(piloting: int) -> int:
    return max(1, 3 + (piloting // 20))


def _calc_dodge_bonus(cells_moved: int, piloting_bonus: int = 0) -> int:
    """Dodge bonus percent: +5/cell moved (cap 30) + half-rate pilot piloting.

    The movement term rewards repositioning during the turn and
    stays capped at 30 so a clever kiter can never make the
    opponent literally invulnerable. The ``piloting_bonus`` is a
    pre-scaled percent (callers pass ``int(pilot_piloting * 0.5)``
    to mirror the gunnery half-rate convention) so AIProfile's
    ``dodge_bonus`` and module ``piloting_bonus`` modifiers (e.g.
    gyro_stabilizer) actually fire instead of sitting unread on
    EnemyInstance / OwnedShip. Total dodge is soft-capped at 60
    so a high-piloting defender still has a counter for skilled
    attackers but no single buff stacks into invulnerability.
    """
    movement = min(cells_moved * 5, 30)
    return min(movement + piloting_bonus, 60)


def _distance(a: world.Position, b: world.Position) -> float:
    return math.hypot(a.x - b.x, a.y - b.y)


def calc_hit_chance(
    weapon_id: str,
    gunnery: int,
    distance: float,
    target_dodge_bonus: int,
) -> int:
    """Return 0-100 hit probability.

    Formula:
        chance = weapon.accuracy
               + int(gunnery * 0.5)        # pilot half-rate
               + (5 if within half-range)  # close_bonus
               - int(overshoot) * 10      # dist_penalty
               - max(0, ws.min_range - math.ceil(distance)) * 5  # min_penalty
               - target_dodge_bonus       # movement + piloting

    ``dist_penalty`` and ``min_penalty`` use ``math.ceil`` so
    fractional distances (Euclidean) don't silently round down
    and bypass the penalty band; standing inside a weapon's
    minimum range (e.g. point-blank with rocket pods) now
    loses accuracy as expected.    The result is clamped to 5-95
    so combat still feels lethal but never deterministic.
    """
    ws = find_weapon(weapon_id)
    dist_penalty = max(0, math.ceil(distance) - ws.max_range) * 10
    min_penalty = max(0, ws.min_range - math.ceil(distance)) * 5
    close_bonus = 5 if distance <= ws.max_range // 2 else 0
    chance = (
        ws.accuracy
        + int(gunnery * 0.5)
        + close_bonus
        - dist_penalty
        - min_penalty
        - target_dodge_bonus
    )
    return max(5, min(95, chance))


def calc_flee_chance(
    player_piloting: int,
    enemy_piloting: int,
    hull_pct: float,
    distance_to_enemy: float,
    attempts: int,
) -> int:
    """Return 0-100 flee success chance."""
    base = 30
    base += (player_piloting - enemy_piloting) * 2
    base += int(max(0, (1.0 - hull_pct) * 20))
    base -= max(0, 5 - int(distance_to_enemy)) * 5
    base += attempts * 10  # stacking bonus per attempt
    return max(5, min(95, base))


def init_combat_state(
    player_ship_catalog: Any,
    player_owned_ship: Any,
    player_pos: world.Position,
    player_pilot_skills: PilotSkills,
    enemy_spec: Any,
    enemy_pos: world.Position,
) -> tuple[dict, EnemyInstance]:
    """Create initial combat state dict for the player and EnemyInstance.

    Returns (player_state, enemy_instance).
    """
    gunnery = player_pilot_skills.gunnery
    piloting = player_pilot_skills.piloting
    engineering = player_pilot_skills.engineering

    # Module bonuses
    for mod_id in getattr(player_owned_ship, 'modules', ()) or ():
        try:
            ms = find_module_spec(mod_id)
            gunnery += ms.gunnery_bonus
            piloting += ms.piloting_bonus
            engineering += ms.engineering_bonus
        except KeyError:
            pass

    ap = _calc_ap(piloting)
    pwr_gen = _calc_power_gen(player_ship_catalog, player_owned_ship)
    max_shield = _calc_max_shields(player_ship_catalog, player_owned_ship)
    hull = _calc_hull(player_ship_catalog, player_owned_ship)
    max_hull = _calc_max_hull(player_ship_catalog, player_owned_ship)

    # Build weapon ammo dict
    w_ammo: dict[str, int] = {}
    for wid in getattr(player_owned_ship, 'weapons', ()) or ():
        try:
            ws = find_weapon(wid)
            w_ammo[wid] = ws.ammo_capacity if ws.ammo_capacity > 0 else -1
        except KeyError:
            w_ammo[wid] = -1

    player_state = {
        "hull": hull,
        "max_hull": max_hull,
        "shields": max_shield,
        "max_shields": max_shield,
        "shields_charged": False,
        "power_pool": pwr_gen,
        "max_power": max(10, pwr_gen * 2) + engineering // 5,
        "ap_remaining": ap,
        "ap_total": ap,
        "pos": player_pos,
        "gunnery": gunnery,
        "piloting": piloting,
        "engineering": engineering,
        "power_gen": pwr_gen,
        "cells_moved_this_turn": 0,
        "shield_regen_rate": 0,
        "weapon_ammo": w_ammo,
    }

    # Enemy instance — uses ship_id to get actual hull value
    e_ap = _calc_ap(enemy_spec.pilot_piloting)
    e_ammo: dict[str, int] = {}
    for wid in enemy_spec.weapons:
        try:
            ws = find_weapon(wid)
            e_ammo[wid] = ws.ammo_capacity if ws.ammo_capacity > 0 else -1
        except KeyError:
            e_ammo[wid] = -1

    enemy_max_hull = _calc_hull_for_enemy(enemy_spec)

    enemy = EnemyInstance(
        spec_id=enemy_spec.id,
        name=enemy_spec.name,
        char=enemy_spec.char,
        fg=enemy_spec.fg,
        hull=enemy_max_hull,
        max_hull=enemy_max_hull,
        shields=_calc_max_shields(enemy_spec, enemy_spec),
        max_shields=_calc_max_shields(enemy_spec, enemy_spec),
        power_pool=enemy_spec.min_power_gen,
        ap_remaining=e_ap,
        ap_total=e_ap,
        pos=enemy_pos,
        weapons=enemy_spec.weapons,
        modules=enemy_spec.modules,
        weapon_ammo=e_ammo,
        pilot_gunnery=enemy_spec.pilot_gunnery + enemy_spec.ai_accuracy_bonus,
        pilot_piloting=enemy_spec.pilot_piloting + enemy_spec.ai_dodge_bonus,
        pilot_engineering=enemy_spec.pilot_engineering,
        power_gen=enemy_spec.min_power_gen,
        max_power=max(10, enemy_spec.min_power_gen * 2) + enemy_spec.pilot_engineering // 5,
    )

    return player_state, enemy


def can_afford_action(
    player_state: dict,
    weapon_id: str,
) -> tuple[bool, str]:
    """Check if the player can fire weapon_id. Returns (ok, reason)."""
    try:
        ws = find_weapon(weapon_id)
    except KeyError:
        return False, "Unknown weapon"

    if player_state["ap_remaining"] < ws.ap_cost:
        return False, f"Need {ws.ap_cost} AP (have {player_state['ap_remaining']})"

    if ws.slot_type == "energy":
        if player_state["power_pool"] < ws.power_cost:
            return False, f"Need {ws.power_cost} power (have {player_state['power_pool']})"
    elif ws.slot_type == "missile":
        ammo = player_state["weapon_ammo"].get(weapon_id, 0)
        if ammo <= 0:
            return False, "Out of ammo"
        if ammo < ws.ammo_per_shot:
            return False, f"Need {ws.ammo_per_shot} ammo (have {ammo})"

    return True, ""


def resolve_damage(
    weapon_id: str,
    target_hull: int,
    target_shields: int,
    target_pilot_piloting: int = 0,
) -> tuple[int, int, int, bool]:
    """Apply weapon damage to a target. Returns (hull_dmg, shield_dmg, final_hull, is_glancing).

    The single RNG draw that decides hit/miss is also used here to
    drive a margin-style damage curve and a pilot-piloting glancing
    threshold (the fused A+C mechanic). The formula:

        q                   = RNG.randint(1, 100)              # damage quality
        glancing_threshold  = int(target_pilot_piloting * 0.5)
        if q <= glancing_threshold:
            damage_mult     = 0.5                              # cap at half
        else:
            damage_mult     = 0.5 + (q - glancing_threshold)
                                       / max(1, 100 - glancing_threshold)
        raw_dmg             = weapon.damage * damage_mult
                              * RNG.uniform(0.8, 1.2)          # weapon variance

    Half-rate piloting mirrors the gunnery half-rate in
    :func:`calc_hit_chance` so the two systems feel symmetric. The
    glancing flag is returned in-place so callers can prefix the log
    line ("Glancing hit..." vs "Hit...") without re-deriving the
    threshold. ``gunnery`` was previously a parameter but unused; the
    return tuple now includes ``is_glancing`` so every call site has
    to be updated once.
    """
    ws = find_weapon(weapon_id)
    q = RNG.randint(1, 100)
    glancing_threshold = int(target_pilot_piloting * 0.5)
    is_glancing = q <= glancing_threshold
    if is_glancing:
        damage_mult = 0.5
    else:
        damage_mult = 0.5 + (q - glancing_threshold) / max(1, 100 - glancing_threshold)
    raw_dmg = ws.damage * damage_mult * RNG.uniform(0.8, 1.2)
    dmg = max(1, int(raw_dmg))

    if target_shields > 0:
        shield_dmg = min(dmg, target_shields)
        hull_dmg = dmg - shield_dmg
    else:
        shield_dmg = 0
        hull_dmg = dmg

    final_hull = max(0, target_hull - hull_dmg)
    return hull_dmg, shield_dmg, final_hull, is_glancing


def start_player_turn(player_state: dict) -> None:
    """Reset per-turn resources for the player and apply shield regen."""
    # Power generation first
    player_state["power_pool"] = min(
        player_state["max_power"],
        player_state["power_pool"] + player_state["power_gen"],
    )
    # Shield regen: rate 0-10, costs power discounted by engineering (half-rate)
    rate = player_state.get("shield_regen_rate", 0)
    max_sh = player_state["max_shields"]
    if rate > 0 and max_sh > 0 and player_state["shields"] < max_sh:
        eng = player_state.get("engineering", 0)
        cost = max(1, rate - eng // 20)
        if player_state["power_pool"] >= cost:
            player_state["power_pool"] -= cost
            player_state["shields"] = min(max_sh, player_state["shields"] + rate)
    player_state["ap_remaining"] = player_state["ap_total"]
    player_state["cells_moved_this_turn"] = 0


def start_enemy_turn(enemy: EnemyInstance) -> None:
    """Reset per-turn resources for an enemy and apply shield regen."""
    enemy.power_pool = min(enemy.max_power, enemy.power_pool + enemy.power_gen)
    rate = enemy.shield_regen_rate
    if rate > 0 and enemy.max_shields > 0 and enemy.shields < enemy.max_shields:
        cost = max(1, rate - enemy.pilot_engineering // 20)
        if enemy.power_pool >= cost:
            enemy.power_pool -= cost
            enemy.shields = min(enemy.max_shields, enemy.shields + rate)
    enemy.ap_remaining = enemy.ap_total
    enemy.cells_moved_this_turn = 0


def move_entity(
    pos: world.Position,
    dx: int,
    dy: int,
    game_map: world.GameMap,
) -> tuple[world.Position, bool]:
    """Try to move an entity by (dx, dy). Returns (new_pos, success)."""
    nx = pos.x + dx
    ny = pos.y + dy
    if not game_map.is_walkable(nx, ny):
        return pos, False
    return world.Position(nx, ny), True


# ---------------------------------------------------------------------------
# Combat animations
# ---------------------------------------------------------------------------


def _responsive_sleep(seconds: float) -> None:
    """Sleep while polling SDL events to keep the window responsive."""
    import time
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


# Explosion ring glyphs — same pattern as __main__'s _animate_jump.
# Expanding bright flash from centre outward.
_COMBAT_EXPLOSION_RINGS: tuple[tuple[str, tuple[int, int, int]], ...] = (
    ("*", (255, 200, 100)),   # inner core - warm gold
    ("+", (255, 255, 150)),   # ring 1      - bright yellow
    ("o", (255, 255, 200)),   # ring 2      - white-yellow
    ("O", (200, 200, 255)),   # ring 3      - pale blue-white
    ("#", (180, 180, 255)),   # ring 4      - dimmer edge
)


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
        # ``alive`` is declared on EnemyInstance; the getattr default is a
        # belt-and-suspenders shield so a future iterator/factory that
        # hands in an enemy-shaped object lacking the field does not
        # silently start painting on stale targets.
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
    """Paint a gold cardinal crosshair reticle around ``enemy``'s footprint.

    Reproduces a "weapons lock" cue after ``world.render_world_view``
    has already drawn the enemy itself: four ASCII bracket marks —
    ``>`` on the left, ``<`` on the right, ``^`` on top, ``v`` below
    — sit one cell outside the footprint so the enemy's own char/fg
    reads unchanged underneath.

    Footprint-aware: walks each cell along the relevant edge of a
    ``width x height`` rectangle, so a 2x2 or larger ship gets a full
    bracket frame instead of a 1-cell dot. Cells outside the
    ``view_w`` x ``view_h`` viewport are silently skipped so a
    target teleported to the camera edge never bleeds negative
    coords into the console buffer (which would crash tcod).

    Color is gold ``(255, 200, 100)`` matching the existing HUD's
    ``COLOR_COMBAT_WEAPON`` palette cue (selected/active items are
    gold elsewhere in the UI), so the reticle reads as an existing
    UI affordance rather than a fresh color the player has to learn.
    The marks are intentionally NOT recoloring the enemy tile; if a
    future iteration wants a recompute-and-recolor behavior, prefer
    extending the helper rather than re-implementing per call site.
    """
    color_gold = (255, 200, 100)
    sx = enemy.pos.x - cam_x
    sy = enemy.pos.y - cam_y
    w = max(1, getattr(enemy, "width", 1))
    h = max(1, getattr(enemy, "height", 1))

    # Left column of `>` and right column of `<` along every row of
    # the footprint.
    for dy in range(h):
        cy = sy + dy
        if not (0 <= cy < view_h):
            continue
        if 0 <= sx - 1 < view_w:
            console.print(
                x=region_x + sx - 1, y=region_y + cy,
                string=">", fg=color_gold,
            )
        if 0 <= sx + w < view_w:
            console.print(
                x=region_x + sx + w, y=region_y + cy,
                string="<", fg=color_gold,
            )

    # Top row of `^` and bottom row of `v` along every column of
    # the footprint. Edges already painted above are skipped by
    # ``range(w)`` which matches column count rather than includes
    # the corner-adjacent cells, so the four corners stay open
    # rather than painted twice.
    for dx in range(w):
        cx = sx + dx
        if not (0 <= cx < view_w):
            continue
        if 0 <= sy - 1 < view_h:
            console.print(
                x=region_x + cx, y=region_y + sy - 1,
                string="^", fg=color_gold,
            )
        if 0 <= sy + h < view_h:
            console.print(
                x=region_x + cx, y=region_y + sy + h,
                string="v", fg=color_gold,
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
) -> None:
    """Render the base world view + HUD + message log during an animation."""
    from .engine import SCREEN_WIDTH, SCREEN_HEIGHT
    from . import hud as _hud
    from . import message_log as _ml
    console.clear()
    world.render_world_view(
        console, game_map,
        region_x=0, region_y=0,
        region_w=view_w, region_h=view_h,
        camera_x=cam_x, camera_y=cam_y,
    )
    # Highlight the currentlytargetted enemy on the map. Painted AFTER
    # the world view so the reticle marks sit on top of the enemy
    # entity's own char/fg without clobbering it. Lives outside the
    # HUD so the right-panel readout and the on-map marker tell the
    # same story without depending on each other.
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
        player_mode="FIRING",
    )
    _ml.render_message_log(
        console, log,
        screen_width=SCREEN_WIDTH,
        screen_height=SCREEN_HEIGHT,
    )
    context.present(console)


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
) -> None:
    """Animate a laser beam from shooter to target over 4 frames.

    Draws a bright line of characters along the Bresenham path from
    shooter to target, then (if ``is_hit``) two impact-flash frames
    at the target position.
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

    # Impact flash (if hit): two quick bright pulses at target
    if is_hit:
        for flash in range(2):
            _render_anim_frame(
                console, context, game_map,
                cam_x, cam_y, view_w, view_h,
                player_state, enemies, target_idx, log,
            )
            tx = target_pos.x - cam_x
            ty = target_pos.y - cam_y
            if 0 <= tx < view_w and 0 <= ty < view_h:
                fg = (255, 255, 255) if flash == 0 else (255, 200, 100)
                console.print(x=tx, y=ty, string="*", fg=fg)
            context.present(console)
            _responsive_sleep(0.06)


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
    )
    _responsive_sleep(0.04)


def run_combat(
    console,
    context,
    player_ship_catalog,
    player_owned_ship,
    player_pos: world.Position,
    player_pilot_skills: PilotSkills,
    enemy_specs: list,
    enemy_positions: list[world.Position],
    game_map: world.GameMap,
    log,    ) -> tuple[str, list[str]]:
    """Drive the combat turn loop using tcod events.

    Accepts lists of enemy specs and positions for multi-enemy combat.
    Returns ``(result, defeated_spec_ids)`` where ``result`` is
    ``"VICTORY"``, ``"DEFEAT"``, or ``"FLEE"`` and
    ``defeated_spec_ids`` lists the ``spec_id`` of each enemy
    destroyed during combat (empty for non-VICTORY outcomes).

    The player cycles targets with Tab. On VICTORY all dead enemy
    entities are removed from ``game_map.entities``. The player's
    hull damage is synced back to ``OwnedShip.hull_damage_pct`` on
    any exit path.
    """
    from . import hud as _hud
    from .engine import SCREEN_WIDTH, SCREEN_HEIGHT, MSG_LOG_HEIGHT, HUD_WIDTH

    if not enemy_specs or not enemy_positions:
        return ("FLEE", [])

    # Build initial combat state(s)
    try:
        enemy_insts: list[EnemyInstance] = []
        for _i in range(len(enemy_specs)):
            if _i == 0:
                _ps, _ei = init_combat_state(
                    player_ship_catalog, player_owned_ship,
                    player_pos, player_pilot_skills,
                    enemy_specs[_i], enemy_positions[_i],
                )
                player_state = _ps
            else:
                _, _ei = init_combat_state(
                    player_ship_catalog, player_owned_ship,
                    player_pos, player_pilot_skills,
                    enemy_specs[_i], enemy_positions[_i],
                )
            enemy_insts.append(_ei)
    except Exception:
        return ("FLEE", [])  # Graceful fallback on init failure

    # -------- Find player entity on map --------
    _player_ent = None
    for _e in game_map.entities:
        if getattr(_e, 'owned', False):
            _player_ent = _e
            break

    # -------- Build enemy-entity mapping (before dedup, so positions align) --------
    # Maps enemy_insts index -> world.Entity for position syncing and
    # entity exclusion in AI movement checks. Matched by position
    # before dedup shifts any instances. Uses id()-based _matched set
    # so two overlapping enemy_insts at the same pre-dedup cell don't
    # both claim the same world.Entity from game_map.entities.
    _enemy_ents: dict[int, Any] = {}
    _matched: set[int] = set()
    for _i, _inst in enumerate(enemy_insts):
        for _e in game_map.entities:
            if _e is _player_ent or getattr(_e, 'owned', False):
                continue
            if id(_e) in _matched:
                continue
            if _e.pos.x == _inst.pos.x and _e.pos.y == _inst.pos.y:
                _enemy_ents[_i] = _e
                _matched.add(id(_e))
                break

    # -------- Deduplicate overlapping positions --------
    # If two or more enemies share the same cell (possible after
    # extended pirate movement on the space map), Tab targeting
    # appears to skip one (the reticle doesn't visually move) and
    # entity-index maps alias. Push overlapping instances apart.
    _occupied: set[tuple[int, int]] = set()
    for _inst in enemy_insts:
        _key = (_inst.pos.x, _inst.pos.y)
        if _key in _occupied:
            # Try 8 directions to find a free cell nearby.
            _placed = False
            for _odx, _ody in [(-1,0),(1,0),(0,-1),(0,1),(-1,-1),(1,-1),(-1,1),(1,1)]:
                _nk = (_inst.pos.x + _odx, _inst.pos.y + _ody)
                if _nk not in _occupied and game_map.in_bounds(*_nk) and game_map.is_walkable(*_nk):
                    _inst.pos = world.Position(*_nk)
                    _occupied.add(_nk)
                    _placed = True
                    break
            if not _placed:
                # Last resort: slide east cell-by-cell until a free
                # cell is found or the map boundary is reached, so
                # enemies pushed from the same origin end up at
                # distinct positions.
                _inst.pos = world.Position(_inst.pos.x + 2, _inst.pos.y)
                _attempts = 0
                while (_inst.pos.x, _inst.pos.y) in _occupied and _attempts < 20:
                    _nx = _inst.pos.x + 1
                    if not game_map.in_bounds(_nx, _inst.pos.y):
                        break
                    _inst.pos = world.Position(_nx, _inst.pos.y)
                    _attempts += 1
                _occupied.add((_inst.pos.x, _inst.pos.y))
        else:
            _occupied.add(_key)

    from .message_log import COLOR_PLAYER_ACTION, COLOR_ENEMY_ACTION, COLOR_COMBAT_EVENT
    from .data.trade_goods import find_trade_good as _ftg

    weapons_list = list(getattr(player_owned_ship, 'weapons', ()) or ())
    selected_weapon_idx = 0
    target_idx = 0
    combat_mode = "DEFAULT"
    flee_attempts: int = 0
    turn: int = 1
    _result: str | None = None  # None = still fighting; set on combat end

    def _p_log(msg: str) -> None:
        """Log a player-facing combat event (green)."""
        log.add_colored(msg, COLOR_PLAYER_ACTION)

    def _e_log(msg: str) -> None:
        """Log an enemy-facing combat event (red)."""
        log.add_colored(msg, COLOR_ENEMY_ACTION)

    def _c_log(msg: str) -> None:
        """Log a system combat event (gold)."""
        log.add_colored(msg, COLOR_COMBAT_EVENT)

    _c_log(f"Combat starts! {len(enemy_insts)} enemy ship(s): "
           + ", ".join(e.name for e in enemy_insts))
    # Track which enemy spec IDs were defeated (for bounty completion).
    _defeated_spec_ids: list[str] = []
    start_player_turn(player_state)

    view_w = 80
    view_h = 54

    # Helper to compute camera centred on player
    def _calc_cam():
        _cw = max(0, game_map.width - view_w)
        _ch = max(0, game_map.height - view_h)
        _cx = max(0, min(
            player_state["pos"].x - view_w // 2,
            _cw,
        ))
        _cy = max(0, min(
            player_state["pos"].y - view_h // 2,
            _ch,
        ))
        return _cx, _cy

    try:
        while True:
            # ---- Check victory (don't prune list — indices must stay stable for _enemy_ents) ----
            _alive_enemies = [e for e in enemy_insts if e.alive]
            if not _alive_enemies:
                _result = "VICTORY"
                break
            if not enemy_insts[target_idx].alive:
                # Move target to next alive enemy
                target_idx = next(
                    (_i for _i, _e in enumerate(enemy_insts) if _e.alive),
                    0,
                )

            # ---- Sync entity positions to game_map so rendering works ----
            if _player_ent is not None:
                _player_ent.pos = player_state["pos"]
            for _i, _inst in enumerate(enemy_insts):
                if _i in _enemy_ents:
                    _enemy_ents[_i].pos = _inst.pos

            # ---- Compute closest alive enemy for flee distance ----
            _closest_enemy = min(
                _alive_enemies,
                key=lambda _e: _distance(player_state["pos"], _e.pos),
            )

            # ---- Compute hit chance for ALL weapons against current target ----
            _weapon_hit_chances: dict[str, int] = {}
            # Player's current evade bonus: +5% per cell moved this turn
            # (capped at 30%) plus half-rate pilot piloting (soft cap 60%).
            # Surfaced in the combat HUD so the player sees the impact
            # of spending AP on movement while in combat.
            _evade_bonus = _calc_dodge_bonus(
                player_state.get("cells_moved_this_turn", 0),
                int(player_state.get("piloting", 0) * 0.5),
            )
            if weapons_list and target_idx < len(enemy_insts):
                _target = enemy_insts[target_idx]
                _dist = _distance(player_state["pos"], _target.pos)
                _dodge = _calc_dodge_bonus(
                    _target.cells_moved_this_turn,
                    int(_target.pilot_piloting * 0.5),
                )
                for _wid in weapons_list:
                    try:
                        _weapon_hit_chances[_wid] = calc_hit_chance(
                            _wid, player_state["gunnery"], _dist, _dodge,
                        )
                    except KeyError:
                        pass

            # ---- Render ----
            console.clear()
            _sys = getattr(game_map, 'width', None)
            if _sys is not None:
                from . import world as _w
                _cam_x, _cam_y = _calc_cam()
                _w.render_world_view(
                    console, game_map,
                    region_x=0, region_y=0,
                    region_w=view_w, region_h=view_h,
                    camera_x=_cam_x, camera_y=_cam_y,
                )
                # Targeted-enemy reticle — drawn AFTER the world view
                # so the gold brackets sit on top of the marker sprite
                # without clobbering its fg. External symbol keeps
                # the call-site cheap.
                _tgt = _resolve_target(enemy_insts, target_idx)
                if _tgt is not None:
                    _paint_target_highlight(
                        console, _cam_x, _cam_y, view_w, view_h, 0, 0, _tgt,
                    )

            _hud.render_combat_hud(
                console,
                screen_width=SCREEN_WIDTH,
                screen_height=SCREEN_HEIGHT,
                player_state=player_state,
                enemies=enemy_insts,
                target_idx=target_idx,
                player_mode=combat_mode,
                selected_weapon_idx=selected_weapon_idx,
                weapon_list=tuple(weapons_list),
                flee_chance=calc_flee_chance(
                    player_state["piloting"],
                    _closest_enemy.pilot_piloting,
                    player_state["hull"] / max(player_state["max_hull"], 1),
                    _distance(player_state["pos"], _closest_enemy.pos),
                    flee_attempts,
                ),
                hit_chances=_weapon_hit_chances,
                evade_bonus=_evade_bonus,
            )
            from . import message_log as _ml
            _ml.render_message_log(
                console, log,
                screen_width=SCREEN_WIDTH,
                screen_height=SCREEN_HEIGHT,
            )
            context.present(console)

            # ---- Auto-end-turn guard (outside ``for event``) ----
            # If ``ap_remaining`` hit 0 from the previous action
            # (move, fire, target switch), or the player pressed
            # ``w``, or a flee attempt failed, run the enemy turn
            # IMMEDIATELY — don't block on the next keypress. The
            # three paths in the event loop below drive this guard
            # by setting ``combat_mode = "WAIT"`` (or zeroing AP)
            # and breaking out of the event loop. Putting this
            # outside ``for event in tcod.event.wait()`` is the
            # fix for the bug where the loop blocked on input
            # after AP reached 0 and the player had to press any
            # key to advance.
            if player_state["ap_remaining"] <= 0 or combat_mode == "WAIT":
                combat_mode = "WAIT"
                # Execute enemy turn for ALL alive enemies
                for _ei in enemy_insts:
                    if not _ei.alive:
                        continue
                    start_enemy_turn(_ei)
                    # Enemy AI: burn the full AP per turn. Each iter =
                    # ONE action that costs 1 AP. Move if outside
                    # preferred_range, else fire (when armed). Loop
                    # terminates on ap_remaining==0 or on the idle
                    # branch (already in range, no weapons). Fire
                    # charges 1 AP too (mirrors player fire cost) so
                    # the loop can't spin forever if the AI is unable
                    # to close distance. Tactical choices (hold vs.
                    # fire, range gating) are out of scope for the
                    # simple v1 of this fix.
                    # Find matching spec for this enemy via spec_id
                    _esp = next(
                        (_sp for _sp in enemy_specs if getattr(_sp, 'id', None) == _ei.spec_id),
                        enemy_specs[0] if enemy_specs else None,
                    )
                    if _esp is None:
                        continue
                    # Cache entity-index lookup once per enemy so the
                    # while loop doesn't re-scan enemy_insts per
                    # move step.
                    _e_idx = next(
                        (_j for _j, _je in enumerate(enemy_insts) if _je is _ei),
                        -1,
                    )
                    while _ei.ap_remaining > 0:
                        _edist = _distance(
                            player_state["pos"], _ei.pos,
                        )
                        _moved = False
                        if _edist > _esp.ai_preferred_range:
                            # Attempt to move one cell toward the
                            # player. The target cell must be both
                            # walkable AND unoccupied — the burn-full
                            # AP refactor exposed overlap because
                            # pirates now move up to 4 cells per
                            # turn instead of 1, so two enemies
                            # converging on the player would happily
                            # step onto each other (or onto the
                            # player). Reject collisions with the
                            # player, another enemy that already
                            # moved earlier in this same for-loop
                            # iteration, or any solar-body entity.
                            _dx = 1 if _ei.pos.x < player_state["pos"].x else -1
                            _dy = 1 if _ei.pos.y < player_state["pos"].y else -1
                            _nx = _ei.pos.x + _dx
                            _ny = _ei.pos.y + _dy
                            # Check direct instance-position collision first:
                            # no other alive enemy may occupy the target cell.
                            # Entity-at checks can miss unmapped enemies whose
                            # game_map entity positions are stale, so skip the
                            # entity mapping entirely and check EnemyInstance
                            # positions directly.
                            _blocked_by_other = any(
                                _oe is not _ei and _oe.alive
                                and _oe.pos.x == _nx and _oe.pos.y == _ny
                                for _oe in enemy_insts
                            )
                            if not _blocked_by_other and (
                                game_map.is_walkable(_nx, _ny)
                                and game_map.entity_at(
                                    _nx, _ny, exclude=None,
                                ) is None
                            ):
                                _ei.pos = world.Position(_nx, _ny)
                                _ei.cells_moved_this_turn += 1
                                _ei.ap_remaining -= 1
                                # Sync enemy entity position AFTER AI movement
                                if _e_idx >= 0 and _e_idx in _enemy_ents:
                                    _enemy_ents[_e_idx].pos = _ei.pos
                                _moved = True
                        if not _moved:
                            # Either in preferred range (no move
                            # attempted) OR move was blocked. Pivot
                            # to fire if armed — mirrors the player-
                            # side rule of "if you can't move, shoot"
                            # so the AP isn't wasted. If move was
                            # blocked AND the enemy is unarmed, idle
                            # for the rest of the turn rather than
                            # spinning.
                            if _ei.weapons:
                                # Enemy fires
                                _wid = _ei.weapons[0]
                                _dist = _distance(
                                    player_state["pos"], _ei.pos,
                                )
                                _dodge = _calc_dodge_bonus(
                                    player_state.get("cells_moved_this_turn", 0),
                                    int(player_state.get("piloting", 0) * 0.5),
                                )
                                _chance = calc_hit_chance(
                                    _wid, _ei.pilot_gunnery, _dist, _dodge,
                                )
                                # Single roll decides both animation AND damage
                                _e_hit = RNG.randint(1, 100) <= _chance
                                _ecx, _ecy = _calc_cam()
                                _animate_laser_shot(
                                    console, context, game_map,
                                    _ei.pos, player_state["pos"],
                                    is_hit=_e_hit,
                                    cam_x=_ecx, cam_y=_ecy,
                                    view_w=view_w, view_h=view_h,
                                    player_state=player_state,
                                    enemies=enemy_insts,
                                    target_idx=target_idx,
                                    log=log,
                                )
                                if _e_hit:
                                    _dmg, _sdmg, _fh, _is_glancing = resolve_damage(
                                        _wid, player_state["hull"],
                                        player_state["shields"],
                                        target_pilot_piloting=player_state.get("piloting", 0),
                                    )
                                    player_state["shields"] = max(0, player_state["shields"] - _sdmg)
                                    player_state["hull"] = _fh
                                    _verb = "glancing hit" if _is_glancing else "hits"
                                    _e_log(f"{_ei.name} {_verb} for {_dmg} hull damage!")
                                    if _fh <= 0:
                                        _e_log("Your ship has been destroyed!")
                                        # Explosion at player position
                                        _ecx, _ecy = _calc_cam()
                                        _animate_explosion(
                                            console, context, game_map,
                                            player_state["pos"],
                                            cam_x=_ecx, cam_y=_ecy,
                                            view_w=view_w, view_h=view_h,
                                            player_state=player_state,
                                            enemies=enemy_insts,
                                            target_idx=target_idx,
                                            log=log,
                                        )
                                        _result = "DEFEAT"
                                        break  # exits while
                                else:
                                    _e_log(f"{_ei.name} misses!")
                                # Fire costs 1 AP — mirrors the
                                # player rule (a shot committed is
                                # a shot paid for) and guarantees
                                # the while loop terminates when
                                # ap_remaining hits 0.
                                _ei.ap_remaining -= 1
                            else:
                                # In preferred range and unarmed, OR
                                # blocked move and unarmed — idle
                                # for the rest of the turn.
                                break
                    # Cascade DEFEAT out of the for-loop so the
                    # remaining enemies don't get their turns after
                    # the player is already destroyed. Without this
                    # the inner ``break`` only exits the new while.
                    if _result is not None:
                        break
                # If DEFEAT happened during the enemy turn, exit
                # combat now (don't re-render a fresh player turn).
                if _result is not None:
                    break
                # New player turn: reset AP, increment counter,
                # drop out of WAIT, then ``continue`` so the
                # top-of-loop render block paints the fresh
                # player turn BEFORE we block on input again.
                combat_mode = "DEFAULT"
                turn += 1
                start_player_turn(player_state)
                continue

            # ---- Wait for input ----
            for event in tcod.event.wait():
                if isinstance(event, tcod.event.Quit):
                    _result = "FLEE"
                    break
                if not isinstance(event, tcod.event.KeyDown):
                    continue
                sym_name: str = getattr(event.sym, "name", "").lower()
                sym = event.sym

                # End-of-turn logic was hoisted OUT of this event
                # loop into a top-of-while guard above (right
                # after ``context.present(console)``). This is the
                # fix for the bug where the game blocked on a
                # keypress after AP hit 0. The three triggers —
                # ``w`` key, ESC flee failure, and AP==0 — all set
                # ``combat_mode = "WAIT"`` (or zero out
                # ``ap_remaining``) and ``break`` out of this event
                # loop; the outer guard then runs the enemy turn
                # and re-renders the new player turn.

                # [Tab] / [Left] / [Right] -> Cycle target
                if sym_name in ("tab", "left", "right") and len(enemy_insts) > 1:
                    if sym_name in ("tab", "right"):
                        target_idx = (target_idx + 1) % len(enemy_insts)
                    else:
                        target_idx = (target_idx - 1) % len(enemy_insts)
                    break

                # Movement in space mode
                _vim_keys = {"h": (-1,0), "j": (0,1), "k": (0,-1), "l": (1,0),
                             "y": (-1,-1), "u": (1,-1), "b": (-1,1), "n": (1,1)}
                if sym_name in _vim_keys and player_state["ap_remaining"] > 0:
                    dx, dy = _vim_keys[sym_name]
                    new_pos, ok = move_entity(
                        player_state["pos"], dx, dy, game_map,
                    )
                    if ok:
                        player_state["pos"] = new_pos
                        player_state["ap_remaining"] -= 1
                        player_state["cells_moved_this_turn"] += 1
                    break

                # ESC -> flee attempt
                if sym in ui._ESCAPE_SYMS:
                    _chance = calc_flee_chance(
                        player_state["piloting"],
                        _closest_enemy.pilot_piloting,
                        player_state["hull"] / max(player_state["max_hull"], 1),
                        _distance(player_state["pos"], _closest_enemy.pos),
                        flee_attempts,
                    )
                    if RNG.randint(1, 100) <= _chance:
                        _p_log("You fled!")
                        _result = "FLEE"
                        break
                    else:
                        flee_attempts += 1
                        _e_log(f"Flee failed! ({_chance}% chance)")
                        player_state["ap_remaining"] = 0
                        combat_mode = "WAIT"
                    break

                # [s] -> Cycle shield regen rate 0-10
                if sym_name == "s":
                    max_sh = player_state.get("max_shields", 0)
                    if max_sh > 0:
                        cur = player_state.get("shield_regen_rate", 0)
                        next_rate = (cur + 1) % 11
                        player_state["shield_regen_rate"] = next_rate
                        eng = player_state.get("engineering", 0)
                        actual_cost = 0 if next_rate == 0 else max(1, next_rate - eng // 20)
                        _p_log(f"Shield regen set to {next_rate}/10 (costs {actual_cost} power per turn)")
                    break

                # [w] -> Wait / end turn
                if sym_name == "w":
                    combat_mode = "WAIT"
                    break

                # [f] -> Fire mode: fire selected weapon at current target
                if sym_name == "f" and weapons_list and target_idx < len(enemy_insts):
                    if selected_weapon_idx >= len(weapons_list):
                        selected_weapon_idx = 0
                    _wid = weapons_list[selected_weapon_idx]
                    _ok, _reason = can_afford_action(player_state, _wid)
                    if not _ok:
                        _p_log(f"Cannot fire: {_reason}")
                        break
                    _target = enemy_insts[target_idx]
                    _dist = _distance(player_state["pos"], _target.pos)
                    _dodge = _calc_dodge_bonus(
                        _target.cells_moved_this_turn,
                        int(_target.pilot_piloting * 0.5),
                    )
                    _chance = calc_hit_chance(
                        _wid, player_state["gunnery"], _dist, _dodge,
                    )
                    # Single roll decides both animation AND damage
                    _roll = RNG.randint(1, 100)
                    _is_hit = _roll <= _chance
                    _cam_x, _cam_y = _calc_cam()
                    _animate_laser_shot(
                        console, context, game_map,
                        player_state["pos"], _target.pos,
                        is_hit=_is_hit,
                        cam_x=_cam_x, cam_y=_cam_y,
                        view_w=view_w, view_h=view_h,
                        player_state=player_state,
                        enemies=enemy_insts,
                        target_idx=target_idx,
                        log=log,
                    )
                    # Resolve the shot
                    _ws = None
                    try:
                        _ws = find_weapon(_wid)
                    except KeyError:
                        pass
                    if _is_hit:
                        _dmg, _sdmg, _fh, _is_glancing = resolve_damage(
                            _wid, _target.hull, _target.shields,
                            target_pilot_piloting=_target.pilot_piloting,
                        )
                        _target.shields = max(0, _target.shields - _sdmg)
                        _target.hull = _fh
                        _dmg_str = f"{_dmg} damage"
                        if _sdmg > 0:
                            _dmg_str += f" ({_sdmg} absorbed by shields)"
                        _verb = "Glancing hit" if _is_glancing else "Hit"
                        _p_log(f"{_verb} {_target.name}! {_ws.name if _ws else _wid} for {_dmg_str} (rolled {_roll}, needed <={_chance})")
                        # Consume ammo/power
                        if _ws and _ws.slot_type == "energy":
                            player_state["power_pool"] -= _ws.power_cost
                        elif _ws and _ws.slot_type == "missile":
                            _ammo = player_state["weapon_ammo"].get(_wid, 0)
                            if _ammo > 0:
                                player_state["weapon_ammo"][_wid] = _ammo - _ws.ammo_per_shot
                                # Each missile round occupies cargo;
                                # firing frees that space so the
                                # player's cargo_used readout tracks
                                # the loadout exactly.
                                if player_owned_ship is not None:
                                    player_owned_ship.cargo_ammo = max(
                                        0,
                                        player_owned_ship.cargo_ammo
                                        - _ws.ammo_per_shot * _ws.cargo_per_round,
                                    )
                        player_state["ap_remaining"] -= (_ws.ap_cost if _ws else 1)
                        if _fh <= 0:
                            _c_log(f"{_target.name} destroyed!")
                            _defeated_spec_ids.append(_target.spec_id)
                            # Explosion animation
                            _cam_x, _cam_y = _calc_cam()
                            _animate_explosion(
                                console, context, game_map,
                                _target.pos,
                                cam_x=_cam_x, cam_y=_cam_y,
                                view_w=view_w, view_h=view_h,
                                player_state=player_state,
                                enemies=enemy_insts,
                                target_idx=target_idx,
                                log=log,
                            )
                            # Mark dead; will be pruned from list next loop
                            _target.alive = False
                            # Remove entity from map
                            if target_idx in _enemy_ents:
                                try:
                                    game_map.entities.remove(_enemy_ents[target_idx])
                                except ValueError:
                                    pass
                            # Spawn loot entities at or near the wreck.
                            # Uses the NPC's cargo_goods from NpcShipSpec
                            # so each ship type drops appropriate loot.
                            _wreck = _target.pos
                            _loot_count = RNG.randint(1, 2)
                            _esp_for_loot = next(
                                (_sp for _sp in enemy_specs
                                 if getattr(_sp, 'id', None) == _target.spec_id),
                                None,
                            )
                            _cargo_pool = getattr(
                                _esp_for_loot, 'cargo_goods', ()
                            ) if _esp_for_loot else ()
                            for _ in range(_loot_count):
                                if not _cargo_pool:
                                    break
                                _loot_good_id = RNG.choice(_cargo_pool)
                                try:
                                    _tg = _ftg(_loot_good_id)
                                except KeyError:
                                    continue
                                if RNG.random() >= _tg.rarity:
                                    continue
                                _qty = RNG.randint(1, 2)
                                _lox = _wreck.x + RNG.randint(-2, 2)
                                _loy = _wreck.y + RNG.randint(-2, 2)
                                if not game_map.is_walkable(_lox, _loy):
                                    continue
                                game_map.entities.append(world.Entity(
                                    char="*", fg=(255, 220, 80),
                                    pos=world.Position(_lox, _loy),
                                    name=f"Cargo: {_tg.name}",
                                    loot_data={"good_id": _tg.id, "quantity": _qty},
                                ))
                    else:
                        _p_log(f"Missed {_target.name}! (rolled {_roll}, needed <={_chance})")
                        # Charge power/ammo + AP on miss too — the
                        # action was committed regardless of whether
                        # it landed. Energy weapons discharge whether
                        # they hit or not; missiles expend a round.
                        if _ws and _ws.slot_type == "energy":
                            player_state["power_pool"] -= _ws.power_cost
                        elif _ws and _ws.slot_type == "missile":
                            _ammo = player_state["weapon_ammo"].get(_wid, 0)
                            if _ammo > 0:
                                player_state["weapon_ammo"][_wid] = _ammo - _ws.ammo_per_shot
                                if player_owned_ship is not None:
                                    player_owned_ship.cargo_ammo = max(
                                        0,
                                        player_owned_ship.cargo_ammo
                                        - _ws.ammo_per_shot * _ws.cargo_per_round,
                                    )
                        player_state["ap_remaining"] -= (_ws.ap_cost if _ws else 1)
                    break

                # [1]-[9] -> Select weapon. tcod's KeySym reports the
                # top-row digit keys as N1..N9 (and numpad as
                # KP_1..KP_9); the ``.lower()`` above turns those into
                # "n1".."n9" / "kp_1".."kp_9". Plain "1".."9" never
                # appear because they would require a tcod version that
                # maps digit keys without the SDL prefix. Pressing a
                # number with index >= len(weapons_list) silently no-ops
                # so the player can't crash combat by mashing digits
                # past their installed weapon count.
                if sym_name in (
                    "n1","n2","n3","n4","n5","n6","n7","n8","n9",
                    "kp_1","kp_2","kp_3","kp_4","kp_5","kp_6",
                    "kp_7","kp_8","kp_9",
                ):
                    _idx = int(sym_name[-1]) - 1
                    if 0 <= _idx < len(weapons_list):
                        selected_weapon_idx = _idx
                    break

                # Any other key: ignore
                continue

            # After the for-loop: if _result was set, exit combat entirely.
            # Otherwise, continue the while loop for the next input event.
            if _result is not None:
                break

    finally:
        # Always sync hull damage back to player's persistent state
        _sync_back_hull(player_state, player_owned_ship)

    return (_result, _defeated_spec_ids)


def _handle_combat_encounter(ctx, console, encounter) -> str:
    """Resolve a triggered combat encounter and return VICTORY / DEFEAT / FLEE.

    Was inlined in __main__._handle_combat_encounter pre-N1; promoted
    to combat.py so the dispatcher stays combat-unaware. The
    encounter payload ((_nearby_specs, _nearby_positions))
    matches the contract of :func:'s
    GotoOutcome.COMBAT branch (__main__._run_goto -> auto-nav
    -> dispatcher -> here).

    On VICTORY a single You defeated ...! entry is added to
    ctx.log so the player sees a clear payoff; DEFEAT / FLEE
    stay silent here because run_combat already emitted per-shot
    logs (incl. the explosion / destruction line).

    If the player has an active bounty mission and the defeated
    enemies include the bounty target, auto-completes the mission
    (instant reward — no turn-in needed).
    """
    # Encounter None / malformed -> silent FLEE (matches _run_goto's
    # contract that combat is only triggered on detected encounters;
    # a None here is a programmer bug we should not crash on).
    if not isinstance(encounter, tuple) or len(encounter) != 2:
        return "FLEE"
    _nearby_specs, _nearby_positions = encounter
    if not _nearby_specs:
        return "FLEE"
    # Mirror _calc_hull_for_enemy's KeyError pattern: find_ship
    # raises on unknown id; degrade gracefully so a corrupted
    # saved ship does not AttributeError out of the tcod context.
    try:
        _ship_cat = _ship_module.find_ship(ctx.player_owned_ship.ship_id)
    except (KeyError, AttributeError):
        # Corrupted ship_id is a save-file or programmer bug; surface
        # it in the message log so a player who triggered it sees why
        # combat silently fled, rather than the encounter vanishing
        # with no explanation.
        ctx.log.add("Ship catalog mismatch -- cannot start combat.")
        return "FLEE"
    # Resolve the player's ACTUAL pilot skills from their (species,
    # class) combo rather than the previous 30/30/30 placeholder.
    # Without this, the crew-and-class math in
    # :mod:`spacehack.character` was for the HUD only and bumping
    # any class's ``skill_bonus`` had zero effect on combat — see
    # the rationale block on :attr:`game_context.CharacterInfo`.
    # Falls back to the base pilot (PILOT_SKILL_BASE) if either id
    # is missing/unrecognised, matching ``starting_pilot_skills``'s
    # safe-lookup behaviour for stale save files.
    _species_id = ctx.character_info.get("species_id") or ""
    _class_id = ctx.character_info.get("class_id") or ""
    _pilot = character.starting_pilot_skills(_species_id, _class_id)
    _result, _defeated_spec_ids = run_combat(
        console,
        ctx.context,
        _ship_cat,
        ctx.player_owned_ship,
        ctx.player.pos,
        _pilot,
        _nearby_specs,
        _nearby_positions,
        ctx.game_map,
        ctx.log,
    )
    if _result == "VICTORY":
        _names = ", ".join(getattr(s, "name", "enemy") for s in _nearby_specs)
        ctx.log.add(f"You defeated {_names}!")
        # Check if an active bounty mission was just completed.
        _active = ctx.player_active_mission
        if _active is not None:
            from . import mission as _mission_mod
            try:
                _mission = _mission_mod.find_mission(_active.mission_id)
            except KeyError:
                _mission = None
            if (
                _mission is not None
                and _mission.target_enemy_id is not None
                and any(_sid == _mission.target_enemy_id for _sid in _defeated_spec_ids)
            ):
                _mission_mod.complete_mission(
                    _mission,
                    ctx.player_owned_ship,
                    ctx.stats,
                    ctx.log,
                )
                ctx.player_active_mission = None
                ctx.log.add("Bounty confirmed — reward transferred via FTL uplink.")
                # Clean up the bounty spawn from the context so it
                # doesn't persist for the next mission.
                _spawn_id = _active.bounty_spawn_id
                _sys_id = _mission.target_system_id
                if _spawn_id is not None and _sys_id is not None:
                    _sys_bounty = ctx.bounty_spawns.get(_sys_id, [])
                    ctx.bounty_spawns[_sys_id] = [
                        _bs for _bs in _sys_bounty
                        if _bs.spawn_id != _spawn_id
                    ]
                    # Also remove the defeated entity from the
                    # game_map if it's still there.
                    if ctx.game_map is not None:
                        for _e in list(ctx.game_map.entities):
                            if any(_sid == _mission.target_enemy_id for _sid in _defeated_spec_ids):
                                # Already removed by run_combat's
                                # explosion handler, but belt-and-
                                # suspenders for any edge cases.
                                pass
    return _result

