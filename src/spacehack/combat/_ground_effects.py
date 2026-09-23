"""Ground combat consumable effects — the active-effect ledger pass.

Owns the player-side temporary effects during a ground fight (heal
over time, temporary AP): applying one consumable's effect and
advancing the ledger at each round start. The enemy-side mirror
(doc 48 phase 5) lives here beside it.
"""

from __future__ import annotations

from .. import message_log as _ml
from ..data.ground_items import list_ground_consumables as _list_gc
from ..ground_consumables import ActiveConsumableEffect, effect_from_spec


def apply_player_effect(state, ctx, spec) -> bool:
    """Apply a validated consumable effect to the active combat state."""
    if spec.effect_id == "restore_hp":
        _before = state.player_hp
        state.player_hp = min(
            state.player_max_hp,
            state.player_hp + spec.combat_heal_amount,
        )
        _healed = state.player_hp - _before
        if _healed > 0:
            ctx.log.add_colored(
                f"{spec.name}: +{_healed} HP.",
                _ml.COLOR_PLAYER_ACTION,
            )
    _effect = effect_from_spec(spec)
    if _effect is not None:
        state.active_consumable_effects[spec.effect_id] = _effect
    return spec.effect_id in {"restore_hp", "stim"}


def _effect_name(effect_id: str) -> str:
    """Resolve a friendly catalog name for a temporary effect."""
    for _spec in _list_gc():
        if _spec.effect_id == effect_id:
            return _spec.name
    return "Regeneration"


def advance_player_effects(state) -> int:
    """Apply regeneration and return the current temporary AP bonus."""
    _ap_bonus = 0
    _remaining: dict[str, ActiveConsumableEffect] = {}
    for _effect_id, _effect in state.active_consumable_effects.items():
        if _effect.regen_amount:
            _before = state.player_hp
            state.player_hp = min(
                state.player_max_hp,
                state.player_hp + _effect.regen_amount,
            )
            _healed = state.player_hp - _before
            if _healed > 0:
                _effect_name_str = _effect_name(_effect_id)
                state.ctx.log.add_colored(
                    f"{_effect_name_str} regeneration: +{_healed} HP.",
                    _ml.COLOR_PLAYER_ACTION,
                )
        if _effect.ap_bonus:
            _ap_bonus += _effect.ap_bonus
        _next = _effect.remaining_turns - 1
        if _next > 0:
            _remaining[_effect_id] = ActiveConsumableEffect(
                _effect.effect_id, _next,
                _effect.regen_amount, _effect.ap_bonus,
            )
    state.active_consumable_effects = _remaining
    return _ap_bonus
