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

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.spacehack.game_context import GameContext
from src.spacehack.hud import HudStats
from src.spacehack.message_log import MessageLog
from src.spacehack.world import GameMap, Entity, Position
from src.spacehack.saveload import save_game, load_game, delete_save


def _build_test_ctx() -> GameContext:
    """Build a minimal GameContext with known state for round-trip testing."""
    mock_ctx = MagicMock()
    gm = GameMap(width=10, height=10, tiles=[], entities=[])
    player = Entity(char="@", fg=(255, 255, 255), pos=Position(5, 5), name="Player")
    gm.entities.append(player)
    stats = HudStats(hp=30, max_hp=30, credits=100)
    log = MessageLog(capacity=6)
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
    ctx.completed_mission_ids = {"m_test_1", "m_test_2"}
    ctx.economy_state = {"earth": {"food": 5, "water": 3}}
    ctx.militia_scanned = {"patrol_1"}
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

    # ---- field-level assertions ----

    def _assert_fields_match(self, original: GameContext, loaded: GameContext) -> None:
        """Compare every field that goes through save/load."""
        # Character info
        assert loaded.character_info == original.character_info

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

        # Economy
        assert loaded.economy_state == original.economy_state

        # Militia
        assert loaded.militia_scanned == original.militia_scanned

        # OwnedShip — default None for a new character
        assert loaded.player_owned_ship is None

        # Active missions — default empty
        assert loaded.player_active_missions == []

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
