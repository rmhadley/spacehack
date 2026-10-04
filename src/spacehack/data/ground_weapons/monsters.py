"""Monster ground weapons — enemy-only natural/machine attacks.

Never sold in armories (``shop_available=False``): the armory lists
every registered weapon, so this flag is what keeps monster attacks
out of player shops. Players can never acquire these ids.

Design doc: ``docs/design/in_progress/11_DESIGN_DUNGEON_MONSTERS.md``
"""

from . import GroundWeaponSpec

WARES: tuple[GroundWeaponSpec, ...] = (
    GroundWeaponSpec(
        id="monster_claws",
        name="Monster Claws",
        damage_type="melee",
        damage=3,
        accuracy=85,
        ap_cost=1,
        hands=1,
        min_range=1,
        max_range=1,
        ammo_capacity=-1,
        price=0,
        tech_level=1,
        shop_available=False,
        loot_droppable=False,
        noise=4,
    ),
    GroundWeaponSpec(
        id="drone_laser",
        name="Drone Laser",
        damage_type="energy",
        damage=4,
        accuracy=70,
        ap_cost=2,
        hands=1,
        min_range=1,
        max_range=6,
        ammo_capacity=-1,
        price=0,
        tech_level=2,
        shop_available=False,
        loot_droppable=False,
        noise=4,
    ),
    GroundWeaponSpec(
        id="frost_bolt",
        name="Frost Bolt",
        damage_type="energy",
        damage=4,
        accuracy=65,
        ap_cost=2,
        hands=1,
        min_range=1,
        max_range=5,
        ammo_capacity=-1,
        price=0,
        tech_level=2,
        shop_available=False,
        loot_droppable=False,
        noise=5,
    ),
    GroundWeaponSpec(
        id="parasite_mandibles",
        name="Parasite Mandibles",
        damage_type="melee",
        damage=3,
        accuracy=80,
        ap_cost=1,
        hands=1,
        min_range=1,
        max_range=1,
        ammo_capacity=-1,
        price=0,
        tech_level=1,
        shop_available=False,
        loot_droppable=False,
        noise=4,
    ),
    # --- biome fauna (doc 48 phase 10, SETTLED 47/48): organic parts
    # shaped per the census cells — every carrier a distinct
    # behavior-attack identity, numbers leaning on the existing rows.
    GroundWeaponSpec(
        id="spore_burst",
        name="Spore Burst",
        damage_type="energy",
        damage=5,
        accuracy=70,
        ap_cost=2,
        hands=1,
        min_range=2,              # the nest's dead zone — rush it
        max_range=8,              # the longest organic range
        ammo_capacity=-1,
        price=0,
        tech_level=1,
        shop_available=False,
        loot_droppable=False,
        noise=5,
    ),
    GroundWeaponSpec(
        id="magma_bolt",
        name="Magma Bolt",
        damage_type="energy",
        damage=8,
        accuracy=75,
        ap_cost=2,
        hands=1,
        min_range=1,
        max_range=4,              # the brawler-caster: heavy, close
        ammo_capacity=-1,
        price=0,
        tech_level=2,
        shop_available=False,
        loot_droppable=False,
        noise=5,
    ),
    GroundWeaponSpec(
        id="rust_spines",
        name="Rust Spines",
        damage_type="kinetic",
        damage=3,
        accuracy=75,
        ap_cost=1,
        hands=1,
        min_range=1,
        max_range=4,              # the swarm sting — short-range volume
        ammo_capacity=-1,
        price=0,
        tech_level=1,
        shop_available=False,
        loot_droppable=False,
        noise=4,
    ),
    GroundWeaponSpec(
        id="venom_fangs",
        name="Venom Fangs",
        damage_type="melee",
        damage=3,
        accuracy=90,
        ap_cost=1,                # fast weak multi-bite — the volley is
        hands=1,                  # the pressure (ap-6 carriers bite 6x)
        min_range=1,
        max_range=1,
        ammo_capacity=-1,
        price=0,
        tech_level=1,
        shop_available=False,
        loot_droppable=False,
        noise=3,
    ),
    # --- the apex weapons (doc 48 phase 10, SETTLED 47/48): knockback
    # and armor_bypass ride the EXISTING weapon fields (the Warden
    # slam's precedent) — data-only apexes, no new mechanic machinery.
    GroundWeaponSpec(
        id="behemoth_maul",
        name="Behemoth Maul",
        damage_type="melee",
        damage=14,
        accuracy=85,
        ap_cost=2,
        hands=2,
        min_range=1,
        max_range=1,
        ammo_capacity=-1,
        price=0,
        tech_level=3,
        shop_available=False,
        loot_droppable=False,
        noise=3,
        # The organic twin of the Warden slam's pushback (SETTLED 42):
        # the anchor apex ejects its victim along the attack vector.
        knockback=2,
    ),
    GroundWeaponSpec(
        id="wyrm_breath",
        name="Wyrm Breath",
        damage_type="energy",
        damage=10,
        accuracy=80,
        ap_cost=2,
        hands=1,
        min_range=2,
        max_range=6,
        ammo_capacity=-1,
        price=0,
        tech_level=3,
        shop_available=False,
        loot_droppable=False,
        noise=6,
        # The soak-breaker: dodge answers what armor cannot (the
        # armor_bypass damage behavior through the existing field).
        armor_bypass=True,
    ),
    GroundWeaponSpec(
        id="siege_bolt",
        name="Siege Bolt",
        damage_type="kinetic",
        damage=12,
        accuracy=75,
        ap_cost=3,
        hands=2,
        min_range=4,              # the bombardier's own dead zone —
        max_range=9,              # close inside its band
        ammo_capacity=-1,
        price=0,
        tech_level=3,
        shop_available=False,
        loot_droppable=False,
        noise=8,
    ),
)
