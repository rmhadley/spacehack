"""Compatibility contract for the mission package extraction."""
from __future__ import annotations

from src.spacehack import mission
from src.spacehack.mission import _helpers, _legacy, _models
from src.spacehack.saveload import delete_save, load_game, save_game
from .test_saveload import _build_test_ctx


_PUBLIC_SURFACE = (
    "ActiveMission",
    "MissionBoard",
    "MissionStatus",
    "MAX_ACTIVE_MISSIONS",
    "MissionSpec",
    "find_mission",
    "list_missions",
    "missions_offered_by",
    "try_accept_mission",
    "commit_accept_mission",
    "is_deliverable_at",
    "active_is_deliverable_at",
    "find_deliverable",
    "find_deliverable_missions",
    "release_mission_cargo",
    "abort_mission",
    "complete_mission",
    "board_key",
    "ensure_board",
    "find_board_for_mission",
    "mission_spec_from_dict",
    "board_offerings",
    "fill_empty_slots",
    "board_remove",
    "board_return_static",
    "refresh_all_boards",
    "system_display_name",
    "system_name_for_planet",
    "destination_system_name",
    "generate_delivery_mission",
    "generate_bounty_mission",
    "generate_bar_mission",
    "_planet_npc_ids",
    "_planet_to_system",
)


def test_mission_package_preserves_compatibility_surface():
    """Historical imports continue to resolve through the package API."""
    assert tuple(mission.__all__) == _PUBLIC_SURFACE
    assert all(hasattr(mission, name) for name in _PUBLIC_SURFACE)


def test_mission_runtime_models_have_one_shared_identity():
    """Save/load-facing runtime classes are not duplicated by the shim."""
    assert mission.ActiveMission is _models.ActiveMission
    assert mission.MissionBoard is _models.MissionBoard
    assert mission.MissionStatus is _models.MissionStatus
    assert mission.MAX_ACTIVE_MISSIONS == _models.MAX_ACTIVE_MISSIONS


def test_mission_helper_ownership_is_not_duplicated():
    """Extracted helper functions retain one package-wide identity."""
    assert mission._planet_to_system is _helpers._planet_to_system
    assert _legacy._planet_to_system is _helpers._planet_to_system


def test_board_key_preserves_legacy_and_city_scoped_forms():
    """Board keys remain compatible while separating same-NPC cities."""
    assert mission.board_key("guild_master") == "guild_master"
    assert mission.board_key("guild_master", "earth") == "guild_master@earth"
    assert mission.board_key("guild_master", "mars") != mission.board_key(
        "guild_master", "earth",
    )


def test_mission_spec_from_dict_reconstructs_known_fields_only():
    """Generated mission specs tolerate unknown or missing serialized keys."""
    restored = mission.mission_spec_from_dict({
        "id": "generated:test",
        "title": "Test contract",
        "description": "Carry a package.",
        "giver_npc_id": "guild_master",
        "mission_type": "bounty",
        "tier": 3,
        "reward_credits": 450,
        "target_system_id": "sol",
        "unknown_future_field": "ignored",
    })

    assert restored == mission.MissionSpec(
        id="generated:test",
        title="Test contract",
        description="Carry a package.",
        giver_npc_id="guild_master",
        mission_type="bounty",
        tier=3,
        reward_credits=450,
        target_system_id="sol",
    )
    assert not hasattr(restored, "unknown_future_field")


def test_mission_models_round_trip_through_save_load(monkeypatch, tmp_path):
    """Active missions and composite-key boards survive Continue intact."""
    monkeypatch.setattr(
        "src.spacehack.saveload._autosave_path",
        lambda: tmp_path / "autosave.json",
    )
    from src.spacehack.engine import RNG

    RNG.seed(901)
    ctx = _build_test_ctx()
    active = mission.ActiveMission(
        mission_id="proc_intercept_earth_sol_4_2",
        is_procedural=True,
        status=mission.MissionStatus.FAILED,
        title="Intercept: Test Hauler",
        required_cargo_size=7,
        delivery_target_npc_id="bar_owner",
        delivery_target_planet_id="earth",
        bounty_spawn_id="bounty:test",
        target_enemy_id="merchant_hauler",
        target_system_id="sol",
        bounty_target_name="Red Test",
        bounty_target_squad_size=2,
        bounty_target_loadout_pct=50,
        bounty_wingmate_enemy_id="pirate_scout",
        tier=2,
        heist_target_good_id="electronics",
        heist_good_secured=True,
        salvage_wreck_enemy_id="derelict_scout",
        salvage_layout_id="scout_a",
        salvage_wreck_spawn_id="wreck:test",
        is_smuggle=True,
        smuggle_good_id="fuel_cells",
        main_quest_step_id="bar_q2_proof",
        time_deadline=(8, 9, 2201),
        deadline_days=120,
        accept_day=44,
        reward_credits=900,
        reward_xp=80,
        early_bonus_pct=25,
    )
    board = mission.MissionBoard(
        npc_id="bar_owner",
        slots=["m_static", active.mission_id, None],
        max_slots=3,
        last_refresh_month=8,
        planet_id="earth",
    )
    ctx.player_active_missions = [active]
    ctx.mission_boards = {mission.board_key("bar_owner", "earth"): board}

    save_game(ctx, mode="city", city_id="earth", system_id="sol")
    loaded = load_game(ctx.context)

    assert loaded is not None
    restored = loaded.player_active_missions[0]
    assert type(restored) is mission.ActiveMission
    assert restored.status is mission.MissionStatus.FAILED
    assert restored == active
    key = mission.board_key("bar_owner", "earth")
    assert key in loaded.mission_boards
    restored_board = loaded.mission_boards[key]
    assert type(restored_board) is mission.MissionBoard
    assert restored_board == board
    delete_save()
