# DESIGN: Game Modes & Pause/Save Menu

> **Priority: LOW** — deferred from `03_DESIGN_GAME_INFRASTRUCTURE` and
> intentionally separated from display configuration in
> `99_DESIGN_CONFIG_POLISH.md`.

## Overview

Add explicit game modes with different death and persistence rules, then add
an in-game pause/save menu whose behavior is defined by the selected mode.
This is a gameplay and save-contract change, not a window or input-polish
feature.

The current game is the Roguelike mode: ship destruction ends the run and
returns the player to the title flow. The other modes must preserve that
behavior when they are not selected.

## Scope boundary

This document owns:

- Mode selection during character creation
- Death, checkpoint, and recovery rules
- Mode-specific save behavior and persistence
- The in-game pause/save menu

This document does **not** own:

- Fullscreen or window preferences — see `99_DESIGN_CONFIG_POLISH.md`
- Keybinding profiles or per-key remapping — not planned
- General title-screen display options

## Game modes

Three modes are selected before species/class creation:

| Mode | Death behavior | Checkpoints | Target audience |
|------|----------------|-------------|-----------------|
| **Roguelike** | Full wipe — character, ship, reputation, XP, and run state are gone. | None | Core roguelike experience |
| **Adventurer** | Recover at the last docked planet with a partial wipe. | Each successful planet landing | Players who want stakes with recovery |
| **RPG** | Combat is heavily forgiving; death recovers through the same medbay flow. | Any landing; manual save allowed | Story and exploration focused play |

### Roguelike mode

This preserves the current behavior:

- Ship destruction ends the active run.
- Character progression and run state are not restored.
- The player returns to the title flow.
- Existing saves and Continue behavior remain unchanged.

### Adventurer mode — death behavior

- Ship destroyed → cargo lost and active missions failed.
- Respawn at the last successful planet checkpoint.
- Keep faction reputation, XP, level, and credits after a medbay fee:
  20% of credits, minimum 100 and maximum 5000.
- Lose the active ship and receive a free starter ship.
- Log: `Your ship was destroyed. You wake up in a medbay on {planet_name}.`
- The checkpoint must restore a coherent city state without restoring lost
  cargo, failed missions, or the destroyed ship.

### RPG mode — death behavior

- Player combat damage taken is reduced to 10% of normal.
- Player damage dealt is increased to 200% of normal.
- Enemy AI flees at 50% hull instead of 15%.
- Player ship hull floors at 1 HP instead of reaching destruction.
- Ground HP reaching zero uses the same medbay recovery flow as Adventurer.
- The mode must be visibly identified so its reduced stakes are clear.

## Pause/save menu

ESC during active gameplay opens a modal menu:

```text
════════════════
     PAUSED
════════════════

> Resume
  Save
  Save and quit
  Quit without saving
```

Rules:

- Opening the menu stops all turn processing: no NPC movement, combat turns,
  mission updates, or world-clock advancement occur while it is open.
- `Resume` returns to the exact active mode and map.
- `Save` writes the current run and returns to gameplay.
- `Save and quit` writes the current run and returns to the title screen.
- `Quit without saving` returns to the title screen after confirmation.
- Destructive actions require confirmation.
- The menu must not create a save shape that Continue cannot restore.
- Mode restrictions on saving must be explicit in the mode contract; they must
  not be inferred from the menu presentation.

The existing ESC save/exit behavior should be migrated into this menu rather
than duplicated beside it.

## Implementation phases

### Phase 1: Mode model and selection

- [ ] Add a frozen/string-backed `GameMode` contract with `roguelike`,
      `adventurer`, and `rpg` values.
- [ ] Add mode selection before species/class creation.
- [ ] Preserve Roguelike as the default/current behavior.
- [ ] Add mode-aware help text and confirmation copy.

### Phase 2: Death and checkpoint recovery

- [ ] Wire Adventurer checkpoints on successful planet landing.
- [ ] Implement Adventurer recovery: fee, cargo loss, mission failure, ship
      replacement, and city-state restoration.
- [ ] Wire RPG combat modifiers and medbay recovery.
- [ ] Ensure all mode-specific state is reset correctly on New Game.

### Phase 3: Pause/save menu

- [ ] Add the ESC pause menu with Resume, Save, Save and quit, and Quit
      without saving.
- [ ] Replace the current direct ESC save/exit path.
- [ ] Add confirmations for quit-without-saving and other destructive actions.
- [ ] Verify title Continue restores the selected mode and active checkpoint.

### Phase 4: Guide, contracts, and playtest

- [ ] Update the guide with mode rules and pause/save behavior.
- [ ] Add pure tests for mode rules and checkpoint transformations.
- [ ] Full playtest: start each mode, save/continue, die in space, die on
      ground, and verify the documented recovery behavior.
- [ ] Run `make check`.

## Contracts compliance (MANDATORY — see knowledge.md)

- [ ] **Save/load:** mode, checkpoint, death-recovery state, and any pause-menu
      relevant state must be added to both `_ctx_to_dict()` and `load_game()`.
- [ ] **Game guide:** mode selection, death rules, save restrictions, and pause
      menu actions must be documented in the player guide.
- [ ] **Pure functions:** mode modifiers and checkpoint transformations receive
      explicit inputs and ship focused tests.
- [ ] **Module-level state:** no mutable mode or checkpoint state may live in
      module globals.
- [ ] **Architecture ratchet:** recovery and menu logic should live in focused
      modules rather than expanding the main gameplay loop or save/load module
      past the project limits.

## Open questions

1. Should Adventurer checkpoints include the exact city map state, or rebuild
   the city from the planet catalog while preserving only player-facing state?
2. Should RPG mode allow manual saves at every location, or only at safe modal
   boundaries and landings?
3. Should mode selection be permanent for a run, or can a player switch modes
   after a warning and an achievement/score reset?
4. Should Roguelike `Save` remain available, or should it only expose `Save and
   quit` to preserve the intended risk model?
5. Should achievements or leaderboards distinguish RPG and Adventurer runs from
   Roguelike runs?
