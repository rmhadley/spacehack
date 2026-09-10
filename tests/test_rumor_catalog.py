"""Catalog integrity for the lore chains (doc 42 phase 1).

The catalog is structural and all prose is JSON-single-source, so the
data test is the enforcement: every key present, every reference
resolvable, every ``rumor.*`` key home in exactly one overlay file.
"""

import json
from pathlib import Path

from spacehack.data.lore import RumorEntry, find_rumor, list_rumors
from spacehack.data.npcs import find_npc
from spacehack.data.traits.core import ALL_TRAITS, QUEST_PERKS
from spacehack.text import overlay

_TEXT_DIR = Path(__file__).resolve().parents[1] / "src" / "spacehack" / "data" / "text"
_KNOWN_FACTIONS = {"pirate", "merchant", "civilian", "militia"}


def _rumor_keys_in(path: Path) -> set[str]:
    data = json.loads(path.read_text(encoding="utf-8"))
    return {key for key in data if key.startswith("rumor.")}


def test_ids_unique_and_findable() -> None:
    ids = [entry.id for entry in list_rumors()]
    assert len(ids) == len(set(ids))
    for rumor_id in ids:
        assert isinstance(find_rumor(rumor_id), RumorEntry)


def test_requires_are_same_chain_lower_tier() -> None:
    for entry in list_rumors():
        for required_id in entry.requires:
            required = find_rumor(required_id)
            assert required.chain == entry.chain
            assert required.tier < entry.tier
        if entry.tier > 1:
            assert entry.requires, "non-entry tiers need a requires link"


def test_sources_reference_real_npcs_gates_and_traits() -> None:
    for entry in list_rumors():
        assert entry.sources, "every entry needs at least one source"
        for npc_id, faction, min_standing, trait in entry.sources:
            find_npc(npc_id)
            if faction is None:
                assert min_standing is None
            else:
                assert faction in _KNOWN_FACTIONS
                assert isinstance(min_standing, int)
            if trait is not None:
                assert trait in QUEST_PERKS or any(
                    t.id == trait for t in ALL_TRAITS
                )


def test_every_entry_has_text_and_topic_keys() -> None:
    _text = overlay()
    for entry in list_rumors():
        assert _text.get(f"rumor.{entry.id}.text"), entry.id
        assert _text.get(f"rumor.{entry.id}.topic"), entry.id


def test_witness_keys_belong_to_entry_sources() -> None:
    _text = overlay()
    for entry in list_rumors():
        _source_ids = {source[0] for source in entry.sources}
        for key in _text:
            if key.startswith(f"rumor.{entry.id}.witness."):
                witness_npc = key.rsplit(".", 1)[1]
                assert witness_npc in _source_ids, key
                assert _text.get(key), key


def test_rumor_keys_live_only_in_08_rumors() -> None:
    homes: dict[str, str] = {}
    for path in sorted(_TEXT_DIR.glob("*.json")):
        for key in _rumor_keys_in(path):
            assert key not in homes, (
                f"{key} authored in both {homes[key]} and {path.name}"
            )
            homes[key] = path.name
    assert homes, "the rumor overlay is empty"
    for key in homes:
        assert homes[key] == "08_rumors.json", key


def test_chain_tiers_are_contiguous() -> None:
    by_chain: dict[str, set[int]] = {}
    for entry in list_rumors():
        by_chain.setdefault(entry.chain, set()).add(entry.tier)
    for chain, tiers in by_chain.items():
        assert tiers == set(range(1, len(tiers) + 1)), chain
