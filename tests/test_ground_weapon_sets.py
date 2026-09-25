"""Doc 51 phase 1 tests: set classification, slot law, swap, migration split."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from src.spacehack import ground_weapon_sets
from src.spacehack.data.ground_weapons import list_ground_weapons
from src.spacehack.ground_equipment import GroundWeaponInstance


def test_classification_covers_every_catalog_weapon():
    """Every registered weapon (monsters included) resolves to a set."""
    classes = {ground_weapon_sets.weapon_set(w.id) for w in list_ground_weapons()}
    assert classes == {"ranged", "melee"}


def test_classification_domain_spans_all_five_damage_types():
    """The catalog exercises the whole table domain — exhaustiveness is
    load-bearing (an unseen family must fail, not silently join)."""
    damage_types = {w.damage_type for w in list_ground_weapons()}
    assert damage_types == {"melee", "kinetic", "energy", "plasma", "explosive"}


def test_classification_maps_representative_ids():
    assert ground_weapon_sets.weapon_set("railgun") == "ranged"
    assert ground_weapon_sets.weapon_set("kinetic_pistol") == "ranged"
    assert ground_weapon_sets.weapon_set("plasma_rifle") == "ranged"
    assert ground_weapon_sets.weapon_set("rocket_launcher") == "ranged"
    assert ground_weapon_sets.weapon_set("combat_knife") == "melee"
    assert ground_weapon_sets.weapon_set("mono_blade") == "melee"


def test_unknown_damage_type_raises(monkeypatch):
    """A future damage type outside the table fails loudly."""
    monkeypatch.setattr(
        ground_weapon_sets, "find_ground_weapon",
        lambda _wid: SimpleNamespace(damage_type="sonic"),
    )
    with pytest.raises(ValueError, match="sonic"):
        ground_weapon_sets.weapon_set("future_gun")


def test_empty_set_accepts_either_class():
    """An empty set is class-agnostic; occupancy counts from zero."""
    assert ground_weapon_sets.can_fit_weapon_set([], "kinetic_pistol")
    assert ground_weapon_sets.can_fit_weapon_set([], "combat_knife")
    assert ground_weapon_sets.can_fit_weapon_set([], "railgun")


def test_two_one_handed_same_class_fits():
    knife = GroundWeaponInstance("combat_knife", None)
    assert ground_weapon_sets.can_fit_weapon_set([knife], "vibroblade")
    pistol = GroundWeaponInstance("kinetic_pistol", 5)
    assert ground_weapon_sets.can_fit_weapon_set([pistol], "smg")


def test_two_handed_fits_alone_and_refuses_company():
    assert ground_weapon_sets.can_fit_weapon_set([], "railgun")
    railgun = GroundWeaponInstance("railgun", 3)
    assert not ground_weapon_sets.can_fit_weapon_set([railgun], "kinetic_pistol")
    mono = GroundWeaponInstance("mono_blade", None)
    assert not ground_weapon_sets.can_fit_weapon_set([mono], "combat_knife")


def test_three_one_handed_refused():
    knife = GroundWeaponInstance("combat_knife", None)
    baton = GroundWeaponInstance("stun_baton", None)
    assert not ground_weapon_sets.can_fit_weapon_set([knife, baton], "vibroblade")


def test_class_mix_refused_even_with_room():
    """A 1H melee never joins a ranged set (class purity, not just Σ hands)."""
    pistol = GroundWeaponInstance("kinetic_pistol", 5)
    assert not ground_weapon_sets.can_fit_weapon_set([pistol], "combat_knife")
    knife = GroundWeaponInstance("combat_knife", None)
    assert not ground_weapon_sets.can_fit_weapon_set([knife], "smg")


def test_exchange_swaps_lists_in_place():
    """The original list objects are mutated — callers holding
    ctx.equipped_ground_weapons / ctx.holstered_ground_weapons see the
    swap without rebinding."""
    equipped = [GroundWeaponInstance("kinetic_pistol", 5, 1)]
    holstered = [GroundWeaponInstance("combat_knife", None, 2)]
    equipped_ref, holstered_ref = equipped, holstered
    ground_weapon_sets.exchange_weapon_sets(equipped, holstered)
    assert equipped_ref == [GroundWeaponInstance("combat_knife", None, 2)]
    assert holstered_ref == [GroundWeaponInstance("kinetic_pistol", 5, 1)]


def test_exchange_moves_instances_not_copies():
    """Magazines + quality ride the SAME instance objects — no reseed."""
    pistol = GroundWeaponInstance("smg", 7, 3)
    holstered: list[GroundWeaponInstance] = []
    ground_weapon_sets.exchange_weapon_sets([pistol], holstered)
    assert holstered == [GroundWeaponInstance("smg", 7, 3)]
    assert holstered[0] is pistol


def test_exchange_with_either_side_empty():
    """Empty↔full both directions — the fists floor (SETTLED 1)."""
    pistol = GroundWeaponInstance("kinetic_pistol", 2)
    equipped, holstered = [pistol], []
    ground_weapon_sets.exchange_weapon_sets(equipped, holstered)
    assert (equipped, holstered) == ([], [pistol])
    ground_weapon_sets.exchange_weapon_sets(equipped, holstered)
    assert (equipped, holstered) == ([pistol], [])


def test_double_exchange_is_identity():
    equipped = [GroundWeaponInstance("railgun", 4, 1)]
    holstered = [
        GroundWeaponInstance("combat_knife", None, 2),
        GroundWeaponInstance("vibroblade", None),
    ]
    snapshot = (list(equipped), list(holstered))
    ground_weapon_sets.exchange_weapon_sets(equipped, holstered)
    ground_weapon_sets.exchange_weapon_sets(equipped, holstered)
    assert (equipped, holstered) == snapshot


def test_partition_keeps_same_class_loadout_together():
    weapons = [
        GroundWeaponInstance("kinetic_pistol", 3),
        GroundWeaponInstance("smg", 9, 2),
    ]
    active, holstered = ground_weapon_sets.partition_weapon_sets(weapons)
    assert active == weapons
    assert holstered == []


def test_partition_splits_mixed_pair_on_slot_zero_class():
    """Active = the ORIGINAL slot 0's class; the other class holsters."""
    pistol = GroundWeaponInstance("kinetic_pistol", 3)
    knife = GroundWeaponInstance("combat_knife", None, 1)
    active, holstered = ground_weapon_sets.partition_weapon_sets([pistol, knife])
    assert active == [pistol]
    assert holstered == [knife]
    active, holstered = ground_weapon_sets.partition_weapon_sets([knife, pistol])
    assert active == [knife]
    assert holstered == [pistol]


def test_partition_empty_loadout_yields_two_empty_sets():
    assert ground_weapon_sets.partition_weapon_sets([]) == ([], [])


# ---------------------------------------------------------------------------
# Phase 2 — the verb (X / SWAP_SETS), input paths, HUD, free explore swap
# ---------------------------------------------------------------------------

from tests.support.asyncutil import run, as_async  # noqa: E402

from src.spacehack import world  # noqa: E402
from src.spacehack.combat import _loop, _rules_ground  # noqa: E402
from src.spacehack.combat import _ground_render  # noqa: E402
from src.spacehack.input_helpers import _is_x_press  # noqa: E402


class _LogCapture:
    def __init__(self):
        self.lines = []

    def add(self, message, **kwargs):
        self.lines.append(message)

    def add_colored(self, message, color, **kwargs):
        self.lines.append(message)


class _Console:
    def __init__(self):
        self.prints = []

    def print(self, x, y, string, fg=None, **kwargs):
        self.prints.append((string, fg))


def _swap_fixture(equipped, holstered):
    """Map + ctx + enemy for ground-rules verb tests (doc 51 phase 2)."""
    _tiles = [[world.DUNGEON_FLOOR for _ in range(7)] for _ in range(7)]
    _game_map = world.GameMap(7, 7, _tiles, [])
    _player = world.Entity("@", (255, 255, 255), world.Position(3, 3), "Player")
    _enemy = world.Entity(
        "D", (255, 100, 100), world.Position(3, 5), "Assault Drone",
        npc_char_id="assault_drone",
    )
    _game_map.entities.extend((_player, _enemy))
    _ctx = SimpleNamespace(
        player=_player,
        ground_stats=SimpleNamespace(reflexes=10, strength=10, stamina=10),
        ground_hp=23,
        ground_max_hp=23,
        equipped_ground_weapons=equipped,
        holstered_ground_weapons=holstered,
        equipped_ground_armor={},
        player_traits=[],
        log=_LogCapture(),
    )
    _rules_ground.init(_ctx, [_enemy], _game_map)
    return _ctx, _game_map


def test_swap_sets_logged_swaps_and_logs_the_shared_outcome_line():
    equipped = [GroundWeaponInstance("kinetic_pistol", 5)]
    holstered = [GroundWeaponInstance("combat_knife", None)]
    log = _LogCapture()
    ground_weapon_sets.swap_sets_logged(equipped, holstered, log)
    assert equipped == [GroundWeaponInstance("combat_knife", None)]
    assert holstered == [GroundWeaponInstance("kinetic_pistol", 5)]
    assert log.lines == ["Weapon sets swapped."]


def test_combat_action_table_maps_x_to_swap_sets():
    assert _loop._key_action("x") == "SWAP_SETS"


def test_combat_x_input_path_plain_and_shift_blind():
    """The combat table is shift-blind: Shift+X also swaps (uniform
    with Shift+R = RELOAD) — pinned per SETTLED 1/2."""
    assert _loop._input_action(SimpleNamespace(key_name="x", repeat=False)) == "SWAP_SETS"
    assert _loop._input_action(
        SimpleNamespace(key_name="x", repeat=False, shift=True),
    ) == "SWAP_SETS"


def test_combat_x_key_repeats_are_swallowed():
    """Held X must not keep swapping on later turns."""
    assert _loop._input_action(SimpleNamespace(key_name="x", repeat=True)) == ""


def test_x_is_not_a_movement_key():
    assert "x" not in world.MOVE_KEYS


def test_is_x_press_matrix():
    """Main-loop matcher: plain x only — shift excluded (dev XP owns
    Shift+X there), keyup never fires."""
    assert _is_x_press(SimpleNamespace(kind="keydown", key_name="x", shift=False))
    assert not _is_x_press(SimpleNamespace(kind="keydown", key_name="x", shift=True))
    assert not _is_x_press(SimpleNamespace(kind="keyup", key_name="x", shift=False))
    assert not _is_x_press(SimpleNamespace(kind="keydown", key_name="c", shift=False))


def test_space_rules_lack_swap_hook_and_dispatch_logs_unavailable():
    from src.spacehack.combat import _rules_space

    assert getattr(_rules_space, "swap_weapon_sets", None) is None
    _ctx = SimpleNamespace(log=_LogCapture())
    run(_loop._dispatch_combat_action(None, _ctx, None, _rules_space, "SWAP_SETS", 0))
    assert "Weapon swap is unavailable here." in _ctx.log.lines


def test_rules_hook_runner_still_routes_reload():
    """The runner extraction preserved RELOAD both ways."""
    _ctx = SimpleNamespace(log=_LogCapture())
    run(_loop._dispatch_combat_action(None, _ctx, None, SimpleNamespace(), "RELOAD", 0))
    assert "Reload is unavailable here." in _ctx.log.lines

    _calls = []

    class _Rules:
        async def reload_weapon(self, ctx):
            _calls.append(ctx)
            return True

    _ctx2 = SimpleNamespace(log=_LogCapture())
    run(_loop._dispatch_combat_action(None, _ctx2, None, _Rules(), "RELOAD", 0))
    assert _calls == [_ctx2]
    assert not _ctx2.log.lines


def test_swap_weapon_sets_charges_one_ap_and_resets_flags():
    _pistol = GroundWeaponInstance("kinetic_pistol", 5)
    _smg = GroundWeaponInstance("smg", 9, 2)
    _mono = GroundWeaponInstance("mono_blade", None, 1)
    _ctx, _ = _swap_fixture([_pistol, _smg], [_mono])
    _rules_ground.set_player_ap(_ctx, 3)
    _rules_ground.set_active_weapons(_ctx, [True, False])

    assert run(_rules_ground.swap_weapon_sets(_ctx)) is True

    assert _ctx.equipped_ground_weapons == [_mono]
    assert _ctx.holstered_ground_weapons == [_pistol, _smg]
    assert _rules_ground.player_ap(_ctx) == 2
    assert _rules_ground.active_weapons(_ctx) == [True]
    assert "Weapon sets swapped." in _ctx.log.lines


def test_swap_weapon_sets_refuses_at_zero_ap_without_mutation():
    _pistol = GroundWeaponInstance("kinetic_pistol", 5)
    _knife = GroundWeaponInstance("combat_knife", None)
    _ctx, _ = _swap_fixture([_pistol], [_knife])
    _rules_ground.set_player_ap(_ctx, 0)

    assert run(_rules_ground.swap_weapon_sets(_ctx)) is False

    assert _ctx.equipped_ground_weapons == [_pistol]
    assert _ctx.holstered_ground_weapons == [_knife]
    assert _rules_ground.player_ap(_ctx) == 0
    assert "Not enough AP to swap weapon sets." in _ctx.log.lines


def test_swap_to_empty_set_fists_floor_still_fires(monkeypatch):
    """ADVISE fold 1: flags must cover the fists fallback, so FIRE
    works after swapping to an empty set (SETTLED 1 floor)."""
    _ctx, _game_map = _swap_fixture([GroundWeaponInstance("kinetic_pistol", 5)], [])

    assert run(_rules_ground.swap_weapon_sets(_ctx)) is True
    assert _ctx.equipped_ground_weapons == []
    assert _rules_ground.player_weapons(_ctx) == ["fists"]
    assert _rules_ground.active_weapons(_ctx) == [True]

    _ctx.player.pos = world.Position(3, 4)  # fists reach: adjacent
    monkeypatch.setattr(
        _rules_ground, "animate_fire", as_async(lambda *args, **kwargs: None),
    )
    monkeypatch.setattr(
        _loop, "RNG", SimpleNamespace(randint=lambda *_args: 1),
    )
    _rules_ground._state.enemies[0].hp = 10
    run(_loop._handle_fire(None, _ctx, _game_map, _rules_ground, target_idx=0))
    assert _rules_ground._state.enemies[0].hp < 10


def test_double_swap_mid_fight_is_identity_with_magazines_intact(monkeypatch):
    _pistol = GroundWeaponInstance("kinetic_pistol", 6)
    _knife = GroundWeaponInstance("combat_knife", None, 2)
    _ctx, _game_map = _swap_fixture([_pistol], [_knife])
    _rules_ground.set_player_ap(_ctx, 9)

    monkeypatch.setattr(
        _rules_ground, "animate_fire", as_async(lambda *args, **kwargs: None),
    )
    monkeypatch.setattr(
        _loop, "RNG", SimpleNamespace(randint=lambda *_args: 1),
    )
    run(_loop._handle_fire(None, _ctx, _game_map, _rules_ground, target_idx=0))
    # Frozen instances: the volley REPLACES the equipped entry, so read
    # the live list, not the construction-time reference.
    _live = _ctx.equipped_ground_weapons[0]
    _fired_rounds = 6 - _live.loaded_ammo
    assert _fired_rounds >= 1
    _ap_after_fire = _rules_ground.player_ap(_ctx)

    run(_rules_ground.swap_weapon_sets(_ctx))
    run(_rules_ground.swap_weapon_sets(_ctx))

    assert _ctx.equipped_ground_weapons == [_live]
    assert _ctx.holstered_ground_weapons == [_knife]
    assert _ctx.equipped_ground_weapons[0].loaded_ammo == 6 - _fired_rounds
    assert _rules_ground.player_ap(_ctx) == _ap_after_fire - 2


def _menu_state(mode, equipped, holstered):
    from src.spacehack import game_loop

    _log = _LogCapture()
    _ctx = SimpleNamespace(
        equipped_ground_weapons=equipped,
        holstered_ground_weapons=holstered,
        log=_log,
    )
    _state = SimpleNamespace(ctx=_ctx, log=_log, current_mode=mode)
    return game_loop, _state


def test_menu_x_swaps_free_in_dungeon_mode():
    game_loop, _state = _menu_state(
        "dungeon",
        [GroundWeaponInstance("kinetic_pistol", 5)],
        [GroundWeaponInstance("mono_blade", None)],
    )
    _event = SimpleNamespace(kind="keydown", key_name="x", shift=False)

    assert run(game_loop._handle_menu_event(_state, _event)) == "HANDLED"
    assert _state.ctx.equipped_ground_weapons == [
        GroundWeaponInstance("mono_blade", None),
    ]
    assert _state.ctx.holstered_ground_weapons == [
        GroundWeaponInstance("kinetic_pistol", 5),
    ]
    assert "Weapon sets swapped." in _state.log.lines


def test_menu_x_does_nothing_in_space_mode():
    game_loop, _state = _menu_state(
        "space",
        [GroundWeaponInstance("kinetic_pistol", 5)],
        [GroundWeaponInstance("mono_blade", None)],
    )
    _event = SimpleNamespace(kind="keydown", key_name="x", shift=False)

    assert run(game_loop._handle_menu_event(_state, _event)) is None
    assert _state.ctx.equipped_ground_weapons == [
        GroundWeaponInstance("kinetic_pistol", 5),
    ]
    assert not _state.log.lines


def test_menu_shift_x_never_swaps():
    """Shift+X belongs to the dev XP grant in the main loop — the
    explore matcher must not fire under shift (SETTLED 1 pin)."""
    game_loop, _state = _menu_state(
        "dungeon",
        [GroundWeaponInstance("kinetic_pistol", 5)],
        [GroundWeaponInstance("mono_blade", None)],
    )
    _event = SimpleNamespace(kind="keydown", key_name="x", shift=True)

    assert run(game_loop._handle_menu_event(_state, _event)) is None
    assert _state.ctx.equipped_ground_weapons == [
        GroundWeaponInstance("kinetic_pistol", 5),
    ]
    assert not _state.log.lines


def test_hud_holster_row_lists_holstered_names_dim():
    _ctx, _ = _swap_fixture(
        [GroundWeaponInstance("kinetic_pistol", 5)],
        [GroundWeaponInstance("mono_blade", None, 2)],
    )
    _console = _Console()
    _ground_render._render_weapons_panel(
        _console, _ctx, _rules_ground.player_weapons(_ctx),
        _rules_ground._state.enemies, 0,
    )
    _holster = [(s, fg) for s, fg in _console.prints if s.startswith("HOLSTER")]
    assert len(_holster) == 1
    assert "Mono Blade" in _holster[0][0]
    assert _holster[0][1] == _ground_render._COLOR_GROUND_WEAPON_DIM


def test_hud_holster_row_hidden_when_set_empty():
    _ctx, _ = _swap_fixture([GroundWeaponInstance("kinetic_pistol", 5)], [])
    _console = _Console()
    _ground_render._render_weapons_panel(
        _console, _ctx, _rules_ground.player_weapons(_ctx),
        _rules_ground._state.enemies, 0,
    )
    assert not [s for s, _ in _console.prints if s.startswith("HOLSTER")]


def test_hud_actions_legend_carries_swap_entry():
    _console = _Console()
    _ground_render._render_actions_panel(_console, ["kinetic_pistol"], 0)
    assert any(
        "[x]" in s and "Swap" in s for s, _ in _console.prints
    )


# ---------------------------------------------------------------------------
# Phase 3 — class-keyed homes (SETTLED 3), install primitive, magazine
# preservation through storage entries
# ---------------------------------------------------------------------------

from src.spacehack.ground_equipment import StoredGroundEquipment  # noqa: E402
from src.spacehack import saveload_ground  # noqa: E402


def _pistol(loaded=12, quality=0):
    return GroundWeaponInstance("kinetic_pistol", loaded, quality)


def test_home_resolution_founded_goes_to_the_holding_set():
    knife = GroundWeaponInstance("combat_knife", None)
    assert ground_weapon_sets.resolve_weapon_home([_pistol()], [knife], "smg") == (
        [_pistol()], "ACTIVE",
    )
    assert ground_weapon_sets.resolve_weapon_home([_pistol()], [knife], "vibroblade") == (
        [knife], "HOLSTER",
    )


def test_home_resolution_unfounded_goes_to_the_empty_set():
    """The empty set that is not the other class's home founds it."""
    assert ground_weapon_sets.resolve_weapon_home([], [_pistol()], "combat_knife") == (
        [], "ACTIVE",
    )
    assert ground_weapon_sets.resolve_weapon_home([_pistol()], [], "combat_knife") == (
        [], "HOLSTER",
    )


def test_home_resolution_both_empty_equips_to_wield():
    home = ground_weapon_sets.resolve_weapon_home([], [], "combat_knife")
    assert home == ([], "ACTIVE")


def test_home_resolution_same_class_both_active_wins():
    knife = GroundWeaponInstance("combat_knife", None)
    other = GroundWeaponInstance("vibroblade", None)
    assert ground_weapon_sets.resolve_weapon_home([knife], [other], "mono_blade") == (
        [knife], "ACTIVE",
    )


def test_home_resolution_mixed_no_empty_refuses():
    """Neither set holds the class and neither is empty (hand-edited
    both-same-class saves) — deterministic refusal (ADVISE fold 7)."""
    assert ground_weapon_sets.resolve_weapon_home(
        [_pistol()], [_pistol(6)], "combat_knife",
    ) is None


def test_founded_set_role_markers_and_flip():
    """Markers read the live homes; X (exchange) flips them."""
    knife = GroundWeaponInstance("mono_blade", None)
    equipped, holstered = [_pistol()], [knife]
    assert ground_weapon_sets.founded_set_role(equipped, holstered, "ranged") == "ACTIVE"
    assert ground_weapon_sets.founded_set_role(equipped, holstered, "melee") == "HOLSTER"
    ground_weapon_sets.exchange_weapon_sets(equipped, holstered)
    assert ground_weapon_sets.founded_set_role(equipped, holstered, "ranged") == "HOLSTER"
    assert ground_weapon_sets.founded_set_role(equipped, holstered, "melee") == "ACTIVE"


def test_founded_set_role_none_when_unfounded():
    assert ground_weapon_sets.founded_set_role([], [], "ranged") is None
    knife = GroundWeaponInstance("combat_knife", None)
    assert ground_weapon_sets.founded_set_role([knife], [], "ranged") is None


def test_weapon_entry_and_instance_round_trip_preserve_magazine():
    entry = ground_weapon_sets.weapon_entry(_pistol(5, 2))
    assert entry == StoredGroundEquipment("weapon", "kinetic_pistol", 2, 5)
    restored = ground_weapon_sets.weapon_instance_from_entry(entry)
    assert restored == GroundWeaponInstance("kinetic_pistol", 5, 2)


def test_unspecified_entry_magazine_seeds_full_and_melee_stays_none():
    legacy = StoredGroundEquipment("weapon", "kinetic_pistol", 1)
    assert ground_weapon_sets.weapon_instance_from_entry(legacy) == _pistol(12, 1)
    knife_entry = ground_weapon_sets.weapon_entry(
        GroundWeaponInstance("combat_knife", None, 3),
    )
    assert knife_entry.loaded_ammo is None
    assert ground_weapon_sets.weapon_instance_from_entry(knife_entry) == (
        GroundWeaponInstance("combat_knife", None, 3)
    )


def test_entry_magazine_clamps_to_capacity():
    hot = StoredGroundEquipment("weapon", "kinetic_pistol", 0, 99)
    assert ground_weapon_sets.weapon_instance_from_entry(hot) == _pistol(12)


def test_stored_entry_parse_preserves_magazine_and_legacy_defaults_full():
    carried = saveload_ground._ground_equipment_from_dict({
        "item_type": "weapon", "item_id": "kinetic_pistol",
        "quality": 2, "loaded_ammo": 5,
    })
    assert carried == StoredGroundEquipment("weapon", "kinetic_pistol", 2, 5)
    legacy = saveload_ground._ground_equipment_from_dict({
        "item_type": "weapon", "item_id": "kinetic_pistol", "quality": 1,
    })
    assert legacy.loaded_ammo is None
    clamped = saveload_ground._ground_equipment_from_dict({
        "item_type": "weapon", "item_id": "kinetic_pistol", "loaded_ammo": 99,
    })
    assert clamped.loaded_ammo == 12
    armor = saveload_ground._ground_equipment_from_dict({
        "item_type": "armor", "item_id": "light_vest", "loaded_ammo": 7,
    })
    assert armor.loaded_ammo is None


def test_install_appends_into_founded_home_with_carried_magazine():
    """Unfounded class + empty active set founds it (equip-to-wield);
    the entry's magazine rides the installed instance."""
    equipped, holstered = [], [GroundWeaponInstance("combat_knife", None)]
    pack = [StoredGroundEquipment("weapon", "smg", 1, 7)]
    entry, role = ground_weapon_sets.install_set_weapon(
        equipped, holstered, pack, 0,
    )
    assert (entry.item_id, role) == ("smg", "ACTIVE")
    assert equipped == [GroundWeaponInstance("smg", 7, 1)]
    assert pack == []


def test_install_routes_to_holstered_home_and_reports_role():
    equipped, holstered = [_pistol()], []
    warehouse = [StoredGroundEquipment("weapon", "mono_blade", 2)]
    _entry, role = ground_weapon_sets.install_set_weapon(
        equipped, holstered, warehouse, 0,
    )
    assert role == "HOLSTER"
    assert holstered == [GroundWeaponInstance("mono_blade", None, 2)]


def test_install_two_handed_displaces_whole_set_to_destination():
    smg = GroundWeaponInstance("smg", 9, 1)
    equipped, holstered = [smg, _pistol(4)], []
    warehouse = [StoredGroundEquipment("weapon", "railgun")]
    ground_weapon_sets.install_set_weapon(
        equipped, holstered, warehouse, 0, displaced_storage=warehouse,
    )
    assert equipped == [GroundWeaponInstance("railgun", 12)]
    # The popped railgun entry leaves the source list first; displaced
    # members rejoin it after.
    assert {e.item_id for e in warehouse} == {"smg", "kinetic_pistol"}
    assert next(e for e in warehouse if e.item_id == "kinetic_pistol").loaded_ammo == 4


def test_install_one_handed_pick_displaces_only_the_chosen_member():
    pistol, smg = _pistol(5), GroundWeaponInstance("smg", 9)
    equipped, holstered = [pistol, smg], []
    pack = [StoredGroundEquipment("weapon", "laser_pistol", 0, 3)]
    ground_weapon_sets.install_set_weapon(
        equipped, holstered, pack, 0,
        displace_index=0, displaced_storage=pack,
        displaced_container="expedition", strength=10,
    )
    # The picked member leaves; the install appends at the end.
    assert equipped == [smg, GroundWeaponInstance("laser_pistol", 3)]
    assert pack == [StoredGroundEquipment("weapon", "kinetic_pistol", 0, 5)]


def test_install_auto_displacement_matches_legacy_whole_set_behaviour():
    equipped, holstered = [_pistol(5), GroundWeaponInstance("smg", 9)], []
    pack = [StoredGroundEquipment("weapon", "laser_pistol")]
    ground_weapon_sets.install_set_weapon(
        equipped, holstered, pack, 0, displaced_storage=pack,
        displaced_container="expedition", strength=10,
    )
    assert equipped == [GroundWeaponInstance("laser_pistol", 100)]
    assert len(pack) == 2


def test_install_purity_stranding_pick_is_refused():
    """A pick that would strand a mixed home (degenerate save) is
    refused — purity guards mutations."""
    knife = GroundWeaponInstance("combat_knife", None)
    equipped, holstered = [knife, _pistol(5)], []
    pack = [StoredGroundEquipment("weapon", "smg")]
    with pytest.raises(ValueError, match="cannot be displaced"):
        ground_weapon_sets.install_set_weapon(
            equipped, holstered, pack, 0,
            displace_index=1, displaced_storage=pack,
            displaced_container="expedition", strength=10,
        )
    assert pack == [StoredGroundEquipment("weapon", "smg")]
    assert len(equipped) == 2


def test_install_no_home_raises_the_deterministic_refusal():
    equipped, holstered = [_pistol()], [_pistol(6)]
    pack = [StoredGroundEquipment("weapon", "combat_knife")]
    with pytest.raises(ValueError, match=ground_weapon_sets.NO_WEAPON_HOME_LINE):
        ground_weapon_sets.install_set_weapon(equipped, holstered, pack, 0)
    assert pack == [StoredGroundEquipment("weapon", "combat_knife")]


def test_install_two_handed_pack_overflow_aborts_atomically():
    """ADVISE fold 10: the +1 displaced member overflows a full pack —
    zero partial mutation."""
    from src.spacehack.ground_equipment import expedition_capacity

    equipped, holstered = [_pistol(5), GroundWeaponInstance("smg", 9)], []
    strength = 10
    junk = [
        StoredGroundEquipment("armor", "light_vest")
        for _ in range(expedition_capacity(strength))
    ]
    pack = [*junk, StoredGroundEquipment("weapon", "railgun")]
    with pytest.raises(ValueError, match="Expedition inventory is full"):
        ground_weapon_sets.install_set_weapon(
            equipped, holstered, pack, len(pack) - 1,
            displaced_storage=pack, displaced_container="expedition",
            strength=strength,
        )
    assert len(pack) == expedition_capacity(strength) + 1
    assert len(equipped) == 2


def test_install_one_handed_pick_from_full_pack_still_fits():
    """Source removal frees the pack slot first — the 1H member
    chooser never overflows from a full pack (net zero)."""
    from src.spacehack.ground_equipment import expedition_capacity

    equipped, holstered = [_pistol(5), GroundWeaponInstance("smg", 9)], []
    strength = 10
    junk = [
        StoredGroundEquipment("armor", "light_vest")
        for _ in range(expedition_capacity(strength) - 1)
    ]
    pack = [*junk, StoredGroundEquipment("weapon", "laser_pistol")]
    ground_weapon_sets.install_set_weapon(
        equipped, holstered, pack, len(pack) - 1,
        displace_index=0, displaced_storage=pack,
        displaced_container="expedition", strength=strength,
    )
    assert len(pack) == expedition_capacity(strength)
    assert equipped == [
        GroundWeaponInstance("smg", 9),
        GroundWeaponInstance("laser_pistol", 100),
    ]


def test_install_bad_displace_index_raises():
    equipped, holstered = [_pistol(5), GroundWeaponInstance("smg", 9)], []
    pack = [StoredGroundEquipment("weapon", "laser_pistol")]
    with pytest.raises(IndexError):
        ground_weapon_sets.install_set_weapon(
            equipped, holstered, pack, 0, displace_index=9,
            displaced_storage=pack, displaced_container="expedition",
        )


def test_install_displacement_requires_a_destination():
    """Whole-set displacement with nowhere to route refuses atomically
    (``displaced_container`` alone defaults to armory; the storage
    list is the required part)."""
    equipped, holstered = [_pistol(5), GroundWeaponInstance("smg", 9)], []
    pack = [StoredGroundEquipment("weapon", "laser_pistol")]
    with pytest.raises(ValueError, match="destination"):
        ground_weapon_sets.install_set_weapon(
            equipped, holstered, pack, 0,
            displaced_container="expedition",
        )
    assert len(equipped) == 2
    assert pack == [StoredGroundEquipment("weapon", "laser_pistol")]


def test_install_carries_quality_both_ways():
    """The installed weapon fights at its rolled tier; a displaced
    member keeps its tier (and magazine) in storage."""
    equipped, holstered = [_pistol(4, 3)], []
    warehouse = [StoredGroundEquipment("weapon", "railgun", 1)]
    ground_weapon_sets.install_set_weapon(
        equipped, holstered, warehouse, 0, displaced_storage=warehouse,
    )
    assert equipped == [GroundWeaponInstance("railgun", 12, 1)]
    assert warehouse == [StoredGroundEquipment("weapon", "kinetic_pistol", 3, 4)]
