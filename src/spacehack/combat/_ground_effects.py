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

from functools import partial

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


def apply_hit_status(
    ctx, container, weapon_id: str, victim_label: str, *,
    victim_band: int, victim_survives: bool, line_color,
) -> None:
    """The on-hit lingering rider's ONE law (doc 103 Build B), shared
    by both fire sites: guarded (no chance-carrier consumes ZERO draws
    — the crit precedent), survivors only (a killing hit leaves no
    victim), the ego seam prices the VICTIM's band, one roll, and the
    ruled apply line logs on every landed roll — fresh or refresh
    (the countdown visibly resets). An unresolvable weapon id raises
    (an authoring error, the apply KeyError law — every fire site
    resolves its id through the catalog before it gets here)."""
    from ..data.ground_weapons import find_ground_weapon as _find_gw

    _ws = _find_gw(weapon_id)
    if _ws.status_chance <= 0 or not _ws.status_id or not victim_survives:
        return
    from ..chrome import status_chance_adjusted
    from ..engine import RNG

    if RNG.randint(1, 100) > status_chance_adjusted(
        _ws.status_chance, victim_band,
    ):
        return
    _statuses.apply(
        container, _ws.status_id, source=_ws.name, theater="ground",
    )
    _line = find_status(_ws.status_id).apply_line
    if _line:
        ctx.log.add_colored(_line.format(victim=victim_label), line_color)


def player_survives_hit(state, hit_dmg: int) -> bool:
    """Whether the player still stands after this hit lands: current
    HP minus the turn's PENDING (resolved-but-unapplied) damage minus
    the hit itself — doc 103 Build B's survivors-only guard at the
    enemy fire site, where shots resolve before their turn's damage
    applies."""
    return state.player_hp - state.enemy_turn_damage_pending - hit_dmg > 0


def apply_enemy_hit_status(ctx, weapon_id: str, hit_dmg: int) -> None:
    """The enemy fire site's rider tail (doc 103 Build B): the same
    law the player's ``damage()`` runs, aimed at the PLAYER's
    container — the ego seam's live exerciser (the victim is you;
    YOUR band prices the roll). No live session: no fight, no rider.
    The container passes STRAIGHT through (never an ``or {}``
    fallback — an empty dict is falsy and the fallback would orphan
    the write; the field is declared on GameContext, Build A)."""
    from . import _rules_ground
    from ..chrome import base_band

    _state = _rules_ground._state
    if _state is None:
        return
    # The declared home passes through untouched — only a ctx MISSING
    # the field (minimal test doubles; GameContext always carries it,
    # Build A) gets a container attached. Never ``or {}``: an empty
    # dict is falsy and the fallback would orphan the write.
    _container = getattr(ctx, "active_statuses", None)
    if _container is None:
        _container = ctx.active_statuses = {}
    apply_hit_status(
        ctx, _container, weapon_id, "You are",
        victim_band=base_band(ctx),
        victim_survives=player_survives_hit(_state, hit_dmg),
        line_color=_ml.COLOR_ENEMY_ACTION,
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


def _log_heal_tick(ctx, spec, source, healed: int) -> None:
    """The shared heal-tick line (doc 103 Build C's extraction — the
    ruled-prose drift trap's one home): logged only when healed > 0,
    the source interpolated with the row's name as the sourceless
    fallback."""
    if healed > 0 and spec.tick_line:
        ctx.log.add_colored(
            spec.tick_line.format(source=source or spec.name, healed=healed),
            _ml.COLOR_PLAYER_ACTION,
        )


def _apply_heal_event(state, spec, source, amount: int) -> None:
    """One IN-COMBAT heal event: clamp at the fight state's max and
    log through the shared composer (callers pass the PRE-ADVANCE
    snapshot's source, because the engine drops the entry at the
    expiring boundary and that round's tick still logs its
    attribution)."""
    _before = state.player_hp
    state.player_hp = min(
        state.player_max_hp,
        state.player_hp + amount,
    )
    _log_heal_tick(state.ctx, spec, source, state.player_hp - _before)


def _walk_round_events(ctx, container, *, theater, apply_heal) -> list[int]:
    """The player adapters' ONE event walk (doc 103 Build C): heal
    events clamp-and-log through the caller's ``apply_heal`` (the
    apply laws stay DISTINCT — the fight state's max in combat, the
    refreshed ctx max while exploring; never homogenized); the
    returned ap values are the CALLER's to fold (the combat gain
    fold; dropped while exploring — no AP pool exists out of
    combat); expire lines log AFTER the walk (today's ledger shape
    — a regen sharing the boundary with a loan keeps its tick line
    first)."""
    _sources = {_sid: _a.source for _sid, _a in container.items()}
    _ap_events: list[int] = []
    _expire_lines: list[str] = []
    for _ev in _statuses.advance(container, theater=theater):
        _kind, _sid = _ev[0], _ev[1]
        _spec = find_status(_sid)
        if _kind == "heal":
            apply_heal(_spec, _sources.get(_sid), _ev[2])
        elif _kind == "ap":
            _ap_events.append(_ev[2])
        elif _kind == "expire" and _spec.expire_line:
            _expire_lines.append(_spec.expire_line)
    for _line in _expire_lines:
        ctx.log.add_colored(_line, _ml.COLOR_PLAYER_ACTION)
    return _ap_events


def advance_player_effects(state) -> int:
    """Advance the player's status container one round boundary and
    return the temporary AP bonus for the gain fold (the shared walk
    passes the ground theater — a row tagged for another theater is
    frozen here)."""
    return sum(_walk_round_events(
        state.ctx,
        getattr(state.ctx, "active_statuses", None) or {},
        theater="ground",
        apply_heal=partial(_apply_heal_event, state),
    ))


def _apply_exploration_heal(ctx, spec, source, amount: int) -> None:
    """One EXPLORATION heal event: clamp at the REFRESHED ctx max —
    a distinct apply law from the fight state's max (live inputs may
    have moved the ceiling since the last fight; the ground-max
    staleness law)."""
    _before = ctx.ground_hp
    ctx.ground_hp = min(ctx.ground_max_hp, ctx.ground_hp + amount)
    _log_heal_tick(ctx, spec, source, ctx.ground_hp - _before)


def advance_exploration_statuses(ctx) -> None:
    """Tick the player's statuses one DUNGEON TURN while exploring
    (doc 103 Build C): heal events restore ``ctx.ground_hp`` clamped
    at the refreshed max, ap events DROP (no AP pool exists out of
    combat — a walking stim spends duration for nothing but its
    timing), and the rows' tick/expire lines log exactly as the
    combat adapter's do. The walk passes the ground theater; a
    paused space row stays frozen."""
    from .. import xp

    xp.refresh_ground_max_hp(ctx)
    _walk_round_events(
        ctx,
        getattr(ctx, "active_statuses", None) or {},
        theater="ground",
        apply_heal=partial(_apply_exploration_heal, ctx),
    )


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
    for _ev in _statuses.advance(enemy.statuses, theater="ground"):
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
