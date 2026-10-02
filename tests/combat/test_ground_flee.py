"""Ground flee / stair dancing (doc 54 phase 2) — the reaction
volley, the refusal probe + step refund, the dispatch-level exit
seam, the tick fall-through, and the city-interior exit.

Binding rulings under test: the step is the commit (AP spent, no
prompt — SETTLED 1); a refusing stair refunds the step as a full
no-op (SETTLED 3); death on the stairs wins (SETTLED 1); only
enemies in band + LOS fire, once each, without moving; the fight
ends DISENGAGED with the exit payload and the CALLER runs the
transition; MOVE is the only trigger (WAIT / blocked bumps /
starting on the stairs fire nothing).
"""

from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from src.spacehack import city_npcs, game_flow, world
from src.spacehack.combat import _ai_ground, _ground_flee, _loop, _rules_ground
from src.spacehack.combat._types import FleeExit
from src.spacehack.data.npc_chars import find_npc_char
from src.spacehack.game_context import PlayerCounters
from src.spacehack.message_log import MessageLog
from tests.support.asyncutil import run
from tests.test_tombstone import _ctx as _reader_ctx


def _floor_map(width: int = 13, height: int = 13, *, kind_at=None,
               walls=()) -> world.GameMap:
    """An open floor map with optional stair/exit tiles and walls."""
    tiles = [[world.DUNGEON_FLOOR for _ in range(width)] for _ in range(height)]
    for x, y in walls:
        tiles[y][x] = world.WALL
    if kind_at is not None:
        _tile = {
            "stairs_down": world.STAIRS_DOWN,
            "stairs_up": world.STAIRS_UP,
            "exit": world.EXIT,
        }[kind_at[0]]
        tiles[kind_at[2]][kind_at[1]] = _tile  # (kind, x, y)
    return world.GameMap(width=width, height=height, tiles=tiles, entities=[])


def _dig_map(depth_floor: int = 1, **kw) -> world.GameMap:
    """A dig-floor map (wolf_b's site s1 is 4 floors deep — floor 1
    can always go down and, above floor 1, up)."""
    game_map = _floor_map(**kw)
    game_map.interior_cache_key = f"dig:wolf_b:s1:{depth_floor}"
    return game_map


def _ground_ctx(game_map, player_pos):
    ctx = _reader_ctx(
        game_map=game_map,
        player=world.Entity(
            "@", (255, 255, 255), world.Position(*player_pos), "Player",
        ),
        log=MessageLog(),
        player_traits=[],
        player_counters=PlayerCounters(),
        equipped_ground_weapons=[],
        equipped_ground_armor={},
        bandolier={},
    )
    ctx.ground_hp = ctx.ground_max_hp = 28
    return ctx


def _seed_enemy(game_map, spec_id: str, pos) -> world.Entity:
    spec = find_npc_char(spec_id)
    entity = world.Entity(
        spec.char, spec.fg, world.Position(*pos), spec.name,
        npc_char_id=spec.id, spawn_band=0,
    )
    game_map.entities.append(entity)
    return entity


def _release_ground_state() -> None:
    if _rules_ground._state is not None:
        _rules_ground._set_combat_locks(False)
    _rules_ground._state = None


def _start_fight(game_map, ctx, enemies=(), *, hp=28):
    """Real init + deterministic weapons (the pistol's 1-4 band)."""
    from tests.support.ground_pins import pin_entity_loadout

    for _ent in enemies:
        pin_entity_loadout(_ent, "kinetic_pistol")
    _rules_ground.init(ctx, list(enemies), game_map, console=None)
    _rules_ground._state.player_hp = hp
    for _inst in _rules_ground._state.enemies:
        assert _inst.weapon_id == "kinetic_pistol"  # derived from the stamp


def _record_shots(monkeypatch):
    """Count resolved enemy shots at the presentation seam — every
    rolled shot passes through exactly once; rolls stay real."""
    shots: list[str] = []

    async def _fake_present(_ctx, _console, _cb, _map, _ent, _ppos,
                            _wid, _qual, _spec, _hit, _dmg, _popup):
        shots.append(_spec.name)

    monkeypatch.setattr(_ai_ground, "_present_enemy_shot", _fake_present)
    return shots


def _record_volley(monkeypatch):
    fired: list = []

    async def _fake_volley(state, ctx, game_map):
        fired.append(game_map)
        return False

    monkeypatch.setattr(_ground_flee, "reaction_volley", _fake_volley)
    return fired


# --- the volley ----------------------------------------------------------------


def test_volley_band_and_los_filter(monkeypatch):
    """Two enemies in band with LOS fire exactly once each; one out
    of band and one behind a wall stand down; nobody moves."""
    shots = _record_shots(monkeypatch)
    game_map = _floor_map(walls=[(6, y) for y in range(13)])
    near1 = _seed_enemy(game_map, "pirate_raider", (4, 4))
    near2 = _seed_enemy(game_map, "pirate_raider", (2, 6))
    far = _seed_enemy(game_map, "pirate_raider", (11, 4))   # beyond band 4
    walled = _seed_enemy(game_map, "pirate_raider", (8, 4))  # behind the wall
    _pos_before = [(e.pos.x, e.pos.y) for e in (near1, near2, far, walled)]
    ctx = _ground_ctx(game_map, (2, 4))
    try:
        _start_fight(game_map, ctx, (near1, near2, far, walled))
        assert run(_rules_ground.reaction_volley(ctx, game_map)) is False
        assert sorted(shots) == ["Pirate Raider", "Pirate Raider"]
        for _e, _pos in zip((near1, near2, far, walled), _pos_before):
            assert (_e.pos.x, _e.pos.y) == _pos  # no movement
    finally:
        _release_ground_state()


def test_volley_can_kill_and_tracks_the_killer(monkeypatch):
    shots = _record_shots(monkeypatch)
    game_map = _floor_map()
    attacker = _seed_enemy(game_map, "pirate_raider", (3, 4))
    ctx = _ground_ctx(game_map, (2, 4))
    monkeypatch.setattr(
        _ai_ground, "RNG", SimpleNamespace(randint=lambda _a, _b: 1),
    )
    try:
        _start_fight(game_map, ctx, (attacker,), hp=1)
        assert run(_rules_ground.reaction_volley(ctx, game_map)) is True
        assert shots == ["Pirate Raider"]
        assert _rules_ground._state.player_hp <= 0
        assert _rules_ground.last_attacker(ctx) == (
            "Pirate Raider's Kinetic Pistol"
        )
        assert ctx.player_counters.ground_damage_taken >= 1
    finally:
        _release_ground_state()


def test_volley_shots_stop_after_the_player_dies(monkeypatch):
    """Death wins mid-volley: the second shooter never fires."""
    shots = _record_shots(monkeypatch)
    game_map = _floor_map()
    first = _seed_enemy(game_map, "pirate_raider", (3, 4))
    second = _seed_enemy(game_map, "pirate_raider", (2, 5))
    ctx = _ground_ctx(game_map, (2, 4))
    monkeypatch.setattr(
        _ai_ground, "RNG", SimpleNamespace(randint=lambda _a, _b: 1),
    )
    try:
        _start_fight(game_map, ctx, (first, second), hp=1)
        assert run(_rules_ground.reaction_volley(ctx, game_map)) is True
        assert shots == ["Pirate Raider"]
    finally:
        _release_ground_state()


# --- the stair-step exit through the dispatch seam ------------------------------


def test_step_onto_stairs_survives_to_disengaged(monkeypatch):
    """The step lands on stairs_down: dispatch ends the fight
    DISENGAGED with the payload, the AP is spent, survivors get the
    stairs as last-seen, and NO transition ran in-loop."""
    shots = _record_shots(monkeypatch)
    game_map = _dig_map(kind_at=("stairs_down", 4, 6))
    watcher = _seed_enemy(game_map, "pirate_raider", (11, 11))  # out of band
    ctx = _ground_ctx(game_map, (3, 6))
    disengaged: list = []

    def _fake_on_disengage(_ctx, _game_map):
        disengaged.append(True)

    monkeypatch.setattr(_rules_ground, "on_disengage", _fake_on_disengage)
    try:
        _start_fight(game_map, ctx, (watcher,))
        _ap_before = _rules_ground.player_ap(ctx)
        _idx, _result = run(_loop._dispatch_combat_action(
            None, ctx, game_map, _rules_ground, "MOVE:l", 0,
        ))
        assert (_idx, _result) == (0, "DISENGAGED")
        assert shots == []
        assert (ctx.player.pos.x, ctx.player.pos.y) == (4, 6)  # ON the stairs
        assert _rules_ground.player_ap(ctx) == _ap_before - 1  # step spent
        cr = _loop._finish_combat(ctx, _rules_ground, "DISENGAGED")
        assert cr.outcome == "DISENGAGED"
        assert cr.flee_exit == FleeExit(verb="stairs_down")
        assert disengaged == [True]
        assert ctx.game_map is game_map  # no transition in-loop
    finally:
        _release_ground_state()


def test_step_onto_refusing_stair_refunds(monkeypatch):
    """A stair with no transition behind it (no dig, no extension):
    the step is refunded — previous cell, AP back, no volley, same
    fight (SETTLED 3)."""
    fired = _record_volley(monkeypatch)
    game_map = _floor_map(kind_at=("stairs_down", 4, 6))
    enemy = _seed_enemy(game_map, "pirate_raider", (3, 5))
    ctx = _ground_ctx(game_map, (3, 6))
    try:
        _start_fight(game_map, ctx, (enemy,))
        _ap_before = _rules_ground.player_ap(ctx)
        _idx, _result = run(_loop._dispatch_combat_action(
            None, ctx, game_map, _rules_ground, "MOVE:l", 0,
        ))
        assert (_idx, _result) == (0, None)  # HELD falls through quietly
        assert (ctx.player.pos.x, ctx.player.pos.y) == (3, 6)  # restored
        assert _rules_ground.player_ap(ctx) == _ap_before      # AP back
        assert fired == []
        assert _rules_ground._state.active is True             # fight on
    finally:
        _release_ground_state()


def test_fight_starting_on_stairs_only_moves_trigger(monkeypatch):
    """MOVE is the only trigger: WAIT fires nothing, a blocked bump
    fires nothing — the player must step off and back on."""
    shots = _record_shots(monkeypatch)
    game_map = _dig_map(kind_at=("stairs_down", 3, 6), walls=[(2, y) for y in range(13)])
    watcher = _seed_enemy(game_map, "pirate_raider", (11, 11))
    ctx = _ground_ctx(game_map, (3, 6))  # the fight STARTS on the stairs
    try:
        _start_fight(game_map, ctx, (watcher,))
        _idx, _result = run(_loop._dispatch_combat_action(
            None, ctx, game_map, _rules_ground, "WAIT", 0,
        ))
        assert (_idx, _result) == (0, None)
        assert _rules_ground._state.flee_exit is None

        # A blocked bump while standing on the stairs: still nothing.
        _idx, _result = run(_loop._dispatch_combat_action(
            None, ctx, game_map, _rules_ground, "MOVE:h", 0,
        ))
        assert (_idx, _result) == (0, None)
        assert _rules_ground._state.flee_exit is None

        # Step off (east), then back on (west): the volley fires.
        # (WAIT zeroed the AP above — restore it for the two steps.)
        _rules_ground.set_player_ap(ctx, 4)
        run(_loop._dispatch_combat_action(
            None, ctx, game_map, _rules_ground, "MOVE:l", 0,
        ))
        assert (ctx.player.pos.x, ctx.player.pos.y) == (4, 6)  # off the stairs
        _rules_ground.set_player_ap(ctx, 4)
        _idx, _result = run(_loop._dispatch_combat_action(
            None, ctx, game_map, _rules_ground, "MOVE:h", 0,
        ))
        assert _result == "DISENGAGED"
        assert shots == []  # the out-of-band watcher stood down throughout
    finally:
        _release_ground_state()


def test_kill_on_stairs_writes_tombstone_no_transition(monkeypatch, tmp_path):
    """Death on the stairs: DEFEAT through the real finish (doc-53
    tombstone written, save deleted) with the map unchanged and no
    payload stashed (SETTLED 1)."""
    import os

    os.environ["HOME"] = str(tmp_path)
    shots = _record_shots(monkeypatch)
    game_map = _dig_map(kind_at=("stairs_down", 4, 6))
    killer = _seed_enemy(game_map, "pirate_raider", (5, 6))  # adjacent, in band
    ctx = _ground_ctx(game_map, (3, 6))
    monkeypatch.setattr(
        _ai_ground, "RNG", SimpleNamespace(randint=lambda _a, _b: 1),
    )
    try:
        _start_fight(game_map, ctx, (killer,), hp=1)
        _idx, _result = run(_loop._dispatch_combat_action(
            None, ctx, game_map, _rules_ground, "MOVE:l", 0,
        ))
        assert _result == "DEFEAT"
        assert shots == ["Pirate Raider"]
        cr = _loop._finish_combat(ctx, _rules_ground, "DEFEAT")
        assert cr.outcome == "DEFEAT"
        assert cr.tombstone_path is not None
        assert Path(cr.tombstone_path).exists()
        assert cr.flee_exit is None
        assert ctx.player_dead is True
        assert ctx.game_map is game_map  # the transition never ran
    finally:
        _release_ground_state()


def test_plain_move_keeps_the_dispatch_shape():
    """A step onto no transition tile dispatches exactly as before."""
    game_map = _floor_map()
    enemy = _seed_enemy(game_map, "pirate_raider", (5, 5))
    ctx = _ground_ctx(game_map, (3, 6))
    try:
        _start_fight(game_map, ctx, (enemy,))
        _idx, _result = run(_loop._dispatch_combat_action(
            None, ctx, game_map, _rules_ground, "MOVE:l", 0,
        ))
        assert (_idx, _result) == (0, None)
        assert (ctx.player.pos.x, ctx.player.pos.y) == (4, 6)
    finally:
        _release_ground_state()


# --- the refusal probe ----------------------------------------------------------


def test_stair_probe_refusal_matrix():
    """Stairs with nothing behind them refuse; dig floors refuse only
    at their bounds; an exit tile never refuses."""
    from src.spacehack.data.planets import find_planet_spec
    from src.spacehack.digs import site_depth

    _plain = _floor_map(kind_at=("stairs_down", 4, 6))
    _plain_ctx = _ground_ctx(_plain, (3, 6))
    assert _ground_flee._stair_transition_refuses(
        _plain_ctx, _plain, "stairs_down",
    ) is True  # no dig, no extension attached
    _up_map = _floor_map(kind_at=("stairs_up", 4, 6))
    assert _ground_flee._stair_transition_refuses(
        _ground_ctx(_up_map, (3, 6)), _up_map, "stairs_up",
    ) is True  # sealed
    _exit_map = _floor_map(kind_at=("exit", 4, 6))
    assert _ground_flee._stair_transition_refuses(
        _ground_ctx(_exit_map, (3, 6)), _exit_map, "exit",
    ) is False

    _depth = site_depth(find_planet_spec("wolf_b"), "s1")
    _top = _dig_map(depth_floor=1, kind_at=("stairs_down", 4, 6))
    _top_ctx = _ground_ctx(_top, (3, 6))
    _top_ctx.game_map = _top
    assert _ground_flee._stair_transition_refuses(
        _top_ctx, _top, "stairs_down",
    ) is False  # floor 2 exists (wolf_b depth >= 3)
    _bottom = _dig_map(depth_floor=_depth, kind_at=("stairs_down", 4, 6))
    assert _ground_flee._stair_transition_refuses(
        _ground_ctx(_bottom, (3, 6)), _bottom, "stairs_down",
    ) is True   # no floor below the bottom


# --- the tick fall-through + the city path ---------------------------------------


def test_combat_tick_result_maps_payload_to_the_exit_signal():
    """DEFEAT stays DEFEAT; a plain fight stays COMBAT; the
    stair-dance payload is the DISTINCT COMBAT_EXIT signal (a None
    fall-through dropped the commit on wait-started fights — the
    reviewer's blocking catch)."""
    assert game_flow._combat_tick_result(
        SimpleNamespace(outcome="DEFEAT", flee_exit=None),
    ) == "DEFEAT"
    assert game_flow._combat_tick_result(
        SimpleNamespace(outcome="DISENGAGED", flee_exit=None),
    ) == "COMBAT"
    assert game_flow._combat_tick_result(
        SimpleNamespace(outcome="DISENGAGED",
                        flee_exit=FleeExit(verb="stairs_down")),
    ) == "COMBAT_EXIT"


def test_dungeon_tick_signals_exit_and_skips_activation(monkeypatch):
    """The payload fight yields COMBAT_EXIT (not None, not COMBAT)
    AND skips the tile activation — the caller's tile dispatch owns
    the transition."""
    from src.spacehack import dungeon_extensions

    async def _fled_fight(*_a, **_kw):
        return SimpleNamespace(
            outcome="DISENGAGED", flee_exit=FleeExit(verb="stairs_down"),
        )

    activations: list = []
    monkeypatch.setattr(game_flow, "_run_ground_combat_tick", _fled_fight)
    monkeypatch.setattr(
        dungeon_extensions, "tick_activation",
        lambda *_a, **_kw: activations.append(True),
    )
    ctx = SimpleNamespace(player=SimpleNamespace(pos=world.Position(1, 1)))
    assert run(game_flow._dungeon_post_move_tick(
        ctx, None, object(),
    )) == "COMBAT_EXIT"
    assert activations == []


def test_wait_started_stair_dance_runs_the_tile_dispatch(monkeypatch):
    """The blocking-fix pin: a WAIT whose tick fight ends as a
    stair-dance runs the SAME tile dispatch a move would (the step
    was the commit); a plain wait on stairs transitions nothing."""
    from src.spacehack import game_loop

    dispatched: list = []

    async def _fake_dispatch(state):
        dispatched.append(state)
        return "HANDLED"

    monkeypatch.setattr(game_loop, "_dispatch_dungeon_tile", _fake_dispatch)
    monkeypatch.setattr(
        game_loop, "_dungeon_post_move_tick",
        _async_signal("COMBAT_EXIT"),
    )

    state = SimpleNamespace(
        ctx=SimpleNamespace(log=MessageLog()), console=None,
        game_map=_floor_map(), player=object(),
        current_mode="dungeon", player_owned_ship=None,
        current_city_id="", player_active_missions=[],
    )
    assert run(game_loop._handle_wait_event(
        state, _period_press_event(),
    )) == "HANDLED"
    assert dispatched == [state]  # the transition dispatch ran

    # A plain wait (no fight) never dispatches a tile.
    monkeypatch.setattr(
        game_loop, "_dungeon_post_move_tick", _async_signal(None),
    )
    dispatched.clear()
    run(game_loop._handle_wait_event(state, _period_press_event()))
    assert dispatched == []
    assert any(
        "You wait." in getattr(m, "text", str(m))
        for m in state.ctx.log._messages
    )


def _async_signal(value):
    async def _tick(*_a, **_kw):
        return value
    return _tick


def _period_press_event():
    from src.spacehack.pygame_engine import PygameInputEvent

    return PygameInputEvent(
        kind="keydown", key_name="period", modifiers=(), shift=False,
        repeat=False,
    )


def test_city_interior_exit_after_stair_dance(monkeypatch):
    """The bump-path city fight that ends as a stair-dance runs the
    ordinary interior exit with the REAL flow state."""
    street = _floor_map()
    street_player = world.Entity(
        "@", (255, 255, 255), world.Position(2, 2), "Player",
    )
    street.entities.append(street_player)
    interior = _floor_map(kind_at=("exit", 4, 6))
    interior.city_interior_id = "crew_bar"
    interior.city_parent_map = street
    interior.city_parent_player = street_player
    player = world.Entity(
        "@", (255, 255, 255), world.Position(4, 6), "Player",
    )
    interior.entities.append(player)
    ctx = _ground_ctx(interior, (4, 6))
    state = SimpleNamespace(
        ctx=ctx, console=None, log=ctx.log, game_map=interior,
        player=player, map_w=13, map_h=13,
        current_mode="dungeon", current_city_id="mercury",
        city_game_map=street, city_player=street_player,
        player_owned_ship=None, player_active_missions=[],
    )
    blocker = SimpleNamespace(city_npc_id="mob")

    async def _fled_fight(_ctx, _console, _map, _hostiles):
        return SimpleNamespace(
            outcome="DISENGAGED", flee_exit=FleeExit(verb="exit"),
        )

    monkeypatch.setattr(city_npcs, "is_hostile", lambda *_a: True)
    monkeypatch.setattr(city_npcs, "run_city_fight", _fled_fight)

    from src.spacehack import game_interactions
    run(game_interactions._resolve_city_npc_blocker(state, blocker))
    assert state.game_map is street           # exit_city_interior ran
    assert state.current_mode == "city"
    assert state.player is street_player
    assert any(
        "You step back outside" in getattr(m, "text", str(m))
        for m in ctx.log._messages
    )


def test_city_street_fight_without_payload_stays_put(monkeypatch):
    """A street fight that ends without a payload is CONTINUE — no
    exit lookup, no state changes (street maps carry no exits)."""
    game_map = _floor_map()
    player = world.Entity(
        "@", (255, 255, 255), world.Position(2, 2), "Player",
    )
    game_map.entities.append(player)
    ctx = _ground_ctx(game_map, (2, 2))
    state = SimpleNamespace(
        ctx=ctx, console=None, log=ctx.log, game_map=game_map,
        player=player, map_w=13, map_h=13,
        current_mode="city", current_city_id="mercury",
        city_game_map=game_map, city_player=player,
        player_owned_ship=None, player_active_missions=[],
    )

    async def _plain_fight(_ctx, _console, _map, _hostiles):
        return SimpleNamespace(outcome="VICTORY", flee_exit=None)

    monkeypatch.setattr(city_npcs, "is_hostile", lambda *_a: True)
    monkeypatch.setattr(city_npcs, "run_city_fight", _plain_fight)

    from src.spacehack import game_interactions
    assert run(game_interactions._resolve_city_npc_blocker(
        state, SimpleNamespace(city_npc_id="mob"),
    )) == "CONTINUE"
    assert state.game_map is game_map
