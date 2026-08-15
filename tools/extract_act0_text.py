#!/usr/bin/env python3
"""Export the main quest's story text to editable JSON overlay files.

Reads the live data catalogs (main quest steps + dialogue, NPC flavor)
and writes per-section JSON files under ``src/spacehack/data/text/``.
The game loads these files at startup as a runtime text overlay
(:mod:`spacehack.text`): edit a JSON value, relaunch — or press F5 in
dev mode — and the change is in-game without touching any Python.

Keys are stable paths into the game data:

    step.<id>.title
    step.<id>.description
    step.<id>.dialogue.<npc>.intro|active|complete|locked|option_label
    npc.<id>.flavor_text

Run this ONLY when new story content lands in the code: it overwrites
the JSON baseline. Writer edits live in the JSON files themselves.

Usage: ``python3 tools/extract_act0_text.py``
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

# Read the RAW code data, bypassing the runtime text overlay: the
# JSON baseline must mirror the Python authoring, not whatever is
# currently in the JSON (the overlay would otherwise re-inject keys
# that were deleted from the code). Point the overlay at an empty
# dir so lookups fall back to the shipped defaults.
import os  # noqa: E402
import tempfile  # noqa: E402

os.environ["SPACEHACK_TEXT_DIR"] = tempfile.mkdtemp()

from src.spacehack.data.main_quest import find_main_quest_step  # noqa: E402
from src.spacehack.data.npcs import find_npc  # noqa: E402
from src.spacehack.text import RUNTIME  # noqa: E402
from src.spacehack.data.main_quest.act1_post_prison import (  # noqa: E402
    ARCHIVE_DISCLOSURES,
)

OUT_DIR = ROOT / "src" / "spacehack" / "data" / "text"

_DIALOGUE_VARIANTS = ("intro", "active", "complete", "locked", "option_label")

_DISCLOSURE_FIELDS = (
    "label",
    "log_message",
    "followup_message",
    "waiting_title",
    "waiting_description",
    "ready_message",
)


def _step_keys(step_id: str) -> dict[str, str]:
    """Return the non-empty overlay keys for one step."""
    _step = find_main_quest_step(step_id)
    _keys: dict[str, str] = {f"step.{step_id}.title": _step.title}
    if _step.description:
        _keys[f"step.{step_id}.description"] = _step.description
    for _npc_id, _dialogue in _step.dialogues.items():
        for _variant in _DIALOGUE_VARIANTS:
            _text = getattr(_dialogue, _variant, "")
            if _text:
                _keys[f"step.{step_id}.dialogue.{_npc_id}.{_variant}"] = _text
    return _keys


def _npc_flavor_keys(npc_id: str) -> dict[str, str]:
    """Return the flavor-text overlay key for an NPC, if any."""
    try:
        _npc = find_npc(npc_id)
    except KeyError:
        return {}
    if not _npc.flavor_text:
        return {}
    return {f"npc.{npc_id}.flavor_text": _npc.flavor_text}


def _build_beginning() -> dict[str, str]:
    """File 01: signal, Mars door, and the seek-help fork."""
    _keys: dict[str, str] = {}
    for _sid in ("prologue_signal", "prologue_mars_unlocked", "prologue_mars_entrance"):
        _keys.update(_step_keys(_sid))
    _keys.update(_step_keys("prologue_seek_help"))
    for _npc in ("barkeep", "guild_master", "militia_captain", "research_officer", "xenolinguist"):
        _keys.update(_npc_flavor_keys(_npc))
    return _keys


def _build_chain(step_ids: tuple[str, ...], flavor_npcs: tuple[str, ...]) -> dict[str, str]:
    """One faction chain's steps plus its flavor NPCs."""
    _keys: dict[str, str] = {}
    for _sid in step_ids:
        _keys.update(_step_keys(_sid))
    for _npc in flavor_npcs:
        _keys.update(_npc_flavor_keys(_npc))
    return _keys


def _build_end() -> dict[str, str]:
    """File 06: the door opens, the descent, and the first reading."""
    _keys: dict[str, str] = {}
    for _sid in ("prologue_open", "act1_prison", "research_alpha", "research_alpha_report"):
        _keys.update(_step_keys(_sid))
    for _spec in ARCHIVE_DISCLOSURES:
        for _field in _DISCLOSURE_FIELDS:
            _value = getattr(_spec, _field, "")
            if _value:
                _keys[f"disclosure.{_spec.key}.{_field}"] = _value
    return _keys


def _build_runtime() -> dict[str, str]:
    """File 00: runtime overlay text (transmissions, log lines, popups)."""
    return dict(RUNTIME)


def main() -> int:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    _sections = {
        "00_runtime.json": _build_runtime(),
        "01_beginning.json": _build_beginning(),
        "02_merchants.json": _build_chain(
            ("mer_q1_contract", "mer_q2_strike", "mer_q3_transport",
             "mer_q4_calibrate", "mer_q5_cutter"),
            ("salvage_specialist",),
        ),
        "03_bar.json": _build_chain(
            ("bar_q1_oldhand", "bar_q2_proof", "bar_q3_rigparts",
             "bar_q4_blackmarket", "bar_q5_charged", "bar_q6_rig"),
            ("old_smuggler", "wolf_barkeep"),
        ),
        "04_lab.json": _build_chain(
            ("lab_q1_sample", "lab_q2_delivery", "lab_q3_reference",
             "lab_q4_xenolinguist", "lab_q5_frequency", "lab_q6_return",
             "lab_q7_key"),
            ("xenolinguist",),
        ),
        "05_militia.json": _build_chain(
            ("mil_q1_report", "mil_q2_cache", "mil_q3_inspection",
             "mil_q4_demolitions", "mil_q5_livefire", "mil_q6_charge"),
            ("blockade_officer", "demolitions_expert"),
        ),
        "06_end.json": _build_end(),
    }
    _count = 0
    for _name, _keys in _sections.items():
        _payload = {_key: _keys[_key] for _key in sorted(_keys)}
        (OUT_DIR / _name).write_text(
            json.dumps(_payload, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
        _count += len(_payload)
        print(f"{_name}: {len(_payload)} strings")
    print(f"total: {_count} strings -> {OUT_DIR}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
