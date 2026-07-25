"""Core playable classes: pirate, merchant, bounty_hunter.

Gameplay numbers (base HP, starting gold, pilot-skill bonuses) live
ON the spec rather than in a separate lookup table so adding a
class becomes a one-file change. The cosmetic HUD read-outs and
combat-init formulas in :mod:`spacehack.character` pull
:attr:`GameClass.hp_base`, :attr:`GameClass.gold` and
:attr:`GameClass.skill_bonus` directly.
"""
from . import GameClass


# Frozen tuples so callers can't accidentally mutate the catalog at
# runtime; iteration order is the menu order used by
# :func:`spacehack.data.classes.list_classes`.
CLASSES: tuple[GameClass, ...] = (
    GameClass(
        id="pirate",
        name="Pirate",
        description="Lives beyond the law. Plunders and pillages.",
        hp_base=9,
        gold=100,
        skill_bonus={"gunnery": 15, "piloting": 10, "engineering": 0},
    ),
    GameClass(
        id="merchant",
        name="Merchant",
        description="Trades goods across the systems.",
        hp_base=7,
        gold=180,
        skill_bonus={"gunnery": 0, "piloting": 5, "engineering": 15},
    ),
    GameClass(
        id="bounty_hunter",
        name="Bounty Hunter",
        description="Hunts the wanted. Paid in credits.",
        hp_base=10,
        gold=70,
        skill_bonus={"gunnery": 10, "piloting": 10, "engineering": 5},
    ),
)
