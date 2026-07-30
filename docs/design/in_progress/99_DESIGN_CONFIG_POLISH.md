# DESIGN: Game Config & Polish — Keybindings, Modes, Display

> **Priority: LOW** — deferred from 03_DESIGN_GAME_INFRASTRUCTURE.
> Only the menu screen + save/load were kept in 03; everything else
> moved here for a future polish pass.

## Overview

Configurable keybindings, display resolution, game modes (Roguelike / Adventurer / RPG), and in-game pause menu. Builds on top of the save/load system implemented in 03.

## Game modes

Three modes selected at character creation:

| Mode | Death = | Checkpoints | Target audience |
|------|---------|-------------|----------------|
| **Roguelike** | Full wipe — character, ship, rep, XP all gone. | None | Core roguelike experience |
| **Adventurer** | Respawn at last-docked planet. Keep faction rep, XP, level. | Each planet landing | Want stakes but less punishing |
| **RPG** | Death is nearly impossible (drastic combat reduction). Save scum-friendly. | Any landing; manual save | Want story and exploration |

### Adventurer mode — death behavior

- Ship destroyed → cargo lost, active missions failed
- Respawn at last-docked planet checkpoint
- Keep: faction rep, XP, level, credits (minus medbay fee: 20%, min 100, max 5000)
- Lose: cargo, active missions, ship (get free starter ship)
- Log: "Your ship was destroyed. You wake up in a medbay on {planet_name}."

### RPG mode — death behavior

- Combat damage reduced to 10% normal (player takes 10%, deals 200%)
- Enemy AI flees at 50% hull instead of 15%
- Ship can't be destroyed (hull floors at 1 HP)
- If HP hits 0: same medbay respawn as Adventurer

## Config file

### Location

`~/.spacehack/config.toml` — created with defaults on first run. Falls back to defaults if missing/corrupted.

### Keybindings

```toml
[keys]
key_profile = "vim"   # vim | wasd
```

Two built-in profiles:

| Profile | Movement | Interact | Cycle | Fire |
|---------|----------|----------|-------|------|
| `vim` | hjkl | various | Tab | f |
| `wasd` | wasd | E | Q | F |

**Implementation:** `KeyBindings` dataclass on `GameContext`. All key checks reference `ctx.keybindings.move_up` etc. Per-key remapping (v2), in-game editor (v3).

### Display options

```toml
[display]
screen_width = 100    # min 80, max 200
screen_height = 60    # min 40, max 100
fullscreen = false
```

Read from config at startup. Runtime resize deferred.

## In-game pause menu

ESC key opens:

```
══════════════
   PAUSED
══════════════

> Resume
  Save (manual)
  Quit to Menu
```

Pauses game loop (no NPC movement, no time advance).

## Implementation phases

### Phase 1: Game modes
- [ ] Add `GameMode` enum to `game_context.py`
- [ ] Mode picker before species/class
- [ ] Wire roguelike (existing behavior)
- [ ] Wire Adventurer checkpoint + partial wipe
- [ ] Wire RPG damage reduction + medbay

### Phase 2: Config file
- [ ] `load_config()` in `engine.py` — TOML → Config dataclass
- [ ] `KeyBindings` dataclass with vim/wasd profiles
- [ ] Migrate all hardcoded key checks to `ctx.keybindings`
- [ ] Wire display options at startup

### Phase 3: Pause menu + title polish
- [ ] ESC pause menu with Resume/Save/Quit to Menu
- [ ] Title screen: add Options (keybinding reference, read-only for v1)
- [ ] Confirmation dialogs for quit/exit/delete

### Phase 4: Guide + playtest
- [ ] Update guide with game modes, config, keybinding reference
- [ ] Full playtest: all three modes across sessions

## Contracts compliance (MANDATORY — see knowledge.md)

- [ ] **Save/load:** New GameContext fields (GameMode, KeyBindings, PauseMode) → added to both `_ctx_to_dict()` AND `load_game()`
- [ ] **Game guide:** New keybindings/config → updated `_GUIDE_CONTROLS`, new modes → new guide section
- [ ] **Module-level state:** Config loaded at startup — ensure reset on New Game if per-run mutable

## Open questions

1. Should save files be JSON or binary? JSON for v1.
2. Per-key remapping or profiles only? v1 = profiles. v2 = per-key.
3. Medbay fee on Adventurer death? 20% of credits (min 100, max 5000).
4. RPG mode disable achievements? Yes — separate tracking.
5. Runtime resize? Deferred — would require re-laying-out every modal + HUD.
