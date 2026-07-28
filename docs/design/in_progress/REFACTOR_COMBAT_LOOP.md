# Combat Loop Analysis and Refactoring Plan

## Overview

This document captures the structural analysis of `src/spacehack/combat/_loop.py` (998 lines) — the main combat turn loop (`run_combat`). It identifies bugs, optimization opportunities, and a phased plan to refactor the loop into smaller, testable pieces.

### History

- **Before this session**: `run_combat` lived in the monolithic `combat.py` (1,951 lines).
- **Earlier this session**: `combat.py` was split into a `combat/` package with 6 sub-modules. `run_combat` now lives in `combat/_loop.py`.
- **Now**: A deep read found 3 bugs, several optimizations, and structural issues.

---

## Bugs

### B1 — Burst fire total power never validated

**File**: `_loop.py`, burst fire (`f` key) handler

**Problem**: The pre-flight check computes `_total_power` but never checks it against `player_state["power_pool"]`. Each weapon's cost is checked individually via `_check_fire_ready`, but the **sum** of costs is not. Example: 10 power, two 6-power weapons → each passes individually, but after first fires (6 deducted from 10), the second deducts 6 from 4, sinking power below zero.

```python
# Lines ~765-775 (approximate)
_total_power += _fws.power_cost   # computed but NEVER USED
```

**Fix**: ``_check_fire_ready`` currently does per-weapon validation. Add a pre-computed total power check for burst fire after the per-weapon loop, or fold it into `_check_fire_ready` with a ``cumulative`` mode.

### B2 — Loot drop uses wrong enemy spec

**File**: `_spawn_loot_drops()` helper in `_loop.py` and both fire path call sites

**Problem**: The helper always reads from `enemy_specs[0]` to determine cargo:
```python
_spec_loot = getattr(enemy_specs[0], 'cargo_goods', None) or ()
```
If multiple enemy types exist and enemy #2 (index 1) is killed, it still drops loot from enemy #0's cargo table. This is a pre-existing bug that went unnoticed because all encounters currently use uniform enemy types.

**Fix**: Pass the specific enemy spec or its `cargo_goods` to `_spawn_loot_drops`. Each call site has access to the target enemy — look up which `enemy_spec` corresponds to the killed enemy by matching `spec_id` against the dead enemy's `spec_id`.

### B3 — Enemy AI moves away from player when aligned on an axis

**File**: `_loop.py`, enemy AI movement section

**Problem**:
```python
_dx = 1 if _ei.pos.x < player_state["pos"].x else -1
_dy = 1 if _ei.pos.y < player_state["pos"].y else -1
```
When `_ei.pos.x == player_state["pos"].x` (enemy and player have the same X coordinate), `_dx` becomes `-1`, moving the enemy **away** from the player on that axis instead of staying put. Same for Y.

**Fix**: Add an equality guard:
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

### Q6 — Movement failure falls through to other handlers

When `move_entity` returns `ok=False` (wall collision), the `break` is skipped but the handler *still breaks* because the `if sym_name in _vim_keys` block always executes `break` whether or not the move succeeded. Actually, looking at the code: `break` is after the `if ok:` block but outside of it, so it ALWAYS breaks after a movement key press, even if the move failed. So Q6 is a non-issue — the break is unconditional.

---

## Phased Implementation Plan

### Phase 1 — Fix bugs (no structural changes)

- [ ] **B1**: Add total-power validation to burst fire pre-check. Either check `player_state["power_pool"] >= _total_power` after summing, or make `_check_fire_ready` support a cumulative mode.
- [ ] **B2**: Thread the correct `enemy_spec` (matched by `spec_id` from the killed enemy) into `_spawn_loot_drops`.
- [ ] **B3**: Fix enemy AI movement direction when player and enemy share an axis.
- [ ] **Q1**: Remove the dead `_total_power` accumulation (or use it now that B1 is fixed).

**Smoke test**: Verify game still runs and combat imports correctly.

### Phase 2 — Extract enemy AI into `_ai.py`

- [ ] Move the enemy-turn section (the `for _ei in enemy_insts` loop with its movement + fire logic) into a new `combat/_ai.py` module.
- [ ] New function: `_run_enemy_turn(ctx, player_state, enemy_insts, enemy_specs, ...)` — takes the current game state and mutates enemies.
- [ ] Keeps all enemy AI logic in one place, testable independently.

**Smoke test**: Verify combat works identically.

### Phase 3 — Extract weapon fire into `_weapons.py`

- [ ] Move single-fire and burst-fire into a new `combat/_weapons.py` module.
- [ ] New function: `_fire_single(player_state, target, weapon_id, ...)` → mutates player state, animates, returns hit result.
- [ ] New function: `_fire_burst(player_state, target, weapon_list, ...)` → calls `_fire_single` per weapon, validates cumulative costs.
- [ ] Also used by enemy AI fire path from `_ai.py`.

**Smoke test**: Verify all fire modes work identically.

### Phase 4 — Optimizations

- [ ] **Q2**: Cache `calc_flee_chance` result per turn iteration.
- [ ] **Q3**: Maintain `_alive_enemies` incrementally instead of filtering every tick.
- [ ] **Q4**: Move the auto-end-turn guard before the render block.

**Smoke test**: Verify no regressions.

---

## Acceptance criteria

1. All weapons fire correctly with proper cost deduction (AP, power, ammo).
2. Loot drops from the correct enemy's cargo table.
3. Enemy AI moves toward the player correctly, even when aligned on an axis.
4. `calc_flee_chance` is computed once per turn, not 6×.
5. `_loop.py` is under 500 lines after extractions.
6. Smoke test passes after each phase.

---

## Open questions

1. **B1 power validation**: Should burst fire check total power before firing (fail-fast), or should it fire as many weapons as it can afford (partial burst)? Current design implies fail-fast.
2. **B2 loot spec**: The `_spawn_loot_drops` call sites have access to `enemy_specs` (the full list). Should the function take the entire list and do the matching internally, or should the caller pass the correct single spec? Internal matching is more robust.
3. **Q5 weapon selection**: Should single-fire (`space`) fire the selected weapon, or should we add a new key to "select next active weapon" for single-fire mode? This is a UX design question, not a bug fix.
4. **Q2 flee caching**: The flee chance depends on `flee_attempts` which only increments on failed flee. Should the cache be invalidated on flee attempts only, or recalculated every frame? Recalculation is negligible cost vs. the 6-call duplication.
