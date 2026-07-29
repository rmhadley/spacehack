"""Trait catalog — frozen dataclass + registry.

Each trait is earned at level 20 or 30 (shared pool) if the player's
counters and/or skill values meet its requirements.

Design doc: ``docs/design/in_progress/02_DESIGN_XP_LEVELING.md``
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Trait:
    """One player trait — earned at level 20 or 30 if requirements met.

    ``counters`` is a tuple of ``(field_name, min_value)`` pairs.
    For skill fields (gunnery/piloting/engineering) the check reads
    from ``ctx.stats``; for playstyle counters it reads from
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
# Registry — shared pool for both level 20 and 30 milestones.
# Initial set: 4 traits testing 4 different counter types.
# Full trait design pass will come later.
# ---------------------------------------------------------------------------

SHARPSHOOTER = Trait(
    id="sharpshooter",
    name="Sharpshooter",
    description="+10% hit chance in combat",
    counters=(("gunnery", 40),),
)

TRADE_ROUTE = Trait(
    id="trade_route",
    name="Trade Route",
    description="-5% buy / +5% sell prices",
    counters=(("deliveries_completed", 10),),
)

ACE_PILOT = Trait(
    id="ace_pilot",
    name="Ace Pilot",
    description="+1 AP per turn in combat",
    counters=(("combat_flees", 10),),
)

JUGGERNAUT = Trait(
    id="juggernaut",
    name="Juggernaut",
    description="-50% missile damage taken",
    counters=(("total_kills", 30),),
)

ALL_TRAITS: tuple[Trait, ...] = (
    SHARPSHOOTER,
    TRADE_ROUTE,
    ACE_PILOT,
    JUGGERNAUT,
)


def find_trait(trait_id: str) -> Trait:
    """Look up a trait by its ``id``.  Raises ``KeyError`` if not found."""
    for t in ALL_TRAITS:
        if t.id == trait_id:
            return t
    raise KeyError(f"Trait {trait_id!r} not found")
