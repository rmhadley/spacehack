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

from src.spacehack.data.main_quest import (
    find_main_quest_step,
    list_main_quest_steps,
)
from src.spacehack.data.npcs import find_npc
from src.spacehack.data.planets import list_planet_specs, load_planet
from src.spacehack.main_quest import _act0


def _ctx(chain: str, progress: dict, city: str = ""):
    return SimpleNamespace(
        main_quest_chain=chain,
        main_quest_progress=progress,
        player_active_missions=[],
        current_city_id=city,  # interior seating keys off it
        log=SimpleNamespace(add=lambda *a, **k: None),
    )



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
    assert find_main_quest_step("mer_q5_alloy").npc_presence == ("salvage_specialist",)
    assert find_main_quest_step("mer_q6_survey").npc_presence == ("salvage_specialist",)
    assert find_main_quest_step("mer_q7_cutter").npc_presence == ()
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
        _ctx("merchants", {"mer_q5_alloy": "available"}), "tc_b",
    ) == ("salvage_specialist",)
    assert _act0._quest_npcs_for_planet(
        _ctx("merchants", {"mer_q6_survey": "active"}), "tc_b",
    ) == ("salvage_specialist",)
    assert _act0._quest_npcs_for_planet(
        _ctx("merchants", {
            "mer_q3_transport": "completed",
            "mer_q5_alloy": "completed",
            "mer_q6_survey": "completed",
            "mer_q7_cutter": "available",
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
# Interior seating (cities-rework model: NPCs stand INSIDE buildings)
# ---------------------------------------------------------------------------


def _interior_record(planet_id: str, label: str) -> dict:
    _gm = load_planet(planet_id)
    return (getattr(_gm, "city_buildings", {}) or {})[label]


def _seat(ctx, planet_id: str, label: str):
    from src.spacehack import city_landmarks

    _rec = _interior_record(planet_id, label)
    _asset = city_landmarks.load_city_interior(_rec["interior_layout_id"])
    _act0.seat_quest_npcs_in_interior(ctx, _asset.game_map, _rec)
    return _asset.game_map


def test_seat_places_smuggler_inside_the_bar_interior():
    _im = _seat(
        _ctx("bar", {"bar_q2_proof": "active"}, city="barnards_b"), "barnards_b", "bar",
    )
    _smugglers = [_e for _e in _im.entities if _e.npc_id == "old_smuggler"]
    assert len(_smugglers) == 1
    assert _im.tiles[_smugglers[0].pos.y][_smugglers[0].pos.x].walkable


def test_seating_is_idempotent_on_cached_interiors():
    _ctx_ = _ctx("bar", {"bar_q2_proof": "active"}, city="barnards_b")
    _im = _seat(_ctx_, "barnards_b", "bar")
    _act0.seat_quest_npcs_in_interior(
        _ctx_, _im, _interior_record("barnards_b", "bar"),
    )
    assert sum(_e.npc_id == "old_smuggler" for _e in _im.entities) == 1


def test_seat_places_each_expert_in_their_guild_interior():
    _cases = (
        ("salvage_specialist", "tc_b", "merchants", "merchants", "mer_q3_transport"),
        ("demolitions_expert", "eri_b", "militia", "militia", "mil_q4_demolitions"),
        ("xenolinguist", "ac_station", "lab", "lab", "lab_q4_xenolinguist"),
        ("old_smuggler", "ross_b", "bar", "bar", "bar_q2_proof"),
    )
    for _npc_id, _planet, _label, _chain, _step_id in _cases:
        _im = _seat(_ctx(_chain, {_step_id: "active"}, city=_planet), _planet, _label)
        _found = [_e for _e in _im.entities if _e.npc_id == _npc_id]
        assert len(_found) == 1, _npc_id
        assert _im.tiles[_found[0].pos.y][_found[0].pos.x].walkable, _npc_id


def test_quest_npc_never_shares_a_tile_with_the_resident():
    """Regression (v12): quest NPCs used to spawn on the CITY map at
    the building rectangle center — mid-roof, unreachable since the
    cities rework. They now stand inside the interior, on a clear
    cell beside the resident."""
    _cases = (
        ("old_smuggler", "barnards_b", "bar", "bar", "bar_q2_proof"),
        ("salvage_specialist", "tc_b", "merchants", "merchants", "mer_q3_transport"),
    )
    for _npc_id, _planet, _label, _chain, _step_id in _cases:
        _im = _seat(_ctx(_chain, {_step_id: "active"}, city=_planet), _planet, _label)
        _quest = next(_e for _e in _im.entities if _e.npc_id == _npc_id)
        _neighbors = [
            _e for _e in _im.entities
            if _e is not _quest and _e.pos == _quest.pos
        ]
        assert not _neighbors, (
            f"{_npc_id} on {_planet} shares tile {_quest.pos} with "
            f"{[_n.name for _n in _neighbors]}"
        )


def test_seat_skips_interiors_whose_building_is_not_tagged():
    """A bar-chain NPC is not seated in the merchants interior."""
    _im = _seat(
        _ctx("bar", {"bar_q2_proof": "active"}, city="tc_b"), "tc_b", "merchants",
    )
    assert not any(_e.npc_id == "old_smuggler" for _e in _im.entities)
