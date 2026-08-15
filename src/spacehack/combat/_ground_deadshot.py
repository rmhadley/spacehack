"""Deadshot trait helpers for ground combat.

Deadshot turns the railgun into a single devastating verb: a shot
spends the pilot's entire remaining AP pool (each AP beyond the
weapon's base 2 adds +5 hit and +4 damage), and a kill chains to an
automatic follow-up shot at the nearest target in range and line of
sight. Chain shots use the railgun's base stats, consume one round
each, and stop on a miss, a target that survives, or an empty
magazine — the same commitment-and-consequence rhythm as Charger.

Mirrors :mod:`._ground_charger`'s hook pattern so the ground rules
module stays within its line budget. State is reached through lazy
imports of :mod:`._rules_ground` at call time (never at module load)
to avoid a circular import.
"""

from __future__ import annotations

from ..engine import RNG
from ..data.ground_weapons import find_ground_weapon as _find_gw
from ._stats import _distance
from ._ground_math import calc_ground_move_dodge as _calc_ground_move_dodge

_RAILGUN_ID: str = "railgun"

# Safety net against runaway chains; the magazine gates it first
# (the railgun holds 12 rounds).
_MAX_CHAIN_LINKS: int = 12


def is_deadshot(ctx, weapon_id: str) -> bool:
    """Whether ``weapon_id`` gets Deadshot behavior for this player."""
    try:
        return (
            "deadshot" in getattr(ctx, "player_traits", ())
            and _find_gw(weapon_id).id == _RAILGUN_ID
        )
    except KeyError:
        return False


def ap_power_hit_bonus(ctx, weapon_id: str) -> int:
    """Hit bonus for a Deadshot railgun shot: +5 per AP beyond the base 2."""
    if not is_deadshot(ctx, weapon_id):
        return 0
    from . import _rules_ground as _rules
    return max(0, _rules.player_ap(ctx) - 2) * 5


def ap_power_damage_bonus(ctx, weapon_id: str) -> int:
    """Damage bonus for a Deadshot railgun shot: +4 per AP beyond the base 2."""
    if not is_deadshot(ctx, weapon_id):
        return 0
    from . import _rules_ground as _rules
    return max(0, _rules.player_ap(ctx) - 2) * 4


def record_player_kill(ctx, weapon_id: str) -> None:
    """Count a Deadshot railgun kill, then resolve the follow-up chain.

    Called from :func:`._ground_charger.record_player_kill` after every
    player kill. Chain kills feed the chain recursively through
    :func:`_resolve_chain`.
    """
    if not is_deadshot(ctx, weapon_id) or not hasattr(ctx, "player_counters"):
        return
    ctx.player_counters.railgun_kills += 1
    _resolve_chain(ctx, weapon_id)


# ---------------------------------------------------------------------------
# Chain resolution
# ---------------------------------------------------------------------------

def _chain_target(ctx, weapon_id: str):
    """Return the nearest living enemy in range + line of sight, or None."""
    from . import _rules_ground as _rules
    from ._animations import _has_los
    _alive = _rules.get_enemies(ctx)
    if not _alive:
        return None
    _pos = ctx.player.pos
    _max_range = _find_gw(weapon_id).max_range
    _gm = _rules._state.game_map
    _best = None
    _best_d = float("inf")
    for _e in _alive:
        _d = _distance(_pos, _e.pos)
        if _d > _max_range:
            continue
        if not _has_los(_gm, _pos.x, _pos.y, _e.pos.x, _e.pos.y):
            continue
        if _d < _best_d:
            _best, _best_d = _e, _d
    return _best


def _chain_hit_chance(ctx, enemy, weapon_id: str) -> int:
    """Hit chance for a chain shot: base railgun stats, no Deadshot bonus."""
    from . import _rules_ground as _rules
    _er = enemy.spec.reflexes if enemy.spec else 10
    _move_dodge = _calc_ground_move_dodge(enemy.cells_moved_this_turn)
    _penalty = _rules._ground_point_blank_penalty(
        weapon_id, int(_distance(ctx.player.pos, enemy.pos)),
    )
    return _rules._ground_hit_chance_raw(
        weapon_id, ctx.ground_stats.reflexes, _er,
        target_dodge_bonus=_move_dodge, hit_bonus=0, range_penalty=_penalty,
    )


def _chain_damage(ctx, enemy, weapon_id: str) -> int:
    """Damage for a chain shot: base railgun stats, no Deadshot bonus."""
    from . import _rules_ground as _rules
    _armor = enemy.spec.armor if enemy.spec else 0
    return _rules._ground_damage_raw(
        weapon_id, ctx.ground_stats.strength, _armor,
        strength_step=_rules._PLAYER_STRENGTH_STEP,
    )


def _consume_chain_round(ctx, weapon_id: str) -> bool:
    """Spend one round from the equipped railgun; False when empty/absent."""
    from ..ground_equipment import consume_weapon_round
    _instances = getattr(ctx, "equipped_ground_weapons", [])
    for _i, _inst in enumerate(_instances):
        if _inst.weapon_id != weapon_id:
            continue
        if _inst.loaded_ammo is None or _inst.loaded_ammo <= 0:
            return False
        _instances[_i] = consume_weapon_round(_inst)
        return True
    return False


def _fire_chain_link(ctx, game_map, console, weapon_id: str, target) -> bool:
    """Fire one chain shot at ``target``; return True if it killed.

    Rolls a base-stats railgun shot, spends the round's ammo (already
    consumed by the caller), animates it, and runs the normal on_kill
    pipeline (loot, XP, counters) plus the railgun kill counter.
    """
    from . import _rules_ground as _rules
    _hit = RNG.randint(1, 100) <= _chain_hit_chance(ctx, target, weapon_id)
    _dmg = _chain_damage(ctx, target, weapon_id) if _hit else 0
    if _hit:
        target.hp -= _dmg
        if target.entity is not None:
            target.entity.hp = max(0, target.hp)
    if console is not None:
        from ._animations import _MISS_POPUP, _damage_popup_for
        from ._shot_animations import _animate_ground_shot
        _popup = _MISS_POPUP if not _hit else _damage_popup_for(_dmg, 0, False)
        _animate_ground_shot(
            console, ctx, game_map,
            ctx.player.pos, target.pos, weapon_id,
            is_hit=_hit, damage=_popup,
            render_callback=_rules.render_frame,
        )
    if target.alive:
        return False
    if hasattr(ctx, "player_counters"):
        ctx.player_counters.railgun_kills += 1
    _rules.on_kill(game_map, target, ctx)
    return True


def _resolve_chain(ctx, weapon_id: str) -> None:
    """Fire automatic follow-up shots until the chain breaks.

    Each link targets the nearest living enemy in range + LOS, spends
    one round, and keeps going only while every shot kills. The
    player never moves during the chain and stays at the AP they
    fired with.
    """
    from . import _rules_ground as _rules
    _state = _rules._state
    if _state is None:
        return
    for _ in range(_MAX_CHAIN_LINKS):
        _target = _chain_target(ctx, weapon_id)
        if _target is None:
            break
        if not _consume_chain_round(ctx, weapon_id):
            break
        if not _fire_chain_link(
            ctx, _state.game_map, _state.console, weapon_id, _target,
        ):
            break
