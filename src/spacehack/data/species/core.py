"""Core playable species (doc 49 SETTLED 1: the five-species roster).

Gameplay numbers (HP bonus, stat spreads, glyph/color/home, origin
trait) live ON the spec rather than in a separate lookup table so
adding a species remains a one-file change. Every species spends a +6
stat-point budget at creation (base 10 everywhere); Lalandan's −5s are
the one deliberate exception. Species never adjusts starting
reputation (doc 49 SETTLED 3-B) — that table is class-only.
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
        glyph="@",
        color=(255, 255, 255),
        home="Earth (Sol)",
        trait_id="fast_learner",
        hp_bonus=0,
        skill_bonus=PilotSkills(gunnery=1, piloting=1, engineering=1),
        ground_bonus=GroundStats(reflexes=1, strength=1, stamina=1),
    ),
    Species(
        id="martian",
        name="Martian",
        description="Native to Mars. Hardy in extremes, adapted to low-gravity.",
        glyph="@",
        color=(130, 225, 90),
        home="Mars (Sol)",
        trait_id="sturdy",
        hp_bonus=2,
        skill_bonus=PilotSkills(gunnery=0, piloting=0, engineering=0),
        ground_bonus=GroundStats(reflexes=0, strength=2, stamina=4),
    ),
    Species(
        id="cygnian",
        name="Cygnian",
        description="Cygni b - the orbital yards (Cygni)",
        glyph="&",
        color=(170, 130, 230),
        home="Cygni b - the orbital yards (Cygni)",
        trait_id="momentum",
        hp_bonus=0,
        skill_bonus=PilotSkills(gunnery=2, piloting=4, engineering=0),
        ground_bonus=GroundStats(reflexes=0, strength=0, stamina=0),
    ),
    Species(
        id="sirian",
        name="Sirian",
        description="Binary Station - the Binary Eye (Sirius)",
        # U+2666: the CP437 card-suit diamond (procedurally patched by
        # the engine) — NOT U+25C6, which is not on the bitmap tilesheet.
        glyph="\u2666",
        color=(185, 215, 245),
        home="Binary Station - the Binary Eye (Sirius)",
        trait_id="longshot",
        hp_bonus=0,
        skill_bonus=PilotSkills(gunnery=4, piloting=0, engineering=0),
        ground_bonus=GroundStats(reflexes=2, strength=0, stamina=0),
    ),
    Species(
        id="lalandan",
        name="Lalandan",
        description="Whisper - the Vault (Lalande)",
        glyph="Q",
        color=(255, 130, 195),
        home="Whisper - the Vault (Lalande)",
        trait_id="nimble",
        hp_bonus=0,
        skill_bonus=PilotSkills(gunnery=0, piloting=0, engineering=0),
        ground_bonus=GroundStats(reflexes=6, strength=-5, stamina=-5),
    ),
)
