"""Procedural bar missions: intercept, smuggling, and salvage."""
from __future__ import annotations

import random
from typing import Callable as _Callable

from ..data.missions import MissionSpec
from ._proc_shared import (
    _dest_candidates_in_system,
    _planet_npc_ids,
    _planet_to_system,
    _roll_tier,
)


_HEIST_GOODS: tuple[str, ...] = (
    "electronics", "machine_parts", "luxury_goods", "fuel_cells",
)


_MERCHANT_POOLS: dict[int, list[str]] = {
    1: ["merchant_hauler"],
    2: ["merchant_hauler"],
    3: ["merchant_freighter"],
    4: ["merchant_caravan"],
}


_PATROL_POOLS: dict[int, list[str]] = {
    1: ["pirate_scout"],
    2: ["pirate_scout"],
    3: ["pirate_raider"],
    4: ["pirate_raider", "pirate_captain"],
}


_WRECK_LAYOUTS: dict[int, tuple[str, str]] = {
    1: ("derelict_scout", "scout_a"),
    2: ("derelict_scout", "scout_a"),
    3: ("derelict_freighter", "freightliner_a"),
    4: ("derelict_freighter", "freightliner_a"),
}


_INTERCEPT_HOP_RANGES: dict[int, tuple[int, int]] = {
    1: (1, 3), 2: (1, 4), 3: (2, 6), 4: (3, 8),
}


_SMUGGLE_HOP_RANGES: dict[int, tuple[int, int]] = {
    1: (0, 2), 2: (1, 3), 3: (2, 5), 4: (3, 7),
}


_SALVAGE_HOP_RANGES: dict[int, tuple[int, int]] = {
    1: (1, 3), 2: (1, 4), 3: (2, 6), 4: (3, 8),
}


def _generate_bar_intercept(
    origin_planet_id: str,
    tier: int,
    rng: random.Random,
    counter: int,
    giver_npc_id: str,
) -> MissionSpec | None:
    """Generate a procedural intercept (merchant hunting) bar mission."""
    from ..data.solar_systems import reachable_system_ids

    p2s = _planet_to_system()
    origin_system_id = p2s.get(origin_planet_id)
    if origin_system_id is None:
        return None

    reachable = reachable_system_ids(origin_system_id, max_hops=10)
    min_hops, max_hops = _INTERCEPT_HOP_RANGES.get(tier, (1, 10))

    _candidates = [
        (sid, h) for sid, h in reachable.items()
        if min_hops <= h <= max_hops and sid != origin_system_id
    ]
    if not _candidates:
        return None

    target_system_id, hops = rng.choice(_candidates)

    # Pick merchant ship + heist good.
    _pool = _MERCHANT_POOLS.get(tier, ["merchant_hauler"])
    enemy_id = rng.choice(_pool)
    heist_good = rng.choice(_HEIST_GOODS)

    # Squad: escorts at T2+.
    squad_size = 1
    wingmate_id = None
    if tier >= 2:
        squad_size = rng.randint(1, min(tier, 3))
        if squad_size > 1:
            wingmate_id = "pirate_scout" if tier <= 3 else "pirate_raider"

    # Round-trip deadline (travel both ways).
    deadline = max(30, hops * 60 + rng.randint(10, 30))

    # Reward: intercepts are round trips with a fight and a cargo
    # return, so they carry a premium over one-way deliveries
    # (~1.5x the old band). They still sit a notch below T4 named
    # bounties at the top end.
    credits = tier * 300 + hops * 60
    xp = tier * 50 + hops * 10

    try:
        from ..data.npc_ships import find_npc_ship
        enemy_name = find_npc_ship(enemy_id).name
    except KeyError:
        enemy_name = enemy_id

    gen_id = f"proc_intercept_{origin_planet_id}_{target_system_id}_{counter}_{tier}"
    title = f"Intercept: {enemy_name}"
    _escort_note = f" ({squad_size - 1} escorts)" if squad_size > 1 else ""
    description = (
        f"Ambush a {enemy_name}{_escort_note} hauling {heist_good} "
        f"{hops} jump(s) away. Return the cargo to the bar."
    )

    return MissionSpec(
        id=gen_id,
        title=title,
        description=description,
        giver_npc_id=giver_npc_id,
        faction="bar",
        mission_type="intercept",
        tier=tier,
        reward_credits=credits,
        reward_xp=xp,
        deadline_days=deadline,
        early_bonus_pct=25,
        target_enemy_id=enemy_id,
        target_system_id=target_system_id,
        bounty_target_squad_size=squad_size,
        bounty_wingmate_enemy_id=wingmate_id,
        heist_target_good_id=heist_good,
        origin_planet_id=origin_planet_id,
    )


def _generate_bar_smuggling(
    origin_planet_id: str,
    tier: int,
    rng: random.Random,
    counter: int,
    giver_npc_id: str,
) -> MissionSpec | None:
    """Generate a procedural smuggling (contraband delivery) bar mission."""
    from ..data.solar_systems import reachable_system_ids

    p2s = _planet_to_system()
    origin_system_id = p2s.get(origin_planet_id)
    if origin_system_id is None:
        return None

    reachable = reachable_system_ids(origin_system_id, max_hops=10)
    min_hops, max_hops = _SMUGGLE_HOP_RANGES.get(tier, (0, 10))

    # Collect destination candidates (same pattern as delivery).
    _dest_candidates: list[tuple[str, str, int]] = []
    if min_hops == 0:
        _dest_candidates.extend(
            _dest_candidates_in_system(origin_system_id, origin_planet_id, 0),
        )
    for sys_id, hops in reachable.items():
        if min_hops <= hops <= max_hops:
            _dest_candidates.extend(
                _dest_candidates_in_system(sys_id, origin_planet_id, hops),
            )

    if not _dest_candidates:
        return None

    dest_planet_id, _dest_sys_id, hops = rng.choice(_dest_candidates)
    npc_ids = _planet_npc_ids(dest_planet_id)
    target_npc_id = rng.choice(npc_ids) if npc_ids else None

    # Cargo and rewards.
    _cargo_ranges = {1: (5, 10), 2: (10, 20), 3: (20, 40), 4: (40, 60)}
    cargo_lo, cargo_hi = _cargo_ranges.get(tier, (5, 10))
    cargo = rng.randint(cargo_lo, cargo_hi)

    # Reward: smuggling is the same shape as a delivery but carries
    # scan/confiscation risk (or a smuggler-hold module tax), so it
    # pays ~20-30% above deliveries at every tier plus a per-hop
    # bonus. XP stays at delivery parity — the premium is credits.
    credits = cargo * 6 * (tier + 1) + hops * 15
    xp = cargo * 2 * tier + hops * 4
    deadline = max(20, hops * 30 + rng.randint(10, 20))

    smuggle_good = rng.choice(_HEIST_GOODS)

    try:
        from ..data.planets import find_planet_spec
        dest_name = find_planet_spec(dest_planet_id).name
    except KeyError:
        dest_name = dest_planet_id

    gen_id = f"proc_smuggle_{origin_planet_id}_{dest_planet_id}_{counter}_{tier}"
    title = f"Smuggle: {dest_name}"
    description = (
        f"Move {cargo} units of contraband to {dest_name} "
        f"({hops} jump(s)). Militia scans are a risk."
    )

    return MissionSpec(
        id=gen_id,
        title=title,
        description=description,
        giver_npc_id=giver_npc_id,
        faction="bar",
        mission_type="smuggling",
        tier=tier,
        reward_credits=credits,
        reward_xp=xp,
        deadline_days=deadline,
        early_bonus_pct=25,
        required_cargo_size=cargo,
        delivery_target_npc_id=target_npc_id,
        delivery_target_planet_id=dest_planet_id,
        origin_planet_id=origin_planet_id,
        is_smuggle=True,
        smuggle_good_id=smuggle_good,
    )


def _generate_bar_salvage(
    origin_planet_id: str,
    tier: int,
    rng: random.Random,
    counter: int,
    giver_npc_id: str,
) -> MissionSpec | None:
    """Generate a procedural salvage (wreck boarding) bar mission."""
    from ..data.solar_systems import reachable_system_ids

    p2s = _planet_to_system()
    origin_system_id = p2s.get(origin_planet_id)
    if origin_system_id is None:
        return None

    reachable = reachable_system_ids(origin_system_id, max_hops=10)
    min_hops, max_hops = _SALVAGE_HOP_RANGES.get(tier, (1, 10))

    _candidates = [
        (sid, h) for sid, h in reachable.items()
        if min_hops <= h <= max_hops and sid != origin_system_id
    ]
    if not _candidates:
        return None

    target_system_id, hops = rng.choice(_candidates)

    # Patrol.
    _pool = _PATROL_POOLS.get(tier, ["pirate_scout"])
    patrol_id = rng.choice(_pool)

    _sq_ranges = {1: (1, 1), 2: (1, 2), 3: (1, 2), 4: (2, 3)}
    _sq_lo, _sq_hi = _sq_ranges.get(tier, (1, 1))
    squad_size = rng.randint(_sq_lo, _sq_hi)

    wingmate_id = None
    if squad_size > 1 and tier >= 3:
        wingmate_id = "pirate_scout" if tier == 3 else "pirate_raider"

    # Wreck + layout.
    wreck_id, layout_id = _WRECK_LAYOUTS.get(tier, ("derelict_scout", "scout_a"))

    # Component.
    component = rng.choice(_HEIST_GOODS)

    # Round-trip deadline.
    deadline = max(30, hops * 60 + rng.randint(15, 35))

    credits = tier * 180 + hops * 40
    xp = tier * 35 + hops * 7

    try:
        from ..data.npc_ships import find_npc_ship
        patrol_name = find_npc_ship(patrol_id).name
    except KeyError:
        patrol_name = patrol_id

    gen_id = f"proc_salvage_{origin_planet_id}_{target_system_id}_{counter}_{tier}"
    title = f"Salvage: {patrol_name} Wreck"
    description = (
        f"Recover {component} from a derelict wreck {hops} jump(s) away. "
        f"{squad_size} pirate(s) guard the site."
    )

    return MissionSpec(
        id=gen_id,
        title=title,
        description=description,
        giver_npc_id=giver_npc_id,
        faction="bar",
        mission_type="salvage",
        tier=tier,
        reward_credits=credits,
        reward_xp=xp,
        deadline_days=deadline,
        early_bonus_pct=25,
        target_enemy_id=patrol_id,
        target_system_id=target_system_id,
        bounty_target_squad_size=squad_size,
        bounty_wingmate_enemy_id=wingmate_id,
        heist_target_good_id=component,
        salvage_wreck_enemy_id=wreck_id,
        salvage_layout_id=layout_id,
        origin_planet_id=origin_planet_id,
    )


_BarGenFn = _Callable[
    [str, int, random.Random, int, str], MissionSpec | None
]


_BAR_GENERATORS: dict[str, _BarGenFn] = {
    "intercept": _generate_bar_intercept,
    "smuggling": _generate_bar_smuggling,
    "salvage": _generate_bar_salvage,
}


_BAR_TYPE_WEIGHTS: dict[str, float] = {
    "intercept": 35.0,
    "smuggling": 35.0,
    "salvage": 30.0,
}


def generate_bar_mission(
    origin_planet_id: str,
    max_tier: int,
    rng: random.Random,
    counter: int = 0,
    giver_npc_id: str = "",
) -> MissionSpec | None:
    """Generate one procedural bar mission (intercept, smuggling, or salvage).

    Algorithm:
      1. Roll tier via shared :func:`_roll_tier`.
      2. Pick a mission type with weighted randomness.
      3. Dispatch to the sub-generator for that type.

    Returns ``None`` if the sub-generator can't find a suitable target
    system or destination.
    """
    tier = _roll_tier(max_tier, rng)

    _types = list(_BAR_TYPE_WEIGHTS.keys())
    _weights = list(_BAR_TYPE_WEIGHTS.values())
    mission_type = rng.choices(_types, weights=_weights, k=1)[0]

    generator = _BAR_GENERATORS[mission_type]
    return generator(origin_planet_id, tier, rng, counter, giver_npc_id)

