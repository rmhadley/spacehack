# DESIGN: Fullscreen & Window Options

> **Priority: LOW** — deferred from `03_DESIGN_GAME_INFRASTRUCTURE`.
> Game modes and the pause/save menu are tracked separately in
> `100_DESIGN_GAME_MODES_SAVE_MENU.md`. Keybinding profiles and per-key
> remapping are intentionally not planned.

## Overview

Add a small display-options flow at game start so the player can choose
fullscreen or windowed presentation without changing the game's fixed logical
canvas. The current Pygame renderer already supports a resizable physical
window and aspect-ratio-preserving letterboxing; this design adds persistence
and a discoverable title-screen Options menu rather than a second renderer.

## Scope

This design owns:

- Fullscreen/windowed preference
- Remembered window preference across launches
- A startup **Options** menu
- Display-related guide text and playtest coverage

This design does **not** own:

- Game modes or death rules
- Pause/save behavior
- Keybinding profiles or per-key remapping
- Runtime changes to the logical 100×60 game grid

## Display contract

The logical canvas remains fixed at the current `100 × 60` character cells.
Changing that grid would affect map layouts, HUD sizing, modal geometry, title
art, and renderer tests, so it is deliberately out of scope.

The physical window may be:

- **Windowed:** use the remembered or default window size and remain resizable.
- **Fullscreen:** use the desktop display while fitting the same logical canvas
  with the existing letterbox behavior.

The engine seam is already present in `PygameEngineConfig` and
`PygameRuntime`. The implementation should configure that seam rather than
introduce display globals throughout gameplay modules.

## Configuration

A user-level config file may store display preferences:

`~/.spacehack/config.toml`

Only display settings belong in this document:

```toml
[display]
fullscreen = false
window_width = 1600
window_height = 960
```

Defaults must be used when the file is missing or malformed. The parser must
remain compatible with the project's supported Python versions; configuration
loading must not make a new game fail to start.

The config file is user preference, not save-game state. New Game and Continue
must use the same display preference without changing gameplay serialization.

## Startup Options menu

Add an **OPTIONS** item to the title screen alongside Start New Game,
Continue, Tutorial, and Exit. The menu opens before character creation and
contains display-only settings:

```text
OPTIONS

> Fullscreen: Off
  Window size: 1600 × 960
  Apply
  Back
```

Requirements:

- Fullscreen toggles between On and Off.
- Window size offers only supported window presets, or preserves the current
  resizable window size if preset selection is not needed for the first pass.
- Apply updates the active Pygame engine without changing the logical canvas.
- Back discards un-applied changes.
- The selected preference is written to the user config after Apply.
- If the platform cannot apply a setting, show a clear message and retain the
  last working configuration.
- Options must be available whether or not a save exists.

The first implementation may apply the display setting by reopening or
reconfiguring the shared Pygame window, provided the logical framebuffer and
active title/game flow remain intact.

## Implementation phases

### Phase 1: Display preference model

- [x] Add a small display-config dataclass with fullscreen and window-size
      fields, using safe defaults.
- [x] Load missing/malformed config as defaults.
- [x] Save only display preferences; never mix them into save-game JSON.

### Phase 2: Engine integration

- [x] Pass the display config into `PygameEngineConfig` at startup.
- [x] Implement fullscreen/windowed application while preserving the fixed
      logical canvas and letterboxing.
- [x] Preserve the existing resizable-window behavior in windowed mode.
- [x] Handle unsupported display operations without crashing the game.

### Phase 3: Title Options menu

- [x] Add `OPTIONS` to the title menu.
- [x] Add fullscreen and window-size controls with Apply and Back behavior.
- [x] Ensure Options works with and without an available Continue save.
- [x] Add rollback/error handling when applying a display mode fails.

### Phase 4: Guide + playtest

- [x] Add the Options menu and fullscreen/windowed behavior to the player guide.
- [x] Add tests for config defaults, malformed files, and option transitions.
- [ ] Playtest windowed startup, fullscreen startup, toggling, Apply/Back,
      resizing, and a Continue session after changing display settings.
- [x] Run `make check`.

**Implementation status:** complete. The manual display playtest remains open
for the user; the design stays in `in_progress/` until that playtest passes.

**PLAYTEST (1):** start the game windowed and open title-screen Options with
and without a Continue save. Toggle fullscreen and cycle window sizes, verify
Back leaves the current display unchanged, then Apply and verify the logical
100×60 canvas remains intact. Resize the windowed mode, switch fullscreen and
back, quit and relaunch, and confirm the applied preference persists. Continue
an existing save after changing display settings and verify gameplay/save state
is unchanged. On a platform where a display operation fails, verify the game
shows an error and retains the last working mode.

## Contracts compliance (MANDATORY — see knowledge.md)

- [x] **Save/load:** display preferences remain outside save-game JSON and do
      not alter the existing save schema.
- [x] **Game guide:** the Options menu and display preferences are documented.
- [x] **Pure functions:** config parsing/defaulting and option transitions
      receive explicit inputs and ship focused tests.
- [x] **Module-level state:** no mutable display preference was introduced as
      an unowned module global; the active engine/config owns it.
- [x] **Architecture ratchet:** config parsing, title Options, and engine
      display application live in focused modules rather than the game loop.

## Resolved implementation decisions

1. The first version cycles three supported window presets: 1280×768,
   1600×960, and 1920×1152. Windowed mode remains freely resizable afterward.
2. Fullscreen and window-size changes apply only after selecting `Apply`;
   `Back` discards pending changes.
3. The title Options menu is display-only. Other preferences are out of scope.
