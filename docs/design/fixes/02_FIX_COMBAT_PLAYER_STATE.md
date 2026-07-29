# FIX: Combat `player_state` TypedDict

## Problem

The combat system's `player_state` is a bare `dict` typed with string keys and `Any` values. It's the most fragile internal API in the codebase.

**Current type:**
```python
# In _stats.py init_combat_state:
player_state: dict  # actually dict[str, Any]

# Used as:
player_state["hull"]
player_state["ap_remaining"]
player_state["pos"]
player_state["weapon_ammo"].get(weapon_id, 0)
```

Every access is a potential `KeyError`. A misspelled key (`"ap_remainng"`, `"max_hul"`) is a runtime crash. Adding a new stat means remembering the exact string key everywhere it's read or written.

**Files that read/write player_state:**
- `combat/_stats.py` — `init_combat_state()` creates it
- `combat/_actions.py` — `resolve_damage()`, `can_afford_action()`, `start_player_turn()`, `move_entity()`, `_sync_back_hull()`
- `combat/_ai.py` — enemy AI reads player pos and state
- `combat/_loop.py` — `run_combat()` reads/writes extensively
- `combat/_weapons.py` — firing logic reads player state
- `combat/_animations.py` — animation code reads player pos
- `hud.py` — `render_combat_hud()` reads player_state for display

## Solution: TypedDict

Replace the bare dict with a `TypedDict` (or frozen dataclass). TypedDict is preferred because it allows the same `player_state[key]` access pattern (so the combat loop doesn't need a complete rewrite) while providing type checking on the keys.

**New file:** `combat/_player_state.py` (or add to `combat/_types.py`)

```python
from __future__ import annotations
from typing import TypedDict
from .. import world

class PlayerState(TypedDict, total=False):
    """Combat-relevant player ship state.
    
    total=False so optional fields (regen/skill bonuses) don't
    need to be set everywhere — same flexibility as the old dict,
    but every key is checked at type-checking time.
    """
    hull: int
    max_hull: int
    shields: int
    max_shields: int
    shields_charged: bool
    power_pool: int
    max_power: int
    ap_remaining: int
    ap_total: int
    pos: world.Position
    gunnery: int
    piloting: int
    engineering: int
    power_gen: int
    cells_moved_this_turn: int
    shield_regen_rate: int
    shield_recharge_bonus: int
    weapon_ammo: dict[str, int]
```

## Phased implementation

### Phase 1: Define the TypedDict

- [ ] Add `PlayerState` TypedDict to `combat/_types.py`
- [ ] Update `init_combat_state()` return type: `-> tuple[PlayerState, EnemyInstance]`
- [ ] Update `start_player_turn(player_state: PlayerState)`
- [ ] Update `_sync_back_hull(player_state: PlayerState, ...)`
- [ ] Update `can_afford_action(player_state: PlayerState, ...)`
- [ ] Update `resolve_damage(...)` — this one doesn't take player_state, just reads weapon_id. No change needed.
- [ ] Update `move_entity(...)` — doesn't take player_state. No change needed.
- [ ] Update `render_combat_hud(player_state: PlayerState, ...)`
- [ ] Update `_fire_weapons(player_state: PlayerState, ...)` in `_weapons.py`
- [ ] Update `_run_enemy_turn(...)` in `_ai.py` — takes player_state as dict, change to PlayerState
- [ ] Update `run_combat(...)` in `_loop.py` — the main loop
- [ ] Smoke test

### Phase 2: Catch all consumers

- [ ] Search for `player_state\[` across all combat files — every access key must be a valid TypedDict key
- [ ] Search for `player_state\.get(` — replace with direct key access where safe
- [ ] Smoke test
- [ ] Playtest: run through 3-4 combat encounters

### Phase 3 (stretch): Migrate to frozen dataclass

If TypedDict feels like a band-aid, a frozen dataclass `PlayerState` with a `_replace()` method would be stricter but require more refactoring of the mutation sites (e.g. `player_state["hull"] -= dmg` → `player_state = player_state._replace(hull=player_state.hull - dmg)`).

This is probably overkill for v1. The TypedDict catches the bulk of the bugs (typos, missing keys) with minimal API disruption.

## Risks

- **Circular imports:** `PlayerState` references `world.Position`. `_types.py` already imports `world`. Should be fine, but test.
- **runtime TypeError:** If any code path sets a value that doesn't match the TypedDict type (e.g. setting `ap_remaining` to a string), Python won't catch it at runtime — TypedDict is typing-only. But that's the same risk as the current bare dict, just now the type checker can flag it.
- **total=False ergonomics:** Keys not in the TypedDict will be flagged by type checkers. Some code may set dynamic keys. Audit for this before landing.

## Acceptance criteria

- [ ] All `player_state` references use `PlayerState` type
- [ ] No `player_state["typo"]` can type-check
- [ ] Combat still works (full playtest: 3 encounters, victory + defeat + flee paths)
- [ ] Smoke test passes
