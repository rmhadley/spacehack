"""Resolver tests for the rumor domain (doc 42 phase 1).

The resolvers are ctx-free: floors read whatever resolved sheet the
host passes, so LIVE / SPOOFED / DARK behavior is pinned here at the
resolver contract level.
"""

from types import SimpleNamespace

from spacehack import rumor


def _no_traits():
    return frozenset()


# --- hearing rows ---------------------------------------------------------


def test_tier_one_rows_appear_for_their_tellers():
    _rows = dict(rumor.hearing_rows([], {}, _no_traits(), "barkeep"))
    assert _rows == {
        "Ask about the derelict line": "derelict_line_1",
        "Ask about the thin month": "thin_month_1",
    }


def test_deeper_tiers_never_appear_as_hearing_rows():
    # Host contract (REVIEW round 1): a chain with any heard entry
    # progresses exclusively through Ask Around — hearing rows are
    # chain openers only.
    _rows = dict(
        rumor.hearing_rows(["derelict_line_1"], {}, _no_traits(), "depot_attendant")
    )
    assert _rows == {}
    _topics = rumor.askable_topics(
        ["derelict_line_1"], {}, _no_traits(), "depot_attendant"
    )
    assert _topics == [("the derelict line", "derelict_line_2")]


def test_heard_entries_never_re_row():
    _rows = dict(rumor.hearing_rows(["derelict_line_1"], {}, _no_traits(), "barkeep"))
    assert "derelict_line_1" not in _rows.values()


def test_floor_hides_source_below_standing():
    _rows = dict(
        rumor.hearing_rows([], {"militia": -5}, _no_traits(), "blockade_officer")
    )
    assert _rows == {}
    _rows = dict(
        rumor.hearing_rows([], {"militia": 0}, _no_traits(), "blockade_officer")
    )
    assert "thin_month_1" in _rows.values()


def test_spoofed_sheet_clears_a_floor_the_true_sheet_does_not():
    # The resolver reads the sheet it is GIVEN (the resolved one) — a
    # worn face at militia liked passes where the true hostile sheet
    # would not. Hosts must pass identity.effective_reputation(ctx).
    _spoofed = dict(rumor.hearing_rows([], {"militia": 30}, _no_traits(), "blockade_officer"))
    _true = dict(rumor.hearing_rows([], {"militia": -40}, _no_traits(), "blockade_officer"))
    assert "thin_month_1" in _spoofed.values()
    assert _true == {}


def test_dark_reads_neutral():
    # DARK: effective_reputation returns {} — every faction reads 0.
    # Neutral floors pass, liked floors and trait gates refuse.
    _rows = dict(rumor.hearing_rows([], {}, _no_traits(), "blockade_officer"))
    assert "thin_month_1" in _rows.values()
    _rows = dict(rumor.hearing_rows([], {}, _no_traits(), "militia_captain"))
    assert _rows == {}


def test_trait_gate_demands_the_trait():
    # Tier-3 progression runs exclusively through Ask Around (chain-
    # opener rule), so the trait gate is pinned on askable_topics.
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
    _rows = rumor.hearing_rows(
        [], {}, _no_traits(), "barkeep", routing=lambda _id: False
    )
    assert _rows == []
    _rows = dict(rumor.hearing_rows(
        [], {}, _no_traits(), "barkeep",
        routing=lambda rumor_id: rumor_id != "thin_month_1",
    ))
    assert "thin_month_1" not in _rows.values()
    assert "derelict_line_1" in _rows.values()


def test_non_source_npc_gets_nothing():
    assert rumor.hearing_rows([], {}, _no_traits(), "guild_master") == []


# --- askable topics -------------------------------------------------------


def test_askable_topics_empty_before_anything_is_heard():
    assert rumor.askable_topics([], {}, _no_traits(), "barkeep") == []


def test_askable_topics_offer_the_next_tier():
    _topics = rumor.askable_topics(
        ["derelict_line_1"], {}, _no_traits(), "depot_attendant"
    )
    assert _topics == [("the derelict line", "derelict_line_2")]


def test_askable_topics_only_for_contacts_who_deliver():
    assert rumor.askable_topics(
        ["derelict_line_1"], {}, _no_traits(), "barkeep"
    ) == []


def test_askable_topics_empty_when_chain_exhausted():
    assert rumor.askable_topics(
        ["derelict_line_1", "derelict_line_2", "derelict_line_3"],
        {},
        _no_traits(),
        "wolf_barkeep",
    ) == []


def test_askable_topics_honor_floors():
    assert rumor.askable_topics(
        ["thin_month_1"], {"militia": -5}, _no_traits(), "blockade_officer"
    ) == []
    assert rumor.askable_topics(
        ["thin_month_1"], {"militia": 0}, _no_traits(), "blockade_officer"
    ) == [("the thin month", "thin_month_2")]


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
    assert rumor.askable_topics(["retired_rumor"], {}, _no_traits(), "barkeep") == []


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
