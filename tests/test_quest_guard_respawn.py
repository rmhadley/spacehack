"""A destroyed quest guard patrol must not respawn on system re-entry.

Regression: killing the survey-wreck patrol, landing, saving, loading and
launching brought it back for infinite XP/credit farming. Guard records
were never cleaned up on kill for main-quest salvage steps (only step
completion cleans them), and ensure_quest_spawns rebuilds the group
whenever the leader record is missing while the step is live. The fix
tombstones defeated records: they stay (blocking group rebuild) but are
never re-stamped as entities.
"""

from __future__ import annotations

from types import SimpleNamespace

from src.spacehack import message_log, world
from src.spacehack.data.main_quest import find_main_quest_step
from src.spacehack.data.solar_systems import find_solar_system
from src.spacehack.main_quest import (
    ensure_quest_spawns,
    mark_quest_guard_defeated,
)
from src.spacehack.navigation_spawns import _add_bounty_spawns_to_map

_LEADER_ID = "mer_consortium_leader"


def _ctx(progress=None, *, chain="merchants"):
    return SimpleNamespace(
        main_quest_progress=progress or {"mer_q6_survey": "active"},
        main_quest_chain=chain,
        bounty_spawns={},
        log=message_log.MessageLog(capacity=6),
    )


def _enter_system(ctx, system_id="vega"):
    """Simulate a system entry: ensure runs, then records stamp entities."""
    ensure_quest_spawns(ctx, system_id)
    system = find_solar_system(system_id)
    game_map = world.GameMap(
        width=system.width, height=system.height,
        tiles=[[world.DUNGEON_FLOOR] * system.width
               for _ in range(system.height)],
        entities=[],
    )
    _add_bounty_spawns_to_map(ctx, game_map, system_id)
    return game_map


def _guards(game_map):
    return [e for e in game_map.entities if getattr(e, "bounty_squad_id", None)]


def _wreck(game_map):
    return [e for e in game_map.entities
            if getattr(e, "salvage_wreck_spawn_id", None)]


def test_killing_the_patrol_leader_destroys_the_whole_patrol():
    ctx = _ctx()
    game_map = _enter_system(ctx)
    step = find_main_quest_step("mer_q6_survey")
    guards = _guards(game_map)
    assert len(guards) == 1 + len(step.bounty_escort_ids)
    assert len(_wreck(game_map)) == 1

    leader = next(
        e for e in guards if getattr(e, "bounty_spawn_id", None) == _LEADER_ID
    )
    mark_quest_guard_defeated(ctx, leader)

    # Re-entry (land, save, load, launch): the patrol stays dead, the
    # wreck stays boardable.
    game_map = _enter_system(ctx)
    assert not _guards(game_map), "destroyed patrol must not respawn"
    assert len(_wreck(game_map)) == 1

    # The leader record survives as a tombstone so ensure_quest_spawns
    # can't rebuild the group while the step is still live.
    leaders = [bs for bs in ctx.bounty_spawns["vega"]
               if bs.spawn_id == _LEADER_ID]
    assert len(leaders) == 1 and leaders[0].defeated


def test_killing_one_escort_tombstones_only_that_escort():
    ctx = _ctx()
    game_map = _enter_system(ctx)
    escorts = [
        e for e in _guards(game_map)
        if getattr(e, "bounty_spawn_id", None) is None
    ]
    assert len(escorts) == 2

    mark_quest_guard_defeated(ctx, escorts[0])

    game_map = _enter_system(ctx)
    remaining = _guards(game_map)
    assert len(remaining) == 2, "leader + surviving escort only"
    assert any(
        getattr(e, "bounty_spawn_id", None) == _LEADER_ID
        for e in remaining
    )


def test_non_quest_squad_kills_are_ignored():
    ctx = _ctx()
    procedural_wingmate = SimpleNamespace(
        bounty_squad_id="bounty_mission_42", npc_ship_id="pirate_raider",
    )
    mark_quest_guard_defeated(ctx, procedural_wingmate)
    assert ctx.bounty_spawns == {}


def test_defeated_tombstone_survives_save_round_trip():
    from src.spacehack.saveload import _d, _parse_bounty_spawns
    from src.spacehack.game_context import BountySpawn

    tombstone = BountySpawn(
        spawn_id=_LEADER_ID, enemy_id="pirate_captain",
        pos=world.Position(3, 4), defeated=True,
    )
    parsed = _parse_bounty_spawns(
        {"bounty_spawns": _d({"vega": [tombstone]})}
    )["vega"][0]
    assert parsed.defeated is True

def test_survey_spawns_wait_for_the_alloy_step():
    """The Vega patrol + wreck cannot exist before the alloy is collected
    (playtest v14: the recorder could be secured with no alloy in the
    hold, permanently skipping the specialist's handover)."""
    ctx = _ctx({"mer_q5_alloy": "available"})
    game_map = _enter_system(ctx)
    assert not _guards(game_map) and not _wreck(game_map)
    assert not ctx.bounty_spawns.get("vega")

    ready = _ctx({"mer_q5_alloy": "completed", "mer_q6_survey": "available"})
    game_map = _enter_system(ready)
    assert len(_guards(game_map)) == 3
    assert len(_wreck(game_map)) == 1

def test_loading_a_save_does_not_resurrect_tombstoned_guards():
    """Regression (playtest v14): the load path has its own entity
    stamper (_add_bounty_npcs) which ignored the tombstones and brought
    the destroyed patrol back with full combat linkage."""
    from src.spacehack.game_context import BountySpawn
    from src.spacehack.data.npc_ships import find_npc_ship
    from src.spacehack.saveload_maps import _add_bounty_npcs

    spawns = [
        BountySpawn(
            spawn_id=_LEADER_ID, enemy_id="pirate_captain",
            pos=world.Position(10, 10), defeated=True,
        ),
        BountySpawn(
            spawn_id=f"{_LEADER_ID}_esc_0", enemy_id="pirate_raider",
            pos=world.Position(12, 10), squad_group_id=_LEADER_ID,
            defeated=True,
        ),
        BountySpawn(
            spawn_id=f"{_LEADER_ID}_wreck", enemy_id="derelict_scout",
            pos=world.Position(15, 10), salvage_wreck=True,
        ),
    ]
    game_map = world.GameMap(
        width=40, height=40,
        tiles=[[world.DUNGEON_FLOOR] * 40 for _ in range(40)],
        entities=[],
    )

    _add_bounty_npcs(game_map, spawns, find_npc_ship)

    stamped = game_map.entities
    assert [getattr(e, "salvage_wreck_spawn_id", None) for e in stamped] == [
        f"{_LEADER_ID}_wreck",
    ], "tombstoned guards must not come back; the wreck must"

    # Live guards still stamp with their combat linkage intact.
    spawns[0] = BountySpawn(
        spawn_id=_LEADER_ID, enemy_id="pirate_captain",
        pos=world.Position(10, 10),
    )
    game_map = world.GameMap(
        width=40, height=40,
        tiles=[[world.DUNGEON_FLOOR] * 40 for _ in range(40)],
        entities=[],
    )
    _add_bounty_npcs(game_map, spawns, find_npc_ship)
    leader = next(
        e for e in game_map.entities
        if getattr(e, "bounty_spawn_id", None) == _LEADER_ID
    )
    assert leader.bounty_squad_id == _LEADER_ID

def test_militia_livefire_squad_tombstones_too():
    """The generic guard tombstone covers the militia live-fire squad:
    an escort killed in a disengaged fight stays dead, and the leader's
    death takes the whole squad (no re-stamping at Cygni)."""
    ctx = _ctx({"mil_q5_livefire": "active"}, chain="militia")
    game_map = _enter_system(ctx, "cygni")
    escorts = [
        e for e in _guards(game_map)
        if getattr(e, "bounty_spawn_id", None) is None
    ]
    assert len(escorts) == 4

    mark_quest_guard_defeated(ctx, escorts[0])

    game_map = _enter_system(ctx, "cygni")
    assert len(_guards(game_map)) == 4, "leader + three escorts remain"

    leader = next(
        e for e in _guards(game_map)
        if getattr(e, "bounty_spawn_id", None) == "mil_livefire_test"
    )
    mark_quest_guard_defeated(ctx, leader)

    game_map = _enter_system(ctx, "cygni")
    assert not _guards(game_map), "the destroyed squad stays destroyed"
