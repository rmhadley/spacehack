# DESIGN: Remove the Remaining tcod Runtime Dependency

> **Status: COMPLETE** — migrated incrementally to a Pygame-only runtime and
> closed after repository cleanup.

## Final result

spacehack no longer depends on the retired backend for runtime, installation,
input, framebuffer, glyph loading, context types, or frozen packaging.
Pygame owns the window, input, surfaces, atlas, and presentation boundary;
gameplay retains its project-owned pathfinding, LOS, dungeon generation,
combat, NPC, save/load, and RNG systems.

## Completed phases

### Phase 0 — Freeze and baseline

Established the migration boundary, recorded the inventory, and added a
temporary reference freeze while the migration was active.

### Phase 1 — Native Pygame input

Promoted `PygameInputEvent` and the runtime polling/waiting contract. Removed
the third-party event queue bridge and preserved key normalization, modifiers,
text, quit, key-up, and repeat behavior.

### Phase 2 — Project-owned framebuffer

Added `FrameBuffer` and renderer-neutral commands. Migrated world, HUD,
message-log, modal, combat, dungeon, animation, and transition render paths.
The shared runtime now consumes project frames directly.

### Phase 3 — Direct Pygame glyph loading

Loaded the CP437 bitmap through Pygame, ported procedural glyph processing to
Pygame surfaces, and verified 140 mapped glyphs with zero processed-raster
mismatches against the approved baseline.

### Phase 4 — Project-owned context contracts

Changed `GameContext.context`, save/load, modal runners, overlays, world
builders, and combat adapters to project-owned `PygameContext`/`GameContext`
contracts. Removed the obsolete event compatibility shim.

### Phase 5 — Dependency and packaging removal

Removed the retired backend from install metadata and obsolete frozen-build
hidden imports. Added a clean import regression that blocks the retired
backend, retained only Pygame as the runtime dependency, and verified source
wheel metadata plus the final PyInstaller payload.

### Phase 6 — Final cleanup and closeout

Removed temporary migration controls, archived migration codemods, stale
fallback terminology, and the obsolete freeze workflow. Generated `dist/`
and `__pycache__/` artifacts were cleaned locally; virtual environments were
preserved. The normal validation gate is now simply:

```bash
python3 tools/smoke.py && python3 tools/test.py
```

## Final validation

- Pygame-only source wheel built successfully; wheel metadata declares
  `pygame>=2.5` and no retired backend or CFFI dependency.
- PyInstaller analysis/build completed successfully on Linux.
- Final frozen payload contained no `tcod`, `libtcod`, `cffi`, or `numpy`
  payload files or contents.
- Clean import passed with the retired backend actively blocked in a
  subprocess.
- Full suite passed: **640 tests**.
- Compile, smoke, and diff checks passed.
- PNG tileset iCCP metadata warning was removed without changing IDAT pixels.
- Manual playtest passed for the current Pygame runtime.

## Architecture contracts after closeout

- Input: `pygame_engine.PygameInputEvent`
- Frames: `framebuffer.FrameBuffer` and `world.WorldDrawCommand`
- Runtime: `pygame_runtime.PygameContext` / `PygameRuntime`
- Atlas: Pygame-loaded `PygameTileset` and `GlyphAtlas`
- Algorithms: project-owned pathfinding, LOS, dungeon generation, combat,
  NPC movement, save/load, and RNG

No migration freeze or compatibility adapter remains in the normal project
workflow. Future presentation work must use these project-owned seams and
must not reintroduce the retired backend as a dependency.
