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
from .input_helpers import _try_open_guide



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
    shield_recharge_bonus = 0
    for mod_id in getattr(player_owned_ship, 'modules', ()) or ():
        try:
            ms = find_module_spec(mod_id)
            gunnery += ms.gunnery_bonus
            piloting += ms.piloting_bonus
            engineering += ms.engineering_bonus
            shield_recharge_bonus += ms.shield_recharge_bonus
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
        "power_pool": max(10, pwr_gen * 2) + engineering // 5,
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
        "shield_recharge_bonus": shield_recharge_bonus,
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
    """Reset per-turn resources for the player and apply shield regen.

    Shield regen uses two tiers:
      - Base rate (player-set via S key): costs power, proportional,
        with engineering discount.
      - Module bonus (shield_recharge_bonus): free regen, no power cost.
    """
    # Power generation first
    player_state["power_pool"] = min(
        player_state["max_power"],
        player_state["power_pool"] + player_state["power_gen"],
    )
    max_sh = player_state["max_shields"]
    if max_sh > 0 and player_state["shields"] < max_sh:
        eng = player_state.get("engineering", 0)
        room = max_sh - player_state["shields"]
        # Tier 1: paid regen from player-set rate (costs power, engineering discount applies).
        base_rate = player_state.get("shield_regen_rate", 0)
        if base_rate > 0:
            full_cost = max(1, base_rate - eng // 20)
            # How many points can we actually regen?  Bounded by rate, room,
            # and what we can afford proportionally.
            paid_regen = min(base_rate, room, player_state["power_pool"] * base_rate // full_cost)
            if paid_regen > 0:
                # Proportional cost: ceil(paid * full_cost / rate)
                paid_cost = (paid_regen * full_cost + base_rate - 1) // base_rate
                paid_cost = min(paid_cost, player_state["power_pool"])
                player_state["power_pool"] -= paid_cost
                player_state["shields"] += paid_regen
                room -= paid_regen
        # Tier 2: free regen from module bonuses (no power cost).
        module_bonus = player_state.get("shield_recharge_bonus", 0)
        if module_bonus > 0 and room > 0:
            free_regen = min(module_bonus, room)
            player_state["shields"] += free_regen
    player_state["ap_remaining"] = player_state["ap_total"]
    player_state["cells_moved_this_turn"] = 0


def start_enemy_turn(enemy: EnemyInstance) -> None:
    """Reset per-turn resources for an enemy and apply shield regen.

    Mirrors :func:`start_player_turn` — base regen costs power with
    engineering discount; module recharge bonus is free.
    """
    enemy.power_pool = min(enemy.max_power, enemy.power_pool + enemy.power_gen)
    # Module shield recharge bonus.
    _module_recharge = 0
    for _mod_id in getattr(enemy, 'modules', ()) or ():
        try:
            _module_recharge += find_module_spec(_mod_id).shield_recharge_bonus
        except KeyError:
            pass
    if enemy.max_shields > 0 and enemy.shields < enemy.max_shields:
        room = enemy.max_shields - enemy.shields
        # Tier 1: paid regen from base rate.
        if enemy.shield_regen_rate > 0:
            full_cost = max(1, enemy.shield_regen_rate - enemy.pilot_engineering // 20)
            paid_regen = min(enemy.shield_regen_rate, room, enemy.power_pool * enemy.shield_regen_rate // full_cost)
            if paid_regen > 0:
                paid_cost = (paid_regen * full_cost + enemy.shield_regen_rate - 1) // enemy.shield_regen_rate
                paid_cost = min(paid_cost, enemy.power_pool)
                enemy.power_pool -= paid_cost
                enemy.shields += paid_regen
                room -= paid_regen
        # Tier 2: free regen from module bonus.
        if _module_recharge > 0 and room > 0:
            enemy.shields += min(_module_recharge, room)
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
) -> None:
    """Draw a range-accuracy line from player to target, colored by weapon range bands.

    Each cell along a Bresenham line is colored based on its distance
    from the player and the selected weapon's range profile:

      * **Green** — within ``max_range // 2`` (close-bonus zone)
      * **Yellow** — within ``max_range`` (normal range)
      * **Orange** — within ``min_range`` (too-close penalty, if min_range > 0)
      * **Red** — beyond ``max_range`` (dist penalty active)

    The line updates immediately when the player switches weapons.    Uses ``~`` (tilde) as the line character so it's visible but
    doesn't fully obscure glyphs underneath. Tilde is a safe
    choice for CP437-based tilesets (``CHARMAP_TCOD``)."""
    try:
        ws = find_weapon(weapon_id)
    except KeyError:
        return

    half_range = ws.max_range // 2
    has_min_range = ws.min_range > 0

    _GREEN = (100, 235, 115)
    _YELLOW = (255, 220, 80)
    _ORANGE = (255, 160, 60)
    _RED = (255, 80, 80)

    for bx, by in _bresenham_line(
        player_pos.x, player_pos.y,
        target_pos.x, target_pos.y,
    ):
        sx = bx - cam_x
        sy = by - cam_y
        if not (0 <= sx < view_w and 0 <= sy < view_h):
            continue

        dist = math.hypot(bx - player_pos.x, by - player_pos.y)

        if dist <= half_range:
            color = _GREEN
        elif dist <= ws.max_range:
            color = _YELLOW
        elif has_min_range and dist <= ws.min_range:
            color = _ORANGE
        else:
            color = _RED

        console.print(
            x=region_x + sx, y=region_y + sy,
            string="~",
            fg=color,
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
    flee_chance: int | None = None,
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
        player_mode="FIRING",
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

    # Impact flash (if hit): two quick bright pulses at target
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
    log,
    ctx = None,    ) -> tuple[str, list[str]]:
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
    from . import message_log as _ml
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
    active_weapons = [True] * max(1, len(weapons_list))
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
                # Move target to next alive enemy (search forward from
                # current index so we don't snap back to the first alive
                # enemy, which would make enemies past a dead one
                # unreachable via Tab).
                _n = len(enemy_insts)
                for _offset in range(1, _n + 1):
                    _candidate = (target_idx + _offset) % _n
                    if enemy_insts[_candidate].alive:
                        target_idx = _candidate
                        break
                else:
                    target_idx = 0

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
                # Range-accuracy line — drawn AFTER the world view so it
            # sits on top of the space background but BEFORE the target
            # highlight so the gold recolor takes visual priority over
            # the line. Uses the first active weapon for range display.
            _range_wid = None
            if weapons_list:
                _first_active = next((i for i, a in enumerate(active_weapons) if a), None)
                if _first_active is not None and _first_active < len(weapons_list):
                    _range_wid = weapons_list[_first_active]
            if _range_wid is not None:
                _tgt = _resolve_target(enemy_insts, target_idx)
                if _tgt is not None:
                    _paint_range_line(
                        console,
                        player_state["pos"], _tgt.pos,
                        _range_wid,
                        _cam_x, _cam_y, view_w, view_h, 0, 0,
                    )

            # Targeted-enemy reticle — drawn AFTER the range line
            # so the gold recolor sits on top of the line marker.
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
                active_weapons=active_weapons,
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
                                # Render a frame so the player sees the enemy move
                                # (prevents the "teleport" feel of multi-AP movement).
                                _cam_x, _cam_y = _calc_cam()
                                console.clear()
                                world.render_world_view(
                                    console, game_map,
                                    region_x=0, region_y=0,
                                    region_w=view_w, region_h=view_h,
                                    camera_x=_cam_x, camera_y=_cam_y,
                                )
                                _tgt = _resolve_target(enemy_insts, target_idx)
                                if _tgt is not None:
                                    _paint_target_highlight(
                                        console, _cam_x, _cam_y,
                                        view_w, view_h, 0, 0, _tgt,
                                    )
                                _flee_now = calc_flee_chance(
                                    player_state["piloting"],
                                    _closest_enemy.pilot_piloting,
                                    player_state["hull"] / max(player_state["max_hull"], 1),
                                    _distance(player_state["pos"], _closest_enemy.pos),
                                    flee_attempts,
                                )
                                _hud.render_combat_hud(
                                    console,
                                    screen_width=SCREEN_WIDTH,
                                    screen_height=SCREEN_HEIGHT,
                                    player_state=player_state,
                                    enemies=enemy_insts,
                                    target_idx=target_idx,
                                    player_mode=combat_mode,
                                    active_weapons=active_weapons,
                                    weapon_list=tuple(weapons_list),
                                    evade_bonus=_evade_bonus,
                                    hit_chances=_weapon_hit_chances,
                                    flee_chance=_flee_now,
                                )
                                _ml.render_message_log(
                                    console, log,
                                    screen_width=SCREEN_WIDTH,
                                    screen_height=SCREEN_HEIGHT,
                                )
                                context.present(console)
                                _responsive_sleep(0.05)
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
                                    weapon_list=tuple(weapons_list),
                                    active_weapons=active_weapons,
                                    evade_bonus=_evade_bonus,
                                    hit_chances=_weapon_hit_chances,
                                    flee_chance=calc_flee_chance(
                                        player_state["piloting"],
                                        _closest_enemy.pilot_piloting,
                                        player_state["hull"] / max(player_state["max_hull"], 1),
                                        _distance(player_state["pos"], _closest_enemy.pos),
                                        flee_attempts,
                                    ),
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
                                            weapon_list=tuple(weapons_list),
                                            active_weapons=active_weapons,
                                            evade_bonus=_evade_bonus,
                                            hit_chances=_weapon_hit_chances,
                                            flee_chance=calc_flee_chance(
                                                player_state["piloting"],
                                                _closest_enemy.pilot_piloting,
                                                player_state["hull"] / max(player_state["max_hull"], 1),
                                                _distance(player_state["pos"], _closest_enemy.pos),
                                                flee_attempts,
                                            ),
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
                # Tick NPCs on the space map between combat rounds
                # so the rest of the universe doesn't freeze.
                if ctx is not None:
                    from .npc_ships import move_npcs as _tick_npcs
                    _tick_npcs(ctx, game_map)
                    # Re-check for NEW enemies that moved within detection
                    # range during the NPC tick. If found, merge them in.
                    # Use entity-ID matching to avoid duplicating enemies
                    # already in combat (whose positions may have shifted
                    # due to move_npcs).
                    from .navigation import _detect_combat_encounter as _re_detect
                    from . import solar_system as _ss_module
                    _new_encounter = _re_detect(ctx, player_state["pos"], _ss_module.current_system())
                    if _new_encounter is not None:
                        _new_specs, _new_positions = _new_encounter
                        _existing_entity_ids = {id(_e) for _e in _enemy_ents.values()}
                        for _ni, (_ns, _np) in enumerate(zip(_new_specs, _new_positions)):
                            # Find the world entity at this position.
                            _found_entity = None
                            for _ge in game_map.entities:
                                if getattr(_ge, 'owned', False):
                                    continue
                                if _ge.pos.x == _np.x and _ge.pos.y == _np.y:
                                    _found_entity = _ge
                                    break
                            # Skip if this entity is already in combat.
                            if _found_entity is not None and id(_found_entity) in _existing_entity_ids:
                                continue
                            # Also skip if already in enemy_insts by position
                            # (belt-and-suspenders).
                            _already = any(
                                _ei.pos.x == _np.x and _ei.pos.y == _np.y
                                for _ei in enemy_insts
                            )
                            if _already:
                                continue
                            # Create EnemyInstance for the new joiner.
                            _ps_dummy, _new_ei = init_combat_state(
                                player_ship_catalog, player_owned_ship,
                                player_state["pos"], player_pilot_skills,
                                _ns, _np,
                            )
                            enemy_insts.append(_new_ei)
                            if _found_entity is not None:
                                _enemy_ents[len(enemy_insts) - 1] = _found_entity
                            _c_log(f"{_ns.name} joins the fight!")
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

                if ctx is not None and _try_open_guide(event, ctx):
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
                        _mod_bonus = player_state.get("shield_recharge_bonus", 0)
                        effective = next_rate + _mod_bonus
                        eng = player_state.get("engineering", 0)
                        actual_cost = 0 if next_rate == 0 else max(1, next_rate - eng // 20)
                        _p_log(f"Shield regen set to {next_rate}/10 (+{_mod_bonus} module = {effective} total, costs {actual_cost} power per turn)")
                    break

                # [w] -> Wait / end turn
                if sym_name == "w":
                    combat_mode = "WAIT"
                    break

                # [f] -> Fire burst: all active weapons at current target
                if sym_name == "f" and weapons_list and target_idx < len(enemy_insts):
                    _active_indices = [i for i, a in enumerate(active_weapons) if a]
                    if not _active_indices:
                        _p_log("No weapons selected. Press 1-6 to toggle.")
                        break
                    _target = enemy_insts[target_idx]
                    _dodge = _calc_dodge_bonus(
                        _target.cells_moved_this_turn,
                        int(_target.pilot_piloting * 0.5),
                    )
                    # ---- Check combined affordability ----
                    _total_ap = 0
                    _total_power = 0
                    _can_burst = True
                    for _bi in _active_indices:
                        _bwid = weapons_list[_bi]
                        _bws = find_weapon(_bwid)
                        _total_ap = max(_total_ap, _bws.ap_cost)
                        if _bws.slot_type == "energy":
                            _total_power += _bws.power_cost
                        # Check ammo for missile weapons
                        if _bws.slot_type == "missile":
                            _ammo = player_state["weapon_ammo"].get(_bwid, 0)
                            if _ammo < _bws.ammo_per_shot:
                                _p_log(f"Not enough ammo for {_bws.name}.")
                                _can_burst = False
                                break
                    if not _can_burst:
                        break
                    if player_state["ap_remaining"] < _total_ap:
                        _p_log(f"Burst needs {_total_ap} AP (have {player_state['ap_remaining']}).")
                        break
                    if _total_power > player_state["power_pool"]:
                        _p_log(f"Burst needs {_total_power} power (have {player_state['power_pool']}).")
                        break
                    # ---- Fire each active weapon ----
                    for _bi in _active_indices:
                        _bwid = weapons_list[_bi]
                        _bws = find_weapon(_bwid)
                        _dist = _distance(player_state["pos"], _target.pos)
                        _chance = calc_hit_chance(
                            _bwid, player_state["gunnery"], _dist, _dodge,
                        )
                        _hit = RNG.randint(1, 100) <= _chance
                        _cam_x, _cam_y = _calc_cam()
                        _animate_laser_shot(
                            console, context, game_map,
                            player_state["pos"], _target.pos,
                            is_hit=_hit,
                            cam_x=_cam_x, cam_y=_cam_y,
                            view_w=view_w, view_h=view_h,
                            player_state=player_state,
                            enemies=enemy_insts,
                            target_idx=target_idx,
                            log=log,
                            weapon_list=tuple(weapons_list),
                            active_weapons=active_weapons,
                            evade_bonus=_evade_bonus,
                            hit_chances=_weapon_hit_chances,
                            flee_chance=calc_flee_chance(
                                player_state["piloting"],
                                _closest_enemy.pilot_piloting,
                                player_state["hull"] / max(player_state["max_hull"], 1),
                                _distance(player_state["pos"], _closest_enemy.pos),
                                flee_attempts,
                            ),
                        )
                        if _hit:
                            _dmg, _sdmg, _fh, _is_glancing = resolve_damage(
                                _bwid, _target.hull, _target.shields,
                                target_pilot_piloting=_target.pilot_piloting,
                            )
                            _target.shields = max(0, _target.shields - _sdmg)
                            _target.hull = _fh
                            _sdmg
                            _dmg
                            _verb = "Glancing hit" if _is_glancing else "Hit"
                            _p_log(f"{_verb} {_target.name}! {_bws.name} for {_dmg} hull")
                            if _fh <= 0:
                                _c_log(f"{_target.name} destroyed!")
                                _defeated_spec_ids.append(_target.spec_id)
                                _ecx2, _ecy2 = _calc_cam()
                                _animate_explosion(
                                    console, context, game_map,
                                    _target.pos,
                                    cam_x=_ecx2, cam_y=_ecy2,
                                    view_w=view_w, view_h=view_h,
                                    player_state=player_state,
                                    enemies=enemy_insts,
                                    target_idx=target_idx,
                                    log=log,
                                    weapon_list=tuple(weapons_list),
                                    active_weapons=active_weapons,
                                    evade_bonus=_evade_bonus,
                                    hit_chances=_weapon_hit_chances,
                                    flee_chance=calc_flee_chance(
                                        player_state["piloting"],
                                        _closest_enemy.pilot_piloting,
                                        player_state["hull"] / max(player_state["max_hull"], 1),
                                        _distance(player_state["pos"], _closest_enemy.pos),
                                        flee_attempts,
                                    ),
                                )
                                _target.alive = False
                                if target_idx in _enemy_ents:
                                    try:
                                        game_map.entities.remove(_enemy_ents[target_idx])
                                    except ValueError:
                                        pass
                                # Spawn loot
                                _wreck = _target.pos
                                _esp_for_loot = next(
                                    (_sp for _sp in enemy_specs
                                     if getattr(_sp, 'id', None) == _target.spec_id),
                                    None,
                                )
                                _cargo_pool = getattr(
                                    _esp_for_loot, 'cargo_goods', ()
                                ) if _esp_for_loot else ()
                                for _ in range(RNG.randint(1, 2)):
                                    if not _cargo_pool:
                                        break
                                    _loot_good_id = RNG.choice(_cargo_pool)
                                    try:
                                        _tg = _ftg(_loot_good_id)
                                    except KeyError:
                                        continue
                                    _pos = world.Position(
                                        _wreck.x + RNG.randint(-1, 1),
                                        _wreck.y + RNG.randint(-1, 1),
                                    )
                                    if not game_map.is_walkable(_pos.x, _pos.y):
                                        _pos = _wreck
                                    game_map.entities.append(world.Entity(
                                        char="*", fg=(255, 200, 50),
                                        pos=_pos,
                                        name=f"Loot: {_tg.name}",
                                        width=1, height=1,
                                        loot_data={"good_id": _loot_good_id, "quantity": 1},
                                    ))
                                    # Don't fire remaining weapons — target already destroyed
                                    break
                        else:
                            _p_log(f"{_bws.name} misses {_target.name}!")
                        # Ammo deduction for missile weapons (regardless of hit)
                        if _bws.slot_type == "missile":
                            _ammo = player_state["weapon_ammo"].get(_bwid, 0)
                            if _ammo > 0:
                                player_state["weapon_ammo"][_bwid] = _ammo - _bws.ammo_per_shot
                                if player_owned_ship is not None:
                                    player_owned_ship.cargo_ammo = max(
                                        0,
                                        player_owned_ship.cargo_ammo
                                        - _bws.ammo_per_shot * _bws.cargo_per_round,
                                    )
                    # Deduct burst costs (max AP, sum power) after all weapons fire
                    player_state["ap_remaining"] -= _total_ap
                    player_state["power_pool"] -= _total_power
                    break
                # [1-9] / [Num1-Num9] -> Toggle weapon on/off
                if sym_name in (
                    "n1","n2","n3","n4","n5","n6","n7","n8","n9",
                    "kp_1","kp_2","kp_3","kp_4","kp_5","kp_6",
                    "kp_7","kp_8","kp_9",
                ):
                    _idx = int(sym_name[-1]) - 1
                    if 0 <= _idx < len(weapons_list):
                        active_weapons[_idx] = not active_weapons[_idx]
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
    # If the player is already dead, skip straight to DEFEAT to
    # prevent re-showing the death screen via __main__'s combat
    # while-loops (G-key, movement, period handlers).
    if ctx.player_dead:
        return "DEFEAT"

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
        ctx=ctx,
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
    if _result == "DEFEAT":
        ctx.player_dead = True
        _render_death_screen(console, ctx.context, ctx.log)
    return _result


# ---------------------------------------------------------------------------
# Death screen
# ---------------------------------------------------------------------------


def _render_death_screen(console, context, log) -> None:
    """Render a full-screen death overlay and wait for a keypress.

    Paints a dramatic red-tinted death screen with the player's
    ship destruction message, then blocks until any key is pressed
    (or the window is closed). The caller is responsible for
    setting ``ctx.player_dead`` and cleaning up after this returns.
    """
    from .engine import SCREEN_WIDTH, SCREEN_HEIGHT
    from . import message_log as _ml

    _death_lines = [
        "",
        "═" * 40,
        " " * 12 + "YOUR SHIP HAS BEEN DESTROYED",
        "═" * 40,
        "",
        "The cold void rushes in as your cockpit",
        "shatters. Systems fail one by one.",
        "Your story among the stars ends here.",
        "",
        "Maybe in another life, under another sun,",
        "you'll get another chance.",
        "",
        "Press any key to return to the main menu...",
    ]
    _red = (255, 60, 60)
    _white = (200, 200, 200)
    _dark_bg = (20, 0, 0)

    while True:
        console.clear()
        # Fill the entire console with dark red background.
        for y in range(SCREEN_HEIGHT):
            for x in range(SCREEN_WIDTH):
                console.print(x=x, y=y, string=" ", fg=_dark_bg, bg=_dark_bg)

        # Draw death lines centred.
        _start_y = (SCREEN_HEIGHT - len(_death_lines)) // 2 - 4
        for _i, _line in enumerate(_death_lines):
            _color = _red if _i == 2 else _white
            _x = (SCREEN_WIDTH - len(_line)) // 2
            console.print(x=_x, y=_start_y + _i, string=_line, fg=_color)

        # Also show the message log so the player can review what happened.
        _ml.render_message_log(
            console, log,
            screen_width=SCREEN_WIDTH,
            screen_height=SCREEN_HEIGHT,
        )

        context.present(console)

        for event in tcod.event.wait():
            if isinstance(event, tcod.event.Quit):
                raise SystemExit()
            if isinstance(event, tcod.event.KeyDown):
                return
