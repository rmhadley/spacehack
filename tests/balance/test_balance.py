"""Balance gate (doc 50, SETTLED 1) — the benchmarks' pytest home.

Every scenario row in ``tests/balance/scenarios.py`` runs its batch
through the real combat resolution here; rows with ruled thresholds
assert them. Pure harness math (seed derivation, aggregate, threshold
bars) is pinned directly, and the ground theater's builders + stance
carry their own pins (doc 50 phase 2).
"""

from __future__ import annotations

import dataclasses

import pytest
from src.spacehack.combat import _loop
from src.spacehack.ground_equipment import GroundWeaponInstance
from tests.support.asyncutil import run as _async_run

from tests.balance import harness
from tests.balance.harness import (
    BatchReport,
    RunResult,
    aggregate,
    begin_run,
    derived_seed,
    meets_thresholds,
    run_batch,
    run_once,
)
from tests.balance.scenarios import (
    SCENARIOS,
    EnemySide,
    GridSpec,
    PlayerSheet,
    Thresholds,
    find_scenario,
)

_RESOLVED = frozenset({"VICTORY", "DEFEAT", "TIMEOUT", "DISENGAGED"})


def test_seed_derivation_is_base_plus_run_index() -> None:
    """The house derived-seed pattern: distinct streams per run."""
    assert derived_seed(100, 0) == 100
    assert [derived_seed(100, i) for i in range(3)] == [100, 101, 102]
    assert len({derived_seed(50, i) for i in range(10)}) == 10


def test_aggregate_math_on_a_mixed_batch() -> None:
    """win_rate over all runs; rounds/damage means over WON runs only;
    DISENGAGED counts as its own unresolved column (SETTLED 5)."""
    results = [
        RunResult("VICTORY", 3, 0),
        RunResult("VICTORY", 5, 10),
        RunResult("DEFEAT", 2, 15),
        RunResult("TIMEOUT", harness.TURN_CAP, 7),
        RunResult("DISENGAGED", 4, 3),
    ]
    report = aggregate(results)
    assert report.runs == 5
    assert report.wins == 2
    assert report.defeats == 1
    assert report.timeouts == 1
    assert report.disengagements == 1
    assert report.win_rate == 0.4
    assert report.mean_turns == 4.0          # (3 + 5) / 2 won runs
    assert report.mean_hull_damage_taken == 5.0  # (0 + 10) / 2
    assert report.max_turns == harness.TURN_CAP


def test_aggregate_on_an_empty_batch() -> None:
    report = aggregate([])
    assert report.win_rate == 0.0
    assert report.mean_turns == 0.0
    assert report.mean_hull_damage_taken == 0.0


def test_meets_thresholds_checks_every_stated_bar() -> None:
    report = BatchReport(
        runs=10, wins=8, defeats=2, timeouts=0, win_rate=0.8,
        mean_turns=4.0, max_turns=7, mean_hull_damage_taken=2.5,
    )
    assert meets_thresholds(report, Thresholds(win_rate_floor=0.7))
    assert not meets_thresholds(report, Thresholds(win_rate_floor=0.9))
    # The ceiling bar bites on both sides: a 0.8 batch passes under
    # 0.99, a sure-thing 1.0 batch fails it ("never a sure thing").
    assert meets_thresholds(report, Thresholds(win_rate_ceiling=0.99))
    assert not meets_thresholds(report, Thresholds(win_rate_ceiling=0.79))
    sure_thing = dataclasses.replace(report, win_rate=1.0)
    assert not meets_thresholds(sure_thing, Thresholds(win_rate_ceiling=0.99))
    assert meets_thresholds(report, Thresholds(rounds_ceiling=4.0))
    assert not meets_thresholds(report, Thresholds(rounds_ceiling=3.9))
    assert meets_thresholds(
        report, Thresholds(damage_taken_ceiling=2.5),
    )
    assert not meets_thresholds(
        report, Thresholds(damage_taken_ceiling=2.4),
    )
    # Bars left unstated never fail the batch.
    assert meets_thresholds(report, Thresholds())


def test_stand_and_trade_fires_while_affordable_then_waits() -> None:
    """The stance reads affordability through the REAL rules: FIRE
    while power/AP hold (one burst covers every active slot), WAIT
    the moment nothing can fire — never a move."""
    row = find_scenario("goal_1_starter_vs_jack")
    with harness._inert_presentation(), harness._sandboxed_home():
        rules = harness._rules_space
        try:
            ctx, game_map, console, rules = _async_run(begin_run(row, 0))
            assert rules.player_ap(ctx) > 0
            assert _async_run(
                harness.STANCES[row.stance](ctx, rules),
            ) == "FIRE"
            # A real FIRE dispatch: both lasers fire (power -2), AP -1.
            power_before = rules._state.player_state["power_pool"]
            ap_before = rules.player_ap(ctx)
            _async_run(_loop._dispatch_combat_action(
                console, ctx, game_map, rules, "FIRE", 0,
            ))
            assert rules._state.player_state["power_pool"] == power_before - 2
            assert rules.player_ap(ctx) == ap_before - 1
            # Power dry -> nothing affordable -> the stance ends the turn.
            rules._state.player_state["power_pool"] = 0
            assert _async_run(
                harness.STANCES[row.stance](ctx, rules),
            ) == "WAIT"
        finally:
            harness.end_run(rules)


# One batch per row per pytest process — the resolve test and the
# thresholds gate share it (a second 50s batch per thresholds-bearing
# row in make check is exactly the cost the checkpoint told us to
# weigh; reviewer issue 10). Keyed on row.id: feed it the AUTHORED
# row, never a dataclasses.replace variant (a short variant would
# poison the cache and fail the len assert).
_BATCH_CACHE: dict = {}


def batch_for(row) -> list:
    if row.id not in _BATCH_CACHE:
        _BATCH_CACHE[row.id] = run_batch(row)
    return _BATCH_CACHE[row.id]


@pytest.mark.parametrize("row", SCENARIOS, ids=[r.id for r in SCENARIOS])
def test_scenario_batch_resolves_every_run(row) -> None:
    """The batch runs to completion under the real resolution: every
    run lands a named outcome — no hangs, no crashes (SETTLED 2)."""
    results = batch_for(row)
    assert len(results) == row.runs
    assert all(r.outcome in _RESOLVED for r in results)


@pytest.mark.parametrize("row", SCENARIOS, ids=[r.id for r in SCENARIOS])
def test_scenario_thresholds(row) -> None:
    """Rows with ruled thresholds assert their goal; report-only rows
    (SETTLED 3, measure-then-rule) skip until the numbers land."""
    if row.thresholds is None:
        pytest.skip("report-only until thresholds are ruled")
    assert any(bar is not None for bar in (
        row.thresholds.win_rate_floor,
        row.thresholds.win_rate_ceiling,
        row.thresholds.rounds_ceiling,
        row.thresholds.damage_taken_ceiling,
    )), "a thresholds row must state at least one bar"
    report = aggregate(batch_for(row))
    assert meets_thresholds(report, row.thresholds), report


def test_goal_1_run_level_determinism() -> None:
    """Same row + run index -> identical fight, end to end through the
    seeded runner (the batch-level determinism contract follows from
    per-run determinism, so the pin needs only a few indices)."""
    row = find_scenario("goal_1_starter_vs_jack")
    first = [run_once(row, i) for i in (0, 1, 2)]
    second = [run_once(row, i) for i in (0, 1, 2)]
    assert first == second


def test_goal_1_batch_aggregate_determinism() -> None:
    """A whole (small) batch re-run folds to the identical aggregate."""
    row = dataclasses.replace(
        find_scenario("goal_1_starter_vs_jack"), runs=3,
    )
    assert aggregate(run_batch(row)) == aggregate(run_batch(row))


def test_skill_spends_fold_onto_starting_skills() -> None:
    """A level-2 sheet spends exactly its 5 points, +1 per point; a
    mis-budgeted row fails loudly (the guard bites)."""
    sheet = PlayerSheet(
        species_id="human", class_id="merchant", hull_id="starter",
        weapon_ids=(), module_ids=(),
        level=2, skill_spends=(("gunnery", 5),),
    )
    skills = harness.build_pilot_skills(sheet)
    base = harness.starting_pilot_skills("human", "merchant")
    assert skills.gunnery == base.gunnery + 5
    assert skills.piloting == base.piloting
    assert skills.engineering == base.engineering
    with pytest.raises(ValueError):
        harness.build_pilot_skills(dataclasses.replace(
            sheet, level=2, skill_spends=(("gunnery", 3),),
        ))


# ---------------------------------------------------------------------------
# Ground theater pins (doc 50 phase 2, SETTLED 4/5)
# ---------------------------------------------------------------------------


def _ground_state(row, run_index: int = 0):
    """begin_run for a ground row under the inert doubles; the caller
    owns the try/finally ``end_run`` teardown."""
    return _async_run(begin_run(row, run_index))


def _synthetic_ground_row(
    *, weapon_ids: tuple = ("kinetic_rifle",),
    ammo: tuple = (),
    enemy_pos: tuple[int, int] = (10, 7),
    player_pos: tuple[int, int] = (7, 7),
):
    """A hand-built geometry row (never in SCENARIOS — a fixture, not
    a protected situation). The kinetic_rifle's min_range 2 makes the
    back-off branch constructible (unreachable on the tutorial sheet,
    whose pistols are min_range 1)."""
    row = find_scenario("goal_2_starter_mars_delve")
    return dataclasses.replace(
        row,
        id="synthetic_pin_fixture",
        grid=GridSpec(width=15, height=15),
        player_start=player_pos,
        enemies=(EnemySide(spec_id="rock_scavenger", pos=enemy_pos, band=1),),
        player=dataclasses.replace(
            row.player, ground_weapon_ids=weapon_ids, ground_ammo=ammo,
        ),
        runs=1,
    )


def test_hold_range_selects_closest_alive_enemy_via_target_cycling() -> None:
    """The reference target is the CLOSEST alive enemy (SETTLED 5) and
    the stance aims at it through real TARGET dispatches — never by
    calling rules internals."""
    row = find_scenario("goal_2_starter_mars_delve")
    with harness._inert_presentation(), harness._sandboxed_home():
        rules = harness._rules_ground
        try:
            ctx, game_map, console, rules = _ground_state(row)
            assert len(rules.get_enemies(ctx)) == 3
            rules.set_target_idx(ctx, 2)  # aim at the FARTHEST first
            cycles = []
            for _ in range(4):
                action = _async_run(harness.STANCES[row.stance](ctx, rules))
                if action != "TARGET":
                    break
                cycles.append(action)
                _async_run(_loop._dispatch_combat_action(
                    console, ctx, game_map, rules, "TARGET",
                    rules._state.target_idx,
                ))
            assert cycles == ["TARGET"]  # 3 enemies: 2 -> 0 (wraps)
            assert rules._state.target_idx == 0
            assert action != "TARGET"  # aimed: the ladder proceeds
        finally:
            harness.end_run(rules)


def test_hold_range_approaches_then_fires_in_band() -> None:
    """Out of band (enemies at sight edge, pistol max 4) the stance
    MOVES through real dispatches until the reference target is inside
    the band — and never emits a FIRE that ``can_fire`` would reject.
    Enemy turns ride the real end-player-turn."""
    row = find_scenario("goal_2_starter_mars_delve")
    with harness._inert_presentation(), harness._sandboxed_home():
        rules = harness._rules_ground
        try:
            ctx, game_map, console, rules = _ground_state(row)
            target_idx = 0
            moves = 0
            fired = False
            for _ in range(60):
                action = _async_run(harness.STANCES[row.stance](ctx, rules))
                if action == "FIRE":
                    target = rules.get_enemies(ctx)[target_idx]
                    dist = int(harness._distance(ctx.player.pos, target.pos))
                    assert dist <= 4  # inside the pistol band at FIRE time
                    assert any(
                        rules.can_fire(slot, ctx)[0]
                        for slot in harness._fire_slots(ctx, rules)
                    )
                    fired = True
                    break
                assert not action.startswith("FIRE")
                if action.startswith("MOVE:"):
                    moves += 1
                target_idx = _async_run(_loop._dispatch_combat_action(
                    console, ctx, game_map, rules, action, target_idx,
                ))
                if rules.player_ap(ctx) == 0:
                    _, defeat = _async_run(_loop._end_player_turn(
                        ctx, game_map, rules, 1,
                    ))
                    assert defeat is None
            assert fired and moves >= 1
        finally:
            harness.end_run(rules)


def test_hold_range_reloads_first_dry_slot_through_real_reload() -> None:
    """Dry magazines with reserve: the stance emits RELOAD and the
    real post-fix path reloads the FIRST dry active slot (SETTLED 5).
    Without reserve the ladder falls through to MOVE (approach)."""
    row = find_scenario("goal_2_starter_mars_delve")
    with harness._inert_presentation(), harness._sandboxed_home():
        rules = harness._rules_ground
        try:
            ctx, game_map, console, rules = _ground_state(row)
            ctx.equipped_ground_weapons = [
                GroundWeaponInstance("kinetic_pistol", 0),
                GroundWeaponInstance("kinetic_pistol", 0),
            ]
            stance = harness.STANCES[row.stance]
            assert _async_run(stance(ctx, rules)) == "RELOAD"
            _async_run(_loop._dispatch_combat_action(
                console, ctx, game_map, rules, "RELOAD", 0,
            ))
            assert ctx.equipped_ground_weapons == [
                GroundWeaponInstance("kinetic_pistol", 12),
                GroundWeaponInstance("kinetic_pistol", 0),
            ]
            # Reserve spent: 40 -> 28 (a full 12-round magazine drawn).
            from src.spacehack.ground_equipment import reserve_ammo_count

            assert reserve_ammo_count(
                ctx.ground_expedition_items, "kinetic_pistol",
            ) == 28
            # No reserve at all: no RELOAD — the band rule takes over.
            ctx.equipped_ground_weapons = [
                GroundWeaponInstance("kinetic_pistol", 0),
                GroundWeaponInstance("kinetic_pistol", 0),
            ]
            ctx.ground_expedition_items = []
            assert _async_run(stance(ctx, rules)).startswith("MOVE:")
        finally:
            harness.end_run(rules)


def test_hold_range_backs_off_inside_min_range_when_firing_is_impossible():
    """The back-off branch (SETTLED 4) on a synthetic min_range>=2 row:
    can_fire allows penalized point-blank shots, so the branch is
    reachable only when firing is IMPOSSIBLE — here a dry rifle with
    no reserve and the scavenger adjacent (dist 1 < min 2)."""
    row = _synthetic_ground_row(enemy_pos=(8, 7), player_pos=(7, 7))
    with harness._inert_presentation(), harness._sandboxed_home():
        rules = harness._rules_ground
        try:
            ctx, game_map, console, rules = _ground_state(row)
            assert ctx.equipped_ground_weapons == [
                GroundWeaponInstance("kinetic_rifle", 20),
            ]
            ctx.equipped_ground_weapons = [GroundWeaponInstance("kinetic_rifle", 0)]
            ctx.ground_expedition_items = []
            ok, _reason = rules.can_fire(0, ctx)
            assert not ok  # firing impossible: the magazine cannot feed
            action = _async_run(harness.STANCES[row.stance](ctx, rules))
            assert action.startswith("MOVE:")
            # The emitted step must move the player AWAY from the
            # reference target (dist 1 < the rifle's min_range 2).
            from src.spacehack.world import MOVE_KEYS, Position

            dx, dy = MOVE_KEYS[action.partition(":")[2]]
            here = ctx.player.pos
            enemy_pos = rules.get_enemies(ctx)[0].pos
            before = harness._distance(here, enemy_pos)
            after = harness._distance(
                Position(here.x + dx, here.y + dy), enemy_pos,
            )
            assert after > before
        finally:
            harness.end_run(rules)


def test_hold_range_waits_only_when_nothing_else_applies() -> None:
    """In band, dry, no reserve: no FIRE, no RELOAD, no move needed —
    WAIT is the only rung left."""
    row = _synthetic_ground_row(enemy_pos=(10, 7), player_pos=(7, 7))
    with harness._inert_presentation(), harness._sandboxed_home():
        rules = harness._rules_ground
        try:
            ctx, game_map, console, rules = _ground_state(row)
            ctx.equipped_ground_weapons = [GroundWeaponInstance("kinetic_rifle", 0)]
            ctx.ground_expedition_items = []
            # dist 3 sits inside the rifle band [2, 7] — hold position.
            assert _async_run(harness.STANCES[row.stance](ctx, rules)) == "WAIT"
        finally:
            harness.end_run(rules)


def test_planet_grid_pins_dims_tiles_and_declared_combatants_only() -> None:
    """The planet-mode grid: dims match the planet's DungeonParams,
    the same grid_seed yields identical tiles + spawn, the generated
    scatter is discarded, and begin_run leaves fog grids present with
    every declared enemy stamped npc_char_id + spawn_band resolving at
    the declared band through the real ground_scale."""
    from src.spacehack.data.planets import find_planet_spec

    row = find_scenario("goal_2_starter_mars_delve")
    params = find_planet_spec(row.grid.planet_id).dungeon_params
    assert (row.grid.width, row.grid.height) == (params.width, params.height)
    map_a, spawn_a = _async_run(harness.build_planet_grid(row.grid))
    map_b, spawn_b = _async_run(harness.build_planet_grid(row.grid))
    assert (spawn_a.x, spawn_a.y) == row.player_start
    assert map_a.tiles == map_b.tiles
    assert not map_a.entities  # populate skipped + prepare's stamps dropped
    with harness._inert_presentation(), harness._sandboxed_home():
        rules = harness._rules_ground
        try:
            ctx, game_map, console, rules = _ground_state(row)
            assert game_map.visible is not None and game_map.seen is not None
            stamped = [
                e for e in game_map.entities if getattr(e, "npc_char_id", "")
            ]
            assert [(e.npc_char_id, e.spawn_band) for e in stamped] == [
                ("rock_scavenger", 1),
            ] * 3
            assert [inst.band for inst in rules._state.enemies] == [1, 1, 1]
            # Stats resolved through the real band resolver — the
            # deterministic band-1 derivation, and max_hp off its stamina.
            from src.spacehack import ground_scale
            from src.spacehack.data.npc_chars import find_npc_char

            spec = find_npc_char("rock_scavenger")
            band1 = ground_scale.derive_stats(spec, 1)
            for inst in rules._state.enemies:
                assert inst.stats == band1
                assert inst.max_hp == spec.hp + band1.stamina // 3
        finally:
            harness.end_run(rules)


def test_goal_2_run_level_determinism() -> None:
    """Same ground row + run index -> identical fight, end to end
    through the seeded runner (the ground rebind set: loop / ai /
    actions / _ai_ground / noise / ground_npcs)."""
    row = find_scenario("goal_2_starter_mars_delve")
    first = [run_once(row, i) for i in (0, 1)]
    second = [run_once(row, i) for i in (0, 1)]
    assert first == second


def test_goal_2_batch_aggregate_determinism() -> None:
    """A whole (small) ground batch re-folds to the identical
    aggregate."""
    row = dataclasses.replace(
        find_scenario("goal_2_starter_mars_delve"), runs=3,
    )
    assert aggregate(run_batch(row)) == aggregate(run_batch(row))
