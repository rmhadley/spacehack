"""Tombstone death-path pins (doc 53 phase 1) — killer tracking, the
ground damage counter, the shared finish's DEFEAT-gated write, the
death-screen notice in all three theaters, and both-theater real-fight
integrations on the balance harness.

The pure text contract and writer I/O live in ``tests/test_tombstone.py``.
"""

import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from src.spacehack import world
from src.spacehack.combat import _loop, _rules_ground
from src.spacehack.data.npc_chars import find_npc_char
from src.spacehack.data.npc_ships import find_npc_ship
from src.spacehack.game_context import PlayerCounters
from src.spacehack.message_log import MessageLog
from tests.balance import harness
from tests.balance.scenarios import (
    BalanceScenario,
    EnemySide,
    GridSpec,
    PlayerSheet,
)
from tests.balance.stances import STANCES
from tests.support.asyncutil import run as _async_run
from tests.test_tombstone import _ctx as _reader_ctx


def _floor_map(width: int = 11, height: int = 11) -> world.GameMap:
    tiles = [
        [world.DUNGEON_FLOOR for _ in range(width)] for _ in range(height)
    ]
    return world.GameMap(width=width, height=height, tiles=tiles, entities=[])


def _ground_ctx(game_map, player_pos) -> SimpleNamespace:
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


def _seed_enemy(game_map, spec_id: str, pos: tuple[int, int]) -> world.Entity:
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


def test_enemy_fire_counts_ground_damage_and_tracks_killer():
    game_map = _floor_map()
    ctx = _ground_ctx(game_map, (5, 5))
    enemy = _seed_enemy(game_map, "pirate_raider", (6, 5))
    try:
        _rules_ground.init(ctx, [enemy], game_map)
        gei = _rules_ground._state.enemies[0]
        gei.weapon_id = "kinetic_pistol"
        gei.weapon_quality = 1
        hp_before = _rules_ground._state.player_hp

        async def fake_ai(ctx, **kwargs):
            return (0, 5, True)

        damage = _async_run(_rules_ground._spend_one_enemy_turn(
            ctx, game_map, fake_ai, gei, 0,
        ))
        assert damage == 5
        assert ctx.player_counters.ground_damage_taken == 5
        assert hp_before - _rules_ground._state.player_hp == 5
        assert _rules_ground.last_attacker(ctx) == (
            "Pirate Raider's Modded Kinetic Pistol"
        )
    finally:
        _release_ground_state()


def test_self_splash_counts_ground_damage_and_pins_the_killer_line():
    game_map = _floor_map()
    ctx = _ground_ctx(game_map, (5, 6))
    enemy = _seed_enemy(game_map, "pirate_raider", (5, 5))
    try:
        _rules_ground.init(ctx, [enemy], game_map)
        gei = _rules_ground._state.enemies[0]
        hp_before = _rules_ground._state.player_hp

        _hits, player_damage = _rules_ground.explosive_blast(
            "grenade_launcher", gei, ctx,
        )
        assert player_damage >= 1
        assert ctx.player_counters.ground_damage_taken == player_damage
        assert hp_before - _rules_ground._state.player_hp == player_damage
        assert _rules_ground.last_attacker(ctx) == "your own explosives"
    finally:
        _release_ground_state()


def test_finish_combat_defeat_writes_and_stashes_the_path(monkeypatch, tmp_path):
    monkeypatch.setenv("HOME", str(tmp_path))
    game_map = _floor_map()
    ctx = _ground_ctx(game_map, (5, 5))
    enemy = _seed_enemy(game_map, "pirate_raider", (6, 5))
    try:
        _rules_ground.init(ctx, [enemy], game_map)
        _rules_ground._state.player_hp = -2
        _rules_ground._state.last_attacker = None

        cr = _loop._finish_combat(ctx, _rules_ground, "DEFEAT")

        assert cr.outcome == "DEFEAT"
        assert cr.tombstone_path is not None
        text = Path(cr.tombstone_path).read_text(encoding="utf-8")
        assert "  Slain by: unknown causes" in text
        assert "  Final state: HP -2/26  AP 4" in text
    finally:
        _release_ground_state()


def test_finish_combat_victory_writes_no_tombstone(monkeypatch, tmp_path):
    monkeypatch.setenv("HOME", str(tmp_path))
    game_map = _floor_map()
    ctx = _ground_ctx(game_map, (5, 5))
    enemy = _seed_enemy(game_map, "pirate_raider", (6, 5))
    try:
        _rules_ground.init(ctx, [enemy], game_map)

        for outcome in ("VICTORY", "DISENGAGED"):
            cr = _loop._finish_combat(ctx, _rules_ground, outcome)
            assert cr.tombstone_path is None
        assert not (tmp_path / ".spacehack" / "saves" / "tombstones").exists()
    finally:
        _release_ground_state()


# ---------------------------------------------------------------------------
# Death-screen notice — all three theaters
# ---------------------------------------------------------------------------


def test_ground_defeat_screen_appends_the_tombstone_notice(monkeypatch):
    import src.spacehack.game_flow as game_flow

    captured = []

    async def fake_death_screen(ctx, *, lines=()):
        captured.append(lines)

    monkeypatch.setattr(
        "src.spacehack.combat._encounter._render_death_screen",
        fake_death_screen,
    )
    result = SimpleNamespace(
        outcome="DEFEAT",
        tombstone_path="/tmp/.spacehack/saves/tombstones/tombstone-x.txt",
    )
    _async_run(game_flow._show_ground_defeat(_reader_ctx(), result))
    assert captured == [(
        "YOU DIED",
        "You collapse from your wounds.",
        "Tombstone saved: /tmp/.spacehack/saves/tombstones/tombstone-x.txt",
    )]


def test_ground_defeat_screen_without_a_tombstone_keeps_its_lines(monkeypatch):
    import src.spacehack.game_flow as game_flow

    captured = []

    async def fake_death_screen(ctx, *, lines=()):
        captured.append(lines)

    monkeypatch.setattr(
        "src.spacehack.combat._encounter._render_death_screen",
        fake_death_screen,
    )
    _async_run(game_flow._show_ground_defeat(
        _reader_ctx(), SimpleNamespace(outcome="DEFEAT", tombstone_path=None),
    ))
    assert captured == [(
        "YOU DIED",
        "You collapse from your wounds.",
    )]


def test_city_defeat_routes_through_the_shared_death_screen(monkeypatch):
    """Doc 53 SETTLED 2: a city hostile-bump death shows the SAME full
    screen (tombstone line included) before the exit."""
    from src.spacehack import city_npcs, tutorial

    shown = []

    async def fake_show_defeat(ctx, result):
        shown.append(result)

    async def noop(*args, **kwargs):
        return None

    async def fake_run_combat(console, ctx, game_map, rules):
        return SimpleNamespace(
            outcome="DEFEAT",
            tombstone_path="/tmp/x/tombstone-1.txt",
        )

    monkeypatch.setattr(tutorial, "maybe_ground_combat_intro", noop)
    monkeypatch.setattr(tutorial, "notify_ground_combat_ended", noop)
    monkeypatch.setattr(_rules_ground, "init", noop)
    monkeypatch.setattr(_loop, "run_combat", fake_run_combat)
    monkeypatch.setattr(
        "src.spacehack.game_flow._apply_ground_combat_rep", noop,
    )
    monkeypatch.setattr(
        "src.spacehack.game_flow._show_ground_defeat", fake_show_defeat,
    )

    with pytest.raises(SystemExit):
        _async_run(city_npcs.run_city_fight(
            _reader_ctx(), None, _floor_map(), [SimpleNamespace()],
        ))
    assert len(shown) == 1
    assert shown[0].tombstone_path == "/tmp/x/tombstone-1.txt"


def test_space_defeat_screen_carries_the_tombstone_notice(monkeypatch):
    from src.spacehack.combat import _encounter, _rules_space
    from src.spacehack import tutorial
    from src.spacehack.ship import OwnedShip

    captured = []

    async def fake_death_screen(ctx, *, lines=()):
        captured.append(lines)

    async def noop(*args, **kwargs):
        return None

    async def fake_run_combat(console, ctx, game_map, rules):
        return SimpleNamespace(
            outcome="DEFEAT",
            tombstone_path="/tmp/x/tombstone-2.txt",
        )

    ctx = _reader_ctx(
        player=world.Entity(
            "@", (255, 255, 255), world.Position(1, 1), "Player",
        ),
        player_owned_ship=OwnedShip(ship_id="scout"),
        main_quest_chain="",
    )
    monkeypatch.setattr(tutorial, "maybe_space_combat_intro", noop)
    monkeypatch.setattr(_rules_space, "init", noop)
    monkeypatch.setattr(_encounter, "run_combat", fake_run_combat)
    monkeypatch.setattr(_encounter, "_render_death_screen", fake_death_screen)

    outcome = _async_run(_encounter._handle_combat_encounter(
        ctx, None, ([find_npc_ship("pirate_scout")], [world.Position(2, 2)]),
    ))
    assert outcome == "DEFEAT"
    assert ctx.player_dead is True
    # The notice APPENDS to the destruction lines (both theaters); the
    # title slot stays the classic one, the path renders as body text.
    assert captured == [(
        "SHIP DESTROYED",
        "Your ship has been destroyed.",
        "All crew lost. All cargo lost.",
        "Tombstone saved: /tmp/x/tombstone-2.txt",
    )]


# ---------------------------------------------------------------------------
# Real-fight integrations (the balance harness's inert presentation)
# ---------------------------------------------------------------------------


def _fight(monkeypatch, tmp_path, row):
    """One real fight under the test's HOME; the tombstone directory
    left behind is the assertion surface."""
    monkeypatch.setenv("HOME", str(tmp_path))
    with harness._inert_presentation():

        async def _go():
            ctx, game_map, console, rules = await harness.begin_run(row, 0)
            try:
                return await harness._mirror_loop(
                    ctx, game_map, console, rules, STANCES[row.stance],
                )
            finally:
                harness.end_run(rules)

        return _async_run(_go())


def _tombstone_files(tmp_path) -> list[Path]:
    return sorted(
        (tmp_path / ".spacehack" / "saves" / "tombstones").glob(
            "tombstone-*.txt",
        )
    )


def test_ground_defeat_fight_writes_a_tombstone_naming_the_killer(
    monkeypatch, tmp_path,
):
    row = BalanceScenario(
        id="doc53_ground_defeat",
        theater="ground",
        goal="an unarmed pilot dies to an always-hostile drone",
        player=PlayerSheet(
            species_id="human", class_id="merchant",
            hull_id="starter", weapon_ids=(), module_ids=(),
        ),
        player_start=(5, 5),
        enemies=(EnemySide(spec_id="assault_drone", pos=(6, 5), band=4),),
        grid=GridSpec(width=20, height=20),
        stance="stand_and_trade",
        runs=1,
        seed=530001,
        thresholds=None,
    )
    result = _fight(monkeypatch, tmp_path, row)
    assert result.outcome == "DEFEAT", result
    (path,) = _tombstone_files(tmp_path)
    text = path.read_text(encoding="utf-8")
    assert f"  Slain by: {find_npc_char('assault_drone').name}'s " in text
    assert "  GEAR" in text
    assert "  --- MESSAGE LOG (full, oldest first) ---" in text


def test_space_defeat_fight_writes_a_tombstone_naming_the_killer(
    monkeypatch, tmp_path,
):
    row = BalanceScenario(
        id="doc53_space_defeat",
        theater="space",
        goal="an unarmed hauler dies to a pirate",
        player=PlayerSheet(
            species_id="human", class_id="merchant",
            hull_id="hauler", weapon_ids=(), module_ids=(),
        ),
        player_start=(50, 50),
        enemies=(EnemySide(spec_id="pirate_scout", pos=(44, 50)),),
        grid=GridSpec(width=100, height=100),
        stance="stand_and_trade",
        runs=1,
        seed=530002,
        thresholds=None,
    )
    result = _fight(monkeypatch, tmp_path, row)
    assert result.outcome == "DEFEAT", result
    (path,) = _tombstone_files(tmp_path)
    text = path.read_text(encoding="utf-8")
    assert f"  Slain by: {find_npc_ship('pirate_scout').name}'s " in text
    assert "  Final state: hull " in text


def test_space_victory_fight_writes_no_tombstone(monkeypatch, tmp_path):
    # Lasers, not the missile racks (doc 57 SETTLED 11 rework): a
    # standoff missile volley no longer guarantees a quick kill — the
    # scout rushes inside the floor and the racks go dead — so the
    # victory surface is pinned with the slugfest loadout.
    row = BalanceScenario(
        id="doc53_space_victory",
        theater="space",
        goal="an overwhelming cruiser wins without a scratch",
        player=PlayerSheet(
            species_id="human", class_id="merchant",
            hull_id="cruiser",
            weapon_ids=("heavy_laser", "heavy_laser"),
            module_ids=("shield_mk1",),
        ),
        player_start=(50, 50),
        enemies=(EnemySide(spec_id="pirate_scout", pos=(44, 50)),),
        grid=GridSpec(width=100, height=100),
        stance="stand_and_trade",
        runs=1,
        seed=530003,
        thresholds=None,
    )
    result = _fight(monkeypatch, tmp_path, row)
    assert result.outcome == "VICTORY", result
    assert _tombstone_files(tmp_path) == []
