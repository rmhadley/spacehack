"""Main quest dialogue: NPC talk integration + quest option resolution."""

from __future__ import annotations

from ..data.main_quest import (
    MainQuestStep,
    QuestDialogue,
    find_main_quest_step,
)
from ._core import (
    STATUS_ACTIVE,
    STATUS_AVAILABLE,
    STATUS_COMPLETED,
    step_status,
    start_step,
    complete_step,
    _iter_known_steps,
    _smuggle_crate_held,
    _trigger_smuggle_crate,
    _complete_smuggle_handover,
    _hold_has_goods,
    _consume_goods,
)
from .. import message_log
from ..text import get as t_get


def _dialogue_is_locked(ctx, dialogue: "QuestDialogue") -> bool:
    """True when dialogue belongs to a faction the player did NOT lock in."""
    if not dialogue.backing_faction:
        return False
    if not ctx.main_quest_chain:
        return False
    return dialogue.backing_faction != ctx.main_quest_chain


def _dialogue_planet_ok(ctx, dialogue: "QuestDialogue") -> bool:
    """True when dialogue has no planet restriction or player is on it."""
    if not dialogue.dialogue_planet_id:
        return True
    return ctx.current_city_id == dialogue.dialogue_planet_id


def _live_dialogue(ctx, npc_id: str) -> tuple[MainQuestStep, "QuestDialogue"] | None:
    """Return (step, dialogue) for the highest-priority live entry."""
    for _status in (STATUS_ACTIVE, STATUS_AVAILABLE, STATUS_COMPLETED):
        for _step_id, _st, _step in _iter_known_steps(ctx):
            if _st != _status:
                continue
            _dialogue = _step.dialogues.get(npc_id)
            if _dialogue is None:
                continue
            if _status == STATUS_ACTIVE and _dialogue.active:
                if _dialogue_planet_ok(ctx, _dialogue):
                    return (_step, _dialogue)
                continue
            if _status == STATUS_AVAILABLE and _dialogue.intro:
                if _dialogue_planet_ok(ctx, _dialogue):
                    return (_step, _dialogue)
                continue
            if _status == STATUS_COMPLETED and _dialogue.complete:
                if _dialogue_planet_ok(ctx, _dialogue):
                    return (_step, _dialogue)
                continue
    return None


def resolve_npc_dialogue(ctx, npc_id: str) -> tuple[str, str | None]:
    """Return (dialogue_text, trigger_step_id or None) for this NPC."""
    from ..data.npcs import find_npc as _find_npc
    _live = _live_dialogue(ctx, npc_id)
    if _live is not None:
        _step, _dialogue = _live
        _status = ctx.main_quest_progress[_step.id]
        if _dialogue_is_locked(ctx, _dialogue):
            _locked = _dialogue.locked or _find_npc(npc_id).flavor_text
            return (_locked, None)
        _trigger = (
            _step.id
            if _dialogue.trigger_on_talk
            and _status in (STATUS_AVAILABLE, STATUS_ACTIVE)
            and not (
                _step.objective_type == "smuggle"
                and (
                    (_held := _smuggle_crate_held(ctx, _step.id))
                    and _step.requires_npc_id != npc_id
                    or (not _held
                        and _step.requires_npc_id == npc_id)
                )
            )
            else None
        )
        if _trigger is not None:
            return (_find_npc(npc_id).flavor_text, _trigger)
        _text = (
            _dialogue.active if _status == STATUS_ACTIVE
            else _dialogue.intro if _status == STATUS_AVAILABLE
            else _dialogue.complete
        )
        return (_text, None)
    return (_find_npc(npc_id).flavor_text, None)


def quest_option_for(ctx, npc_id: str) -> tuple[str, str] | None:
    """Return (option_label, step_id) when this NPC offers a live quest row."""
    _live = _live_dialogue(ctx, npc_id)
    if _live is None:
        return None
    _step, _dialogue = _live
    if _dialogue_is_locked(ctx, _dialogue):
        return None
    if not _dialogue.option_label:
        return None
    if step_status(ctx, _step.id) == STATUS_COMPLETED:
        return None
    if _step.objective_type == "smuggle":
        _held = _smuggle_crate_held(ctx, _step.id)
        _is_receiver = _step.requires_npc_id == npc_id
        if (_held and not _is_receiver) or (not _held and _is_receiver):
            return None
    return (_dialogue.option_label, _step.id)


def _goods_ok(ctx, step) -> bool:
    """True when the player's hold covers a goods step's requirement."""
    if step_status(ctx, step.id) not in (STATUS_AVAILABLE, STATUS_ACTIVE):
        return False
    if not _hold_has_goods(ctx, step.requires_goods):
        ctx.log.add(t_get("runtime.missing_goods_log"))
        return False
    _consume_goods(ctx, step.requires_goods)
    return True


def _lock_in_chain(ctx, dialogue) -> None:
    """Record a locks_chain faction choice and its unlock item/backing."""
    if (dialogue.locks_chain and dialogue.backing_faction
            and not ctx.main_quest_chain):
        ctx.main_quest_chain = dialogue.backing_faction
        ctx.log.add_colored(
            t_get("runtime.chain_lockin_log").format(
                faction=dialogue.backing_faction.capitalize(),
            ),
            message_log.COLOR_IMPORTANT_EVENT,
        )
    if dialogue.backing_faction:
        ctx.main_quest_backing.add(dialogue.backing_faction)
    if dialogue.unlock_item:
        ctx.main_quest_unlocked_items.add(dialogue.unlock_item)


def _start_salvage_step(ctx, step) -> bool:
    """Start a salvage step from NPC talk (loads cargo, marks active)."""
    if step_status(ctx, step.id) == STATUS_ACTIVE:
        return False
    _started = start_step(ctx, step.id)
    if _started and step.smuggle_good_id:
        _owned = ctx.player_owned_ship
        if _owned is not None and step.smuggle_cargo_size > 0:
            _owned.inventory[step.smuggle_good_id] = (
                _owned.inventory.get(step.smuggle_good_id, 0)
                + step.smuggle_cargo_size
            )
    return _started


def trigger_dialogue(ctx, npc_id: str, step_id: str) -> bool:
    """Advance step_id from an NPC-talk quest option selection."""
    _step = find_main_quest_step(step_id)
    _dialogue = _step.dialogues.get(npc_id)
    if _dialogue is None:
        return False
    if _step.objective_type == "goods" and _step.requires_goods:
        if not _goods_ok(ctx, _step):
            return False
    _lock_in_chain(ctx, _dialogue)
    if _step.objective_type == "smuggle":
        if step_status(ctx, step_id) == STATUS_ACTIVE:
            return _complete_smuggle_handover(ctx, _step)
        return _trigger_smuggle_crate(ctx, _step)
    if _step.objective_type == "salvage":
        return _start_salvage_step(ctx, _step)
    if _step.objective_type == "visit":
        from ._objectives import maybe_complete_visit as _maybe_visit
        return _maybe_visit(ctx, _step.requires_npc_id)
    if _step.objective_type == "bump":
        return True
    return complete_step(ctx, step_id)
