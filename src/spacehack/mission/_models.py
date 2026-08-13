"""Mutable runtime mission models.

Static mission definitions remain in :mod:`spacehack.data.missions`; this
module contains only the session-state records used by the runtime.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum, auto


MAX_ACTIVE_MISSIONS: int = 5


@dataclass
class MissionBoard:
    """Per-NPC, per-city mission offering state."""

    npc_id: str
    slots: list[str | None] = field(default_factory=list)
    max_slots: int = 5
    last_refresh_month: int = 0
    planet_id: str = ""


class MissionStatus(Enum):
    """Lifecycle state of an :class:`ActiveMission`."""

    IN_PROGRESS = auto()
    COMPLETED = auto()
    FAILED = auto()


@dataclass
class ActiveMission:
    """Mutable state of one player-accepted mission."""

    mission_id: str
    is_procedural: bool = False
    status: MissionStatus = MissionStatus.IN_PROGRESS
    title: str = ""

    # Delivery fields
    required_cargo_size: int = 0
    delivery_target_npc_id: str | None = None
    delivery_target_planet_id: str | None = None

    # Bounty fields
    bounty_spawn_id: str | None = None
    target_enemy_id: str | None = None
    target_system_id: str | None = None
    bounty_target_name: str | None = None
    bounty_target_squad_size: int = 1
    bounty_target_loadout_pct: int = 0
    bounty_wingmate_enemy_id: str | None = None
    tier: int = 1

    # Intercept fields
    heist_target_good_id: str | None = None
    heist_good_secured: bool = False

    # Salvage fields
    salvage_wreck_enemy_id: str | None = None
    salvage_layout_id: str | None = None
    salvage_wreck_spawn_id: str | None = None

    # Smuggling fields
    is_smuggle: bool = False
    smuggle_good_id: str | None = None

    # Main-quest link
    main_quest_step_id: str = ""

    # Deadline
    time_deadline: tuple[int, int, int] | None = None
    deadline_days: int = 0
    accept_day: int = 0

    # Reward
    reward_credits: int = 0
    reward_xp: int = 0
    early_bonus_pct: int = 0
