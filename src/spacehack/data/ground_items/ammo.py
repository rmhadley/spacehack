"""Ground ammunition catalog — calibers the bandolier tracks (doc 52).

Each entry is a frozen :class:`GroundAmmoSpec`. ``ammo_type`` is the
identity that links a caliber to the weapons it feeds; ``carry_cap`` is
the bandolier maximum per caliber (doc 52 SETTLED 1: ~40-50 kills of
endurance for gun calibers, ~10 uses for premium explosives). The
legacy stack rows stay for pre-52 save migration only.
"""

from . import GroundAmmoSpec

AMMO: tuple[GroundAmmoSpec, ...] = (
    GroundAmmoSpec(
        id="pistol_rounds",
        name="Pistol Rounds",
        ammo_type="kinetic_pistol",
        rounds_per_stack=40,
        price_per_round=1,
        carry_cap=160,
    ),
    GroundAmmoSpec(
        id="rifle_rounds",
        name="Rifle Rounds",
        ammo_type="rifle_round",
        rounds_per_stack=40,
        price_per_round=2,
        carry_cap=240,
    ),
    GroundAmmoSpec(
        id="shotgun_shells",
        name="Shotgun Shells",
        ammo_type="shotgun_shell",
        rounds_per_stack=20,
        price_per_round=2,
        carry_cap=130,
    ),
    GroundAmmoSpec(
        id="energy_cells",
        name="Energy Cells",
        ammo_type="energy_cell",
        rounds_per_stack=50,
        price_per_round=1,
        carry_cap=250,
    ),
    GroundAmmoSpec(
        id="grenades",
        name="Grenades",
        ammo_type="grenade",
        rounds_per_stack=6,
        price_per_round=8,
        carry_cap=18,
    ),
    GroundAmmoSpec(
        id="rockets",
        name="Rockets",
        ammo_type="rocket",
        rounds_per_stack=4,
        price_per_round=20,
        carry_cap=10,
    ),
)
