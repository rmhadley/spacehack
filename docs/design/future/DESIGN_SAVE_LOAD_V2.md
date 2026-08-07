# DESIGN: Save/Load System Rewrite (v2)

> **Status: future.** Updated 2026-08-07 after pytest-coverage work.
> The pytest suite now includes a round-trip test (`tests/test_saveload.py`),
> and `knowledge.md`'s pure-function test contract covers mutation-wrappers.
> This doc's open questions have been resolved; phases re-scoped to focus
> on the highest-leverage change (auto-discovering ctx fields) rather than
> a full reflection + entity-registry rewrite.

## Overview

Replace the current hand-maintained `_ctx_to_dict()` / `load_game()` pair in
`saveload.py` with a save/load architecture that is **correct by
construction** rather than correct by human discipline. The current system
requires a developer to remember to update two parallel functions every time
mutable state is added anywhere in the game (`GameContext` fields, module
globals, spawned entities, new game modes). Forgetting produces a *silent*
bug — no crash, no smoke-test failure, only a playtest catches it. That
failure mode is exactly what this rewrite eliminates structurally.

This is foundational work: every remaining `in_progress/` design doc (bar
missions, militia patrols, main quest, NPC-vs-NPC combat, comms RP) will add
new state that needs to survive save/load. Doing this rewrite before those
land means each of them is built on a system that can't silently drop their
state, instead of adding six more manual sync points to an already-fragile
system.

---

## Philosophy Alignment

| Principle | How it's met |
|-----------|-------------|
| ctx-first | Serialization operates on `GameContext` as the single source of truth, not scattered manual field lists. |
| Data-first | Save format is a versioned, schema-described data structure — not pickled live objects. |
| Atomic commits | Phased implementation, one commit per phase, per project convention. |
| No silent breakage | The explicit goal: a new field/entity/mode should be saved/loaded automatically, or fail loudly (test failure), never silently. |

---

## Current State — Why It's Brittle (updated 2026-08-07)

From the existing save/load contract in `knowledge.md`:

| Pattern | How it breaks today |
|---------|---------------------|
| Adding a `GameContext` field without updating both `_ctx_to_dict()` and `load_game()` | Field silently missing from save JSON, or resets to default on load. |
| Adding module-level mutable state without save/load support | Global retains its default value on Continue instead of the saved value. |
| Spawning entities without registering them for save/load sync | Entities despawn on load, or respawn duplicated on top of existing ones. |
| Adding a new game mode without wiring its map into the save file | Loading produces the wrong map with the old mode's entities scattered on it. |

Root cause in the first row: there is no single mechanism that *guarantees*
new `GameContext` fields get picked up. Each is a manual step a human has to
remember, on every future change, forever. This is the **highest-leverage gap**
— a `GameContext` field auto-discovery mechanism eliminates the most common
silent-bug category in a few dozen lines.

The other three rows (module globals, entity spawning, game modes) have
**not** produced bugs since the current system was built. The entity paths
(bounty spawns, procedural spawns, dungeon entities, loot) all serialize
correctly today. Module globals are only 2 (`current_solar_system_id`, `RNG`)
and both work. New game modes have a clear pattern (space/dungeon branches in
`load_game`). These are lower-leverage than the ctx-field gap — worth
improving but not the primary target.

### What the pytest suite changed

`tests/test_saveload.py` now has a round-trip test (`test_round_trip_city_mode`)
that builds a `GameContext`, saves to a temp path, loads back, and asserts
25+ fields survived. This test **already catches the silent-field-regression
bug**: if a new `GameContext` field is added without updating `_ctx_to_dict()`
and `load_game()`, the test would fail because the loaded value would be the
default, not the known test value. The gap is that no one runs this test
*before* they forget — the contract is still manual.

### What `_d()` already does well

The current `_d()` helper (the recursive serialization primitive) already
handles dataclass recursion, sets, enums, and Position objects. It's
well-tested and stable. The fragility is NOT in the serialization primitives
— it's in the manual field list in `_ctx_to_dict()` (~45 fields) and the
mirror restoration block in `load_game()` (~55 lines). Replacing `_d()`
is unnecessary; replacing the manual field list is high-leverage.

---

## Prior Art / Standards This Design Follows

This is a well-studied problem, not a novel one. The design below borrows
directly from:

1. **Schema versioning + migrations** — the same pattern as DB migrations
   (Rails, Django, Ghost). Every save file carries a `save_version`. Schema
   changes ship a forward-only migration function, never an in-place edit to
   load logic. Long-lived roguelikes with active development (Cogmind,
   Dwarf Fortress, Brogue) use this exact technique to survive years of
   schema churn without every old save breaking on every commit.
2. **Reflection-based serialization** — serialize by introspecting the
   dataclass (`dataclasses.asdict`, or `attrs`/`cattrs`/`pydantic`), not by
   hand-listing fields in two places. A new field is picked up automatically.
3. **Generic entity registry keyed by stable ID** — one save/load code path
   for all entities (same idea underlying ECS serialization), instead of
   per-entity-type special casing. Eliminates the "forgot to register this
   entity" bug category entirely. **Deferred:** the current per-path entity
   serialization (dungeon entities, bounty/procedural spawns, map loot) works
   correctly — revisit if a new entity type introduces the bug this was
   designed to prevent.
4. **Explicit persisted-vs-transient boundary** — state that must round-trip
   is visually distinct in code from session/UI/animation state that's safe
   to reset, rather than relying on memory.
5. **Memento pattern (GoF) + round-trip test as acceptance criterion** —
   "save → load → assert deep-equal to pre-save state" is the standard
   verification technique for any serialization system. **Already done:**
   `tests/test_saveload.py` has a round-trip test with 25+ field assertions
   that passes as part of the pre-commit gate.

---

## Decisions Already Made (do not re-litigate without reason)

- **No backward save compatibility is required right now.** This is a
  pre-release solo project; breaking old saves on a schema change is
  acceptable.
- **The option to add compatibility later must stay open and cheap.**
  Concretely:
  - Every save file stamps `save_version` from day one of this rewrite.
  - Save format is plain versioned data (dict → JSON), never pickled live
    class instances — old saves stay interpretable as data independent of
    future class/field renames.
  - The migration dispatch loop exists now, even with an empty migration
    table (`MIGRATIONS: dict[int, Callable] = {}`).
  - Loading a save with an unrecognized/unsupported version fails loudly and
    cleanly ("incompatible save, starting fresh") — never a silent partial
    load or crash.
- **Migrations are written when the schema changes, not deferred.**
  Phase 1 ships with one real migration (v1→v2: manual field list →
  auto-discovered fields). The dispatch loop is tested on this first
  real use, not on a synthetic example. Future schema changes add new
  entries to `MIGRATIONS` and bump `CURRENT_SAVE_VERSION`.

---

## Data Model (draft — refine before implementing)

### `SaveEnvelope`

```python
@dataclass
class SaveEnvelope:
    save_version: int
    ctx: dict            # reflection-serialized GameContext
    entities: dict        # {stable_id: entity_dict}, one path for all types
    module_state: dict     # registered module-level globals, see below
```

### Reflection-based `GameContext` (de)serialization

Replace the manual field list in `_ctx_to_dict()` / `load_game()` with
auto-discovery via `dataclasses.fields()`:

```python
def _ctx_to_dict_v2(ctx: GameContext) -> dict:
    """Serialize all ctx fields, skipping non-serializable ones."""
    result = {}
    for f in dataclasses.fields(ctx):
        if f.name in _SKIP_FIELDS:  # context, game_map, player, log
            continue
        result[f.name] = _d(getattr(ctx, f.name))
    return result
```

The inverse in `load_game()` iterates the saved keys and sets them on the
new `GameContext` instance. Special-case restoration (mission boards,
bounty spawns, procedural spawns) stays as explicit `_restore_*()` helpers
— these aren't field-level assignments, they're complex domain objects
that need construction logic.

Keep `_d()` as the recursive serialization primitive (no new dependency).
It already handles dataclasses, sets, enums, Position objects — all the
types `GameContext` fields use.

### Entity registry (stable ID, single path) — deferred

The original proposal was a single `EntityRegistry` that every spawn path
registers through. **Deferred** — the current per-path serialization
(dungeon entities via `_dungeon_to_dict`, bounty/procedural spawn sync
in `save_game`, map loot via `_save_loot`) works correctly with no known
bugs. Revisit if a new entity-spawning feature introduces serialization
bugs that the per-path approach doesn't catch.

```python
# Original proposal (retained for reference if/when needed):
@dataclass
class EntityRecord:
    stable_id: str
    entity_type: str
    data: dict

class EntityRegistry:
    def register(self, entity) -> str: ...
    def serialize_all(self) -> dict[str, dict]: ...
    def deserialize_all(self, data: dict) -> None: ...
```

### Module-level state contract, formalized — deferred

Currently module globals rely on the "Module-level state contract" section
of `knowledge.md` being followed by hand. Only 2 globals exist
(`current_solar_system_id`, `RNG`) and both work correctly.

**Deferred** — the proposed `register_module_state()` framework would be
more lines of framework code than the current manual handling. Revisit if
a third module global is introduced.

```python
# Original proposal (retained for reference):
saveload.register_module_state("navigation", get=lambda: current_solar_system_id, set=...)
```

### Migration dispatch (tested on first real use)

The migration dispatch loop lands in Phase 1 alongside the auto-discovery
change, and is tested immediately on the v1→v2 format migration:

```python
CURRENT_SAVE_VERSION = 2   # bumped from 1 by auto-discovery
MIGRATIONS: dict[int, Callable[[dict], dict]] = {
    1: _migrate_v1_to_v2,  # old manual field list → auto-discovered format
}

def load_save(raw: dict) -> SaveEnvelope:
    version = raw.get("save_version")
    if version is None or version > CURRENT_SAVE_VERSION:
        raise IncompatibleSaveError(
            f"Save version {version} is incompatible with game version "
            f"{CURRENT_SAVE_VERSION}. Starting a new game."
        )
    while version < CURRENT_SAVE_VERSION:
        raw = MIGRATIONS[version](raw)
        version += 1
    return SaveEnvelope(**raw)
```

The empty-table approach from the original draft ("dispatch loop exists now,
no real migrations") is skipped — testing the loop on a fake migration is
worse than testing it on the first real one. Phase 1 ships with one real
migration (`v1→v2`) and the test to prove it works.

---

## Implementation Plan (re-scoped 2026-08-07)

### Phase 1: Envelope + auto-discover ctx fields (the high-leverage change)

These are merged into one implementation session because the migration
dispatch loop is only tested on its first real use — the v1→v2 format
change auto-discovery introduces. Separating them would require a fake
migration to test the loop; merging them tests it on real data.

- [ ] Add `SaveEnvelope` dataclass, `CURRENT_SAVE_VERSION = 1`, empty
      `MIGRATIONS` table, `IncompatibleSaveError` (hard refuse).
- [ ] Stamp `save_version` on every save; validate on load.
- [ ] Replace the manual field list in `_ctx_to_dict()` with
      `dataclasses.fields(ctx)` iteration, feeding each field through `_d()`.
- [ ] Replace the manual field restoration in `load_game()` with the inverse
      (iterate saved keys, set on the new ctx).
- [ ] Handle the special cases: `GameMap`/`player`/`context`/`log` are
      reconstructed, not serialized (skip via `_SKIP_FIELDS`);
      `mission_boards` and `bounty_spawns` need their custom restoration
      helpers.
- [ ] Bump to `save_version: 2`, add `MIGRATIONS[1]` to transform the old
      manual-field-list save format into the auto-discovered format.
- [ ] Add a migration test: build a v1 save, run it through the dispatch
      loop, assert the loaded ctx matches a fresh v2 save.
- [ ] → **Playtest**: save/quit/continue in city, space, and dungeon modes.
      Existing round-trip test must pass with its 25+ field assertions.
- [ ] **After this phase, adding a new `GameContext` field requires zero
      save/load code — it's picked up automatically.**

### Phase 2: Retire old code + update contracts
- [ ] Delete the old manual `_ctx_to_dict()` field list and the mirror
      restoration block in `load_game()`.
- [ ] Update `knowledge.md`'s save/load contract to describe the new
      auto-discovery mechanism and the migration dispatch pattern.
- [ ] → **Final playtest**: full regression pass across every game system.

### Deferred (not in scope)

| Item | Why deferred |
|------|-------------|
| EntityRegistry | Entity paths already serialize correctly; no bugs reported |
| Module-state registration | Only 2 globals; framework would be heavier than current code |
| `cattrs` / `pydantic` dependency | `_d()` already handles all needed types |
| Migration dispatch with real migrations | No backward-compat burden yet; dispatch loop exists for when needed |

---

## Acceptance Criteria (re-scoped)

- Adding a new `GameContext` field requires **zero** save/load code changes
  to be persisted correctly — auto-discovered via `dataclasses.fields()`.
- The existing round-trip test (`tests/test_saveload.py`) passes with its
  25+ field assertions, plus any new fields added during implementation.
- A migration test proves the dispatch loop works: build a v1-format save,
  run it through `MIGRATIONS[1]`, load it, assert it matches a fresh v2 save.
- `knowledge.md`'s save/load contract section is updated to describe the
  auto-discovery mechanism and migration dispatch pattern; the old per-field
  checklist is removed.
- Save files carry a `save_version` stamp; loading an incompatible version
  fails loudly with a clear message.

---

## Open Questions (resolved 2026-08-07)

1. **`dataclasses.asdict` vs `cattrs`** — **Neither. Keep `_d()`.**
   `_d()` already handles dataclass recursion, sets→sorted-list, enums→name,
   Position→[x,y]. It's zero-dependency, well-tested, and handles all the
   edge cases the project needs. `dataclasses.asdict` would lose the custom
   enum/set/Position handling. `cattrs` is overkill for a single-dataclass
   serialization task. Instead: auto-discover GameContext fields via
   `dataclasses.fields(ctx)` and feed each through `_d()`, replacing the
   manual field list.

2. **EntityRegistry** — **Defer. Entity paths already work.**
   Bounty spawns, procedural spawns, dungeon entities, and map loot all
   serialize correctly through their respective paths (`_dungeon_to_dict`,
   `_save_loot`, procedural/bounty spawn sync in `save_game`). No entity
   despawn/duplication bugs have been reported since these paths landed.
   A generic EntityRegistry would touch every entity construction site
   (~30+ across the codebase) for a problem that doesn't currently exist.
   Revisit if a new entity-spawning feature introduces the bug this was
   designed to prevent.

3. **Module state registration** — **Defer. Manual contract is fine for 2 globals.**
   Only `current_solar_system_id` and `RNG` need save/load as module globals.
   Both already work correctly (verified by the round-trip test). A
   `register_module_state()` framework would be more lines of framework
   code than the total lines currently handling the 2 globals. Add it only
   if a third module global is introduced.

4. **`IncompatibleSaveError` behavior** — **Hard refuse with a message.**
   Standard roguelike answer: "This save is from a newer / incompatible
   version of the game. Starting a new game." No partial load, no silent
   corruption. The migration dispatch loop handles forward-compatible
   upgrades; unrecognized versions fail loudly.

5. **RNG state in SaveEnvelope** — **Keep it top-level.**
   RNG is module-level state on `engine.RNG`, not a `GameContext` field.
   Keeping it top-level in the save JSON matches the module-level state
   contract in `knowledge.md`. Don't force it onto `ctx` just to satisfy
   a reflection-based serialization model — the `SaveEnvelope` can carry
   both `ctx` (auto-discovered fields) and `rng_state` (explicit top-level)
   without conflict.
