"""Ground explosive-blast resolution — the friendly-fire blast math.

Split from ``_rules_ground`` (the architecture ratchet): the blast
cluster takes the combat state explicitly; the rules module keeps its
public signatures as thin wrappers over these.
"""

from __future__ import annotations

from .. import noise
from ..data.ground_weapons import find_ground_weapon as _find_gw
from ..xp import (
    apply_ground_damage_reduction as ground_damage_taken,
    demolitionist_splash_bonus as _demolitionist_splash_bonus,
)
from ._ground_math import _PLAYER_STRENGTH_STEP
from ._ground_math import ground_damage_raw as _ground_damage_raw

# Doc 53 SETTLED 2: the self-splash tombstone killer line, pinned
# verbatim — a splash suicide never names a stale enemy.
SELF_SPLASH_KILLER = "your own explosives"


def is_explosive(weapon_id: str) -> bool:
    """Whether a ground weapon resolves as an area blast."""
    return _find_gw(weapon_id).damage_type == "explosive"


def apply_explosive_enemy_hit(
    weapon_id: str,
    enemy,
    primary,
    ctx,
    *,
    primary_hit: bool = True,
    quality: int = 0,
) -> tuple | None:
    """Apply one enemy's primary-or-splash share of an explosion."""
    if not enemy.alive:
        return None
    _dx = abs(enemy.pos.x - primary.pos.x)
    _dy = abs(enemy.pos.y - primary.pos.y)
    if _dx > 1 or _dy > 1:
        return None
    _armor = enemy.spec.armor if enemy.spec else 0
    _full_damage = _ground_damage_raw(
        weapon_id, ctx.ground_stats.strength, _armor,
        strength_step=_PLAYER_STRENGTH_STEP, quality=quality,
    )
    _is_primary = enemy is primary and primary_hit
    if _is_primary:
        _damage = _full_damage
    else:
        _splash_pct = 50 + _demolitionist_splash_bonus(ctx)
        _damage = max(1, _full_damage * _splash_pct // 100)
    enemy.hp -= _damage
    if enemy.entity is not None:
        enemy.entity.hp = max(0, enemy.hp)
    return enemy, _damage, _is_primary


def _apply_self_splash(state, weapon_id, primary, ctx, quality) -> int:
    """The player's own splash share when caught in the blast: the
    doc 53 ground damage tally increments on the applied (post-DR)
    amount and the tracked killer becomes the settled self line."""
    _full_damage = _ground_damage_raw(
        weapon_id, 0, state.armor_defense, quality=quality,
    )
    _splash_pct = 50 + _demolitionist_splash_bonus(ctx)
    _splash_damage = max(1, _full_damage * _splash_pct // 100)
    _player_damage = ground_damage_taken(ctx, _splash_damage)
    if hasattr(ctx, "player_counters"):
        ctx.player_counters.ground_damage_taken += _player_damage
    state.player_hp -= _player_damage
    state.last_attacker = SELF_SPLASH_KILLER
    return _player_damage


def explosive_blast(
    state,
    weapon_id: str,
    primary,
    ctx,
    *,
    primary_hit: bool = True,
    quality: int = 0,
) -> tuple[tuple, int]:
    """Resolve an explosive impact around ``primary`` with friendly fire.

    A direct hit damages primary fully; a miss catches it for half damage
    alongside neighboring cells. The player also takes half damage nearby.
    """
    _enemy_hits = tuple(
        _hit for _enemy in state.enemies
        if (_hit := apply_explosive_enemy_hit(
            weapon_id, _enemy, primary, ctx, primary_hit=primary_hit,
            quality=quality,
        )) is not None
    )
    _player_dx = abs(ctx.player.pos.x - primary.pos.x)
    _player_dy = abs(ctx.player.pos.y - primary.pos.y)
    if _player_dx <= 1 and _player_dy <= 1:
        _player_damage = _apply_self_splash(
            state, weapon_id, primary, ctx, quality,
        )
    else:
        _player_damage = 0
    # Blast event at the impact cell (SETTLED 17/22): the explosion
    # draws entities from where it landed, not where it was fired —
    # the firing report already emitted at the shooter.
    noise.emit(
        ctx, state.game_map, primary.pos, weapon_id, by_player=True,
    )
    return _enemy_hits, _player_damage
