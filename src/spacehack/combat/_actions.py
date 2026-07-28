"""Combat action resolution — damage, turns, movement.

Each function here performs a discrete combat action: checking
whether an action is affordable, resolving damage against a
target, resetting per-turn resources, or moving an entity.
"""

from __future__ import annotations

from typing import Any

from .. import world
from ._types import EnemyInstance
from ..data.weapons import find_weapon
from ..data.modules import find_module as find_module_spec
from ..engine import RNG


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
    line (\"Glancing hit...\" vs \"Hit...\") without re-deriving the
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


def _sync_back_hull(player_state: dict, player_owned_ship: Any) -> None:
    """Persist combat hull damage back to the player's OwnedShip."""
    if player_owned_ship is None:
        return
    max_hull = player_state.get("max_hull", 100)
    current_hull = player_state.get("hull", max_hull)
    new_dmg_pct = 100 - (current_hull * 100 // max(max_hull, 1))
    player_owned_ship.hull_damage_pct = max(0, min(100, new_dmg_pct))


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
