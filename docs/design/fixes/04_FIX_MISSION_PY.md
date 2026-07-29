# FIX: Break `mission.py` into a Package

## Problem

`mission.py` handles too many distinct responsibilities. Based on the design docs and code I've read, it likely covers:

| Responsibility | What it does |
|----------------|-------------|
| **Data models** | `ActiveMission`, `MissionBoard`, `MissionStatus` |
| **Board lifecycle** | `ensure_board`, `fill_empty_slots`, `board_offerings`, `board_remove`, `board_return_static`, `refresh_all_boards` |
| **Procedural delivery gen** | `generate_delivery_mission`, hop-range BFS, destination picker |
| **Procedural bounty gen** | `generate_bounty_mission`, `_generate_bounty_name`, `_bounty_enemy_pool` |
| **Accept/Complete/Abort** | `try_accept_mission`, `commit_accept_mission`, `complete_mission`, `abort_mission` |
| **Delivery target helpers** | `find_deliverable_missions`, `active_is_deliverable_at`, `missions_offered_by` |
| **Cargo/reservation** | Cargo reservation logic on accept/complete/abort |
| **Constants** | `MAX_ACTIVE_MISSIONS`, deadline formulas |

This makes the file hard to navigate. Adding a new mission type (e.g. bar missions, patrol missions) means adding more procedural generators to an already-crowded module.

## Solution: Package structure

Convert `mission.py` into a `mission/` package with sub-modules grouped by concern:

```
src/spacehack/mission/              # was mission.py
├── __init__.py                     # re-exports all public symbols
├── _models.py                      # ActiveMission, MissionStatus, MissionBoard
├── _board.py                       # Board lifecycle: ensure, fill, offerings, refresh
├── _proc_delivery.py               # Procedural delivery mission generation
├── _proc_bounty.py                 # Procedural bounty mission generation
├── _lifecycle.py                   # accept, complete, abort, cargo reservation
├── _helpers.py                     # find_deliverable_missions, missions_offered_by, constants
```

### `__init__.py` re-exports

Following the pattern established by `combat/__init__.py`:

```python
from ._models import ActiveMission, MissionStatus, MissionBoard
from ._board import ensure_board, fill_empty_slots, board_offerings, board_remove, board_return_static, refresh_all_boards
from ._proc_delivery import generate_delivery_mission
from ._proc_bounty import generate_bounty_mission, _generate_bounty_name
from ._lifecycle import try_accept_mission, commit_accept_mission, complete_mission, abort_mission
from ._helpers import find_deliverable_missions, active_is_deliverable_at, missions_offered_by, MAX_ACTIVE_MISSIONS
```

## Implementation plan

### Phase 1: Create package skeleton + re-exports

- [ ] `mkdir src/spacehack/mission/`
- [ ] Create `mission/__init__.py` with all current re-exports
- [ ] Create `mission/_models.py` — move `ActiveMission`, `MissionStatus`, `MissionBoard` from old `mission.py`
- [ ] Create `mission/_helpers.py` — move `MAX_ACTIVE_MISSIONS`, `find_deliverable_missions`, `active_is_deliverable_at`, `missions_offered_by`
- [ ] Verify all imports still resolve (the package covers the same symbols as the old module via `__init__.py`)
- [ ] Smoke test

### Phase 2: Extract board lifecycle

- [ ] Create `mission/_board.py` — move `ensure_board`, `fill_empty_slots`, `board_offerings`, `board_remove`, `board_return_static`, `refresh_all_boards`
- [ ] Smoke test

### Phase 3: Extract procedural generators

- [ ] Create `mission/_proc_delivery.py` — move `generate_delivery_mission`, hop-range helpers
- [ ] Create `mission/_proc_bounty.py` — move `generate_bounty_mission`, `_generate_bounty_name`, `_bounty_enemy_pool`
- [ ] Smoke test

### Phase 4: Extract lifecycle

- [ ] Create `mission/_lifecycle.py` — move `try_accept_mission`, `commit_accept_mission`, `complete_mission`, `abort_mission`, cargo reservation logic
- [ ] Smoke test

### Phase 5: Remove old file

- [ ] `git rm src/spacehack/mission.py`
- [ ] Full playtest: accept, complete, and abort both delivery and bounty missions
- [ ] Smoke test

## Risks

- **Circular imports:** `_lifecycle.py` imports `_models.py` for `ActiveMission`. `_board.py` imports `_models.py`. `_proc_delivery.py` imports from `_helpers.py`. None of these should be circular if the package is structured as a DAG (models → helpers → board → lifecycle/procedural). The `__init__.py` aggregates them all.
- **`combat/_encounter.py` imports from `mission`:** This is fine — it imports `complete_mission` which will be in `_lifecycle.py` and re-exported from `__init__.py`.
- **`__main__.py` imports from `mission`:** This is the most common import site. As long as `__init__.py` re-exports the same symbols, all call sites work unchanged.

## Acceptance criteria

- [ ] `src/spacehack/mission/` package exists with 6 sub-modules
- [ ] `src/spacehack/mission.py` deleted
- [ ] All imports of `mission.symbol` work without changes — no call-site rewrites needed
- [ ] No sub-module exceeds 400 lines
- [ ] Smoke test passes
- [ ] Full playtest: accept delivery, accept bounty, complete both, abort both
