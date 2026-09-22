"""Ground tactics wave tests (doc 48 phase 5, SETTLED 16-27/36/37).

Build 1: the data layer — per-weapon noise column, per-spec AP, the
detect_radius retirement. Later builds extend this module with the
noise system, combat-time movement, range management, and enemy
consumables.
"""

from __future__ import annotations

import pytest

from src.spacehack.data.ground_weapons import list_ground_weapons
from src.spacehack.data.npc_chars import NpcCharSpec, find_npc_char
from src.spacehack.data.npc_ships import NpcShipSpec


# --- weapon noise column (SETTLED 17) ---------------------------------------

# The authored leans, pinned id-by-id so a new weapon FAILS until its
# hearing radius is authored (registry completeness). Playtest-tunable:
# edits update this table in the same commit.
EXPECTED_NOISE: dict[str, int] = {
    # melee 1-2 — knife kills stay quiet
    "fists": 1, "combat_knife": 1, "stun_baton": 2, "survival_axe": 2,
    "vibroblade": 2, "mono_blade": 2, "power_fist": 2,
    # pistols/SMG 5-6; energy rides the quiet lever at 4
    "laser_pistol": 4, "kinetic_pistol": 5, "smg": 6, "laser_carbine": 4,
    # kinetic rifles 8; energy rifles quiet
    "laser_rifle": 4, "kinetic_rifle": 8, "shotgun": 8, "battle_rifle": 8,
    "railgun": 8, "ion_blaster": 4,
    # plasma 4 — the energy lever
    "plasma_pistol": 4, "plasma_rifle": 4, "plasma_caster": 4,
    # explosives 12
    "grenade_launcher": 12, "rocket_launcher": 12,
    # organic monster parts 4-5
    "monster_claws": 4, "drone_laser": 4, "frost_bolt": 5,
    "parasite_mandibles": 4,
}


def test_every_ground_weapon_carries_authored_noise():
    catalog = {w.id: w.noise for w in list_ground_weapons()}
    assert catalog == EXPECTED_NOISE


@pytest.mark.parametrize("wid,noise", sorted(EXPECTED_NOISE.items()))
def test_noise_values_stay_in_playable_band(wid, noise):
    assert 1 <= noise <= 12, f"{wid} noise {noise} outside [1, 12]"


# --- per-spec AP (SETTLED 27) ----------------------------------------------

def test_authored_speed_axis_aps():
    assert find_npc_char("dust_prowler").ap == 6
    for hunter in ("ice_worm", "rock_scavenger", "hull_parasite"):
        assert find_npc_char(hunter).ap == 5
    for anchor in ("assault_drone", "pirate_brute"):
        assert find_npc_char(anchor).ap == 3


def test_humanoids_and_sentry_default_to_four_ap():
    for spec_id in (
        "pirate_raider", "pirate_rifleman", "militia_marine",
        "militia_sniper", "militia_trooper", "consortium_enforcer",
        "consortium_gunner", "civilian_bystander", "sentry_drone",
        "frost_spitter",
    ):
        assert find_npc_char(spec_id).ap == 4


# --- detect_radius retirement (SETTLED 36) ---------------------------------

def test_ground_detect_radius_is_retired():
    with pytest.raises(TypeError):
        NpcCharSpec(
            id="x", name="X", char="x", fg=(1, 2, 3), faction="pirate",
            detect_radius=5,
        )


def test_ship_detect_radius_stays_live():
    """The retirement is ground-only — NpcShipSpec keeps its field."""
    assert NpcShipSpec.__dataclass_fields__["detect_radius"].default == 0
