# Refactor `__main__.py` — Extract into Dedicated Files

**Status**: In progress  
**Current size**: 2,322 lines  
**Target size**: ~700 lines (main loop + event dispatch only)

## Philosophy

Each extraction follows the same pattern established by `comms.py`, `trade.py`, and `combat.py`:

1. Create a new module file in `src/spacehack/`
2. Move the relevant functions, their Outcome enums, and any module-level constants into it
3. Add a `from . import new_module` import in `__main__.py`
4. Replace local function references with `new_module.function_name()`
5. Run `tools/smoke.py` to verify nothing broke
6. Run a quick playtest of the affected screens
7. ✅ Mark done

No classes, no state, no refactoring of the logic itself — purely mechanical extraction.

---

## Phase 1 — Input helpers (`input_helpers.py`) ~150 lines

**What moves** (lines 146–397):

| Symbol | Line | Purpose |
|--------|------|---------|
| `Outcome` enum | 45 | General outcome (CONTINUE, QUIT, PICK_SPECIES, etc.) |
| `_run_pick()` | 146 | Species/class selection menu |
| `_run_confirm()` | 166 | Yes/No confirmation dialog |
| `_vim_action()` | 185 | Map vim keypress → direction delta |
| `_is_q_press()` | 205 | Q key check |
| `_is_m_press()` | 219 | M key check |
| `_is_period_press()` | 243 | `.` (wait) key check |
| `_is_g_press()` | 255 | G key check |
| `_is_c_press()` | 276 | C key check |
| `_is_t_press()` | 297 | T key check |
| `_render_aoi_panel()` | 318 | Area-of-interest overlay in space mode |

**Dependencies**: `ui`, `world`, `engine` (constants), `tcod.console`, `tcod.event`  
**Called from**: `_run_game()` (startup pick + space mode input dispatch)  
**Playtest**: Start game → verify species/class picker works. Press Q, M, ., G, C, T in space mode and verify each triggers its action.

---

## Phase 2 — Planet-side menus (`menus.py`) ~500 lines

**What moves** (lines 1254–1881 + scattered enums):

| Symbol | Line | Purpose |
|--------|------|---------|
| `ShipBuyOutcome` enum | 59 | Ship purchase outcomes |
| `ShipMenuAction` enum | 72 | Ship menu actions |
| `PlanetMenuOutcome` enum | 82 | Planet bump outcomes |
| `MissionOutcome` enum | 1314 | Mission board outcomes |
| `QuestLogOutcome` enum | 1325 | Quest log outcomes |
| `_MechanicOutcome` enum | 1696 | Mechanic terminal outcomes |
| `render_ship_buy()` | 1254 | Ship purchase screen render |
| `update_ship_buy()` | 1285 | Ship purchase input |
| `_run_ship_buy()` | 1298 | Ship purchase flow |
| `_offerings_to_menu()` | 1338 | Convert mission data → menu rows |
| `render_mission_offerings()` | 1350 | Mission board render |
| `update_mission_offerings()` | 1395 | Mission board input |
| `_mission_navigate()` | 1415 | Mission selection helper |
| `_run_mission_offerings()` | 1435 | Mission board flow |
| `render_quest_log()` | 1461 | Quest log render |
| `update_quest_log()` | 1509 | Quest log input |
| `_run_quest_log()` | 1538 | Quest log flow |
| `render_ship_menu()` | 1568 | Ship hangar render |
| `_ship_menu_navigate()` | 1614 | Ship menu selection |
| `update_ship_menu()` | 1640 | Ship menu input |
| `_run_ship_menu()` | 1661 | Ship menu flow |
| `_run_mech_menu()` | 1705 | Mechanic terminal flow |
| `_find_hangar_ship()` | 1804 | Lookup player ship entity in city |
| `render_planet_menu()` | 1819 | Planet bump render |
| `update_planet_menu()` | 1858 | Planet bump input |
| `_run_planet_menu()` | 1881 | Planet bump flow |

**Dependencies**: `ui`, `world`, `engine`, `ship`, `hud`, `mission_module`, `trade` (open_npc_trade, open_trade), `npc_module` (TalkOutcome, _run_npc_talk), `message_log`, `tcod.console`, `tcod.event`, `GameContext`, `solar_system_module`  
**Called from**: `_run_game()` — individual menu invocations  
**Playtest**: Land on Earth → interact with each planet feature (ship, mech, missions, quests, bump planet). Verify all render correctly.

---

## Phase 3 — Navigation & Jump (`navigation.py`) ~350 lines

**What moves** (lines 398–760 + 976–1237):

| Symbol | Line | Purpose |
|--------|------|---------|
| `NavigationOutcome` enum | 398 | Navigation outcomes |
| `render_navigation()` | 410 | GO TO screen render |
| `update_navigation()` | 500 | GO TO screen input |
| `_run_navigation()` | 517 | GO TO flow |
| `_nearest_body_name()` | 534 | Nearest body lookup for HUD |
| `GotoOutcome` enum | 114 | Goto/jump compound outcome |
| `_run_goto()` | 760 | Full space movement flow |
| `JumpMenuOutcome` enum | 95 | Jump outcomes |
| `render_jump_menu()` | 976 | Jump gate render |
| `update_jump_menu()` | 1007 | Jump gate input |
| `_run_jump_menu()` | 1023 | Jump gate flow |
| `_run_cargo_scan()` | 1053 | Cargo scanning interaction |
| `_responsive_sleep()` | 1119 | Animation timing |
| `_animate_jump()` | 1142 | Jump animation |
| `_jump_to_system()` | 1205 | System transition logic |

**Dependencies**: `ui`, `world`, `engine`, `solar_system_module`, `solar_systems_module`, `ship_module`, `hud`, `message_log`, `npc_module`, `npc_ships` (process_spawns), `combat` (_detect_encounter_on_jump from Phase 4), `GameContext`, `tcod.console`, `tcod.event`  
**Called from**: `_run_game()` — goto flow during space mode  
**Playtest**: Launch from Earth → press G → navigate to a jump gate → jump to another system. Verify GO TO screen, jump gate dialog, animation, and arrival all work.

---

## Phase 4 — Bounty combat detection (`bounty.py`) ~100 lines

**What moves** (lines 564–667):

| Symbol | Line | Purpose |
|--------|------|---------|
| `_add_bounty_spawns_to_map()` | 564 | Place bounty targets on system map |
| `_pick_bounty_spawn_pos()` | 605 | Find valid spawn position |
| `_remove_bounty_spawn()` | 632 | Clean up bounty on completion |
| `_detect_combat_encounter()` | 668 | Check if player is near any enemy |

**Dependencies**: `world`, `engine`, `mission_module`, `player_entity module` (Pos, entity), `tcod.console`  
**Called from**: `_run_game()` during space movement + `_jump_to_system()` / launch  
**Playtest**: Accept a bounty mission → jump to target system → verify bounty target spawns. Approach → verify combat triggers.

---

## Phase 5 — City/space transitions (`city.py`) ~100 lines

**What moves** (lines 1912–1987):

| Symbol | Line | Purpose |
|--------|------|---------|
| `_animate_ship_to_y()` | 1912 | Landing/takeoff animation |
| `_launch_to_space()` | 1939 | City → space transition |
| `_return_to_city()` | 1973 | Space → city transition |

**Dependencies**: `world`, `engine`, `npc_module`, `npc_ships` (process_spawns), `GameContext`, `tcod.console`  
**Called from**: `_run_game()` — land/launch dispatch  
**Playtest**: Land on Earth → Launch to space → Land again. Verify animation and state transitions are smooth.

---

## After all phases

`__main__.py` will contain only:

- **Top imports** (~20 lines)
- **_run_game()** — the main event loop + mode dispatch (~700 lines)
- **run()** — top-level orchestration (~20 lines)
- **main()** — entry point (~10 lines)

**Total**: ~750 lines — same ballpark as `combat.py`, well within comfortable range.

---

## Playtest plan

Each phase has its own playtest noted above. A **final runthrough** after all phases:

1. ✅ Start game → pick species/class → verify `_run_pick` works via new module
2. ✅ Launch to Sol → press Q, M, ., G, C, T → verify all input helpers work
3. ✅ Open ship menu, mech terminal, mission board, quest log → verify menus render
4. ✅ Press G → navigate to jump gate → jump → verify navigation + jump flow
5. ✅ Bump into a pirate → verify combat detection still works
6. ✅ Land on a planet → verify city transition
7. ✅ Launch back to space → verify space transition
8. ✅ Tools/smoke.py passes

---

## Status

- [x] Phase 1 — Input helpers (`input_helpers.py`)
- [x] Phase 2 — Planet-side menus (`menus.py`)
- [x] Phase 3 — Navigation & Jump (`navigation.py`)
  - Note: `_add_bounty_spawns_to_map` + `_detect_combat_encounter` moved here
  (Phase 3 needed them; Phase 4 no longer a separate file)
- [ ] Phase 4 — Remaining bounty spawn helpers stay in `__main__`
  (just `_pick_bounty_spawn_pos`, `_remove_bounty_spawn` — small enough to keep)
- [ ] Phase 5 — City/space transitions (`city.py`)
- [ ] Final runthrough + smoke ✅
