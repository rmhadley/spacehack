"""Compatibility contract for the mission package extraction."""
from __future__ import annotations

from types import SimpleNamespace

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


def test_mission_lifecycle_ownership_is_not_duplicated():
    """Lifecycle functions have one implementation behind both shims."""
    from src.spacehack.mission import _lifecycle

    for name in (
        "try_accept_mission",
        "commit_accept_mission",
        "release_mission_cargo",
        "abort_mission",
        "complete_mission",
    ):
        assert getattr(mission, name) is getattr(_lifecycle, name)
        assert getattr(_legacy, name) is getattr(_lifecycle, name)


def test_accept_validation_does_not_mutate_then_commit_reserves_cargo():
    """Acceptance checks stay read-only until the explicit commit step."""
    from src.spacehack.ship import OwnedShip

    spec = mission.MissionSpec(
        id="test_delivery",
        title="Test delivery",
        description="Carry a test crate.",
        giver_npc_id="guild_master",
        required_cargo_size=5,
    )
    owned = OwnedShip(ship_id="starter")
    messages: list[str] = []
    log = SimpleNamespace(add=messages.append)

    assert mission.try_accept_mission(spec, owned, log) is True
    assert owned.mission_reserved == 0

    mission.commit_accept_mission(spec, owned, log)
    assert owned.mission_reserved == 5
    assert messages[-1].startswith("You accept: Test delivery.")


def test_release_and_abort_include_secured_intercept_cargo():
    """Abort releases both delivery reservation and secured heist volume."""
    from src.spacehack.data.trade_goods import find_trade_good
    from src.spacehack.mission import MissionStatus
    from src.spacehack.ship import OwnedShip, effective_max_cargo
    from src.spacehack.data.ships import find_ship

    active = mission.ActiveMission(
        mission_id="proc_intercept_test",
        status=MissionStatus.IN_PROGRESS,
        title="Test intercept",
        required_cargo_size=4,
        heist_target_good_id="electronics",
        heist_good_secured=True,
    )
    owned = OwnedShip(ship_id="starter", mission_reserved=100)
    expected = active.required_cargo_size + find_trade_good("electronics").volume
    messages: list[str] = []

    mission.abort_mission(active, owned, SimpleNamespace(add=messages.append))

    assert owned.mission_reserved == 100 - expected
    capacity = effective_max_cargo(find_ship(owned.ship_id), owned)
    assert messages == [
        f"Cargo released from abandoned 'Test intercept' "
        f"({owned.cargo_used}/{capacity}).",
    ]


def test_complete_mission_applies_early_bonus_and_releases_cargo():
    """Early completion pays the configured bonus and clears reservations."""
    from src.spacehack.ship import OwnedShip

    active = mission.ActiveMission(
        mission_id="test_delivery",
        title="Early delivery",
        required_cargo_size=3,
        reward_credits=100,
        reward_xp=20,
        deadline_days=10,
        accept_day=1,
        early_bonus_pct=25,
    )
    owned = OwnedShip(ship_id="starter", mission_reserved=3)
    stats = SimpleNamespace(credits=0)
    messages: list[str] = []

    mission.complete_mission(
        active, owned, stats, SimpleNamespace(add=messages.append),
        current_day=3,
    )

    assert stats.credits == 125
    assert owned.mission_reserved == 0
    assert "+20xp" in messages[-1]
    assert "Early delivery bonus: +25$." in messages[-1]


def test_complete_mission_applies_late_penalty_and_zero_xp():
    """Late completion halves credits and awards no XP."""
    from src.spacehack.ship import OwnedShip

    active = mission.ActiveMission(
        mission_id="test_delivery",
        title="Late delivery",
        reward_credits=101,
        reward_xp=20,
        deadline_days=10,
        accept_day=1,
    )
    stats = SimpleNamespace(credits=7)
    messages: list[str] = []

    mission.complete_mission(
        active, OwnedShip(ship_id="starter"), stats,
        SimpleNamespace(add=messages.append), current_day=20,
    )

    assert stats.credits == 57
    assert "+0xp" in messages[-1]
    assert "Late delivery - half pay." in messages[-1]


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
