"""Ancient machines — the prison's alien trio (doc 48 phase 9 build 2).

Pins the weapon family (SETTLED 29/42/44), the three specs (SETTLED
42/45), and their mechanics against the build-1 volley loop. Grows
per build.
"""

from src.spacehack.data.ground_weapons import (
    find_ground_weapon,
    list_ground_weapons,
    weapon_families,
)

# The family's own three rows (SETTLED 29: never cross-resolved with
# human bands; SETTLED 44: the shot is a normal volley weapon).
_ANCIENT_ROWS = ("ancient_claws", "ancient_slam", "ancient_warden_shot")


def test_ancient_weapon_rows_register():
    for wid in _ANCIENT_ROWS:
        ws = find_ground_weapon(wid)
        assert ws.shop_available is False
        assert ws.loot_droppable is False


def test_ancient_family_never_ladders():
    # SETTLED 29: the family is structurally absent from the band
    # ladder (every row non-droppable, the monsters-module precedent).
    assert "ancient" not in weapon_families()


def test_ancient_weapons_are_not_ammo_fed():
    # SETTLED 43: participation is by weapon data — nothing ancient
    # carries a magazine or draws from a pool.
    from src.spacehack.ground_scale import ammo_fed

    for wid in _ANCIENT_ROWS:
        assert not ammo_fed(find_ground_weapon(wid))


def test_knockback_field_defaults_to_zero_everywhere_else():
    # The slam is the ONLY authored wearer (doc 48 SETTLED 42); the
    # field's default keeps every human weapon pushback-free.
    wearers = {
        ws.id for ws in list_ground_weapons() if ws.knockback > 0
    }
    assert wearers == {"ancient_slam"}
    assert find_ground_weapon("ancient_slam").knockback == 2


def test_warden_shot_is_a_normal_volley_weapon():
    # SETTLED 44: ap_cost 3, armor-pierce through the EXISTING field
    # (soak contributes zero — no new math), a real min band so the
    # point-blank penalty composes honestly.
    ws = find_ground_weapon("ancient_warden_shot")
    assert ws.ap_cost == 3
    assert ws.armor_bypass is True
    assert ws.min_range >= 2
    from src.spacehack.combat._ground_math import ground_damage_raw

    assert ground_damage_raw("ancient_warden_shot", 10, 23) == 30
    assert ground_damage_raw("ancient_warden_shot", 10, 0) == 30

