"""Loot quality tiers (doc 47 phase 2).

Quality is a rolled per-instance tier above base on stored gear
(SETTLED 1/2): shops, starting gear, quest gear, and mission cargo
never variant — base only. The legendary row (4) ships dormant
(SETTLED 11): its multiplier exists so sell/read paths are complete,
but no phase-2 rate ladder can roll it; phase 4 turns on delve-bottom
rolls and the randart generator together.
"""

from __future__ import annotations

import dataclasses

from .ground_armor import find_ground_armor
from .ground_weapons import find_ground_weapon
from .modules import find_module

# SETTLED 10 (user, verbatim): t1/t2/t3 tokens, title-cased at the
# label seam ("Modded Kinetic Pistol"). Legendaries carry no token —
# the rolled randart name IS the label (phase 4).
QUALITY_TOKENS: tuple[str, ...] = ("modded", "overclocked", "prototype")

LEGENDARY_QUALITY: int = 4

# Per-family multiplier rows indexed by quality (0 = base), authored
# in integer hundredths so scaling is integer-exact; fractions round
# UP in magnitude — a tier never rounds a bump away (SETTLED 18;
# SETTLED 2's ~15/30/45% shape, legendary sits high per SETTLED 4).
# Tuned at playtest.
WEAPON_MULTIPLIER_PCT: tuple[int, ...] = (100, 115, 130, 145, 220)
ARMOR_MULTIPLIER_PCT: tuple[int, ...] = (100, 115, 130, 145, 220)
MODULE_MULTIPLIER_PCT: tuple[int, ...] = (100, 115, 130, 145, 220)

# The ten ModuleSpec bonus fields quality scales (doc 47.3). Price,
# tech_level, and slot_type stay catalog-fixed; negative bonuses scale
# in magnitude ("more of what it is" — a prototype Armor Plating has
# more hull AND a bigger power draw).
_MODULE_BONUS_FIELDS: tuple[str, ...] = (
    "power_gen_bonus", "max_shield_bonus", "shield_recharge_bonus",
    "cargo_bonus", "gunnery_bonus", "piloting_bonus",
    "engineering_bonus", "max_hull_bonus", "speed_bonus",
    "smuggler_cargo",
)

# Per-source 1-in-N rate ladders (t1, t2, t3) — the DOOR_RATES shape.
# Opening guesses, tuned at playtest.
KILL_QUALITY_RATES: tuple[int, int, int] = (5, 11, 25)
WRECK_QUALITY_RATES: tuple[int, int, int] = (6, 14, 30)
DIG_QUALITY_RATES: tuple[int, int, int] = (5, 12, 28)

_FAMILY_ROWS: dict[str, tuple[int, ...]] = {
    "weapon": WEAPON_MULTIPLIER_PCT,
    "armor": ARMOR_MULTIPLIER_PCT,
    "module": MODULE_MULTIPLIER_PCT,
}


def roll_quality(rates: tuple[int, ...], rng) -> int:
    """Roll one quality tier from a 1-in-N ladder, rarest-first.

    ``rates`` is the ``(t1, t2, t3)`` 1-in-N triple: a t3 hit wins
    outright, then t2, then t1; every roll missing returns 0 (base).
    No ladder entry can produce legendary (SETTLED 11).
    """
    for tier, one_in_n in reversed(list(enumerate(rates, start=1))):
        if rng.randint(1, one_in_n) == 1:
            return tier
    return 0


def quality_multiplier_pct(family: str, quality: int) -> int:
    """Return the multiplier in integer hundredths for one family/tier."""
    row = _FAMILY_ROWS.get(family)
    if row is None:
        raise ValueError(f"unknown quality family: {family!r}")
    if not 0 <= quality < len(row):
        raise ValueError(f"unknown quality tier: {quality!r}")
    return row[quality]


def quality_multiplier(family: str, quality: int) -> float:
    """Return the multiplier for one family and tier (hundredths / 100)."""
    return quality_multiplier_pct(family, quality) / 100


def _scaled(value: int, pct: int) -> int:
    """Scale one stat by hundredths, rounding fractions UP in
    magnitude at both signs — a tier never rounds a bump away
    (user ruling 2026-09-20: ceiling; damage 2 x 1.15 must read 3,
    not round back to 2)."""
    if value >= 0:
        return (value * pct + 99) // 100
    return -((-value * pct + 99) // 100)


def effective_weapon_spec(weapon_id: str, quality: int = 0):
    """Return the catalog weapon with damage/accuracy scaled by quality.

    Base quality (or a malformed negative tier) returns the catalog row
    itself; higher tiers return a ``dataclasses.replace`` copy.
    Catalogs stay descriptive (SETTLED 2).
    """
    spec = find_ground_weapon(weapon_id)
    if quality <= 0:
        return spec
    pct = _FAMILY_ROWS["weapon"][quality]
    return dataclasses.replace(
        spec,
        damage=_scaled(spec.damage, pct),
        accuracy=_scaled(spec.accuracy, pct),
    )


def effective_armor_spec(armor_id: str, quality: int = 0):
    """Return the catalog armor with defense and bonus fields scaled.

    Scales the four cybernetic bonus fields alongside defense so a
    variant of a bonus piece is better at what it does.
    """
    spec = find_ground_armor(armor_id)
    if quality <= 0:
        return spec
    pct = _FAMILY_ROWS["armor"][quality]
    return dataclasses.replace(
        spec,
        defense=_scaled(spec.defense, pct),
        **{
            name: _scaled(getattr(spec, name), pct)
            for name in ("ap_bonus", "hit_bonus", "melee_bonus", "hp_bonus")
        },
    )


def effective_module_spec(module_id: str, quality: int = 0):
    """Return the catalog ship module with all ten bonus fields scaled.

    Base quality (or a malformed negative tier) returns the catalog
    row itself; higher tiers return a ``dataclasses.replace`` copy
    with every bonus field scaled in magnitude — price, tech_level,
    and slot_type never change.
    """
    spec = find_module(module_id)
    if quality <= 0:
        return spec
    pct = _FAMILY_ROWS["module"][quality]
    return dataclasses.replace(
        spec,
        **{
            name: _scaled(getattr(spec, name), pct)
            for name in _MODULE_BONUS_FIELDS
        },
    )


def token_prefix(quality: int) -> str:
    """Return the title-cased label prefix for one tier.

    Base and legendary carry no prefix (the randart name is the
    legendary label, phase 4).
    """
    if not 0 < quality <= len(QUALITY_TOKENS):
        return ""
    return QUALITY_TOKENS[quality - 1].title() + " "
