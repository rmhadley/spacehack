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
    return SimpleNamespace(
        main_quest_chain=chain,
        main_quest_progress=progress,
        player_active_missions=missions or [],
    )


# ---------------------------------------------------------------------------
# Tag placement in the step catalog
# ---------------------------------------------------------------------------


def test_heat_tags_are_declared_on_the_expected_steps():
    assert find_main_quest_step("bar_q2_proof").heat == ("militia_scan",)
    assert find_main_quest_step("bar_q4_blackmarket").heat == (
        "militia_scan",
        "militia_aggro",
    )
    assert find_main_quest_step("bar_q5_charged").heat == (
        "militia_scan",
        "militia_aggro",
    )
    assert find_main_quest_step("bar_q6_rig").heat == ()  # final step: implicit expiry
    assert find_main_quest_step("mer_q3_transport").heat == ("consortium",)
    assert find_main_quest_step("mer_q4_calibrate").heat == ("consortium",)
    assert find_main_quest_step("mer_q5_cutter").heat == ()  # final step: implicit expiry


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
        _ctx("merchants", {"mer_q4_calibrate": "active"})
    )


def test_consortium_heat_off_for_other_chains():
    assert not _heat.consortium_heat_active(
        _ctx("bar", {"mer_q3_transport": "available"})
    )


def test_consortium_heat_expires_once_the_final_step_completes():
    assert not _heat.consortium_heat_active(_ctx("merchants", {
        "mer_q3_transport": "completed",
        "mer_q4_calibrate": "completed",
        "mer_q5_cutter": "completed",
    }))
