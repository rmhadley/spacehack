"""Tests for saveload.py — save/load round-trip integrity.

The save/load contract is explicitly called out in knowledge.md as
"not checked by the smoke test." A round-trip test builds a
GameContext with known state, saves it, loads it back, and asserts
every serialized field survived.
"""

from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import MagicMock
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.spacehack.game_context import GameContext, DungeonExtensionState
from src.spacehack.hud import HudStats
from src.spacehack.message_log import MessageLog
from src.spacehack.world import GameMap, Entity, Position
from src.spacehack import world
from src.spacehack.saveload import save_game, load_game, delete_save
from src.spacehack import dungeon_extensions
from src.spacehack.ship import OwnedShip, StoredEquipment
from src.spacehack.ground_equipment import (
    GroundItemStack,
    GroundWeaponInstance,
    StoredGroundEquipment,
)


def _build_test_ctx() -> GameContext:
    """Build a minimal GameContext with known state for round-trip testing."""
    mock_ctx = MagicMock()
    gm = GameMap(width=10, height=10, tiles=[], entities=[])
    player = Entity(char="@", fg=(255, 255, 255), pos=Position(5, 5), name="Player")
    gm.entities.append(player)
    stats = HudStats(hp=30, max_hp=30, credits=100)
    log = MessageLog(capacity=6)
    log.add("Run started.")
    log.add_colored("A hostile signal appears.", (255, 70, 70))
    ci = {
        "species_id": "human",
        "species_name": "Human",
        "class_id": "pirate",
        "class_name": "Pirate",
    }
    ctx = GameContext(
        context=mock_ctx,
        character_info=ci,
        log=log,
        game_map=gm,
        player=player,
        stats=stats,
    )
    # Set non-default fields with known values.
    ctx.faction_reputation = {"pirate": -50, "merchant": 25}
    ctx.player_xp = 500
    ctx.player_level = 4
    ctx.player_skill_points = 3
    ctx.player_gunnery_bonus = 10
    ctx.player_piloting_bonus = 5
    ctx.player_engineering_bonus = 0
    ctx.player_traits = ["sharpshooter"]
    ctx.time_day = 15
    ctx.time_month = 6
    ctx.time_year = 2201
    ctx.move_counter = 7
    ctx.ground_hp = 28
    ctx.ground_max_hp = 30
    ctx.player_counters.total_kills = 12
    ctx.player_counters.bounties_completed = 3
    ctx.player_counters.merchant_missions_completed = 11
    ctx.player_counters.bar_missions_completed = 12
    ctx.player_counters.bounty_missions_completed = 13
    ctx.player_counters.melee_kills = 7
    ctx.completed_mission_ids = {"m_test_1", "m_test_2"}
    ctx.economy_state = {"earth": {"food": 5, "water": 3}}
    ctx.militia_scanned = {"patrol_1"}
    ctx.main_quest_disclosure = "archive_sealed"
    ctx.post_prison_orbit_seen = True
    ctx.post_prison_orbit_pending = True
    ctx.main_quest_chain = "lab"
    ctx.main_quest_gate = {"research_alpha": (1, 3, 2200)}
    ctx.main_quest_pending_message = "The archive comparison is ready."
    ctx.main_quest_pending_objective = "Report to Alpha Centauri's Science Port."
    # Tutorial state (design doc 14) — non-default so the round-trip
    # proves the fields survive a save/continue cycle.
    ctx.tutorial_mode = True
    ctx.tutorial_steps = {"intro", "accepted_crimson"}
    ctx.tutorial_complete = False
    ctx.dungeon_extension = DungeonExtensionState(
        extension_id="mars_alien_prison",
        current_floor=1,
        active=True,
        parent_map_key="surface:mars",
        parent_position=Position(4, 4),
        activated_events={"security_alpha", "__entry_flavor__:floor:1"},
        event_positions={"security_alpha": [7, 8]},
    )
    return ctx


class TestSaveLoadRoundTrip:
    """Build → save → load → assert field-level equality."""

    def test_round_trip_city_mode(self, monkeypatch, tmp_path):
        """City-mode save/load preserves all serialized fields."""
        # Redirect saves to a temp directory so the test doesn't touch
        # the user's real autosave.
        monkeypatch.setattr(
            "src.spacehack.saveload._autosave_path",
            lambda: tmp_path / "autosave.json",
        )

        # Seed RNG so getstate()/setstate() don't fail on uninitialised RNG.
        from src.spacehack.engine import RNG
        RNG.seed(42)

        ctx = _build_test_ctx()

        # Save in city mode (Earth).
        save_game(ctx, mode="city", city_id="earth", system_id="sol")

        # Load back — needs the same mock context type.
        loaded = load_game(ctx.context)

        assert loaded is not None, "load_game returned None"
        self._assert_fields_match(ctx, loaded)

        # Clean up.
        delete_save()
        # Reset module-level global set by load_game.
        import src.spacehack.solar_system as _ss
        _ss.current_solar_system_id = "sol"

    def test_init_seed_survives_round_trip(self, monkeypatch, tmp_path):
        """The run's initial seed persists so month-keyed stock stays consistent."""
        monkeypatch.setattr(
            "src.spacehack.saveload._autosave_path",
            lambda: tmp_path / "autosave.json",
        )
        from src.spacehack import engine
        engine.seed_rng(12345)

        ctx = _build_test_ctx()
        save_game(ctx, mode="city", city_id="earth", system_id="sol")

        # Simulate a fresh process with a different seed, then Continue.
        engine.seed_rng(99999)
        loaded = load_game(ctx.context)

        assert loaded is not None
        assert engine.INIT_SEED == 12345
        delete_save()
        import src.spacehack.solar_system as _ss
        _ss.current_solar_system_id = "sol"

    # ---- field-level assertions ----

    def _assert_fields_match(self, original: GameContext, loaded: GameContext) -> None:
        """Compare every field that goes through save/load."""
        # Character info
        assert loaded.character_info == original.character_info

        # Full console history, including colored entries
        assert [entry.text for entry in loaded.log.history()] == [
            entry.text for entry in original.log.history()
        ] + ["Game loaded."]
        assert loaded.log.history()[-2].fg == (255, 70, 70)

        # Stats
        assert loaded.stats.hp == original.stats.hp
        assert loaded.stats.max_hp == original.stats.max_hp
        assert loaded.stats.credits == original.stats.credits

        # Faction rep
        assert loaded.faction_reputation == original.faction_reputation

        # XP / leveling
        assert loaded.player_xp == original.player_xp
        assert loaded.player_level == original.player_level
        assert loaded.player_skill_points == original.player_skill_points
        assert loaded.player_gunnery_bonus == original.player_gunnery_bonus
        assert loaded.player_piloting_bonus == original.player_piloting_bonus
        assert loaded.player_engineering_bonus == original.player_engineering_bonus
        assert loaded.player_traits == original.player_traits

        # Player counters
        assert loaded.player_counters.total_kills == original.player_counters.total_kills
        assert loaded.player_counters.bounties_completed == original.player_counters.bounties_completed
        assert loaded.player_counters.merchant_missions_completed == original.player_counters.merchant_missions_completed
        assert loaded.player_counters.bar_missions_completed == original.player_counters.bar_missions_completed
        assert loaded.player_counters.bounty_missions_completed == original.player_counters.bounty_missions_completed
        assert loaded.player_counters.melee_kills == original.player_counters.melee_kills

        # Game time
        assert loaded.time_day == original.time_day
        assert loaded.time_month == original.time_month
        assert loaded.time_year == original.time_year
        assert loaded.move_counter == original.move_counter

        # Ground combat
        assert loaded.ground_hp == original.ground_hp
        assert loaded.ground_max_hp == original.ground_max_hp

        # Missions
        assert loaded.completed_mission_ids == original.completed_mission_ids

        # Post-prison Act 1 orbit disclosure and sandbox gate
        assert loaded.main_quest_disclosure == original.main_quest_disclosure
        assert loaded.post_prison_orbit_seen == original.post_prison_orbit_seen
        assert loaded.post_prison_orbit_pending == original.post_prison_orbit_pending
        assert loaded.main_quest_chain == original.main_quest_chain
        assert loaded.main_quest_gate == original.main_quest_gate
        assert loaded.main_quest_pending_message == original.main_quest_pending_message
        assert loaded.main_quest_pending_objective == original.main_quest_pending_objective

        # Economy
        assert loaded.economy_state == original.economy_state

        # Militia
        assert loaded.militia_scanned == original.militia_scanned

        # Tutorial mode
        assert loaded.tutorial_mode == original.tutorial_mode
        assert loaded.tutorial_steps == original.tutorial_steps
        assert loaded.tutorial_complete == original.tutorial_complete

        # Themed dungeon extension state
        assert loaded.dungeon_extension == original.dungeon_extension
        assert "__entry_flavor__:floor:1" in loaded.dungeon_extension.activated_events

        # OwnedShip — default None for a new character
        assert loaded.player_owned_ship is None

        # Active missions — default empty
        assert loaded.player_active_missions == []

    def test_quicksave_round_trip_is_independent_of_autosave(
        self, monkeypatch, tmp_path,
    ):
        """Dev quicksave/quickload round-trips and never touches the autosave."""
        from src.spacehack.dev_mode import quick_load, quick_save

        monkeypatch.setattr(
            "src.spacehack.saveload._autosave_path",
            lambda: tmp_path / "autosave.json",
        )
        monkeypatch.setattr(
            "src.spacehack.dev_mode._quicksave_path",
            lambda: tmp_path / "quicksave.json",
        )
        from src.spacehack.engine import RNG
        RNG.seed(42)

        # No checkpoint yet -> quick_load returns None, not a crash.
        assert quick_load(MagicMock()) is None

        ctx = _build_test_ctx()
        quick_save(ctx, mode="city", city_id="earth", system_id="sol")

        # Quicksave is a separate file — the autosave stays untouched.
        assert not (tmp_path / "autosave.json").exists()
        assert (tmp_path / "quicksave.json").exists()

        loaded = quick_load(ctx.context)
        assert loaded is not None
        self._assert_fields_match(ctx, loaded)

        # Reusable checkpoint: loading does not delete the file, and a
        # second save overwrites it in place.
        assert (tmp_path / "quicksave.json").exists()
        quick_save(ctx, mode="city", city_id="earth", system_id="sol")
        assert (tmp_path / "quicksave.json").exists()

        (tmp_path / "quicksave.json").unlink()
        import src.spacehack.solar_system as _ss
        _ss.current_solar_system_id = "sol"

    def test_legacy_save_without_extension_state_loads(self, monkeypatch, tmp_path):
        """Pre-extension saves load with no active extension state."""
        monkeypatch.setattr(
            "src.spacehack.saveload._autosave_path",
            lambda: tmp_path / "autosave.json",
        )
        from src.spacehack.engine import RNG
        RNG.seed(42)
        ctx = _build_test_ctx()
        save_game(ctx, mode="city", city_id="earth", system_id="sol")
        import json
        path = tmp_path / "autosave.json"
        payload = json.loads(path.read_text())
        payload.pop("dungeon_extension", None)
        for _field in (
            "main_quest_chain",
            "main_quest_gate",
            "main_quest_pending_message",
            "main_quest_pending_objective",
            "main_quest_disclosure",
            "post_prison_orbit_seen",
            "post_prison_orbit_pending",
        ):
            payload.pop(_field, None)
        path.write_text(json.dumps(payload))

        loaded = load_game(ctx.context)

        assert loaded is not None
        assert loaded.dungeon_extension is None
        assert loaded.main_quest_chain == ""
        assert loaded.main_quest_gate == {}
        assert loaded.main_quest_pending_message == ""
        assert loaded.main_quest_pending_objective == ""
        assert loaded.main_quest_disclosure == ""
        assert not loaded.post_prison_orbit_seen
        assert not loaded.post_prison_orbit_pending
        delete_save()

    def test_active_extension_round_trip_restores_floor_cache_and_parent(
        self, monkeypatch, tmp_path,
    ):
        """Continue inside Floor 1 preserves the active floor and Mars return."""
        monkeypatch.setattr(
            "src.spacehack.saveload._autosave_path",
            lambda: tmp_path / "autosave.json",
        )
        from src.spacehack.engine import RNG
        RNG.seed(43)
        ctx = _build_test_ctx()
        parent_tiles = [
            [world.DUNGEON_FLOOR for _ in range(12)] for _ in range(12)
        ]
        parent_map = GameMap(12, 12, parent_tiles, [])
        parent_position = Position(4, 5)
        extension_map, extension_player = dungeon_extensions.enter_extension(
            SimpleNamespace(
                interiors={"surface:mars": parent_map},
                dungeon_extension=None,
                game_map=parent_map,
                player=Entity("@", (255, 255, 255), parent_position, "Player"),
                current_city_id="mars",
                log=ctx.log,
            ),
            parent_map,
            Entity("@", (255, 255, 255), parent_position, "Player"),
            extension_id="mars_alien_prison",
            parent_map_key="surface:mars",
        )
        # Reuse the state created by enter_extension on a real GameContext.
        ctx.game_map = extension_map
        ctx.player = extension_player
        ctx.interiors = {
            "surface:mars": parent_map,
            dungeon_extensions.floor_key("mars_alien_prison", 1): extension_map,
        }
        ctx.dungeon_extension = DungeonExtensionState(
            extension_id="mars_alien_prison",
            current_floor=1,
            active=True,
            parent_map_key="surface:mars",
            parent_position=parent_position,
            activated_events={"security_alpha", "__entry_flavor__:floor:1"},
            event_positions={"security_alpha": [7, 8]},
        )

        save_game(
            ctx,
            mode="dungeon",
            city_id="mars",
            system_id="sol",
            space_player_pos=(3, 4),
        )
        loaded = load_game(ctx.context)

        assert loaded is not None
        assert loaded.dungeon_extension == ctx.dungeon_extension
        assert loaded.dungeon_extension.active
        assert not loaded.dungeon_extension.power_restored
        floor_key = dungeon_extensions.floor_key("mars_alien_prison", 1)
        assert loaded.interiors[floor_key] is loaded.game_map
        assert loaded.interiors["surface:mars"].width == 12
        assert loaded.dungeon_extension.parent_position == parent_position
        assert loaded.dungeon_extension.activated_events == {
            "security_alpha", "__entry_flavor__:floor:1",
        }

        shown = []
        monkeypatch.setattr(
            "src.spacehack.main_quest.show_gate_popup",
            lambda *args, **kwargs: shown.append((args, kwargs)),
        )
        restored_parent = loaded.interiors["surface:mars"]
        restored_parent_player = Entity(
            "@", (255, 255, 255), parent_position, "Player",
        )
        dungeon_extensions.enter_extension(
            loaded,
            restored_parent,
            restored_parent_player,
            extension_id="mars_alien_prison",
            parent_map_key="surface:mars",
        )
        assert not shown

        delete_save()

    def test_loaded_surface_dungeon_reuses_active_map_for_extension_entry(
        self, monkeypatch, tmp_path,
    ):
        """Continue on Mars keeps the surface cache linked to the active map."""
        monkeypatch.setattr(
            "src.spacehack.saveload._autosave_path",
            lambda: tmp_path / "autosave.json",
        )
        from src.spacehack.engine import RNG
        RNG.seed(45)
        ctx = _build_test_ctx()
        parent_map = GameMap(
            12, 12,
            [[world.DUNGEON_FLOOR for _ in range(12)] for _ in range(12)],
            [],
        )
        stairs = Position(6, 6)
        parent_map.tiles[stairs.y][stairs.x] = world.STAIRS_DOWN
        parent_map.extension_entry_id = "mars_alien_prison"
        parent_map.mars_stairs_pos = stairs
        parent_player = Entity("@", (255, 255, 255), stairs, "Player")
        parent_map.entities.append(parent_player)
        ctx.game_map = parent_map
        ctx.player = parent_player
        ctx.interiors = {"surface:mars": parent_map}
        ctx.dungeon_extension.active = False
        ctx.dungeon_extension.current_floor = 1

        save_game(
            ctx,
            mode="dungeon",
            city_id="mars",
            system_id="sol",
            space_player_pos=(3, 4),
        )
        loaded = load_game(ctx.context)

        assert loaded is not None
        assert loaded.interiors["surface:mars"] is loaded.game_map
        assert getattr(loaded.game_map, "interior_cache_key", "") == ""
        monkeypatch.setattr(
            "src.spacehack.main_quest.show_gate_popup",
            lambda *args, **kwargs: None,
        )
        extension_map, _ = dungeon_extensions.enter_extension(
            loaded,
            loaded.game_map,
            loaded.player,
            extension_id="mars_alien_prison",
        )
        assert extension_map.extension_floor == 1
        assert loaded.dungeon_extension.active

        delete_save()

    def test_derelict_round_trip_does_not_rebind_surface_cache(
        self, monkeypatch, tmp_path,
    ):
        """A non-extension dungeon save cannot masquerade as a surface cache."""
        monkeypatch.setattr(
            "src.spacehack.saveload._autosave_path",
            lambda: tmp_path / "autosave.json",
        )
        from src.spacehack.engine import RNG
        RNG.seed(46)
        ctx = _build_test_ctx()
        surface_map = GameMap(
            12, 12,
            [[world.DUNGEON_FLOOR for _ in range(12)] for _ in range(12)],
            [],
        )
        surface_map.interior_cache_key = "surface:mars"
        wreck_map = GameMap(
            8, 8,
            [[world.DUNGEON_FLOOR for _ in range(8)] for _ in range(8)],
            [],
        )
        wreck_map.wreck_spawn_id = "wreck:test"
        wreck_map.entry_spawn = Position(2, 2)
        wreck_map.interior_cache_key = "wreck:test"
        wreck_player = Entity("@", (255, 255, 255), Position(2, 2), "Player")
        wreck_map.entities.append(wreck_player)
        ctx.game_map = wreck_map
        ctx.player = wreck_player
        ctx.interiors = {
            "surface:mars": surface_map,
            "wreck:test": wreck_map,
        }

        save_game(
            ctx,
            mode="dungeon",
            city_id="mars",
            system_id="sol",
            space_player_pos=(3, 4),
        )
        loaded = load_game(ctx.context)

        assert loaded is not None
        assert loaded.interiors["surface:mars"] is not loaded.game_map
        assert loaded.interiors["wreck:test"] is loaded.game_map
        delete_save()

    def test_extraction_and_partial_ascent_round_trip(self, monkeypatch, tmp_path):
        """Continue preserves extraction state and already-fired ascent events."""
        monkeypatch.setattr(
            "src.spacehack.saveload._autosave_path",
            lambda: tmp_path / "autosave.json",
        )
        from src.spacehack.engine import RNG
        RNG.seed(47)
        ctx = _build_test_ctx()
        ctx.dungeon_extension.state_flags.add("prison_data_extracted")
        ctx.dungeon_extension.current_floor = 2
        ctx.dungeon_extension.activated_events = {
            "__entry_flavor__:floor:1",
            "prison_ascent_f2_assault",
        }
        ctx.dungeon_extension.active = True
        save_game(ctx, mode="city", city_id="mars", system_id="sol")

        loaded = load_game(ctx.context)

        assert loaded is not None
        assert "prison_data_extracted" in loaded.dungeon_extension.state_flags
        assert loaded.dungeon_extension.activated_events == {
            "__entry_flavor__:floor:1",
            "prison_ascent_f2_assault",
        }
        assert loaded.dungeon_extension.current_floor == 2
        delete_save()

    def test_loaded_ascent_map_keeps_completed_event_and_stages_next(
        self, monkeypatch, tmp_path,
    ):
        """An actual loaded prison floor resumes its staged ascent response."""
        monkeypatch.setattr(
            "src.spacehack.saveload._autosave_path",
            lambda: tmp_path / "autosave.json",
        )
        monkeypatch.setattr(
            "src.spacehack.main_quest.show_gate_popup",
            lambda *args, **kwargs: None,
        )
        from src.spacehack.engine import RNG
        RNG.seed(48)
        ctx = _build_test_ctx()
        ctx.context = None
        parent_map = GameMap(
            12, 12,
            [[world.DUNGEON_FLOOR for _ in range(12)] for _ in range(12)],
            [],
        )
        parent_player = Entity("@", (255, 255, 255), Position(4, 5), "Player")
        parent_map.entities.append(parent_player)
        ctx.game_map = parent_map
        ctx.player = parent_player
        ctx.interiors = {"surface:mars": parent_map}
        dungeon_extensions.enter_extension(
            ctx,
            parent_map,
            parent_player,
            extension_id="mars_alien_prison",
            parent_map_key="surface:mars",
        )
        floor_two, floor_two_player = dungeon_extensions.transition_floor(ctx, 1)
        ctx.dungeon_extension.activated_events.clear()
        ctx.dungeon_extension.state_flags.add("prison_data_extracted")
        floor_two_player.pos = floor_two.up_stair_pos
        assert dungeon_extensions.tick_activation(ctx)
        assert ctx.dungeon_extension.activated_events == {
            "prison_ascent_f2_assault",
        }
        _assault_count = sum(
            entity.npc_char_id == "assault_drone"
            for entity in floor_two.entities
        )

        save_game(
            ctx,
            mode="dungeon",
            city_id="mars",
            system_id="sol",
            space_player_pos=(3, 4),
        )
        loaded = load_game(ctx.context)

        assert loaded is not None
        assert loaded.dungeon_extension.activated_events == {
            "prison_ascent_f2_assault",
        }
        assert sum(
            entity.npc_char_id == "assault_drone"
            for entity in loaded.game_map.entities
        ) == _assault_count
        loaded.player.pos = loaded.game_map.up_stair_pos
        assert dungeon_extensions.tick_activation(loaded)
        assert loaded.dungeon_extension.activated_events == {
            "prison_ascent_f2_assault",
            "prison_ascent_f2_sentries",
        }
        assert sum(
            entity.npc_char_id == "sentry_drone"
            for entity in loaded.game_map.entities
        ) == 2
        assert not dungeon_extensions.tick_activation(loaded)
        delete_save()

    def test_phase_two_floor_round_trip_preserves_links_and_cache(
        self, monkeypatch, tmp_path,
    ):
        """Continue on Floor 2 preserves both visited floors and stair links."""
        monkeypatch.setattr(
            "src.spacehack.saveload._autosave_path",
            lambda: tmp_path / "autosave.json",
        )
        from src.spacehack.engine import RNG
        RNG.seed(44)
        ctx = _build_test_ctx()
        parent_map = GameMap(
            12, 12,
            [[world.DUNGEON_FLOOR for _ in range(12)] for _ in range(12)],
            [],
        )
        parent_player = Entity("@", (255, 255, 255), Position(4, 5), "Player")
        parent_map.entities.append(parent_player)
        ctx.interiors = {"surface:mars": parent_map}
        ctx.game_map = parent_map
        ctx.player = parent_player
        floor_one, _ = dungeon_extensions.enter_extension(
            ctx,
            parent_map,
            parent_player,
            extension_id="mars_alien_prison",
            parent_map_key="surface:mars",
        )
        floor_two, _ = dungeon_extensions.transition_floor(ctx, 1)

        save_game(
            ctx,
            mode="dungeon",
            city_id="mars",
            system_id="sol",
            space_player_pos=(3, 4),
        )
        loaded = load_game(ctx.context)

        assert loaded is not None
        assert loaded.dungeon_extension.current_floor == 2
        assert loaded.interiors[dungeon_extensions.floor_key(
            "mars_alien_prison", 1,
        )].extension_floor == 1
        loaded_floor_two = loaded.interiors[dungeon_extensions.floor_key(
            "mars_alien_prison", 2,
        )]
        assert loaded_floor_two is loaded.game_map
        assert loaded_floor_two.up_stair_pos == floor_two.up_stair_pos
        assert loaded_floor_two.down_stair_pos == floor_two.down_stair_pos
        assert loaded_floor_two.tiles[
            loaded_floor_two.down_stair_pos.y
        ][loaded_floor_two.down_stair_pos.x].kind == "stairs_down"
        assert sum(
            tile.kind == "prison_cell_door"
            for row in loaded_floor_two.tiles for tile in row
        ) == sum(
            tile.kind == "prison_cell_door"
            for row in floor_two.tiles for tile in row
        )
        assert floor_one is not floor_two

        dungeon_extensions.transition_floor(loaded, 1)
        dungeon_extensions.transition_floor(loaded, 1)
        assert loaded.dungeon_extension.current_floor == 4
        assert dungeon_extensions.restore_power(loaded)
        save_game(
            loaded,
            mode="dungeon",
            city_id="mars",
            system_id="sol",
            space_player_pos=(3, 4),
        )
        powered = load_game(ctx.context)
        assert powered is not None
        assert powered.dungeon_extension.power_restored
        assert "engineering_power" in powered.dungeon_extension.state_flags
        assert getattr(powered.game_map, "power_restored", False)

        delete_save()

    def test_round_trip_ship_storage(self, monkeypatch, tmp_path):
        """Storage preserves duplicate parts and partial missile ammo."""
        monkeypatch.setattr(
            "src.spacehack.saveload._autosave_path",
            lambda: tmp_path / "autosave.json",
        )
        from src.spacehack.engine import RNG
        RNG.seed(49)
        ctx = _build_test_ctx()
        ctx.player_owned_ship = OwnedShip(
            ship_id="scout",
            weapons=("light_laser",),
            modules=(),
        )
        ctx.ship_storage = [
            StoredEquipment("module", "shield_mk4"),
            StoredEquipment("module", "shield_mk4"),
            StoredEquipment("weapon", "light_missile", 2),
        ]

        save_game(ctx, mode="city", city_id="earth", system_id="sol")
        loaded = load_game(ctx.context)

        assert loaded is not None
        assert loaded.ship_storage == ctx.ship_storage
        assert loaded.player_owned_ship is not None
        assert loaded.player_owned_ship.weapons == ("light_laser",)
        delete_save()

    def test_ship_upgrade_transfer_round_trips_exactly(self, monkeypatch, tmp_path):
        """Equipment moved by an upgrade remains exact after Continue."""
        monkeypatch.setattr(
            "src.spacehack.saveload._autosave_path",
            lambda: tmp_path / "autosave.json",
        )
        from src.spacehack.engine import RNG
        from src.spacehack.ship import move_installed_equipment_to_storage
        RNG.seed(52)
        ctx = _build_test_ctx()
        ctx.player_owned_ship = OwnedShip(
            ship_id="starter",
            weapons=("light_missile", "light_laser"),
            modules=("shield_mk1", "shield_mk1"),
        )
        ctx.player_owned_ship.weapon_ammo[0] = 1
        move_installed_equipment_to_storage(
            ctx.player_owned_ship,
            ctx.ship_storage,
        )

        save_game(ctx, mode="city", city_id="earth", system_id="sol")
        loaded = load_game(ctx.context)

        assert loaded is not None
        assert loaded.player_owned_ship is not None
        assert loaded.player_owned_ship.weapons == ()
        assert loaded.player_owned_ship.modules == ()
        assert loaded.ship_storage == [
            StoredEquipment("weapon", "light_missile", 1),
            StoredEquipment("weapon", "light_laser"),
            StoredEquipment("module", "shield_mk1"),
            StoredEquipment("module", "shield_mk1"),
        ]
        delete_save()

    def test_malformed_ship_storage_entries_are_ignored(self, monkeypatch, tmp_path):
        """Malformed storage records do not prevent Continue."""
        monkeypatch.setattr(
            "src.spacehack.saveload._autosave_path",
            lambda: tmp_path / "autosave.json",
        )
        from src.spacehack.engine import RNG
        RNG.seed(51)
        ctx = _build_test_ctx()
        save_game(ctx, mode="city", city_id="earth", system_id="sol")
        import json
        path = tmp_path / "autosave.json"
        payload = json.loads(path.read_text())
        payload["ship_storage"] = [
            {"item_type": "module", "item_id": "shield_mk4"},
            {"item_type": "module", "item_id": "missing_module"},
            {"item_type": "unknown", "item_id": "shield_mk4"},
            {"item_type": "weapon", "item_id": "light_missile", "ammo": "bad"},
            {"item_type": "weapon", "item_id": "light_laser", "ammo": None},
            "not a record",
        ]
        path.write_text(json.dumps(payload))

        loaded = load_game(ctx.context)

        assert loaded is not None
        assert loaded.ship_storage == [
            StoredEquipment("module", "shield_mk4"),
            StoredEquipment("weapon", "light_laser"),
        ]
        delete_save()

    def test_legacy_save_without_ship_storage_loads_empty(self, monkeypatch, tmp_path):
        """Pre-storage saves load with an empty storage locker."""
        monkeypatch.setattr(
            "src.spacehack.saveload._autosave_path",
            lambda: tmp_path / "autosave.json",
        )
        from src.spacehack.engine import RNG
        RNG.seed(50)
        ctx = _build_test_ctx()
        save_game(ctx, mode="city", city_id="earth", system_id="sol")
        import json
        path = tmp_path / "autosave.json"
        payload = json.loads(path.read_text())
        payload.pop("ship_storage", None)
        path.write_text(json.dumps(payload))

        loaded = load_game(ctx.context)

        assert loaded is not None
        assert loaded.ship_storage == []
        delete_save()

    def test_dungeon_equipment_loot_data_round_trips(self, monkeypatch, tmp_path):
        """Uncollected ground gear remains identifiable after Continue."""
        monkeypatch.setattr(
            "src.spacehack.saveload._autosave_path",
            lambda: tmp_path / "autosave.json",
        )
        from src.spacehack.engine import RNG
        RNG.seed(57)
        ctx = _build_test_ctx()
        tiles = [[world.DUNGEON_FLOOR for _ in range(6)] for _ in range(6)]
        player = Entity("@", (255, 255, 255), Position(2, 2), "Player")
        loot = Entity(
            "%", (255, 215, 0), Position(3, 2), "Loot",
            loot_data={"item_type": "weapon", "item_id": "combat_knife"},
        )
        dungeon_map = GameMap(6, 6, tiles, [player, loot])
        dungeon_map.entry_spawn = Position(2, 2)
        dungeon_map.location_name = "Test Wreck"
        ctx.game_map = dungeon_map
        ctx.player = player
        ctx.ground_expedition_inventory = [
            StoredGroundEquipment("armor", "light_helmet"),
        ]

        save_game(
            ctx,
            mode="dungeon",
            city_id="earth",
            system_id="sol",
            space_player_pos=(4, 4),
        )
        loaded = load_game(ctx.context)

        assert loaded is not None
        restored_loot = next(
            entity for entity in loaded.game_map.entities
            if entity.loot_data is not None
        )
        assert restored_loot.loot_data == {
            "item_type": "weapon", "item_id": "combat_knife",
        }
        assert loaded.ground_expedition_inventory == [
            StoredGroundEquipment("armor", "light_helmet"),
        ]
        delete_save()

    def test_round_trip_ground_equipment_containers(self, monkeypatch, tmp_path):
        """Ground loadout and both storage containers survive Continue."""
        monkeypatch.setattr(
            "src.spacehack.saveload._autosave_path",
            lambda: tmp_path / "autosave.json",
        )
        from src.spacehack.engine import RNG
        RNG.seed(53)
        ctx = _build_test_ctx()
        ctx.ground_stats.strength = 20
        ctx.equipped_ground_weapons = [
            GroundWeaponInstance("laser_pistol", 37),
            GroundWeaponInstance("combat_knife", None),
        ]
        ctx.equipped_ground_armor = {"body": "light_vest"}
        ctx.ground_armory_storage = [
            StoredGroundEquipment("weapon", "laser_rifle"),
            StoredGroundEquipment("weapon", "laser_rifle"),
            StoredGroundEquipment("armor", "heavy_vest"),
        ]
        ctx.ground_expedition_inventory = [
            StoredGroundEquipment("weapon", "combat_knife"),
            StoredGroundEquipment("armor", "light_helmet"),
        ]

        save_game(ctx, mode="city", city_id="earth", system_id="sol")
        loaded = load_game(ctx.context)

        assert loaded is not None
        assert loaded.equipped_ground_weapons == ctx.equipped_ground_weapons
        assert loaded.equipped_ground_armor == ctx.equipped_ground_armor
        assert loaded.ground_armory_storage == ctx.ground_armory_storage
        assert loaded.ground_expedition_inventory == ctx.ground_expedition_inventory
        delete_save()

    def test_round_trip_duplicate_weapon_instances_keep_independent_ammo(
        self, monkeypatch, tmp_path,
    ):
        """Two copies of the same weapon hold independent magazines."""
        monkeypatch.setattr(
            "src.spacehack.saveload._autosave_path",
            lambda: tmp_path / "autosave.json",
        )
        from src.spacehack.engine import RNG
        RNG.seed(60)
        ctx = _build_test_ctx()
        ctx.equipped_ground_weapons = [
            GroundWeaponInstance("kinetic_pistol", 3),
            GroundWeaponInstance("kinetic_pistol", 11),
        ]

        save_game(ctx, mode="city", city_id="earth", system_id="sol")
        loaded = load_game(ctx.context)

        assert loaded is not None
        assert loaded.equipped_ground_weapons == [
            GroundWeaponInstance("kinetic_pistol", 3),
            GroundWeaponInstance("kinetic_pistol", 11),
        ]
        delete_save()

    def test_legacy_string_weapons_migrate_to_full_magazines(
        self, monkeypatch, tmp_path,
    ):
        """Pre-instance saves load as instances seeded at full magazines."""
        monkeypatch.setattr(
            "src.spacehack.saveload._autosave_path",
            lambda: tmp_path / "autosave.json",
        )
        from src.spacehack.engine import RNG
        RNG.seed(61)
        ctx = _build_test_ctx()
        save_game(ctx, mode="city", city_id="earth", system_id="sol")
        import json
        path = tmp_path / "autosave.json"
        payload = json.loads(path.read_text())
        payload["equipped_ground_weapons"] = ["kinetic_pistol", "combat_knife"]
        path.write_text(json.dumps(payload))

        loaded = load_game(ctx.context)

        assert loaded is not None
        assert loaded.equipped_ground_weapons == [
            GroundWeaponInstance("kinetic_pistol", 12),
            GroundWeaponInstance("combat_knife", None),
        ]
        delete_save()

    def test_round_trip_ground_item_stacks(self, monkeypatch, tmp_path):
        """Field-item ammo and consumable stacks survive Continue."""
        monkeypatch.setattr(
            "src.spacehack.saveload._autosave_path",
            lambda: tmp_path / "autosave.json",
        )
        from src.spacehack.engine import RNG
        RNG.seed(58)
        ctx = _build_test_ctx()
        ctx.ground_armory_items = [
            GroundItemStack("ammo", "rifle_rounds", 12),
            GroundItemStack("consumable", "med_pack", 3),
        ]
        ctx.ground_expedition_items = [
            GroundItemStack("ammo", "shotgun_shells", 7),
        ]

        save_game(ctx, mode="city", city_id="earth", system_id="sol")
        loaded = load_game(ctx.context)

        assert loaded is not None
        assert loaded.ground_armory_items == ctx.ground_armory_items
        assert loaded.ground_expedition_items == ctx.ground_expedition_items
        delete_save()

    def test_malformed_ground_item_stacks_are_ignored(self, monkeypatch, tmp_path):
        """Malformed field-item records do not prevent Continue."""
        monkeypatch.setattr(
            "src.spacehack.saveload._autosave_path",
            lambda: tmp_path / "autosave.json",
        )
        from src.spacehack.engine import RNG
        RNG.seed(59)
        ctx = _build_test_ctx()
        save_game(ctx, mode="city", city_id="earth", system_id="sol")
        import json
        path = tmp_path / "autosave.json"
        payload = json.loads(path.read_text())
        payload["ground_armory_items"] = [
            {"item_type": "ammo", "item_id": "rifle_rounds", "quantity": 12},
            {"item_type": "ammo", "item_id": "missing_ammo", "quantity": 5},
            {"item_type": "weapon", "item_id": "laser_pistol", "quantity": 1},
            {"item_type": "ammo", "item_id": "rifle_rounds", "quantity": 999},
            "not a record",
        ]
        payload["ground_expedition_items"] = [
            {"item_type": "consumable", "item_id": "med_pack", "quantity": 0},
            {"item_type": "consumable", "item_id": "med_pack", "quantity": 2},
        ]
        path.write_text(json.dumps(payload))

        loaded = load_game(ctx.context)

        assert loaded is not None
        assert loaded.ground_armory_items == [
            GroundItemStack("ammo", "rifle_rounds", 12),
            GroundItemStack("ammo", "rifle_rounds", 40),
        ]
        assert loaded.ground_expedition_items == [
            GroundItemStack("consumable", "med_pack", 2),
        ]
        delete_save()

    def test_malformed_ground_equipment_entries_are_ignored(self, monkeypatch, tmp_path):
        """Malformed ground records do not prevent Continue."""
        monkeypatch.setattr(
            "src.spacehack.saveload._autosave_path",
            lambda: tmp_path / "autosave.json",
        )
        from src.spacehack.engine import RNG
        RNG.seed(54)
        ctx = _build_test_ctx()
        save_game(ctx, mode="city", city_id="earth", system_id="sol")
        import json
        path = tmp_path / "autosave.json"
        payload = json.loads(path.read_text())
        payload["ground_armory_storage"] = [
            {"item_type": "weapon", "item_id": "laser_rifle"},
            {"item_type": "weapon", "item_id": "missing_weapon"},
            {"item_type": "module", "item_id": "shield_mk4"},
            {"item_type": "armor", "item_id": "light_helmet"},
            "not a record",
        ]
        payload["ground_expedition_inventory"] = [
            {"item_type": "armor", "item_id": "heavy_vest"},
            {"item_type": "unknown", "item_id": "light_helmet"},
        ]
        path.write_text(json.dumps(payload))

        loaded = load_game(ctx.context)

        assert loaded is not None
        assert loaded.ground_armory_storage == [
            StoredGroundEquipment("weapon", "laser_rifle"),
            StoredGroundEquipment("armor", "light_helmet"),
        ]
        assert loaded.ground_expedition_inventory == [
            StoredGroundEquipment("armor", "heavy_vest"),
        ]
        delete_save()

    def test_malformed_active_ground_fields_are_safely_normalized(
        self, monkeypatch, tmp_path,
    ):
        """Malformed active armor, stats, and HP cannot poison Continue."""
        monkeypatch.setattr(
            "src.spacehack.saveload._autosave_path",
            lambda: tmp_path / "autosave.json",
        )
        from src.spacehack.engine import RNG
        RNG.seed(62)
        ctx = _build_test_ctx()
        save_game(ctx, mode="city", city_id="earth", system_id="sol")
        import json
        path = tmp_path / "autosave.json"
        payload = json.loads(path.read_text())
        payload["ground_stats"] = {
            "reflexes": "bad", "strength": 999, "stamina": -5,
        }
        payload["equipped_ground_armor"] = {
            "body": "light_vest",
            "head": "missing_armor",
            "hands": "light_vest",
            "invalid": "light_vest",
        }
        payload["ground_hp"] = "bad"
        payload["ground_max_hp"] = 0
        path.write_text(json.dumps(payload))

        loaded = load_game(ctx.context)

        assert loaded is not None
        assert loaded.ground_stats.reflexes == 10
        assert loaded.ground_stats.strength == 100
        assert loaded.ground_stats.stamina == 0
        assert loaded.equipped_ground_armor == {"body": "light_vest"}
        assert loaded.ground_max_hp == 1
        assert loaded.ground_hp == 1
        delete_save()

    def test_legacy_ground_storage_migrates_to_armory(self, monkeypatch, tmp_path):
        """The intermediate single-storage name loads into Armory Storage."""
        monkeypatch.setattr(
            "src.spacehack.saveload._autosave_path",
            lambda: tmp_path / "autosave.json",
        )
        from src.spacehack.engine import RNG
        RNG.seed(55)
        ctx = _build_test_ctx()
        save_game(ctx, mode="city", city_id="earth", system_id="sol")
        import json
        path = tmp_path / "autosave.json"
        payload = json.loads(path.read_text())
        payload.pop("ground_armory_storage", None)
        payload.pop("ground_expedition_inventory", None)
        payload["ground_equipment_storage"] = [
            {"item_type": "weapon", "item_id": "combat_knife"},
            {"item_type": "armor", "item_id": "light_vest"},
        ]
        path.write_text(json.dumps(payload))

        loaded = load_game(ctx.context)

        assert loaded is not None
        assert loaded.ground_armory_storage == [
            StoredGroundEquipment("weapon", "combat_knife"),
            StoredGroundEquipment("armor", "light_vest"),
        ]
        assert loaded.ground_expedition_inventory == []
        delete_save()

    def test_legacy_save_without_ground_storage_loads_empty(self, monkeypatch, tmp_path):
        """Pre-ground-storage saves load both containers empty."""
        monkeypatch.setattr(
            "src.spacehack.saveload._autosave_path",
            lambda: tmp_path / "autosave.json",
        )
        from src.spacehack.engine import RNG
        RNG.seed(56)
        ctx = _build_test_ctx()
        save_game(ctx, mode="city", city_id="earth", system_id="sol")
        import json
        path = tmp_path / "autosave.json"
        payload = json.loads(path.read_text())
        payload.pop("ground_armory_storage", None)
        payload.pop("ground_expedition_inventory", None)
        path.write_text(json.dumps(payload))

        loaded = load_game(ctx.context)

        assert loaded is not None
        assert loaded.ground_armory_storage == []
        assert loaded.ground_expedition_inventory == []
        delete_save()

    def test_round_trip_owned_ship(self, monkeypatch, tmp_path):
        """Ship state (hull damage, fuel, weapons, name) survives round-trip."""
        monkeypatch.setattr(
            "src.spacehack.saveload._autosave_path",
            lambda: tmp_path / "autosave.json",
        )
        from src.spacehack.engine import RNG
        RNG.seed(42)
        from src.spacehack.ship import OwnedShip

        ctx = _build_test_ctx()
        ctx.player_owned_ship = OwnedShip(
            ship_id="scout",
            display_name="Test Runner",
            hull_damage_pct=15,
            weapons=("light_laser",),
            modules=(),
            fuel=25,
            inventory={"food": 3},
        )

        save_game(ctx, mode="city", city_id="earth", system_id="sol")
        loaded = load_game(ctx.context)
        assert loaded is not None
        ship = loaded.player_owned_ship
        assert ship is not None
        assert ship.ship_id == "scout"
        assert ship.display_name == "Test Runner"
        assert ship.hull_damage_pct == 15
        assert ship.weapons == ("light_laser",)
        assert ship.fuel == 25
        assert ship.inventory == {"food": 3}

        delete_save()
        import src.spacehack.solar_system as _ss
        _ss.current_solar_system_id = "sol"


class TestCityInteriorSaveMigration:
    """City interiors are deterministic assets and never serialize.

    Regression: city rooms rode along in the wreck-interior autosave
    cache, so an old save restored stale tiles and a stale mid-floor
    entry spawn even after the layout data was fixed in code.
    """

    def _stale_city_interior(self) -> GameMap:
        """A bar interior as an OLD save would hold it: mid-floor spawn."""
        from src.spacehack import city_landmarks
        game_map = city_landmarks.load_city_interior(
            "barnards_c_bar_interior",
        ).game_map
        game_map.city_interior_id = "city:barnards_c:bar"
        game_map.interior_cache_key = "city:barnards_c:bar"
        game_map.city_building_label = "bar"
        game_map.entry_spawn = Position(6, 4)
        return game_map

    def _wreck_interior(self) -> GameMap:
        return GameMap(
            width=4, height=4,
            tiles=[[world.VOID for _ in range(4)] for _ in range(4)],
            entities=[],
        )

    def test_save_skips_city_interiors_but_keeps_wrecks(self):
        from src.spacehack.saveload import _write_dungeon_and_interiors
        ctx = SimpleNamespace(
            interiors={
                "city:barnards_c:bar": self._stale_city_interior(),
                "wreck_1": self._wreck_interior(),
            },
            game_map=None,
        )
        data: dict = {}
        _write_dungeon_and_interiors(ctx, data, "city", None)
        assert "city:barnards_c:bar" not in data["interiors"]
        assert "wreck_1" in data["interiors"]

    def test_legacy_city_cache_entries_are_dropped_on_load(self):
        from src.spacehack.saveload_maps import _restore_interiors
        from src.spacehack.saveload_maps import _dungeon_to_dict
        stale_dict = _dungeon_to_dict(self._stale_city_interior(), None)
        ctx = SimpleNamespace(
            interiors={}, dungeon_extension=None, player_owned_ship=None,
        )
        rebuilt = SimpleNamespace(
            mode="city", game_map=self._wreck_interior(),
            player_ent=None, city_id="barnards_c",
        )
        _restore_interiors(
            ctx, {"interiors": {"city:barnards_c:bar": stale_dict}}, rebuilt,
        )
        assert "city:barnards_c:bar" not in ctx.interiors

    def test_resume_inside_city_interior_rebuilds_current_room(self):
        """Continue indoors swaps the stale room for the authored asset
        and places the player at the current door-side entry spawn."""
        from src.spacehack.saveload_maps import _restore_interiors
        from src.spacehack.saveload_maps import _RebuiltMap
        stale = self._stale_city_interior()
        player = Entity("@", (255, 255, 255), Position(6, 4), name="Player")
        stale.entities.append(player)
        rebuilt = _RebuiltMap(
            game_map=stale, player_ent=player, mode="dungeon",
            city_id="barnards_c", system_id="barnards",
            space_map=None, space_player=None,
        )
        ctx = SimpleNamespace(
            interiors={}, dungeon_extension=None, player_owned_ship=None,
        )
        result = _restore_interiors(ctx, {}, rebuilt)
        fresh = result.game_map
        assert fresh is not stale
        # The current asset's door-side spawn, not the stale mid-floor one.
        assert (player.pos.x, player.pos.y) == (9, 8)
        assert ctx.interiors["city:barnards_c:bar"] is fresh
        assert ctx.game_map is fresh
        assert ctx.player is player
        # The seated service NPC re-seats in the rebuilt room.
        assert any(
            getattr(entity, "npc_id", "") == "barkeep"
            for entity in fresh.entities
        )
        # The exterior city is attached as the exit parent.
        assert getattr(fresh, "city_parent_map", None) is not None
