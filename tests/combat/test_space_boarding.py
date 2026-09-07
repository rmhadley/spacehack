"""Live-ship boarding tests (doc 40 phase 6a).

The BOARD action's four ruled conditions, the consuming capture
entry, and the capture-target data opt-ins.
"""

from __future__ import annotations

from types import SimpleNamespace

from src.spacehack import world
from src.spacehack.combat._space_boarding import attempt_board, board_denial
from src.spacehack.combat._types import CombatResult, SpaceCombatState


def _state(player_pos=(10, 10), ent=None, enemy_pos=(11, 10), **enemy_kwargs):
    _enemy = dict(
        alive=True, spec_id="pirate_scout", name="Pirate Scout",
        shields=0, max_shields=0, hull=20, max_hull=100,
    )
    _enemy.update(enemy_kwargs)
    _ent = ent if ent is not None else SimpleNamespace(
        procedural_squad_id="sq_1", npc_ship_id=_enemy["spec_id"],
    )
    return SpaceCombatState(
        log=SimpleNamespace(add=lambda *a, **k: None),
        enemy_insts=[SimpleNamespace(
            pos=world.Position(*enemy_pos), **_enemy,
        )],
        enemy_ents={0: _ent},
        player_ent=SimpleNamespace(pos=world.Position(*player_pos)),
        cr=CombatResult(),
    ), _ent


def test_board_denial_truth_table():
    state, _ent = _state()
    assert board_denial(state, state.enemy_insts[0], _ent) is None, \
        "strip shields, 80% hull damage, duel, adjacent: boardable"

    _shielded, _ = _state(shields=20, max_shields=20)
    assert "shields" in board_denial(_shielded, _shielded.enemy_insts[0], _ent)

    _intact, _ = _state(hull=90)
    assert "hull" in board_denial(_intact, _intact.enemy_insts[0], _ent)

    _escorted, _ = _state()
    _escorted.enemy_insts.append(SimpleNamespace(
        alive=True, shields=0, hull=10, max_hull=100,
        pos=world.Position(30, 30),
    ))
    assert "escorts" in board_denial(_escorted, _escorted.enemy_insts[0], _ent)

    _far, _ = _state(player_pos=(10, 10), enemy_pos=(14, 10))
    assert "alongside" in board_denial(_far, _far.enemy_insts[0], _ent)


def test_board_denial_refuses_non_capture_ships():
    _bounty, _ = _state(ent=SimpleNamespace(
        procedural_squad_id="sq", npc_ship_id="pirate_captain",
        bounty_spawn_id="b1",
    ))
    assert "can't be boarded" in board_denial(
        _bounty, _bounty.enemy_insts[0], _bounty.enemy_ents[0],
    )

    _plain, _ = _state(
        spec_id="militia_patrol", ent=SimpleNamespace(
            procedural_squad_id="sq", npc_ship_id="militia_patrol",
        ),
    )
    assert "can't be boarded" in board_denial(
        _plain, _plain.enemy_insts[0], _plain.enemy_ents[0],
    )


def test_attempt_board_sets_the_result(monkeypatch):
    state, _ent = _state()
    seen = {}
    monkeypatch.setattr(
        "src.spacehack.data.npc_ships.find_npc_ship",
        lambda sid: SimpleNamespace(capture_layout_id="scout_crew"),
    )

    assert attempt_board(state, 0) is True
    assert state.cr.boarded_spec_id == "pirate_scout"
    assert state.cr.boarded_ent is _ent

    _intact, _ = _state(hull=90)
    _intact.log = SimpleNamespace(add=lambda *a, **k: seen.update(reason=True))
    assert attempt_board(_intact, 0) is False
    assert seen == {"reason": True}, "the denial was logged, fight continues"


def test_capture_targets_are_data_optins():
    from src.spacehack.data.npc_ships import find_npc_ship

    assert find_npc_ship("pirate_scout").capture_layout_id == "scout_crew"
    assert find_npc_ship("pirate_raider").capture_layout_id == "cruiser_crew"
    assert find_npc_ship("militia_patrol").capture_layout_id == ""
    assert find_npc_ship("derelict_scout").capture_layout_id == ""


def test_capture_layouts_carry_console_and_crew():
    from src.spacehack.dungeon_layout import load_layout

    for lid in ("scout_crew", "cruiser_crew"):
        _map, _spawn = load_layout(lid)
        assert _spawn is not None, lid
        assert any(e.char == "C" for e in _map.entities), lid
        assert any(e.char in "rR" for e in _map.entities), lid


def test_begin_capture_boarding_consumes_the_hull(monkeypatch):
    """The ship is consumed at ENTRY: gone from the space map, spawn
    record dropped, before the player steps inside the interior."""
    from src.spacehack.game_interactions import begin_capture_boarding

    _boarded = SimpleNamespace(procedural_squad_id="sq_9", npc_ship_id="pirate_scout")
    _space_map = SimpleNamespace(entities=[_boarded], width=80, height=60)
    _ctx = SimpleNamespace(
        game_map=_space_map, player=SimpleNamespace(pos=world.Position(11, 10)),
        log=SimpleNamespace(add=lambda *a, **k: None),
        procedural_spawns={"sol": [SimpleNamespace(squad_id="sq_9", npc_id="pirate_scout")]},
        ground_hp=10, ground_max_hp=20,
    )
    _interior = SimpleNamespace(entities=[], seen=None)
    _entered = {}
    monkeypatch.setattr(
        "src.spacehack.dungeon.load_layout",
        lambda lid, **k: (_interior, world.Position(8, 15)),
    )
    monkeypatch.setattr(
        "src.spacehack.game_interactions._enter_boarding_dungeon",
        lambda state, spec, dm, sp, reboard: _entered.update(
            spec=spec.id, dm=dm, reboard=reboard,
        ),
    )
    _cr = CombatResult(outcome="BOARDED", boarded_spec_id="pirate_scout",
                       boarded_ent=_boarded)

    begin_capture_boarding(_ctx, None, _cr)

    assert _boarded not in _space_map.entities, "the hull is gone"
    assert _ctx.procedural_spawns["sol"] == [], "the spawn record is dropped"
    assert _interior.capture_spec_id == "pirate_scout"
    assert _entered == {"spec": "pirate_scout", "dm": _interior, "reboard": False}


def test_input_b_maps_to_board_not_the_vim_diagonal():
    """The action table wins over movement: B boards (the reviewer's
    blocker — 'b' is a VIM diagonal; the table entry was dead code)."""
    from src.spacehack.combat._loop import _input_action

    _event = SimpleNamespace(key_name="b")
    assert _input_action(
        _event, rules=SimpleNamespace(try_board=lambda *a: True),
    ) == "BOARD"
    assert _input_action(SimpleNamespace(key_name="n")) == "MOVE:n", \
        "the rest of the VIM set still moves"


def test_attempt_board_resolves_through_the_alive_list():
    """The loop's target_idx indexes the ALIVE list — after an escort
    dies, filtered index 0 is the survivor, not the dead first mate."""
    _dead = SimpleNamespace(
        alive=False, spec_id="pirate_scout", name="Dead Scout",
        shields=0, hull=0, max_hull=100, pos=world.Position(5, 5),
    )
    _live = SimpleNamespace(
        alive=True, spec_id="pirate_raider", name="Live Raider",
        shields=0, hull=10, max_hull=100, pos=world.Position(11, 10),
    )
    _live_ent = SimpleNamespace(
        procedural_squad_id="sq_2", npc_ship_id="pirate_raider",
    )
    state = SpaceCombatState(
        log=SimpleNamespace(add=lambda *a, **k: None),
        enemy_insts=[_dead, _live],
        enemy_ents={0: SimpleNamespace(procedural_squad_id="sq_1"),
                    1: _live_ent},
        player_ent=SimpleNamespace(pos=world.Position(10, 10)),
        cr=CombatResult(),
    )
    import src.spacehack.data.npc_ships as _ship_mod
    _real = _ship_mod.find_npc_ship
    _ship_mod.find_npc_ship = lambda sid: SimpleNamespace(capture_layout_id="x")
    try:
        assert attempt_board(state, 0) is True, \
            "filtered index 0 boards the LIVE survivor"
    finally:
        _ship_mod.find_npc_ship = _real
    assert state.cr.boarded_spec_id == "pirate_raider"
    assert state.cr.boarded_ent is _live_ent


def test_capture_stamps_round_trip_through_the_dungeon_payload():
    """Save/load contract: the console stamps serialize with the
    dungeon payload and restore (a save inside the capture interior
    keeps the clone available)."""
    from src.spacehack.saveload_maps import (
        _apply_dungeon_attributes, _dungeon_to_dict,
    )

    from src.spacehack.dungeon_layout import load_layout

    _map, _spawn = load_layout("scout_crew")
    _map.capture_spec_id = "pirate_scout"
    _map.cloned = False
    _data = _dungeon_to_dict(_map, None)
    _restored = SimpleNamespace(entities=[])
    _apply_dungeon_attributes(_restored, _data)
    assert _restored.capture_spec_id == "pirate_scout"
    assert _restored.cloned is False

    _map.cloned = True
    _apply_dungeon_attributes(
        _restored, _dungeon_to_dict(_map, None),
    )
    assert _restored.cloned is True, "the one-clone stamp survives"


def test_ground_combat_keeps_the_b_diagonal():
    """Rules-aware mapping: without a try_board hook (ground), "b"
    stays the VIM south-west diagonal; space rules get BOARD."""
    from src.spacehack.combat._loop import _input_action

    _event = SimpleNamespace(key_name="b")
    assert _input_action(_event) == "MOVE:b", "no rules: plain movement"
    assert _input_action(_event, rules=SimpleNamespace()) == "MOVE:b", \
        "rules without try_board: plain movement"
    assert _input_action(
        _event, rules=SimpleNamespace(try_board=lambda *a: True),
    ) == "BOARD"


def test_adopt_capture_boarding_flips_the_state(monkeypatch):
    """The state layer adopts ctx's capture transition: dungeon mode,
    interior map/player, the space map kept for the exit."""
    from types import SimpleNamespace as NS

    import src.spacehack.game_loop as gl

    _interior = object()
    _interior_player = object()
    _space_map = object()
    _space_player = object()
    _ctx = NS(game_map=_interior, player=_interior_player,
              player_active_missions=["m1"])
    _state = NS(
        ctx=_ctx, game_map=_space_map, player=_space_player,
        current_mode='space', space_game_map=None, space_player=None,
        player_active_missions=[],
    )
    gl._adopt_capture_boarding(_state)
    assert _state.current_mode == 'dungeon'
    assert _state.game_map is _interior
    assert _state.player is _interior_player
    assert _state.space_game_map is _space_map
    assert _state.space_player is _space_player
    assert _state.player_active_missions == ["m1"]
