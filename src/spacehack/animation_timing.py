"""Shared presentation timing for gameplay animations.

These values keep animation pacing consistent across combat, navigation,
transitions, and scripted effects. They are deliberately presentation-only;
no gameplay turn or state timing depends on them.
"""
from __future__ import annotations


COMBAT_BEAM: float = 0.025
COMBAT_IMPACT: float = 0.03
DAMAGE_POPUP: float = 0.025
EXPLOSION_RING: float = 0.035
EXPLOSION_FLASH: float = 0.04
EXPLOSION_SETTLE: float = 0.02
GROUND_STEP: float = 0.025
AUTO_NAV: float = 0.02
JUMP: float = 0.035
CITY_TRANSITION: float = 0.045
DUNGEON_BREACH: float = 0.045
SIGNAL_WAVE: float = 0.055
SIGNAL_SETTLE: float = 0.10
