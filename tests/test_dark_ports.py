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


# --- pads that teach (doc 42 SETTLED 19) -----------------------------------


def _pad_ctx(known=None, entities=None):
    ctx = _ctx(known)
    ctx.game_map = SimpleNamespace(entities=list(entities or []))
    return ctx


def test_pad_spawns_only_while_unheard():
    from src.spacehack import loot

    ctx = _pad_ctx()
    assert loot.maybe_spawn_pad(ctx, ctx.game_map, Position(5, 5), "pirate_raider") is True
    assert len(ctx.game_map.entities) == 1
    pad = ctx.game_map.entities[0]
    assert pad.loot_data == {"teaches": "dark_berth_1"}
    assert loot._loot_choice_label(pad) == "Data Pad"
    # Heard by another door: no pad. Unknown carrier: no pad.
    heard = _pad_ctx(known=["dark_berth_1"])
    assert loot.maybe_spawn_pad(heard, heard.game_map, Position(5, 5), "pirate_raider") is False
    assert loot.maybe_spawn_pad(ctx, ctx.game_map, Position(5, 5), "militia_patrol") is False


def test_pad_pickup_teaches_presents_and_consumes(monkeypatch):
    from src.spacehack import loot

    seen = _quiet_present(monkeypatch)
    ctx = _pad_ctx()
    loot.maybe_spawn_pad(ctx, ctx.game_map, Position(5, 5), "pirate_raider")
    pad = ctx.game_map.entities[0]
    ctx.game_map.entities.append(
        Entity("@", (255, 255, 255), Position(0, 0), "Player")
    )
    loot._open_single_loot_pickup(ctx, pad)
    assert ctx.known_rumors == ["dark_berth_1"]
    assert pad not in ctx.game_map.entities, "the pad is consumed"
    assert seen == [("dark ports", rumor.entry_text("dark_berth_1"))]


def test_already_heard_pad_consumes_silently(monkeypatch):
    from src.spacehack import loot

    seen = _quiet_present(monkeypatch)
    ctx = _pad_ctx(known=["dark_berth_1"])
    loot.maybe_spawn_pad(_pad_ctx(), ctx.game_map, Position(5, 5), "pirate_raider")
    pad = ctx.game_map.entities[0]
    loot._open_single_loot_pickup(ctx, pad)
    assert ctx.known_rumors == ["dark_berth_1"]
    assert pad not in ctx.game_map.entities
    assert seen == [], "no duplicate readout"


# --- the shady tech (doc 42 phase 2.5: the gated city spawn) ---------------


def test_shady_tech_is_always_at_the_containers():
    """Playtest ruling (user, 2026-09-12): he is ALWAYS there —
    knowledge gates the passphrase row, not his existence."""
    from src.spacehack.data.planets import load_planet

    game_map = load_planet("lal_c")
    tech = [
        e for e in game_map.entities
        if getattr(e, "city_npc_id", "") == "lalc_shady_tech"
    ]
    assert len(tech) == 1
    assert (tech[0].pos.x, tech[0].pos.y) == (80, 66)
    assert tech[0].npc_id == "shady_tech"


def test_shady_tech_anchor_is_walkable_pavement():
    from src.spacehack.data.planets import load_planet

    # By the containers south-east of the bounty office — off the
    # road lane (a stationary blocker belongs beside the lane, not
    # on it).
    game_map = load_planet("lal_c")
    assert game_map.is_walkable(80, 66)


# --- the Shift+N dev instrument (doc 42 phase 3) ----------------------------


def test_log_rumor_routing_names_carriers_and_holder():
    from src.spacehack import dev_mode
    from src.spacehack import engine as engine_mod

    engine_mod.INIT_SEED = 7
    try:
        ctx = _ctx()
        dev_mode.log_rumor_routing(ctx)
        _text = "\n".join(e.text for e in ctx.log.history())
        assert "[DEV] Rumor routing (seed 7):" in _text
        assert "dark_berth_2:" in _text
        assert "exclusive dark_berth_4: held by" in _text
        assert "dark pirate groups: 1 in" in _text
    finally:
        engine_mod.INIT_SEED = 0


# --- review fixes: Continue rebuild + tick coin + readout dark hulls --------


def test_shady_tech_survives_the_continue_rebuild():
    """A plain population citizen: the Continue rebuild places him
    with the population and restores his saved position (the
    former gated-spawn blocker class, gone structurally)."""
    from src.spacehack import city_npcs
    from src.spacehack.data.planets import load_planet
    from src.spacehack.data.solar_systems import system_for_planet
    from src.spacehack.saveload_maps import _rebuild_city

    ctx = _ctx()
    ctx.game_map = load_planet("lal_c")
    tech = next(
        e for e in ctx.game_map.entities
        if getattr(e, "city_npc_id", "") == "lalc_shady_tech"
    )
    tech.pos = Position(41, 42)
    saved = city_npcs.save_city_npc_positions(ctx)
    assert "lalc_shady_tech" in saved

    rebuilt = _rebuild_city(
        system_for_planet("lal_c").id, ctx.log, None, 10, 10, "lal_c",
        saved,
    )
    tech_after = [
        e for e in rebuilt.game_map.entities
        if getattr(e, "city_npc_id", "") == "lalc_shady_tech"
    ]
    assert len(tech_after) == 1
    assert (tech_after[0].pos.x, tech_after[0].pos.y) == (41, 42)


def test_tick_coin_is_deterministic_and_share_shaped():
    from src.spacehack.rumor_routing import flies_dark_coin

    assert flies_dark_coin(3, "sol", "tick_npc_sol_pirate_raider_1") == \
        flies_dark_coin(3, "sol", "tick_npc_sol_pirate_raider_1")
    draws = sum(
        flies_dark_coin(s, "sol", "tick_npc_sol_pirate_raider_1")
        for s in range(200)
    )
    assert 20 < draws < 100, f"share drifted: {draws}/200"


def test_shift_n_names_live_dark_hulls():
    from src.spacehack import dev_mode

    ctx = _pad_ctx()
    hull = Entity("R", (255, 80, 80), Position(1, 1), "Pirate Raider",
                  npc_ship_id="pirate_raider")
    hull.flies_dark = True
    ctx.game_map.entities.append(hull)
    dev_mode.log_rumor_routing(ctx)
    _text = "\n".join(e.text for e in ctx.log.history())
    assert "dark hulls here: Pirate Raider" in _text


# --- the spawn batch end-to-end (playtest crash regression) -----------------
# The first playtest crashed jumping systems: _spawn_table_groups
# grew a 4th tuple element (the dark stamp) and a consumer still
# unpacked 3. Drive the real spawn path so producer/consumer drift
# can never ship silently again.


def test_spawn_npcs_registers_a_legal_batch():
    from src.spacehack import engine as engine_mod, npc_ships
    from tests.support.quest_ctx import quest_ctx

    game_map = GameMap(200, 160, [], [])
    ctx = quest_ctx()
    ctx.procedural_spawns = {}
    rows = []
    for seed in range(64):
        engine_mod.RNG.seed(seed)
        ctx.procedural_spawns = {}
        game_map.entities.clear()
        npc_ships.spawn_npcs(ctx, game_map, "barnards_star")
        rows = ctx.procedural_spawns.get("barnards_star", [])
        if rows:
            break
    assert rows, "no spawn batch fired across 64 seeds"
    by_mid = {
        getattr(e, "procedural_squad_id", ""): e for e in game_map.entities
    }
    for row in rows:
        ent = by_mid.get(row.squad_id or "")
        if ent is not None:  # stationary derelicts carry no mid
            assert ent.flies_dark == row.flies_dark
    assert any(
        "signal" in e.text for e in ctx.log.history()
    ), "the sensor ping logged"
