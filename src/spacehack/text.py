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
    runtime.<name>            (overlay text: transmissions, log lines, popups)
    disclosure.<key>.<field>  (orbit archive-disclosure choices)

Regenerate the baseline from code with
``python3 tools/extract_act0_text.py`` (overwrites the JSON files).
The ``SPACEHACK_TEXT_DIR`` env var overrides the overlay directory
(used by tests and for pointing at an absolute path).
"""

from __future__ import annotations

import json
import os
from pathlib import Path

# ---------------------------------------------------------------------------
# Runtime string defaults — the single source of truth for story text that
# the main-quest code shows outside the step/dialogue catalog (transmission
# overlays, log lines, popups, orbit scene). Call sites use ``get()``; the
# extractor exports ``RUNTIME`` so the JSON baseline stays in lockstep.
# ``{placeholders}`` are filled in by the call site — keep them verbatim.
# ---------------------------------------------------------------------------

RUNTIME: dict[str, str] = {
    # --- The signal (first jump out of Sol) ---
    "runtime.transmission_title": "INCOMING TRANSMISSION",
    "runtime.transmission_body": (
        "Comms lights up with a strange signal.It's mostly noise and "
        "static. But through the incomprehensible chatter the systems "
        "detect a pattern.\n\n"
        "Coordinates that appear to be pointing to a remote part of "
        "Mars in Sol."
    ),
    "runtime.signal_log_static": (
        "STATIC... a garbled transmission cuts through the noise."
    ),
    "runtime.signal_log_coordinates": (
        "Your ship crunches the data and outputs coordinates on mars."
    ),
    # --- Sealed door: discover + open overlays ---
    "runtime.door_discover_title": "SEALED ENTRANCE",
    "runtime.door_discover_meta": (
        "MAKE: ALIEN    MECHANISM: NONE VISIBLE    AGE: UNKNOWN"
    ),
    "runtime.door_discover_body": (
        "The martian rock merges with high tech metal machinery.\n"
        "You see a wall that undulates before you as you examine it.\n"
        "An alien console stands before it, still with power.\n"
        "But a mystery you can't solve alone."
    ),
    "runtime.door_discover_highlight": (
        "The console just hums and ignores your input."
    ),
    "runtime.door_discover_log": (
        "An undulating wall of alien make, set into the red dust."
    ),
    "runtime.door_open_title": "THE SEAL GIVES WAY",
    "runtime.door_open_meta": (
        "SEAL: BROKEN    CHAMBER: EMPTY    ACCESS: GRANTED"
    ),
    "runtime.door_open_body": (
        "The seal gives way - cleanly, as if it were waiting.\n"
        "Inside: an empty cell built for something enormous -\n"
        "and a dark terminal interface waiting for input."
    ),
    "runtime.door_open_highlight": (
        "The entrance is open. The way forward leads deeper into the facility."
    ),
    "runtime.door_open_log": (
        "The seal gives way. Inside: an empty cell built for something "
        "enormous - and a dark terminal interface waiting to be accessed."
    ),
    "runtime.door_open_log2": (
        "The entrance is open. Beyond it, the facility descends into darkness."
    ),
    "runtime.door_gapes_log": "The opened entrance gapes dark and empty.",
    "runtime.door_holds_log": (
        "The sealed door holds fast. It needs a tool you don't have."
    ),
    "runtime.chip_fragment_log": (
        "You chip a fragment of the alien material off the door's "
        "surface. The seal holds."
    ),
    "runtime.door_ambush_title": "AMBUSH!",
    "runtime.door_ambush_faction": "Pirate Raiders",
    "runtime.door_ambush_body": (
        "Raiders pour out of the shadows around the sealed "
        "door - they were watching the dig site, waiting for "
        "someone to come back for the sample. They want it."
    ),
    # --- Summon + gate popup chrome ---
    "runtime.summon_title": "INCOMING MESSAGE",
    "runtime.gate_popup_default_title": "THE WORK BEGINS",
    # --- Smuggle crate + goods log lines ---
    "runtime.smuggle_loaded_log": (
        "{good} loaded into your mission hold. Deliver it to "
        "complete the job."
    ),
    "runtime.smuggle_handover_log": "The crate is handed over.",
    "runtime.smuggle_lost_log": (
        "The crate is lost. Talk to the quest giver for another "
        "one."
    ),
    "runtime.smuggle_resecured_log": (
        "The {good} is re-secured in your mission hold."
    ),
    "runtime.no_ship_log": "You don't have a ship to carry the crate.",
    "runtime.goods_handed_over_log": "The required goods are handed over.",
    "runtime.missing_goods_log": (
        "You don't have the required goods for this task."
    ),
    # --- Chain lock-in + readout guidance ---
    "runtime.chain_lockin_log": (
        "You've agreed to work with the "
        "{faction} - the plan is in motion."
    ),
    "runtime.readout_wait_hint": (
        "The {faction} will contact "
        "you when they're ready for the next step. "
        "Check your quest log (Q) for updates."
    ),
    # --- Orbit disclosure scene (first post-prison reading) ---
    "runtime.orbit_title": "THE FIRST READING",
    "runtime.orbit_body_intro": (
        "The recovered archive has begun interacting with your "
        "communications array."
    ),
    "runtime.orbit_body_route": (
        "One layer may be a route beyond the Luyten blockade. "
        "The others remain unread."
    ),
    "runtime.orbit_faction_militia": (
        "The Militia calls it a containment record and warns you not to "
        "transmit it."
    ),
    "runtime.orbit_faction_merchants": (
        "The Guild sees infrastructure: routes, stations, and technology "
        "someone will try to own."
    ),
    "runtime.orbit_faction_bar": (
        "The Bar hears a route to a score - and recognizes the shape of "
        "an old warning underneath it."
    ),
    "runtime.orbit_faction_lab": (
        "The Lab calls it layered structure, not language, and refuses "
        "to separate the warning from the route."
    ),
    "runtime.orbit_faction_unknown": (
        "The recovered archive has no trusted interpreter yet; its layers "
        "resist a clean reading."
    ),
}


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


def get(key: str, default: str = "") -> str:
    """Return the overlay value for ``key``, falling back to ``default``.

    Runtime call sites pass their authored literal as ``default``; when
    a key also exists in :data:`RUNTIME`, that shipped default is used
    when the JSON overlay has no override.
    """
    if key in overlay():
        return overlay()[key]
    if key in RUNTIME:
        return RUNTIME[key]
    return default


def reload() -> None:
    """Re-parse the overlay files (dev-mode F5 hot reload)."""
    global _overlay
    _overlay = _load()
