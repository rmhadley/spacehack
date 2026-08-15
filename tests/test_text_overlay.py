"""Runtime story-text overlay: loader + catalog application.

The game reads writer-facing JSON files (src/spacehack/data/text/)
at startup and overrides the Python story strings with them. These tests
pin the loader semantics (override, fallback, hot reload) and the
baseline hygiene of the shipped JSON (every key resolves to a real
catalog string).
"""

from __future__ import annotations

import json

import pytest

from src.spacehack import text as text_module
from src.spacehack.data.main_quest import (
    find_main_quest_step,
    list_main_quest_steps,
    reload_text_overlay as reload_mq_text,
)
from src.spacehack.data.npcs import (
    find_npc,
    list_npcs,
    reload_text_overlay as reload_npc_text,
)


@pytest.fixture
def overlay_dir(tmp_path, monkeypatch):
    """Point the overlay at a temp dir and restore the real one after."""
    (tmp_path / "sample.json").write_text(
        json.dumps(
            {
                "step.prologue_signal.title": "Overridden Signal",
                "step.prologue_seek_help.dialogue.barkeep.intro": (
                    "Overridden intro."
                ),
                "npc.barkeep.flavor_text": "Overridden flavor.",
                "runtime.transmission_title": "STATIC BURST",
                "disclosure.diagnostic_fragment.label": "Override label",
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setenv("SPACEHACK_TEXT_DIR", str(tmp_path))
    text_module.reload()
    reload_mq_text()
    reload_npc_text()
    yield tmp_path
    monkeypatch.delenv("SPACEHACK_TEXT_DIR", raising=False)
    text_module.reload()
    reload_mq_text()
    reload_npc_text()


def test_overlay_overrides_step_text(overlay_dir):
    assert find_main_quest_step("prologue_signal").title == "Overridden Signal"


def test_overlay_overrides_dialogue(overlay_dir):
    _step = find_main_quest_step("prologue_seek_help")
    assert _step.dialogues["barkeep"].intro == "Overridden intro."


def test_overlay_overrides_npc_flavor(overlay_dir):
    assert find_npc("barkeep").flavor_text == "Overridden flavor."


def test_missing_key_falls_back_to_default(overlay_dir):
    assert find_main_quest_step("prologue_mars_unlocked").title == "Mars"


def test_runtime_get_overrides(overlay_dir):
    assert text_module.get("runtime.transmission_title") == "STATIC BURST"


def test_runtime_get_falls_back_to_shipped_default(overlay_dir):
    assert text_module.get("runtime.summon_title") == "INCOMING MESSAGE"


def test_runtime_get_falls_back_to_literal_default(overlay_dir):
    assert text_module.get("runtime.no_such_key", "fallback") == "fallback"


def test_disclosure_overlay_applies(overlay_dir):
    from src.spacehack.data.main_quest.act1_post_prison import (
        find_archive_disclosure,
    )

    _spec = find_archive_disclosure("diagnostic_fragment")
    assert _spec.label == "Override label"
    assert _spec.log_message  # un-overridden fields keep defaults


def test_shipped_overlay_keys_resolve():
    """Every shipped overlay key maps to a real catalog string.

    Guards against orphan keys (typos / keys the loader can't apply).
    """
    _known: set[str] = set(text_module.RUNTIME)
    for _step in list_main_quest_steps():
        _known.add(f"step.{_step.id}.title")
        _known.add(f"step.{_step.id}.description")
        for _npc_id, _dialogue in _step.dialogues.items():
            for _variant in ("intro", "active", "complete", "locked", "option_label"):
                _known.add(f"step.{_step.id}.dialogue.{_npc_id}.{_variant}")
    for _npc in list_npcs():
        _known.add(f"npc.{_npc.id}.flavor_text")
    from src.spacehack.data.main_quest.act1_post_prison import ARCHIVE_DISCLOSURES

    for _spec in ARCHIVE_DISCLOSURES:
        for _field in (
            "label", "log_message", "followup_message",
            "waiting_title", "waiting_description", "ready_message",
        ):
            _known.add(f"disclosure.{_spec.key}.{_field}")
    _unknown = sorted(set(text_module.overlay()) - _known)
    assert _unknown == []
