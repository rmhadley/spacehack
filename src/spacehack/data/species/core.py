"""Core playable species: human + martian (the two starting options).

Gameplay numbers (HP bonus, pilot-skill bonuses) live ON the spec
rather than in a separate lookup table so adding a species becomes
a one-file change. Edit :data:`SPECIES` to add or tweak a species
- the rest of the game pulls :attr:`Species.hp_bonus` and
:attr:`Species.skill_bonus` directly.
"""
from . import Species


# Frozen tuples so callers can't accidentally mutate the catalog at
# runtime; iteration order is the menu order used by
# :func:`spacehack.data.species.list_species`.
SPECIES: tuple[Species, ...] = (
    Species(
        id="human",
        name="Human",
        description="Native to Earth. Versatile and adaptable.",
        hp_bonus=0,
        skill_bonus={"gunnery": 5, "piloting": 0, "engineering": 5},
    ),
    Species(
        id="martian",
        name="Martian",
        description="Native to Mars. Hardy in extremes, adapted to low-gravity.",
        hp_bonus=1,
        skill_bonus={"gunnery": 5, "piloting": 10, "engineering": 5},
    ),
)
