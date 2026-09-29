"""Doc-50 exploration front: plug a REAL SAVE's character into the
balance harness and measure the power curve (2026-09-29).

The pinned scenario table (``tests/balance/scenarios.py``) expresses
sheets through ``PlayerSheet`` — starting stats + declared spends,
quality-less installs. A played character carries more than that
vocabulary holds (band-scaled ground stats, quality-3 gear, a
magazine mid-fight, a cruiser with four mounted weapons), so this
front does not go through the sheet builders at all: it loads the
save through the production deserializer
(``debug_session.HeadlessSaveSession``) and fights with the REAL
``GameContext`` — every read the rules make (stats, ground stats,
HP, armor qualities, bandolier, traits, ship) resolves against the
played values, never a re-derivation.

Per-run isolation: the fight mutates ctx (HP, ammo, counters, pos),
so each run deep-copies the pristine loaded ctx. DEFEAT reaches
``saveload.delete_save()`` through the real finish path — HOME is
sandboxed per run (harness pattern) and the source save is never
the autosave the game would unlink (``~/.spacehack`` != repo
``saves/``), but back the file up anyway before bulk runs.

Usage:
    python3 tools/balance_probe.py saves/autosave.json
    python3 tools/balance_probe.py saves/autosave.json --runs 30
    python3 tools/balance_probe.py saves/autosave.json --only b4
"""

from __future__ import annotations

import argparse
import copy
import sys
from dataclasses import dataclass

sys.path.insert(0, ".")

from src.spacehack import solar_system, world
from src.spacehack.combat import _rules_ground, _rules_space
from src.spacehack.data.npc_ships import find_npc_ship
from src.spacehack.data.pilot_skills import PilotSkills
from src.spacehack.data.ships import find_ship
from src.spacehack.debug_session import HeadlessSaveSession
from src.spacehack.dungeon import init_fog, reveal_around
from tests.balance.harness import (
    _AbsorbingConsole,
    _fake_pygame_context,
    _inert_presentation,
    _mirror_loop,
    _rebind_run_rng,
    _sandboxed_home,
    _seed_enemy_entities,
    _seed_ground_enemies,
    _snapshot_rng_world,
    aggregate,
    build_game_map,
    build_ground_grid,
    build_planet_grid,
    end_run,
)
from tests.balance.scenarios import EnemySide, GridSpec
from tests.balance.stances import STANCES
from tests.support.asyncutil import run as _async_run


@dataclass(frozen=True)
class ProbeRow:
    """One probe matchup: enemies + grid + stance, run at N seeds."""

    id: str
    theater: str          # "ground" | "space"
    label: str
    enemy_ids: tuple[str, ...]
    enemy_cells: tuple[tuple[int, int], ...]
    band: int             # ground rows: spawn_band stamp
    grid: GridSpec | None # ground rows; space rows use the sol grid
    start: tuple[int, int]
    stance: str
    reference: str = ""   # pinned-standard comparison line, if any


# The pinned tutorial fight's exact geometry (goal_2_mars row): the
# apples-to-apples row — same grid, same seed, same enemies, same
# stance as the starter-sheet standard.
_MARS_GRID = GridSpec(
    width=120, height=90, planet_id="mars", grid_seed=115,
)

# Open-floor arena (hold_range rung-0 geometry): 41x25 floor, player
# center, enemies on fixed rings well inside sight.
_ARENA = GridSpec(width=41, height=25)
_RING_5 = ((26, 12), (20, 6), (14, 12), (20, 18), (24, 8))
_RING_10 = (
    (26, 12), (24, 8), (20, 6), (16, 8), (14, 12),
    (16, 16), (20, 18), (24, 16), (23, 12), (17, 12),
)

GROUND_ROWS: tuple[ProbeRow, ...] = (
    ProbeRow(
        id="g_mars_pinned",
        theater="ground",
        label="3x rock_scavenger band 1 — the pinned goal_2 fight",
        enemy_ids=("rock_scavenger",) * 3,
        enemy_cells=((106, 44), (107, 44), (108, 43)),
        band=1,
        grid=_MARS_GRID,
        start=(100, 47),
        stance="toggle_sets",
        reference=(
            "starter sheet (pinned standard): win 1.00 / 4.68 HP "
            "(17%) / 12.56 rds / 12.6 ammo"
        ),
    ),
    ProbeRow(
        id="g_b2_riflemen",
        theater="ground",
        label="5x pirate_rifleman band 2",
        enemy_ids=("pirate_rifleman",) * 5,
        enemy_cells=_RING_5,
        band=2,
        grid=_ARENA,
        start=(20, 12),
        stance="toggle_sets",
    ),
    ProbeRow(
        id="g_b3_brutes",
        theater="ground",
        label="5x pirate_brute band 3",
        enemy_ids=("pirate_brute",) * 5,
        enemy_cells=_RING_5,
        band=3,
        grid=_ARENA,
        start=(20, 12),
        stance="toggle_sets",
    ),
    ProbeRow(
        id="g_b4_drones",
        theater="ground",
        label="5x assault_drone band 4 (top-band melee)",
        enemy_ids=("assault_drone",) * 5,
        enemy_cells=_RING_5,
        band=4,
        grid=_ARENA,
        start=(20, 12),
        stance="toggle_sets",
    ),
    ProbeRow(
        id="g_b4_gunners",
        theater="ground",
        label="5x consortium_gunner band 4 (top-band ranged)",
        enemy_ids=("consortium_gunner",) * 5,
        enemy_cells=_RING_5,
        band=4,
        grid=_ARENA,
        start=(20, 12),
        stance="toggle_sets",
    ),
    ProbeRow(
        id="g_b4_swarm",
        theater="ground",
        label="10x assault_drone band 4 (breaking-point stress)",
        enemy_ids=("assault_drone",) * 10,
        enemy_cells=_RING_10,
        band=4,
        grid=_ARENA,
        start=(20, 12),
        stance="toggle_sets",
    ),
)

_SOL_GRID = GridSpec(width=200, height=140, system_id="sol")

SPACE_ROWS: tuple[ProbeRow, ...] = (
    ProbeRow(
        id="s_scout_b1",
        theater="space",
        label="vs pirate_scout band 1 — Jack's own fight",
        enemy_ids=("pirate_scout",),
        enemy_cells=((80, 52),),
        band=1,
        grid=None,
        start=(88, 52),
        stance="stand_and_trade",
        reference=(
            "starter ship (goal_1 pinned standard): win 0.94-0.99"
        ),
    ),
    ProbeRow(
        id="s_raider_b2",
        theater="space",
        label="vs pirate_raider band 2",
        enemy_ids=("pirate_raider",),
        enemy_cells=((80, 52),),
        band=2,
        grid=None,
        start=(88, 52),
        stance="stand_and_trade",
    ),
    ProbeRow(
        id="s_marauder_b3",
        theater="space",
        label="vs pirate_marauder band 3",
        enemy_ids=("pirate_marauder",),
        enemy_cells=((80, 52),),
        band=3,
        grid=None,
        start=(88, 52),
        stance="stand_and_trade",
    ),
    ProbeRow(
        id="s_warlord_b4",
        theater="space",
        label="vs pirate_warlord band 4 (catalog ceiling)",
        enemy_ids=("pirate_warlord",),
        enemy_cells=((80, 52),),
        band=4,
        grid=None,
        start=(88, 52),
        stance="stand_and_trade",
    ),
    ProbeRow(
        id="s_2x_marauder",
        theater="space",
        label="vs 2x pirate_marauder band 3 (swarm stress)",
        enemy_ids=("pirate_marauder", "pirate_marauder"),
        enemy_cells=((80, 52), (80, 44)),
        band=3,
        grid=None,
        start=(88, 52),
        stance="stand_and_trade",
    ),
)


def _sheet_summary(ctx) -> str:
    """The played character, one block of plain lines."""
    gear = ", ".join(
        f"{w.weapon_id} q{w.quality}"
        + (f" ({w.loaded_ammo}+{ctx.bandolier.get('rifle_round', 0)})"
           if w.loaded_ammo is not None else "")
        for w in (*ctx.equipped_ground_weapons, *ctx.holstered_ground_weapons)
    )
    armor = ", ".join(
        f"{v.item_id} q{v.quality}"
        for v in ctx.equipped_ground_armor.values()
    )
    ship = ctx.player_owned_ship
    ship_gear = ", ".join(
        f"{w.item_id} q{w.quality}" for w in ship.weapons
    ) + " | " + ", ".join(m.item_id for m in ship.modules)
    c = ctx.player_counters
    return (
        f"  {ctx.character_info['species_name']}"
        f" {ctx.character_info['class_name']}, level {ctx.player_level}"
        f" ({ctx.player_xp} XP)\n"
        f"  ground: REF {ctx.ground_stats.reflexes}"
        f" / STR {ctx.ground_stats.strength}"
        f" / STA {ctx.ground_stats.stamina}"
        f" — HP {ctx.ground_hp}/{ctx.ground_max_hp}\n"
        f"  pilot: GUN {ctx.stats.gunnery} / PIL {ctx.stats.piloting}"
        f" / ENG {ctx.stats.engineering}\n"
        f"  kit: {gear}\n"
        f"  armor: {armor}\n"
        f"  traits: {', '.join(ctx.player_traits)}\n"
        f"  ship: {ship.ship_id} — {ship_gear}\n"
        f"  lifetime: {c.total_kills} kills,"
        f" {c.total_damage_taken} hull dmg taken,"
        f" {c.ground_damage_taken} ground dmg taken"
    )


async def _begin_ground(pristine, row: ProbeRow, seed: int):
    """One ground fight on a save-sourced ctx (harness mirror)."""
    if row.grid.planet_id:
        game_map, _spawn = await build_planet_grid(row.grid)
    else:
        game_map = build_ground_grid(row.grid)
    ctx = copy.deepcopy(pristine)
    ctx.context = _fake_pygame_context()  # combat presents absorb
    ctx.game_map = game_map
    ctx.player.pos = world.Position(*row.start)
    game_map.entities.append(ctx.player)
    enemies = tuple(
        EnemySide(spec_id=sid, pos=pos, band=row.band)
        for sid, pos in zip(row.enemy_ids, row.enemy_cells)
    )
    entities = _seed_ground_enemies(game_map, enemies)
    init_fog(game_map)
    reveal_around(game_map, ctx.player.pos, radius=game_map.sight_radius)
    _rebind_run_rng(seed)
    console = _AbsorbingConsole()
    _rules_ground.init(ctx, entities, game_map, console=console)
    return ctx, game_map, console, _rules_ground


def _begin_space(pristine, row: ProbeRow, seed: int):
    """One space fight on a save-sourced ctx (harness mirror)."""
    solar_system.set_current_solar_system(_SOL_GRID.system_id)
    game_map = build_game_map(_SOL_GRID)
    ctx = copy.deepcopy(pristine)
    ctx.context = _fake_pygame_context()  # combat presents absorb
    ctx.game_map = game_map
    ctx.player.pos = world.Position(*row.start)
    ctx.player.owned = True
    game_map.entities.append(ctx.player)
    enemies = tuple(
        EnemySide(spec_id=sid, pos=pos, band=row.band)
        for sid, pos in zip(row.enemy_ids, row.enemy_cells)
    )
    _seed_enemy_entities(game_map, enemies)
    _rebind_run_rng(seed)
    console = _AbsorbingConsole()
    skills = PilotSkills(
        gunnery=ctx.stats.gunnery,
        piloting=ctx.stats.piloting,
        engineering=ctx.stats.engineering,
    )
    _rules_space.init(
        ctx, console, find_ship(ctx.player_owned_ship.ship_id),
        ctx.player_owned_ship, ctx.player.pos, skills,
        [find_npc_ship(e.spec_id) for e in enemies],
        [world.Position(*e.pos) for e in enemies],
        game_map, ctx.log,
    )
    _rules_space._state.view_w, _rules_space._state.view_h = 40, 27
    return ctx, game_map, console, _rules_space


async def _probe_run_once(pristine, row: ProbeRow, run_index: int, base: int):
    """Snapshot world, begin the fight, mirror the loop, restore."""
    rules = _rules_ground if row.theater == "ground" else _rules_space
    try:
        _snapshot_rng_world()
        seed = base + run_index
        if row.theater == "ground":
            ctx, game_map, console, rules = await _begin_ground(
                pristine, row, seed,
            )
        else:
            ctx, game_map, console, rules = _begin_space(
                pristine, row, seed,
            )
        return await _mirror_loop(
            ctx, game_map, console, rules, STANCES[row.stance],
        )
    finally:
        # end_run drops session state AND restores the RNG world
        # (the harness runner's exact teardown — no second restore).
        end_run(rules)


def run_probe_row(pristine, row: ProbeRow, runs: int, base: int) -> dict:
    """N seeded fights on the save-sourced sheet; the batch report
    plus the worst-case damage spike over won runs."""
    with _inert_presentation(), _sandboxed_home():
        results = [
            _async_run(_probe_run_once(pristine, row, i, base))
            for i in range(runs)
        ]
    report = aggregate(results)
    wins = [r for r in results if r.outcome == "VICTORY"]
    return {
        "report": report,
        "max_damage": max((r.hull_damage_taken for r in wins), default=0),
    }


def _print_row(row: ProbeRow, stats: dict) -> None:
    r = stats["report"]
    print(
        f"  {row.id:16} win {r.win_rate:5.3f}  def {r.defeats:3}"
        f"  t/o {r.timeouts:2}  dis {r.disengagements:2}"
        f"  dmg {r.mean_hull_damage_taken:6.2f}"
        f" (worst {stats['max_damage']:3})"
        f"  turns {r.mean_turns:6.2f}"
        + (f"  ammo {r.mean_ammo_spent:6.2f}" if row.theater == "ground" else "")
    )
    if row.reference:
        print(f"  {'':16} ref: {row.reference}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("save", help="path to the savegame to probe")
    parser.add_argument("--runs", type=int, default=50)
    parser.add_argument("--only", default="", help="substring row filter")
    args = parser.parse_args()

    session = HeadlessSaveSession.load(args.save)
    pristine = session.ctx
    print("=== character under test ===")
    print(_sheet_summary(pristine))
    print(f"  credits: {pristine.stats.credits}")
    print()

    rows = [
        row for row in (*GROUND_ROWS, *SPACE_ROWS)
        if args.only in row.id
    ]
    base_seed = 20260929
    for offset, row in enumerate(rows):
        print(f"[{row.theater}] {row.label}  ({args.runs} runs)")
        stats = run_probe_row(pristine, row, args.runs, base_seed + offset * 1000)
        _print_row(row, stats)
        print()


if __name__ == "__main__":
    main()
