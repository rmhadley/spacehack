"""Tests for the data-driven quest-NPC presence system (Phase 3).

Quest NPCs (the four faction experts) are ADDITIVE city NPCs: they stand in
their guild building only while a live step of the locked chain tags them via
``MainQuestStep.npc_presence``, and vanish once those steps complete. Placement
comes from each planet's ``quest_npc_spots``. No step ids are hard-coded in the
runtime — these tests pin the tag placement, the filter semantics, and the
spawn behavior.
"""

from __future__ import annotations

from types import SimpleNamespace

from src.spacehack import world
from src.spacehack.data.main_quest import (
    find_main_quest_step,
    list_main_quest_steps,
)
from src.spacehack.data.npcs import find_npc
from src.spacehack.data.planets import find_planet_spec, list_planet_specs, load_planet
from src.spacehack.main_quest import _act0


def _ctx(chain: str, progress: dict):
    return SimpleNamespace(
        main_quest_chain=chain,
        main_quest_progress=progress,
        player_active_missions=[],
        log=SimpleNamespace(add=lambda *a, **k: None),
    )


def _building_spot(planet_id: str, label: str) -> world.Position:
    """Where a quest NPC stands: one tile east of the interior center."""
    _spec = find_planet_spec(planet_id)
    for _b in _spec.buildings:
        if _b.label == label:
            return world.Position(
                (_b.x_lo + _b.x_hi) // 2 + 1,
                (_b.y_lo + _b.y_hi) // 2,
            )
    raise AssertionError(f"no {label!r} building on {planet_id}")


# ---------------------------------------------------------------------------
# Tag placement in the step catalog
# ---------------------------------------------------------------------------


def test_npc_presence_tags_are_declared_on_the_expected_steps():
    # Bar chain: the old smuggler covers the proof run through the
    # power-cell handover, then leaves (q5/q6 carry no tag).
    assert find_main_quest_step("bar_q2_proof").npc_presence == ("old_smuggler",)
    assert find_main_quest_step("bar_q3_rigparts").npc_presence == ("old_smuggler",)
    assert find_main_quest_step("bar_q4_blackmarket").npc_presence == ("old_smuggler",)
    assert find_main_quest_step("bar_q5_charged").npc_presence == ()
    assert find_main_quest_step("bar_q6_rig").npc_presence == ()
    # Merchant chain: the salvage specialist handles the ore + the alloy.
    assert find_main_quest_step("mer_q3_transport").npc_presence == ("salvage_specialist",)
    assert find_main_quest_step("mer_q4_calibrate").npc_presence == ("salvage_specialist",)
    assert find_main_quest_step("mer_q5_cutter").npc_presence == ()
    # Militia + lab chains: the recruit / dataset receiver.
    assert find_main_quest_step("mil_q4_demolitions").npc_presence == ("demolitions_expert",)
    assert find_main_quest_step("lab_q4_xenolinguist").npc_presence == ("xenolinguist",)


def test_every_presence_npc_resolves_in_catalog_and_has_a_spot():
    """Cross-data integrity: a tagged NPC must exist and stand somewhere."""
    _spotted = {
        _nid
        for _ps in list_planet_specs()
        for _nid, _label in _ps.quest_npc_spots
    }
    for _step in list_main_quest_steps():
        for _nid in _step.npc_presence:
            assert find_npc(_nid).id == _nid, _step.id
            assert _nid in _spotted, f"{_nid} tagged by {_step.id} has no spot"


def test_quest_npc_spots_name_existing_guild_buildings():
    for _ps in list_planet_specs():
        _labels = {_b.label for _b in _ps.buildings}
        for _nid, _label in _ps.quest_npc_spots:
            assert _label in _labels, f"{_ps.id} spot for {_nid} has no {_label!r}"
            assert any(
                _b.label == _label and _b.npc_id for _b in _ps.buildings
            ), f"{_ps.id} {_label!r} is not a real guild building"


# ---------------------------------------------------------------------------
# Presence filter semantics (_quest_npcs_for_planet)
# ---------------------------------------------------------------------------


def test_old_smuggler_present_through_the_bar_chain_window():
    assert _act0._quest_npcs_for_planet(
        _ctx("bar", {"bar_q2_proof": "active"}), "barnards_b",
    ) == ("old_smuggler",)
    assert _act0._quest_npcs_for_planet(
        _ctx("bar", {"bar_q3_rigparts": "available"}), "barnards_b",
    ) == ("old_smuggler",)
    assert _act0._quest_npcs_for_planet(
        _ctx("bar", {"bar_q4_blackmarket": "active"}), "barnards_b",
    ) == ("old_smuggler",)


def test_old_smuggler_leaves_once_the_chain_moves_past_him():
    # After the cell handover (q4 complete) he is gone.
    assert _act0._quest_npcs_for_planet(
        _ctx("bar", {
            "bar_q2_proof": "completed",
            "bar_q3_rigparts": "completed",
            "bar_q4_blackmarket": "completed",
            "bar_q5_charged": "available",
        }),
        "barnards_b",
    ) == ()


def test_presence_is_chain_gated():
    # Another chain's steps never summon a bar NPC.
    assert _act0._quest_npcs_for_planet(
        _ctx("militia", {"bar_q2_proof": "active"}), "barnards_b",
    ) == ()
    # Pre-fork (no chain chosen yet) no expert is present.
    assert _act0._quest_npcs_for_planet(
        _ctx("", {"bar_q2_proof": "active"}), "barnards_b",
    ) == ()


def test_presence_is_planet_gated():
    # The old smuggler only stands on his spot planet.
    assert _act0._quest_npcs_for_planet(
        _ctx("bar", {"bar_q2_proof": "active"}), "tc_b",
    ) == ()
    assert _act0._quest_npcs_for_planet(
        _ctx("bar", {"bar_q2_proof": "active"}), "earth",
    ) == ()


def test_salvage_specialist_present_for_ore_and_alloy():
    # q3 (ore delivery) and q4 (alloy handover — a space salvage whose
    # objective planet is NOT tc_b) both keep her on Tau Ceti b.
    assert _act0._quest_npcs_for_planet(
        _ctx("merchants", {"mer_q3_transport": "active"}), "tc_b",
    ) == ("salvage_specialist",)
    assert _act0._quest_npcs_for_planet(
        _ctx("merchants", {"mer_q4_calibrate": "available"}), "tc_b",
    ) == ("salvage_specialist",)
    assert _act0._quest_npcs_for_planet(
        _ctx("merchants", {
            "mer_q3_transport": "completed",
            "mer_q4_calibrate": "completed",
            "mer_q5_cutter": "available",
        }),
        "tc_b",
    ) == ()


def test_militia_and_lab_experts_present_only_while_recruiting():
    assert _act0._quest_npcs_for_planet(
        _ctx("militia", {"mil_q4_demolitions": "available"}), "eri_b",
    ) == ("demolitions_expert",)
    assert _act0._quest_npcs_for_planet(
        _ctx("militia", {"mil_q4_demolitions": "completed"}), "eri_b",
    ) == ()
    assert _act0._quest_npcs_for_planet(
        _ctx("lab", {"lab_q4_xenolinguist": "active"}), "ac_station",
    ) == ("xenolinguist",)
    assert _act0._quest_npcs_for_planet(
        _ctx("lab", {"lab_q4_xenolinguist": "completed"}), "ac_station",
    ) == ()


# ---------------------------------------------------------------------------
# Spawn behavior
# ---------------------------------------------------------------------------


def test_spawn_places_old_smuggler_at_the_bar_interior_center():
    _gm = load_planet("barnards_b")
    _act0.spawn_quest_npcs(
        _ctx("bar", {"bar_q2_proof": "active"}), _gm, "barnards_b",
    )
    _smugglers = [_e for _e in _gm.entities if _e.npc_id == "old_smuggler"]
    assert len(_smugglers) == 1
    assert _smugglers[0].pos == _building_spot("barnards_b", "bar")


def test_spawn_is_idempotent():
    _gm = load_planet("barnards_b")
    _act0.spawn_quest_npcs(
        _ctx("bar", {"bar_q2_proof": "active"}), _gm, "barnards_b",
    )
    _act0.spawn_quest_npcs(
        _ctx("bar", {"bar_q2_proof": "active"}), _gm, "barnards_b",
    )
    assert sum(_e.npc_id == "old_smuggler" for _e in _gm.entities) == 1


def test_spawn_places_each_expert_in_their_guild_building():
    _cases = (
        ("salvage_specialist", "merchants", "tc_b", "merchants", "mer_q3_transport"),
        ("demolitions_expert", "militia", "eri_b", "militia", "mil_q4_demolitions"),
        ("xenolinguist", "lab", "ac_station", "lab", "lab_q4_xenolinguist"),
    )
    for _npc_id, _label, _planet, _chain, _step_id in _cases:
        _gm = load_planet(_planet)
        _act0.spawn_quest_npcs(
            _ctx(_chain, {_step_id: "active"}), _gm, _planet,
        )
        _found = [_e for _e in _gm.entities if _e.npc_id == _npc_id]
        assert len(_found) == 1, _npc_id
        assert _found[0].pos == _building_spot(_planet, _label), _npc_id


def test_quest_npc_never_shares_a_tile_with_the_building_occupant():
    """Regression: the additive NPC must not be buried under the
    building's regular occupant (both used to stand at the interior
    center, making the quest NPC untalkable)."""
    _cases = (
        ("old_smuggler", "barnards_b", "bar", "bar", "bar_q2_proof"),
        ("salvage_specialist", "tc_b", "merchants", "merchants", "mer_q3_transport"),
        ("demolitions_expert", "eri_b", "militia", "militia", "mil_q4_demolitions"),
        ("xenolinguist", "ac_station", "lab", "lab", "lab_q4_xenolinguist"),
    )
    for _npc_id, _planet, _label, _chain, _step_id in _cases:
        _gm = load_planet(_planet)
        _act0.spawn_quest_npcs(
            _ctx(_chain, {_step_id: "active"}), _gm, _planet,
        )
        _quest = next(_e for _e in _gm.entities if _e.npc_id == _npc_id)
        _neighbors = [
            _e for _e in _gm.entities
            if _e is not _quest and _e.pos == _quest.pos
        ]
        assert not _neighbors, (
            f"{_npc_id} on {_planet} shares tile {_quest.pos} with "
            f"{[_n.name for _n in _neighbors]}"
        )


def test_spawn_does_not_add_npcs_on_planets_without_spots():
    _gm = load_planet("earth")
    _act0.spawn_quest_npcs(_ctx("bar", {"bar_q2_proof": "active"}), _gm, "earth")
    assert not any(_e.npc_id == "old_smuggler" for _e in _gm.entities)
