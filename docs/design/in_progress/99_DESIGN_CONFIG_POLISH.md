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

- [ ] Add a small display-config dataclass with fullscreen and window-size
      fields, using safe defaults.
- [ ] Load missing/malformed config as defaults.
- [ ] Save only display preferences; never mix them into save-game JSON.

### Phase 2: Engine integration

- [ ] Pass the display config into `PygameEngineConfig` at startup.
- [ ] Implement fullscreen/windowed application while preserving the fixed
      logical canvas and letterboxing.
- [ ] Preserve the existing resizable-window behavior in windowed mode.
- [ ] Handle unsupported display operations without crashing the game.

### Phase 3: Title Options menu

- [ ] Add `OPTIONS` to the title menu.
- [ ] Add fullscreen and window-size controls with Apply and Back behavior.
- [ ] Ensure Options works with and without an available Continue save.
- [ ] Add confirmation or rollback behavior if applying a mode fails.

### Phase 4: Guide + playtest

- [ ] Add the Options menu and fullscreen/windowed behavior to the player guide.
- [ ] Add tests for config defaults, malformed files, and option transitions.
- [ ] Playtest windowed startup, fullscreen startup, toggling, Apply/Back,
      resizing, and a Continue session after changing display settings.
- [ ] Run `make check`.

## Contracts compliance (MANDATORY — see knowledge.md)

- [ ] **Save/load:** display preferences remain outside save-game JSON and do
      not alter the existing save schema.
- [ ] **Game guide:** the Options menu and display preferences are documented.
- [ ] **Pure functions:** config parsing/defaulting and option transitions
      receive explicit inputs and ship focused tests.
- [ ] **Module-level state:** no mutable display preference may be introduced
      as an unowned module global; the active engine/config owns it.
- [ ] **Architecture ratchet:** keep config parsing, title Options, and engine
      display application in focused modules rather than expanding the game
      loop.

## Open questions

1. Which window-size presets, if any, should the first version expose beyond
   the current resizable window?
2. Should fullscreen apply immediately on toggle, or only after selecting
   Apply?
3. Should the title Options menu eventually include non-display preferences,
   or remain display-only?
