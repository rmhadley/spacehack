"""Ross 154 — the flare star at the end of the Sirius arm.

The Binary Station operators first logged Ross 154 as a flare star
just three light-years past Sirius: violent, unpredictable, and
forever washing out scan range. That was the end of the public
record. Anything official that tried to survey it came back with
corrupted charts and empty logs — or didn't come back.

What's actually here is a pirate kingdom the flares built. The
storms scramble sensors just enough that the federation's patrols
never bother; the deep currents make the sector a reef. Two
settlements keep the economy alive: Ashfall on Ember, a fire-and-
bounty town; and the Scrap Ring on Cinder, a salvage bazaar domed
over a shattered moon. The Warlord of the Flare Crown keeps a
garrison in the belt, between the ports and the gate — anyone
flying this deep pays in either blood or cargo.

There is ONE Jump Point back to Sirius. Ross 154 is a dead end by
design: the deep end.

Map dims match the other 200x140 systems.
"""
from __future__ import annotations

from spacehack import solar_system as solar_module
from spacehack import world

from . import EnemySpawn, JumpPoint, SolarSystem


_planets: tuple[solar_module.Planet, ...] = (
    # Ross 154 — a flaring red dwarf, 7x7 footprint. Wavering
    # orange-red reads 'this star is angry'.
    solar_module.Planet(
        id="sun", name="Ross 154",
        char="O", fg=(255, 110, 70),
        pos=world.Position(100, 70), width=7, height=7,
        sun=True,
        description="A flaring red dwarf - the last star on this arm.",
    ),
    # Ember — flare-scorched rocky world, landable (Ashfall town).
    solar_module.Planet(
        id="ross_b", name="Ember",
        char="p", fg=(200, 90, 50),
        pos=world.Position(48, 108), width=2, height=2,
        description="Ashfall - a pirate town on a flare-scorched world.",
    ),
    # Cinder — a shattered moon with the Scrap Ring dome city.
    solar_module.Planet(
        id="ross_c", name="Cinder",
        char="p", fg=(150, 120, 160),
        pos=world.Position(152, 45), width=2, height=2,
        description="The Scrap Ring - a salvage bazaar domed over a shattered moon.",
    ),
)


# Single Jump Point on the WEST — back to Sirius. Ross 154 is a
# dead-end tail by design: the arm ends here in flame.
_jump_points: tuple[JumpPoint, ...] = (
    JumpPoint(
        id="jump_sirius",
        name="Sirius Gate",
        char=">",
        fg=(180, 200, 255),                           # pale blue-white (Sirius palette)
        pos=world.Position(5, 70),
        width=2, height=2,
        connects_to=(("sirius", "jump_ross_154"),),
        description="A humming FTL gate facing Sirius - the only road back to charted space.",
    ),
)


# Static garrison — the Flare Crown. A warlord frigate with two
# marauder cruisers holding the mid-sector, between the jump gate
# and both settlements, so no one gets in or out without paying.
_static_enemies: tuple[EnemySpawn, ...] = (
    EnemySpawn(
        enemy_id="pirate_warlord",
        pos=world.Position(102, 82),
        squad_id="ross_flare_crown",
    ),
    EnemySpawn(
        enemy_id="pirate_marauder",
        pos=world.Position(93, 92),
        squad_id="ross_flare_crown",
    ),
    EnemySpawn(
        enemy_id="pirate_marauder",
        pos=world.Position(112, 74),
        squad_id="ross_flare_crown",
    ),
    # Gate wolves — a fast pair that snaps at anyone who lingers
    # near the way back out.
    EnemySpawn(
        enemy_id="pirate_hound",
        pos=world.Position(48, 28),
        squad_id="ross_gate_wolves",
    ),
    EnemySpawn(
        enemy_id="pirate_hound",
        pos=world.Position(58, 22),
        squad_id="ross_gate_wolves",
    ),
)


_stars = solar_module.make_stars(200, 140, seed="ross_154")


SYSTEM: SolarSystem = SolarSystem(
    id="ross_154",
    name="Ross 154",
    width=200,
    height=140,
    planets=_planets,
    jump_points=_jump_points,
    stations=(),
    stars=_stars,
    enemies=_static_enemies,
    # No militia anywhere near this arm — patrol_density stays (0, 0).
    # The danger is overwhelming pirate traffic + the static garrison.
    npc_spawn_chance=0.90,
    npc_spawn_table=(
        ("pirate_raider", 0.85),
        ("pirate_hound", 0.65),
        ("pirate_marauder", 0.60),
        ("pirate_warlord", 0.30),
        ("pirate_scout", 0.45),
        ("merchant_caravan", 0.20),      # rare, rich prey - worth the trip
    ),
    npc_density=7,
    patrol_density=(0, 0),
    derelict_spawn_chance=0.10,          # salvage is a big reason to come out here
)