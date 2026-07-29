# FIX: Quick Wins — Small Cleanups, High ROI

## Overview

Small, safe refactors that improve extensibility and code quality without changing gameplay. Each should take less than a session. Do these before the P0 feature work to reduce friction.

---

## Quick Win 1: Normalize all data catalogs to auto-discovery

**Estimate: 30 minutes**

**Problem:** Adding a new catalog entry is inconsistent across data domains:
- `data/planets/` — auto-discovers via `pkgutil.iter_modules`. Drop a new `.py` with `SPEC` and it's registered. No registry file to touch. ✅
- `data/weapons/` — manual import list in `_build_registry()` ❌
- `data/modules/` — manual import list ❌
- `data/missions/` — manual import list ❌

**Solution:** Replace `_build_registry()` in each catalog with `pkgutil.iter_modules` auto-discovery, matching the pattern in `data/planets/__init__.py`.

**Pattern to follow:**
```python
# data/planets/__init__.py (reference implementation)
def _build_registry() -> dict[str, PlanetSpec]:
    import importlib, pkgutil
    spec_map: dict[str, PlanetSpec] = {}
    for _finder, name, _ispkg in pkgutil.iter_modules(__path__):
        if name.startswith("_"):
            continue
        mod = importlib.import_module(f"{__name__}.{name}")
        if hasattr(mod, "SPEC"):
            spec_map[mod.SPEC.id] = mod.SPEC
    return spec_map
```

**Files to touch:**
- `src/spacehack/data/weapons/__init__.py`
- `src/spacehack/data/modules/__init__.py`
- `src/spacehack/data/missions/__init__.py`

**Check:**
- [ ] `data/weapons/` auto-discovers `lasers.py`, `missiles.py`
- [ ] `data/modules/` auto-discovers `engines.py`, `systems.py`
- [ ] `data/missions/` auto-discovers all faction mission files
- [ ] `find_*()` and `list_*()` still resolve correctly

---

## Quick Win 2: Extract dev-mode from `__main__.py`

**Estimate: 20 minutes**

**Problem:** The `SPACEHACK_DEV` dev-mode override is inline in `_run_game()` — a ~40-line block inside the main game loop that overrides the player's ship and credits when `os.environ.get('SPACEHACK_DEV')` is set. This adds noise to the main loop and makes dev-mode harder to extend (e.g. adding a debug overlay or god-mode toggle later).

**Solution:** Extract to `src/spacehack/dev_mode.py` with a single `apply_dev_overrides(ctx)` function called from `_run_game()`.

```python
# dev_mode.py
def apply_dev_overrides(ctx: GameContext) -> None:
    """If SPACEHACK_DEV is set, grant super-powered ship + credits."""
    import os
    if not os.environ.get('SPACEHACK_DEV'):
        return
    
    from .data.ships import find_ship
    frigate = find_ship("frigate")
    # ... (the existing inline block, moved here)
```

**Files to touch:**
- New: `src/spacehack/dev_mode.py`
- Edit: `src/spacehack/__main__.py` — replace the inline block with `apply_dev_overrides(ctx)`

**Check:**
- [ ] `SPACEHACK_DEV=1 python -m spacehack` still gives super-powered frigate
- [ ] Without env var, game starts normally
- [ ] Smoke test passes

---

## Quick Win 3: Replace `faction_reputation` hardcoded default with a function call

**Estimate: 15 minutes**

**Problem:** The hardcoded `default_factory` lambda in `GameContext`:
```python
faction_reputation: dict[str, int] = field(
    default_factory=lambda: {"pirate": -100, "merchant": 0, "civilian": 0, "militia": 50}
)
```
This needs to be dynamic (species/class-gated) for the Faction Rep system (Doc 01). Currently there's already a `faction.starting_reputation()` function designed for this purpose — it's just not wired up yet.

**Solution:** This is actually Phase 1 of `01_DESIGN_FACTION_REPUTATION.md`. Do it there. But slot it as a quick win because:
- It's a 15-minute change
- It unblocks 5 other feature docs
- It replaces inline data with a proper function

**Files to touch:**
- `src/spacehack/game_context.py` — remove the lambda, set to `None`, init in `__main__.py` at character creation
- New or existing: `src/spacehack/faction.py` — ensure `starting_reputation()` exists

---

## Quick Win 4: Add type annotations where `Any` is used unnecessarily

**Estimate: 30 minutes**

**Problem:** The combat stat functions use `Any` for parameters that have concrete types in the project:
```python
def _calc_hull(ship_catalog: Any, owned_ship: Any) -> int:
```
`ship_catalog` is always a `Ship` from `data/ships/core.py`. `owned_ship` is always `OwnedShip` from `ship.py`.

**Solution:** Replace `Any` with the concrete types. Use `TYPE_CHECKING` if circular imports are a concern.

```python
from __future__ import annotations
from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from ..data.ships.core import Ship
    from ..ship import OwnedShip

def _calc_hull(ship_catalog: Ship, owned_ship: OwnedShip) -> int:
```

**Files to touch:**
- `src/spacehack/combat/_stats.py` — `_calc_hull`, `_calc_max_hull`, `_calc_power_gen`, `_calc_max_shields`, `init_combat_state`
- `src/spacehack/combat/_actions.py` — `_sync_back_hull`

**Check:**
- [ ] No new circular import errors
- [ ] `mypy` or pyright passes (if ever run)
- [ ] Smoke test passes

---

## Quick Win 5: Clean up orphaned `data/enemies/` directory

**Estimate: 5 minutes**

**Problem:** NPC ship specs migrated from `data/enemies/` to `data/npc_ships/` (mentioned in comments in `npc_ships/core.py`). If `data/enemies/` still exists on disk, it's dead code that could confuse future contributors.

**Solution:**
```bash
git rm -r src/spacehack/data/enemies/  # if it still exists
```

**Check:**
- [ ] No imports reference the old module path
- [ ] Smoke test passes

---

## Acceptance criteria

Before considering quick wins done:
- [ ] All 5 items completed and committed (quick wins can be one commit)
- [ ] Smoke test passes
- [ ] Game still plays correctly from start
