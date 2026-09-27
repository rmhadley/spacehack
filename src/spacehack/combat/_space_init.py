"""Space-combat init helpers — enemy construction and entity matching.

Split from ``_rules_space`` (the architecture ratchet, doc 49 phase 2):
the four init-time builders take their inputs explicitly and never
touch the rules module's session global, so they live here beside the
init flow that calls them. ``init`` remains the only caller.
"""

from __future__ import annotations

from typing import Any

from .. import world
from ._stats import init_combat_state
from ._types import EnemyInstance


def build_initial_enemies(
    ctx,
    player_ship_catalog,
    player_owned_ship,
    player_pos: world.Position,
    player_pilot_skills,
    enemy_specs: list,
    enemy_positions: list[world.Position],
    *,
    ap_bonus: int,
    plasma_ap_discount: int,
    max_power_bonus: int,
) -> tuple[dict, list[EnemyInstance]]:
    """Build the player state dict + one EnemyInstance per enemy spec.

    The three trait knobs arrive resolved (the ace-pilot / plasma-
    savant / systems-expert bonus helpers) so this module stays
    trait-free.
    """
    _enemy_insts: list[EnemyInstance] = []
    _player_state: dict = {}
    for _i in range(len(enemy_specs)):
        _ps, _ei = init_combat_state(
            player_ship_catalog, player_owned_ship,
            player_pos, player_pilot_skills,
            enemy_specs[_i], enemy_positions[_i],
            ap_bonus=ap_bonus,
            plasma_ap_discount=plasma_ap_discount,
            max_power_bonus=max_power_bonus,
        )
        if _i == 0:
            _player_state = _ps
        _enemy_insts.append(_ei)
    return _player_state, _enemy_insts


def find_player_entity(game_map: world.GameMap) -> Any:
    """Return the owned (player) entity on the map, or None."""
    for _e in game_map.entities:
        if getattr(_e, 'owned', False):
            return _e
    return None


def flown_weapons(player_owned_ship) -> tuple[list, list]:
    """``(weapons_list, weapon_qualities)`` for the flown instance
    entries (doc 48.7) — bare ids migrate to base-quality items."""
    _flown = getattr(player_owned_ship, 'weapons', ()) or ()
    _weapons_list = [
        entry.item_id if hasattr(entry, "item_id") else entry for entry in _flown
    ]
    _weapon_qualities = [
        getattr(entry, "quality", 0) for entry in _flown
    ]
    return _weapons_list, _weapon_qualities


def match_enemy_entities(
    game_map: world.GameMap, player_ent: Any, enemy_insts: list[EnemyInstance],
) -> dict[int, Any]:
    """Map each enemy instance to its entity, stamping display names."""
    _enemy_ents: dict[int, Any] = {}
    _matched: set[int] = set()
    for _i, _inst in enumerate(enemy_insts):
        for _e in game_map.entities:
            if _e is player_ent or getattr(_e, 'owned', False):
                continue
            if id(_e) in _matched:
                continue
            if _e.pos.x == _inst.pos.x and _e.pos.y == _inst.pos.y:
                _enemy_ents[_i] = _e
                _matched.add(id(_e))
                break
        _ent = _enemy_ents.get(_i)
        if _ent is not None and getattr(_ent, 'name', ''):
            _inst.name = _ent.name
    return _enemy_ents


def dedupe_enemy_positions(
    game_map: world.GameMap, enemy_insts: list[EnemyInstance],
) -> None:
    """Shift overlapping enemy instances onto distinct walkable cells."""
    _occupied: set[tuple[int, int]] = set()
    for _inst in enemy_insts:
        _key = (_inst.pos.x, _inst.pos.y)
        if _key not in _occupied:
            _occupied.add(_key)
            continue
        _placed = False
        for _odx, _ody in [(-1, 0), (1, 0), (0, -1), (0, 1), (-1, -1), (1, -1), (-1, 1), (1, 1)]:
            _nk = (_inst.pos.x + _odx, _inst.pos.y + _ody)
            if _nk not in _occupied and game_map.in_bounds(*_nk) and game_map.is_walkable(*_nk):
                _inst.pos = world.Position(*_nk)
                _occupied.add(_nk)
                _placed = True
                break
        if not _placed:
            _inst.pos = world.Position(_inst.pos.x + 2, _inst.pos.y)
            _attempts = 0
            while (_inst.pos.x, _inst.pos.y) in _occupied and _attempts < 20:
                _nx = _inst.pos.x + 1
                if not game_map.in_bounds(_nx, _inst.pos.y):
                    break
                _inst.pos = world.Position(_nx, _inst.pos.y)
                _attempts += 1
            _occupied.add((_inst.pos.x, _inst.pos.y))
