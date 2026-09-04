"""Tests for the main-quest objective handler registry (Phase 1).

The registry replaces the scattered if/elif objective dispatch: every
cataloged objective type must resolve to a handler, unknown types must not,
and the type-specific hooks (smuggle gating, smuggle trigger) keep their
documented behaviour.
"""

from __future__ import annotations

from types import SimpleNamespace

from src.spacehack.data.main_quest import list_main_quest_steps
from src.spacehack.main_quest.handlers import (
    _smuggle_option_gating,
    _smuggle_trigger,
    handler_for,
    registered_objective_types,
)


def test_every_cataloged_objective_type_has_a_handler():
    """Every objective type used by the step catalog resolves to a handler."""
    _used = {step.objective_type for step in list_main_quest_steps()}
    assert _used  # sanity: the catalog is not empty
    for _objective_type in sorted(_used):
        assert handler_for(_objective_type) is not None, (
            f"objective_type {_objective_type!r} has no registered handler"
        )


def test_unknown_objective_type_has_no_handler():
    """An unregistered objective type resolves to None, never a crash."""
    assert handler_for("not_a_real_objective") is None


def test_registered_types_cover_the_core_objectives():
    _registered = set(registered_objective_types())
    assert {
        "talk",
        "goods",
        "smuggle",
        "salvage",
        "visit",
        "bump",
        "delve",
        "bounty",
        "prison",
    } <= _registered


def test_talk_handler_has_no_trigger_hook():
    """talk steps fall through to complete_step (the default trigger)."""
    _handler = handler_for("talk")
    assert _handler is not None
    assert _handler.on_trigger is None


def test_delve_and_salvage_secure_quest_loot():
    """Only loot-bearing types expose secure_quest_loot to secure_quest_loot."""
    assert handler_for("delve").secures_quest_loot
    assert handler_for("salvage").secures_quest_loot
    assert not handler_for("talk").secures_quest_loot
    assert not handler_for("smuggle").secures_quest_loot


def test_bounty_and_salvage_expose_spawn_creation():
    """Only space-spawn types expose an ensure_spawns hook."""
    assert handler_for("bounty").ensure_spawns is not None
    assert handler_for("salvage").ensure_spawns is not None
    assert handler_for("delve").ensure_spawns is None


def test_smuggle_option_gating_giver_receiver():
    """Smuggle gating: giver offers while the crate is NOT held, receiver
    only while it IS held (mirrors the pre-refactor quest_option_for)."""
    _step = SimpleNamespace(id="bar_q4_blackmarket", requires_npc_id="wolf_barkeep")
    _ctx = SimpleNamespace(
        player_active_missions=[
            SimpleNamespace(main_quest_step_id="bar_q4_blackmarket"),
        ],
    )
    # Crate held: receiver sees the option, giver does not.
    assert _smuggle_option_gating(_ctx, _step, "wolf_barkeep")
    assert not _smuggle_option_gating(_ctx, _step, "old_smuggler")
    # Crate not held: giver sees the option, receiver does not.
    _ctx.player_active_missions = []
    assert _smuggle_option_gating(_ctx, _step, "old_smuggler")
    assert not _smuggle_option_gating(_ctx, _step, "wolf_barkeep")


def test_smuggle_trigger_loads_when_available_hands_over_when_active(monkeypatch):
    """The smuggle on_trigger hook loads the crate when available and hands
    it over when active (mirrors the pre-refactor trigger_dialogue branch)."""
    from src.spacehack.main_quest import _core

    _step = SimpleNamespace(id="lab_q2_delivery")
    _ctx = SimpleNamespace(main_quest_progress={"lab_q2_delivery": "available"})
    _calls: list[str] = []
    monkeypatch.setattr(
        _core,
        "_trigger_smuggle_crate",
        lambda _ctx, _step: _calls.append("load") or True,
    )
    monkeypatch.setattr(
        _core,
        "_complete_smuggle_handover",
        lambda _ctx, _step: _calls.append("handover") or True,
    )

    assert _smuggle_trigger(_ctx, _step)
    assert _calls == ["load"]

    _ctx.main_quest_progress["lab_q2_delivery"] = "active"
    assert _smuggle_trigger(_ctx, _step)
    assert _calls == ["load", "handover"]


# ----- Payment steps (mer_q4_bribe, doc 32) -----------------------------


def _payment_ctx(credits: int):
    from types import SimpleNamespace

    return SimpleNamespace(
        stats=SimpleNamespace(credits=credits),
        main_quest_progress={"mer_q3_transport": "completed"},
        main_quest_gate={},
        main_quest_chain="merchants",
        main_quest_backing={"merchants"},
        main_quest_progress_rewards={},
        current_city_id="depot",  # the attendant's dialogue is depot-gated
        log=SimpleNamespace(
            add=lambda _msg: None,
            add_colored=lambda *_a, **_k: None,  # xp reward logging
        ),
        player_xp=0,  # complete_step rewards
        player_level=1,  # xp level-up loop
        player_skill_points=0,
        main_quest_disclosure="",  # breadcrumb act1 checks
        time_day=10, time_month=3, time_year=2200,  # refit-gate scheduling
    )


def test_payment_option_hidden_until_affordable():
    """The quest row appears only when the player can pay — before that,
    the sandbox raises the funds and the log carries the shortfall."""
    from src.spacehack.main_quest._dialogue import quest_option_for
    poor = _payment_ctx(7_999)
    poor.main_quest_progress["mer_q4_bribe"] = "available"
    assert quest_option_for(poor, "depot_attendant") is None

    rich = _payment_ctx(8_000)
    rich.main_quest_progress["mer_q4_bribe"] = "available"
    row = quest_option_for(rich, "depot_attendant")
    assert row is not None
    assert "8,000" in row[0] or "8000" in row[0], row[0]
    assert row[1] == "mer_q4_bribe"


def test_payment_trigger_consumes_and_completes():
    from src.spacehack.main_quest._dialogue import trigger_dialogue
    from src.spacehack.main_quest._core import step_status

    ctx = _payment_ctx(9_500)
    ctx.main_quest_progress["mer_q4_bribe"] = "available"
    assert trigger_dialogue(ctx, "depot_attendant", "mer_q4_bribe") is True
    assert ctx.stats.credits == 1_500  # consumed exactly 8,000
    assert step_status(ctx, "mer_q4_bribe") == "completed"
    assert "mer_q5_alloy" in ctx.main_quest_gate, "refit wait registered"


def test_merchants_chain_linkage_and_cadence():
    """Seven steps in strict order, Lab-cadence waits (45/60/45/70),
    payment only on the bribe, cutter unlocks the prologue."""
    from src.spacehack.data.main_quest import find_main_quest_step

    order = [
        "mer_q1_contract", "mer_q2_strike", "mer_q3_transport",
        "mer_q4_bribe", "mer_q5_alloy", "mer_q6_survey", "mer_q7_cutter",
    ]
    waits = []
    for i, sid in enumerate(order):
        step = find_main_quest_step(sid)
        if i:
            assert step.requires_step == order[i - 1], sid
        waits.append(step.wait_days)
        if sid != "mer_q4_bribe":
            assert step.payment_credits == 0, sid
    assert waits == [45, 0, 60, 45, 0, 70, 0]  # cutter collects, no wait
    assert find_main_quest_step("mer_q4_bribe").payment_credits == 8000
    assert find_main_quest_step("mer_q7_cutter").unlocks_step == "prologue_open"


def test_merchants_renumber_migration():
    """Saves from older chain layouts map onto the 7-step chain, status
    preserved; a pre-split completed survey back-fills the alloy step."""
    from src.spacehack.main_quest._gates import check_quest_gates

    ctx = _payment_ctx(0)
    ctx.main_quest_progress = {
        "mer_q3_transport": "completed",
        "mer_q4_calibrate": "completed",
        "mer_q5_cutter": "available",
    }
    check_quest_gates(ctx)
    assert "mer_q4_calibrate" not in ctx.main_quest_progress
    assert ctx.main_quest_progress["mer_q5_alloy"] == "completed"
    assert ctx.main_quest_progress["mer_q6_survey"] == "completed"
    assert ctx.main_quest_progress["mer_q7_cutter"] == "available"

    # 6-step era: The Survey was one step (alloy + Vega run).
    split = _payment_ctx(0)
    split.main_quest_progress = {
        "mer_q4_bribe": "completed",
        "mer_q5_calibration": "available",
    }
    check_quest_gates(split)
    assert split.main_quest_progress["mer_q5_alloy"] == "available"
    assert "mer_q6_survey" not in split.main_quest_progress


def test_quest_log_cost_line_renders_from_data():
    """The payment cost renders as a structured Q line (Cost: X$ have Y$).
    Prose MAY cite the cost (the attendant names his price) but the
    digits must match the data — cross-check, don't source (doc 33)."""
    from src.spacehack.main_quest._breadcrumb import _active_payment_step

    ctx = _payment_ctx(6_200)
    ctx.main_quest_progress["mer_q4_bribe"] = "available"
    step = _active_payment_step(ctx)
    assert step is not None and step.payment_credits == 8000
    from src.spacehack.text import get as t_get
    assert f"{step.payment_credits:,}" in t_get(
        "step.mer_q4_bribe.dialogue.depot_attendant.intro"
    ), "intro must cite the exact data cost"
    assert f"{step.payment_credits:,}" in t_get(
        "step.mer_q4_bribe.description"
    ), "description must cite the exact data cost"


def test_alloy_row_one_shot_and_survey_has_no_starter_row():
    """The alloy handover is a one-shot talk row, and the survey step is
    portrait-only — nothing at Tau Ceti b starts the Vega run, which only
    exists once the alloy is collected (playtest v14: the recorder could
    be secured with no alloy in the hold)."""
    from src.spacehack.main_quest._dialogue import quest_option_for

    ctx = _payment_ctx(0)
    ctx.main_quest_progress = {"mer_q5_alloy": "available"}
    row = quest_option_for(ctx, "salvage_specialist")
    assert row is not None and row[1] == "mer_q5_alloy"
    assert row[0] == "Take the smelted alloy"

    done = _payment_ctx(0)
    done.main_quest_progress = {
        "mer_q5_alloy": "completed", "mer_q6_survey": "available",
    }
    assert quest_option_for(done, "salvage_specialist") is None


def test_mer_q5_alloy_completion_loads_the_alloy():
    """Taking the alloy completes the step, lashes the goods into the
    hold, and schedules the survey run immediately (auto-advance, no
    wait — the specialist already briefed the run)."""
    from src.spacehack.main_quest._core import complete_step, step_status

    ctx = _payment_ctx(0)
    ctx.player_owned_ship = SimpleNamespace(inventory={})
    ctx.main_quest_progress["mer_q5_alloy"] = "available"
    assert complete_step(ctx, "mer_q5_alloy") is True
    assert ctx.player_owned_ship.inventory["smelted_alloy"] == 3
    assert step_status(ctx, "mer_q6_survey") == "available"


def test_militia_chain_linkage_and_cadence():
    """Six steps in strict order, Merchants-cadence waits
    (60/40/70/50 = 220 gate-days), charge unlocks the prologue."""
    from src.spacehack.data.main_quest import find_main_quest_step

    order = [
        "mil_q1_report", "mil_q2_cache", "mil_q3_inspection",
        "mil_q4_demolitions", "mil_q5_livefire", "mil_q6_charge",
    ]
    waits = []
    for i, sid in enumerate(order):
        step = find_main_quest_step(sid)
        if i:
            assert step.requires_step == order[i - 1], sid
        waits.append(step.wait_days)
    assert waits == [60, 0, 40, 70, 50, 0]  # charge collects, no wait
    assert find_main_quest_step("mil_q6_charge").unlocks_step == "prologue_open"


def test_quest_cargo_is_quest_goods_not_market_goods():
    """Quest pickups/crates hand out named quest goods (the recorder
    pattern) or virtual mission cargo — never market goods (playtest
    v15: "cargo for quests should be mission cargo"). The bar chain is
    excluded until its own pass (known machine_parts/electronics crate)."""
    from src.spacehack.data.main_quest import list_main_quest_steps
    from src.spacehack.data.trade_goods import find_trade_good

    for step in list_main_quest_steps():
        if step.chain == "bar":
            continue
        good_ids = [gid for gid, _qty in step.delve_good_ids]
        if step.smuggle_good_id:
            good_ids.append(step.smuggle_good_id)
        good_ids += [gid for gid, _qty in step.rewards_goods]
        for gid in good_ids:
            try:
                good = find_trade_good(gid)
            except KeyError:
                continue  # virtual mission cargo (no catalog entry)
            assert good.rarity <= 0.1, (
                f"{step.id} hands out market good {gid!r}"
            )


def test_active_step_breadcrumb_points_at_remaining_route():
    """Each step's Q text names exactly its own leg — the alloy step says
    Tau Ceti b and not Vega; the survey step says Vega and not collection."""
    from src.spacehack.main_quest._breadcrumb import current_main_quest_objective

    ctx = _payment_ctx(0)
    ctx.main_quest_progress = {"mer_q5_alloy": "available"}
    title, desc = current_main_quest_objective(ctx)
    assert title == "The Alloy"
    assert "Tau Ceti" in desc and "Vega" not in desc

    survey = _payment_ctx(0)
    survey.main_quest_progress = {"mer_q6_survey": "active"}
    title2, desc2 = current_main_quest_objective(survey)
    assert title2 == "The Survey"
    assert "Vega" in desc2 and "Collect the smelted alloy" not in desc2

def test_militia_breadcrumb_names_each_leg():
    """Q names the live leg at every state of the militia arc - Earth
    report, Luyten inspection, Cygni live-fire - and the gated state
    shows the Militia wait, never a dead end (doc 35 Phase 3)."""
    from types import SimpleNamespace
    from src.spacehack import message_log
    from src.spacehack.main_quest._breadcrumb import current_main_quest_objective

    def _mil(progress, gate=None):
        return SimpleNamespace(
            main_quest_progress=progress,
            main_quest_chain="militia",
            main_quest_gate=gate or {},
            main_quest_disclosure="",
            log=message_log.MessageLog(capacity=6),
        )

    title, desc = current_main_quest_objective(_mil({"mil_q1_report": "available"}))
    assert title == "Report to the Captain" and "Earth" in desc

    title, desc = current_main_quest_objective(_mil({
        "mil_q2_cache": "completed", "mil_q3_inspection": "available",
    }))
    assert title == "The Inspection" and "Luyten" in desc

    title, desc = current_main_quest_objective(_mil({"mil_q5_livefire": "active"}))
    assert title == "Live-Fire Test" and "Cygni" in desc

    gated = _mil(
        {"mil_q2_cache": "completed"},
        gate={"mil_q3_inspection": (99, 99, 9999)},
    )
    title, desc = current_main_quest_objective(gated)
    assert title == "Awaiting word from the Militia..."
    assert "blockade inspector" in desc, "the gate shows the flavor beat"
