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
from ..data.quality import quality_multiplier
from ..engine import RNG
from ..loot_common import equipment_payload, loot_fg

if TYPE_CHECKING:
    from ..ship import OwnedShip


def _append_loot_entity(
    game_map: world.GameMap,
    pos: world.Position,
    loot_data: dict,
) -> None:
    """Append one neutral loot entity with the supplied payload."""
    game_map.entities.append(world.Entity(
        char="%", fg=loot_fg(loot_data),
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


def roll_carried_consumables(spec) -> list[list]:
    """Pre-roll the consumables an enemy CARRIES (doc 48 SETTLED 36):
    the consumable entries of ``field_item_loot_pool`` resolve onto the
    fighter as live items — what they drop is what they carry, used
    items are consumed and never drop. Same distribution the death
    roll uses; ammo/equipment entries keep their death-time roll."""
    from ..ground_equipment import item_stack_capacity

    _pool = tuple(
        _entry for _entry in spec.field_item_loot_pool
        if _entry[0] == "consumable"
    )
    if not _pool:
        return []
    _min_c, _max_c = spec.field_item_loot_count
    _carried: list[list] = []
    for _ in range(RNG.randint(_min_c, _max_c)):
        item_type, item_id = RNG.choice(_pool)
        try:
            _max_quantity = item_stack_capacity(item_type, item_id)
        except (KeyError, ValueError):
            continue
        _carried.append([
            item_type, item_id, RNG.randint(1, _drop_ceiling(item_type, item_id, _max_quantity)),
        ])
    return _carried


def _drop_stamped_carried(
    game_map: world.GameMap, pos: world.Position,
    item_pool: tuple[tuple[str, str], ...], carried: list,
) -> tuple[tuple[str, str], ...]:
    """Drop the carried stamp's unused consumable charges at their
    remainder qty (doc 48 SETTLED 36) and return the pool the
    death-time roll still owns — the non-consumable entries."""
    for _entry in carried:
        _item_type, _item_id, _quantity = _entry
        if _quantity > 0:
            _append_loot_entity(
                game_map, pos,
                {
                    "item_type": _item_type,
                    "item_id": _item_id,
                    "quantity": _quantity,
                },
            )
    return tuple(
        _entry for _entry in item_pool if _entry[0] != "consumable"
    )


def _drop_ceiling(item_type: str, item_id: str, stack_cap: int) -> int:
    """A drop's quantity ceiling — the shared law lives in
    :func:`ground_equipment.drop_quantity_ceiling` (one home since the
    carried-pool roll joined it, doc 48 SETTLED 43)."""
    from ..ground_equipment import drop_quantity_ceiling

    return drop_quantity_ceiling(item_type, item_id, stack_cap)


def _spawn_field_item_loot_at_position(
    game_map: world.GameMap,
    pos: world.Position,
    item_pool: tuple[tuple[str, str], ...],
    count_range: tuple[int, int] = (0, 1),
    *,
    carried: list | None = None,
    retired_ammo_types: frozenset[str] = frozenset(),
) -> None:
    """Drop authored ammo/consumable stacks with valid quantities.

    A present ``carried`` stamp (doc 48 SETTLED 36) is the ONE
    resolution for the consumable entries — unused charges drop, used
    ones never do. ``retired_ammo_types`` (the loadout's own ammo-fed
    weapons' types, doc 48 SETTLED 43) hands THOSE ammo entries to the
    kit drop's remainder-of-carried — their death-time roll retires,
    fought-dry included; authored ammo no carried weapon feeds (the
    machines' energy cells) keeps rolling. No stamps: today's roll.
    """
    if carried is not None:
        item_pool = _drop_stamped_carried(game_map, pos, item_pool, carried)
    if retired_ammo_types:
        item_pool = _retire_carried_ammo(item_pool, retired_ammo_types)
    _spawn_field_item_rolls(game_map, pos, item_pool, count_range)


def _retire_carried_ammo(
    item_pool: tuple[tuple[str, str], ...],
    retired_ammo_types: frozenset[str],
) -> tuple[tuple[str, str], ...]:
    """Filter the authored pool's ammo entries feeding a carried ammo
    type (unknown item ids roll on — the count loop skips them)."""
    from ..data.ground_items import find_ground_ammo

    _kept = []
    for _entry in item_pool:
        if _entry[0] == "ammo":
            try:
                _feeds = find_ground_ammo(_entry[1]).ammo_type
            except KeyError:
                _kept.append(_entry)
                continue
            if _feeds in retired_ammo_types:
                continue
        _kept.append(_entry)
    return tuple(_kept)


def _spawn_field_item_rolls(
    game_map: world.GameMap, pos: world.Position,
    item_pool: tuple[tuple[str, str], ...],
    count_range: tuple[int, int],
) -> None:
    """The death-time roll over the surviving authored entries (empty
    pools no-op)."""
    from ..ground_equipment import item_stack_capacity

    if not item_pool:
        return
    _min_c, _max_c = count_range
    for _ in range(RNG.randint(_min_c, _max_c)):
        item_type, item_id = RNG.choice(item_pool)
        try:
            _max_quantity = item_stack_capacity(item_type, item_id)
        except (KeyError, ValueError):
            continue
        _quantity = RNG.randint(1, _drop_ceiling(item_type, item_id, _max_quantity))
        _append_loot_entity(
            game_map, pos,
            {
                "item_type": item_type,
                "item_id": item_id,
                "quantity": _quantity,
            },
        )


def _spawn_kit_drop(game_map: world.GameMap, pos, loadout=None) -> None:
    """Diegetic kit drop (doc 47.1 + 48 SETTLED 43/51): BOTH carried set
    weapons fall at their equip-time stamped qualities — no re-roll
    (doc 47.2 SETTLED 13), what they carried is what drops — the WORN
    cyber pieces beside them at their stamped qualities (what they wear
    is what drops), plus the carried pool's REMAINDER as the ammo stacks, deterministic: the
    death-time ammo roll is retired (what drops reflects the fight;
    shot-starving is a minor play). Organic/unwieldable weapons
    (``loot_droppable=False``) never drop; a slot pair sharing one id
    drops it once (the raider's knife-in-both-slots corner).
    """
    if not loadout:
        return
    from .. import ground_loadout

    _dropped: set[str] = set()
    for _set_name in (ground_loadout.SET_RANGED, ground_loadout.SET_MELEE):
        _drop_set_weapon(game_map, pos, loadout, _set_name, _dropped)
    for _entry in ground_loadout.worn_entries(loadout):
        _append_loot_entity(
            game_map, pos,
            equipment_payload("armor", _entry.item_id, _entry.quality),
        )
    for _item_type, _item_id, _qty in ground_loadout.pool_entries(loadout):
        _append_loot_entity(
            game_map, pos,
            {"item_type": _item_type, "item_id": _item_id, "quantity": _qty},
        )


def _drop_set_weapon(game_map, pos, loadout, set_name, dropped) -> None:
    """One carried set's weapon falls at its stamped quality — no
    re-roll, wieldable catalog pieces only, one copy per shared id."""
    from .. import ground_loadout
    from ..data.ground_weapons import find_ground_weapon

    _pair = ground_loadout.pair_for(loadout, set_name)
    if _pair is None or _pair[0] in dropped:
        return
    try:
        _ws = find_ground_weapon(_pair[0])
    except KeyError:
        return
    if not _ws.loot_droppable:
        return
    dropped.add(_pair[0])
    _append_loot_entity(
        game_map, pos, equipment_payload("weapon", _ws.id, _pair[1]),
    )


def _spawn_tinker_kit_drop(game_map: world.GameMap, pos, spec) -> None:
    """The tinker-kit kill roll (doc 47.5 SETTLED 34 as amended by
    doc 48 SETTLED 58): a 1-in-N drip on LOOT-PAYING kills — humanoid
    and machine corpses; fauna never (a viper dropping a toolkit is
    the same nonsense as rations). Wreck and dig-scatter rates are
    untouched site channels."""
    from ..data.npc_chars import loot_class
    from ..data.quality import KIT_KILL_RATE
    from ..ground_consumables import kit_drop_payload

    if loot_class(spec) not in ("humanoid", "machine"):
        return
    if RNG.randint(1, KIT_KILL_RATE) != 1:
        return
    _append_loot_entity(game_map, pos, kit_drop_payload())


def spawn_kill_drops(
    game_map: world.GameMap, pos, spec, ctx, loadout: dict | None = None,
    *, band: int = 0, carried: list | None = None,
) -> None:
    """The full ground-kill drop sequence (doc 47.1): authored pools,
    the kit drop, the site-reveal pad, then the shared entity cap.

    ``spec`` is an ``NpcCharSpec``; ``ctx`` feeds the pad door only;
    ``loadout`` is the entity's two-set stamp (doc 48 SETTLED 43) —
    the kit drop reads BOTH weapons and the carried pool's remainder
    off it; ``band`` sizes the drop-time quality ladder (doc 48
    SETTLED 35); ``carried`` is the entity's pre-rolled consumable
    stamp (doc 48 SETTLED 36) — unused charges drop, used ones never
    do. Pools land before the kit drop so extras age out of the cap
    first; the tinker-kit roll draws last (seeded-order).
    """
    from ..digs import maybe_spawn_ground_pad

    _spawn_authored_pools(game_map, pos, spec, loadout, band, carried)
    _spawn_kit_drop(game_map, pos, loadout)
    maybe_spawn_ground_pad(ctx, game_map, pos, spec.id)
    _spawn_tinker_kit_drop(game_map, pos, spec)


def _spawn_authored_pools(
    game_map: world.GameMap, pos: world.Position, spec,
    loadout: dict | None, band: int, carried: list | None,
) -> None:
    """The authored pool sequence (doc 47.1 as amended by 48 SETTLED
    56): trade goods, then field items — the equipment-extras channel
    retired with the carried-loot doctrine (what they drop is what
    they carried). Ammo entries feeding a CARRIED ammo type retire to
    the kit drop's remainder (doc 48 SETTLED 43)."""
    from .. import ground_loadout

    if spec.loot_pool:
        _min, _max = spec.loot_count
        # A guaranteed single-entry pool is THE one thing the corpse
        # pays (an apex trophy, SETTLED 57): exactly one unit. Pocket
        # change keeps the 1-2 unit roll.
        _one_thing = (_min, _max) == (1, 1) and len(spec.loot_pool) == 1
        _spawn_loot_at_position(
            game_map, pos, spec.loot_pool,
            count_range=(_min, _max),
            qty_range=(1, 1) if _one_thing else (1, 2),
        )
    if spec.field_item_loot_pool:
        _spawn_field_item_loot_at_position(
            game_map, pos, spec.field_item_loot_pool,
            count_range=spec.field_item_loot_count, carried=carried,
            retired_ammo_types=frozenset(
                ground_loadout.magazine_ammo_types(loadout),
            ),
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

    Uses the shared :func:`_spawn_loot_at_position` for the actual
    entity creation so both ship and ground loot behave identically.
    """
    _spec_loot = getattr(enemy_spec, 'cargo_goods', None) or ()
    _loot_items = list(_spec_loot)
    if not _loot_items:
        _loot_items = ["scrap_metal"]

    _drop_count = max(1, min(len(_loot_items), RNG.randint(1, 2)))

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
    _ap, _power, _ammo = weapon_costs(
        ws, ap_discount=_ap_discount, ap_mult=ap_mult, power_mult=power_mult,
    )
    if player_state["ap_remaining"] < _ap:
        return False, f"Need {_ap} AP (have {player_state['ap_remaining']})"

    if _power:
        if player_state["power_pool"] < _power:
            return False, f"Need {_power} power (have {player_state['power_pool']})"
    elif _ammo:
        ammo = player_state["weapon_ammo"].get(slot_idx, 0)
        if ammo <= 0:
            return False, "Out of ammo"
        if ammo < _ammo:
            return False, f"Need {_ammo} ammo (have {ammo})"

    return True, ""


def weapon_costs(ws, *, ap_discount: int = 0, ap_mult: int = 1,
                 power_mult: int = 1) -> tuple[int, int, int]:
    """One weapon's real fire costs — ``(ap, power, ammo_per_shot)``.

    The ONE slot-type economy table both sides read (doc 48 SETTLED
    39): energy/plasma pay power, missiles pay rounds; the plasma AP
    discount and Focus trait mults fold in on the player's side.
    """
    ap = max(1, ws.ap_cost - ap_discount) * ap_mult
    power = ws.power_cost * power_mult if ws.slot_type in ("energy", "plasma") else 0
    ammo = ws.ammo_per_shot if ws.slot_type == "missile" else 0
    return ap, power, ammo


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
    *,
    weapon_quality: int = 0,
) -> tuple[int, int, int, bool]:
    """Apply weapon damage and return hull, shield, final-hull, glancing state.

    ``weapon_quality`` is the SHOOTER's flown weapon tier (doc 48.7):
    quality multiplies damage — both sides pass their rolled instance
    tier (enemy fire and the player's flown weapons alike)."""
    weapon = find_weapon(weapon_id)
    if weapon.shield_strip_pct > 0:
        # The boss-key (doc 56 SETTLED 34): strips ALL current shields
        # — the magazine (2/flight, restocked at a mechanic) is the
        # balance lever, never the strip.
        return 0, target_shields, target_hull, False
    if weapon.shield_strip > 0:
        strip = min(weapon.shield_strip, target_shields)
        return 0, strip, target_hull, False
    quality, is_glancing = _damage_quality(target_pilot_piloting)
    _gear_mult = quality_multiplier("weapon", weapon_quality)
    raw_damage = weapon.damage * _gear_mult * quality * RNG.uniform(0.8, 1.2)
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


def divert_full_cost(enemy: EnemyInstance) -> int:
    """The full-rate power price of one paid shield divert (doc 48
    SETTLED 40). ONE expression shared by the payer
    (:func:`start_enemy_turn`) and the AI's conservation reserve (doc
    57.2.5) — the twin must never drift."""
    return max(1, enemy.shield_regen_rate - enemy.pilot_engineering // 20)


def start_enemy_turn(enemy: EnemyInstance) -> None:
    """Reset per-turn resources for an enemy and apply shield regen.

    Mirrors :func:`start_player_turn` — base regen costs power with
    engineering discount; the free tier (hull base + module bonus,
    folded at build — doc 48 SETTLED 39) needs no power. AP uses the
    same fractional regeneration with carry as the player.
    """
    enemy.power_pool = min(enemy.max_power, enemy.power_pool + enemy.power_gen)
    if enemy.max_shields > 0 and enemy.shields < enemy.max_shields:
        room = enemy.max_shields - enemy.shields
        # Tier 1: paid divert from the spec's authored rate (doc 48
        # SETTLED 40) — the AI's S-dial, fired only while shields sit
        # below the spec's threshold of max (default half); power
        # availability bounds it below.
        _below_threshold = enemy.shields < (
            enemy.shield_regen_threshold * enemy.max_shields
        )
        if enemy.shield_regen_rate > 0 and _below_threshold:
            full_cost = divert_full_cost(enemy)
            paid_regen = min(enemy.shield_regen_rate, room, enemy.power_pool * enemy.shield_regen_rate // full_cost)
            if paid_regen > 0:
                paid_cost = (paid_regen * full_cost + enemy.shield_regen_rate - 1) // enemy.shield_regen_rate
                paid_cost = min(paid_cost, enemy.power_pool)
                enemy.power_pool -= paid_cost
                enemy.shields += paid_regen
                room -= paid_regen
        # Tier 2: free regen — the build-time hull+module term.
        if enemy.shield_recharge_bonus > 0 and room > 0:
            enemy.shields += min(enemy.shield_recharge_bonus, room)
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


def apply_knockback(
    game_map: world.GameMap,
    entity: world.Entity,
    dx: int,
    dy: int,
    distance: int,
) -> int:
    """Displace ``entity`` one cell at a time along ``(dx, dy)`` for up
    to ``distance`` cells — the game's first involuntary displacement
    (doc 48 SETTLED 42, the Warden's slam; the property is weapon
    data, so player-side weapons may carry it someday).

    A wall or an occupied cell stops the ride early (no stacking);
    pure displacement — NO collision damage (not ruled; keep it
    pure). Returns the cells actually moved; ``0`` when even the
    first step is blocked.
    """
    moved = 0
    for _ in range(max(0, distance)):
        _new, _ok = move_entity(
            entity.pos, dx, dy, game_map, exclude=entity,
        )
        if not _ok:
            break
        entity.pos = _new
        moved += 1
    return moved
