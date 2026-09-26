"""Space flee (doc 54 phase 1) — the reaction volley, the exit-commit
split of the wall resolvers, the FLED result flow, and the caller-side
execution/adoption.

Binding rulings under test: the volley fires AFTER the committing
choice (SETTLED 1); cancels and refusals are full no-ops (SETTLED 3);
death on the threshold wins (SETTLED 1); every in-range hostile fires
exactly once with no movement; the transition NEVER runs inside the
combat loop; no victory bookkeeping and no space-NPC drift on FLED.
"""

from __future__ import annotations

import sys
from contextlib import contextmanager
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from src.spacehack import game_interactions, solar_system, world
from src.spacehack import space_flee
from src.spacehack.combat import _ai, _loop, _rules_ground, _rules_space
from src.spacehack.combat._types import (
    CombatResult, EnemyInstance, FleeExit, SpaceCombatState,
)
from src.spacehack.game_context import PlayerCounters
from src.spacehack.message_log import MessageLog
from src.spacehack.ship import OwnedShip, StoredEquipment
from tests.balance import harness
from tests.support.asyncutil import as_async, run


def _texts(log) -> list[str]:
    return [getattr(m, "text", str(m)) for m in log._messages]


def _open_map(width: int = 20, height: int = 12) -> world.GameMap:
    tiles = [[world.DUNGEON_FLOOR] * width for _ in range(height)]
    return world.GameMap(width, height, tiles, [])


def _enemy(name: str, pos, weapons=("light_laser",), **kw) -> EnemyInstance:
    from src.spacehack.data.weapons import find_weapon

    entries = tuple(StoredEquipment("weapon", w) for w in weapons)
    ammo = kw.pop("ammo", {
        slot: (find_weapon(w).ammo_capacity
               if find_weapon(w).ammo_capacity > 0 else -1)
        for slot, w in enumerate(weapons)
    })
    return EnemyInstance(
        spec_id="x", name=name, char="X", fg=(1, 2, 3),
        weapons=entries, pos=pos,
        pilot_gunnery=kw.pop("gunnery", 20),
        weapon_ammo=ammo,
        **kw,
    )


def _release_space_state() -> None:
    _rules_space._state = None


def _space_state(game_map, player_pos, enemies, *, hull=100, ap=3):
    """A hand-built SpaceCombatState on a real map — the volley's
    real machinery (resolution, costs, LOS) without the ship
    catalogs. ctx carries the fields the flow shim reads."""
    ctx = SimpleNamespace(
        log=MessageLog(), player_counters=PlayerCounters(),
        game_map=game_map,
        player=world.Entity("@", (255, 255, 255), player_pos, "Player"),
        player_owned_ship=OwnedShip(ship_id="scout", fuel=50),
        context=harness._fake_pygame_context(),
    )
    state = SpaceCombatState(
        ctx=ctx, console=harness._AbsorbingConsole(), game_map=game_map,
        log=ctx.log,
        player_state={
            "pos": player_pos, "hull": hull, "max_hull": 100,
            "shields": 0, "max_shields": 0,
            "power_pool": 10, "max_power": 10,
            "ap_remaining": ap, "ap_total": ap,
            "piloting": 0, "gunnery": 20,
            "cells_moved_this_turn": 0, "weapons": (),
        },
        enemy_insts=list(enemies), cr=CombatResult(),
    )
    _rules_space._state = state
    return state, ctx


def _record_shots(monkeypatch):
    """Count shots at the animation seam — every resolved attack
    animates exactly once; resolution and costs stay real."""
    shots: list[str] = []

    async def _fake_anim(_state, ei, _wid, _hit, _popup, _evade, _cam):
        shots.append(ei.name)

    monkeypatch.setattr(_ai, "_animate_enemy_shot", _fake_anim)
    return shots


def _async_val(value):
    return as_async(lambda *_a, **_kw: value)


@contextmanager
def _sol_system():
    """Run a block with sol current; restore the ambient RNG world."""
    harness._snapshot_rng_world()
    solar_system.set_current_solar_system("sol")
    try:
        yield
    finally:
        harness._restore_rng_world()


def _empty_sol_cell():
    """A sol coordinate with no planet/jump/station over it — the
    non-exit bump target for the Blocked pin."""
    for y in range(3, 130):
        for x in range(3, 190):
            if (
                solar_system.planet_id_at(x, y) is None
                and solar_system.jump_point_at(x, y) is None
                and solar_system.station_id_at(x, y) is None
            ):
                return world.Position(x, y)
    raise AssertionError("sol has no empty cell")


# --- the reaction pick ---------------------------------------------------------


def test_reaction_pick_skips_weapons_that_cannot_reach():
    """A light laser (max range 5) never answers at distance 6 — the
    ranked scores stay positive at the 5% hit floor, so the reach
    filter is explicit, not scoring-emergent."""
    from src.spacehack.data.weapons import find_weapon

    enemy = _enemy("E", world.Position(0, 0), ("light_laser", "heavy_missile"))
    pick = _ai._reaction_pick(enemy, 6.0, {"shields": 0})
    assert pick is not None
    assert pick[1].id == "heavy_missile"
    assert find_weapon(pick[1].id).max_range >= 6


def test_reaction_pick_returns_none_when_nothing_reaches():
    """The volley's termination rule: a ship whose every weapon is
    out of range stands down — it cannot hit the player right now."""
    enemy = _enemy("E", world.Position(0, 0), ("light_laser",))
    assert _ai._reaction_pick(enemy, 6.0, {"shields": 0}) is None


def test_reaction_pick_keeps_the_affordability_gate():
    """A dry magazine is not 'in range' — the reaction uses the same
    affordability gate as the enemy turn."""
    dry = _enemy("E", world.Position(0, 0), ("heavy_missile",), ammo={0: 0})
    assert _ai._reaction_pick(dry, 4.0, {"shields": 0}) is None


# --- the volley ----------------------------------------------------------------


def test_volley_every_in_range_hostile_fires_once(monkeypatch):
    shots = _record_shots(monkeypatch)
    game_map = _open_map()
    near1 = _enemy("Near One", world.Position(3, 2))
    near2 = _enemy("Near Two", world.Position(3, 6))
    far = _enemy("Far", world.Position(18, 6))  # 16+ cells out
    state, ctx = _space_state(game_map, world.Position(2, 4), [near1, near2, far])
    try:
        assert run(_rules_space.reaction_volley(ctx, game_map)) is False
        assert len(shots) == 2
        assert set(shots) == {"Near One", "Near Two"}
        # No movement in the reaction — everyone stands.
        assert (near1.pos.x, near1.pos.y) == (3, 2)
        assert (near2.pos.x, near2.pos.y) == (3, 6)
        assert (far.pos.x, far.pos.y) == (18, 6)
        # Real costs were paid: one light-laser shot's power each.
        assert near1.power_pool < 10 and near2.power_pool < 10
    finally:
        _release_space_state()


def test_volley_requires_los(monkeypatch):
    shots = _record_shots(monkeypatch)
    game_map = _open_map()
    for y in range(12):
        game_map.tiles[y][3] = world.WALL
    blocked = _enemy("Behind Rock", world.Position(4, 4))
    state, ctx = _space_state(game_map, world.Position(2, 4), [blocked])
    try:
        assert run(_rules_space.reaction_volley(ctx, game_map)) is False
        assert shots == []
    finally:
        _release_space_state()


def test_volley_can_kill_and_tracks_the_killer(monkeypatch):
    shots = _record_shots(monkeypatch)
    game_map = _open_map()
    attacker = _enemy("Killer", world.Position(3, 4), ("medium_laser",))
    state, ctx = _space_state(game_map, world.Position(2, 4), [attacker], hull=1)
    monkeypatch.setattr(
        _ai, "RNG", SimpleNamespace(randint=lambda _a, _b: 1),
    )
    try:
        with harness._inert_presentation():
            assert run(_rules_space.reaction_volley(ctx, game_map)) is True
        assert shots == ["Killer"]
        assert state.player_state["hull"] <= 0
        assert state.last_attacker == "Killer's Medium Laser"
        assert ctx.player_counters.total_damage_taken >= 1
    finally:
        _release_space_state()


def test_volley_shots_stop_after_the_player_dies(monkeypatch):
    """Death wins mid-volley: the second ship never fires — the fight
    is over at the threshold (SETTLED 1)."""
    shots = _record_shots(monkeypatch)
    game_map = _open_map()
    first = _enemy("First", world.Position(3, 4), ("medium_laser",))
    second = _enemy("Second", world.Position(2, 5))
    state, ctx = _space_state(
        game_map, world.Position(2, 4), [first, second], hull=1,
    )
    monkeypatch.setattr(
        _ai, "RNG", SimpleNamespace(randint=lambda _a, _b: 1),
    )
    try:
        with harness._inert_presentation():
            assert run(_rules_space.reaction_volley(ctx, game_map)) is True
        assert shots == ["First"]
    finally:
        _release_space_state()


# --- attempt_flee: cancel / refusal / commit -----------------------------------


def _patch_exit(monkeypatch, target, commit, refused):
    """Canned probe + commit: attempt_flee's orchestration under
    test here; the real prompt flow under the split tests below."""
    monkeypatch.setattr(
        game_interactions, "_space_exit_target",
        lambda _state, _dx, _dy: target,
    )

    async def _fake_commit(_state, _target):
        return commit, refused

    monkeypatch.setattr(game_interactions, "_space_exit_commit", _fake_commit)


def _patch_volley_recorder(monkeypatch):
    fired: list = []

    async def _fake_volley(_ctx, game_map):
        fired.append(game_map)
        return False

    monkeypatch.setattr(_rules_space, "reaction_volley", _fake_volley)
    return fired


def test_attempt_flee_cancel_is_a_full_noop(monkeypatch):
    """ESC / fly past fires nothing: no volley, no AP, same fight."""
    _patch_exit(monkeypatch, ("planet", "earth"), None, False)
    fired = _patch_volley_recorder(monkeypatch)
    game_map = _open_map()
    state, ctx = _space_state(game_map, world.Position(2, 4), [])
    try:
        assert run(_rules_space.attempt_flee(
            ctx, game_map, "MOVE:h",
        )) == "HELD"
        assert fired == []
        assert _rules_space.player_ap(ctx) == 3
        assert state.cr.flee_exit is None
        assert state.active is True
    finally:
        _release_space_state()


def test_attempt_flee_refusal_is_a_full_noop(monkeypatch):
    """A refused commit (no fuel, dark dock, nothing to explore)
    leaves the map unchanged and fires nothing (SETTLED 3)."""
    _patch_exit(monkeypatch, ("planet", "earth"), None, True)
    fired = _patch_volley_recorder(monkeypatch)
    game_map = _open_map()
    state, ctx = _space_state(game_map, world.Position(2, 4), [])
    try:
        assert run(_rules_space.attempt_flee(
            ctx, game_map, "MOVE:h",
        )) == "HELD"
        assert fired == []
        assert state.cr.flee_exit is None
    finally:
        _release_space_state()


def test_attempt_flee_commit_survives_to_fled(monkeypatch):
    """A survived volley ends the fight FLED with the commit on the
    result — the transition itself never runs in-loop."""
    _patch_exit(
        monkeypatch, ("planet", "earth"),
        FleeExit(verb="land", planet_id="earth"), False,
    )
    game_map = _open_map()
    enemy = _enemy("Too Far", world.Position(19, 4))  # out of range
    state, ctx = _space_state(game_map, world.Position(2, 4), [enemy])
    try:
        assert run(_rules_space.attempt_flee(
            ctx, game_map, "MOVE:h",
        )) == "FLED"
        assert state.cr.flee_exit == FleeExit(verb="land", planet_id="earth")
        assert ctx.game_map is game_map  # no map change in-loop
    finally:
        _release_space_state()


def test_attempt_flee_death_wins(monkeypatch):
    """The volley destroyed the player: DEFEAT, no commit stashed —
    the transition must never run (SETTLED 1)."""
    _patch_exit(
        monkeypatch, ("planet", "earth"),
        FleeExit(verb="land", planet_id="earth"), False,
    )

    async def _killer_volley(_ctx, _game_map):
        return True

    monkeypatch.setattr(_rules_space, "reaction_volley", _killer_volley)
    game_map = _open_map()
    state, ctx = _space_state(game_map, world.Position(2, 4), [])
    try:
        assert run(_rules_space.attempt_flee(
            ctx, game_map, "MOVE:h",
        )) == "DEFEAT"
        assert state.cr.flee_exit is None
    finally:
        _release_space_state()


def test_attempt_flee_no_exit_or_no_ap_returns_none(monkeypatch):
    """No exit at the target (or no AP to act): the attempt declines
    and the move dispatches normally — blocked bumps log Blocked."""
    calls: list = []

    async def _fail_commit(_state, _target):
        calls.append(_target)
        return None, False

    monkeypatch.setattr(
        game_interactions, "_space_exit_target", lambda *_a: None,
    )
    monkeypatch.setattr(game_interactions, "_space_exit_commit", _fail_commit)
    game_map = _open_map()
    state, ctx = _space_state(game_map, world.Position(2, 4), [])
    try:
        assert run(_rules_space.attempt_flee(
            ctx, game_map, "MOVE:h",
        )) is None
        assert calls == []

        _rules_space._state.player_state["ap_remaining"] = 0
        monkeypatch.setattr(
            game_interactions, "_space_exit_target",
            lambda *_a: ("planet", "earth"),
        )
        assert run(_rules_space.attempt_flee(
            ctx, game_map, "MOVE:h",
        )) is None
        assert calls == []
    finally:
        _release_space_state()


# --- the meta seam: MOVE onto an exit ends or no-ops the fight ------------------


def test_meta_move_fled_and_defeat_end_the_fight(monkeypatch):
    async def _fake_flee(_ctx, _game_map, _action):
        return "FLED"

    monkeypatch.setattr(_rules_space, "attempt_flee", _fake_flee)
    assert run(_loop._handle_meta_action(
        "MOVE:h", SimpleNamespace(), rules=_rules_space, game_map=None,
    )) == ("MOVE:h", "FLED", False)

    async def _fake_flee_death(_ctx, _game_map, _action):
        return "DEFEAT"

    monkeypatch.setattr(_rules_space, "attempt_flee", _fake_flee_death)
    assert run(_loop._handle_meta_action(
        "MOVE:h", SimpleNamespace(), rules=_rules_space, game_map=None,
    )) == ("MOVE:h", "DEFEAT", False)


def test_meta_move_held_redoes_without_dispatch(monkeypatch):
    """HELD = the redo path: the loop re-renders and takes the next
    input — no dispatch, no AP, same turn (SETTLED 3)."""
    async def _fake_flee(_ctx, _game_map, _action):
        return "HELD"

    monkeypatch.setattr(_rules_space, "attempt_flee", _fake_flee)
    assert run(_loop._handle_meta_action(
        "MOVE:h", SimpleNamespace(), rules=_rules_space, game_map=None,
    )) == ("MOVE:h", None, True)


def test_meta_ground_moves_pass_through_untouched():
    """Ground has no flee hook (phase 2): a MOVE reaches dispatch
    exactly as before."""
    assert run(_loop._handle_meta_action(
        "MOVE:h", SimpleNamespace(), rules=_rules_ground, game_map=None,
    )) == ("MOVE:h", None, False)


def test_non_exit_blocked_bump_still_logs_blocked():
    """The regression pin: a failed move onto no exit logs Blocked.
    exactly as today — the flee routing must not swallow it."""
    with _sol_system():
        pos = _empty_sol_cell()
        game_map = _open_map(width=pos.x + 4, height=pos.y + 4)
        game_map.tiles[pos.y][pos.x + 1] = world.WALL
        state, ctx = _space_state(game_map, pos, [])
        try:
            assert run(_rules_space.attempt_flee(
                ctx, game_map, "MOVE:l",
            )) is None
            target_idx, _exit = run(_loop._dispatch_combat_action(
                None, ctx, game_map, _rules_space, "MOVE:l", 0,
            ))
            assert target_idx == 0
            assert _exit is None
            assert "Blocked." in _texts(ctx.log)
        finally:
            _release_space_state()


# --- the exit-commit split (real prompts, refusals before anything) -------------


def _gi_state():
    """A minimal main-loop-shaped state for the wall resolvers."""
    game_map = _open_map()
    ctx = SimpleNamespace(
        log=MessageLog(), game_map=game_map,
        player=world.Entity("@", (255, 255, 255), world.Position(2, 4), "P"),
        player_owned_ship=OwnedShip(ship_id="scout", fuel=50),
    )
    return SimpleNamespace(
        ctx=ctx, console=None, log=ctx.log, game_map=game_map,
        player=ctx.player, map_w=20, map_h=12,
        player_owned_ship=ctx.player_owned_ship,
        current_mode="space", current_city_id="",
    )


def test_planet_menu_commit_and_refusal_matrix(monkeypatch):
    """The split at the outcome branch: Land commits; a refused Land
    (the dark-dock denial) refuses; a Leave cancels — and only the
    commit ever reaches the apply."""
    from src.spacehack.menus import PlanetMenuOutcome

    state = _gi_state()
    monkeypatch.setattr(
        game_interactions, "_run_planet_menu",
        _async_val((PlanetMenuOutcome.LAND, None)),
    )
    applied: list = []

    async def _apply(_state, commit):
        applied.append(commit)
        return "CONTINUE"

    monkeypatch.setattr(game_interactions, "_apply_exit_commit", _apply)

    commit, refused = run(game_interactions._planet_exit_commit(state, "earth"))
    assert commit == FleeExit(verb="land", planet_id="earth")
    assert refused is False

    # A refused Land fires nothing downstream.
    monkeypatch.setattr(
        game_interactions, "_dark_dock_refusal",
        lambda _ctx, _pid: "Docking request denied: transponder not responding.",
    )
    commit, refused = run(game_interactions._planet_exit_commit(state, "earth"))
    assert (commit, refused) == (None, True)
    assert any("Docking request denied" in t for t in _texts(state.log))

    # A canceled menu commits nothing and does not count as refused.
    monkeypatch.setattr(
        game_interactions, "_run_planet_menu",
        _async_val((PlanetMenuOutcome.BACK, None)),
    )
    commit, refused = run(game_interactions._planet_exit_commit(state, "earth"))
    assert (commit, refused) == (None, False)
    assert applied == []  # nothing ran the transition


def test_explore_refusal_probes_before_anything():
    """A world with no authored surface params never leaves orbit —
    refused before a volley could ever fire (SETTLED 3)."""
    from src.spacehack.data.planets import find_planet_spec

    state = _gi_state()
    planet_obj = find_planet_spec("barnards_c")
    commit, refused = game_interactions._explore_exit_commit(
        state.log, "barnards_c", planet_obj,
    )
    assert commit is None and refused is True
    assert any("Nothing to explore" in t for t in _texts(state.log))


def test_jump_commit_fuel_refusal_and_success(monkeypatch):
    """ENTER with an empty tank refuses; with fuel it commits the
    jump and the apply burns exactly JUMP_FUEL_COST."""
    from src.spacehack import ship as ship_module
    from src.spacehack.navigation import JumpMenuOutcome

    state = _gi_state()
    jp = SimpleNamespace(name="Gate", connects_to=[("alpha_centauri", "jp1")])
    target = ("jump", jp, "alpha_centauri", "jp1")
    monkeypatch.setattr(
        game_interactions, "_run_jump_menu", _async_val(JumpMenuOutcome.JUMP),
    )

    state.player_owned_ship.fuel = ship_module.JUMP_FUEL_COST - 1
    commit, refused = run(game_interactions._jump_exit_commit(state, target))
    assert commit is None and refused is True

    state.player_owned_ship.fuel = 50
    commit, refused = run(game_interactions._jump_exit_commit(state, target))
    assert commit == FleeExit(
        verb="jump", jp=jp,
        target_system_id="alpha_centauri", target_jp_id="jp1",
    )
    assert refused is False

    new_map, new_player = object(), object()
    monkeypatch.setattr(
        game_interactions, "_animate_jump", _async_val(None),
    )
    monkeypatch.setattr(
        game_interactions, "_jump_to_system",
        _async_val((new_map, new_player)),
    )
    run(game_interactions._apply_jump_commit(state, commit))
    assert state.player_owned_ship.fuel == 50 - ship_module.JUMP_FUEL_COST
    assert state.game_map is new_map
    assert state.ctx.game_map is new_map


def test_out_of_combat_wall_resolution_keeps_its_shapes(monkeypatch):
    """The refactored _resolve_space_wall preserves today's returns:
    wall bump → None + Blocked line; jump cancel → None + Blocked
    line; refusal → CONTINUE with no Blocked line."""
    blocker = SimpleNamespace()
    monkeypatch.setattr(world, "blocked_message_for", lambda _b: "Blocked.")

    state = _gi_state()
    # A plain wall: no exit anywhere near.
    assert run(game_interactions._resolve_space_wall(state, 0, -1, blocker)) is None
    assert "Blocked." in _texts(state.log)

    # A jump prompt canceled stays the blocked bump it always was.
    from src.spacehack.navigation import JumpMenuOutcome

    monkeypatch.setattr(
        game_interactions, "_space_exit_target",
        lambda _s, _dx, _dy: ("jump", SimpleNamespace(name="Gate"), "sys", "jp"),
    )
    monkeypatch.setattr(
        game_interactions, "_run_jump_menu", _async_val(JumpMenuOutcome.BACK),
    )
    state.log._messages.clear()
    assert run(game_interactions._resolve_space_wall(state, 0, -1, blocker)) is None
    assert "Blocked." in _texts(state.log)

    # A fuel refusal resolves CONTINUE with no Blocked line after it.
    monkeypatch.setattr(
        game_interactions, "_run_jump_menu", _async_val(JumpMenuOutcome.JUMP),
    )
    state.player_owned_ship.fuel = 0
    state.log._messages.clear()
    assert run(game_interactions._resolve_space_wall(state, 0, -1, blocker)) == "CONTINUE"
    assert "Blocked." not in _texts(state.log)


# --- the caller side: encounter branch, begin/adopt, the drift guard ------------


def test_fled_encounter_branch_runs_the_transition_caller_side(monkeypatch):
    """FLED never books victory and never re-runs combat: the branch
    hands the result to begin_flee_transition and returns FLED."""
    from src.spacehack.combat import _encounter
    from src.spacehack.data.npc_ships import find_npc_ship
    from src.spacehack import tutorial

    async def noop(*_a, **_kw):
        return None

    cr = SimpleNamespace(
        outcome="FLED", tombstone_path=None,
        flee_exit=FleeExit(verb="land", planet_id="earth"),
    )

    async def fake_run_combat(_console, _ctx, _game_map, _rules):
        return cr

    seen: list = []

    async def fake_begin(_ctx, _console, _cr):
        seen.append(_cr)
        return True

    ctx = SimpleNamespace(
        player=world.Entity("@", (255, 255, 255), world.Position(1, 1), "P"),
        log=MessageLog(), game_map=object(),
        player_owned_ship=OwnedShip(ship_id="scout"),
        player_active_missions=[], main_quest_chain="",
        stats=SimpleNamespace(credits=100, gunnery=20, piloting=20, engineering=10),
    )
    monkeypatch.setattr(tutorial, "maybe_space_combat_intro", noop)
    monkeypatch.setattr(_rules_space, "init", lambda *_a, **_kw: None)
    monkeypatch.setattr(_encounter, "run_combat", fake_run_combat)
    monkeypatch.setattr(
        space_flee, "begin_flee_transition", fake_begin,
    )

    outcome = run(_encounter._handle_combat_encounter(
        ctx, None, ([find_npc_ship("pirate_scout")], [world.Position(2, 2)]),
    ))
    assert outcome == "FLED"
    assert seen == [cr]


def test_begin_flee_transition_lands_and_adopts(monkeypatch):
    """The full survive flow on the real apply path: the transition
    runs caller-side and the GameLoopState adoption mirrors it."""
    space_map = _open_map()
    ctx = SimpleNamespace(
        log=MessageLog(), game_map=space_map,
        player=world.Entity("@", (255, 255, 255), world.Position(2, 4), "P",
                            owned=True),
        player_owned_ship=OwnedShip(ship_id="scout", fuel=50),
        current_city_id="", militia_scanned=set(),
        ground_hp=5, ground_max_hp=10, player_active_missions=[],
    )
    monkeypatch.setattr(
        game_interactions, "_run_cargo_scan", _async_val(None),
    )
    monkeypatch.setattr(
        game_interactions, "_animate_ship_to_y", _async_val(None),
    )

    cr = SimpleNamespace(
        outcome="FLED",
        flee_exit=FleeExit(verb="land", planet_id="mercury"),
    )
    assert run(space_flee.begin_flee_transition(ctx, None, cr))
    assert ctx.current_city_id == "mercury"
    assert ctx.game_map is not space_map
    assert ctx.ground_hp == ctx.ground_max_hp  # landing at a city heals

    # The adoption: state mirrors the ctx-level transition.
    state = SimpleNamespace(
        ctx=ctx, game_map=space_map, player=object(),
        space_game_map=None, space_player=None,
        city_game_map=None, city_player=None,
        current_city_id="earth", current_mode="space",
        player_active_missions=[],
    )
    rules_state = SpaceCombatState(ctx=ctx, cr=CombatResult(outcome="FLED"))
    rules_state.cr.flee_exit = cr.flee_exit
    _rules_space._state = rules_state
    try:
        space_flee.adopt_flee_transition(state)
        assert state.current_mode == "city"
        assert state.city_game_map is ctx.game_map
        assert state.game_map is ctx.game_map
        assert state.current_city_id == "mercury"
    finally:
        _release_space_state()


def test_adopt_flee_dungeon_and_space_kinds():
    """Explore/dig adopt the capture-boarding shape; a jump stays in
    space on the new map."""
    for verb, mode in (("explore", "dungeon"), ("dig", "dungeon"),
                       ("jump", "space")):
        ctx = SimpleNamespace(
            game_map=object(), player=object(), player_active_missions=[],
        )
        old_map, old_player = object(), object()
        state = SimpleNamespace(
            ctx=ctx, game_map=old_map, player=old_player,
            space_game_map=None, space_player=None,
            city_game_map=None, city_player=None,
            current_city_id="", current_mode="space",
            player_active_missions=[],
        )
        rules_state = SpaceCombatState(ctx=ctx, cr=CombatResult(outcome="FLED"))
        rules_state.cr.flee_exit = FleeExit(verb=verb, planet_id="mars")
        _rules_space._state = rules_state
        try:
            space_flee.adopt_flee_transition(state)
            assert state.current_mode == mode
            assert state.game_map is ctx.game_map
            assert state.player is ctx.player
            if mode == "dungeon":
                assert state.space_game_map is old_map
                assert state.space_player is old_player
        finally:
            _release_space_state()


def test_adopt_flee_without_a_fight_is_a_noop():
    state = SimpleNamespace(current_mode="space")
    space_flee.adopt_flee_transition(state)  # no fight ran: no crash
    assert state.current_mode == "space"


def test_begin_flee_transition_execute_refusal_aborts(monkeypatch):
    """An execute-time refusal (map unchanged after the apply) pays
    the volley but books no destination: ABORTED, the break-away
    twin of a failed boarding."""
    ctx = SimpleNamespace(
        log=MessageLog(), game_map=_open_map(),
        player=object(), player_owned_ship=None,
    )
    cr = SimpleNamespace(
        outcome="FLED",
        flee_exit=FleeExit(verb="explore", planet_id="mars"),
    )
    monkeypatch.setattr(
        space_flee, "_apply_exit_commit", _async_val("CONTINUE"),
    )
    assert run(space_flee.begin_flee_transition(ctx, None, cr)) is False
    assert cr.outcome == "ABORTED"


def test_combat_loop_guard_skips_drift_after_fled(monkeypatch):
    """The also_move_npcs tail must never run against a post-flee
    map — the BOARDED guard's FLED twin (doc 54)."""
    from src.spacehack import game_flow

    drift: list = []

    async def _no_line(_ctx, _console, _player):
        return False, None

    async def _no_warning(_ctx, _console, _player):
        return None

    def _detect(_ctx, _pos, _system):
        return (object(), object())

    async def _fled_fight(_ctx, _console, _encounter):
        return "FLED"

    monkeypatch.setattr(game_flow, "_run_line_crossing", _no_line)
    monkeypatch.setattr(game_flow, "_auto_warning_outcome", _no_warning)
    monkeypatch.setattr(game_flow, "_detect_combat_encounter", _detect)
    monkeypatch.setattr(
        game_flow.combat, "_handle_combat_encounter", _fled_fight,
    )
    monkeypatch.setattr(
        game_flow, "_move_npcs",
        lambda *_a, **_kw: drift.append("move_npcs"),
    )
    monkeypatch.setattr(game_flow, "_line_mod", SimpleNamespace(
        step_watch=lambda *_a, **_kw: drift.append("step_watch"),
    ))

    ctx = SimpleNamespace(player=SimpleNamespace(pos=world.Position(1, 1)))
    outcome = run(game_flow._run_combat_loop(
        ctx, None, ctx.player, also_move_npcs=True, day_pass=True,
    ))
    assert outcome == "FLED"
    assert drift == []


def test_auto_warning_fled_returns_before_the_detection_loop(monkeypatch):
    """The pre-loop auto-warning pass carries the same hazard as
    goto's second pass: a FLED there must return immediately — a
    detection pass against the stale pre-flee position could init a
    spurious fight and overwrite the outcome before adoption."""
    from src.spacehack import game_flow

    detected: list = []

    async def _no_line(_ctx, _console, _player):
        return False, None

    async def _fled_warning(_ctx, _console, _player):
        return "FLED"

    def _detect(_ctx, _pos, _system):
        detected.append(_pos)
        return None

    monkeypatch.setattr(game_flow, "_run_line_crossing", _no_line)
    monkeypatch.setattr(game_flow, "_auto_warning_outcome", _fled_warning)
    monkeypatch.setattr(game_flow, "_detect_combat_encounter", _detect)

    ctx = SimpleNamespace(player=SimpleNamespace(pos=world.Position(1, 1)))
    outcome = run(game_flow._run_combat_loop(ctx, None, ctx.player))
    assert outcome == "FLED"
    assert detected == []  # the loop never ran its detection pass


# --- real-fight integration on the balance harness ------------------------------


def _sol_grid_row(seed, player_start, enemies):
    from tests.balance.scenarios import (
        BalanceScenario, EnemySide, GridSpec, PlayerSheet,
    )

    return BalanceScenario(
        id=f"doc54_{seed}",
        theater="space",
        goal="flee through a planet exit mid-fight",
        player=PlayerSheet(
            species_id="human", class_id="merchant",
            hull_id="hauler", weapon_ids=(), module_ids=(),
        ),
        player_start=player_start,
        enemies=tuple(
            EnemySide(spec_id="pirate_scout", pos=pos, band=1)
            for pos in enemies
        ),
        grid=GridSpec(width=200, height=140, system_id="sol"),
        stance="stand_and_trade",
        runs=1,
        seed=seed,
        thresholds=None,
    )


def _earth_edge_cell(game_map):
    """A walkable cell beside earth's footprint, and an earth cell to
    bump toward."""
    for y in range(30, 50):
        for x in range(130, 152):
            if solar_system.planet_id_at(x, y) == "earth":
                for dy in (-1, 0, 1):
                    for dx in (-1, 0, 1):
                        if (dx, dy) == (0, 0):
                            continue
                        _nx, _ny = x + dx, y + dy
                        if game_map.in_bounds(_nx, _ny) and game_map.is_walkable(_nx, _ny):
                            return world.Position(_nx, _ny), (x, y)
    raise AssertionError("no walkable cell beside earth")


def _move_key_toward(player_pos, target_cell):
    for key, (dx, dy) in world.MOVE_KEYS.items():
        if (player_pos.x + dx, player_pos.y + dy) == target_cell:
            return f"MOVE:{key}"
    raise AssertionError(f"no move key from {player_pos} to {target_cell}")


def _open_cell_near(game_map, pos, min_dist: int):
    """A walkable map cell at least ``min_dist`` from ``pos``."""
    for radius in range(min_dist, 20):
        for dy in range(-radius, radius + 1):
            for dx in range(-radius, radius + 1):
                _nx, _ny = pos.x + dx, pos.y + dy
                if game_map.in_bounds(_nx, _ny) and game_map.is_walkable(_nx, _ny):
                    if (dx * dx + dy * dy) ** 0.5 >= min_dist:
                        return world.Position(_nx, _ny)
    raise AssertionError("no open cell")


def test_real_flee_death_writes_tombstone_and_no_transition(
    monkeypatch, tmp_path,
):
    """A volley kill at the threshold: DEFEAT through the real finish
    (tombstone written, save deleted) with the map unchanged — the
    landing never ran (SETTLED 1)."""
    from src.spacehack.combat._stats import _build_enemy
    from src.spacehack.data.npc_ships import find_npc_ship
    from src.spacehack.menus import PlanetMenuOutcome

    monkeypatch.setenv("HOME", str(tmp_path))
    with _sol_system(), harness._inert_presentation():

        async def _go():
            ctx, game_map, console, rules = await harness.begin_run(
                _sol_grid_row(540001, (5, 5), [(8, 5)]), 0,
            )
            try:
                stand, earth_cell = _earth_edge_cell(game_map)
                rules._state.player_state["pos"] = stand
                ctx.player.pos = stand
                rules._state.player_state["hull"] = 1
                rules._state.player_state["shields"] = 0
                killer = _build_enemy(
                    find_npc_ship("pirate_scout"),
                    _open_cell_near(game_map, stand, 2),
                )
                rules._state.enemy_insts = [killer]
                rules._state.enemy_specs = [find_npc_ship("pirate_scout")]
                action = _move_key_toward(stand, earth_cell)
                monkeypatch.setattr(
                    game_interactions, "_run_planet_menu",
                    _async_val((PlanetMenuOutcome.LAND, None)),
                )
                # The hit roll is forced: the death PATH is the pin,
                # not this seed's dice.
                monkeypatch.setattr(
                    _ai, "RNG", SimpleNamespace(randint=lambda _a, _b: 1),
                )
                _action, result, _redo = await _loop._handle_meta_action(
                    action, ctx, rules=rules, game_map=game_map,
                )
                assert result == "DEFEAT"
                cr = _loop._finish_combat(ctx, rules, result)
                assert cr.outcome == "DEFEAT"
                assert cr.tombstone_path is not None
                assert Path(cr.tombstone_path).exists()
                assert ctx.game_map is game_map  # no transition ran
            finally:
                harness.end_run(rules)

        run(_go())


def test_real_flee_survives_lands_and_books_no_victory(
    monkeypatch, tmp_path,
):
    """The survive path end to end: the out-of-range watcher never
    fires, FLED carries the commit, the transition runs caller-side,
    the adoption mirrors it, and nothing books a victory."""
    from src.spacehack.combat._stats import _build_enemy
    from src.spacehack.data.npc_ships import find_npc_ship
    from src.spacehack.menus import PlanetMenuOutcome

    monkeypatch.setenv("HOME", str(tmp_path))
    with _sol_system(), harness._inert_presentation():

        async def _go():
            ctx, game_map, console, rules = await harness.begin_run(
                _sol_grid_row(540002, (5, 5), [(8, 5)]), 0,
            )
            try:
                stand, earth_cell = _earth_edge_cell(game_map)
                rules._state.player_state["pos"] = stand
                ctx.player.pos = stand
                rules._state.player_state["hull"] = 80
                watcher = _build_enemy(
                    find_npc_ship("pirate_scout"),
                    _open_cell_near(game_map, stand, 8),
                )
                watcher_power = watcher.power_pool
                rules._state.enemy_insts = [watcher]
                rules._state.enemy_specs = [find_npc_ship("pirate_scout")]
                action = _move_key_toward(stand, earth_cell)
                monkeypatch.setattr(
                    game_interactions, "_run_planet_menu",
                    _async_val((PlanetMenuOutcome.LAND, None)),
                )
                _action, result, _redo = await _loop._handle_meta_action(
                    action, ctx, rules=rules, game_map=game_map,
                )
                assert result == "FLED"
                cr = _loop._finish_combat(ctx, rules, "FLED")
                assert cr.outcome == "FLED"
                assert cr.flee_exit == FleeExit(verb="land", planet_id="earth")
                # The watcher stood down: no shot, no damage, no cost.
                assert watcher.power_pool == watcher_power
                assert rules._state.player_state["hull"] == 80
                kills = ctx.player_counters.total_kills

                # Caller side: the transition + the adoption.
                monkeypatch.setattr(
                    game_interactions, "_run_cargo_scan", _async_val(None),
                )
                monkeypatch.setattr(
                    game_interactions, "_animate_ship_to_y", _async_val(None),
                )
                ctx.ground_hp = ctx.ground_max_hp = 20
                assert await space_flee.begin_flee_transition(
                    ctx, console, cr,
                )
                assert ctx.current_city_id == "earth"
                assert ctx.game_map is not game_map
                state = SimpleNamespace(
                    ctx=ctx, game_map=game_map, player=ctx.player,
                    space_game_map=None, space_player=None,
                    city_game_map=None, city_player=None,
                    current_city_id="", current_mode="space",
                    player_active_missions=[],
                )
                space_flee.adopt_flee_transition(state)
                assert state.current_mode == "city"
                assert state.game_map is ctx.game_map
                # No victory bookkeeping rode the flee.
                assert ctx.player_counters.total_kills == kills
                assert not any(
                    "Victory!" in t for t in _texts(ctx.log)
                )
            finally:
                harness.end_run(rules)

        run(_go())
