"""Loot quality tier tests (doc 47 phase 2).

Pure-function coverage for :mod:`spacehack.data.quality` — the tier
ladder, per-family multipliers, effective specs, and token prefixes.
"""

import pytest

from spacehack.data import quality
from spacehack.data.ground_armor import find_ground_armor
from spacehack.data.ground_weapons import find_ground_weapon


class _SeqRng:
    """Test double: serves one scripted roll per randint call."""

    def __init__(self, values: list[int]) -> None:
        self._values = values

    def randint(self, low: int, high: int) -> int:
        value = self._values.pop(0)
        if not low <= value <= high:
            raise AssertionError(f"roll {value} outside [{low}, {high}]")
        return value


def test_roll_quality_ladder_is_rarest_first():
    rates = (5, 11, 25)
    # t3 roll hits first -> tier 3 wins outright.
    assert quality.roll_quality(rates, _SeqRng([1, 3, 2])) == 3
    # t3 misses, t2 hits.
    assert quality.roll_quality(rates, _SeqRng([2, 1, 3])) == 2
    # t3 and t2 miss, t1 hits.
    assert quality.roll_quality(rates, _SeqRng([2, 3, 1])) == 1
    # every roll misses -> base.
    assert quality.roll_quality(rates, _SeqRng([2, 3, 2])) == 0


def test_roll_quality_never_produces_legendary():
    # Even a maximally lucky ladder stops at t3 (SETTLED 11).
    for rates in (
        quality.KILL_QUALITY_RATES,
        quality.WRECK_QUALITY_RATES,
        quality.DIG_QUALITY_RATES,
    ):
        assert quality.roll_quality(rates, _SeqRng([1, 1, 1])) == 3


def test_rate_ladders_are_three_ascending_runs():
    for rates in (
        quality.KILL_QUALITY_RATES,
        quality.WRECK_QUALITY_RATES,
        quality.DIG_QUALITY_RATES,
    ):
        assert len(rates) == 3
        assert rates[0] < rates[1] < rates[2]


@pytest.mark.parametrize(
    "family,row",
    [
        ("weapon", quality.WEAPON_MULTIPLIER_PCT),
        ("armor", quality.ARMOR_MULTIPLIER_PCT),
    ],
)
def test_quality_multiplier_rows(family, row):
    assert len(row) == quality.LEGENDARY_QUALITY + 1
    assert row[0] == 100
    for tier, pct in enumerate(row):
        assert quality.quality_multiplier(family, tier) == pct / 100


def test_quality_multiplier_rejects_unknown_family_and_tier():
    with pytest.raises(ValueError):
        quality.quality_multiplier("module", 1)
    with pytest.raises(ValueError):
        quality.quality_multiplier("weapon", quality.LEGENDARY_QUALITY + 1)
    with pytest.raises(ValueError):
        quality.quality_multiplier("weapon", -1)


def test_effective_weapon_spec_base_is_the_catalog_row():
    spec = find_ground_weapon("kinetic_pistol")
    assert quality.effective_weapon_spec("kinetic_pistol", 0) is spec


def test_effective_weapon_spec_scales_damage_and_accuracy_only():
    base = find_ground_weapon("kinetic_pistol")  # damage 6, accuracy 72
    t1 = quality.effective_weapon_spec("kinetic_pistol", 1)
    assert t1.damage == 7          # 6 * 1.15 = 6.9 -> 7
    assert t1.accuracy == 83       # 72 * 1.15 = 82.8 -> 83
    assert t1.ammo_capacity == base.ammo_capacity
    assert t1.ap_cost == base.ap_cost
    assert t1.max_range == base.max_range
    assert t1.id == base.id and t1.name == base.name


def test_effective_specs_scale_exact_halves_up():
    # 10 * 1.15 = 11.5 and 70 * 1.15 = 80.5 must round UP — float
    # arithmetic rounds 80.4999... down, so scaling is integer-exact.
    rifle_t1 = quality.effective_weapon_spec("kinetic_rifle", 1)  # damage 10
    assert rifle_t1.damage == 12
    smg_t1 = quality.effective_weapon_spec("smg", 1)           # accuracy 70
    assert smg_t1.accuracy == 81


def test_effective_weapon_spec_legendary_row_resolves():
    t4 = quality.effective_weapon_spec("kinetic_pistol", quality.LEGENDARY_QUALITY)
    assert t4.damage == 13         # 6 * 2.20 = 13.2 -> 13
    assert t4.accuracy == 158      # 72 * 2.20 = 158.4 -> 158


def test_effective_armor_spec_base_is_the_catalog_row():
    spec = find_ground_armor("cybernetic_eyes")
    assert quality.effective_armor_spec("cybernetic_eyes", 0) is spec


def test_effective_armor_spec_scales_defense_and_bonus_fields():
    t2 = quality.effective_armor_spec("cybernetic_eyes", 2)  # hit_bonus 8
    assert t2.hit_bonus == 10      # 8 * 1.30 = 10.4 -> 10
    assert t2.defense == 0         # base 0 stays 0
    vest_t3 = quality.effective_armor_spec("medium_vest", 3)  # defense 3
    assert vest_t3.defense == 4    # 3 * 1.45 = 4.35 -> 4
    assert vest_t3.slot == find_ground_armor("medium_vest").slot


def test_effective_specs_clamp_malformed_negative_tiers_to_base():
    assert quality.effective_weapon_spec("kinetic_pistol", -1) is find_ground_weapon(
        "kinetic_pistol",
    )
    assert quality.effective_armor_spec("light_vest", -2) is find_ground_armor(
        "light_vest",
    )


def test_effective_specs_reject_unknown_ids():
    with pytest.raises(KeyError):
        quality.effective_weapon_spec("no_such_weapon", 1)
    with pytest.raises(KeyError):
        quality.effective_armor_spec("no_such_armor", 1)


@pytest.mark.parametrize(
    "tier,expected",
    [
        (0, ""),
        (1, "Modded "),
        (2, "Overclocked "),
        (3, "Prototype "),
        (quality.LEGENDARY_QUALITY, ""),
    ],
)
def test_token_prefix_title_cases_the_settled_tokens(tier, expected):
    assert quality.token_prefix(tier) == expected


def test_quality_tokens_are_the_user_wording_verbatim():
    assert quality.QUALITY_TOKENS == ("modded", "overclocked", "prototype")


# ---------------------------------------------------------------------------
# Presentation + economy (doc 47 phase 2 step 6)
# ---------------------------------------------------------------------------


def test_display_name_prefixes_the_token_at_the_label_seam():
    from spacehack.ground_equipment import display_name

    assert display_name("weapon", "kinetic_pistol", 1) == "Modded Kinetic Pistol"
    assert display_name("weapon", "kinetic_pistol", 3) == "Prototype Kinetic Pistol"
    assert display_name("armor", "cybernetic_eyes", 2) == "Overclocked Cybernetic Eyes"
    assert display_name("weapon", "kinetic_pistol") == "Kinetic Pistol"
    assert display_name("armor", "light_vest", 4) == "Light Armor Vest"  # randart name later


def test_loot_label_carries_the_token():
    from types import SimpleNamespace

    from spacehack.loot import _loot_choice_label

    entity = SimpleNamespace(loot_data={
        "item_type": "weapon", "item_id": "smg", "quality": 2,
    })
    assert _loot_choice_label(entity) == "Overclocked SMG"


def test_sell_price_scales_half_catalog_by_tier():
    from spacehack.menus._armory import _sell_price
    from spacehack.data.ground_weapons import find_ground_weapon

    base_price = find_ground_weapon("kinetic_pistol").price  # 35
    assert _sell_price("kinetic_pistol") == base_price // 2
    assert _sell_price("kinetic_pistol", 1) == 20   # 17.5 * 1.15 = 20.125
    assert _sell_price("kinetic_pistol", 3) == 25   # 17.5 * 1.45 = 25.375
    assert _sell_price("kinetic_pistol", 4) == 39   # 17.5 * 2.20 = 38.5 -> 39
    # Base gear keeps the exact legacy half-catalog price.
    assert _sell_price("light_vest") == 50 // 2
    # A worthless catalog row still sells for the minimum.
    assert _sell_price("monster_claws", 3) == 1


def test_armory_names_and_details_read_the_tier():

    from spacehack.ground_equipment import StoredGroundEquipment
    from spacehack.menus._armory import _equipment_detail, _equipment_name

    entry = StoredGroundEquipment("weapon", "kinetic_pistol", 2)
    assert _equipment_name(entry) == "Overclocked Kinetic Pistol"
    assert "Damage: 8" in _equipment_detail(entry)  # 6 * 1.30
    base = StoredGroundEquipment("armor", "cybernetic_eyes")
    assert _equipment_name(base) == "Cybernetic Eyes"


@pytest.mark.parametrize(
    "quality,expected",
    [
        (0, (130, 145, 170)),
        (1, (143, 160, 187)),
        (2, (159, 177, 207)),
        (3, (177, 197, 231)),
        (4, (202, 225, 264 - 9)),  # clamped channels cap at 255
    ],
)
def test_loot_fg_brightens_equipment_by_quality(quality, expected):
    from spacehack.loot_common import loot_fg

    fg = loot_fg({"item_type": "weapon", "item_id": "smg", "quality": quality})
    assert fg == expected


def test_loot_fg_categories_ignore_quality():
    from spacehack.loot_common import loot_fg

    # Non-equipment payloads keep their phase-1 category hues exactly.
    assert loot_fg({"item_type": "ammo", "item_id": "pistol_rounds",
                    "quality": 3}) == (200, 175, 110)
    assert loot_fg({"good_id": "scrap_metal", "quantity": 2,
                    "quality": 3}) == (255, 215, 0)
    assert loot_fg({"item_type": "weapon", "item_id": "smg"}) == (130, 145, 170)


def test_managed_slot_quality_reads_equipped_tiers_synchronously():
    from types import SimpleNamespace

    from spacehack.ground_equipment import StoredGroundEquipment
    from spacehack.menus._armory import _managed_slot_quality

    ctx = SimpleNamespace(
        equipped_ground_weapons=[SimpleNamespace(quality=2)],
        equipped_ground_armor={
            "body": StoredGroundEquipment("armor", "light_vest", 3),
        },
    )
    # Plain ints, not coroutines — the manage chooser calls this sync.
    assert _managed_slot_quality(ctx, "MANAGE_WEAPON", 0) == 2
    assert _managed_slot_quality(ctx, "MANAGE_ARMOR", "body") == 3
    assert _managed_slot_quality(ctx, "MANAGE_ARMOR", "head") == 0


def test_reload_target_carries_the_token_prefixed_name():
    from types import SimpleNamespace

    from spacehack.ground_equipment import weapon_instance
    from spacehack.ground_reload_ui import _resolve_reload_target

    ctx = SimpleNamespace(
        equipped_ground_weapons=[weapon_instance("smg", 2)],
        log=SimpleNamespace(add=lambda *_: None),
    )
    _instance, _spec, name = _resolve_reload_target(ctx, 0)
    assert name == "Overclocked SMG"


def test_player_side_weapon_name_carries_the_tier():
    from types import SimpleNamespace

    from spacehack.combat import _rules_ground, _rules_space

    ctx = SimpleNamespace()
    assert _rules_ground.weapon_name("smg", ctx, 2) == "Overclocked SMG"
    assert _rules_ground.weapon_name("smg", ctx) == "SMG"
    # The space twin accepts and ignores the seam.
    _space_ctx = SimpleNamespace()
    assert _rules_space.weapon_name(
        "light_laser", _space_ctx, 3,
    ) == _rules_space.weapon_name("light_laser", _space_ctx)
