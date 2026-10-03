"""Ancient-machine mechanics (doc 48 phase 9 build 2) — combat side.

The trio's machinery against the real seam functions: knockback
application (SETTLED 42), the Shredder's mend, and — as later builds
land — the Watcher's stare/shriek and the Warden's field.
"""

from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from src.spacehack import world
from src.spacehack.combat import _ancients
from src.spacehack.combat._actions import apply_knockback
from src.spacehack.data.npc_chars import find_npc_char


def _floor_map(w: int = 8, h: int = 6) -> world.GameMap:
    tile = world.Tile("floor", ".", True, (200, 210, 220), (10, 20, 30))
    return world.GameMap(
        width=w, height=h,
        tiles=[[tile for _ in range(w)] for _ in range(h)],
        entities=[],
    )


# --- knockback (SETTLED 42 — the slam's pushback) ---------------------------


class TestApplyKnockback:
    def test_clear_field_moves_the_full_distance(self):
        game_map = _floor_map()
        victim = world.Entity("@", (1, 2, 3), world.Position(2, 2), "Player")
        moved = apply_knockback(game_map, victim, 1, 0, 2)
        assert moved == 2
        assert (victim.pos.x, victim.pos.y) == (4, 2)

    def test_wall_stops_the_ride_early(self):
        game_map = _floor_map()
        wall = world.Tile("wall", "#", False, (1, 1, 1), (0, 0, 0))
        game_map.tiles[2][4] = wall
        victim = world.Entity("@", (1, 2, 3), world.Position(2, 2), "Player")
        moved = apply_knockback(game_map, victim, 1, 0, 2)
        assert moved == 1
        assert (victim.pos.x, victim.pos.y) == (3, 2)

    def test_occupied_cell_stops_the_ride(self):
        game_map = _floor_map()
        game_map.entities.append(
            world.Entity("S", (4, 5, 6), world.Position(3, 2), "Blocker"),
        )
        victim = world.Entity("@", (1, 2, 3), world.Position(2, 2), "Player")
        moved = apply_knockback(game_map, victim, 1, 0, 2)
        assert moved == 0  # no stacking: the first step is blocked
        assert (victim.pos.x, victim.pos.y) == (2, 2)

    def test_blocked_first_step_moves_zero(self):
        game_map = _floor_map()
        wall = world.Tile("wall", "#", False, (1, 1, 1), (0, 0, 0))
        game_map.tiles[2][3] = wall
        victim = world.Entity("@", (1, 2, 3), world.Position(2, 2), "Player")
        assert apply_knockback(game_map, victim, 1, 0, 2) == 0

    def test_diagonal_vector_steps_diagonally(self):
        game_map = _floor_map()
        victim = world.Entity("@", (1, 2, 3), world.Position(2, 2), "Player")
        moved = apply_knockback(game_map, victim, 1, -1, 2)
        assert moved == 2
        assert (victim.pos.x, victim.pos.y) == (4, 0)

    def test_zero_distance_is_a_noop(self):
        game_map = _floor_map()
        victim = world.Entity("@", (1, 2, 3), world.Position(2, 2), "Player")
        assert apply_knockback(game_map, victim, 1, 0, 0) == 0
        assert (victim.pos.x, victim.pos.y) == (2, 2)


def _slam_context():
    """ctx + map with the player east of the Warden, plus a capture log."""
    lines: list = []

    class _Log:
        def add_colored(self, text, color, **_kwargs):
            lines.append(text)

        def add(self, text, **_kwargs):
            lines.append(text)

    game_map = _floor_map()
    player = world.Entity("@", (1, 2, 3), world.Position(4, 2), "Player")
    ctx = SimpleNamespace(player=player, log=_Log())
    return ctx, game_map, lines


def test_slam_hit_displaces_the_player_along_the_vector():
    from src.spacehack.combat._ai_ground import _apply_hit_knockback

    ctx, game_map, lines = _slam_context()
    warden = world.Entity("W", (1, 1, 1), world.Position(2, 2), "Warden")
    _apply_hit_knockback(
        ctx, game_map, warden, ctx.player.pos, "ancient_slam",
    )
    # ~2 east: ejected back through the shimmer (wordless — no log line).
    assert (ctx.player.pos.x, ctx.player.pos.y) == (6, 2)
    assert lines == []


def test_slam_through_the_shot_seam_displaces_and_logs_the_attack():
    """The wiring pin (the review's seam class): a slam resolving
    through the real per-shot path displaces the player; the shot's
    own attack line is the ONLY line (knockback stays wordless)."""
    from src.spacehack.combat import _ai_ground
    from tests.support.asyncutil import run as _run

    ctx, game_map, _lines = _slam_context()
    ctx.ground_stats = SimpleNamespace(reflexes=10)
    ctx.player_traits = []
    warden = world.Entity("W", (1, 1, 1), world.Position(2, 2), "Warden")

    seen_lines: list = []

    class _Log:
        def add_colored(self, text, color, **_kw):
            seen_lines.append(text)

        def add(self, text, **_kw):
            seen_lines.append(text)

    ctx.log = _Log()

    class _AlwaysHit:
        """Stand in for RNG.randint: the roll always hits."""

        @staticmethod
        def randint(*_args):
            return 1

    original = _ai_ground.RNG
    _ai_ground.RNG = _AlwaysHit
    try:
        _run(_ai_ground._one_enemy_shot(
            ctx, None, None, game_map, warden,
            "ancient_slam", 0, find_npc_char("warden"),
            SimpleNamespace(reflexes=10, strength=10),
            0, 0,
        ))
    finally:
        _ai_ground.RNG = original
    # Displaced ~2 east through the shot seam.
    assert (ctx.player.pos.x, ctx.player.pos.y) == (6, 2)
    # The attack line logged; nothing else did (knockback is wordless).
    assert len(seen_lines) == 1 and "Warden" in seen_lines[0]


def test_non_knockback_weapon_never_displaces():
    from src.spacehack.combat._ai_ground import _apply_hit_knockback

    ctx, game_map, _lines = _slam_context()
    rifleman = world.Entity("r", (1, 1, 1), world.Position(2, 2), "R")
    _apply_hit_knockback(
        ctx, game_map, rifleman, ctx.player.pos, "kinetic_rifle",
    )
    assert (ctx.player.pos.x, ctx.player.pos.y) == (4, 2)


# --- the Shredder's mend (SETTLED 42) ----------------------------------------


def _shredder_instance(hp: int, max_hp: int = 97):
    entity = world.Entity(
        "S", (170, 140, 250), world.Position(2, 2),
        npc_char_id="shredder",
    )
    return SimpleNamespace(
        entity=entity, spec=find_npc_char("shredder"),
        hp=hp, max_hp=max_hp, alive=hp > 0,
        name="Shredder",
    )


def _session_state():
    """A minimal GroundCombatState stand-in carrying the mend flag."""
    return SimpleNamespace(mend_told=set())


class TestMend:
    def test_mend_heals_at_turn_start(self):
        gei = _shredder_instance(hp=80)
        ctx, _map, lines = _slam_context()
        _ancients.mend_turn_start(_session_state(), ctx, gei)
        assert gei.hp == 85
        assert gei.entity.hp == 85  # the wound mirror syncs
        assert lines == ["The Shredder's wounds begin to mend."]

    def test_mend_caps_at_max(self):
        gei = _shredder_instance(hp=95)
        ctx, _map, _lines = _slam_context()
        _ancients.mend_turn_start(_session_state(), ctx, gei)
        assert gei.hp == 97

    def test_line_fires_once_per_engagement(self):
        gei = _shredder_instance(hp=60)
        ctx, _map, lines = _slam_context()
        state = _session_state()
        _ancients.mend_turn_start(state, ctx, gei)
        _ancients.mend_turn_start(state, ctx, gei)
        assert gei.hp == 70
        assert lines == ["The Shredder's wounds begin to mend."]  # once

    def test_unwounded_shredder_mends_nothing_and_stays_silent(self):
        gei = _shredder_instance(hp=97)
        ctx, _map, lines = _slam_context()
        _ancients.mend_turn_start(_session_state(), ctx, gei)
        assert gei.hp == 97
        assert lines == []

    def test_ordinary_rows_noop(self):
        gei = SimpleNamespace(
            entity=world.Entity("r", (1, 1, 1), world.Position(1, 1)),
            spec=find_npc_char("pirate_rifleman"), hp=5, max_hp=30,
            alive=True, name="Rifleman",
        )
        ctx, _map, lines = _slam_context()
        _ancients.mend_turn_start(_session_state(), ctx, gei)
        assert gei.hp == 5
        assert lines == []


def test_mend_wires_into_the_real_enemy_turn(monkeypatch):
    """The hook is LIVE on the per-enemy turn path: the Shredder mends
    before its AI runs (a module without its call site never mends in
    play — the silent-breakage class the review exists for)."""
    from tests.support.asyncutil import as_async, run
    from src.spacehack.combat import _rules_ground

    entity = world.Entity(
        "S", (170, 140, 250), world.Position(3, 3),
        npc_char_id="shredder",
    )
    game_map = _floor_map()
    gei = _rules_ground._build_enemy_instance(entity, game_map)
    gei.hp = gei.max_hp - 20
    entity.hp = gei.hp

    ctx, _map, lines = _slam_context()
    monkeypatch.setattr(
        _rules_ground, "_state",
        _rules_ground.GroundCombatState(ctx=ctx, game_map=game_map,
                                        enemies=[gei]),
    )
    _ai_calls: list = []

    def _ai(_ctx, **_kw):
        _ai_calls.append(_kw.get("enemy_ap"))
        return (_kw.get("enemy_ap"), 0, False, 0)

    run(_rules_ground._spend_one_enemy_turn(
        ctx, game_map, as_async(_ai), gei, 0,
    ))
    assert gei.hp == gei.max_hp - 20 + 5  # mended before the AI ran
    assert lines == ["The Shredder's wounds begin to mend."]
    assert _ai_calls  # the AI still took its turn
