# FIX: Break Up `__main__.py`

## Problem

`__main__.py` is ~600 lines and handles too many responsibilities:

| Responsibility | Lines (approx) |
|----------------|---------------|
| Character creation flow (species/class pick, confirm) | 50 |
| `_run_game()` dispatch loop (city mode) | 200 |
| `_run_game()` dispatch loop (space mode) | 200 |
| Bounty spawn logic (`_pick_bounty_spawn_pos`, `_bounty_landmarks`) | 80 |
| Mission accept/complete/abandon wiring | 100 |
| NPC interaction routing | 80 |
| Dev mode override | 40 |

The result is a file where every new space-mode feature adds another `if` branch to the giant event-dispatch chain, and every new mission type adds more inline lifecycle code.

## Goals of the refactor

1. Extract **scene dispatch** — the city-mode vs space-mode key handlers should live in their own modules
2. Extract **mission lifecycle** — the accept/complete/abandon wiring that spans ~100 lines should be in `mission.py` or a dedicated handler
3. Extract **bounty spawn logic** — `_bounty_landmarks` and `_pick_bounty_spawn_pos` are purely mission-domain and should move
4. `_run_game()` should call into domain modules, not inline their logic
5. No behavior change — the refactor is purely structural

## Extraction plan

### Module: `src/spacehack/scene.py` (new)

Holds the dispatch logic for what happens when the player presses keys in each mode. The `_run_game` loop becomes a thin event loop that delegates to scene objects.

```python
# scene.py

@dataclass
class SceneState:
    mode: str  # "city" or "space"
    game_map: world.GameMap
    player: world.Entity
    current_city_id: str

def handle_city_event(ctx, event, scene) -> SceneOutcome: ...
def handle_space_event(ctx, event, scene) -> SceneOutcome: ...
```

But this might be over-engineering. A lighter approach:

### Module: `src/spacehack/dispatch.py` (new)

Extract just the key-handler helper functions that are currently in `__main__.py`:

- `_handle_quest_log(ctx, player_active_missions)` — currently inlined in the keyboard check
- `_handle_navigation(ctx, player_pos)` — wraps `_run_navigation`, handles outcome
- `_handle_goto(ctx, player)` — wraps `_run_goto`, handles combat fallout
- `_handle_comms(ctx, player_pos)` — wraps `_open_comms`, handles attack outcome
- `_handle_wait(ctx)` — wraps the period-key wait flow
- `_handle_move(ctx, dx, dy, current_mode)` — wraps the vim movement + collision + NPC movement + combat detection chain

Each handler returns an outcome enum (`CONTINUE`, `QUIT`, `COMBAT`, etc.) and the caller (`_run_game`) acts on the outcome.

### Module: `src/spacehack/bounty_spawn.py` (new)

Move `_bounty_landmarks()` and `_pick_bounty_spawn_pos()` from `__main__.py` into a shared module so mission-domain code doesn't have to live in the entry point.

### Inline extraction: Mission lifecycle

The accept/complete/abandon wiring in `_run_game()` currently:
1. Checks for cargo capacity
2. Creates `BountySpawn` entries
3. Adds to `ctx.player_active_missions`
4. Reserves cargo
5. Logs success messages

This should be exposed as `mission_module.accept_mission(ctx, spec, planet_id) -> bool` that handles all of the above internally. The caller in `__main__.py` becomes:

```python
if mission_module.accept_mission(ctx, picked, current_city_id):
    log.add("Mission accepted.")
else:
    log.add("Could not accept mission.")
```

## Files changed

| Action | File |
|--------|------|
| **New** | `src/spacehack/dispatch.py` |
| **New** | `src/spacehack/bounty_spawn.py` |
| **Modified** | `src/spacehack/__main__.py` — strip down to ~250 lines |
| **Modified** | `src/spacehack/mission.py` — add `accept_mission()` with full lifecycle |

## Risks

- **High-touch file:** `__main__.py` is the entry point and any import error crashes the game. Each extraction must be committed separately and smoke-tested before the next.
- **No behavior change:** The extracted functions must produce identical behavior. Any divergence is a bug.

## Playtest checklist

After each extraction phase:

- [ ] Fresh game → species/class pick → city mode → walk around
- [ ] Take a mission → fly to destination → complete it
- [ ] Take a bounty → fly to target system → destroy target → complete
- [ ] Abandon a mission → verify cargo released
- [ ] Open quest log → navigate → abandon
- [ ] Launch → space mode → move, auto-nav, comms, cargo, wait
- [ ] Combat encounter triggers correctly
- [ ] Land on a planet → city mode
- [ ] Jump between systems
- [ ] Smoke test passes

## Acceptance criteria

- [ ] `__main__.py` is under 300 lines
- [ ] All key-dispatch logic lives in `dispatch.py`
- [ ] All bounty spawn logic lives in `bounty_spawn.py`
- [ ] Mission accept/complete/abandon is a single call into `mission.py`
- [ ] No behavior change
- [ ] Smoke test passes
