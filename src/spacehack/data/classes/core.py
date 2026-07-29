"""Core playable classes: pirate, merchant, bounty_hunter.

Gameplay numbers (base HP, starting credits, pilot-skill bonuses) live
ON the spec rather than in a separate lookup table so adding a
class becomes a one-file change. The cosmetic HUD read-outs and
combat-init formulas in :mod:`spacehack.character` pull
:attr:`GameClass.hp_base`, :attr:`GameClass.credits` and
:attr:`GameClass.skill_bonus` directly.
"""
from . import GameClass
from ..pilot_skills import PilotSkills


# Frozen tuples so callers can't accidentally mutate the catalog at
# runtime; iteration order is the menu order used by
# :func:`spacehack.data.classes.list_classes`.
CLASSES: tuple[GameClass, ...] = (
    GameClass(
        id="pirate",
        name="Pirate",
        description="Lives beyond the law. Plunders and pillages.",
        hp_base=9,
        credits=1000,
        skill_bonus=PilotSkills(gunnery=8, piloting=0, engineering=0),
    ),
    GameClass(
        id="merchant",
        name="Merchant",
        description="Trades goods across the systems.",
        hp_base=7,
        credits=1000,
        skill_bonus=PilotSkills(gunnery=0, piloting=0, engineering=8),
    ),
    GameClass(
        id="bounty_hunter",
        name="Bounty Hunter",
        description="Hunts the wanted. Paid in credits.",
        hp_base=10,
        credits=1000,
        skill_bonus=PilotSkills(gunnery=3, piloting=3, engineering=3),
    ),
)
