"""Pure shared helpers for ground combat range and movement math."""

from __future__ import annotations

from ..data.ground_weapons import find_ground_weapon as _find_gw


def ground_point_blank_penalty(weapon_id: str, distance: int) -> int:
    """Return the accuracy penalty for firing inside minimum range."""
    _ws = _find_gw(weapon_id)
    return max(0, _ws.min_range - distance) * 35


def calc_ground_move_dodge(cells_moved: int) -> int:
    """Return movement evade: +5% per cell, capped at 30."""
    return min(cells_moved * 5, 30)
