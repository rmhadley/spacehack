"""Resolver tests for the rumor domain (doc 42 phases 1-3).

The resolvers are ctx-free: floors read whatever resolved sheet the
host passes, so LIVE / SPOOFED / DARK behavior is pinned here at the
resolver contract level. One ask surface since the playtest-round-1
ruling: askable_topics lists unheard openers AND heard-chain
extensions; the main menu carries a single Ask around row. Phase 3:
sources are planet-scoped candidates and the routing map is an
explicit pure input. The live catalog (dark_berth) authors no gates,
so the gate contracts ride the fixture registry
(tests.support.rumor_fixture).
"""

from types import SimpleNamespace

from spacehack import rumor
from tests.support.rumor_fixture import install


def _no_traits():
    return frozenset()


# --- the ask surface (openers + extensions in one sub-menu) ---------------


def test_no_chain_is_askable_at_spawn():
    # Doc 42 phase 2.5: tier 1 is trigger-delivered (no sources) —
    # no contact anywhere opens the chain by asking.
    for _npc in ("wolf_barkeep", "deadfall_scrubber", "barkeep"):
        assert rumor.askable_topics([], {}, _no_traits(), _npc, "wolf_b") == []


def test_extensions_offer_the_next_tier_on_the_carrier_planet():
    _rows = dict(rumor.askable_topics(
        ["dark_berth_1"], {}, _no_traits(), "wolf_barkeep", "wolf_b"))
    assert _rows == {"dark ports": "dark_berth_2"}


def test_wrong_planet_never_delivers():
    # The wolf seats on wolf_b — on any other planet's map his row
    # is absent (the candidate is planet-scoped, SETTLED 15).
    assert rumor.askable_topics(
        ["dark_berth_1"], {}, _no_traits(), "wolf_barkeep", "lal_b") == []


def test_openers_and_extensions_coexist_in_one_submenu(monkeypatch):
    # One teller can extend a heard chain AND open another — both rows
    # list together. The live catalog's single linear chain can't shape
    # this any more, so it rides the fixture registry.
    install(monkeypatch)
    _rows = dict(rumor.askable_topics(
        ["gate_probe_1"], {}, _no_traits(), "blockade_officer", "blockade_south"))
    # The extension row carries the heard tier's label.
    assert _rows == {"side probe 1": "side_probe_1",
                     "gate probe 1": "gate_probe_2"}


def test_askable_topics_only_for_contacts_who_deliver():
    # The chain exhausted: the scrubber (a tier-2 carrier) holds
    # nothing further once every tier is heard.
    assert rumor.askable_topics(
        ["dark_berth_1", "dark_berth_2", "dark_berth_3", "dark_berth_4"],
        {},
        _no_traits(),
        "deadfall_scrubber",
        "lal_b",
    ) == []


def test_non_source_npc_gets_nothing():
    assert rumor.askable_topics(
        [], {}, _no_traits(), "guild_master", "earth") == []


# --- the routing map (phase 3 seam) ----------------------------------------


def test_live_map_filters_candidates():
    _all = dict(rumor.askable_topics(
        ["dark_berth_1"], {}, _no_traits(), "deadfall_scrubber", "lal_b"))
    assert _all == {"dark ports": "dark_berth_2"}
    # The scrubber's pair is not live this run — no row.
    _dark = rumor.askable_topics(
        ["dark_berth_1"], {}, _no_traits(), "deadfall_scrubber", "lal_b",
        live={"dark_berth_2": frozenset({("wolf_barkeep", "wolf_b")})},
    )
    assert _dark == []
    # The live pair delivers.
    _wolf = rumor.askable_topics(
        ["dark_berth_1"], {}, _no_traits(), "wolf_barkeep", "wolf_b",
        live={"dark_berth_2": frozenset({("wolf_barkeep", "wolf_b")})},
    )
    assert _wolf == [("dark ports", "dark_berth_2")]


# --- gate contracts (fixture registry; the live chain authors none) -------


def test_askable_topics_honor_floors(monkeypatch):
    install(monkeypatch)
    # Hostile militia: the opener is withheld entirely.
    assert rumor.askable_topics(
        [], {"militia": -5}, _no_traits(), "blockade_officer", "blockade_south"
    ) == []
    # Neutral sheet: openers surface; below-floor rep hides extensions.
    assert rumor.askable_topics(
        [], {"militia": 0}, _no_traits(), "blockade_officer", "blockade_south"
    ) == [("gate probe 1", "gate_probe_1"), ("side probe 1", "side_probe_1")]
    assert rumor.askable_topics(
        ["gate_probe_1"], {"militia": -5}, _no_traits(),
        "blockade_officer", "blockade_south",
    ) == []
    assert rumor.askable_topics(
        ["gate_probe_1"], {"militia": 0}, _no_traits(),
        "blockade_officer", "blockade_south",
    ) == [("side probe 1", "side_probe_1"), ("gate probe 1", "gate_probe_2")]


def test_spoofed_sheet_clears_a_floor_the_true_sheet_does_not(monkeypatch):
    # The resolver reads the sheet it is GIVEN (the resolved one) — a
    # worn face at militia liked passes where the true hostile sheet
    # would not. Hosts must pass identity.effective_reputation(ctx).
    install(monkeypatch)
    _spoofed = dict(rumor.askable_topics(
        [], {"militia": 30}, _no_traits(), "blockade_officer", "blockade_south"))
    _true = dict(rumor.askable_topics(
        [], {"militia": -40}, _no_traits(), "blockade_officer", "blockade_south"))
    assert "gate_probe_1" in _spoofed.values()
    assert _true == {}


def test_dark_reads_neutral(monkeypatch):
    # DARK: effective_reputation returns {} — every faction reads 0.
    # Neutral floors pass; the trait-gated captain still refuses.
    install(monkeypatch)
    _rows = dict(rumor.askable_topics(
        ["gate_probe_1", "gate_probe_2"], {}, _no_traits(),
        "militia_captain", "earth"))
    assert _rows == {}
    _rows = dict(rumor.askable_topics(
        [], {}, _no_traits(), "blockade_officer", "blockade_south"))
    assert "gate_probe_1" in _rows.values()


def test_trait_gate_demands_the_trait(monkeypatch):
    # The captain's tier is trait-gated, pinned on askable_topics.
    install(monkeypatch)
    assert rumor.askable_topics(
        ["gate_probe_1", "gate_probe_2"],
        {"militia": 50},
        _no_traits(),
        "militia_captain",
        "earth",
    ) == []
    assert rumor.askable_topics(
        ["gate_probe_1", "gate_probe_2"],
        {"militia": 50},
        frozenset({"warrant_license"}),
        "militia_captain",
        "earth",
    ) == [("gate probe 2", "gate_probe_3")]


# --- text resolvers -------------------------------------------------------


def test_witness_override_and_canonical_fallback():
    # The live chain authors no witness keys (canonical text only) —
    # the fallback path is the live data; the override path rides
    # prose data tests.
    assert rumor.witness_text(
        "dark_berth_2", "wolf_barkeep"
    ) == rumor.entry_text("dark_berth_2")


def test_topic_labels_resolve_from_the_overlay():
    assert rumor.topic_label("dark_berth_2") == "dark ports"


def test_known_entries_preserve_heard_order():
    _entries = rumor.known_entries(["dark_berth_3", "dark_berth_1"])
    assert [entry.id for entry in _entries] == ["dark_berth_3", "dark_berth_1"]


def test_stale_ids_are_skipped_not_raised():
    # A rumor id removed from the catalog must never crash a render
    # path on an old save — knowledge fades, the game doesn't fall
    # over. derelict_line_1 shipped in phase 1 and retired with the
    # one-chain ruling. A stale id satisfies no requires link — only
    # the real heard opener opens the extension.
    _entries = rumor.known_entries(["derelict_line_1", "dark_berth_1"])
    assert [entry.id for entry in _entries] == ["dark_berth_1"]
    assert rumor.askable_topics(
        ["derelict_line_1"], {}, _no_traits(), "deadfall_scrubber", "lal_b",
    ) == []
    _rows = dict(rumor.askable_topics(
        ["derelict_line_1", "dark_berth_1"], {}, _no_traits(),
        "deadfall_scrubber", "lal_b",
    ))
    assert _rows == {"dark ports": "dark_berth_2"}


# --- the keyring mutation -------------------------------------------------


def test_hear_is_idempotent_and_ordered():
    ctx = SimpleNamespace(known_rumors=[])
    assert rumor.hear(ctx, "dark_berth_1") is True
    assert rumor.hear(ctx, "dark_berth_2") is True
    assert rumor.hear(ctx, "dark_berth_1") is False
    assert ctx.known_rumors == ["dark_berth_1", "dark_berth_2"]


def test_hear_rejects_unknown_ids():
    import pytest

    ctx = SimpleNamespace(known_rumors=[])
    with pytest.raises(KeyError):
        rumor.hear(ctx, "not_a_rumor")
