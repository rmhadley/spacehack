"""Dungeon monster catalog — non-sentient hostile fauna and drones.

Every monster sets ``always_hostile=True`` and ``faction=""`` so it
fights on sight regardless of faction reputation and killing one
changes no reputation score (``_COMBAT_KILL_DELTAS.get("", {})`` is
a no-op). Behavior + squad size drive out-of-combat movement and
procedural dungeon population.

Design doc: ``docs/design/in_progress/11_DESIGN_DUNGEON_MONSTERS.md``
"""

from . import NpcCharSpec

NPC_CHARS: tuple[NpcCharSpec, ...] = (
    NpcCharSpec(
        id="rock_scavenger",
        name="Rock Scavenger",
        char="s",
        fg=(205, 170, 120),       # sandy rock-grey — desert/rock fauna
        faction="",
        hp=14,
        weapons=("monster_claws",),
        reflexes=10,
        strength=12,
        stamina=10,
        detect_radius=4,
        behavior="hunter",
        squad_size=(3, 5),        # swarmer — always hunts in packs
        always_hostile=True,
        loot_pool=("scrap_metal",),
        loot_count=(1, 2),
        xp_reward=10,
    ),
    NpcCharSpec(
        id="sentry_drone",
        name="Sentry Drone",
        char="d",
        fg=(150, 185, 255),       # cold blue-white — security lighting
        faction="",
        hp=18,
        weapons=("drone_laser",),
        reflexes=14,
        strength=10,
        stamina=12,
        detect_radius=6,
        behavior="guard",         # holds position, fires at range
        squad_size=(1, 1),
        always_hostile=True,
        loot_pool=("electronics", "machine_parts"),
        loot_count=(1, 2),
        xp_reward=25,
    ),
    NpcCharSpec(
        id="ice_worm",
        name="Ice Worm",
        char="w",
        fg=(185, 220, 245),       # pale ice-blue — cold-cave ambusher
        faction="",
        hp=26,
        weapons=("monster_claws",),
        reflexes=12,
        strength=28,
        stamina=14,
        detect_radius=5,
        behavior="ambusher",      # holds still, bursts out on approach
        squad_size=(1, 2),
        always_hostile=True,
        loot_pool=("scrap_metal", "research_data"),
        loot_count=(1, 1),
        xp_reward=20,
    ),
)
