"""Player ship catalog — the purchasable starships at the space port.

Six-ship progression:

  * **Skiff** — given free at game start; basic stats, few slots. Its
    hull class is fixed, but each new run rolls a colorful name from
    :data:`STARTER_NAMES` (see ``__main__.py`` new-game setup).
  * **Scout** — early upgrade; better combat, light shields.
  * **Hauler** — cargo specialist; big holds, light weapons.
  * **Cruiser** — combat mid-tier; heavy guns, good shields.
  * **Frigate** — end-game combat; overwhelming firepower.
  * **Freighter** — end-game cargo; massive holds.

Extracted from ``ship.py`` during the data-first migration.
Rebalanced to give the player a free starter ship and a clear
progression path to earn better ships.

**Hold sizing rule (balance pass):** each non-merchant hull can pack
FIVE deliveries of its tier's max crate size — Skiff 5×T1 (50),
Scout 5×T2 (100), Cruiser 5×T3 (200), Frigate 5×T4 (300) — so
the mission loop (load a board of orders, fly a cluster, drop them
all off) works in every ship. Hauler and Freighter keep the
merchant identity with massive holds on top.

``STARTER_NAMES`` lives here (data-first) so the pool is content,
not code. The rolled name is stored on ``OwnedShip.display_name``
and survives save/load; ``Ship.name`` is only the fallback.
"""

from . import Ship


SHIPS: tuple[Ship, ...] = (
    # ------------------------------------------------------------------- #
    # Tier 1 — Skiff (free, given at game start; name rolled per run)
    # ------------------------------------------------------------------- #
    Ship(
        id="starter",
        name="Skiff",
        char="t",
        fg=(180, 200, 220),                                              # muted steel-blue
        price=500,  # given free at start, but has value: repairs/trade-ins are never $0
        width=1, height=1,
        description=(
            "A modest starter vessel. Gets you where you need to go."
        ),
        speed=10,
        weapon_slots=2,
        module_slots=1,
        max_cargo=50,   # 5 × T1 delivery max (10)
        max_fuel=80,
        base_power_gen=2,
        base_shield_max=0,
        base_hull=15,
        start_weapons=('light_laser',),
        start_modules=(),
    ),
    # ------------------------------------------------------------------- #
    # Tier 2 — Scout (early combat upgrade)
    # ------------------------------------------------------------------- #
    Ship(
        id="scout",
        name="Scout",
        char="s",
        fg=(130, 220, 255),
        price=5000,
        width=1, height=1,
        description=(
            "A small, fast scoutship - quick on cargo runs, lightly armed."
        ),
        speed=14,
        weapon_slots=4,
        module_slots=2,
        max_cargo=100,  # 5 × T2 delivery max (20)
        max_fuel=100,
        base_power_gen=3,
        base_shield_max=5,
        base_shield_recharge=1,
        base_hull=25,
        start_weapons=('light_laser', 'light_laser'),
        start_modules=('compact_reactor',),
    ),
    # ------------------------------------------------------------------- #
    # Tier 3 — Hauler (cargo specialist)
    # ------------------------------------------------------------------- #
    Ship(
        id="hauler",
        name="Hauler",
        char="H",
        fg=(140, 210, 140),
        price=12000,
        width=1, height=1,
        description=(
            "A long-range cargo hauler with roomy cargo bays."
        ),
        speed=7,
        weapon_slots=2,
        module_slots=2,
        max_cargo=400,  # merchant workhorse — massive hold
        max_fuel=80,
        base_power_gen=4,
        base_shield_max=10,
        base_shield_recharge=1,
        base_hull=30,
        start_weapons=('light_laser',),
        start_modules=('expanded_cargo', 'armor_plating'),
    ),
    # ------------------------------------------------------------------- #
    # Tier 4 — Cruiser (combat mid-tier)
    # ------------------------------------------------------------------- #
    Ship(
        id="cruiser",
        name="Cruiser",
        char="C",
        fg=(235, 130, 130),
        price=25000,
        width=1, height=1,
        description=(
            "A well-armed cruiser - capable in a fight, well-shielded."
        ),
        speed=9,
        weapon_slots=6,
        module_slots=4,
        max_cargo=200,  # 5 × T3 delivery max (40)
        max_fuel=80,
        base_power_gen=5,
        base_shield_max=25,
        base_shield_recharge=3,
        base_hull=60,
        start_weapons=('light_laser', 'heavy_laser', 'light_missile'),
        start_modules=('compact_reactor', 'shield_mk1'),
    ),
    # ------------------------------------------------------------------- #
    # Tier 5 — Frigate (end-game combat)
    # ------------------------------------------------------------------- #
    Ship(
        id="frigate",
        name="Frigate",
        char="F",
        fg=(200, 100, 255),                                              # purple — distinct from cruiser red
        price=50000,
        width=1, height=1,
        description=(
            "Heavy warship with overwhelming firepower and thick armour."
        ),
        speed=8,
        weapon_slots=8,
        module_slots=6,
        max_cargo=300,  # 5 × T4 delivery max (60)
        max_fuel=100,
        base_power_gen=6,
        base_shield_max=40,
        base_shield_recharge=5,
        base_hull=100,
        start_weapons=('light_laser', 'light_laser', 'heavy_laser', 'light_missile'),
        start_modules=('compact_reactor', 'shield_mk1', 'shield_recharger', 'targeting_computer'),
    ),
    # ------------------------------------------------------------------- #
    # Tier 5 — Freighter (end-game cargo)
    # ------------------------------------------------------------------- #
    Ship(
        id="freighter",
        name="Freighter",
        char="F",
        fg=(255, 180, 80),                                               # gold — distinct from hauler green
        price=40000,
        width=1, height=1,
        description=(
            "Massive cargo hauler for the serious trader."
        ),
        speed=6,
        weapon_slots=3,
        module_slots=4,
        max_cargo=700,  # endgame merchant — massive hold
        max_fuel=70,
        base_power_gen=4,
        base_shield_max=15,
        base_shield_recharge=2,
        base_hull=40,
        start_weapons=('light_laser',),
        start_modules=('expanded_cargo', 'compact_reactor'),
    ),
)


# Colorful names rolled at new-game start for the free starting ship.
# The pool is deliberately scrappy-frontier in tone — these are hand-
# me-downs and workhorses, not showroom cruisers. All CP437-safe ASCII.
STARTER_NAMES: tuple[str, ...] = (
    "Corvid",
    "Mule",
    "Tramp",
    "Sparrow",
    "Rustbucket",
    "Lady Luck",
    "Old Bess",
    "Second Wind",
    "Honey Badger",
    "Gnat",
    "Wanderer",
    "Drifter",
    "Husk",
    "Barnacle",
    "Tinker",
    "Patchwork",
)
