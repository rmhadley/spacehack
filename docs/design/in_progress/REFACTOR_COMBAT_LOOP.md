# Combat Loop Analysis and Refactoring Plan

## Overview

This document captures the structural analysis of `src/spacehack/combat/_loop.py` — the main combat turn loop (`run_combat`). It identifies bugs, optimization opportunities, and a phased plan to refactor the loop into smaller, testable pieces.

### History

- **Before this session**: `run_combat` lived in the monolithic `combat.py` (1,951 lines).
- **Monolithic → Package split**: `combat.py` was split into a `combat/` package with 6 sub-modules. `run_combat` now lives in `combat/_loop.py`.
- **Initial analysis (this doc)**: Deep read found 3 bugs, several optimizations, and structural issues.
- **Bug-hunt session**: 7 additional bugs were found and fixed during playtesting. The 3 original design-doc bugs remain open.

### Current file size

`_loop.py` — **~940 lines** (down from 1,031 due to extracting `_spawn_loot_drops` and `_remove_dead_entity` helpers).

---

## Bugs Fixed During Bug Hunt

These were discovered during playtesting after the initial analysis and have already been committed.

| Bug | Symptom | Fix | Commit |
|-----|---------|-----|--------|
| Loot entity constructor crash | `TypeError: Entity.__init__() got unexpected keyword argument 'x'` | Changed `x=_lx, y=_ly` to `pos=world.Position(_lx, _ly)`, removed nonexistent `blocks_movement` field | `ca85894` |
| Loot menu not opening | Bumping `%` did nothing | Changed `loot_data={_loot_id: qty}` to `loot_data={"good_id": _loot_id, "quantity": qty}` to match `trade.py` expected format | `ca85894` |
| Weapon toggle keys 1–9 broken | Pressing number keys didn't toggle weapons | `tcod.KeySym.N1.name` returns `"N1"` (lowered `"n1"`), not `"1"` — fixed dict keys to `"n1"`–`"n9"` | `ca85894` |
| Dead enemies not removed from map | Combat immediately re-triggered on same dead enemies | Victory cleanup used `getattr(_e, 'spec_id', None)` but `world.Entity` has `npc_ship_id`, not `spec_id` — always returned `None` so cleanup was a no-op | `c0c1f41` |
| Dead enemy glyph lingers on screen | After death, enemy character stayed visible until combat ended | Added `_remove_dead_entity` helper that pops the entity from `_enemy_ents` and removes it from `game_map.entities` at death time (both fire paths) | `4edda76` |
| Starter ship ignores ship data | Starter ship got hardcoded `('light_laser',)` and `()` instead of `starter_ship.start_weapons` / `start_modules` | Changed `__main__.py` to pass `starter_ship.start_weapons` and `starter_ship.start_modules` | `5d836df` |

---

## Bugs (Still Open)

### B1 — Burst fire total power never validated

**File**: `_loop.py`, burst fire (`f` key) handler

**Problem**: The pre-flight check computes `_total_power` but never checks it against `player_state["power_pool"]`. Each weapon's cost is checked individually via `_check_fire_ready`, but the **sum** of costs is not. Example: 10 power, two 6-power weapons → each passes individually, but after first fires (6 deducted from 10), the second deducts 6 from 4, sinking power below zero.

```python
_total_power += _fws.power_cost   # computed but NEVER USED
```

**Fix**: Add `if player_state["power_pool"] < _total_power:` check after the per-weapon sum loop, before firing. Also remove the dead `_total_power` accumulation (or use it now that the check exists).

### B2 — Loot drop uses wrong enemy spec

**File**: `_spawn_loot_drops()` helper in `_loop.py` and both fire path call sites

**Problem**: The helper always reads from `enemy_specs[0]` to determine cargo:
```python
_spec_loot = getattr(enemy_specs[0], 'cargo_goods', None) or ()
```
If multiple enemy types exist and enemy #2 (index 1) is killed, it still drops loot from enemy #0's cargo table. Currently harmless because all encounters use uniform enemy types, but this will bite when mixed squads are introduced.

**Fix**: Match the dead enemy's `spec_id` against `enemy_specs` to find the correct spec, and pass either the correct spec or its `cargo_goods` to `_spawn_loot_drops`.

### B3 — Enemy AI moves away from player when aligned on an axis

**File**: `_loop.py`, enemy AI movement section

**Problem**:
```python
_dx = 1 if _ei.pos.x < player_state["pos"].x else -1
_dy = 1 if _ei.pos.y < player_state["pos"].y else -1
```
When `_ei.pos.x == player_state["pos"].x` (enemy and player have the same X coordinate), `_dx` becomes `-1`, moving the enemy **away** from the player on that axis instead of staying put. Same for Y.

**Fix**:
```python
_dx = 0 if _ei.pos.x == player_state["pos"].x else (1 if _ei.pos.x < player_state["pos"].x else -1)
_dy = 0 if _ei.pos.y == player_state["pos"].y else (1 if _ei.pos.y < player_state["pos"].y else -1)
```

---

## Performance / Code Quality Issues

### Q1 — Dead code: `_total_power` in burst fire pre-check

**File**: `_loop.py`, burst fire handler

`_total_power` is accumulated but never referenced after the loop. It's either dead code or an unfinished feature. Remove it (fixing B1 properly handles power validation).

### Q2 — `calc_flee_chance` called 6× per frame

**File**: `_loop.py`, multiple call sites

The same 5-argument formula `calc_flee_chance(piloting, enemy_piloting, hull_pct, distance, flee_attempts)` is computed in:
1. Main render block (HUD)
2. Enemy AI movement render
3. Enemy fire block (in `_animate_laser_shot` arg)
4. Single-fire block (in `_animate_laser_shot` arg)
5. Burst-fire block (in `_animate_laser_shot` arg, per-weapon)
6. ESC flee handler

Only `flee_attempts` changes mid-turn (on failed flee). Cache the result per turn iteration and reuse it.

### Q3 — `_alive_enemies` filtered every loop iteration

```python
_alive_enemies = [e for e in enemy_insts if e.alive]
```
This list is rebuilt from scratch every tick but only changes when an enemy dies (rare). Maintain it incrementally: filter once per turn, then `.remove()` from the cached list on death.

### Q4 — Redundant render before auto-end-turn guard

The render block runs at the top of `while True`, *before* the guard that checks `ap_remaining <= 0 or combat_mode == "WAIT"`. When AP hits 0, the flow is: **render → guard catches AP=0 → enemy turn → continue → render again**. That's one unnecessary full render per player turn. Minor (one frame flash), but noticeable.

**Fix**: Move the guard check before the render block, or restructure to: `while not _result: [guard → render → input → enemy_turn]`.

### Q5 — Single-fire always uses first active weapon

`space`/`enter` selects the first active weapon via a linear scan of `active_weapons`. There is no key binding to fire a specific weapon in single-fire mode. The only way to fire non-first weapons is burst fire (`f`). Consider allowing number keys to select which weapon single-fire uses, or add a weapon-selection mode.

---

## Phased Implementation Plan

### Phase 1 — Fix bugs (no structural changes) ✅ DONE

- [x] **B1**: Add total-power validation to burst fire pre-check. Check `player_state["power_pool"] >= _total_power` after summing — fail-fast with a log message if insufficient.
- [x] **B2**: Thread the correct `enemy_spec` (matched by `spec_id` from the killed enemy) into `_spawn_loot_drops`. Call site now does `next(...)` matching and passes the correct spec.
- [x] **B3**: Fix enemy AI movement direction when player and enemy share an axis (`_dx` / `_dy` zero-check).
- [x] **Q1**: `_total_power` is now used by the B1 power check — no longer dead code.
- [x] **Space/enter removed**: Single-fire fire path removed per player feedback. Toggle weapons with 1-9, fire with `f`.

**Smoke test**: ✅ PASS
**Commit**: `4edda76` (entity removal helper) + Phase 1 commit (B1/B2/B3/space-enter removal)

### Phase 2 — Extract enemy AI into `_ai.py` ✅ DONE

- [x] Move the enemy-turn section (the `for _ei in enemy_insts` loop with its movement + fire logic) into a new `combat/_ai.py` module.
- [x] New function: `_run_enemy_turn(...)` — 17 positional params, returns `"DEFEAT"` or `None`.
- [x] Keeps all enemy AI logic in one place, testable independently.
- [x] Removed dead imports from `_loop.py`: `start_enemy_turn`, `_render_anim_frame`, `_responsive_sleep`.
- [x] `_loop.py` is now ~680 lines (was ~940).

**Smoke test**: ✅ PASS
**Commit**: `7c08550`
**Note**: The 17-param function signature is a consequence of pure extraction. Phase 3 (weapons) is a natural point to consider a shared `CombatState` namespace to reduce parameter explosion.

### Phase 3 — Extract weapon fire into `_weapons.py` ✅ DONE

- [x] Move fire logic (the `f` handler) into a new `combat/_weapons.py` module.
- [x] New function: `_fire_weapons(...)` — 19 positional params, mutates state in place, returns `None`.
- [x] Moved `_check_fire_ready` alongside the fire logic (was a module-level function in `_loop.py`).
- [x] Single-fire (space/enter) was removed in Phase 1, so only burst-fire (`f`) was extracted.
- [x] Removing dead imports from `_loop.py`: `resolve_damage`, `can_afford_action`, `calc_hit_chance`, `find_weapon`, `_animate_laser_shot`, `_animate_explosion`.
- [x] `_loop.py` is now ~540 lines (was ~680).

**Smoke test**: ✅ PASS
**Commit**: `e703c97`

### Phase 4 — Optimizations

- [ ] **Q2**: Cache `calc_flee_chance` result per turn iteration. Recalculate only when `flee_attempts` changes.
- [ ] **Q3**: Maintain `_alive_enemies` incrementally instead of filtering every tick.
- [ ] **Q4**: Move the auto-end-turn guard before the render block.

**Smoke test**: Verify no regressions.

---

## Acceptance criteria

1. All weapons fire correctly with proper cost deduction (AP, power, ammo).
2. Loot drops from the correct enemy's cargo table.
3. Enemy AI moves toward the player correctly, even when aligned on an axis.
4. `calc_flee_chance` is computed once per turn, not 6×.
5. `_loop.py` is well under 500 lines after extractions.
6. Smoke test passes after each phase.

---

## Resolved decisions

| Question | Decision | Rationale |
|----------|----------|-----------|
| B1 — Fail-fast or partial burst? | **Fail-fast**: check total power before firing, cancel whole burst if insufficient | Simplest. The player can toggle weapons off (1–9) to match their power budget. |
| B2 — Internal loot spec matching or caller passes? | **Caller passes correct spec**: each fire site does the spec_id match and passes the single spec | Explicit, no hidden magic. `_spawn_loot_drops` takes a single spec rather than the full list. |
| Q5 — Weapon selection for single-fire? | **Removed**: space/enter single-fire was never in scope | Fire a single weapon by toggling it on and pressing `f` (burst). Simplifies the loop considerably. |

## Still open

- None. All open questions have been resolved above.
