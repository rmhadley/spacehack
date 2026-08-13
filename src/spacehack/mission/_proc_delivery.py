"""Procedural delivery mission generation."""
from __future__ import annotations

import random

from ..data.missions import MissionSpec
from ._proc_shared import (
    _dest_candidates_in_system,
    _planet_npc_ids,
    _planet_to_system,
    _roll_tier,
)


def generate_delivery_mission(
    origin_planet_id: str,
    max_tier: int,
    rng: random.Random,
    counter: int = 0,
    giver_npc_id: str = "",
) -> MissionSpec | None:
    """Generate one procedural delivery mission originating from
    ``origin_planet_id``.

    Algorithm:
      1. Roll tier: weighted 1..max_tier using min-of-two-rolls.
      2. Find the origin system, then filter reachable systems by
         tier-appropriate jump range (via BFS hop count).
      3. Pick a destination planet in a different system with a
         landable port and at least one NPC.
      4. Generate cargo, deadline, and reward scaled by tier + distance.

    Returns ``None`` if no suitable destination planet can be found
    (e.g. isolated system with no jump gates, or no NPCs on any
    reachable planet).

    Args:
        origin_planet_id: planet registry key (e.g. ``"earth"``).
        max_tier: planet's ``mission_tier`` — caps the rolled tier.
        rng: shared :data:`engine.RNG` for deterministic generation.
        counter: unique per-fill counter appended to the generated ID.
    """
    from ..data.solar_systems import reachable_system_ids

    # 1. Weighted tier roll.
    tier = _roll_tier(max_tier, rng)

    # 2. Resolve origin system and reachable systems.
    p2s = _planet_to_system()
    origin_system_id = p2s.get(origin_planet_id)
    if origin_system_id is None:
        return None

    reachable = reachable_system_ids(origin_system_id, max_hops=10)

    # Tier → hop range: same-system deliveries are allowed for tier 1.
    _hop_ranges = {
        1: (0, 2),   # local: same system, neighbor, or 2 hops
        2: (1, 3),   # regional
        3: (2, 5),   # sector
        4: (3, 7),   # frontier
    }
    min_hops, max_hops = _hop_ranges.get(tier, (0, 10))

    # Build candidate (system_id, hop_count) pairs.
    _candidates: list[tuple[str, int]] = []
    if min_hops == 0:
        # Include same-system destinations (hop count 0).
        _candidates.append((origin_system_id, 0))
    for sys_id, hops in reachable.items():
        if min_hops <= hops <= max_hops:
            _candidates.append((sys_id, hops))

    if not _candidates:
        return None

    # 3. Collect all landable planets (excl. origin) in candidate
    #    systems, with at least one NPC. Uses a shared helper so
    #    same-system and different-system enumeration share one path.
    _dest_candidates: list[tuple[str, str, int]] = []  # (planet_id, system_id, hops)
    for cand_sys_id, hops in _candidates:
        _dest_candidates.extend(
            _dest_candidates_in_system(cand_sys_id, origin_planet_id, hops),
        )

    if not _dest_candidates:
        return None

    dest_planet_id, dest_system_id, hops = rng.choice(_dest_candidates)

    # 4. Pick a delivery target NPC on the destination planet.
    npc_ids = _planet_npc_ids(dest_planet_id)
    target_npc_id = rng.choice(npc_ids) if npc_ids else None

    # 5. Cargo amount, scaled by tier.
    _cargo_ranges = {1: (5, 10), 2: (10, 20), 3: (20, 40), 4: (40, 60)}
    cargo_lo, cargo_hi = _cargo_ranges.get(tier, (5, 10))
    cargo = rng.randint(cargo_lo, cargo_hi)

    # 6. Deadline: ~30 days per hop for comfortable travel.
    #    All solar systems are 200x140 cells. Crossing one from gate to gate
    #    takes ~180 moves = 18 days at speed 10. A multi-hop journey also
    #    includes launch-area transit + local destination transit (~2 extra
    #    systems of travel). Formula: hops * 30 + random(10-20) gives roughly
    #    2-3x the actual travel time for slow ships.
    deadline = max(20, hops * 30 + rng.randint(10, 20))

    # 7. Reward: credits scale by cargo * 5 * (tier + 1) so tier ranges
    #    match the design doc: T1 50-100, T2 150-300, T3 400-800, T4 1000-1500.
    #    A per-jump bonus (+10$/hop) pays more for deliveries picked up
    #    far from the destination — payout scales with pickup location.
    credits = cargo * 5 * (tier + 1) + hops * 10
    xp = cargo * 2 * tier + hops * 4

    # 8. Generated ID: unique per run, deterministic from RNG state.
    gen_id = f"proc_delivery_{origin_planet_id}_{dest_planet_id}_{counter}_{tier}"

    # 9. Construct display title and description. Destination-focused:
    #    "Deliver to <landmark> in <system>" — the pickup planet is
    #    where the player is standing, so it's not spelled out.
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
    # Build a simple description mentioning cargo and jumps.
    _hop_desc = "same system" if hops == 0 else f"{hops} jump(s)"
    description = (
        f"Deliver {cargo} units to {dest_name} in "
        f"{dest_system_name}. ({_hop_desc}, tier {tier})."
    )

    # 10. Determine faction + giver NPC from the board.
    # For procedural missions, we use the board's NPC id as giver.
    # The faction defaults to "merchants" for delivery missions.
    # These fields are filled in by the caller based on the board.

    return MissionSpec(
        id=gen_id,
        title=title,
        description=description,
        giver_npc_id=giver_npc_id,
        faction="merchants",
        mission_type="delivery",
        tier=tier,
        reward_credits=credits,
        reward_xp=xp,
        deadline_days=deadline,
        early_bonus_pct=25,
        required_cargo_size=cargo,
        delivery_target_npc_id=target_npc_id,
        delivery_target_planet_id=dest_planet_id,
        origin_planet_id=origin_planet_id,
    )

