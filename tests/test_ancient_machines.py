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
    # The authored wearers (doc 48 SETTLED 42 + phase 10's organic
    # twin): the Warden slam and the apex behemoth_maul; the field's
    # default keeps every human weapon pushback-free.
    wearers = {
        ws.id for ws in list_ground_weapons() if ws.knockback > 0
    }
    assert wearers == {"ancient_slam", "behemoth_maul"}
    assert find_ground_weapon("ancient_slam").knockback == 2
    assert find_ground_weapon("behemoth_maul").knockback == 2


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
        # equipment_loot_pool RETIRED with the channel (doc 48
        # SETTLED 56) — the field itself is gone.
        assert not hasattr(spec, "equipment_loot_pool")
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


# --- the prison re-pin (SETTLED 29-as-amended + 42) ---------------------------


def test_prison_generation_data_is_all_ancient():
    """Every activation event resolves an ancient machine; no
    contemporary drone id remains in prison GENERATION data (live
    old saves keep theirs — the ids stay registered)."""
    from src.spacehack.data.dungeon_extensions import find_extension

    prison = find_extension("mars_alien_prison")
    assert prison.security_fallback_id == "watcher"
    for floor in prison.floors:
        for event in floor.activation_events:
            assert event.enemy_id in {"watcher", "shredder", "warden"}, (
                floor.floor, event.id,
            )
        for monster in floor.params.monster_pool:
            assert monster not in {
                "sentry_drone", "assault_drone", "rock_scavenger",
            }, floor.floor


def test_rock_scavenger_is_gone_from_prison_pools():
    """The flagged punch-list rider: prison pools drop the desert
    fauna (station vermin only — hull_parasite)."""
    from src.spacehack.data.dungeon_extensions import find_extension

    prison = find_extension("mars_alien_prison")
    for floor in prison.floors:
        if floor.params.monster_pool:
            assert "rock_scavenger" not in floor.params.monster_pool


def test_warden_events_authored_on_the_deep_floors():
    """The deep-cell Wardens arrive via AUTHORED events (the brief's
    reviewer issue 9: the machine mapping alone never delivers
    them)."""
    from src.spacehack.data.dungeon_extensions import find_extension

    prison = find_extension("mars_alien_prison")
    for floor_number in (4, 5):
        events = [
            e for e in prison.floor(floor_number).activation_events
            if e.enemy_id == "warden"
        ]
        assert events and all(
            e.count <= e.max_count <= 3 for e in events
        ), floor_number


def test_contemporary_drones_keep_every_non_alien_job():
    """The re-pin's other edge: dig sites, derelict decks, Mars's own
    surface sites, and the registry itself keep the contemporary
    drone rows (source-scan pin — the swap is the prison's alone)."""
    from pathlib import Path

    repo = Path(__file__).resolve().parents[1]
    holders = {
        str(p.relative_to(repo))
        for p in (repo / "src/spacehack/data").rglob("*.py")
        if "sentry_drone" in p.read_text()
        or "assault_drone" in p.read_text()
    }
    assert {
        "src/spacehack/data/digs/__init__.py",
        "src/spacehack/data/npc_chars/__init__.py",
        "src/spacehack/data/npc_chars/crew_roles.py",
        "src/spacehack/data/npc_chars/monsters.py",
        "src/spacehack/data/planets/mars.py",
    } <= holders
    assert not any(
        "dungeon_extensions" in holder for holder in holders
    ), "the prison's generation data must carry no drone id"


def test_the_dormant_fallback_reads_the_authored_field():
    """The :639 sentry_drone hardcode is dead — an event-less floor's
    lockdown extras draw the extension's authored fallback id."""
    from types import SimpleNamespace

    from src.spacehack import world
    from src.spacehack.dungeon_activation import _stock_lockdown_extras

    tile = world.Tile("floor", ".", True, (200, 210, 220), (10, 20, 30))
    wall = world.Tile("wall", "#", False, (1, 1, 1), (0, 0, 0))
    game_map = world.GameMap(
        width=11, height=11,
        tiles=[[tile for _ in range(11)] for _ in range(11)],
        entities=[],
    )
    # one true alcove beside the spawn: a wall pocket with exactly a
    # single walkable opening
    for cell in ((4, 4), (6, 4), (5, 3), (5, 4)):
        game_map.tiles[cell[1]][cell[0]] = wall
    floor = SimpleNamespace(
        activation_events=(), lockdown_extras=1,
        floor=1,
    )
    spawn = world.Position(5, 5)
    _stock_lockdown_extras(
        game_map, floor, spawn, set(), set(),
        landmark_cells=set(), transit_cells=set(),
        fallback_id="watcher",
    )
    assert [
        e.npc_char_id for e in game_map.entities
    ] == ["watcher"]

    # neither events nor fallback: no extras, and no alcoves carved
    empty_map = world.GameMap(
        width=11, height=11,
        tiles=[[tile for _ in range(11)] for _ in range(11)],
        entities=[],
    )
    _stock_lockdown_extras(
        empty_map, floor, spawn, set(), set(),
        landmark_cells=set(), transit_cells=set(),
        fallback_id="",
    )
    assert empty_map.entities == []


def test_warden_events_wake_silent():
    """The wordless wake (the reuse-dedupe catch): the Warden events
    never fire a popup — no reused prose can double-show in a run;
    the log's shared spawn line still reads."""
    from src.spacehack.data.dungeon_extensions import find_extension

    prison = find_extension("mars_alien_prison")
    for floor_number in (4, 5):
        warden_events = [
            e for e in prison.floor(floor_number).activation_events
            if e.enemy_id == "warden"
        ]
        assert warden_events and all(e.silent for e in warden_events)


def test_probe_extension_cells_pinned():
    """The probe's generated-floor placement (doc 48 p9): the
    walkable-graph band pick — path-distance band from the spawn,
    spread >= 3 apart, never on an occupant, capped at the sight
    radius (the harness disengages what it cannot see)."""
    import importlib.util
    from pathlib import Path

    spec = importlib.util.spec_from_file_location(
        "balance_probe",
        Path(__file__).resolve().parents[1] / "tools" / "balance_probe.py",
    )
    import sys as _sys

    probe = importlib.util.module_from_spec(spec)
    _sys.modules["balance_probe"] = probe  # dataclass resolution needs it
    spec.loader.exec_module(probe)

    tile = world.Tile("floor", ".", True, (200, 210, 220), (10, 20, 30))
    wall = world.Tile("wall", "#", False, (1, 1, 1), (0, 0, 0))
    game_map = world.GameMap(
        width=20, height=20,
        tiles=[[tile for _ in range(20)] for _ in range(20)],
        entities=[], sight_radius=8,
    )
    # a wall ring at Chebyshev 5-6 around the spawn: picks must route
    # through the one gap at (10, 5) — path distance, not Chebyshev
    for y in range(4, 13):
        for x in range(4, 17):
            if max(abs(x - 10), abs(y - 10)) in (5, 6) and (x, y) != (10, 5):
                if game_map.in_bounds(x, y):
                    game_map.tiles[y][x] = wall
    game_map.entities.append(world.Entity(
        "X", (1, 1, 1), world.Position(14, 14),
    ))
    cells = probe._extension_cells(
        game_map, world.Position(10, 10), 3,
    )
    assert len(cells) == 3
    assert all(game_map.tiles[y][x].walkable for x, y in cells)
    assert all((x, y) != (14, 14) for x, y in cells)
    for i, a in enumerate(cells):
        for b in cells[i + 1:]:
            assert max(abs(a[0] - b[0]), abs(a[1] - b[1])) >= 3
