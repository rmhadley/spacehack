"""Live-ship boarding (doc 40 phase 6a): the BOARD action.

Offered in combat only under the four ruled conditions — no shields
up, 75% hull damage done, a duel (the target is the only live enemy),
adjacency. Boarding ends the encounter into the target's crewed
interior; the hull is consumed at entry, so each ship boards once
(the physical one-roll-per-source enforcement).
"""

from __future__ import annotations

from ._types import CombatResult, EnemyInstance, SpaceCombatState

# Hull damage fraction a target must take before BOARD is offered
# (user ruling: "you've shot it up enough that it can't easily evade
# your docking attempt"). Tunable.
BOARD_HULL_DAMAGE = 0.75


def board_denial(
    state: SpaceCombatState, enemy: EnemyInstance | None, ent,
) -> str | None:
    """Pure: why BOARD is unavailable for this target, else None."""
    if enemy is None or not enemy.alive:
        return "No target to board."
    if enemy.shields > 0:
        return "Their shields are still up."
    if 1 - enemy.hull / max(1, enemy.max_hull) < BOARD_HULL_DAMAGE:
        return "Their hull is still too intact to board."
    if len([_e for _e in state.enemy_insts if _e.alive]) > 1:
        return "You can't board while their escorts are still fighting."
    _p, _e = state.player_ent.pos, enemy.pos
    if max(abs(_p.x - _e.x), abs(_p.y - _e.y)) > 1:
        return "Pull alongside to board."
    if not _capture_target(enemy, ent):
        return "This ship can't be boarded."
    return None


def _capture_target(enemy: EnemyInstance, ent) -> bool:
    """A capture target: a plain procedural spawn whose spec has a
    crewed interior. Bounty/heist-linked ships keep kill-or-die."""
    if ent is None or getattr(ent, "bounty_spawn_id", None) is not None \
            or getattr(ent, "heist_spawn_id", None) is not None:
        return False
    if not getattr(ent, "procedural_squad_id", ""):
        return False
    from ..data.npc_ships import find_npc_ship
    try:
        spec = find_npc_ship(enemy.spec_id)
    except KeyError:
        return False
    return bool(getattr(spec, "capture_layout_id", ""))


def attempt_board(state: SpaceCombatState, target_idx: int) -> bool:
    """Try to board the current target. False: denial logged, fight on.

    ``target_idx`` indexes the ALIVE-filtered list (the loop's target
    space) — resolve the unfiltered instance + entity from it."""
    _alive = [_e for _e in state.enemy_insts if _e.alive]
    enemy = _alive[target_idx] if target_idx < len(_alive) else None
    ent = None
    if enemy is not None:
        for _i, _inst in enumerate(state.enemy_insts):
            if _inst is enemy:
                ent = state.enemy_ents.get(_i)
                break
    _denial = board_denial(state, enemy, ent)
    if _denial is not None:
        state.log.add(_denial)
        return False
    if state.cr is None:
        state.cr = CombatResult()
    state.cr.boarded_spec_id = enemy.spec_id
    state.cr.boarded_ent = ent
    state.log.add(f"You bring your ship alongside and board the {enemy.name}.")
    return True
