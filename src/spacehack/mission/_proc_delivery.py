"""Procedural delivery mission generation."""
from __future__ import annotations

import random

from ..data.missions import MissionSpec
from ._proc_shared import (
    _planet_npc_ids,
    _roll_tier,
    planet_destinations,
)


_DELIVERY_HOP_RANGES = {
    1: (0, 2),   # local: same system, neighbor, or 2 hops
    2: (1, 3),   # regional
    3: (2, 5),   # sector
    4: (3, 7),   # frontier
}


def _pick_destination(origin_planet_id, tier, rng, reachable_system_ids):
    """One candidate destination as (planet, system, hops), or None.

    Candidate planets are landable, NPC-bearing, and not the origin.
    """
    _candidates = planet_destinations(
        origin_planet_id, tier, hop_ranges=_DELIVERY_HOP_RANGES,
    )
    if not _candidates:
        return None
    return rng.choice(_candidates)


def _delivery_terms(tier, hops, rng):
    """(cargo, deadline, credits, xp) scaled by tier and distance.

    Deadline: hops * 30 + slack ≈ 2-3x real travel time (a system
    crossing is ~18 days; multi-hop runs add local transit). Credits
    keep the design-doc tier ranges (T1 50-100 .. T4 1000-1500) plus
    a +10$/hop pickup-distance bonus.
    """
    _cargo_ranges = {1: (5, 10), 2: (10, 20), 3: (20, 40), 4: (40, 60)}
    cargo_lo, cargo_hi = _cargo_ranges.get(tier, (5, 10))
    cargo = rng.randint(cargo_lo, cargo_hi)
    deadline = max(20, hops * 30 + rng.randint(10, 20))
    credits = cargo * 5 * (tier + 1) + hops * 10
    xp = cargo * 2 * tier + hops * 4
    return cargo, deadline, credits, xp


def _delivery_display(dest_planet_id, dest_system_id, cargo, hops, tier):
    """Destination-focused title/description (the pickup is where you stand)."""
    try:
        from ..data.planets import find_planet_spec as _fps_dest
        dest_name = _fps_dest(dest_planet_id).name
    except KeyError:
        dest_name = dest_planet_id
    try:
        from ..data.solar_systems import find_solar_system as _fss
        dest_system_name = _fss(dest_system_id).name
    except KeyError:
        dest_system_name = dest_system_id

    title = f"Deliver to {dest_name} in {dest_system_name}"
    _hop_desc = "same system" if hops == 0 else f"{hops} jump(s)"
    description = (
        f"Deliver {cargo} units to {dest_name} in "
        f"{dest_system_name}. ({_hop_desc}, tier {tier})."
    )
    return title, description


def generate_delivery_mission(
    origin_planet_id: str,
    max_tier: int,
    rng: random.Random,
    counter: int = 0,
    giver_npc_id: str = "",
) -> MissionSpec | None:
    """One delivery mission from ``origin_planet_id`` (``None`` if no
    candidate destination exists). ``rng`` is the shared engine RNG;
    ``counter`` makes the generated id unique per board fill."""
    from ..data.solar_systems import reachable_system_ids

    tier = _roll_tier(max_tier, rng)
    _picked = _pick_destination(origin_planet_id, tier, rng, reachable_system_ids)
    if _picked is None:
        return None
    dest_planet_id, dest_system_id, hops = _picked

    # The delivery target NPC on the destination planet.
    npc_ids = _planet_npc_ids(dest_planet_id)
    target_npc_id = rng.choice(npc_ids) if npc_ids else None

    cargo, deadline, credits, xp = _delivery_terms(tier, hops, rng)
    gen_id = f"proc_delivery_{origin_planet_id}_{dest_planet_id}_{counter}_{tier}"
    title, description = _delivery_display(
        dest_planet_id, dest_system_id, cargo, hops, tier,
    )

    return MissionSpec(
        id=gen_id, title=title, description=description,
        giver_npc_id=giver_npc_id, faction="merchants",
        mission_type="delivery", tier=tier,
        reward_credits=credits, reward_xp=xp,
        deadline_days=deadline, early_bonus_pct=25,
        required_cargo_size=cargo,
        delivery_target_npc_id=target_npc_id,
        delivery_target_planet_id=dest_planet_id,
        origin_planet_id=origin_planet_id,
    )

