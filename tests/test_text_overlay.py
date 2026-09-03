"""Runtime story-text overlay: loader + catalog application.

The game reads writer-facing JSON files (src/spacehack/data/text/)
at startup and overrides the Python story strings with them. These tests
pin the loader semantics (override, fallback, hot reload) and the
baseline hygiene of the shipped JSON (every key resolves to a real
catalog string).
"""

from __future__ import annotations

import importlib.util
import json
import os
from pathlib import Path

import pytest

from src.spacehack import text as text_module
from src.spacehack.data.main_quest import (
    find_main_quest_step,
    list_main_quest_steps,
    main_quest_step_after,
    reload_text_overlay as reload_mq_text,
)
from src.spacehack.data.npcs import (
    find_npc,
    list_npcs,
    reload_text_overlay as reload_npc_text,
)
from src.spacehack.data.trade_goods import (
    find_trade_good,
    reload_text_overlay as reload_goods_text,
)


def _reload_all():
    """Rebuild the text + catalog caches after pointing the overlay."""
    text_module.reload()
    reload_mq_text()
    reload_npc_text()
    reload_goods_text()


def _copy_shipped_text(dest: Path) -> None:
    """Copy the shipped overlay so the JSON-authoritative build has every
    required key before test overrides are layered on top."""
    for _file in Path(text_module._DEFAULT_DIR).glob("*.json"):
        (dest / _file.name).write_bytes(_file.read_bytes())


@pytest.fixture
def overlay_dir(tmp_path, monkeypatch):
    """Temp copy of the shipped text plus a layer of test overrides."""
    _copy_shipped_text(tmp_path)
    # "zz_" sorts after the numbered shipped files, so its keys win.
    (tmp_path / "zz_overrides.json").write_text(
        json.dumps(
            {
                "step.prologue_signal.title": "Overridden Signal",
                "step.prologue_seek_help.dialogue.barkeep.intro": (
                    "Overridden intro."
                ),
                "npc.barkeep.flavor_text": "Overridden flavor.",
                "good.reference_recorder.name": "Overridden Recorder",
                "runtime.transmission_title": "STATIC BURST",
                "runtime.prison.entry_f1_title": "OVERRIDDEN PRISON ENTRY",
                "runtime.prison.floor1_name": "Overridden Prison Floor",
                "disclosure.diagnostic_fragment.label": "Override label",
                "step.lab_q2_delivery.completion_flavor": "Overridden flavor line.",
                "step.lab_q2_delivery.ready_message": "Overridden summon.",
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setenv("SPACEHACK_TEXT_DIR", str(tmp_path))
    _reload_all()
    yield tmp_path
    monkeypatch.delenv("SPACEHACK_TEXT_DIR", raising=False)
    _reload_all()


def test_overlay_overrides_step_text(overlay_dir):
    assert find_main_quest_step("prologue_signal").title == "Overridden Signal"


def test_overlay_overrides_dialogue(overlay_dir):
    _step = find_main_quest_step("prologue_seek_help")
    assert _step.dialogues["barkeep"].intro == "Overridden intro."


def test_overlay_overrides_npc_flavor(overlay_dir):
    assert find_npc("barkeep").flavor_text == "Overridden flavor."


def test_overlay_overrides_good_name(overlay_dir):
    assert find_trade_good("reference_recorder").name == "Overridden Recorder"


def test_missing_title_raises(tmp_path):
    """A step whose title key is absent fails the build loudly instead of
    silently rendering blank text (no more Python prose fallback)."""
    _copy_shipped_text(tmp_path)
    _path = tmp_path / "01_beginning.json"
    _data = json.loads(_path.read_text(encoding="utf-8"))
    del _data["step.prologue_mars_unlocked.title"]
    _path.write_text(json.dumps(_data), encoding="utf-8")
    _old_env = os.environ.get("SPACEHACK_TEXT_DIR")
    os.environ["SPACEHACK_TEXT_DIR"] = str(tmp_path)
    try:
        _reload_all()
        with pytest.raises(ValueError, match="prologue_mars_unlocked"):
            list_main_quest_steps()
    finally:
        if _old_env is None:
            os.environ.pop("SPACEHACK_TEXT_DIR", None)
        else:
            os.environ["SPACEHACK_TEXT_DIR"] = _old_env
        _reload_all()


def test_runtime_get_overrides(overlay_dir):
    assert text_module.get("runtime.transmission_title") == "STATIC BURST"


def test_runtime_get_falls_back_to_shipped_default(overlay_dir):
    assert text_module.get("runtime.summon_title") == "INCOMING MESSAGE"


def test_runtime_get_falls_back_to_literal_default(overlay_dir):
    assert text_module.get("runtime.no_such_key", "fallback") == "fallback"


def test_prison_data_resolves_overlay_text(overlay_dir):
    from src.spacehack.data.dungeon_extensions import find_extension

    _floor = find_extension("mars_alien_prison").floor(1)
    assert _floor.location_name == "Overridden Prison Floor"
    assert _floor.entry_flavor.title == "OVERRIDDEN PRISON ENTRY"
    assert _floor.entry_flavor.message
    _event = _floor.activation_events[0]
    assert _event.faction_label == "ALIEN SECURITY"
    assert _event.title
    _engineering = find_extension("mars_alien_prison").floor(4).interactions[0]
    assert _engineering.name == "Engineering Console"
    assert _engineering.popup_title == "ENGINEERING POWER RESTORED"


def test_overlay_overrides_completion_flavor_and_ready_message(overlay_dir):
    _step = find_main_quest_step("lab_q2_delivery")
    assert _step.completion_flavor == "Overridden flavor line."
    assert _step.ready_message == "Overridden summon."


def test_disclosure_overlay_applies(overlay_dir):
    from src.spacehack.data.main_quest.act1_post_prison import (
        find_archive_disclosure,
    )

    _spec = find_archive_disclosure("diagnostic_fragment")
    assert _spec.label == "Override label"
    assert _spec.log_message  # un-overridden fields keep defaults


def test_extractor_merge_preserves_writer_edits(tmp_path, monkeypatch):
    """Re-running the extractor must never overwrite writer edits.

    Regression: the tool used to regenerate JSON from the code
    defaults, clobbering values the writer had edited in the JSON.
    The merge keeps existing JSON values and only adds new keys /
    prunes keys that no longer exist in the code.
    """
    _script = Path(__file__).resolve().parent.parent / "tools" / "extract_act0_text.py"
    _spec = importlib.util.spec_from_file_location("extract_act0_text", _script)
    assert _spec is not None and _spec.loader is not None
    _mod = importlib.util.module_from_spec(_spec)

    # The script points the overlay at an empty temp dir at import
    # time — save and restore the real env var around it.
    _old_env = os.environ.get("SPACEHACK_TEXT_DIR")
    try:
        _spec.loader.exec_module(_mod)

        _out = tmp_path / "text"
        _out.mkdir()
        # Seed a file with a writer edit (differs from the code
        # default) plus a stale key that no longer exists in the code.
        (_out / "01_beginning.json").write_text(
            json.dumps(
                {
                    "npc.research_officer.flavor_text": "WRITER EDITED FLAVOR",
                    "step.gone_step.title": "stale",
                }
            ),
            encoding="utf-8",
        )

        monkeypatch.setattr(_mod, "OUT_DIR", _out)
        assert _mod.main() == 0

        _merged = json.loads(
            (_out / "01_beginning.json").read_text(encoding="utf-8")
        )
        # Writer edit survives the merge.
        assert _merged["npc.research_officer.flavor_text"] == "WRITER EDITED FLAVOR"
        # Dead key from the seeded file is pruned.
        assert "step.gone_step.title" not in _merged
        # Live code content is added back in.
        assert "step.prologue_signal.title" in _merged
    finally:
        if _old_env is None:
            os.environ.pop("SPACEHACK_TEXT_DIR", None)
        else:
            os.environ["SPACEHACK_TEXT_DIR"] = _old_env
        text_module.reload()


def test_ready_message_only_authored_on_gated_steps():
    """A ready_message summons the player only when a wait gate elapses,

    so it may only be authored on a step that sets a gate (wait_days > 0)
    and has a following step to unlock. A ready_message anywhere else
    can never render — the gate never exists to fire it.
    """
    for _step in list_main_quest_steps():
        _next = main_quest_step_after(_step.id, chain=_step.chain)
        if not _step.ready_message:
            continue
        assert _step.wait_days > 0, (
            f"{_step.id}.ready_message is dead: wait_days == 0, so no gate "
            "ever elapses to summon the player"
        )
        assert _next is not None, (
            f"{_step.id}.ready_message is dead: it has no next step to unlock"
        )


def test_shipped_overlay_keys_resolve():
    """Every shipped overlay key maps to a real catalog string.

    Guards against orphan keys (typos / keys the loader can't apply).
    """
    _known: set[str] = set(text_module.RUNTIME)
    for _step in list_main_quest_steps():
        _known.add(f"step.{_step.id}.title")
        _known.add(f"step.{_step.id}.description")
        _known.add(f"step.{_step.id}.completion_flavor")
        _known.add(f"step.{_step.id}.ready_message")
        _known.add(f"step.{_step.id}.active_description")
        for _npc_id, _dialogue in _step.dialogues.items():
            for _variant in ("intro", "active", "complete", "locked", "option_label"):
                _known.add(f"step.{_step.id}.dialogue.{_npc_id}.{_variant}")
    for _npc in list_npcs():
        _known.add(f"npc.{_npc.id}.flavor_text")
    from src.spacehack.data.trade_goods.core import TRADE_GOODS
    for _g in TRADE_GOODS:
        _known.add(f"good.{_g.id}.name")
        _known.add(f"good.{_g.id}.description")
    from src.spacehack.data.main_quest.act1_post_prison import ARCHIVE_DISCLOSURES

    for _spec in ARCHIVE_DISCLOSURES:
        for _field in (
            "label", "log_message", "followup_message",
            "waiting_title", "waiting_description", "ready_message",
        ):
            _known.add(f"disclosure.{_spec.key}.{_field}")
    _unknown = sorted(set(text_module.overlay()) - _known)
    assert _unknown == []
