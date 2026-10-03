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


# --- the Watcher: shriek + stare (SETTLED 42) --------------------------------


def _watcher_gei(game_map, pos=(3, 3)):
    from src.spacehack.combat import _rules_ground

    entity = world.Entity(
        "O", (170, 140, 250), world.Position(*pos), npc_char_id="watcher",
    )
    game_map.entities.append(entity)  # on the map: victim scans see it
    return _rules_ground._build_enemy_instance(entity, game_map)


def _combat_ctx(game_map, player_pos=(4, 4), player_hp=40, lines=None):
    lines = lines if lines is not None else []
    player = world.Entity("@", (1, 2, 3), world.Position(*player_pos))
    player.pos = world.Position(*player_pos)

    class _Log:
        def add_colored(self, text, color, **_kw):
            lines.append(text)

        def add(self, text, **_kw):
            lines.append(text)

    ctx = SimpleNamespace(
        player=player, log=_Log(), lines=lines,
        ground_stats=SimpleNamespace(reflexes=10, strength=10),
        player_traits=[], player_counters=SimpleNamespace(
            ground_damage_taken=0, total_kills=0,
        ),
    )
    return ctx


def _ground_state(ctx, game_map, enemies, player_hp=40):
    from src.spacehack.combat import _rules_ground

    return _rules_ground.GroundCombatState(
        ctx=ctx, game_map=game_map, enemies=enemies,
        player_hp=player_hp, player_max_hp=player_hp,
        armor_defense=16, last_attacker=None,
    )


class TestWatcherTurnStart:
    def test_seeing_watcher_marks_shrieks_and_spends_one_ap(self):
        game_map = _floor_map()
        gei = _watcher_gei(game_map)
        ctx = _combat_ctx(game_map, player_pos=(4, 4))
        state = _ground_state(ctx, game_map, [gei])
        _ancients.enemy_turn_start(state, ctx, gei, game_map)
        assert gei.ap == 3  # the shriek booked its FIRST AP
        assert game_map.stare_zones == {(4, 4): [id(gei.entity)]}
        assert ctx.lines == [
            "The Watcher turns and looks at you, its eye flashing red.",
            "The floor beneath you begins to glow.",
            "The Watcher lets out a piercing shriek.",
        ]

    def test_blind_watcher_marks_nothing(self):
        game_map = _floor_map()
        # The mutual-sight doctrine: the Watcher sees the player iff
        # its own cell sits in the player's sight grid. A fog grid
        # that says the Watcher's cell is unseen = blind.
        game_map.seen = [[True] * 8 for _ in range(6)]
        game_map.visible = [[False] * 8 for _ in range(6)]
        gei = _watcher_gei(game_map, pos=(3, 3))
        ctx = _combat_ctx(game_map, player_pos=(7, 7))
        state = _ground_state(ctx, game_map, [gei])
        assert _ancients.watcher_turn_start(state, ctx, gei, game_map) == 0
        assert game_map.stare_zones is None
        assert ctx.lines == []

    def test_stacked_watchers_coincide_and_stack(self):
        game_map = _floor_map()
        first = _watcher_gei(game_map, pos=(2, 4))
        second = _watcher_gei(game_map, pos=(6, 4))
        ctx = _combat_ctx(game_map, player_pos=(4, 4))
        state = _ground_state(ctx, game_map, [first, second])
        _ancients.watcher_turn_start(state, ctx, first, game_map)
        _ancients.watcher_turn_start(state, ctx, second, game_map)
        assert game_map.stare_zones == {
            (4, 4): [id(first.entity), id(second.entity)],
        }
        # the glow line reads brighter on the second (live) zone
        assert ctx.lines.count("The floor beneath you glows brighter.") == 1


class TestShriek:
    def test_heard_is_not_aggroed_and_dormant_stay_deaf(self):
        game_map = _floor_map(20, 12)
        awake = world.Entity(
            "S", (170, 140, 250), world.Position(10, 2), npc_char_id="shredder",
        )
        dormant = world.Entity(
            "W", (110, 110, 110), world.Position(10, 3), npc_char_id="warden",
            powered_down=True,
        )
        game_map.entities.extend([awake, dormant])
        ctx = _combat_ctx(game_map, player_pos=(2, 2))
        stamped = _ancients.noise.emit_radius(ctx, game_map, world.Position(2, 2), 32)
        assert awake in stamped and awake.last_seen_pos == world.Position(2, 2)
        assert dormant not in stamped and dormant.last_seen_pos is None
        assert len(game_map.entities) == 2  # no spawns (SETTLED 21)

    def test_radius_gates_hearing(self):
        game_map = _floor_map(40, 12)
        far = world.Entity(
            "S", (170, 140, 250), world.Position(35, 2), npc_char_id="shredder",
        )
        game_map.entities.append(far)
        ctx = _combat_ctx(game_map, player_pos=(2, 2))
        assert _ancients.noise.emit_radius(
            ctx, game_map, world.Position(2, 2), 32,
        ) == []
        assert far.last_seen_pos is None


class TestStareEruption:
    def _marked(self, game_map, ctx, gei, cell):
        state = _ground_state(ctx, game_map, [gei])
        _ancients.watcher_turn_start(state, ctx, gei, game_map)
        return state

    def test_core_hits_harder_than_ring_and_armor_soaks(self):
        game_map = _floor_map()
        gei = _watcher_gei(game_map, pos=(6, 6))
        ctx = _combat_ctx(game_map, player_pos=(4, 4))
        state = self._marked(game_map, ctx, gei, (4, 4))
        _ancients.resolve_stare_eruptions(state, ctx, game_map)
        # core: 36 - 16 soak = 20 (no dodge roll, no to-hit)
        assert state.player_hp == 40 - 20
        assert "causing 20 damage to you." in " ".join(ctx.lines)

        # ring: stand one cell off the fixed cell at eruption
        game_map2 = _floor_map()
        gei2 = _watcher_gei(game_map2, pos=(6, 6))
        ctx2 = _combat_ctx(game_map2, player_pos=(4, 4))
        state2 = self._marked(game_map2, ctx2, gei2, (4, 4))
        ctx2.player.pos = world.Position(5, 4)  # vacated to the ring
        _ancients.resolve_stare_eruptions(state2, ctx2, game_map2)
        # ring: 36*1//2 - 16 = 18-16 = 2 -> min 1? (18-16=2)
        assert state2.player_hp == 40 - 2

    def test_vacated_zone_hits_nothing(self):
        game_map = _floor_map()
        gei = _watcher_gei(game_map, pos=(6, 6))
        ctx = _combat_ctx(game_map, player_pos=(4, 4))
        state = self._marked(game_map, ctx, gei, (4, 4))
        ctx.player.pos = world.Position(9, 9)  # fully clear
        _ancients.resolve_stare_eruptions(state, ctx, game_map)
        assert state.player_hp == 40
        assert ctx.lines[-1] == "The floor erupts in a violent explosion."

    def test_stacked_watchers_double_the_zone(self):
        game_map = _floor_map()
        first = _watcher_gei(game_map, pos=(2, 4))
        second = _watcher_gei(game_map, pos=(6, 4))
        ctx = _combat_ctx(game_map, player_pos=(4, 4))
        state = _ground_state(ctx, game_map, [first, second])
        _ancients.watcher_turn_start(state, ctx, first, game_map)
        _ancients.watcher_turn_start(state, ctx, second, game_map)
        _ancients.resolve_stare_eruptions(state, ctx, game_map)
        # two stacks, core: 36*2 - 16 = 56
        assert state.player_hp == 40 - 56

    def test_enemy_victim_dies_drops_and_grants_no_player_credit(self):
        game_map = _floor_map()
        watcher = _watcher_gei(game_map, pos=(6, 6))
        from src.spacehack.combat import _rules_ground

        # The baiting vector: the zone fixed where the player stood;
        # the player vacates and a lured victim sits in the ring.
        victim_ent = world.Entity(
            "r", (220, 120, 80), world.Position(5, 4),
            npc_char_id="pirate_rifleman",
        )
        game_map.entities.append(victim_ent)
        victim = _rules_ground._build_enemy_instance(victim_ent, game_map)
        victim.hp = 1  # one ring hit kills it
        victim_ent.hp = 1
        ctx = _combat_ctx(game_map, player_pos=(4, 4))
        state = _ground_state(ctx, game_map, [watcher, victim])
        _ancients.watcher_turn_start(state, ctx, watcher, game_map)
        ctx.player.pos = world.Position(9, 9)  # vacated — the trap is baited
        _ancients.resolve_stare_eruptions(state, ctx, game_map)
        assert not victim.alive
        assert victim_ent not in game_map.entities  # body removed
        # the victim's own drops land (rifleman carries loot pools)
        assert any(getattr(e, "loot_data", None) for e in game_map.entities)
        # NO player credit: no kill counted, no damage taken
        assert ctx.player_counters.total_kills == 0
        assert state.player_hp == 40

    def test_player_death_tombstones_the_watcher(self):
        game_map = _floor_map()
        gei = _watcher_gei(game_map, pos=(6, 6))
        ctx = _combat_ctx(game_map, player_pos=(4, 4), player_hp=5)
        state = self._marked(game_map, ctx, gei, (4, 4))
        state.player_hp = 5
        assert _ancients.resolve_stare_eruptions(state, ctx, game_map) == "DEFEAT"
        assert state.last_attacker == "Watcher"

    def test_dead_watchers_zone_fades_before_erupting(self):
        game_map = _floor_map()
        gei = _watcher_gei(game_map, pos=(6, 6))
        ctx = _combat_ctx(game_map, player_pos=(4, 4))
        state = self._marked(game_map, ctx, gei, (4, 4))
        gei.hp = 0  # the player killed it during their turn
        _ancients.resolve_stare_eruptions(state, ctx, game_map)
        assert state.player_hp == 40  # defused — never erupted
        assert game_map.stare_zones in (None, {})

    def test_fade_on_disengage(self):
        game_map = _floor_map()
        gei = _watcher_gei(game_map, pos=(6, 6))
        ctx = _combat_ctx(game_map, player_pos=(4, 4))
        state = self._marked(game_map, ctx, gei, (4, 4))
        _ancients.fade_stare_zones(game_map)
        assert game_map.stare_zones in (None, {})
        assert state.player_hp == 40


class TestWeaponlessDrift:
    def _run_turn(self, game_map, ctx, dial, ap=4, roll=50):
        """Dial-driven drift with the roll STUBBED (the real RNG could
        roll the 1% edge at dial 100 and flake the pin)."""
        import dataclasses

        from src.spacehack.combat import _ai_ground
        from src.spacehack.data.npc_chars import find_npc_char as _find
        from tests.support.asyncutil import run as _run

        entity = world.Entity(
            "O", (170, 140, 250), world.Position(3, 3), npc_char_id="watcher",
        )
        spec = dataclasses.replace(
            _find("watcher"), ai_aggressiveness=dial,
        )

        class _Roll:
            @staticmethod
            def randint(*_args):
                return roll

            @staticmethod
            def choice(pool):
                return pool[0]

        original = _ai_ground.RNG
        _ai_ground.RNG = _Roll
        try:
            result = _run(_ai_ground.run_ground_enemy_turn(
                ctx, enemy_spec=spec, enemy_stats=SimpleNamespace(
                    reflexes=100, strength=10,
                ),
                enemy_ap=ap, player_pos=ctx.player.pos, enemy_entity=entity,
                game_map=game_map, armor_defense=0,
            ))
        finally:
            _ai_ground.RNG = original
        return entity, result

    def test_low_dial_drifts_and_logs_nothing(self):
        game_map = _floor_map()
        ctx = _combat_ctx(game_map, player_pos=(4, 4))
        entity, (ap, dmg, fired, cells) = self._run_turn(
            game_map, ctx, dial=0, roll=50,
        )
        assert cells >= 1  # never a statue while a legal step exists
        assert (ap, dmg, fired) == (0, 0, False)
        assert ctx.lines == []  # wordless — no "moves into position."

    def test_high_dial_weaponless_holds(self):
        game_map = _floor_map()
        ctx = _combat_ctx(game_map, player_pos=(4, 4))
        entity, (ap, dmg, fired, cells) = self._run_turn(
            game_map, ctx, dial=100, roll=50,  # 50 < 100: hold
        )
        assert (ap, cells) == (4, 0)
        assert ctx.lines == []

    def test_boxed_in_weaponless_holds_without_spinning(self):
        game_map = _floor_map()
        wall = world.Tile("wall", "#", False, (1, 1, 1), (0, 0, 0))
        for dx in (-1, 0, 1):
            for dy in (-1, 0, 1):
                if (dx, dy) != (0, 0):
                    game_map.tiles[3 + dy][3 + dx] = wall
        ctx = _combat_ctx(game_map, player_pos=(7, 7))
        entity, (ap, dmg, fired, cells) = self._run_turn(game_map, ctx, dial=0)
        assert (ap, cells) == (4, 0)  # no legal step: hold, never spin


def test_weaponless_turn_runs_through_the_enemy_turns_impl():
    """The :745 weapon-gate drop: a weaponless spec takes its turn in
    the per-round loop (the drift), not a silent skip."""
    from src.spacehack.combat import _rules_ground
    from tests.support.asyncutil import run as _run

    game_map = _floor_map()
    gei = _watcher_gei(game_map, pos=(3, 3))
    ctx = _combat_ctx(game_map, player_pos=(6, 6))
    old_state = _rules_ground._state
    _rules_ground._state = _ground_state(ctx, game_map, [gei])
    try:
        async def _ai(_ctx, **_kw):
            return (_kw["enemy_ap"], 0, False, 1)

        _run(_rules_ground._run_enemy_turns_impl(ctx, game_map, _ai))
    finally:
        _rules_ground._state = old_state
    # the watcher's preamble ran (shriek + mark) and the AI took its turn
    assert any("shriek" in line for line in ctx.lines)
    assert game_map.stare_zones == {(6, 6): [id(gei.entity)]}


def test_stare_state_save_round_trip_and_old_save_tolerance():
    from src.spacehack.saveload_maps import (
        _apply_dungeon_attributes, _dungeon_to_dict,
    )

    game_map = _floor_map()
    game_map.field_tiles = {(5, 5): 30, (6, 5): 12}
    game_map.stare_zones = {(2, 2): [1, 2]}
    payload = _dungeon_to_dict(game_map, None)
    assert payload["field_tiles"] == [[5, 5, 30], [6, 5, 12]]
    assert payload["stare_zones"] == [[2, 2, 2]]  # counts, not ids

    restored = world.GameMap(
        width=game_map.width, height=game_map.height,
        tiles=game_map.tiles, entities=[],
    )
    _apply_dungeon_attributes(restored, payload)
    assert restored.field_tiles == {(5, 5): 30, (6, 5): 12}
    # Stare zones are combat-scoped: no zone restores armed (fake
    # markers would render-then-defuse — a half-state).
    assert restored.stare_zones == {}

    # old save: neither key — tolerated
    old = world.GameMap(
        width=4, height=4, tiles=game_map.tiles[:4], entities=[],
    )
    _apply_dungeon_attributes(old, {"width": 4, "height": 4})
    assert old.stare_zones == {}
    assert old.field_tiles == {}


def test_eruption_victim_never_enters_the_defeated_lists():
    """The rep back-door (the review catch): an eruption kill is NOT a
    player kill — get_combat_result must not list it, or faction rep
    flows through _apply_ground_combat_rep."""
    from src.spacehack.combat import _rules_ground

    game_map = _floor_map()
    watcher = _watcher_gei(game_map, pos=(6, 6))
    from src.spacehack.combat import _rules_ground as _rg

    victim_ent = world.Entity(
        "r", (220, 120, 80), world.Position(5, 4),
        npc_char_id="pirate_rifleman",
    )
    game_map.entities.append(victim_ent)
    victim = _rg._build_enemy_instance(victim_ent, game_map)
    victim.hp = 1
    victim_ent.hp = 1
    player_kill_ent = world.Entity(
        "r", (220, 120, 80), world.Position(7, 7),
        npc_char_id="pirate_rifleman",
    )
    game_map.entities.append(player_kill_ent)
    player_kill = _rg._build_enemy_instance(player_kill_ent, game_map)
    player_kill.hp = 0  # the player shot this one
    ctx = _combat_ctx(game_map, player_pos=(4, 4))
    state = _ground_state(ctx, game_map, [watcher, victim, player_kill])
    _ancients.watcher_turn_start(state, ctx, watcher, game_map)
    ctx.player.pos = world.Position(9, 9)
    _ancients.resolve_stare_eruptions(state, ctx, game_map)

    _rg._state = state
    try:
        result = _rules_ground.get_combat_result()
    finally:
        _rg._state = None
    assert result.defeated_spec_ids == ["pirate_rifleman"]  # only the player's
    assert result.defeated_names.count("Pirate Rifleman") == 1


def test_eruption_fires_before_enemy_turns_in_the_shared_loop(monkeypatch):
    """The load-bearing ordering pin: the eruption runs at the END of
    the player's spent turn, BEFORE enemy turns — moving it beside
    ``advance_flights`` would give the player zero vacate turns and
    this test fails."""
    from src.spacehack.combat import _loop, _rules_ground
    from tests.support.asyncutil import as_async, run as _run

    game_map = _floor_map()
    gei = _watcher_gei(game_map, pos=(6, 6))
    ctx = _combat_ctx(game_map, player_pos=(4, 4))
    state = _ground_state(ctx, game_map, [gei])
    state.player_ap = 0
    _ancients.watcher_turn_start(state, ctx, gei, game_map)  # zone live

    order: list = []
    monkeypatch.setattr(_rules_ground, "_state", state)
    _real_erupt = _rules_ground.resolve_stare_eruptions

    async def _erupt_spy(_ctx, _map):
        order.append("erupt")
        return await _real_erupt(_ctx, _map)

    monkeypatch.setattr(_rules_ground, "resolve_stare_eruptions", _erupt_spy)
    monkeypatch.setattr(_rules_ground, "run_enemy_turns", as_async(
        lambda *_a, **_k: order.append("enemy_turns") or 0,
    ))
    monkeypatch.setattr(_rules_ground, "check_reinforcements", lambda *a, **k:
                        order.append("reinforcements"))
    monkeypatch.setattr(_rules_ground, "reset_turn", lambda *a, **k:
                        order.append("reset_turn"))
    _run(_loop._end_player_turn(ctx, game_map, _rules_ground, 1))
    # THE ordering pin: relocating the hook beside advance_flights
    # (after enemy turns) fails this equality — the player would get
    # zero vacate turns against an enemy-phase re-fix.
    assert order == ["erupt", "enemy_turns", "reinforcements", "reset_turn"]
    # the zone's damage landed during the turn-end
    assert state.player_hp == 40 - 20
    assert game_map.stare_zones in (None, {})  # spent its beat


def test_eruption_noise_is_deduped_per_zone_cell(monkeypatch):
    """One blast-class emission per zone CELL per beat: stacked
    Watchers coincide into one zone key — one emission, blast-class
    radius, through the emit_radius variant."""
    from src.spacehack import noise as _noise

    calls: list = []
    real = _noise.emit_radius

    def _spy(_ctx, _map, origin, radius):
        calls.append((origin.x, origin.y, radius))
        return real(_ctx, _map, origin, radius)

    monkeypatch.setattr(_noise, "emit_radius", _spy)

    game_map = _floor_map()
    first = _watcher_gei(game_map, pos=(2, 4))
    second = _watcher_gei(game_map, pos=(6, 4))
    ctx = _combat_ctx(game_map, player_pos=(4, 4))
    state = _ground_state(ctx, game_map, [first, second])
    _ancients.watcher_turn_start(state, ctx, first, game_map)
    _ancients.watcher_turn_start(state, ctx, second, game_map)
    calls.clear()  # the shrieks already emitted; watch the eruption beat
    _ancients.resolve_stare_eruptions(state, ctx, game_map)
    assert calls == [(4, 4, _ancients.ERUPTION_NOISE_RADIUS)]


# --- the Warden: the force field (SETTLED 42) --------------------------------


def _warden_gei(game_map, pos=(4, 4)):
    from src.spacehack.combat import _rules_ground

    entity = world.Entity(
        "W", (170, 140, 250), world.Position(*pos), npc_char_id="warden",
        bold=True,
    )
    game_map.entities.append(entity)  # on the map: sibling/victim scans see it
    return _rules_ground._build_enemy_instance(entity, game_map)


class TestFieldShell:
    def test_shell_is_a_radius2_ring_walkable_only(self):
        game_map = _floor_map(12, 12)
        # a wall inside the ring's band: no field tile there
        game_map.tiles[4][6] = world.Tile(
            "wall", "#", False, (1, 1, 1), (0, 0, 0),
        )
        cells = _ancients.shell_cells(game_map, world.Position(6, 6))
        assert (4, 4) in cells and (8, 8) in cells   # radius-2 ring
        assert (6, 6) not in cells                   # empty interior
        assert (5, 5) not in cells and (7, 7) not in cells  # radius 1 open
        assert (6, 4) not in cells                   # the wall hosts no tile
        assert all(max(abs(x - 6), abs(y - 6)) == 2 for x, y in cells)

    def test_combat_entry_stands_the_field_up_full(self):
        game_map = _floor_map(12, 12)
        gei = _warden_gei(game_map, pos=(6, 6))
        assert gei is not None
        tiles = game_map.field_tiles
        assert tiles and set(tiles) == set(
            _ancients.shell_cells(game_map, world.Position(6, 6))
        )
        assert all(hp == 30 for hp in tiles.values())

    def test_turn_start_regens_capped_and_regrows_carved_holes(self):
        game_map = _floor_map(12, 12)
        gei = _warden_gei(game_map, pos=(6, 6))
        # carve a hole: destroy one tile outright
        carved = (6, 4)
        del game_map.field_tiles[carved]
        # a damaged tile regens +10 to the cap
        game_map.field_tiles[(4, 4)] = 25
        _ancients.warden_turn_start(gei, game_map)
        assert game_map.field_tiles[carved] == 10  # regrown from 0
        assert game_map.field_tiles[(4, 4)] == 30  # capped at full

    def test_moved_warden_drops_old_cells(self):
        game_map = _floor_map(14, 14)
        gei = _warden_gei(game_map, pos=(6, 6))
        gei.entity.pos = world.Position(9, 9)
        _ancients.warden_turn_start(gei, game_map)
        cells = set(game_map.field_tiles)
        assert (6, 4) not in cells        # the old shell is gone
        assert (9, 9 + 2) in cells        # the new shell stands (post-regen)
        assert all(max(abs(x - 9), abs(y - 9)) == 2 for x, y in cells)

    def test_sibling_wardens_shells_survive_each_others_turns(self):
        """Plural Wardens are authored (the review catch): one
        Warden's re-derive must never drop a sibling's shell."""
        game_map = _floor_map(20, 20)
        first = _warden_gei(game_map, pos=(6, 6))
        _warden_gei(game_map, pos=(14, 14))  # the sibling (on the map)
        second_cells = set(game_map.field_tiles)
        # both shells stood at combat entry
        assert (6, 4) in second_cells and (14, 12) in second_cells
        _ancients.warden_turn_start(first, game_map)
        cells = set(game_map.field_tiles)
        assert (14, 12) in cells  # the sibling's shell survives
        assert (14, 14 + 2) in cells
        assert (6, 4) in cells     # my own shell regen'd in place
        # and a line into the sibling still absorbs
        assert _ancients.absorb_shot(
            game_map, world.Position(14, 10), world.Position(14, 14),
            shooter_carries_field=False,
        ) == (14, 12)


class TestAbsorption:
    def _fielded_map(self):
        game_map = _floor_map(12, 12)
        _warden_gei(game_map, pos=(6, 6))
        return game_map

    def test_crossing_shot_absorbs_at_the_first_live_tile(self):
        game_map = self._fielded_map()
        cell = _ancients.absorb_shot(
            game_map, world.Position(6, 1), world.Position(6, 6),
            shooter_carries_field=False,
        )
        assert cell == (6, 4)  # the first shell cell on the line

    def test_field_carrier_shoots_through(self):
        game_map = self._fielded_map()
        assert _ancients.absorb_shot(
            game_map, world.Position(6, 6), world.Position(6, 1),
            shooter_carries_field=True,
        ) is None

    def test_no_field_never_absorbs(self):
        game_map = _floor_map(12, 12)
        assert _ancients.absorb_shot(
            game_map, world.Position(6, 1), world.Position(6, 6),
            shooter_carries_field=False,
        ) is None

    def test_destroyed_tile_is_open_ground(self):
        game_map = self._fielded_map()
        del game_map.field_tiles[(6, 4)]
        assert _ancients.absorb_shot(
            game_map, world.Position(6, 1), world.Position(6, 6),
            shooter_carries_field=False,
        ) is None  # the hole is open — carve + shoot through same turn

    def test_binary_blocking_overflow_is_lost(self):
        game_map = self._fielded_map()
        ctx = _combat_ctx(game_map)
        broke = _ancients.damage_field_tile(ctx, game_map, (6, 4), 8)
        assert not broke and game_map.field_tiles[(6, 4)] == 22
        assert _ancients.absorb_shot(  # still blocking at 22 HP
            game_map, world.Position(6, 1), world.Position(6, 6),
            shooter_carries_field=False,
        ) == (6, 4)

    def test_tile_break_logs_the_approved_line(self):
        game_map = self._fielded_map()
        ctx = _combat_ctx(game_map)
        broke = _ancients.damage_field_tile(ctx, game_map, (6, 4), 64)
        assert broke and (6, 4) not in game_map.field_tiles
        assert ctx.lines == ["A section of the shimmer breaks apart."]


class TestPlayerSeamAbsorption:
    def _rules_stub(self, game_map, target):
        from tests.support.asyncutil import as_async

        class _Rules:
            def enemy_pos(self, t):
                return t.pos

            def enemy_alive(self, t):
                return t is target and target.hp > 0

            def weapon_ap_cost(self, _wid, _ctx):
                return 2

            def consume_shot(self, slot, _ctx):
                self.consumed = slot

            def damage(self, *_a):
                raise AssertionError(
                    "the body must never pay an absorbed shot",
                )

            animate_fire = staticmethod(as_async(lambda *a, **k: None))

        return _Rules()

    def test_absorbed_shot_pays_the_tile_and_consumes(self):
        from src.spacehack.combat import _loop
        from tests.support.asyncutil import run as _run

        game_map = _floor_map(12, 12)
        _warden_gei(game_map, pos=(6, 6))
        target = SimpleNamespace(
            pos=world.Position(6, 6), hp=85, name="Warden",
        )
        ctx = _combat_ctx(game_map, player_pos=(6, 1))
        rules = self._rules_stub(game_map, target)
        hit, ap = _run(_loop._roll_player_shot(
            None, ctx, game_map, rules, 0, target,
            "railgun", "Railgun", 0,
        ))
        assert hit is False
        assert "The shimmer swallows your shot." in ctx.lines
        assert "A section of the shimmer breaks apart." in ctx.lines  # 64 > 30
        assert game_map.field_tiles.get((6, 4)) is None
        assert target.hp == 85  # the body never paid
        assert rules.consumed == 0
        assert ap == 2


class TestEnemySeamAbsorption:
    def test_non_field_shooter_absorbs_wordless(self):
        from src.spacehack.combat import _ai_ground
        from tests.support.asyncutil import run as _run

        game_map = _floor_map(12, 12)
        _warden_gei(game_map, pos=(6, 6))  # the field stands
        # the player INSIDE the shell: an outside shooter's line
        # crosses the (6, 4) tile to reach them
        ctx = _combat_ctx(game_map, player_pos=(6, 5))
        ctx.ground_stats = SimpleNamespace(reflexes=10, strength=10)
        shooter = world.Entity(
            "e", (90, 120, 200), world.Position(6, 0), npc_char_id="consortium_gunner",
        )
        from src.spacehack.data.npc_chars import find_npc_char as _find

        dmg = _run(_ai_ground._one_enemy_shot(
            ctx, None, None, game_map, shooter,
            "kinetic_rifle", 0, _find("consortium_gunner"),
            SimpleNamespace(reflexes=50, strength=20), 0, 0,
        ))
        assert dmg == 0  # the player never paid — the tile did
        assert game_map.field_tiles[(6, 4)] == 30 - 20  # the rifle's full 20
        assert state_line_absent(ctx)  # wordless: no absorb line

    def test_warden_shot_fires_through_its_own_field(self):
        from src.spacehack.combat import _ai_ground
        from tests.support.asyncutil import run as _run

        game_map = _floor_map(12, 12)
        gei = _warden_gei(game_map, pos=(6, 6))
        ctx = _combat_ctx(game_map, player_pos=(6, 1))
        ctx.ground_stats = SimpleNamespace(reflexes=10, strength=10)

        class _AlwaysHit:
            @staticmethod
            def randint(*_args):
                return 1

        original = _ai_ground.RNG
        _ai_ground.RNG = _AlwaysHit
        try:
            dmg = _run(_ai_ground._one_enemy_shot(
                ctx, None, None, game_map, gei.entity,
                "ancient_warden_shot", 0, gei.spec,
                gei.stats, 0, 0,
            ))
        finally:
            _ai_ground.RNG = original
        assert dmg == 30  # armor-bypassed full price reached the player
        assert game_map.field_tiles[(6, 4)] == 30  # its own field untouched


def state_line_absent(ctx) -> bool:
    return not any("shimmer" in line for line in ctx.lines)


class TestBlastCarvesTiles:
    def test_rocket_at_the_shell_carves_multiple_tiles(self):
        from src.spacehack.combat import _ground_blast

        game_map = _floor_map(12, 12)
        gei = _warden_gei(game_map, pos=(6, 6))
        ctx = _combat_ctx(game_map, player_pos=(6, 1))
        ctx.ground_stats = SimpleNamespace(reflexes=10, strength=10)
        state = _ground_state(ctx, game_map, [gei])
        # the detonation centered on the shell tile at (6, 4)
        enemy_hits, player_damage = _ground_blast.explosive_blast(
            state, "rocket_launcher", gei, ctx, primary_hit=False,
            quality=0, center=world.Position(6, 4),
        )
        # the Warden at radius 2 is OUTSIDE the 3x3: untouched — and
        # the player at distance 3 takes no self-splash either
        assert enemy_hits == () and gei.hp == gei.max_hp
        assert player_damage == 0
        # the center tile and its two side neighbours on the shell
        # broke (full 60 at the center, 30 splash vs 30 HP beside it)
        assert (6, 4) not in game_map.field_tiles
        assert (5, 4) not in game_map.field_tiles
        assert (7, 4) not in game_map.field_tiles

    def test_blast_near_a_shell_carves_without_absorption(self):
        from src.spacehack.combat import _ground_blast

        game_map = _floor_map(12, 12)
        gei = _warden_gei(game_map, pos=(6, 6))
        ctx = _combat_ctx(game_map, player_pos=(2, 2))
        ctx.ground_stats = SimpleNamespace(reflexes=10, strength=10)
        state = _ground_state(ctx, game_map, [gei])
        # a grenade-equivalent blast one cell north of the shell: the
        # 3x3 catches the shell's top row; 50% splash of 60 breaks
        # 30-HP tiles outright
        _ground_blast.explosive_blast(
            state, "rocket_launcher", gei, ctx, primary_hit=False,
            quality=0, center=world.Position(6, 3),
        )
        for _broken in ((6, 4), (5, 4), (7, 4)):
            assert _broken not in game_map.field_tiles
        assert (4, 6) in game_map.field_tiles  # the far side stands


class TestFieldDeathAndPersistence:
    def test_last_warden_death_drops_the_field(self):
        game_map = _floor_map(12, 12)
        gei = _warden_gei(game_map, pos=(6, 6))
        # on_kill removes the body BEFORE the drop call
        game_map.entities.remove(gei.entity)
        _ancients.maybe_drop_field(game_map, gei.spec)
        assert game_map.field_tiles is None

    def test_sibling_death_collapses_to_the_survivors_shell(self):
        game_map = _floor_map(14, 14)
        gei = _warden_gei(game_map, pos=(6, 6))
        sibling = world.Entity(
            "W", (170, 140, 250), world.Position(10, 10),
            npc_char_id="warden",
        )
        game_map.entities.append(sibling)
        # the sibling's own shell stands (its turn derived it)
        from src.spacehack.combat import _rules_ground

        sibling_gei = _rules_ground._build_enemy_instance(sibling, game_map)
        _ancients.warden_turn_start(sibling_gei, game_map)
        game_map.entities.remove(gei.entity)  # on_kill removes first
        _ancients.maybe_drop_field(game_map, gei.spec)
        assert game_map.field_tiles is not None
        # the DEAD one's ring collapsed; only the survivor's stands
        assert (6, 4) not in game_map.field_tiles
        assert (10, 8) in game_map.field_tiles

    def test_eruption_killed_warden_drops_its_field(self):
        """The player-kill path's twin (the review catch): a Warden
        killed by a stare eruption must not leave an ownerless
        shimmer blocking the floor forever."""
        game_map = _floor_map(12, 12)
        watcher = _watcher_gei(game_map, pos=(2, 2))
        warden = _warden_gei(game_map, pos=(6, 6))
        assert game_map.field_tiles  # the shell stood
        ctx = _combat_ctx(game_map, player_pos=(4, 4))
        state = _ground_state(ctx, game_map, [watcher, warden])
        # the warden stands in the watcher's zone, hp 1
        warden.entity.pos = world.Position(5, 4)
        warden.hp = 1
        warden.entity.hp = 1
        _ancients.watcher_turn_start(state, ctx, watcher, game_map)
        ctx.player.pos = world.Position(11, 11)
        _ancients.resolve_stare_eruptions(state, ctx, game_map)
        assert not warden.alive
        assert game_map.field_tiles is None  # no orphan shimmer

    def test_field_tiles_serialize_by_position(self):
        from src.spacehack.saveload_maps import _dungeon_to_dict

        game_map = _floor_map(12, 12)
        game_map.field_tiles = {(4, 4): 30, (4, 5): 0}
        payload = _dungeon_to_dict(game_map, None)
        assert payload["field_tiles"] == [[4, 4, 30]]  # dead tiles don't ride


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


def test_diagonal_adjacency_is_melee_range_for_enemies():
    """The p9 playtest catch ("shredders never attack"): an enemy
    closing on a DIAGONAL deadlocked — the band gates compared raw
    Euclidean distance (1.414 > max_range 1) while the player's own
    fire gate int-truncates. Both sides now read the same metric."""
    from src.spacehack.combat._ai_ground import _within_max
    from src.spacehack.data.ground_weapons import find_ground_weapon

    claws = find_ground_weapon("ancient_claws")
    assert _within_max(claws, 1.414, True)   # diagonal adjacency
    assert _within_max(claws, 1.0, True)
    assert not _within_max(claws, 1.5 + 1, True)  # beyond max stays out
    shot = find_ground_weapon("ancient_warden_shot")
    assert _within_max(shot, 2.828, True)    # diagonal 2 inside min 2


def test_diagonal_shredder_swings_not_stalls():
    """The end-to-end deadlock pin: a shredder diagonally adjacent to
    the player spends its turn ATTACKING (the volley picks the claws),
    not stalled in "moves into position" forever."""
    from src.spacehack.combat import _rules_ground
    from tests.support.asyncutil import run as _run

    game_map = _floor_map(12, 12)
    shredder_ent = world.Entity(
        "S", (170, 140, 250), world.Position(5, 5), npc_char_id="shredder",
    )
    game_map.entities.append(shredder_ent)
    ctx = _combat_ctx(game_map, player_pos=(6, 4))  # diagonal to (5,5)
    ctx.ground_stats = SimpleNamespace(reflexes=58, strength=30)
    old = _rules_ground._state
    _rules_ground._state = _rules_ground.GroundCombatState(
        ctx=ctx, game_map=game_map,
        enemies=[_rules_ground._build_enemy_instance(shredder_ent, game_map)],
        player_hp=40, player_max_hp=40, armor_defense=23,
    )
    try:
        for _ in range(3):
            _rules_ground._state.player_ap = 0
            dmg = _run(_rules_ground.run_enemy_turns(ctx, game_map))
            if dmg:
                break
        assert dmg and dmg > 0, (
            "the diagonal-adjacent shredder never attacked"
        )
        assert any("Shredder Claws" in line for line in ctx.lines)
    finally:
        _rules_ground._state = old


def test_field_renders_as_the_violet_curtain():
    """The playtest readability dial (2026-10-03, "hard to see"): the
    shimmer paints a medium-shade glyph over its OWN violet-dark cell
    background — a translucent curtain at a glance — and destroyed
    tiles clear from the render."""
    from src.spacehack.world_render import world_draw_commands

    game_map = _floor_map(12, 12)
    game_map.field_tiles = {(6, 6): 30}
    commands = world_draw_commands(
        game_map, region_x=0, region_y=0, region_w=12, region_h=12,
    )
    field_cmds = [c for c in commands if (c.x, c.y) == (6, 6)]
    assert any(
        c.char == "\u2592" and c.bg is not None and c.fg[2] > c.fg[0]
        for c in field_cmds
    ), "the shell must paint its own violet-dark cell background"

    game_map.field_tiles = {(6, 6): 0}  # destroyed: open ground again
    commands = world_draw_commands(
        game_map, region_x=0, region_y=0, region_w=12, region_h=12,
    )
    assert not any(
        c.char == "\u2592" for c in commands
    )


def test_shell_tracks_the_wardens_turn_end_position():
    """The lag catch ("as it moves the force field doesn't move with
    it"): the start-side re-derive ran BEFORE the movement — the
    shimmer trailed the body for a full round. The turn-end pass
    recenters the shell on where the Warden ENDS its turn (fresh
    cells enter at 0, no regen double-dip)."""
    game_map = _floor_map(20, 20)
    gei = _warden_gei(game_map, pos=(6, 6))
    _ancients.warden_turn_start(gei, game_map)   # start: ring at (6,6)
    # the W moves during its turn (AI steps), then the turn ends
    gei.entity.pos = world.Position(9, 9)
    _ancients.enemy_turn_end(gei, game_map)
    cells = set(game_map.field_tiles)
    assert (9, 7) in cells                        # the new ring stands
    assert all(max(abs(x - 9), abs(y - 9)) == 2 for x, y in cells)
    assert game_map.field_tiles[(9, 7)] == 0      # fresh cells regrow
    assert (6, 4) not in cells                    # the old ring dropped


def test_killing_a_warden_collapses_only_its_share():
    """The death catch ("when I kill the W the force field stays"):
    the merged-survivor rule kept the DEAD ring while the survivor's
    never stood. A death now rebuilds the field as the survivors'
    current rings — killing a W always visibly collapses something."""
    game_map = _floor_map(20, 20)
    first = _warden_gei(game_map, pos=(6, 6))
    second = _warden_gei(game_map, pos=(14, 14))
    _ancients.warden_turn_start(second, game_map)  # both rings stand
    game_map.entities.remove(first.entity)
    _ancients.maybe_drop_field(game_map, first.spec)
    cells = set(game_map.field_tiles)
    assert (6, 4) not in cells       # the dead W's ring is gone
    assert (14, 12) in cells         # the survivor keeps its own


def test_end_pass_preserves_a_stationary_sibling_shell():
    """The tracking pass shares the sibling preserve: a MOVING Warden
    A's end pass must never drop stationary sibling B's ring."""
    game_map = _floor_map(20, 20)
    first = _warden_gei(game_map, pos=(6, 6))
    second = _warden_gei(game_map, pos=(14, 14))
    _ancients.warden_turn_start(second, game_map)
    # A moves (its own turn) and its turn ends
    first.entity.pos = world.Position(9, 9)
    _ancients.enemy_turn_end(first, game_map)
    cells = set(game_map.field_tiles)
    assert (14, 12) in cells and (14, 16) in cells  # B untouched
    assert all(
        max(abs(x - 9), abs(y - 9)) == 2
        or max(abs(x - 14), abs(y - 14)) == 2
        for x, y in cells
    )


def test_aim_line_stops_at_the_shimmer():
    """The p9 playtest catch ("the targeting line is writing overtop
    of the force field"): the aim line ends at the first LIVE shell
    tile — the shimmer eats the line like it eats the shot, and the
    barrier stays visible along the blocked lane."""
    from src.spacehack.combat._animations import _draw_range_colored_line
    from src.spacehack.framebuffer import FrameBuffer

    game_map = _floor_map(16, 16)
    _warden_gei(game_map, pos=(8, 8))  # the shell stands around (8,8)
    console = FrameBuffer(16, 16)
    player = world.Position(8, 2)
    target = world.Position(8, 8)      # the line crosses (8,6)
    _draw_range_colored_line(
        console, player, target, 8, 3,
        cam_x=0, cam_y=0, view_w=16, view_h=16,
        game_map=game_map, distance_round=int,
    )
    commands = {
        (c.x, c.y): c for c in console.to_commands()
    }
    # in-bounds lane cells before the shimmer carry the line mark
    assert (8, 3) in commands
    # the first shell tile keeps its curtain, not the line's squiggle
    assert (8, 6) not in commands or commands[(8, 6)].char != "~"
