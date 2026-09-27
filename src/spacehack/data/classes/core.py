"""Core playable classes: pirate, merchant, bounty_hunter.

Gameplay numbers (starting credits, stat spreads) live ON the spec
rather than in a separate lookup table so adding a class becomes a
one-file change. The spreads sit on a +6 stat-point budget per class
(doc 49 SETTLED 4/5/6/7) — the class layer mirrors the species pool;
hull HP is never a class stat (SETTLED 5: ship + modules own it).
"""
from . import GameClass
from ..pilot_skills import PilotSkills, GroundStats


# Frozen tuples so callers can't accidentally mutate the catalog at
# runtime; iteration order is the menu order used by
# :func:`spacehack.data.classes.list_classes`.
CLASSES: tuple[GameClass, ...] = (
    GameClass(
        id="pirate",
        name="Pirate",
        description="Lives beyond the law. Plunders and pillages.",
        credits=25,
        skill_bonus=PilotSkills(gunnery=3, piloting=0, engineering=0),
        ground_bonus=GroundStats(reflexes=0, strength=3, stamina=0),
    ),
    GameClass(
        id="merchant",
        name="Merchant",
        description="Trades goods across the systems.",
        credits=75,
        skill_bonus=PilotSkills(gunnery=0, piloting=0, engineering=4),
        ground_bonus=GroundStats(reflexes=0, strength=0, stamina=2),
    ),
    GameClass(
        id="bounty_hunter",
        name="Bounty Hunter",
        description="Hunts the wanted. Paid in credits.",
        credits=50,
        skill_bonus=PilotSkills(gunnery=2, piloting=2, engineering=0),
        ground_bonus=GroundStats(reflexes=2, strength=0, stamina=0),
    ),
)
