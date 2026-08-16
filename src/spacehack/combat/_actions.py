"""Combat action resolution — damage, turns, movement.

Each function here performs a discrete combat action: checking
whether an action is affordable, resolving damage against a
target, resetting per-turn resources, or moving an entity.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from .. import world
from ._types import EnemyInstance
from ._stats import _roll_ap
from ..data.weapons import find_weapon
from ..data.modules import find_module as find_module_spec
from ..engine import RNG

if TYPE_CHECKING:
    from ..ship import OwnedShip


# Max number of loot entities allowed on the map at once.
# Beyond this, oldest loot is removed when new loot spawns.
_MAX_LOOT_ENTITIES: int = 30


def _append_loot_entity(
    game_map: world.GameMap,
    pos: world.Position,
    loot_data: dict,
) -> None:
    """Append one neutral loot entity with the supplied payload."""
    game_map.entities.append(world.Entity(
        char="%", fg=(255, 215, 0),
        pos=pos,
        name="Loot", width=1, height=1,
        loot_data=loot_data,
    ))


def _spawn_loot_at_position(
    game_map: world.GameMap,
    pos: world.Position,
    loot_pool: tuple[str, ...],
    count_range: tuple[int, int] = (1, 2),
    qty_range: tuple[int, int] = (1, 2),
) -> None:
    """Drop trade-good loot items at a death position using the pool."""
    _items = list(loot_pool) or ["scrap_metal"]
    _min_c, _max_c = count_range
    _count = RNG.randint(_min_c, _max_c)
    for _ in range(_count):
        _good_id = RNG.choice(_items)
        _qty = RNG.randint(qty_range[0], qty_range[1])
        _append_loot_entity(
            game_map, pos,
            {"good_id": _good_id, "quantity": _qty},
        )


def _spawn_equipment_loot_at_position(
    game_map: world.GameMap,
    pos: world.Position,
    equipment_pool: tuple[tuple[str, str], ...],
    count_range: tuple[int, int] = (0, 1),
) -> None:
    """Drop ground-equipment loot using ``(item_type, item_id)`` entries."""
    if not equipment_pool:
        return
    _min_c, _max_c = count_range
    _count = RNG.randint(_min_c, _max_c)
    for _ in range(_count):
        item_type, item_id = RNG.choice(equipment_pool)
        _append_loot_entity(
            game_map, pos,
            {"item_type": item_type, "item_id": item_id},
        )


def _spawn_field_item_loot_at_position(
    game_map: world.GameMap,
    pos: world.Position,
    item_pool: tuple[tuple[str, str], ...],
    count_range: tuple[int, int] = (0, 1),
) -> None:
    """Drop authored ammo/consumable stacks with valid quantities."""
    if not item_pool:
        return
    from ..ground_equipment import item_stack_capacity

    _min_c, _max_c = count_range
    for _ in range(RNG.randint(_min_c, _max_c)):
        item_type, item_id = RNG.choice(item_pool)
        try:
            _max_quantity = item_stack_capacity(item_type, item_id)
        except (KeyError, ValueError):
            continue
        _quantity = RNG.randint(1, min(5, _max_quantity))
        _append_loot_entity(
            game_map, pos,
            {
                "item_type": item_type,
                "item_id": item_id,
                "quantity": _quantity,
            },
        )


def set_combat_locks(locked: bool, entities) -> None:
    """Mark/unmark entities so ambient patrol systems leave them alone.

    Both combat rule sets freeze their participants during a fight:
    ``npc_ships.move_npcs`` (space) and ``ground_npcs.move_ground_npcs``
    (ground) skip entities carrying ``combat_locked``, so engaged
    enemies are neither patrolled toward body goals nor despawned at
    gates/planets mid-fight (the "enemy disappeared" bug) — their
    only mover is the combat AI.

    ``combat_locked`` is a transient runtime flag: never serialized
    (entities only persist declared dataclass fields on save) and
    cleared by each rules module's ``sync_state`` when the fight ends.
    ``None`` entries are skipped so callers can pass heterogeneous
    lists safely.
    """
    for _ent in entities:
        if _ent is None:
            continue
        if locked:
            _ent.combat_locked = True
        else:
            try:
                del _ent.combat_locked
            except AttributeError:
                pass


def _remove_dead_entity(
    game_map: world.GameMap,
    enemy_ents: dict,
    target_idx: int,
) -> None:
    """Remove a destroyed enemy's world entity from the game map.

    Pops the entity from ``enemy_ents`` by index and removes it from
    ``game_map.entities`` so its glyph doesn't linger on screen.
    No-op if the index is not in the mapping.
    """
    _dead_ent = enemy_ents.pop(target_idx, None)
    if _dead_ent is not None and _dead_ent in game_map.entities:
        game_map.entities.remove(_dead_ent)


def _spawn_loot_drops(
    game_map: world.GameMap,
    target_pos: world.Position,
    enemy_spec,
) -> None:
    """Spawn 1-2 loot items near a destroyed enemy ship.

    Caps total loot entities at :data:`_MAX_LOOT_ENTITIES` — removes
    the oldest loot first to prevent unbounded entity-list growth.
    Uses the shared :func:`_spawn_loot_at_position` for the actual
    entity creation so both ship and ground loot behave identically.
    """
    _spec_loot = getattr(enemy_spec, 'cargo_goods', None) or ()
    _loot_items = list(_spec_loot)
    if not _loot_items:
        _loot_items = ["scrap_metal"]

    _drop_count = max(1, min(len(_loot_items), RNG.randint(1, 2)))
    _existing_loot = [e for e in game_map.entities if e.loot_data is not None]
    _excess = max(0, len(_existing_loot) + _drop_count - _MAX_LOOT_ENTITIES)
    for _ in range(_excess):
        if _existing_loot:
            try:
                game_map.entities.remove(_existing_loot[0])
            except ValueError:
                pass
            _existing_loot.pop(0)

    for _li in range(_drop_count):
        _lx = target_pos.x + RNG.randint(-1, 1)
        _ly = target_pos.y + RNG.randint(-1, 1)
        if not game_map.is_walkable(_lx, _ly):
            _lx, _ly = target_pos.x, target_pos.y
        _loot_pos = world.Position(_lx, _ly)
        _spawn_loot_at_position(
            game_map, _loot_pos,
            tuple(_loot_items),
            count_range=(1, 1),
            qty_range=(1, 3),
        )


def can_afford_action(
    player_state: dict, slot_idx: int, *, ap_mult: int = 1,
    power_mult: int = 1,
) -> tuple[bool, str]:
    """Check if the player can fire the weapon in ``slot_idx``.

    Ammo is keyed by weapon SLOT index. ``ap_mult``/``power_mult``
    scale the AP and power costs (the Focus trait doubles them for
    the single enabled weapon). Returns ``(ok, reason)``.
    """
    _weapons = player_state.get("weapons", ())
    if not (0 <= slot_idx < len(_weapons)):
        return False, "Unknown weapon"
    weapon_id = _weapons[slot_idx]
    try:
        ws = find_weapon(weapon_id)
    except KeyError:
        return False, "Unknown weapon"

    _ap_discount = (
        player_state.get("plasma_ap_discount", 0)
        if ws.slot_type == "plasma" else 0
    )
    _effective_ap = max(1, ws.ap_cost - _ap_discount) * ap_mult
    if player_state["ap_remaining"] < _effective_ap:
        return False, f"Need {_effective_ap} AP (have {player_state['ap_remaining']})"

    if ws.slot_type in ("energy", "plasma"):
        _power_needed = ws.power_cost * power_mult
        if player_state["power_pool"] < _power_needed:
            return False, f"Need {_power_needed} power (have {player_state['power_pool']})"
    elif ws.slot_type == "missile":
        ammo = player_state["weapon_ammo"].get(slot_idx, 0)
        if ammo <= 0:
            return False, "Out of ammo"
        if ammo < ws.ammo_per_shot:
            return False, f"Need {ws.ammo_per_shot} ammo (have {ammo})"

    return True, ""


def _damage_quality(target_pilot_piloting: int) -> tuple[float, bool]:
    """Roll damage quality and return its multiplier plus glancing state."""
    quality = RNG.randint(1, 100)
    threshold = int(target_pilot_piloting * 0.5)
    if quality <= threshold:
        return 0.5, True
    return 0.5 + (quality - threshold) / max(1, 100 - threshold), False


def _apply_hull_and_shields(
    damage: int, target_hull: int, target_shields: int,
) -> tuple[int, int, int]:
    """Split damage between shields and hull and return final hull."""
    shield_damage = min(damage, target_shields) if target_shields > 0 else 0
    hull_damage = damage - shield_damage
    return hull_damage, shield_damage, max(0, target_hull - hull_damage)


def resolve_damage(
    weapon_id: str,
    target_hull: int,
    target_shields: int,
    target_pilot_piloting: int = 0,
    damage_taken_mult: float = 1.0,
) -> tuple[int, int, int, bool]:
    """Apply weapon damage and return hull, shield, final-hull, glancing state."""
    weapon = find_weapon(weapon_id)
    if weapon.shield_strip > 0:
        strip = min(weapon.shield_strip, target_shields)
        return 0, strip, target_hull, False
    quality, is_glancing = _damage_quality(target_pilot_piloting)
    raw_damage = weapon.damage * quality * RNG.uniform(0.8, 1.2)
    damage = max(1, int(raw_damage * damage_taken_mult))
    hull_damage, shield_damage, final_hull = _apply_hull_and_shields(
        damage, target_hull, target_shields,
    )
    return hull_damage, shield_damage, final_hull, is_glancing


def _reset_ap_carry(player_state: dict) -> None:
    """Roll the next round's fractional AP pool (gain + carry).

    TE4-style speed: the banked twentieths plus this round's gain form
    the pool; the integer part is spendable and the remainder rolls
    forward, so every point of Piloting shifts the average AP.
    """
    _avail, _carry = _roll_ap(
        player_state.get("ap_carry_twentieths", 0),
        player_state.get("ap_gain_twentieths", 60 + player_state.get("piloting", 10)),
    )
    player_state["ap_carry_twentieths"] = _carry
    player_state["ap_total"] = _avail
    player_state["ap_remaining"] = _avail


def start_player_turn(player_state: dict) -> None:
    """Reset per-turn resources for the player and apply shield regen.

    Shield regen uses two tiers:
      - Base rate (player-set via S key): costs power, proportional,
        with engineering discount.
      - Module bonus (shield_recharge_bonus): free regen, no power cost.
    AP is reset by :func:`_reset_ap_carry` (fractional with carry).
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
    _reset_ap_carry(player_state)
    player_state["cells_moved_this_turn"] = 0


def start_enemy_turn(enemy: EnemyInstance) -> None:
    """Reset per-turn resources for an enemy and apply shield regen.

    Mirrors :func:`start_player_turn` — base regen costs power with
    engineering discount; module recharge bonus is free. AP uses the
    same fractional regeneration with carry as the player.
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
    _avail, _carry = _roll_ap(enemy.ap_carry_twentieths, enemy.ap_gain_twentieths)
    enemy.ap_carry_twentieths = _carry
    enemy.ap_total = _avail
    enemy.ap_remaining = _avail
    enemy.cells_moved_this_turn = 0


def _sync_back_hull(player_state: dict, player_owned_ship: OwnedShip | None) -> None:
    """Persist combat hull damage back to the player's OwnedShip."""
    if player_owned_ship is None:
        return
    max_hull = player_state.get("max_hull", 100)
    current_hull = player_state.get("hull", max_hull)
    new_dmg_pct = 100 - (current_hull * 100 // max(max_hull, 1))
    player_owned_ship.hull_damage_pct = max(0, min(100, new_dmg_pct))


def _sync_back_ammo(player_state: dict, player_owned_ship: OwnedShip | None) -> None:
    """Persist remaining missile ammo back to the player's OwnedShip.

    Spent rounds stay spent: combat consumes from ``player_state["weapon_ammo"]``
    and this writes the survivors back so the next fight starts with the
    same depleted magazines. Energy weapons (ammo -1) are left untouched.
    """
    if player_owned_ship is None:
        return
    _owned_ammo = getattr(player_owned_ship, 'weapon_ammo', None)
    if _owned_ammo is None:
        return
    # Keys are weapon slot indices (matches OwnedShip.weapon_ammo).
    for _slot, _ammo in player_state.get("weapon_ammo", {}).items():
        if _ammo >= 0:
            _owned_ammo[_slot] = _ammo


def move_entity(
    pos: world.Position,
    dx: int,
    dy: int,
    game_map: world.GameMap,
    *,
    exclude: world.Entity | None = None,
) -> tuple[world.Position, bool]:
    """Try to move an entity by (dx, dy). Returns (new_pos, success).

    Blocks on walls and on any entity footprint other than ``exclude``
    (the mover) — combatants can't stack on each other, matching
    :func:`world.try_move` collision semantics used everywhere else.

    .. note::

        Only the single target cell at ``(nx, ny)`` is validated.
        Multi-cell entities (width > 1 or height > 1) would need
        a full-footprint collision sweep. Currently all combatants
        are 1×1 so this is sufficient; revisit when multi-cell
        ships ever move in combat.
    """
    nx = pos.x + dx
    ny = pos.y + dy
    if not game_map.is_walkable(nx, ny):
        return pos, False
    if game_map.blocking_entity_at(nx, ny, exclude=exclude) is not None:
        return pos, False
    return world.Position(nx, ny), True
