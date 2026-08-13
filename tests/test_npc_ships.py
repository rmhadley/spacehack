"""Tests for npc_ships.move_npcs combat-lock skipping.

Space-combat participants carry a transient ``combat_locked`` flag
(set by combat/_rules_space.py at every reinforcement tick) so the
ambient patrol system leaves them alone mid-fight — otherwise they
drift toward body goals or despawn at gates/planets while the combat
instance still considers them alive (the "enemy disappeared" bug).
"""

from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.spacehack import npc_ships, world


class _RNGStub:
    """Forces the 80% move gate to always pass; deterministic picks."""

    def random(self) -> float:
        return 0.0

    def choice(self, seq):
        return seq[0]

    def randint(self, a: int, b: int) -> int:
        return a


def _ctx_with(player_pos):
    return SimpleNamespace(
        player=world.Entity("@", (255, 255, 255), player_pos, "Player", owned=True),
        log=SimpleNamespace(add=lambda _m: None, add_colored=lambda _m, _c: None),
        procedural_spawns={"sol": []},
        npc_targets={},
        npc_paths={},
        npc_flash_events=[],
    )


def _system():
    return SimpleNamespace(
        id="sol", width=40, height=30,
        planets=[
            SimpleNamespace(
                pos=world.Position(5, 5), width=2, height=2,
                name="Earth", sun=False,
            ),
        ],
        jump_points=[],
        stations=[],
        npc_spawn_chance=0.0,  # no per-tick spawn rolls
        npc_density=1,
        npc_spawn_table=[],
        patrol_density=(0, 0),
    )


def _pirate_entity(pos, squad_id: str) -> world.Entity:
    return world.Entity(
        "P", (255, 100, 100), pos, "Pirate Scout",
        width=1, height=1,
        npc_ship_id="pirate_scout",
        procedural_squad_id=squad_id,
    )


def test_move_npcs_skips_combat_locked_entities(monkeypatch):
    _tiles = [[world.DUNGEON_FLOOR for _ in range(40)] for _ in range(30)]
    _game_map = world.GameMap(40, 30, _tiles, [])
    _locked = _pirate_entity(world.Position(20, 15), "squad_a")
    _free = _pirate_entity(world.Position(10, 15), "squad_b")
    _locked.combat_locked = True
    _game_map.entities.extend((_locked, _free))

    _ctx = _ctx_with(world.Position(30, 15))
    # Pre-computed adjacent paths: deterministic movement, no A* needed.
    _ctx.npc_targets["squad_a"] = (30, 15)
    _ctx.npc_paths["squad_a"] = [(21, 15)]
    _ctx.npc_targets["squad_b"] = (30, 15)
    _ctx.npc_paths["squad_b"] = [(11, 15)]

    monkeypatch.setattr(npc_ships._engine, "RNG", _RNGStub())
    monkeypatch.setattr(
        npc_ships, "_solar_module",
        SimpleNamespace(current_system=_system),
    )
    monkeypatch.setattr(
        npc_ships, "main_quest_module",
        SimpleNamespace(
            consortium_heat_active=lambda _ctx: False,
            charged_cell_in_sol=lambda _ctx, _sid: False,
        ),
    )

    npc_ships.move_npcs(_ctx, _game_map)

    # The combat participant is frozen; the free ship patrolled.
    assert _locked.pos == world.Position(20, 15)
    assert _free.pos == world.Position(11, 15)


def test_squad_cohesion_steps_one_cell_toward_centre(monkeypatch):
    """The space cohesion pull steps a straggler ONE cell per tick —
    the visible squad member can no longer snap across the system."""
    _tiles = [[world.DUNGEON_FLOOR for _ in range(40)] for _ in range(30)]
    _game_map = world.GameMap(40, 30, _tiles, [])
    _straggler = _pirate_entity(world.Position(5, 18), "squad_c")
    _mate_a = _pirate_entity(world.Position(14, 8), "squad_c")
    _mate_b = _pirate_entity(world.Position(16, 9), "squad_c")
    _game_map.entities.extend((_straggler, _mate_a, _mate_b))

    _ctx = _ctx_with(world.Position(30, 15))
    _ctx.npc_targets["squad_c"] = (30, 15)
    _ctx.npc_paths["squad_c"] = [(6, 18)]  # leader steps east, then cohesion

    monkeypatch.setattr(npc_ships._engine, "RNG", _RNGStub())
    monkeypatch.setattr(
        npc_ships, "_solar_module",
        SimpleNamespace(current_system=_system),
    )
    monkeypatch.setattr(
        npc_ships, "main_quest_module",
        SimpleNamespace(
            consortium_heat_active=lambda _ctx: False,
            charged_cell_in_sol=lambda _ctx, _sid: False,
        ),
    )

    npc_ships.move_npcs(_ctx, _game_map)

    # Patrol: (5,18) -> (6,18). Cohesion: at most one cell further
    # (no (13, 10) snap to centre+1).
    assert max(abs(_straggler.pos.x - 6), abs(_straggler.pos.y - 18)) == 1


def test_move_npcs_counts_locked_ships_against_spawn_cap(monkeypatch):
    """Locked ships are still on the map — the density cap counts them.

    With density=1 the cap is 3. Three locked ships fill the cap, so
    the per-tick spawn roll must NOT add a fourth ship; if the count
    wrongly excluded locked ships, 0 < 3 would pass and a new pirate
    would spawn (npc_spawn_chance=1.0 forces the roll to hit).
    """
    _tiles = [[world.DUNGEON_FLOOR for _ in range(40)] for _ in range(30)]
    _game_map = world.GameMap(40, 30, _tiles, [])
    for _i in range(3):
        _locked = _pirate_entity(world.Position(15 + _i, 15), f"squad_{_i}")
        _locked.combat_locked = True
        _game_map.entities.append(_locked)

    _ctx = _ctx_with(world.Position(30, 15))

    monkeypatch.setattr(npc_ships._engine, "RNG", _RNGStub())
    _sys = _system()
    _sys.npc_spawn_chance = 1.0
    _sys.npc_spawn_table = [("pirate_scout", 1.0)]
    monkeypatch.setattr(
        npc_ships, "_solar_module",
        SimpleNamespace(current_system=lambda: _sys),
    )
    monkeypatch.setattr(
        npc_ships, "main_quest_module",
        SimpleNamespace(
            consortium_heat_active=lambda _ctx: False,
            charged_cell_in_sol=lambda _ctx, _sid: False,
        ),
    )

    npc_ships.move_npcs(_ctx, _game_map)

    assert len(_game_map.entities) == 3  # cap respected — no 4th ship
    assert all(
        _e.pos.x == 15 + _i for _i, _e in enumerate(_game_map.entities)
    )  # none of the locked ships moved
