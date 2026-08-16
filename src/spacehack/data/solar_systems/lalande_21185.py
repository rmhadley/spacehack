"""Lalande 21185 — the uncharted star beyond the north arm.

Every chart ends at Groombridge 34. Beyond the gate there should
be nothing but dark — and for years, that was true. Then a survey
drone lost on a dead heading came home six decades late with a
single image: a dim red star, no catalogue number, no beacon, no
colony registry. The transport "Requiem" answered the signal and
went silent mid-flight. The system was marked hazard, and the arm
was quietly closed.

The squatters who finally ran the gate anyway found the Requiem's
habitat deck frozen solid and the Record vault gone. They stayed.
Deadfall, a colony built on the ice from the Requiem's wreckage,
and Whisper, a vault moon where the lost manifest's cargo surfaces
for a price. Beyond them the path ends in a husk of a gas giant
and a belt of dead metal — and the Tollkeeper's garrison, which
has never let anyone leave richer than they arrived.

There is ONE Jump Point back to Groombridge. Lalande 21185 is a
dead end by design: the end of the arm.

Map dims match the other 200x140 systems.
"""
from __future__ import annotations

from spacehack import solar_system as solar_module
from spacehack import world

from . import EnemySpawn, JumpPoint, SolarSystem


_planets: tuple[solar_module.Planet, ...] = (
    # Lalande 21185 — a dim red dwarf, 7x7 footprint. The pale
    # violet-red reads 'wrong star' against the charted reds.
    solar_module.Planet(
        id="sun", name="Lalande 21185",
        char="O", fg=(235, 90, 110),
        pos=world.Position(100, 70), width=7, height=7,
        sun=True,
        description="A dim red dwarf - the star that appears on no chart.",
    ),
    # Deadfall — frozen world, landable (Requiem colony).
    solar_module.Planet(
        id="lal_b", name="Deadfall",
        char="p", fg=(140, 150, 160),
        pos=world.Position(45, 55), width=3, height=3,
        description="A squatters' colony on a frozen world - the Requiem's last stop.",
    ),
    # Whisper — vault moon, landable (smuggler den).
    solar_module.Planet(
        id="lal_c", name="Whisper",
        char="p", fg=(90, 100, 140),
        pos=world.Position(152, 100), width=2, height=2,
        description="The Vault - a smuggler moon no chart mentions.",
    ),
    # Husk — the dead gas giant trailing a ring of wreckage.
    solar_module.Planet(
        id="lal_d", name="Husk",
        char="P", fg=(110, 130, 170),
        pos=world.Position(150, 38), width=4, height=4,
        description="A cold, dead gas giant ringed with the wreckage of old convoys.",
    ),
)


# Single Jump Point on the WEST — back to Groombridge. The arm
# truly ends here; this gate is the only charted way home.
_jump_points: tuple[JumpPoint, ...] = (
    JumpPoint(
        id="jump_groombridge",
        name="Groombridge Gate",
        char=">",
        fg=(255, 100, 70),                           # cool red (Groombridge palette)
        pos=world.Position(5, 70),
        width=2, height=2,
        connects_to=(("groombridge", "jump_lalande_21185"),),
        description="A humming FTL gate facing Groombridge - the road back to the charts.",
    ),
)


# Static garrison — the Tollkeeper. A warlord frigate and two
# marauders hold the reach between the gate and Deadfall: the
# first and last thing any visitor sees.
_static_enemies: tuple[EnemySpawn, ...] = (
    EnemySpawn(
        enemy_id="pirate_warlord",
        pos=world.Position(78, 30),
        squad_id="lal_tollkeeper",
    ),
    EnemySpawn(
        enemy_id="pirate_marauder",
        pos=world.Position(68, 36),
        squad_id="lal_tollkeeper",
    ),
    EnemySpawn(
        enemy_id="pirate_marauder",
        pos=world.Position(86, 42),
        squad_id="lal_tollkeeper",
    ),
    # Casket raiders — a fast pair that prowls the dark between
    # Deadfall and the Husk.
    EnemySpawn(
        enemy_id="pirate_hound",
        pos=world.Position(118, 24),
        squad_id="lal_casket_raiders",
    ),
    EnemySpawn(
        enemy_id="pirate_hound",
        pos=world.Position(128, 30),
        squad_id="lal_casket_raiders",
    ),
)


_stars = solar_module.make_stars(200, 140, seed="lalande_21185")


SYSTEM: SolarSystem = SolarSystem(
    id="lalande_21185",
    name="Lalande 21185",
    width=200,
    height=140,
    planets=_planets,
    jump_points=_jump_points,
    stations=(),
    stars=_stars,
    enemies=_static_enemies,
    # Beyond any patrol route — no militia, all pirates, and
    # enough of them that every crossing is a decision.
    npc_spawn_chance=0.90,
    npc_spawn_table=(
        ("pirate_raider", 0.85),
        ("pirate_marauder", 0.65),
        ("pirate_hound", 0.60),
        ("pirate_warlord", 0.35),
        ("pirate_scout", 0.40),
        ("merchant_caravan", 0.25),
    ),
    npc_density=7,
    patrol_density=(0, 0),
    derelict_spawn_chance=0.10,
)