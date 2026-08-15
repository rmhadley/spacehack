"""Combat data types — enums and the EnemyInstance dataclass.

Extracted from the monolithic ``combat.py`` to keep type definitions
in their own module with no runtime logic.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum, auto

from .. import world


class CombatPhase(Enum):
    PLAYER_TURN = auto()
    ENEMY_TURN = auto()
    VICTORY = auto()
    DEFEAT = auto()


class CombatMode(Enum):
    DEFAULT = auto()
    MOVING = auto()
    FIRING = auto()


@dataclass
class EnemyInstance:
    """Mutable copy of an enemy ship during combat."""
    spec_id: str
    name: str
    char: str
    fg: tuple[int, int, int]
    hull: int = 100
    max_hull: int = 100
    shields: int = 0
    max_shields: int = 0
    shields_charged: bool = False
    power_pool: int = 5
    ap_remaining: int = 3
    ap_total: int = 3
    pos: world.Position = field(default_factory=lambda: world.Position(0, 0))
    weapons: tuple[str, ...] = ()
    modules: tuple[str, ...] = ()
    weapon_ammo: dict[str, int] = field(default_factory=dict)
    pilot_gunnery: int = 20
    pilot_piloting: int = 20
    pilot_engineering: int = 10
    power_gen: int = 3
    max_power: int = 10
    cells_moved_this_turn: int = 0
    shield_regen_rate: int = 0
    alive: bool = True


@dataclass
class CombatResult:
    """Bundles the outcome and defeated-entity tracking from a combat
    encounter. Returned by :func:`run_combat` so callers access named
    fields instead of unpacking a naked tuple."""
    outcome: str = "VICTORY"  # "VICTORY", "DEFEAT", or "DISENGAGED" (ground)
    defeated_names: list[str] = field(default_factory=list)
    defeated_bounty_ids: list[str] = field(default_factory=list)
    defeated_heist_ids: list[str] = field(default_factory=list)
    defeated_spec_ids: list[str] = field(default_factory=list)
