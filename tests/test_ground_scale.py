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
        weapons=(),
        weapon_families=("rifles",),
        melee_weapons=(),
        melee_families=(),
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


def test_planet_band_clamps_into_range():
    assert [ground_scale.planet_band(t) for t in (0, 1, 4, 5, 9)] == [
        1, 1, 4, 4, 4,
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
    # without touching the tier cap (the band-wiring build raises that
    # cap 3 -> 4 and re-pins the digs suite).
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


# --- consumption + stamping (doc 48 phase 4 build 2) ---------------------------

def test_no_straggler_reads_of_the_retired_fields():
    """Grep-pin: nothing reads the retired spec fields (they no longer
    exist — this pins that no consumer regrows one via getattr)."""
    import subprocess

    result = subprocess.run(
        ["git", "grep", "-n", "-E",
         r"weapon_pick|spec\.reflexes|spec\.strength|spec\.stamina",
         "src/spacehack/"],
        capture_output=True, text=True,
    )
    assert result.returncode in (0, 1), result.stderr
    assert not result.stdout, f"straggler reads:\n{result.stdout}"


def test_enemy_instance_resolves_through_the_band():
    """The combat-entry build derives stats/weapon at the stamped band."""
    from src.spacehack import world
    from src.spacehack.combat import _rules_ground

    entity = world.Entity(
        char="R", fg=(220, 120, 80), pos=world.Position(1, 1), name="",
        npc_char_id="pirate_rifleman", spawn_band=4,
    )
    instance = _rules_ground._build_enemy_instance(entity, None)
    assert instance.band == 4
    # rifleman: reflexes-biased profile — reflexes leads the ground trio
    assert instance.stats.reflexes > instance.stats.stamina > 10
    # band-4 window {3,4} 30/70: either tier legal, never below t3
    from src.spacehack.data.ground_weapons import find_ground_weapon
    assert find_ground_weapon(instance.weapon_id).tech_level >= 3


def test_unstamped_entity_derives_band_one_stats():
    """Band 0 (no stamp, no site) reads base-leaning band-1 numbers."""
    from types import SimpleNamespace

    from src.spacehack import world
    from src.spacehack.combat import _rules_ground

    entity = world.Entity(
        char="r", fg=(220, 120, 80), pos=world.Position(1, 1), name="",
        npc_char_id="pirate_raider",
    )
    instance = _rules_ground._build_enemy_instance(
        entity, SimpleNamespace(interior_cache_key=""),
    )
    assert instance.band == 1
    # base 10 + band-1 budget 10: every ground stat in [11, 14]
    for value in (
        instance.stats.reflexes, instance.stats.strength,
        instance.stats.stamina,
    ):
        assert 11 <= value <= 14


def test_entity_spawn_band_round_trips_save_load():
    """The band serializes with the entity (ground bold restore gets
    its real assert when the elite rows land, build 4)."""
    from src.spacehack import world
    from src.spacehack.saveload_maps import _entity_from_dict, _entity_to_dict

    entity = world.Entity(
        char="R", fg=(220, 120, 80), pos=world.Position(2, 3), name="",
        npc_char_id="pirate_raider", spawn_band=3,
    )
    restored = _entity_from_dict(_entity_to_dict(entity))
    assert restored.spawn_band == 3


def test_dig_population_stamps_the_tier_band():
    """populate_dungeon stamps its tier on every placed enemy."""
    from src.spacehack import dungeon_population, world
    from src.spacehack.dungeon_params import DungeonParams

    tiles = [
        [world.DUNGEON_FLOOR for _ in range(30)] for _ in range(30)
    ]
    game_map = world.GameMap(30, 30, tiles, [])
    params = DungeonParams(
        width=30, height=30, min_room_size=4, max_room_size=8,
        room_fill_pct=0.6, monster_pool=("pirate_raider",),
        monster_density=6.0,
    )
    from src.spacehack import engine
    engine.RNG.seed(4242)
    dungeon_population.populate_dungeon(
        game_map, params, world.Position(15, 15), tier=3,
    )
    stamped = [e for e in game_map.entities if e.npc_char_id]
    assert stamped
    assert all(e.spawn_band == 3 for e in stamped)


def test_quest_camp_landmarks_stamp_the_planet_band():
    """Delve-camp ENEMY markers carry the parent planet's tier (the
    build-2 review's blocking catch: wolf_b's camp read band 1)."""
    from unittest.mock import patch as mock_patch

    from src.spacehack import world
    from src.spacehack.main_quest import _delve

    seen = {}

    def fake_load(layout_id, spawn_band=0):
        seen[layout_id] = spawn_band
        return world.GameMap(4, 4, [[world.DUNGEON_FLOOR] * 4 for _ in range(4)], [])

    def fake_stamp(game_map, asset, spawn):
        raise ValueError  # stamp fails -> loop continues, load recorded

    tiles = [[world.DUNGEON_FLOOR for _ in range(20)] for _ in range(20)]
    game_map = world.GameMap(20, 20, tiles, [])
    with mock_patch.object(_delve.landmark, "load_landmark", fake_load), \
            mock_patch.object(_delve.landmark, "stamp_landmark", fake_stamp):
        _delve._camp_or_far_cache(
            game_map, world.Position(2, 2), "wolf_camp", band=3,
        )
    assert seen == {"wolf_camp": 3}


def test_band_level_maps_settled_levels():
    assert [ground_scale.band_level(b) for b in (1, 2, 3, 4)] == [
        3, 10, 18, 30,
    ]
    assert ground_scale.band_level(0) == 3   # no band reads band 1
    assert ground_scale.band_level(9) == 30


def test_target_card_title_states_the_level():
    """The combat card's title reads ``LVL <level> <name>`` (user
    wording, 2026-09-22) — the band's effective level, stated."""
    from types import SimpleNamespace

    from src.spacehack.combat._ground_presentation import _ground_card_rows

    enemy = SimpleNamespace(
        name="Pirate Raider", hp=24, max_hp=24, ap=4, band=4,
        spec=SimpleNamespace(armor=0),
    )
    rows = _ground_card_rows(enemy, None, None)
    title = "".join(text for text, _fg in rows[0])
    assert title == "LVL 30 Pirate Raider"


def test_target_card_colours_wielded_variant_name_without_token():
    """The card's weapon line takes the tier COLOUR on the base name —
    no "Modded" token (user ruling 2026-09-23: colour teaches, clutter
    stays off the card)."""
    from types import SimpleNamespace

    from src.spacehack.combat._ground_presentation import (
        _ground_card_rows, enemy_weapon_fg,
    )
    from src.spacehack.data.ground_weapons import find_ground_weapon
    from src.spacehack.pygame_target_card import TARGET_CARD_DIM

    weapon = find_ground_weapon("mono_blade")
    enemy = SimpleNamespace(
        name="Pirate Raider", hp=24, max_hp=24, ap=4, band=0,
        spec=SimpleNamespace(armor=0), weapon_quality=2,
    )

    rows = _ground_card_rows(enemy, weapon, None)

    assert rows[3] == (("Mono Blade", (130, 210, 240)),)
    assert enemy_weapon_fg(enemy, TARGET_CARD_DIM) == (130, 210, 240)
    # Base-quality enemies keep the plain dim treatment.
    enemy.weapon_quality = 0
    assert _ground_card_rows(enemy, weapon, None)[3] == (
        ("Mono Blade", TARGET_CARD_DIM),
    )
    assert enemy_weapon_fg(enemy, TARGET_CARD_DIM) == TARGET_CARD_DIM


# --- the two-set loadout roll (doc 48 phase 9, SETTLED 43) ----------------------

class LoadoutRng:
    """Behavioral rng double: first pick, top window roll, quality
    misses (randint returns hi, never the 1-in-N hit), pool at max."""

    def choice(self, seq):
        return seq[0]

    def random(self):
        return 0.99

    def randint(self, lo, hi):
        return hi


def test_roll_loadout_fills_both_sets_through_the_same_windows():
    """The melee set rolls through the SAME band windows as the ranged
    set (SETTLED 43): band 1 keeps both slots at tier 1."""
    spec = _spec(weapon_families=("pistols",), melee_families=("melee",))
    stamp = ground_scale.roll_loadout(spec, 1, LoadoutRng())
    assert stamp["ranged"][0] in family_tiers("pistols")[1]
    assert stamp["melee"][0] in family_tiers("melee")[1]
    assert stamp["active"] == "ranged"
    # Band 4's window is {3, 4}; pistols top out at t3, so the snap
    # lands the ladder's ceiling.
    stamp4 = ground_scale.roll_loadout(spec, 4, LoadoutRng())
    assert stamp4["ranged"][0] in family_tiers("pistols")[3]


def test_roll_loadout_stamps_full_magazines_and_the_carried_pool():
    """Ammo-fed weapons stamp a full magazine (the player instance's
    mirror) and the pool rolls in the half-to-three-quarters window —
    never a full stack, one entry per distinct ammo type."""
    from src.spacehack.data.ground_weapons import find_ground_weapon

    spec = _spec(weapon_families=("rifles",), melee_families=("melee",))
    stamp = ground_scale.roll_loadout(spec, 2, LoadoutRng())
    # Band 2's 0.99 roll takes tier 2: laser_rifle (energy_cell fed).
    _ranged_id = stamp["ranged"][0]
    _ws = find_ground_weapon(_ranged_id)
    assert _ws.ammo_capacity > 0
    assert stamp["loaded"][_ranged_id] == _ws.ammo_capacity
    (entry,) = stamp["pool"]
    assert entry == ["ammo", "energy_cells", 4]  # ceiling 5 -> (2, 4)
    # The melee knife never needs ammo.
    assert stamp["melee"][0] not in stamp["loaded"]


def test_roll_loadout_one_pool_entry_per_distinct_ammo_type():
    spec = _spec(
        weapon_families=("pistols",), melee_weapons=("stun_baton",),
    )
    stamp = ground_scale.roll_loadout(spec, 2, LoadoutRng())
    ids = [e[1] for e in stamp["pool"]]
    assert len(ids) == len(set(ids))


def test_roll_loadout_fixed_rows_keep_their_weapons_and_fixed_melee_set():
    spec = SimpleNamespace(
        weapons=("kinetic_pistol",), weapon_families=(),
        melee_weapons=("combat_knife",), melee_families=(),
        pin_window_top=False,
    )
    stamp = ground_scale.roll_loadout(spec, 3, LoadoutRng())
    assert stamp["ranged"][0] == "kinetic_pistol"
    assert stamp["melee"][0] == "combat_knife"
    assert stamp["loaded"] == {"kinetic_pistol": 12}
    assert stamp["pool"] == [["ammo", "pistol_rounds", 4]]


def test_roll_loadout_weaponless_row_stamps_empty_slots():
    spec = _spec(weapon_families=())
    stamp = ground_scale.roll_loadout(spec, 1, LoadoutRng())
    assert stamp["ranged"] is None
    assert stamp["melee"] is None
    assert stamp["pool"] == []


def test_carried_pool_range_is_half_to_three_quarters():
    assert ground_scale.carried_pool_range(5) == (2, 4)
    assert ground_scale.carried_pool_range(2) == (1, 2)
    assert ground_scale.carried_pool_range(1) == (1, 1)


def test_humanoid_rows_author_melee_sets():
    """The data pass (SETTLED 43): every humanoid row carries a melee
    set — family rows roll it, the merchant's knife is fixed; fauna
    and machines author neither melee field."""
    expected_melee_families = {
        "consortium_enforcer", "consortium_gunner", "pirate_raider",
        "pirate_rifleman", "pirate_brute", "militia_marine",
        "militia_sniper", "militia_trooper",
    }
    for spec in list_npc_chars():
        if spec.id in expected_melee_families:
            assert spec.melee_families == ("melee",), spec.id
        elif spec.id == "merchant":
            assert spec.melee_weapons == ("combat_knife",), spec.id
            assert spec.weapons == ("kinetic_pistol",), spec.id
        else:
            assert not spec.melee_weapons and not spec.melee_families, spec.id


def test_never_author_both_weapons_and_families_per_set():
    """The families-take-precedence law holds PER SET (SETTLED 43)."""
    for spec in list_npc_chars():
        assert not (spec.weapons and spec.weapon_families), spec.id
        assert not (spec.melee_weapons and spec.melee_families), spec.id
        if spec.melee_families:
            assert set(spec.melee_families) <= set(weapon_families()), spec.id
