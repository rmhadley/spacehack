"""Trait catalog — frozen dataclass + registry.

Each trait is earned at level 40 or 50 (shared pool) if the player's
counters and/or skill values meet its requirements. Level 60 is
reserved for a future capstone specialization.

Design doc: ``docs/design/in_progress/02_DESIGN_XP_LEVELING.md``
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Trait:
    """One player trait — earned at level 40 or 50 if requirements met.

    ``counters`` is a tuple of ``(field_name, min_value)`` pairs.
    For ship skill fields (gunnery/piloting/engineering) the check reads
    from ``ctx.stats``; ground skill fields (reflexes/strength/stamina)
    read from ``ctx.ground_stats``; playstyle counters read from
    ``ctx.player_counters``.  ALL must be met for the trait to
    appear at a milestone.

    ``rep_required`` is an optional ``(faction_id, attitude)`` gate
    checked against ``ctx.faction_reputation`` (future use).
    """

    id: str
    name: str
    description: str
    counters: tuple[tuple[str, int], ...]
    rep_required: tuple[str, str] | None = None


# ---------------------------------------------------------------------------
# Registry — shared pool for both level 40 and 50 milestones.
# Traits reward both focused skill investment and repeated playstyle choices.


SHARPSHOOTER = Trait(
    id="sharpshooter",
    name="Sharpshooter",
    description="+10% hit chance in combat",
    counters=(("gunnery", 40),),
)

HAULER = Trait(
    id="hauler",
    name="Hauler",
    description="Merchant boards shift one mission tier higher (T1 missions are removed)",
    counters=(("merchant_missions_completed", 20),),
)

FIXER = Trait(
    id="fixer",
    name="Fixer",
    description="Bar boards shift one mission tier higher (T1 missions are removed)",
    counters=(("bar_missions_completed", 20),),
)

HUNTER = Trait(
    id="hunter",
    name="Hunter",
    description="Bounty boards shift one mission tier higher (T1 missions are removed)",
    counters=(("bounty_missions_completed", 20),),
)

ACE_PILOT = Trait(
    id="ace_pilot",
    name="Ace Pilot",
    description="+1 AP per turn in combat",
    counters=(("piloting", 40),),
)

JUGGERNAUT = Trait(
    id="juggernaut",
    name="Juggernaut",
    description="Take 1 less damage from each ground attack",
    counters=(("total_kills", 30),),
)

CHARGER = Trait(
    id="charger",
    name="Charger",
    description="Melee weapons reach current AP; charging grants +5 hit and +1 damage per tile",
    counters=(("melee_kills", 40),),
)

EVASIVE = Trait(
    id="evasive",
    name="Evasive",
    description="+5% baseline ground evade",
    counters=(("reflexes", 40),),
)

PACK_MULE = Trait(
    id="pack_mule",
    name="Pack Mule",
    description="+2 Expedition Pack slots",
    counters=(("strength", 40),),
)

IRONCLAD = Trait(
    id="ironclad",
    name="Ironclad",
    description="+6 maximum ground HP",
    counters=(("stamina", 40),),
)

SYSTEMS_EXPERT = Trait(
    id="systems_expert",
    name="Systems Expert",
    description="+10 maximum ship power",
    counters=(("engineering", 40),),
)

DEMOLITIONIST = Trait(
    id="demolitionist",
    name="Demolitionist",
    description="+25% explosive splash damage",
    counters=(("explosive_hits", 15),),
)

LASER_SPECIALIST = Trait(
    id="laser_specialist",
    name="Laser Specialist",
    description="+10% laser hit chance",
    counters=(("laser_shots", 100),),
)

MISSILEER = Trait(
    id="missileer",
    name="Missileer",
    description="+10% missile hit chance",
    counters=(("missile_shots", 15),),
)

PLASMA_SAVANT = Trait(
    id="plasma_savant",
    name="Plasma Savant",
    description="Plasma weapons cost 1 less AP",
    counters=(("plasma_shots", 100),),
)

ALL_TRAITS: tuple[Trait, ...] = (
    SHARPSHOOTER,
    HAULER,
    FIXER,
    HUNTER,
    ACE_PILOT,
    JUGGERNAUT,
    CHARGER,
    EVASIVE,
    PACK_MULE,
    IRONCLAD,
    SYSTEMS_EXPERT,
    DEMOLITIONIST,
    LASER_SPECIALIST,
    MISSILEER,
    PLASMA_SAVANT,
)


def find_trait(trait_id: str) -> Trait:
    """Look up a trait by its ``id``.  Raises ``KeyError`` if not found."""
    for t in ALL_TRAITS:
        if t.id == trait_id:
            return t
    raise KeyError(f"Trait {trait_id!r} not found")
