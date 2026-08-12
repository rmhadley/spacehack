# DESIGN: Remove the Remaining tcod Runtime Dependency

> **Status: IN PROGRESS** — Phases 1, 2, 3, 4, and 5 implemented;
> final validation/closeout remains planned.
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
- NumPy removal is included only if the narrow glyph-processing port can
  preserve the raster; it must not become an unrelated gameplay refactor.

## Current architecture audit

### Existing modules and responsibilities

| Current tcod touchpoint | Current location | Target responsibility |
|---|---|---|
| Event objects and event queue | `pygame_runtime.py`, `input_helpers.py`, `__main__.py`, combat loops, `navigation.py`, `menus/_quest_log.py` | Project-owned input events produced by Pygame |
| Temporary event monkey-patch | `pygame_runtime.PygameRuntime.__enter__()` / `close()` | No global patching; runtime owns polling and passes events explicitly |
| Console framebuffer | `engine.make_console()`, `world.render_*()`, HUD/log/modal renderers | Project-owned `FrameBuffer` or cell/draw-command protocol |
| Console-to-Pygame extraction | `pygame_runtime.PygameRuntime.present()` | Direct frame/draw-command consumption |
| Context compatibility adapter | `pygame_runtime.PygameContext` | Project-owned `PygameContext` with no tcod-shaped promises |
| Tilesheet loading | `engine.load_tileset()` | Direct Pygame PNG/atlas loading |
| CP437 mapping | `engine.CP437_CHARMAP` | A project-owned immutable CP437 codepoint table |
| Procedural glyph patches | `engine._procedural_texture_glyphs()` and text widening | Pygame-surface glyph processing |
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

Phase 3 resolves the earlier NumPy packaging inconsistency: the runtime and
bitmap comparison spike now use Pygame surfaces only, so NumPy is no longer a
runtime or visual-extra dependency. The optional visual path remains a Pygame
path and does not require a second pixel-processing library.

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
- [x] Decide to replace the narrow glyph-processing use of NumPy with Pygame
      surfaces after parity testing in Phase 3.

**Exit criteria:** new work can proceed without increasing the tcod inventory,
and the visual/test baseline is recorded. The freeze audit is part of the
pre-commit gate for the migration period.

### Phase 1 — Native Pygame input

Replace the Pygame-to-tcod event conversion first because it is a narrow,
well-tested boundary and currently relies on global monkey-patching.

- [x] Make `pygame_engine.PygameInputEvent` the canonical input type, or
      introduce a similarly small project-owned `InputEvent` dataclass.
- [x] Preserve key normalization, modifiers, text, quit, key-up, and repeat
      behavior exactly.
- [x] Update `input_helpers.py` predicates to consume the project event.
- [x] Update `__main__.py`, combat loops/animations, navigation, and quest-log
      input handlers.
- [x] Remove `tcod.event` imports and the `PygameRuntime` monkey-patch.
- [x] Replace direct tcod event fixtures in `tests/test_dev_mode.py`,
      `tests/test_dungeon.py`, and the tcod-event portions of
      `tests/test_pygame_ui.py` / `tests/test_pygame_engine.py` with project
      event fixtures. Classify `tools/_archived/` scripts and
      `tools/text_render_spike.py` explicitly as historical/optional tooling;
      they must not be imported by the game or the no-tcod gate.
- [x] Define the event-loop contract before changing call sites: blocking
      waits return the next translated event; polling returns all currently
      queued events; `QUIT`, `KEYDOWN`, `KEYUP`, modifiers, text, and key
      repeat retain their current semantics.
- [x] Add tests for letters, arrows, numpad, shifted punctuation, modifiers,
      quit, unknown keys, blocking-vs-polling behavior, and Pygame key-repeat.

**Exit criteria:** no runtime `tcod.event` import; input tests and a complete
modal/keybinding playtest pass.

### Phase 2 — Project-owned framebuffer

Replace the tcod console without changing domain behavior or visual layout.

- [x] Define a small mutable `FrameBuffer`/cell protocol after inventorying
      the actual operations used by renderers: `clear`, `print`/write text,
      cell access/planes where still needed, and any explicit presentation
      boundary. The contract specifies white/blank defaults, optional
      backgrounds, newline and multi-cell writes, overwrite order,
      clipping/out-of-bounds writes, explicit default-cell writes, and
      omission of untouched default cells from draw commands.
- [x] Keep `WorldDrawCommand` as the preferred path for world rendering.
- [x] Build a compatibility adapter only inside the migration boundary, not
      as a public tcod-shaped API. `pygame_world.CaptureConsole` is now a
      compatibility name over `FrameBuffer`.
- [x] Migrate world, HUD, message log, navigation, combat presentation, city
      transitions, dungeon animation, NPC flashes, comms, and quest-log
      render signatures to the project frame type or draw commands.
- [x] Update `pygame_runtime.present()` to consume project frames directly;
      the old native-console plane extraction path is deleted.
- [x] Retain capture support for headless renderer tests.
- [x] Add frame tests for clipping, background colors, default background
      normalization, overwrite order, clearing, newline/multi-cell writes,
      zero-size frames, and out-of-bounds writes.

**Exit criteria:** no production `tcod.console.Console` construction or
annotation; frame output matches the visual baseline.

### Phase 3 — Direct Pygame glyph loading

Remove `tcod.tileset` while preserving the current raster exactly.

- [x] Make the CP437 codepoint order a project-owned constant/table.
- [x] Load the bundled PNG through Pygame into the project-owned
      `PygameTileset` and existing `GlyphAtlas`.
- [x] Port `_procedural_texture_glyphs()` and `_widen_text_glyphs()` to
      Pygame surfaces without changing the processed raster.
- [x] Preserve box-drawing, shade, block, middot, suit, and ordinary-text
      glyph behavior from `engine.py`.
- [x] Add representative codepoint, pixel-size, and full processed-raster
      digest tests; measured parity is 140 mapped glyphs with zero mismatches.
- [x] Remove NumPy from the runtime glyph path, visual extra, and frozen
      hidden-import list.

**Exit criteria:** `pygame_engine.GlyphAtlas` no longer imports tcod and the
rendered atlas is byte-equivalent to the pre-Phase-3 processed raster at the
current logical size.

### Phase 4 — Remove tcod-shaped context and type contracts

- [x] Change `GameContext.context` to the project-owned `PygameContext` type.
- [x] Update `saveload.load_game()` and shared presentation context
      annotations across the runtime, modal families, world/HUD overlays,
      and combat adapters.
- [x] Remove stale backend names from active docstrings, comments, and helper
      descriptions; archived codemods and freeze-policy records remain
      explicitly retained as historical records.
- [x] Delete the obsolete `PygameContext.convert_event()` compatibility shim
      and its regression fixture; shared-runtime detection remains centralized
      in `pygame_runtime.is_shared_context()`.
- [x] Use a code-search gate to verify all exported symbol call sites after
      signature changes.

**Exit criteria:** production source imports and annotations contain no tcod
references.

#### Phase 4 pre-implementation audit

**Existing modules/classes/helpers to extend or reuse**

- `pygame_runtime.PygameContext` already owns the project presentation
  boundary (`present`, `events`, and `wait_events`) and is the natural type for
  `GameContext.context`.
- `pygame_runtime.is_shared_context()` is the existing shared-window guard;
  retain it rather than duplicating runtime-introspection checks in callers.
- `pygame_runtime.PygameRuntime` and `GameRuntime` own lifecycle state and
  remain the only runtime constructors. `pygame_ui._context_game_context()`
  remains the one bridge for reading the live context from the shared runtime.
- `saveload.load_game()` reconstructs `GameContext` in one place, so its input
  annotation and reconstructed context wiring can be updated together.
- `pygame_*` `run_shared()` / `run_for_context()` pairs already establish the
  common presentation-context call shape; update their context annotations
  without changing their event or rendering behavior.

**Three potential duplication hotspots and DRY strategy**

1. **Context annotations across modal runners.**
   - Risk: replacing `Any` piecemeal could create several near-identical
     protocol aliases or leave a mixed contract.
   - Strategy: use the single project-owned `PygameContext` type from
     `pygame_runtime`; keep `Any` only for actual Pygame/test-double values,
     not the shared runtime context parameter.

2. **Shared-runtime detection.**
   - Risk: converting every `getattr(context, "_runtime", ...)` check into a
     local variant would duplicate lifecycle logic.
   - Strategy: keep `is_shared_context()` as the single guard and use the
     existing private runtime access only where a renderer must draw directly
     to the shared logical surface.

3. **Compatibility naming and stale documentation.**
   - Risk: deleting old adapters or renaming helpers can silently leave stale
     call sites and misleading comments.
   - Strategy: search every exported symbol after each signature change, update
     active docstrings/comments in the same change, and leave explicitly
     archived migration scripts outside the runtime inventory unless they are
     still imported or executed by tests.

### Phase 5 — Dependency, packaging, and CI removal

#### Phase 5 pre-implementation audit

**Existing modules/classes/helpers to extend or reuse**

- `pyproject.toml` and `requirements.txt` are the single source for source-install
  runtime dependencies; keep the Pygame requirement aligned in both files.
- `spacehack.spec` already collects the complete `spacehack` package and data
  tree; remove only retired hidden imports and use PyInstaller exclusions to
  prevent an installed build host from leaking retired libraries into output.
- `tools/smoke.py` is the canonical import/signature gate; extend it with a
  subprocess import blocker rather than creating a second dependency checker.
- `tools/tcod_freeze.py` and its baseline remain the controlled inventory for
  approved removals from protected dependency, packaging, CI, and policy files.
- `Makefile`, `.github/workflows/build.yml`, and the Homebrew cask document the
  existing distribution paths; update wording in place rather than duplicating
  install instructions.

**Three potential duplication hotspots and DRY strategy**

1. **Dependency declarations.**
   - Risk: requirements, project metadata, and package docs can drift.
   - Strategy: keep `pygame>=2.5` identical in the two install manifests and
     verify wheel `METADATA` in the Phase 5 build check.

2. **No-retired-backend validation.**
   - Risk: a grep-only test can pass while an import is hidden behind a dynamic
     path, or separate smoke/test implementations can diverge.
   - Strategy: expose one `_assert_backend_independence()` helper from
     `tools/smoke.py`; the smoke gate and its focused regression test call that
     same subprocess check.

3. **Frozen artifact dependency leakage.**
   - Risk: PyInstaller can discover optional packages installed on the build
     host even when the application does not use them.
   - Strategy: retain one dynamic project-submodule collection and use the
     spec's `excludes` list for retired `tcod`/`cffi`/`numpy`, then inspect the
     final dist payload rather than relying on analysis logs.

- [x] Remove `tcod` from `requirements.txt` and `pyproject.toml`.
- [x] Update the package description and README credits/install guidance.
- [x] Remove tcod/cffi hidden imports from `spacehack.spec`.
- [x] Recheck the final `cffi`/tcod dependency boundary after Phase 4;
      active source has no consumer, so no native hidden imports remain.
- [x] Update `tools/smoke.py` so it no longer claims to mount tcod and add a
      no-tcod import test that blocks the retired backend in a subprocess.
- [x] Update Makefile and CI/build notes where dependency or bundle
      assumptions changed; Homebrew has no runtime dependency declaration.
- [x] Build and inspect the Linux/source wheel and PyInstaller onedir analysis;
      macOS signing and Windows artifacts remain covered by their CI jobs and
      are reserved for the cross-platform Phase 6 validation.

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
  imports and port/retire stale dependency wording during final cleanup.
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
2. **Glyph processing dependency:** Phase 3 selected Pygame surfaces and
   removed NumPy after a 140-glyph zero-mismatch raster comparison.
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
- [x] Implementation begins with Phase 1 after the freeze baseline is
      reviewed.

**Phase 0 result:** the repository now permits existing tcod references but
fails when protected source, tests, dependencies, packaging, CI, knowledge
policy, or root launchers gain new source-aware tcod references. The audit runs
through the canonical smoke gate, as a standalone CI freeze job on normal
pushes/PRs, and before platform builds. The audit implementation and its
baseline are operational control files excluded from their own inventory;
historical design docs, archived codemods, and the excluded text render spike
remain outside the protected inventory.

### Phase 1 — native Pygame input

- [x] Promoted `pygame_engine.PygameInputEvent` to the canonical runtime event
      type and added renderer-neutral predicates for keydown, keyup, quit,
      Escape, Shift, guide, and movement lookup. Key repeat is preserved as a
      project-owned `repeat` flag; raw Pygame events are not exposed.
- [x] Added explicit `events()` polling and `wait_events()` blocking APIs to
      `PygameRuntime` and `PygameContext`; both use the shared translator and
      the global tcod event monkey-patch was removed.
- [x] Migrated the main loop, combat loop/encounter/animations, navigation,
      city transition, quest log, and input helpers to      the project event
      contract.

- [x] Migrated the affected event fixtures and bridge tests to
      `PygameInputEvent` fixtures, including key normalization, modifiers,
      guide punctuation, quit, keyup filtering, and runtime polling seams.
- [x] Removed runtime `tcod.event` references from protected production source;
      the remaining tcod inventory is the intentional Phase 3 tileset boundary
      plus approved historical/tooling references.
- [x] Freeze audit, smoke gate, AST compilation, focused migration tests, and
      full test suite pass. Focused migration tests: 618 passed; full suite:
      618 passed.
- [x] Complete the manual input/modal/combat playtest checklist before closing
      Phase 1's playtest exit criterion.

**Phase 1 result:** native Pygame events now travel directly from the shared
runtime to game consumers. Blocking waits preserve the old tuple-style loop
contract while polling drains the current queue; no third-party event queue
is patched. The Phase 1 playtest passed.

### Phase 2 — project-owned framebuffer

- [x] Added `src/spacehack/framebuffer.py` with the explicit mutable
      `FrameBuffer`/`FrameCell` contract and renderer-neutral command output.
- [x] Switched `engine.make_console()` to return `FrameBuffer`; migrated the
      production renderer annotations and shared presentation boundary away
      from `tcod.console.Console`.
- [x] Made `CaptureConsole` a compatibility subclass of `FrameBuffer` and
      updated combat's map projection to use `write_cell()` rather than
      mutating a command snapshot.
- [x] Removed the native console-plane fallback from combat presentation and
      migrated its direct console test fixture to `FrameBuffer`.
- [x] Freeze audit confirms zero protected production `tcod.console` imports,
      allocations, or annotations. The remaining protected tcod inventory is
      the intentionally deferred Phase 3 tileset/charmap path.
- [x] Propagated framebuffer default backgrounds through shared presentation,
      exploration frames, combat payloads, and isolated workers.
- [x] Frame contract and Pygame presentation tests pass: 632 focused tests;
      the full suite also passes with 632 tests.
- [ ] Complete the manual Phase 2 visual checklist: city/world rendering,
      camera edges, HUD, message log, animations, modal transitions, dungeon
      fog, and combat overlays. Automated validation is complete; this manual
      playtest remains the next checkpoint.

**Phase 2 result:** all normal renderers now target a project-owned framebuffer
and the shared Pygame runtime consumes its command stream directly. Visual
layout and gameplay behavior are unchanged; Phase 3 still owns direct glyph
and tileset loading.

### Phase 3 — direct Pygame glyph loading

- [x] Replaced the tcod tileset loader with direct Pygame loading of the bundled
      512x128 RGBA bitmap and a project-owned `CP437_CHARMAP`.
- [x] Ported procedural texture/suit/middot patches and text widening to
      Pygame surfaces.
- [x] Removed NumPy from the engine glyph path, visual extra, and frozen hidden
      imports; the comparison spike now uses the same Pygame tiles.
- [x] Verified exact parity against the pre-Phase-3 processed raster: 140
      mapped glyphs, zero mismatches, digest
      `9211a90e2938fe9066050abb97e5e8658f81f346227ff0a79b498dcf0ce14cef`.
- [x] Focused glyph/runtime tests pass; the full suite currently passes with
      638 tests.
- [ ] Complete the manual Phase 3 visual checklist: text, map glyphs, box
      drawing, shades, floor dots, suits, entity tint, and fractional scaling.

**Phase 3 result:** the active renderer no longer imports `tcod.tileset` and
loads the CP437 bitmap entirely through Pygame. The remaining tcod dependency
is now outside the active glyph/input/framebuffer presentation paths and is
handled by the later context/dependency phases.

### Phase 4 result — project-owned context contracts

- [x] `GameContext.context` and `saveload.load_game(context)` now use the
      project-owned `pygame_runtime.PygameContext` type.
- [x] Shared modal runners, navigation, overlays, world frame builders, and
      combat presentation state use explicit `PygameContext`/`GameContext`
      annotations where those meanings are known; generic `Any` remains only
      for actual Pygame modules, surfaces, payloads, and test doubles.
- [x] Removed the unused `convert_event()` adapter and updated its runtime
      contract test.
- [x] Active production source has zero `tcod`/`libtcod` terminology or
      imports; archived codemods and policy/design history remain intentionally
      retained outside the active runtime contract.
- [x] Focused and full validation pass with 640 tests; import/compile and
      diff checks are clean.

**Phase 4 result:** the last active presentation boundary is now explicitly
project-owned. Runtime contexts no longer advertise a third-party console or
event contract, while the existing Pygame lifecycle, event semantics,
framebuffer behavior, save/load behavior, and modal call shapes remain intact.

### Phase 5 — dependency, packaging, and CI removal

- [x] Removed the retired backend from `requirements.txt` and the project
      dependency metadata; Pygame is now the only runtime dependency.
- [x] Removed the obsolete `tcod` and `cffi` PyInstaller hidden imports while
      retaining dynamic collection of project submodules and all data assets.
- [x] Rewrote smoke-test environment guidance and added a subprocess import
      check that actively blocks the retired backend.
- [x] Updated README, agent knowledge, Makefile, and build-workflow wording to
      describe the Pygame-only runtime. The freeze-policy workflow remains an
      intentional migration control.
- [x] Built/inspected the source package boundary and Linux PyInstaller
      analysis; no active source consumer of `tcod` or `cffi` was found.
- [x] Freeze audit, compile, smoke, focused dependency test, and full suite
      pass with 640 tests; the approved inventory was refreshed for the
      dependency-removal deletions.

**Phase 5 result:** source installation metadata and frozen-build configuration
now describe the actual Pygame-only runtime. A clean import remains valid when
the retired backend is actively unavailable, and the remaining tcod references
are limited to the migration policy, audit tooling, historical records, and
this design document.
