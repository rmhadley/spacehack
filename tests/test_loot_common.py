"""Loot category colours + spawn-path behaviour (doc 47 phase 1)."""

import pytest

from types import SimpleNamespace

from spacehack.ground_equipment import StoredGroundEquipment
from spacehack.world import DUNGEON_FLOOR, Entity, GameMap, Position
from spacehack.loot_common import (
    CARGO_FG,
    DATA_FG,
    EQUIPMENT_FG,
    FIELD_ITEM_FG,
    MISSION_FG,
    loot_fg,
)


def _make_map(width: int, height: int) -> GameMap:
    """Build a map filled with floor tiles."""
    tiles = [[DUNGEON_FLOOR for _ in range(width)] for _ in range(height)]
    return GameMap(width=width, height=height, tiles=tiles, entities=[])


def _loot(payload, **attrs):
    entity = Entity(
        char="%", fg=CARGO_FG, pos=Position(0, 0),
        loot_data=payload,
    )
    for name, value in attrs.items():
        setattr(entity, name, value)
    return entity


class TestLootFg:
    """Hue answers content, never source (SETTLED 5)."""

    @pytest.mark.parametrize("payload, expected", [
        ({"good_id": "scrap_metal", "quantity": 2}, CARGO_FG),
        ({"item_type": "weapon", "item_id": "kinetic_pistol"}, EQUIPMENT_FG),
        ({"item_type": "armor", "item_id": "light_helmet"}, EQUIPMENT_FG),
        ({"item_type": "ammo", "item_id": "pistol_rounds", "quantity": 5}, FIELD_ITEM_FG),
        ({"item_type": "consumable", "item_id": "med_pack", "quantity": 1}, FIELD_ITEM_FG),
        ({"teaches": "dark_berth_1"}, DATA_FG),
        ({"reveals_site": True}, DATA_FG),
        ({"goods": [("scrap_metal", 1)]}, DATA_FG),
        (None, CARGO_FG),
        ({"unknown_shape": 1}, CARGO_FG),
    ])
    def test_category_colours(self, payload, expected):
        assert loot_fg(payload) == expected

    def test_mission_flag_wins(self):
        assert loot_fg({"good_id": "electronics", "quantity": 1}, mission=True) == MISSION_FG


class TestNoSilentEviction:
    """Spawning loot NEVER deletes existing loot (cap removed
    2026-09-23 — the perf pass removed the need, and the old cap
    silently ate a floor-placed legendary when a guard squad's drops
    pushed the map over the limit)."""

    def test_space_debris_spawns_never_evict_placed_loot(self):
        from spacehack.combat import _actions
        from types import SimpleNamespace

        gm = _make_map(3, 3)
        legendary = _loot({
            "item_type": "module", "item_id": "shield_mk1",
            "quality": 4, "randart_seed": 4242,
        })
        gm.entities.append(legendary)
        spec = SimpleNamespace(cargo_goods=("scrap_metal",))
        for _ in range(40):
            _actions._spawn_loot_drops(gm, Position(1, 1), spec)

        loot = [e for e in gm.entities if e.loot_data is not None]
        assert len(loot) > 30          # no cap: debris keeps piling up
        assert any(e is legendary for e in gm.entities)

    def test_ground_kills_never_evict_placed_loot(self):
        from spacehack.combat._actions import spawn_kill_drops
        from types import SimpleNamespace

        gm = _make_map(3, 3)
        early = _loot({"good_id": "electronics", "quantity": 1})
        gm.entities.append(early)
        spec = SimpleNamespace(
            loot_pool=("scrap_metal",), loot_count=(1, 1),
            equipment_loot_pool=(), field_item_loot_pool=(),
            field_item_loot_count=(0, 0), tier=1, id="rock_scavenger",
            xp_reward=10,
        )
        for _ in range(40):
            spawn_kill_drops(gm, Position(1, 1), spec, SimpleNamespace(known_rumors=set()))

        assert any(e is early for e in gm.entities)
        assert len([e for e in gm.entities if e.loot_data is not None]) > 30


class TestConstructorRouting:
    """Every spawn path routes its payload through loot_fg."""

    def test_ground_kill_spawns_carry_category_colours(self):
        from spacehack.combat import _actions

        gm = _make_map(3, 3)
        pos = Position(1, 1)
        _actions._spawn_loot_at_position(gm, pos, ("scrap_metal",), count_range=(2, 2))
        _actions._spawn_field_item_loot_at_position(
            gm, pos, (("ammo", "pistol_rounds"),), count_range=(1, 1),
        )
        # The equipment-extras channel retired (doc 48 SETTLED 56);
        # equipment payloads still route through loot_fg via the kit
        # drop's worn/weapon pieces.
        _actions._spawn_kit_drop(
            gm, pos, {"worn": [["armor", "light_helmet", 0]]},
        )

        by_payload = {
            e.loot_data.get("item_type", "cargo"): (e.fg, e.loot_data)
            for e in gm.entities if e.loot_data is not None
        }
        assert by_payload["cargo"][0] == CARGO_FG
        assert by_payload["ammo"][0] == FIELD_ITEM_FG
        # Equipment colour routes through loot_fg at whatever tier the
        # drop rolled (the equipment hue or its brightened steps).
        _weapon_fg, _weapon_payload = by_payload["armor"]
        assert _weapon_fg == loot_fg(_weapon_payload)
        assert _weapon_fg == EQUIPMENT_FG or _weapon_payload.get("quality", 0) > 0

    def test_pad_entity_is_data_coloured(self):
        from spacehack.loot import spawn_pad_entity

        gm = _make_map(1, 1)
        assert spawn_pad_entity(gm, Position(0, 0), {"teaches": "some_rumor"})
        assert gm.entities[0].fg == DATA_FG

class TestSaveLoadColourRoundTrip:
    """The restore path is the colour authority for non-dungeon maps
    (fg is not serialized) — it must rebuild through loot_fg."""

    def test_restore_rebuilds_category_colours_and_mission_cyan(self):
        from spacehack.saveload import _restore_loot_entities, _save_loot

        saved = _make_map(1, 1)
        _plain = _loot({"good_id": "scrap_metal", "quantity": 1})
        _ammo = _loot({"item_type": "ammo", "item_id": "pistol_rounds", "quantity": 3})
        _heist = _loot({"good_id": "fuel_cells", "quantity": 1})
        _heist.heist_mission = True
        saved.entities.extend((_plain, _ammo, _heist))
        data = {"map_loot": _save_loot(saved)}

        restored = _make_map(1, 1)
        _restore_loot_entities(data, restored)

        colours = sorted(e.fg for e in restored.entities)
        assert colours == sorted([CARGO_FG, FIELD_ITEM_FG, MISSION_FG])


class TestGroundKillDrops:
    """The extracted ground drop sequence keeps pool behavior
    (doc 47.1 step 2)."""

    @pytest.fixture(autouse=True)
    def _no_tinker_kit(self, monkeypatch):
        """Kill-drop tests isolate the kit roll (kit tests force it)."""
        from spacehack.data import quality

        monkeypatch.setattr(quality, "KIT_KILL_RATE", 10**9)

    def _spec(self, **overrides):
        from types import SimpleNamespace

        spec = SimpleNamespace(
            loot_pool=("scrap_metal",), loot_count=(1, 1),            field_item_loot_pool=(("ammo", "pistol_rounds"),),
            field_item_loot_count=(1, 1), tier=1, id="rock_scavenger",
            xp_reward=10,
        )
        for key, value in overrides.items():
            setattr(spec, key, value)
        return spec

    def test_spawns_all_pool_kinds(self):
        from spacehack.combat._actions import spawn_kill_drops
        from spacehack.engine import RNG
        from types import SimpleNamespace

        # Both counts are (1, 1): deterministic on the first kill —
        # goods + field items (the equipment-extras channel retired,
        # doc 48 SETTLED 56).
        RNG.seed(4747)
        gm = _make_map(1, 1)
        spawn_kill_drops(gm, Position(0, 0), self._spec(), SimpleNamespace())
        kinds = {
            e.loot_data.get("item_type", "cargo")
            for e in gm.entities if e.loot_data is not None
        }
        assert kinds == {"cargo", "ammo"}

    def test_pad_door_receives_the_spec_id(self, monkeypatch):
        import spacehack.digs as digs
        from spacehack.combat._actions import spawn_kill_drops
        from types import SimpleNamespace

        seen = []

        def _record(ctx, game_map, pos, spec_id):
            seen.append(spec_id)
            return False

        monkeypatch.setattr(digs, "maybe_spawn_ground_pad", _record)
        spec = self._spec(id="pirate_raider")
        spawn_kill_drops(_make_map(1, 1), Position(0, 0), spec, SimpleNamespace())
        assert seen == ["pirate_raider"]

    def _bare_spec(self):
        """A spec whose every pool is empty — only the kit drop fires."""
        return self._spec(
            loot_pool=(), equipment_loot_pool=(), field_item_loot_pool=(),
        )

    def _loadout(self, ranged=None, melee=None, pool=None):
        from tests.support.ground_pins import pinned_loadout

        return pinned_loadout(ranged, melee, pool=pool or [])

    def test_kit_drop_spawns_both_weapons_and_the_pool_remainder(self):
        """SETTLED 43: BOTH carried set weapons fall at their stamped
        qualities and the ammo stack is the carried pool's REMAINDER —
        deterministic, the death-time roll retired."""
        from spacehack.combat._actions import spawn_kill_drops
        from types import SimpleNamespace

        gm = _make_map(1, 1)
        spawn_kill_drops(
            gm, Position(0, 0), self._bare_spec(), SimpleNamespace(),
            self._loadout(("kinetic_rifle", 2), ("combat_knife", 1),
                          pool=[["ammo", "rifle_rounds", 3]]),
        )
        payloads = [e.loot_data for e in gm.entities if e.loot_data is not None]
        assert {
            "item_type": "weapon", "item_id": "kinetic_rifle", "quality": 2,
        } in payloads
        assert {
            "item_type": "weapon", "item_id": "combat_knife", "quality": 1,
        } in payloads
        ammo = [p for p in payloads if p.get("item_type") == "ammo"]
        assert ammo == [{"item_type": "ammo", "item_id": "rifle_rounds",
                         "quantity": 3}]  # remainder, never a roll

    def test_kit_drop_carries_the_rolled_quality_without_reroll(self):
        from spacehack.combat._actions import spawn_kill_drops
        from types import SimpleNamespace

        gm = _make_map(1, 1)
        spawn_kill_drops(
            gm, Position(0, 0), self._bare_spec(), SimpleNamespace(),
            self._loadout(("kinetic_pistol", 2)),
        )
        payloads = [e.loot_data for e in gm.entities if e.loot_data is not None]
        weapon = next(p for p in payloads if p.get("item_type") == "weapon")
        assert weapon == {
            "item_type": "weapon", "item_id": "kinetic_pistol", "quality": 2,
        }
        # Base-tier drops keep the legacy payload shape (no quality key).
        gm2 = _make_map(1, 1)
        spawn_kill_drops(
            gm2, Position(0, 0), self._bare_spec(), SimpleNamespace(),
            self._loadout(("kinetic_pistol", 0)),
        )
        base = next(
            e.loot_data for e in gm2.entities
            if e.loot_data.get("item_type") == "weapon"
        )
        assert "quality" not in base

    def test_kit_drop_dedupes_a_weapon_held_in_both_slots(self):
        """The raider corner: the melee family can roll the SAME id
        into both slots — one knife drops, not two."""
        from spacehack.combat._actions import spawn_kill_drops
        from types import SimpleNamespace

        gm = _make_map(1, 1)
        spawn_kill_drops(
            gm, Position(0, 0), self._bare_spec(), SimpleNamespace(),
            self._loadout(("combat_knife", 0), ("combat_knife", 1)),
        )
        knives = [
            e.loot_data for e in gm.entities
            if e.loot_data is not None
            and e.loot_data.get("item_id") == "combat_knife"
        ]
        assert len(knives) == 1

    def test_kit_drop_spent_pool_drops_no_ammo(self):
        """A bled-out fighter (pool spent to 0) drops weapons only —
        what drops reflects the fight."""
        from spacehack.combat._actions import spawn_kill_drops
        from types import SimpleNamespace

        gm = _make_map(1, 1)
        spawn_kill_drops(
            gm, Position(0, 0), self._bare_spec(), SimpleNamespace(),
            self._loadout(("kinetic_pistol", 0),
                          pool=[["ammo", "pistol_rounds", 0]]),
        )
        payloads = [e.loot_data for e in gm.entities if e.loot_data is not None]
        assert [p for p in payloads if p.get("item_type") == "ammo"] == []

    def test_kit_drop_skips_organic_and_unknown_weapons(self):
        from spacehack.combat._actions import spawn_kill_drops
        from types import SimpleNamespace

        for weapon_id in ("monster_claws", "fists", "does_not_exist"):
            gm = _make_map(1, 1)
            # Raw stamp (the pin builder needs a catalog id): the kit
            # drop must skip organic, unwieldable, and unknown ids.
            stamp = {"ranged": [weapon_id, 0], "melee": None,
                     "loaded": {}, "pool": [], "active": "ranged"}
            spawn_kill_drops(
                gm, Position(0, 0), self._bare_spec(), SimpleNamespace(),
                stamp,
            )
            assert [e for e in gm.entities if e.loot_data is not None] == []

    def test_the_authored_ammo_entries_death_roll_retires_with_a_loadout(self):
        """The authored field-pool ammo entries feeding a CARRIED ammo
        type never death-roll — the kit drop's remainder is the one
        source (no double-ammo), fought-dry included."""
        from spacehack.combat._actions import spawn_kill_drops
        from types import SimpleNamespace

        spec = self._spec(field_item_loot_pool=(
            ("ammo", "rifle_rounds"), ("consumable", "med_pack"),
        ), field_item_loot_count=(1, 1))
        gm = _make_map(1, 1)
        spawn_kill_drops(
            gm, Position(0, 0), spec, SimpleNamespace(),
            self._loadout(("kinetic_rifle", 0),
                          pool=[["ammo", "rifle_rounds", 2]]),
            carried=[["consumable", "med_pack", 1]],
        )
        ammo = [
            e.loot_data for e in gm.entities
            if e.loot_data is not None
            and e.loot_data.get("item_type") == "ammo"
        ]
        assert ammo == [{"item_type": "ammo", "item_id": "rifle_rounds",
                         "quantity": 2}]  # the remainder only

    def test_fought_dry_still_retires_the_authored_ammo_entry(self):
        """A bled-out fighter (pool spent to 0) drops NO rounds and the
        authored entry does not re-roll them: carried replaces rolled,
        even empty — what drops reflects the fight."""
        from spacehack.combat._actions import spawn_kill_drops
        from types import SimpleNamespace

        spec = self._spec(field_item_loot_pool=(
            ("ammo", "rifle_rounds"),
        ), field_item_loot_count=(1, 1))
        gm = _make_map(1, 1)
        spawn_kill_drops(
            gm, Position(0, 0), spec, SimpleNamespace(),
            self._loadout(("kinetic_rifle", 0),
                          pool=[["ammo", "rifle_rounds", 0]]),
        )
        assert [
            e.loot_data for e in gm.entities
            if e.loot_data is not None
            and e.loot_data.get("item_type") == "ammo"
        ] == []

    def test_the_machines_authored_ammo_keeps_rolling(self):
        """Organic-weapon rows (the drones' authored energy cells) keep
        their death-time ammo roll — no carried weapon feeds it, the
        channel is ordinary pool loot (the review catch: a blanket
        retirement deleted it)."""
        from spacehack.combat._actions import spawn_kill_drops
        from types import SimpleNamespace
        from spacehack.data.ground_weapons import find_ground_weapon

        assert find_ground_weapon("drone_laser").ammo_capacity == -1
        spec = self._spec(field_item_loot_pool=(
            ("ammo", "energy_cells"),
        ), field_item_loot_count=(1, 1))
        gm = _make_map(1, 1)
        spawn_kill_drops(
            gm, Position(0, 0), spec, SimpleNamespace(),
            self._loadout(("drone_laser", 0)),  # not ammo-fed: no pool
        )
        ammo = [
            e.loot_data for e in gm.entities
            if e.loot_data is not None
            and e.loot_data.get("item_type") == "ammo"
        ]
        assert ammo and ammo[0]["item_id"] == "energy_cells"

    def test_tinker_kit_kill_roll_spawns_one_qty1_stack(self, monkeypatch):
        from spacehack.combat._actions import spawn_kill_drops
        from spacehack.data import quality
        from spacehack.ground_consumables import kit_drop_payload
        from types import SimpleNamespace

        monkeypatch.setattr(quality, "KIT_KILL_RATE", 1)
        gm = _make_map(1, 1)
        spawn_kill_drops(gm, Position(0, 0), self._bare_spec(), SimpleNamespace())
        payloads = [e.loot_data for e in gm.entities if e.loot_data is not None]
        assert payloads.count(kit_drop_payload()) == 1

    def test_space_debris_never_produces_tinker_kits(self):
        from spacehack.combat._actions import _spawn_loot_drops
        from spacehack.engine import RNG
        from types import SimpleNamespace

        RNG.seed(97531)
        gm = _make_map(3, 3)
        spec = SimpleNamespace(cargo_goods=("scrap_metal", "fuel_cells"))
        for _ in range(12):
            _spawn_loot_drops(gm, Position(1, 1), spec)
        payloads = [e.loot_data for e in gm.entities if e.loot_data is not None]
        assert payloads
        assert all("item_type" not in p for p in payloads)

    def test_organic_weapons_are_authored_not_droppable(self):
        from spacehack.data.ground_weapons import find_ground_weapon

        organic = (
            "monster_claws", "drone_laser", "frost_bolt",
            "parasite_mandibles", "fists",
        )
        for weapon_id in organic:
            assert find_ground_weapon(weapon_id).loot_droppable is False
        assert find_ground_weapon("kinetic_pistol").loot_droppable is True

    def test_on_kill_forwards_the_two_set_loadout(self, monkeypatch):
        from tests.support.asyncutil import run, as_async
        from spacehack.combat import _actions, _rules_ground
        from spacehack import xp as xp_module
        from types import SimpleNamespace

        seen = []
        monkeypatch.setattr(
            _actions, "spawn_kill_drops",
            lambda *args, **kwargs: seen.append(kwargs),
        )
        monkeypatch.setattr(xp_module, "add_xp", as_async(lambda *a, **k: None))

        ent = Entity(
            char="r", fg=(255, 255, 255), pos=Position(0, 0), name="raider",
        )
        ent.rolled_loadout = self._loadout(("kinetic_pistol", 2))
        gm = _make_map(1, 1)
        gm.entities.append(ent)
        enemy = _rules_ground.GroundEnemyInstance(
            entity=ent, spec=self._bare_spec(), weapon_id="kinetic_pistol",
            weapon_quality=2,
        )
        run(_rules_ground.on_kill(gm, enemy, SimpleNamespace()))
        # The entity's two-set stamp forwards — the corpse drops BOTH
        # carried weapons at their stamped tiers, no re-roll (47.2/43).
        assert seen and seen[0]["loadout"] is ent.rolled_loadout


def test_tinker_kit_rates_pin_the_briefs_opening_guesses():
    """The rates are playtest-tunable data — the pins make every
    retune a deliberate test edit, never a silent drift. Module
    scope: the kill-drop class's autouse fixture forces the rate."""
    from spacehack.data import quality

    assert quality.KIT_KILL_RATE == 40
    assert quality.KIT_WRECK_RATE == 12
    assert quality.KIT_DIG_RATE == 16


class TestDerelictSaySo:
    """Leaving a loot-laden one-shot derelict confirms first (47.1.5)."""

    def _derelict_map(self, with_loot: bool = True) -> GameMap:
        gm = _make_map(2, 2)
        gm.derelict_interior = True
        if with_loot:
            gm.entities.append(
                _loot({"good_id": "scrap_metal", "quantity": 1})
            )
        return gm

    def _run_exit(self, monkeypatch, game_map, confirm_result):
        from tests.support.asyncutil import run
        import spacehack.game_flow as game_flow
        from types import SimpleNamespace

        asks = []
        leaves = []

        async def _confirm(ctx):
            asks.append(True)
            return confirm_result

        async def _leave(*args, **kwargs):
            leaves.append(True)
            return None

        monkeypatch.setattr(game_flow, "_confirm_abandon_derelict", _confirm)
        monkeypatch.setattr(game_flow, "_leave_dungeon_to_space", _leave)
        result = run(game_flow._handle_dungeon_exit(
            SimpleNamespace(), game_map, None, None, None, [], [],
        ))
        return result, asks, leaves

    def test_loot_laden_derelict_asks_and_leave_proceeds(self, monkeypatch):
        _result, asks, leaves = self._run_exit(
            monkeypatch, self._derelict_map(), confirm_result=True,
        )
        assert asks == [True]
        assert leaves == [True]

    def test_stay_aborts_before_the_transition(self, monkeypatch):
        _result, asks, leaves = self._run_exit(
            monkeypatch, self._derelict_map(), confirm_result=False,
        )
        assert asks == [True]
        assert leaves == []

    def test_clean_derelict_and_cached_dungeons_never_ask(self, monkeypatch):
        _r, asks, leaves = self._run_exit(
            monkeypatch, self._derelict_map(with_loot=False), True,
        )
        assert asks == []
        assert leaves == [True]

        gm_cached = _make_map(2, 2)
        gm_cached.entities.append(
            _loot({"good_id": "scrap_metal", "quantity": 1})
        )
        _r, asks, leaves = self._run_exit(monkeypatch, gm_cached, True)
        assert asks == []
        assert leaves == [True]

    def test_confirm_uses_the_approved_strings(self, monkeypatch):
        from tests.support.asyncutil import run, as_async
        import spacehack.game_flow as game_flow
        from types import SimpleNamespace

        captured = {}
        monkeypatch.setattr(
            game_flow,
            "_run_pygame_dungeon_confirm",
            as_async(lambda ctx, **kw: captured.update(kw) or "CONFIRM"),
        )
        assert run(game_flow._confirm_abandon_derelict(SimpleNamespace()))
        assert captured == {
            "title": "ABANDON THE SHIP?",
            "body": "This ship won't survive a second breach, anything "
            "left behind is gone.",
            "accept_label": "Leave",
            "cancel_label": "Stay",
            "caption": "spacehack - abandon ship",
        }

    def test_generic_derelict_constructor_stamps_the_flag(self):
        from types import SimpleNamespace
        from spacehack.boarding_wrecks import _build_generic_derelict

        ctx = SimpleNamespace(game_map=SimpleNamespace(entities=[]))
        npcspec = SimpleNamespace(
            loot_budget=(50, 100), id="scout_wreck", security_drones=1.0,
        )
        dungeon_map, _spawn, handled = _build_generic_derelict(
            ctx, object(), npcspec, SimpleNamespace(add=lambda _m: None),
        )
        assert handled is False
        assert dungeon_map.derelict_interior is True

    def test_derelict_stamp_survives_save_load(self):
        from spacehack import saveload_maps

        gm = _make_map(2, 2)
        gm.derelict_interior = True
        dd = saveload_maps._dungeon_to_dict(gm, None)
        assert dd["derelict_interior"] is True
        restored, _pos = saveload_maps._dungeon_from_dict(dd)
        assert restored.derelict_interior is True


class TestDropTimeQualityRolls:
    """Wreck rooms and dig caches roll tiers at drop time; pickup and
    pack-drops keep the rolled tier (doc 47.2 — the kill-extras half
    retired with the channel, doc 48 SETTLED 56)."""

    class _ScriptRng:
        """Serves scripted rolls; choice picks by list order."""

        def __init__(self, values):
            self._values = list(values)

        def randint(self, low, high):
            value = self._values.pop(0)
            assert low <= value <= high, (value, low, high)
            return value

        def choice(self, seq):
            self._values.pop(0)
            return seq[0]

    def test_wreck_room_equipment_rolls_presence_then_quality(self, monkeypatch):
        from spacehack import dungeon_layout, engine

        build = SimpleNamespace(
            entities=[], loot_markers=[("personal_storage", 1, 1)],
        )
        monkeypatch.setattr(
            dungeon_layout, "_room_cells_for_marker", lambda build, m: [(2, 2)],
        )
        # presence 1-in-3 hit; cell pick; pool choice consumes one;
        # WRECK ladder: t3 miss, t2 hit -> tier 2.
        rng = self._ScriptRng([1, 0, 2, 2, 1, 2])
        monkeypatch.setattr(engine, "RNG", rng)
        dungeon_layout._scatter_room_equipment(build)
        (entity,) = build.entities
        assert entity.loot_data == {
            "item_type": "weapon", "item_id": "kinetic_pistol",
            "quality": 2,
        }

    def test_wreck_room_equipment_presence_miss_spawns_nothing(self, monkeypatch):
        from spacehack import dungeon_layout, engine

        build = SimpleNamespace(
            entities=[], loot_markers=[("personal_storage", 1, 1)],
        )
        rng = self._ScriptRng([2])  # pool present; presence roll misses
        monkeypatch.setattr(engine, "RNG", rng)
        dungeon_layout._scatter_room_equipment(build)
        assert build.entities == []
        assert rng._values == []

    def test_dig_cache_payload_gear_and_goods_branches(self, monkeypatch):
        from spacehack import digs

        spec = SimpleNamespace(mission_tier=2, produces=(("ore_processed", 5),))
        # [lockbox miss, presence miss, off-world miss] -> the row's good.
        rng = self._ScriptRng([2, 2, 2])
        monkeypatch.setattr(digs, "engine", SimpleNamespace(RNG=rng))
        assert digs._dig_cache_payload(spec, ("ore_processed", 3)) == {
            "good_id": "ore_processed", "quantity": 3,
        }

        # [lockbox miss, presence hit] -> tier-2 gear.
        rng = self._ScriptRng([2, 1, 0, 1, 1, 1])
        monkeypatch.setattr(digs, "engine", SimpleNamespace(RNG=rng))
        payload = digs._dig_cache_payload(spec, ("ore_processed", 3))
        from spacehack.data.digs import TIER_EQUIPMENT_POOLS
        assert payload["item_type"] in {"weapon", "armor"}
        assert payload["item_id"] in {
            item for _, item in TIER_EQUIPMENT_POOLS[2]
        }
        assert payload.get("quality", 0) in {0, 1, 2, 3}

        # A lockbox hit returns the credit container instead.
        rng = self._ScriptRng([1, 500])
        monkeypatch.setattr(digs, "engine", SimpleNamespace(RNG=rng))
        assert digs._dig_cache_payload(spec, ("ore_processed", 3)) == {
            "credits": 500, "credits_kind": "lockbox",
        }

        # [lockbox miss, presence miss, off-world hit] -> a pool good
        # this planet does not produce (SETTLED 23).
        rng = self._ScriptRng([2, 2, 1, 0])
        monkeypatch.setattr(digs, "engine", SimpleNamespace(RNG=rng))
        payload = digs._dig_cache_payload(spec, ("ore_processed", 3))
        assert payload["quantity"] == 3
        from spacehack.data.digs import OUT_OF_PRODUCE_GOODS
        assert payload["good_id"] in {
            good for good in OUT_OF_PRODUCE_GOODS
            if good != "ore_processed"
        }

    def test_pickup_threads_quality_into_the_stored_entry(self):
        from spacehack import loot

        entity = SimpleNamespace(loot_data={
            "item_type": "weapon", "item_id": "smg", "quality": 2,
        })
        assert loot._ground_equipment_loot_entry(entity) == StoredGroundEquipment(
            "weapon", "smg", 2,
        )
        base = SimpleNamespace(loot_data={"item_type": "armor", "item_id": "light_vest"})
        assert loot._ground_equipment_loot_entry(base) == StoredGroundEquipment(
            "armor", "light_vest",
        )

    def test_pack_drop_writes_the_rolled_quality(self, monkeypatch):
        from spacehack import loot

        gm = _make_map(1, 1)
        ctx = SimpleNamespace(
            game_map=gm,
            ground_expedition_inventory=[
                StoredGroundEquipment("weapon", "smg", 3),
            ],
        )
        loot._drop_expedition_entry_at(ctx, Position(0, 0), 0)
        (entity,) = gm.entities
        assert entity.loot_data == {
            "item_type": "weapon", "item_id": "smg", "quality": 3,
        }
        assert ctx.ground_expedition_inventory == []


# --- credit containers (doc 47 phase 4) --------------------------------------


class _CreditsLog:
    def __init__(self) -> None:
        self.lines: list[str] = []

    def add(self, message: str, **_kwargs) -> None:
        self.lines.append(message)


def test_credits_payload_shape():
    from spacehack.loot_common import CREDIT_CHIP_KIND, LOCKBOX_KIND, credits_payload

    assert credits_payload(86, CREDIT_CHIP_KIND) == {
        "credits": 86, "credits_kind": "chip",
    }
    assert credits_payload(640, LOCKBOX_KIND) == {
        "credits": 640, "credits_kind": "lockbox",
    }


def test_loot_fg_credits_reads_the_gold_cargo_hue():
    from spacehack.loot_common import CARGO_FG, loot_fg

    assert loot_fg({"credits": 86, "credits_kind": "chip"}) == CARGO_FG
    assert loot_fg({"credits": 640, "credits_kind": "lockbox"}) == CARGO_FG


def test_credits_pickup_adds_credits_logs_and_consumes():
    from types import SimpleNamespace

    from tests.support.asyncutil import run
    from spacehack.loot import _open_single_loot_pickup

    entity = SimpleNamespace(
        loot_data={"credits": 86, "credits_kind": "chip"},
        pos=SimpleNamespace(x=1, y=1),
    )
    ctx = SimpleNamespace(
        log=_CreditsLog(), stats=SimpleNamespace(credits=100),
        game_map=SimpleNamespace(entities=[entity]),
        ground_expedition_inventory=[], ground_expedition_items=[],
        ship_storage=[], player_owned_ship=None,
    )

    run(_open_single_loot_pickup(ctx, entity))

    assert ctx.stats.credits == 186
    assert ctx.log.lines == ["Picked up a credit chip: 86$."]
    assert entity not in ctx.game_map.entities


def test_lockbox_pickup_line_reads_the_lockbox_wording():
    from types import SimpleNamespace

    from tests.support.asyncutil import run
    from spacehack.loot import _open_single_loot_pickup

    entity = SimpleNamespace(
        loot_data={"credits": 640, "credits_kind": "lockbox"},
        pos=SimpleNamespace(x=1, y=1),
    )
    ctx = SimpleNamespace(
        log=_CreditsLog(), stats=SimpleNamespace(credits=0),
        game_map=SimpleNamespace(entities=[entity]),
        ground_expedition_inventory=[], ground_expedition_items=[],
        ship_storage=[], player_owned_ship=None,
    )

    run(_open_single_loot_pickup(ctx, entity))

    assert ctx.stats.credits == 640
    assert ctx.log.lines == ["Opened a lockbox: 640$."]


def test_credits_chooser_labels_show_the_value_precommit():
    from types import SimpleNamespace

    from spacehack.loot import _loot_choice_label

    chip = SimpleNamespace(loot_data={"credits": 86, "credits_kind": "chip"})
    box = SimpleNamespace(loot_data={"credits": 640, "credits_kind": "lockbox"})
    assert _loot_choice_label(chip) == "Credit Chip (86$)"
    assert _loot_choice_label(box) == "Lockbox (640$)"


def test_credits_payload_round_trips_save_load():
    """A chip entity survives the map-loot save path with its gold hue
    recomputed on restore (the credits twin of the quality round-trip)."""
    from spacehack import saveload, world
    from spacehack.loot_common import CARGO_FG, credits_payload

    game_map = world.GameMap(width=2, height=1, tiles=[
        [world.DUNGEON_FLOOR, world.DUNGEON_FLOOR],
    ], entities=[])
    chip = world.Entity(
        char="%", fg=CARGO_FG, pos=world.Position(0, 0), name="Cache",
        loot_data=credits_payload(86, "chip"),
    )
    game_map.entities.append(chip)

    saved = saveload._save_loot(game_map)
    restored = world.GameMap(width=2, height=1, tiles=[
        [world.DUNGEON_FLOOR, world.DUNGEON_FLOOR],
    ], entities=[])
    saveload._restore_loot_entities({"map_loot": saved}, restored)

    (entity,) = restored.entities
    assert entity.loot_data == {"credits": 86, "credits_kind": "chip"}
    assert entity.fg == CARGO_FG
    assert (entity.pos.x, entity.pos.y) == (0, 0)
