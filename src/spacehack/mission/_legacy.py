"""Mission runtime layer: lifecycle state + accept/deliver/complete/abort.

Missions live in two layers:

  * :mod:`spacehack.data.missions` - the static catalog (the
    :class:`MissionSpec` dataclass + per-faction ``MISSIONS`` tuples
    + :func:`find_mission` / :func:`missions_offered_by` lookup
    helpers). Adding a new mission is a one-file edit there.
  * Here - board management and procedural mission generation. Lifecycle
    mutations live in :mod:`spacehack.mission._lifecycle`.

This module re-exports :class:`MissionSpec`, :func:`find_mission`,
and :func:`missions_offered_by` from :mod:`spacehack.data.missions`
so the dispatcher's ``mission_module.MissionSpec`` references keep
working without a second import line.
"""

from __future__ import annotations

import random

from ..data.missions import MissionSpec, find_mission, list_missions, missions_offered_by
from ._models import ActiveMission, MissionStatus, MAX_ACTIVE_MISSIONS
from ._proc_shared import (
    _dest_candidates_in_system,
    _planet_npc_ids,
    _planet_to_system,
    _roll_tier,
)
from ._board import (
    board_offerings,
    board_remove,
    board_return_static,
    ensure_board,
    fill_empty_slots,
    refresh_all_boards,
)
from ._lifecycle import (
    abort_mission,
    commit_accept_mission,
    complete_mission,
    release_mission_cargo,
    try_accept_mission,
)
from ._helpers import (
    active_is_deliverable_at,
    board_key,
    destination_system_name,
    find_board_for_mission,
    find_deliverable,
    find_deliverable_missions,
    is_deliverable_at,
    system_display_name,
    system_name_for_planet,
)











































# ---------------------------------------------------------------------------
# Procedural delivery mission generator
# ---------------------------------------------------------------------------















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


# ---------------------------------------------------------------------------
# Procedural bounty mission generator
# ---------------------------------------------------------------------------

_BOUNTY_ADJECTIVES: tuple[str, ...] = (
    "Crimson", "Shadow", "Iron", "Silver", "Black", "Red",
    "Void", "Ghost", "Rust", "Bone", "Ash", "Frost",
    "Storm", "Venom", "Blade", "Fang", "Claw", "Wraith",
    "Dusk", "Blazing", "Rogue", "Savage", "Bleeding", "Obsidian",
    "Scorch", "Drift", "Hollow", "Broken", "Silent", "Grim",
    "Vile", "Pale", "Dead", "Cold", "Grave", "Midnight",
    "Scarred", "Jagged", "Shade", "Spectral", "Cursed", "Slate",
    "Thunder", "Onyx", "Deep", "Feral", "Plague", "Wild",
    "Bitter", "Bleak", "Blind", "Bloody", "Blunt", "Brass",
    "Brazen", "Burning", "Charred", "Chrome", "Copper", "Corroded",
    "Cracked", "Crude", "Dread", "Drowned", "Dusty", "Fallen",
    "Fiery", "Flaming", "Forged", "Fractured", "Frozen", "Fuming",
    "Gilded", "Glassy", "Gleaming", "Gloom", "Glowing", "Golden",
    "Granite", "Haunted", "Howling", "Hungry", "Hushed", "Icy",
    "Keen", "Lethal", "Livid", "Lonely", "Meridian", "Molten",
    "Mortal", "Nocturnal", "Quick", "Reckless", "Restless", "Rusted",
)

_BOUNTY_FIRST_NAMES: tuple[str, ...] = (
    "Jack", "Kai", "Nova", "Rex", "Vex", "Zara",
    "Finn", "Mira", "Cole", "Sera", "Jax", "Vega",
    "Lyra", "Kira", "Zane", "Rook", "Tessa", "Orin",
    "Cora", "Dax", "Luna", "Rhea", "Thane", "Arya",
    "Kael", "Nyla", "Talon", "Sasha", "Remy", "Jett",
    "Quinn", "Phoenix", "River", "Sky", "Echo", "Sparrow",
    "Raven", "Storm", "Blaze", "Jinx", "Sol", "Wren",
    "Vesper", "Flint", "Ridge", "Vale", "Mara", "Toren",
    "Shae", "Elyse", "Doran", "Kestrel", "Nyx", "Korra",
    "Alden", "Astra", "Bex", "Briar", "Calyx", "Cass",
    "Cinder", "Cypher", "Dash", "Dove", "Draven", "Dune",
    "Elara", "Ember", "Faye", "Gage", "Galen", "Garnet",
    "Harlow", "Haven", "Iris", "Ivory", "Jade", "Jorah",
    "Kaida", "Lark", "Lira", "Lorn", "Mace", "Maren",
    "Maven", "Nash", "Niam", "Oren", "Orion",
    "Palen", "Pax", "Rayne", "Reed", "Riven", "Rowan",
    "Ryan", "Salem", "Soren", "Sylvan", "Torin", "Vance",
)



def _generate_bounty_name(rng: random.Random) -> str:
    """Generate a bounty target name like "Crimson Jack".

    Picks a random adjective + first name from large flat pools
    (96 adjectives × 107 first names = 10,272 possible combos).
    """
    _adj = rng.choice(_BOUNTY_ADJECTIVES)
    _fn = rng.choice(_BOUNTY_FIRST_NAMES)
    return f"{_adj} {_fn}"


def _bounty_enemy_pool(tier: int) -> list[str]:
    """Return eligible NpcShipSpec IDs for a bounty of the given tier."""
    _pools: dict[int, list[str]] = {
        1: ["pirate_scout"],
        2: ["pirate_scout", "pirate_raider"],
        3: ["pirate_raider"],
        4: ["pirate_raider", "pirate_captain"],
    }
    return _pools.get(max(1, min(4, tier)), ["pirate_scout"])


def _bounty_loadout_range(tier: int) -> tuple[int, int]:
    """Return (min_pct, max_pct) for loadout scaling by tier."""
    return {
        1: (0, 25),
        2: (25, 50),
        3: (50, 75),
        4: (75, 100),
    }.get(max(1, min(4, tier)), (0, 25))


def _bounty_squad_range(tier: int) -> tuple[int, int]:
    """Return (min_squad, max_squad) by tier."""
    return {
        1: (1, 1),
        2: (1, 1),
        3: (1, 2),
        4: (2, 3),
    }.get(max(1, min(4, tier)), (1, 1))


def _bounty_danger_text(tier: int, squad_size: int) -> str:
    """Return a danger-level label for mission descriptions.

    Based purely on tier so the label always matches the mission's
    reward tier (which already scales with squad size internally).
    """
    if tier >= 4:
        return "Extreme"
    if tier >= 3:
        return "High"
    if tier >= 2:
        return "Moderate"
    return "Low"


def generate_bounty_mission(
    origin_planet_id: str,
    max_tier: int,
    rng: random.Random,
    counter: int = 0,
    giver_npc_id: str = "",
) -> MissionSpec | None:
    """Generate one procedural bounty mission originating from
    ``origin_planet_id``.

    Algorithm:
      1. Roll tier: weighted 1..max_tier using min-of-two-rolls.
      2. Find origin system and reachable systems (reuses hop-range
         pattern from delivery generation).
      3. Pick a target system via hop-range gating tuned for bounty
         distances (longer ranges than delivery).
      4. Pick enemy from tier-appropriate pool.
      5. Roll loadout_pct and squad_size within tier ranges.
      6. Generate name via tier-gated prefix/title pools.
      7. Compute reward: base = hull_strength × tier × 40, adjusted
         by squad size.
      8. Compute deadline: max(20, hops × 35 + randint(10, 25)) — accounts for
         200×140 system size (~18 days per crossing at speed 10).
      9. Build MissionSpec with mission_type="bounty", faction="bhguild".

    Returns ``None`` if no suitable target system can be found.
    """
    from ..data.solar_systems import reachable_system_ids
    from ..data.npc_ships import find_npc_ship
    from ..data.ships import find_ship as _find_ship_cat

    # 1. Tier roll (shared two-roll pattern for rarity curve).
    tier = _roll_tier(max_tier, rng)

    # 2. Resolve origin system and reachable systems.
    p2s = _planet_to_system()
    origin_system_id = p2s.get(origin_planet_id)
    if origin_system_id is None:
        return None

    reachable = reachable_system_ids(origin_system_id, max_hops=10)

    # Bounty hop ranges: slightly longer than delivery.
    _hop_ranges = {
        1: (1, 3),
        2: (1, 4),
        3: (2, 6),
        4: (3, 8),
    }
    min_hops, max_hops = _hop_ranges.get(tier, (1, 10))

    # Build candidate system list.
    _candidates: list[tuple[str, int]] = []
    for sys_id, hops in reachable.items():
        if min_hops <= hops <= max_hops and sys_id != origin_system_id:
            _candidates.append((sys_id, hops))

    if not _candidates:
        return None

    # 3. Pick a target system.
    target_system_id, hops = rng.choice(_candidates)

    # 4. Pick enemy from tier-appropriate pool.
    _pool = _bounty_enemy_pool(tier)
    enemy_id = rng.choice(_pool)
    try:
        _espec = find_npc_ship(enemy_id)
        _ship_cat = _find_ship_cat(_espec.ship_id)
        _hull_strength = _ship_cat.base_hull
    except (KeyError, ImportError):
        _hull_strength = 50

    # 5. Roll loadout and squad.
    _lo_lo, _lo_hi = _bounty_loadout_range(tier)
    loadout_pct = rng.randint(_lo_lo, _lo_hi)
    _sq_lo, _sq_hi = _bounty_squad_range(tier)
    squad_size = rng.randint(_sq_lo, _sq_hi)

    # 6. Generate name.
    target_name = _generate_bounty_name(rng)

    # 7. Reward: base = hull_strength × tier × 40, × squad multiplier.
    _sq_mult = {1: 1.0, 2: 1.5, 3: 2.0}.get(squad_size, 1.0)
    credits = int(_hull_strength * tier * 40 * _sq_mult)
    xp = int(_hull_strength * tier * 2 * _sq_mult)

    # 8. Deadline: ~35 days per hop so travel + hunting fits comfortably.
    #    All solar systems are 200x140 cells. Crossing one from gate to gate
    #    takes ~180 moves = 18 days at speed 10. Bounties get a slightly
    #    more generous multiplier than deliveries to account for local
    #    searching and combat (even though combat is "free", the hunt
    #    before engagement can add crossing time).
    deadline = max(20, hops * 35 + rng.randint(10, 25))

    # 9. Danger text + description.
    _danger = _bounty_danger_text(tier, squad_size)
    try:
        from ..data.planets import find_planet_spec as _fps_origin
        origin_name = _fps_origin(origin_planet_id).name
    except KeyError:
        origin_name = origin_planet_id

    title = f"Wanted: {target_name}"
    _squad_note = f" + {squad_size - 1} wingmates" if squad_size > 1 else ""
    _loadout_note = " (heavy loadout)" if loadout_pct >= 75 else ""
    description = (
        f"The Bounty Guild on {origin_name} seeks {target_name}, "
        f"last seen {hops} jump(s) away. "
        f"Danger: {_danger}.{_squad_note}{_loadout_note}"
    )

    # 10. Generated ID.
    gen_id = f"proc_bounty_{origin_planet_id}_{target_system_id}_{enemy_id}_{counter}_{tier}"

    return MissionSpec(
        id=gen_id,
        title=title,
        description=description,
        giver_npc_id=giver_npc_id,
        faction="bhguild",
        mission_type="bounty",
        tier=tier,
        reward_credits=credits,
        reward_xp=xp,
        deadline_days=deadline,
        early_bonus_pct=30,
        target_enemy_id=enemy_id,
        target_system_id=target_system_id,
        bounty_target_name=target_name,
        bounty_target_squad_size=squad_size,
        bounty_target_loadout_pct=loadout_pct,
        origin_planet_id=origin_planet_id,
    )



# ---------------------------------------------------------------------------
# Procedural bar mission generator
# ---------------------------------------------------------------------------

# Heist goods pool — trade good IDs used as intercept loot / salvage components.
_HEIST_GOODS: tuple[str, ...] = (
    "electronics", "machine_parts", "luxury_goods", "fuel_cells",
)

# Merchant ship pool by tier (intercept targets).
_MERCHANT_POOLS: dict[int, list[str]] = {
    1: ["merchant_hauler"],
    2: ["merchant_hauler"],
    3: ["merchant_freighter"],
    4: ["merchant_caravan"],
}

# Pirate patrol pool by tier (salvage guards).
_PATROL_POOLS: dict[int, list[str]] = {
    1: ["pirate_scout"],
    2: ["pirate_scout"],
    3: ["pirate_raider"],
    4: ["pirate_raider", "pirate_captain"],
}

# Wreck + layout by tier (salvage boarding).
_WRECK_LAYOUTS: dict[int, tuple[str, str]] = {
    1: ("derelict_scout", "scout_a"),
    2: ("derelict_scout", "scout_a"),
    3: ("derelict_freighter", "freightliner_a"),
    4: ("derelict_freighter", "freightliner_a"),
}

# Hop-range tables for bar mission types.
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

    # Reward.
    credits = tier * 200 + hops * 50
    xp = tier * 40 + hops * 10

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

    credits = cargo * 4 * (tier + 1)
    xp = cargo * tier
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


# Dispatch table for bar mission type -> sub-generator.
from typing import Callable as _Callable

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


# Re-exports so consumers can keep using ``mission_module.MissionSpec``
# etc. without a second import line.
__all__ = [
    "ActiveMission",
    "MissionSpec",
    "MissionStatus",
    "MAX_ACTIVE_MISSIONS",
    "release_mission_cargo",
    "abort_mission",
    "active_is_deliverable_at",
    "commit_accept_mission",
    "complete_mission",
    "find_mission",
    "find_deliverable",
    "find_deliverable_missions",
    "is_deliverable_at",
    "list_missions",
    "missions_offered_by",
    "try_accept_mission",
    "ensure_board",
    "board_key",
    "find_board_for_mission",
    "board_offerings",
    "fill_empty_slots",
    "board_remove",
    "board_return_static",
    "refresh_all_boards",
    "generate_delivery_mission",
    "generate_bounty_mission",
    "generate_bar_mission",
    "_planet_npc_ids",
    "_planet_to_system",
    "system_display_name",
    "system_name_for_planet",
    "destination_system_name",
]
