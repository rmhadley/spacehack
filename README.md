# spacehack

A terminal-based sci-fi roguelike built on [python-tcod](https://github.com/HexDecimal/python-tcod).

## Quick start

Requires Python 3.10+ on macOS / Linux.

```bash
# from the repo root (the directory containing this README)
python3 -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -e .                   # editable install of spacehack itself

# Run the game (both of these work)
python -m spacehack
# or, after install:
spacehack
```

Press **ESC** or close the window to quit.

## First-run setup

The first launch downloads the bundled **DejaVu 16×16** tilesheet (the same one used in the official python-tcod tutorial) and caches it under the user's data directory:

| Platform | Tilesheet cache path |
|----------|----------------------|
| macOS       | `~/.local/share/spacehack/dejavu16x16_gs_tc.png` |
| Linux       | `~/.local/share/spacehack/dejavu16x16_gs_tc.png` (unless `XDG_DATA_HOME` is set, then `$XDG_DATA_HOME/spacehack/dejavu16x16_gs_tc.png`) |

(If you previously ran an older 10×10 build, the stale `dejavu10x10_gs_tc.png` may still be sitting in the same directory; it's harmless and can be deleted.)

Subsequent launches reuse the cached file. If the cached file ever becomes unreadable (partial download, disk error, etc.), the loader wipes it and re-downloads once before giving up.

If the download fails outright (offline, firewall, etc.), engine init raises a clear `EngineError` instead of silently falling back.

## Project layout

```
spacehack/
├── pyproject.toml                 # setuptools build config + the `spacehack` script
├── requirements.txt               # runtime dependency pin
├── README.md
├── tools/
│   ├── audit_loose_refs.py        # pre-commit gate (see The audit gate below)
│   └── _archived/                 # one-shot P3.6.x migration scripts (do not run)
└── src/
    └── spacehack/
        ├── __init__.py            # package marker + __version__
        ├── __main__.py            # entry point + top-level dispatcher
        ├── engine.py              # libtcod boilerplate (tileset, context, console, events)
        ├── game_context.py        # GameContext -- cross-cutting mutable state (the "ctx")
        ├── character.py           # character / species / class helpers
        ├── combat.py              # owns the entire combat domain (N1)
        ├── hud.py                 # combat HUD renderer
        ├── message_log.py         # in-game log renderer + writers
        ├── mission.py             # mission lifecycle helpers
        ├── npc.py                 # NPC dialogue / interaction helpers
        ├── ship.py                # owned-ship + ship-catalog helpers
        ├── solar_system.py        # system/planet helpers
        ├── ui.py                  # the central Modal loop + render helpers
        ├── world.py               # world generation + rendering
        └── data/                  # static content catalogs (dataclass-driven)
            ├── classes/           # character class specs
            ├── enemies/           # enemy ship specs
            ├── missions/          # mission offerings (per faction)
            ├── modules/           # ship module (system/engine) specs
            ├── npcs/              # NPC specs
            ├── planets/           # planet spawn tables
            ├── solar_systems/     # planet clusters per star
            ├── species/           # species traits
            └── weapons/           # laser / missile weapon specs
```

## Adding content

All content is data-driven. The shape is the same across every catalog:

*(Fields below are illustrative; check the actual data file for the canonical field set.)*

```python
# src/spacehack/data/weapons/lasers.py
from dataclasses import dataclass

@dataclass(frozen=True)
class Laser:
    id: str                          # match weapons/__init__:find_weapon key
    name: str
    damage: int
    ap_cost: int
    ammo_capacity: int
    # ...whatever fields the game needs

# src/spacehack/data/weapons/__init__.py
def find_weapon(weapon_id: str) -> Laser: ...
```

* **Add a weapon** -- add a frozen dataclass entry to the relevant file in `src/spacehack/data/weapons/` (e.g. `lasers.py`, `missiles.py`) and slot it into any ship loadout.
* **Add a ship module** (engine or system) -- add to `src/spacehack/data/modules/`.
* **Add an enemy ship spec** -- add to `src/spacehack/data/enemies/` (e.g. `pirates.py`).
* **Add a solar system** -- add a new `<system>.py` to `src/spacehack/data/solar_systems/` and register it in that directory's `__init__.py`.
* **Add a planet** -- add to `src/spacehack/data/planets/`. Per-planet building layouts land as data when N3 is implemented.
* **Add an NPC or species** -- `src/spacehack/data/npcs/`, `src/spacehack/data/species/`.
* **Add a mission** -- `src/spacehack/data/missions/`. New factions get their own `<faction>.py`; existing factions append new entries to the existing file.

Each data file should expose a frozen `@dataclass` for one or more specs and a `find_<thing>(id)` helper that raises `KeyError` on unknown ids (used for friendly error surfaces at runtime).

## Adding a new game domain

The dispatcher in `__main__._run_game` calls each domain by name. To add a new domain:

1. Create `src/spacehack/<domain>.py` and put its **entire** flow inside that file -- setup, execution, and post-state mutation live together.
2. Make the entry point take `ctx` (and any pure positional args) and access cross-cutting state through `ctx` (e.g. `ctx.log`, `ctx.player_owned_ship`), never as bare names.
3. From `__main__`, hand off with one call: `<domain>.<entry_point>(ctx, ...)`. No helper indirection; the dispatcher should be domain-unaware.

If the domain is modal-driven (cancelable, keypress-driven UI like ship-buy / jump-menu / NPC-talk), use the existing loop rather than rolling your own:

```python
ui.Modal(ctx.context, console).run(render_fn, update_fn)
```

If the domain needs new cross-cutting state, add it as a field on `GameContext` rather than threading it through every signature.

**GameContext fields** -- everything available via `ctx.<field>`:

| Field | Type | Purpose |
|-------|------|---------|
| `species_name`, `class_name` | `str` | character identity |
| `context` | `tcod.context.Context` | the SDL window; pass to `ui.Modal` etc. |
| `character_info`, `player` | dataclasses | character + entity state |
| `log` | `MessageLog` | in-game log + colour helpers |
| `game_map` | `world.GameMap` | world / entity container |
| `stats` | `HudStats` | aggregate HUD-facing values |
| `player_owned_ship` | `` `OwnedShip | None` `` | equipped ship (optional mid-save) |
| `player_active_mission` | `` `ActiveMission | None` `` | current mission (optional idle) |

## The audit gate

Before every commit:

```bash
python3 tools/audit_loose_refs.py
```

The audit walks the AST of `src/spacehack/__main__.py` and `src/spacehack/combat.py`. For every function in its `SCAN` list (currently `_handle_combat_encounter`, `_jump_to_system`, `_detect_combat_encounter`, `_animate_jump`, `_animate_ship_to_y`, `_launch_to_space`, `_return_to_city`), it fails if any of these tokens appears as a **bare** Name reference:

```
game_map, log, stats, character_info,
player_owned_ship, player_active_mission, context
```

If you hit the audit, your function is reading one of these tokens as a bare local instead of via `ctx.<token>` (e.g. `game_map.entities` instead of `ctx.game_map.entities`). Fix the call, not the audit.

Add new SCAN'd helpers to the `SCAN` tuple in `tools/audit_loose_refs.py` once they finish their context-bundle migration.

## Smoke testing

After refactoring signatures (especially in `combat.py` or other domain modules), verify entry points survived with the smoke tool rather than ad-hoc `python3 -c` imports. The tool auto-mounts `.venv/bin/python3` so a bare-`python3` invocation still resolves `tcod` (which lives only in the project venv):

```bash
python3 tools/smoke.py
```

Pass: `PASS: Smoke tests OK.` and exit 0. Fail: `FAIL: <reason>` to stderr, exit 1. The tool checks `combat._handle_combat_encounter`, `combat.run_combat`, `game_context.GameContext`, `world.GameMap`, and `ui.Modal` are present.

## Refactor philosophy

* **Data-first.** New content is a file in `data/` backed by a frozen dataclass. No content lives in `__main__.py` or any runtime module.
* **Cross-cutting state goes through `ctx`.** Functions that touch `game_map`, `log`, `stats`, character info, the owned ship, or the active mission read them off `ctx`. This eliminates bare-Name regressions and stabilizes signatures.
* **Domains own their flow.** Each domain module owns its setup, execution, and post-state mutation. The dispatcher is domain-unaware and hands off with one call.
* **Atomic commits.** Each commit is one self-contained change (one refactor step, one feature, or one bug fix) with a descriptive message. Non-trivial work lands as a sequence of atomic commits, not one mega-commit.
* **Git anchors every AI-assisted step.** Each new request starts with no memory of the last turn, so orient with `git status` / `git diff --stat`, commit one logical change per AI-assisted step (same atomicity as the rule above), and run the audit + smoke gates before each commit. The next session opens from the diff, not from prose recall -- the working tree, not the chat log, is the source of truth.
* **Idempotent tooling.** Migration and audit scripts are safe to re-run without double-inserting. Anchors on unique substrings; asserts on count==1; early-exits if the new content is already present.
* **Gates beat playtests.** Catch a regression class by extending the audit's `SCAN` list and `LOOSE` set, not by waiting for someone to hit it in-game.
* **Terse code-shaped docs.** Optimize for the skim-don't-read mode; assume a future-after-context-wipe reader.

## Tweaking

Screen size, tile source, and window title live as module-level constants in
`src/spacehack/engine.py`:

```python
SCREEN_WIDTH         = 100                 # character cells
SCREEN_HEIGHT        = 50                  # character cells
WINDOW_TITLE         = "spacehack"
TILESHEET_FILENAME   = "dejavu16x16_gs_tc.png"
```

100 cells × 16 px = 1600 logical-pixel wide window, 50 cells × 16 px = 800 logical-pixel tall -- the default libtcod roguelike starter size. Change the constants and the rest of the codebase picks them up (`make_console()` reads them at call time, so a runtime override is fine).

Swap to a bigger or different bitmap tilesheet by editing `TILESHEET_FILENAME` -- other available filenames in libtcod's `data/fonts/` include `dejavu10x10_gs_tc.png`, `dejavu12x12_gs_tc.png`, `consolas10x10_gs_tc.png`, etc.

## License

MIT (or your choice -- update `pyproject.toml` accordingly).