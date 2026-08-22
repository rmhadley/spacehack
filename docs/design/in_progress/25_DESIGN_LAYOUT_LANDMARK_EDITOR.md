# Design: Standalone Layout and Landmark Editor

## Overview

Build a separate Pygame-based utility for creating and editing the game's
hand-authored `.layout` assets. The tool edits both boardable ship layouts in
`src/spacehack/data/layouts/` and stamped landmark layouts in
`src/spacehack/data/landmarks/`, previews them using the game's native tile
renderer, and validates the game-specific marker contracts before saving.

The first release is a focused editor, not a general map-making suite. It
should make new assets practical to author without hand-counting whitespace,
remembering directive syntax, or discovering malformed landmarks only during a
play session.

## Philosophy alignment

| Project rule | Editor application |
|---|---|
| Data-first | `.layout` remains the source of truth; no new map format or embedded asset database. |
| Pygame-only runtime boundary | The utility uses `pygame-ce` and the existing framebuffer/renderer seams. |
| Reuse before duplication | Existing layout parsing, tile catalog, landmark marker checks, and renderer are reused. |
| Pure computation is tested | Grid conversion, directive generation, and validation helpers receive focused pytest coverage. |
| CP437-safe rendering | The palette only offers glyphs supported by the tilesheet and displays the actual rendered glyph. |
| Domain separation | Editor code lives outside gameplay flow and does not add editor state to `GameContext`. |
| Save/load contract | The editor changes authored data files only; it does not introduce runtime session state. |
| Atomic commits | Each implementation phase is independently testable and committed separately. |

## Scope

### In scope for the MVP

- Open an existing `.layout` file or create a new ship/landmark layout.
- Edit a fixed-width ASCII grid with mouse and keyboard.
- Paint tile glyphs, entity markers, loot markers, and enemy markers.
- Add, remove, and edit `TILE`, `COLOUR`, `LOOT`, and `ENEMY` directives.
- Resize the map while preserving existing cells.
- Save a canonical, readable `.layout` file.
- Preview the parsed layout with the game's native renderer.
- Validate syntax, known tile names, marker rules, and basic reachability.
- Provide clear in-app status/error messages without requiring a terminal.
- Launch independently from the game, initially through a developer command.

### Out of scope for the MVP

- Editing procedural dungeon generation parameters.
- Visual room/corridor generation tools.
- Editing story, mission, or NPC data catalogs.
- Image import/export or arbitrary Unicode font support.
- Undo/redo history, clipboard integration, or collaborative editing.
- Packaging the editor as a separately downloadable executable.
- Replacing the existing `.layout` parser with a second incompatible format.

## User experience

### Main window

The editor uses a three-panel layout:

- **Canvas:** the authored grid, shown at an integer cell scale with a visible
  coordinate grid and optional hull-boundary overlay.
- **Palette:** searchable/grouped tile and marker choices, showing glyph,
  name, kind, and a short semantic description.
- **Inspector/status:** asset type, dimensions, selected glyph, directive
  properties, validation messages, and save path.

The canvas supports left-click painting, right-click sampling, and keyboard
navigation. A selected cell's raw glyph and parsed tile/entity meaning are
shown in the inspector. The preview view renders the loaded `GameMap` through
the normal game renderer so authored colors, backgrounds, entity placement,
and tile behavior are visible before saving.

### Asset modes

- **Ship layout mode:** requires exactly one `P` spawn marker and permits the
  boardable ship marker conventions.
- **Landmark mode:** does not require `P`; validates the landmark entrance and
  optional arrival, console, and stairs contracts used by `landmark.py`.

The mode is selected when creating an asset and inferred from the opened
folder or file path when opening an existing asset.

### Canonical writing

Saving rewrites the file into a stable structure:

1. Generated header with asset name and mode.
2. `MAP` / `ENDMAP` grid, preserving meaningful leading/trailing spaces.
3. `TILE` directives.
4. `ENEMY` directives.
5. `LOOT` directives.
6. `COLOUR` directives.

The writer will not attempt to preserve arbitrary comments or original
formatting. It will preserve all represented map semantics and use only
CP437-safe glyphs. A future version may add editable comments/metadata.

## Data model

The editor's internal model is a mutable editing model, separate from the
runtime `world.GameMap`:

- `EditorDocument`: asset path, asset mode, title/description, grid, and
  directive collections.
- `EditorGrid`: rectangular list of raw glyphs, dimensions, and resize logic.
- `TileDirective`: glyph plus `world.Tile` constant name.
- `ColourDirective`: glyph plus RGB foreground and optional RGB background.
- `LootDirective`: glyph plus room type.
- `EnemyDirective`: glyph plus enemy id, chance, and squad bounds.
- `ValidationIssue`: severity, message, optional cell and directive location.

The document model owns parsing/writing transformations and remains free of
Pygame objects. Pygame canvas/palette code consumes the model and returns user
intent through small event handlers.

The editor will use the current runtime loader as the semantic authority where
possible. A successful temporary-document load must agree with the editor's
own structural validation; discrepancies become validation errors rather than
silently changing the authored grid.

## Domain changes

### New editor package

Create a separate editor package under `tools/layout_editor/` for the MVP,
with focused modules:

- `model.py` — document and directive dataclasses.
- `format.py` — parse/write canonical `.layout` text.
- `validation.py` — pure structural and semantic validation.
- `palette.py` — available tile/entity/marker choices.
- `app.py` — Pygame event loop and screen orchestration.
- `__main__.py` — command-line launch and optional file argument.

The editor must not modify `dungeon.py` or `landmark.py` merely to duplicate
their parsing logic. If a reusable loader or validator needs extraction from
an oversized gameplay module, that extraction is a separate refactor phase
and must satisfy the architecture ratchet.

### Runtime integration

Reuse the existing `dungeon.load_layout()` for preview parsing, passing the
selected document's temporary directory and `require_spawn` according to
asset mode. Reuse `landmark._landmark_markers()` for landmark marker
validation where its contract applies. The editor should report parser errors
with line/cell context.

### Launching

Initial launch forms:

```bash
python -m tools.layout_editor
python -m tools.layout_editor path/to/example.layout
```

The editor will default new documents to a temporary/in-memory state and will
not overwrite a file until the user explicitly saves.

## Phased implementation plan

### Phase 1 — Document model, format writer, and validator

- [ ] Add editor document/directive dataclasses.
- [ ] Parse the existing `.layout` syntax into the document model.
- [ ] Write a deterministic canonical `.layout` representation.
- [ ] Implement structural validation and mode-specific marker checks.
- [ ] Add tests for round-tripping both existing ship and landmark assets,
      preserving spaces, colors, loot, enemies, and special markers.

**PLAYTEST**

1. Run the format/validation tests.
2. Open both a ship layout and a landmark layout through the model loader.
3. Save each to a temporary directory.
4. Load the generated files through `dungeon.load_layout()` and compare the
   parsed dimensions, tiles, entities, and marker directives.
5. Confirm invalid maps produce actionable issues instead of exceptions that
   lose the document.

### Phase 2 — Canvas, palette, and preview application

- [ ] Add a Pygame editor window using the existing runtime conventions.
- [ ] Render an editable grid at an integer scale with pan/scroll support for
      larger maps.
- [ ] Add tile/entity/loot/enemy palette selection and cell painting.
- [ ] Add resize controls and a document mode selector.
- [ ] Add parsed preview mode and validation/status panel.
- [ ] Add open/save/save-as behavior with an unsaved-change indicator.

**PLAYTEST**

1. Launch `python -m tools.layout_editor` with the SDL dummy driver or a real
   display.
2. Create a small ship map with walls, floors, one `P`, one exit, and one
   enemy marker.
3. Save it, reopen it, and verify the canvas is unchanged.
4. Open `mars_signal_door.layout`, switch to preview, and verify its console,
   stairs, colors, and door render as they do in-game.
5. Delete the required landmark entrance and confirm the status panel reports
   the missing marker without crashing.

### Phase 3 — Workflow polish and asset safety

- [ ] Add keyboard shortcuts and concise in-app help.
- [ ] Add safe-save behavior that writes through a temporary file and keeps
      the original until the write succeeds.
- [ ] Add a command-line validation mode for CI/developer workflows.
- [ ] Add regression tests for malformed directives, unknown glyphs, invalid
      references, resize behavior, and landmark reachability.
- [ ] Document the editor command and authoring workflow in `README.md` or a
      concise tool guide.

**PLAYTEST**

1. Run the command-line validator against all shipped layout and landmark
   assets.
2. Intentionally introduce an invalid directive, run validation, and verify
   the reported line and reason.
3. Save a modified copy of an existing asset, interrupt/deny the destination
   if supported, and confirm the original remains intact.
4. Open the saved copy in the game or the relevant layout-loading test and
   verify it remains playable/reachable.

## Acceptance criteria

- Existing shipped layouts and landmarks can be opened without semantic loss.
- A user can create and save a valid small asset without manually editing
  directive syntax.
- The preview uses the same tile semantics and rendering path as the game.
- Invalid ship and landmark assets are identified before save, with actionable
  messages and cell/line context where possible.
- Canonical save/load is deterministic and preserves literal map whitespace.
- The editor adds no gameplay dependency, cross-cutting runtime state, or
  alternate asset format.
- `make check` passes after each committed implementation phase.

## Open questions

1. Should the first release include an explicit undo/redo stack, or should it
   remain a follow-up after the basic authoring workflow is proven?
2. Should saving be restricted to the repository's data directories, or may
   the tool write arbitrary user-selected `.layout` paths?
3. Should the first release include a packaged standalone binary, or is the
   Python module launch sufficient for the initial workflow?
4. Should authored comments/descriptions be editable in the first release, or
   is canonical generated output acceptable?
