"""Tests for saveload.py — save/load round-trip integrity.

The save/load contract is explicitly called out in knowledge.md as
"not checked by the smoke test." A round-trip test builds a
GameContext with known state, saves it, loads it back, and asserts
every serialized field survived.
"""

from __future__ import annotations
from tests.support.asyncutil import run, as_async

import json
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
from src.spacehack.saveload import save_game, load_game, delete_save, _d
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
    stats = HudStats(credits=100)
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
    # Set non-default fields with known values (full four-axis sheet —
    # doc 48 phase 2; the load migration seeds absent axes, so a
    # partial fixture would not round-trip equal).
    ctx.faction_reputation = {
        "pirate": -50, "merchant": 25, "militia": 50, "consortium": -100,
    }
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
    # Tenure-qualified (doc 41 phase 2): a QUALIFIED key round-trips
    # untouched; the pre-phase-2 unqualified-key migration is pinned
    # in test_navigation_line (load re-stamps those to the current
    # tenure, so they intentionally do NOT round-trip verbatim).
    ctx.defeated_static_spawns = {"luyten_star:militia_blockade:150:25:t2"}
    # Identity layer (doc 40): registration, dark flag, worn face, and
    # the collected-ID library must survive a save/continue cycle.
    ctx.ship_registration = "AB-1234"
    ctx.broadcast_dark = True
    ctx.transponder_cutout = True  # dark survives only with a cut-out
    ctx.broadcast_identity = {
        "id": "KG-8812", "kind": "cloned",
        "label": "Warlord face", "faction": "pirate",
    }
    ctx.collected_ids = [
        ctx.broadcast_identity,
        {"id": "KX-1234", "kind": "scrubbed", "label": "Scrubbed hull",
         "faction": None, "origin": "no history, no debts",
         "rep": {"merchant": -40}},
    ]
    ctx.main_quest_disposition = "archive_sealed"
    # Rumor keyring (doc 42): non-tier order proves heard order
    # survives the round trip. (derelict_line/thin_month retired with
    # the one-chain ruling — a pre-ruling save carries those ids and
    # the stale-id skip must handle them.)
    ctx.known_rumors = ["dark_berth_2", "dark_berth_1", "dark_berth_3"]
    # Favor ledgers (doc 42 phase 2): two books, earned sets included.
    ctx.rumor_favor = {
        "wolf_barkeep": {"favor": 4, "earned": ["dark_berth_1", "dark_berth_2"]},
        "research_officer": {"favor": 1, "earned": ["dark_berth_3"]},
    }
    # Discovered dig sites (doc 42 phase 4): reveal order preserved.
    ctx.discovered_sites = [
        {"id": "s1", "planet": "mars", "name": "Sunken Vault"},
        {"id": "s2", "planet": "venus", "name": "Rusted Warren"},
    ]
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

    def test_message_history_runs_survive_round_trip(self):
        """Inline colour runs serialize, reload, and drop when corrupt."""
        from src.spacehack import message_log, saveload

        text, runs = message_log.with_runs(
            "Stored ship module: ", ("Prototype Shield Mk. 2", (190, 140, 255)), ".",
        )
        entry = message_log.MessageEntry(text, (9, 9, 9), runs)
        payload = {"message_history": [saveload._entry_payload(entry)]}

        log = saveload._parse_log(payload)
        restored = log.history()[0]

        assert restored.text == text
        assert restored.fg == (9, 9, 9)
        assert restored.runs == runs

        corrupt = {
            "message_history": [
                {"text": text, "fg": [9, 9, 9], "runs": [["orphan", [1, 2, 3]]]},
                {"text": "legacy entry", "fg": [1, 1, 1]},
            ],
        }
        log = saveload._parse_log(corrupt)
        assert log.history()[0].runs is None  # runs text != entry text
        assert log.history()[1].runs is None  # legacy saves carry no runs key

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

        # The vestigial hull readouts never reach the save payload
        # (doc 49 SETTLED 5).
        payload = json.loads((tmp_path / "autosave.json").read_text())
        assert set(payload["stats"]) == {
            "credits", "gunnery", "piloting", "engineering",
        }

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

    def test_ground_damage_taken_survives_round_trip(self, monkeypatch, tmp_path):
        """The doc 53 ground tally counter persists (career total)."""
        monkeypatch.setattr(
            "src.spacehack.saveload._autosave_path",
            lambda: tmp_path / "autosave.json",
        )
        from src.spacehack.engine import RNG
        RNG.seed(21)

        ctx = _build_test_ctx()
        ctx.player_counters.ground_damage_taken = 31
        save_game(ctx, mode="city", city_id="earth", system_id="sol")

        loaded = load_game(ctx.context)
        assert loaded is not None
        assert loaded.player_counters.ground_damage_taken == 31
        delete_save()
        import src.spacehack.solar_system as _ss
        _ss.current_solar_system_id = "sol"

    def test_both_creation_traits_survive_round_trip(self, monkeypatch, tmp_path):
        """Doc 49 phase 2: a fresh character's exactly-two traits (species'
        + class') persist through save/quit/Continue."""
        monkeypatch.setattr(
            "src.spacehack.saveload._autosave_path",
            lambda: tmp_path / "autosave.json",
        )
        from src.spacehack.engine import RNG
        RNG.seed(7)

        ctx = _build_test_ctx()
        ctx.player_traits = ["fast_learner", "merchant"]
        save_game(ctx, mode="city", city_id="earth", system_id="sol")

        loaded = load_game(ctx.context)
        assert loaded is not None
        assert loaded.player_traits == ["fast_learner", "merchant"]
        delete_save()
        import src.spacehack.solar_system as _ss
        _ss.current_solar_system_id = "sol"

    def test_parse_counters_defaults_ground_damage_taken_to_zero(self):
        """A pre-doc-53 save (no ground tally key) loads as 0; the
        railgun/focused counters (a pre-existing silent reset, found
        in the doc 53 audit) rebuild from their keys."""
        from src.spacehack import saveload as _saveload_module

        counters = _saveload_module._parse_counters({
            "player_counters": {
                "total_damage_taken": 4,
                "railgun_kills": 2,
                "focused_shots": 9,
            },
        })
        assert counters.ground_damage_taken == 0
        assert counters.total_damage_taken == 4
        assert counters.railgun_kills == 2
        assert counters.focused_shots == 9

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

        # Stats (hull HP is gone from HudStats — doc 49 SETTLED 5:
        # hull is ship + modules, never a character stat)
        assert loaded.stats.credits == original.stats.credits
        assert loaded.stats.gunnery == original.stats.gunnery
        assert loaded.stats.piloting == original.stats.piloting
        assert loaded.stats.engineering == original.stats.engineering

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
        assert loaded.known_rumors == original.known_rumors
        # Favor ledgers: books and earned sets survive verbatim.
        assert loaded.rumor_favor == original.rumor_favor
        # Discovered dig sites: reveal order preserved (doc 42 phase 4).
        assert loaded.discovered_sites == original.discovered_sites

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
        assert loaded.main_quest_disposition == original.main_quest_disposition
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

        # Static-spawn tombstones (doc 41): a defeated picket stays dead
        assert loaded.defeated_static_spawns == original.defeated_static_spawns

        # Identity layer (doc 40)
        assert loaded.ship_registration == original.ship_registration
        assert loaded.broadcast_dark == original.broadcast_dark
        assert loaded.transponder_cutout == original.transponder_cutout
        assert loaded.broadcast_identity == original.broadcast_identity
        assert loaded.collected_ids == original.collected_ids

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
            "main_quest_disposition",
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
        assert loaded.main_quest_disposition == ""
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
        extension_map, extension_player = run(
                                              dungeon_extensions.enter_extension(
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
            as_async(lambda *args, **kwargs: shown.append((args, kwargs))),
        )
        restored_parent = loaded.interiors["surface:mars"]
        restored_parent_player = Entity(
            "@", (255, 255, 255), parent_position, "Player",
        )
        run(
            dungeon_extensions.enter_extension(
            loaded,
            restored_parent,
            restored_parent_player,
            extension_id="mars_alien_prison",
            parent_map_key="surface:mars",
        )
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
            as_async(lambda *args, **kwargs: None),
        )
        extension_map, _ = run(
                               dungeon_extensions.enter_extension(
            loaded,
            loaded.game_map,
            loaded.player,
            extension_id="mars_alien_prison",
        )
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
            as_async(lambda *args, **kwargs: None),
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
        run(
            dungeon_extensions.enter_extension(
            ctx,
            parent_map,
            parent_player,
            extension_id="mars_alien_prison",
            parent_map_key="surface:mars",
        )
        )
        floor_two, floor_two_player = run(dungeon_extensions.transition_floor(ctx, 1))
        ctx.dungeon_extension.activated_events.clear()
        ctx.dungeon_extension.state_flags.add("prison_data_extracted")
        floor_two_player.pos = floor_two.up_stair_pos
        assert run(dungeon_extensions.tick_activation(ctx))
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
        assert run(dungeon_extensions.tick_activation(loaded))
        assert loaded.dungeon_extension.activated_events == {
            "prison_ascent_f2_assault",
            "prison_ascent_f2_sentries",
        }
        # Wakeups can fall one short of event.count when placement
        # filters claim a cell (Phase B footprints) — at least one per
        # squad always wakes.
        assert sum(
            entity.npc_char_id == "sentry_drone"
            and not entity.powered_down
            for entity in loaded.game_map.entities
        ) >= 1
        assert not run(dungeon_extensions.tick_activation(loaded))
        delete_save()

    def test_phase_two_floor_round_trip_preserves_links_and_cache(
        self, monkeypatch, tmp_path,
    ):
        """Continue on Floor 2 preserves both visited floors and stair links."""
        monkeypatch.setattr(
            "src.spacehack.saveload._autosave_path",
            lambda: tmp_path / "autosave.json",
        )
        monkeypatch.setattr(
            "src.spacehack.main_quest.show_gate_popup",
            as_async(lambda *args, **kwargs: None),
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
        floor_one, _ = run(
                           dungeon_extensions.enter_extension(
            ctx,
            parent_map,
            parent_player,
            extension_id="mars_alien_prison",
            parent_map_key="surface:mars",
        )
                       )
        floor_two, _ = run(dungeon_extensions.transition_floor(ctx, 1))

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

        run(dungeon_extensions.transition_floor(loaded, 1))
        run(dungeon_extensions.transition_floor(loaded, 1))
        assert loaded.dungeon_extension.current_floor == 4
        assert run(dungeon_extensions.restore_power(loaded))
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
            weapons=(StoredEquipment("weapon", "light_laser", grid_x=0, grid_y=0),),
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
        assert tuple(e.item_id for e in loaded.player_owned_ship.weapons) == ("light_laser",)
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
            modules=(StoredEquipment("module", "shield_mk1"),) * 2,
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
        assert tuple(e.item_id for e in loaded.player_owned_ship.weapons) == ()
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
        quality_loot = Entity(
            char="%", fg=(130, 145, 170), pos=Position(3, 3),
            name="Loot", width=1, height=1,
            loot_data={
                "item_type": "weapon", "item_id": "smg", "quality": 2,
            },
        )
        dungeon_map.entities.append(quality_loot)

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
        restored_quality = next(
            entity for entity in loaded.game_map.entities
            if (entity.loot_data or {}).get("quality")
        )
        assert restored_quality.loot_data == {
            "item_type": "weapon", "item_id": "smg", "quality": 2,
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
        ctx.equipped_ground_armor = {
            "body": StoredGroundEquipment("armor", "light_vest", 2),
            "head": StoredGroundEquipment("armor", "light_helmet"),
        }
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

    def test_round_trip_weapon_quality_survives_continue(
        self, monkeypatch, tmp_path,
    ):
        """Rolled quality tiers ride every equipment shape (doc 47.2)."""
        monkeypatch.setattr(
            "src.spacehack.saveload._autosave_path",
            lambda: tmp_path / "autosave.json",
        )
        from src.spacehack.engine import RNG
        RNG.seed(62)
        ctx = _build_test_ctx()
        ctx.equipped_ground_weapons = [
            GroundWeaponInstance("smg", 5, 2),
            GroundWeaponInstance("combat_knife", None, 3),
        ]
        ctx.ground_armory_storage = [
            StoredGroundEquipment("weapon", "railgun", 1),
            StoredGroundEquipment("armor", "heavy_vest", 2),
        ]
        ctx.ground_expedition_inventory = [
            StoredGroundEquipment("weapon", "shotgun", 3),
        ]

        save_game(ctx, mode="city", city_id="earth", system_id="sol")
        loaded = load_game(ctx.context)

        assert loaded is not None
        assert loaded.equipped_ground_weapons == [
            GroundWeaponInstance("smg", 5, 2),
            GroundWeaponInstance("combat_knife", None, 3),
        ]
        assert loaded.ground_armory_storage == [
            StoredGroundEquipment("weapon", "railgun", 1),
            StoredGroundEquipment("armor", "heavy_vest", 2),
        ]
        assert loaded.ground_expedition_inventory == [
            StoredGroundEquipment("weapon", "shotgun", 3),
        ]
        delete_save()

    def test_legacy_qualityless_stored_entries_migrate_to_base(
        self, monkeypatch, tmp_path,
    ):
        """Pre-quality saves load every stored item at base tier."""
        monkeypatch.setattr(
            "src.spacehack.saveload._autosave_path",
            lambda: tmp_path / "autosave.json",
        )
        from src.spacehack.engine import RNG
        RNG.seed(63)
        ctx = _build_test_ctx()
        ctx.ground_armory_storage = [
            StoredGroundEquipment("weapon", "laser_rifle"),
        ]
        save_game(ctx, mode="city", city_id="earth", system_id="sol")

        # Strip the quality key the way a pre-quality save would look.
        path = tmp_path / "autosave.json"
        raw = json.loads(path.read_text())
        for key in ("ground_armory_storage", "ground_expedition_inventory"):
            for entry in raw.get(key, []):
                entry.pop("quality", None)
        path.write_text(json.dumps(raw))

        loaded = load_game(ctx.context)
        assert loaded is not None
        assert loaded.ground_armory_storage == [
            StoredGroundEquipment("weapon", "laser_rifle", 0),
        ]
        delete_save()

    def test_legacy_string_weapons_migrate_to_full_magazines(
        self, monkeypatch, tmp_path,
    ):
        """Pre-instance saves load as instances seeded at full magazines.

        Doc 51: the payload is stripped to a true pre-51 shape (no
        holstered key), so the load also partitions the mixed pair —
        pistol active, knife holstered."""
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
        payload.pop("holstered_ground_weapons", None)
        path.write_text(json.dumps(payload))

        loaded = load_game(ctx.context)

        assert loaded is not None
        assert loaded.equipped_ground_weapons == [
            GroundWeaponInstance("kinetic_pistol", 12),
        ]
        assert loaded.holstered_ground_weapons == [
            GroundWeaponInstance("combat_knife", None),
        ]
        delete_save()

    def test_round_trip_holstered_weapon_set(self, monkeypatch, tmp_path):
        """Holstered set members round-trip with magazines + quality."""
        monkeypatch.setattr(
            "src.spacehack.saveload._autosave_path",
            lambda: tmp_path / "autosave.json",
        )
        from src.spacehack.engine import RNG
        RNG.seed(64)
        ctx = _build_test_ctx()
        ctx.equipped_ground_weapons = [GroundWeaponInstance("kinetic_pistol", 5)]
        ctx.holstered_ground_weapons = [
            GroundWeaponInstance("railgun", 2, 1),
            GroundWeaponInstance("mono_blade", None, 2),
        ]
        save_game(ctx, mode="city", city_id="earth", system_id="sol")
        loaded = load_game(ctx.context)

        assert loaded is not None
        assert loaded.holstered_ground_weapons == [
            GroundWeaponInstance("railgun", 2, 1),
            GroundWeaponInstance("mono_blade", None, 2),
        ]
        assert loaded.equipped_ground_weapons == [
            GroundWeaponInstance("kinetic_pistol", 5),
        ]
        delete_save()

    def test_stored_weapon_magazines_round_trip_through_containers(
            self, tmp_path, monkeypatch):
        """Doc 51.3: a half-spent magazine survives a save/load cycle
        in every storage container (pack, warehouse, both sets)."""
        monkeypatch.setattr(
            "src.spacehack.saveload._autosave_path",
            lambda: tmp_path / "autosave.json",
        )
        from src.spacehack.engine import RNG
        RNG.seed(64)
        ctx = _build_test_ctx()
        ctx.equipped_ground_weapons = [GroundWeaponInstance("kinetic_pistol", 5)]
        ctx.holstered_ground_weapons = [GroundWeaponInstance("smg", 9, 1)]
        ctx.ground_expedition_inventory = [
            StoredGroundEquipment("weapon", "laser_pistol", 2, 3),
        ]
        ctx.ground_armory_storage = [
            StoredGroundEquipment("weapon", "railgun", 1, 4),
        ]
        save_game(ctx, mode="city", city_id="earth", system_id="sol")
        loaded = load_game(ctx.context)

        assert loaded is not None
        assert loaded.ground_expedition_inventory == [
            StoredGroundEquipment("weapon", "laser_pistol", 2, 3),
        ]
        assert loaded.ground_armory_storage == [
            StoredGroundEquipment("weapon", "railgun", 1, 4),
        ]
        delete_save()

    def test_pre_doc51_mixed_pair_migrates_on_slot_zero_class(
        self, monkeypatch, tmp_path,
    ):
        """A pre-51 save with a mixed pair splits: slot 0's class stays
        active, the other class holsters (doc 51 phase 1)."""
        monkeypatch.setattr(
            "src.spacehack.saveload._autosave_path",
            lambda: tmp_path / "autosave.json",
        )
        from src.spacehack.engine import RNG
        RNG.seed(65)
        ctx = _build_test_ctx()
        ctx.equipped_ground_weapons = [
            GroundWeaponInstance("kinetic_pistol", 3),
            GroundWeaponInstance("combat_knife", None, 1),
        ]
        save_game(ctx, mode="city", city_id="earth", system_id="sol")
        import json
        path = tmp_path / "autosave.json"
        payload = json.loads(path.read_text())
        payload.pop("holstered_ground_weapons", None)
        path.write_text(json.dumps(payload))

        loaded = load_game(ctx.context)

        assert loaded is not None
        assert loaded.equipped_ground_weapons == [
            GroundWeaponInstance("kinetic_pistol", 3),
        ]
        assert loaded.holstered_ground_weapons == [
            GroundWeaponInstance("combat_knife", None, 1),
        ]
        delete_save()

    def test_pre_doc51_same_class_pair_stays_active(
        self, monkeypatch, tmp_path,
    ):
        """Same-class loadouts migrate with zero behavior change."""
        monkeypatch.setattr(
            "src.spacehack.saveload._autosave_path",
            lambda: tmp_path / "autosave.json",
        )
        from src.spacehack.engine import RNG
        RNG.seed(66)
        ctx = _build_test_ctx()
        ctx.equipped_ground_weapons = [
            GroundWeaponInstance("kinetic_pistol", 3),
            GroundWeaponInstance("smg", 7, 2),
        ]
        save_game(ctx, mode="city", city_id="earth", system_id="sol")
        import json
        path = tmp_path / "autosave.json"
        payload = json.loads(path.read_text())
        payload.pop("holstered_ground_weapons", None)
        path.write_text(json.dumps(payload))

        loaded = load_game(ctx.context)

        assert loaded is not None
        assert loaded.equipped_ground_weapons == [
            GroundWeaponInstance("kinetic_pistol", 3),
            GroundWeaponInstance("smg", 7, 2),
        ]
        assert loaded.holstered_ground_weapons == []
        delete_save()

    def test_pre_doc51_empty_equipped_loads_clean(
        self, monkeypatch, tmp_path,
    ):
        """No starter loadout exists — pre-51 saves are mostly empty
        here; the migration is a no-op that never crashes."""
        monkeypatch.setattr(
            "src.spacehack.saveload._autosave_path",
            lambda: tmp_path / "autosave.json",
        )
        from src.spacehack.engine import RNG
        RNG.seed(67)
        ctx = _build_test_ctx()
        save_game(ctx, mode="city", city_id="earth", system_id="sol")
        import json
        path = tmp_path / "autosave.json"
        payload = json.loads(path.read_text())
        payload.pop("holstered_ground_weapons", None)
        path.write_text(json.dumps(payload))

        loaded = load_game(ctx.context)

        assert loaded is not None
        assert loaded.equipped_ground_weapons == []
        assert loaded.holstered_ground_weapons == []
        delete_save()

    def test_present_holstered_key_loads_verbatim(
        self, monkeypatch, tmp_path,
    ):
        """A present key suppresses migration — the restore path never
        enforces class purity (the brief's current-save trap, pinned)."""
        monkeypatch.setattr(
            "src.spacehack.saveload._autosave_path",
            lambda: tmp_path / "autosave.json",
        )
        from src.spacehack.engine import RNG
        RNG.seed(68)
        ctx = _build_test_ctx()
        ctx.equipped_ground_weapons = [
            GroundWeaponInstance("kinetic_pistol", 3),
            GroundWeaponInstance("combat_knife", None),
        ]
        ctx.holstered_ground_weapons = [GroundWeaponInstance("smg", 9, 1)]
        save_game(ctx, mode="city", city_id="earth", system_id="sol")
        loaded = load_game(ctx.context)

        assert loaded is not None
        assert loaded.equipped_ground_weapons == [
            GroundWeaponInstance("kinetic_pistol", 3),
            GroundWeaponInstance("combat_knife", None),
        ]
        assert loaded.holstered_ground_weapons == [
            GroundWeaponInstance("smg", 9, 1),
        ]
        delete_save()

    def test_round_trip_ground_item_stacks(self, monkeypatch, tmp_path):
        """Consumable stacks survive Continue verbatim; ammo lives in
        the bandolier only (doc 52.2 — no stack class remains)."""
        monkeypatch.setattr(
            "src.spacehack.saveload._autosave_path",
            lambda: tmp_path / "autosave.json",
        )
        from src.spacehack.engine import RNG
        RNG.seed(58)
        ctx = _build_test_ctx()
        ctx.ground_armory_items = [
            GroundItemStack("consumable", "med_pack", 3),
        ]
        ctx.ground_expedition_items = [
            GroundItemStack("consumable", "med_pack", 2),
        ]
        ctx.bandolier = {"kinetic_pistol": 132, "rifle_round": 12}

        save_game(ctx, mode="city", city_id="earth", system_id="sol")
        loaded = load_game(ctx.context)

        assert loaded is not None
        assert loaded.ground_armory_items == ctx.ground_armory_items
        assert loaded.ground_expedition_items == ctx.ground_expedition_items
        assert loaded.bandolier == {"kinetic_pistol": 132, "rifle_round": 12}
        delete_save()

    def test_pre52_stored_ammo_migrates_to_bandolier_with_refund(
        self, monkeypatch, tmp_path,
    ):
        """A pre-52 save's stacks — pack AND Armory Storage — convert
        into bandolier counts at cap, overflow refunds credits, pack
        slots free, and no ammo stack persists anywhere (doc 52.2)."""
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
        payload.pop("bandolier", None)
        payload["ground_expedition_items"] = [
            {"item_type": "ammo", "item_id": "pistol_rounds", "quantity": 40},
            {"item_type": "ammo", "item_id": "pistol_rounds", "quantity": 40},
            {"item_type": "ammo", "item_id": "pistol_rounds", "quantity": 40},
            {"item_type": "ammo", "item_id": "pistol_rounds", "quantity": 40},
            {"item_type": "ammo", "item_id": "pistol_rounds", "quantity": 40},
            {"item_type": "ammo", "item_id": "rockets", "quantity": 4},
            {"item_type": "ammo", "item_id": "rockets", "quantity": 4},
            {"item_type": "ammo", "item_id": "rockets", "quantity": 4},
            {"item_type": "consumable", "item_id": "med_pack", "quantity": 3},
        ]
        payload["ground_armory_items"] = [
            {"item_type": "ammo", "item_id": "rifle_rounds", "quantity": 12},
        ]
        path.write_text(json.dumps(payload))

        loaded = load_game(ctx.context)

        assert loaded is not None
        # Pack: 200 pistol rounds -> 160 cap (40 over x 1 cr); 12
        # rockets -> 10 cap (2 over x 20 cr). Armory: 12 rifle rounds
        # convert under cap. Refund 40 + 40 = 80 cr.
        assert loaded.bandolier == {
            "kinetic_pistol": 160, "rocket": 10, "rifle_round": 12,
        }
        assert loaded.ground_expedition_items == [
            GroundItemStack("consumable", "med_pack", 3),
        ]
        assert loaded.ground_armory_items == []
        # The retirement pin (doc 52.2): no ammo stack persists in
        # either container after load.
        assert not any(
            stack.item_type == "ammo"
            for stack in (
                loaded.ground_expedition_items
                + loaded.ground_armory_items
            )
        )
        assert loaded.stats.credits == ctx.stats.credits + 80
        history = " ".join(entry.text for entry in loaded.log.history())
        assert "Packed 182 reserve rounds into ammo storage." in history
        assert "Refunded 42 rounds past carry caps: 80$." in history

        # Migrated save re-saves and re-loads cleanly (sniff test).
        save_game(loaded, mode="city", city_id="earth", system_id="sol")
        reloaded = load_game(ctx.context)
        assert reloaded is not None
        assert reloaded.bandolier == {
            "kinetic_pistol": 160, "rocket": 10, "rifle_round": 12,
        }
        assert reloaded.ground_expedition_items == [
            GroundItemStack("consumable", "med_pack", 3),
        ]
        assert reloaded.ground_armory_items == []
        delete_save()

    def test_round_trip_bandolier(self, monkeypatch, tmp_path):
        """Bandolier counts survive Continue verbatim (doc 52 phase 1)."""
        monkeypatch.setattr(
            "src.spacehack.saveload._autosave_path",
            lambda: tmp_path / "autosave.json",
        )
        from src.spacehack.engine import RNG
        RNG.seed(60)
        ctx = _build_test_ctx()
        ctx.bandolier = {"kinetic_pistol": 132, "energy_cell": 250}

        save_game(ctx, mode="city", city_id="earth", system_id="sol")
        loaded = load_game(ctx.context)

        assert loaded is not None
        assert loaded.bandolier == {"kinetic_pistol": 132, "energy_cell": 250}
        delete_save()

    def test_bandolier_parse_clamps_and_skips_unknown_calibers(
        self, monkeypatch, tmp_path,
    ):
        """Over-cap counts clamp; unknown calibers and malformed values skip."""
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
        payload["bandolier"] = {
            "kinetic_pistol": 999,
            "rocket": 4,
            "black_powder": 50,
            "energy_cell": "many",
            7: 10,
        }
        path.write_text(json.dumps(payload))

        loaded = load_game(ctx.context)

        assert loaded is not None
        assert loaded.bandolier == {"kinetic_pistol": 160, "rocket": 4}
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
        # Parsed armory ammo stacks (12 + clamped 40) migrate into the
        # bandolier (doc 52.2); malformed records never arrive.
        assert loaded.ground_armory_items == []
        assert loaded.bandolier.get("rifle_round") == 52
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
            "legs": {"item_type": "armor", "item_id": "armour_pads", "quality": 2},
            "feet": {"item_type": "armor", "item_id": "combat_boots", "quality": "bad"},
        }
        payload["ground_hp"] = "bad"
        payload["ground_max_hp"] = 0
        path.write_text(json.dumps(payload))

        loaded = load_game(ctx.context)

        assert loaded is not None
        assert loaded.ground_stats.reflexes == 10
        assert loaded.ground_stats.strength == 100
        assert loaded.ground_stats.stamina == 0
        assert loaded.equipped_ground_armor == {
            "body": StoredGroundEquipment("armor", "light_vest"),
            "legs": StoredGroundEquipment("armor", "armour_pads", 2),
            "feet": StoredGroundEquipment("armor", "combat_boots"),
        }
        assert loaded.ground_max_hp == 1
        assert loaded.ground_hp == 1
        delete_save()

    def test_equipped_armor_parser_rejects_non_armor_values(self):
        """Only str and armor-typed dict values load; the rest drop."""
        from src.spacehack.saveload_ground import _parse_equipped_ground_armor

        parsed = _parse_equipped_ground_armor({
            "body": {"item_type": "weapon", "item_id": "laser_pistol"},
            "head": 42,
            "legs": {"item_id": "armour_pads"},  # missing item_type
            "feet": {"item_type": "armor", "item_id": "combat_boots"},
        })
        assert parsed == {"feet": StoredGroundEquipment("armor", "combat_boots")}

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
        from src.spacehack.ship import StoredEquipment
        ctx.player_owned_ship = OwnedShip(
            ship_id="scout",
            display_name="Test Runner",
            hull_damage_pct=15,
            # Placed (doc 56 phase 2): unplaced installed entries strip
            # to storage at load, by design.
            weapons=(StoredEquipment("weapon", "light_laser", grid_x=0, grid_y=0),),
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
        assert tuple(e.item_id for e in ship.weapons) == ("light_laser",)
        assert ship.fuel == 25
        assert ship.inventory == {"food": 3}

        delete_save()
        import src.spacehack.solar_system as _ss
        _ss.current_solar_system_id = "sol"

    def test_module_quality_survives_installed_and_stored(self, monkeypatch, tmp_path):
        """Variant modules keep their tier through Continue, both
        installed on the ship and sitting in storage (doc 47.3)."""
        monkeypatch.setattr(
            "src.spacehack.saveload._autosave_path",
            lambda: tmp_path / "autosave.json",
        )
        from src.spacehack.engine import RNG
        RNG.seed(47)
        from src.spacehack.ship import OwnedShip

        ctx = _build_test_ctx()
        ctx.player_owned_ship = OwnedShip(
            ship_id="scout",
            modules=(
                StoredEquipment("module", "shield_mk2", quality=2, grid_x=0, grid_y=0),
                StoredEquipment("module", "compact_reactor", grid_x=2, grid_y=0),
            ),
        )
        ctx.ship_storage = [StoredEquipment("module", "armor_plating", quality=3)]

        save_game(ctx, mode="city", city_id="earth", system_id="sol")
        loaded = load_game(ctx.context)

        assert loaded is not None
        ship = loaded.player_owned_ship
        assert ship is not None
        assert ship.modules == (
            StoredEquipment("module", "shield_mk2", quality=2, grid_x=0, grid_y=0),
            StoredEquipment("module", "compact_reactor", grid_x=2, grid_y=0),
        )
        assert loaded.ship_storage == [
            StoredEquipment("module", "armor_plating", quality=3),
        ]
        delete_save()

    def test_legacy_owned_ship_modules_migrate_to_base_entries(self):
        """Pre-instance saves carry bare module ids (or dicts without
        quality) — both load as base entries, unknown ids drop."""
        from src.spacehack.saveload import _parse_owned_ship

        osh = _parse_owned_ship({"player_owned_ship": {
            "ship_id": "scout",
            "modules": [
                "shield_mk1",
                {"item_type": "module", "item_id": "shield_mk2", "quality": 3},
                {"item_type": "module", "item_id": "no_such_module"},
                42,
            ],
        }})
        assert osh is not None
        assert osh.modules == (
            StoredEquipment("module", "shield_mk1"),
            StoredEquipment("module", "shield_mk2", quality=3),
        )

    def test_stored_equipment_quality_parses_or_migrates_to_base(self):
        from src.spacehack.saveload import _stored_equipment_from_dict

        base = {"item_type": "module", "item_id": "shield_mk1"}
        assert _stored_equipment_from_dict(base) == StoredEquipment(
            "module", "shield_mk1",
        )
        assert _stored_equipment_from_dict(
            {**base, "quality": 2},
        ) == StoredEquipment("module", "shield_mk1", quality=2)
        # Malformed or out-of-ladder quality migrates to base (0).
        assert _stored_equipment_from_dict(
            {**base, "quality": "junk"},
        ) == StoredEquipment("module", "shield_mk1")
        assert _stored_equipment_from_dict(
            {**base, "quality": 99},
        ) == StoredEquipment("module", "shield_mk1")


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
        # The current asset's door-side spawn — asserted against the
        # authored asset itself so layout polish can't stale this pin —
        # not the stale mid-floor one.
        from src.spacehack.city_landmarks import load_city_interior
        authored = load_city_interior("barnards_c_bar_interior")
        assert (player.pos.x, player.pos.y) == (authored.spawn.x, authored.spawn.y)
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


def test_npc_credit_round_trips_with_the_sync_population(monkeypatch, tmp_path):
    """Doc 44: movement credit persists EXACTLY what the path sync
    persists — a current-system patrol mid round-trips; a watch
    spawn key never does (flights are session-scoped by ruling)."""
    monkeypatch.setattr(
        "src.spacehack.saveload._autosave_path",
        lambda: tmp_path / "autosave.json",
    )
    from src.spacehack.engine import RNG
    RNG.seed(42)
    from src.spacehack.game_context import ProceduralSpawn

    ctx = _build_test_ctx()
    ctx.game_map.entities.append(world.Entity(
        "p", (255, 80, 80), Position(3, 3),
        npc_ship_id="pirate_scout", procedural_squad_id="m1",
    ))
    ctx.procedural_spawns = {"sol": [
        ProceduralSpawn(npc_id="pirate_scout", pos=Position(3, 3),
                        squad_id="m1"),
    ]}
    ctx.npc_targets = {"m1": (5, 5)}
    ctx.npc_paths = {"m1": [(4, 4), (5, 5)]}
    ctx.npc_credit = {
        "m1": 0.5,
        "luyten_star:militia_blockade:150:7:t4": 0.9,
    }

    save_game(ctx, mode="city", city_id="earth", system_id="sol")
    loaded = load_game(ctx.context)

    assert loaded.npc_credit == {"m1": 0.5}, (
        "the patrol mid's credit survives; the watch key drops"
    )


def test_line_defiance_fields_round_trip(monkeypatch, tmp_path):
    """Doc 41 phase 3: the defiance record AND the complying latch
    survive save/quit/Continue (ruling 1 + ruling 4's hardened
    form — no save-scummed lies)."""
    monkeypatch.setattr(
        "src.spacehack.saveload._autosave_path",
        lambda: tmp_path / "autosave.json",
    )
    from src.spacehack.engine import RNG
    RNG.seed(42)

    ctx = _build_test_ctx()
    ctx.line_defiance_system = "luyten_star"
    ctx.line_comply_latch = True

    save_game(ctx, mode="city", city_id="earth", system_id="sol")
    loaded = load_game(ctx.context)

    assert loaded.line_defiance_system == "luyten_star"
    assert loaded.line_comply_latch is True


def test_legacy_save_without_rumor_ledgers_loads_empty(monkeypatch, tmp_path):
    """Doc 42: pre-phase-2 saves restore with an empty ledger book —
    the favor economy starts at zero, never on stale state."""
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
    payload.pop("rumor_favor", None)
    path.write_text(json.dumps(payload))

    loaded = load_game(ctx.context)

    assert loaded is not None
    assert loaded.rumor_favor == {}
    delete_save()


# ---------------------------------------------------------------------------
# Doc 48 phase 2 — rep-sheet migration (retired civilian, absent consortia)
# ---------------------------------------------------------------------------

class TestReputationSheetMigration:
    """The load path drops retired axes; the true sheet seeds absent
    axes at their start value, worn-ID sheets stay blank paper."""

    def test_true_sheet_drops_civilian_and_seeds_consortium(self):
        from src.spacehack.saveload import _sanitize_rep_sheet
        legacy = {"pirate": -50, "merchant": 20, "civilian": 30, "militia": 60}
        migrated = _sanitize_rep_sheet(legacy, seed_defaults=True)
        assert migrated == {
            "pirate": -50, "merchant": 20, "militia": 60, "consortium": -100,
        }

    def test_true_sheet_never_overwrites_an_existing_consortium(self):
        from src.spacehack.saveload import _sanitize_rep_sheet
        migrated = _sanitize_rep_sheet(
            {"pirate": -50, "consortium": -42}, seed_defaults=True,
        )
        assert migrated["consortium"] == -42

    def test_worn_sheet_drops_civilian_without_seeding(self):
        from src.spacehack.saveload import _sanitize_rep_sheet
        migrated = _sanitize_rep_sheet(
            {"pirate": 40, "civilian": 5}, seed_defaults=False,
        )
        assert migrated == {"pirate": 40}  # absent keys read neutral

    def test_collected_ids_sheets_migrate(self):
        from src.spacehack.saveload import _migrate_worn_sheet
        entry = {"id": "SC-1234", "kind": "scrubbed",
                 "rep": {"pirate": 40, "civilian": 5, "merchant": 0}}
        assert _migrate_worn_sheet(entry) == {
            "id": "SC-1234", "kind": "scrubbed",
            "rep": {"pirate": 40, "merchant": 0},
        }

    def test_sheetless_entries_untouched(self):
        from src.spacehack.saveload import _migrate_worn_sheet
        entry = {"id": "SC-9999", "kind": "cloned"}
        assert _migrate_worn_sheet(entry) == {"id": "SC-9999", "kind": "cloned"}

    def test_legacy_civilian_rep_keys_migrate_through_load(
        self, monkeypatch, tmp_path,
    ):
        """A pre-doc-48 save loads with civilian dropped from BOTH rep
        stores and the consortium axis seeded at −100 on the true
        sheet only (worn sheets stay blank paper)."""
        monkeypatch.setattr(
            "src.spacehack.saveload._autosave_path",
            lambda: tmp_path / "autosave.json",
        )
        from src.spacehack.engine import RNG
        RNG.seed(62)
        ctx = _build_test_ctx()
        ctx.collected_ids = [{
            "id": "SC-1234", "kind": "scrubbed", "faction": None,
            "rep": {"pirate": 40, "merchant": 0,
                    "militia": 0, "civilian": 5},
        }]
        save_game(ctx, mode="city", city_id="earth", system_id="sol")
        import json
        path = tmp_path / "autosave.json"
        payload = json.loads(path.read_text())
        payload["faction_reputation"] = {
            "pirate": -50, "merchant": 25, "civilian": 30, "militia": 60,
        }
        path.write_text(json.dumps(payload))

        loaded = load_game(ctx.context)

        assert loaded is not None
        assert loaded.faction_reputation == {
            "pirate": -50, "merchant": 25, "militia": 60,
            "consortium": -100,
        }
        entry = loaded.collected_ids[0]
        assert entry["rep"] == {"pirate": 40, "merchant": 0, "militia": 0}
        delete_save()


class TestSpeciesGlyphRoundTrip:
    """Doc 49: the exotic player glyphs (&, ♦, Q) survive save/load —
    every load-rebuild path threads character_info's species_id into
    the walker entity; the transient player is identified by NAME,
    never by a hardcoded '@'."""

    def _round_trip(self, monkeypatch, tmp_path, species_id):
        monkeypatch.setattr(
            "src.spacehack.saveload._autosave_path",
            lambda: tmp_path / "autosave.json",
        )
        from src.spacehack.engine import RNG
        RNG.seed(42)
        ctx = _build_test_ctx()
        ctx.character_info = {
            **ctx.character_info,
            "species_id": species_id,
            "species_name": species_id.title(),
        }
        save_game(ctx, mode="city", city_id="earth", system_id="sol")
        loaded = load_game(ctx.context)
        delete_save()
        import src.spacehack.solar_system as _ss
        _ss.current_solar_system_id = "sol"
        return loaded

    def test_cygnian_ampersand_survives(self, monkeypatch, tmp_path):
        loaded = self._round_trip(monkeypatch, tmp_path, "cygnian")
        assert loaded.player.char == "&"
        assert loaded.player.name == "Player"

    def test_lalandan_q_survives(self, monkeypatch, tmp_path):
        loaded = self._round_trip(monkeypatch, tmp_path, "lalandan")
        assert loaded.player.char == "Q"

    def test_sirian_diamond_survives(self, monkeypatch, tmp_path):
        loaded = self._round_trip(monkeypatch, tmp_path, "sirian")
        assert loaded.player.char == "\u2666"

    def test_unknown_species_falls_back_to_at(self, monkeypatch, tmp_path):
        """A stale save's unknown species id renders the safe default."""
        loaded = self._round_trip(monkeypatch, tmp_path, "removed_species")
        assert loaded.player.char == "@"


def test_dungeon_serialization_drops_only_the_named_player():
    """The player-id refactor's bite: a NON-player entity wearing '@'
    survives dungeon serialization; the transient player — whatever
    glyph it wears — does not."""
    from src.spacehack.saveload_maps import _dungeon_to_dict

    _tiles = []
    gm = GameMap(width=2, height=1, tiles=_tiles, entities=[
        Entity(char="Q", fg=(255, 130, 195), pos=Position(0, 0), name="Player"),
        Entity(char="@", fg=(255, 255, 255), pos=Position(1, 0), name="statue"),
    ])
    data = _dungeon_to_dict(gm, None)
    names = {e["name"] for e in data["entities"]}
    assert names == {"statue"}


def test_cygnian_glyph_survives_dungeon_round_trip(monkeypatch, tmp_path):
    """Dungeon-mode Continue rebuilds the walker with the saved species'
    glyph (the _rebuild_dungeon threading, distinct from the city path)."""
    monkeypatch.setattr(
        "src.spacehack.saveload._autosave_path",
        lambda: tmp_path / "autosave.json",
    )
    from src.spacehack.engine import RNG
    RNG.seed(7)
    ctx = _build_test_ctx()
    ctx.character_info = {
        **ctx.character_info, "species_id": "cygnian",
        "species_name": "Cygnian",
    }
    tiles = [[world.DUNGEON_FLOOR for _ in range(8)] for _ in range(8)]
    dungeon_map = GameMap(8, 8, tiles, [])
    ctx.player = Entity("&", (170, 130, 230), Position(3, 3), name="Player")
    dungeon_map.entities.append(ctx.player)
    ctx.game_map = dungeon_map

    save_game(ctx, mode="dungeon", city_id="earth", system_id="sol",
              space_player_pos=(2, 2))
    loaded = load_game(ctx.context)
    delete_save()
    import src.spacehack.solar_system as _ss
    _ss.current_solar_system_id = "sol"

    assert loaded is not None
    assert loaded.player.char == "&"


def test_shipless_space_walker_wears_the_species_glyph():
    """The no-ship space branch of _build_space_map threads species_id
    into the walker (the pinned city/dungeon paths' sibling)."""
    from src.spacehack.saveload_maps import _build_space_map

    built = _build_space_map(
        "sol", SimpleNamespace(add=lambda _m: None), None, {}, {}, {},
        10, 10, species_id="sirian",
    )
    assert built is not None
    assert built[1].name == "Player"
    assert built[1].char == "\u2666"


def test_doubled_missile_reserve_booking_survives_the_load_path():
    """Doc 49 phase 2 (BH racks x2): the saved ammo booking is
    authoritative on load — the ctx-free __post_init__ recompute
    cannot know the doubled reserve."""
    from src.spacehack.saveload import _parse_owned_ship

    from src.spacehack.ship import StoredEquipment
    _src = OwnedShip(
        ship_id="starter",
        weapons=(StoredEquipment("weapon", "light_missile"),),
        weapon_ammo={3: 8},
    )
    # Post-construction, like every hunter path (the ctx-free
    # __post_init__ recompute would overwrite a constructor value).
    _src.cargo_ammo = 16
    _saved = _d({"player_owned_ship": _src})
    assert _saved["player_owned_ship"]["cargo_ammo"] == 16  # save side
    owned = _parse_owned_ship(_saved)
    assert owned.weapon_ammo[3] == 8  # the saved rack, not re-seeded
    assert owned.cargo_ammo == 16


class TestFittingGridRoundTrip:
    """Doc 56 phase 2: placements ride the installed entries; storage
    payloads never carry placement keys; loads normalize illegal
    grids deterministically (SETTLED 11/14)."""

    def _save_and_load(self, monkeypatch, tmp_path, ctx):
        monkeypatch.setattr(
            "src.spacehack.saveload._autosave_path",
            lambda: tmp_path / "autosave.json",
        )
        save_game(ctx, mode="city", city_id="earth", system_id="sol")
        return load_game(ctx.context)

    def _fitted_scout_ctx(self):
        ctx = _build_test_ctx()
        ctx.player_owned_ship = OwnedShip(
            ship_id="scout",
            weapons=(StoredEquipment("weapon", "light_missile", grid_x=0, grid_y=0),),
            modules=(
                StoredEquipment("module", "compact_reactor", grid_x=1, grid_y=0),
                StoredEquipment("module", "shield_mk1", grid_x=2, grid_y=0),
            ),
        )
        ctx.ship_storage = [StoredEquipment("module", "armor_plating", quality=3)]
        return ctx

    def test_placed_grid_survives_exactly(self, monkeypatch, tmp_path):
        loaded = self._save_and_load(monkeypatch, tmp_path, self._fitted_scout_ctx())
        ship = loaded.player_owned_ship
        assert [(e.item_id, e.grid_x, e.grid_y) for e in ship.weapons] == [
            ("light_missile", 0, 0),
        ]
        assert [(e.item_id, e.grid_x, e.grid_y) for e in ship.modules] == [
            ("compact_reactor", 1, 0), ("shield_mk1", 2, 0),
        ]
        # Ammo booking rides the same indices.
        assert 0 in ship.weapon_ammo

    def test_hand_placed_anchors_survive_exactly(self, monkeypatch, tmp_path):
        """Doc 56 phase 3: anchors the EDITOR placed (never first_fit's
        row-major choices) are what serialize — the save never
        re-derives placement."""
        ctx = self._fitted_scout_ctx()
        # Re-anchor everything OFF the first_fit row-major spots.
        ctx.player_owned_ship = OwnedShip(
            ship_id="scout",
            weapons=(StoredEquipment("weapon", "light_missile", grid_x=3, grid_y=0),),
            modules=(
                StoredEquipment("module", "compact_reactor", grid_x=0, grid_y=0),
                StoredEquipment("module", "shield_mk1", grid_x=1, grid_y=1),
            ),
        )
        loaded = self._save_and_load(monkeypatch, tmp_path, ctx)
        ship = loaded.player_owned_ship
        assert [(e.item_id, e.grid_x, e.grid_y) for e in ship.weapons] == [
            ("light_missile", 3, 0),
        ]
        assert [(e.item_id, e.grid_x, e.grid_y) for e in ship.modules] == [
            ("compact_reactor", 0, 0), ("shield_mk1", 1, 1),
        ]

    def test_storage_payloads_carry_no_placement_keys(self, monkeypatch, tmp_path):
        import json as _json
        path = tmp_path / "autosave.json"
        monkeypatch.setattr(
            "src.spacehack.saveload._autosave_path", lambda: path,
        )
        ctx = self._fitted_scout_ctx()
        save_game(ctx, mode="city", city_id="earth", system_id="sol")
        raw = _json.loads(path.read_text())
        # Stored items have no position: their payloads carry NO
        # placement keys, whatever else rides the entry shape.
        assert len(raw["ship_storage"]) == 1
        assert raw["ship_storage"][0]["item_id"] == "armor_plating"
        assert "grid_x" not in raw["ship_storage"][0]
        assert "grid_y" not in raw["ship_storage"][0]
        # Installed entries DO carry their anchors.
        assert raw["player_owned_ship"]["weapons"][0]["grid_x"] == 0
        assert raw["player_owned_ship"]["weapons"][0]["grid_y"] == 0

    def test_old_shape_save_strips_with_notice(self, monkeypatch, tmp_path):
        ctx = _build_test_ctx()
        ctx.player_owned_ship = OwnedShip(
            ship_id="scout",
            weapons=(StoredEquipment("weapon", "light_laser"),),
            modules=(StoredEquipment("module", "shield_mk1"),),
        )
        ctx.ship_storage = []
        loaded = self._save_and_load(monkeypatch, tmp_path, ctx)
        ship = loaded.player_owned_ship
        assert ship.weapons == () and ship.modules == ()
        assert loaded.ship_storage == [
            StoredEquipment("weapon", "light_laser"),
            StoredEquipment("module", "shield_mk1"),
        ]
        assert "Fitted gear moved to storage: Light Laser, Shield Mk. 1." in [
            entry.text for entry in loaded.log.history()
        ]

    def _rewrite_ship(self, monkeypatch, tmp_path, ctx, weapons, modules):
        import json as _json
        path = tmp_path / "autosave.json"
        monkeypatch.setattr(
            "src.spacehack.saveload._autosave_path", lambda: path,
        )
        save_game(ctx, mode="city", city_id="earth", system_id="sol")
        raw = _json.loads(path.read_text())
        raw["player_owned_ship"]["weapons"] = weapons
        raw["player_owned_ship"]["modules"] = modules
        path.write_text(_json.dumps(raw))
        return load_game(ctx.context)

    def test_power_invalid_save_normalizes_highest_upkeep_first(
        self, monkeypatch, tmp_path,
    ):
        ctx = _build_test_ctx()
        ctx.player_owned_ship = OwnedShip(ship_id="scout")
        ctx.ship_storage = []
        # Scout 3 - 3 (shield_mk3) - 1 (targeting) = -1: the shield is
        # the highest-upkeep offender and strips, leaving net +2.
        loaded = self._rewrite_ship(
            monkeypatch, tmp_path, ctx,
            weapons=[],
            modules=[
                {"item_id": "shield_mk3", "grid_x": 0, "grid_y": 0},
                {"item_id": "targeting_computer", "grid_x": 2, "grid_y": 0},
            ],
        )
        assert [e.item_id for e in loaded.player_owned_ship.modules] == [
            "targeting_computer",
        ]
        assert loaded.ship_storage == [
            StoredEquipment("module", "shield_mk3"),
        ]

    def test_overlapping_save_strips_module_in_cross_tuple_overlap(
        self, monkeypatch, tmp_path,
    ):
        ctx = _build_test_ctx()
        ctx.player_owned_ship = OwnedShip(ship_id="scout")
        ctx.ship_storage = []
        loaded = self._rewrite_ship(
            monkeypatch, tmp_path, ctx,
            weapons=[{"item_id": "heavy_laser", "grid_x": 0, "grid_y": 0}],
            modules=[{"item_id": "shield_mk1", "grid_x": 0, "grid_y": 0}],
        )
        assert [e.item_id for e in loaded.player_owned_ship.weapons] == ["heavy_laser"]
        assert loaded.player_owned_ship.modules == ()
        assert loaded.ship_storage == [StoredEquipment("module", "shield_mk1")]
