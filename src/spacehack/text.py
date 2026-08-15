"""Runtime story-text overlay.

The game's authored story text (main quest steps + dialogue, NPC
flavor) ships as Python defaults, but writer-facing JSON files under
``src/spacehack/data/text/`` override those strings at catalog-build
time. Editing a JSON file and relaunching — or pressing F5 in dev
mode — is all that's needed to see new story text in-game. No code
edits.

Keys are stable paths into the game data:

    step.<id>.title
    step.<id>.description
    step.<id>.dialogue.<npc>.intro|active|complete|locked|option_label
    npc.<id>.flavor_text

Regenerate the baseline from code with
``python3 tools/extract_act0_text.py`` (overwrites the JSON files).
The ``SPACEHACK_TEXT_DIR`` env var overrides the overlay directory
(used by tests and for pointing at an absolute path).
"""

from __future__ import annotations

import json
import os
from pathlib import Path

_DEFAULT_DIR = Path(__file__).resolve().parent / "data" / "text"

_overlay: dict[str, str] | None = None


def _text_dir() -> Path:
    """Return the overlay directory (``SPACEHACK_TEXT_DIR`` wins)."""
    _env = os.environ.get("SPACEHACK_TEXT_DIR")
    return Path(_env) if _env else _DEFAULT_DIR


def _load() -> dict[str, str]:
    """Parse every ``*.json`` in the overlay dir into one key map."""
    _merged: dict[str, str] = {}
    _dir = _text_dir()
    if not _dir.is_dir():
        return _merged
    for _path in sorted(_dir.glob("*.json")):
        try:
            _data = json.loads(_path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        if not isinstance(_data, dict):
            continue
        for _key, _value in _data.items():
            if isinstance(_value, str):
                _merged[_key] = _value
    return _merged


def overlay() -> dict[str, str]:
    """Return the merged text overlay (parsed once, then cached)."""
    global _overlay
    if _overlay is None:
        _overlay = _load()
    return _overlay


def reload() -> None:
    """Re-parse the overlay files (dev-mode F5 hot reload)."""
    global _overlay
    _overlay = _load()
