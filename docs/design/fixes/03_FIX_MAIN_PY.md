# FIX: Break Up `__main__.py` — Superseded

**Status:** Superseded by [`REFACTOR_MAIN_PY.md`](../complete/REFACTOR_MAIN_PY.md)

## Historical purpose

This document described the original plan for reducing the old `__main__.py`
monolith. At the time, the entry point contained character creation, city and
space event dispatch, bounty spawning, mission wiring, NPC interactions, and
dev-mode handling in one large loop.

The proposed `scene.py`, `dispatch.py`, and `bounty_spawn.py` modules were
planning alternatives, not an architecture that should be implemented now.
The codebase took a different and more focused route: gameplay, title flow,
navigation, city transitions, mission interactions, and combat orchestration
were extracted into domain-owned modules while preserving compatibility names
for existing callers and tests.

## Current replacement

The active refactor record is:

- [`docs/design/complete/REFACTOR_MAIN_PY.md`](../complete/REFACTOR_MAIN_PY.md)

The current ownership is:

| Concern | Current module |
|---|---|
| Title splash, continue, tutorial, character creation | `src/spacehack/title_flow.py` |
| Normalized input predicates and picker screens | `src/spacehack/input_helpers.py` |
| Gameplay setup, presentation, event processing | `src/spacehack/game_loop.py` |
| Movement blockers and world interactions | `src/spacehack/game_interactions.py` |
| Combat, save/exit, dungeon, and ship-flow orchestration | `src/spacehack/game_flow.py` |
| Navigation, jumps, cargo scans, bounty positioning | `src/spacehack/navigation.py` |
| City/space transitions and animations | `src/spacehack/city.py` |
| Menus | `src/spacehack/menus/` |
| Application entry point and compatibility adapters | `src/spacehack/__main__.py` |

Do not implement the old `scene.py`, `dispatch.py`, or `bounty_spawn.py` plan
without first reconciling it with the active refactor document and current
module ownership.

## Historical acceptance target

The old target of putting all dispatch logic in one `dispatch.py` and reducing
`__main__.py` below 300 lines is retained only as historical context. The
current structural contract is defined by `REFACTOR_MAIN_PY.md`, which keeps
`__main__.py` focused on application entry and compatibility while allowing
follow-up decomposition of oversized domain handlers where it improves
ownership and testability.
