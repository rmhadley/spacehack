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

## Project layout

```
spacehack/
├── pyproject.toml                 # setuptools build config + the `spacehack` script
├── requirements.txt               # runtime dependency pin
├── README.md
├── tools/
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

### When to extract a new domain

If you find yourself writing a substantial block inside an existing module, step back and ask:

* **Single concern?** — Does this code handle one coherent responsibility
  (combat, trade, navigation, comms, cargo, etc.)?
* **Independent reasoning?** — Could this block be understood, tested, or
  modified without knowing the rest of the file it lives in?
* **File size trigger?** — Is the target file approaching ~1000 lines?

If yes to any of these, the code belongs in its own domain module. Create
a new `<domain>.py`, move the logic there, and hand off from the dispatcher
with one call. This keeps the dispatcher thin and prevents any single file
from becoming a monolith.

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

## Pre-commit gate

Before every commit:

```bash
python3 tools/smoke.py
```

The smoke test auto-mounts `.venv/bin/python3` so a bare-`python3` invocation still resolves `tcod` (which lives only in the project venv). It verifies all major modules import correctly and checks key entry points survived signature changes: `combat._handle_combat_encounter`, `combat.run_combat`, `game_context.GameContext`, `world.GameMap`, and `ui.Modal`. Pass: `PASS: Smoke tests OK.` and exit 0. Fail: `FAIL: <reason>` to stderr, exit 1.

## Refactor philosophy

* **Data-first.** New content is a file in `data/` backed by a frozen dataclass. No content lives in `__main__.py` or any runtime module.
* **Cross-cutting state goes through `ctx`.** Functions that touch `game_map`, `log`, `stats`, character info, the owned ship, or the active mission read them off `ctx`. This eliminates bare-Name regressions and stabilizes signatures.
* **Domains own their flow.** Each domain module owns its setup, execution, and post-state mutation. The dispatcher is domain-unaware and hands off with one call.
* **Atomic commits.** Each commit is one self-contained change (one refactor step, one feature, or one bug fix) with a descriptive message. Non-trivial work lands as a sequence of atomic commits, not one mega-commit.
* **Git anchors every AI-assisted step.** Each new request starts with no memory of the last turn, so orient with `git status` / `git diff --stat`, commit one logical change per AI-assisted step (same atomicity as the rule above), and run the smoke gate before each commit. The next session opens from the diff, not from prose recall -- the working tree, not the chat log, is the source of truth.
* **Gates beat playtests.** Run the smoke test before each commit to catch import errors and missing entry points before they surface in-game.
* **File size trigger.** No module should become a monolith by accident. When a production file approaches ~1000 lines, pause and evaluate whether it has grown beyond one coherent responsibility. The ~1000 line mark is not a rigid cap — but passing it should be a deliberate choice, not a surprise.
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

Swap to a different tilesheet by placing the PNG in `src/spacehack/data/` and updating `TILESHEET_FILENAME`. The bundled tilesheet is DejaVu 16x16; the python-tcod repository also ships a 10x10 and 12x12 variant under `data/fonts/`.

For a modern look, drop any monospace `.ttf` or `.otf` into `data/` and set `TRUETYPE_FONT_FILENAME` — the game rasterizes it at 16×16 and automatically falls back to the CP437 tilesheet if the font file is missing. The bundled font is Hack v3.003 (MIT — see `data/Hack-LICENSE.txt`).

**Choosing a font (gotcha):** libtcod 2.2.2 scales a font to the tile height, then shrinks it to fit the tile width if the font's head-bbox width exceeds it — fonts whose head bbox is wider than their em height (e.g. Iosevka, JetBrains Mono, Fira Code, Cascadia Code) render at ~50% size at 16×16. Before adopting a font, verify `head.xMax - head.xMin < hhea.ascent - hhea.descent` (e.g. with fontTools); Hack and Source Code Pro pass.

**Box drawing (second gotcha):** libtcod centers each TrueType glyph's *ink bounding box* in its tile. Symmetric glyphs (`─ │ ┼`) center fine, but asymmetric box-drawing corners (`┌ ┐ └ ┘`, `╔ ╗ ╚ ╝`) drift off the shared centerline — every font fails this way, so font choice can't fix it. Instead, `engine.py` draws the box-drawing block (U+2500-256C) procedurally at load time: straight strokes anchored to a common center (single: 4px strokes at rows/cols 6-9; double: 4px bars at 2-5 and 10-13), mirroring the CP437 tilesheet geometry. Text glyphs are untouched. If you swap fonts, this keeps walls and menu frames seamless.

## License

Released under the [MIT License](LICENSE) — Copyright (c) 2026 rmhadley.
See the `LICENSE` file for the full text.