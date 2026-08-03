"""Breach charge prototype — temporarily mounted during the militia
live-fire test (mil_q5_livefire).  Not sold at any mechanic; only
available during the quest combat at Cygni b.

Design doc: docs/design/in_progress/07_DESIGN_MAIN_QUEST.md
"""

from __future__ import annotations

from . import WeaponSpec

WEAPONS: tuple[WeaponSpec, ...] = (
    WeaponSpec(
        id="breach_charge_test",
        name="Breach Charge (Prototype)",
        slot_type="energy",
        damage=90,
        accuracy=95,
        ap_cost=3,
        power_cost=10,
        ammo_capacity=-1,
        min_range=1,
        max_range=8,
        shield_strip=50,
        price=0,
        tech_level=99,
    ),
)
