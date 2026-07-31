# DESIGN: Save/Load System Rewrite (v2)

> **Status: future.** This is a starting draft for the user to refine before
> promoting to `in_progress/`. Do not implement from this doc as-is — it needs
> a decision pass first (see Open Questions).

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

## Current State — Why It's Brittle

From the existing save/load contract in `knowledge.md`:

| Pattern | How it breaks today |
|---------|---------------------|
| Adding a `GameContext` field without updating both `_ctx_to_dict()` and `load_game()` | Field silently missing from save JSON, or resets to default on load. |
| Adding module-level mutable state without save/load support | Global retains its default value on Continue instead of the saved value. |
| Spawning entities without registering them for save/load sync | Entities despawn on load, or respawn duplicated on top of existing ones. |
| Adding a new game mode without wiring its map into the save file | Loading produces the wrong map with the old mode's entities scattered on it. |

Root cause in all four rows: there is no single mechanism that *guarantees*
new state gets picked up. Each is a manual step a human has to remember, on
every future change, forever.

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
   entity" bug category entirely.
4. **Explicit persisted-vs-transient boundary** — state that must round-trip
   is visually distinct in code from session/UI/animation state that's safe
   to reset, rather than relying on memory.
5. **Memento pattern (GoF) + round-trip test as acceptance criterion** —
   "save → load → assert deep-equal to pre-save state" is the standard
   verification technique for any serialization system. Write this test
   first; build the system to pass it.

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
- **Migrations themselves are not written yet.** The trigger to start
  writing real migrations is a future decision point (roughly: first
  external playtester, or a v1.0 cut) — not part of this doc's scope.

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

Replace `_ctx_to_dict()` / `load_game()`'s manual field lists with:

```python
def serialize_ctx(ctx: GameContext) -> dict:
    return dataclasses.asdict(ctx)   # or cattrs.unstructure(ctx)

def deserialize_ctx(data: dict) -> GameContext:
    return GameContext(**data)       # or cattrs.structure(data, GameContext)
```

Open question: `dataclasses.asdict` is stdlib and zero-dependency but has
rough edges around non-dataclass nested types (enums, custom classes). May
be worth adopting `cattrs` for the nested-type handling alone. Decide during
Phase 1.

### Entity registry (stable ID, single path)

```python
@dataclass
class EntityRecord:
    stable_id: str
    entity_type: str
    data: dict

class EntityRegistry:
    def register(self, entity) -> str: ...   # assigns/returns stable_id
    def serialize_all(self) -> dict[str, dict]: ...
    def deserialize_all(self, data: dict) -> None: ...
```

Every spawn path (missions, dungeons, NPC ships, wrecks, …) registers
through this one registry instead of each feature wiring its own save
support. This is the part of the rewrite that most directly prevents the
"forgot to register this entity type" bug class.

### Module-level state contract, formalized

Currently module globals rely on the "Module-level state contract" section
of `knowledge.md` being followed by hand. Replace with an explicit
registration call each module makes at import time:

```python
saveload.register_module_state("navigation", get=lambda: current_solar_system_id, set=...)
```

The save/load system iterates registered module state generically instead
of `saveload.py` needing to know about every module by name.

### Migration dispatch (empty for now)

```python
CURRENT_SAVE_VERSION = 1
MIGRATIONS: dict[int, Callable[[dict], dict]] = {}

def load_save(raw: dict) -> SaveEnvelope:
    version = raw.get("save_version")
    if version is None or version > CURRENT_SAVE_VERSION:
        raise IncompatibleSaveError(...)
    while version < CURRENT_SAVE_VERSION:
        raw = MIGRATIONS[version](raw)
        version += 1
    return SaveEnvelope(**raw)
```

---

## Implementation Plan (draft phases — refine before promoting to in_progress)

### Phase 1: Round-trip test + envelope scaffolding
- [ ] Write the save/load round-trip test first (populate representative
      state across every current system, save, load, assert equality). This
      test defines "done" for every later phase.
- [ ] Add `SaveEnvelope`, `save_version` stamping, empty `MIGRATIONS` table,
      `IncompatibleSaveError` handling.
- [ ] → **Playtest 1**: save/quit/continue still works for the current game,
      unchanged behavior, now version-stamped.

### Phase 2: Reflection-based GameContext serialization
- [ ] Replace `_ctx_to_dict()` / manual `load_game()` field restoration with
      introspection-based (de)serialization.
- [ ] Decide stdlib `dataclasses.asdict` vs `cattrs` (see open question
      above) and resolve any nested-type gaps found.
- [ ] → **Playtest 2**: full sniff test across every current game mode.

### Phase 3: Entity registry
- [ ] Introduce `EntityRegistry`; migrate one existing entity-spawning path
      (e.g. bounty spawns) onto it as a proof of concept.
- [ ] Migrate remaining spawn paths (dungeons, NPC ships, heist loot, wrecks).
- [ ] → **Playtest 3**: spawn/save/load/continue for every entity-producing
      system; verify no duplication, no despawn.

### Phase 4: Module-level state registration
- [ ] Replace manual module-global handling with the
      `register_module_state()` pattern; migrate every global currently
      listed under the module-level state contract.
- [ ] → **Playtest 4**: full sniff test, focused on mode transitions
      (city/space/dungeon) that depend on module globals.

### Phase 5: Retire old system + update contracts
- [ ] Delete `_ctx_to_dict()` and the old `load_game()` field-restoration
      code.
- [ ] Rewrite the "Save/load contract" section of `knowledge.md` to describe
      the new system (reflection-based, registry-based) instead of the old
      manual checklist.
- [ ] → **Final playtest**: full regression pass across every game system.

---

## Acceptance Criteria

- Adding a new `GameContext` field requires zero save/load code changes to
  be persisted correctly.
- Adding a new entity type requires only registering it with
  `EntityRegistry` — no bespoke save/load wiring.
- The round-trip test from Phase 1 passes and is run as part of the regular
  pre-commit/self-audit gate going forward.
- `knowledge.md`'s save/load contract section reflects the new system, and
  its old manual checklist is removed (it should no longer be needed).

---

## Open Questions (resolve before promoting to `in_progress/`)

1. `dataclasses.asdict` vs adopting `cattrs`/`pydantic` as a dependency —
   decide based on how much nested-type pain Phase 1/2 actually surfaces.
2. Does `EntityRegistry` replace `world.Entity`'s existing identity handling,
   or wrap it? Needs a pre-implementation audit against the current entity
   code before Phase 3 is scoped for real.
3. Should `module_state` registration happen at import time or at
   `GameContext` construction time? Affects ordering/circular-import risk.
4. Exact player-facing behavior for `IncompatibleSaveError` — hard refuse
   with a message, or offer to discard and start fresh from the same menu?
5. Where does RNG state fit in `SaveEnvelope` — part of `ctx`, or its own
   top-level field? (Currently a `GameContext` field per the old contract;
   confirm that still holds under the new model.)
