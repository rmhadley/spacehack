#!/usr/bin/env python3
"""Extract the main quest's Act 0 story text into editable .txt files.

Reads the live data catalogs (main quest steps + NPC flavor) and the
hand-mapped runtime strings in ``main_quest/_act0.py`` / ``_core.py`` /
``_dialogue.py`` / ``_objectives.py``, then writes six plain-text files
under ``docs/writing/act0/`` that a writer can edit freely.

Each block is keyed (``### <key> — <label>``) so a later sync pass can
write edits back into the Python source. Text is normalized for output:
line wrapping and indentation are cosmetic, blank lines separate
paragraphs, and the keys are stable paths into the game data
(``step.<id>.<field>``, ``step.<id>.dialogue.<npc>.<variant>``,
``npc.<id>.flavor_text``, ``runtime.<name>``).

Usage: ``python3 tools/extract_act0_text.py``
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src.spacehack.data.main_quest import find_main_quest_step  # noqa: E402
from src.spacehack.data.npcs import find_npc  # noqa: E402

OUT_DIR = ROOT / "docs" / "writing" / "act0"

_DIALOGUE_VARIANTS: tuple[tuple[str, str], ...] = (
    ("intro", "intro (before the step is accepted)"),
    ("active", "active (while the step is in progress)"),
    ("complete", "complete (after the step is done)"),
    ("locked", "locked (another faction was chosen)"),
    ("option_label", "menu option row"),
)

# ---------------------------------------------------------------------------
# Runtime strings — hand-mapped from main_quest/_act0.py, _core.py,
# _dialogue.py, _objectives.py. (file, fragment) lets a future sync pass
# locate the literal in the source; fragment is the first ~40 chars.
# ---------------------------------------------------------------------------

_RUNTIME: dict[str, tuple[str, str, str]] = {
    # --- The signal (file 1) ---
    "runtime.transmission_title": (
        "_act0.py", "title=\"INCOMING TRANSMISSION\"",
        "INCOMING TRANSMISSION overlay title",
    ),
    "runtime.transmission_body": (
        "_act0.py", "body=\"A burst of coordinates cuts through the static",
        "signal transmission body",
    ),
    "runtime.signal_log_static": (
        "_act0.py", "STATIC... a garbled transmission cuts through the noise.",
        "log line when the signal fires",
    ),
    "runtime.signal_log_coordinates": (
        "_act0.py", "A burst of coordinates cuts through the static, followed by a second pattern",
        "log line with the resolved coordinates",
    ),
    # --- The sealed door (file 1) ---
    "runtime.door_discover_title": (
        "_act0.py", "\"title\": \"SEALED ENTRANCE\"",
        "SEALED ENTRANCE overlay title",
    ),
    "runtime.door_discover_meta": (
        "_act0.py", "\"meta\": \"MAKE: ALIEN",
        "SEALED ENTRANCE overlay meta line",
    ),
    "runtime.door_discover_body": (
        "_act0.py", "\"body\": (",
        "SEALED ENTRANCE overlay body",
    ),
    "runtime.door_discover_highlight": (
        "_act0.py", "\"highlight\": \"It will not open with any human tool.\"",
        "SEALED ENTRANCE overlay highlight",
    ),
    "runtime.door_discover_instruction": (
        "_act0.py", "\"instruction\": \"Press ENTER to acknowledge\"",
        "SEALED ENTRANCE overlay instruction",
    ),
    "runtime.door_discover_log": (
        "_act0.py", "A door of alien make, set into the red dust. No visible",
        "log line when the door is discovered",
    ),
    # --- Choosing a route (file 1) ---
    "runtime.chain_lockin_log": (
        "_dialogue.py", "You've agreed to work with the",
        "log line when a faction chain is locked in ({faction} is filled in)",
    ),
    # --- Shared system text (file 1) ---
    "runtime.summon_title": (
        "_act0.py", "title=\"INCOMING MESSAGE\"",
        "INCOMING MESSAGE overlay title (quest summons)",
    ),
    "runtime.gate_popup_default_title": (
        "_act0.py", "title: str = \"THE WORK BEGINS\"",
        "default title for time-gate popups",
    ),
    "runtime.smuggle_loaded_log": (
        "_core.py", "loaded into your mission hold. Deliver it to",
        "log line when a quest crate loads ({good} is filled in)",
    ),
    "runtime.smuggle_handover_log": (
        "_core.py", "The crate is handed over.",
        "log line when a quest crate is handed over",
    ),
    "runtime.smuggle_lost_log": (
        "_objectives.py", "The crate is lost. Talk to the quest giver for another",
        "log line when a hot crate is confiscated",
    ),
    "runtime.smuggle_resecured_log": (
        "_objectives.py", "is re-secured in your mission hold.",
        "log line when a story crate auto-reloads ({good} is filled in)",
    ),
    "runtime.no_ship_log": (
        "_core.py", "You don't have a ship to carry the crate.",
        "log line when a crate can't load without a ship",
    ),
    "runtime.mission_log_full": (
        "_core.py", "Your mission log is full",
        "log line when the mission log is full ({max} is filled in)",
    ),
    "runtime.goods_handed_over_log": (
        "_core.py", "The required goods are handed over.",
        "log line when required goods are consumed",
    ),
    "runtime.missing_goods_log": (
        "_dialogue.py", "You don't have the required goods for this task.",
        "log line when required goods are missing",
    ),
    # --- The door opens (file 6) ---
    "runtime.door_open_title": (
        "_act0.py", "\"title\": \"THE SEAL GIVES WAY\"",
        "THE SEAL GIVES WAY overlay title",
    ),
    "runtime.door_open_meta": (
        "_act0.py", "\"meta\": \"SEAL: BROKEN",
        "THE SEAL GIVES WAY overlay meta line",
    ),
    "runtime.door_open_body": (
        "_act0.py", "\"body\": (",
        "THE SEAL GIVES WAY overlay body",
    ),
    "runtime.door_open_highlight": (
        "_act0.py", "\"highlight\": \"The entrance is open.",
        "THE SEAL GIVES WAY overlay highlight",
    ),
    "runtime.door_open_instruction": (
        "_act0.py", "\"instruction\": \"Press ENTER to continue\"",
        "THE SEAL GIVES WAY overlay instruction",
    ),
    "runtime.door_open_log_1": (
        "_act0.py", "The seal gives way. Inside: an empty cell built for something enormous -",
        "log line when the door opens",
    ),
    "runtime.door_open_log_2": (
        "_act0.py", "The entrance is open. Beyond it, the facility descends into darkness.",
        "log line after the door opens",
    ),
    "runtime.door_already_open_log": (
        "_act0.py", "The opened entrance gapes dark and empty.",
        "log line when bumping the already-open door",
    ),
    "runtime.door_locked_log": (
        "_act0.py", "The sealed door holds fast. It needs a tool you don't have.",
        "log line when bumping the door without a tool",
    ),
    "runtime.bump_chip_log": (
        "_core.py", "You chip a fragment of the alien material off the door's",
        "log line when chipping the lab sample from the door",
    ),
    "runtime.ambush_title": (
        "_act0.py", "\"AMBUSH!\"",
        "AMBUSH! popup title (lab route, door room)",
    ),
    "runtime.ambush_body": (
        "_act0.py", "Raiders pour out of the shadows around the sealed",
        "ambush popup body (lab route, door room)",
    ),
    "runtime.act1_start_log": (
        "_act0.py", "[MAIN QUEST] Act 1: The Prison Below - descend the facility.",
        "log line when the prison descent starts",
    ),
}

# ---------------------------------------------------------------------------
# File assembly
# ---------------------------------------------------------------------------

_NPC_NAMES: dict[str, str] = {}


def _npc_name(npc_id: str) -> str:
    if npc_id not in _NPC_NAMES:
        try:
            _NPC_NAMES[npc_id] = find_npc(npc_id).name
        except KeyError:
            _NPC_NAMES[npc_id] = npc_id
    return _NPC_NAMES[npc_id]


def _normalize(text: str) -> str:
    """Collapse whitespace within paragraphs; keep blank-line breaks."""
    _paras = [re.sub(r"\s+", " ", _p).strip() for _p in text.split("\n\n")]
    return "\n\n".join(_p for _p in _paras if _p)


def _write_block(out, key: str, label: str, text: str) -> None:
    out.write(f"### {key} — {label}\n")
    out.write(_normalize(text))
    out.write("\n\n")


# Steps whose ``description`` is catalog-only: the step is started and
# completed in the same instant it triggers (e.g. the signal fires and
# auto-completes), so the quest-log breadcrumb never renders it. The
# player-visible text for these beats lives in the overlay/log runtime
# blocks instead.
_HIDDEN_DESCRIPTIONS: frozenset[str] = frozenset({"prologue_signal"})


def _write_step(out, step_id: str) -> None:
    """Write one step's blocks in narrative order."""
    _step = find_main_quest_step(step_id)
    _write_block(out, f"step.{step_id}.title", "TITLE", _step.title)
    _desc_label = (
        "DESCRIPTION — NOT SHOWN IN-GAME (step auto-completes on trigger; "
        "the overlay + log lines below carry this beat)"
        if step_id in _HIDDEN_DESCRIPTIONS
        else "DESCRIPTION"
    )
    _write_block(out, f"step.{step_id}.description", _desc_label, _step.description)
    for _npc_id, _dialogue in _step.dialogues.items():
        _who = _npc_name(_npc_id)
        for _variant, _label in _DIALOGUE_VARIANTS:
            _text = getattr(_dialogue, _variant, "")
            if not _text:
                continue
            _write_block(
                out,
                f"step.{step_id}.dialogue.{_npc_id}.{_variant}",
                f"DIALOGUE ({_who}) {_label}",
                _text,
            )
    if _step.completion_flavor:
        _write_block(
            out, f"step.{step_id}.completion_flavor",
            "COMPLETION FLAVOR (what happens when this step is done)",
            _step.completion_flavor,
        )
    if _step.ready_message:
        _write_block(
            out, f"step.{step_id}.ready_message",
            "READY MESSAGE (the summons that begins this step)",
            _step.ready_message,
        )


def _write_npc_flavor(out, npc_id: str) -> None:
    try:
        _npc = find_npc(npc_id)
    except KeyError:
        return
    _write_block(
        out, f"npc.{npc_id}.flavor_text",
        f"NPC FLAVOR ({_npc.name}) — idle chatter when not on a quest",
        _npc.flavor_text,
    )


def _runtime_text(key: str) -> str:
    """Return the current value for a runtime key (matches the source)."""
    _texts = {
        "runtime.transmission_title": "INCOMING TRANSMISSION",
        "runtime.transmission_body": (
            "Comms lights up with a strange signal. It's mostly noise and "
            "static. But through the incomprehensible chatter the systems "
            "detect a pattern. Coordinates that appear to pointing to a "
            "remote part of Mars in Sol."
        ),
        "runtime.signal_log_static": (
            "STATIC... a garbled transmission cuts through the noise."
        ),
        "runtime.signal_log_coordinates": (
            "Your ship crunches the data and outputs coordinates on mars."
        ),
        "runtime.door_discover_title": "SEALED ENTRANCE",
        "runtime.door_discover_meta": "MAKE: ALIEN    MECHANISM: NONE VISIBLE    AGE: UNKNOWN",
        "runtime.door_discover_body": (
            "The martian rock merges with high tech metal machinery.\n"
            "You see a wall that undulates before you as you examine it.\n"
            "An alien console stands before it, still with power.\n"
            "But a mystery you can't solve alone."
        ),
        "runtime.door_discover_highlight": "The console just hums and ignores your input.",
        "runtime.door_discover_instruction": "Press ENTER to acknowledge",
        "runtime.door_discover_log": (
            "An undulating wall of alien make, set into the red dust."
        ),
        "runtime.chain_lockin_log": (
            "You've agreed to work with the {faction} - the plan is in motion."
        ),
        "runtime.summon_title": "INCOMING MESSAGE",
        "runtime.gate_popup_default_title": "THE WORK BEGINS",
        "runtime.smuggle_loaded_log": (
            "{good} loaded into your mission hold. Deliver it to complete the job."
        ),
        "runtime.smuggle_handover_log": "The crate is handed over.",
        "runtime.smuggle_lost_log": (
            "The crate is lost. Talk to the quest giver for another one."
        ),
        "runtime.smuggle_resecured_log": (
            "The {good} is re-secured in your mission hold."
        ),
        "runtime.no_ship_log": "You don't have a ship to carry the crate.",
        "runtime.mission_log_full": (
            "Your mission log is full ({max}/{max}). Abandon one first (Q)."
        ),
        "runtime.goods_handed_over_log": "The required goods are handed over.",
        "runtime.missing_goods_log": (
            "You don't have the required goods for this task."
        ),
        "runtime.door_open_title": "THE SEAL GIVES WAY",
        "runtime.door_open_meta": "SEAL: BROKEN    CHAMBER: EMPTY    ACCESS: GRANTED",
        "runtime.door_open_body": (
            "The seal gives way - cleanly, as if it were waiting.\n"
            "Inside: an empty cell built for something enormous -\n"
            "and a dark terminal interface waiting for input."
        ),
        "runtime.door_open_highlight": (
            "The entrance is open. The way forward leads deeper into the facility."
        ),
        "runtime.door_open_instruction": "Press ENTER to continue",
        "runtime.door_open_log_1": (
            "The seal gives way. Inside: an empty cell built for something "
            "enormous - and a dark terminal interface waiting to be accessed."
        ),
        "runtime.door_open_log_2": (
            "The entrance is open. Beyond it, the facility descends into darkness."
        ),
        "runtime.door_already_open_log": "The opened entrance gapes dark and empty.",
        "runtime.door_locked_log": (
            "The sealed door holds fast. It needs a tool you don't have."
        ),
        "runtime.bump_chip_log": (
            "You chip a fragment of the alien material off the door's surface. "
            "The seal holds."
        ),
        "runtime.ambush_title": "AMBUSH!",
        "runtime.ambush_body": (
            "Raiders pour out of the shadows around the sealed door - they "
            "were watching the dig site, waiting for someone to come back "
            "for the sample. They want it."
        ),
        "runtime.act1_start_log": (
            "[MAIN QUEST] Act 1: The Prison Below - descend the facility."
        ),
    }
    return _texts[key]


def _write_runtime_block(out, key: str) -> None:
    _file, _fragment, _label = _RUNTIME[key]
    _write_block(
        out, key, f"RUNTIME — {_label} (main_quest/{_file})", _runtime_text(key),
    )


_FORMAT_FULL = """\
# FORMAT: each block starts with a header line "### <key> — <label>". The text
# below it (until the next "###" header or end of file) is the value.
#
#   * Edit the text freely - line wrapping and indentation are ignored.
#   * Blank lines between paragraphs are preserved (they become \\n\\n in-game).
#   * "###" keys are stable paths into the game data; do NOT rename them.
#     To remove text, delete the whole block (header + body).
#   * {placeholders} like {faction} or {good} are filled in by the game -
#     keep them exactly as written.
#
# To sync your edits back into the game, tell Buffy: "sync the act 0 text".
"""


def _write_header(out, title: str, flow: str, full_format: bool) -> None:
    out.write("# =============================================================================\n")
    out.write(f"# {title}\n")
    out.write("# =============================================================================\n")
    out.write("# EDITABLE STORY TEXT - extracted from the live game data by\n")
    out.write("# tools/extract_act0_text.py. Re-running that script regenerates this file.\n")
    out.write("#\n")
    if full_format:
        out.write(_FORMAT_FULL)
    else:
        out.write("# FORMAT: blocks start with \"### <key> — <label>\"; see 01_beginning.txt\n")
        out.write("# for the full spec. Edit text freely; keep the \"###\" keys intact.\n")
    out.write("#\n")
    out.write(f"# FLOW: {flow}\n")
    out.write("# =============================================================================\n")
    out.write("\n")


def _build_beginning(out) -> None:
    _write_header(
        out,
        "ACT 0 - BEGINNING (shared prologue: signal, Mars door, choosing a route)",
        "prologue_signal -> prologue_mars_unlocked -> prologue_mars_entrance -> "
        "prologue_seek_help (choose ONE route: bar / merchants / lab / militia) "
        "-> [your chain, files 02-05] -> prologue_open (file 06)",
        full_format=True,
    )
    out.write("# --- The Signal ---\n\n")
    for _sid in ("prologue_signal", "prologue_mars_unlocked", "prologue_mars_entrance"):
        _write_step(out, _sid)
    out.write("# --- The transmission scene ---\n\n")
    for _key in (
        "runtime.transmission_title",
        "runtime.transmission_body",
        "runtime.signal_log_static",
        "runtime.signal_log_coordinates",
    ):
        _write_runtime_block(out, _key)
    out.write("# --- Discovering the sealed door ---\n\n")
    for _key in (
        "runtime.door_discover_title",
        "runtime.door_discover_meta",
        "runtime.door_discover_body",
        "runtime.door_discover_highlight",
        "runtime.door_discover_instruction",
        "runtime.door_discover_log",
    ):
        _write_runtime_block(out, _key)
    out.write("# --- Seek help: the four routes are offered here ---\n\n")
    _write_step(out, "prologue_seek_help")
    _write_runtime_block(out, "runtime.chain_lockin_log")
    out.write("# --- The faction faces (idle chatter) ---\n\n")
    for _npc in ("barkeep", "guild_master", "militia_captain", "research_officer", "xenolinguist"):
        _write_npc_flavor(out, _npc)
    out.write("# --- Shared system text (all routes) ---\n\n")
    for _key in (
        "runtime.summon_title",
        "runtime.gate_popup_default_title",
        "runtime.smuggle_loaded_log",
        "runtime.smuggle_handover_log",
        "runtime.smuggle_lost_log",
        "runtime.smuggle_resecured_log",
        "runtime.no_ship_log",
        "runtime.mission_log_full",
        "runtime.goods_handed_over_log",
        "runtime.missing_goods_log",
    ):
        _write_runtime_block(out, _key)


def _build_chain(out, title: str, step_ids: tuple[str, ...], flavor_npcs: tuple[str, ...]) -> None:
    _flow = " -> ".join((*step_ids, "prologue_open"))
    _write_header(out, title, _flow, full_format=False)
    for _sid in step_ids:
        _write_step(out, _sid)
    if flavor_npcs:
        out.write("# --- The people you meet on this route (idle chatter) ---\n\n")
        for _npc in flavor_npcs:
            _write_npc_flavor(out, _npc)


def _build_end(out) -> None:
    _write_header(
        out,
        "ACT 0 - END (the door opens, the descent, and the first reading)",
        "prologue_open -> act1_prison -> [orbit disclosure] -> research_alpha -> "
        "research_alpha_report",
        full_format=False,
    )
    out.write("# --- The door opens (all routes converge here) ---\n\n")
    _write_step(out, "prologue_open")
    for _key in (
        "runtime.door_open_title",
        "runtime.door_open_meta",
        "runtime.door_open_body",
        "runtime.door_open_highlight",
        "runtime.door_open_instruction",
        "runtime.door_open_log_1",
        "runtime.door_open_log_2",
        "runtime.door_already_open_log",
        "runtime.door_locked_log",
    ):
        _write_runtime_block(out, _key)
    out.write("# --- The lab route's moment at the door (sample chip + ambush) ---\n\n")
    _write_runtime_block(out, "runtime.bump_chip_log")
    _write_runtime_block(out, "runtime.ambush_title")
    _write_runtime_block(out, "runtime.ambush_body")
    out.write("# --- The descent (Act 1 begins on the other side of the door) ---\n\n")
    _write_runtime_block(out, "runtime.act1_start_log")
    _write_step(out, "act1_prison")
    out.write("# --- After the descent: the orbit disclosure (how much you share) ---\n\n")
    from src.spacehack.data.main_quest.act1_post_prison import (  # noqa: E402
        ARCHIVE_DISCLOSURES,
    )
    for _d in ARCHIVE_DISCLOSURES:
        _key = f"disclosure.{_d.key}"
        _write_block(out, f"{_key}.label", "ORBIT CHOICE - menu row", _d.label)
        _write_block(out, f"{_key}.menu_description", "ORBIT CHOICE - help text", _d.menu_description)
        _write_block(out, f"{_key}.log_message", "ORBIT CHOICE - log line", _d.log_message)
        _write_block(out, f"{_key}.followup_message", "ORBIT CHOICE - follow-up line", _d.followup_message)
        if _d.waiting_title:
            _write_block(out, f"{_key}.waiting_title", "ORBIT CHOICE - waiting title", _d.waiting_title)
        if _d.waiting_description:
            _write_block(out, f"{_key}.waiting_description", "ORBIT CHOICE - waiting description", _d.waiting_description)
        if _d.ready_message:
            _write_block(out, f"{_key}.ready_message", "ORBIT CHOICE - ready message", _d.ready_message)
    out.write("# --- The first reading (Alpha Centauri) ---\n\n")
    _write_step(out, "research_alpha")
    _write_step(out, "research_alpha_report")


def main() -> int:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    _builders = {
        "01_beginning.txt": lambda f: _build_beginning(f),
        "02_merchants.txt": lambda f: _build_chain(
            f,
            "ACT 0 - MERCHANTS ROUTE: \"The Contract\" (build the cutter)",
            ("mer_q1_contract", "mer_q2_strike", "mer_q3_transport",
             "mer_q4_calibrate", "mer_q5_cutter"),
            ("salvage_specialist",),
        ),
        "03_bar.txt": lambda f: _build_chain(
            f,
            "ACT 0 - BAR ROUTE: \"The Old Hand\" (build the brute-force rig)",
            ("bar_q1_oldhand", "bar_q2_proof", "bar_q3_rigparts",
             "bar_q4_blackmarket", "bar_q5_charged", "bar_q6_rig"),
            ("old_smuggler", "wolf_barkeep"),
        ),
        "04_lab.txt": lambda f: _build_chain(
            f,
            "ACT 0 - LAB ROUTE: \"The Resonance\" (forge the key)",
            ("lab_q1_sample", "lab_q2_delivery", "lab_q3_reference",
             "lab_q4_xenolinguist", "lab_q5_frequency", "lab_q6_return",
             "lab_q7_key"),
            ("xenolinguist",),
        ),
        "05_militia.txt": lambda f: _build_chain(
            f,
            "ACT 0 - MILITIA ROUTE: \"The Incident\" (build the breach charge)",
            ("mil_q1_report", "mil_q2_cache", "mil_q3_inspection",
             "mil_q4_demolitions", "mil_q5_livefire", "mil_q6_charge"),
            ("blockade_officer", "demolitions_expert"),
        ),
        "06_end.txt": lambda f: _build_end(f),
    }
    _count = 0
    for _name, _build in _builders.items():
        with (OUT_DIR / _name).open("w", encoding="utf-8") as _f:
            _build(_f)
        _n = sum(
            1 for _line in (OUT_DIR / _name).read_text(encoding="utf-8").splitlines()
            if _line.startswith("### ")
        )
        _count += _n
        print(f"{_name}: {_n} blocks")
    print(f"total: {_count} blocks -> {OUT_DIR}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
