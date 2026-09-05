"""Tests for the data-driven main-quest heat hooks (Phase 2).

Heat behavior is declared on the step data (``MainQuestStep.heat`` tags) and
consumed by :mod:`spacehack.main_quest._heat` — no step ids are hard-coded in
the runtime. These tests pin both the tag placement and the filter semantics.
"""

from __future__ import annotations

from types import SimpleNamespace

from src.spacehack.data.main_quest import find_main_quest_step
from src.spacehack.main_quest import _heat


def _ctx(chain: str, progress: dict, missions: list | None = None):
    from src.spacehack.message_log import MessageLog
    return SimpleNamespace(
        main_quest_chain=chain,
        main_quest_progress=progress,
        player_active_missions=missions or [],
        main_quest_gate={},
        main_quest_backing=set(),
        log=MessageLog(capacity=6),
    )


# ---------------------------------------------------------------------------
# Tag placement in the step catalog
# ---------------------------------------------------------------------------


def test_heat_tags_are_declared_on_the_expected_steps():
    assert find_main_quest_step("bar_q2_proof").heat == ("militia_scan",)
    assert find_main_quest_step("bar_q4_blackmarket").heat == (
        "militia_scan",
    )
    assert find_main_quest_step("bar_q5_charged").heat == (
        "militia_scan",
        "militia_aggro",
    )
    assert find_main_quest_step("bar_q6_rig").heat == ()  # final step: implicit expiry
    assert find_main_quest_step("mer_q3_transport").heat == ("consortium",)
    assert find_main_quest_step("mer_q6_survey").heat == ("consortium",)
    assert find_main_quest_step("mer_q7_cutter").heat == ()  # final step: implicit expiry


# ---------------------------------------------------------------------------
# Bar chain: militia scan floor (militia_scan)
# ---------------------------------------------------------------------------


def test_bar_scan_floor_live_while_a_heat_step_is_active():
    assert _heat.bar_heat_active(_ctx("bar", {"bar_q4_blackmarket": "active"}))
    assert _heat.bar_heat_active(_ctx("bar", {"bar_q5_charged": "available"}))
    # The proof run's crate is in the hold -> step active -> scan floor on.
    assert _heat.bar_heat_active(_ctx("bar", {"bar_q2_proof": "active"}))


def test_bar_scan_floor_off_for_other_chains():
    assert not _heat.bar_heat_active(
        _ctx("militia", {"bar_q4_blackmarket": "active"})
    )


def test_bar_scan_floor_off_with_no_live_heat_steps():
    assert not _heat.bar_heat_active(_ctx("bar", {}))


def test_bar_scan_floor_expires_once_the_final_step_completes():
    """Expiry is implicit: no live heat steps remain after bar_q6."""
    assert not _heat.bar_heat_active(_ctx("bar", {
        "bar_q2_proof": "completed",
        "bar_q3_rigparts": "completed",
        "bar_q4_blackmarket": "completed",
        "bar_q5_charged": "completed",
        "bar_q6_rig": "completed",
    }))


# ---------------------------------------------------------------------------
# Bar chain: charged-cell auto-aggro (militia_aggro)
# ---------------------------------------------------------------------------


def test_charged_cell_aggro_while_the_crate_is_held():
    _missions = [SimpleNamespace(main_quest_step_id="bar_q5_charged")]
    assert _heat.charged_cell_in_sol(
        _ctx("bar", {"bar_q5_charged": "active"}, missions=_missions),
        "sol",
    )


def test_charged_cell_no_aggro_outside_sol():
    """Regression (playtest v2): the cell hunted the player out of Wolf
    359 - the system check was missing. The hunt starts at the Sol
    jump, where the discharge profile is on file."""
    _missions = [SimpleNamespace(main_quest_step_id="bar_q5_charged")]
    assert not _heat.charged_cell_in_sol(
        _ctx("bar", {"bar_q5_charged": "active"}, missions=_missions),
        "wolf_359",
    )


def test_charged_cell_no_aggro_without_the_crate():
    assert not _heat.charged_cell_in_sol(
        _ctx("bar", {"bar_q5_charged": "active"}, missions=[]),
        "sol",
    )


def test_charged_cell_aggro_ignored_for_other_chains():
    _missions = [SimpleNamespace(main_quest_step_id="bar_q5_charged")]
    assert not _heat.charged_cell_in_sol(
        _ctx("militia", {"bar_q5_charged": "active"}, missions=_missions),
        "sol",
    )


# ---------------------------------------------------------------------------
# Merchant chain: consortium pirate heat (consortium)
# ---------------------------------------------------------------------------


def test_consortium_heat_live_while_merchant_steps_are_live():
    assert _heat.consortium_heat_active(
        _ctx("merchants", {"mer_q3_transport": "available"})
    )
    assert _heat.consortium_heat_active(
        _ctx("merchants", {"mer_q6_survey": "active"})
    )


def test_consortium_heat_off_for_other_chains():
    assert not _heat.consortium_heat_active(
        _ctx("bar", {"mer_q3_transport": "available"})
    )


def test_consortium_heat_expires_once_the_final_step_completes():
    assert not _heat.consortium_heat_active(_ctx("merchants", {
        "mer_q3_transport": "completed",
        "mer_q5_alloy": "completed",
        "mer_q6_survey": "completed",
        "mer_q7_cutter": "completed",
    }))


def test_lost_quest_cargo_raises_the_quest_styled_window(monkeypatch):
    """Playtest v2 legibility: a confiscated main-quest crate shows a
    main-quest-styled window (the colored log line was missed twice),
    and the step resets so the giver re-offers."""
    from src.spacehack import main_quest as _mq
    from src.spacehack.main_quest import _act0

    summon = []
    monkeypatch.setattr(_act0, "show_quest_summon",
                        lambda _ctx, message, objective="": summon.append((message, objective)))
    ctx = _ctx("bar", {"bar_q5_charged": "active"})
    crate = SimpleNamespace(
        main_quest_step_id="bar_q5_charged", title="The Return Run",
        is_procedural=True, mission_id="mq:bar_q5_charged",
    )
    assert _mq.fail_smuggle_step(ctx, crate)
    assert ctx.main_quest_progress["bar_q5_charged"] == "available"
    assert summon and "Power Cell" in summon[0][0]
    assert "Wolf 359" in summon[0][1], "the window breadcrumbs the pickup"


def test_smuggle_handover_lands_with_a_readout(monkeypatch):
    """Bar playtest v3: accept the handover -> the modals closed and
    NOTHING visible happened. The handover now shows the completion
    readout (flavor + next step) unless the step gates its next - the
    gate popup owns that case, as with visit steps."""
    from src.spacehack.main_quest import _core, _objectives

    readouts = []
    monkeypatch.setattr(_objectives, "show_step_readout",
                        lambda _ctx, step: readouts.append(step.id))
    ship = SimpleNamespace(inventory={}, mission_reserved=1,
                           ship_id="scout", weapons=(), modules=(), cargo_ammo=0)
    crate = SimpleNamespace(main_quest_step_id="bar_q5_charged")
    ctx = _ctx("bar", {"bar_q5_charged": "active"}, missions=[crate])
    ctx.player_owned_ship = ship
    ctx.stats = SimpleNamespace(credits=0)
    ctx.player_xp, ctx.player_level, ctx.player_skill_points = 0, 1, 0
    ctx.main_quest_backing = set()
    ctx.time_day, ctx.time_month, ctx.time_year = 1, 1, 2200

    step = _core.find_main_quest_step("bar_q5_charged")
    assert _core._complete_smuggle_handover(ctx, step)
    assert readouts == ["bar_q5_charged"]
    assert ship.mission_reserved == 0

    # Gated handover (mer q3: wait 60 + flavor): the gate popup owns it.
    readouts.clear()
    gate = _core.find_main_quest_step("mer_q3_transport")
    ctx2 = _ctx("merchants", {"mer_q3_transport": "active"},
                missions=[SimpleNamespace(main_quest_step_id="mer_q3_transport")])
    ctx2.player_owned_ship = SimpleNamespace(
        inventory={}, mission_reserved=3, ship_id="scout",
        weapons=(), modules=(), cargo_ammo=0)
    ctx2.stats = ctx.stats
    ctx2.player_xp, ctx2.player_level, ctx2.player_skill_points = 0, 1, 0
    ctx2.main_quest_backing = set()
    ctx2.time_day, ctx2.time_month, ctx2.time_year = 1, 1, 2200
    assert _core._complete_smuggle_handover(ctx2, gate)
    assert readouts == [], "the gate popup owns gated flavor"
