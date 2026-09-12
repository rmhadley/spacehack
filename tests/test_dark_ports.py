"""The dark-ports discovery beats (doc 42 phase 2.5 / phase 3).

The dock credential line, the silent hail, the dark-hull spawn stamp
and its save/load round-trip, and the broadcast suppression — every
door into the chain through the one hearing path.
"""

import sys
from types import SimpleNamespace

from src.spacehack import game_interactions
from src.spacehack import identity
from src.spacehack import npc_ships
from src.spacehack import rumor
from src.spacehack.message_log import MessageLog
from src.spacehack.saveload import _d, _parse_procedural_spawns
from src.spacehack.saveload_maps import _add_procedural_npcs
from src.spacehack.world import Entity, GameMap, Position


def _ctx(known=None):
    return SimpleNamespace(
        known_rumors=list(known or []), rumor_favor={}, log=MessageLog(),
        context=None,
    )


class _ContactSpec:
    """A stand-in contact spec with no comms lines."""


def _quiet_present(monkeypatch):
    """Capture presentations on every loaded rumor module instance."""
    seen = []
    for name in ("spacehack.rumor", "src.spacehack.rumor"):
        mod = sys.modules.get(name)
        if mod is not None:
            monkeypatch.setattr(
                mod, "present_hearing",
                lambda ctx, title, text: seen.append((title, text)),
            )
    return seen


def test_dock_beat_logs_every_landing_and_hears_once(monkeypatch):
    seen = _quiet_present(monkeypatch)
    ctx = _ctx()
    # A dark port: the line logs...
    game_interactions._dark_port_landing_beat(ctx, ctx.log, "lal_c")
    assert "This port didn't verify any credentials." in [
        e.text for e in ctx.log.history()
    ]
    assert ctx.known_rumors == ["dark_berth_1"]
    assert seen == [("dark ports", rumor.entry_text("dark_berth_1"))]
    # ...on EVERY landing (the militia-scan cadence; the log collapses
    # the repeat with its x2 marker)...
    game_interactions._dark_port_landing_beat(ctx, ctx.log, "lal_c")
    assert any(
        e.text.startswith("This port didn't verify any credentials.")
        for e in ctx.log.history()
    )
    # ...while the trigger hears once.
    assert ctx.known_rumors == ["dark_berth_1"]
    assert len(seen) == 1


def test_dock_beat_silent_at_lawful_ports(monkeypatch):
    _quiet_present(monkeypatch)
    ctx = _ctx()
    game_interactions._dark_port_landing_beat(ctx, ctx.log, "earth")
    assert ctx.known_rumors == []
    assert ctx.log.history() == []


def test_hailing_a_dark_hull_fires_the_trigger(monkeypatch):
    from src.spacehack import comms

    seen = _quiet_present(monkeypatch)
    monkeypatch.setattr(
        comms, "_pygame_interaction_outcome", lambda *a, **k: None,
    )
    monkeypatch.setattr(
        comms, "_handle_interaction", lambda *a, **k: None,
    )
    ctx = _ctx()
    comms._run_interaction_modal(
        ctx, None, "Pirate Raider", SimpleNamespace(), SimpleNamespace(),
    )
    assert ctx.known_rumors == []
    dark_contact = SimpleNamespace(flies_dark=True)
    comms._run_interaction_modal(
        ctx, None, "Pirate Raider", _ContactSpec(), dark_contact,
    )
    assert ctx.known_rumors == ["dark_berth_1"]
    assert seen == [("dark ports", rumor.entry_text("dark_berth_1"))]


def test_dark_entities_broadcast_nothing():
    hull = Entity(
        "R", (255, 80, 80), Position(0, 0), "Pirate Raider",
        npc_ship_id="pirate_raider",
    )
    assert identity.npc_identity(hull) is not None
    hull.flies_dark = True
    assert identity.npc_identity(hull) is None


def test_stamp_dark_groups_marks_only_members():
    game_map = GameMap(10, 10, [], [])
    dark_ent = Entity("R", (255, 80, 80), Position(1, 1), "A",
                      npc_ship_id="pirate_raider")
    dark_ent.procedural_squad_id = "dark_group"
    bright_ent = Entity("R", (255, 80, 80), Position(2, 2), "B",
                        npc_ship_id="pirate_raider")
    bright_ent.procedural_squad_id = "bright_group"
    game_map.entities.extend([dark_ent, bright_ent])
    npc_ships._stamp_dark_groups(game_map, frozenset({"dark_group"}))
    assert dark_ent.flies_dark is True
    assert bright_ent.flies_dark is False


def test_dark_spawn_stamp_round_trips_through_save_parse_and_load():
    from src.spacehack.game_context import ProceduralSpawn

    spawn = ProceduralSpawn(
        npc_id="pirate_raider", pos=Position(3, 4),
        squad_id="proc_npc_sol_pirate_raider_1", flies_dark=True,
    )
    parsed, _mids, _targets, _paths = _parse_procedural_spawns({
        "procedural_spawns": _d({"sol": [spawn]}),
    })
    assert parsed["sol"][0].flies_dark is True

    game_map = GameMap(20, 20, [], [])
    _add_procedural_npcs(
        game_map, parsed["sol"], "sol", {"sol": [spawn.squad_id]},
        npc_ships._find_npc_ship,
    )
    restored = next(
        e for e in game_map.entities if e.procedural_squad_id == spawn.squad_id
    )
    assert restored.flies_dark is True
