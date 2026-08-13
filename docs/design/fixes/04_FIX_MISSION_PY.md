# FIX: Break `mission.py` into a Package

**Status:** In progress — through Phase 2

## Problem

`src/spacehack/mission.py` is approximately 1,700 lines and currently owns
several unrelated parts of the mission system:

| Responsibility | Current contents |
|---|---|
| Runtime models | `ActiveMission`, `MissionBoard`, `MissionStatus`, `MAX_ACTIVE_MISSIONS` |
| Mission lifecycle | Acceptance checks, cargo reservation, completion, rewards, XP, faction reputation, abort/failure cleanup |
| Delivery state | Standard delivery checks plus secured intercept/heist delivery checks |
| Mission boards | Board keys, creation, offerings, stale-slot eviction, monthly refresh, tutorial filtering, reputation-scaled procedural pay |
| Shared procedural infrastructure | Planet-to-system cache, destination candidate selection, tier rolls, system/planet display helpers |
| Procedural delivery missions | Destination selection, cargo, deadlines, rewards, generated IDs |
| Procedural bounty missions | Target pools, names, squads, loadouts, danger text, deadlines, rewards |
| Procedural bar missions | Intercept/heist, smuggling, salvage, wreck layouts, patrol squads, component cargo |
| Compatibility exports | Static `MissionSpec`, `find_mission`, `list_missions`, and `missions_offered_by` from `data.missions` |

The original file predates the bar-mission system and the current save/load
model. It also underestimates the compatibility surface: callers use both
`from spacehack.mission import symbol` and `mission_module.symbol`, including
helpers such as `destination_system_name`, `release_mission_cargo`,
`mission_spec_from_dict`, and `board_key`.

The goal is a structural refactor only. Mission behavior, generated IDs,
serialized field names, RNG behavior, and call-site semantics must not change.

## Current runtime contracts

### Static versus runtime mission data

Static mission definitions live in `src/spacehack/data/missions/` as frozen
`MissionSpec` records. `mission.py` owns mutable runtime state and business
logic. The package split must retain that boundary:

- Do not move static mission catalogs into the runtime package.
- Do not make `ActiveMission` frozen; it is mutable session state.
- Do not duplicate `MissionSpec` or its lookup registry.

### Save/load contract

Mission state is persisted by `src/spacehack/saveload.py` and attached to
`GameContext`. The refactor must preserve all of the following:

- `player_active_missions` and every `ActiveMission` field, including bounty,
  heist, salvage, smuggling, main-quest, deadline, and reward fields.
- `mission_boards`, their composite `npc_id@planet_id` keys, slots, and refresh
  month.
- `generated_missions`, including reconstruction through
  `mission_spec_from_dict`.
- `MissionStatus` enum names used by serialized data.
- Generated mission IDs and deterministic RNG behavior.

A Continue cycle must produce equivalent runtime objects and behavior. Every
implementation phase must run the save/load tests. Before cutover, add explicit
round-trip fixtures for: one ordinary delivery mission, one bounty mission,
one intercept mission with secured heist state, one smuggling mission, one
salvage mission with wreck/layout fields, at least one mission board with
composite keys, and generated mission specs. Assert the restored dataclass
fields, enum status, board slots, generated IDs, and cargo reservations.

### Compatibility surface

`mission/__init__.py` must re-export the current public compatibility surface,
not only the subset listed in the old design. Before moving code, create an
inventory test or audit of these symbols:

```text
ActiveMission
MissionBoard
MissionStatus
MAX_ACTIVE_MISSIONS
MissionSpec
find_mission
list_missions
missions_offered_by
try_accept_mission
commit_accept_mission
is_deliverable_at
active_is_deliverable_at
find_deliverable
find_deliverable_missions
release_mission_cargo
abort_mission
complete_mission
board_key
ensure_board
find_board_for_mission
mission_spec_from_dict
board_offerings
fill_empty_slots
board_remove
board_return_static
refresh_all_boards
system_display_name
system_name_for_planet
destination_system_name
generate_delivery_mission
generate_bounty_mission
generate_bar_mission
```

The package must preserve existing imports from runtime modules, tests, and
tools. Call-site rewrites are not part of the first refactor unless a symbol
is intentionally made private and the compatibility contract is updated
explicitly. `src/spacehack/npc.py` currently has a `TYPE_CHECKING`-only import
of `Mission`, while the runtime mission module exposes `MissionSpec` and
`ActiveMission` instead; Phase 0 must either correct that annotation or
explicitly document why it remains unresolved before the old module is removed.

## Target package structure

Convert `src/spacehack/mission.py` into the following package:

```text
src/spacehack/mission/
├── __init__.py          # compatibility re-exports and package API
├── _models.py           # ActiveMission, MissionBoard, MissionStatus, constants
├── _helpers.py          # delivery checks, board lookup, display/lookup helpers
├── _lifecycle.py        # accept, complete, abort, cargo, XP, reputation
├── _board.py            # board creation, filling, offerings, refresh, slots
├── _proc_shared.py      # tier rolls, planet/system cache, destination candidates
├── _proc_delivery.py    # procedural delivery generation
├── _proc_bounty.py      # procedural bounty generation and bounty helpers
└── _proc_bar.py         # intercept, smuggling, salvage, bar dispatch
```

### Ownership rules

| Module | Owns |
|---|---|
| `_models.py` | Mutable runtime dataclasses and `MAX_ACTIVE_MISSIONS` |
| `_helpers.py` | Delivery predicates, deliverable searches, board lookup, mission-spec reconstruction, display helpers |
| `_lifecycle.py` | Acceptance, cargo reservation/release, completion rewards, XP, reputation, abort/failure behavior |
| `_board.py` | Board creation, stale-slot eviction, static/procedural offerings, tutorial filtering, monthly refresh |
| `_proc_shared.py` | Shared tier logic, planet/system mapping, destination candidate enumeration, shared procedural tables/helpers |
| `_proc_delivery.py` | Delivery generation only |
| `_proc_bounty.py` | Bounty generation, bounty names, enemy/loadout/squad helpers |
| `_proc_bar.py` | Intercept/heist, smuggling, salvage generators, bar mission dispatch |
| `__init__.py` | Re-export compatibility only; no business logic |

The exact placement of a small helper may change during implementation, but
each function should have one clear owning module. Avoid duplicating destination
selection, tier rolls, or mission-spec reconstruction across generator modules.

## Dependency and import strategy

Keep the package dependency graph acyclic where practical. Use one owner for
shared system/destination primitives; do not make `_helpers.py` and
`_proc_shared.py` import each other:

```text
_models
   ↓
_proc_shared ───────────────┐
   ↓                        │
_helpers ───────────────┐   │
   ↓                    │   │
_board ─────────────────┘   │
   ↓                        │
_lifecycle                 │
   ↑                        │
_proc_delivery / _proc_bounty / _proc_bar

__init__.py imports from the implementation modules last and contains only
compatibility re-exports.
```

`_proc_shared.py` owns tier rolls, planet-to-system mapping, reachability, and
candidate enumeration. `_helpers.py` owns runtime delivery predicates, board
lookup, generated-spec reconstruction, and display formatting; it may import
shared lookup primitives but must not be their second implementation.

Expected external dependencies include `ship`, `faction`, `xp`, tutorial state,
planet/system catalogs, and trade-good/NPC-ship data. Use local imports or
`TYPE_CHECKING` where needed to avoid importing the package aggregator from
its own implementation modules.

Do not assume the old document's simple DAG is sufficient: board filling calls
procedural generators, lifecycle calls XP/reputation and cargo logic, and
save/load reconstructs models and generated specs. Validate imports with the
smoke test and a direct compatibility-import test.

## Pre-implementation audit

### Existing modules and patterns to reuse

- `src/spacehack/data/missions/__init__.py`: frozen `MissionSpec` catalog and
  static lookup functions; keep this as the data source.
- `src/spacehack/game_context.py`: owns `player_active_missions`,
  `mission_boards`, and `generated_missions`; no new parallel state container.
- `src/spacehack/saveload.py`: current serialization/deserialization contract;
  preserve field names and `mission_spec_from_dict` behavior.
- `src/spacehack/faction.py`: existing reputation mutation and mission reward
  tables; lifecycle should call these helpers rather than duplicate them.
- `src/spacehack/ship.py`: cargo capacity and effective-cargo helpers; lifecycle
  should reuse them.
- `src/spacehack/combat/_encounter.py`, `navigation.py`, `time.py`, and
  `game_interactions.py`: existing mission consumers and compatibility seams.
- `src/spacehack/combat/` and `src/spacehack/menus/`: established package
  `__init__.py` re-export pattern.

### Duplication hotspots and DRY strategy

1. **Destination/system enumeration** — delivery, smuggling, bounty, and
   salvage all need reachability and destination selection. Keep one shared
   `_proc_shared` candidate path and parameterize hop ranges/filters.
2. **Mission lifecycle cargo/reward handling** — complete, abort, and failure
   paths must share cargo-release and reward/reputation helpers. Keep mutation
   wrappers in `_lifecycle`; do not copy reservation math into callers.
3. **Compatibility and generated-spec reconstruction** — save/load and board
   rendering depend on the same runtime exports and generated mission fields.
   Re-export through `__init__.py` and keep `mission_spec_from_dict` in one
   helper instead of creating parallel serializers.

## Implementation plan

Each phase is a separate logical commit and must pass the relevant focused tests
before starting the next phase. Do not delete `mission.py` until the package
imports and save/load behavior are verified.

### Phase 0 — Contract audit

- [x] Inventory all current imports and runtime symbol references.
- [x] Add a compatibility import/export test covering the current surface.
- [x] Record all serialized `ActiveMission`, board, and generated-spec fields.
- [x] Confirm no stale `Mission` symbol is required by a live caller; resolve or
      document any stale import before deleting the old module. `npc.py` now
      annotates the payload as `ActiveMission`.

### Phase 1a — Package skeleton, models, and compatibility shim

- [x] Create `mission/` package skeleton.
- [x] Move models/constants to `_models.py`.
- [x] Re-export the full compatibility surface from `__init__.py` while the
      remaining business logic is temporarily held in `_legacy.py`.
- [x] Correct the stale `npc.py` type annotation from nonexistent `Mission` to
      runtime `ActiveMission`.
- [x] Add compatibility, model-identity, and mission round-trip tests.
- [x] Run import smoke and focused mission/save-load tests (86 focused tests
      pass; full gate passes before this commit).

`_legacy.py` is an intentional temporary owner for the unmoved business logic;
Phase 1b extracts its delivery predicates, searches, board lookup, display
helpers, and `mission_spec_from_dict` into `_helpers.py` before lifecycle and
procedural phases begin.

### Phase 1b — Helpers

- [x] Move delivery predicates, searches, board lookup, display helpers, and
      `mission_spec_from_dict` to `_helpers.py`.
- [x] Keep the compatibility shim and model identity tests green.
- [x] Add direct tests for helper ownership/cache identity, composite board keys,
      and generated-spec reconstruction.
- [x] Run the focused mission/save-load suite (89 tests pass; full gate pending
      final validation for this phase).

`_helpers.py` now owns `_PLANET_SYSTEM_CACHE` and the display/system lookup
functions; `_legacy.py` imports those symbols rather than maintaining a second
implementation. Board and procedural extraction remain future phases.

### Phase 2 — Lifecycle

- [x] Move accept/commit/complete/abort, cargo release, XP, and reputation logic
      to `_lifecycle.py`.
- [x] Preserve mutation timing and caller-owned list bookkeeping.
- [x] Add regression coverage for acceptance/commit separation, secured-heist
      cargo release, abort logging, early bonus, and late penalty.
- [x] Run focused mission/save-load/lifecycle tests (94 passed; full gate pending
      final validation for this phase).

`_lifecycle.py` is now the sole owner of acceptance, cargo reservation/release,
completion rewards, XP/counters, faction reputation, and abort behavior. The
legacy module re-exports those functions so existing imports remain stable.

### Phase 3 — Board management

- [x] Move board creation, offering lookup, fill/eviction, slot mutation, and
      monthly refresh to `_board.py`.
- [x] Preserve tutorial filtering, faction pay scaling, and per-planet keys.
- [x] Test board refresh and save/load round trips (94 focused tests pass).

`_board.py` owns board state transitions and uses lazy procedural-generator
lookup so board imports remain acyclic while later generator modules are
extracted.

### Phase 4 — Shared procedural infrastructure

- [x] Move shared tier/system/planet/destination helpers to `_proc_shared.py`.
- [x] Preserve one planet/system cache and shared destination enumeration.
- [x] Run generator and save/load tests (94 focused tests pass).

`_proc_shared.py` now owns tier rolls, planet/NPC lookup, destination candidate
enumeration, and the planet-to-system cache. `_helpers.py` consumes the shared
cache rather than defining a second one.

### Phase 5 — Delivery generator

- [ ] Move delivery generation to `_proc_delivery.py`.
- [ ] Preserve generated IDs, RNG ordering, fields, rewards, deadlines, and
      destination selection.
- [ ] Run delivery generator and board-refresh tests.

### Phase 6 — Bounty generator

- [ ] Move bounty generation and name/enemy/loadout/squad helpers to
      `_proc_bounty.py`.
- [ ] Preserve target pools, squad fields, rewards, deadlines, and generated
      IDs.
- [ ] Run bounty generator, navigation, combat, and save/load tests.

### Phase 7 — Bar generators

- [ ] Move intercept/heist, smuggling, salvage, and bar dispatch to
      `_proc_bar.py`.
- [ ] Preserve heist, smuggling, salvage wreck/layout, patrol, and component
      fields exactly.
- [ ] Run bar mission, trade, navigation, combat, and save/load tests.

### Phase 8 — Cutover and removal

- [ ] Verify all compatibility imports and package-level symbols.
- [ ] Verify save/load for active missions, boards, generated missions, and
      status fields.
- [ ] Run full mission, navigation, combat, tutorial, trade, and save/load tests.
- [ ] Run `python3 tools/smoke.py`, `ruff check src tests`, and `python3 tools/test.py`.
- [ ] Delete `src/spacehack/mission.py` only after the preceding checks pass.
- [ ] Run a short playtest: accept, complete, and abort delivery/bounty jobs;
      accept an intercept, smuggling, and salvage job; save, continue, and
      inspect the quest log/board state.

## Risks and mitigations

- **Module/package collision:** Python will resolve `spacehack.mission` to the
  new package after the old file is removed. Keep the package API complete and
  test imports before deletion.
- **Circular imports:** Keep models independent; use local imports and avoid
  importing `mission` from implementation modules when importing sibling modules
  directly is sufficient.
- **Save corruption:** Do not rename serialized keys, enum names, generated IDs,
  or dataclass fields. Add round-trip tests before deleting the old file.
- **RNG drift:** Preserve generator call order and shared RNG usage. Refactoring
  must not alter generated mission outcomes for a given RNG state.
- **Static/runtime confusion:** Keep `MissionSpec` in `data.missions`; runtime
  package code should import and re-export it, never define a second catalog.
- **Over-fragmentation:** Split by responsibility, not by arbitrary line count.
  No new helper should be a dumping ground for unrelated mission families.

## Acceptance criteria

- [ ] `src/spacehack/mission/` package exists with the ownership structure above.
- [ ] `src/spacehack/mission.py` is removed only after cutover verification.
- [ ] Existing `spacehack.mission` imports and the audited compatibility surface
      continue to work without unnecessary call-site rewrites.
- [ ] No serialized mission, board, generated-spec, or status field is lost or
      renamed.
- [ ] Procedural delivery, bounty, intercept, smuggling, and salvage generation
      preserve IDs, RNG ordering, fields, rewards, and deadlines.
- [ ] Shared destination, cargo, reward, and generated-spec logic is not
      duplicated across modules.
- [ ] No new module-level function exceeds 40 lines without a documented reason;
      modules remain responsibility-focused rather than arbitrary line-count
      targets.
- [ ] Smoke test, Ruff, focused tests, and the full test suite pass.
- [ ] Save/load and the short mission playtest pass.
