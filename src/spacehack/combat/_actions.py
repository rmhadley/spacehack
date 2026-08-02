"""Combat action resolution — damage, turns, movement.

Each function here performs a discrete combat action: checking
whether an action is affordable, resolving damage against a
target, resetting per-turn resources, or moving an entity.
"""

from __future__ import annotations

from .. import world
from ._types import EnemyInstance
from ..data.weapons import find_weapon
from ..data.modules import find_module as find_module_spec
from ..engine import RNG


# Max number of loot entities allowed on the map at once.
# Beyond this, oldest loot is removed when new loot spawns.
_MAX_LOOT_ENTITIES: int = 30


def _spawn_loot_at_position(
    game_map: world.GameMap,
    pos: world.Position,
    loot_pool: tuple[str, ...],
    count_range: tuple[int, int] = (1, 2),
    qty_range: tuple[int, int] = (1, 2),
) -> None:
    """Drop loot items at a death position using the given loot pool.

    Shared by both ship combat (:func:`_spawn_loot_drops`) and ground
    combat (:func:`spacehack.combat._ground._spawn_ground_loot`) so
    loot-spawning behavior stays consistent between systems.
    """
    _items = list(loot_pool)
    if not _items:
        _items = ["scrap_metal"]
    _min_c, _max_c = count_range
    _count = RNG.randint(_min_c, _max_c)
    for _ in range(_count):
        _good_id = RNG.choice(_items)
        _qty = RNG.randint(qty_range[0], qty_range[1])
        game_map.entities.append(world.Entity(
            char="%", fg=(255, 215, 0),
            pos=pos,
            name="Loot", width=1, height=1,
            loot_data={"good_id": _good_id, "quantity": _qty},
        ))


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

    if ws.slot_type in ("energy", "plasma"):
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

    # EMP shield-stripper: on hit, strip shields instead of dealing
    # hull damage. Ignores armor/hull entirely; runs before the normal
    # damage path so 0-damage EMPs never fall into the 1-damage floor.
    if ws.shield_strip > 0:
        strip = min(ws.shield_strip, target_shields)
        return 0, strip, target_hull, False

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
    for _wid, _ammo in player_state.get("weapon_ammo", {}).items():
        if _ammo >= 0:
            _owned_ammo[_wid] = _ammo


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
