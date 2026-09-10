"""Tests for npc_ships movement (combat locks, cohesion, spawn
caps) and the doc-44 map-speed resolver + its load-path gate."""

from __future__ import annotations

import sys
from pathlib import Path
from dataclasses import replace
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


def test_cohesion_does_not_undo_patrol_progress(monkeypatch):
    """The space cohesion pull never yanks back a member that just
    took a patrol step — the pack keeps flowing (the tau_ceti freeze)."""
    _tiles = [[world.DUNGEON_FLOOR for _ in range(40)] for _ in range(30)]
    _game_map = world.GameMap(40, 30, _tiles, [])
    _straggler = _pirate_entity(world.Position(5, 18), "squad_c")
    _mate_a = _pirate_entity(world.Position(14, 8), "squad_c")
    _mate_b = _pirate_entity(world.Position(16, 9), "squad_c")
    _game_map.entities.extend((_straggler, _mate_a, _mate_b))

    _ctx = _ctx_with(world.Position(30, 15))
    _ctx.npc_targets["squad_c"] = (30, 15)
    _ctx.npc_paths["squad_c"] = [(6, 18)]  # leader steps east

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

    # All three moved east via patrol; the centre is ~6 cells further
    # east, so a cohesion pull would have yanked them back. It doesn't.
    assert _straggler.pos == world.Position(6, 18)
    assert _mate_a.pos == world.Position(15, 8)
    assert _mate_b.pos == world.Position(17, 9)


def test_wedged_squad_member_unfreezes_the_pack(monkeypatch):
    """Repro of the tau_ceti save: 3 healthy pirates + 1 member wedged
    against planet tc_d. The pack keeps patrolling (cohesion never
    yanks back a member that just moved) and the wedged member slips
    around the planet instead of freezing everyone."""
    from src.spacehack import solar_system as _ss
    from src.spacehack.data.npc_ships import find_npc_ship as _find_npc_ship
    from src.spacehack.data.solar_systems import find_solar_system as _fss

    _spec = _fss("tau_ceti")
    _ss.set_current_solar_system("tau_ceti")
    _game_map = _ss.make_solar_system(system=_spec)
    _pspec = _find_npc_ship("pirate_scout")
    _squad = "wedged_test"
    for _x, _y in ((135, 102), (135, 103), (135, 101), (154, 102)):
        _game_map.entities.append(world.Entity(
            _pspec.char, _pspec.fg, world.Position(_x, _y),
            name=_pspec.name, width=1, height=1,
            npc_ship_id=_pspec.id, procedural_squad_id=_squad,
        ))

    _ctx = _ctx_with(world.Position(144, 119))
    _ctx.npc_targets[_squad] = (58, 46)

    class _RNG:
        """Always move (0.5 < 0.8 gate); never per-tick spawn."""

        def random(self) -> float:
            return 0.5

        def choice(self, seq):
            return seq[0]

        def randint(self, a: int, b: int) -> int:
            return a

    monkeypatch.setattr(npc_ships._engine, "RNG", _RNG())
    monkeypatch.setattr(
        npc_ships, "_solar_module",
        SimpleNamespace(current_system=lambda: _spec),
    )
    monkeypatch.setattr(
        npc_ships, "main_quest_module",
        SimpleNamespace(
            consortium_heat_active=lambda _ctx: False,
            charged_cell_in_sol=lambda _ctx, _sid: False,
        ),
    )

    for _ in range(40):
        npc_ships.move_npcs(_ctx, _game_map)

    _members = [
        e for e in _game_map.entities
        if getattr(e, "procedural_squad_id", "") == _squad
    ]
    assert len(_members) == 4
    _healthy = sorted(_members, key=lambda m: m.pos.x)[:3]
    _wedged = [m for m in _members if m not in _healthy][0]
    # The pack made real progress toward the west target (~40 cells).
    assert all(m.pos.x < 130 for m in _healthy), \
        [(m.pos.x, m.pos.y) for m in _healthy]
    # The wedged member escaped the planet's east edge and moved west.
    assert _wedged.pos != world.Position(154, 102)
    assert _wedged.pos.x < 154


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


# ---------------------------------------------------------------------------
# map_speed + hull-derived speeds (doc 44 phase 1)
# ---------------------------------------------------------------------------

def test_map_speed_derives_from_the_hull_and_explicit_wins():
    """Doc 44: an NPC's map speed is the hull's own speed stat —
    the same number a player flying that hull gets. Explicit
    authoring wins (derelicts pin 0); unknown hulls never raise."""
    from src.spacehack.data.npc_ships import NpcShipSpec, map_speed
    from src.spacehack.data.ships import find_ship

    spec = NpcShipSpec(
        id="test_derived", name="T", char="T", fg=(255, 255, 255),
        ship_id="cruiser", faction="pirate",
    )
    assert spec.base_speed is None
    assert map_speed(spec) == find_ship("cruiser").speed == 9

    pinned = replace(spec, base_speed=0)
    assert map_speed(pinned) == 0, "derelicts' explicit 0 wins"

    unknown = replace(spec, ship_id="not_a_hull")
    assert map_speed(unknown) == 1, "an unknown hull resolves, never raises"


def test_every_spec_resolves_hull_speed_with_named_pins():
    """The launch table: every registered spec moves at its hull's
    speed (doc 44's settled table). militia_blockade is NAMED —
    phase 4's retune premise is picket speed 9, and a hull-grouped
    assert alone could pass without ever naming the picket."""
    from src.spacehack.data.npc_ships import (
        find_npc_ship, list_npc_ships, map_speed,
    )
    from src.spacehack.data.ships import find_ship

    specs = list_npc_ships()
    assert len(specs) >= 15, "the catalog is discovered in full"

    for spec in specs:
        if spec.base_speed is not None:
            assert map_speed(spec) == spec.base_speed
        else:
            assert map_speed(spec) == find_ship(spec.ship_id).speed

    assert map_speed(find_npc_ship("militia_blockade")) == 9
    assert map_speed(find_npc_ship("pirate_scout")) == 14
    assert map_speed(find_npc_ship("merchant_freighter")) == 6
    assert map_speed(find_npc_ship("derelict_scout")) == 0


def test_load_gate_reads_through_the_resolver():
    """The ADVISE blocker, pinned at its seam: base_speed is
    None-able now, and the load-path stationary gate must read
    map_speed (the old getattr default never fired for a PRESENT
    None — `None > 0` raised on every load with a live procedural
    NPC). A pirate keeps its squad id and moves; a derelict gets
    none."""
    from src.spacehack.data.npc_ships import find_npc_ship
    from src.spacehack.game_context import ProceduralSpawn
    from src.spacehack.saveload_maps import _add_procedural_npcs
    from src.spacehack.solar_system import make_solar_system
    from src.spacehack.data.solar_systems import find_solar_system

    game_map = make_solar_system(system=find_solar_system("sol"))
    spawns = [
        ProceduralSpawn(npc_id="pirate_scout",
                        pos=world.Position(30, 30), squad_id="m1"),
        ProceduralSpawn(npc_id="derelict_scout",
                        pos=world.Position(35, 35), squad_id="d1"),
    ]

    _add_procedural_npcs(game_map, spawns, "sol", {}, find_npc_ship)

    by_id = {_e.npc_ship_id: _e for _e in game_map.entities}
    assert by_id["pirate_scout"].procedural_squad_id == "m1"
    assert by_id["derelict_scout"].procedural_squad_id == "", (
        "the stationary gate still holds through the resolver"
    )
