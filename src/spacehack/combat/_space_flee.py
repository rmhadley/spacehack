"""Space flee — the in-combat exit machinery (doc 54 phase 1).

The implementation sibling of ``_rules_space``'s one-line flee hooks
(the ``_ground_flee`` pattern, ground's mirror): the reaction volley
(every live hostile that can hit the player right now fires once from
where it stands) and the in-combat exit attempt (probe the world exit,
eat the volley, end the fight FLED with the exit payload — the CALLER
runs the transition; the loop never does).
"""

from __future__ import annotations

from .. import world


async def reaction_volley(state, ctx, game_map: world.GameMap) -> bool:
    """The flee reaction volley (doc 54): every live hostile that can
    hit the player RIGHT NOW — LOS plus a weapon in range — fires one
    shot from where it stands; no movement, no repositioning. Shots
    pay their real costs and can kill. Returns True when the player
    was destroyed (death wins: the transition never runs)."""
    from . import _rules_space
    from ._ai import _enemy_attack, _reaction_pick

    _p_pos = state.player_state["pos"]
    _hit_chances = _rules_space._build_hit_chances(
        _rules_space._current_target(),
    )
    _evade = _rules_space._player_evade()
    for _ei in _rules_space.get_enemies(ctx):
        if not _rules_space._has_los(
            game_map, _ei.pos.x, _ei.pos.y, _p_pos.x, _p_pos.y,
        ):
            continue
        _pick = _reaction_pick(
            _ei, _rules_space._distance(_p_pos, _ei.pos), state.player_state,
        )
        if _pick is None:
            continue
        if await _enemy_attack(
            state, _ei, _pick[0],
            hit_chances=_hit_chances, evade_bonus=_evade,
            calc_cam=_rules_space._calc_camera, ctx=ctx,
        ) == "DEFEAT":
            return True
    return False


async def attempt_flee(
    state, ctx, game_map: world.GameMap, action: str,
) -> str | None:
    """The in-combat exit attempt (doc 54 phase 1), space's hook.

    A move whose target is a world exit (planet / station / jump
    gate) runs the SAME exit prompt the main loop runs — cancels and
    refusals fire nothing (SETTLED 1/3); a committing choice eats the
    reaction volley, then the fight ends WITHOUT running the
    transition (the caller executes it from ``cr.flee_exit``, the
    BOARD seam). Returns ``None`` when the target is no exit (the
    move dispatches normally, blocked bumps logging "Blocked."),
    ``"HELD"`` for a canceled or refused exit (full no-op, same
    turn), ``"FLED"`` when the volley was survived, ``"DEFEAT"``
    when it killed the player."""
    from . import _rules_space
    from ..game_interactions import (
        _ctx_state_shim, _space_exit_commit, _space_exit_target,
    )

    if _rules_space.player_ap(ctx) <= 0:
        return None
    _dx, _dy = world.MOVE_KEYS.get(action.partition(":")[2], (0, 0))
    if (_dx, _dy) == (0, 0):
        return None
    _shim = _ctx_state_shim(state.ctx, state.console)
    _target = _space_exit_target(_shim, _dx, _dy)
    if _target is None:
        return None
    _commit, _refused = await _space_exit_commit(_shim, _target)
    if _commit is None:
        return "HELD"
    if await reaction_volley(state, ctx, game_map):
        return "DEFEAT"
    state.cr.flee_exit = _commit
    return "FLED"
