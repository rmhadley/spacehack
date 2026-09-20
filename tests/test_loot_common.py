"""Loot category colours + the shared entity cap (doc 47 phase 1)."""

import pytest

from spacehack.world import DUNGEON_FLOOR, Entity, GameMap, Position
from spacehack.loot_common import (
    CARGO_FG,
    DATA_FG,
    EQUIPMENT_FG,
    FIELD_ITEM_FG,
    MISSION_FG,
    MAX_LOOT_ENTITIES,
    enforce_loot_cap,
    is_protected_loot,
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


class TestProtection:
    """Quest/pad/heist loot never answers to the cap."""

    def test_plain_cargo_is_not_protected(self):
        assert not is_protected_loot(_loot({"good_id": "scrap_metal", "quantity": 1}))

    def test_quest_cache_goods_manifest_is_protected(self):
        assert is_protected_loot(_loot({"goods": [("ore_processed", 3)]}))

    def test_step_id_marker_is_protected(self):
        entity = _loot({"good_id": "research_data", "quantity": 1})
        entity.main_quest_step_id = "mq_step_2"
        assert is_protected_loot(entity)

    def test_heist_marker_is_protected(self):
        entity = _loot({"good_id": "fuel_cells", "quantity": 1})
        entity.heist_mission = True
        assert is_protected_loot(entity)

    def test_pads_are_protected(self):
        assert is_protected_loot(_loot({"teaches": "some_rumor"}))
        assert is_protected_loot(_loot({"reveals_site": True}))

    def test_non_loot_entity_is_not_protected(self):
        assert not is_protected_loot(Entity(char="@", fg=(255, 255, 255), pos=Position(0, 0)))


class TestEnforceLootCap:
    """Oldest non-protected loot evicts beyond the cap, silently."""

    def test_under_cap_untouched(self):
        gm = _make_map(1, 1)
        keep = [_loot({"good_id": "scrap_metal", "quantity": 1}) for _ in range(5)]
        gm.entities.extend(keep)

        enforce_loot_cap(gm)

        assert gm.entities == keep

    def test_over_cap_evicts_oldest_first(self):
        gm = _make_map(1, 1)
        oldest = _loot({"good_id": "scrap_metal", "quantity": 1})
        newer = [_loot({"good_id": "electronics", "quantity": 1}) for _ in range(MAX_LOOT_ENTITIES)]
        gm.entities.append(oldest)
        gm.entities.extend(newer)

        enforce_loot_cap(gm)

        loot = [e for e in gm.entities if e.loot_data is not None]
        assert len(loot) == MAX_LOOT_ENTITIES
        assert oldest not in loot

    def test_protected_loot_survives_regardless_of_age(self):
        gm = _make_map(1, 1)
        ancient_pad = _loot({"teaches": "some_rumor"})
        fillers = [_loot({"good_id": "scrap_metal", "quantity": 1}) for _ in range(MAX_LOOT_ENTITIES)]
        gm.entities.append(ancient_pad)
        gm.entities.extend(fillers)

        enforce_loot_cap(gm)

        loot = [e for e in gm.entities if e.loot_data is not None]
        assert ancient_pad in loot
        assert len(loot) == MAX_LOOT_ENTITIES

    def test_non_loot_entities_never_counted_or_evicted(self):
        gm = _make_map(1, 1)
        npc = Entity(char="N", fg=(255, 255, 255), pos=Position(0, 0))
        gm.entities.append(npc)
        gm.entities.extend(
            _loot({"good_id": "scrap_metal", "quantity": 1})
            for _ in range(MAX_LOOT_ENTITIES + 3)
        )

        enforce_loot_cap(gm)

        assert npc in gm.entities
        loot = [e for e in gm.entities if e.loot_data is not None]
        assert len(loot) == MAX_LOOT_ENTITIES


class TestConstructorRouting:
    """Every spawn path routes its payload through loot_fg."""

    def test_ground_kill_spawns_carry_category_colours(self):
        from spacehack.combat import _actions

        gm = _make_map(3, 3)
        pos = Position(1, 1)
        _actions._spawn_loot_at_position(gm, pos, ("scrap_metal",), count_range=(2, 2))
        _actions._spawn_equipment_loot_at_position(
            gm, pos, (("weapon", "kinetic_pistol"),), count_range=(1, 1),
        )
        _actions._spawn_field_item_loot_at_position(
            gm, pos, (("ammo", "pistol_rounds"),), count_range=(1, 1),
        )

        by_type = {
            e.loot_data.get("item_type", "cargo"): e.fg
            for e in gm.entities if e.loot_data is not None
        }
        assert by_type["cargo"] == CARGO_FG
        assert by_type["weapon"] == EQUIPMENT_FG
        assert by_type["ammo"] == FIELD_ITEM_FG

    def test_pad_entity_is_data_coloured(self):
        from spacehack.loot import spawn_pad_entity

        gm = _make_map(1, 1)
        assert spawn_pad_entity(gm, Position(0, 0), {"teaches": "some_rumor"})
        assert gm.entities[0].fg == DATA_FG

    def test_space_debris_spawn_enforces_cap(self):
        from spacehack.combat import _actions
        from types import SimpleNamespace

        gm = _make_map(1, 1)
        spec = SimpleNamespace(cargo_goods=("scrap_metal",))
        for _ in range(MAX_LOOT_ENTITIES + 5):
            _actions._spawn_loot_drops(gm, Position(0, 0), spec)

        loot = [e for e in gm.entities if e.loot_data is not None]
        assert len(loot) == MAX_LOOT_ENTITIES


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

    def test_eviction_is_identity_based_against_value_equal_twins(self):
        ancient = _loot({"good_id": "fuel_cells", "quantity": 1})
        ancient.heist_mission = True
        twin = _loot({"good_id": "fuel_cells", "quantity": 1})
        assert ancient == twin  # value-equal despite protection

        # ancient (protected) first, its plain twin SECOND — inside
        # the doomed window — then fillers to one over cap: a
        # value-based remove(twin) would delete ancient instead.
        gm = _make_map(1, 1)
        gm.entities.append(ancient)
        gm.entities.append(twin)
        gm.entities.extend(
            _loot({"good_id": "scrap_metal", "quantity": 1})
            for _ in range(MAX_LOOT_ENTITIES - 1)
        )

        enforce_loot_cap(gm)

        assert any(e is ancient for e in gm.entities)
        assert not any(e is twin for e in gm.entities)


class TestGroundKillDrops:
    """The extracted ground drop sequence keeps pool behavior and
    enforces the shared cap (doc 47.1 step 2)."""

    def _spec(self, **overrides):
        from types import SimpleNamespace

        spec = SimpleNamespace(
            loot_pool=("scrap_metal",), loot_count=(1, 1),
            equipment_loot_pool=(("weapon", "kinetic_pistol"),),
            field_item_loot_pool=(("ammo", "pistol_rounds"),),
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

        # The equipment count rolls (0, 1) on the global RNG — seed it
        # and retry within a bound so the assertion is deterministic,
        # never a coin flip (reviewer-caught flake).
        RNG.seed(4747)
        gm = _make_map(1, 1)
        kinds = set()
        for _ in range(20):
            spawn_kill_drops(gm, Position(0, 0), self._spec(), SimpleNamespace())
            kinds = {
                e.loot_data.get("item_type", "cargo")
                for e in gm.entities if e.loot_data is not None
            }
            if kinds == {"cargo", "weapon", "ammo"}:
                break
        assert kinds == {"cargo", "weapon", "ammo"}

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

    def test_caps_the_map_across_many_kills(self):
        from spacehack.combat._actions import spawn_kill_drops
        from types import SimpleNamespace

        gm = _make_map(1, 1)
        spec = self._spec(equipment_loot_pool=(), field_item_loot_pool=())
        ctx = SimpleNamespace(known_rumors=set())
        for _ in range(MAX_LOOT_ENTITIES + 5):
            spawn_kill_drops(gm, Position(0, 0), spec, ctx)

        loot = [e for e in gm.entities if e.loot_data is not None]
        assert len(loot) == MAX_LOOT_ENTITIES

    def _bare_spec(self):
        """A spec whose every pool is empty — only the kit drop fires."""
        return self._spec(
            loot_pool=(), equipment_loot_pool=(), field_item_loot_pool=(),
        )

    def test_kit_drop_spawns_resolved_weapon_and_matching_ammo(self):
        from spacehack.combat._actions import spawn_kill_drops
        from types import SimpleNamespace

        gm = _make_map(1, 1)
        spawn_kill_drops(
            gm, Position(0, 0), self._bare_spec(), SimpleNamespace(),
            "kinetic_pistol",
        )
        payloads = [e.loot_data for e in gm.entities if e.loot_data is not None]
        assert {"item_type": "weapon", "item_id": "kinetic_pistol"} in payloads
        ammo = [p for p in payloads if p.get("item_type") == "ammo"]
        assert len(ammo) == 1
        assert ammo[0]["item_id"] == "pistol_rounds"
        assert 1 <= ammo[0]["quantity"] <= 5

    def test_kit_drop_carries_the_rolled_quality_without_reroll(self):
        from spacehack.combat._actions import spawn_kill_drops
        from types import SimpleNamespace

        gm = _make_map(1, 1)
        spawn_kill_drops(
            gm, Position(0, 0), self._bare_spec(), SimpleNamespace(),
            "kinetic_pistol", 2,
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
            "kinetic_pistol", 0,
        )
        base = next(
            e.loot_data for e in gm2.entities
            if e.loot_data.get("item_type") == "weapon"
        )
        assert "quality" not in base

    def test_kit_drop_melee_weapon_brings_no_ammo(self):
        from spacehack.combat._actions import spawn_kill_drops
        from types import SimpleNamespace

        gm = _make_map(1, 1)
        spawn_kill_drops(
            gm, Position(0, 0), self._bare_spec(), SimpleNamespace(),
            "combat_knife",
        )
        payloads = [e.loot_data for e in gm.entities if e.loot_data is not None]
        assert payloads == [{"item_type": "weapon", "item_id": "combat_knife"}]

    def test_kit_drop_skips_organic_and_unknown_weapons(self):
        from spacehack.combat._actions import spawn_kill_drops
        from types import SimpleNamespace

        for weapon_id in ("monster_claws", "fists", "does_not_exist", ""):
            gm = _make_map(1, 1)
            spawn_kill_drops(
                gm, Position(0, 0), self._bare_spec(), SimpleNamespace(),
                weapon_id,
            )
            assert [e for e in gm.entities if e.loot_data is not None] == []

    def test_organic_weapons_are_authored_not_droppable(self):
        from spacehack.data.ground_weapons import find_ground_weapon

        organic = (
            "monster_claws", "drone_laser", "frost_bolt",
            "parasite_mandibles", "fists",
        )
        for weapon_id in organic:
            assert find_ground_weapon(weapon_id).loot_droppable is False
        assert find_ground_weapon("kinetic_pistol").loot_droppable is True

    def test_equipment_pools_stay_beyond_the_wielded_weapons(self):
        from spacehack.data.npc_chars import _registry

        for spec in _registry().values():
            wielded = set(spec.weapons or ()) | set(spec.weapon_pick or ())
            pooled = {
                item_id
                for kind, item_id in (spec.equipment_loot_pool or ())
                if kind == "weapon"
            }
            assert not (pooled & wielded), (spec.id, pooled & wielded)

    def test_on_kill_forwards_the_resolved_weapon(self, monkeypatch):
        from tests.support.asyncutil import run, as_async
        from spacehack.combat import _actions, _rules_ground
        from spacehack import xp as xp_module
        from types import SimpleNamespace

        seen = []
        monkeypatch.setattr(
            _actions, "spawn_kill_drops",
            lambda *args, **kwargs: seen.append(args),
        )
        monkeypatch.setattr(xp_module, "add_xp", as_async(lambda *a, **k: None))

        ent = Entity(
            char="r", fg=(255, 255, 255), pos=Position(0, 0), name="raider",
        )
        gm = _make_map(1, 1)
        gm.entities.append(ent)
        enemy = _rules_ground.GroundEnemyInstance(
            entity=ent, spec=self._bare_spec(), weapon_id="kinetic_pistol",
            weapon_quality=2,
        )
        run(_rules_ground.on_kill(gm, enemy, SimpleNamespace()))
        # The resolved weapon AND its equip-time rolled tier forward —
        # the corpse drops what was firing at you, no re-roll (47.2).
        assert seen and seen[0][-2:] == ("kinetic_pistol", 2)


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
            "title": "ABANDON THE DERELICT?",
            "body": "This derelict ship is highly unstable, you won't "
            "be able to safely breach and dock it again.",
            "accept_label": "Leave",
            "cancel_label": "Stay",
            "caption": "spacehack - derelict",
        }

    def test_generic_derelict_constructor_stamps_the_flag(self):
        from types import SimpleNamespace
        from spacehack.game_interactions import _build_generic_derelict

        ctx = SimpleNamespace(game_map=SimpleNamespace(entities=[]))
        npcspec = SimpleNamespace(loot_budget=(50, 100), id="scout_wreck")
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
