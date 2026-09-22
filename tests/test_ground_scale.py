"""Ground band resolver tests (doc 48 phase 4, SETTLED 35).

Pure-function coverage for the three scaling axes plus the data-shape
lint over every NpcCharSpec row (weights, families, exemption).
"""

from types import SimpleNamespace

import pytest

from src.spacehack import ground_scale
from src.spacehack.data.ground_weapons import family_tiers, weapon_families
from src.spacehack.data.npc_chars import list_npc_chars
from src.spacehack.data.quality import KILL_QUALITY_RATES


class ScriptedRng:
    """Deterministic rng double: scripted draws, consumed in order."""

    def __init__(self, *draws):
        self._draws = list(draws)

    def random(self):
        return self._draws.pop(0)

    def choice(self, seq):
        return seq[self._draws.pop(0)]


def _spec(**overrides):
    base = dict(
        weapon_families=("rifles",),
        stat_weights=(0.45, 0.15, 0.25, 0.05, 0.05, 0.05),
        pin_window_top=False,
    )
    base.update(overrides)
    return SimpleNamespace(**base)


# --- budgets ---------------------------------------------------------------

def test_band_budget_levels_map_to_settled_budgets():
    assert [ground_scale.band_budget(band) for band in (1, 2, 3, 4)] == [
        10, 45, 85, 145,
    ]


def test_band_budget_clamps_out_of_range():
    assert ground_scale.band_budget(0) == 0
    assert ground_scale.band_budget(-3) == 0
    assert ground_scale.band_budget(9) == ground_scale.band_budget(4)


# --- stat derivation ---------------------------------------------------------

def test_derive_stats_band_zero_reads_base():
    stats = ground_scale.derive_stats(_spec(), 0)
    assert (stats.reflexes, stats.strength, stats.stamina) == (10, 10, 10)
    assert (stats.gunnery, stats.piloting, stats.engineering) == (10, 10, 10)


def test_derive_stats_distributes_the_whole_budget():
    for band in (1, 2, 3, 4):
        stats = ground_scale.derive_stats(_spec(), band)
        spent = sum(
            getattr(stats, name) - ground_scale.STAT_BASE
            for name in (
                "reflexes", "strength", "stamina",
                "gunnery", "piloting", "engineering",
            )
        )
        assert spent == ground_scale.band_budget(band), band


def test_derive_stats_caps_at_100():
    weights = (0.70, 0.10, 0.0, 0.05, 0.05, 0.05)
    stats = ground_scale.derive_stats(_spec(stat_weights=weights), 4)
    assert stats.reflexes == 100  # 10 + 101 rounds past the 100 cap


def test_derive_stats_zero_weights_stay_flat():
    weights = (0.0, 0.0, 0.0, 0.0, 0.0, 0.0)
    stats = ground_scale.derive_stats(_spec(stat_weights=weights), 4)
    assert stats == ground_scale.GroundBandStats()


def test_derive_stats_largest_remainder_ties_break_earlier():
    # Even 0.85 split at band 1: floors eat 6 of the 10 points; the
    # three ground fracs outrank the space tail's 0.5s, so the ground
    # block reads 13/13/13 and gunnery takes the last point.
    even = (0.2834, 0.2833, 0.2833, 0.05, 0.05, 0.05)
    stats = ground_scale.derive_stats(_spec(stat_weights=even), 1)
    assert (stats.reflexes, stats.strength, stats.stamina) == (13, 13, 13)
    assert stats.gunnery == 11


# --- quality -----------------------------------------------------------------

def test_quality_rates_table_is_settled_35():
    assert ground_scale.BAND_QUALITY_RATES == (
        (5, 11, 25), (7, 14, 30), (8, 17, 35), (10, 20, 40),
    )


def test_quality_rates_band_zero_reads_band_one():
    assert ground_scale.quality_rates(0) == KILL_QUALITY_RATES
    assert ground_scale.quality_rates(1) == KILL_QUALITY_RATES


# --- weapon family ladder ------------------------------------------------------

def test_roll_weapon_band_one_is_tier_one_only():
    spec = _spec(weapon_families=("pistols",))
    weapon = ground_scale.roll_weapon(spec, 1, ScriptedRng(0, 0.99, 0))
    assert weapon in ("laser_pistol", "kinetic_pistol")


def test_roll_weapon_window_weights_by_band():
    spec = _spec(weapon_families=("rifles",))
    # band 2: a 0.5 roll takes tier 1 (70% share); a 0.75 takes tier 2.
    low = ground_scale.roll_weapon(spec, 2, ScriptedRng(0, 0.5, 0))
    high = ground_scale.roll_weapon(spec, 2, ScriptedRng(0, 0.75, 0))
    assert low in family_tiers("rifles")[1]
    assert high in family_tiers("rifles")[2]
    # band 3: 0.2 takes tier 2, 0.5 takes tier 3 (30/70, SETTLED 35).
    low3 = ground_scale.roll_weapon(spec, 3, ScriptedRng(0, 0.2, 0))
    high3 = ground_scale.roll_weapon(spec, 3, ScriptedRng(0, 0.5, 0))
    assert low3 in family_tiers("rifles")[2]
    assert high3 in family_tiers("rifles")[3]
    # band 4: 0.29 takes tier 3, 0.5 takes tier 4.
    low4 = ground_scale.roll_weapon(spec, 4, ScriptedRng(0, 0.29, 0))
    high4 = ground_scale.roll_weapon(spec, 4, ScriptedRng(0, 0.5, 0))
    assert low4 in family_tiers("rifles")[3]
    assert high4 in family_tiers("rifles")[4]


def test_roll_weapon_sniper_pins_window_top():
    spec = _spec(weapon_families=("rifles",), pin_window_top=True)
    band4 = ground_scale.roll_weapon(spec, 4, ScriptedRng(0, 0))
    band2 = ground_scale.roll_weapon(spec, 2, ScriptedRng(0, 0))
    assert band4 in family_tiers("rifles")[4]   # railgun / ion blaster
    assert band2 in family_tiers("rifles")[2]


def test_roll_weapon_snaps_empty_tier_upward():
    # Explosives ladder t3-t4: a band-3 tier-2 roll must land the
    # grenade launcher, never an empty tier.
    spec = _spec(weapon_families=("explosive",))
    weapon = ground_scale.roll_weapon(spec, 3, ScriptedRng(0, 0.1, 0))
    assert weapon == "grenade_launcher"


def test_roll_weapon_band_zero_reads_band_one_window():
    spec = _spec(weapon_families=("explosive",))
    # Band 0 reads the band-1 window {t1}; explosives have no t1, so
    # the snap climbs to the nearest populated tier (grenade launcher).
    weapon = ground_scale.roll_weapon(spec, 0, ScriptedRng(0, 0.1, 0))
    assert weapon == "grenade_launcher"


def test_roll_weapon_empty_families_returns_empty():
    assert ground_scale.roll_weapon(_spec(weapon_families=()), 4, None) == ""


def test_family_tiers_exclude_organic_rows():
    assert "fists" not in family_tiers("melee").get(1, ())
    assert family_tiers("monsters") == {}
    assert "monsters" not in weapon_families()


# --- context fallback ----------------------------------------------------------

def _map_with_key(key):
    from types import SimpleNamespace

    return SimpleNamespace(interior_cache_key=key)


def test_context_band_dig_key_rederives_climbed_band():
    # Mars is mission_tier 1, so floors 1-2 read bands 1-2 — the climb
    # without touching the tier cap (which phase 4's unclamp raises
    # from 3 to 4; deeper assertions live in the digs suite).
    assert ground_scale.context_band(_map_with_key("dig:mars:s7:1")) == 1
    assert ground_scale.context_band(_map_with_key("dig:mars:s7:2")) == 2


def test_context_band_non_dig_maps_read_band_one():
    assert ground_scale.context_band(_map_with_key("city:earth")) == 1
    assert ground_scale.context_band(None) == 1


def test_entity_band_stamp_wins_over_context():
    entity = SimpleNamespace(spawn_band=3)
    assert ground_scale.entity_band(entity, _map_with_key("dig:vega_b:s7:5")) == 3


def test_entity_band_unstamped_falls_back_to_context():
    entity = SimpleNamespace(spawn_band=0)
    assert ground_scale.entity_band(entity, _map_with_key("city:earth")) == 1


# --- data-shape lint over every row ---------------------------------------------

def test_every_row_carries_six_valid_weights():
    space_share = (0.05, 0.05, 0.05)
    for spec in list_npc_chars():
        assert len(spec.stat_weights) == 6, spec.id
        if not any(spec.stat_weights):
            # The band-exempt bystander: ALL SIX zero — no stamp
            # moves anything (SETTLED 14).
            assert spec.stat_weights == (0.0,) * 6, spec.id
            continue
        assert spec.stat_weights[3:] == space_share, spec.id
        assert sum(spec.stat_weights[:3]) == pytest.approx(0.85, abs=1e-3), (
            spec.id
        )


def test_bystander_row_is_scale_invariant():
    from src.spacehack.data.npc_chars import find_npc_char

    bystander = find_npc_char("civilian_bystander")
    for band in (0, 1, 2, 3, 4):
        assert ground_scale.derive_stats(bystander, band) == (
            ground_scale.GroundBandStats()
        )


def test_every_humanoid_row_names_ladder_families():
    ladder = set(weapon_families())
    for spec in list_npc_chars():
        assert set(spec.weapon_families) <= ladder, spec.id
        # A row must be able to fight: families roll, or weapons fix.
        assert spec.weapon_families or spec.weapons, spec.id
        # The window pin only means something on a rolling row.
        if spec.pin_window_top:
            assert spec.weapon_families, spec.id


def test_ladder_families_are_populated():
    for family in weapon_families():
        tiers = family_tiers(family)
        assert tiers, family
