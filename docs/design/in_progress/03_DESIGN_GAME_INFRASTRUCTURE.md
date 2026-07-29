# DESIGN: Game Infrastructure — Modes, Config, Save/Load

## Overview

The nuts-and-bolts layer that makes the game playable across sessions: three game modes with different death consequences, configurable keybindings and resolution, and a save/continue system that works even for roguelike permadeath.

## Game modes

Three modes selected at character creation (before the player picks species/class):

| Mode | Death = | Checkpoints | Target audience |
|------|---------|-------------|----------------|
| **Roguelike** | Full wipe — character, ship, rep, XP all gone. Back to title screen. | None | Core roguelike experience |
| **Adventurer** | Wipe character, but respawn at last-docked planet. Keep faction rep and some progress. | Each planet landing autosaves | Want stakes but less punishing |
| **RPG** | Death is nearly impossible (drastic combat reduction). Save scum-friendly. | Any planet landing; manual save anytime | Want the story and exploration |

### Roguelike mode

**Current behavior (unchanged):**
- `ctx.player_dead = True` → death screen → `_run_game` returns → back to title screen
- Full wipe: character, ship, XP, rep, credits, missions — all gone
- Fresh start every run

**Save/continue even in roguelike:**
- Autosave on planet landing and on quit
- On continue: last save loads, but death still wipes
- This is critical for multi-session play — a roguelike run often takes multiple sittings
- Save file stores the full `GameContext` state

**What persists between runs (account-level):**
- Nothing for now. Future: maybe unlockable ships/classes for completing the main quest?

### Adventurer mode

**Death = partial wipe:**
- Player ship destroyed → cargo lost, active missions failed
- Respawn at the last planet they docked at (the checkpoint)
- Keep: faction rep, XP, player level, credits (minus debt)
- Lose: current cargo, active missions, ship (must buy a new one)
- Starting ship is free (one-time)

**Save frequency:**
- Autosave on every planet landing
- Autosave on quit
- Death loads the most recent checkpoint

**Implementation:**
- On planet landing: save a "checkpoint" snapshot of `ctx` that excludes transient state (cargo in transit, active mission cargo, ship hull damage)
- On death: load checkpoint, set `ctx.player_dead = False`, place player back at the docked planet with a basic starter ship
- Log: "Your ship was destroyed. You wake up in a medbay on {planet_name}, stripped of cargo but alive."

### RPG mode

**Death = nearly impossible:**
- Combat damage reduced to 10% of normal (player takes 10%, deals 200%)
- Enemy AI flees at 50% hull instead of 15%
- If player HP hits 0: "You black out. The next thing you know, you're in a medbay." (same as adventurer respawn)
- Ship can't be destroyed (hull stops at 1 HP)

**Save frequency:**
- Autosave on planet landing
- Autosave on quit
- Manual save from menu (new)

## Config options

### Keybindings

A config file (JSON or TOML) at `~/.spacehack/config.toml`:

```toml
[keys]
move_up = "k"
move_down = "j"
move_left = "h"
move_right = "l"
move_up_left = "y"
move_up_right = "u"
move_down_left = "b"
move_down_right = "n"
open_comms = "t"
open_nav_map = "n"
open_guide = "?"
open_quest_log = "q"
auto_nav = "g"
ship_menu = "i"
fire_weapons = "f"
wait_turn = "w"
cycle_target_right = "Tab"
cycle_target_left = "Left"
shield_regen = "s"
toggle_weapon_1 = "1"
toggle_weapon_2 = "2"
toggle_weapon_3 = "3"
toggle_weapon_4 = "4"
toggle_weapon_5 = "5"
toggle_weapon_6 = "6"
toggle_weapon_7 = "7"
toggle_weapon_8 = "8"
confirm = "Return"
back = "Escape"
open_menu = "Escape"  # in-game pause menu
```

**Implementation:**
- `engine.py` loads `~/.spacehack/config.toml` at startup
- A `KeyBindings` dataclass stores all bindings with sensible defaults
- All key checks in `__main__.py`, `comms.py`, `navigation.py`, `menus/*.py` reference `ctx.keybindings` or a module-level `KEYBINDINGS` constant
- If config file is missing or corrupted, use defaults silently
- In-game keybinding editor? Not for v1 — edit the config file manually

### Config file sections

```toml
[display]
screen_width = 100
screen_height = 50
fullscreen = false
font_size = 16  # future: scale tileset

[gameplay]
mode = "roguelike"           # roguelike | adventurer | rpg
autosave_interval = 0         # 0 = on landing only, N = every N moves
show_tutorial_hints = true
combat_animations = true
message_log_lines = 50

[audio]  # future
music_enabled = false
sfx_enabled = false
music_volume = 50
sfx_volume = 70

[accessibility]
screen_shake = false
flash_effects = true
colorblind_mode = "none"     # none | protanopia | deuteranopia
```

### Display options

| Option | Type | Default | Notes |
|--------|------|---------|-------|
| `screen_width` | int | 100 | Min 80, max 200 |
| `screen_height` | int | 50 | Min 40, max 100 |
| `fullscreen` | bool | false | Toggles SDL fullscreen mode |
| `font_size` | int | 16 | Scales tileset; requires restart |

**Resolution note:** The current `SCREEN_WIDTH`/`SCREEN_HEIGHT` constants in `engine.py` are module-level, not configurable at runtime. For v1, they'd be read from config at startup. True runtime resize is deferred — would require re-laying-out every modal and HUD.

### Keybinding presets

Two built-in profiles selectable from config:

| Profile | Description |
|---------|-------------|
| `vim` | Default — hjkl movement, Tab cycle, f fire |
| `wasd` | WASD movement, E interact, Q cycle, F fire |

The config file just sets `key_profile = "vim"` or `key_profile = "wasd"` — the profile defines the full mapping.

## Save/Continue system

### Save data

Save files stored at `~/.spacehack/saves/`:

```
~/.spacehack/
  config.toml
  saves/
    autosave.json          # autosave (overwritten each time)
    quick_save.json         # manual save (RPG mode only)
    slot_1.json             # future: named save slots
    slot_2.json
    slot_3.json
```

**Save file format:** JSON serialization of `GameContext` state.

### What gets saved

| Field | Save? | Notes |
|-------|-------|-------|
| `character_info` | ✅ | Species, class identity |
| `stats` | ✅ | Credits, HP, XP |
| `player_owned_ship` | ✅ | Ship state, cargo, modules, hull damage |
| `player_active_missions` | ✅ | Mission state, deadlines |
| `completed_mission_ids` | ✅ | Prevent re-offering |
| `mission_boards` | ✅ | Board state, current offerings |
| `bounty_spawns` | ✅ | Active bounty targets |
| `faction_reputation` | ✅ | Standings with all factions |
| `player_xp`, `player_level` | ✅ | XP system state |
| `player_skill_points` | ✅ | Unspent skill points |
| `player_*_bonus` | ✅ | Skill point allocations |
| `time_day/month/year` | ✅ | Game clock |
| `move_counter` | ✅ | Movement counter |
| `main_quest_progress` | ✅ | Quest step states |
| `game_map` | ❌ | Regenerated on load (map state is deterministic from position + system) |
| `player.pos` | ✅ | Current system + position |
| `current_solar_system_id` | ✅ | Which system the player is in |
| `player_dead` | ❌ | Always false on save (can't save while dead) |
| `context` (tcod) | ❌ | SDL state — cannot serialize |

### Load flow

```python
def load_game(save_path: str) -> GameContext:
    \"\"\"Load a save file and reconstruct GameContext.\n\n    1. Deserialize JSON → SaveData dict\n    2. Create tcod.context.Context (new SDL window)\n    3. Build fresh Console\n    4. Reconstruct GameContext from saved fields\n    5. Regenerate game_map from current_solar_system_id + player.pos\n    6. Rebuild HUD state from stats\n    7. Return ctx\n    \"\"\"
```

### Title screen updates

```
╔══════════════════════════════════════╗
║            SPACEHACK                 ║
║        Date: 22000101               ║
║                                      ║
║   > New Game <                       ║
║     Continue                        ║
║     Options                         ║
║     Quit                            ║
╚══════════════════════════════════════╝
```

- **New Game** → species/class selection (existing flow) with mode picker added
- **Continue** → load autosave, drop into game. If no save exists, gray out
- **Options** → keybinding reference screen (read-only for v1 — shows current bindings)
- **Quit** → exit

### Confirmation dialogs

| Action | Prompt | Options |
|--------|--------|---------|
| Quit to menu (in-game) | "Return to title screen? Unsaved progress will be lost." | Continue / Quit to Menu |
| Close game | "Exit Spacehack? Unsaved progress will be lost." | Cancel / Exit |
| Delete save | "Delete this save? This cannot be undone." | Cancel / Delete |
| Abandon mission (Q log) | Already has confirmation? Check current behavior. | |

### In-game pause/menu

New key: `Escape` (or configured menu key) opens:

```
══════════════
   PAUSED
══════════════

> Resume
  Save & Continue (RPG only)
  Options
  Quit to Menu
  Exit Game
```

The pause menu pauses the game loop (no NPC movement, no time advance) while open.

## Implementation phases

### Phase 1: Save/load system

- [ ] Add serialization function: `save_game(ctx, path)` — converts GameContext to JSON
- [ ] Add deserialization function: `load_game(path)` — reconstructs GameContext from JSON
- [ ] Add `~/.spacehack/saves/` directory creation on first run
- [ ] Wire autosave into planet landing (city.py or __main__.py)
- [ ] Wire autosave into quit (graceful shutdown handler)
- [ ] Add "Continue" button to title screen
- [ ] Smoke test + commit

### Phase 2: Game modes

- [ ] Add `GameMode` enum to `game_context.py` or a new `gamemode.py` module
- [ ] Add mode picker to character creation flow (select mode before species)
- [ ] Wire roguelike mode: full wipe on death (existing behavior)
- [ ] Wire adventurer mode: checkpoint save on landing, partial wipe on death
- [ ] Wire RPG mode: 90% damage reduction, 200% player damage, medbay respawn
- [ ] Ensure mode is stored in save file and doesn't change mid-run
- [ ] Smoke test + commit

### Phase 3: Config file

- [ ] Add `load_config()` to `engine.py` — reads `~/.spacehack/config.toml`, falls back to defaults
- [ ] Add `KeyBindings` dataclass with vim and wasd profiles
- [ ] Create default config file on first run
- [ ] Migrate all hardcoded key checks to use keybinding lookups
  - `__main__.py`: movement keys, fire, wait, comms, nav, quest log, ship menu
  - `comms.py`: navigation keys
  - `navigation.py`: auto-nav keys
  - `menus/*.py`: up/down/enter/escape (these are already centralized via `ui._UP_SYMS` etc.)
- [ ] Wire `screen_width` / `screen_height` from config at startup
- [ ] Smoke test + commit

#### DRY eval

- [ ] Are keybinding lookups centralized (e.g. `KEYBINDINGS["move_up"]`) or duplicated inline?
- [ ] Check all 10+ files that reference key checks — any missed?
- [ ] Verify `ui._UP_SYMS` / `ui._DOWN_SYMS` / `ui._ESCAPE_SYMS` / `ui._ENTER_SYMS` are updated to use config

### Phase 4: Title screen + pause menu

- [ ] Add "Continue" option to title screen (grayed if no save exists)
- [ ] Add "Options" screen (read-only keybinding reference for v1)
- [ ] Add in-game pause menu (Escape key)
- [ ] Add confirmation dialogs for quit, exit, delete
- [ ] Wire pause menu to save (RPG mode: manual save)
- [ ] Smoke test + commit

### Phase 5: Guide + final polish

- [ ] Update in-game guide with game modes, save system
- [ ] Full playtest: roguelike run across multiple sessions (save → quit → continue → play → die → fresh start)
- [ ] Full playtest: adventurer death → respawn
- [ ] Full playtest: RPG mode combat (10% damage taken)
- [ ] DRY/RNG audit on all new code

## Open questions

1. **Should save files be human-readable JSON or compact binary?** JSON for v1 — easy to debug, inspect, and manually recover. Binary (pickle/msgpack) for v2 if save-file size becomes an issue.
2. **Should roguelike mode still save game state for "continue" purposes?** Yes — even roguelike players need multi-session play. Death still wipes.
3. **Should config file support per-key remapping or only profiles (vim/wasd)?** v1 = profiles only. v2 = per-key remapping via the config file. In-game keybinding editor is v3.
4. **Should Adventurer mode deduct credits on death (medbay fee)?** Yes — 20% of current credits (min 100, max 5000). Adds consequence without full wipe.
5. **Should RPG mode disable achievements/trophies (if we ever add them)?** Yes — RPG mode is "story mode," separate tracking.
