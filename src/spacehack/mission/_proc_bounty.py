"""Procedural bounty mission generation and bounty tables."""
from __future__ import annotations

import random

from ..data.missions import MissionSpec
from ._proc_shared import _planet_to_system, _roll_tier


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

