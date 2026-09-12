"""Shared presentation timing for gameplay animations.

These values keep animation pacing consistent across combat, navigation,
transitions, and scripted effects. They are deliberately presentation-only;
no gameplay turn or state timing depends on them.

The module-level speed scale is user preference (Options menu), not save
state: it is derived from the config file at startup and updated on Apply,
like the engine's window settings. Consumers apply it via ``scaled()``.
"""
from __future__ import annotations


COMBAT_BEAM: float = 0.025
COMBAT_IMPACT: float = 0.03
DAMAGE_POPUP: float = 0.025
# Per-cell travel for projectile weapons (kinetic tracers, plasma
# bolts) — faster than the missile's arc, slower than an instant beam.
COMBAT_PROJECTILE: float = 0.028
# Per-cell travel for missiles and lobbed explosives (slow, visible arc).
COMBAT_MISSILE: float = 0.035
# Frame pacing for the melee slash flash.
COMBAT_MELEE: float = 0.045
EXPLOSION_RING: float = 0.035
EXPLOSION_FLASH: float = 0.04
EXPLOSION_SETTLE: float = 0.02
GROUND_STEP: float = 0.025
AUTO_NAV: float = 0.02
# Per-step pacing for dungeon auto-explore (the O key).
AUTO_EXPLORE: float = 0.02
JUMP: float = 0.035
CITY_TRANSITION: float = 0.045
# Transit arrival pulse frames (the stop's glow finds the player in a
# busy city; see city_transit.animate_transit_arrival).
TRANSIT_ARRIVAL: float = 0.05
DUNGEON_BREACH: float = 0.045
SIGNAL_WAVE: float = 0.055
SIGNAL_SETTLE: float = 0.10
# Descent elevator frames (see descent_animation.animate_descent).
DESCENT: float = 0.075

# User-selectable animation speed multiplier (0.0 plays frames with no
# delay). Set from DisplayConfig.animation_speed at startup and on Apply.
_SPEED_SCALE: float = 1.0


def set_speed_scale(scale: float) -> None:
    """Set the global animation speed multiplier; negative values clamp to 0."""
    global _SPEED_SCALE
    _SPEED_SCALE = max(0.0, float(scale))


def speed_scale() -> float:
    """Return the active animation speed multiplier."""
    return _SPEED_SCALE


def scaled(seconds: float) -> float:
    """Return a frame delay under the active animation speed setting.

    The scale is a SPEED multiplier: 2.0 halves every delay, 4.0 quarters
    it, and 0.0 removes the delay entirely (instant playback).
    """
    if _SPEED_SCALE <= 0.0:
        return 0.0
    return seconds / _SPEED_SCALE
