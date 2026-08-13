"""Tests for the native Pygame HUD/message-log overlay bridge."""

from __future__ import annotations

from types import SimpleNamespace

from src.spacehack import pygame_overlay, pygame_runtime, world


def test_overlay_segments_group_adjacent_cells_by_color_and_split_gaps():
    commands = (
        world.WorldDrawCommand(2, 1, "A", (1, 2, 3), None),
        world.WorldDrawCommand(3, 1, "B", (1, 2, 3), None),
        world.WorldDrawCommand(5, 1, "C", (1, 2, 3), None),
        world.WorldDrawCommand(6, 1, "D", (4, 5, 6), None),
    )

    assert pygame_overlay._segments(
        commands, x_min=0, x_max=10, y_min=0, y_max=3,
    ) == (
        pygame_overlay.OverlaySegment(2, 1, "AB", (1, 2, 3)),
        pygame_overlay.OverlaySegment(5, 1, "C", (1, 2, 3)),
        pygame_overlay.OverlaySegment(6, 1, "D", (4, 5, 6)),
    )


def test_overlay_segments_carry_background_and_split_runs_on_bg_change():
    # Mirrors the combat HUD shield line: the regen-rate cells share the
    # bar's foreground but paint a white background, so they must become
    # their own segment instead of merging into the unpainted run.
    commands = (
        world.WorldDrawCommand(5, 1, "#", (1, 2, 3), None),
        world.WorldDrawCommand(6, 1, "#", (1, 2, 3), (255, 255, 255)),
        world.WorldDrawCommand(7, 1, ".", (1, 2, 3), (255, 255, 255)),
        world.WorldDrawCommand(8, 1, ".", (1, 2, 3), None),
    )

    assert pygame_overlay._segments(
        commands, x_min=0, x_max=10, y_min=0, y_max=3,
    ) == (
        pygame_overlay.OverlaySegment(5, 1, "#", (1, 2, 3)),
        pygame_overlay.OverlaySegment(6, 1, "#.", (1, 2, 3), (255, 255, 255)),
        pygame_overlay.OverlaySegment(8, 1, ".", (1, 2, 3)),
    )


def test_overlay_capture_keeps_hud_and_log_regions_separate(monkeypatch):
    from src.spacehack import hud, message_log

    def fake_hud(console, _ctx, **_kwargs):
        console.print(x=80, y=2, string="HUD", fg=(10, 20, 30))
        console.print(x=1, y=2, string="not hud", fg=(99, 99, 99))

    def fake_log(console, _log, **_kwargs):
        console.print(x=0, y=54, string="old", fg=(40, 50, 60))
        console.print(x=0, y=55, string="> event", fg=(70, 80, 90))

    monkeypatch.setattr(hud, "render_hud", fake_hud)
    monkeypatch.setattr(message_log, "render_message_log", fake_log)

    frame = pygame_overlay.capture(
        SimpleNamespace(log=object()),
        mode="city",
        location="Earth",
        screen_width=100,
        screen_height=60,
        hud_view_height=54,
    )

    assert frame.hud == (
        pygame_overlay.OverlaySegment(80, 2, "HUD", (10, 20, 30)),
    )
    assert frame.messages == (
        pygame_overlay.OverlaySegment(0, 54, "old", (40, 50, 60)),
        pygame_overlay.OverlaySegment(0, 55, "> event", (70, 80, 90)),
    )
    assert frame.hud_x == 80
    assert frame.message_top == 54
    assert frame.message_height == 6


def test_normalize_bg_maps_default_black_to_none():
    assert pygame_overlay._normalize_bg(None) is None
    assert pygame_overlay._normalize_bg((0, 0, 0)) is None
    assert pygame_overlay._normalize_bg((255, 255, 255)) == (255, 255, 255)


def test_overlay_payload_round_trips_segments_and_layout():
    frame = pygame_overlay.OverlayFrame(
        hud=(pygame_overlay.OverlaySegment(80, 0, "HUD", (1, 2, 3)),),
        messages=(
            pygame_overlay.OverlaySegment(0, 54, "msg", (4, 5, 6), (255, 255, 255)),
        ),
        hud_x=80,
        hud_top=0,
        hud_height=54,
        message_top=54,
        message_height=6,
        shields=(pygame_overlay.ShieldBubble(12, 8, 2, 1, 0.75),),
    )

    payload = pygame_overlay.payload(frame)

    assert payload["hud"][0] == {
        "x": 80, "y": 0, "text": "HUD", "color": (1, 2, 3), "bg": None,
    }
    assert payload["messages"][0]["text"] == "msg"
    assert payload["messages"][0]["bg"] == (255, 255, 255)
    assert payload["hud_height"] == 54
    assert payload["shields"] == ({
        "x": 12, "y": 8, "width": 2, "height": 1, "strength": 0.75,
    },)
    restored = pygame_overlay.frame_from_payload(payload)
    assert restored == frame


def test_overlay_payload_round_trips_floating_text():
    frame = pygame_overlay.OverlayFrame(
        hud=(),
        messages=(),
        hud_x=80,
        hud_top=0,
        hud_height=54,
        message_top=54,
        message_height=6,
        shields=(),
        floaters=(
            pygame_overlay.FloatingText("-14", 32, 20, (255, 140, 70), 2, 8),
            pygame_overlay.FloatingText("MISS", 12, 5, (170, 170, 185), 0, 6),
        ),
    )

    payload = pygame_overlay.payload(frame)

    assert payload["floaters"] == (
        {"text": "-14", "x": 32, "y": 20, "color": (255, 140, 70),
         "age": 2, "lifetime": 8},
        {"text": "MISS", "x": 12, "y": 5, "color": (170, 170, 185),
         "age": 0, "lifetime": 6},
    )
    assert pygame_overlay.frame_from_payload(payload) == frame


def test_frame_from_commands_carries_floating_text_through():
    floater = pygame_overlay.FloatingText("-4", 10, 8, (255, 140, 70), 1, 8)

    frame = pygame_overlay._frame_from_commands(
        (),
        screen_width=100,
        screen_height=60,
        hud_view_height=54,
        floaters=(floater,),
    )

    assert frame.floaters == (floater,)


def test_pirate_scout_combat_and_exploration_both_have_zero_shields():
    from src.spacehack.combat._stats import init_combat_state
    from src.spacehack.data.npc_ships import find_npc_ship
    from src.spacehack.data.ships import find_ship
    from src.spacehack.data.pilot_skills import PilotSkills

    scout = find_npc_ship("pirate_scout")
    player_state, enemy = init_combat_state(
        find_ship("starter"),
        SimpleNamespace(
            modules=(),
            weapons=(),
            weapon_ammo={},
            hull_damage_pct=0,
        ),
        world.Position(1, 1),
        PilotSkills(gunnery=10, piloting=10, engineering=10),
        scout,
        world.Position(3, 2),
    )

    assert player_state["max_shields"] == 0
    assert enemy.shields == 0

    game_map = world.GameMap(
        width=8,
        height=6,
        tiles=[[world.DUNGEON_FLOOR for _ in range(8)] for _ in range(6)],
        entities=[
            world.Entity(
                "p", (255, 100, 100), world.Position(3, 2),
                npc_ship_id="pirate_scout",
            ),
        ],
    )
    assert pygame_overlay.shield_bubbles_for_map(
        game_map,
        camera_x=0,
        camera_y=0,
        region_w=8,
        region_h=6,
    ) == ()


def test_shield_bubbles_omit_unshielded_pirate_scout():
    game_map = world.GameMap(
        width=8,
        height=6,
        tiles=[[world.DUNGEON_FLOOR for _ in range(8)] for _ in range(6)],
        entities=[
            world.Entity(
                "p", (255, 100, 100), world.Position(3, 2),
                npc_ship_id="pirate_scout",
            ),
        ],
    )

    assert pygame_overlay.shield_bubbles_for_map(
        game_map,
        camera_x=0,
        camera_y=0,
        region_w=8,
        region_h=6,
    ) == ()


def test_shield_bubbles_use_npc_modules_without_hull_base_shields():
    game_map = world.GameMap(
        width=8,
        height=6,
        tiles=[[world.DUNGEON_FLOOR for _ in range(8)] for _ in range(6)],
        entities=[
            world.Entity(
                "P", (220, 60, 60), world.Position(3, 2),
                npc_ship_id="pirate_raider",
            ),
        ],
    )

    assert pygame_overlay.shield_bubbles_for_map(
        game_map,
        camera_x=0,
        camera_y=0,
        region_w=8,
        region_h=6,
    ) == (pygame_overlay.ShieldBubble(3, 2),)


def test_shield_bubbles_include_shielded_ships_and_apply_camera_region_offset():
    game_map = world.GameMap(
        width=20,
        height=12,
        tiles=[[world.DUNGEON_FLOOR for _ in range(20)] for _ in range(12)],
        entities=[
            world.Entity(
                "S", (100, 200, 255), world.Position(7, 5),
                ship_id="scout", owned=True,
            ),
            world.Entity(
                "t", (180, 180, 180), world.Position(8, 5),
                ship_id="starter", owned=False,
            ),
            world.Entity(
                "T", (180, 180, 180), world.Position(6, 5),
                ship_id="starter", owned=True,
            ),
            world.Entity(
                "P", (255, 100, 100), world.Position(10, 6),
                npc_ship_id="pirate_raider",
            ),
        ],
    )

    bubbles = pygame_overlay.shield_bubbles_for_map(
        game_map,
        camera_x=4,
        camera_y=2,
        region_x=3,
        region_y=1,
        region_w=8,
        region_h=6,
        player_owned_ship=SimpleNamespace(modules=()),
    )

    assert bubbles == (
        pygame_overlay.ShieldBubble(6, 4),
        pygame_overlay.ShieldBubble(9, 5),
    )


def test_shield_bubbles_keep_matching_owned_shield_loadout():
    game_map = world.GameMap(
        width=8,
        height=6,
        tiles=[[world.DUNGEON_FLOOR for _ in range(8)] for _ in range(6)],
        entities=[
            world.Entity(
                "C", (180, 180, 180), world.Position(3, 2),
                ship_id="cruiser", owned=True,
            ),
        ],
    )

    bubbles = pygame_overlay.shield_bubbles_for_map(
        game_map,
        camera_x=0,
        camera_y=0,
        region_w=8,
        region_h=6,
        player_owned_ship=SimpleNamespace(
            ship_id="cruiser",
            modules=("shield_mk1",),
        ),
    )

    assert bubbles == (pygame_overlay.ShieldBubble(3, 2),)


def test_shield_bubbles_omit_unshielded_owned_hull_when_loadout_is_shielded():
    game_map = world.GameMap(
        width=8,
        height=6,
        tiles=[[world.DUNGEON_FLOOR for _ in range(8)] for _ in range(6)],
        entities=[
            world.Entity(
                "T", (180, 180, 180), world.Position(3, 2),
                ship_id="starter", owned=True,
            ),
        ],
    )

    bubbles = pygame_overlay.shield_bubbles_for_map(
        game_map,
        camera_x=0,
        camera_y=0,
        region_w=8,
        region_h=6,
        player_owned_ship=SimpleNamespace(
            ship_id="cruiser",
            modules=("shield_mk1",),
        ),
    )

    assert bubbles == ()


def test_shield_bubbles_cull_ships_outside_the_viewport():
    game_map = world.GameMap(
        width=20,
        height=12,
        tiles=[[world.DUNGEON_FLOOR for _ in range(20)] for _ in range(12)],
        entities=[
            world.Entity(
                "S", (100, 200, 255), world.Position(18, 5),
                ship_id="scout", owned=True,
            ),
        ],
    )

    assert pygame_overlay.shield_bubbles_for_map(
        game_map,
        camera_x=0,
        camera_y=0,
        region_w=8,
        region_h=6,
        player_owned_ship=SimpleNamespace(modules=()),
    ) == ()


def test_draw_segments_offsets_text_inside_panel_padding(monkeypatch):
    drawn = []

    class FakeScreen:
        def set_clip(self, _clip):
            pass

    class FakePygame:
        class Rect:
            def __init__(self, *args):
                self.args = args

    class FakeFont:
        def size(self, text):
            return (len(text) * 8, 12)

        def get_linesize(self):
            return 12

    monkeypatch.setattr(
        pygame_overlay.pygame_ui,
        "draw_text",
        lambda _pygame, _screen, _font, text, x, y, **_kwargs: drawn.append((text, x, y)),
    )

    pygame_overlay._draw_segments(
        FakePygame,
        FakeScreen(),
        FakeFont(),
        (pygame_overlay.OverlaySegment(80, 2, "HUD", (1, 2, 3)),),
        origin_x=1280,
        origin_y=0,
        width=320,
        height=864,
        origin_cell_x=80,
        origin_cell_y=0,
    )

    assert drawn == [("HUD", 1292, 36)]


def test_draw_segments_paints_background_highlight_before_text(monkeypatch):
    drawn = []
    filled = []

    class FakeScreen:
        def set_clip(self, _clip):
            pass

    class FakePygame:
        class Rect:
            def __init__(self, *args):
                self.args = args

        class draw:
            @staticmethod
            def rect(_screen, color, rect):
                filled.append((color, rect))

    class FakeFont:
        def size(self, text):
            return (len(text) * 8, 12)

        def get_linesize(self):
            return 12

    monkeypatch.setattr(
        pygame_overlay.pygame_ui,
        "draw_text",
        lambda _pygame, _screen, _font, text, x, y, **_kwargs: drawn.append((text, x, y)),
    )

    pygame_overlay._draw_segments(
        FakePygame,
        FakeScreen(),
        FakeFont(),
        (pygame_overlay.OverlaySegment(80, 2, "##", (1, 2, 3), (255, 255, 255)),),
        origin_x=1280,
        origin_y=0,
        width=320,
        height=864,
        origin_cell_x=80,
        origin_cell_y=0,
    )

    assert len(filled) == 1
    fill_color, fill_rect = filled[0]
    assert fill_color == (255, 255, 255)
    # The highlight hugs the drawn glyphs (2 chars x 8px), not the full cells.
    assert fill_rect.args == (1292, 36, 16, 16)
    assert drawn == [("##", 1292, 36)]


def test_draw_segments_chains_contiguous_segments_by_glyph_width(monkeypatch):
    # Mirrors the combat shield line: a white regen segment splits the run,
    # but the trailing text must land exactly where an un-split line would
    # put it — never pushed right by cell-aligned jumps.
    drawn = []
    filled = []

    class FakeScreen:
        def set_clip(self, _clip):
            pass

    class FakePygame:
        class Rect:
            def __init__(self, *args):
                self.args = args

        class draw:
            @staticmethod
            def rect(_screen, color, rect):
                filled.append((color, rect))

    class FakeFont:
        def size(self, text):
            return (len(text) * 8, 12)

        def get_linesize(self):
            return 12

    monkeypatch.setattr(
        pygame_overlay.pygame_ui,
        "draw_text",
        lambda _pygame, _screen, _font, text, x, y, **_kwargs: drawn.append((text, x, y)),
    )

    pygame_overlay._draw_segments(
        FakePygame,
        FakeScreen(),
        FakeFont(),
        (
            pygame_overlay.OverlaySegment(80, 5, "Shd  ", (1, 2, 3)),
            pygame_overlay.OverlaySegment(85, 5, "#####", (1, 2, 3), (255, 255, 255)),
            pygame_overlay.OverlaySegment(90, 5, "#.... 60%", (1, 2, 3)),
        ),
        origin_x=1280,
        origin_y=0,
        width=320,
        height=864,
        origin_cell_x=80,
        origin_cell_y=0,
    )

    # 'Shd  ' at 1292 (5x8px) -> white segment chains at 1332 -> trailing
    # text chains at 1372. A cell-aligned layout would have placed the white
    # segment at 1372 and the trailing text at 1452.
    assert drawn == [
        ("Shd  ", 1292, 84),
        ("#####", 1332, 84),
        ("#.... 60%", 1372, 84),
    ]
    assert len(filled) == 1
    fill_color, fill_rect = filled[0]
    assert fill_color == (255, 255, 255)
    assert fill_rect.args == (1332, 84, 40, 16)


def test_draw_segments_split_line_keeps_trailing_text_at_un_split_position(monkeypatch):
    # Regression for the reported bug: as the shield-regen highlight grows,
    # the ' 60%' readout must stay exactly where an un-split line renders it.
    drawn = []

    class FakeScreen:
        def set_clip(self, _clip):
            pass

    class FakePygame:
        class Rect:
            def __init__(self, *args):
                self.args = args

        class draw:
            @staticmethod
            def rect(_screen, _color, rect):
                pass

    class FakeFont:
        def size(self, text):
            return (len(text) * 8, 12)

        def get_linesize(self):
            return 12

    monkeypatch.setattr(
        pygame_overlay.pygame_ui,
        "draw_text",
        lambda _pygame, _screen, _font, text, x, y, **_kwargs: drawn.append((text, x, y)),
    )

    def draw_with(segments):
        drawn.clear()
        pygame_overlay._draw_segments(
            FakePygame, FakeScreen(), FakeFont(), segments,
            origin_x=1280, origin_y=0, width=320, height=864,
            origin_cell_x=80, origin_cell_y=0,
        )
        return dict((text, x) for text, x, _y in drawn)

    # Rate 0: one un-split line (' 60%' starts 15 chars in, '%' is the 19th).
    draw_with((pygame_overlay.OverlaySegment(80, 5, "Shd  ######.... 60%", (1, 2, 3)),))
    # Rate 10: the highlight splits the line into three segments.
    split = draw_with((
        pygame_overlay.OverlaySegment(80, 5, "Shd  ", (1, 2, 3)),
        pygame_overlay.OverlaySegment(85, 5, "######....", (1, 2, 3), (255, 255, 255)),
        pygame_overlay.OverlaySegment(95, 5, " 60%", (1, 2, 3)),
    ))

    # The '%' glyph must land at the same pixel whether the line is split
    # (1412 + 3*8) or un-split (1292 + 18*8) — both are 1436.
    assert split[" 60%"] == 1292 + 15 * 8
    assert split[" 60%"] + 3 * 8 == 1292 + 18 * 8


def test_draw_segments_resets_chaining_at_row_boundaries(monkeypatch):
    drawn = []

    class FakeScreen:
        def set_clip(self, _clip):
            pass

    class FakePygame:
        class Rect:
            def __init__(self, *args):
                self.args = args

        class draw:
            @staticmethod
            def rect(_screen, _color, rect):
                pass

    class FakeFont:
        def size(self, text):
            return (len(text) * 8, 12)

        def get_linesize(self):
            return 12

    monkeypatch.setattr(
        pygame_overlay.pygame_ui,
        "draw_text",
        lambda _pygame, _screen, _font, text, x, y, **_kwargs: drawn.append((text, x, y)),
    )

    pygame_overlay._draw_segments(
        FakePygame, FakeScreen(), FakeFont(),
        (
            pygame_overlay.OverlaySegment(80, 5, "Shd  ", (1, 2, 3)),
            pygame_overlay.OverlaySegment(85, 6, "AB", (1, 2, 3)),  # next row, x-contiguous
        ),
        origin_x=1280, origin_y=0, width=320, height=864,
        origin_cell_x=80, origin_cell_y=0,
    )

    # Row 2 starts at its cell position (1292 + 5*16), not chained after row 1.
    assert drawn == [("Shd  ", 1292, 84), ("AB", 1372, 100)]


def test_draw_segments_falls_back_to_cell_position_on_gap(monkeypatch):
    drawn = []

    class FakeScreen:
        def set_clip(self, _clip):
            pass

    class FakePygame:
        class Rect:
            def __init__(self, *args):
                self.args = args

        class draw:
            @staticmethod
            def rect(_screen, _color, rect):
                pass

    class FakeFont:
        def size(self, text):
            return (len(text) * 8, 12)

        def get_linesize(self):
            return 12

    monkeypatch.setattr(
        pygame_overlay.pygame_ui,
        "draw_text",
        lambda _pygame, _screen, _font, text, x, y, **_kwargs: drawn.append((text, x, y)),
    )

    pygame_overlay._draw_segments(
        FakePygame,
        FakeScreen(),
        FakeFont(),
        (
            pygame_overlay.OverlaySegment(80, 5, "AB", (1, 2, 3)),
            pygame_overlay.OverlaySegment(83, 5, "CD", (1, 2, 3)),  # gap at cell 82
        ),
        origin_x=1280,
        origin_y=0,
        width=320,
        height=864,
        origin_cell_x=80,
        origin_cell_y=0,
    )

    # Non-contiguous segments keep their cell-aligned positions.
    assert drawn == [("AB", 1292, 84), ("CD", 1340, 84)]


def test_bubble_ring_width_thins_as_strength_drops():
    assert pygame_overlay._bubble_ring_width(1.0) == 3
    assert pygame_overlay._bubble_ring_width(0.75) == 3
    assert pygame_overlay._bubble_ring_width(0.5) == 2
    assert pygame_overlay._bubble_ring_width(0.25) == 1
    assert pygame_overlay._bubble_ring_width(0.0) == 1
    # Out-of-range strengths clamp to the hairline/full endpoints.
    assert pygame_overlay._bubble_ring_width(-0.5) == 1
    assert pygame_overlay._bubble_ring_width(1.5) == 3


def test_draw_shield_bubbles_thins_ring_and_drops_inner_at_low_strength():
    ellipses = []

    class FakeScreen:
        def set_clip(self, _clip):
            pass

    class FakeRect:
        def __init__(self, x, y, width, height):
            self.x, self.y, self.width, self.height = x, y, width, height

        def inflate(self, dx, dy):
            return FakeRect(self.x, self.y, self.width + dx, self.height + dy)

    class FakePygame:
        Rect = FakeRect

        class draw:
            @staticmethod
            def ellipse(_screen, color, rect, width=0):
                ellipses.append((color, rect, width))

    pygame_overlay._draw_shield_bubbles(
        FakePygame,
        FakeScreen(),
        (
            pygame_overlay.ShieldBubble(1, 1, 1, 1, 1.0),
            pygame_overlay.ShieldBubble(3, 1, 1, 1, 0.0),
        ),
        map_width=8,
        map_height=6,
    )

    # Full shield: 3px outer ring + 1px inner ring. Depleted shield:
    # a single 1px hairline with no inner ring.
    assert [width for _color, _rect, width in ellipses] == [3, 1, 1]


def test_present_exploration_uses_shared_overlay_without_fallback(monkeypatch):
    frame = object()
    shared_calls = []
    shared_ctx = SimpleNamespace(
        log=object(),
        context=SimpleNamespace(
            _runtime=object(),
            present=lambda console, **kwargs: shared_calls.append((console, kwargs)),
        ),
    )
    monkeypatch.setattr(pygame_overlay, "capture", lambda *_args, **_kwargs: frame)

    assert pygame_overlay.present_exploration(
        shared_ctx,
        "console",
        mode="city",
        location="Earth",
        screen_width=100,
        screen_height=60,
        hud_view_height=54,
    ) is True
    assert shared_calls == [("console", {"overlay": frame})]

    fallback_calls = []
    fallback_ctx = SimpleNamespace(
        log=object(),
        context=SimpleNamespace(
            present=lambda console: fallback_calls.append(("present", console)),
        ),
    )
    from src.spacehack import hud, message_log
    monkeypatch.setattr(hud, "render_hud", lambda *args, **kwargs: fallback_calls.append(("hud", args[0])))
    monkeypatch.setattr(message_log, "render_message_log", lambda *args, **kwargs: fallback_calls.append(("log", args[0])))

    assert pygame_overlay.present_exploration(
        fallback_ctx,
        "console",
        mode="city",
        location="Earth",
        screen_width=100,
        screen_height=60,
        hud_view_height=54,
    ) is False
    assert fallback_calls == [("hud", "console"), ("log", "console"), ("present", "console")]


def test_shared_context_preserves_legacy_present_call_without_overlay():
    calls = []
    runtime = SimpleNamespace(
        present=lambda console, **kwargs: calls.append((console, kwargs)),
    )
    context = pygame_runtime.PygameContext(runtime)
    console = object()

    context.present(console)

    assert calls == [(console, {})]


def test_shared_context_forwards_optional_overlay_to_runtime():
    calls = []
    runtime = SimpleNamespace(
        present=lambda console, **kwargs: calls.append((console, kwargs)),
    )
    context = pygame_runtime.PygameContext(runtime)
    overlay = object()
    console = object()

    context.present(console, overlay=overlay)

    assert calls == [(console, {"overlay": overlay})]
