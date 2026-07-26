# spacehack — Agent knowledge

A terminal-based sci-fi roguelike built on [python-tcod](https://github.com/HexDecimal/python-tcod).

## Quick start

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e .
python -m spacehack           # run the game
```

## Git workflow (MANDATORY — aggressive local commits)

**Commit after every logical change.** Do not batch changes. Do not wait until the end of a session. The working tree, not the chat log, is the source of truth.

### Commit discipline
- **One commit = one self-contained change** (one refactor step, one feature, or one bug fix).
- **Descriptive messages.** Start with a prefix tag: `feat:`, `fix:`, `refactor:`, `docs:`, `tools:`, `content:`. Example: `feat: add laser damage falloff at range`.
- **Run gates before each commit.** Never commit without passing audit + smoke (see Pre-commit gates below).
- **NO mega-commits.** Break large work into a sequence of atomic commits.

### Why
Each new AI session opens from `git status` / `git diff --stat` / `git log`. If changes aren't committed, the agent has no memory of what was done. Commit aggressively so the next turn picks up from a clean diff, not from prose recall.

---

## Key conventions (always follow)

### ctx-first design
All cross-cutting state goes through `GameContext` (`ctx`). **Never** use these as bare names in domain functions:

- `game_map`, `log`, `stats`, `character_info`
- `player_owned_ship`, `player_active_mission`, `context`

Always: `ctx.game_map`, `ctx.log`, etc.

### GameContext fields
| Field | Type | Purpose |
|-------|------|---------|
| `species_name`, `class_name` | `str` | character identity |
| `context` | `tcod.context.Context` | SDL window; pass to `ui.Modal` |
| `character_info`, `player` | dataclasses | character + entity state |
| `log` | `MessageLog` | in-game log + colour helpers |
| `game_map` | `world.GameMap` | world / entity container |
| `stats` | `HudStats` | aggregate HUD-facing values |
| `player_owned_ship` | `` `OwnedShip | None` `` | equipped ship |
| `player_active_mission` | `` `ActiveMission | None` `` | current mission |

### Adding content (data-first)
All content lives in `src/spacehack/data/` as frozen dataclasses:

| Content | Location |
|---------|----------|
| Weapons (lasers) | `data/weapons/lasers.py` |
| Weapons (missiles) | `data/weapons/missiles.py` |
| Ship modules (engines) | `data/modules/engines.py` |
| Ship modules (systems) | `data/modules/systems.py` |
| Enemy ships | `data/enemies/pirates.py` |
| Solar systems | `data/solar_systems/<name>.py` + register in `__init__.py` |
| Planets | `data/planets/` |
| NPCs | `data/npcs/` |
| Species | `data/species/` |
| Missions | `data/missions/<faction>.py` |
| Character classes | `data/classes/core.py` |

Each data file exposes a frozen `@dataclass` + `find_<thing>(id)` that raises `KeyError`.

### Adding a new game domain
1. Create `src/spacehack/<domain>.py` — setup, execution, post-state live together.
2. Entry point takes `ctx` (+ pure positional args). Access all state via `ctx`.
3. From `__main__`, hand off: `<domain>.<entry_point>(ctx, ...)`. No indirection.
4. For modal-driven UI: `ui.Modal(ctx.context, console).run(render_fn, update_fn)`
5. Add new cross-cutting state as a field on `GameContext`.

### Pre-commit gates
```bash
# 1. Audit — catches bare-Name regressions in scanned functions
python3 tools/audit_loose_refs.py

# 2. Smoke — verifies entry points survived signature changes
python3 tools/smoke.py
```

When you add a new domain function that accesses cross-cutting state, add it to the `SCAN` tuple in `tools/audit_loose_refs.py`. Current scanned functions:
`_handle_combat_encounter`, `_jump_to_system`, `_detect_combat_encounter`, `_animate_jump`, `_animate_ship_to_y`, `_launch_to_space`, `_return_to_city`

### Refactor philosophy
- **Data-first.** New content is a file in `data/` backed by a frozen dataclass. No content lives in `__main__.py` or runtime modules.
- **Cross-cutting state through `ctx`.** No bare-Name regressions.
- **Domains own their flow.** Dispatcher is domain-unaware, one-call handoff.
- **Atomic commits.** One self-contained change per commit. Descriptive message.
- **Git anchors every step.** Each new session starts from `git status` / `git diff --stat`, not prose recall.
- **Gates beat playtests.** Extend audit's `SCAN` list and `LOOSE` set to catch regressions.
- **Terse code-shaped docs.** Skim-don't-read mode.

## Screen constants (in `engine.py`)
```python
SCREEN_WIDTH   = 100
SCREEN_HEIGHT  = 50
WINDOW_TITLE   = "spacehack"
TILESHEET_FILENAME = "dejavu16x16_gs_tc.png"
```

## Modal UI pattern
```python
ui.Modal(ctx.context, console).run(render_fn, update_fn)
```
