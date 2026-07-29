# DESIGN: Save/Load & Title Menu

## Overview

A title menu that replaces the current splash screen (New Game / Continue / Exit) and a JSON save/load system so players can continue runs across sessions.

**Scope note:** Config file, game modes, keybinding remapping, and pause menu were deferred to `99_DESIGN_CONFIG_POLISH.md`. This doc covers only the menu + save/load.

## Philosophy alignment

| Principle | How it applies |
|-----------|---------------|
| **ctx-first** | Save serializes `GameContext` fields; load reconstructs it |
| **Data-first** | Save-data shape is a structured dict, not ad-hoc field lists |
| **Simple > clever** | JSON — human-readable, inspectable, recoverable |
| **Live-by-side-effect** | `save_game(ctx)` writes to disk, `load_game()` returns fresh ctx |

## Data model

### Save file format

`~/.spacehack/saves/autosave.json` — single file, overwritten each save.

### What gets saved

| Field | Format | Notes |
|-------|--------|-------|
| `character_info` | `{species_id, species_name, class_id, class_name}` | String keys |
| `stats` | `{hp, max_hp, credits, gunnery, piloting, engineering}` | HudStats as dict |
| `player_owned_ship` | `OwnedShip` as dict | Ship state, cargo, modules, hull |
| `player_active_missions` | `list[dict]` | ActiveMission as dicts |
| `completed_mission_ids` | `list[str]` | Set → list for JSON |
| `mission_boards` | `dict[str, dict]` | Per-NPC board state |
| `bounty_spawns` | `dict[str, list[dict]]` | Active bounty targets |
| `faction_reputation` | `dict[str, int]` | Standings |
| `player_xp` / `player_level` / `player_skill_points` | `int` | XP system |
| `player_*_bonus` | `int` | Skill allocations |
| `player_traits` | `list[str]` | Chosen trait IDs |
| `player_counters` | `dict[str, int]` | PlayerCounters as dict |
| `time_day/month/year` | `int` | Game clock |
| `move_counter` | `int` | Movement counter |
| `current_system_id` | `str` | Which system (for map regen) |
| `current_mode` | `str` | "city" or "space" |
| `current_city_id` | `str` | Planet ID if in city |
| `player_pos` | `{x, y}` | Player's position |
| `game_map` | ❌ | Regenerated on load |
| `player_dead` | ❌ | Can't save while dead |

### Serialization helpers

```python
def _ctx_to_dict(ctx: GameContext) -> dict: ...
def _dict_to_ctx(data: dict, context: tcod.context.Context) -> GameContext: ...
```

## Title menu

Replaces `ui.render_title_splash()` — after the splash art, show a menu:

```
╔══════════════════════════════════════╗
║            SPACEHACK                 ║
║    [ship art + starfield as now]     ║
║                                      ║
║   > New Game                        ║
║     Continue                        ║
║     Exit                            ║
║                                      ║
║  ↑↓ navigate  ENTER select          ║
╚══════════════════════════════════════╝
```

- **New Game** → species/class selection (existing flow)
- **Continue** → load autosave, drop into game. Grayed out if no save exists.
- **Exit** → clean shutdown

## Implementation phases

### Phase 1: Save/load engine

**Pre-implementation audit:**

**Existing modules to extend/reuse:**
- `game_context.py` — `GameContext` dataclass is the save source-of-truth
- `mission.py` — `ActiveMission` + `MissionBoard` need dict round-trips
- `ship.py` — `OwnedShip` needs dict round-trip
- `engine.py` — `make_console`, `open_terminal` already exist for load flow
- `__main__.py` — `run()` orchestrates the game flow; load slots in here

**Three duplication hotspots:**
1. **Dataclass → dict conversion scattered per type.** Fix: single `_dataclass_to_dict(obj)` helper using `dataclasses.fields()`, with type-specific overrides for `OwnedShip` (inventory is a `dict[str, int]`), `ActiveMission` (has `time_deadline` tuple), etc.
2. **Dict → dataclass reconstruction.** Fix: `_dict_to_dataclass(data, cls)` helper.
3. **Path resolution for `~/.spacehack/saves/`.** Fix: single `_saves_dir()` function in `engine.py`.

**Checklist:**
- [ ] Add `save_game(ctx, path)` + `_ctx_to_dict(ctx)` in new `saveload.py`
- [ ] Add `load_game(path, context)` + `_dict_to_ctx(data, context)` in `saveload.py`
- [ ] Add `_saves_dir()` helper — creates `~/.spacehack/saves/` on first call
- [ ] Wire autosave on planet landing (`city.py` `_launch_to_space` / `_return_to_city`)
- [ ] Wire autosave on graceful quit (before `sys.exit`)
- [ ] Smoke test + commit

**Playtest checklist:**
- [ ] Start new game → land on Earth → quit → start again → Continue → loads at Earth
- [ ] Accept a mission → save → quit → continue → mission still active
- [ ] Spend skill points → save → quit → continue → skills still applied
- [ ] No save exists → Continue grayed out on title menu

### Phase 2: Title menu

**Pre-implementation audit:**

**Existing modules to extend/reuse:**
- `ui.py` — `render_title_splash()` already paints the splash art; extend to show menu
- `ui.py` — `render_selectable_list()` for the menu options
- `__main__.py` — `run()` currently calls `ui.render_title_splash()` then jumps to species picker; insert menu loop before species picker

**Three duplication hotspots:**
1. **Menu rendering duplicated from species/class screens.** Fix: reuse `render_selectable_list()` with custom items — same pattern.
2. **Input handling.** Fix: reuse `update_menu()` / `Modal` pattern from existing menus.
3. **Save-existence check.** Fix: single `_save_exists()` boolean in `saveload.py`.

**Checklist:**
- [ ] Replace direct `render_title_splash()` call with title menu loop in `run()`
- [ ] New Game → species picker (existing flow)
- [ ] Continue → `load_game()` → `_run_game(ctx)` with loaded ctx
- [ ] Exit → clean `sys.exit(0)`
- [ ] Continue grayed out / disabled when no save file exists
- [ ] Menu uses ↑↓ navigation + ENTER (same as species/class)
- [ ] Smoke test + commit

**Playtest checklist:**
- [ ] Title menu shows after splash art
- [ ] ↑↓ navigates between New Game / Continue / Exit
- [ ] New Game → species selection works
- [ ] Continue with no save → grayed out, can't select
- [ ] Continue with save → loads game correctly
- [ ] Exit → clean shutdown

### Phase 3: Final polish

**Checklist:**
- [ ] Full DRY audit on `saveload.py` + title menu
- [ ] Save on quit confirmation (if we add ESC → quit flow)
- [ ] Smoke test + commit

**Playtest checklist:**
- [ ] Complete playthrough: new game → play → save → quit → continue → play more → die → back to title → new game
- [ ] Verify all saved fields round-trip correctly
