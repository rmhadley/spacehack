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

Sync the JSON key set against the code with
``python3 tools/extract_act0_text.py`` (keeps writer edits, prunes dead
keys, scaffolds new step titles/descriptions). The
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
    # --- Quest breadcrumbs + lifecycle logs ---
    "runtime.quest_gated_title": "Awaiting word from the {faction}...",
    "runtime.quest_gated_fallback": (
        "The faction will contact you when they're ready."
    ),
    "runtime.quest_departure_title": "Leave Mars",
    "runtime.quest_departure_body": (
        "Return to your ship and launch from Mars. The recovered archive "
        "is waiting for its first reading."
    ),
    "runtime.quest_sealed_archive_title": "Deliver the sealed archive",
    "runtime.quest_sealed_archive_body": (
        "Take the intact recovered archive to the Research Officer at Alpha "
        "Centauri's Science Port for its first independent reading."
    ),
    "runtime.quest_first_translation_title": "Awaiting the first translation...",
    "runtime.quest_first_translation_body": (
        "The Alpha Centauri processing cluster is separating and translating "
        "the alien archive's layers. Return to the Research Officer when the "
        "first report is ready; the work has no deadline."
    ),
    "runtime.quest_fallback_handoff_title": "Awaiting archive handoff...",
    "runtime.quest_fallback_handoff_body": (
        "The archive handoff is being prepared. Take the recovered archive to "
        "the Research Officer at Alpha Centauri's Science Port for an "
        "independent reading when the summons arrives."
    ),
    "runtime.quest_complete_log": "[MAIN QUEST] {title} - complete.",
    "runtime.quest_reward_log": "+{credits}$ reward.",
    "runtime.quest_goods_log": "{good} x{qty} lashed in your mission hold.",
    "runtime.quest_prison_start_log": (
        "[MAIN QUEST] Act 1: The Prison Below - descend the facility."
    ),
    # --- Mars prison arc ---
    "runtime.prison.facility_faction": "ALIEN FACILITY",
    "runtime.prison.security_faction": "ALIEN SECURITY",
    "runtime.prison.floor1_name": "Prison Intake",
    "runtime.prison.floor2_name": "Prisoner Quarters",
    "runtime.prison.floor3_name": "Defensive Layer",
    "runtime.prison.floor4_name": "High-Risk Containment",
    "runtime.prison.floor5_name": "The Deep Cell",
    "runtime.prison.entry_f1_title": "THE PRISON BELOW",
    "runtime.prison.entry_f1_message": (
        "The stairs descend into a facility built beneath Mars. "
        "The walls are seamless, the air is still, and every "
        "surface suggests a technology humanity never reached. "
        "There are no voices. No prisoners. Only dormant systems "
        "waiting in the dark."
    ),
    "runtime.prison.entry_f2_title": "PRISONER QUARTERS",
    "runtime.prison.entry_f2_message": (
        "The cells begin here. Rows of them, cut seamless into the "
        "rock, every door hanging open. Whatever numbering system "
        "the wardens used, it was not made for human eyes. The "
        "cells are empty. All of them are empty."
    ),
    "runtime.prison.entry_f3_title": "THE DEFENSIVE LAYER",
    "runtime.prison.entry_f3_message": (
        "The architecture changes. The open galleries give way to "
        "barrier lines and firing lanes - this floor was built to "
        "stop whatever the quarters above could not hold. Security "
        "nodes stud every junction, waiting for a signal."
    ),
    "runtime.prison.entry_f4_title": "HIGH-RISK CONTAINMENT",
    "runtime.prison.entry_f4_message": (
        "The cells are larger here. Larger, and fewer. These doors "
        "were not built to hold prisoners - they were built to hold "
        "problems. An engineering lattice hums behind the walls, "
        "and below it all, something deep is still listening."
    ),
    "runtime.prison.entry_f5_title": "THE DEEP CELL",
    "runtime.prison.entry_f5_message": (
        "The elevator opens onto a chamber so vast it swallows "
        "the light. A prison cell built for something enormous - "
        "and the doors that once held it have been torn from "
        "their frames. Terminals dot the floor, dark and silent. "
        "Somewhere in the dark, one of them still answers."
    ),
    "runtime.prison.event.prison_ascent_f1_sentries.title": "SURFACE SECURITY AWAKENS",
    "runtime.prison.event.prison_ascent_f1_sentries.message": (
        "The upper staging floor is no longer dormant. Sentry drones "
        "drop from ceiling rails and cut off the last quiet route "
        "to the Mars surface."
    ),
    "runtime.prison.event.prison_ascent_f1_final_lockdown.title": "TOTAL FACILITY LOCKDOWN",
    "runtime.prison.event.prison_ascent_f1_final_lockdown.message": (
        "Warning glyphs ignite across the walls. Three assault frames "
        "advance through the intake halls - the prison's final "
        "response before it lets you see the sky again."
    ),
    "runtime.prison.event.prison_floor1_security_alpha.title": "SECURITY POWER RISING",
    "runtime.prison.event.prison_floor1_security_alpha.message": (
        "A buried current ripples through the facility. Panels brighten "
        "in the distance, then a dormant security frame unfolds with a "
        "sound like breaking ice. Something is bringing this place back online."
    ),
    "runtime.prison.event.prison_floor1_security_beta.title": "DEEPER SYSTEMS AWAKEN",
    "runtime.prison.event.prison_floor1_security_beta.message": (
        "The lights climb another stage, and the prison's deeper "
        "security lattice answers the first signal. Heavy footsteps "
        "echo through the corridors. Whatever is waking below is "
        "more prepared than the surface systems."
    ),
    "runtime.prison.event.prison_ascent_f2_assault.title": "QUARTERS LOCKDOWN",
    "runtime.prison.event.prison_ascent_f2_assault.message": (
        "The prisoner quarters seal in sequence. Two heavy frames force "
        "their way through the cell blocks as the dormant security grid "
        "learns your route."
    ),
    "runtime.prison.event.prison_ascent_f2_sentries.title": "CELL BLOCK PURSUIT",
    "runtime.prison.event.prison_ascent_f2_sentries.message": (
        "The cell doors flash awake behind you. Sentry drones pour from "
        "the observation posts, driving you toward the upper stairs."
    ),
    "runtime.prison.event.prison_ascent_f3_sentries.title": "DEFENSIVE LATTICE ONLINE",
    "runtime.prison.event.prison_ascent_f3_sentries.message": (
        "The defensive layer wakes in sections. Two sentry drones slide "
        "from the walls and triangulate your position. Every corridor is "
        "becoming a firing lane."
    ),
    "runtime.prison.event.prison_ascent_f3_heavy.title": "DEFENSES ESCALATE",
    "runtime.prison.event.prison_ascent_f3_heavy.message": (
        "The sentries' signal summons something heavier. An assault drone "
        "unfolds in the corridor ahead, sealing the climb with bronze armor "
        "and cutting limbs."
    ),
    "runtime.prison.event.prison_ascent_f4_lockdown.title": "HIGH-RISK LOCKDOWN",
    "runtime.prison.event.prison_ascent_f4_lockdown.message": (
        "The high-risk cells unlock behind you. A heavy security frame tears "
        "itself from a charging cradle and blocks the route upward. The prison "
        "is hunting you now."
    ),
    "runtime.prison.engineering_name": "Engineering Console",
    "runtime.prison.engineering_popup_title": "ENGINEERING POWER RESTORED",
    "runtime.prison.engineering_popup_message": (
        "A buried engineering lattice surges awake. Power flows through the "
        "high-risk quarters, and the deep elevator unlocks below."
    ),
    "runtime.prison.elevator_name": "Deep Elevator",
    "runtime.prison.descent_log": (
        "The cage settles. You are 2 km beneath the Martian dust."
    ),
    "runtime.prison.data_terminal_name": "Data Terminal",
    "runtime.prison.data_popup_title": "DATA STREAM",
    "runtime.prison.data_popup_message": (
        "The terminal floods the cell with light. A torrent of data pours out "
        "- coordinates, schematics, structures built for something far larger "
        "than a human frame. None of it decodes. The data is alien beyond any "
        "human language or logic, but the sheer volume is proof enough: something "
        "was here, and it escaped. Then the dark panels flare white. Emergency "
        "power surges through the facility. The prison is fully awake. The route "
        "back to Mars will not be quiet."
    ),
    "runtime.prison.security_spawned_log": (
        "Security systems online: {count} hostile unit(s) activated."
    ),
    "runtime.prison.security_no_deploy_log": (
        "Security systems online; no deployable unit detected."
    ),
    "runtime.prison.interface_unresponsive": (
        "The alien interface is unresponsive."
    ),
    "runtime.prison.interaction_already_active": "{name} is already active.",
    "runtime.prison.interaction_offline": (
        "{name} is inert. Required systems are offline."
    ),
    "runtime.prison.elevator_refuses": "The elevator refuses to move.",
    "runtime.prison.elevator_descends": (
        "{name} descends into the next secured floor."
    ),
    "runtime.prison.interaction_activated": (
        "{name} activated. The gated system is online."
    ),
    "runtime.prison.data_extracted": (
        "{name}: data extracted. Incomprehensible."
    ),
    "runtime.prison.dead_terminal_name": "Dead Terminal",
    "runtime.prison.dead_terminal_flavor_1": (
        "The terminal is dark. Its screen shows nothing."
    ),
    "runtime.prison.dead_terminal_flavor_2": (
        "The terminal is cold to the touch. Long dead."
    ),
    "runtime.prison.dead_terminal_flavor_3": (
        "The terminal's surface is cracked, its power long gone."
    ),
    "runtime.prison.dead_terminal_flavor_4": (
        "The terminal flickers once, then goes dark."
    ),
    "runtime.prison.dead_terminal_flavor_5": (
        "A dead terminal. Whatever powered these, it has been silent for ages."
    ),
    "runtime.prison.leave_orbit_log": (
        "You leave the prison complex and return to Mars orbit."
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
