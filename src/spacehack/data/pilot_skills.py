"""Shared PilotSkills and GroundStats dataclasses used by species, classes,
and enemy specs.

A frozen dataclass replacing the duplicated ``{"gunnery": X, "piloting": Y,
"engineering": Z}`` dict pattern across three catalogs. Eliminates the
``None`` + ``__post_init__`` hack that every dict-field dataclass needed.

Usage in data files::

    from ..pilot_skills import PilotSkills, GroundStats

    skill_bonus=PilotSkills(gunnery=15, piloting=10, engineering=0)
    ground_bonus=GroundStats(reflexes=1, strength=0, stamina=2)

    # instead of:
    skill_bonus={"gunnery": 15, "piloting": 10, "engineering": 0}
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class PilotSkills:
    """Per-pilot skill bonuses — additive to the base rating.

    Each field corresponds to one combat-relevant skill:

        gunnery: weapon accuracy modifier.
        piloting: AP-per-turn and dodge modifier.
        engineering: power efficiency and shield recharge modifier.
    """
    gunnery: int = 0
    piloting: int = 0
    engineering: int = 0


@dataclass(frozen=True)
class GroundStats:
    """Per-character ground combat stat bonuses — additive to the base 10.

    Each field corresponds to one ground-combat stat:

        reflexes:  ranged accuracy, dodge bonus.
        strength:  melee damage, heavy-weapon efficiency.
        stamina:   HP pool, damage resistance.
    """
    reflexes: int = 0
    strength: int = 0
    stamina: int = 0


__all__ = ["PilotSkills", "GroundStats"]
