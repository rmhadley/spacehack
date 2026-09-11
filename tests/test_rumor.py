"""Resolver tests for the rumor domain (doc 42 phase 1).

The resolvers are ctx-free: floors read whatever resolved sheet the
host passes, so LIVE / SPOOFED / DARK behavior is pinned here at the
resolver contract level. One ask surface since the playtest-round-1
ruling: askable_topics lists unheard openers AND heard-chain
extensions; the main menu carries a single Ask around row.
"""

from types import SimpleNamespace

from spacehack import rumor


def _no_traits():
    return frozenset()


# --- the ask surface (openers + extensions in one sub-menu) ---------------


def test_openers_surface_for_their_tellers():
    _rows = dict(rumor.askable_topics([], {}, _no_traits(), "barkeep"))
    assert _rows == {"the derelict line": "derelict_line_1",
                     "the thin month": "thin_month_1"}


def test_openers_stop_once_heard():
    _rows = dict(rumor.askable_topics(
        ["derelict_line_1"], {}, _no_traits(), "barkeep"))
    assert "derelict_line_1" not in _rows.values()
    assert "thin_month_1" in _rows.values()


def test_extensions_offer_the_next_tier():
    _rows = dict(rumor.askable_topics(
        ["derelict_line_1"], {}, _no_traits(), "depot_attendant"))
    # The opener is gone (heard) and the extension replaces it.
    assert _rows == {"the derelict line": "derelict_line_2"}


def test_openers_and_extensions_coexist_across_chains():
    # The wolf operator extends the derelict chain (tier 3) AND opens
    # the dark-berth chain — both rows in one sub-menu.
    _rows = dict(rumor.askable_topics(
        ["derelict_line_1", "derelict_line_2"], {}, _no_traits(), "wolf_barkeep"))
    assert _rows == {"the derelict line": "derelict_line_3",
                     "the dark berths": "dark_berth_1"}


def test_askable_topics_only_for_contacts_who_deliver():
    # The barkeep opened both his chains but extends neither.
    assert rumor.askable_topics(
        ["derelict_line_1", "thin_month_1"], {}, _no_traits(), "barkeep"
    ) == []


def test_askable_topics_empty_when_everything_heard():
    # Exhausted derelict chain + heard dark-berth opener: the wolf
    # operator holds nothing further.
    assert rumor.askable_topics(
        ["derelict_line_1", "derelict_line_2", "derelict_line_3",
         "dark_berth_1"],
        {},
        _no_traits(),
        "wolf_barkeep",
    ) == []


def test_askable_topics_honor_floors():
    # Hostile militia: the opener is withheld entirely.
    assert rumor.askable_topics(
        [], {"militia": -5}, _no_traits(), "blockade_officer"
    ) == []
    # Neutral sheet: opener surfaces; below-floor rep hides extensions.
    assert rumor.askable_topics(
        [], {"militia": 0}, _no_traits(), "blockade_officer"
    ) == [("the thin month", "thin_month_1")]
    assert rumor.askable_topics(
        ["thin_month_1"], {"militia": -5}, _no_traits(), "blockade_officer"
    ) == []
    assert rumor.askable_topics(
        ["thin_month_1"], {"militia": 0}, _no_traits(), "blockade_officer"
    ) == [("the thin month", "thin_month_2")]


def test_spoofed_sheet_clears_a_floor_the_true_sheet_does_not():
    # The resolver reads the sheet it is GIVEN (the resolved one) — a
    # worn face at militia liked passes where the true hostile sheet
    # would not. Hosts must pass identity.effective_reputation(ctx).
    _spoofed = dict(rumor.askable_topics([], {"militia": 30}, _no_traits(), "blockade_officer"))
    _true = dict(rumor.askable_topics([], {"militia": -40}, _no_traits(), "blockade_officer"))
    assert "thin_month_1" in _spoofed.values()
    assert _true == {}


def test_dark_reads_neutral():
    # DARK: effective_reputation returns {} — every faction reads 0.
    # Neutral floors pass, liked floors and trait gates refuse.
    _rows = dict(rumor.askable_topics([], {}, _no_traits(), "blockade_officer"))
    assert "thin_month_1" in _rows.values()
    _rows = dict(rumor.askable_topics([], {}, _no_traits(), "militia_captain"))
    assert _rows == {}


def test_trait_gate_demands_the_trait():
    # The captain's tier is trait-gated, pinned on askable_topics.
    assert rumor.askable_topics(
        ["thin_month_1", "thin_month_2"],
        {"militia": 50},
        _no_traits(),
        "militia_captain",
    ) == []
    assert rumor.askable_topics(
        ["thin_month_1", "thin_month_2"],
        {"militia": 50},
        frozenset({"warrant_license"}),
        "militia_captain",
    ) == [("the thin month", "thin_month_3")]


def test_routing_predicate_filters_rows():
    assert rumor.askable_topics(
        [], {}, _no_traits(), "barkeep", routing=lambda _id: False
    ) == []
    _rows = dict(rumor.askable_topics(
        [], {}, _no_traits(), "barkeep",
        routing=lambda rumor_id: rumor_id != "thin_month_1",
    ))
    assert "thin_month_1" not in _rows.values()
    assert "derelict_line_1" in _rows.values()


def test_non_source_npc_gets_nothing():
    assert rumor.askable_topics([], {}, _no_traits(), "guild_master") == []


# --- text resolvers -------------------------------------------------------


def test_witness_override_and_canonical_fallback():
    _told = rumor.witness_text("thin_month_1", "blockade_officer")
    assert _told == (
        "Rotation is posted duty, not a secret. Three full watches, then "
        "the maintenance month. If you're looking for reasons to run it, "
        "I'm not the one who hands those out."
    )
    assert rumor.witness_text("thin_month_1", "barkeep") == rumor.entry_text(
        "thin_month_1"
    )


def test_topic_labels_resolve_from_the_overlay():
    assert rumor.topic_label("dark_berth_2") == "the dark berths"


def test_known_entries_preserve_heard_order():
    _entries = rumor.known_entries(["thin_month_1", "derelict_line_1"])
    assert [entry.id for entry in _entries] == ["thin_month_1", "derelict_line_1"]


def test_stale_ids_are_skipped_not_raised():
    # A rumor id removed from the catalog must never crash a render
    # path on an old save — knowledge fades, the game doesn't fall over.
    _entries = rumor.known_entries(["retired_rumor", "derelict_line_1"])
    assert [entry.id for entry in _entries] == ["derelict_line_1"]
    # A stale id offers no ghost row; the NPC's real rows are untouched.
    _rows = dict(rumor.askable_topics(
        ["retired_rumor"], {}, _no_traits(), "barkeep"))
    assert _rows == {"the derelict line": "derelict_line_1",
                     "the thin month": "thin_month_1"}


# --- the keyring mutation -------------------------------------------------


def test_hear_is_idempotent_and_ordered():
    ctx = SimpleNamespace(known_rumors=[])
    assert rumor.hear(ctx, "derelict_line_1") is True
    assert rumor.hear(ctx, "thin_month_1") is True
    assert rumor.hear(ctx, "derelict_line_1") is False
    assert ctx.known_rumors == ["derelict_line_1", "thin_month_1"]


def test_hear_rejects_unknown_ids():
    import pytest

    ctx = SimpleNamespace(known_rumors=[])
    with pytest.raises(KeyError):
        rumor.hear(ctx, "not_a_rumor")
