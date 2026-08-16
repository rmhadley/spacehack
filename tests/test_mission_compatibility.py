"""Compatibility contract for the mission package extraction."""
from __future__ import annotations

from types import SimpleNamespace
import random

from src.spacehack import mission
from src.spacehack.mission import _helpers, _models
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


def test_faction_trait_shifts_mission_tier_band_and_caps_at_t4():
    """Career traits raise only their own faction's board tier band."""
    from src.spacehack.mission import _board

    assert _board._faction_tier_band(
        SimpleNamespace(player_traits=["hauler"]), "merchants", 1,
    ) == (2, 2)
    assert _board._faction_tier_band(
        SimpleNamespace(player_traits=["hauler"]), "merchants", 3,
    ) == (2, 4)
    assert _board._faction_tier_band(
        SimpleNamespace(player_traits=["hauler"]), "merchants", 4,
    ) == (2, 4)
    assert _board._faction_tier_band(
        SimpleNamespace(player_traits=["hauler"]), "bar", 1,
    ) == (1, 1)


def test_faction_trait_replaces_existing_t1_board_missions(monkeypatch):
    """An earned career trait removes stale T1 slots and generates T2 work."""
    from src.spacehack.mission import _board

    generated = {}
    board = mission.MissionBoard(
        npc_id="guild_master",
        slots=["old_t1", None],
        max_slots=2,
        planet_id="earth",
    )
    generated["old_t1"] = mission.MissionSpec(
        id="old_t1", title="Old", description="", giver_npc_id="guild_master", tier=1,
    )
    seen = {}

    def _generator(**kwargs):
        seen.update(kwargs)
        return mission.MissionSpec(
            id=f"new_t2_{kwargs['counter']}", title="New", description="",
            giver_npc_id="guild_master", faction="merchants", tier=2,
        )

    ctx = SimpleNamespace(
        player_traits=["hauler"],
        faction_reputation={},
        generated_missions=generated,
    )
    monkeypatch.setattr(_board, "_board_guild", lambda _npc_id: "merchants")
    monkeypatch.setattr(_board, "_tutorial_live", lambda _ctx: False)
    monkeypatch.setattr(_board, "missions_offered_by", lambda *_args, **_kwargs: ())
    monkeypatch.setattr(
        _board, "_procedural_generators", lambda: {"merchants": _generator},
    )

    _board.fill_empty_slots(
        board, planet_tier=1, completed_ids=frozenset(),
        active_ids=frozenset(), planet_id="earth", generated=generated,
        rng=random.Random(1), ctx=ctx,
    )

    assert board.slots == ["new_t2_0", "new_t2_1"]
    assert seen["max_tier"] == 2


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


def test_mission_package_implementation_modules_are_directly_usable():
    """The package surface does not depend on the retired legacy shim."""
    from src.spacehack.mission import _board, _proc_bar, _proc_bounty, _proc_delivery

    assert mission.generate_delivery_mission is _proc_delivery.generate_delivery_mission
    assert mission.generate_bounty_mission is _proc_bounty.generate_bounty_mission
    assert mission.generate_bar_mission is _proc_bar.generate_bar_mission
    assert _board._procedural_generators()["merchants"] is _proc_delivery.generate_delivery_mission


def test_mission_helper_ownership_is_not_duplicated():
    """Extracted helper functions retain one package-wide identity."""
    from src.spacehack.mission import _proc_shared

    assert mission._planet_to_system is _helpers._planet_to_system
    assert mission._planet_to_system is _proc_shared._planet_to_system


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


def test_complete_mission_records_faction_career_counter_before_xp(
    monkeypatch,
):
    """Bar, merchant, and bounty progress use explicit mission factions."""
    from src.spacehack import game_context
    from src.spacehack.mission import _lifecycle

    active = mission.ActiveMission(
        mission_id="proc_bar_test", is_procedural=True, title="Bar job",
    )
    spec = mission.MissionSpec(
        id="proc_bar_test", title="Bar job", description="", giver_npc_id="bar_owner",
        faction="bar", mission_type="salvage", tier=2,
    )
    messages = []
    ctx = SimpleNamespace(
        generated_missions={spec.id: spec},
        player_counters=game_context.PlayerCounters(),
        log=SimpleNamespace(add=messages.append),
        faction_reputation={},
    )
    monkeypatch.setattr(_lifecycle, "_apply_mission_rep", lambda *args, **kwargs: None)

    mission.complete_mission(
        active, None, SimpleNamespace(credits=0),
        SimpleNamespace(add=messages.append), ctx=ctx,
    )

    assert ctx.player_counters.bar_missions_completed == 1
    assert ctx.player_counters.merchant_missions_completed == 0
    assert ctx.player_counters.bounty_missions_completed == 0


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


def test_proc_delivery_target_npcs_resolve_through_planet_overrides():
    """Building slot keys must never leak into delivery targets.

    Regression: ``ac_station``'s archive building carries the slot id
    ``archive_research_officer``, which resolves through
    ``npc_overrides`` to the real spec id ``research_officer``. The
    old ``_planet_npc_ids`` returned the raw slot id, so a procedural
    delivery could target an NPC that never exists on the map — cargo
    reserved forever, mission uncompletable.
    """
    from src.spacehack.data.npcs import find_npc
    from src.spacehack.mission import _planet_npc_ids

    ids = _planet_npc_ids("ac_station")
    assert "archive_research_officer" not in ids
    assert "research_officer" in ids
    assert "xenolinguist" in ids
    # Every returned id is a real catalog NPC id.
    for _nid in ids:
        assert find_npc(_nid).id == _nid

    # Any proc delivery generated from Earth must carry a resolvable
    # target NPC regardless of which planet/seed the RNG picks.
    for _seed in range(40):
        _m = mission.generate_delivery_mission(
            "earth", max_tier=4, rng=random.Random(_seed),
        )
        assert _m is not None
        assert find_npc(_m.delivery_target_npc_id).id == _m.delivery_target_npc_id


def test_stale_slot_id_delivery_target_still_completes():
    """Missions accepted before the resolver fix keep working.

    The live save regression: ``proc_delivery_earth_ac_station_1_1``
    stores ``delivery_target_npc_id="archive_research_officer"`` on
    planet ``ac_station``. It must complete at the Research Officer
    (spec id ``research_officer``), and only there.
    """
    stale = mission.ActiveMission(
        mission_id="proc_delivery_earth_ac_station_1_1",
        is_procedural=True,
        title="Deliver to Science Port",
        required_cargo_size=5,
        delivery_target_npc_id="archive_research_officer",
        delivery_target_planet_id="ac_station",
    )
    assert mission.active_is_deliverable_at(
        stale, "research_officer", "ac_station",
    )
    # Still requires the right planet + the resolved NPC.
    assert not mission.active_is_deliverable_at(
        stale, "research_officer", "earth",
    )
    assert not mission.active_is_deliverable_at(
        stale, "xenolinguist", "ac_station",
    )

    # The same tolerance holds on MissionSpec-level predicates.
    spec = mission.MissionSpec(
        id="stale_spec", title="Stale", description="", giver_npc_id="barkeep",
        delivery_target_npc_id="archive_research_officer",
        delivery_target_planet_id="ac_station",
        required_cargo_size=5,
    )
    assert mission.is_deliverable_at(spec, "research_officer", "ac_station")
