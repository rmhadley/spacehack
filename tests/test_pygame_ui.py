"""Tests for the Pygame presentation and shared-runtime seam."""

from __future__ import annotations

from types import SimpleNamespace

from src.spacehack import (
    character_screen,
    pygame_batch,
    pygame_screen,
    pygame_menu,
    pygame_merchant,
    pygame_quest_log,
    pygame_story,
    pygame_ui,
    pygame_world,
    pygame_quantity,
    pygame_combat,
    pygame_runtime,
    pygame_engine,
    pygame_navigation,
    animation_timing,
)
from src.spacehack.menus import _armory, _missions, _planet, _ship_buy, _ship_menu
from src.spacehack import navigation, npc, pygame_split
from src.spacehack.main_quest import _act0
from src.spacehack.ground_equipment import (
    GroundItemStack,
    GroundWeaponInstance,
    weapon_instance,
)
from tests.support.fake_pygame import FakeFont as _FakeFont


def test_character_c_opens_managed_equipment_in_every_game_mode(monkeypatch):
    from src.spacehack import __main__ as game_main

    calls = []
    monkeypatch.setattr(
        "src.spacehack.character_screen.open_character_screen",
        lambda ctx, **kwargs: calls.append((ctx, kwargs)) or 0,
    )
    ctx = SimpleNamespace()

    for mode in ("city", "space", "dungeon"):
        assert game_main._open_character_for_mode(ctx) == 0

    assert [kwargs for _ctx, kwargs in calls] == [
        {"equipment_management": True},
        {"equipment_management": True},
        {"equipment_management": True},
    ]


def test_character_equipment_backpack_rows_are_selectable():
    from src.spacehack.ground_equipment import StoredGroundEquipment

    ctx = SimpleNamespace(
        equipped_ground_weapons=[weapon_instance("laser_pistol")],
        equipped_ground_armor={},
        ground_expedition_inventory=[
            StoredGroundEquipment("weapon", "laser_rifle"),
        ],
    )

    rows = character_screen._equipment_rows(ctx, equipment_management=True)

    backpack_row = rows[8]
    assert backpack_row.text == "Laser Rifle"
    assert backpack_row.action == "PACK_ITEM:0"
    assert backpack_row.selectable is True


def test_character_equipment_backpack_discard_removes_selected_item(monkeypatch):
    from src.spacehack import pygame_story
    from src.spacehack.ground_equipment import StoredGroundEquipment

    messages = []
    ctx = SimpleNamespace(
        equipped_ground_weapons=[weapon_instance("laser_pistol")],
        equipped_ground_armor={},
        ground_expedition_inventory=[
            StoredGroundEquipment("weapon", "laser_rifle"),
        ],
        log=SimpleNamespace(add=messages.append),
    )
    monkeypatch.setattr(
        pygame_story,
        "choose",
        lambda *_args, **_kwargs: "PACK_DISCARD:0",
    )

    assert character_screen._manage_pack_item(ctx, "PACK_ITEM:0") == "DISCARD"
    assert ctx.ground_expedition_inventory == []
    assert messages == ["Discarded Laser Rifle."]


def test_character_equipment_backpack_equip_uses_compact_choice(monkeypatch):
    from src.spacehack import pygame_story
    from src.spacehack.ground_equipment import StoredGroundEquipment

    choices = []
    ctx = SimpleNamespace(
        equipped_ground_weapons=[weapon_instance("laser_pistol")],
        equipped_ground_armor={},
        ground_expedition_inventory=[
            StoredGroundEquipment("weapon", "laser_rifle"),
        ],
        ground_stats=SimpleNamespace(strength=10),
        log=SimpleNamespace(add=lambda _message: None),
    )

    def choose(_ctx, **kwargs):
        choices.append(kwargs)
        return "PACK_EQUIP:0" if kwargs["title"] == "BACKPACK ITEM" else "__BACK__"

    monkeypatch.setattr(pygame_story, "choose", choose)

    assert character_screen._manage_pack_item(ctx, "PACK_ITEM:0") == "EQUIP"
    assert ctx.equipped_ground_weapons == [weapon_instance("laser_rifle")]
    assert ctx.ground_expedition_inventory[0].item_id == "laser_pistol"
    assert choices[0]["options"] == (
        ("Equip", "PACK_EQUIP:0"),
        ("Discard", "PACK_DISCARD:0"),
    )


def test_character_equipment_backpack_equip_requires_ap_but_discard_remains_available(monkeypatch):
    from src.spacehack import pygame_story
    from src.spacehack.ground_equipment import StoredGroundEquipment

    ctx = SimpleNamespace(
        equipped_ground_weapons=[weapon_instance("laser_pistol")],
        equipped_ground_armor={},
        ground_expedition_inventory=[
            StoredGroundEquipment("weapon", "laser_rifle"),
        ],
        log=SimpleNamespace(add=lambda _message: None),
    )
    captured = {}
    monkeypatch.setattr(
        pygame_story,
        "choose",
        lambda _ctx, **kwargs: captured.update(kwargs) or "__BACK__",
    )

    assert character_screen._manage_pack_item(
        ctx, "PACK_ITEM:0", swap_allowed=False,
    ) is None
    assert captured["options"] == (
        ("Equip (requires 1 AP)", "PACK_EQUIP:0"),
        ("Discard", "PACK_DISCARD:0"),
    )
    assert ctx.equipped_ground_weapons == [weapon_instance("laser_pistol")]
    assert len(ctx.ground_expedition_inventory) == 1


def test_character_equipment_ammo_stack_reloads_matching_weapon():
    ctx = SimpleNamespace(
        equipped_ground_weapons=[GroundWeaponInstance("kinetic_pistol", 2)],
        equipped_ground_armor={},
        ground_expedition_items=[GroundItemStack("ammo", "pistol_rounds", 40)],
        log=SimpleNamespace(add=lambda _message: None),
    )

    assert character_screen._reload_pack_ammo(ctx, 0, in_ground_combat=False)

    assert ctx.equipped_ground_weapons == [GroundWeaponInstance("kinetic_pistol", 12)]
    assert ctx.ground_expedition_items == [GroundItemStack("ammo", "pistol_rounds", 30)]


def test_combat_character_screen_returns_after_successful_swap(monkeypatch):
    ctx = SimpleNamespace(context=object())
    monkeypatch.setattr(
        character_screen,
        "_combat_ap_available",
        lambda *_args, **_kwargs: True,
    )
    monkeypatch.setattr(
        character_screen,
        "_character_frame",
        lambda *_args, **_kwargs: object(),
    )
    monkeypatch.setattr(
        character_screen,
        "_swap_from_pack",
        lambda *_args, **_kwargs: True,
    )
    outcomes = iter((
        ("TAB", "", 0),
        ("SELECT", "SWAP:weapon:0", 0),
    ))
    monkeypatch.setattr(
        pygame_screen,
        "run_for_context",
        lambda *_args, **_kwargs: next(outcomes),
    )

    assert character_screen._run_pygame_character_screen(
        ctx, equipment_management=True, in_ground_combat=True,
    ) == 1


def test_combat_character_action_charges_only_reported_swaps(monkeypatch):
    from src.spacehack.combat import _loop

    calls = []
    ctx = SimpleNamespace(log=SimpleNamespace(add=lambda message: calls.append(message)))
    rules = SimpleNamespace(
        player_ap=lambda _ctx: 3,
        set_player_ap=lambda _ctx, value: calls.append(("ap", value)),
        refresh_equipment_state=lambda _ctx: calls.append("refresh"),
    )
    monkeypatch.setattr(
        _loop,
        "_rules_ground",
        rules,
    )
    monkeypatch.setattr(
        "src.spacehack.character_screen.open_character_screen",
        lambda *_args, **_kwargs: 1,
    )

    assert _loop._handle_character_action(ctx, rules) == 1
    assert ("ap", 2) in calls
    assert "refresh" in calls


def test_combat_character_action_is_free_when_screen_reports_cancel(monkeypatch):
    from src.spacehack.combat import _loop

    calls = []
    ctx = SimpleNamespace(log=SimpleNamespace(add=lambda message: calls.append(message)))
    rules = SimpleNamespace(
        player_ap=lambda _ctx: 3,
        set_player_ap=lambda _ctx, value: calls.append(("ap", value)),
        refresh_equipment_state=lambda _ctx: calls.append("refresh"),
    )
    monkeypatch.setattr(_loop, "_rules_ground", rules)
    monkeypatch.setattr(
        "src.spacehack.character_screen.open_character_screen",
        lambda *_args, **_kwargs: 0,
    )

    assert _loop._handle_character_action(ctx, rules) == 0
    assert not any(item[0] == "ap" for item in calls if isinstance(item, tuple))


def test_combat_character_action_is_unavailable_for_space_rules():
    from src.spacehack.combat import _loop

    messages = []
    ctx = SimpleNamespace(log=SimpleNamespace(add=messages.append))
    rules = SimpleNamespace()

    assert _loop._handle_character_action(ctx, rules) == 0
    assert messages == ["The character screen is unavailable here."]


def test_combat_key_mapping_returns_opaque_actions():
    class FakePygame:
        QUIT = 1
        KEYDOWN = 2
        K_ESCAPE = 10
        K_TAB = 11
        K_UP = 12
        K_DOWN = 13
        K_LEFT = 14
        K_RIGHT = 15

        class key:
            @staticmethod
            def name(value):
                return {
                    20: "f", 21: "1", 22: "?", 23: "period", 24: "backslash",
                }.get(value, "")

    fake = FakePygame()
    key = lambda value: SimpleNamespace(type=fake.KEYDOWN, key=value, unicode="")

    assert pygame_combat._action_for_key(fake, SimpleNamespace(type=fake.QUIT)) == "QUIT"
    assert pygame_combat._action_for_key(fake, key(fake.K_ESCAPE)) == "FLEE"
    assert pygame_combat._action_for_key(fake, key(fake.K_TAB)) == "TARGET"
    assert pygame_combat._action_for_key(fake, key(fake.K_UP)) == "MOVE:up"
    assert pygame_combat._action_for_key(fake, key(20)) == "FIRE"
    assert pygame_combat._action_for_key(fake, key(21)) == "WEAPON:0"
    assert pygame_combat._action_for_key(fake, key(23)) == "WAIT"
    assert pygame_combat._action_for_key(fake, key(24)) == "HISTORY"

    from src.spacehack.combat import _loop
    assert _loop._input_action(
        pygame_engine.PygameInputEvent(kind="keydown", key_name="period"),
    ) == "WAIT"
    assert _loop._input_action(
        pygame_engine.PygameInputEvent(kind="keydown", key_name="backslash"),
    ) == "HISTORY"
    # Top-row digits arrive as "1".."9" from the shared Pygame runtime
    # (tcod-era "n1".."n9" names are gone) and map to weapon slots.
    assert _loop._input_action(
        pygame_engine.PygameInputEvent(kind="keydown", key_name="1"),
    ) == "WEAPON:0"
    assert _loop._input_action(
        pygame_engine.PygameInputEvent(kind="keydown", key_name="9"),
    ) == "WEAPON:8"


def test_combat_present_rejects_failed_presenter_without_shared_runtime(monkeypatch):
    calls = []

    class FailedPresenter:
        def show(self, *_args, **_kwargs):
            raise pygame_combat.PygameCombatUnavailable("stopped")

        def close(self):
            calls.append("close")

    ctx = SimpleNamespace(
        _pygame_combat_presenter=FailedPresenter(),
        context=SimpleNamespace(present=lambda _console: calls.append("legacy")),
    )

    monkeypatch.setattr(pygame_runtime, "is_shared_context", lambda _context: False)
    try:
        pygame_combat.present(ctx, SimpleNamespace(commands=[]))
    except pygame_combat.PygameCombatUnavailable:
        pass
    else:
        raise AssertionError("combat must require the shared Pygame runtime")
    assert calls == ["close"]
    assert ctx._pygame_combat_presenter is None


def test_invalid_combat_console_rejects_without_shared_runtime(monkeypatch):
    calls = []

    class Presenter:
        def show(self, console, **_kwargs):
            pygame_combat._frame_payload(console, interactive=False)

        def close(self):
            calls.append("close")

    ctx = SimpleNamespace(
        _pygame_combat_presenter=Presenter(),
        context=SimpleNamespace(present=lambda _console: calls.append("legacy")),
    )

    monkeypatch.setattr(pygame_runtime, "is_shared_context", lambda _context: False)
    try:
        pygame_combat.present(ctx, SimpleNamespace(commands=[SimpleNamespace(x=0)]))
    except pygame_combat.PygameCombatUnavailable:
        pass
    else:
        raise AssertionError("combat must require the shared Pygame runtime")
    assert calls == ["close"]
    assert ctx._pygame_combat_presenter is None


def test_combat_action_falls_back_when_presenter_stops():
    class UnavailablePresenter:
        def show(self, *_args, **_kwargs):
            raise pygame_combat.PygameCombatUnavailable("stopped")

        def wait_action(self):
            raise AssertionError("wait_action must not run after show fails")

    assert pygame_combat.PygameCombatUnavailable.__name__ == "PygameCombatUnavailable"
    from src.spacehack.combat import _loop

    assert _loop._combat_action(
        SimpleNamespace(), SimpleNamespace(), presenter=UnavailablePresenter(),
    ) == "UNAVAILABLE"


def _combat_history_rules() -> SimpleNamespace:
    """Minimal rules stub for driving _run_combat_impl to an input wait."""
    from src.spacehack.combat._types import CombatResult

    return SimpleNamespace(
        refresh_engaged=lambda _ctx, _map: None,
        get_enemies=lambda _ctx: [SimpleNamespace(alive=True, pos=(1, 1))],
        enemy_name=lambda _e: "Pirate Scout",
        combat_should_end=lambda _ctx, _map, _enemies: False,
        set_target_idx=lambda _ctx, _idx: None,
        enemy_alive=lambda _e: True,
        render_frame=lambda _console, _ctx, _map: None,
        sync_state=lambda _ctx: None,
        get_combat_result=lambda: CombatResult(),
    )


def test_combat_history_opens_console_log_and_resumes(monkeypatch):
    """\\ in combat opens the full console log; ESC returns to the fight."""
    from src.spacehack.combat import _loop

    opened = []
    monkeypatch.setattr(
        "src.spacehack.console_log.open_console_log",
        lambda ctx: opened.append(ctx) or "BACK",
    )
    monkeypatch.setattr(_loop, "_present", lambda ctx, console: None)
    actions = iter(("HISTORY", "FLEE"))
    monkeypatch.setattr(
        _loop,
        "_combat_action",
        lambda ctx, console, *, presenter: next(actions),
    )

    ctx = SimpleNamespace(
        log=SimpleNamespace(add_colored=lambda *_args: None),
        _pygame_combat_presenter=None,
    )
    result = _loop._run_combat_impl(None, ctx, object(), _combat_history_rules())

    assert opened == [ctx]  # the log opened once, then the fight resumed
    assert result.outcome == "FLEE"


def test_combat_history_window_close_counts_as_flee(monkeypatch):
    """Closing the log window quits the fight the same way ESC does."""
    from src.spacehack.combat import _loop

    monkeypatch.setattr(
        "src.spacehack.console_log.open_console_log",
        lambda ctx: "QUIT",
    )
    monkeypatch.setattr(_loop, "_present", lambda ctx, console: None)
    actions = iter(("HISTORY",))
    monkeypatch.setattr(
        _loop,
        "_combat_action",
        lambda ctx, console, *, presenter: next(actions),
    )

    ctx = SimpleNamespace(
        log=SimpleNamespace(add_colored=lambda *_args: None),
        _pygame_combat_presenter=None,
    )
    result = _loop._run_combat_impl(None, ctx, object(), _combat_history_rules())

    assert result.outcome == "FLEE"


def test_combat_action_ignores_triggering_key_release_before_next_action(monkeypatch):
    from src.spacehack.combat import _loop
    key_up = pygame_engine.PygameInputEvent(kind="keyup", key_name="right")
    key_down = pygame_engine.PygameInputEvent(kind="keydown", key_name="period")
    waits = iter(((key_up,), (key_down,)))
    shared_ctx = SimpleNamespace(
        context=SimpleNamespace(
            _runtime=SimpleNamespace(engine=object()),
            wait_events=lambda: next(waits),
        ),
    )
    monkeypatch.setattr(
        pygame_runtime,
        "is_shared_context",
        lambda _context: True,
    )

    assert _loop._combat_action(shared_ctx, SimpleNamespace(), presenter=None) == "WAIT"

    unknown_key = pygame_engine.PygameInputEvent(kind="keydown", key_name="a")
    waits = iter(((unknown_key,), (key_down,)))
    monkeypatch.setattr(shared_ctx.context, "wait_events", lambda: next(waits))
    assert _loop._combat_action(shared_ctx, SimpleNamespace(), presenter=None) == ""

    monkeypatch.setattr(
        shared_ctx.context,
        "wait_events",
        lambda: (pygame_engine.PygameInputEvent(kind="quit"),),
    )
    assert _loop._combat_action(shared_ctx, SimpleNamespace(), presenter=None) == "QUIT"


def test_combat_frame_payload_preserves_commands_and_mode():
    console = SimpleNamespace(commands=[SimpleNamespace(x=1, y=2, char="@", fg=(1, 2, 3), bg=None)])

    payload = pygame_combat._frame_payload(console, interactive=True)

    assert payload["logical_size"] == (1600, 960)
    assert payload["interactive"] is True
    assert payload["commands"][0]["char"] == "@"


def test_combat_frame_payload_filters_hud_and_log_from_bitmap_layer():
    commands = [
        SimpleNamespace(x=10, y=10, char="@", fg=(1, 2, 3), bg=None),
        SimpleNamespace(x=80, y=10, char="H", fg=(4, 5, 6), bg=None),
        SimpleNamespace(x=10, y=54, char="M", fg=(7, 8, 9), bg=None),
    ]

    payload = pygame_combat._frame_payload(
        SimpleNamespace(commands=commands),
        interactive=False,
    )

    assert [command["char"] for command in payload["commands"]] == ["@"]
    assert payload["overlay"]["hud"][0]["text"] == "H"
    assert payload["overlay"]["messages"][0]["text"] == "M"


def test_combat_frame_payload_accepts_project_framebuffer():
    from src.spacehack.framebuffer import FrameBuffer

    frame = FrameBuffer(2, 1)
    frame.print(x=0, y=0, string="@A", fg=(1, 2, 3), bg=(4, 5, 6))

    payload = pygame_combat._frame_payload(frame, interactive=False)

    assert [command["char"] for command in payload["commands"]] == ["@", "A"]
    assert payload["commands"][0]["fg"] == (1, 2, 3)
    assert payload["commands"][0]["bg"] == (4, 5, 6)


def test_shared_combat_present_preserves_default_background(monkeypatch):
    from src.spacehack.framebuffer import FrameBuffer

    calls = []
    ctx = SimpleNamespace(
        _pygame_combat_presenter=None,
        context=SimpleNamespace(
            _runtime=object(),
            present=lambda console, **kwargs: calls.append((console, kwargs)),
        ),
    )
    frame = FrameBuffer(2, 1, background=(7, 8, 9))
    frame.print(string="@")
    monkeypatch.setattr(pygame_runtime, "is_shared_context", lambda _context: True)

    pygame_combat.present(ctx, frame)

    assert calls[0][0].default_background() == (7, 8, 9)


def test_shared_combat_present_uses_native_overlay_and_map_only(monkeypatch):
    calls = []
    ctx = SimpleNamespace(
        _pygame_combat_presenter=None,
        context=SimpleNamespace(
            _runtime=object(),
            present=lambda console, **kwargs: calls.append((console, kwargs)),
        ),
    )
    console = SimpleNamespace(commands=[
        SimpleNamespace(x=1, y=1, char="@", fg=(1, 2, 3), bg=None),
        SimpleNamespace(x=80, y=1, char="H", fg=(4, 5, 6), bg=None),
        SimpleNamespace(x=1, y=54, char="M", fg=(7, 8, 9), bg=None),
    ])

    monkeypatch.setattr(pygame_runtime, "is_shared_context", lambda _context: True)
    pygame_combat.present(ctx, console)

    rendered_console, kwargs = calls[0]
    assert [command.char for command in rendered_console.commands] == ["@"]
    assert kwargs["overlay"].hud[0].text == "H"
    assert kwargs["overlay"].messages[0].text == "M"


def test_shared_combat_present_captures_hud_text_past_window_width(monkeypatch):
    """The live shared present() path must capture combat HUD cells past
    cell SCREEN_WIDTH (the worker-only hud_x_max fix). A 24-cell shield
    row starting at hud_x=80 spans past cell 100; dropping it clips the
    shield readout at 20 cells."""
    from src.spacehack.engine import HUD_WIDTH, SCREEN_WIDTH
    from src.spacehack.framebuffer import FrameBuffer

    calls = []
    ctx = SimpleNamespace(
        _pygame_combat_presenter=None,
        context=SimpleNamespace(
            _runtime=object(),
            present=lambda console, **kwargs: calls.append((console, kwargs)),
        ),
    )
    console = FrameBuffer(SCREEN_WIDTH + HUD_WIDTH, 2)
    line = "Shd  ########## 135/135 +12"
    console.print(x=SCREEN_WIDTH - HUD_WIDTH, y=1, string=line)
    console.print(x=1, y=1, string="@")

    monkeypatch.setattr(pygame_runtime, "is_shared_context", lambda _context: True)
    pygame_combat.present(ctx, console)

    rendered_console, kwargs = calls[0]
    assert [command.char for command in rendered_console.commands] == ["@"]
    hud_text = "".join(segment.text for segment in kwargs["overlay"].hud)
    assert line in hud_text


def test_combat_present_death_requires_shared_runtime():
    ctx = SimpleNamespace(
        context=SimpleNamespace(_runtime=SimpleNamespace(engine=None)),
    )

    try:
        pygame_combat.present_death(ctx)
    except pygame_combat.PygameCombatUnavailable:
        pass
    else:
        raise AssertionError("death frame must require the shared runtime")


def test_combat_present_death_paints_full_surface_without_hud_or_log(monkeypatch):
    """The death frame fills the whole surface — no HUD, no log band."""
    class FakeFont:
        def get_linesize(self):
            return 24

    class FakePygame:
        class font:
            @staticmethod
            def Font(_path, _size):
                return FakeFont()

    class Surface:
        def __init__(self):
            self.size = (1600, 960)
            self.filled = None

        def get_size(self):
            return self.size

        def fill(self, color):
            self.filled = color

    surface = Surface()
    presented = []
    engine = SimpleNamespace(
        pygame=FakePygame,
        logical_surface=surface,
        present=lambda: presented.append(1),
    )
    ctx = SimpleNamespace(
        context=SimpleNamespace(_runtime=SimpleNamespace(engine=engine)),
    )
    drawn = []
    monkeypatch.setattr(
        pygame_ui, "draw_centered_text",
        lambda _pygame, _screen, _font, text, _rect, _y, **_kwargs: drawn.append(text),
    )
    monkeypatch.setattr(pygame_menu, "_font_path", lambda _pygame: None)

    pygame_combat.present_death(ctx, lines=("YOU DIED", "You collapse."))

    assert surface.filled == (40, 0, 0)
    assert presented == [1]
    assert "YOU DIED" in drawn
    assert "You collapse." in drawn
    assert "Press any key to return to the main menu" in drawn


def test_render_death_screen_presents_full_screen_and_waits_for_key(monkeypatch):
    from src.spacehack.combat import _encounter

    calls = []
    monkeypatch.setattr(
        pygame_combat, "present_death",
        lambda ctx, lines=(): calls.append((ctx, lines)),
    )
    key_down = pygame_engine.PygameInputEvent(kind="keydown", key_name="a")
    ctx = SimpleNamespace(
        context=SimpleNamespace(wait_events=lambda: (key_down,)),
    )
    _encounter._render_death_screen(ctx)

    assert calls == [(ctx, ())]


def test_ground_defeat_shows_full_screen_death_frame(monkeypatch):
    from src.spacehack import __main__ as game_main
    from src.spacehack.combat import _encounter
    from src.spacehack.combat._types import CombatResult

    ctx = SimpleNamespace(
        player=SimpleNamespace(pos=SimpleNamespace(x=1, y=1)),
        log=SimpleNamespace(add=lambda _message: None),
    )
    game_map = SimpleNamespace(sight_radius=8)
    console = object()
    hostiles = [SimpleNamespace()]
    shown = []
    monkeypatch.setattr(
        "src.spacehack.ground_npcs.move_ground_npcs", lambda *args: None,
    )
    monkeypatch.setattr(
        "src.spacehack.dungeon.reveal_around", lambda *args, **kwargs: None,
    )
    monkeypatch.setattr(_encounter, "detect_ground_combat", lambda *args: hostiles)
    monkeypatch.setattr(game_main, "_ground_init", lambda *args, **kwargs: None)
    monkeypatch.setattr(
        game_main, "_run_combat_unified",
        lambda *args: CombatResult(outcome="DEFEAT"),
    )
    monkeypatch.setattr(game_main, "_apply_ground_combat_rep", lambda *args: None)
    monkeypatch.setattr(
        game_main.tutorial_module, "maybe_ground_combat_intro", lambda *args: None,
    )
    monkeypatch.setattr(
        game_main.tutorial_module, "notify_ground_combat_ended", lambda *args: None,
    )
    monkeypatch.setattr(
        _encounter, "_render_death_screen",
        lambda ctx, **kwargs: shown.append((ctx, kwargs)),
    )

    result = game_main._run_ground_combat_tick(ctx, console, game_map)

    assert result.outcome == "DEFEAT"
    assert shown and shown[0][0] is ctx
    assert shown[0][1]["lines"] == ("YOU DIED", "You collapse from your wounds.")


def test_navigation_capture_builds_native_data_without_legacy_renderer(monkeypatch):
    system = SimpleNamespace(
        id="test", name="Test", width=200, height=140, stars=(),
        planets=(), jump_points=(), stations=(),
    )
    monkeypatch.setattr(
        "src.spacehack.solar_system.current_system",
        lambda: system,
    )
    monkeypatch.setattr(
        pygame_navigation.solar_system_module,
        "reachable_system_ids",
        lambda _system_id: {},
    )
    monkeypatch.setattr(
        "src.spacehack.navigation.render_navigation",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(
            AssertionError("native map must not call the legacy renderer")
        ),
    )

    frame = pygame_navigation._capture(SimpleNamespace(), SimpleNamespace(x=1, y=1))

    assert frame.title == "NAVIGATION - TEST"
    assert frame.markers[-1].tag == "YOU"


def test_navigation_native_frame_builds_tagged_plot_data(monkeypatch):
    from src.spacehack import solar_system

    system = SimpleNamespace(
        id="test",
        name="Test",
        width=200,
        height=140,
        stars=((10, 20),),
        planets=(
            SimpleNamespace(
                name="Sun", pos=SimpleNamespace(x=100, y=70),
                width=5, height=5, fg=(255, 220, 130), sun=True,
            ),
            SimpleNamespace(
                name="Earth", pos=SimpleNamespace(x=40, y=50),
                width=3, height=3, fg=(130, 195, 230), sun=False,
            ),
        ),
        jump_points=(SimpleNamespace(
            name="Vega Gate", pos=SimpleNamespace(x=190, y=100),
            width=2, height=2, fg=(245, 215, 110),
        ),),
        stations=(),
    )
    monkeypatch.setattr(
        "src.spacehack.navigation.render_navigation",
        lambda console, *_args, **_kwargs: None,
    )
    monkeypatch.setattr(solar_system, "current_system", lambda: system)
    monkeypatch.setattr(
        pygame_navigation.solar_system_module,
        "reachable_system_ids",
        lambda _system_id: {},
    )

    frame = pygame_navigation._capture(SimpleNamespace(), SimpleNamespace(x=12, y=14))

    assert frame.map_width == 200
    assert frame.map_height == 140
    assert frame.stars == ((10, 20),)
    assert [marker.tag for marker in frame.markers] == ["S1", "P1", "G1", "YOU"]
    assert frame.markers[-1].kind == "ship"
    assert frame.aoi_sections[0].title == "STARS"
    assert frame.aoi_sections[1].rows[0].detail.endswith("u")
    assert any(section.title == "JUMP GATES" for section in frame.aoi_sections)


def test_navigation_plot_projection_scales_body_coordinates():
    marker = pygame_navigation.NavigationMarker(
        "P1", "Earth", "planet", 100, 70, 3, 3, (1, 2, 3),
    )
    point = pygame_navigation._plot_point(
        marker, pygame_ui.Rect(100, 50, 400, 280), 200, 140,
    )

    assert point == (303, 193)


def test_navigation_marker_labels_are_above_small_objects():
    marker = pygame_navigation.NavigationMarker(
        "P1", "Earth", "planet", 100, 70, 1, 1, (1, 2, 3),
    )
    plot = pygame_ui.Rect(100, 50, 400, 280)

    x, y = pygame_navigation._marker_label_position(
        marker, plot, 200, 140, _FakeFont(),
    )
    center_x, center_y = pygame_navigation._plot_point(marker, plot, 200, 140)

    assert abs((x + _FakeFont().size(marker.tag)[0] // 2) - center_x) <= 1
    assert y + _FakeFont().get_linesize() < center_y


def test_navigation_marker_labels_fall_below_objects_at_top_edge():
    marker = pygame_navigation.NavigationMarker(
        "S1", "Sol", "star", 0, 0, 1, 1, (1, 2, 3),
    )
    plot = pygame_ui.Rect(100, 50, 400, 280)

    _x, y = pygame_navigation._marker_label_position(
        marker, plot, 200, 140, _FakeFont(),
    )

    _center_x, center_y = pygame_navigation._plot_point(marker, plot, 200, 140)
    assert y > center_y


def test_footer_rows_leave_exit_text_inside_hud_bounds():
    from src.spacehack import hud

    xp_y, bump_y, exit_y = hud._footer_rows(54)

    assert (xp_y, bump_y, exit_y) == (50, 51, 52)
    assert exit_y < 54


def test_modal_footer_geometry_leaves_clearance_above_log_panel():
    from src.spacehack import pygame_ui

    height = 960
    boundary = pygame_ui.modal_footer_y(height)

    assert boundary == height - pygame_ui.LOG_PANEL_HEIGHT - pygame_ui.FOOTER_PAD
    # A hint drawn at modal_footer_text_y has its bottom at the boundary, so
    # its ink never reaches the console-log panel border.
    line_height = 40
    hint_y = pygame_ui.modal_footer_text_y(height, line_height)
    assert hint_y == boundary - line_height
    assert hint_y + line_height <= height - pygame_ui.LOG_PANEL_HEIGHT


def test_animation_timing_is_slightly_faster_than_previous_defaults():
    assert animation_timing.COMBAT_BEAM < 0.05
    assert animation_timing.COMBAT_IMPACT < 0.06
    assert animation_timing.JUMP < 0.06
    assert animation_timing.CITY_TRANSITION < 0.08
    assert animation_timing.DUNGEON_BREACH < 0.08


def test_combat_presentation_is_always_enabled():
    assert pygame_combat.enabled()
    assert pygame_ui.presentation_enabled()


def test_guide_key_accepts_unicode_question_mark_without_k_question():
    """Shift+/ arrives as K_SLASH with unicode '?' on most keyboards,
    so the guide key must match the unicode fallback, not only the
    (usually absent) K_QUESTION keycode.
    """
    class FakePygame:
        KEYDOWN = 2
        # No K_QUESTION attribute — the SDL2 keyboards that fire
        # shift+/ as K_SLASH never deliver a dedicated question key.

    fake = FakePygame()
    slash = SimpleNamespace(type=fake.KEYDOWN, key=47, unicode="?")
    plain_slash = SimpleNamespace(type=fake.KEYDOWN, key=47, unicode="")
    non_keydown = SimpleNamespace(type=99, key=47, unicode="?")

    assert pygame_ui.is_guide_key(fake, slash) is True
    assert pygame_ui.is_guide_key(fake, plain_slash) is False
    assert pygame_ui.is_guide_key(fake, non_keydown) is False

    class WithQuestionKey(FakePygame):
        K_QUESTION = 14

    assert pygame_ui.is_guide_key(
        WithQuestionKey(),
        SimpleNamespace(type=fake.KEYDOWN, key=14, unicode=""),
    ) is True


def test_quantity_key_mapping_clamps_and_confirms():
    class FakePygame:
        QUIT = 1
        KEYDOWN = 2
        K_ESCAPE = 10
        K_QUESTION = 11
        K_UP = 12
        K_DOWN = 13
        K_k = 14
        K_j = 15
        K_RETURN = 16
        K_KP_ENTER = 17
        K_PLUS = 18
        K_EQUALS = 19
        K_MINUS = 20

    fake = FakePygame()
    key = lambda value: SimpleNamespace(type=fake.KEYDOWN, key=value)

    assert pygame_quantity._handle_key(fake, key(fake.K_UP), 1, 2) == ("IGNORE", 2)
    assert pygame_quantity._handle_key(fake, key(fake.K_UP), 2, 2) == ("IGNORE", 2)
    assert pygame_quantity._handle_key(fake, key(fake.K_DOWN), 1, 2) == ("IGNORE", 1)
    assert pygame_quantity._handle_key(fake, key(fake.K_RETURN), 2, 2) == ("CONFIRM", 2)
    assert pygame_quantity._handle_key(fake, key(fake.K_ESCAPE), 1, 2) == ("BACK", 1)
    assert pygame_quantity._handle_key(fake, SimpleNamespace(type=fake.QUIT), 1, 2) == ("QUIT", 1)


def test_quantity_worker_propagates_quit(monkeypatch):
    monkeypatch.setattr(
        pygame_ui,
        "run_json_worker",
        lambda *args, **kwargs: {"outcome": "QUIT", "quantity": 1},
    )

    try:
        pygame_quantity.run(SimpleNamespace(), "Buy", 3, 10)
    except pygame_quantity.PygameQuantityQuit:
        pass
    else:
        raise AssertionError("quantity window close must remain distinct from cancel")


def test_quantity_worker_rejects_invalid_confirmed_amount(monkeypatch):
    monkeypatch.setattr(
        pygame_ui,
        "run_json_worker",
        lambda *args, **kwargs: {"outcome": "CONFIRM", "quantity": 8},
    )

    try:
        pygame_quantity.run(SimpleNamespace(), "Buy", 3, 10)
    except pygame_quantity.PygameQuantityUnavailable as exc:
        assert "invalid quantity" in str(exc)
    else:
        raise AssertionError("quantity worker must reject out-of-range values")


def test_goto_menu_pygame_maps_destination_index(monkeypatch):
    from src.spacehack import pygame_menu

    destinations = [
        ("Mars", SimpleNamespace(name="Mars", description="Red world.")),
        ("[Gate] Sirius", SimpleNamespace(name="Sirius gate", description="A stable gate.")),
    ]
    captured = {}

    def fake_run(frames, **kwargs):
        captured["frames"] = frames
        return ("SELECT", "DEST:1", 1)

    monkeypatch.setattr(pygame_menu, "run_for_context", lambda _context, frames, **kwargs: fake_run(frames, **kwargs))

    assert navigation._run_pygame_goto_menu(SimpleNamespace(context=object()), destinations) == (True, 1)
    assert captured["frames"][1].items[1].action == "DEST:1"
    assert captured["frames"][1].items[1].description == "A stable gate."


def test_goto_menu_pygame_back_is_handled_as_cancel(monkeypatch):
    from src.spacehack import pygame_menu

    monkeypatch.setattr(
        pygame_menu,
        "run_for_context",
        lambda *args, **kwargs: ("BACK", "", 0),
    )

    assert navigation._run_pygame_goto_menu(
        SimpleNamespace(context=object()), [("Mars", SimpleNamespace(name="Mars"))],
    ) == (True, None)


def test_goto_menu_pygame_unavailable_is_explicit(monkeypatch):
    from src.spacehack import pygame_menu

    monkeypatch.setattr(
        pygame_menu,
        "run_for_context",
        lambda *args, **kwargs: (_ for _ in ()).throw(
            pygame_menu.PygameMenuUnavailable("missing")
        ),
    )

    try:
        navigation._run_pygame_goto_menu(
            SimpleNamespace(context=object()), [("Mars", SimpleNamespace(name="Mars"))],
        )
    except pygame_menu.PygameMenuUnavailable as exc:
        assert str(exc) == "missing"
    else:
        raise AssertionError("unavailable shared menus must not fall back to the legacy console")


def test_jump_menu_pygame_maps_opaque_action(monkeypatch):
    from src.spacehack import pygame_menu

    jump = SimpleNamespace(name="Gate", description="A stable gate.")
    monkeypatch.setattr(
        pygame_menu,
        "run_for_context",
        lambda _context, frames, **kwargs: ("SELECT", "JUMP", 0),
    )
    monkeypatch.setattr(
        navigation.solar_systems_module,
        "find_solar_system",
        lambda _system_id: SimpleNamespace(name="Sirius"),
    )

    assert navigation._run_pygame_jump_menu(
        SimpleNamespace(context=object()), jump, "sirius", 20, 30,
    ) is navigation.JumpMenuOutcome.JUMP


def test_npc_trade_frame_uses_opaque_buy_and_sell_actions():
    from src.spacehack import trade

    npc = SimpleNamespace(name="Trader")
    ctx = SimpleNamespace(
        player_owned_ship=SimpleNamespace(
            ship_id="starter", inventory={"food_rations": 2}, cargo_used=2,
        ),
        stats=SimpleNamespace(credits=100),
    )
    frame = trade._pygame_npc_trade_frame(
        ctx, npc, {"food_rations": 3}, 1.2, 0.5,
    )

    assert frame.left_rows[0].action == "BUY_NPC:food_rations"
    assert frame.right_rows[0].action == "SELL_NPC:food_rations"


def test_npc_trade_frame_uses_shared_content_policy():
    from src.spacehack import trade

    npc = SimpleNamespace(name="Trader")
    ctx = SimpleNamespace(
        player_owned_ship=SimpleNamespace(
            ship_id="starter", inventory={"food_rations": 2}, cargo_used=2,
        ),
        stats=SimpleNamespace(credits=100),
    )
    frame = trade._pygame_npc_trade_frame(
        ctx, npc, {"food_rations": 3}, 1.2, 0.5,
    )

    assert frame.title == "TRADE - TRADER"
    assert frame.footer_left == "Credits: 100$"
    assert frame.footer_right == "Cargo: 2/20"
    assert frame.hint == pygame_split.SPLIT_SHOP_HINT
    assert frame.left_rows[0].value == "24$ (3)"
    assert frame.right_rows[0].value == "(sell 10$) x2"


def test_hold_cargo_label_formats_used_and_capacity():
    from src.spacehack import trade

    owned = SimpleNamespace(ship_id="starter", cargo_used=2)
    assert trade._hold_cargo_label(owned) == "Cargo: 2/20"
    assert trade._hold_cargo_label(None) == "Cargo: 0/0"


def test_station_trade_frame_uses_shared_content_policy(monkeypatch):
    from src.spacehack import trade

    ctx = SimpleNamespace(
        player_owned_ship=SimpleNamespace(
            ship_id="starter", inventory={"food_rations": 2}, cargo_used=2,
        ),
        stats=SimpleNamespace(credits=1000),
        economy_state={},
    )
    monkeypatch.setattr(trade, "_unit_price", lambda _ctx, _planet, _gid: 30)
    monkeypatch.setattr(trade, "_sell_price", lambda _ctx, _planet, _gid: 15)

    frame = trade._pygame_trade_frame(ctx, "earth", ("food_rations",))

    assert frame.title == "TRADE - EARTH"
    assert frame.footer_left == "Credits: 1000$"
    assert frame.footer_right == "Cargo: 2/20"
    assert frame.hint == pygame_split.SPLIT_SHOP_HINT
    assert frame.left_rows[0].value == "30$ (0)"
    assert frame.right_rows[0].value == "(sell 15$) x2"


def test_loot_parent_apply_removes_entity_and_grants_inventory():
    from src.spacehack import loot

    entity = SimpleNamespace(loot_data={"good_id": "food_rations", "quantity": 2})
    owned = SimpleNamespace(inventory={}, mission_reserved=0)
    ctx = SimpleNamespace(
        player_owned_ship=owned,
        game_map=SimpleNamespace(entities=[entity]),
        log=SimpleNamespace(add=lambda _message: None),
    )
    good = SimpleNamespace(name="Food")

    loot._apply_loot_pickup(ctx, entity, owned, False, [], "food", 2, good)

    assert owned.inventory == {"food": 2}
    assert entity not in ctx.game_map.entities


def test_screen_frame_payload_round_trips_page_offset_and_rows():
    frame = pygame_screen.ScreenFrame(
        "Guide", ("body",),
        (pygame_screen.ScreenRow("Pick", "Details", "ACTION"),),
        ("ESC close",), 0, 4,
    )

    assert pygame_screen._frame_from_payload(
        pygame_screen._frame_payload(frame),
    ) == frame


def test_screen_key_mapping_supports_tabs_and_paging():
    class FakePygame:
        QUIT = 1
        KEYDOWN = 2
        K_ESCAPE = 10
        K_TAB = 11
        K_PAGEDOWN = 12
        K_PAGEUP = 13
        K_QUESTION = 14
        K_UP = 15
        K_DOWN = 16
        K_k = 17
        K_j = 18
        K_RETURN = 19
        K_KP_ENTER = 20

    fake = FakePygame()
    frame = pygame_screen.ScreenFrame(
        "T", (), (pygame_screen.ScreenRow("row", action="A"),),
    )
    key = lambda value: SimpleNamespace(type=fake.KEYDOWN, key=value)

    assert pygame_screen._handle_key(fake, key(fake.K_TAB), frame) == ("TAB", 0)
    assert pygame_screen._handle_key(fake, key(fake.K_PAGEDOWN), frame) == ("PAGE_DOWN", 0)
    assert pygame_screen._handle_key(fake, key(fake.K_PAGEUP), frame) == ("PAGE_UP", 0)


def test_scrollable_body_scrolls_with_vim_keys_and_arrows():
    class FakePygame:
        QUIT = 1
        KEYDOWN = 2
        K_ESCAPE = 10
        K_TAB = 11
        K_PAGEDOWN = 12
        K_PAGEUP = 13
        K_QUESTION = 14
        K_UP = 15
        K_DOWN = 16
        K_k = 17
        K_j = 18
        K_RETURN = 19
        K_KP_ENTER = 20

    fake = FakePygame()
    key = lambda value: SimpleNamespace(type=fake.KEYDOWN, key=value)
    scrollable = pygame_screen.ScreenFrame(
        "T", ("long body " * 200,), (), scrollable=True,
    )

    assert pygame_screen._handle_key(fake, key(fake.K_j), scrollable) == ("PAGE_DOWN", 0)
    assert pygame_screen._handle_key(fake, key(fake.K_DOWN), scrollable) == ("PAGE_DOWN", 0)
    assert pygame_screen._handle_key(fake, key(fake.K_k), scrollable) == ("PAGE_UP", 0)
    assert pygame_screen._handle_key(fake, key(fake.K_UP), scrollable) == ("PAGE_UP", 0)

    # Non-scrollable frames keep the old no-op behavior.
    plain = pygame_screen.ScreenFrame("T", ("long body " * 200,), ())
    assert pygame_screen._handle_key(fake, key(fake.K_j), plain) == ("IGNORE", 0)

    # Scrollable frames with selectable rows keep row navigation.
    rows = (
        pygame_screen.ScreenRow("a", selectable=True),
        pygame_screen.ScreenRow("b", selectable=True),
    )
    with_rows = pygame_screen.ScreenFrame("T", (), rows, scrollable=True)
    assert pygame_screen._handle_key(fake, key(fake.K_j), with_rows) == ("IGNORE", 1)
    # Row navigation wins over scrolling (wraps from row 0 to row 1).
    assert pygame_screen._handle_key(fake, key(fake.K_k), with_rows) == ("IGNORE", 1)


def test_fit_text_uses_renderer_metrics_and_ascii_ellipsis():
    font = _FakeFont()

    assert pygame_ui.fit_text("short", 60, lambda text: font.size(text)[0]) == "short"
    assert pygame_ui.fit_text("long mission title", 100, lambda text: font.size(text)[0]) == "long mi..."
    assert pygame_ui.fit_text("long", 20, lambda text: font.size(text)[0]) == "..."
    assert pygame_ui.fit_text("long", 0, lambda text: font.size(text)[0]) == ""


def test_wrap_text_uses_font_width_and_preserves_paragraph_breaks():
    font = _FakeFont()
    measure = lambda text: font.size(text)[0]

    assert pygame_ui.wrap_text("one two three", 80, measure) == ("one two", "three")
    assert pygame_ui.wrap_text("one\n\ntwo", 100, measure) == ("one", "", "two")
    assert pygame_ui.wrap_text("abcdefgh", 30, measure) == ("abc", "def", "gh")
    assert pygame_ui.wrap_text("", 100, measure) == ()


def test_pygame_comms_preserves_distress_beacon_line_breaks(monkeypatch):
    from src.spacehack import comms

    captured = {}
    contact_spec = SimpleNamespace(
        comms_lines=("BEACON LINE ONE", "BEACON LINE TWO", "BEACON LINE THREE"),
    )
    menu = __import__("src.spacehack.pygame_menu", fromlist=["MenuFrame"])

    def fake_run(_context, frames, **_kwargs):
        captured["frame"] = frames[0]
        return "BACK", "", 0

    monkeypatch.setattr(menu, "run_for_context", fake_run)
    monkeypatch.setattr(comms, "_INTERACTION_DISPATCH", {})

    result = comms._pygame_interaction_outcome(
        SimpleNamespace(context=object()),
        "Derelict Scout",
        contact_spec,
        ["End Transmission"],
    )

    assert result is comms._InteractionOutcome.BACK
    assert captured["frame"].body == (
        "BEACON LINE ONE\nBEACON LINE TWO\nBEACON LINE THREE"
    )


def test_open_comms_accepts_contact_tuple_with_unhashable_entity(monkeypatch):
    """Regression: a selected contact is a ``(name, spec, entity)`` tuple
    whose ``entity`` is an unhashable ``world.Entity``. The sentinel check
    must compare (tuple membership) instead of hashing (set membership),
    which crashed with ``TypeError: unhashable type: 'Entity'``.
    """
    from src.spacehack import comms
    from src.spacehack.world import Entity, Position

    entity = Entity(
        char="P", fg=(255, 0, 0), pos=Position(1, 1), npc_ship_id="pirate_scout",
    )
    contact = ("Pirate Scout", SimpleNamespace(comms_lines=()), entity)
    ctx = SimpleNamespace(
        game_map=SimpleNamespace(entities=[]),
        faction_reputation={},
        log=SimpleNamespace(add=lambda _message: None),
        context=object(),
    )
    hailed = {}

    monkeypatch.setattr(comms, "_scan_contacts", lambda _ctx, _player_pos: [contact])
    monkeypatch.setattr(
        comms,
        "_run_interaction_modal",
        lambda _ctx, _console, name, spec, ent: hailed.update(
            name=name, spec=spec, ent=ent,
        ),
    )

    # A selected contact tuple (unhashable entity inside) must NOT crash
    # the sentinel check — it proceeds to hail the contact.
    monkeypatch.setattr(comms, "_pygame_contact_result", lambda _ctx, _contacts: contact)
    assert comms.open_comms(ctx, SimpleNamespace(x=0, y=0)) is None
    assert hailed["ent"] is entity

    # Every sentinel short-circuits without invoking the interaction modal.
    for sentinel in ("QUIT", "BACK", None):
        monkeypatch.setattr(
            comms,
            "_pygame_contact_result",
            lambda _ctx, _contacts, _s=sentinel: _s,
        )
        assert comms.open_comms(ctx, SimpleNamespace(x=0, y=0)) is None
        assert hailed == {
            "name": "Pirate Scout", "spec": contact[1], "ent": entity,
        }


def test_merchant_frame_uses_live_content_and_selected_details():
    offerings = (
        SimpleNamespace(
            title="Deliver to Mars",
            description="Food crates for Mars.",
            reward_credits=100,
            reward_xp=20,
            recommended_class_id="merchant",
            recommended_ship_min_cargo=5,
        ),
        SimpleNamespace(
            title="Deliver to Sirius",
            description="Medical supplies for Sirius.",
            reward_credits=400,
            reward_xp=50,
            recommended_class_id=None,
            recommended_ship_min_cargo=0,
        ),
    )
    npc = SimpleNamespace(name="Guild Master")

    frame = pygame_merchant._frame_for(
        npc,
        offerings,
        3,
        lambda mission: f"[Delivery] {mission.title} @ Sol ({mission.reward_credits}$)",
        lambda class_id: "Merchant",
    )

    assert frame.title == "Guild Master - available work"
    assert frame.options == (
        "[Delivery] Deliver to Mars @ Sol (100$)",
        "[Delivery] Deliver to Sirius @ Sol (400$)",
    )
    assert frame.selected == 1
    assert frame.description == "Medical supplies for Sirius."
    assert frame.hints == (
        "UP/DOWN navigate   ENTER accept   ESC walk away",
        "Reward: 400$ + 50xp",
    )


def test_default_merchant_window_matches_game_canvas():
    assert pygame_merchant._default_screen_size() == (1600, 960)


def test_merchant_layout_matches_game_canvas_and_keeps_content_inside_panel():
    layout = pygame_merchant._merchant_layout(1600, 960, 34)

    assert layout.panel == pygame_ui.Rect(40, 32, 1520, 896)
    assert layout.content.x == layout.panel.x + 34
    assert layout.content.y > layout.rule_y
    assert layout.content.x + layout.content.width < layout.panel.x + layout.panel.width
    assert layout.content.y + layout.content.height < layout.panel.y + layout.panel.height


def test_font_fit_uses_each_candidate_font_metrics(monkeypatch):
    class FakePygame:
        class font:
            @staticmethod
            def Font(_path, size):
                return SimpleNamespace(
                    get_linesize=lambda: size + 20,
                    size=lambda text: (len(text) * size, size),
                )

    frame = pygame_merchant.MerchantFrame(
        "title",
        ("row",),
        "description",
        ("hint",),
        0,
    )
    font = pygame_merchant._fit_font(
        FakePygame,
        None,
        24,
        (frame,),
        1600,
        960,
    )

    assert font.get_linesize() == 44


def test_worker_payload_carries_display_configuration():
    frame = pygame_merchant.MerchantFrame("title", ("row",), "desc", ("hint",), 0)

    payload = pygame_merchant._worker_payload((frame,), (1600, 960), 24, True)

    assert payload["screen_size"] == (1600, 960)
    assert payload["font_size"] == 24
    assert payload["antialias"] is True
    assert payload["frames"][0]["options"] == ("row",)


def test_merchant_key_mapping_matches_existing_modal_contract():
    class FakePygame:
        QUIT = 1
        KEYDOWN = 2
        K_ESCAPE = 10
        K_RETURN = 11
        K_KP_ENTER = 12
        K_UP = 13
        K_DOWN = 14
        K_k = 15
        K_j = 16

    fake = FakePygame()
    assert pygame_merchant._handle_key(fake, SimpleNamespace(type=fake.QUIT), 0, 3) == ("QUIT", 0)
    assert pygame_merchant._handle_key(fake, SimpleNamespace(type=fake.KEYDOWN, key=fake.K_UP), 0, 3) == ("IGNORE", 2)
    assert pygame_merchant._handle_key(fake, SimpleNamespace(type=fake.KEYDOWN, key=fake.K_DOWN), 2, 3) == ("IGNORE", 0)
    assert pygame_merchant._handle_key(
        fake,
        SimpleNamespace(type=fake.KEYDOWN, key=fake.K_RETURN),
        1,
        3,
    ) == ("ACCEPT", 1)
    assert pygame_merchant._handle_key(fake, SimpleNamespace(type=fake.KEYDOWN, key=fake.K_ESCAPE), 1, 3) == ("BACK", 1)
    assert pygame_merchant._handle_key(fake, SimpleNamespace(type=99, key=0), 1, 3) == ("IGNORE", 1)


def test_json_worker_rejects_nonzero_worker_exit(monkeypatch):
    monkeypatch.setattr(
        pygame_ui.subprocess,
        "run",
        lambda *args, **kwargs: SimpleNamespace(returncode=2, stdout=""),
    )

    try:
        pygame_ui.run_json_worker(
            ["python"],
            {},
            unavailable_message="unavailable",
        )
    except pygame_ui.PygameWorkerUnavailable as exc:
        assert str(exc) == "unavailable"
    else:
        raise AssertionError("nonzero worker exits must use the fallback path")


def test_json_worker_returns_last_json_line_and_uses_supplied_environment(monkeypatch):
    captured = {}

    def fake_run(command, **kwargs):
        captured["command"] = command
        captured.update(kwargs)
        return SimpleNamespace(returncode=0, stdout="worker noise\n{\"outcome\": \"BACK\"}\n")

    monkeypatch.setattr(pygame_ui.subprocess, "run", fake_run)

    result = pygame_ui.run_json_worker(
        ["python", "-m", "worker"],
        {"value": 1},
        unavailable_message="unavailable",
        environment={"TEST": "1"},
    )

    assert result == {"outcome": "BACK"}
    assert captured["command"] == ["python", "-m", "worker"]
    assert captured["env"] == {"TEST": "1"}
    assert captured["input"] == '{"value": 1}'


def test_captured_quest_rows_merge_cells_by_color():
    capture = pygame_world.CaptureConsole(6, 1)
    capture.print(x=0, y=0, string="AB", fg=(1, 2, 3))
    capture.print(x=2, y=0, string="CD", fg=(4, 5, 6))

    assert pygame_quest_log._captured_rows(capture) == (
        (
            pygame_quest_log.QuestSpan("AB", (1, 2, 3)),
            pygame_quest_log.QuestSpan("CD", (4, 5, 6)),
        ),
    )


def test_ship_buy_frame_uses_modern_screen_contract_with_live_price():
    ship = SimpleNamespace(
        name="Scout", description="Fast courier.", price=5000,
    )
    ctx = SimpleNamespace(stats=SimpleNamespace(credits=2000))

    frame = _ship_buy._ship_buy_frame(ctx, ship, None, 0)

    assert frame.title == "SCOUT - FOR SALE"
    assert frame.body == ("Fast courier.", "You are 3000$ short of the asking price.")
    assert frame.rows[0].text == "Buy the Scout - 5000$"
    assert "5000$" in frame.rows[0].detail
    assert "3000$" in frame.rows[0].detail
    assert "Credits: 2000$" in frame.rows[0].detail
    assert frame.rows[0].action == "BUY"
    assert frame.footer == ("ENTER buy   ESC walk away   ? guide",)
    assert "? guide" in frame.footer[0]


def test_ship_buy_frame_shows_trade_in_and_affordability():
    ship = SimpleNamespace(
        name="Freighter", description="Big hold.", price=8000,
    )
    ctx = SimpleNamespace(stats=SimpleNamespace(credits=6000))

    frame = _ship_buy._ship_buy_frame(ctx, ship, 5000, 0)

    assert any("Trade-in value: 3000$" in line for line in frame.body)
    assert any("Credits: 6000$" in line for line in frame.body)
    assert frame.rows[0].text == "Buy the Freighter - 5000$"
    assert "5000$" in frame.rows[0].detail
    assert "short" not in frame.rows[0].detail.lower()


def test_ship_buy_pygame_maps_buy_expensive_and_guide(monkeypatch):
    from src.spacehack import pygame_screen

    ship = SimpleNamespace(name="Scout", description="Fast.", price=5000)
    outcomes = iter((("GUIDE", "", 0), ("SELECT", "BUY", 0)))
    captured = {}

    def fake_run(_context, frame, **_kwargs):
        captured["frame"] = frame
        return next(outcomes)

    monkeypatch.setattr(pygame_screen, "run_for_context", fake_run)
    monkeypatch.setattr("src.spacehack.help._open_context_guide", lambda _ctx, _topic: None)

    ctx = SimpleNamespace(
        context=object(),
        stats=SimpleNamespace(credits=6000),
    )
    assert _ship_buy._run_pygame_ship_buy(ctx, ship, None) is _ship_buy.ShipBuyOutcome.BUY
    assert captured["frame"].title == "SCOUT - FOR SALE"

    monkeypatch.setattr(
        pygame_screen,
        "run_for_context",
        lambda _context, _frame, **_kwargs: ("SELECT", "BUY", 0),
    )
    poor_ctx = SimpleNamespace(
        context=object(),
        stats=SimpleNamespace(credits=100),
    )
    assert _ship_buy._run_pygame_ship_buy(
        poor_ctx, ship, None,
    ) is _ship_buy.ShipBuyOutcome.TOO_EXPENSIVE

    monkeypatch.setattr(
        pygame_screen,
        "run_for_context",
        lambda _context, _frame, **_kwargs: ("BACK", "", 0),
    )
    assert _ship_buy._run_pygame_ship_buy(
        SimpleNamespace(context=object(), stats=SimpleNamespace(credits=6000)),
        ship, None,
    ) is _ship_buy.ShipBuyOutcome.BACK


def test_pygame_presentation_is_enabled_without_migration_flags():
    assert pygame_menu.enabled()
    assert pygame_ui.presentation_enabled()


def test_quest_frame_payload_round_trips_text_colors_and_state():
    frame = pygame_quest_log.QuestFrame(
        rows=((pygame_quest_log.QuestSpan("> Mission", (255, 255, 255)),),),
        selected=2,
        confirm_abandon=True,
    )

    payload = pygame_quest_log._worker_payload((frame,))
    restored = pygame_quest_log._frame_from_payload(
        payload["frames"][pygame_quest_log._frame_key(2, True)]
    )

    assert restored == frame


def test_quest_key_mapping_preserves_navigation_and_confirmation_contract():
    class FakePygame:
        QUIT = 1
        KEYDOWN = 2
        K_ESCAPE = 10
        K_UP = 11
        K_DOWN = 12
        K_k = 13
        K_j = 14
        K_a = 15
        K_RETURN = 16
        K_KP_ENTER = 17
        K_QUESTION = 18

    fake = FakePygame()
    key = lambda value: SimpleNamespace(type=fake.KEYDOWN, key=value)

    assert pygame_quest_log._handle_key(fake, key(fake.K_UP), 0, False, 3) == ("IGNORE", 2, False)
    assert pygame_quest_log._handle_key(fake, key(fake.K_a), 1, False, 3) == ("IGNORE", 1, True)
    assert pygame_quest_log._handle_key(fake, key(fake.K_RETURN), 1, True, 3) == ("ABANDONED", 1, True)
    assert pygame_quest_log._handle_key(fake, key(fake.K_ESCAPE), 1, True, 3) == ("BACK", 1, True)
    assert pygame_quest_log._handle_key(fake, key(fake.K_QUESTION), 1, False, 3) == ("GUIDE", 1, False)
    assert pygame_quest_log._handle_key(fake, SimpleNamespace(type=fake.QUIT), 1, False, 3) == ("QUIT", 1, False)


def test_empty_quest_log_uses_a_non_abandonable_worker_state():
    frame = pygame_quest_log.QuestFrame(rows=((),), selected=-1, confirm_abandon=False)
    payload = pygame_quest_log._worker_payload((frame,))

    assert pygame_quest_log._frame_key(-1, False) in payload["frames"]



def test_batch_frame_payload_round_trips_text_and_colors():
    frame = pygame_batch.BatchFrame(
        rows=((pygame_quest_log.QuestSpan("NAVIGATION", (1, 2, 3)),),),
        key="readonly",
    )

    restored = pygame_batch._frame_from_payload(
        pygame_batch.frame_payload(frame)["frame"]
    )

    assert restored == frame


def test_batch_key_mapping_preserves_read_only_modal_contract():
    class FakePygame:
        QUIT = 1
        KEYDOWN = 2
        K_ESCAPE = 10
        K_QUESTION = 11

    fake = FakePygame()
    key = lambda value: SimpleNamespace(type=fake.KEYDOWN, key=value)

    assert pygame_batch._handle_key(fake, SimpleNamespace(type=fake.QUIT)) == "QUIT"
    assert pygame_batch._handle_key(fake, key(fake.K_ESCAPE)) == "BACK"
    assert pygame_batch._handle_key(fake, key(fake.K_QUESTION)) == "GUIDE"
    assert pygame_batch._handle_key(fake, SimpleNamespace(type=99, key=0)) == "IGNORE"



def test_read_only_batch_presentation_is_enabled():
    assert pygame_batch.enabled()


def test_split_font_budget_is_stable_across_dense_and_sparse_frames():
    sparse = pygame_split.SplitFrame(
        "ARMORY", "Storage", "Loadout",
        (pygame_split.SplitRow("One item", "", "short", "ITEM"),),
        (pygame_split.SplitRow("Weapon", "", "short", "WEAPON"),),
        "", "", "",
    )
    dense_rows = tuple(
        pygame_split.SplitRow(f"Item {index}", "", "long detail", f"ITEM:{index}")
        for index in range(pygame_split.MAX_VISIBLE_ROWS + 5)
    )
    dense = pygame_split.SplitFrame(
        "ARMORY", "Buy", "Loadout", dense_rows, sparse.right_rows, "", "", "",
    )

    class Font:
        def get_linesize(self):
            return 24

    assert pygame_split._frame_height(Font(), sparse) == pygame_split._frame_height(Font(), dense)


def test_split_frame_payload_round_trips_rows_and_selection():
    frame = pygame_split.SplitFrame(
        title="ARMORY",
        left_label="For Sale",
        right_label="My Loadout",
        left_rows=(pygame_split.SplitRow("Laser", "100$", "damage", "BUY:laser"),),
        right_rows=(pygame_split.SplitRow(
            "[empty]", "", "", "", divider=False, selectable=False,
        ),),
        footer_left="Credits: 100",
        footer_right="",
        hint="TAB switch",
        focus=0,
        selected=0,
    )

    restored = pygame_split._frame_from_payload(
        pygame_split._frame_payload(frame),
    )

    assert restored == frame
    assert restored.right_rows[0].selectable is False


def test_informational_split_rows_match_selectable_row_spacing():
    class Font:
        def get_linesize(self):
            return 24

        def size(self, text):
            return len(text) * 10, 24

        def render(self, text, _antialias, _color):
            return text

    class Screen:
        def __init__(self):
            self.blit_calls = []

        def blit(self, surface, position):
            self.blit_calls.append((surface, position))

    class Pygame:
        pass

    font = Font()
    selectable_screen = Screen()
    informational_screen = Screen()
    selectable_y = pygame_ui.draw_menu_row(
        Pygame, selectable_screen, font, "Weapon 1: Laser Pistol",
        100, 200, 400, selected=False,
    )
    informational_y = pygame_ui.draw_informational_row(
        Pygame, informational_screen, font, "Weapon 2: [empty]",
        100, 200, 400,
    )

    assert informational_y == selectable_y
    assert selectable_screen.blit_calls[0][1] == informational_screen.blit_calls[0][1]
    assert informational_screen.blit_calls[0][1] == (112, 202)


def test_split_key_mapping_skips_informational_rows():
    frame = pygame_split.SplitFrame(
        "ARMORY", "Loadout", "Owned",
        (
            pygame_split.SplitRow("Weapon 1", "", "", "WEAPON"),
            pygame_split.SplitRow(
                "Weapon 2: --- (occupied by 2H)", "", "", "", False, False,
            ),
        ),
        (), "", "", "", 0, 1,
    )

    assert pygame_split._clamp_selected(frame) == 0
    assert pygame_split._selectable_indices(frame.left_rows) == (0,)


def test_split_key_mapping_switches_panels_and_returns_opaque_action():
    class FakePygame:
        QUIT = 1
        KEYDOWN = 2
        K_ESCAPE = 10
        K_TAB = 11
        K_UP = 12
        K_DOWN = 13
        K_k = 14
        K_j = 15
        K_RETURN = 16
        K_KP_ENTER = 17
        K_b = 18
        K_s = 19

    frame = pygame_split.SplitFrame(
        "ARMORY", "Sale", "Owned",
        (pygame_split.SplitRow("Laser", "100$", "", "BUY"),),
        (pygame_split.SplitRow("Armor", "50$", "", "SELL"),),
        "", "", "", 0, 0,
    )
    fake = FakePygame()
    key = lambda value: SimpleNamespace(type=fake.KEYDOWN, key=value)

    assert pygame_split._handle_key(fake, key(fake.K_TAB), frame) == ("IGNORE", 1, 0)
    assert pygame_split._handle_key(fake, key(fake.K_RETURN), frame) == ("SELECT", 0, 0)

    tabbed = pygame_split.SplitFrame(
        "LOADOUT", "Store", "My Ship", (), (), "", "", "",
        left_tabs=("[B]uy", "[S]torage"),
    )
    assert pygame_split._handle_key(fake, key(fake.K_b), tabbed) == ("MODE:STORE", 0, 0)
    assert pygame_split._handle_key(fake, key(fake.K_s), tabbed) == ("MODE:STORAGE", 0, 0)
    assert pygame_split._handle_key(fake, SimpleNamespace(type=fake.QUIT), frame) == ("QUIT", 0, 0)


def test_split_frame_explicit_tab_modes_override_label_defaults():
    class FakePygame:
        QUIT = 1
        KEYDOWN = 2
        K_ESCAPE = 10
        K_b = 18
        K_a = 19
        K_e = 20

    frame = pygame_split.SplitFrame(
        "ARMORY", "Buy", "My Loadout", (), (), "", "", "",
        left_tabs=("[B]uy", "[A]rmory", "[E]xpedition"),
        left_tab_modes=("BUY", "ARMORY", "EXPEDITION"),
    )

    assert pygame_split._handle_key(
        FakePygame, SimpleNamespace(type=FakePygame.KEYDOWN, key=FakePygame.K_b), frame,
    ) == ("MODE:BUY", 0, 0)
    assert pygame_split._handle_key(
        FakePygame, SimpleNamespace(type=FakePygame.KEYDOWN, key=FakePygame.K_a), frame,
    ) == ("MODE:ARMORY", 0, 0)
    assert pygame_split._handle_key(
        FakePygame, SimpleNamespace(type=FakePygame.KEYDOWN, key=FakePygame.K_e), frame,
    ) == ("MODE:EXPEDITION", 0, 0)


def test_loadout_frame_exposes_buy_storage_tabs_and_active_state():
    from src.spacehack.menus import _loadout
    from src.spacehack.ship import OwnedShip

    ctx = SimpleNamespace(
        player_owned_ship=OwnedShip(ship_id="starter"),
        ship_storage=[],
        stats=SimpleNamespace(credits=321),
    )

    buy = _loadout._pygame_loadout_frame(
        ctx, weapon_ids=("light_laser",), module_ids=(), mode="STORE",
    )
    storage = _loadout._pygame_loadout_frame(
        ctx, weapon_ids=("light_laser",), module_ids=(), mode="STORAGE",
    )

    assert buy.left_tabs == ("[B]uy", "[S]torage")
    assert storage.left_tabs == buy.left_tabs
    assert buy.active_left_tab == 0
    assert storage.active_left_tab == 1
    assert buy.left_label == "Store"
    assert storage.left_label == "Storage"
    assert "B buy" in buy.hint
    assert "S storage" in storage.hint


def test_loadout_chooser_dismissal_is_a_safe_noop(monkeypatch):
    from src.spacehack import pygame_story
    from src.spacehack.menus import _loadout
    from src.spacehack.ship import OwnedShip

    messages = []
    ctx = SimpleNamespace(
        player_owned_ship=OwnedShip(
            ship_id="starter", weapons=("light_laser",),
        ),
        ship_storage=[_loadout.ship_module.StoredEquipment("module", "shield_mk1")],
        stats=SimpleNamespace(credits=1000),
        log=SimpleNamespace(add=messages.append),
    )
    monkeypatch.setattr(pygame_story, "choose", lambda *args, **kwargs: None)

    _loadout._apply_manage_stored_item(ctx, "MANAGE_STORED:0")
    _loadout._apply_manage_ship_item(ctx, "MANAGE_WEAPON_SLOT:0")

    assert ctx.stats.credits == 1000
    assert ctx.player_owned_ship.weapons == ("light_laser",)
    assert ctx.ship_storage == [_loadout.ship_module.StoredEquipment("module", "shield_mk1")]
    assert messages == []
    assert messages == []


def test_split_worker_rejects_unknown_outcomes(monkeypatch):
    monkeypatch.setattr(
        pygame_ui,
        "run_json_worker",
        lambda *args, **kwargs: {"outcome": "MUTATE"},
    )
    frame = pygame_split.SplitFrame("T", "L", "R", (), (), "", "", "")

    try:
        pygame_split.run(frame)
    except pygame_split.PygameSplitUnavailable as exc:
        assert "unknown choice" in str(exc)
    else:
        raise AssertionError("unknown split outcomes must use fallback")


def test_split_interactive_preserves_initial_focus_and_selection(monkeypatch):
    frame = pygame_split.SplitFrame(
        "Terminal", "Buy", "Sell", (), (), "", "", "hint", 1, 3,
    )
    seen = []
    monkeypatch.setattr(pygame_split, "_shared_runtime_enabled", lambda _ctx: True)
    monkeypatch.setattr(
        pygame_split,
        "run_shared",
        lambda _context, current, **kwargs: seen.append(current) or ("BACK", "", 1, 3),
    )

    assert pygame_split.run_interactive(
        SimpleNamespace(context=object()), lambda: frame, lambda *args: True, caption="test",
    ) == "BACK"
    assert seen[0].focus == 1
    assert seen[0].selected == 3


def test_split_interactive_preserves_focus_and_selection_after_action(monkeypatch):
    frame = pygame_split.SplitFrame(
        "Terminal", "Buy", "Sell", (), (), "", "", "hint",
    )
    seen = []
    outcomes = iter((("SELECT", "BUY:item", 1, 3), ("BACK", "", 1, 3)))

    def fake_run(current, **kwargs):
        seen.append(current)
        return next(outcomes)

    monkeypatch.setattr(pygame_split, "_shared_runtime_enabled", lambda _ctx: True)
    monkeypatch.setattr(pygame_split, "run_shared", lambda _context, current, **kwargs: fake_run(current, **kwargs))
    applied = []

    result = pygame_split.run_interactive(
        SimpleNamespace(context=object()),
        lambda: frame,
        lambda action, focus, selected: applied.append(
            (action, focus, selected)
        ) or True,
        caption="test",
    )

    assert result == "BACK"
    assert applied == [("BUY:item", 1, 3)]
    assert seen[1].focus == 1
    assert seen[1].selected == 3


def test_armory_pygame_frame_builds_ground_weapon_details():
    ctx = SimpleNamespace(
        equipped_ground_weapons=[],
        equipped_ground_armor={},
        stats=SimpleNamespace(credits=1000),
    )

    frame = _armory._pygame_armory_frame(ctx, "earth")
    actions = [row.action for row in frame.left_rows if not row.divider]

    assert actions
    assert "BUY_WEAPON:laser_pistol" in actions
    assert all("fists" not in row.action.lower() for row in frame.left_rows)
    assert all("Fists" not in row.label for row in frame.left_rows)
    assert all("Accuracy:" in row.detail for row in frame.left_rows if row.action.startswith("BUY_WEAPON:"))


def test_armory_empty_views_explain_storage_scope():
    ctx = SimpleNamespace(
        equipped_ground_weapons=[],
        equipped_ground_armor={},
        ground_armory_storage=[],
        ground_expedition_inventory=[],
        stats=SimpleNamespace(credits=1000),
        ground_stats=SimpleNamespace(strength=10),
    )

    armory = _armory._pygame_armory_frame(ctx, "earth", "ARMORY")
    expedition = _armory._pygame_armory_frame(ctx, "earth", "EXPEDITION")

    assert armory.left_rows[1].label == "[empty]"
    assert "unlimited" in armory.left_rows[1].detail
    assert expedition.left_rows[1].label == "[empty]"
    assert "no reserve items" in expedition.left_rows[1].detail
    assert "ENTER equip/manage" in armory.hint


def test_armory_frame_uses_shared_content_policy():
    ctx = SimpleNamespace(
        equipped_ground_weapons=[weapon_instance("laser_pistol")],
        equipped_ground_armor={},
        stats=SimpleNamespace(credits=1000),
    )

    frame = _armory._pygame_armory_frame(ctx, "earth")

    assert frame.title == "ARMORY - EARTH"
    assert frame.footer_left == "Credits: 1000$"
    assert frame.footer_right == "Pack: 0/4  Armory: unlimited"
    assert "B buy" in frame.hint
    assert "A armory" in frame.hint
    assert "E expedition" in frame.hint
    assert frame.left_rows[0].label == "--- WEAPONS ---"
    assert frame.left_rows[0].divider is True
    buy_cells = [row.value for row in frame.left_rows if row.action.startswith("BUY_WEAPON:")]
    assert buy_cells and all(cell.endswith("$") and "(" not in cell for cell in buy_cells)
    manage_cells = [row.value for row in frame.right_rows if row.action.startswith("MANAGE_WEAPON:")]
    assert manage_cells and all(cell.startswith("(sell ") for cell in manage_cells)

    two_handed = _armory._pygame_armory_frame(SimpleNamespace(
        equipped_ground_weapons=[weapon_instance("laser_rifle")],
        equipped_ground_armor={},
        stats=SimpleNamespace(credits=1000),
    ), "earth")
    disabled = [row for row in two_handed.right_rows if "occupied by 2H" in row.label]
    assert len(disabled) == 1
    assert disabled[0].action == ""
    assert disabled[0].selectable is False


def test_character_equipment_rows_offer_only_weapon_one_for_two_handed_pack_items():
    ctx = SimpleNamespace(
        equipped_ground_weapons=[weapon_instance("laser_pistol")],
        equipped_ground_armor={},
        ground_expedition_inventory=(
            __import__(
                "src.spacehack.ground_equipment",
                fromlist=["StoredGroundEquipment"],
            ).StoredGroundEquipment(
                "weapon", "laser_rifle",
            ),
        ),
    )

    rows = character_screen._equipment_rows(ctx, equipment_management=True)

    assert rows[0].action == "SWAP:weapon:0"
    assert rows[1].action == ""
    assert rows[1].selectable is False


def test_character_equipment_rows_mirror_loadout_slots():
    ctx = SimpleNamespace(
        equipped_ground_weapons=[weapon_instance("laser_pistol")],
        equipped_ground_armor={"body": "light_vest"},
    )

    rows = character_screen._equipment_rows(ctx)

    # Filled weapon slot: selectable, stats in the detail pane.
    assert rows[0].selectable
    assert "Laser Pistol" in rows[0].text
    assert "Damage 4" in rows[0].detail
    assert "Accuracy 78%" in rows[0].detail
    assert "Energy" in rows[0].detail
    # Empty weapon slot: non-selectable Fists placeholder.
    assert not rows[1].selectable
    assert rows[1].text == "Weapon slot 2: Fists"

    two_handed = character_screen._equipment_rows(SimpleNamespace(
        equipped_ground_weapons=[weapon_instance("laser_rifle")],
        equipped_ground_armor={},
    ))
    assert not two_handed[1].selectable
    assert two_handed[1].text == "Weapon slot 2: --- (occupied by 2H)"
    # Empty head slot first, then the filled body slot.
    assert not rows[2].selectable
    assert rows[2].text == "Head armor: None"
    assert rows[3].selectable
    assert "Light Armor Vest" in rows[3].text
    assert "Defense 2" in rows[3].detail


def test_character_equipment_rows_show_cybernetic_effects():
    ctx = SimpleNamespace(
        equipped_ground_weapons=[],
        equipped_ground_armor={"legs": "cybernetic_legs"},
    )

    rows = character_screen._equipment_rows(ctx)

    legs_row = next(row for row in rows if "Legs armor" in row.text)
    assert "+1 AP" in legs_row.detail


def test_character_equipment_rows_empty_gear_is_informational():
    ctx = SimpleNamespace(
        equipped_ground_weapons=[],
        equipped_ground_armor={},
    )

    rows = character_screen._equipment_rows(ctx)

    assert len(rows) == 7
    assert all(not row.selectable for row in rows)
    assert rows[0].text == "Weapon slot 1: Fists"
    assert rows[6].text == "Feet armor: None"


def test_character_equipment_management_explains_backpack_actions():
    ctx = SimpleNamespace(
        player_level=1,
        player_xp=0,
        player_skill_points=0,
        player_traits=[],
        character_info={"class_name": "merchant"},
        stats=SimpleNamespace(gunnery=10, piloting=10, engineering=10),
        ground_stats=SimpleNamespace(reflexes=10, strength=10, stamina=10),
        equipped_ground_weapons=[],
        equipped_ground_armor={},
        ground_expedition_inventory=[],
    )

    frame = character_screen._character_frame(
        ctx, 1, 0, equipment_management=True,
    )

    assert frame.body[1] == "Select a slot and press ENTER to swap from your backpack."
    assert frame.footer[0].endswith("ESC close   ? guide")


def test_character_equipment_management_keeps_slots_selectable_without_pack_items():
    ctx = SimpleNamespace(
        equipped_ground_weapons=[weapon_instance("laser_pistol")],
        equipped_ground_armor={"body": "light_vest"},
        ground_expedition_inventory=[],
    )

    rows = character_screen._equipment_rows(ctx, equipment_management=True)

    # Managed slots remain actionable even when there is no compatible
    # backpack item; Enter can then explain that the pack has no match.
    assert rows[0].selectable is True
    assert rows[0].action == "SWAP:weapon:0"
    assert rows[2].selectable is True
    assert rows[2].action == "SWAP:armor:head"
    assert rows[3].selectable is True
    assert rows[3].action == "SWAP:armor:body"
    assert rows[7].text == "--- BACKPACK ITEMS (0/4) ---"


def test_character_equipment_management_reports_empty_compatible_choices():
    messages = []
    ctx = SimpleNamespace(
        equipped_ground_weapons=[weapon_instance("laser_pistol")],
        equipped_ground_armor={},
        ground_expedition_inventory=[],
        log=SimpleNamespace(add=messages.append),
    )

    assert character_screen._swap_from_pack(ctx, "SWAP:weapon:0") is False
    assert messages == ["No compatible items are in your Expedition Pack."]


def test_screen_info_window_shows_informational_only_frames():
    frame = pygame_screen.ScreenFrame(
        "T", (),
        tuple(
            pygame_screen.ScreenRow(f"line {i}", selectable=False)
            for i in range(4)
        ),
    )
    assert pygame_screen._info_window(frame) == (0, 4)
    # Empty frames stay empty.
    assert pygame_screen._info_window(
        pygame_screen.ScreenFrame("T", (), ())
    ) == (0, 0)


def test_screen_rows_height_reserves_informational_rows():
    frame = pygame_screen.ScreenFrame(
        "T", (),
        tuple(
            pygame_screen.ScreenRow(f"line {i}", selectable=False)
            for i in range(3)
        ),
    )
    info_step = _FakeFont().get_linesize() + 4
    assert pygame_screen._rows_height(_FakeFont(), frame) == 3 * info_step


def test_armory_menu_forwards_planet_id_to_frame(monkeypatch):
    ctx = SimpleNamespace(
        equipped_ground_weapons=[],
        equipped_ground_armor={},
        stats=SimpleNamespace(credits=1000),
    )
    captured = {}

    def fake_run(_ctx, frame_builder, _apply, **_kwargs):
        captured["frame"] = frame_builder()

    monkeypatch.setattr(pygame_split, "run_interactive", fake_run)
    _armory._run_armory_menu(ctx, "earth")

    assert captured["frame"].title == "ARMORY - EARTH"


def test_armory_frame_exposes_all_storage_modes_and_active_tab():
    ctx = SimpleNamespace(
        equipped_ground_weapons=[],
        equipped_ground_armor={},
        ground_armory_storage=[
            _armory.ground_equipment.StoredGroundEquipment("weapon", "laser_pistol"),
        ],
        ground_expedition_inventory=[
            _armory.ground_equipment.StoredGroundEquipment("armor", "light_helmet"),
        ],
        stats=SimpleNamespace(credits=1000),
    )

    frames = {
        mode: _armory._pygame_armory_frame(ctx, "earth", mode)
        for mode in _armory._ARMORY_MODES
    }

    assert all(frame.left_tabs == ("[B]uy", "[A]rmory", "[E]xpedition (1/4)") for frame in frames.values())
    assert all(frame.left_tab_modes == ("BUY", "ARMORY", "EXPEDITION") for frame in frames.values())
    assert [frames[mode].active_left_tab for mode in _armory._ARMORY_MODES] == [0, 1, 2]
    assert frames["ARMORY"].left_rows[0].label == "--- OWNED EQUIPMENT ---"
    assert frames["ARMORY"].left_rows[1].action == "MANAGE_ARMORY:0"
    assert frames["EXPEDITION"].left_rows[0].label == "--- BACKPACK ITEMS ---"
    assert frames["EXPEDITION"].left_rows[1].action == "MANAGE_EXPEDITION:0"

    empty_pack = _armory._pygame_armory_frame(
        SimpleNamespace(
            equipped_ground_weapons=[],
            equipped_ground_armor={},
            ground_expedition_inventory=[],
            stats=SimpleNamespace(credits=1000),
        ),
        "earth",
        "EXPEDITION",
    )
    assert empty_pack.left_rows[0].label == "--- BACKPACK ITEMS ---"
    assert frames["EXPEDITION"].left_tabs[2] == "[E]xpedition (1/4)"
    assert "Pack: 1/4" in frames["EXPEDITION"].footer_right


def test_armory_frame_without_planet_id_uses_bare_title():
    ctx = SimpleNamespace(
        equipped_ground_weapons=[],
        equipped_ground_armor={},
        stats=SimpleNamespace(credits=1000),
    )

    assert _armory._pygame_armory_frame(ctx).title == "ARMORY"


def test_armory_pygame_empty_slot_action_is_noop():
    ctx = SimpleNamespace(
        equipped_ground_weapons=[],
        equipped_ground_armor={},
        stats=SimpleNamespace(credits=1000),
        log=SimpleNamespace(add=lambda _message: None),
    )

    assert _armory._apply_pygame_armory_action(ctx, "", 1, 1) is True
    assert ctx.stats.credits == 1000


def test_armory_pygame_rejects_unknown_action():
    ctx = SimpleNamespace(
        equipped_ground_weapons=[],
        equipped_ground_armor={},
        stats=SimpleNamespace(credits=1000),
        log=SimpleNamespace(add=lambda _message: None),
    )

    try:
        _armory._apply_pygame_armory_action(ctx, "BROKEN", 0, 0)
    except ValueError as exc:
        assert "Unknown armory action" in str(exc)
    else:
        raise AssertionError("unknown Armory actions must trigger fallback")


def test_armory_buy_action_opens_destination_chooser(monkeypatch):
    messages = []
    captured = {}
    ctx = SimpleNamespace(
        equipped_ground_weapons=[],
        equipped_ground_armor={},
        ground_armory_storage=[],
        ground_expedition_inventory=[],
        stats=SimpleNamespace(credits=1000),
        log=SimpleNamespace(add=messages.append),
    )

    def choose_destination(*args):
        captured["args"] = args
        return "BUY_ARMORY:weapon:laser_pistol"

    monkeypatch.setattr(_armory, "_choose_destination", choose_destination)

    keep_open = _armory._apply_pygame_armory_action(
        ctx, "BUY_WEAPON:laser_pistol", 0, 1,
    )

    assert keep_open is True
    assert ctx.equipped_ground_weapons == []
    assert ctx.ground_armory_storage == [
        _armory.ground_equipment.StoredGroundEquipment("weapon", "laser_pistol"),
    ]
    assert ctx.stats.credits < 1000
    assert messages
    assert captured["args"] == (ctx, "weapon", "laser_pistol")


def test_armory_purchase_chooser_labels_equip(monkeypatch):
    captured = {}
    monkeypatch.setattr(
        pygame_story,
        "choose",
        lambda _ctx, **kwargs: captured.update(kwargs) or "__BACK__",
    )

    _armory._choose_destination(SimpleNamespace(), "weapon", "laser_pistol")

    assert captured["options"][0] == (
        "Equip", "BUY_INSTALL:weapon:laser_pistol",
    )


def test_armory_container_transfer_uses_domain_helper(monkeypatch):
    from src.spacehack import pygame_story

    ctx = SimpleNamespace(
        equipped_ground_weapons=[],
        equipped_ground_armor={},
        ground_armory_storage=[
            _armory.ground_equipment.StoredGroundEquipment("weapon", "laser_pistol"),
        ],
        ground_expedition_inventory=[],
        stats=SimpleNamespace(credits=1000),
        log=SimpleNamespace(add=lambda _message: None),
    )
    monkeypatch.setattr(
        pygame_story,
        "choose",
        lambda *_args, **_kwargs: "MOVE_TO_EXPEDITION:0",
    )

    assert _armory._apply_pygame_armory_action(ctx, "MANAGE_ARMORY:0", 0, 0) is True
    assert ctx.ground_armory_storage == []
    assert ctx.ground_expedition_inventory == [
        _armory.ground_equipment.StoredGroundEquipment("weapon", "laser_pistol"),
    ]


def test_armory_replacement_automatically_prefers_expedition_pack(monkeypatch):
    from src.spacehack import pygame_story

    monkeypatch.setattr(
        pygame_story, "choose", lambda *_args, **_kwargs: "INSTALL_ARMORY:0",
    )
    ctx = SimpleNamespace(
        equipped_ground_weapons=[weapon_instance("laser_pistol"), weapon_instance("kinetic_pistol")],
        equipped_ground_armor={},
        ground_armory_storage=[
            _armory.ground_equipment.StoredGroundEquipment("weapon", "laser_rifle"),
        ],
        ground_expedition_inventory=[],
        stats=SimpleNamespace(credits=1000),
        log=SimpleNamespace(add=lambda _message: None),
    )

    _armory._apply_pygame_armory_action(ctx, "MANAGE_ARMORY:0", 0, 0)

    assert ctx.equipped_ground_weapons == [weapon_instance("laser_rifle")]
    assert ctx.ground_armory_storage == []
    assert ctx.ground_expedition_inventory == [
        _armory.ground_equipment.StoredGroundEquipment("weapon", "laser_pistol"),
        _armory.ground_equipment.StoredGroundEquipment("weapon", "kinetic_pistol"),
    ]


def test_armory_replacement_falls_back_to_armory_when_pack_is_full(monkeypatch):
    from src.spacehack import pygame_story

    monkeypatch.setattr(
        pygame_story, "choose", lambda *_args, **_kwargs: "INSTALL_ARMORY:0",
    )
    ctx = SimpleNamespace(
        equipped_ground_weapons=[weapon_instance("laser_pistol"), weapon_instance("kinetic_pistol")],
        equipped_ground_armor={},
        ground_armory_storage=[
            _armory.ground_equipment.StoredGroundEquipment("weapon", "laser_rifle"),
        ],
        ground_expedition_inventory=[
            _armory.ground_equipment.StoredGroundEquipment("armor", "light_helmet"),
            _armory.ground_equipment.StoredGroundEquipment("armor", "light_vest"),
            _armory.ground_equipment.StoredGroundEquipment("armor", "combat_boots"),
        ],
        stats=SimpleNamespace(credits=1000),
        log=SimpleNamespace(add=lambda _message: None),
    )

    _armory._apply_pygame_armory_action(ctx, "MANAGE_ARMORY:0", 0, 0)

    assert ctx.equipped_ground_weapons == [weapon_instance("laser_rifle")]
    assert ctx.ground_expedition_inventory[-1].item_id == "combat_boots"
    assert ctx.ground_armory_storage == [
        _armory.ground_equipment.StoredGroundEquipment("weapon", "laser_pistol"),
        _armory.ground_equipment.StoredGroundEquipment("weapon", "kinetic_pistol"),
    ]


def test_armory_purchase_equip_uses_armory_fallback_when_pack_is_full(monkeypatch):
    messages = []
    ctx = SimpleNamespace(
        equipped_ground_weapons=[weapon_instance("laser_pistol"), weapon_instance("kinetic_pistol")],
        equipped_ground_armor={},
        ground_armory_storage=[],
        ground_expedition_inventory=[
            _armory.ground_equipment.StoredGroundEquipment("armor", "light_helmet"),
            _armory.ground_equipment.StoredGroundEquipment("armor", "light_vest"),
            _armory.ground_equipment.StoredGroundEquipment("armor", "combat_boots"),
            _armory.ground_equipment.StoredGroundEquipment("weapon", "combat_knife"),
        ],
        stats=SimpleNamespace(credits=1000),
        log=SimpleNamespace(add=messages.append),
    )
    monkeypatch.setattr(
        _armory, "_choose_destination",
        lambda *_args: "BUY_INSTALL:weapon:laser_rifle",
    )

    _armory._apply_pygame_armory_action(ctx, "BUY_WEAPON:laser_rifle", 0, 0)

    assert ctx.equipped_ground_weapons == [weapon_instance("laser_rifle")]
    assert [entry.item_id for entry in ctx.ground_armory_storage] == [
        "laser_pistol", "kinetic_pistol",
    ]
    assert ctx.stats.credits < 1000
    assert messages


def test_armory_purchase_dismissal_preserves_credits_and_ownership(monkeypatch):
    from src.spacehack import pygame_story

    ctx = SimpleNamespace(
        equipped_ground_weapons=[],
        equipped_ground_armor={},
        ground_armory_storage=[],
        ground_expedition_inventory=[],
        stats=SimpleNamespace(credits=1000),
        log=SimpleNamespace(add=lambda _message: None),
    )
    monkeypatch.setattr(
        pygame_story,
        "choose",
        lambda *_args, **_kwargs: "__DISMISS__",
    )

    _armory._apply_pygame_armory_action(ctx, "BUY_WEAPON:laser_pistol", 0, 0)

    assert ctx.stats.credits == 1000
    assert ctx.equipped_ground_weapons == []
    assert ctx.ground_armory_storage == []
    assert ctx.ground_expedition_inventory == []


def test_armory_pygame_action_returns_keep_open_after_buy(monkeypatch):
    messages = []
    ctx = SimpleNamespace(
        equipped_ground_weapons=[],
        equipped_ground_armor={},
        ground_armory_storage=[],
        ground_expedition_inventory=[],
        stats=SimpleNamespace(credits=1000),
        log=SimpleNamespace(add=messages.append),
    )
    monkeypatch.setattr(
        _armory, "_choose_destination",
        lambda *_args: "BUY_INSTALL:weapon:laser_pistol",
    )

    keep_open = _armory._apply_pygame_armory_action(
        ctx, "BUY_WEAPON:laser_pistol", 0, 1,
    )

    assert keep_open is True
    assert ctx.equipped_ground_weapons == [weapon_instance("laser_pistol")]
    assert ctx.stats.credits < 1000
    assert messages


def test_hangar_loadout_tab_shows_installed_gear_and_empty_slots():
    from src.spacehack.menus import _ship_menu
    from src.spacehack.ship import OwnedShip

    ship = _ship_menu.ship_module.find_ship("starter")
    ctx = SimpleNamespace(
        player_owned_ship=OwnedShip(
            ship_id="starter",
            weapons=("light_laser",),
            modules=("shield_mk1",),
            fuel=12,
        ),
        stats=SimpleNamespace(credits=321),
    )

    frame = _ship_menu._ship_hangar_frame(ctx, ship, tab=2, selected=0)

    assert frame.title.startswith("YOUR ")
    assert frame.tabs == ("SHIP", "CARGO", "LOADOUT")
    assert frame.active_tab == 2
    assert frame.body == ()  # ship stats live on the SHIP tab
    assert "WEAPON SLOTS" in [row.text for row in frame.rows]
    assert "MODULE SLOTS" in [row.text for row in frame.rows]
    laser_row = next(row for row in frame.rows if row.text == "Light Laser")
    assert "Damage" in laser_row.detail
    assert any(row.text == "[empty]" for row in frame.rows)
    assert any(row.text == "Shield Mk. 1" for row in frame.rows)
    assert all(row.action != "LAUNCH" for row in frame.rows)
    assert any("TAB ship" in hint for hint in frame.footer)
    selectable = [row.text for row in frame.rows if row.selectable]
    assert selectable == ["Light Laser", "Shield Mk. 1"]


def test_hangar_loadout_tab_marks_empty_slots():
    from src.spacehack.menus import _ship_menu
    from src.spacehack.ship import OwnedShip

    ship = _ship_menu.ship_module.find_ship("starter")
    ctx = SimpleNamespace(
        player_owned_ship=OwnedShip(ship_id="starter", fuel=12),
        stats=SimpleNamespace(credits=321),
    )

    frame = _ship_menu._ship_hangar_frame(ctx, ship, tab=2, selected=0)

    texts = [row.text for row in frame.rows]
    assert "WEAPON SLOTS" in texts
    assert "MODULE SLOTS" in texts
    assert texts.count("[empty]") == 3  # 2 weapon slots + 1 module slot
    assert all(not row.selectable for row in frame.rows)


def test_slot_rows_render_installed_gear_beyond_slot_count():
    from src.spacehack.menus import _ship_menu

    rows = _ship_menu._slot_rows(1, ("light_laser", "light_laser"), _ship_menu._weapon_row)

    assert [row.text for row in rows] == ["Light Laser", "Light Laser"]
    assert all(row.selectable for row in rows)


def test_slot_rows_mark_unknown_ids_and_empty_slots():
    from src.spacehack.menus import _ship_menu

    rows = _ship_menu._slot_rows(2, ("not_a_real_module",), _ship_menu._module_row)

    assert rows[0].text == "not_a_real_module"
    assert rows[0].detail == "Unknown module specification"
    assert rows[1].text == "[empty]"
    assert rows[1].detail == ""
    assert rows[0].selectable is True
    assert rows[1].selectable is False


def test_ship_hangar_pygame_maps_back_and_quit(monkeypatch):
    from src.spacehack import pygame_screen
    from src.spacehack.menus import _ship_menu
    from src.spacehack.ship import OwnedShip

    ship = _ship_menu.ship_module.find_ship("starter")
    ctx = SimpleNamespace(
        context=object(),
        player_owned_ship=OwnedShip(ship_id="starter", fuel=12),
        stats=SimpleNamespace(credits=321),
    )
    for outcome in ("BACK", "QUIT"):
        monkeypatch.setattr(
            pygame_screen,
            "run_for_context",
            lambda *args, _outcome=outcome, **kwargs: (_outcome, "", 0),
        )
        assert _ship_menu._run_pygame_ship_hangar(
            ctx, ship,
        ) is _ship_menu.ShipMenuAction[outcome]


def test_ship_hangar_pygame_maps_launch(monkeypatch):
    from src.spacehack import pygame_screen
    from src.spacehack.menus import _ship_menu
    from src.spacehack.ship import OwnedShip

    ship = _ship_menu.ship_module.find_ship("starter")
    ctx = SimpleNamespace(
        context=object(),
        player_owned_ship=OwnedShip(ship_id="starter", fuel=12),
        stats=SimpleNamespace(credits=321),
    )
    monkeypatch.setattr(
        pygame_screen,
        "run_for_context",
        lambda _context, frame, **kwargs: ("SELECT", "LAUNCH", len(frame.rows) - 1),
    )

    assert _ship_menu._run_pygame_ship_hangar(
        ctx, ship,
    ) is _ship_menu.ShipMenuAction.LAUNCH


def test_ship_hangar_pygame_tab_cycles_all_tabs_and_wraps(monkeypatch):
    from src.spacehack import pygame_screen
    from src.spacehack.menus import _ship_menu
    from src.spacehack.ship import OwnedShip

    ship = _ship_menu.ship_module.find_ship("starter")
    ctx = SimpleNamespace(
        context=object(),
        player_owned_ship=OwnedShip(ship_id="starter", fuel=12),
        stats=SimpleNamespace(credits=321),
    )
    seen = []
    outcomes = iter((("TAB", "", 3), ("TAB", "", 0), ("TAB", "", 0), ("BACK", "", 0)))

    def fake_run(_context, frame, **_kwargs):
        seen.append(frame)
        return next(outcomes)

    monkeypatch.setattr(pygame_screen, "run_for_context", fake_run)

    assert _ship_menu._run_pygame_ship_hangar(
        ctx, ship,
    ) is _ship_menu.ShipMenuAction.BACK
    assert [frame.active_tab for frame in seen] == [0, 1, 2, 0]
    assert seen[1].selected == 0
    assert seen[3].selected == 0


def test_ship_hangar_pygame_guide_reopens(monkeypatch):
    from src.spacehack import pygame_screen
    from src.spacehack.menus import _ship_menu
    from src.spacehack.ship import OwnedShip

    ship = _ship_menu.ship_module.find_ship("starter")
    ctx = SimpleNamespace(
        context=object(),
        player_owned_ship=OwnedShip(ship_id="starter", fuel=12),
        stats=SimpleNamespace(credits=321),
    )
    outcomes = iter((("GUIDE", "", 0), ("BACK", "", 0)))
    monkeypatch.setattr(
        pygame_screen, "run_for_context", lambda *args, **kwargs: next(outcomes),
    )
    monkeypatch.setattr("src.spacehack.help._open_context_guide", lambda _ctx, _topic: None)

    assert _ship_menu._run_pygame_ship_hangar(
        ctx, ship,
    ) is _ship_menu.ShipMenuAction.BACK


def test_ship_hangar_pygame_jettisons_on_cargo_tab(monkeypatch):
    from src.spacehack import pygame_screen, trade
    from src.spacehack.menus import _ship_menu
    from src.spacehack.ship import OwnedShip

    ship = _ship_menu.ship_module.find_ship("starter")
    owned = OwnedShip(ship_id="starter", fuel=12)
    owned.inventory = {"food_rations": 2}
    ctx = SimpleNamespace(
        context=object(),
        player_owned_ship=owned,
        stats=SimpleNamespace(credits=321),
        log=SimpleNamespace(add=lambda _message: None),
    )
    # TAB to the CARGO tab first (SHIP is the default), then jettison.
    outcomes = iter((
        ("TAB", "", 0),
        ("SELECT", "JETTISON:food_rations", 0),
        ("BACK", "", 0),
    ))
    monkeypatch.setattr(
        pygame_screen, "run_for_context", lambda *args, **kwargs: next(outcomes),
    )
    monkeypatch.setattr(trade, "_run_quantity_prompt", lambda *_args: 2)

    assert _ship_menu._run_pygame_ship_hangar(
        ctx, ship,
    ) is _ship_menu.ShipMenuAction.BACK
    assert owned.inventory == {}


def test_loadout_pygame_frame_uses_parent_inventory_snapshot():
    from src.spacehack.ship import OwnedShip

    ctx = SimpleNamespace(
        player_owned_ship=OwnedShip(ship_id="starter"),
        stats=SimpleNamespace(credits=1000),
    )

    frame = __import__(
        "src.spacehack.menus._loadout", fromlist=["_pygame_loadout_frame"]
    )._pygame_loadout_frame(
        ctx,
        "earth",
        ("light_missile",),
        ("armor_plating",),
    )

    actions = [row.action for row in frame.left_rows if not row.divider]
    assert actions == [
        "BUY_WEAPON:light_missile",
        "BUY_MODULE:armor_plating",
    ]
    assert frame.left_label == "Store"
    assert frame.left_tabs == ("[B]uy", "[S]torage")
    assert frame.active_left_tab == 0


def test_loadout_buy_chooser_offers_install_or_store(monkeypatch):
    from src.spacehack import pygame_story
    from src.spacehack.menus import _loadout
    from src.spacehack.ship import OwnedShip

    choices = []
    ctx = SimpleNamespace(
        player_owned_ship=OwnedShip(ship_id="scout"),
        ship_storage=[],
        stats=SimpleNamespace(credits=1000),
        log=SimpleNamespace(add=lambda _message: None),
    )
    monkeypatch.setattr(
        pygame_story,
        "choose",
        lambda *args, **kwargs: choices.append(kwargs) or "__BACK__",
    )

    assert _loadout._apply_pygame_loadout_action(
        ctx, "BUY_WEAPON:light_laser", 0, 0, "earth",
    )
    assert choices[0]["options"] == (
        ("Install", "BUY_INSTALL_WEAPON:light_laser"),
        ("Store", "BUY_STORE_WEAPON:light_laser"),
    )
    assert choices[0]["compact"] is True
    assert ctx.stats.credits == 1000
    assert ctx.player_owned_ship.weapons == ()
    assert ctx.ship_storage == []


def test_loadout_buy_install_charges_only_after_successful_install(monkeypatch):
    from src.spacehack import pygame_story
    from src.spacehack.menus import _loadout
    from src.spacehack.ship import OwnedShip

    ctx = SimpleNamespace(
        player_owned_ship=OwnedShip(ship_id="scout"),
        ship_storage=[],
        stats=SimpleNamespace(credits=1000),
        log=SimpleNamespace(add=lambda _message: None),
    )
    monkeypatch.setattr(pygame_story, "choose", lambda *args, **kwargs: "BUY_INSTALL_WEAPON:light_laser")

    _loadout._apply_pygame_loadout_action(
        ctx, "BUY_WEAPON:light_laser", 0, 0, "earth",
    )

    assert ctx.stats.credits == 970
    assert ctx.player_owned_ship.weapons == ("light_laser",)
    assert ctx.ship_storage == []


def test_loadout_buy_store_works_when_ship_slots_are_full(monkeypatch):
    from src.spacehack import pygame_story
    from src.spacehack.menus import _loadout
    from src.spacehack.ship import OwnedShip

    ctx = SimpleNamespace(
        player_owned_ship=OwnedShip(
            ship_id="starter", weapons=("light_laser", "light_laser"),
        ),
        ship_storage=[],
        stats=SimpleNamespace(credits=1000),
        log=SimpleNamespace(add=lambda _message: None),
    )
    monkeypatch.setattr(pygame_story, "choose", lambda *args, **kwargs: "BUY_STORE_WEAPON:heavy_laser")

    _loadout._apply_pygame_loadout_action(
        ctx, "BUY_WEAPON:heavy_laser", 0, 0, "earth",
    )

    assert ctx.stats.credits == 910
    assert ctx.player_owned_ship.weapons == ("light_laser", "light_laser")
    assert len(ctx.ship_storage) == 1
    assert ctx.ship_storage[0].item_id == "heavy_laser"
    assert ctx.ship_storage[0].ammo is None


def test_loadout_buy_install_full_slot_does_not_charge(monkeypatch):
    from src.spacehack import pygame_story
    from src.spacehack.menus import _loadout
    from src.spacehack.ship import OwnedShip

    messages = []
    ctx = SimpleNamespace(
        player_owned_ship=OwnedShip(
            ship_id="starter", weapons=("light_laser", "light_laser"),
        ),
        ship_storage=[],
        stats=SimpleNamespace(credits=1000),
        log=SimpleNamespace(add=messages.append),
    )
    monkeypatch.setattr(pygame_story, "choose", lambda *args, **kwargs: "BUY_INSTALL_WEAPON:heavy_laser")

    _loadout._apply_pygame_loadout_action(
        ctx, "BUY_WEAPON:heavy_laser", 0, 0, "earth",
    )

    assert ctx.stats.credits == 1000
    assert ctx.ship_storage == []
    assert any("No compatible weapon slot" in message for message in messages)


def test_loadout_storage_frame_shows_manage_actions_and_spent_ammo():
    from src.spacehack.menus import _loadout
    from src.spacehack.ship import OwnedShip, StoredEquipment

    ctx = SimpleNamespace(
        player_owned_ship=OwnedShip(ship_id="scout", weapons=("light_laser",)),
        ship_storage=[
            StoredEquipment("weapon", "light_missile", 1),
            StoredEquipment("module", "shield_mk1"),
        ],
        stats=SimpleNamespace(credits=1000),
    )

    frame = _loadout._pygame_loadout_frame(ctx, mode="STORAGE")

    assert frame.left_label == "Storage"
    assert "B buy" in frame.hint
    assert "S storage" in frame.hint
    assert "ENTER choose" in frame.hint
    assert [row.action for row in frame.left_rows if not row.divider] == [
        "MANAGE_STORED:0",
        "MANAGE_STORED:1",
    ]
    assert frame.left_tabs == ("[B]uy", "[S]torage")
    assert frame.active_left_tab == 1
    assert all(row.value == "" for row in frame.left_rows if row.action.startswith("MANAGE_STORED:"))
    missile = next(row for row in frame.left_rows if row.action == "MANAGE_STORED:0")
    assert "Ammo: 1/4" in missile.detail
    assert frame.right_rows[0].divider is True
    assert any(row.action.startswith("MANAGE_") for row in frame.right_rows)


def test_loadout_storage_view_handles_missing_and_malformed_storage():
    from src.spacehack.menus import _loadout
    from src.spacehack.ship import OwnedShip

    ctx = SimpleNamespace(
        player_owned_ship=OwnedShip(ship_id="scout"),
        stats=SimpleNamespace(credits=1000),
    )
    frame = _loadout._pygame_loadout_frame(ctx, mode="STORAGE")
    assert any(row.label == "[empty]" for row in frame.left_rows)
    assert ctx.ship_storage == []

    ctx.ship_storage = [None, {"item_id": "shield_mk1"}, "bad"]
    frame = _loadout._pygame_loadout_frame(ctx, mode="STORAGE")
    assert any(row.label == "[empty]" for row in frame.left_rows)


def test_compact_menu_frame_round_trips_compact_flag():
    frame = pygame_menu.MenuFrame(
        "MANAGE EQUIPMENT", "Light Laser",
        (
            pygame_menu.MenuItem("Store", "", "STORE"),
            pygame_menu.MenuItem("Sell for 15$", "", "SELL"),
        ),
        ("ENTER select", "ESC back"), 0, compact=True,
    )

    restored = pygame_menu._frame_from_payload(pygame_menu._frame_payload(frame))

    assert restored == frame
    assert restored.compact is True


def test_compact_popup_wraps_long_body_inside_popup_width():
    frame = pygame_menu.MenuFrame(
        "REPLACE GROUND EQUIPMENT",
        "Choose where the displaced gear should go.",
        (pygame_menu.MenuItem("Keep old gear in Armory", "", "KEEP"),),
        (),
        0,
        compact=True,
    )

    popup_width, title_lines, body_lines = pygame_menu._compact_popup_layout(
        _FakeFont(), frame, 1600,
    )
    measure = lambda text: _FakeFont().size(text)[0]

    assert len(body_lines) > 1
    assert title_lines == ("REPLACE GROUND EQUIPMENT",)
    assert all(measure(line) <= popup_width - 48 for line in (*title_lines, *body_lines))


def test_compact_popup_handles_long_titles_and_narrow_surfaces():
    frame = pygame_menu.MenuFrame(
        "A VERY LONG GROUND EQUIPMENT REPLACEMENT TITLE",
        "",
        (),
        (),
        0,
        compact=True,
    )
    font = _FakeFont()

    popup_width, title_lines, body_lines = pygame_menu._compact_popup_layout(
        font, frame, 120,
    )

    assert popup_width == 1
    assert title_lines
    assert body_lines == ()
    assert pygame_menu._compact_frame_height(font, frame, 120) > 0

    many = pygame_menu.MenuFrame(
        "MENU", "", tuple(
            pygame_menu.MenuItem(f"Option {index}", "", str(index))
            for index in range(pygame_menu.COMPACT_MAX_VISIBLE_ROWS + 3)
        ), (), 0, compact=True,
    )
    four = pygame_menu.MenuFrame(
        many.title, many.body, many.items[:pygame_menu.COMPACT_MAX_VISIBLE_ROWS],
        many.hints, many.selected, compact=True,
    )
    assert pygame_menu._compact_frame_height(font, many, 1600) == \
        pygame_menu._compact_frame_height(font, four, 1600)


def test_compact_shared_menu_preserves_underlying_surface(monkeypatch):
    from src.spacehack import pygame_menu

    class Surface:
        def __init__(self):
            self.fills = 0

        def get_size(self):
            return (1600, 960)

        def fill(self, _color):
            self.fills += 1

    class Events:
        @staticmethod
        def wait():
            return SimpleNamespace(type=Pygame.KEYDOWN, key=Pygame.K_ESCAPE)

    class Pygame:
        QUIT = 1
        KEYDOWN = 2
        K_ESCAPE = 3
        K_RETURN = 4
        K_KP_ENTER = 5
        K_UP = 6
        K_DOWN = 7
        K_k = 8
        K_j = 9

        event = Events()

    surface = Surface()
    engine = SimpleNamespace(
        pygame=Pygame,
        logical_surface=surface,
        present=lambda: None,
    )
    context = SimpleNamespace(_runtime=SimpleNamespace(engine=engine))
    frame = pygame_menu.MenuFrame(
        "MANAGE", "Laser",
        (pygame_menu.MenuItem("Store", "", "STORE"),),
        (), 0, compact=True,
    )
    monkeypatch.setattr(pygame_menu, "_fit_shared_font", lambda *args: SimpleNamespace())
    monkeypatch.setattr(pygame_menu, "_draw_shared_frame", lambda *args, **kwargs: None)

    pygame_menu.run_shared(context, (frame,))

    assert surface.fills == 0


def test_loadout_my_ship_enter_opens_store_sell_chooser(monkeypatch):
    from src.spacehack.menus import _loadout
    from src.spacehack.ship import OwnedShip

    chosen = []
    monkeypatch.setattr(
        _loadout.pygame_story if hasattr(_loadout, "pygame_story") else __import__(
            "src.spacehack.pygame_story", fromlist=["choose"]
        ),
        "choose",
        lambda *args, **kwargs: chosen.append(kwargs["options"]) or "__BACK__",
    )
    ctx = SimpleNamespace(
        player_owned_ship=OwnedShip(ship_id="scout", weapons=("light_laser",)),
        ship_storage=[],
        stats=SimpleNamespace(credits=1000),
        log=SimpleNamespace(add=lambda _message: None),
    )

    assert _loadout._apply_pygame_loadout_action(
        ctx, "MANAGE_WEAPON_SLOT:0", 1, 0, "earth",
    )
    assert chosen == [(
        ("Store", "STORE_WEAPON_SLOT:0"),
        ("Sell for 15$", "SELL_WEAPON_SLOT:0"),
    )]
    assert ctx.player_owned_ship.weapons == ("light_laser",)


def test_loadout_my_ship_chooser_store_and_sell_apply_selected_action(monkeypatch):
    from src.spacehack import pygame_story
    from src.spacehack.menus import _loadout
    from src.spacehack.ship import OwnedShip

    ctx = SimpleNamespace(
        player_owned_ship=OwnedShip(ship_id="scout", weapons=("light_laser",)),
        ship_storage=[],
        stats=SimpleNamespace(credits=0),
        log=SimpleNamespace(add=lambda _message: None),
    )
    monkeypatch.setattr(pygame_story, "choose", lambda *args, **kwargs: "STORE_WEAPON_SLOT:0")
    _loadout._apply_pygame_loadout_action(ctx, "MANAGE_WEAPON_SLOT:0", 1, 0, "earth")
    assert ctx.player_owned_ship.weapons == ()
    assert ctx.ship_storage[0].item_id == "light_laser"

    ctx.player_owned_ship = OwnedShip(ship_id="scout", weapons=("light_laser",))
    ctx.ship_storage.clear()
    monkeypatch.setattr(pygame_story, "choose", lambda *args, **kwargs: "SELL_WEAPON_SLOT:0")
    _loadout._apply_pygame_loadout_action(ctx, "MANAGE_WEAPON_SLOT:0", 1, 0, "earth")
    assert ctx.player_owned_ship.weapons == ()
    assert ctx.ship_storage == []
    assert ctx.stats.credits > 0


def test_loadout_storage_chooser_install_and_sell(monkeypatch):
    from src.spacehack import pygame_story
    from src.spacehack.menus import _loadout
    from src.spacehack.ship import OwnedShip, StoredEquipment

    ctx = SimpleNamespace(
        player_owned_ship=OwnedShip(ship_id="scout"),
        ship_storage=[StoredEquipment("weapon", "light_missile", 1)],
        stats=SimpleNamespace(credits=0),
        log=SimpleNamespace(add=lambda _message: None),
    )
    captured = []
    monkeypatch.setattr(
        pygame_story,
        "choose",
        lambda *args, **kwargs: captured.append(kwargs["options"]) or "__BACK__",
    )

    assert _loadout._apply_pygame_loadout_action(
        ctx, "MANAGE_STORED:0", 0, 0, "earth",
    )
    assert captured == [
        (
            ("Install", "INSTALL_STORED:0"),
            ("Sell for 20$", "SELL_STORED:0"),
        ),
    ]
    assert ctx.ship_storage == [StoredEquipment("weapon", "light_missile", 1)]

    monkeypatch.setattr(pygame_story, "choose", lambda *args, **kwargs: "SELL_STORED:0")
    _loadout._apply_pygame_loadout_action(
        ctx, "MANAGE_STORED:0", 0, 0, "earth",
    )
    assert ctx.ship_storage == []
    assert ctx.stats.credits == 20

    ctx.ship_storage = [StoredEquipment("weapon", "light_missile", 1)]
    monkeypatch.setattr(pygame_story, "choose", lambda *args, **kwargs: "INSTALL_STORED:0")
    _loadout._apply_pygame_loadout_action(
        ctx, "MANAGE_STORED:0", 0, 0, "earth",
    )
    assert ctx.player_owned_ship.weapons == ("light_missile",)
    assert ctx.player_owned_ship.weapon_ammo == {0: 1}
    assert ctx.ship_storage == []


def test_loadout_storage_chooser_invalid_index_is_safe(monkeypatch):
    from src.spacehack.menus import _loadout
    from src.spacehack.ship import OwnedShip

    ctx = SimpleNamespace(
        player_owned_ship=OwnedShip(ship_id="scout"),
        ship_storage=[],
        stats=SimpleNamespace(credits=0),
        log=SimpleNamespace(add=lambda _message: None),
    )
    monkeypatch.setattr(
        "src.spacehack.pygame_story.choose",
        lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("chooser must not open")),
    )

    assert _loadout._apply_pygame_loadout_action(
        ctx, "MANAGE_STORED:9", 0, 0, "earth",
    )
    assert ctx.stats.credits == 0


def test_loadout_store_and_install_actions_preserve_partial_ammo():
    from src.spacehack.menus import _loadout
    from src.spacehack.ship import OwnedShip

    messages = []
    ctx = SimpleNamespace(
        player_owned_ship=OwnedShip(ship_id="scout", weapons=("light_missile",)),
        ship_storage=[],
        stats=SimpleNamespace(credits=1000),
        log=SimpleNamespace(add=messages.append),
    )
    ctx.player_owned_ship.weapon_ammo[0] = 1

    assert _loadout._apply_pygame_loadout_action(
        ctx, "STORE_WEAPON_SLOT:0", 1, 0, "earth",
    )
    assert ctx.player_owned_ship.weapons == ()
    assert ctx.ship_storage[0].ammo == 1

    assert _loadout._apply_pygame_loadout_action(
        ctx, "INSTALL_STORED:0", 0, 0, "earth",
    )
    assert ctx.player_owned_ship.weapons == ("light_missile",)
    assert ctx.player_owned_ship.weapon_ammo == {0: 1}
    assert ctx.ship_storage == []


def test_loadout_install_full_slot_keeps_storage_and_logs_reason():
    from src.spacehack.menus import _loadout
    from src.spacehack.ship import OwnedShip, StoredEquipment

    messages = []
    ctx = SimpleNamespace(
        player_owned_ship=OwnedShip(
            ship_id="starter", weapons=("light_laser", "light_laser"),
        ),
        ship_storage=[StoredEquipment("weapon", "heavy_laser")],
        stats=SimpleNamespace(credits=1000),
        log=SimpleNamespace(add=messages.append),
    )

    assert _loadout._apply_pygame_loadout_action(
        ctx, "INSTALL_STORED:0", 0, 0, "earth",
    )
    assert ctx.ship_storage == [StoredEquipment("weapon", "heavy_laser")]
    assert any("No compatible weapon slot" in message for message in messages)


def test_loadout_stored_sell_is_explicit_and_preserves_installed_gear():
    from src.spacehack.menus import _loadout
    from src.spacehack.ship import OwnedShip, StoredEquipment

    messages = []
    ctx = SimpleNamespace(
        player_owned_ship=OwnedShip(ship_id="scout", weapons=("light_laser",)),
        ship_storage=[StoredEquipment("module", "shield_mk1")],
        stats=SimpleNamespace(credits=0),
        log=SimpleNamespace(add=messages.append),
    )

    from src.spacehack.ship import OwnedShip

    ctx = SimpleNamespace(
        player_owned_ship=OwnedShip(
            ship_id="starter",
            weapons=("light_laser", "light_laser"),
        ),
        stats=SimpleNamespace(credits=0),
        log=SimpleNamespace(add=lambda _message: None),
    )
    original = ctx.player_owned_ship.weapons

    assert _loadout._apply_pygame_loadout_action(
        ctx, "SELL_WEAPON_SLOT:1", 1, 2, "earth",
    )
    assert original == ("light_laser", "light_laser")
    assert ctx.player_owned_ship.weapons == ("light_laser",)


def test_split_interactive_frame_build_failure_is_explicit(monkeypatch):
    monkeypatch.setattr(pygame_split, "_shared_runtime_enabled", lambda _ctx: True)
    try:
        pygame_split.run_interactive(
            SimpleNamespace(context=object()),
            lambda: (_ for _ in ()).throw(KeyError("bad inventory")),
            lambda *args: True,
            caption="test",
        )
    except pygame_split.PygameSplitUnavailable as exc:
        assert "could not be built" in str(exc)
    else:
        raise AssertionError("invalid split frames must not fall back to the legacy console")


def test_split_interactive_malformed_action_is_explicit(monkeypatch):
    frame = pygame_split.SplitFrame("Terminal", "Buy", "Sell", (), (), "", "", "hint")
    monkeypatch.setattr(pygame_split, "_shared_runtime_enabled", lambda _ctx: True)
    monkeypatch.setattr(
        pygame_split,
        "run_shared",
        lambda *args, **kwargs: ("SELECT", "BROKEN:action", 0, 0),
    )

    try:
        pygame_split.run_interactive(
            SimpleNamespace(context=object()), lambda: frame,
            lambda action, focus, selected: int(action.split(":", 1)[1]),
            caption="test",
        )
    except pygame_split.PygameSplitUnavailable as exc:
        assert "could not be rebuilt" in str(exc)
    else:
        raise AssertionError("invalid split actions must not fall back to the legacy console")


def test_hangar_ship_tab_shows_at_a_glance_stats_and_launch():
    from src.spacehack.menus import _ship_menu
    from src.spacehack.ship import OwnedShip

    ship = _ship_menu.ship_module.find_ship("starter")
    owned = OwnedShip(
        ship_id="starter", weapons=("light_laser",), fuel=12, hull_damage_pct=5,
    )
    ctx = SimpleNamespace(
        player_owned_ship=owned,
        stats=SimpleNamespace(credits=321),
    )

    frame = _ship_menu._ship_hangar_frame(ctx, ship, tab=0, selected=0)

    assert frame.title.startswith("YOUR ")
    assert frame.tabs == ("SHIP", "CARGO", "LOADOUT")
    assert frame.active_tab == 0
    body_text = "\n".join(frame.body)
    assert "Fuel: 12 / 80" in body_text
    assert "Hull: 95%" in body_text
    assert "Shields:" in body_text
    assert "Power:" in body_text
    assert "Cargo:" in body_text
    assert "Credits: 321$" in body_text
    assert [row.action for row in frame.rows] == ["LAUNCH"]
    assert any("ENTER launch" in hint for hint in frame.footer)
    assert any("TAB cargo" in hint for hint in frame.footer)


def test_hangar_ship_tab_launch_is_the_only_selectable_row():
    from src.spacehack import pygame_screen
    from src.spacehack.menus import _ship_menu
    from src.spacehack.ship import OwnedShip

    ship = _ship_menu.ship_module.find_ship("starter")
    ctx = SimpleNamespace(
        player_owned_ship=OwnedShip(ship_id="starter", fuel=12),
        stats=SimpleNamespace(credits=321),
    )

    frame = _ship_menu._ship_hangar_frame(ctx, ship, tab=0, selected=0)

    assert [row.action for row in frame.rows] == ["LAUNCH"]
    assert pygame_screen._clamp(frame) == 0


def test_hangar_cargo_tab_reuses_cargo_rows_without_launch():
    from src.spacehack.menus import _ship_menu
    from src.spacehack.ship import OwnedShip

    ship = _ship_menu.ship_module.find_ship("starter")
    owned = OwnedShip(ship_id="starter", fuel=12, hull_damage_pct=5)
    owned.inventory = {"food_rations": 2}
    ctx = SimpleNamespace(
        player_owned_ship=owned,
        stats=SimpleNamespace(credits=321),
    )

    frame = _ship_menu._ship_hangar_frame(ctx, ship, tab=1, selected=0)

    assert frame.title.startswith("YOUR ")
    assert frame.tabs == ("SHIP", "CARGO", "LOADOUT")
    assert frame.active_tab == 1
    assert any("Cargo: 2 / 20" in line for line in frame.body)
    assert frame.rows[0].action == "JETTISON:food_rations"
    assert all(row.action != "LAUNCH" for row in frame.rows)
    assert any("TAB loadout" in hint for hint in frame.footer)


def test_hangar_empty_hold_cargo_tab_has_no_selectable_rows():
    from src.spacehack.menus import _ship_menu
    from src.spacehack.ship import OwnedShip

    ship = _ship_menu.ship_module.find_ship("starter")
    ctx = SimpleNamespace(
        player_owned_ship=OwnedShip(ship_id="starter", fuel=12),
        stats=SimpleNamespace(credits=321),
    )

    frame = _ship_menu._ship_hangar_frame(ctx, ship, tab=1, selected=0)

    assert frame.active_tab == 1
    assert any("No trade goods in hold" in row.text for row in frame.rows)
    assert all(not row.selectable for row in frame.rows)


def test_hangar_pygame_empty_hold_enter_is_back_not_select():
    from src.spacehack import pygame_screen
    from src.spacehack.menus import _ship_menu
    from src.spacehack.ship import OwnedShip

    ship = _ship_menu.ship_module.find_ship("starter")
    ctx = SimpleNamespace(
        player_owned_ship=OwnedShip(ship_id="starter", fuel=12),
        stats=SimpleNamespace(credits=321),
    )

    frame = _ship_menu._ship_hangar_frame(ctx, ship, tab=1, selected=0)

    class FakePygame:
        QUIT = 1
        KEYDOWN = 2
        K_ESCAPE = 10
        K_UP = 12
        K_DOWN = 13
        K_k = 17
        K_j = 18
        K_RETURN = 19
        K_KP_ENTER = 20

    enter = SimpleNamespace(type=FakePygame.KEYDOWN, key=FakePygame.K_RETURN)
    # With zero selectable rows the shared screen maps ENTER to BACK, so
    # the hangar can never jettison a bogus action from an empty hold.
    assert pygame_screen._handle_key(FakePygame, enter, frame) == ("BACK", 0)


def test_hangar_frame_without_owned_ship_is_tabless_fallback():
    from src.spacehack.menus import _ship_menu

    ship = _ship_menu.ship_module.find_ship("starter")
    ctx = SimpleNamespace(
        player_owned_ship=None,
        stats=SimpleNamespace(credits=321),
    )

    frame = _ship_menu._ship_hangar_frame(ctx, ship, tab=1, selected=0)

    assert frame.title == "YOUR SHIP"
    assert frame.tabs == ()
    assert "No ship equipped." in frame.body


def test_cargo_rows_are_shared_with_the_hangar_tab():
    from src.spacehack import trade
    from src.spacehack.ship import OwnedShip

    owned = OwnedShip(ship_id="starter")
    owned.inventory = {"food_rations": 2}

    rows = trade._cargo_rows(owned)

    assert rows[0].action == "JETTISON:food_rations"
    assert "x2" in rows[0].text
    assert "Value:" in rows[0].detail


def test_apply_jettison_removes_selected_quantity(monkeypatch):
    from src.spacehack import trade
    from src.spacehack.ship import OwnedShip

    owned = OwnedShip(ship_id="starter")
    owned.inventory = {"food_rations": 5}
    messages = []
    ctx = SimpleNamespace(log=SimpleNamespace(add=messages.append))
    monkeypatch.setattr(trade, "_run_quantity_prompt", lambda *_args: 3)

    assert trade._apply_jettison(ctx, owned, "JETTISON:food_rations") is True
    assert owned.inventory == {"food_rations": 2}
    assert messages


def test_apply_jettison_full_quantity_removes_the_good(monkeypatch):
    from src.spacehack import trade
    from src.spacehack.ship import OwnedShip

    owned = OwnedShip(ship_id="starter")
    owned.inventory = {"food_rations": 4}
    ctx = SimpleNamespace(log=SimpleNamespace(add=lambda _m: None))
    monkeypatch.setattr(trade, "_run_quantity_prompt", lambda *_args: 4)

    assert trade._apply_jettison(ctx, owned, "JETTISON:food_rations") is True
    assert owned.inventory == {}


def test_apply_jettison_rejects_malformed_or_unknown_actions():
    from src.spacehack import trade
    from src.spacehack.ship import OwnedShip

    owned = OwnedShip(ship_id="starter")
    ctx = SimpleNamespace(log=SimpleNamespace(add=lambda _m: None))

    assert trade._apply_jettison(ctx, owned, "BROKEN") is False
    assert trade._apply_jettison(ctx, owned, "JETTISON:") is False
    assert trade._apply_jettison(ctx, owned, "JETTISON:unknown_good") is False



def test_faction_progress_bar_is_cp437_safe_and_centered():
    assert _ship_menu._faction_progress_bar(0) == "---------------|---------------"
    assert _ship_menu._faction_progress_bar(-100) == "###############|---------------"
    assert _ship_menu._faction_progress_bar(100) == "---------------|###############"
    assert all(ord(char) < 128 for char in _ship_menu._faction_progress_bar(-37))



def test_selectable_menu_wraps_long_mission_text_without_tiny_font():
    class FakeFont:
        def __init__(self, size):
            self.point_size = size

        def get_linesize(self):
            return self.point_size + 6

        def size(self, text):
            return len(text) * self.point_size // 2, self.point_size

    class FakePygame:
        class font:
            @staticmethod
            def match_font(_family):
                return None

            @staticmethod
            def Font(_path, size):
                return FakeFont(size)

    long_description = "Cargo and deadline details. " * 30
    frame = pygame_menu.MenuFrame(
        title="Guild Master - available work",
        body="Select a contract to review its details.",
        items=(pygame_menu.MenuItem("Deliver supplies", long_description, "0"),),
        hints=("UP/DOWN navigate   ENTER accept   ESC walk away",),
        selected=0,
    )

    font = pygame_menu._fit_font(FakePygame, (frame,), 1600, 960)

    assert font.point_size == 24
    assert pygame_menu._frame_height(
        font, frame, pygame_menu._content_width(1600),
    ) <= 828


def test_fixed_description_layout_budgets_cover_all_selection_states():
    class Font:
        def get_linesize(self):
            return 20

        def size(self, text):
            return len(text) * 8, 20

    descriptions = ("short", "long detail " * 12)
    menu_frames = tuple(
        pygame_menu.MenuFrame(
            "Menu", "body",
            tuple(
                pygame_menu.MenuItem(f"Option {index}", description, str(index))
                for index, description in enumerate(descriptions)
            ),
            (), selected,
        )
        for selected in range(2)
    )
    assert len({pygame_menu._frame_height(Font(), frame, 500) for frame in menu_frames}) == 1

    screen_frame = pygame_screen.ScreenFrame(
        "Screen", (), tuple(
            pygame_screen.ScreenRow(f"Row {index}", description, str(index))
            for index, description in enumerate(descriptions)
        ), selected=0,
    )
    alternate_screen = pygame_screen.ScreenFrame(
        screen_frame.title, screen_frame.body, screen_frame.rows,
        screen_frame.footer, selected=1,
    )
    assert pygame_screen._non_body_height(Font(), screen_frame, 500) == \
        pygame_screen._non_body_height(Font(), alternate_screen, 500)

    split_frames = tuple(
        pygame_split.SplitFrame(
            "Split", "Left", "Right",
            tuple(
                pygame_split.SplitRow(f"Row {index}", "", description, str(index))
                for index, description in enumerate(descriptions)
            ), (), "", "", "", 0, selected,
        )
        for selected in range(2)
    )
    assert len({pygame_split._frame_height(Font(), frame) for frame in split_frames}) == 1


def test_split_visible_window_keeps_selection_inside_and_capped():
    rows = tuple(
        pygame_split.SplitRow(f"Item {index}", "", "", f"ACT:{index}")
        for index in range(30)
    )

    top, count = pygame_split._visible_window(rows, 0, 9)
    assert (top, count) == (0, 9)

    top, count = pygame_split._visible_window(rows, 29, 9)
    assert top + count == len(rows)
    assert top <= 29 < top + count

    top, count = pygame_split._visible_window(rows, 15, 9)
    assert top <= 15 < top + count
    assert count <= 9

    # Empty and divider-only panels expose no viewport.
    assert pygame_split._visible_window((), 0, 9) == (0, 0)
    dividers = (pygame_split.SplitRow("--- X ---", "", "", "", True),)
    assert pygame_split._visible_window(dividers, 0, 9) == (0, 0)


def test_split_visible_window_includes_adjacent_dividers():
    rows = (
        pygame_split.SplitRow("--- WEAPONS ---", "", "", "", True),
        pygame_split.SplitRow("Laser", "30$", "", "BUY:laser"),
        pygame_split.SplitRow("--- ARMOUR ---", "", "", "", True),
        pygame_split.SplitRow("Vest", "50$", "", "BUY:vest"),
    )

    top, count = pygame_split._visible_window(rows, 3, 9)
    assert top == 0
    assert top + count == len(rows)


def test_split_frame_height_caps_rows_and_detail_lines():
    class Font:
        def get_linesize(self) -> int:
            return 29

        def size(self, text):
            return len(text) * 14, 29

    def frame(row_count, detail="d"):
        return pygame_split.SplitFrame(
            "Split", "Left", "Right",
            tuple(
                pygame_split.SplitRow(f"Row {index}", "", detail, str(index))
                for index in range(row_count)
            ),
            (), "", "", "", 0, 0,
        )

    # Heights use one stable capped layout budget regardless of the
    # current tab's list length.
    capped = pygame_split._frame_height(Font(), frame(pygame_split.MAX_VISIBLE_ROWS))
    assert capped == pygame_split._frame_height(Font(), frame(40))
    assert capped == pygame_split._frame_height(Font(), frame(100))
    assert capped == (
        150
        + pygame_split.MAX_VISIBLE_ROWS * (29 + 14)
        + 2 * (29 + 5)
        + pygame_split.MAX_DETAIL_LINES * (29 + 2)
    )

    # Sparse rows and long details use the same reserved layout budget.
    wrapped = frame(1, detail="word " * 60)
    assert pygame_split._frame_height(Font(), wrapped) == capped


def test_split_font_fit_is_stable_once_rows_exceed_cap():
    class Font:
        def __init__(self, size):
            self.point_size = size

        def get_linesize(self):
            return int(self.point_size * 1.2) + 1

        def size(self, text):
            return int(len(text) * self.point_size * 0.6), self.point_size

    class FakePygame:
        class font:
            @staticmethod
            def match_font(_family):
                return None

            @staticmethod
            def Font(_path, size):
                return Font(size)

    small = pygame_split.SplitFrame(
        "T", "L", "R",
        (pygame_split.SplitRow("a", "1", "short", "X"),), (), "", "", "",
    )
    huge = pygame_split.SplitFrame(
        "T", "L", "R",
        tuple(
            pygame_split.SplitRow(f"item {index}", "1", "details " * 3, f"X:{index}")
            for index in range(40)
        ),
        (), "", "", "",
    )
    huger = pygame_split.SplitFrame(
        "T", "L", "R",
        tuple(
            pygame_split.SplitRow(f"item {index}", "1", "details " * 3, f"X:{index}")
            for index in range(41)
        ),
        (), "", "", "",
    )

    font_small = pygame_split._fit_font(FakePygame, small, 1600, 960)
    font_huge = pygame_split._fit_font(FakePygame, huge, 1600, 960)
    font_huger = pygame_split._fit_font(FakePygame, huger, 1600, 960)

    # The fit is catalog-independent, including for a sparse tab.
    assert font_small.point_size == font_huge.point_size == font_huger.point_size


def test_menu_frame_height_caps_rows_and_detail_lines():
    class Font:
        def get_linesize(self) -> int:
            return 29

        def size(self, text):
            return len(text) * 14, 29

    def frame(row_count, detail="d"):
        return pygame_menu.MenuFrame(
            "Menu", "body",
            tuple(
                pygame_menu.MenuItem(f"Option {index}", detail, str(index))
                for index in range(row_count)
            ),
            ("hint",), 0,
        )

    # Heights are identical at the cap and beyond (independent of list
    # length), and the detail budget stops at MAX_DETAIL_LINES.
    capped = pygame_menu._frame_height(
        Font(), frame(pygame_ui.MAX_VISIBLE_ROWS), 800,
    )
    assert capped == pygame_menu._frame_height(Font(), frame(40), 800)
    assert capped == pygame_menu._frame_height(Font(), frame(100), 800)
    assert capped == (
        1 * (29 + 3) + 10
        + pygame_ui.MAX_VISIBLE_ROWS * (29 + 14)
        + 1 * (29 + 2)
        + 8 + 1 * (29 + 4)
    )

    wrapped = frame(1, detail="word " * 60)
    assert pygame_menu._frame_height(Font(), wrapped, 800) == (
        1 * (29 + 3) + 10
        + (29 + 14)
        + pygame_ui.MAX_DETAIL_LINES * (29 + 2)
        + 8 + 1 * (29 + 4)
    )


def test_screen_non_body_height_caps_rows_and_detail_lines():
    class Font:
        def get_linesize(self) -> int:
            return 29

        def size(self, text):
            return len(text) * 14, 29

    def frame(row_count, detail="d"):
        return pygame_screen.ScreenFrame(
            "Screen", ("body",),
            tuple(
                pygame_screen.ScreenRow(f"Row {index}", detail, str(index))
                for index in range(row_count)
            ),
            ("footer",), 0,
        )

    capped = pygame_screen._non_body_height(
        Font(), frame(pygame_ui.MAX_VISIBLE_ROWS), 800,
    )
    assert capped == pygame_screen._non_body_height(Font(), frame(40), 800)
    assert capped == pygame_screen._non_body_height(Font(), frame(100), 800)
    assert capped == (
        pygame_ui.MAX_VISIBLE_ROWS * (29 + 14)
        + pygame_screen.ROWS_DETAIL_GAP
        + 1 * (29 + 2)
        + 12
        + (max(1, 1) + 1) * (29 + 3)
    )

    wrapped = frame(1, detail="word " * 60)
    assert pygame_screen._non_body_height(Font(), wrapped, 800) == (
        (29 + 14)
        + pygame_screen.ROWS_DETAIL_GAP
        + pygame_ui.MAX_DETAIL_LINES * (29 + 2)
        + 12
        + (max(1, 1) + 1) * (29 + 3)
    )


def test_shared_font_solver_uses_the_24_to_11_ladder():
    class FakePygame:
        class font:
            @staticmethod
            def Font(_path, size):
                return SimpleNamespace(point_size=size)

    # Everything above 20px is too tall; 20px fits — the first fitting
    # size on the 24→11 ladder wins.
    def measure(font):
        return 50 if font.point_size > 20 else 0 if font.point_size == 20 else 10

    font = pygame_ui.fit_font(
        FakePygame, None, measure_height=measure, available_height=40,
    )
    assert font.point_size == 20

    # Never fitting content falls back to the 12px ladder floor.
    tiny = pygame_ui.fit_font(
        FakePygame, None, measure_height=lambda font: 9999, available_height=40,
    )
    assert tiny.point_size == 12


def test_menu_font_fit_is_stable_once_items_exceed_cap():
    class Font:
        def __init__(self, size):
            self.point_size = size

        def get_linesize(self):
            return int(self.point_size * 1.2) + 1

        def size(self, text):
            return int(len(text) * self.point_size * 0.6), self.point_size

    class FakePygame:
        class font:
            @staticmethod
            def match_font(_family):
                return None

            @staticmethod
            def Font(_path, size):
                return Font(size)

    def frame(count):
        return pygame_menu.MenuFrame(
            "Guild Master - available work",
            "Select a contract to review its details.",
            tuple(
                pygame_menu.MenuItem(
                    f"Contract {index}",
                    "Cargo and deadline details. " * 3,
                    str(index),
                )
                for index in range(count)
            ),
            ("hint",), 0,
        )

    font_small = pygame_menu._fit_font(FakePygame, (frame(1),), 1600, 960, reserve_log=True)
    font_huge = pygame_menu._fit_font(FakePygame, (frame(40),), 1600, 960, reserve_log=True)
    font_huger = pygame_menu._fit_font(FakePygame, (frame(41),), 1600, 960, reserve_log=True)

    assert font_small.point_size == 24
    assert font_huge.point_size == font_huger.point_size


def test_screen_font_fit_is_stable_once_rows_exceed_cap():
    class Font:
        def __init__(self, size):
            self.point_size = size

        def get_linesize(self):
            return int(self.point_size * 1.2) + 1

        def size(self, text):
            return int(len(text) * self.point_size * 0.6), self.point_size

    class FakePygame:
        class font:
            @staticmethod
            def match_font(_family):
                return None

            @staticmethod
            def Font(_path, size):
                return Font(size)

    def frame(count):
        return pygame_screen.ScreenFrame(
            "Cargo",
            ("Select an item to inspect it.",),
            tuple(
                pygame_screen.ScreenRow(
                    f"Item {index}", "short detail", f"ROW:{index}",
                )
                for index in range(count)
            ),
            ("ESC back",), 0,
        )

    font_small = pygame_screen._fit_font(FakePygame, frame(1), 1600, 960, reserve_log=True)
    font_huge = pygame_screen._fit_font(FakePygame, frame(40), 1600, 960, reserve_log=True)
    font_huger = pygame_screen._fit_font(FakePygame, frame(41), 1600, 960, reserve_log=True)

    assert font_small.point_size == 24
    assert font_huge.point_size == font_huger.point_size


def test_menu_and_screen_viewports_reuse_the_shared_window():
    items = tuple(
        pygame_menu.MenuItem(f"Item {index}", "", str(index))
        for index in range(30)
    )
    top, count = pygame_ui.visible_window(
        items, 29, 13, is_selectable=lambda item: True,
    )
    assert top + count == len(items)
    assert top <= 29 < top + count

    rows = tuple(
        pygame_screen.ScreenRow(
            f"Row {index}", "", str(index), selectable=(index % 2 == 0),
        )
        for index in range(30)
    )
    top, count = pygame_ui.visible_window(
        rows, 29, 13, is_selectable=lambda row: row.selectable,
    )
    assert top <= 28 < top + count
    selectable_in_window = sum(
        1 for index in range(top, top + count) if rows[index].selectable
    )
    assert selectable_in_window == 13


def test_log_panel_height_matches_world_band():
    """Modals reserve exactly the world renderer's log band height."""
    from src.spacehack.engine import MSG_LOG_HEIGHT, TILE_HEIGHT

    assert pygame_ui.LOG_PANEL_HEIGHT == MSG_LOG_HEIGHT * TILE_HEIGHT
    assert pygame_ui.LOG_PANEL_HEIGHT == 96


def test_draw_context_log_delegates_to_message_band(monkeypatch):
    """The modal log renders through the same band painter as the world."""
    log = object()
    ctx = SimpleNamespace(
        _runtime=SimpleNamespace(game_context=SimpleNamespace(log=log)),
    )
    seen = []
    monkeypatch.setattr(
        pygame_ui, "draw_message_band",
        lambda _pygame, _screen, band_log, **_kwargs: seen.append(band_log),
    )

    pygame_ui.draw_context_log(SimpleNamespace(), object(), ctx)

    assert seen == [log]


def test_screen_frame_payload_round_trips_scrollable():
    frame = pygame_screen.ScreenFrame(
        "T", ("body",), (), selected=1, scrollable=True, start_at_end=True,
    )
    back = pygame_screen._frame_from_payload(pygame_screen._frame_payload(frame))

    assert back.scrollable is True
    assert back.start_at_end is True
    assert back.title == "T"
    assert back.selected == 1


def test_scrollable_frame_can_start_at_end_without_changing_default():
    font = _FakeFont()
    body = tuple(f"line {index}" for index in range(100))
    top = pygame_screen.ScreenFrame("T", body, (), scrollable=True)
    end = pygame_screen.ScreenFrame("T", body, (), scrollable=True, start_at_end=True)

    assert pygame_screen._initial_page_offset(font, top, 200, 960) == 0
    assert pygame_screen._initial_page_offset(font, end, 200, 960) > 0


def test_layout_height_caps_scrollable_bodies():
    long_body = tuple(f"paragraph {i} " + "text " * 40 for i in range(20))
    plain = pygame_screen.ScreenFrame("T", long_body, (), footer=("ESC",))
    scrollable = pygame_screen.ScreenFrame(
        "T", long_body, (), footer=("ESC",), scrollable=True,
    )
    font = _FakeFont()

    uncapped = pygame_screen._layout_height(font, plain, 200)
    capped = pygame_screen._layout_height(
        font, scrollable, 200, available_height=120,
    )

    assert capped == 120
    assert uncapped > 120


def test_guide_section_frame_is_scrollable():
    from src.spacehack.help import GUIDE_SECTIONS, _section_frame

    frame = _section_frame(GUIDE_SECTIONS[0])

    assert frame.scrollable is True
    assert frame.title == GUIDE_SECTIONS[0].title
    assert frame.rows == ()


def test_terminal_title_grammar():
    assert pygame_ui.terminal_title("MECHANIC", "SHIP LOADOUT") == "MECHANIC - SHIP LOADOUT"
    assert pygame_ui.terminal_title("TRADE", "earth") == "TRADE - EARTH"
    assert pygame_ui.terminal_title("ARMORY", "earth") == "ARMORY - EARTH"
    assert pygame_ui.terminal_title("ARMORY") == "ARMORY"
    assert pygame_ui.terminal_title("scout", "for sale") == "SCOUT - FOR SALE"


def test_price_and_sell_cells():
    assert pygame_ui.price_cell(30) == "30$"
    assert pygame_ui.price_cell(30, 12) == "30$ (12)"
    assert pygame_ui.sell_cell(15) == "(sell 15$)"
    assert pygame_ui.sell_cell(15, 2) == "(sell 15$) x2"


def test_stat_and_reward_labels():
    assert pygame_ui.credits_label(1000) == "Credits: 1000$"
    assert pygame_ui.cargo_label(12, 50) == "Cargo: 12/50"
    assert pygame_ui.shortfall_label(3000) == "3000$ short"
    assert pygame_ui.reward_label(400, 50) == "Reward: 400$ + 50xp"


def test_modal_hint_uses_canonical_separator_and_strips_dots():
    assert pygame_ui.modal_hint("UP/DOWN navigate", "ENTER select", "ESC back") == (
        "UP/DOWN navigate   ENTER select   ESC back"
    )
    assert pygame_ui.modal_hint("ESC leave.") == "ESC leave"
    assert pygame_ui.modal_hint("a.", "b", "c.") == "a   b   c"


def test_split_section_header_builds_divider_row():
    row = pygame_split.section_header("WEAPONS")
    assert row.label == "--- WEAPONS ---"
    assert row.divider is True
    assert row.action == ""
    assert row.value == ""


def test_split_shop_hint_is_canonical_with_guide_key():
    assert pygame_split.SPLIT_SHOP_HINT == (
        "UP/DOWN navigate   TAB switch panel   ENTER buy/sell   "
        "ESC back   ? guide"
    )
    assert "? guide" in pygame_split.SPLIT_SHOP_HINT


def test_merchant_description_budget_is_selection_independent():
    class Font:
        def get_linesize(self):
            return 20

        def size(self, text):
            return len(text) * 8, 20

    frames = (
        pygame_merchant.MerchantFrame("M", ("A", "B"), "short", (), 0),
        pygame_merchant.MerchantFrame("M", ("A", "B"), "long detail " * 12, (), 1),
    )
    height = pygame_merchant._description_height(Font(), frames, 500)
    assert pygame_merchant._content_height(Font(), frames[0], 500, height) == \
        pygame_merchant._content_height(Font(), frames[1], 500, height)


def test_selectable_menu_frame_payload_round_trips_actions_and_ascii_art():
    frame = pygame_menu.MenuFrame(
        title="Mars",
        body="Choose an action.",
        items=(pygame_menu.MenuItem("Land", "Dock", "LAND"),),
        hints=("ESC back",),
        selected=0,
        art=("~=~=~", "=+=+=",),
        art_color=(150, 95, 255),
        art_colors=((150, 95, 255), (140, 80, 255)),
    )

    restored = pygame_menu._frame_from_payload(pygame_menu._frame_payload(frame))

    assert restored == frame


def test_ascii_art_increases_selectable_frame_height():
    class FakeFont:
        def get_linesize(self):
            return 24

        def size(self, text):
            return len(text) * 10, 24

    plain = pygame_menu.MenuFrame("title", "body", (), (), 0)
    decorated = pygame_menu.MenuFrame(
        "title", "body", (), (), 0, art=("rune", "door",),
    )

    assert pygame_menu._frame_height(
        FakeFont(), decorated, 600,
    ) > pygame_menu._frame_height(FakeFont(), plain, 600)


def test_screen_font_fit_accounts_for_long_detail_on_any_selection():
    class FakeFont:
        def __init__(self, size):
            self.point_size = size

        def get_linesize(self):
            return self.point_size + 6

        def size(self, text):
            return len(text) * self.point_size // 2, self.point_size

    class FakePygame:
        class font:
            @staticmethod
            def match_font(_family):
                return None

            @staticmethod
            def Font(_path, size):
                return FakeFont(size)

    frame = pygame_screen.ScreenFrame(
        "Terminal",
        ("Choose an option",),
        (
            pygame_screen.ScreenRow("Short", "brief", "SHORT"),
            pygame_screen.ScreenRow("Long", "details " * 80, "LONG"),
        ),
        ("ESC back",),
        selected=0,
    )

    font = pygame_screen._fit_font(FakePygame, frame, 640, 480)

    assert pygame_screen._layout_height(font, frame, 560) <= 396


def test_pygame_trade_valid_actions_keep_terminal_open(monkeypatch):
    from src.spacehack import trade

    class Good:
        name = "Food"
        volume = 1

    calls = []
    monkeypatch.setattr(trade, "find_trade_good", lambda _good_id: Good())
    monkeypatch.setattr(trade, "_unit_price", lambda *_args: 10)
    monkeypatch.setattr(trade, "_sell_price", lambda *_args: 7)
    monkeypatch.setattr(trade, "_free_cargo", lambda _owned: 5)
    monkeypatch.setattr(trade, "_run_quantity_prompt", lambda *_args: 1)
    monkeypatch.setattr(trade, "_buy_good", lambda *args: calls.append(("BUY", args)) or True)
    monkeypatch.setattr(trade, "_sell_good", lambda *args: calls.append(("SELL", args)) or True)

    ctx = SimpleNamespace(
        player_owned_ship=SimpleNamespace(inventory={"food": 2}),
        economy_state={"earth": {"food": 3}},
        stats=SimpleNamespace(credits=100),
    )

    assert trade._apply_pygame_trade_action(ctx, "earth", "BUY:food") is True
    assert trade._apply_pygame_trade_action(ctx, "earth", "SELL:food") is True
    assert [kind for kind, _args in calls] == ["BUY", "SELL"]


def test_screen_body_budget_reserves_rows_and_footer():
    class Font:
        def get_linesize(self):
            return 20

        def size(self, text):
            return len(text) * 8, 20

    frame = pygame_screen.ScreenFrame(
        "Guide",
        ("body " * 20,),
        (pygame_screen.ScreenRow("Choice", "details", "CHOICE"),),
        ("ESC close",),
    )

    budget = pygame_screen._body_budget(Font(), frame, 500, 480, 84)

    assert budget > 0
    assert budget * (20 + 3) + pygame_screen._non_body_height(Font(), frame, 500) <= 480 - 70 - 84 - 8


def test_screen_worker_rejects_unknown_outcome(monkeypatch):
    monkeypatch.setattr(
        pygame_ui,
        "run_json_worker",
        lambda *args, **kwargs: {"outcome": "MUTATE"},
    )
    frame = pygame_screen.ScreenFrame("T", (), ())

    try:
        pygame_screen.run(frame)
    except pygame_screen.PygameScreenUnavailable as exc:
        assert "unknown choice" in str(exc)
    else:
        raise AssertionError("unknown text-screen outcomes must use fallback")


def test_story_menu_dismisses_with_enter_without_items():
    class FakePygame:
        QUIT = 1
        KEYDOWN = 2
        K_ESCAPE = 10
        K_RETURN = 11
        K_KP_ENTER = 12
        K_UP = 13
        K_DOWN = 14
        K_k = 15
        K_j = 16

    fake = FakePygame()
    key = lambda value: SimpleNamespace(type=fake.KEYDOWN, key=value)

    assert pygame_menu._handle_key(fake, key(fake.K_RETURN), 0, 0) == ("DISMISS", 0)
    assert pygame_menu._handle_key(fake, key(fake.K_ESCAPE), 0, 0) == ("BACK", 0)


def test_story_confirm_maps_confirm_and_back(monkeypatch):
    outcomes = iter((("SELECT", "CONFIRM", 0), ("BACK", "", 0)))
    monkeypatch.setattr(pygame_menu, "run_for_context", lambda *args, **kwargs: next(outcomes))

    assert pygame_story.confirm(
        SimpleNamespace(),
        title="Computer",
        body="Restore power?",
        accept_label="Activate",
        cancel_label="Leave",
        caption="test",
    ) == "CONFIRM"
    assert pygame_story.confirm(
        SimpleNamespace(),
        title="Computer",
        body="Restore power?",
        accept_label="Activate",
        cancel_label="Leave",
        caption="test",
    ) == "BACK"


def test_story_confirm_preserves_quit(monkeypatch):
    monkeypatch.setattr(
        pygame_menu,
        "run_for_context",
        lambda *args, **kwargs: ("QUIT", "", 0),
    )

    assert pygame_story.confirm(
        SimpleNamespace(),
        title="Board",
        body="Board the wreck?",
        accept_label="Board",
        cancel_label="Fly past",
        caption="test",
    ) == "QUIT"


def test_story_dismiss_attaches_ascii_art_to_worker_frame(monkeypatch):
    captured = {}

    def fake_run(frames, **kwargs):
        captured["frame"] = frames[0]
        return "DISMISS", "", 0

    monkeypatch.setattr(
        pygame_menu,
        "run_for_context",
        lambda _context, frames, **kwargs: fake_run(frames, **kwargs),
    )
    result = pygame_story.dismiss(
        SimpleNamespace(),
        title="Transmission",
        body="Body",
        caption="test",
        art=("STATIC",),
        art_color=(90, 150, 90),
    )

    assert result == "DISMISS"
    assert captured["frame"].art == ("STATIC",)
    assert captured["frame"].art_color == (90, 150, 90)


def test_main_quest_story_art_preserves_transmission_and_door_flavor(monkeypatch):
    captured = []

    monkeypatch.setattr(
        "src.spacehack.pygame_story.dismiss",
        lambda _ctx, **kwargs: captured.append(kwargs) or "DISMISS",
    )

    _act0.show_prologue_transmission(SimpleNamespace())
    _act0.show_sealed_door_overlay(SimpleNamespace(), "discover")

    assert captured[0]["art"] == _act0._SIGNAL_ART
    assert captured[0]["art_color"] == _act0._SIGNAL_TRACE_FG
    assert captured[0]["art_colors"] == _act0._SIGNAL_ART_COLORS
    assert captured[1]["art"] == tuple(
        ("MAKE: ALIEN    MECHANISM: NONE VISIBLE    AGE: UNKNOWN", "", *_act0._DOOR_RUNES, *_act0._DOOR_ART_SEALED)
    )
    assert captured[1]["art_color"] == _act0._DOOR_ART_FG
    assert captured[1]["art_colors"] == (
        _act0.ui.COLOR_VALUE_DIM,
        _act0.ui.COLOR_VALUE_DIM,
        *(_act0._DOOR_RUNE_FG for _ in _act0._DOOR_RUNES),
        *(_act0._DOOR_ART_FG for _ in _act0._DOOR_ART_SEALED),
    )


def test_story_frames_preserve_opaque_archive_choices(monkeypatch):
    captured = {}

    def fake_run(frames, **kwargs):
        captured["frames"] = frames
        return "SELECT", "archive_sealed", 1

    monkeypatch.setattr(
        pygame_menu,
        "run_for_context",
        lambda _context, frames, **kwargs: fake_run(frames, **kwargs),
    )
    result = pygame_story.choose(
        SimpleNamespace(),
        title="THE FIRST READING",
        body="Archive body",
        options=(("Share fragment", "diagnostic_fragment"), ("Keep sealed", "archive_sealed")),
        caption="test",
    )

    assert result == "archive_sealed"
    assert captured["frames"][1].items[1].action == "archive_sealed"


def test_story_choice_rejects_unknown_worker_action(monkeypatch):
    monkeypatch.setattr(
        pygame_menu,
        "run_for_context",
        lambda _context, frames, **kwargs: ("SELECT", "mutate_quest", 0),
    )

    assert pygame_story.choose(
        SimpleNamespace(),
        title="THE FIRST READING",
        body="Archive body",
        options=(("Keep sealed", "archive_sealed"),),
        caption="test",
    ) is None


def test_story_dismiss_is_explicit_when_shared_runtime_unavailable(monkeypatch):
    monkeypatch.setattr(
        pygame_menu,
        "run_for_context",
        lambda *args, **kwargs: (_ for _ in ()).throw(
            pygame_menu.PygameMenuUnavailable("missing")
        ),
    )

    try:
        pygame_story.dismiss(
            SimpleNamespace(context=object()), title="Message", body="Body", caption="test",
        )
    except pygame_menu.PygameMenuUnavailable as exc:
        assert str(exc) == "missing"
    else:
        raise AssertionError("story presentation must not fall back to the legacy console")


def test_story_dismiss_preserves_worker_quit_outcome(monkeypatch):
    monkeypatch.setattr(
        pygame_menu,
        "run_for_context",
        lambda *args, **kwargs: ("QUIT", "", 0),
    )

    assert pygame_story.dismiss(
        SimpleNamespace(context=object()), title="Message", body="Body", caption="test",
    ) == "QUIT"


def test_story_dismiss_propagates_quit_to_act0(monkeypatch):
    from src.spacehack.main_quest import _act0

    monkeypatch.setattr(
        pygame_story,
        "dismiss",
        lambda *args, **kwargs: "QUIT",
    )

    try:
        _act0._show_pygame_dismiss(
            SimpleNamespace(), title="Message", body="Body", caption="test",
        )
    except SystemExit:
        pass
    else:
        raise AssertionError("story worker QUIT must propagate to Act 0")


def test_selectable_menu_key_mapping_preserves_navigation_and_actions():
    class FakePygame:
        QUIT = 1
        KEYDOWN = 2
        K_ESCAPE = 10
        K_QUESTION = 11
        K_UP = 12
        K_DOWN = 13
        K_k = 14
        K_j = 15
        K_RETURN = 16
        K_KP_ENTER = 17

    fake = FakePygame()
    key = lambda value: SimpleNamespace(type=fake.KEYDOWN, key=value)

    assert pygame_menu._handle_key(fake, SimpleNamespace(type=fake.QUIT), 0, 2) == ("QUIT", 0)
    assert pygame_menu._handle_key(fake, key(fake.K_ESCAPE), 1, 2) == ("BACK", 1)
    assert pygame_menu._handle_key(fake, key(fake.K_QUESTION), 1, 2) == ("GUIDE", 1)
    assert pygame_menu._handle_key(fake, key(fake.K_UP), 0, 2) == ("IGNORE", 1)
    assert pygame_menu._handle_key(fake, key(fake.K_RETURN), 1, 2) == ("SELECT", 1)


def test_selectable_menu_rejects_unknown_worker_outcomes(monkeypatch):
    monkeypatch.setattr(
        pygame_ui,
        "run_json_worker",
        lambda *args, **kwargs: {"outcome": "MUTATE"},
    )
    frame = pygame_menu.MenuFrame("title", "body", (), (), 0)

    try:
        pygame_menu.run((frame,))
    except pygame_menu.PygameMenuUnavailable as exc:
        assert "unknown choice" in str(exc)
    else:
        raise AssertionError("unknown menu outcomes must be rejected")


def test_interactive_batch_is_enabled():
    assert pygame_menu.enabled()


def test_planet_menu_items_keep_domain_outcomes_opaque_to_worker():
    planet = SimpleNamespace(id="mars", name="Mars")

    items = _planet._build_menu_items(planet, True, ["Alien ruins"])

    assert [item[2] for item in items] == [
        _planet.PlanetMenuOutcome.LAND,
        _planet.PlanetMenuOutcome.EXPLORE,
        _planet.PlanetMenuOutcome.BACK,
    ]


def test_npc_pygame_actions_map_back_to_existing_outcomes(monkeypatch):
    mission = SimpleNamespace(title="Deliver supplies")
    npc_obj = SimpleNamespace(name="Guild Master", guild="merchants", flavor_text="Welcome")
    from src.spacehack import pygame_menu

    monkeypatch.setattr(
        pygame_menu,
        "run_for_context",
        lambda _context, frames, **kwargs: ("SELECT", "DELIVER:0", 0),
    )

    from src.spacehack import pygame_runtime
    monkeypatch.setattr(pygame_runtime, "is_shared_context", lambda _context: True)
    monkeypatch.setattr(pygame_menu, "run_shared", lambda _context, frames, **kwargs: ("SELECT", "DELIVER:0", 0))
    result = npc._run_pygame_npc_talk(
        SimpleNamespace(context=object()), npc_obj, "Welcome", [mission],
    )

    assert result == (npc.TalkOutcome.DELIVER, mission)


def test_pygame_backend_reports_unavailable_when_loader_fails(monkeypatch):
    assert not pygame_merchant.PygameMerchantUnavailable.__module__.endswith("ui")

    monkeypatch.setattr(
        pygame_merchant,
        "_load_pygame",
        lambda: (_ for _ in ()).throw(
            pygame_merchant.PygameMerchantUnavailable("missing")
        ),
    )
    try:
        pygame_merchant._load_pygame()
    except pygame_merchant.PygameMerchantUnavailable:
        pass
    else:
        raise AssertionError("missing Pygame must remain an explicit fallback condition")


def test_shared_menu_runner_uses_existing_engine_and_returns_action(monkeypatch):
    class FakePygame:
        QUIT = 1
        KEYDOWN = 2
        K_ESCAPE = 10
        K_RETURN = 11
        K_KP_ENTER = 12
        K_UP = 13
        K_DOWN = 14
        K_k = 15
        K_j = 16
        K_QUESTION = 17
        event = SimpleNamespace(
            wait=lambda: SimpleNamespace(type=FakePygame.KEYDOWN, key=FakePygame.K_RETURN),
        )

    class Surface:
        def get_size(self):
            return (1600, 960)

        def fill(self, _color):
            pass

    engine = SimpleNamespace(
        pygame=FakePygame,
        logical_surface=Surface(),
        present=lambda: None,
    )
    context = SimpleNamespace(_runtime=SimpleNamespace(engine=engine))
    frame = pygame_menu.MenuFrame(
        "Merchant", "Choose", (pygame_menu.MenuItem("Work", "Details", "WORK"),), (), 0,
    )
    monkeypatch.setattr(pygame_menu, "_fit_font", lambda *args: object())
    monkeypatch.setattr(pygame_menu, "_draw_frame", lambda *args: None)

    assert pygame_menu.run_shared(context, (frame,), caption="test") == (
        "SELECT", "WORK", 0,
    )


def test_mission_menu_routes_to_shared_window_without_worker(monkeypatch):
    from src.spacehack import pygame_runtime

    monkeypatch.setattr(pygame_runtime, "is_shared_context", lambda _context: True)
    captured = {}

    def fake_shared(context, frames, **kwargs):
        captured["context"] = context
        captured["frames"] = frames
        return "BACK", "", 0

    monkeypatch.setattr(pygame_menu, "run_shared", fake_shared)
    ctx = SimpleNamespace(context=object())
    npc_obj = SimpleNamespace(name="Guild Master")

    result = _missions._run_pygame_interactive_missions(ctx, npc_obj, ())

    assert result == (_missions.MissionOutcome.BACK, None)
    assert captured["context"] is ctx.context
    assert captured["frames"][0].title == "Guild Master - available work"


def test_npc_talk_routes_to_shared_window_without_worker(monkeypatch):
    from src.spacehack import pygame_runtime

    monkeypatch.setattr(pygame_runtime, "is_shared_context", lambda _context: True)
    captured = {}

    monkeypatch.setattr(
        pygame_menu,
        "run_shared",
        lambda context, frames, **kwargs: captured.update(
            context=context, frames=frames,
        ) or ("SELECT", "WORK", 0),
    )
    ctx = SimpleNamespace(context=object())
    npc_obj = SimpleNamespace(name="Guild Master", guild="merchants", flavor_text="Welcome")

    result = npc._run_pygame_npc_talk(ctx, npc_obj, "Welcome", [])

    assert result == (npc.TalkOutcome.WORK, None)
    assert captured["context"] is ctx.context
    assert captured["frames"][0].items[0].action == "WORK"


def test_all_shared_adapters_bypass_workers(monkeypatch):
    from src.spacehack import pygame_runtime

    monkeypatch.setattr(pygame_runtime, "is_shared_context", lambda _context: True)

    menu_frame = pygame_menu.MenuFrame(
        "Menu", "", (pygame_menu.MenuItem("Go", "", "GO"),), (), 0,
    )
    screen_frame = pygame_screen.ScreenFrame(
        "Screen", (), (pygame_screen.ScreenRow("Go", action="GO"),),
    )
    split_frame = pygame_split.SplitFrame(
        "Split", "Left", "Right",
        (pygame_split.SplitRow("Go", "", "", "GO"),), (),
        "", "", "", 0, 0,
    )
    context = object()
    game_ctx = SimpleNamespace(context=context)
    calls = []

    monkeypatch.setattr(
        pygame_menu, "run_shared",
        lambda *args, **kwargs: calls.append("menu") or ("BACK", "", 0),
    )
    monkeypatch.setattr(
        pygame_screen, "run_shared",
        lambda *args, **kwargs: calls.append("screen") or ("BACK", "", 0),
    )
    monkeypatch.setattr(
        pygame_batch, "run_shared",
        lambda *args, **kwargs: calls.append("batch") or "BACK",
    )
    monkeypatch.setattr(
        pygame_split, "run_shared",
        lambda *args, **kwargs: calls.append("split") or ("BACK", "", 0, 0),
    )
    monkeypatch.setattr(
        pygame_quantity, "run_shared",
        lambda *args, **kwargs: calls.append("quantity") or None,
    )
    monkeypatch.setattr(
        pygame_quest_log, "run_shared",
        lambda *args, **kwargs: calls.append("quest_log") or ("BACK", 0),
    )

    for module in (
        pygame_menu, pygame_screen, pygame_split,
        pygame_quantity, pygame_quest_log,
    ):
        monkeypatch.setattr(
            module, "run", lambda *args, **kwargs: (_ for _ in ()).throw(
                AssertionError(f"{module.__name__} started a worker")
            ),
        )
    assert pygame_menu.run_for_context(context, (menu_frame,))[0] == "BACK"
    assert pygame_screen.run_for_context(context, screen_frame)[0] == "BACK"
    assert pygame_batch.run_for_context(context, lambda _console: None) == "BACK"
    assert pygame_quantity.run_for_context(context, game_ctx, "Buy", 1) is None
    assert pygame_quest_log.run_for_context(game_ctx)[0] == "BACK"

    assert pygame_split.run_interactive(
        game_ctx, lambda: split_frame, lambda *_args: True, caption="test",
    ) == "BACK"
    assert calls == [
        "menu", "screen", "batch", "quantity", "quest_log", "split",
    ]


def test_story_adapters_use_the_shared_menu_runner(monkeypatch):
    captured = []
    monkeypatch.setattr(
        pygame_menu,
        "run_for_context",
        lambda context, frames, **kwargs: captured.append(
            (context, frames),
        ) or ("DISMISS", "", 0),
    )
    monkeypatch.setattr(
        pygame_menu,
        "run",
        lambda *args, **kwargs: (_ for _ in ()).throw(
            AssertionError("shared story adapters must not start a worker")
        ),
    )
    ctx = SimpleNamespace(context=object())

    assert pygame_story.dismiss(
        ctx, title="Signal", body="Message", caption="test",
    ) == "DISMISS"
    assert captured[0][0] is ctx.context
    assert captured[0][1][0].title == "Signal"


def test_quest_log_guide_reopens_the_same_shared_modal(monkeypatch):
    from src.spacehack.menus import _quest_log

    outcomes = iter((("GUIDE", 2, True), ("BACK", 2, True)))
    calls = []
    states = []
    monkeypatch.setattr(
        "src.spacehack.help._run_help_guide",
        lambda ctx: calls.append(ctx),
    )
    monkeypatch.setattr(
        "src.spacehack.pygame_quest_log.run_for_context",
        lambda ctx, selected=0, confirm=False: states.append(
            (selected, confirm),
        ) or next(outcomes),
    )
    ctx = SimpleNamespace()

    assert _quest_log._run_pygame_quest_log(ctx) == (_quest_log.QuestLogOutcome.BACK, None)
    assert calls == [ctx]
    assert states == [(0, False), (2, True)]


def test_cargo_screen_uses_context_adapter_when_fixture_has_no_context(monkeypatch):
    from src.spacehack import trade

    captured = {}
    monkeypatch.setattr(
        pygame_screen,
        "run_for_context",
        lambda context, frame, **kwargs: captured.update(
            context=context, frame=frame,
        ) or ("BACK", "", frame.selected),
    )
    owned = SimpleNamespace(
        ship_id="starter",
        inventory={},
        cargo_used=0,
        mission_reserved=0,
        cargo_ammo=0,
        hull_damage_pct=0,
    )
    ctx = SimpleNamespace(
        player_owned_ship=owned,
        stats=SimpleNamespace(credits=0),
    )

    result = trade._run_pygame_cargo(ctx, owned, "Scout", 10)

    assert result is True
    assert captured["context"] is ctx


def test_title_menu_frames_do_not_draw_the_console_log():
    """The pre-game title menu must never paint a previous run's log band."""
    from src.spacehack import pygame_title

    frames = pygame_title.frames(save_available=True)

    assert frames
    assert all(frame.draw_log is False for frame in frames)
    assert all("CONTINUE" in item.label for item in frames[0].items if item.action == "CONTINUE")


def test_title_menu_frames_without_save_omit_continue():
    from src.spacehack import pygame_title

    frames = pygame_title.frames(save_available=False)

    assert all(item.action != "CONTINUE" for frame in frames for item in frame.items)
    assert frames[0].initial_selected == 0


def test_menu_draw_log_flag_round_trips_payload():
    frame = pygame_menu.MenuFrame(
        title="Mars",
        body="Choose an action.",
        items=(pygame_menu.MenuItem("Land", "Dock", "LAND"),),
        hints=("ESC back",),
        selected=0,
        draw_log=False,
    )

    restored = pygame_menu._frame_from_payload(pygame_menu._frame_payload(frame))

    assert restored == frame
    assert restored.draw_log is False


def test_menu_draw_frame_skips_log_when_flag_is_off(monkeypatch):
    """draw_log=False (title menu) must not paint the console-log band
    even when a shared context with a live game log is attached."""
    class FakePygame:
        class Rect:
            def __init__(self, *args):
                self.args = args

    class Surface:
        def get_size(self):
            return (1600, 960)

        def fill(self, _color):
            pass

        def set_clip(self, _rect):
            pass

    class FakeFont:
        def get_linesize(self):
            return 24

        def size(self, text):
            return len(text) * 10, 24

    screen = Surface()
    log_calls = []
    monkeypatch.setattr(
        pygame_ui, "draw_context_log",
        lambda *args, **kwargs: log_calls.append(args),
    )
    # The remaining painter helpers only need to not crash.
    for name in (
        "draw_panel", "draw_centered_text", "draw_rule",
        "draw_menu_row", "draw_text", "draw_wrapped_text",
    ):
        monkeypatch.setattr(pygame_ui, name, lambda *args, **kwargs: None)
    monkeypatch.setattr(pygame_ui, "fit_text", lambda text, *args, **kwargs: text)
    monkeypatch.setattr(
        pygame_ui, "wrap_text", lambda text, *args, **kwargs: (text,),
    )
    monkeypatch.setattr(
        pygame_ui, "visible_window", lambda *args, **kwargs: (0, 0),
    )

    context = SimpleNamespace()
    frame = pygame_menu.MenuFrame(
        "TITLE", "body", (pygame_menu.MenuItem("New", "d", "NEW"),), (), 0,
        draw_log=False,
    )
    pygame_menu._draw_frame(FakePygame, screen, FakeFont(), frame, context=context)

    assert log_calls == []

    # In-game menus keep the log band.
    frame = pygame_menu.MenuFrame(
        "TITLE", "body", (pygame_menu.MenuItem("New", "d", "NEW"),), (), 0,
    )
    pygame_menu._draw_frame(FakePygame, screen, FakeFont(), frame, context=context)

    assert len(log_calls) == 1


def test_exit_to_menu_confirm_returns_true_only_on_confirm(monkeypatch):
    from src.spacehack import __main__ as game_main
    from src.spacehack import pygame_story

    captured = {}
    monkeypatch.setattr(
        pygame_story,
        "confirm",
        lambda ctx, **kwargs: captured.update(
            ctx=ctx, kwargs=kwargs,
        ) or "CONFIRM",
    )
    ctx = SimpleNamespace()

    assert game_main._run_pygame_exit_confirm(ctx) is True
    assert captured["ctx"] is ctx
    assert captured["kwargs"]["title"] == "EXIT TO MAIN MENU"
    assert captured["kwargs"]["accept_label"] == "Save & Exit"
    assert captured["kwargs"]["cancel_label"] == "Keep Playing"

    for dismissal in ("BACK", "QUIT", None):
        monkeypatch.setattr(
            pygame_story,
            "confirm",
            lambda *args, _result=dismissal, **kwargs: _result,
        )
        assert game_main._run_pygame_exit_confirm(ctx) is False


def test_guide_says_esc_saves_and_confirms_before_exit():
    from src.spacehack.help import GUIDE_SECTIONS

    controls = next(
        section for section in GUIDE_SECTIONS
        if section.title == "Controls & Keybindings"
    )
    assert "save and exit to the main menu (asks first)" in controls.body


def test_font_path_prefers_bundled_font_over_system_match(monkeypatch):
    families = []

    class FakeFile:
        exists = True

        def is_file(self):
            return self.exists

        def __truediv__(self, _other):
            return self

    class FakePath:
        def __init__(self, *_args):
            self.parent = self

        def __truediv__(self, _other):
            return FakeFile()

    class FakePygame:
        class font:
            @staticmethod
            def match_font(family):
                families.append(family)
                return f"/system/{family}.ttf"

    monkeypatch.setattr(pygame_merchant, "Path", FakePath)

    assert pygame_merchant._font_path(FakePygame) is not None
    # The bundled font wins; the system font table is never consulted.
    assert families == []


def test_font_path_falls_back_to_system_fonts_when_bundled_missing(monkeypatch):
    families = []

    class FakeFile:
        def is_file(self):
            return False

        def __truediv__(self, _other):
            return self

    class FakePath:
        def __init__(self, *_args):
            self.parent = self

        def __truediv__(self, _other):
            return FakeFile()

    class FakePygame:
        class font:
            @staticmethod
            def match_font(family):
                families.append(family)
                return f"/system/{family}.ttf"

    monkeypatch.setattr(pygame_merchant, "Path", FakePath)

    assert (
        pygame_merchant._font_path(FakePygame)
        == "/system/DejaVu Sans Mono.ttf"
    )
    # Families are tried in order; the first system hit wins.
    assert families == ["DejaVu Sans Mono"]


def test_font_path_returns_none_when_no_font_is_found(monkeypatch):
    families = []

    class FakeFile:
        def is_file(self):
            return False

        def __truediv__(self, _other):
            return self

    class FakePath:
        def __init__(self, *_args):
            self.parent = self

        def __truediv__(self, _other):
            return FakeFile()

    class FakePygame:
        class font:
            @staticmethod
            def match_font(family):
                families.append(family)
                return None

    monkeypatch.setattr(pygame_merchant, "Path", FakePath)

    assert pygame_merchant._font_path(FakePygame) is None
    # Every candidate is exhausted before giving up.
    assert families == ["DejaVu Sans Mono", "Liberation Mono", "Courier New"]


def test_bundled_dejavu_mono_font_ships_with_the_package():
    from pathlib import Path

    bundled = Path(pygame_merchant.__file__).parent / "data" / "DejaVuSansMono.ttf"

    assert bundled.is_file()
