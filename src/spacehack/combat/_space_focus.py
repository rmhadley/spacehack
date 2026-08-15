"""Focus trait helpers for space combat.

Focus turns a one-weapon loadout into a single devastating verb: with
exactly one weapon enabled, that weapon's AP, power, and range are all
doubled, and it deals double damage beyond half its (doubled) range —
the kiting payoff for the pilot who holds the line. The player
controls the gate entirely through the weapon toggles (1-9): toggle a
second weapon on and Focus goes quiet, exactly like Charger/Deadshot's
per-shot commitment.

Mirrors :mod:`._ground_deadshot`'s hook pattern so the space rules
module stays within its line budget. Combat session state is reached
through lazy imports of :mod:`._rules_space` at call time (never at
module load) to avoid a circular import.
"""

from __future__ import annotations

from ..data.weapons import find_weapon as _find_weapon
from ..xp import plasma_savant_ap_discount as _plasma_ap_discount


def _focused_weapon_id(ctx) -> str | None:
    """Return the single enabled weapon's id, or None when not focused.

    Focus is live only while exactly one weapon is toggled on — the
    player-controlled gate. ``None`` covers both the no-trait case and
    any 0/2+ active-weapon state.
    """
    if "focus" not in getattr(ctx, "player_traits", ()):
        return None
    from . import _rules_space as _rules
    if _rules._state is None:
        return None
    _active = [
        _rules._state.weapons_list[i]
        for i in range(len(_rules._state.weapons_list))
        if i < len(_rules._state.active_weapons)
        and _rules._state.active_weapons[i]
    ]
    return _active[0] if len(_active) == 1 else None


def is_focus_active(ctx) -> bool:
    """Whether the player's Focus trait is live right now."""
    return _focused_weapon_id(ctx) is not None


def ap_cost(weapon_id: str, ctx) -> int:
    """AP cost to fire ``weapon_id``: doubled under Focus.

    The Plasma Savant discount applies before the doubling, so the
    trait still trims the effective cost of a focused plasma cannon.
    """
    _spec = _find_weapon(weapon_id)
    _discount = _plasma_ap_discount(ctx) if _spec.slot_type == "plasma" else 0
    _base = max(1, _spec.ap_cost - _discount)
    if _focused_weapon_id(ctx) != weapon_id:
        return _base
    return _base * 2


def power_cost(weapon_id: str, ctx) -> int:
    """Power cost to fire ``weapon_id``: doubled under Focus.

    Missiles never cost power, focused or not (0 x 2 = 0) — their cost
    stays the doubled AP and the spent rack.
    """
    _spec = _find_weapon(weapon_id)
    if _spec.slot_type not in ("energy", "plasma"):
        return 0
    _base = _spec.power_cost
    if _focused_weapon_id(ctx) != weapon_id:
        return _base
    return _base * 2


def max_range(weapon_id: str, ctx) -> int:
    """Effective max range: doubled for the focused weapon."""
    _spec = _find_weapon(weapon_id)
    if _focused_weapon_id(ctx) != weapon_id:
        return _spec.max_range
    return _spec.max_range * 2


def min_range(weapon_id: str, ctx) -> int:
    """Effective min range: doubled for the focused weapon."""
    _spec = _find_weapon(weapon_id)
    if _focused_weapon_id(ctx) != weapon_id:
        return _spec.min_range
    return _spec.min_range * 2


def damage_mult(weapon_id: str, ctx, distance) -> float:
    """Damage multiplier for a focused shot: 2x beyond half its range.

    Half the doubled range is the weapon's original max range, so the
    bonus pays out only while the pilot holds ground past the normal
    envelope — the kiting band Focus exists for. Close-quarters shots
    stay at base damage.
    """
    if _focused_weapon_id(ctx) != weapon_id:
        return 1.0
    _threshold = _find_weapon(weapon_id).max_range  # half of the doubled range
    return 2.0 if distance >= _threshold else 1.0
