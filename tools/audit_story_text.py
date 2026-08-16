#!/usr/bin/env python3
"""Audit the main-quest story text for keys that can never be displayed.

Simulates every faction playthrough (bar / merchants / lab / militia)
through the full main quest — prologue, chain, door, prison, first
reading — and at each reachable quest state records which overlay keys
the real display paths would surface:

  * quest-log breadcrumb (step titles + descriptions)
  * NPC talk modal (intro / active / complete / locked + flavor) —
    a faithful port of resolve_npc_dialogue, including the rule that
    trigger-on-talk dialogues show the NPC's flavor text (the option
    row is the trigger) and smuggle crate-hold suppression
  * the post-lock-in help-offer modal (q1 intros)
  * quest menu option rows (option_label)

Any extracted overlay key (step.* / npc.*) that no state ever displays
is reported as dead, so it can be removed from the Python data and the
JSON baseline regenerated.

Usage: ``python3 tools/audit_story_text.py``
"""

from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src.spacehack.data.main_quest import (  # noqa: E402
    find_main_quest_step,
    list_main_quest_steps,
    main_quest_step_after,
)
from src.spacehack.data.main_quest.act1_post_prison import (  # noqa: E402
    ARCHIVE_DISCLOSURES,
)
from src.spacehack.data.npcs import list_npcs  # noqa: E402
from src.spacehack.data.trade_goods.core import TRADE_GOODS  # noqa: E402
from src.spacehack.text import RUNTIME  # noqa: E402

STATUS_ACTIVE = "active"
STATUS_AVAILABLE = "available"
STATUS_COMPLETED = "completed"

_VARIANTS = ("intro", "active", "complete", "locked", "option_label")

# objective types that are ever started (start_step): smuggle (crate),
# salvage (talk start), prison (descent). Everything else completes
# straight from AVAILABLE and is never ACTIVE.
_ACTIVE_TYPES = frozenset({"smuggle", "salvage", "prison"})

# Candidate planets for dialogue_planet_id resolution — the union of
# every planet restriction used by any dialogue, plus unrestricted.
_CANDIDATE_PLANETS = ("", "earth", "mercury", "ac_station", "barnards_b")


def _all_npc_ids() -> tuple[str, ...]:
    _ids: set[str] = set()
    for _step in list_main_quest_steps():
        _ids.update(_step.dialogues.keys())
    for _npc in list_npcs():
        _ids.add(_npc.id)
    return tuple(sorted(_ids))


_DISCLOSURE_FIELDS = (
    "label",
    "log_message",
    "followup_message",
    "waiting_title",
    "waiting_description",
    "ready_message",
)


def _all_overlay_keys() -> set[str]:
    """Every step.* / npc.* / good.* / runtime.* / disclosure.* key the extractor emits."""
    _keys: set[str] = set(RUNTIME)
    for _spec in ARCHIVE_DISCLOSURES:
        for _field in _DISCLOSURE_FIELDS:
            if getattr(_spec, _field, ""):
                _keys.add(f"disclosure.{_spec.key}.{_field}")
    for _step in list_main_quest_steps():
        _keys.add(f"step.{_step.id}.title")
        if _step.description:
            _keys.add(f"step.{_step.id}.description")
        if _step.completion_flavor:
            _keys.add(f"step.{_step.id}.completion_flavor")
        if _step.ready_message:
            _keys.add(f"step.{_step.id}.ready_message")
        for _npc_id, _dlg in _step.dialogues.items():
            for _variant in _VARIANTS:
                if getattr(_dlg, _variant, ""):
                    _keys.add(f"step.{_step.id}.dialogue.{_npc_id}.{_variant}")
    for _npc in list_npcs():
        if _npc.flavor_text:
            _keys.add(f"npc.{_npc.id}.flavor_text")
    for _g in TRADE_GOODS:
        _keys.add(f"good.{_g.id}.name")
        _keys.add(f"good.{_g.id}.description")
    return _keys


def _ctx(progress: dict[str, str], chain: str, planet: str) -> SimpleNamespace:
    return SimpleNamespace(
        main_quest_progress=dict(progress),
        main_quest_chain=chain,
        main_quest_gate={},
        main_quest_disclosure="",
        main_quest_complete=False,
        post_prison_orbit_seen=False,
        current_city_id=planet,
        player_active_missions=[],
        main_quest_backing=set(),
        main_quest_unlocked_items=set(),
        log=None,
    )


# ---------------------------------------------------------------------------
# Faithful ports of main_quest/_dialogue.py
# ---------------------------------------------------------------------------

def _dialogue_locked(ctx, dlg) -> bool:
    return bool(dlg.backing_faction) and dlg.backing_faction != ctx.main_quest_chain


def _planet_ok(ctx, dlg) -> bool:
    return (not dlg.dialogue_planet_id) or ctx.current_city_id == dlg.dialogue_planet_id


def _live_entry(ctx, npc_id: str):
    """Port of _live_dialogue: return (step, dialogue) for the top entry."""
    for _status in (STATUS_ACTIVE, STATUS_AVAILABLE, STATUS_COMPLETED):
        for _step_id, _st in ctx.main_quest_progress.items():
            if _st != _status:
                continue
            try:
                _step = find_main_quest_step(_step_id)
            except KeyError:
                continue
            _dlg = _step.dialogues.get(npc_id)
            if _dlg is None:
                continue
            if _status == STATUS_ACTIVE and not _dlg.active:
                continue
            if _status == STATUS_AVAILABLE and not _dlg.intro:
                continue
            if _status == STATUS_COMPLETED and not _dlg.complete:
                continue
            if _planet_ok(ctx, _dlg):
                return _step, _dlg
    return None


def _smuggle_suppressed(step, npc_id: str, crate_held: bool) -> bool:
    """Port of the smuggle crate condition inside resolve_npc_dialogue."""
    if step.objective_type != "smuggle":
        return False
    return (
        (crate_held and step.requires_npc_id != npc_id)
        or (not crate_held and step.requires_npc_id == npc_id)
    )


def _talk_key(ctx, npc_id: str, crates_held: frozenset[str]) -> str:
    """Port of resolve_npc_dialogue; return the overlay key displayed."""
    _live = _live_entry(ctx, npc_id)
    if _live is None:
        return f"npc.{npc_id}.flavor_text"
    _step, _dlg = _live
    _status = ctx.main_quest_progress[_step.id]
    if _dialogue_locked(ctx, _dlg):
        return (
            f"step.{_step.id}.dialogue.{npc_id}.locked"
            if _dlg.locked else f"npc.{npc_id}.flavor_text"
        )
    _triggers = (
        _dlg.trigger_on_talk
        and _status in (STATUS_AVAILABLE, STATUS_ACTIVE)
        and not _smuggle_suppressed(_step, npc_id, _step.id in crates_held)
    )
    if _triggers:
        return f"npc.{npc_id}.flavor_text"
    _variant = (
        "active" if _status == STATUS_ACTIVE
        else "intro" if _status == STATUS_AVAILABLE
        else "complete"
    )
    return f"step.{_step.id}.dialogue.{npc_id}.{_variant}"


def _option_key(ctx, npc_id: str, crates_held: frozenset[str]) -> str | None:
    """Port of quest_option_for; return the overlay key, if any."""
    _live = _live_entry(ctx, npc_id)
    if _live is None:
        return None
    _step, _dlg = _live
    if _dialogue_locked(ctx, _dlg):
        return None
    if not _dlg.option_label:
        return None
    if ctx.main_quest_progress[_step.id] == STATUS_COMPLETED:
        return None
    if _step.objective_type == "smuggle":
        _held = _step.id in crates_held
        _is_receiver = _step.requires_npc_id == npc_id
        if (_held and not _is_receiver) or (not _held and _is_receiver):
            return None
    return f"step.{_step.id}.dialogue.{npc_id}.option_label"


def _breadcrumb_keys(progress: dict[str, str], chain: str) -> set[str]:
    """Mirror _breadcrumb.current_main_quest_objective via the real fn."""
    from src.spacehack.main_quest._breadcrumb import current_main_quest_objective as _cmqo
    _obj = _cmqo(_ctx(progress, chain, ""))
    if _obj is None:
        return set()
    _title, _desc = _obj
    _keys: set[str] = set()
    for _step_id, _st in progress.items():
        try:
            _step = find_main_quest_step(_step_id)
        except KeyError:
            continue
        if _step.title == _title:
            _keys.add(f"step.{_step_id}.title")
        if _step.description and _step.description == _desc:
            _keys.add(f"step.{_step_id}.description")
    return _keys


def _snapshot_keys(
    progress: dict[str, str],
    chain: str,
    crates_held: frozenset[str],
) -> set[str]:
    _keys = _breadcrumb_keys(progress, chain)
    for _npc_id in _all_npc_ids():
        for _planet in _CANDIDATE_PLANETS:
            _ctx_p = _ctx(progress, chain, _planet)
            _keys.add(_talk_key(_ctx_p, _npc_id, crates_held))
            _opt = _option_key(_ctx_p, _npc_id, crates_held)
            if _opt is not None:
                _keys.add(_opt)
    return _keys


def _q1_offer_keys(chain: str) -> set[str]:
    """The post-lock-in help-offer modal shows the q1 dialogue intro."""
    _q1 = main_quest_step_after("prologue_seek_help", chain=chain)
    if _q1 is None:
        return set()
    _keys: set[str] = set()
    for _npc_id, _dlg in _q1.dialogues.items():
        if _dlg.intro:
            _keys.add(f"step.{_q1.id}.dialogue.{_npc_id}.intro")
    return _keys


def _walk(chain: str, chain_steps: tuple[str, ...]):
    """Yield (progress, crates_held) for every reachable display state."""
    _progress: dict[str, str] = {}
    _crates: set[str] = set()

    def _snap():
        return dict(_progress), frozenset(_crates)

    yield _snap()  # pre-signal
    _progress["prologue_signal"] = STATUS_COMPLETED
    _progress["prologue_mars_unlocked"] = STATUS_AVAILABLE
    yield _snap()  # signal received, not yet on Mars
    _progress["prologue_mars_unlocked"] = STATUS_COMPLETED
    _progress["prologue_mars_entrance"] = STATUS_ACTIVE
    yield _snap()  # on Mars, door not found
    _progress["prologue_mars_entrance"] = STATUS_COMPLETED
    _progress["prologue_seek_help"] = STATUS_AVAILABLE
    yield _snap()  # seeking help
    _progress["prologue_seek_help"] = STATUS_COMPLETED
    yield _snap()  # locked in; q1 available (+ offer modal fires)
    for _sid in chain_steps:
        _step = find_main_quest_step(_sid)
        if _step.objective_type == "smuggle":
            # AVAILABLE without a crate (hot steps wait for the giver
            # to re-issue; non-hot auto-loads instantly — harmless to
            # over-include)
            _progress[_sid] = STATUS_AVAILABLE
            yield _snap()
            _progress[_sid] = STATUS_ACTIVE
            _crates.add(_sid)
            yield _snap()  # crate in the mission hold
            if _step.smuggle_hot:
                _progress[_sid] = STATUS_AVAILABLE
                _crates.discard(_sid)
                yield _snap()  # crate confiscated; giver recovery live
                _progress[_sid] = STATUS_ACTIVE
                _crates.add(_sid)
                yield _snap()
            _progress[_sid] = STATUS_COMPLETED
            _crates.discard(_sid)
            yield _snap()
        elif _step.objective_type == "salvage":
            _progress[_sid] = STATUS_AVAILABLE
            yield _snap()
            _progress[_sid] = STATUS_ACTIVE
            yield _snap()
            _progress[_sid] = STATUS_COMPLETED
            yield _snap()
        else:
            _progress[_sid] = STATUS_AVAILABLE
            yield _snap()
            _progress[_sid] = STATUS_COMPLETED
            yield _snap()
        _next = main_quest_step_after(_sid, chain=chain)
        if _next is not None and _step.wait_days > 0:
            yield _snap()  # time gate: next step not yet scheduled
    _progress["prologue_open"] = STATUS_AVAILABLE
    yield _snap()
    _progress["prologue_open"] = STATUS_COMPLETED
    yield _snap()
    _progress["act1_prison"] = STATUS_AVAILABLE
    yield _snap()
    _progress["act1_prison"] = STATUS_ACTIVE
    yield _snap()
    _progress["act1_prison"] = STATUS_COMPLETED
    yield _snap()
    _progress["research_alpha"] = STATUS_AVAILABLE
    yield _snap()
    _progress["research_alpha"] = STATUS_COMPLETED
    yield _snap()
    yield _snap()  # research_alpha_report gate (14 days)
    _progress["research_alpha_report"] = STATUS_AVAILABLE
    yield _snap()
    _progress["research_alpha_report"] = STATUS_COMPLETED
    yield _snap()


_CHAINS: dict[str, tuple[str, ...]] = {
    "bar": ("bar_q1_oldhand", "bar_q2_proof", "bar_q3_rigparts",
            "bar_q4_blackmarket", "bar_q5_charged", "bar_q6_rig"),
    "merchants": ("mer_q1_contract", "mer_q2_strike", "mer_q3_transport",
                  "mer_q4_calibrate", "mer_q5_cutter"),
    "lab": ("lab_q1_sample", "lab_q2_delivery", "lab_q3_reference",
            "lab_q4_xenolinguist", "lab_q5_frequency", "lab_q6_return",
            "lab_q7_key"),
    "militia": ("mil_q1_report", "mil_q2_cache", "mil_q3_inspection",
                "mil_q4_demolitions", "mil_q5_livefire", "mil_q6_charge"),
}


def main() -> int:
    _all = _all_overlay_keys()
    # Runtime strings and disclosure fields render whenever their code
    # path fires (not gated by quest state), so they display by
    # construction; the state simulation below covers step.* / npc.*.
    _displayed: set[str] = set(RUNTIME)
    _displayed |= {
        f"disclosure.{_spec.key}.{_field}"
        for _spec in ARCHIVE_DISCLOSURES
        for _field in _DISCLOSURE_FIELDS
    }
    # Trade-good names + descriptions render in inventory, trade, loot,
    # and quest-log cargo UI regardless of quest state — displayed by
    # construction.
    _displayed |= {
        f"good.{_g.id}.{_field}"
        for _g in TRADE_GOODS
        for _field in ("name", "description")
    }
    # completion_flavor renders in the completion log line, the
    # wait-days gate popup, and the waiting breadcrumb — every step
    # that completes does so through complete_step, which logs it, so
    # credit it by construction. ready_message renders ONLY as the
    # gate-elapse summon (INCOMING MESSAGE), so it is live only when
    # the step sets a gate (wait_days > 0) and has a next step to
    # unlock; anything else is dead text.
    _displayed |= {
        f"step.{_step.id}.completion_flavor"
        for _step in list_main_quest_steps()
        if _step.completion_flavor
    }
    _displayed |= {
        f"step.{_step.id}.ready_message"
        for _step in list_main_quest_steps()
        if _step.ready_message
        and _step.wait_days > 0
        and main_quest_step_after(_step.id, chain=_step.chain) is not None
    }
    for _chain, _steps in _CHAINS.items():
        _displayed |= _q1_offer_keys(_chain)
        for _progress, _crates in _walk(_chain, _steps):
            _displayed |= _snapshot_keys(_progress, _chain, _crates)
    _dead = _all - _displayed
    # Classify: only active/complete/locked variants can be deleted.
    # Functional gates must stay even though never displayed:
    #   * ``intro`` on an option-bearing dialogue gates the option row
    #     in the AVAILABLE pass of _live_dialogue
    #   * ``active`` on a smuggle RECEIVER's option-bearing dialogue
    #     gates the handover row in the ACTIVE pass (removing it would
    #     softlock the delivery)
    #   * titles render in the completion log line
    #     ("[MAIN QUEST] {title} - complete.")
    _keep = {_k for _k in _dead if _k.endswith(".intro")}
    _keep |= {_k for _k in _dead if _k.endswith(".title")}
    for _step in list_main_quest_steps():
        if _step.objective_type != "smuggle":
            continue
        for _npc_id, _dlg in _step.dialogues.items():
            if _dlg.active and _dlg.option_label and _step.requires_npc_id == _npc_id:
                _keep.add(f"step.{_step.id}.dialogue.{_npc_id}.active")
    _removable = _dead - _keep
    print(
        f"overlay keys: {len(_all)}   displayed: {len(_all - _dead)}"
        f"   unreachable: {len(_dead)}"
    )
    print(f"  REMOVABLE ({len(_removable)}) — delete from data:")
    for _key in sorted(_removable):
        print(f"    {_key}")
    print(f"  KEEP ({len(_keep)}) — functional gates + log-line titles:")
    for _key in sorted(_keep):
        print(f"    {_key}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
