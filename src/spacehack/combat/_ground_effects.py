"""Ground combat consumable + status adapter pass.

Owns the player-side effect application and the round-boundary
advance. Doc 103 Build A retired the ActiveConsumableEffect ledger:
the shared ctx container + the pure ``combat/_statuses`` engine are
the mechanism, and THIS module is the rules adapter that applies
events — clamping, log lines, and the AP gain fold stay here (the
engine never logs, never writes HP). The enemy-side mirror (doc 48
phase 5, SETTLED 27/36) lives here beside it: AP derivation and
carried-consumable use.
"""

from __future__ import annotations

from .. import message_log as _ml
from ..data.ground_items import find_ground_consumable
from ..data.statuses import find_status
from . import _statuses


def player_status_effects(ctx) -> "_statuses.StatusEffects":
    """The player's status sums — the choke-point read every ground
    assembly resolves itself from the state it already holds (doc
    103). Lives here beside the adapter pass it serves (getattr:
    formula-only callers pass ad-hoc ctxs without the container)."""
    return _statuses.sum_effects(
        getattr(ctx, "active_statuses", None) or {},
    )


def apply_player_effect(state, ctx, spec) -> bool:
    """Apply a validated consumable effect to the active combat state."""
    if spec.effect_id == "regen":
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
    if spec.duration_turns > 0:
        # The status row owns the applied numbers (the catalog law);
        # the source rides for tick-line attribution. ``apply`` raises
        # on an unresolvable id — an authoring error, never runtime.
        _statuses.apply(
            ctx.active_statuses, spec.effect_id,
            source=spec.name, theater="ground",
        )
    return spec.effect_id in {"regen", "stim"}


def advance_player_effects(state) -> int:
    """Advance the player's status container one round boundary and
    return the temporary AP bonus for the gain fold: heal events
    clamp at max and log the row's tick line only when healed > 0
    (today's ledger shape, the source interpolated); ap events fold
    into the returned bonus; expire events log the row's ruled line
    when one is authored (the Neural Stim loan's repay line)."""
    _container = getattr(state.ctx, "active_statuses", None) or {}
    _ap_bonus = 0
    for _ev in _statuses.advance(_container):
        _kind, _sid = _ev[0], _ev[1]
        _spec = find_status(_sid)
        if _kind == "heal":
            _before = state.player_hp
            state.player_hp = min(
                state.player_max_hp,
                state.player_hp + _ev[2],
            )
            _healed = state.player_hp - _before
            if _healed > 0 and _spec.tick_line:
                _source = _container[_sid].source or _spec.name
                state.ctx.log.add_colored(
                    _spec.tick_line.format(
                        source=_source, healed=_healed,
                    ),
                    _ml.COLOR_PLAYER_ACTION,
                )
        elif _kind == "ap":
            _ap_bonus += _ev[2]
        elif _kind == "expire" and _spec.expire_line:
            state.ctx.log.add_colored(
                _spec.expire_line, _ml.COLOR_PLAYER_ACTION,
            )
    return _ap_bonus


def enemy_ap_total(spec, armor_entries=()) -> int:
    """An enemy's per-round AP (doc 48 SETTLED 27): the spec's
    authored base. ``armor_entries`` is the seam the enemy chrome
    container lands on (doc 102, deferred per SETTLED 6) — the
    placeholder ap_bonus fold retired with its fields (4.2)."""
    return max(1, spec.ap)


def advance_enemy_effects(enemy) -> int:
    """Tick one enemy instance's status container at round start (the
    mirror of :func:`advance_player_effects`): regen heals SILENTLY
    (the enemy side never logged its ticks), a live stim grants its
    AP bonus as the returned fold. Fight-scoped — never serialized;
    a new fight re-derives from the carried stamp. The dead do not
    regenerate — an instance killed inside its regen window stays
    dead, and its container is left untouched."""
    if enemy.hp <= 0:
        return 0
    _bonus = 0
    for _ev in _statuses.advance(enemy.statuses):
        if _ev[0] == "heal":
            enemy.hp = min(enemy.max_hp, enemy.hp + _ev[2])
        elif _ev[0] == "ap":
            _bonus += _ev[2]
    return _bonus


def _triggered(spec, gei, game_map, player_pos) -> bool:
    """Whether one carried consumable's use trigger fires (SETTLED 36):
    a Med Pack at half health; a Combat Stim only when the carrier can
    see the player and isn't already stimmed — the one live AI-side
    status read, moved with the field (doc 103 Build A). Any other
    effect id has no enemy-side trigger yet."""
    from ..dungeon_fov import cell_in_sight

    if spec.effect_id == "regen":
        return gei.hp * 2 <= gei.max_hp
    if spec.effect_id == "stim":
        return not _statuses.has(gei.statuses, "stim") and cell_in_sight(
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
        if _spec.effect_id == "regen":
            gei.hp = min(gei.max_hp, gei.hp + _spec.combat_heal_amount)
            _line = f"{gei.name} uses a {_spec.name}."
        elif _spec.effect_id == "stim":
            _line = f"{gei.name} injects a {_spec.name}."
        else:
            continue  # no enemy-side use for other effect ids
        _statuses.apply(
            gei.statuses, _spec.effect_id,
            source=_spec.name, theater="ground",
        )
        _entry[2] -= 1
        if _entry[2] <= 0:
            (gei.entity.carried_items or []).remove(_entry)
        gei.ap -= _spec.use_ap_cost
        ctx.log.add_colored(_line, _ml.COLOR_ENEMY_ACTION)
        return _spec.use_ap_cost
    return 0
