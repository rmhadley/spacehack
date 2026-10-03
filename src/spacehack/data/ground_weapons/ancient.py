"""Ancient-machine weapons — the prison's alien attackers (doc 48 SETTLED 29/42/44).

The ancient family's OWN module, never cross-resolved with human bands
(SETTLED 29): no row ladders (``loot_droppable=False`` — no usable
drops, the sites pay in alien tech), never sold (``shop_available=False``),
nothing ammo-fed (SETTLED 43: participation is by weapon data).

Soak semantics are per-weapon authored behavior (the 10-02 sim's flag
resolved): claws and the slam soak FULL armor; the shot pierces via the
existing ``armor_bypass`` field — no new energy-type math.
"""

from . import GroundWeaponSpec

WARES: tuple[GroundWeaponSpec, ...] = (
    GroundWeaponSpec(
        id="ancient_claws",
        name="Shredder Claws",
        damage_type="melee",
        damage=26,
        accuracy=85,
        ap_cost=2,
        hands=2,
        min_range=1,
        max_range=1,
        ammo_capacity=-1,
        price=0,
        tech_level=4,
        shop_available=False,
        loot_droppable=False,
        noise=2,
    ),
    GroundWeaponSpec(
        id="ancient_slam",
        name="Warden Slam",
        damage_type="melee",
        damage=15,
        accuracy=90,
        ap_cost=2,
        hands=2,
        min_range=1,
        max_range=1,
        ammo_capacity=-1,
        price=0,
        tech_level=4,
        shop_available=False,
        loot_droppable=False,
        noise=3,
        # The game's first authored knockback (doc 48 SETTLED 42): the
        # slam's ~2-cell pushback is WEAPON DATA — player-side weapons
        # may carry the field someday.
        knockback=2,
    ),
    GroundWeaponSpec(
        id="ancient_warden_shot",
        name="Warden Shot",
        damage_type="energy",
        damage=30,
        accuracy=95,
        ap_cost=3,
        hands=2,
        min_range=2,
        max_range=8,
        ammo_capacity=-1,
        price=0,
        tech_level=4,
        shop_available=False,
        loot_droppable=False,
        noise=8,
        # A normal volley weapon (SETTLED 44): no telegraph, no lane,
        # no charge — scored by EV-per-AP like every weapon. The
        # armor-pierce is DAMAGE behavior through the existing field.
        armor_bypass=True,
    ),
)
