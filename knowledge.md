# spacehack — Agent knowledge

A traditional ASCII-art sci-fi roguelike built on [Pygame](https://www.pygame.org/).

## Quick start

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e .
python -m spacehack           # run the game
```

Launcher scripts (no venv handling — just `python3 run.py`):
`run.py` (cross-platform entry), `run_spacehack` (Linux/macOS shell
launcher), `run_spacehack.bat` (Windows).

## Git workflow (MANDATORY — aggressive local commits)

**Commit after every logical change.** Do not batch changes. Do not wait until the end of a session. The working tree, not the chat log, is the source of truth.

### Commit discipline
- **One commit = one self-contained change** (one refactor step, one feature, or one bug fix).
- **Descriptive messages.** Start with a prefix tag: `feat:`, `fix:`, `refactor:`, `docs:`, `tools:`, `content:`. Example: `feat: add laser damage falloff at range`.
- **Run the smoke gate before each commit.** Never commit without a passing smoke test (see Pre-commit gate below).
- **NO mega-commits.** Break large work into a sequence of atomic commits.

### Commit triggers (AI agents: follow these rules absolutely)

1. **One phase = one commit.** When a design-doc phase is fully implemented and all its checkboxes are checked, commit before starting the next phase.

2. **Bug fixes commit immediately.** A single fix (even one line) is a commit. Do not bundle it with the next feature.

3. **Refactors commit separately.** If a refactor (e.g. DRY extraction) touches files that were modified by the current phase, commit the refactor as its own commit directly after the phase commit.

4. **User says "great" = commit trigger.** Any time the user says some variant of "looks good", "looks great", "nice", "approved" — stop and commit what you have before continuing.

5. **Every distinct file change is a candidate.** If you edit a file that wasn't part of the current phase's plan, that's probably a separate commit waiting to happen.

6. **Boundary rule for cross-cutting changes.** A cross-cutting change (same edit repeated in many files) still counts as ONE commit, because the individual edits are meaningless without each other. Example: wiring `?` into 16 modal handlers across 6 files = one commit ("feat: wire ? into all modal sub-screens").

7. **Never commit without the full pre-commit gate.** Run
   ``python3 tools/tcod_freeze.py && python3 tools/smoke.py && python3 tools/test.py``.

**Violation example from a real session:** After a session with 11 files changed, the agent made 2 commits instead of ~6. The second commit bundled 5+ unrelated changes (a feature, a refactor, a content restructure, a HUD addition, and a one-line fix). Each should have been separate.

### Why
Each new AI session opens from `git status` / `git diff --stat` / `git log`. If changes aren't committed, the agent has no memory of what was done. Commit aggressively so the next turn picks up from a clean diff, not from prose recall.

### Pushing to GitHub (origin: rmhadley/spacehack)

The remote is **HTTPS** — `https://github.com/rmhadley/spacehack.git`.
gh CLI is logged into **two accounts**:

| Account | Role |
|---------|------|
| `rmhadley` | personal — **owns the repo**; repo-local commit identity is `rmhadley <rmhadley@users.noreply.github.com>` |
| `rhadley-recurly` | work — the usual **active** account |

HTTPS git auth follows the gh **active** account, and the SSH key
(`~/.ssh/id_rsa`) is registered to `rhadley-recurly` — so **never** push
via SSH and **never** push while `rhadley-recurly` is active (it would
authenticate as the wrong account).

**Push sequence (MANDATORY when the user asks to push):**

```bash
gh auth status                  # confirm the active account
gh auth switch --user rmhadley  # only if rmhadley is not active
# commit locally first per the discipline above — then:
git push origin main
gh auth switch --user rhadley-recurly  # restore the work default
```

One-liner: `gh auth switch --user rmhadley && git push origin main && gh auth switch --user rhadley-recurly`

Notes:
- **Never force-push** (`git push -f`) to origin unless the user explicitly asks.
- Push is a separate explicit step from committing — never bundle an uncommitted change into a push.
- Do not change the repo-local git identity; every commit is already attributed to `rmhadley` automatically.

---

## Key conventions (always follow)

### ctx-first design
All cross-cutting state goes through `GameContext` (`ctx`). **Never** use these as bare names in domain functions:

- `game_map`, `log`, `stats`, `character_info`
- `player_owned_ship`, `player_active_mission`, `context`

Always: `ctx.game_map`, `ctx.log`, etc.

### GameContext fields
| Field | Type | Purpose |
|-------|------|---------|
| `species_name`, `class_name` | `str` | character identity |
| `context` | `PygameContext` | shared Pygame runtime adapter; pass to `pygame_*.run_for_context` |
| `character_info`, `player` | dataclasses | character + entity state |
| `log` | `MessageLog` | in-game log + colour helpers |
| `game_map` | `world.GameMap` | world / entity container |
| `stats` | `HudStats` | aggregate HUD-facing values |
| `player_owned_ship` | `` `OwnedShip | None` `` | equipped ship |
| `player_active_mission` | `` `ActiveMission | None` `` | current mission |

### Adding content (data-first)
All content lives in `src/spacehack/data/` as frozen dataclasses:

| Content | Location |
|---------|----------|
| Weapons (lasers) | `data/weapons/lasers.py` |
| Weapons (missiles) | `data/weapons/missiles.py` |
| Ship modules (engines) | `data/modules/engines.py` |
| Ship modules (systems) | `data/modules/systems.py` |
| Enemy ships | `data/enemies/pirates.py` |
| Solar systems | `data/solar_systems/<name>.py` + register in `__init__.py` |
| Planets | `data/planets/` |
| NPCs | `data/npcs/` |
| Species | `data/species/` |
| Missions | `data/missions/<faction>.py` |
| Character classes | `data/classes/core.py` |

Each data file exposes a frozen `@dataclass` + `find_<thing>(id)` that raises `KeyError`.

### Adding a new game domain
1. Create `src/spacehack/<domain>.py` — setup, execution, post-state live together.
2. Entry point takes `ctx` (+ pure positional args). Access all state via `ctx`.
3. From `__main__`, hand off: `<domain>.<entry_point>(ctx, ...)`. No indirection.
4. For modal-driven UI: run the domain's shared `pygame_*` presentation helper with `ctx.context` (e.g. `pygame_screen.run_for_context(ctx.context, frame, caption=...)`).
5. Add new cross-cutting state as a field on `GameContext`.
6. **Monitor file size** — If any existing `src/spacehack/*.py` approaches ~1000 lines during development, pause and evaluate whether the new code should live in its own module rather than inflating an existing file.

### Pre-commit gate
```bash
python3 tools/tcod_freeze.py && python3 tools/smoke.py && python3 tools/test.py
```

The tcod freeze audit rejects new protected-file references while the
migration is in progress. Existing references are tracked in
`tools/tcod_freeze_baseline.json`; only approved removals or an explicitly
approved migration phase may change that inventory.

The smoke test reuses `.venv/bin/python3` when available and otherwise runs
with the current interpreter. It verifies that the Pygame runtime imports
cleanly with the retired backend actively blocked, along with major modules
and key entry points.

The test runner (`tools/test.py`) also auto-mounts the venv and runs the
pytest suite — formula-correctness tests for pure computation functions.
Never commit without all three gates passing.

### tcod removal freeze — mandatory

The project is completing its migration away from tcod. Until
`docs/design/in_progress/16_DESIGN_REMOVE_TCOD.md` is complete:

- **Do not add new tcod usage.**
- Do not add new `import tcod` / `from tcod` statements in production code.
- Do not add new references to `tcod.event`, `tcod.console.Console`,
  `tcod.context.Context`, or `tcod.tileset`.
- Do not add new calls to `tcod.event.wait()`, `tcod.event.get()`, or
  `tcod.event.poll()`.
- Do not add tcod types to public function signatures, `GameContext` fields,
  or new protocols.
- Do not create new tests that construct tcod events or consoles.
- Do not add tcod to dependencies, PyInstaller hidden imports, CI setup,
  packaging scripts, or future-architecture documentation.
- Do not copy an existing tcod compatibility pattern into new code merely
  because it is convenient.

When adding or modifying presentation/input code, use the migration seams:

- `pygame_engine.PygameInputEvent` for input;
- `world.WorldDrawCommand` for world rendering;
- `pygame_world.CaptureConsole` only as a temporary capture/test seam; and
- project-owned frame/runtime types rather than tcod-shaped contracts.

Existing tcod references may remain temporarily. The freeze inventory
protects `src/`, `tests/`, `tools/`, `knowledge.md`, root launchers,
dependencies, packaging, and CI. The audit implementation and its checked-in
baseline are operational control files, so they are excluded from their own
inventory; do not weaken or broaden those exclusions without updating this
policy and the design doc.

A change may touch an existing tcod reference only when it:

1. removes or reduces that reference;
2. is part of an approved phase in
   `docs/design/in_progress/16_DESIGN_REMOVE_TCOD.md`; or
3. is a narrowly-scoped compatibility/test change with a comment explaining
   why it cannot yet be removed.

The exception must be reflected in the design doc's current phase log, and
the baseline must be intentionally regenerated after review. Historical design
docs, `tools/_archived/`, and explicitly excluded visual spikes are not part
of the protected inventory; they must not be imported by the game or the
no-tcod validation gate.

Before implementing any change, inspect the changed files with:

```bash
python3 tools/tcod_freeze.py
```

If the audit reports an added reference, remove it or stop and obtain explicit
approval for the migration exception. The freeze is lifted only after the
design doc's final no-tcod acceptance criteria pass.

### Refactor philosophy
- **Data-first.** New content is a file in `data/` backed by a frozen dataclass. No content lives in `__main__.py` or runtime modules.
- **Cross-cutting state through `ctx`.** No bare-Name regressions.
- **Domains own their flow.** Dispatcher is domain-unaware, one-call handoff.
- **Atomic commits.** One self-contained change per commit. Descriptive message.
- **Git anchors every step.** Each new session starts from `git status` / `git diff --stat`, not prose recall.
- **Gates beat playtests.** Run the smoke test before each commit to catch import errors and missing entry points.
- **Terse code-shaped docs.** Skim-don't-read mode.

### Tcod-safe characters (CP437)

The tilesheet `dejavu16x16_gs_tc.png` uses CP437 encoding. Only characters in the CP437 set render correctly. **Always use CP437-safe characters for UI elements** — avoid Unicode block chars (U+2588 `█`, U+2591 `░`, U+2502 `│`, U+2500 `─`) that may not map to the tilesheet. Safe alternatives:

| Purpose | Safe (CP437) | Unsafe (Unicode) |
|---------|-------------|------------------|
| Filled bar | `#` (0x23) | `█` (U+2588) |
| Empty bar | `-` (0x2D) or `.` (0x2E) | `░` (U+2591) |
| Center marker | `|` (0x7C) | `│` (U+2502) |
| Horizontal line | `-` (0x2D) or `=` (0x3D) | `─` (U+2500) |

Pre-existing violations (faction bars were fixed; `═` in some titles remains but renders on the tilesheet — double-check before using box-drawing chars).

### Fonts & rendering (engine.py)

- **The native bitmap is the only renderer**: `dejavu16x16_gs_tc.png` is
  loaded at its native 16×16 tile size, keeping ordinary text crisp and free
  of runtime anti-aliasing. The game intentionally fails clearly if this
  asset is missing instead of silently switching fonts. The logical grid
  remains 100×60, so the window is 1600×960 pixels before OS/display scaling.- **Text spacing refinement**: after loading the bitmap and its procedural
  texture patches, `engine.py` widens only ASCII letters and digits by three
  bitmap columns, centered inside the same 16×16 cells. Punctuation, map
  symbols, box drawing, and the logical grid remain unchanged.
- **No runtime font fallback**: the project no longer bundles or loads TTF,
  OTF, or TTC fonts. This keeps rendering deterministic across platforms.
- **Font gotcha**: runtime TTF screens scale a font to the requested pixel
  height and may narrow wide faces to fit their panels. Iosevka / JetBrains
  Mono / Fira Code / Cascadia Code can render too narrow at small sizes.
  Before adopting a font verify
  `head.xMax - head.xMin < hhea.ascent - hhea.descent` (fontTools).
  Hack and Source Code Pro pass.
- **Box-drawing gotcha**: asymmetric corners (┌ ┐ └ ┘, ╔ ╗ ╚ ╝) can drift
  off a shared centerline when a renderer centers ink bounds. The bitmap
  engine avoids that variability by drawing the box-drawing block
  (U+2500-256C) **procedurally at load time**: single strokes are adaptive
  4px bands, with double bars positioned from the active tile dimensions,
  mirroring the CP437 tilesheet geometry. `_procedural_texture_glyphs`
  similarly patches shades / block / dot / card-suit glyphs.
- `load_tileset()`: load the native CP437 bitmap → apply procedural texture
  patches → apply the ordinary-text spacing pass. It raises `EngineError` if
  the bitmap cannot be loaded.
- **Retina/fractional-scaling gotcha**: SDL texture scaling can drop pixel
  rows/columns when the window backing scale is not an exact integer multiple
  of the logical grid (fractional Retina / macOS "scaled" display modes).
  Fix: `spacehack/__init__.py` sets `SDL_RENDER_SCALE_QUALITY=linear` at
  package init, before Pygame initialises SDL (effectively identical at
  integer scales).
- `pyproject.toml` package-data ships the bitmap `data/*.png` plus
  `layouts/` and `landmarks/`; `spacehack.spec` bundles the complete data
  tree for frozen builds.
- **macOS frozen builds must be ad-hoc deep-signed** — macOS (mandatory
  on Apple Silicon) rejects unsigned nested dylibs as "damaged".
  `make app` builds and signs (`codesign --force --deep --sign -`); the
  release workflow does the same. Never set `codesign_identity='-'` in the
  spec — it also enables hardened runtime, which makes ad-hoc-signed
  dylibs fail library validation.
- **Never zip the .app with plain `zip -r`** — PyInstaller stores the code
  signatures of non-binary files inside `Contents/Frameworks` (the data
  tree, `spacehack.pkg`) in extended attributes; plain zip drops xattrs,
  so the downloaded app's signature becomes INVALID — "damaged and can't
  be opened", and even Open Anyway fails (only `xattr -cr` bypasses it).
  The release workflow archives with `ditto -c -k --sequesterRsrc
  --keepParent` (single source only). Verify downloads with
  `codesign --verify --deep --strict`; if it fails, the zip step is the
  culprit, not the signing.

### Code quality guardrails

#### 1. State tables over conditional logic

**Never** write chained `if`/`elif`/`else` blocks for state matching, type
dispatching, or command routing when there are **3 or more branches**.
Extract the conditional logic into a static table (dict, tuple, or mapping)
and look up the result. Treat code execution as a table lookup where possible.

**Threshold:** 2-branch `if`/`elif` is fine. The rule activates at 3+.

**Exempt:** Sequential event-dispatch loops (e.g. ``__main__.py`` mode-gated
key handling) where branch order, compound conditions, or fundamentally
different side effects make a flat table obscure the control flow.

**Before (violation):**
```python
if chosen == "Open Trade":
    return _InteractionOutcome.TRADE
elif chosen == "Attack":
    return _InteractionOutcome.ATTACK
elif chosen == "Scan Cargo":
    return _InteractionOutcome.SCAN
else:
    return _InteractionOutcome.BACK
```

**After (table-driven):**
```python
_COMMAND_OUTCOME = {
    "Open Trade": _InteractionOutcome.TRADE,
    "Attack":      _InteractionOutcome.ATTACK,
    "Scan Cargo":  _InteractionOutcome.SCAN,
}
return _COMMAND_OUTCOME.get(chosen, _InteractionOutcome.BACK)
```

**For fat branches** (≥5 lines per case), extract the body of each branch
into a named module-level function and dispatch to it via a handler dict:

```python
_HANDLERS = {
    "weapon":  _handle_buy_weapon,
    "module":  _handle_buy_module,
    "slot":    _handle_sell_slot,
}
handler = _HANDLERS.get(item_type)
if handler:
    handler(ctx, owned, ship_spec, item_id)
```

**What this project already does right (table-driven data):**
- Every ``data/`` catalog — ``_BY_ID: dict[str, Spec]`` with ``find_*(id)``
- ``world.MOVE_KEYS: dict[str, tuple[int, int]]`` — key name → dx,dy
  (vim letters + arrows + numpad; ``VIM_DELTAS`` is the vim-only subset)
- ``faction._SPECIES_REP`` / ``faction._CLASS_REP`` — species/class → rep delta
- ``world.BUILDING_LABEL_COLORS: dict[str, tuple]`` — building label → colour

#### 2. Single Responsibility Principle (SRP)

Every function must do exactly **one thing** — if you can't describe it with
a simple verb phrase (no "and"), split it into private helpers prefixed with
``_``.

**Line-count rules:**

| Lines | Rule |
|-------|------|
| **≤25** | The sweet spot. The project's cleanest code (``ship.py``, ``faction.py``, ``character.py``) already lives here — 90% of functions are 2–21 lines. |
| **26–40** | Allowed only if the function passes the "one verb phrase" test. Pygame modal runners (``pygame_*.run_for_context``), render functions with multiple visual sections, and complex pure-formula functions may legitimately reach this range — but ask yourself: *"could this be two functions?"* |
| **>40** | **Never allowed.** Always split. Every function in this range in the current codebase is doing multiple things by definition. |

**How to split:** Extract logical sections into private module-level helpers.
If a helper needs closure over local state, consider whether that state
should be a parameter instead. Example — a 60-line function with three
sections becomes:

```python
def _do_thing(ctx, data):
    _validate_inputs(data)
    result = _compute_result(data)
    _apply_result(ctx, result)
```

**Exempt:** The top-level game loop ``_run_game`` in ``__main__.py`` is a
known legacy violation (~500 lines). New features must not add to it —
extract to domain modules per the "Adding a new game domain" convention.
When refactoring it, split into ``_handle_key_dispatch``,
``_handle_wall_bump``, ``_handle_occupied_bump``, etc.

#### 3. Composition over inheritance

**Never** use class inheritance for domain logic. Keep inheritance flat —
maximum **1 level deep** — and restricted to standard-library base classes
(``Enum``, ``RuntimeError``, ``TypedDict``). Prefer ``@dataclass`` with
explicit composition over deep hierarchies.

**Dependency injection:** Classes that need collaborators must accept them
via their constructor — never instantiate their own sub-components internally.

**What this project already does right:**
- Every domain class is a ``@dataclass`` — zero inheritance hierarchies.
- ``pygame_engine.PygameEngine(pygame, config, tileset=...)`` — all collaborators injected at construction.
- ``MessageLog(capacity)`` — configuration injected.
- Domain functions take ``ctx`` as first parameter — parameter-based DI
  instead of hidden global state.

**Before (violation):**
```python
class PirateShip(EnemyShip):          # 2-level hierarchy
    def __init__(self):
        self.weapon = LaserCannon()   # instantiates own dependency
```

**After (composition):**
```python
@dataclass
class PirateShip:
    weapon: WeaponSpec                # injected, swappable, testable
```

#### 4. Pure functions for computation, explicit mutation for actions

**Utility and computation functions must be pure:** take explicit inputs, return
new values, never mutate their arguments, and never produce side effects
(logging, I/O, state mutation). Use ``@dataclass(frozen=True)`` for static
data containers — the project already does this for all 24+ data specs.

**Domain action functions** that need to mutate game state (``ctx``) are
allowed, but the computation and the mutation should live in **separate
functions**:

```python
# Pure computation (testable, no ctx)
def _calc_price(base: int, stock: int, target: int) -> int:
    ...

# Thin mutation wrapper (orchestrates, calls pure helpers)
def _buy_good(ctx, planet_id, good_id, qty):
    price = _calc_price(base, stock, target)
    ctx.stats.credits -= price * qty
    ctx.log.add(f"Bought {qty}x {good.name} for {price*qty}$.")
```

**What this project already does right:**
- ``combat/_stats.py`` — every function is pure (``calc_hit_chance``,
  ``calc_flee_chance``, ``_calc_hull``, etc.). Module docstring explicitly
  states "deterministic … suitable for testing in isolation."
- ``faction.py`` — ``get_attitude``, ``starting_reputation`` are pure.
- ``ship.py`` — ``total_ammo_cargo``, ``effective_speed``, ``_sell_price``
  are pure.
- ``trade.py`` — ``trade_price()`` is pure; ``_buy_good()`` / ``_sell_good()``
  call it then mutate ``ctx`` (computation separated from mutation).
- All 24+ data specs in ``data/`` use ``@dataclass(frozen=True)``.

**Exempt:** Render functions (painting to console is inherently a side
effect), modal runners, and the top-level game loop.

#### 5. Performance awareness

Every player move in space mode calls ``move_npcs``, which iterates all
entities and may trigger A* pathfinding for multiple squads. Performance
regressions here are immediately noticeable ("space movement feels
sluggish").

**When adding or modifying code that runs every player step:**

| Rule | Rationale |
|------|-----------|
| **Cache A* paths.** Recompute only on arrival or collision, not every tick. | ``world.find_path()`` explores dozens of cells per call. With 15-30 NPC squads recomputing each tick, this dominates the frame budget. |
| **Batch entity iteration.** Collect squad maps, faction data, and pirate positions in a single pass over ``game_map.entities``. | Three passes = 3x the iteration cost. Every loop over all entities multiplies with the number of entities. |
| **Throttle with probability.** Movement, pathfinding, and spawn rolls can skip 60-80% of ticks with minimal visible impact. | NPCs already move with 80% probability per tick — adding another throttle on top is imperceptible to the player. |
| **Cap per-tick spawns.** Always enforce an upper limit on entity count. | Per-tick spawns compound: ``density × 3`` keeps traffic alive without exponential growth. |
| **Viewport-cull rendering.** Skip entities outside the visible camera area. | Off-screen entities don't need A* paths or movement updates on the same tick. |
| **Prefer simple drift over A* for far-away NPCs.** If a squad is >50 cells from the player, skip pathfinding and let them drift toward their target. | The player can't see or interact with those NPCs anyway — precise pathfinding is wasted work. |

**Common perf traps:**
- Calling ``world.find_path()`` for every squad that needs a new target on the same tick (batch them or stagger them)
- Iterating ``game_map.entities`` inside a loop that also iterates ``game_map.entities`` (quadratic cost)
- Building blocked sets or goal lists from scratch every tick when they rarely change (cache until bodies are destroyed)
- Per-tick log/rendering work that scales with entity count (skip if entity is outside viewport)

**Checklist before shipping a per-tick change:**
- [ ] Does this add a new O(n) pass over all entities? Can it be folded into an existing pass?
- [ ] Does this call ``world.find_path()``? Can it skip ticks or cache the result?
- [ ] Does this spawn new entities? Is there a cap to prevent unbounded growth?

#### 6. Session-state encapsulation — one dataclass, not 14 globals

Module-level combat/encounter state (e.g. ``_rules_space.py``,
``_rules_ground.py``) must live in a single ``@dataclass`` instance
rather than a dozen scattered ``None``-initialized globals with
``global`` declarations in every function.

**Pattern:**

```python
@dataclass
class CombatState:
    ctx: Any
    game_map: world.GameMap
    enemies: list = field(default_factory=list)
    player_hp: int = 30
    target_idx: int = 0
    # … remaining session fields

_state: CombatState | None = None  # ← the ONLY module-level mutable global

def init(ctx, ...) -> None:
    global _state
    _state = CombatState(ctx=ctx, game_map=game_map, ...)

def player_hp(ctx) -> int:
    return _state.player_hp           # ← no global declaration needed
```

**Why:**
- **Readability:** one place to look for all session fields — the dataclass
  definition IS the schema.
- **Testability:** you can construct ``CombatState(...)`` in a test harness
  without touching the module.
- **Fewer ``global`` declarations:** only ``init()`` needs ``global _state``.
  Every other function just reads/writes ``_state.field``.
- **Threadability (future):** a single ``_state`` object is trivially
  replaceable with a parameter if we ever need concurrent encounters.

**Also:** once the dataclass exists, thread it through to callees.
``_run_enemy_turn(state, *, hit_chances, …)`` is better than
``_run_enemy_turn(console, ctx, game_map, player_state, enemy_insts, …)``
with 18 positional params.

**What this project already does right:**
- ``combat/_rules_space.py`` — :class:`SpaceCombatState` (15 globals → 1)
- ``combat/_rules_ground.py`` — :class:`GroundCombatState` (14 globals → 1)

---

## System contracts (MANDATORY — silent breakage if violated)

These contracts govern subsystems that have no automated enforcement.
Forgetting a step here produces a **silent bug**, not a crash — the
smoke test won't catch it. Only a playtest will.

---

### Save/load contract

This is a **roguelike**. Save/load is sacred — every piece of player
state must survive a save/quit/continue cycle without data loss,
duplication, or map corruption. There is no checkpoint system, no
"last autosave" safety net. The single autosave file IS the game.

#### Principle

**All mutable game state must serialize and deserialize correctly.**
This includes, but is not limited to:

- Every ``GameContext`` field (in ``saveload._ctx_to_dict()`` and
  ``load_game()``)
- Module-level globals that carry session state (see Module-level
  state contract)
- The current map and all entities on it
- Player position, inventory, ship state, mission state, reputation
- RNG state (so Continue doesn't replay the same random outcomes)
- Any mode the player can be in (city, space, dungeon, …)

There is only one rule:

> **Every code change that introduces or modifies mutable state MUST
> ensure that state survives a save/load cycle.**

This is not checked by the smoke test. Forgetting it produces a
silent bug that only a playtest can catch.

#### Minimal sniff test

After any change to game state, run this manual check:

1. Reach the modified state (e.g. enter a new mode, interact with a
   new system, take an action that modifies the new state)
2. Save and quit (ESC from the main game loop)
3. Continue from the title menu
4. Verify the game is in the **exact same state** — same map, same
   position, same inventory, same progress, same entities alive/dead

If any piece of state is wrong, the save/load contract is violated.

#### Common gotchas (from real bugs)

| Pattern | How it breaks |
|---------|---------------|
| Adding a ``GameContext`` field without updating both ``_ctx_to_dict()`` and ``load_game()`` | Field silently missing from save JSON (``_ctx_to_dict``) or resets to default (``load_game``). |
| Adding module-level mutable state without save/load support | On Continue the global retains its default value (e.g.
  ``current_solar_system_id`` stays ``"sol"`` instead of the saved
  system). |
| Spawning entities without registering them for save/load sync | Entities despawned on load (not recreated) or respawn on top of
  existing ones (duplication). |
| Adding a new game mode without wiring its map into the save file | Loading produces a wrong map (e.g. Earth instead of dungeon) with
  the old mode's entities scattered across it. |

**Checklist before shipping any change:**
- [ ] Does this change introduce or modify mutable state? (If no, stop here.)
- [ ] Is every new/modified field serialized in ``saveload.save_game()``?
- [ ] Is every new/modified field deserialized in ``saveload.load_game()``?
- [ ] Do module-level globals get saved/restored? (See Module-level state contract.)
- [ ] Does the sniff test pass? (Save → quit → Continue → verify exact state.)

---

### Game guide contract

The in-game guide (``?`` key, ``help.py``) is the player's only
built-in documentation. Every player-facing feature must have a
corresponding ``GuideSection`` that explains how it works. If the
guide is stale, the player has no way to learn the system.

#### Principle

**Every player-facing feature MUST have an up-to-date guide entry.**

> **Any code change that adds, changes, or removes player-facing
> behavior MUST also update the guide.** If the affected system has
> an existing section, update it. If it's a new system, add a section
> and append it to ``GUIDE_SECTIONS``.

#### Minimal sniff test

Open the guide (``?`` from the main game loop) and verify:
1. The new/changed feature has a section
2. The section's body text accurately describes the current behavior
3. Keybindings, formulas, and numbers match the implementation

#### Common gotchas

| Pattern | How it breaks |
|---------|---------------|
| Adding a new interaction (keybinding, bump action, modal) without updating the guide | Player can't discover the feature exists. |
| Changing formulas (damage, prices, XP curves) without updating numbers in the relevant section | Player sees wrong numbers in the guide — trust erodes. |
| Removing a feature without removing or updating its section | Dead section misleads the player into thinking a feature still exists. |
| Adding a section with Unicode box-drawing chars (``│``, ``─``, ``█``) | Characters don't render on the CP437 tilesheet — garbled display. |

**Checklist before shipping:**
- [ ] Does this change affect player-facing behavior? (If no, stop here.)
- [ ] Is the affected guide section updated? Or a new section added?
- [ ] Do keybindings, formulas, and numbers match the implementation?

---

### Module-level state contract

Module-level mutable globals are a deliberate exception to the
``ctx``-first pattern — each one must be explicitly managed across
New Game and Continue. Currently two such globals exist:

| Variable | Module | Reset (New Game) | Save | Restore (Continue) |
|----------|--------|-----------------|------|--------------------|
| ``current_solar_system_id`` | ``solar_system.py`` | ``set_current_solar_system("sol")`` | auto via system_id param | ``solar_system_module.current_solar_system_id = _system_id`` |
| ``RNG`` | ``engine.py`` | ``seed_rng(os.urandom())`` | ``RNG.getstate()`` | ``RNG.setstate(...)`` |

#### Principle

**Every module-level mutable global must survive New Game AND
Continue.** Neither path is optional.

> **Adding a new module-level global is a last resort.** Prefer
> ``GameContext`` fields first. If a global is unavoidable, you
> MUST wire all three lifecycle events.

#### Common gotchas

| Pattern | How it breaks |
|---------|---------------|
| Adding a module-level global without resetting it on New Game | Starting a new game after Continue carries over stale state from the previous session. |
| Adding a global without saving/restoring it | On Continue the global silently reverts to its Python default — the game behaves as though the player never advanced. |

**Checklist when adding a new module-level global:**
- [ ] Is there really no way to put this on ``GameContext`` instead?
- [ ] Reset in ``__main__.py`` new-game setup block
- [ ] Serialize in ``saveload.save_game()``
- [ ] Deserialize + restore in ``saveload.load_game()``

---

### Pure function test contract

**Every new pure function added to the codebase must ship with a pytest
test in the same commit. Any modification to an existing pure function
that changes its behavior or signature must update its corresponding
test in the same commit.**

"Pure" follows the existing guardrail: no I/O, no mutation of arguments,
no side effects, deterministic given its inputs.

A pure function without a test — or a test that hasn't been updated to
match a changed function — is a regression waiting to happen: its
correctness is invisible to the smoke test AND to manual playtesting.

**Mutation-wrapper functions carry the same obligation.** A
mutation-wrapper is a function that mutates domain state (``ctx``, a
``GameMap``, an ``OwnedShip``, or similar data structure) but whose
*logic* is deterministic and testable in isolation — clamping,
re-indexing, boundary crossing, stock drift, LOS propagation, etc.
These are the functions that produced real silent bugs in the past
(guard-post drift, stale LOS frames, negative prices, ammo off-by-one).
Test them by constructing the data structure they mutate, calling them,
and asserting the resulting state.

Examples:
- ``faction.modify_rep`` — mutates ``ctx.faction_reputation``;
  test the clamping and boundary-crossing logic directly
- ``ship._install_weapon`` / ``ship._remove_weapon`` — mutate
  ``OwnedShip``; test slot re-indexing and ammo seeding
- ``trade.tick_economy`` — mutates planet stock dicts; test drift
- ``dungeon.reveal_around`` — mutates ``GameMap.visible``/``seen``;
  test LOS propagation

This applies to all new and modified code. Existing untested functions
are backfilled on the schedule in
``docs/design/in_progress/pytest-coverage.md``.

**Checklist before shipping any new or modified pure or
mutation-wrapper function:**
- [ ] Is there a corresponding test in ``tests/``?
- [ ] If the function was modified, was the test updated to match?
- [ ] Does the test cover the function's key edge cases (boundaries,
      min/max, zero/empty inputs)?
- [ ] Does ``tools/test.py`` pass?

---

## Screen constants (in `engine.py`)
```python
SCREEN_WIDTH   = 100
SCREEN_HEIGHT  = 60
WINDOW_TITLE   = "spacehack"
TILE_WIDTH, TILE_HEIGHT = 16, 16
TILESHEET_FILENAME = "dejavu16x16_gs_tc.png"       # sole CP437 bitmap renderer
```

## Modal UI pattern
```python
pygame_menu.run_for_context(ctx.context, frames, caption="spacehack - ...")
# or pygame_screen.run_for_context(ctx.context, frame, caption=...) for
# tabbed/text screens — the shared Pygame runtime does the presenting.
```

---

## Design doc workflow

Design docs live in `docs/design/` and are the contract between the user and the agent for building complex features.

### Reference (see `docs/design/README.md`)
Directory layout, creating a new doc, and moving docs through the lifecycle live in `docs/design/README.md` — read it before starting any design-doc work. The mandatory process rules below live here because they fire on almost every session.

### Pre-implementation audit (MANDATORY before writing code)

After the design doc is approved but **before writing any code**, you MUST
scan the codebase and add a **"Pre-implementation audit"** section to the
design doc covering three items:

1. **Existing classes / modules to extend or reuse.**
   List every module, class, helper, or pattern already in the project that
   the new feature can build on. Include concrete file paths and function
   names. Examples:
   - ``EnemyInstance`` (``combat/_types.py``) can be reused for crew members
   - ``BountySpawn`` lifecycle (``game_context.py`` → ``__main__.py`` spawn
     + ``navigation.py`` cleanup) can be reused for heist targets
   - ``pygame_faction.run_for_context`` can render the faction standings viewer
   - ``world.Entity`` with ``loot_data`` can place interactable wrecks

2. **Three potential duplication hotspots.**
   Predict where the implementation might accidentally duplicate existing
   logic. Common traps:
   - Copy-pasting an ``Entity(...)`` construction block instead of reusing a
     factory helper
   - Re-implementing a path-computation loop that already exists
   - Duplicating a modal runner pattern instead of reusing the shared
     ``pygame_*`` presentation helpers (``run_for_context`` / ``run_shared``)

3. **DRY strategy for each hotspot.**
   Describe the specific approach: extract a shared helper, parameterize an
   existing function, or use a table-driven dispatch instead of copy-pasted
   conditionals. Reference the relevant guardrail from this document where
   applicable.

Update this audit section as the implementation reveals surprises — it's a
living part of the design doc alongside the playtest checklists.

### Iterating — doc stays the contract

During implementation, the design doc is a **living document**:

- **Update checkboxes** as each sub-step lands (mark `[x]` done)
- **Update playtest instructions** when you learn something mid-phase that changes what needs testing
- **After each playtest**, update the doc with: what passed, what failed, any new edge cases discovered
- **After each playtest**, the agent should ask "what's next per the design doc?" to steer conversation
- If the user says to change direction, **update the doc first** to reflect the new plan, then implement

### Self-audit pass (MANDATORY before every code review)

**After implementing changes but before spawning the code reviewer**, you MUST do a self-audit pass over every file you touched. This prevents the codebase from accumulating cruft between reviews.

Checklist:

1. **Repetition (DRY)** — Scan the changed file(s) for duplicated patterns. Are there loops, formulas, imports, or entity-construction blocks that appear more than once? Do NOT accept ``it was already duplicated`` as an excuse — flag it even if it is pre-existing. Extract shared helpers before moving on.

2. **ctx-first** — Is new cross-cutting state going through `GameContext` or being passed around as bare parameters?

3. **Data-first** — Does new content belong in a `data/` catalog + frozen dataclass?

4. **Live-by-side-effect** — Are domain functions mutating state directly or returning values for the caller to apply?

5. **Unused code** — Did this change leave behind dead imports, functions, fields, or constants? Remove them.

6. **File size** — Check if any touched domain module exceeds ~1000 lines. If so, plan an extraction before moving to the code reviewer.

Once the self-audit is done and any issues are fixed, spawn the code reviewer with the full reviewer checklist (next section).

### Code reviewer — what to look for

The ``code-reviewer-deepseek-flash`` agent is spawned after every significant change. **You MUST include the checklist below verbatim in the prompt you send to the reviewer** — the reviewer does not read knowledge.md, so it can only check what you ask it to check.

Reviewer checklist to paste into every reviewer prompt:

1. **DRY violations** — Scan the changed file(s) for duplicated patterns. Are there loops, formulas, or entity-construction blocks that appear more than once? Do NOT accept ``it was already duplicated`` as an excuse — flag it even if it is pre-existing. Examples of recent misses:
   - Three inner functions doing the identical planet/gate/station iteration (``_goal_for``, ``_tick_goal``, ``_body_goal``)
   - ``world.Entity(...)`` with the same field set constructed inline in two spawn paths
   - Path-computation + target-storage block copy-pasted between initial and per-tick spawn

2. **Inner functions that should be module-level** — If an inner function has no meaningful closure over the parent scope, it should be a module-level helper. Inner functions that duplicate another inner function's logic are always wrong.

3. **Dead code** — Did the change leave behind unused imports, functions, or variables? Check for functions that were only called from the now-replaced code.

4. **Signature mismatches** — Verify that all call sites match updated function signatures (new params, removed params, renamed fields).

5. **Edge cases** — What happens when inputs are empty/None? Does a loop that used to have a fallback still have one? (E.g. the old pirate random-scatter was a fallback when body goals were missing — if that path was removed, is the new guard equivalent?)

6. **Behavior preservation** — If a refactor claims to be purely structural (no behavior change), verify that claim. If behavior DID change (e.g. pirate spawn location standardisation), confirm that was intentional.

If any of these are found, the reviewer MUST flag them as blocking before commit, even if the change ``works.``

Document findings in the design doc's current phase section. Resolve before moving to the next phase.

