"""Space flee — the caller side of doc 54's FLED outcome.

The combat loop never runs a flee transition: it breaks with outcome
``"FLED"`` plus the committed :class:`~spacehack.combat._types.FleeExit`
on the CombatResult. This module executes that commit (the same apply
code the main loop runs out of combat) and mirrors the result onto the
game-loop state — the ``begin_capture_boarding`` /
``_adopt_capture_boarding`` seam's flee twin. Kept beside
``game_interactions`` (whose exit machinery it drives) in its own
module to hold that file under the size ratchet.
"""

from __future__ import annotations

from .game_interactions import _apply_exit_commit, _ctx_state_shim


async def begin_flee_transition(ctx, console, cr) -> bool:
    """Doc 54 phase 1: execute the FLED payload's transition — the
    same apply code the main loop runs, caller-side (never inside the
    combat loop). Returns False when the transition refused at execute
    time (an Explore build failure: the volley was paid but no map
    changed) and downgrades the outcome to ABORTED — the
    ``begin_capture_boarding`` break-away twin."""
    _commit = getattr(cr, 'flee_exit', None)
    if _commit is None:
        return False
    _before_map = ctx.game_map
    await _apply_exit_commit(_ctx_state_shim(ctx, console), _commit)
    if ctx.game_map is _before_map:
        cr.outcome = "ABORTED"  # refused at execute time; still in space
        return False
    return True


def _current_flee_commit():
    """The just-ended fight's FLED commit (doc 54) — the adoption
    seam's read of the combat result the outcome string can't carry.
    Valid immediately after the fight ends; None once the next fight
    initializes its own result."""
    from .combat import _rules_space
    _st = _rules_space._state
    if _st is None or getattr(_st.cr, 'outcome', None) != "FLED":
        return None
    return _st.cr.flee_exit


def _adopt_flee_dungeon(state):
    state.space_game_map = state.game_map
    state.space_player = state.player
    state.game_map = state.ctx.game_map
    state.player = state.ctx.player
    state.current_mode = 'dungeon'


def _adopt_flee_city(state):
    state.city_game_map = state.ctx.game_map
    state.city_player = state.ctx.player
    state.game_map = state.ctx.game_map
    state.player = state.ctx.player
    state.current_city_id = state.ctx.current_city_id
    state.current_mode = 'city'


def _adopt_flee_space(state):
    state.game_map = state.ctx.game_map
    state.player = state.ctx.player
    state.current_mode = 'space'


_FLEE_ADOPTERS = {
    'explore': _adopt_flee_dungeon,
    'dig': _adopt_flee_dungeon,
    'land': _adopt_flee_city,
    'jump': _adopt_flee_space,
}


def adopt_flee_transition(state) -> None:
    """FLED (doc 54): the transition ran caller-side — mirror it onto
    the loop state per the commit's kind (the capture-adoption twin;
    the combat path has no state to write)."""
    _commit = _current_flee_commit()
    if _commit is None:
        return
    _FLEE_ADOPTERS[_commit.verb](state)
    state.player_active_missions = state.ctx.player_active_missions
