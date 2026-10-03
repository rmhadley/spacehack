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
    pirate_opener_damage_pct as _opener_damage_pct,
)
from ._ground_math import _PLAYER_STRENGTH_STEP
from ._ground_math import ground_damage_raw as _ground_damage_raw

# Doc 53 SETTLED 2: the self-splash tombstone killer line, pinned
# verbatim — a splash suicide never names a stale enemy.
SELF_SPLASH_KILLER = "your own explosives"


def is_explosive(weapon_id: str) -> bool:
    """Whether a ground weapon resolves as an area blast."""
    return _find_gw(weapon_id).damage_type == "explosive"


def _blast_share(full_damage: int, is_primary: bool, ctx) -> int:
    """One victim's share: full at the primary, the splash percent
    (50 + Demolitionist) beside it — never below 1."""
    if is_primary:
        return full_damage
    _splash_pct = 50 + _demolitionist_splash_bonus(ctx)
    return max(1, full_damage * _splash_pct // 100)


def apply_explosive_enemy_hit(
    weapon_id: str,
    enemy,
    primary,
    ctx,
    *,
    primary_hit: bool = True,
    quality: int = 0,
    opener_pct: int = 100,
    center=None,
) -> tuple | None:
    """Apply one enemy's primary-or-splash share of an explosion.

    ``opener_pct`` is the Pirate opener's damage multiplier (doc 49
    SETTLED 5): it scales the enemy shares only — the player's own
    splash share never benefits from the opener. ``center`` is the
    blast's cell (the primary's position unless the explosion
    detonated on a force-field tile — doc 48 p9's absorbed rocket,
    where NO body is primary and every share is splash).
    """
    if not enemy.alive:
        return None
    _center = center if center is not None else primary.pos
    _dx = abs(enemy.pos.x - _center.x)
    _dy = abs(enemy.pos.y - _center.y)
    if _dx > 1 or _dy > 1:
        return None
    _armor = enemy.spec.armor if enemy.spec else 0
    _full_damage = _ground_damage_raw(
        weapon_id, ctx.ground_stats.strength, _armor,
        strength_step=_PLAYER_STRENGTH_STEP, quality=quality,
    ) * opener_pct // 100
    _is_primary = primary_hit and center is None and enemy is primary
    _damage = _blast_share(_full_damage, _is_primary, ctx)
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


def _damage_field_victims(state, weapon_id, ctx, center, quality) -> None:
    """Field tiles as blast victims (doc 48 SETTLED 42): every shell
    tile within the blast's 3x3 pays — FULL weapon damage at the
    detonation cell, the splash share beside it. The code behind "a
    rocket at the shell carves multiple tiles" (the called-out
    counter)."""
    from ._ancients import damage_field_tile

    _tiles = state.game_map.field_tiles or {}
    if not _tiles:
        return
    _full = _ground_damage_raw(
        weapon_id, ctx.ground_stats.strength, 0,
        strength_step=_PLAYER_STRENGTH_STEP, quality=quality,
    )
    _splash = _blast_share(_full, False, ctx)
    for _dy in (-1, 0, 1):
        for _dx in (-1, 0, 1):
            _cell = (center.x + _dx, center.y + _dy)
            if _cell in _tiles:
                damage_field_tile(
                    ctx, state.game_map, _cell,
                    _full if (_dx, _dy) == (0, 0) else _splash,
                )


def _blast_player_share(state, weapon_id, primary, ctx, quality, center) -> int:
    """The player's own splash when caught in the blast (doc 53 tally
    + the settled self-splash killer line), plus the blast noise at
    the detonation cell (SETTLED 17/22: the explosion draws entities
    from where it landed, not where it was fired)."""
    _player_dx = abs(ctx.player.pos.x - center.x)
    _player_dy = abs(ctx.player.pos.y - center.y)
    if _player_dx <= 1 and _player_dy <= 1:
        _player_damage = _apply_self_splash(
            state, weapon_id, primary, ctx, quality,
        )
    else:
        _player_damage = 0
    noise.emit(ctx, state.game_map, center, weapon_id, by_player=True)
    return _player_damage


def explosive_blast(
    state,
    weapon_id: str,
    primary,
    ctx,
    *,
    primary_hit: bool = True,
    quality: int = 0,
    center=None,
) -> tuple[tuple, int]:
    """Resolve an explosive impact around ``primary`` (or ``center``
    — the absorbed-rocket detonation on a field tile) with friendly
    fire. A direct hit damages primary fully; a miss catches it for
    half damage alongside neighboring cells. The player also takes
    half damage nearby. Field tiles in the area carve (doc 48 p9).
    """
    _center = center if center is not None else primary.pos
    _enemy_hits = tuple(
        _hit for _enemy in state.enemies
        if (_hit := apply_explosive_enemy_hit(
            weapon_id, _enemy, primary, ctx, primary_hit=primary_hit,
            quality=quality, opener_pct=_opener_damage_pct(
                ctx, enemy_fired=state.enemy_fired,
                opener_spent=state.opener_spent,
            ), center=center,
        )) is not None
    )
    _damage_field_victims(state, weapon_id, ctx, _center, quality)
    _player_damage = _blast_player_share(
        state, weapon_id, primary, ctx, quality, _center,
    )
    return _enemy_hits, _player_damage
