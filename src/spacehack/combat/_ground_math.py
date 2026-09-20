"""Pure shared helpers for ground combat math."""

from __future__ import annotations

from ..data.ground_weapons import find_ground_weapon as _find_gw
from ..data.quality import effective_weapon_spec


def ground_point_blank_penalty(weapon_id: str, distance: int) -> int:
    """Return the accuracy penalty for firing inside minimum range."""
    _ws = _find_gw(weapon_id)
    return max(0, _ws.min_range - distance) * 35


def calc_ground_move_dodge(cells_moved: int) -> int:
    """Return movement evade: +5% per cell, capped at 30."""
    return min(cells_moved * 5, 30)


def ground_hit_chance_raw(
    weapon_id: str,
    attacker_reflexes: int,
    target_reflexes: int,
    target_dodge_bonus: int = 0,
    hit_bonus: int = 0,
    range_penalty: int = 0,
    quality: int = 0,
) -> int:
    """Base hit chance before movement dodge.

    Half-rate convention shared with ship combat (Gunnery * 0.5):
    each point of attacker Reflexes adds +0.5% accuracy and each
    point of target Reflexes subtracts 0.5% (dodge). All six stats
    live on the same 0-100 scale. ``hit_bonus`` carries permanent
    bonuses (e.g. the Sharpshooter trait's +10%). ``quality`` scales
    the weapon's accuracy contribution (doc 47 phase 2).
    """
    _ws = effective_weapon_spec(weapon_id, quality)
    return max(5, min(95,
        _ws.accuracy + attacker_reflexes // 2 - target_reflexes // 2
        - target_dodge_bonus + hit_bonus - range_penalty,
    ))


# Player stat progression steps every 5 points: every 5 Strength adds
# +1 melee damage. Monsters keep the legacy 10-point divisor so their
# tuned damage values are unchanged.
_PLAYER_STRENGTH_STEP: int = 5


def ground_damage_raw(
    weapon_id: str, strength: int, armor_defense: int,
    melee_bonus: int = 0, strength_step: int = 10, quality: int = 0,
) -> int:
    """Raw hit damage: base + melee bonuses - armor, minimum 1.

    ``armor_bypass`` weapons ignore armor entirely; plasma halves
    ``armor_defense``; ``melee_bonus`` (cybernetic arms) applies only
    to melee weapons. ``strength_step`` is the divisor for the melee
    strength bonus — the player passes ``_PLAYER_STRENGTH_STEP`` (5)
    so every 5 points of Strength adds +1 melee damage. ``quality``
    scales the weapon's damage (doc 47 phase 2).
    """
    _ws = effective_weapon_spec(weapon_id, quality)
    _str_bonus = (strength // strength_step) if _ws.damage_type == 'melee' else 0
    _melee = melee_bonus if _ws.damage_type == 'melee' else 0
    if _ws.armor_bypass:
        armor_defense = 0
    elif _ws.damage_type == 'plasma':
        armor_defense = armor_defense // 2
    return max(1, _ws.damage + _str_bonus + _melee - armor_defense)
