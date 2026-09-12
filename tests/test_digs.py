"""Dig-site derivations (doc 42 phase 4): reveal determinism, name
pools, depth bounds, and the cache-key contract."""

from __future__ import annotations

import dataclasses
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.spacehack import digs, engine
from src.spacehack.data.digs import DEFAULT_PREFIXES, DEFAULT_SUFFIXES
from src.spacehack.data.planets import list_planet_specs, find_planet_spec


@pytest.fixture(autouse=True)
def _pinned_seed(monkeypatch):
    monkeypatch.setattr(engine, "INIT_SEED", 424242)


def _ctx(monkeypatch, sites=None):
    """A ctx with the readout captured instead of presented."""
    seen = []
    monkeypatch.setattr(
        digs.rumor, "present_hearing",
        lambda ctx, title, text: seen.append((title, text)),
    )
    return SimpleNamespace(discovered_sites=list(sites or [])), seen


def test_reveal_is_deterministic_per_seed_and_ordinal(monkeypatch):
    """Same INIT_SEED + same ordinal → the same planet and name; the
    ordinal keys the derivation (SETTLED 7/28)."""
    first, _ = _ctx(monkeypatch)
    second, _ = _ctx(monkeypatch)
    a = digs.reveal_site(first)
    b = digs.reveal_site(second)
    assert a == b


def test_reveal_records_and_presents(monkeypatch):
    ctx, seen = _ctx(monkeypatch)
    site = digs.reveal_site(ctx)
    assert ctx.discovered_sites == [site]
    assert set(site) == {"id", "planet", "name"}
    assert site["id"] == "s1"
    assert site["planet"] in {spec.id for spec in list_planet_specs()}
    title, text = seen[0]
    assert title
    assert site["name"] in text
    assert find_planet_spec(site["planet"]).name in text


def test_reveal_stacks_a_new_site(monkeypatch):
    """Each reveal is a new, distinct site (SETTLED 31); the ordinal
    advances, so the derivation moves on."""
    ctx, _ = _ctx(monkeypatch)
    one = digs.reveal_site(ctx)
    two = digs.reveal_site(ctx)
    assert one["id"] == "s1" and two["id"] == "s2"
    assert ctx.discovered_sites == [one, two]


def test_rerolled_seed_yields_a_different_legal_reveal(monkeypatch):
    """A reroll must move the derivation — distinct planets or names
    across seeds, every draw legal (the rumor-routing shape)."""
    planets = {spec.id for spec in list_planet_specs()}
    draws = set()
    for seed in range(40):
        monkeypatch.setattr(engine, "INIT_SEED", seed)
        ctx, _ = _ctx(monkeypatch)
        site = digs.reveal_site(ctx)
        assert site["planet"] in planets
        draws.add((site["planet"], site["name"]))
    assert len(draws) > 1


def test_same_planet_sites_never_share_a_name(monkeypatch):
    """Rows are one per site, so two reveals on one planet never
    render the same name: the seeded walk skips taken names, and a
    fully exhausted (one-combo) pool numbers instead of looping."""
    spec = find_planet_spec("mars")
    narrow = dataclasses.replace(
        spec, dig_prefixes=("Only",), dig_suffixes=("Name",),
    )
    monkeypatch.setattr(digs, "list_planet_specs", lambda: [narrow])
    ctx, _ = _ctx(monkeypatch)
    one = digs.reveal_site(ctx)
    two = digs.reveal_site(ctx)
    three = digs.reveal_site(ctx)
    assert one["name"] == "Only Name"
    assert two["name"] == "Only Name 2"
    assert three["name"] == "Only Name 3"


def test_authored_name_pools_win(monkeypatch):
    """A spec's pools are the only source when authored (SETTLED 33)."""
    spec = find_planet_spec("mars")
    authored = dataclasses.replace(
        spec, dig_prefixes=("Alpha",), dig_suffixes=("One", "Two"),
    )
    for roll in range(1, 20):
        assert digs.site_name(authored, roll) in {"Alpha One", "Alpha Two"}


def test_default_pools_fill_unauthored_specs():
    spec = find_planet_spec("mars")
    name = digs.site_name(spec, 7)
    prefix, suffix = name.split(" ")
    assert prefix in DEFAULT_PREFIXES
    assert suffix in DEFAULT_SUFFIXES


def test_depth_lands_within_spec_bounds():
    spec = find_planet_spec("mars")
    tight = dataclasses.replace(spec, dig_min_floors=3, dig_max_floors=5)
    for n in range(1, 15):
        assert 3 <= digs.site_depth(tight, f"s{n}") <= 5
        assert 1 <= digs.site_depth(spec, f"s{n}") <= 2


def test_depth_min_beats_inverted_max():
    spec = find_planet_spec("mars")
    inverted = dataclasses.replace(spec, dig_min_floors=4, dig_max_floors=2)
    assert digs.site_depth(inverted, "s1") == 4


def test_cache_key_round_trip():
    key = digs.cache_key("mars", "s3", 2)
    assert key == "dig:mars:s3:2"
    assert digs.parse_cache_key(key) == ("mars", "s3", 2)


def test_parse_cache_key_rejects_other_families():
    assert digs.parse_cache_key("city:earth:bar") is None
    assert digs.parse_cache_key("surface:mars") is None
    assert digs.parse_cache_key("extension:mars_alien_prison:floor:1") is None
    assert digs.parse_cache_key("dig:mars:s3") is None
    assert digs.parse_cache_key("dig:mars:s3:x") is None
    assert digs.parse_cache_key("plainly not a key") is None
