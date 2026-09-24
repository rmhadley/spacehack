"""Combat math — pure stat calculations for ship combat.

All functions here are deterministic (aside from reading data catalogs)
and have no UI side effects. Suitable for testing in isolation.
"""

from __future__ import annotations

import math
from types import SimpleNamespace
from typing import TYPE_CHECKING

from .. import world
from ._types import EnemyInstance
from ..data.pilot_skills import PilotSkills
from ..data.weapons import find_weapon
from ..data.quality import effective_module_spec
from .. import ship as _ship_mod
from ..space_scale import derive_skills, roll_flown_equipment

if TYPE_CHECKING:
    from ..data.ships import Ship
    from ..data.npc_ships import NpcShipSpec
    from ..ship import OwnedShip


def _module_bonus_sum(modules, field: str) -> int:
    """Sum one bonus field across module instances at their quality.

    ``modules`` is an iterable of ``StoredEquipment`` instances —
    installed (player), flown (enemy, doc 47.3), or base entries.
    Unknown ids are skipped like every other module reader.
    """
    total = 0
    for entry in modules:
        try:
            total += getattr(
                effective_module_spec(
                    entry.item_id, entry.quality, entry.randart_seed,
                ),
                field,
            )
        except KeyError:
            pass
    return total


def _calc_hull(ship_catalog: Ship, owned_ship: OwnedShip) -> int:
    """Compute current hull HP from hull_damage_pct."""
    max_h = _calc_max_hull(ship_catalog, owned_ship)
    dmg_pct = getattr(owned_ship, 'hull_damage_pct', 0)
    return max(1, max_h * (100 - dmg_pct) // 100)


def _calc_max_hull(ship_catalog: Ship, owned_ship: OwnedShip) -> int:
    base = getattr(ship_catalog, 'base_hull', 100)
    return base + _module_bonus_sum(
        getattr(owned_ship, 'modules', ()) or (), 'max_hull_bonus',
    )


def _enemy_hull(enemy_spec: NpcShipSpec):
    """The flown hull's catalog record — the parity mirror's source
    (doc 48 SETTLED 39): enemy shields, recharge, and power read the
    same hull the player would fly. A hull id that misses the
    catalog contributes nothing (modules-only stats) — a data error
    degrades, never crashes mid-game."""
    try:
        return _ship_mod.find_ship(enemy_spec.ship_id)
    except KeyError:
        return SimpleNamespace(
            base_hull=0, base_shield_max=0,
            base_shield_recharge=0, base_power_gen=0,
        )


def _calc_hull_for_enemy(enemy_spec: NpcShipSpec, modules) -> int:
    """Compute an enemy ship's max (and initial) hull HP from its
    ship_id plus the quality-bearing modules it flies (doc 47.3:
    pass base entries for out-of-combat reads, rolled instances
    inside combat)."""
    return _enemy_hull(enemy_spec).base_hull + _module_bonus_sum(
        modules, 'max_hull_bonus',
    )


def _calc_power_gen(ship_catalog: Ship, modules) -> int:
    """Power generated per turn: hull base + module bonuses — one
    implementation read by both the player and enemy paths."""
    return max(0, getattr(ship_catalog, 'base_power_gen', 3) + _module_bonus_sum(
        modules, 'power_gen_bonus',
    ))


def _calc_max_shields(ship_catalog: Ship, modules) -> int:
    """Max shields for a hull plus module instances (entries). The
    enemy path passes :func:`_enemy_hull`'s record — same formula the
    player and the exploration overlay read."""
    base = getattr(ship_catalog, 'base_shield_max', 0)
    return max(0, base + _module_bonus_sum(modules, 'max_shield_bonus'))


def _calc_ap_twentieths(piloting: int, ap_bonus: int = 0) -> int:
    """AP gained per round, in twentieths: ``(3 + piloting/20 + ap_bonus) * 20``.

    Every piloting point shifts the gain by one twentieth (0.05 AP), so
    a 20-point investment averages +1 AP per round. ``ap_bonus`` carries
    permanent bonuses (e.g. the Ace Pilot trait's +1 AP) into the pure
    formula so callers don't mutate the result.
    """
    return max(20, 60 + piloting) + 20 * ap_bonus


def _calc_ap(piloting: int, ap_bonus: int = 0) -> int:
    """Spendable AP in the first round: the integer part of the gain.

    The fractional remainder banks and rolls into later rounds via
    :func:`_roll_ap`, so a pilot at 15 Piloting sees 3 AP three rounds
    out of four instead of a flat 3 forever.
    """
    return _calc_ap_twentieths(piloting, ap_bonus) // 20


def _roll_ap(pool_twentieths: int, gain_twentieths: int) -> tuple[int, int]:
    """Roll AP for one round: return ``(available, carry_twentieths)``.

    TE4-style fractional regeneration with carry: the banked fraction
    plus this round's gain forms the pool; the integer part is
    spendable and the remainder carries into the next round. Stored
    in twentieths so the math is exact (no float drift): a gain of 75
    twentieths (3.75 AP) rolls 3 available with 15 twentieths carried,
    then the next round rolls 4 available with 10 carried.
    """
    _pool = pool_twentieths + gain_twentieths
    return _pool // 20, _pool % 20


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
    weapon_id: str, gunnery: int, distance: float,
    target_dodge_bonus: int, hit_bonus: int = 0, *,
    max_range: int | None = None, min_range: int | None = None,
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

    ``max_range``/``min_range`` override the catalog range profile
    (the Focus trait doubles it).
    """
    ws = find_weapon(weapon_id)
    _max = max_range if max_range is not None else ws.max_range
    _min = min_range if min_range is not None else ws.min_range
    dist_penalty = max(0, math.ceil(distance) - _max) * 10
    min_penalty = max(0, _min - math.ceil(distance)) * 5
    close_bonus = 5 if distance <= _max // 2 else 0
    chance = (
        ws.accuracy + int(gunnery * 0.5) + close_bonus - dist_penalty
        - min_penalty - target_dodge_bonus + hit_bonus
    )
    return max(5, min(95, chance))


def _skill_bonuses(skills: PilotSkills, modules) -> tuple[int, int, int]:
    """Sum module skill bonuses onto base skill values — the one
    implementation both the player and enemy builds read."""
    return (
        skills.gunnery + _module_bonus_sum(modules, 'gunnery_bonus'),
        skills.piloting + _module_bonus_sum(modules, 'piloting_bonus'),
        skills.engineering + _module_bonus_sum(modules, 'engineering_bonus'),
    )


def _free_shield_regen(ship_catalog, modules) -> int:
    """Free shield regen per turn: hull base + module recharge bonuses
    (both sides read this one function)."""
    return getattr(ship_catalog, 'base_shield_recharge', 0) + _module_bonus_sum(
        modules, 'shield_recharge_bonus',
    )


def _player_weapon_ammo(owned_ship: OwnedShip) -> dict[int, int]:
    """Player ammo keyed by weapon SLOT index; persistent across fights.

    The rounds remaining on the owned ship (``weapon_ammo``) carry into
    combat and spent rounds are written back by ``sync_state``. Keyed by
    slot index so two launchers of the same type keep independent
    magazines.
    """
    _owned = tuple(getattr(owned_ship, 'weapons', ()) or ())
    _ammo = getattr(owned_ship, 'weapon_ammo', None) or {}
    w_ammo: dict[int, int] = {}
    for i, wid in enumerate(_owned):
        try:
            ws = find_weapon(wid)
            if ws.ammo_capacity > 0:
                w_ammo[i] = _ammo.get(i, ws.ammo_capacity)
            else:
                w_ammo[i] = -1
        except KeyError:
            w_ammo[i] = -1
    return w_ammo


def _enemy_flown_loadout(enemy_spec):
    """Roll the spec's flown weapons + modules at its band's fly-time
    quality (weapons first — one deterministic draw order)."""
    from ..engine import RNG

    return (
        roll_flown_equipment("weapon", enemy_spec.weapons, enemy_spec.band, RNG),
        roll_flown_equipment("module", enemy_spec.modules, enemy_spec.band, RNG),
    )


def _enemy_skills(enemy_spec, flown) -> tuple[int, int, int]:
    """Band-derived skills + module bonuses + the per-spec
    reconciliation dials — the fold order the harness mirrors."""
    g, p, e = derive_skills(enemy_spec)
    return (
        g + _module_bonus_sum(flown, 'gunnery_bonus') + enemy_spec.ai_accuracy_bonus,
        p + _module_bonus_sum(flown, 'piloting_bonus') + enemy_spec.ai_dodge_bonus,
        e + _module_bonus_sum(flown, 'engineering_bonus'),
    )


def _slot_ammo(flown_weapons) -> dict[int, int]:
    """Magazine sizes keyed by weapon SLOT index (duplicates keep
    independent magazines); -1 = energy weapon, no ammo."""
    ammo: dict[int, int] = {}
    for slot, entry in enumerate(flown_weapons):
        try:
            ws = find_weapon(entry.item_id)
        except KeyError:
            ammo[slot] = -1
            continue
        ammo[slot] = ws.ammo_capacity if ws.ammo_capacity > 0 else -1
    return ammo


def _build_enemy(enemy_spec: NpcShipSpec, enemy_pos: world.Position) -> EnemyInstance:
    """Construct the EnemyInstance — the parity mirror (doc 48
    SETTLED 39): hull-catalog shields/recharge/power, module effects
    onto band-derived skills, flown equipment at band quality, and
    the paid shield divert left unset (Tier 1)."""
    _weapons, _flown = _enemy_flown_loadout(enemy_spec)
    _hull = _enemy_hull(enemy_spec)
    _g, _p, _e = _enemy_skills(enemy_spec, _flown)
    enemy_max_hull = _calc_hull_for_enemy(enemy_spec, _flown)
    _shields = _calc_max_shields(_hull, _flown)
    _pwr_gen = _calc_power_gen(_hull, _flown)
    _max_power = max(10, _pwr_gen * 2) + _e // 5
    return EnemyInstance(
        spec_id=enemy_spec.id,
        name=enemy_spec.name,
        char=enemy_spec.char,
        fg=enemy_spec.fg,
        hull=enemy_max_hull,
        max_hull=enemy_max_hull,
        shields=_shields,
        max_shields=_shields,
        power_pool=_max_power,
        ap_remaining=_calc_ap(_p),
        ap_total=_calc_ap(_p),
        ap_gain_twentieths=_calc_ap_twentieths(_p),
        pos=enemy_pos,
        weapons=_weapons,
        modules=_flown,
        weapon_ammo=_slot_ammo(_weapons),
        pilot_gunnery=_g,
        pilot_piloting=_p,
        pilot_engineering=_e,
        power_gen=_pwr_gen,
        max_power=_max_power,
        band=enemy_spec.band,
        shield_recharge_bonus=_free_shield_regen(_hull, _flown),
    )


def _player_combat_values(
    player_ship_catalog: Ship,
    player_owned_ship: OwnedShip,
    player_pilot_skills: PilotSkills,
    ap_bonus: int,
    max_power_bonus: int,
) -> tuple:
    """Derive the player's combat numbers from ship catalog + skills."""
    _owned_modules = getattr(player_owned_ship, 'modules', ()) or ()
    gunnery, piloting, engineering = _skill_bonuses(
        player_pilot_skills, _owned_modules,
    )
    pwr_gen = _calc_power_gen(player_ship_catalog, _owned_modules)
    return (
        gunnery, piloting, engineering,
        _calc_ap(piloting, ap_bonus),
        _calc_ap_twentieths(piloting, ap_bonus),
        pwr_gen,
        _calc_max_shields(player_ship_catalog, _owned_modules),
        _calc_hull(player_ship_catalog, player_owned_ship),
        _calc_max_hull(player_ship_catalog, player_owned_ship),
        max(10, pwr_gen * 2) + engineering // 5 + max_power_bonus,
    )


def _player_state_dict(
    player_pos: world.Position, values: tuple, plasma_ap_discount: int,
    owned_ship: "OwnedShip", ship_catalog: Ship,
) -> dict:
    """Assemble the player's combat state dict from derived values."""
    (_g, _p, _e, _ap, _ap_gain, _pwr_gen, _max_shield, _hull, _max_hull, _power_max) = values
    return {
        "hull": _hull,
        "max_hull": _max_hull,
        "shields": _max_shield,
        "max_shields": _max_shield,
        "shields_charged": False,
        "power_pool": _power_max,
        "max_power": _power_max,
        "ap_remaining": _ap,
        "ap_total": _ap,
        "ap_gain_twentieths": _ap_gain,
        "ap_carry_twentieths": 0,
        "pos": player_pos,
        "gunnery": _g,
        "piloting": _p,
        "engineering": _e,
        "power_gen": _pwr_gen,
        "plasma_ap_discount": plasma_ap_discount,
        "cells_moved_this_turn": 0,
        "shield_regen_rate": 0,
        "shield_recharge_bonus": _free_shield_regen(
            ship_catalog, getattr(owned_ship, 'modules', ()) or (),
        ),
        "weapons": tuple(getattr(owned_ship, 'weapons', ()) or ()),
        "weapon_ammo": _player_weapon_ammo(owned_ship),
    }


def init_combat_state(
    player_ship_catalog: Ship,
    player_owned_ship: OwnedShip,
    player_pos: world.Position,
    player_pilot_skills: PilotSkills,
    enemy_spec: NpcShipSpec,
    enemy_pos: world.Position,
    ap_bonus: int = 0,
    plasma_ap_discount: int = 0,
    max_power_bonus: int = 0,
) -> tuple[dict, EnemyInstance]:
    """Create initial combat state dict for the player and EnemyInstance."""
    _values = _player_combat_values(
        player_ship_catalog, player_owned_ship, player_pilot_skills,
        ap_bonus, max_power_bonus,
    )
    return (
        _player_state_dict(
            player_pos, _values, plasma_ap_discount,
            player_owned_ship, player_ship_catalog,
        ),
        _build_enemy(enemy_spec, enemy_pos),
    )
