"""Space-combat reinforcements — mid-fight joiners.

The patrol tick, re-detection, and joiner attach extracted from
``_rules_space`` (the doc-57 ratchet split, the ``_space_kills``
pattern): functions take the encounter ``state`` explicitly instead
of reading the module global. ``_rules_space.check_reinforcements``
remains the rules interface the unified loop calls.
"""

from __future__ import annotations

from typing import Any

from .. import world
from .. import message_log as _ml
from ._actions import set_combat_locks
from ._types import EnemyInstance, SpaceCombatState


def _find_reinforcement_entity(game_map: world.GameMap, pos: world.Position) -> Any:
    """Return the unowned, non-loot entity at ``pos``, or None."""
    for _ge in game_map.entities:
        if getattr(_ge, 'owned', False):
            continue
        if getattr(_ge, 'loot_data', None) is not None:
            continue
        if getattr(_ge, 'non_blocking', False):
            continue  # a crossing missile is not a joinable hull (doc 57)
        if _ge.pos.x == pos.x and _ge.pos.y == pos.y:
            return _ge
    return None


def _build_reinforcement_enemy(spec, pos: world.Position) -> EnemyInstance:
    """Build one joiner from the JOINER's own spec — the one enemy
    construction path (doc 48 SETTLED 21: joiner stats must match
    their spec). The old player-hull reads fed a discarded player
    state and a spurious None dropped legitimate joiners whenever the
    PLAYER's catalog lookup failed."""
    from ._stats import _build_enemy
    return _build_enemy(spec, pos)


def _join_reinforcements(
    state: SpaceCombatState,
    game_map: world.GameMap,
    new_specs: list,
    new_positions: list[world.Position],
    existing_entity_ids: set[int],
) -> None:
    """Build and attach newly-detected reinforcement enemy instances."""
    for _ns, _np in zip(new_specs, new_positions):
        _found_entity = _find_reinforcement_entity(game_map, _np)
        if _found_entity is not None and id(_found_entity) in existing_entity_ids:
            continue
        if any(
            _ei.pos.x == _np.x and _ei.pos.y == _np.y
            for _ei in state.enemy_insts
        ):
            continue
        _new_ei = _build_reinforcement_enemy(_ns, _np)
        state.enemy_insts.append(_new_ei)
        state.enemy_specs.append(_ns)
        if _found_entity is not None:
            state.enemy_ents[len(state.enemy_insts) - 1] = _found_entity
            if getattr(_found_entity, 'name', ''):
                _new_ei.name = _found_entity.name
        state.log.add_colored(
            f"{getattr(_found_entity, 'name', '') or _ns.name} joins the fight!",
            _ml.COLOR_COMBAT_EVENT,
        )


def check_reinforcements(state: SpaceCombatState, ctx, game_map: world.GameMap) -> None:
    """The patrol tick + re-detection pass; new contacts join the fight.

    Freezes combatants before the patrol tick so they can't drift or
    despawn, syncs live entity positions back onto the instances, then
    re-runs encounter detection — a fresh contact becomes a joiner
    with its entity matched into ``state.enemy_ents``."""
    from ..npc_ships import move_npcs as _tick_npcs
    from ..navigation import _detect_combat_encounter as _re_detect
    from .. import solar_system as _ss_module

    # Freeze combatants before the patrol tick so they can't drift/despawn
    # (values(), not the dict — the raw primitive iterates what it's given).
    set_combat_locks(True, state.enemy_ents.values())

    _tick_npcs(ctx, game_map)

    for _i, _ent in state.enemy_ents.items():
        if _i < len(state.enemy_insts) and state.enemy_insts[_i].alive:
            state.enemy_insts[_i].pos = _ent.pos

    _new_encounter = _re_detect(ctx, state.player_state["pos"], _ss_module.current_system())
    if _new_encounter is None:
        return

    _new_specs, _new_positions = _new_encounter
    _existing_entity_ids = {id(_e) for _e in state.enemy_ents.values()}
    _join_reinforcements(state, game_map, _new_specs, _new_positions, _existing_entity_ids)
