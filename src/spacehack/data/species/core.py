"""Core playable species: human + martian (the two starting options).

Gameplay numbers (HP bonus, pilot-skill bonuses) live ON the spec
rather than in a separate lookup table so adding a species becomes
a one-file change. Edit :data:`SPECIES` to add or tweak a species
- the rest of the game pulls :attr:`Species.hp_bonus` and
:attr:`Species.skill_bonus` directly.
"""
from . import Species
from ..pilot_skills import PilotSkills, GroundStats


# Frozen tuples so callers can't accidentally mutate the catalog at
# runtime; iteration order is the menu order used by
# :func:`spacehack.data.species.list_species`.
SPECIES: tuple[Species, ...] = (
    Species(
        id="human",
        name="Human",
        description="Native to Earth. Versatile and adaptable.",
        hp_bonus=0,
        skill_bonus=PilotSkills(gunnery=2, piloting=0, engineering=2),
        ground_bonus=GroundStats(reflexes=2, strength=0, stamina=2),
    ),
    Species(
        id="martian",
        name="Martian",
        description="Native to Mars. Hardy in extremes, adapted to low-gravity.",
        hp_bonus=1,
        skill_bonus=PilotSkills(gunnery=0, piloting=5, engineering=0),
        ground_bonus=GroundStats(reflexes=5, strength=0, stamina=0),
    ),
)
