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
from src.spacehack.data.npc_chars import (
    CHAR_CLASS_FAMILIES,
    find_npc_char,
    list_npc_chars,
)
from src.spacehack import world
from src.spacehack.ground_scale import derive_stats, entity_band

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

# --- the three specs (SETTLED 42/45) ----------------------------------------


def test_ancient_rows_register_with_authored_stat_block():
    watcher = find_npc_char("watcher")
    shredder = find_npc_char("shredder")
    warden = find_npc_char("warden")
    assert (watcher.hp, watcher.armor, watcher.ap) == (16, 0, 4)
    assert (shredder.hp, shredder.armor, shredder.ap) == (80, 10, 6)
    assert (warden.hp, warden.armor, warden.ap) == (65, 12, 3)
    for spec in (watcher, shredder, warden):
        assert spec.always_hostile is True
        assert spec.faction == ""
        assert spec.fixed_band == 4
        assert spec.loot_count == (0, 0)  # no usable drops (SETTLED 29)
        assert spec.loot_pool == ()
        assert spec.equipment_loot_pool == ()
        assert spec.field_item_loot_pool == ()


def test_ancient_family_glyphs_and_color():
    # SETTLED 45: three DISTINCT letters, ONE cold violet; the Warden
    # alone is bold (the unique's emphasis callout).
    family = CHAR_CLASS_FAMILIES["ancient"]
    assert family.glyphs == ("O", "S", "W")
    assert family.color == (170, 140, 250)
    assert find_npc_char("watcher").char == "O"
    assert find_npc_char("shredder").char == "S"
    assert find_npc_char("warden").char == "W"
    assert find_npc_char("warden").elite is True
    assert not any(
        find_npc_char(_id).elite for _id in ("watcher", "shredder")
    )


def test_ancient_glyphs_are_tile_free():
    # The glyph-freeness lesson: check TILE glyphs, not just registries
    # (the lowercase-o prison-panel rejection, SETTLED 45). Scope: the
    # world tile REGISTRY — the tiles the machines' own floors paint.
    # Known cross-context shares OUTSIDE this registry, tolerated by
    # SETTLED 45's never-co-rendered classes: the space map's sun `O`
    # (solar_system.py) and Saturn `S` (data/solar_systems/sol.py),
    # and indi_b's grain-silo `O` (indi_city.py) — a ground CITY tile;
    # the machines are prison-exclusive FOR NOW, and a prison floor
    # never co-renders with a city map either.
    tile_chars = {
        value.char for value in vars(world).values()
        if isinstance(value, world.Tile)
    }
    assert set("OSW").isdisjoint(tile_chars)


def test_fixed_band_pins_flat_over_the_site_stamp():
    # SETTLED 42: the rows derive at band 4 FLAT — a floor-1 stamp
    # never dilutes them (the difficulty axis is row-picking, SETTLED 29).
    from src.spacehack.engine import RNG
    from src.spacehack.ground_scale import roll_loadout

    spec = find_npc_char("watcher")
    entity = world.Entity(
        char="O", fg=(170, 140, 250),
        pos=world.Position(1, 1), npc_char_id="watcher",
        spawn_band=1,
    )
    assert entity_band(entity, None, spec=spec) == 4
    # The loadout roll resolves through the same pinned band; a
    # weaponless row stamps both slots empty (drops read the emptiness).
    stamp = roll_loadout(spec, entity_band(entity, None, spec=spec), RNG)
    assert stamp["ranged"] is None and stamp["melee"] is None


def test_watcher_derives_authored_reflexes_at_band_4():
    # "Look at the accuracy we're bringing": reflexes-max weights at
    # the pinned band land the authored 90-100 REF ceiling.
    stats = derive_stats(find_npc_char("watcher"), 4)
    assert stats.reflexes >= 90


def test_machine_mechanics_dials_are_authored():
    # SETTLED 42 leans, pinned as data: stare core + shriek radius on
    # the Watcher; in-combat mend on the Shredder; field tile HP +
    # regen on the Warden; every ordinary row carries None.
    watcher = find_npc_char("watcher").mechanics
    shredder = find_npc_char("shredder").mechanics
    warden = find_npc_char("warden").mechanics
    assert 32 <= watcher.stare_core <= 42
    assert 25 <= watcher.shriek_radius <= 40
    assert shredder.mend_rate == 5
    assert warden.field_tile_hp == 30
    assert warden.field_regen >= 10

    for spec in list_npc_chars():
        if spec.id not in {"watcher", "shredder", "warden"}:
            assert spec.mechanics is None, spec.id

def test_warden_carries_both_weapon_sets():
    # The shot rides the ranged slot; the slam is the melee set — the
    # volley scorer picks between them (fire at range, slam in melee).
    warden = find_npc_char("warden")
    assert warden.weapons == ("ancient_warden_shot",)
    assert warden.melee_weapons == ("ancient_slam",)
    assert find_npc_char("shredder").weapons == ("ancient_claws",)
    assert find_npc_char("watcher").weapons == ()
