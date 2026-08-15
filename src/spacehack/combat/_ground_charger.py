"""Charger trait helpers for ground combat.

This module keeps the pathfinding and dynamic-range rules out of the
already-large ground combat rules module.
"""

from __future__ import annotations

from .. import world
from ..data.ground_weapons import find_ground_weapon as _find_gw
from ._stats import _distance


_CHARGE_TILES = "_ground_charge_tiles"


def is_charger_melee(ctx, weapon_id: str) -> bool:
    """Whether ``weapon_id`` gets Charger behavior for this player."""
    try:
        return (
            "charger" in getattr(ctx, "player_traits", ())
            and _find_gw(weapon_id).damage_type == "melee"
        )
    except KeyError:
        return False


def weapon_range(weapon_id: str, ctx, current_ap: int) -> tuple[int, int]:
    """Return the player's effective ``(min, max)`` weapon range."""
    setattr(ctx, "_ground_ap", current_ap)
    _spec = _find_gw(weapon_id)
    if is_charger_melee(ctx, weapon_id):
        return _spec.min_range, max(1, current_ap)
    return _spec.min_range, _spec.max_range


def charge_path(ctx, target, game_map: world.GameMap, max_steps: int):
    """Return the shortest walkable path to a cell beside ``target``."""
    if max_steps <= 0:
        return None
    _target = target.pos
    _candidates = {
        (_target.x + _dx, _target.y + _dy)
        for _dx in (-1, 0, 1)
        for _dy in (-1, 0, 1)
        if (_dx, _dy) != (0, 0)
    }
    _candidates = {
        _cell for _cell in _candidates
        if game_map.in_bounds(*_cell)
        and game_map.is_walkable(*_cell)
        and game_map.blocking_entity_at(*_cell, exclude=ctx.player) is None
    }
    if not _candidates:
        return None
    _path = world.find_path(
        (ctx.player.pos.x, ctx.player.pos.y),
        _candidates,
        game_map,
        exclude_entity=ctx.player,
    )
    if _path is None or len(_path) > max_steps:
        return None
    return _path


def charge_tiles(ctx) -> int:
    """Return the transient tile count for the current attack."""
    return int(getattr(ctx, _CHARGE_TILES, 0))


def prepare_attack(ctx, game_map: world.GameMap, target, weapon_id: str) -> None:
    """Move a ranged Charger attack to the target's adjacent cell."""
    setattr(ctx, _CHARGE_TILES, 0)
    if not (is_charger_melee(ctx, weapon_id)
            and int(_distance(ctx.player.pos, target.pos)) > 1):
        return
    _path = charge_path(ctx, target, game_map, getattr(ctx, "_ground_ap", 0))
    if not _path:
        return
    ctx.player.pos = world.Position(*_path[-1])
    setattr(ctx, _CHARGE_TILES, len(_path))
    from ..dungeon import reveal_around
    reveal_around(game_map, ctx.player.pos, radius=game_map.sight_radius)


def clear_attack_modifier(ctx) -> None:
    """Clear the transient Charger bonus after one weapon resolves."""
    setattr(ctx, _CHARGE_TILES, 0)


def attack_ap_cost(ctx, weapon_id: str, current_ap: int) -> int:
    """Return the AP cost, with a Charger lunge consuming the full pool."""
    return current_ap if charge_tiles(ctx) > 0 else _find_gw(weapon_id).ap_cost


def record_player_kill(ctx, weapon_id: str) -> None:
    """Track kills made with melee weapons for the Charger requirement."""
    if _find_gw(weapon_id).damage_type == "melee" and hasattr(ctx, "player_counters"):
        ctx.player_counters.melee_kills += 1


def charge_bonuses(tiles_moved: int) -> tuple[int, int]:
    """Return ``(hit_percent, damage)`` for a Charger lunge."""
    _tiles = max(0, tiles_moved)
    return _tiles * 5, _tiles

