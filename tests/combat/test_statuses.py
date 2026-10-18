"""The status engine's unit pins (doc 103 Build A): apply / advance /
sum_effects laws (S1-S3), the KeyError/silent-skip pair, the
actor-symmetry pin, and the structural vocabulary (dot events, the
HUD segment fold). The engine is pure — every test drives plain
containers, no combat session.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

import pytest

from src.spacehack.combat import _statuses
from src.spacehack.combat._statuses import ActiveStatus, StatusEffects
from src.spacehack.data.statuses import (
    NEURAL_STIM_LOAN_ID,
    NEURAL_STIM_REPAY_LINE,
    OPENER_WINDOW_ID,
    PIRATE_OPENER_ID,
    REGEN_ID,
    STIM_ID,
    StatusSpec,
    find_status,
)


def _fresh(status_id: str, **over) -> ActiveStatus:
    """One ActiveStatus with spec defaults (the apply-side twin)."""
    spec = find_status(status_id)
    fields = dict(
        status_id=status_id,
        remaining_turns=spec.duration if spec.duration_class == "rounds" else 0,
        potency=1.0, source=None, theater=None,
    )
    fields.update(over)
    return ActiveStatus(**fields)


# --- apply -------------------------------------------------------------------


def test_apply_returns_applied_and_uses_row_numbers():
    player: dict[str, ActiveStatus] = {}
    assert _statuses.apply(player, REGEN_ID, source="Med Pack") == "applied"
    assert player[REGEN_ID].remaining_turns == 3
    assert player[REGEN_ID].source == "Med Pack"
    assert _statuses.apply(player, STIM_ID) == "applied"
    assert player[STIM_ID].remaining_turns == 3


def test_apply_raises_on_unknown_ids_authoring_errors_only():
    with pytest.raises(KeyError):
        _statuses.apply({}, "no_such_status")


def test_refresh_is_new_wins_metadata_and_duration_reset():
    player: dict[str, ActiveStatus] = {}
    _statuses.apply(player, REGEN_ID, source="Med Pack")
    _statuses.advance(player)  # 3 -> 2
    assert player[REGEN_ID].remaining_turns == 2
    assert _statuses.apply(player, REGEN_ID, source="Field Kit") == "refreshed"
    assert len(player) == 1
    assert player[REGEN_ID].remaining_turns == 3  # duration reset
    assert player[REGEN_ID].source == "Field Kit"  # NEW WINS (S2)
    assert player[REGEN_ID].potency == 1.0


def test_refresh_at_cap_refreshes_duration_grants_no_stack(monkeypatch):
    """S3, via a synthetic stacking row (none ships in v1)."""
    _row = StatusSpec(
        id="synth_stack", name="Synth", polarity=True,
        duration=2, duration_class="rounds",
        stacking="stacks", stacks_max=2, ap_per_round=1,
    )
    monkeypatch.setattr(_statuses, "find_status", lambda i: _row)
    enemy: dict[str, ActiveStatus] = {}
    assert _statuses.apply(enemy, "synth_stack") == "applied"
    assert _statuses.apply(enemy, "synth_stack") == "stacked"
    assert enemy["synth_stack"].stacks == 2
    assert _statuses.apply(enemy, "synth_stack") == "refreshed"  # at cap
    assert enemy["synth_stack"].stacks == 2  # no new stack
    assert enemy["synth_stack"].remaining_turns == 2  # duration still resets


# --- advance (the S1 tick law) -------------------------------------------------


def test_three_round_regen_fires_exactly_three_heals():
    player: dict[str, ActiveStatus] = {}
    _statuses.apply(player, REGEN_ID)
    heals = [_statuses.advance(player) for _ in range(4)]
    assert [ev for evs in heals for ev in evs].count(("heal", REGEN_ID, 2)) == 3
    assert REGEN_ID not in player  # dropped at the third boundary
    assert heals[2] == (
        ("heal", REGEN_ID, 2), ("expire", REGEN_ID),
    )  # events fire, THEN the drop


def test_one_round_loan_fires_exactly_once_then_expires():
    player: dict[str, ActiveStatus] = {}
    _statuses.apply(player, NEURAL_STIM_LOAN_ID)
    events = _statuses.advance(player)
    assert events == (
        ("ap", NEURAL_STIM_LOAN_ID, -1), ("expire", NEURAL_STIM_LOAN_ID),
    )
    assert NEURAL_STIM_LOAN_ID not in player
    assert _statuses.advance(player) == ()


def test_same_boundary_refresh_never_double_ticks():
    player: dict[str, ActiveStatus] = {}
    _statuses.apply(player, REGEN_ID)
    _statuses.advance(player)  # heal 1, remaining 2
    _statuses.apply(player, REGEN_ID)  # refresh back to 3
    events = _statuses.advance(player)
    assert events == (("heal", REGEN_ID, 2),)  # ONE heal, not two


def test_fight_class_never_decrements():
    enemies: dict[str, ActiveStatus] = {}
    _statuses.apply(enemies, OPENER_WINDOW_ID)
    assert _statuses.advance(enemies) == ()
    assert enemies[OPENER_WINDOW_ID].remaining_turns == 0


def test_advance_silently_skips_unknown_ids():
    player: dict[str, ActiveStatus] = {}
    # A retired row's live shape under a dead key: unreadable, skipped.
    player["retired_row"] = ActiveStatus("retired_row", 3)
    assert _statuses.advance(player) == ()  # skipped, kept
    assert "retired_row" in player


def test_dot_event_vocabulary_fires_from_a_dot_row(monkeypatch):
    """Structural vocabulary pin: no v1 row authors dot_per_round, so
    the synthetic row proves the ("damage", id, n) event exists."""
    _row = StatusSpec(
        id="synth_dot", name="Burn", polarity=False,
        duration=2, duration_class="rounds", dot_per_round=3,
    )
    monkeypatch.setattr(_statuses, "find_status", lambda i: _row)
    victim: dict[str, ActiveStatus] = {}
    _statuses.apply(victim, "synth_dot")
    assert _statuses.advance(victim)[0] == ("damage", "synth_dot", 3)


# --- sum_effects ---------------------------------------------------------------


def test_sum_effects_folds_payload_times_stacks_times_potency():
    player: dict[str, ActiveStatus] = {}
    _statuses.apply(player, REGEN_ID)
    _statuses.apply(player, STIM_ID)
    _statuses.apply(player, NEURAL_STIM_LOAN_ID)
    assert _statuses.sum_effects(player) == StatusEffects(
        regen_per_round=2, ap_per_round=0,  # +1 stim -1 loan
    )


def test_sum_effects_silently_skips_unknown_ids():
    player: dict[str, ActiveStatus] = {
        "retired_row": ActiveStatus("retired_row", 3),
    }
    assert _statuses.sum_effects(player) == StatusEffects()


def test_sum_effects_scales_with_stacks_and_potency():
    enemy: dict[str, ActiveStatus] = {}
    enemy[STIM_ID] = _fresh(STIM_ID, stacks=2, potency=1.5)
    assert _statuses.sum_effects(enemy).ap_per_round == 3  # 1 x 2 x 1.5


# --- has / potency_of / consume / dispel ----------------------------------------


def test_has_consume_and_potency_of():
    player: dict[str, ActiveStatus] = {}
    assert not _statuses.has(player, PIRATE_OPENER_ID)
    _statuses.apply(player, PIRATE_OPENER_ID)
    assert _statuses.has(player, PIRATE_OPENER_ID)
    assert _statuses.potency_of(player, PIRATE_OPENER_ID) == 1.0
    assert _statuses.potency_of(player, REGEN_ID) is None
    assert _statuses.consume(player, PIRATE_OPENER_ID) is True
    assert _statuses.consume(player, PIRATE_OPENER_ID) is False  # once only


def test_dispel_removes_matches_silently():
    player: dict[str, ActiveStatus] = {}
    _statuses.apply(player, REGEN_ID)
    _statuses.apply(player, PIRATE_OPENER_ID)
    assert _statuses.dispel(player, lambda a: True) == (REGEN_ID, PIRATE_OPENER_ID)
    assert player == {}
    # Removal is silent — never an expire event, never a repay line.
    _statuses.apply(player, NEURAL_STIM_LOAN_ID)
    assert _statuses.dispel(player, lambda a: False) == ()
    assert NEURAL_STIM_LOAN_ID in player


# --- actor symmetry (acceptance criterion 5) -------------------------------------


def test_actor_symmetry_same_battery_both_container_kinds():
    """The player container and an enemy container are the same type
    and read by the same rules: one battery, both shapes, identical
    results (doc 103, actor-symmetric by construction)."""
    player: dict[str, ActiveStatus] = {}
    enemy: dict[str, ActiveStatus] = {}
    for container in (player, enemy):
        assert _statuses.apply(container, REGEN_ID, source="Med Pack") == "applied"
        assert _statuses.apply(container, STIM_ID) == "applied"
        assert _statuses.sum_effects(container) == StatusEffects(
            regen_per_round=2, ap_per_round=1,
        )
        events = _statuses.advance(container)
        assert ("heal", REGEN_ID, 2) in events
        assert ("ap", STIM_ID, 1) in events
        assert _statuses.has(container, REGEN_ID)
        assert _statuses.consume(container, REGEN_ID)
        assert not _statuses.has(container, REGEN_ID)


# --- presentation data + the chrome alias ----------------------------------------


def test_hud_segments_render_labelled_rows_in_their_class_shape():
    player: dict[str, ActiveStatus] = {}
    assert _statuses.hud_segments(player) == ()
    _statuses.apply(player, REGEN_ID)
    _statuses.apply(player, STIM_ID)
    _statuses.apply(player, NEURAL_STIM_LOAN_ID)  # no label: declined
    _statuses.apply(player, PIRATE_OPENER_ID)  # fight class: label only
    assert _statuses.hud_segments(player) == (
        ("REGEN 3", True), ("STIM 3", True), ("OPENER", True),
    )


def test_chrome_stim_repay_alias_is_bit_exact():
    """The ruled repay line has ONE canonical home (the loan row);
    chrome's historical name is the same bytes."""
    from src.spacehack.chrome import STIM_REPAY_LINE

    assert STIM_REPAY_LINE == NEURAL_STIM_REPAY_LINE
    assert find_status(NEURAL_STIM_LOAN_ID).expire_line == STIM_REPAY_LINE


# --- the staggered debut (doc 103 Build B) ---------------------------------------


def test_staggered_row_numbers_and_ruled_prose():
    """The debut row carries the ruled package (S4: -1 AP, 2 rounds,
    refresh) and the Build B prose ledger's exact strings."""
    from src.spacehack.data.statuses import STAGGERED_ID

    spec = find_status(STAGGERED_ID)
    assert (spec.polarity, spec.duration, spec.duration_class) == (
        False, 2, "rounds",
    )
    assert spec.ap_per_round == -1
    assert spec.stacking == "refresh"
    # {victim} carries the CONJUGATED subject ("You are" / "X is") so
    # one template renders both directions grammatically — the ruled
    # renderings, bit-identical.
    assert spec.apply_line == "{victim} staggered!"
    assert spec.expire_line == "The stagger wears off."
    assert spec.hud_label == "STAGGERED"
    assert spec.description == "-1 AP per round."


def test_stun_baton_carries_the_staggered_rider():
    """The delivery vehicle's data home (the retired id branch's
    replacement): staggered at 50 on the spec, the instant-rider
    family's first lingering member."""
    from src.spacehack.data.ground_weapons import find_ground_weapon
    from src.spacehack.data.statuses import STAGGERED_ID

    baton = find_ground_weapon("stun_baton")
    assert baton.status_id == STAGGERED_ID
    assert baton.status_chance == 50
    # The rider resolves: a delivery site naming a dead id is an
    # authoring error (apply raises) — pin the resolution now.
    assert find_status(baton.status_id).id == STAGGERED_ID


def test_every_catalog_row_carries_a_description():
    """The inspect overlay reads every row (q7): a description-less
    row renders bare — the Build B ledger settled all seven."""
    from src.spacehack.data.statuses import list_status

    assert all(spec.description for spec in list_status())
