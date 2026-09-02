"""Regression coverage for dungeon ambient light and sight extension.

Phase 4 of the dynamic lighting system: glow fungus in BSP-carved
rooms emits light that extends the player's sight radius, and the
light grid tints visible cells while staying fog-gated (unseen cells
carry no light).

See ``docs/design/in_progress/27_DESIGN_DYNAMIC_LIGHTING.md`` Phase 4.
"""

from __future__ import annotations

from src.spacehack import dungeon_fov, world
from src.spacehack.dungeon_bsp import generate_dungeon
from src.spacehack.dungeon_params import DungeonParams


def _make_dungeon_with_fungus():
    """Generate a dungeon that has at least one glow_fungus tile."""
    for _ in range(50):
        params = DungeonParams(width=50, height=40)
        game_map, spawn = generate_dungeon(params)
        if any(
            tile.kind == "glow_fungus"
            for row in game_map.tiles
            for tile in row
        ):
            return game_map, spawn
    return game_map, spawn


def test_dungeon_generation_places_glow_fungus():
    game_map, _ = _make_dungeon_with_fungus()
    fungus = [
        (x, y)
        for y, row in enumerate(game_map.tiles)
        for x, tile in enumerate(row)
        if tile.kind == "glow_fungus"
    ]
    assert fungus, "no glow_fungus placed after 50 generations"
    # Fungus is walkable.
    for x, y in fungus:
        assert game_map.tiles[y][x].walkable


def test_glow_fungus_is_in_static_light_table():
    from src.spacehack.data.lighting import light_spec_for_kind

    spec = light_spec_for_kind("glow_fungus")
    assert spec is not None
    assert spec.radius == 3


def test_reveal_around_seeds_dungeon_light_grid():
    game_map, spawn = _make_dungeon_with_fungus()
    dungeon_fov.init_fog(game_map)
    # Find a fungus tile and reveal around it so the light is in sight.
    fungus = next(
        (x, y)
        for y, row in enumerate(game_map.tiles)
        for x, tile in enumerate(row)
        if tile.kind == "glow_fungus"
    )
    reveal_pos = world.Position(*fungus)
    dungeon_fov.reveal_around(game_map, reveal_pos)
    # A dungeon with fungus gets a light grid.
    assert game_map.light_grid is not None
    # Some visible cells carry non-zero light.
    lit = [
        (x, y)
        for y, row in enumerate(game_map.light_grid)
        for x, cell in enumerate(row)
        if cell != (0, 0, 0)
    ]
    assert lit, "no lit cells despite glow fungus"


def test_light_grid_is_masked_to_visible_cells():
    game_map, spawn = _make_dungeon_with_fungus()
    dungeon_fov.init_fog(game_map)
    dungeon_fov.reveal_around(game_map, spawn)
    # Cells outside the current LOS carry no light, even if a fungus
    # is nearby (light is fog-gated).
    for y in range(game_map.height):
        for x in range(game_map.width):
            if not game_map.visible[y][x]:
                assert game_map.light_grid[y][x] == (0, 0, 0), (
                    f"unseen cell ({x},{y}) carries light"
                )


def test_lit_cells_extend_sight_beyond_base_radius():
    """A glow fungus within sight reveals cells beyond the base radius."""
    # Build a small flat dungeon: a corridor with fungus in the middle.
    width, height = 21, 3
    tiles = [[world.DUNGEON_WALL for _ in range(width)] for _ in range(height)]
    for x in range(1, width - 1):
        tiles[1][x] = world.DUNGEON_FLOOR
    # Place fungus at x=5, player at x=1, sight radius 3.
    tiles[1][5] = world.GLOW_FUNGUS
    game_map = world.GameMap(width=width, height=height, tiles=tiles, entities=[])
    player_pos = world.Position(1, 1)
    dungeon_fov.init_fog(game_map)
    # With sight radius 3, the player sees x=1..4. The fungus at x=5 is
    # at distance 4 — just outside the base radius. But wait: distance
    # 3 reaches x=4, not x=5. So fungus at x=5 isn't visible yet.
    # Let's place fungus at x=4 (distance 3, within sight).
    tiles[1][4] = world.GLOW_FUNGUS
    tiles[1][5] = world.DUNGEON_FLOOR
    game_map = world.GameMap(width=width, height=height, tiles=tiles, entities=[])
    dungeon_fov.init_fog(game_map)
    dungeon_fov.reveal_around(game_map, player_pos, radius=3)
    # Player sees x=1..4 (radius 3). Fungus at x=4 is visible.
    assert game_map.visible[1][4]
    # The fungus (radius 3) should reveal x=5..7, beyond the base radius.
    # x=7 is at distance 6 from the player (beyond radius 3) but within
    # the fungus's light radius.
    assert game_map.visible[1][7], "fungus didn't extend sight to x=7"


def test_dungeon_without_fungus_has_no_light_grid():
    """A dungeon with no light sources gets no light grid."""
    width, height = 15, 7
    tiles = [[world.DUNGEON_WALL for _ in range(width)] for _ in range(height)]
    for x in range(1, width - 1):
        tiles[3][x] = world.DUNGEON_FLOOR
    game_map = world.GameMap(width=width, height=height, tiles=tiles, entities=[])
    player_pos = world.Position(2, 3)
    dungeon_fov.init_fog(game_map)
    dungeon_fov.reveal_around(game_map, player_pos, radius=5)
    assert game_map.light_grid is None


# ----- The undulating alien door pulses (Mars prison descent) ----------


def test_alien_door_is_in_static_light_table_with_pulse():
    """The Mars door emits a small pulsing light — the landmark's
    "undulating" description made visible."""
    from src.spacehack.data.lighting import light_spec_for_kind

    spec = light_spec_for_kind("alien_door")
    assert spec is not None
    assert spec.radius == 3
    assert 0.4 <= spec.intensity <= 0.7  # a small amount of light
    assert spec.flicker == "pulse"


def test_mars_landmark_door_cells_collect_as_pulsing_sources():
    """Every ~=~=~=~=~ tile stamped from mars_signal_door becomes a
    pulse-flicker light source carrying its own tile colour."""
    import copy

    from src.spacehack import dungeon, landmark
    from src.spacehack.data.planets import find_planet_spec
    from src.spacehack.engine import seed_rng
    from src.spacehack.lighting import collect_light_sources

    seed_rng(11)
    params = find_planet_spec("mars").dungeon_params
    game_map, spawn = dungeon.generate_dungeon(params)
    asset = copy.deepcopy(landmark.load_landmark("mars_signal_door"))
    landmark.stamp_landmark(game_map, asset, spawn)

    door_cells = {
        (x, y)
        for y, row in enumerate(game_map.tiles)
        for x, tile in enumerate(row)
        if tile.kind == "alien_door"
    }
    assert door_cells, "landmark must stamp alien_door tiles"

    sources = collect_light_sources(game_map)
    door_sources = {(s.x, s.y): s for s in sources if (s.x, s.y) in door_cells}
    assert set(door_sources) == door_cells
    assert all(s.flicker == "pulse" for s in door_sources.values())
    # The two glyphs carry different colours; the light follows the tile.
    colours = {s.colour for s in door_sources.values()}
    assert len(colours) == 2


def test_dungeon_seed_caches_sources_and_recompute_masks_and_animates():
    """The seed pass caches light_sources so the per-frame recompute can
    animate; recompute stays fog-gated and the pulse varies over time."""
    width, height = 15, 7
    tiles = [[world.DUNGEON_WALL for _ in range(width)] for _ in range(height)]
    for x in range(1, width - 1):
        tiles[3][x] = world.DUNGEON_FLOOR
    for i, x in enumerate(range(4, 11)):
        tiles[3][x] = (
            world.UNDULATING_DOOR_A if i % 2 == 0 else world.UNDULATING_DOOR_B
        )
    game_map = world.GameMap(width=width, height=height, tiles=tiles, entities=[])
    dungeon_fov.init_fog(game_map)
    dungeon_fov.reveal_around(game_map, world.Position(2, 3), radius=5)
    dungeon_fov._seed_dungeon_light_grid(game_map)

    assert game_map.light_sources, "seed must cache sources for the frame loop"
    assert game_map.light_grid is not None
    # Fog gate: a far-off cell outside LOS stays black even though the
    # door's radius would reach it after recompute.
    from src.spacehack.lighting import recompute_light_grid

    sources = game_map.light_sources
    recompute_light_grid(
        game_map, sources, t=0,
        occluder=lambda x, y: not game_map.tiles[y][x].walkable,
    )
    assert game_map.light_grid[3][13] == (0, 0, 0)
    # Animation: the pulse multiplier differs at different frame clocks.
    probe = (3, 3)  # visible side of the door, inside its radius
    recompute_light_grid(
        game_map, sources, t=0,
        occluder=lambda x, y: not game_map.tiles[y][x].walkable,
    )
    at_zero = game_map.light_grid[probe[1]][probe[0]]
    recompute_light_grid(
        game_map, sources, t=7,
        occluder=lambda x, y: not game_map.tiles[y][x].walkable,
    )
    at_seven = game_map.light_grid[probe[1]][probe[0]]
    assert at_zero != at_seven, "pulse must vary with the frame clock"


def test_opaque_emitter_does_not_reveal_through_itself():
    """The alien door glows but never extends sight through itself —
    the sealed chamber behind it stays fogged (regression: pulsing the
    door revealed the chamber via light-radius rays)."""
    width, height = 15, 9
    tiles = [[world.DUNGEON_WALL for _ in range(width)] for _ in range(height)]
    # Chamber rows north of the door, corridor rows south.
    for y in (2, 3, 4, 6, 7):
        for x in range(1, width - 1):
            tiles[y][x] = world.DUNGEON_FLOOR
    for i, x in enumerate(range(4, 11)):
        tiles[5][x] = (
            world.UNDULATING_DOOR_A if i % 2 == 0 else world.UNDULATING_DOOR_B
        )
    game_map = world.GameMap(width=width, height=height, tiles=tiles, entities=[])
    dungeon_fov.init_fog(game_map)
    dungeon_fov.reveal_around(game_map, world.Position(7, 7), radius=6)

    # The door row itself is in sight and glows...
    assert any(game_map.visible[5][x] for x in range(4, 11))
    # ...the corridor on the player's side is lit...
    assert any(
        game_map.light_grid[6][x] != (0, 0, 0) for x in range(4, 11)
    ), "door light should still spill onto the player's side"
    # ...but nothing behind the door is revealed or lit.
    for y in (2, 3, 4):
        for x in range(2, width - 2):
            assert not game_map.visible[y][x], (x, y)
            if game_map.light_grid is not None:
                assert game_map.light_grid[y][x] == (0, 0, 0), (x, y)


# ----- Prison panel vocabulary (doc 29 phase 1) ------------------------


def test_prison_panel_states_in_light_table():
    """The three lit panel states emit; the dormant one does not."""
    from src.spacehack.data.lighting import light_spec_for_kind

    assert light_spec_for_kind("prison_panel_off") is None
    dim = light_spec_for_kind("prison_panel_dim")
    assert (dim.radius, dim.intensity, dim.flicker) == (2, 0.35, "pulse")
    mid = light_spec_for_kind("prison_panel_mid")
    assert (mid.radius, mid.intensity, mid.flicker) == (3, 0.6, "pulse")
    normal = light_spec_for_kind("prison_panel_normal")
    assert (normal.radius, normal.intensity, normal.flicker) == (5, 0.9, "steady")
    alarm = light_spec_for_kind("prison_panel_alarm")
    assert (alarm.radius, alarm.intensity, alarm.flicker) == (5, 1.0, "alarm")


def test_alarm_profile_strobes_hard_and_out_of_phase():
    """The alarm strobe swings between a dim baseline and full brightness
    on a fixed cadence, and adjacent panels blink out of phase."""
    from src.spacehack.lighting import FLICKER_PROFILES, LightSource

    alarm = FLICKER_PROFILES["alarm"]
    source = LightSource(x=3, y=3, colour=(255, 64, 48), radius=5)
    values = {alarm(source, t) for t in range(16)}
    assert values == {0.35, 1.0}, values

    neighbour = LightSource(x=4, y=3, colour=(255, 64, 48), radius=5)
    same_frame = [
        (alarm(source, t), alarm(neighbour, t)) for t in range(16)
    ]
    assert any(a != b for a, b in same_frame), (
        "adjacent alarm panels must blink out of phase"
    )


# ----- Prison panel scatter (doc 29 phase 2) ---------------------------


def test_prison_floors_carry_dormant_panels():
    """Every prison floor spec scatters PRISON_PANEL_OFF panels; a
    generated floor really has them and stays dark (no light grid)."""
    from src.spacehack import dungeon as dungeon_mod
    from src.spacehack.data.dungeon_extensions import find_extension

    extension = find_extension("mars_alien_prison")
    assert extension.floors, "prison extension must have floors"
    for spec in extension.floors:
        assert spec.params.panel_tile is world.PRISON_PANEL_OFF, spec.floor
        assert spec.params.panel_density > 0, spec.floor

    game_map, _spawn = dungeon_mod.generate_dungeon(extension.floors[0].params)
    dungeon_mod.populate_dungeon(game_map, extension.floors[0].params, _spawn)
    panels = [
        (x, y)
        for y, row in enumerate(game_map.tiles)
        for x, tile in enumerate(row)
        if tile.kind == "prison_panel_off"
    ]
    assert panels, "F1 must scatter dormant panels"
    assert all(game_map.tiles[y][x].walkable for x, y in panels)

    dungeon_fov.init_fog(game_map)
    dungeon_fov.reveal_around(game_map, _spawn, radius=8)
    assert game_map.light_grid is None, "all-off panels must leave F1 dark"


def test_panel_scatter_leaves_ordinary_dungeons_untouched():
    """Dungeons without panel params generate exactly as before."""
    params = DungeonParams(width=50, height=40)
    game_map, spawn = generate_dungeon(params)
    populate = __import__(
        "src.spacehack.dungeon_population", fromlist=["populate_dungeon"],
    ).populate_dungeon
    populate(game_map, params, spawn)
    assert not any(
        tile.kind.startswith("prison_panel")
        for row in game_map.tiles for tile in row
    )


# ----- Facility phase wake-up (doc 29 phase 3) --------------------------


def _state_with(events=(), flags=()):
    from types import SimpleNamespace
    return SimpleNamespace(
        activated_events=set(events), state_flags=set(flags),
    )


def test_facility_phase_derives_from_persisted_state():
    from src.spacehack.dungeon_activation import _facility_phase

    assert _facility_phase(_state_with()) == "dormant"
    assert _facility_phase(_state_with(events=["prison_floor1_security_alpha"])) == "waking"
    assert _facility_phase(_state_with(events=[
        "prison_floor1_security_alpha", "prison_floor1_security_beta",
    ])) == "rising"
    assert _facility_phase(_state_with(
        events=["prison_floor1_security_alpha"],
        flags=["prison_data_extracted"],
    )) == "lockdown"


def test_panel_kinds_follow_phase_and_skip_rule():
    from src.spacehack.dungeon_activation import _effective_phase, _panel_kind

    assert _panel_kind("dormant", 1).kind == "prison_panel_off"
    assert _panel_kind("waking", 1).kind == "prison_panel_dim"
    assert _panel_kind("waking", 2).kind == "prison_panel_off"
    assert _panel_kind("rising", 1).kind == "prison_panel_mid"
    assert _panel_kind("rising", 4).kind == "prison_panel_normal"
    assert _panel_kind("lockdown", 5).kind == "prison_panel_alarm"
    # Skip rule: entering floor 2 counts as at least rising.
    assert _effective_phase("dormant", 2) == "rising"
    assert _effective_phase("dormant", 1) == "dormant"
    assert _effective_phase("waking", 3) == "rising"


def test_refresh_prison_panels_rewrites_and_invalidates():
    from src.spacehack.dungeon_activation import refresh_prison_panels

    width, height = 20, 10
    tiles = [[world.PRISON_PANEL_OFF for _ in range(width)] for _ in range(height)]
    for y in range(height):
        for x in range(width):
            if (x + y) % 2:
                tiles[y][x] = world.DUNGEON_FLOOR
    game_map = world.GameMap(width=width, height=height, tiles=tiles, entities=[])
    game_map.light_grid = [[(1, 1, 1)] * width for _ in range(height)]
    game_map.light_sources = ["stale"]

    assert refresh_prison_panels(game_map, "lockdown", 1) is True
    kinds = {
        t.kind for row in game_map.tiles for t in row
        if t.kind.startswith("prison_panel_")
    }
    assert kinds == {"prison_panel_alarm"}
    assert game_map.light_grid is None and game_map.light_sources is None
    assert refresh_prison_panels(game_map, "lockdown", 1) is False  # idempotent


def test_generation_is_phase_gated():
    from src.spacehack.dungeon_extensions import _generate_floor

    # Floor 2 generated dormant still wakes: the skip rule applies.
    game_map, _ = _generate_floor("mars_alien_prison", 2, phase="dormant")
    kinds = {
        t.kind for row in game_map.tiles for t in row
        if t.kind.startswith("prison_panel_")
    }
    assert kinds == {"prison_panel_mid"}

    # A floor generated post-lockdown alarms and its security is awake.
    game_map, _ = _generate_floor("mars_alien_prison", 1, phase="lockdown")
    kinds = {
        t.kind for row in game_map.tiles for t in row
        if t.kind.startswith("prison_panel_")
    }
    assert kinds == {"prison_panel_alarm"}
    assert not any(e.powered_down for e in game_map.entities)


def test_terminal_landing_glow_reaches_across_the_abyss():
    """Doc 31 phase D: the deep cell's landing emits a faint pulse —
    'somewhere in the dark, one of them still answers' made visible."""
    from src.spacehack.data.lighting import light_spec_for_kind

    spec = light_spec_for_kind("terminal_landing")
    assert spec is not None
    assert spec.radius >= 3 and spec.flicker == "pulse"
