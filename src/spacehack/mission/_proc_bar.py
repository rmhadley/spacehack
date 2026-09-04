"""Procedural bar missions: intercept, smuggling, and salvage."""
from __future__ import annotations

import random
from typing import Callable as _Callable

from ..data.missions import MissionSpec
from ._proc_shared import (
    _planet_npc_ids,
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


def _pick_system(origin_planet_id, tier, rng, hop_ranges):
    """One (system_id, hops) target for bar work, or None."""
    from ._proc_shared import hop_candidates
    _candidates = hop_candidates(
        origin_planet_id, tier, hop_ranges=hop_ranges,
    )
    if not _candidates:
        return None
    return rng.choice(_candidates)


def _bar_spec(
    gen_id, title, description, giver_npc_id, tier,
    credits, xp, deadline, origin_planet_id, mission_type, **extra,
):
    return MissionSpec(
        id=gen_id, title=title, description=description,
        giver_npc_id=giver_npc_id, faction="bar",
        mission_type=mission_type, tier=tier,
        reward_credits=credits, reward_xp=xp,
        deadline_days=deadline, early_bonus_pct=25,
        origin_planet_id=origin_planet_id, **extra,
    )


def _ship_display_name(ship_id):
    from ..data.npc_ships import find_npc_ship
    from ._proc_shared import display_name_of
    return display_name_of(find_npc_ship, ship_id)


def _intercept_target(tier, rng):
    """(enemy_id, heist_good, squad_size, wingmate_id) for a tier.

    Escorts appear at T2+.
    """
    enemy_id = rng.choice(_MERCHANT_POOLS.get(tier, ["merchant_hauler"]))
    heist_good = rng.choice(_HEIST_GOODS)
    squad_size = 1
    wingmate_id = None
    if tier >= 2:
        squad_size = rng.randint(1, min(tier, 3))
        if squad_size > 1:
            wingmate_id = "pirate_scout" if tier <= 3 else "pirate_raider"
    return enemy_id, heist_good, squad_size, wingmate_id


def _generate_bar_intercept(
    origin_planet_id: str,
    tier: int,
    rng: random.Random,
    counter: int,
    giver_npc_id: str,
) -> MissionSpec | None:
    """Generate a procedural intercept (merchant hunting) bar mission."""
    picked = _pick_system(origin_planet_id, tier, rng, _INTERCEPT_HOP_RANGES)
    if picked is None:
        return None
    target_system_id, hops = picked

    enemy_id, heist_good, squad_size, wingmate_id = _intercept_target(tier, rng)

    # Round-trip deadline (travel both ways). Reward: a fight plus a
    # cargo return carries ~1.5x the delivery band, a notch below T4
    # named bounties at the top end.
    deadline = max(30, hops * 60 + rng.randint(10, 30))
    credits = tier * 300 + hops * 60
    xp = tier * 50 + hops * 10

    enemy_name = _ship_display_name(enemy_id)
    gen_id = f"proc_intercept_{origin_planet_id}_{target_system_id}_{counter}_{tier}"
    title = f"Intercept: {enemy_name}"
    _escort_note = f" ({squad_size - 1} escorts)" if squad_size > 1 else ""
    description = (
        f"Ambush a {enemy_name}{_escort_note} hauling {heist_good} "
        f"{hops} jump(s) away. Return the cargo to the bar."
    )
    return _bar_spec(
        gen_id, title, description, giver_npc_id, tier,
        credits, xp, deadline, origin_planet_id, "intercept",
        target_enemy_id=enemy_id, target_system_id=target_system_id,
        bounty_target_squad_size=squad_size,
        bounty_wingmate_enemy_id=wingmate_id,
        heist_target_good_id=heist_good,
    )


def _smuggle_terms(tier, hops, rng):
    """(cargo, credits, xp, deadline) for a smuggling run.

    Same shape as a delivery but with scan/confiscation risk, so it
    pays ~20-30% above deliveries plus a per-hop bonus; XP stays at
    delivery parity — the premium is credits.
    """
    _cargo_ranges = {1: (5, 10), 2: (10, 20), 3: (20, 40), 4: (40, 60)}
    cargo_lo, cargo_hi = _cargo_ranges.get(tier, (5, 10))
    cargo = rng.randint(cargo_lo, cargo_hi)
    credits = cargo * 6 * (tier + 1) + hops * 15
    xp = cargo * 2 * tier + hops * 4
    deadline = max(20, hops * 30 + rng.randint(10, 20))
    return cargo, credits, xp, deadline


def _generate_bar_smuggling(
    origin_planet_id: str,
    tier: int,
    rng: random.Random,
    counter: int,
    giver_npc_id: str,
) -> MissionSpec | None:
    """Generate a procedural smuggling (contraband delivery) bar mission."""
    from ._proc_shared import planet_destinations
    _dest_candidates = planet_destinations(
        origin_planet_id, tier, hop_ranges=_SMUGGLE_HOP_RANGES,
    )
    if not _dest_candidates:
        return None
    dest_planet_id, _dest_sys_id, hops = rng.choice(_dest_candidates)
    npc_ids = _planet_npc_ids(dest_planet_id)
    target_npc_id = rng.choice(npc_ids) if npc_ids else None

    cargo, credits, xp, deadline = _smuggle_terms(tier, hops, rng)

    smuggle_good = rng.choice(_HEIST_GOODS)

    from ._proc_shared import display_name_of
    from ..data.planets import find_planet_spec
    dest_name = display_name_of(find_planet_spec, dest_planet_id)
    gen_id = f"proc_smuggle_{origin_planet_id}_{dest_planet_id}_{counter}_{tier}"
    title = f"Smuggle: {dest_name}"
    description = (
        f"Move {cargo} units of contraband to {dest_name} "
        f"({hops} jump(s)). Militia scans are a risk."
    )
    return _bar_spec(
        gen_id, title, description, giver_npc_id, tier,
        credits, xp, deadline, origin_planet_id, "smuggling",
        required_cargo_size=cargo,
        delivery_target_npc_id=target_npc_id,
        delivery_target_planet_id=dest_planet_id,
        is_smuggle=True, smuggle_good_id=smuggle_good,
    )


def _salvage_site(tier, rng):
    """The site rolls: patrol, squad, wingmate, wreck, layout, component."""
    patrol_id = rng.choice(_PATROL_POOLS.get(tier, ["pirate_scout"]))
    _sq_lo, _sq_hi = {1: (1, 1), 2: (1, 2), 3: (1, 2), 4: (2, 3)}.get(
        tier, (1, 1),
    )
    squad_size = rng.randint(_sq_lo, _sq_hi)
    wingmate_id = None
    if squad_size > 1 and tier >= 3:
        wingmate_id = "pirate_scout" if tier == 3 else "pirate_raider"
    wreck_id, layout_id = _WRECK_LAYOUTS.get(tier, ("derelict_scout", "scout_a"))
    return patrol_id, squad_size, wingmate_id, wreck_id, layout_id, rng.choice(_HEIST_GOODS)


def _generate_bar_salvage(
    origin_planet_id: str,
    tier: int,
    rng: random.Random,
    counter: int,
    giver_npc_id: str,
) -> MissionSpec | None:
    """Generate a procedural salvage (wreck boarding) bar mission."""
    picked = _pick_system(origin_planet_id, tier, rng, _SALVAGE_HOP_RANGES)
    if picked is None:
        return None
    target_system_id, hops = picked

    patrol_id, squad_size, wingmate_id, wreck_id, layout_id, component = (
        _salvage_site(tier, rng)
    )

    # Round-trip deadline.
    deadline = max(30, hops * 60 + rng.randint(15, 35))

    credits = tier * 180 + hops * 40
    xp = tier * 35 + hops * 7

    patrol_name = _ship_display_name(patrol_id)
    gen_id = f"proc_salvage_{origin_planet_id}_{target_system_id}_{counter}_{tier}"
    title = f"Salvage: {patrol_name} Wreck"
    description = (
        f"Recover {component} from a derelict wreck {hops} jump(s) away. "
        f"{squad_size} pirate(s) guard the site."
    )
    return _bar_spec(
        gen_id, title, description, giver_npc_id, tier,
        credits, xp, deadline, origin_planet_id, "salvage",
        target_enemy_id=patrol_id, target_system_id=target_system_id,
        bounty_target_squad_size=squad_size,
        bounty_wingmate_enemy_id=wingmate_id,
        heist_target_good_id=component,
        salvage_wreck_enemy_id=wreck_id,
        salvage_layout_id=layout_id,
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

