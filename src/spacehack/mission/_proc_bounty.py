"""Procedural bounty mission generation and bounty tables."""
from __future__ import annotations

import random

from ..data.missions import MissionSpec
from ._proc_shared import _roll_tier, hop_candidates


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


_BOUNTY_HOP_RANGES = {
    1: (1, 3),
    2: (1, 4),
    3: (2, 6),
    4: (3, 8),
}


def _pick_bounty_system(origin_planet_id, tier, rng, reachable_system_ids):
    """One candidate target system as (system_id, hops), or None.

    Bounty hop ranges run slightly longer than delivery ranges.
    """
    _candidates = hop_candidates(
        origin_planet_id, tier, hop_ranges=_BOUNTY_HOP_RANGES,
    )
    if not _candidates:
        return None
    return rng.choice(_candidates)


def _bounty_target(tier, rng):
    """(enemy_id, loadout_pct, squad_size, target_name) for a tier."""
    enemy_id = rng.choice(_bounty_enemy_pool(tier))
    _lo_lo, _lo_hi = _bounty_loadout_range(tier)
    loadout_pct = rng.randint(_lo_lo, _lo_hi)
    _sq_lo, _sq_hi = _bounty_squad_range(tier)
    squad_size = rng.randint(_sq_lo, _sq_hi)
    return enemy_id, loadout_pct, squad_size, _generate_bounty_name(rng)


def _bounty_reward(tier, squad_size, loadout_pct, hops):
    """(credits, xp): flat tier base x squad x loadout + hop bonus.

    Deliberately not hull-scaled (the old quadratic formula made
    bounties the only board worth playing); bands sit alongside bar
    missions and slightly below named static bounties so named work
    stays the premium.
    """
    _sq_mult = {1: 1.0, 2: 1.3, 3: 1.6}.get(squad_size, 1.0)
    _loadout_mult = 1.0 + loadout_pct / 400.0      # 0%→1.0, 100%→1.25
    _base_credits = {1: 220, 2: 350, 3: 600, 4: 950}.get(tier, 220)
    _base_xp = {1: 30, 2: 55, 3: 100, 4: 160}.get(tier, 30)
    credits = int(_base_credits * _sq_mult * _loadout_mult) + hops * 10
    xp = int(_base_xp * _sq_mult) + hops * 4
    return credits, xp


def _bounty_display(origin_planet_id, target_name, hops, tier, squad_size, loadout_pct):
    """Wanted-poster title and description."""
    try:
        from ..data.planets import find_planet_spec as _fps_origin
        origin_name = _fps_origin(origin_planet_id).name
    except KeyError:
        origin_name = origin_planet_id
    _squad_note = f" + {squad_size - 1} wingmates" if squad_size > 1 else ""
    _loadout_note = " (heavy loadout)" if loadout_pct >= 75 else ""
    title = f"Wanted: {target_name}"
    description = (
        f"The Bounty Guild on {origin_name} seeks {target_name}, "
        f"last seen {hops} jump(s) away. "
        f"Danger: {_bounty_danger_text(tier, squad_size)}.{_squad_note}{_loadout_note}"
    )
    return title, description


def generate_bounty_mission(
    origin_planet_id: str,
    max_tier: int,
    rng: random.Random,
    counter: int = 0,
    giver_npc_id: str = "",
) -> MissionSpec | None:
    """One bounty mission from ``origin_planet_id`` (``None`` if no
    candidate target system exists). Reward bands sit alongside bar
    missions and below named static bounties — see _bounty_reward."""
    from ..data.solar_systems import reachable_system_ids

    tier = _roll_tier(max_tier, rng)
    _picked = _pick_bounty_system(origin_planet_id, tier, rng, reachable_system_ids)
    if _picked is None:
        return None
    target_system_id, hops = _picked

    enemy_id, loadout_pct, squad_size, target_name = _bounty_target(tier, rng)
    credits, xp = _bounty_reward(tier, squad_size, loadout_pct, hops)
    deadline = max(20, hops * 35 + rng.randint(10, 25))
    title, description = _bounty_display(
        origin_planet_id, target_name, hops, tier, squad_size, loadout_pct,
    )
    gen_id = f"proc_bounty_{origin_planet_id}_{target_system_id}_{enemy_id}_{counter}_{tier}"

    return MissionSpec(
        id=gen_id, title=title, description=description,
        giver_npc_id=giver_npc_id, faction="bhguild",
        mission_type="bounty", tier=tier,
        reward_credits=credits, reward_xp=xp,
        deadline_days=deadline, early_bonus_pct=30,
        target_enemy_id=enemy_id, target_system_id=target_system_id,
        bounty_target_name=target_name,
        bounty_target_squad_size=squad_size,
        bounty_target_loadout_pct=loadout_pct,
        origin_planet_id=origin_planet_id,
    )

