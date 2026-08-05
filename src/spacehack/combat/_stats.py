"""Combat math — pure stat calculations for ship combat.

All functions here are deterministic (aside from reading data catalogs)
and have no UI side effects. Suitable for testing in isolation.
"""

from __future__ import annotations

import math
from typing import TYPE_CHECKING

from .. import world
from ._types import EnemyInstance
from ..data.pilot_skills import PilotSkills
from ..data.weapons import find_weapon
from ..data.modules import find_module as find_module_spec
from .. import ship as _ship_mod

if TYPE_CHECKING:
    from ..data.ships import Ship
    from ..data.npc_ships import NpcShipSpec
    from ..ship import OwnedShip


def _calc_hull(ship_catalog: Ship, owned_ship: OwnedShip) -> int:
    """Compute current hull HP from hull_damage_pct."""
    max_h = _calc_max_hull(ship_catalog, owned_ship)
    dmg_pct = getattr(owned_ship, 'hull_damage_pct', 0)
    return max(1, max_h * (100 - dmg_pct) // 100)


def _calc_max_hull(ship_catalog: Ship, owned_ship: OwnedShip) -> int:
    base = getattr(ship_catalog, 'base_hull', 100)
    bonus = 0
    for mod_id in getattr(owned_ship, 'modules', ()) or ():
        try:
            ms = find_module_spec(mod_id)
            bonus += ms.max_hull_bonus
        except KeyError:
            pass
    return base + bonus


def _calc_hull_for_enemy(enemy_spec: NpcShipSpec) -> int:
    """Compute an enemy ship's max (and initial) hull HP from its ship_id + modules."""
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


def _calc_power_gen(ship_catalog: Ship, owned_ship: OwnedShip) -> int:
    base = getattr(ship_catalog, 'base_power_gen', 3)
    for mod_id in getattr(owned_ship, 'modules', ()) or ():
        try:
            ms = find_module_spec(mod_id)
            base += ms.power_gen_bonus
        except KeyError:
            pass
    return max(0, base)


def _calc_max_shields(ship_catalog: Ship | NpcShipSpec, owned_ship: OwnedShip | NpcShipSpec) -> int:
    base = getattr(ship_catalog, 'base_shield_max', 0)
    for mod_id in getattr(owned_ship, 'modules', ()) or ():
        try:
            ms = find_module_spec(mod_id)
            base += ms.max_shield_bonus
        except KeyError:
            pass
    return max(0, base)


def _calc_ap(piloting: int, ap_bonus: int = 0) -> int:
    """Action points per turn: ``3 + Piloting//20`` plus a flat bonus.

    ``ap_bonus`` carries permanent bonuses (e.g. the Ace Pilot trait's
    +1 AP) into the pure formula so callers don't mutate the result.
    """
    return max(1, 3 + (piloting // 20)) + ap_bonus


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
    hit_bonus: int = 0,
) -> int:
    """Return 0-100 hit probability.

    Formula:
        chance = weapon.accuracy
               + int(gunnery * 0.5)        # pilot half-rate
               + (5 if within half-range)  # close_bonus
               - int(overshoot) * 10      # dist_penalty
               - max(0, ws.min_range - math.ceil(distance)) * 5  # min_penalty
               - target_dodge_bonus       # movement + piloting
               + hit_bonus                # permanent bonuses (Sharpshooter)

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
        + hit_bonus
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
    player_ship_catalog: Ship,
    player_owned_ship: OwnedShip,
    player_pos: world.Position,
    player_pilot_skills: PilotSkills,
    enemy_spec: NpcShipSpec,
    enemy_pos: world.Position,
    ap_bonus: int = 0,
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

    ap = _calc_ap(piloting, ap_bonus)
    pwr_gen = _calc_power_gen(player_ship_catalog, player_owned_ship)
    max_shield = _calc_max_shields(player_ship_catalog, player_owned_ship)
    hull = _calc_hull(player_ship_catalog, player_owned_ship)
    max_hull = _calc_max_hull(player_ship_catalog, player_owned_ship)

    # Build weapon ammo dict — player ammo is PERSISTENT across fights:
    # the rounds remaining on the owned ship (weapon_ammo) carry into
    # combat and spent rounds are written back by sync_state. Keyed by
    # weapon SLOT index (not weapon id) so two launchers of the same
    # type keep independent magazines. Enemies keep full magazines
    # below (they're per-encounter spawns).
    _owned_weapons = tuple(getattr(player_owned_ship, 'weapons', ()) or ())
    _owned_ammo = getattr(player_owned_ship, 'weapon_ammo', None) or {}
    w_ammo: dict[int, int] = {}
    for i, wid in enumerate(_owned_weapons):
        try:
            ws = find_weapon(wid)
            if ws.ammo_capacity > 0:
                w_ammo[i] = _owned_ammo.get(i, ws.ammo_capacity)
            else:
                w_ammo[i] = -1
        except KeyError:
            w_ammo[i] = -1

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
        "weapons": _owned_weapons,       # slot-ordered ids (ammo keyed by index)
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
