"""Balance-sim harness (doc 50 phases 1-2) — build real state, run real
combat (space and ground), headless and inert.

Everything the fight needs is REAL: the rules module, the loop's own
dispatch helpers, the enemy AI, the quality rolls, the reinforcement
path. Presentation runs inert — an absorbing console double swallows
every paint (frame counts and pacing awaits still run; the ~50ms/frame
overlay build a real FrameBuffer feeds does not), a fake
PygameContext (the ``tests/support/fake_pygame.py`` pattern) absorbs
every present, and INSTANT animation timing makes every pacing sleep
a zero-length yield. No AI or rules internals are monkeypatched.

The sim loop mirrors ``combat/_loop._run_combat_impl`` step by step,
sharing its actual helper bodies (end check, retarget, dispatch,
end-turn, finish) and replacing only the two presentation seams:
render/present (dropped) and input (the stance). Ground rows build on
the planet's LIVE delve pipeline under the row's fixed grid seed
(SETTLED 4/5). Cross-reference any change to ``_run_combat_impl`` here.
"""

from __future__ import annotations

import tempfile
from contextlib import contextmanager
from dataclasses import dataclass
from types import SimpleNamespace
from typing import Iterator

from src.spacehack import (
    animation_timing,
    engine,
    ground_npcs,
    noise,
    solar_system,
    world,
)
from src.spacehack.character import starting_ground_stats, starting_pilot_skills
from src.spacehack.combat import (
    _actions,
    _ai,
    _ai_ground,
    _loop,
    _rules_ground,
    _rules_space,
)
from src.spacehack.data.npc_chars import find_npc_char
from src.spacehack.data.npc_ships import find_npc_ship
from src.spacehack.data.pilot_skills import PilotSkills
from src.spacehack.data.ships import find_ship
from src.spacehack.game_context import PlayerCounters
from src.spacehack.bandolier import add_rounds, effective_cap
from src.spacehack.data.ground_items import find_ground_ammo
from src.spacehack.ground_equipment import (
    StoredGroundEquipment,
    install_armor,
    sum_armor_bonus,
)
from src.spacehack.ground_weapon_sets import install_set_weapon
from src.spacehack.message_log import MessageLog
from src.spacehack.ship import (
    OwnedShip,
    StoredEquipment,
    install_stored_equipment,
)
from src.spacehack.xp import ground_max_hp_bonus

from tests.balance.stances import STANCES
from tests.support.asyncutil import run as _async_run

# Modules holding import-time ``from ..engine import RNG`` bindings —
# the hit/loot roll sites. seed_rng REBINDS engine.RNG, so each run
# must refresh these to the same instance or the batch's rolls split
# across two Random objects (doc 50 audit §4). The ground theater adds
# the ground AI, the noise/investigation rolls, and the ambient patrol
# pass (doc 50 SETTLED 5 rebind set).
_RNG_MODULES = (_loop, _ai, _actions, _ai_ground, noise, ground_npcs)

# A stuck fight is itself a balance finding, never a hung test.
TURN_CAP = 200
# Loop-iteration bound: TURN_CAP counts TURNS, and a stance that
# emits AP-free actions forever would never advance the count — the
# iteration cap turns a stuck stance into a loud error instead of a
# hung suite (a turn spends at most a handful of actions).
ACTION_CAP = 5000


def derived_seed(base: int, i: int) -> int:
    """Run ``i``'s seed: the house derived-seed pattern, ``base + i``."""
    return base + i


def _rebind_run_rng(seed: int) -> None:
    """Point every RNG reader the fight touches at one fresh instance."""
    engine.seed_rng(seed)
    for module in _RNG_MODULES:
        module.RNG = engine.RNG


# The ambient world the sim borrows: engine's RNG instance + INIT_SEED,
# the import-time RNG bindings other tests hold, and the ambient
# solar-system id (the reinforcement path reads it). begin_run
# snapshots it, end_run restores it — a rebind or system switch that
# leaked past a run would desync every later test in the process from
# its own seeded instance or sim the fight in the wrong system.
_RNG_SNAPSHOT_STACK: list = []


def _snapshot_rng_world() -> None:
    _RNG_SNAPSHOT_STACK.append((
        engine.RNG,
        engine.INIT_SEED,
        [(module, module.RNG) for module in _RNG_MODULES],
        solar_system.current_solar_system_id,
    ))


def _restore_rng_world() -> None:
    if not _RNG_SNAPSHOT_STACK:
        return
    rng, init_seed, bindings, system_id = _RNG_SNAPSHOT_STACK.pop()
    engine.RNG = rng
    engine.INIT_SEED = init_seed
    for module, original in bindings:
        module.RNG = original
    solar_system.current_solar_system_id = system_id


def end_run(rules) -> None:
    """Teardown after one fight: release locks, drop session state,
    and restore the RNG world other tests rely on."""
    if rules._state is not None:
        rules._set_combat_locks(False)
    rules._state = None
    _restore_rng_world()


# ---------------------------------------------------------------------------
# Headless presentation doubles
# ---------------------------------------------------------------------------

_pygame_ready = False


def _ensure_headless_pygame() -> None:
    """Initialize the real pygame event system once, headless.

    ``_responsive_sleep`` polls ``pygame.event.get()`` on every pacing
    sleep and that raises until the subsystem is initialized (only
    ModuleNotFoundError is caught in the real code). Initializing the
    real library is the ``test_pygame_integration`` pattern, not a
    monkeypatch — no window ever opens because nothing calls set_mode.
    """
    global _pygame_ready
    if _pygame_ready:
        return
    import pygame

    pygame.init()
    _pygame_ready = True


class _AbsorbingConsole:
    """The combat console double: swallows every paint.

    The real renderers touch only ``clear`` and ``print``; the
    presentation adapter reads ``to_commands``. Absorbing paints (and
    reporting an empty frame) keeps the real animation code paths —
    frame counts, pacing awaits, popup plumbing — while skipping the
    ~50ms/frame overlay build a real FrameBuffer feeds. Combat logic
    never reads the console, so nothing measured is lost.
    """

    def clear(self, **kwargs) -> None:
        pass

    def print(self, **kwargs) -> None:
        pass

    @property
    def commands(self) -> list:
        return []

    def to_commands(self) -> tuple:
        return ()

    def default_background(self):
        return None


async def _empty_batch(seconds: float = 0.0) -> tuple:
    """The runtime double's event seam: no events, ever."""
    return ()


def _fake_pygame_context() -> SimpleNamespace:
    """A runtime double: presents absorb, event polls return nothing.

    ``_runtime.engine`` satisfies ``pygame_runtime.is_shared_context``
    (a duck-typed check); ``note_drained`` is the held-key hook
    ``_responsive_sleep`` feeds drained events to.
    """
    return SimpleNamespace(
        _runtime=SimpleNamespace(engine=object()),
        present=lambda *args, **kwargs: None,
        note_drained=lambda drained: None,
        pump=_empty_batch,
        wait_events=_empty_batch,
    )


@contextmanager
def _sandboxed_home() -> Iterator[None]:
    """Keep the sim away from the real ``~/.spacehack``.

    A DEFEAT run reaches ``saveload.delete_save()`` through the real
    finish path, which unlinks the player's actual autosave — the
    batch runs with HOME pointed at a scratch directory instead.
    """
    import os

    original = os.environ.get("HOME")
    with tempfile.TemporaryDirectory(prefix="spacehack-balance-") as tmp:
        os.environ["HOME"] = tmp
        try:
            yield
        finally:
            if original is None:
                os.environ.pop("HOME", None)
            else:
                os.environ["HOME"] = original


# ---------------------------------------------------------------------------
# Sheet builders — real objects through the game's own helpers
# ---------------------------------------------------------------------------


def build_owned_ship(sheet) -> OwnedShip:
    """The flown ship: declared loadout installed through the real
    install path, so slot caps and ammo seeding are the game's own."""
    spec = find_ship(sheet.hull_id)
    owned = OwnedShip(
        ship_id=sheet.hull_id,
        weapons=(),
        modules=(),
        fuel=spec.max_fuel,
    )
    storage = [
        StoredEquipment("weapon", weapon_id)
        for weapon_id in sheet.weapon_ids
    ]
    storage += [
        StoredEquipment("module", module_id)
        for module_id in sheet.module_ids
    ]
    while storage:
        assert install_stored_equipment(owned, storage, 0, spec), (
            f"scenario loadout does not fit {sheet.hull_id}: "
            f"{sheet.weapon_ids} / {sheet.module_ids}"
        )
    return owned


def build_pilot_skills(sheet) -> PilotSkills:
    """Starting skills through the real species/class fold, plus the
    sheet's declared level-up spends — the same +1-per-point fold
    ``xp._apply_skill_point`` performs, with the same 100 cap.

    The spend budget must match the level (5 points per level past
    1); anything else is a mis-authored row and fails loudly.
    """
    if sheet.level != 1 + sum(points for _skill, points in sheet.skill_spends) // 5:
        raise ValueError(
            f"level {sheet.level} grants 5 skill points per level past 1 — "
            f"declared spends {sheet.skill_spends} do not match"
        )
    skills = starting_pilot_skills(sheet.species_id, sheet.class_id)
    for skill, points in sheet.skill_spends:
        spent = min(points, 100 - getattr(skills, skill))
        setattr(skills, skill, getattr(skills, skill) + spent)
    return skills


def _ctx_core(sheet, game_map, player) -> dict:
    """Fields every theater's ctx carries, pinned with real values (no
    MagicMock defaults to misread) — the shared spine of the space and
    ground ctx builders."""
    return dict(
        player=player,
        game_map=game_map,
        context=_fake_pygame_context(),
        log=MessageLog(capacity=200),
        stats=SimpleNamespace(credits=100),
        player_counters=PlayerCounters(),
        player_traits=list(sheet.trait_ids),
        player_xp=0,
        player_level=sheet.level,
        player_skill_points=0,
        player_dead=False,
        bounty_spawns={},
        procedural_spawns={},
        defeated_static_spawns=set(),
        faction_reputation={},
        player_active_missions=[],
        known_rumors=[],
        # Ambient-traffic state (the end-turn patrol tick reads/writes
        # these; all start empty — the scenario grid carries no traffic).
        npc_targets={},
        npc_paths={},
        npc_credit={},
        npc_flash_events=[],
        militia_scanned={},
        main_quest_chain="",
        main_quest_progress={},
        # Doc 41 defiance/comply + doc 39 expedition + doc 47 storage
        # fields — read (guarded or not) by the reinforcement path.
        line_defiance_system=None,
        line_comply_latch=False,
        ground_expedition_inventory=[],
        ground_expedition_items=[],
        ship_storage=[],
        broadcast_dark=False,
        broadcast_identity=None,
    )


def build_ctx(sheet, game_map, player_start) -> SimpleNamespace:
    """The space-side ctx: the core spine plus the flown ship."""
    player = world.Entity(
        "@", (255, 255, 255), world.Position(*player_start),
        "Player", owned=True,
    )
    fields = _ctx_core(sheet, game_map, player)
    fields["player_owned_ship"] = build_owned_ship(sheet)
    return SimpleNamespace(**fields)


def _body_rects(system) -> tuple[tuple[int, int, int, int], ...]:
    """A system's blocking footprints: planets, jump points, stations.

    Stars are walkable decoration and stay out. Derived from the live
    catalog at build time so a body move in the system spec flows into
    scenarios (composition by id) instead of fighting on a stale copy.
    """
    bodies = (
        list(system.planets) + list(system.jump_points)
        + list(getattr(system, "stations", ()) or ())
    )
    return tuple(
        (b.pos.x, b.pos.y, b.width, b.height) for b in bodies
    )


def build_game_map(grid) -> world.GameMap:
    """The declared grid as a real map: STARFIELD void + body blocks.

    A ``system_id`` grid IS that system's map — dims asserted against
    the catalog, obstacles derived from its bodies. A system-less grid
    (synthetic geometry) stamps its declared rect blocks.
    """
    blocks = grid.blocks
    if grid.system_id:
        from src.spacehack.data.solar_systems import find_solar_system

        system = find_solar_system(grid.system_id)
        assert (grid.width, grid.height) == (system.width, system.height), (
            f"{grid.system_id} grid must match the system's "
            f"{system.width}x{system.height} map"
        )
        blocks = _body_rects(system)
    tiles = [
        [solar_system.STARFIELD for _ in range(grid.width)]
        for _ in range(grid.height)
    ]
    blocked = world.Tile(
        kind="planet", char="O", walkable=False,
        fg=(200, 180, 120), bg=(40, 36, 24),
    )
    _stamp_blocks(tiles, blocks, blocked)
    return world.GameMap(
        width=grid.width, height=grid.height, tiles=tiles, entities=[],
    )


def _seed_enemy_entities(game_map, enemies) -> None:
    """Place each enemy's map entity — the position match + name stamp
    ``_rules_space.init`` runs need."""
    for side in enemies:
        spec = find_npc_ship(side.spec_id)
        game_map.entities.append(world.Entity(
            spec.char, spec.fg, world.Position(*side.pos),
            spec.name, npc_ship_id=spec.id,
        ))


# ---------------------------------------------------------------------------
# Ground builders (doc 50 phase 2, SETTLED 4/5)
# ---------------------------------------------------------------------------


def build_ground_loadout(sheet) -> tuple:
    """The declared ground kit through the set-aware install path:
    weapons found their class homes (magazines seed FULL via the
    entry default), armor fills its catalog slot, ammo seeds the
    bandolier at each caliber's effective cap (doc 52 phase 1 — a
    store swap, not a policy change: declared quantities must fit)."""
    weapons: list = []
    holstered: list = []
    storage = [
        StoredGroundEquipment("weapon", weapon_id)
        for weapon_id in sheet.ground_weapon_ids
    ]
    while storage:
        install_set_weapon(weapons, holstered, storage, 0)
    armor: dict = {}
    for armor_id in sheet.ground_armor_ids:
        install_armor(
            armor, [StoredGroundEquipment("armor", armor_id)], 0,
        )
    bandolier: dict[str, int] = {}
    for item_id, quantity in sheet.ground_ammo:
        spec = find_ground_ammo(item_id)
        before = bandolier.get(spec.ammo_type, 0)
        bandolier = add_rounds(
            bandolier, spec.ammo_type, quantity, effective_cap(spec.ammo_type),
        )
        assert bandolier.get(spec.ammo_type, 0) - before == quantity, (
            f"ground_ammo {item_id}x{quantity} exceeds the caliber's "
            "carry cap (bars would silently clamp)"
        )
    return weapons, holstered, armor, bandolier


def sheet_strength(sheet) -> int:
    """The sheet's ground Strength — drives expedition pack capacity."""
    return starting_ground_stats(sheet.species_id, sheet.class_id).strength


def build_ground_ctx(sheet, game_map, player_start) -> SimpleNamespace:
    """The ground-side ctx: the core spine plus the ground fields the
    rules touch. HP seeds at the sheet's true ground max — the
    GameContext default 23 must never leak into a ground ctx
    (SETTLED 5: the tutorial sheet's max is 28 = 20 + stamina 24//3,
    and the fight's own ``_player_hp_state`` growth lands there)."""
    player = world.Entity(
        "@", (255, 255, 255), world.Position(*player_start), "Player",
    )
    fields = _ctx_core(sheet, game_map, player)
    weapons, holstered, armor, bandolier = build_ground_loadout(sheet)
    stats = starting_ground_stats(sheet.species_id, sheet.class_id)
    fields["ground_stats"] = stats
    fields["equipped_ground_weapons"] = weapons
    fields["holstered_ground_weapons"] = holstered
    fields["equipped_ground_armor"] = armor
    fields["ground_expedition_items"] = []
    fields["bandolier"] = bandolier
    ctx = SimpleNamespace(**fields)
    # The trait-aware max (the same fold ``_player_hp_state`` performs);
    # seeded full — the default 23 never leaks into a ground ctx.
    ctx.ground_max_hp = ctx.ground_hp = (
        20 + stats.stamina // 3
        + sum_armor_bonus(armor.values(), "hp_bonus")
        + ground_max_hp_bonus(ctx)
    )
    return ctx


def _quest_shell_ctx() -> SimpleNamespace:
    """The minimal ctx the planet-pipeline prepare step reads — quest
    progress is empty (the tutorial's sealed-door Mars moment: the
    landmark stamps, the stairs conceal)."""
    return SimpleNamespace(
        main_quest_progress={},
        main_quest_chain="",
        faction_reputation={},
        log=MessageLog(capacity=50),
    )


async def build_planet_grid(grid) -> tuple:
    """Planet mode: the LIVE delve pipeline under the row's fixed grid
    seed — generate (tiles only) → the planet's prepare step (the tile
    mutations the fight happens among) → SKIP populate (the entity
    scatter; SETTLED 4's isolated fight). Returns (map, spawn). The
    RNG world is snapshotted/restored around the build: the pipeline
    reads ``engine.RNG`` at call time, and a direct call (outside
    begin_run) must never leave the process's RNG split across
    instances."""
    from src.spacehack.data.planets import find_planet_spec
    from src.spacehack.dungeon_bsp import generate_dungeon
    from src.spacehack import main_quest

    pspec = find_planet_spec(grid.planet_id)
    params = pspec.dungeon_params
    assert (grid.width, grid.height) == (params.width, params.height), (
        f"{grid.planet_id} grid must match the planet's "
        f"{params.width}x{params.height} DungeonParams"
    )
    _snapshot_rng_world()
    try:
        engine.seed_rng(grid.grid_seed)
        game_map, spawn = generate_dungeon(params)
        if grid.planet_id == "mars":
            await main_quest.prepare_mars_surface(
                _quest_shell_ctx(), game_map, spawn,
            )
        else:
            main_quest.prepare_delve_site(
                _quest_shell_ctx(), game_map, spawn, grid.planet_id,
            )
    finally:
        _restore_rng_world()
    # Only the declared combatants fight: discard everything the
    # prepare step stamped (the cache guardian included).
    game_map.entities = []
    return game_map, spawn


def _stamp_blocks(tiles, blocks, tile) -> None:
    """Stamp unwalkable rect blocks (x, y, w, h) onto a tile grid,
    clipped to the map — the shared stamping of both grid builders."""
    height, width = len(tiles), len(tiles[0])
    for bx, by, bw, bh in blocks:
        for dy in range(bh):
            for dx in range(bw):
                x, y = bx + dx, by + dy
                if 0 <= x < width and 0 <= y < height:
                    tiles[y][x] = tile


def build_ground_grid(grid) -> world.GameMap:
    """Synthetic ground geometry (SETTLED 4's hand-built option): a
    dungeon-floor map with the declared rect blocks stamped as walls."""
    tiles = [
        [world.DUNGEON_FLOOR for _ in range(grid.width)]
        for _ in range(grid.height)
    ]
    _stamp_blocks(tiles, grid.blocks, world.DUNGEON_WALL)
    return world.GameMap(
        width=grid.width, height=grid.height, tiles=tiles, entities=[],
    )


def _seed_ground_enemies(game_map, enemies) -> list:
    """Place each declared ground combatant — the ``npc_char_id`` +
    ``spawn_band`` stamps ``_rules_ground.init`` resolves through."""
    seeded = []
    for side in enemies:
        spec = find_npc_char(side.spec_id)
        assert game_map.tiles[side.pos[1]][side.pos[0]].walkable, (
            f"{side.spec_id} cell {side.pos} is not floor on the "
            "declared grid — the row's audit pin has drifted"
        )
        entity = world.Entity(
            spec.char, spec.fg, world.Position(*side.pos), spec.name,
            npc_char_id=spec.id, spawn_band=side.band,
        )
        game_map.entities.append(entity)
        seeded.append(entity)
    return seeded


# ---------------------------------------------------------------------------
# Stances — the player policy vocabulary (SETTLED 3)
# ---------------------------------------------------------------------------





# ---------------------------------------------------------------------------
# The run + batch drivers
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class RunResult:
    """One fight's outcome: result string, turns used, damage taken
    (hull in the space theater, HP on the ground), and ground rounds
    spent (0 in space — no ammo economy)."""

    outcome: str        # "VICTORY" | "DEFEAT" | "TIMEOUT" | "DISENGAGED"
    turns: int
    hull_damage_taken: int
    ammo_spent: int = 0


def _ground_ammo_total(ctx) -> int | None:
    """All ground rounds currently carried (loaded + bandolier reserve),
    or ``None`` off the ground theater (no ammo economy to measure)."""
    weapons = getattr(ctx, "equipped_ground_weapons", None)
    if weapons is None:
        return None
    loaded = sum(w.loaded_ammo or 0 for w in weapons)
    reserve = sum((getattr(ctx, "bandolier", None) or {}).values())
    return loaded + reserve


async def _mirror_loop(ctx, game_map, console, rules, stance) -> RunResult:
    """``_run_combat_impl`` minus presentation: same helper bodies,
    the stance in the input seat, a turn cap instead of a human."""
    target_idx = 0
    turn = 1
    start_hull = rules.player_hp(ctx)
    start_ammo = _ground_ammo_total(ctx)
    _loop._log_combat_start(ctx, rules)
    for _iteration in range(ACTION_CAP):
        rules.refresh_engaged(ctx, game_map)
        result = _loop._combat_end_check(ctx, game_map, rules)
        if result is not None:
            break
        enemies = rules.get_enemies(ctx)
        target_idx = _loop._retarget_if_dead(ctx, rules, target_idx, enemies)
        action = await stance(ctx, rules)
        target_idx = await _loop._dispatch_combat_action(
            console, ctx, game_map, rules, action, target_idx,
        )
        turn, defeat = await _loop._end_player_turn(ctx, game_map, rules, turn)
        if defeat == "DEFEAT":
            result = "DEFEAT"
            break
        if turn > TURN_CAP:
            result = "TIMEOUT"
            break
    else:
        raise RuntimeError(
            f"stance looped {ACTION_CAP} actions without resolving — "
            "a stuck stance, not a stuck fight"
        )
    damage = max(0, start_hull - rules.player_hp(ctx))
    end_ammo = _ground_ammo_total(ctx)
    ammo = max(0, start_ammo - end_ammo) if start_ammo is not None else 0
    cr = _loop._finish_combat(ctx, rules, result)
    return RunResult(cr.outcome, turn, damage, ammo)


async def _run_once_async(row, run_index: int) -> RunResult:
    """One seeded fight: fresh state, real init, the mirror loop."""
    rules = (
        _rules_ground if row.theater == "ground" else _rules_space
    )
    try:
        ctx, game_map, console, rules = await begin_run(row, run_index)
        return await _mirror_loop(
            ctx, game_map, console, rules, STANCES[row.stance],
        )
    finally:
        # Never leak session state, RNG bindings, or combat locks
        # into the next run or the next test in this process.
        end_run(rules)


async def begin_run(row, run_index: int):
    """Build one fight's full state: grid, entities, seeded ctx, real init.

    Dispatches on the row's theater; returns ``(ctx, game_map,
    console, rules)`` with the RNG already rebound to the run's derived
    seed and the borrowed world snapshotted for ``end_run`` — the
    stance unit tests drive this same state the runner fights from.
    """
    _snapshot_rng_world()
    if row.theater == "ground":
        return await _begin_ground_run(row, run_index)
    return _begin_space_run(row, run_index)


def _begin_space_run(row, run_index: int):
    """The space fight's state (phase 1): system map, ship entities,
    the real ``_rules_space.init`` at the encounter's argument shape."""
    if row.grid.system_id:
        solar_system.set_current_solar_system(row.grid.system_id)
    game_map = build_game_map(row.grid)
    _seed_enemy_entities(game_map, row.enemies)
    ctx = build_ctx(row.player, game_map, row.player_start)
    game_map.entities.append(ctx.player)
    _rebind_run_rng(derived_seed(row.seed, run_index))
    console = _AbsorbingConsole()
    specs = [find_npc_ship(side.spec_id) for side in row.enemies]
    positions = [world.Position(*side.pos) for side in row.enemies]
    rules = _rules_space
    rules.init(
        ctx, console, find_ship(row.player.hull_id),
        ctx.player_owned_ship, ctx.player.pos,
        build_pilot_skills(row.player), specs, positions,
        game_map, ctx.log,
    )
    # Presentation-only dial: the same fight through a compact
    # camera. Verified outcome-neutral (A/B over identical seeds) —
    # view size feeds render/camera math alone, never combat.
    rules._state.view_w, rules._state.view_h = 40, 27
    return ctx, game_map, console, rules


async def _begin_ground_run(row, run_index: int):
    """The ground fight's state (phase 2): the planet-pinned delve
    grid under the row's fixed seed (synthetic geometry when no
    planet is declared), the declared combatants only, the entry
    invariants (fog + reveal at spawn), and the real
    ``_rules_ground.init`` — enemy weapon and carried-consumable rolls
    resolve inside the seeded run."""
    if row.grid.planet_id:
        game_map, spawn = await build_planet_grid(row.grid)
        assert (spawn.x, spawn.y) == tuple(row.player_start), (
            f"{row.grid.planet_id} grid_seed {row.grid.grid_seed} now "
            f"spawns at {(spawn.x, spawn.y)}, not the row's pinned "
            f"{row.player_start} — the audit pin has drifted"
        )
    else:
        game_map = build_ground_grid(row.grid)
    ctx = build_ground_ctx(row.player, game_map, row.player_start)
    game_map.entities.append(ctx.player)
    enemy_entities = _seed_ground_enemies(game_map, row.enemies)
    from src.spacehack.dungeon import init_fog, reveal_around

    init_fog(game_map)
    reveal_around(game_map, ctx.player.pos, radius=game_map.sight_radius)
    _rebind_run_rng(derived_seed(row.seed, run_index))
    console = _AbsorbingConsole()
    rules = _rules_ground
    rules.init(ctx, enemy_entities, game_map, console=console)
    return ctx, game_map, console, rules


@contextmanager
def _inert_presentation() -> Iterator[None]:
    """Headless pygame + INSTANT timing, restored on exit."""
    _ensure_headless_pygame()
    previous = animation_timing.speed_scale()
    animation_timing.set_speed_scale(0.0)
    try:
        yield
    finally:
        animation_timing.set_speed_scale(previous)


def run_once(row, run_index: int) -> RunResult:
    """Sync driver for one run of ``row`` at derived seed ``base+i``.

    Self-contained inert presentation: INSTANT timing regardless of
    caller, and a sandboxed HOME — a DEFEAT reaches
    ``saveload.delete_save()`` through the real finish path and must
    never see the player's actual ``~/.spacehack``.
    """
    with _inert_presentation(), _sandboxed_home():
        return _async_run(_run_once_async(row, run_index))


def run_batch(row) -> list[RunResult]:
    """The full batch: N seeded runs under the row's declared grid.

    Each run pins its own system + inert presentation (see
    ``run_once``/``begin_run``); the wrapper just holds the batch-level
    timing context so per-run save/restore work is idempotent.
    """
    with _inert_presentation():
        return [run_once(row, i) for i in range(row.runs)]


# ---------------------------------------------------------------------------
# Aggregate — pure batch math
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class BatchReport:
    """Averaged outcomes over one batch.

    ``win_rate`` covers every run; the rounds/damage means cover WON
    runs only — the goal shape is "wins come easily", and losing
    runs' shorter, cheaper fights would flatter those bars.
    DISENGAGED counts alongside TIMEOUT as unresolved (SETTLED 5) —
    never a win, never a defeat; a nonzero count is itself a
    stance/geometry finding named at the checkpoint.
    """

    runs: int
    wins: int
    defeats: int
    timeouts: int
    disengagements: int = 0
    win_rate: float = 0.0
    mean_turns: float = 0.0
    max_turns: int = 0
    mean_hull_damage_taken: float = 0.0
    mean_ammo_spent: float = 0.0


def aggregate(results: list[RunResult]) -> BatchReport:
    """Fold run results into the report (pure)."""
    wins = [r for r in results if r.outcome == "VICTORY"]
    defeats = [r for r in results if r.outcome == "DEFEAT"]
    timeouts = [r for r in results if r.outcome == "TIMEOUT"]
    disengaged = [r for r in results if r.outcome == "DISENGAGED"]
    n = len(results)
    mean_turns = (
        sum(r.turns for r in wins) / len(wins) if wins else 0.0
    )
    mean_damage = (
        sum(r.hull_damage_taken for r in wins) / len(wins) if wins else 0.0
    )
    mean_ammo = (
        sum(r.ammo_spent for r in wins) / len(wins) if wins else 0.0
    )
    return BatchReport(
        runs=n,
        wins=len(wins),
        defeats=len(defeats),
        timeouts=len(timeouts),
        disengagements=len(disengaged),
        win_rate=(len(wins) / n) if n else 0.0,
        mean_turns=mean_turns,
        max_turns=max((r.turns for r in results), default=0),
        mean_hull_damage_taken=mean_damage,
        mean_ammo_spent=mean_ammo,
    )


def threshold_checks(report: BatchReport, thresholds) -> tuple:
    """Per-bar results for a stated thresholds row (pure).

    One tuple of ``(name, value, bar, sign, passed)`` per STATED bar —
    the single comparison source the gate asserts and the report
    prints, so the two verdicts (and the printed operator) can never
    drift apart.
    """
    _DIRECTIONS = {
        "win_rate_floor": ">=",
        "win_rate_ceiling": "<=",
        "rounds_ceiling": "<=",
        "damage_taken_ceiling": "<=",
        "ammo_spent_ceiling": "<=",
    }
    pairs = (
        ("win_rate_floor", report.win_rate, thresholds.win_rate_floor),
        ("win_rate_ceiling", report.win_rate, thresholds.win_rate_ceiling),
        ("rounds_ceiling", report.mean_turns, thresholds.rounds_ceiling),
        (
            "damage_taken_ceiling",
            report.mean_hull_damage_taken,
            thresholds.damage_taken_ceiling,
        ),
        (
            "ammo_spent_ceiling",
            report.mean_ammo_spent,
            thresholds.ammo_spent_ceiling,
        ),
    )
    return tuple(
        (
            name, value, bar, _DIRECTIONS[name],
            value >= bar if _DIRECTIONS[name] == ">=" else value <= bar,
        )
        for name, value, bar in pairs
        if bar is not None
    )


def meets_thresholds(report: BatchReport, thresholds) -> bool:
    """Whether a batch clears every stated bar (pure)."""
    return all(check[4] for check in threshold_checks(report, thresholds))
