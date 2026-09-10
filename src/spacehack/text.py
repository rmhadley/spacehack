"""Runtime story-text overlay.

Main-quest step prose (titles, descriptions, dialogue) lives ONLY in the
writer-facing JSON files under ``src/spacehack/data/text/`` — the step
catalogs are structural, and a missing required key fails the build
loudly. The other catalogs (NPC flavor, trade-good names, runtime
strings, disclosure choices) ship Python defaults that these JSON files
override. Editing a JSON file and relaunching — or pressing F5 in dev
mode — is all that's needed to see new story text in-game. No code
edits.

Keys are stable paths into the game data:

    step.<id>.title
    step.<id>.description
    step.<id>.dialogue.<npc>.intro|active|complete|locked|option_label
    npc.<id>.flavor_text
    runtime.<name>            (overlay text: transmissions, log lines, popups)
    disclosure.<key>.<field>  (orbit archive-disclosure choices)
    rumor.<id>.text|topic|witness.<npc>   (lore prose — single-source
                              like step.*; enforced by the data tests)

The JSON files are the single authoring surface; sync the key set
against the code — orphaned keys are reported by
``tools/quest_lint.py`` (keeps writer edits, prunes dead keys,
scaffolds new step titles/descriptions). The
``SPACEHACK_TEXT_DIR`` env var overrides the overlay directory (used by
tests and for pointing at an absolute path).
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

# Registry of shipped runtime.* overlay keys (doc 33 Phase 4):
# validation only — the prose values live solely in the JSON
# overlay (data/text/00_runtime.json). Call sites pass their own
# literal default to get(); a key missing from the shipped overlay
# is caught by tests/test_text_overlay.py.
RUNTIME: frozenset[str] = frozenset({
    "runtime.transmission_title",
    "runtime.transmission_body",
    "runtime.signal_log_static",
    "runtime.signal_log_coordinates",
    "runtime.door_discover_title",
    "runtime.door_discover_meta",
    "runtime.door_discover_body",
    "runtime.door_discover_highlight",
    "runtime.door_discover_log",
    "runtime.door_open_title",
    "runtime.door_open_meta",
    "runtime.door_open_body",
    "runtime.door_open_highlight",
    "runtime.door_open_log",
    "runtime.door_open_log2",
    "runtime.door_gapes_log",
    "runtime.door_holds_log",
    "runtime.chip_fragment_log",
    "runtime.door_ambush_title",
    "runtime.door_ambush_faction",
    "runtime.door_ambush_body",
    "runtime.quest_gated_title",
    "runtime.quest_gated_fallback",
    "runtime.quest_departure_title",
    "runtime.quest_departure_body",
    "runtime.quest_complete_log",
    "runtime.quest_reward_log",
    "runtime.quest_goods_log",
    "runtime.quest_prison_start_log",
    "runtime.prison.facility_faction",
    "runtime.prison.security_faction",
    "runtime.prison.floor1_name",
    "runtime.prison.floor2_name",
    "runtime.prison.floor3_name",
    "runtime.prison.floor4_name",
    "runtime.prison.floor5_name",
    "runtime.prison.entry_f1_title",
    "runtime.prison.entry_f1_message",
    "runtime.prison.entry_f2_title",
    "runtime.prison.entry_f2_message",
    "runtime.prison.entry_f3_title",
    "runtime.prison.entry_f3_message",
    "runtime.prison.entry_f4_title",
    "runtime.prison.entry_f4_message",
    "runtime.prison.entry_f5_title",
    "runtime.prison.entry_f5_message",
    "runtime.prison.event.prison_ascent_f1_sentries.title",
    "runtime.prison.event.prison_ascent_f1_sentries.message",
    "runtime.prison.event.prison_ascent_f1_final_lockdown.title",
    "runtime.prison.event.prison_ascent_f1_final_lockdown.message",
    "runtime.prison.event.prison_floor1_security_alpha.title",
    "runtime.prison.event.prison_floor1_security_alpha.message",
    "runtime.prison.event.prison_floor1_security_beta.title",
    "runtime.prison.event.prison_floor1_security_beta.message",
    "runtime.prison.event.prison_ascent_f2_assault.title",
    "runtime.prison.event.prison_ascent_f2_assault.message",
    "runtime.prison.event.prison_ascent_f2_sentries.title",
    "runtime.prison.event.prison_ascent_f2_sentries.message",
    "runtime.prison.event.prison_ascent_f3_sentries.title",
    "runtime.prison.event.prison_ascent_f3_sentries.message",
    "runtime.prison.event.prison_ascent_f3_heavy.title",
    "runtime.prison.event.prison_ascent_f3_heavy.message",
    "runtime.prison.event.prison_ascent_f4_lockdown.title",
    "runtime.prison.event.prison_ascent_f4_lockdown.message",
    "runtime.prison.engineering_name",
    "runtime.prison.engineering_popup_title",
    "runtime.prison.engineering_popup_message",
    "runtime.prison.elevator_name",
    "runtime.prison.descent_log",
    "runtime.prison.data_terminal_name",
    "runtime.prison.data_popup_title",
    "runtime.prison.data_popup_message",
    "runtime.prison.security_spawned_log",
    "runtime.prison.security_no_deploy_log",
    "runtime.prison.interface_unresponsive",
    "runtime.prison.interaction_already_active",
    "runtime.prison.interaction_offline",
    "runtime.prison.elevator_refuses",
    "runtime.prison.elevator_descends",
    "runtime.prison.interaction_activated",
    "runtime.prison.data_extracted",
    "runtime.prison.dead_terminal_name",
    "runtime.prison.dead_terminal_flavor_1",
    "runtime.prison.dead_terminal_flavor_2",
    "runtime.prison.dead_terminal_flavor_3",
    "runtime.prison.dead_terminal_flavor_4",
    "runtime.prison.dead_terminal_flavor_5",
    "runtime.prison.leave_orbit_log",
    "runtime.summon_title",
    "runtime.gate_popup_default_title",
    "runtime.smuggle_loaded_log",
    "runtime.smuggle_handover_log",
    "runtime.smuggle_lost_summon",
    "runtime.smuggle_lost_log",
    "runtime.smuggle_resecured_log",
    "runtime.no_ship_log",
    "runtime.goods_handed_over_log",
    "runtime.missing_goods_log",
    "runtime.chain_lockin_log",
    "runtime.readout_wait_hint",
    "runtime.orbit_title",
    "runtime.orbit_body_intro",
    "runtime.orbit_body_route",
    "runtime.orbit_faction_militia",
    "runtime.orbit_faction_merchants",
    "runtime.orbit_faction_bar",
    "runtime.orbit_faction_lab",
    "runtime.orbit_faction_unknown",
    "runtime.epilogue_option_deliver",
    "runtime.epilogue_option_keep",
    "runtime.epilogue_delivered_log",
    "runtime.epilogue_kept_log",
    "runtime.epilogue_kept_title",
    "runtime.epilogue_kept_body",
    "runtime.perk_gained_log",
})


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
    return default


def reload() -> None:
    """Re-parse the overlay files (dev-mode F5 hot reload)."""
    global _overlay
    _overlay = _load()
