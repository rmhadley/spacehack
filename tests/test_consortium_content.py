"""Consortium content tests (doc 48 phase 11, SETTLED 50-54).

The hunt's two ships, the three ground rungs, the quality floors, the
reskin, and the exposure guard (SETTLED 12 — nothing procedural
spawns consortium).
"""

import random

from src.spacehack import ground_scale, space_scale
from src.spacehack.data.npc_chars import find_npc_char, list_npc_chars
from src.spacehack.data.npc_ships import find_npc_ship, list_npc_ships
from src.spacehack.data.ships import find_ship
from src.spacehack.data.solar_systems import list_solar_systems


# --- the two hunter ships (SETTLED 52) --------------------------------------

def test_hunter_registry_pins():
    hunter = find_npc_ship("consortium_hunter")
    assert hunter.name == "Consortium Hunter"
    assert hunter.ship_id == "cruiser"
    assert hunter.char == find_ship("cruiser").char
    assert hunter.fg == (90, 120, 200)
    assert hunter.faction == "consortium"
    assert hunter.band == 2
    assert hunter.elite is False
    assert hunter.capture_layout_id == "cruiser_crew"
    assert hunter.quality_floor == 1


def test_dreadnought_registry_pins():
    anchor = find_npc_ship("consortium_dreadnought")
    assert anchor.name == "Consortium Dreadnought"
    assert anchor.ship_id == "frigate"
    assert anchor.char == find_ship("frigate").char
    assert anchor.fg == (90, 120, 200)
    assert anchor.faction == "consortium"
    assert anchor.band == 3
    assert anchor.elite is True  # the bold-F hunt anchor (SETTLED 33/50)
    assert anchor.capture_layout_id == "frigate_crew"
    assert anchor.quality_floor == 1
    assert anchor.shield_regen_rate == 2  # the captain/patrol_heavy class


def test_hunters_fly_existing_ids_only():
    """No new module or weapon ids (SETTLED 52 stop point)."""
    from src.spacehack.data.modules import find_module
    from src.spacehack.data.weapons import find_weapon

    for spec_id in ("consortium_hunter", "consortium_dreadnought"):
        spec = find_npc_ship(spec_id)
        for weapon_id in spec.weapons:
            find_weapon(weapon_id)  # raises KeyError on an unknown id
        for module_id in spec.modules:
            find_module(module_id)


def test_no_system_spawn_table_fields_consortium():
    """SETTLED 12/52: the two hunt beats are the hunters' ONLY spawn
    surfaces — no ``npc_spawn_table`` seat anywhere."""
    for system in list_solar_systems():
        for npc_id, _weight in system.npc_spawn_table:
            spec = find_npc_ship(npc_id)
            assert spec.faction != "consortium", (
                f"{system.id} spawn table seats {npc_id}"
            )


# --- the quality floor (SETTLED 51/52) --------------------------------------

def test_flown_floor_zero_is_bit_identical():
    """Floor 0 draws identically to the no-floor path — one RNG draw
    either way, no player path carries a floor."""
    for band in (0, 1, 4):
        ids = ("light_laser", "heavy_missile", "shield_mk1")
        plain = space_scale.roll_flown_equipment(
            "weapon", ids, band, random.Random(7),
        )
        floored = space_scale.roll_flown_equipment(
            "weapon", ids, band, random.Random(7), quality_floor=0,
        )
        assert plain == floored


def test_flown_floor_one_never_rolls_base():
    weapons = space_scale.roll_flown_equipment(
        "weapon", ("light_laser", "heavy_laser", "light_laser"),
        2, random.Random(11), quality_floor=1,
    )
    modules = space_scale.roll_flown_equipment(
        "module", ("shield_mk1", "targeting_computer"), 2,
        random.Random(12), quality_floor=1,
    )
    for entry in weapons + modules:
        assert entry.quality >= 1


def test_flown_floor_clamp_distribution_is_pinned():
    """CLAMP semantics (SETTLED 52): the below-floor mass lumps onto
    the floor rung; every higher tier's count is UNCHANGED."""
    ids = tuple(f"mod_{i}" for i in range(4000))
    plain = [
        entry.quality for entry in space_scale.roll_flown_equipment(
            "module", ids, 2, random.Random(99),
        )
    ]
    floored = [
        entry.quality for entry in space_scale.roll_flown_equipment(
            "module", ids, 2, random.Random(99), quality_floor=2,
        )
    ]
    assert set(floored) >= {2, 3}
    assert all(q >= 2 for q in floored)
    assert floored.count(3) == plain.count(3)
    assert floored.count(2) == plain.count(2) + plain.count(1) + plain.count(0)


def test_ground_roll_slot_floors_the_equip_draw():
    rng_a, rng_b = random.Random(3), random.Random(3)
    plain = ground_scale.roll_slot(("pistols",), (), 2, rng_a)
    floored = ground_scale.roll_slot(
        ("pistols",), (), 2, rng_b, quality_floor=1,
    )
    assert plain[0] == floored[0]  # same family/tier window draws
    assert floored[1] >= 1
    assert floored[1] >= plain[1]  # the clamp only ever raises


def test_rolled_weapon_quality_floor_zero_unchanged():
    rng_a, rng_b = random.Random(5), random.Random(5)
    for _ in range(50):
        plain = ground_scale.rolled_weapon_quality("kinetic_pistol", 2, rng_a)
        floored = ground_scale.rolled_weapon_quality(
            "kinetic_pistol", 2, rng_b, quality_floor=0,
        )
        assert plain == floored


def test_every_default_spec_carries_no_floor():
    """The floor is authored on the consortium rows only (SETTLED 51/
    52); every other row stays floor-0 in both registries."""
    for spec in list_npc_ships():
        if spec.faction != "consortium":
            assert spec.quality_floor == 0, spec.id
    for spec in list_npc_chars():
        if spec.faction != "consortium":
            assert spec.quality_floor == 0, spec.id


# --- the three ground rungs (SETTLED 51/54) ----------------------------------

from types import SimpleNamespace  # noqa: E402

from src.spacehack import ground_loadout  # noqa: E402
from src.spacehack import world  # noqa: E402
from src.spacehack.data.ground_armor import find_ground_armor  # noqa: E402

RUNG_PINS = {
    #          fixed_band  tier  elite  floor  worn pieces
    "consortium_gunner": (2, 2, False, 1, ("cybernetic_eyes", "cybernetic_arms")),
    "consortium_enforcer": (3, 3, False, 1, ("cybernetic_arms", "cybernetic_legs")),
    "consortium_executor": (
        4, 4, True, 2,
        ("cybernetic_eyes", "cybernetic_torso",
         "cybernetic_arms", "cybernetic_legs"),
    ),
}


def test_rung_registry_pins():
    names = {
        "consortium_gunner": "Consortium Gunner",
        "consortium_enforcer": "Consortium Enforcer",
        "consortium_executor": "Consortium Executor",  # SETTLED 54 verbatim
    }
    chars = {
        "consortium_gunner": "e",       # the common case
        "consortium_enforcer": "E",     # the serious case
        "consortium_executor": "E",     # the bold high rung
    }
    for spec_id, (band, tier, elite, floor, worn) in RUNG_PINS.items():
        spec = find_npc_char(spec_id)
        assert spec.name == names[spec_id]
        assert spec.char == chars[spec_id]
        assert spec.fg == (90, 120, 200)
        assert spec.faction == "consortium"
        assert spec.fixed_band == band, spec_id
        assert spec.tier == tier, spec_id
        assert spec.elite is elite, spec_id
        assert spec.quality_floor == floor, spec_id
        assert spec.worn_armor == worn, spec_id


def test_rung_fixed_band_never_diluted_by_the_site_stamp():
    """SETTLED 51: a rung reads identical wherever it appears — a
    floor-1 entity stamp does not dilute the Executor's band 4."""
    from src.spacehack import ground_scale as gs

    spec = find_npc_char("consortium_executor")
    entity = SimpleNamespace(spawn_band=1)
    assert gs.entity_band(entity, None, spec=spec) == 4


def test_rung_tier_gates_every_worn_piece():
    """The tier-gate law (doc 48 memory + brief): rung tier >= every
    worn piece's tech_level, or the drop filter silently empties."""
    for spec_id, (_band, tier, _elite, _floor, worn) in RUNG_PINS.items():
        for piece_id in worn:
            assert tier >= find_ground_armor(piece_id).tech_level, (
                spec_id, piece_id,
            )


def test_rung_equipment_loot_pools_retire_total():
    """The brief: worn pieces drop via the kit path — a residual
    equipment_loot_pool would roll UNFLOORED gear at the drop site."""
    for spec_id in RUNG_PINS:
        assert find_npc_char(spec_id).equipment_loot_pool == (), spec_id


def test_rung_quality_floors_pin():
    assert find_npc_char("consortium_executor").quality_floor == 2
    assert find_npc_char("consortium_gunner").quality_floor == 1
    assert find_npc_char("consortium_enforcer").quality_floor == 1


# --- the worn mechanism (SETTLED 51/27) --------------------------------------

def _rung_entity(spec_id):
    entity = world.Entity(
        "E", (90, 120, 200), world.Position(0, 0), "rung",
        npc_char_id=spec_id,
    )
    game_map = world.GameMap(
        width=4, height=3,
        tiles=[[world.DUNGEON_FLOOR for _ in range(4)] for _ in range(3)],
        entities=[entity],
    )
    return entity, game_map


def test_worn_stamp_resolves_once_and_floors():
    entity, game_map = _rung_entity("consortium_executor")
    stamp = ground_loadout.ensure_loadout(entity, game_map)
    worn = stamp["worn"]
    assert [entry[0] for entry in worn] == ["armor"] * 4
    assert [entry[1] for entry in worn] == list(
        find_npc_char("consortium_executor").worn_armor,
    )
    assert all(entry[2] >= 2 for entry in worn)  # overclocked floor

    # Idempotent: the second read returns the SAME list, never a re-roll.
    seed_state = [list(entry) for entry in worn]
    assert ground_loadout.ensure_loadout(entity, game_map)["worn"] is worn
    assert worn == seed_state


def test_worn_stamp_fills_on_a_p11_era_save():
    """A stamp saved before phase 11 carries no ``worn`` key — the
    pieces resolve at first engagement (the melee-set precedent)."""
    entity, game_map = _rung_entity("consortium_gunner")
    entity.rolled_loadout = {
        "ranged": ["kinetic_pistol", 1], "melee": ["combat_knife", 1],
        "loaded": {}, "pool": [], "active": "ranged",
    }
    stamp = ground_loadout.ensure_loadout(entity, game_map)
    assert [entry[1] for entry in stamp["worn"]] == [
        "cybernetic_eyes", "cybernetic_arms",
    ]
    assert all(entry[2] >= 1 for entry in stamp["worn"])


def test_worn_stamp_serializes_through_the_whitelist():
    from src.spacehack.saveload_maps import _loadout_dict, _loadout_from_dict

    entity, game_map = _rung_entity("consortium_executor")
    stamp = ground_loadout.ensure_loadout(entity, game_map)
    saved = _loadout_dict(stamp)
    assert _loadout_from_dict({"rolled_loadout": saved})["worn"] == saved["worn"]
    # Key-absent (a pre-11 save) loads WITHOUT the key — the fill is
    # ensure_worn's job, never the loader's.
    legacy = dict(saved)
    legacy.pop("worn")
    assert "worn" not in _loadout_from_dict({"rolled_loadout": legacy})


def test_worn_bonuses_read_the_catalog_fields():
    """Base-quality helper pins: the eyes carry +8 hit, the arms +2
    melee (the bonus fields go live on the wearer, SETTLED 27)."""
    stamp = {"worn": [["armor", "cybernetic_eyes", 0],
                      ["armor", "cybernetic_arms", 0]]}
    assert ground_loadout.worn_bonuses(stamp) == (8, 2)
    assert ground_loadout.worn_bonuses({}) == (0, 0)


def test_executor_instance_folds_every_bonus_field():
    from src.spacehack import ground_scale
    from src.spacehack.combat import _rules_ground
    from src.spacehack.ground_equipment import (
        sum_armor_bonus, sum_armor_defense,
    )

    entity, game_map = _rung_entity("consortium_executor")
    instance = _rules_ground._build_enemy_instance(entity, game_map)
    worn = ground_loadout.worn_entries(instance.entity.rolled_loadout)
    stats = ground_scale.derive_stats(instance.spec, instance.band)
    assert instance.max_hp == (
        instance.spec.hp + stats.stamina // 3
        + sum_armor_bonus(worn, "hp_bonus")
    )
    assert instance.armor == (
        instance.spec.armor + sum_armor_defense(worn)
    )
    # The cyber legs' ap_bonus rides the shared modifier math.
    assert instance.ap_total >= instance.spec.ap + 1


def test_the_folded_armor_reaches_the_readers():
    """What they wear is what they are, on the card and in every
    math: the detail lines + the damage soak read the INSTANCE value."""
    from src.spacehack.combat import _ground_presentation, _rules_ground

    entity, game_map = _rung_entity("consortium_executor")
    instance = _rules_ground._build_enemy_instance(entity, game_map)
    assert instance.armor > instance.spec.armor  # the worn pieces count
    assert _ground_presentation.enemy_detail_lines(instance)[0] == (
        f"Armor {instance.armor}"
    )
    ctx = SimpleNamespace(
        ground_stats=SimpleNamespace(strength=20),
        equipped_ground_armor={},
    )
    _dmg, _ = _rules_ground.damage(
        "kinetic_pistol", instance, ctx, quality=0,
    )
    from src.spacehack.combat._ground_math import ground_damage_raw
    assert _dmg == ground_damage_raw(
        "kinetic_pistol", 20, instance.armor, quality=0,
    )


def test_scorer_and_resolution_share_the_worn_terms():
    """SETTLED 41's same-math rule: the eyes' +8 hit moves the volley
    scorer's EV and the shot resolution's chance IDENTICALLY — both
    read the one ``worn_bonuses`` helper."""
    from src.spacehack.combat._ai_ground import _score_ground_weapon
    from src.spacehack.combat._ground_math import (
        ground_hit_chance_raw, ground_point_blank_penalty,
    )
    from src.spacehack.data.ground_weapons import find_ground_weapon

    ws = find_ground_weapon("kinetic_pistol")
    stats = SimpleNamespace(reflexes=30, strength=20)
    ctx = SimpleNamespace(ground_stats=SimpleNamespace(reflexes=30))
    plain = _score_ground_weapon(ws, 0, 4, stats, 0, 0, ctx)
    worn = _score_ground_weapon(ws, 0, 4, stats, 0, 0, ctx, (8, 2))
    _chance_plain = ground_hit_chance_raw(
        ws.id, 30, 30, range_penalty=ground_point_blank_penalty(ws.id, 4),
    )
    _chance_worn = ground_hit_chance_raw(
        ws.id, 30, 30, hit_bonus=8,
        range_penalty=ground_point_blank_penalty(ws.id, 4),
    )
    # The EV ratio is exactly the hit-chance ratio (damage untouched:
    # a pistol is ranged, the melee bonus never applies).
    assert abs(worn / plain - _chance_worn / _chance_plain) < 1e-9


def test_kit_drop_carries_the_worn_pieces_at_stamped_qualities():
    from src.spacehack.combat._actions import spawn_kill_drops

    entity, game_map = _rung_entity("consortium_executor")
    spec = find_npc_char("consortium_executor")
    stamp = ground_loadout.ensure_loadout(entity, game_map)
    loot_map = world.GameMap(
        width=2, height=2,
        tiles=[[world.DUNGEON_FLOOR for _ in range(2)] for _ in range(2)],
        entities=[],
    )
    spawn_kill_drops(
        loot_map, world.Position(0, 0), spec, SimpleNamespace(), stamp,
    )
    payloads = [
        e.loot_data for e in loot_map.entities
        if e.loot_data is not None
    ]
    for entry in stamp["worn"]:
        assert {
            "item_type": "armor", "item_id": entry[1], "quality": entry[2],
        } in payloads, entry


# --- boarded-hunter decks + survey_a (SETTLED 51 exposure surfaces) ----------

def _load_crew_deck(layout_id, faction, seed):
    from src.spacehack import engine
    from src.spacehack.dungeon import load_layout

    engine.RNG.seed(seed)
    game_map, _spawn = load_layout(
        layout_id, crew_faction=faction, loot_budget=None,
    )
    return [e.npc_char_id for e in game_map.entities if e.npc_char_id]


def test_crew_roles_heavy_is_the_executor():
    from src.spacehack.data.npc_chars.crew_roles import CREW_ROLES

    assert CREW_ROLES["consortium"]["heavy"] == "consortium_executor"
    assert CREW_ROLES["consortium"]["line"] == "consortium_enforcer"
    assert CREW_ROLES["consortium"]["marksman"] == "consortium_gunner"


def _consortium_table_ids() -> set:
    """The consortium crew table's own id set — the legal crew set a
    boarded hunter deck may field, derived (never hand-copied)."""
    from src.spacehack.data.npc_chars.crew_roles import CREW_ROLES

    return set(CREW_ROLES["consortium"].values())


def test_boarded_dreadnought_guarantees_its_executor():
    """frigate_crew's heavy marker is certain (@1.0) — every boarded
    Dreadnought fields its bold-E rung (SETTLED 51)."""
    _legal = _consortium_table_ids()
    for seed in (1, 7, 42, 909, 31337):
        crew = _load_crew_deck("frigate_crew", "consortium", seed)
        assert "consortium_executor" in crew, seed
        assert set(crew) <= _legal, seed


def test_boarded_hunter_carries_the_chance_slot_executor():
    """cruiser_crew's heavy marker is the shared CHANCE slot (@0.4) —
    the geometry stands, the EXPECTATION bends (the brief's
    ADVISE-folded ruling): some boarded Hunters carry an Executor,
    none carries anything outside the consortium table."""
    _legal = _consortium_table_ids()
    _seen_executor = False
    for seed in range(40):
        crew = _load_crew_deck("cruiser_crew", "consortium", seed)
        assert set(crew) <= _legal, seed
        _seen_executor = _seen_executor or "consortium_executor" in crew
    assert _seen_executor, "the 0.4 chance slot must fire sometimes"


def test_survey_a_fields_the_high_rung():
    from src.spacehack import engine
    from src.spacehack.dungeon import load_layout

    engine.RNG.seed(5)
    game_map, _spawn = load_layout("survey_a", loot_budget=None)
    enemies = [e.npc_char_id for e in game_map.entities if e.npc_char_id]
    assert "consortium_executor" in enemies  # the @1.0 S slots
    assert {"consortium_enforcer", "consortium_gunner"} <= set(enemies)


# --- the hunt reskin (SETTLED 50/54) ----------------------------------------

class _HuntLog:
    def __init__(self):
        self.lines: list[str] = []

    def add(self, line):
        self.lines.append(line)

    def add_colored(self, line, _color, **_kw):
        self.lines.append(line)


def _hunt_ctx():
    return SimpleNamespace(log=_HuntLog(), procedural_spawns={})


def _hunt_map():
    return world.GameMap(
        width=40, height=20,
        tiles=[[world.DUNGEON_FLOOR for _ in range(40)] for _ in range(20)],
        entities=[],
    )


def _hunt_call(seed):
    from src.spacehack import engine, npc_ships

    engine.RNG.seed(seed)
    ctx = _hunt_ctx()
    game_map = _hunt_map()
    system = SimpleNamespace(
        width=40, height=20,
        planets=[], jump_points=[], stations=[], npc_density=3,
    )
    spawned = npc_ships._spawn_consortium_squad(
        ctx, game_map, "tau_ceti", system, [(10, 10, "planet", "X")],
    )
    return ctx, game_map, spawned


def test_hunt_squads_are_hunters_only():
    """SETTLED 50: 2-3 pursuit cruisers — the hauler front and pirate
    tag-alongs are gone; nothing else spawns."""
    for seed in range(30):
        ctx, game_map, spawned = _hunt_call(seed)
        assert spawned is True, seed
        rows = ctx.procedural_spawns["tau_ceti"]
        assert 2 <= len(rows) <= 3, seed
        assert all(r.npc_id == "consortium_hunter" for r in rows), seed
        ship_ids = {e.npc_ship_id for e in game_map.entities}
        assert ship_ids == {"consortium_hunter"}, seed
        assert not any(
            "hauler" in line or "pirate" in line for line in ctx.log.lines
        ), seed


def test_hunt_ping_line_is_verbatim():
    """SETTLED 54: the sensor-ping line lands VERBATIM, N = ships."""
    for seed in range(12):
        ctx, _map, _spawned = _hunt_call(seed)
        _n = len(ctx.procedural_spawns["tau_ceti"])
        assert ctx.log.lines == [
            f"Sensor ping: consortium hunters detected - {_n} ships closing.",
        ], seed


def test_heat_aggro_keys_on_consortium_not_pirate(monkeypatch):
    """SETTLED 50: ambient pirates go back to ambient during heat;
    the HUNTERS chase while heat is live and stop at expiry."""
    from src.spacehack import main_quest, npc_ships

    system = SimpleNamespace(id="tau_ceti")
    pirate = SimpleNamespace(npc_ship_id="pirate_scout")
    hunter = SimpleNamespace(npc_ship_id="consortium_hunter")

    monkeypatch.setattr(main_quest, "consortium_heat_active", lambda _c: True)
    monkeypatch.setattr(main_quest, "charged_cell_in_sol", lambda *_a: False)
    assert npc_ships._squad_aggro(None, system, hunter) is True
    assert npc_ships._squad_aggro(None, system, pirate) is False  # retired

    monkeypatch.setattr(main_quest, "consortium_heat_active", lambda _c: False)
    assert npc_ships._squad_aggro(None, system, hunter) is False  # expiry


def test_q6_guard_is_the_anchor_plus_two_hunters():
    """SETTLED 50: the guarded wreck's set-piece — bold-F anchor +
    1-2 pursuit escorts (landed as the tuple's 2, the existing
    shape), one squad group."""
    from src.spacehack.data.main_quest import find_main_quest_step
    from src.spacehack.main_quest import _spawns

    step = find_main_quest_step("mer_q6_survey")
    assert step.bounty_enemy_id == "consortium_dreadnought"
    assert step.bounty_escort_ids == ("consortium_hunter", "consortium_hunter")
    system = SimpleNamespace(width=40, height=20)
    leader = _spawns._quest_leader_spawn(step, world.Position(10, 10))
    escorts = _spawns._quest_escort_spawns(step, system, world.Position(10, 10))
    assert leader.enemy_id == "consortium_dreadnought"
    assert [e.enemy_id for e in escorts] == ["consortium_hunter"] * 2
    assert all(e.squad_group_id == leader.spawn_id for e in escorts)


def test_silent_leader_spec_never_auto_hails():
    """The hunt ships author silence (comms_lines=()): the q6 anchor
    never opens a contentless ``...`` hail — talkative leaders (the
    chains' pirate-captain bounties) keep the range-12 hail (doc 48
    SETTLED 50 review fold)."""
    from src.spacehack.data.main_quest import find_main_quest_step
    from src.spacehack.main_quest import _spawns

    silent = _spawns._quest_leader_spawn(
        find_main_quest_step("mer_q6_survey"), world.Position(1, 1),
    )
    assert silent.comms_warning_range == 0

    talkative = _spawns._quest_leader_spawn(
        find_main_quest_step("lab_q5_frequency"), world.Position(1, 1),
    )
    assert talkative.comms_warning_range == 12
