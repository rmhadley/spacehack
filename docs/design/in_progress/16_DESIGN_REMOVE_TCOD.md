# DESIGN: Remove the Remaining tcod Runtime Dependency

> **Status: PROPOSED** — architecture/design only; no implementation has
> started.
>
> **Priority: HIGH** — begin the decoupling now, but execute it in small
> phases rather than as a big-bang rewrite.

## Executive decision

The presentation migration already removed tcod from the visible rendering
path, but the game still uses tcod-shaped consoles, tcod event objects, and a
tcod tileset loader. Removing that last runtime dependency would broaden
 deployment options and simplify the architecture.

The important distinction is that the game does **not** currently depend on
tcod for its gameplay algorithms:

- `world.find_path()` owns the A* implementation.
- `dungeon.reveal_around()` / `_cast_ray()` own dungeon LOS/FOV.
- `dungeon._bsp_split()` owns procedural room-and-corridor generation.
- NPC movement and combat AI consume the project-owned path API.
- No production code currently uses `tcod.path`, `tcod.map`, `tcod.bsp`,
  `tcod.noise`, or `tcod.los`.

Therefore this is primarily a **runtime-boundary and packaging migration**,
not a backend-algorithm rewrite.

### Do we risk a more complicated tcod rug pull by waiting?

**Yes, but the risk is manageable and is mostly proportional to the number of
new call sites we add.** Every new modal, animation, test, or packaging path
that accepts `tcod.console.Console`, constructs `tcod.event.KeyDown`, or
relies on `tcod.context.Context` increases the eventual migration surface.
The current compatibility layer also encourages new code to copy the old
contract because it is convenient.

**We do not need to rush into a dangerous big-bang rewrite.** The game
algorithms are already independent, so postponing this does not create a
hidden algorithmic lock-in. The correct immediate action is to freeze the
boundary and start with low-risk seams:

1. add no new production `tcod` imports or type annotations;
2. replace the event bridge;
3. replace the console framebuffer;
4. replace tileset loading;
5. remove the dependency and update packaging only after the no-tcod import
   gate passes.

In short: **start sooner rather than later, but migrate incrementally.** A
short delay while we finish unrelated gameplay work is safe if the boundary
is frozen. A long delay while continuing to add tcod-shaped features is what
turns this into a rug pull.

## Goals

- Remove `tcod` from the runtime dependency graph.
- Keep Pygame as the only window, input, and presentation owner.
- Preserve the current visual output, CP437 glyph mapping, layout, scaling,
  and interaction behavior.
- Keep gameplay/domain modules independent of both tcod and Pygame where
  practical.
- Preserve headless testing of game algorithms and data.
- Simplify source installs, PyInstaller bundles, CI, and future deployment
  experiments.
- Make the final dependency boundary explicit and mechanically testable.

## Non-goals

- Do not rewrite A*, FOV, BSP, combat, NPC behavior, save/load, or map data
  merely because tcod is being removed.
- Do not replace Pygame with another renderer.
- Do not redesign the UI while changing the backend boundary.
- Do not promise that Pygame becomes a pure-Python deployment: Pygame still
  has native SDL dependencies and platform-specific wheels.
- Do not remove NumPy automatically. First decide whether the final glyph
  pipeline still needs it; eliminating an unnecessary NumPy runtime
  dependency is desirable, but it is a separate choice.

## Current architecture audit

### Existing modules and responsibilities

| Current tcod touchpoint | Current location | Target responsibility |
|---|---|---|
| Event objects and event queue | `pygame_runtime.py`, `input_helpers.py`, `__main__.py`, combat loops, `navigation.py`, `menus/_quest_log.py` | Project-owned input events produced by Pygame |
| Temporary event monkey-patch | `pygame_runtime.PygameRuntime.__enter__()` / `close()` | No global patching; runtime owns polling and passes events explicitly |
| Console framebuffer | `engine.make_console()`, `world.render_*()`, HUD/log/modal renderers | Project-owned `FrameBuffer` or cell/draw-command protocol |
| Console-to-Pygame extraction | `pygame_runtime._commands_from_console()` | Direct frame/draw-command consumption |
| Context compatibility adapter | `pygame_runtime.PygameContext` | Project-owned `PygameContext` with no tcod-shaped promises |
| Tilesheet loading | `engine.load_tileset()` and `tcod.tileset.load_tilesheet()` | Direct Pygame PNG/atlas loading |
| CP437 mapping | `pygame_engine.GlyphAtlas._load_tcod_charmap()` | A project-owned immutable CP437 codepoint table |
| Procedural glyph patches | `engine._procedural_texture_glyphs()` and text widening | Pygame-surface or array-based glyph processing |
| Type annotations | `city.py`, `comms.py`, `dungeon.py`, `game_context.py`, `hud.py`, `message_log.py`, `navigation.py`, `npc_ships.py`, `world.py`, `saveload.py` | Project-owned protocols/types or untyped presentation adapters |
| Direct test fixtures | `tests/test_dev_mode.py`, `tests/test_dungeon.py`, Pygame tests | Project-owned event fixtures and frame fixtures |
| Packaging and documentation | `requirements.txt`, `pyproject.toml`, `spacehack.spec`, `tools/smoke.py`, README, `knowledge.md` | Pygame-only dependency and build documentation |

### Existing seams to preserve

- `world.WorldDrawCommand` and `world.world_draw_commands()` already provide
  a renderer-neutral cell command stream.
- `pygame_world.CaptureConsole` already demonstrates a small project-owned
  console protocol for presentation capture.
- `pygame_engine.PygameInputEvent` already provides a project-owned event
  shape, although the main game still converts events back into tcod objects.
- `pygame_engine.PygameEngine` owns the logical surface, viewport fitting,
  scaling, and display flip.
- `pygame_runtime.PygameRuntime` is the single shared-runtime owner and is
  the natural migration seam.
- `pygame_ui` and the specialized `pygame_*` modules already own the visible
  modal presentation.
- `world.GameMap` owns tile/entity state and collision; it should remain
  independent of rendering.

## Research findings

### What tcod provides in principle

python-tcod includes useful roguelike-oriented algorithm modules such as
pathfinding, FOV/LOS, BSP, and noise. These modules can be used headlessly,
without opening a tcod display context. The relevant documentation is:

- [`tcod.path`](https://python-tcod.readthedocs.io/en/latest/tcod/path.html)
- [`tcod.map`](https://python-tcod.readthedocs.io/en/latest/tcod/map.html)
- [`tcod.bsp`](https://python-tcod.readthedocs.io/en/latest/tcod/bsp.html)
- [`tcod.noise`](https://python-tcod.readthedocs.io/en/latest/tcod/noise.html)

That capability does not create a reason to retain tcod here: this project
already owns the algorithms it uses, and a repository search found no
production imports of those tcod algorithm modules.

### What Pygame provides

Pygame provides the SDL-facing application layer: window creation, input
events, surfaces, image loading, drawing, audio, timing, and display
presentation. It does not provide roguelike-specific A*, FOV, BSP, noise, or
grid-navigation algorithms. Removing tcod therefore means retaining the
project's existing algorithms, not asking Pygame to replace them.

### Deployment implications

Removing tcod should, subject to dependency inspection:

- remove the libtcod/cffi-related dependency and bundle surface;
- reduce PyInstaller hidden-import and native-library complexity;
- avoid tcod/SDL version interactions in environments where Pygame already
  owns SDL presentation;
- make it easier to test or run domain code in environments where tcod is not
  installed;
- make the dependency list describe the actual runtime architecture;
- reduce the number of native binaries that must be inspected and signed in
  frozen macOS builds.

This is not automatically a NumPy removal. `engine.py` currently imports
NumPy at module load time, while `pyproject.toml` lists it under the optional
`visual` extra. Phase 0 must resolve that packaging inconsistency explicitly:
retain NumPy as a declared runtime dependency, or finish the glyph-processing
port without it and remove the dependency separately.

It will **not**:

- eliminate all native dependencies, because Pygame remains a compiled SDL
  package;
- make browser/WASM deployment automatic;
- remove the need for platform-specific Pygame wheels and PyInstaller tests;
- prove headless operation unless gameplay imports are kept separate from the
  Pygame runtime.

## Target architecture

```text
Pygame event queue
        |
        v
PygameRuntime -> PygameInputEvent / project input event
        |
        v
Domain loops and modal runners
        |
        v
Project-owned FrameBuffer or WorldDrawCommand stream
        |
        v
PygameEngine -> GlyphAtlas -> Pygame logical surface -> window
```

The target has no tcod-shaped compatibility layer in the normal path:

- no `tcod.event.wait/get` monkey-patching;
- no `tcod.event.KeyDown` checks in domain code;
- no `tcod.console.Console` annotations or allocations;
- no `tcod.context.Context` field type;
- no tcod tileset loader or charmap lookup;
- no tcod import required to import the game domain.

The target should retain a small project-owned frame abstraction rather than
making every domain know about Pygame surfaces. A frame abstraction keeps
world/HUD rendering testable and leaves room for a future renderer without
reintroducing tcod-shaped APIs.

## Phased implementation plan

### Phase 0 — Freeze and baseline

No behavior change. This phase makes the later migration safer.

- [x] Add a contributor rule: no new `tcod` imports, annotations, event
      fixtures, or console parameters in production code.
- [x] Record the current tcod reference inventory with a checked-in,
      baseline-aware audit tool (`tools/tcod_freeze.py` and
      `tools/tcod_freeze_baseline.json`).
- [ ] Establish visual baselines for city, space, dungeon, combat, title,
      modal, HUD, and message-log frames using the existing Pygame runtime.
- [x] Confirm the existing full test and smoke gates pass before migration.
- [ ] Decide whether the final runtime will retain NumPy for glyph processing
      or replace that narrow use with Pygame surfaces.

**Exit criteria:** new work can proceed without increasing the tcod inventory,
and the visual/test baseline is recorded. The freeze audit is part of the
pre-commit gate for the migration period.

### Phase 1 — Native Pygame input

Replace the Pygame-to-tcod event conversion first because it is a narrow,
well-tested boundary and currently relies on global monkey-patching.

- [ ] Make `pygame_engine.PygameInputEvent` the canonical input type, or
      introduce a similarly small project-owned `InputEvent` dataclass.
- [ ] Preserve key normalization, modifiers, text, quit, key-up, and repeat
      behavior exactly.
- [ ] Update `input_helpers.py` predicates to consume the project event.
- [ ] Update `__main__.py`, combat loops/animations, navigation, and quest-log
      input handlers.
- [ ] Remove `tcod.event` imports and the `PygameRuntime` monkey-patch.
- [ ] Replace direct tcod event fixtures in `tests/test_dev_mode.py`,
      `tests/test_dungeon.py`, and the tcod-event portions of
      `tests/test_pygame_ui.py` / `tests/test_pygame_engine.py` with project
      event fixtures. Classify `tools/_archived/` scripts and
      `tools/text_render_spike.py` explicitly as historical/optional tooling;
      they must not be imported by the game or the no-tcod gate.
- [ ] Define the event-loop contract before changing call sites: blocking
      waits return the next translated event; polling returns all currently
      queued events; `QUIT`, `KEYDOWN`, `KEYUP`, modifiers, text, and key
      repeat retain their current semantics.
- [ ] Add tests for letters, arrows, numpad, shifted punctuation, modifiers,
      quit, unknown keys, blocking-vs-polling behavior, and Pygame key-repeat.

**Exit criteria:** no runtime `tcod.event` import; input tests and a complete
modal/keybinding playtest pass.

### Phase 2 — Project-owned framebuffer

Replace the tcod console without changing domain behavior or visual layout.

- [ ] Define a small mutable `FrameBuffer`/cell protocol after inventorying
      the actual operations used by renderers: `clear`, `print`/write text,
      cell access/planes where still needed, and any explicit presentation
      boundary. Specify default foreground/background values, newline and
      multi-cell text behavior, overwrite order, clipping/out-of-bounds
      writes, and whether blank cells are represented as commands.
- [ ] Keep `WorldDrawCommand` as the preferred path for world rendering.
- [ ] Build a compatibility adapter only inside the migration boundary, not
      as a public tcod-shaped API.
- [ ] Migrate world, HUD, message log, navigation, combat animations, city
      transitions, and remaining render helpers to the project frame type or
      draw commands.
- [ ] Update `pygame_runtime.present()` to consume project frames directly;
      delete `_commands_from_console()` once all callers have moved.
- [ ] Retain capture support for headless renderer tests.
- [ ] Add frame tests for clipping, background colors, default background
      normalization, overwrite order, clearing, Unicode/CP437 handling,
      newline/multi-cell writes, and out-of-bounds writes.

**Exit criteria:** no production `tcod.console.Console` construction or
annotation; frame output matches the visual baseline.

### Phase 3 — Direct Pygame glyph loading

Remove `tcod.tileset` while preserving the current raster exactly.

- [ ] Make the CP437 codepoint order a project-owned constant/table.
- [ ] Load the bundled PNG through Pygame (or a deliberately isolated image
      loader) into the existing `GlyphAtlas`.
- [ ] Port `_procedural_texture_glyphs()` and `_widen_text_glyphs()` to the
      chosen Pygame/array representation.
- [ ] Preserve box-drawing, shade, block, middot, suit, and ordinary-text
      glyph behavior from `engine.py`.
- [ ] Add glyph parity tests for representative codepoints and pixel-size
      invariants; keep a visual regression comparison for the full atlas.
- [ ] Resolve the current packaging inconsistency: because `engine.py`
      imports NumPy at module load time, either declare NumPy as a runtime
      dependency or complete the glyph port without it. Do not leave NumPy
      listed only under the optional `visual` extra if the core runtime still
      imports it.

**Exit criteria:** `pygame_engine.GlyphAtlas` no longer imports tcod and the
rendered atlas is visually equivalent at the current logical size.

### Phase 4 — Remove tcod-shaped context and type contracts

- [ ] Change `GameContext.context` to the project-owned runtime type/protocol.
- [ ] Update `saveload.load_game()` and all context annotations.
- [ ] Remove stale `tcod` names from docstrings, comments, and helper names.
- [ ] Delete obsolete compatibility adapters and archived migration references
      that are no longer useful as historical records.
- [ ] Use a code-search gate to verify all exported symbol call sites after
      signature changes.

**Exit criteria:** production source imports and annotations contain no tcod
references.

### Phase 5 — Dependency, packaging, and CI removal

- [ ] Remove `tcod` from `requirements.txt` and `pyproject.toml`.
- [ ] Update the package description and README credits/install guidance.
- [ ] Remove tcod/cffi hidden imports from `spacehack.spec`.
- [ ] Recheck `numpy` as required, optional, or removed based on Phase 3;
      remove `cffi`/NumPy from the frozen hidden-import list only after
      dependency inspection confirms no remaining consumer.
- [ ] Update `tools/smoke.py` so it no longer claims to mount tcod and add a
      no-tcod import test.
- [ ] Update Makefile, CI, release workflow, and Homebrew/build notes where
      dependency or bundle assumptions changed.
- [ ] Build Linux/source, Windows onedir, and macOS app artifacts; inspect
      native libraries and verify macOS signing remains valid.

**Exit criteria:** a clean environment without tcod can install, import, test,
and launch the game; frozen artifacts contain no tcod/libtcod payload.

### Phase 6 — Final validation and closeout

- [ ] Run `python3 tools/smoke.py && python3 tools/test.py` in the project
      environment.
- [ ] Run import, smoke, full tests, source launch, and PyInstaller analysis
      in an environment where importing `tcod` is impossible, not merely
      where tcod happens to be unused. Verify the supported install path, not
      just selected domain modules.
- [ ] Playtest new game, Continue, city, space, dungeon, ground combat,
      space combat, title, guide, all modal families, and graceful exit.
- [ ] Verify save/load behavior is unchanged across every mode.
- [ ] Verify no accidental gameplay algorithm changes by comparing path,
      LOS, dungeon-generation, and combat regression tests.
- [ ] Update this doc with results, mark all phases complete, then move it to
      `docs/design/complete/`.

## Pre-implementation audit

### Existing modules/classes/helpers to extend or reuse

- `pygame_engine.PygameInputEvent`, `_event_from_pygame()`,
  `normalize_key_name()` — canonical Pygame event representation and key
  normalization.
- `pygame_runtime.PygameRuntime` — shared SDL/Pygame lifecycle; retain its
  ownership of polling, presentation, and cleanup while removing its tcod
  bridge.
- `pygame_engine.PygameEngine` — logical surface, viewport fitting, display
  flip, and glyph atlas ownership.
- `pygame_world.CaptureConsole` — precedent for a project-owned capture/frame
  protocol and isolated presentation tests.
- `world.WorldDrawCommand`, `world.world_draw_commands()`,
  `_append_tile_commands()`, and `_append_entity_commands()` — preferred
  renderer-neutral world output.
- `world.GameMap`, `Tile`, and `Entity` — gameplay state and collision; these
  do not need to become Pygame objects.
- `dungeon.reveal_around()`, `world.find_path()`,
  `dungeon.generate_dungeon()` — project-owned backend algorithms to leave
  untouched.
- `pygame_ui`, `pygame_menu`, `pygame_screen`, `pygame_split`,
  `pygame_combat`, `pygame_navigation`, `pygame_quest_log`, and
  `pygame_world` — existing Pygame presentation families and test seams.
- `tests/test_pygame_engine.py`, `tests/test_pygame_ui.py`,
  `tests/test_pygame_world.py`, `tests/test_pygame_overlay.py`,
  `tests/test_dev_mode.py`, `tests/test_dungeon.py`, and the combat/dungeon
  tests — regression coverage to extend rather than replace.
- `tools/text_render_spike.py` and `tools/_archived/` — classify as optional
  visual tooling or historical migration records; keep them out of runtime
  imports and decide whether they should retain a documented tcod dependency
  or be ported/retired in the final cleanup.
- `spacehack.spec`, `.github/workflows/build.yml`, `Makefile`, and the
  Homebrew cask/tap documentation — existing distribution paths to preserve.

### Three potential duplication hotspots and DRY strategy

1. **Input predicates across the main loop, combat, navigation, and modals.**
   - Risk: each migration adds its own Pygame key-name/modifier checks.
   - Strategy: one project event type, one key normalization helper, and one
     shared predicate/mapping layer. Keep domain actions table-driven where
     possible. Tests target the shared helpers rather than every duplicate
     spelling.

2. **Frame-buffer implementations across world, HUD, combat, and modals.**
   - Risk: a world frame, capture frame, and modal frame independently grow
     slightly different `print`, clipping, color, or clear behavior.
   - Strategy: define one small project-owned frame contract and make
     `CaptureConsole` an implementation/test double of that contract. Keep
     `WorldDrawCommand` as the immutable output form for world rendering;
     do not add a second command model.

3. **Glyph processing and charmap definitions.**
   - Risk: the direct Pygame atlas and the old processed-tcod atlas diverge,
     especially for procedural shades, box-drawing characters, and text
     widening.
   - Strategy: move the CP437 table, glyph patch definitions, and processing
     rules into one renderer-owned module. Build one atlas path and test it
     against the current visual baseline before deleting the old loader.

Additional duplication to watch: packaging dependency lists, hidden-import
lists, README install instructions, smoke-test environment assumptions, and
release-workflow comments. Update each from one migration checklist rather
than inventing a new dependency story per platform.

## Contracts compliance

### Save/load

This design introduces no new gameplay state. Input and frame state are
transient and must not be serialized. Any implementation that adds runtime
configuration or persistent renderer settings must update both
`saveload._ctx_to_dict()` and `load_game()` before landing.

### Game guide

The design does not intentionally change controls. Phase 1 must preserve all
existing key behavior; if key names, repeat behavior, or modal navigation
change, update `help.py` in the same phase and run the guide sniff test.

### Module-level state

Do not add a new mutable module-level renderer or input global. The existing
Pygame runtime object should own lifecycle state. If a new global is
unavoidable, wire its New Game, save, and Continue behavior before merging.

### Pure-function and mutation-wrapper tests

Every new key-normalization, frame-layout, clipping, charmap, or glyph helper
must receive a pytest test in the same phase. Tests must cover empty input,
boundaries, unknown keys, modifiers, out-of-bounds writes, and representative
CP437 codepoints.

## Acceptance criteria

1. `grep` finds no production `tcod` import, annotation, or runtime reference.
2. A clean environment without tcod can import `spacehack`, run smoke tests,
   and execute the game with Pygame installed.
3. No code monkey-patches a third-party event queue.
4. No game/domain module accepts a tcod console or tcod context.
5. World, HUD, combat, dungeon, title, guide, and modal frames match the
   approved Pygame visual baseline.
6. `world.find_path()`, `dungeon.reveal_around()`, BSP generation, combat,
   NPC movement, save/load, and RNG behavior remain regression-green.
7. Source, PyInstaller, macOS, Windows, and Homebrew documentation agree on
   the dependency set.
8. Frozen artifacts contain Pygame and required assets but no tcod/libtcod
   payload.
9. The design doc is updated with phase results and moved to `complete/` only
   after the full validation/playtest checklist passes.

## Open decisions

1. **Frame abstraction:** a minimal mutable `FrameBuffer` with `print()`-style
   compatibility, a stricter cell grid, or direct command streams everywhere?
   Recommendation: use a small frame protocol during migration and prefer
   immutable `WorldDrawCommand` streams for world output.
2. **Glyph processing dependency:** keep NumPy as a required runtime
   dependency, or move the narrow processing path to Pygame surfaces and
   remove NumPy? Recommendation: remove NumPy if pixel parity and startup
   performance remain acceptable; do not make this decision implicitly.
3. **Input type name:** promote `PygameInputEvent`, or rename it to a
   renderer-neutral `InputEvent` before migration? Recommendation: rename to
   `InputEvent` if future non-Pygame input/testing backends are likely.
4. **Compatibility window:** should an internal adapter support old console
   renderers for one phase, or should each renderer migrate directly?
   Recommendation: allow one short-lived adapter, with a deletion checkbox
   and a no-new-callers rule.
5. **Release timing:** ship a Pygame-only development build before removing
   tcod from the public release, or remove it in the next release directly?
   Recommendation: build/test a Pygame-only artifact in CI before the public
   dependency removal, even if it is not advertised.

## Playtest checklist

### Before Phase 1

- [ ] Baseline title, city, space, dungeon, combat, guide, modal, resize,
      and quit behavior.

### After Phase 1

- [ ] Arrows, vim keys, diagonals, numpad, `?`, shifted punctuation,
      modifiers, `ESC`, key repeat, modal navigation, and combat controls.

### After Phase 2

- [ ] City/world rendering, camera edges, HUD, message log, animations,
      modal transitions, dungeon fog, and combat overlays.

### After Phase 3

- [ ] Text, map glyphs, box drawing, shades, floor dots, suits, entity tint,
      and fractional window scaling on macOS/Windows/Linux.

### Before Phase 5 dependency removal

- [ ] New Game → save → Continue in city, space, and dungeon.
- [ ] Full combat flows and death/return-to-title behavior.
- [ ] Fresh install in an environment that has never installed tcod.
- [ ] Frozen macOS and Windows artifacts launch and contain all assets.

## Current phase log

### Phase 0 — design and boundary freeze

- [x] Existing tcod use inventoried.
- [x] Research recorded: Pygame does not replace tcod's roguelike
      algorithms; this project already owns the algorithms it uses.
- [x] Deployment benefit and rug-pull risk assessed.
- [x] User approved the staged direction.
- [x] Strict contributor freeze added to `knowledge.md`.
- [x] Baseline-aware `tools/tcod_freeze.py` audit added and current
      inventory committed to `tools/tcod_freeze_baseline.json`.
- [x] Pre-commit gate expanded to run the freeze audit before smoke/tests.
- [x] Canonical smoke gate invokes the freeze audit, and the build workflow
      runs the freeze audit before platform builds.
- [x] Freeze audit runs on normal `main` pushes and pull requests via the
      dedicated `.github/workflows/tcod-freeze.yml` workflow.
- [ ] Implementation begins with Phase 1 after the freeze baseline is
      reviewed.

**Phase 0 result:** the repository now permits existing tcod references but
fails when protected source, tests, dependencies, packaging, CI, knowledge
policy, or root launchers gain new source-aware tcod references. The audit runs
through the canonical smoke gate, as a standalone CI freeze job on normal
pushes/PRs, and before platform builds. The audit implementation and its
baseline are operational control files excluded from their own inventory;
historical design docs, archived codemods, and the excluded text render spike
remain outside the protected inventory.
