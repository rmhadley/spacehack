"""Ground combat enemy AI — extracted from _ground.py's inline enemy turn.

Mirrors :mod:`combat._ai` which handles ship enemy behavior. Currently
simple (attack-if-in-range), but extracted so multi-enemy support and
smarter AI (movement, cover-seeking, etc.) can be added without
inflating the main combat loop.
"""

from __future__ import annotations

from .. import world
from .. import message_log as _ml
from ..engine import RNG


def run_ground_enemy_turn(
    ctx,
    *,
    enemy_weapon_id: str,
    enemy_spec,
    enemy_ap: int,
    player_pos: world.Position,
    enemy_pos: world.Position,
    dist: int,
    armor_defense: int,
) -> tuple[int, int]:
    """Execute one enemy turn during ground combat.

    The enemy fires its weapon if it has one, has AP remaining, and
    the player is within weapon range.

    Returns ``(new_enemy_ap, damage_dealt)`` where ``damage_dealt`` is
    the amount of player HP reduced this turn (0 if miss or no weapon).
    The caller is responsible for applying ``damage_dealt`` to the
    player's HP pool and checking for defeat.

    Pure logic — no rendering. The caller (``run_ground_combat``)
    renders frames and advances the turn clock.
    """
    # Lazy import avoids circular import (both _ground.py and _ai_ground.py
    # reference each other's functions).
    from ._ground import _ground_hit_chance, _ground_damage

    if not enemy_weapon_id or enemy_ap <= 0:
        return (enemy_ap, 0)

    from ..data.ground_weapons import find_ground_weapon as _find_gw
    try:
        _ews = _find_gw(enemy_weapon_id)
    except KeyError:
        return (enemy_ap, 0)

    _result_ap = enemy_ap
    _damage_dealt = 0

    if _ews and dist <= _ews.max_range and dist >= _ews.min_range:
        _hit = RNG.randint(1, 100) <= _ground_hit_chance(
            enemy_weapon_id, enemy_spec.reflexes, ctx.ground_stats.reflexes,
        )
        if _hit:
            _damage_dealt = _ground_damage(
                enemy_weapon_id, enemy_spec.strength, armor_defense,
            )
            ctx.log.add_colored(
                f"{enemy_spec.name} hits you for {_damage_dealt}!",
                _ml.COLOR_ENEMY_ACTION,
            )
        else:
            ctx.log.add_colored(
                f"{enemy_spec.name} fires but misses!",
                _ml.COLOR_ENEMY_ACTION,
            )
        _result_ap -= _ews.ap_cost if _ews else 1

    return (_result_ap, _damage_dealt)
