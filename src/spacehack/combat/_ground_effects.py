"""Ground combat consumable effects — the active-effect ledger pass.

Owns the player-side temporary effects during a ground fight (heal
over time, temporary AP): applying one consumable's effect and
advancing the ledger at each round start. The enemy-side mirror (doc
48 phase 5, SETTLED 27/36) lives here beside it: AP derivation and
carried-consumable use.
"""

from __future__ import annotations

from .. import message_log as _ml
from ..data.ground_items import find_ground_consumable, list_ground_consumables as _list_gc
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


def enemy_ap_total(spec, armor_entries=()) -> int:
    """An enemy's per-round AP (doc 48 SETTLED 27): the spec's authored
    base plus worn cybernetics' ``ap_bonus`` — the same modifier math
    the player's cyber-legs run, so phase 11's consortium wearers just
    work. No AP-armor exists yet; the entries seam is the contract."""
    from ..ground_equipment import sum_armor_bonus

    return max(1, spec.ap + sum_armor_bonus(armor_entries, "ap_bonus"))


def advance_enemy_effects(enemy) -> int:
    """Tick one enemy instance's temporary effects at round start (the
    mirror of :func:`advance_player_effects`): med-pack regeneration
    heals, a live stim grants its catalog AP bonus. Fight-scoped —
    never serialized; a new fight re-derives from the carried stamp.
    The dead do not regenerate — an instance killed inside its regen
    window stays dead."""
    if enemy.hp <= 0:
        return 0
    if enemy.regen_turns > 0:
        enemy.hp = min(enemy.max_hp, enemy.hp + enemy.regen_amount)
        enemy.regen_turns -= 1
    _bonus = enemy.stim_ap_bonus if enemy.stim_turns > 0 else 0
    if enemy.stim_turns > 0:
        enemy.stim_turns -= 1
    return _bonus


def _triggered(spec, gei, game_map, player_pos) -> bool:
    """Whether one carried consumable's use trigger fires (SETTLED 36):
    a Med Pack at half health; a Combat Stim only when the carrier can
    see the player and isn't already stimmed. Any other effect id has
    no enemy-side trigger yet."""
    from ._animations import _has_los

    if spec.effect_id == "restore_hp":
        return gei.hp * 2 <= gei.max_hp
    if spec.effect_id == "stim":
        return gei.stim_turns <= 0 and _has_los(
            game_map, gei.entity.pos.x, gei.entity.pos.y,
            player_pos.x, player_pos.y,
        )
    return False


def use_carried_consumable(ctx, gei, game_map, player_pos) -> int:
    """Use the first triggered carried consumable (ANY carrier — beasts
    gobble scavenged med packs too, SETTLED 36): apply the effect,
    consume one charge, log the approved line, spend its use AP.
    Returns the AP spent (0 when nothing applies or AP runs short)."""
    for _entry in list(getattr(gei.entity, "carried_items", None) or []):
        _item_type, _item_id, _qty = _entry
        if _item_type != "consumable" or _qty <= 0:
            continue
        try:
            _spec = find_ground_consumable(_item_id)
        except KeyError:
            continue
        if not _triggered(_spec, gei, game_map, player_pos):
            continue
        if gei.ap < _spec.use_ap_cost:
            return 0
        if _spec.effect_id == "restore_hp":
            gei.hp = min(gei.max_hp, gei.hp + _spec.combat_heal_amount)
            gei.regen_amount = _spec.combat_regen_amount
            gei.regen_turns = _spec.duration_turns
            _line = f"{gei.name} uses a {_spec.name}."
        elif _spec.effect_id == "stim":
            gei.stim_turns = _spec.duration_turns
            gei.stim_ap_bonus = _spec.combat_ap_bonus
            _line = f"{gei.name} injects a {_spec.name}."
        else:
            continue  # no enemy-side use for other effect ids
        _entry[2] -= 1
        if _entry[2] <= 0:
            (gei.entity.carried_items or []).remove(_entry)
        gei.ap -= _spec.use_ap_cost
        ctx.log.add_colored(_line, _ml.COLOR_ENEMY_ACTION)
        return _spec.use_ap_cost
    return 0
