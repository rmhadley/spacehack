"""Shared PilotSkills dataclass used by species, classes, and enemy specs.

A frozen dataclass replacing the duplicated ``{"gunnery": X, "piloting": Y,
"engineering": Z}`` dict pattern across three catalogs. Eliminates the
``None`` + ``__post_init__`` hack that every dict-field dataclass needed.

Usage in data files::

    from ..pilot_skills import PilotSkills

    skill_bonus=PilotSkills(gunnery=15, piloting=10, engineering=0)

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


__all__ = ["PilotSkills"]
