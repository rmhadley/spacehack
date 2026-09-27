"""Ground weapon-action mechanics — reload and weapon-set swap.

Split from ``_rules_ground`` (the architecture ratchet, doc 49 phase
2): the action cluster takes the combat state explicitly (the
``_ground_blast`` precedent) so the rules module keeps only its
public ``(ctx)`` signatures as thin wrappers.
"""

from __future__ import annotations

from ..data.ground_weapons import find_ground_weapon as _find_gw
from ..ground_weapon_sets import swap_sets_logged


def _reloadable_slots(state, ctx) -> tuple[tuple[int, object, object, int], ...]:
    """Return active weapons with a matching reserve and room to reload."""
    from ..ground_equipment import reserve_ammo_count

    candidates = []
    for _slot, _instance in enumerate(ctx.equipped_ground_weapons):
        if _slot >= len(state.active_weapon_list) or not state.active_weapon_list[_slot]:
            continue
        _spec = _find_gw(_instance.weapon_id)
        if _instance.loaded_ammo is None or _instance.loaded_ammo >= _spec.ammo_capacity:
            continue
        _reserve = reserve_ammo_count(ctx.bandolier, _spec.ammo_type)
        if _reserve > 0:
            candidates.append((_slot, _instance, _spec, _reserve))
    return tuple(candidates)


def _reload_slot(state, ctx, slot: int) -> bool:
    """Reload one validated slot transactionally and charge its AP cost."""
    from ..ground_equipment import apply_reload

    from ..ground_equipment import display_name
    from ..ground_reload_ui import _log_name_line

    _instance = ctx.equipped_ground_weapons[slot]
    _spec = _find_gw(_instance.weapon_id)
    _wname = display_name("weapon", _instance.weapon_id, _instance.quality)
    if state.player_ap < _spec.reload_ap_cost:
        ctx.log.add(
            f"Need {_spec.reload_ap_cost} AP to reload "
            f"(have {state.player_ap}).",
        )
        return False
    try:
        _new = apply_reload(
            ctx.equipped_ground_weapons, slot, ctx.bandolier,
        )
    except (IndexError, KeyError, ValueError) as exc:
        _log_name_line(ctx, "", _wname, _instance.quality, f": {exc}")
        return False
    state.player_ap -= _spec.reload_ap_cost
    _log_name_line(
        ctx, "Reloaded ", _wname, _instance.quality,
        f" ({_new.loaded_ammo}/{_spec.ammo_capacity}).",
    )
    return True


async def reload_weapon(state, ctx) -> bool:
    """Reload the first dry active slot with reserve (doc 50 SETTLED 5).

    Deterministic — no chooser: the multi-slot chooser shipped dead (the
    dispatch called this coroutine without await, so the live R key
    never ran), and a tutorial-honest reload is one keypress anyway.
    """
    _candidates = _reloadable_slots(state, ctx)
    if not _candidates:
        ctx.log.add("No active weapon can be reloaded.")
        return False
    return _reload_slot(state, ctx, _candidates[0][0])


async def swap_weapon_sets(state, ctx) -> bool:
    """Swap the whole active set for the holstered set (doc 51 phase 2).

    One mid-turn action: 1 AP, never turn-ending. Magazines and quality
    ride the instances; the fresh set arrives all-armed (combat-start
    flags over the fists-fallback weapon list — an empty active set
    swaps to fists, the SETTLED 1 floor). Out of 1 AP: refuse, no
    mutation.
    """
    from ._rules_ground import player_weapons

    if state.player_ap < 1:
        ctx.log.add("Not enough AP to swap weapon sets.")
        return False
    swap_sets_logged(
        ctx.equipped_ground_weapons, ctx.holstered_ground_weapons, ctx.log,
    )
    state.active_weapon_list = [True] * len(player_weapons(ctx))
    state.player_ap -= 1
    return True
