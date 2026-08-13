"""Roguelike-flavored combat log lines.

Every attack message in the game flows through this module so space
and ground combat speak one dialect:

    You fire your Light Laser at Pirate Raider. It hits for 8 damage (2 shields, 6 hull)!
    Assault Drone fires its Drone Laser at you. It misses!
    Ice Worm swings its Monster Claws at you. It hits for 5 damage!

Weapons carry their own verbs — missiles are launched, melee is
swung, everything else is fired — and hits report the shield/hull
split and glancing quality, so a player reviewing the scrollable
history (``\\`` in combat) can tell exactly what happened and why.
"""

from __future__ import annotations


def weapon_family(weapon_id: str) -> str:
    """Return the verb-driving family: ``"missile"``, ``"melee"`` or ``"ranged"``.

    Ship weapons classify on ``slot_type``; ground weapons on
    ``damage_type``. Unknown ids fall back to ``"ranged"`` so a
    catalog miss still yields a sensible line.
    """
    try:
        from ..data.weapons import find_weapon as _fw
        return "missile" if _fw(weapon_id).slot_type == "missile" else "ranged"
    except KeyError:
        pass
    try:
        from ..data.ground_weapons import find_ground_weapon as _fgw
        return "melee" if _fgw(weapon_id).damage_type == "melee" else "ranged"
    except KeyError:
        return "ranged"


def _indefinite_article(weapon_name: str) -> str:
    """``"an"`` before a vowel-sound initial (EMP Missile), else ``"a"``."""
    return "an" if weapon_name[:1].lower() in "aeiou" else "a"


def _player_opening(weapon_id: str, weapon_name: str) -> str:
    """Player attack opening: ``"You fire your Light Laser at"``."""
    _fam = weapon_family(weapon_id)
    if _fam == "melee":
        return f"You swing your {weapon_name} at"
    if _fam == "missile":
        return f"You launch {_indefinite_article(weapon_name)} {weapon_name} at"
    return f"You fire your {weapon_name} at"


def _enemy_opening(enemy_name: str, weapon_id: str, weapon_name: str) -> str:
    """Enemy attack opening: ``"Pirate Raider fires its Light Laser at"``."""
    _fam = weapon_family(weapon_id)
    if _fam == "melee":
        return f"{enemy_name} swings its {weapon_name} at"
    if _fam == "missile":
        return f"{enemy_name} launches {_indefinite_article(weapon_name)} {weapon_name} at"
    return f"{enemy_name} fires its {weapon_name} at"


def _result_clause(
    *,
    hit: bool,
    hull_dmg: int,
    shield_dmg: int,
    is_strip: bool,
    is_glancing: bool,
) -> str:
    """Outcome clause: ``"It misses!"`` / ``"It hits for 6 damage!"``.

    Hits report the total damage, plus the shield/hull split whenever
    shields absorbed part of it (space combat) so the log explains
    why a target is still flying. EMP strips show the shields-only
    line; glancing hits (halved by high target Piloting) are labeled.
    """
    if not hit:
        return "It misses!"
    _shield_word = "shield" if shield_dmg == 1 else "shields"
    if is_strip:
        return f"It strips {shield_dmg} {_shield_word}!"
    _verb = "glances for" if is_glancing else "hits for"
    _total = hull_dmg + shield_dmg
    if shield_dmg > 0 and hull_dmg > 0:
        _split = f" ({shield_dmg} {_shield_word}, {hull_dmg} hull)"
    elif shield_dmg > 0:
        _split = f" ({shield_dmg} {_shield_word})"
    else:
        _split = ""
    return f"It {_verb} {_total} damage{_split}!"


def player_attack_line(
    weapon_id: str,
    weapon_name: str,
    target_name: str,
    *,
    hit: bool,
    hull_dmg: int = 0,
    shield_dmg: int = 0,
    is_strip: bool = False,
    is_glancing: bool = False,
) -> str:
    """Full player-attack message: ``"{opening} {target}. {result}"``.

    ``hull_dmg`` is the damage to the target's health pool (hull in
    space, HP on the ground); ``shield_dmg`` is what shields absorbed
    (always 0 in ground combat). ``is_strip`` marks EMP-style hits.
    """
    return (
        f"{_player_opening(weapon_id, weapon_name)} {target_name}. "
        f"{_result_clause(hit=hit, hull_dmg=hull_dmg, shield_dmg=shield_dmg, is_strip=is_strip, is_glancing=is_glancing)}"
    )


def enemy_attack_line(
    enemy_name: str,
    weapon_id: str,
    weapon_name: str,
    *,
    hit: bool,
    hull_dmg: int = 0,
    shield_dmg: int = 0,
    is_strip: bool = False,
    is_glancing: bool = False,
) -> str:
    """Full enemy-attack message: ``"{enemy} {opening} you. {result}"``."""
    return (
        f"{_enemy_opening(enemy_name, weapon_id, weapon_name)} you. "
        f"{_result_clause(hit=hit, hull_dmg=hull_dmg, shield_dmg=shield_dmg, is_strip=is_strip, is_glancing=is_glancing)}"
    )
