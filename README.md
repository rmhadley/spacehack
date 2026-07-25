# spacehack

A terminal-based roguelike built on [python-tcod](https://github.com/HexDecimal/python-tcod) (the modern Python binding for libtcod).

> Status: minimal hello-world scaffold. Wire a player, a map, turns, then go.

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

## What happens on first run

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
├── pyproject.toml         # setuptools build config + the `spacehack` script
├── requirements.txt       # runtime dependency pin
├── README.md
├── .gitignore
└── src/
    └── spacehack/
        ├── __init__.py    # package marker + __version__
        ├── __main__.py    # `python -m spacehack` entry point
        └── engine.py      # libtcod boilerplate (tileset, context, console, events)
```

## Tweaking

Screen size, tile source, and window title live as module-level constants in
`src/spacehack/engine.py`:

```python
SCREEN_WIDTH         = 100                 # character cells
SCREEN_HEIGHT        = 50                  # character cells
WINDOW_TITLE         = "spacehack"
TILESHEET_FILENAME   = "dejavu16x16_gs_tc.png"
```

100 cells × 16 px = 1600 logical-pixel wide window, 50 cells × 16 px = 800 logical-pixel tall - the default libtcod roguelike starter size. Change the constants and the rest of the codebase picks them up (`make_console()` reads them at call time, so a runtime override is fine).

Swap to a bigger or different bitmap tilesheet by editing `TILESHEET_FILENAME` - other available filenames in libtcod's data/fonts/ include `dejavu10x10_gs_tc.png`, `dejavu12x12_gs_tc.png`, `consolas10x10_gs_tc.png`, etc.

## License

MIT (or your choice - update `pyproject.toml` accordingly).
