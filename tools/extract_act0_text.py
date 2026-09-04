#!/usr/bin/env python3
"""Sync the story-text JSON files against the main-quest structure.

Story text lives ONLY in the JSON files under ``src/spacehack/data/text/``
— titles, descriptions, completion flavor, and dialogue are the single
source of truth there. The code catalogs are structural (ids, triggers,
rewards, dialogue NPC keys). This tool:

  * keeps every JSON value (writer edits always win),
  * prunes keys whose step / dialogue NPC / NPC / good / runtime key no
    longer exists in the code,
  * scaffolds empty ``step.<id>.title`` / ``step.<id>.description`` keys
    for new steps so the runtime's missing-text check points at them.

It never overwrites a writer's edit.

Usage: ``python3 tools/extract_act0_text.py``
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

# Point the overlay at an empty dir so the non-step catalogs (NPC flavor,
# goods, runtime, disclosure) resolve to their shipped Python defaults
# rather than whatever is currently in the JSON files.
import os  # noqa: E402
import tempfile  # noqa: E402

os.environ["SPACEHACK_TEXT_DIR"] = tempfile.mkdtemp()

from src.spacehack.data.main_quest import list_raw_main_quest_steps  # noqa: E402
from src.spacehack.data.npcs import find_npc  # noqa: E402
from src.spacehack.data.trade_goods.core import TRADE_GOODS  # noqa: E402
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


def _step_namespace(step) -> tuple[set[str], set[str]]:
    """Return (valid_keys, required_keys) for one structural step."""
    _valid = {
        f"step.{step.id}.title",
        f"step.{step.id}.description",
        f"step.{step.id}.completion_flavor",
        f"step.{step.id}.ready_message",
    }
    _required = {f"step.{step.id}.title"}
    if step.description_required:
        _required.add(f"step.{step.id}.description")
    for _npc_id in step.dialogues:
        for _variant in _DIALOGUE_VARIANTS:
            _valid.add(f"step.{step.id}.dialogue.{_npc_id}.{_variant}")
    return _valid, _required


def _npc_fresh(*npc_ids: str) -> dict[str, str]:
    """Flavor-text overlay keys for the given NPCs, from Python defaults."""
    _keys: dict[str, str] = {}
    for _npc_id in npc_ids:
        try:
            _npc = find_npc(_npc_id)
        except KeyError:
            continue
        if _npc.flavor_text:
            _keys[f"npc.{_npc_id}.flavor_text"] = _npc.flavor_text
    return _keys


def _disclosure_fresh() -> dict[str, str]:
    _keys: dict[str, str] = {}
    for _spec in ARCHIVE_DISCLOSURES:
        for _field in _DISCLOSURE_FIELDS:
            _value = getattr(_spec, _field, "")
            if _value:
                _keys[f"disclosure.{_spec.key}.{_field}"] = _value
    return _keys


def _goods_fresh() -> dict[str, str]:
    _keys: dict[str, str] = {}
    for _g in TRADE_GOODS:
        _keys[f"good.{_g.id}.name"] = _g.name
        _keys[f"good.{_g.id}.description"] = _g.description
    return _keys


def _load_existing(path: Path) -> dict[str, str]:
    if not path.is_file():
        return {}
    try:
        _data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}
    return _data if isinstance(_data, dict) else {}


def _merge(path: Path, *, step_ids: tuple[str, ...], fresh: dict[str, str]) -> dict[str, str]:
    """Merge code structure onto an overlay file.

    Step keys are kept when their step (and dialogue NPC) still exists,
    then required ``title``/``description`` keys are scaffolded empty.
    Non-step keys (NPC flavor / goods / runtime / disclosure) follow the
    fresh-from-Python rule: keep writer values, add new keys, prune keys
    removed from the code.
    """
    _existing = _load_existing(path)
    _valid: set[str] = set()
    _required: set[str] = set()
    _by_id = {_s.id: _s for _s in list_raw_main_quest_steps()}
    for _sid in step_ids:
        _step = _by_id[_sid]
        _v, _r = _step_namespace(_step)
        _valid |= _v
        _required |= _r

    _payload: dict[str, str] = {}
    for _key, _value in _existing.items():
        if _key in _valid or _key in fresh:
            _payload[_key] = _value
    for _key, _value in fresh.items():
        _payload.setdefault(_key, _value)
    for _key in sorted(_required):
        _payload.setdefault(_key, "")
    return dict(sorted(_payload.items()))


def main() -> int:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    _sections: dict[str, tuple[tuple[str, ...], dict[str, str]]] = {
        "00_runtime.json": ((), dict(RUNTIME)),
        "01_beginning.json": (
            (
                "prologue_signal",
                "prologue_mars_unlocked",
                "prologue_mars_entrance",
                "prologue_seek_help",
            ),
            # xenolinguist is emitted by the lab chain (04_lab.json) —
            # kept out of here so her flavor_text key isn't written twice.
            _npc_fresh("barkeep", "guild_master", "militia_captain", "research_officer"),
        ),
        "02_merchants.json": (
            (
                "mer_q1_contract",
                "mer_q2_strike",
                "mer_q3_transport",
                "mer_q4_bribe",
                "mer_q5_alloy",
                "mer_q6_survey",
                "mer_q7_cutter",
            ),
            _npc_fresh("depot_attendant", "salvage_specialist"),
        ),
        "03_bar.json": (
            (
                "bar_q1_oldhand",
                "bar_q2_proof",
                "bar_q3_rigparts",
                "bar_q4_blackmarket",
                "bar_q5_charged",
                "bar_q6_rig",
            ),
            _npc_fresh("old_smuggler", "wolf_barkeep"),
        ),
        "04_lab.json": (
            (
                "lab_q1_sample",
                "lab_q2_delivery",
                "lab_q3_reference",
                "lab_q4_xenolinguist",
                "lab_q5_frequency",
                "lab_q6_return",
                "lab_q7_key",
            ),
            _npc_fresh("xenolinguist"),
        ),
        "05_militia.json": (
            (
                "mil_q1_report",
                "mil_q2_cache",
                "mil_q3_inspection",
                "mil_q4_demolitions",
                "mil_q5_livefire",
                "mil_q6_charge",
            ),
            _npc_fresh("blockade_officer", "demolitions_expert"),
        ),
        "06_end.json": (
            (
                "prologue_open",
                "act1_prison",
                "research_alpha",
                "research_alpha_report",
            ),
            _disclosure_fresh(),
        ),
        "07_goods.json": ((), _goods_fresh()),
    }
    _count = 0
    for _name, (_step_ids, _fresh) in _sections.items():
        _payload = _merge(OUT_DIR / _name, step_ids=_step_ids, fresh=_fresh)
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
