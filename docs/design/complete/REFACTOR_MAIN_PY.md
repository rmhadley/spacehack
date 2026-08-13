# Refactor `__main__.py` — Extract into Dedicated Files

**Status**: Complete (main-loop extraction; interaction-handler decomposition remains follow-up work)

## Result

The old gameplay monolith has been split into focused modules:

- `input_helpers.py` — normalized input predicates and character-creation screens
- `menus/` — interactive menu domains
- `navigation.py` — navigation, jumps, cargo scans, and bounty positioning
- `city.py` — city/space transition primitives and animations
- `game_flow.py` — combat, save/exit, dungeon transition, and ship-flow orchestration
- `game_interactions.py` — movement blocker dispatch and interaction handlers
- `game_loop.py` — gameplay state setup, frame presentation, event processing, and the thin gameplay coordinator
- `title_flow.py` — title splash, continue/tutorial selection, and character creation
- `__main__.py` — compatibility adapters, application entry point, and runtime ownership only

The implementation preserves the historical `__main__` helper names used by
existing tests and callers. The live gameplay loop imports its concrete
implementations from the extracted modules; new tests for live-loop behavior
should patch those owning modules rather than the compatibility aliases.

## Verification

- `__main__.py` no longer contains the long-lived gameplay loop.
- Title flow is isolated in `title_flow.py`.
- Gameplay setup, presentation, input processing, and interactions are isolated
  from the application entry point.
- The local pre-commit gate remains `make check`.
- The CI workflow is intentionally outside this refactor's scope.

## Historical phases

The original mechanical extraction phases are retained in git history. The
active contract is the module ownership above; future changes should extend the
smallest owning module and add focused tests for new pure or mutation-wrapper
behavior.
