"""Ground ammunition catalog — reserve ammo carried in the Expedition Pack.

Each entry is a frozen :class:`GroundAmmoSpec`. ``ammo_type`` is the
identity that links a stack to the weapons it feeds; the weapon-side
``ammo_type`` backfill lands with design doc 19 Phase 2/3.
"""

from . import GroundAmmoSpec

AMMO: tuple[GroundAmmoSpec, ...] = (
    GroundAmmoSpec(
        id="pistol_rounds",
        name="Pistol Rounds",
        ammo_type="kinetic_pistol",
        rounds_per_stack=40,
        price_per_round=1,
    ),
    GroundAmmoSpec(
        id="rifle_rounds",
        name="Rifle Rounds",
        ammo_type="rifle_round",
        rounds_per_stack=40,
        price_per_round=2,
    ),
    GroundAmmoSpec(
        id="shotgun_shells",
        name="Shotgun Shells",
        ammo_type="shotgun_shell",
        rounds_per_stack=20,
        price_per_round=2,
    ),
    GroundAmmoSpec(
        id="energy_cells",
        name="Energy Cells",
        ammo_type="energy_cell",
        rounds_per_stack=50,
        price_per_round=1,
    ),
    GroundAmmoSpec(
        id="grenades",
        name="Grenades",
        ammo_type="grenade",
        rounds_per_stack=6,
        price_per_round=8,
    ),
    GroundAmmoSpec(
        id="rockets",
        name="Rockets",
        ammo_type="rocket",
        rounds_per_stack=4,
        price_per_round=15,
    ),
)
