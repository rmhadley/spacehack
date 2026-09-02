"""Reusable procedural dungeon-extension runtime.

An extension is a persistent, themed dungeon attached to a parent dungeon.
Content definitions live in :mod:`spacehack.data.dungeon_extensions`; this
module owns generation, map caching, connection transitions, and activation
state so future caves, ruins, stations, and prisons share one runtime.
"""

from __future__ import annotations

from . import dungeon, world
from . import dungeon_activation
from .dungeon_activation import (  # noqa: F401 — size-limit split
    _activation_cells,
    _activation_positions,
    _place_dormant_units,
    _stock_dormant_security,
    _walkable_distances,
    floor_key,
)
from .dungeon_extension_deep_cell import stamp_deep_cell
from .game_context import DungeonExtensionState


ALIEN_PRISON_EXTENSION_ID = "mars_alien_prison"
_ENTRY_FLAVOR_KEY = "__entry_flavor__"


def _entry_flavor_key(floor: int) -> str:
    """Return the per-floor key for one-time entry flavor."""
    return f"{_ENTRY_FLAVOR_KEY}:floor:{floor}"


def extension_id_at(game_map: world.GameMap, position: world.Position) -> str | None:
    """Return the extension attached to a parent-dungeon connection."""
    _entry_id = getattr(game_map, "extension_entry_id", "")
    if _entry_id and getattr(game_map.tiles[position.y][position.x], "kind", "") == "stairs_down":
        return _entry_id
    # Migration for Mars surface maps written before entry metadata existed.
    _stairs = getattr(game_map, "mars_stairs_pos", None)
    if _stairs == position and game_map.tiles[position.y][position.x].kind == "stairs_down":
        return ALIEN_PRISON_EXTENSION_ID
    return None


def _floor_spec(extension_id: str, floor: int):
    """Resolve a floor definition from the data catalog."""
    from .data.dungeon_extensions import find_extension

    return find_extension(extension_id).floor(floor)


def _farthest_free_cell(
    game_map: world.GameMap,
    origin: world.Position,
) -> world.Position | None:
    """Return the farthest reachable, unoccupied floor cell from ``origin``."""
    _distances = _walkable_distances(game_map, origin)
    _occupied = {(entity.pos.x, entity.pos.y) for entity in game_map.entities}
    _cells = sorted(
        _distances,
        key=lambda _cell: (-_distances[_cell], _cell[1], _cell[0]),
    )
    for _x, _y in _cells:
        if (_x, _y) not in _occupied and (_x, _y) != (origin.x, origin.y):
            return world.Position(_x, _y)
    return None


def _set_floor_metadata(
    game_map: world.GameMap,
    extension_id: str,
    floor: int,
    spec,
    entry: world.Position,
) -> None:
    """Attach generic extension metadata and connection markers to a floor."""
    game_map.entry_spawn = entry
    game_map.up_stair_pos = entry
    game_map.location_name = spec.location_name
    game_map.extension_id = extension_id
    game_map.extension_floor = floor
    game_map.extension_entry_id = extension_id
    game_map.feature_theme = spec.feature_theme


def _feature_cells(
    game_map: world.GameMap,
    origin: world.Position,
    *,
    adjacent_to_wall: bool = False,
) -> list[tuple[int, int]]:
    """Return deterministic walkable cells suitable for visual features."""
    _distances = _walkable_distances(game_map, origin)
    _cells = sorted(
        _distances,
        key=lambda _cell: (-_distances[_cell], _cell[1], _cell[0]),
    )
    if not adjacent_to_wall:
        return _cells
    return [
        _cell for _cell in _cells
        if any(
            not game_map.is_walkable(_cell[0] + _dx, _cell[1] + _dy)
            for _dx, _dy in ((0, -1), (0, 1), (-1, 0), (1, 0))
        )
    ]


def _stamp_features(
    game_map: world.GameMap,
    cells: list[tuple[int, int]],
    tile: world.Tile,
    count: int,
    used: set[tuple[int, int]],
) -> None:
    """Paint up to ``count`` non-stair feature markers."""
    _placed = 0
    for _x, _y in cells:
        if _placed >= count:
            return
        if (_x, _y) in used:
            continue
        if game_map.tiles[_y][_x].kind in {"stairs_up", "stairs_down"}:
            continue
        game_map.tiles[_y][_x] = tile
        used.add((_x, _y))
        _placed += 1


def _stamp_prisoner_quarters(
    game_map: world.GameMap,
    origin: world.Position,
    _spec=None,
) -> None:
    """Add empty-cell doors and security posts to a quarters floor."""
    _used: set[tuple[int, int]] = set()
    _stamp_features(
        game_map,
        _feature_cells(game_map, origin, adjacent_to_wall=True),
        world.PRISON_CELL_DOOR,
        8,
        _used,
    )
    _stamp_features(
        game_map,
        _feature_cells(game_map, origin),
        world.SECURITY_POST,
        3,
        _used,
    )


def _stamp_defensive_layer(
    game_map: world.GameMap,
    origin: world.Position,
    _spec=None,
) -> None:
    """Add non-blocking barriers and active security nodes to Floor 3."""
    _used: set[tuple[int, int]] = set()
    _cells = _feature_cells(game_map, origin)
    _stamp_features(game_map, _cells, world.DEFENSE_BARRIER, 5, _used)
    _stamp_features(
        game_map,
        list(reversed(_cells)),
        world.SECURITY_NODE,
        4,
        _used,
    )


def _stamp_high_risk_quarters(
    game_map: world.GameMap,
    origin: world.Position,
    _spec=None,
) -> None:
    """Add larger-cell markers and advanced security to Floor 4."""
    _used: set[tuple[int, int]] = set()
    _cells = _feature_cells(game_map, origin, adjacent_to_wall=True)
    _stamp_features(game_map, _cells, world.HIGH_RISK_CELL_DOOR, 10, _used)
    _stamp_features(
        game_map,
        list(reversed(_cells)),
        world.SECURITY_NODE,
        5,
        _used,
    )


_FEATURE_STAMPERS = {
    "prisoner_quarters": _stamp_prisoner_quarters,
    "defensive_layer": _stamp_defensive_layer,
    "high_risk_quarters": _stamp_high_risk_quarters,
    "deep_cell": lambda _game_map, _origin, _spec=None: stamp_deep_cell(
        _game_map,
        _origin,
        landmark_variants=(getattr(_spec, "landmark_variants", ()) if _spec else ()),
    ),
}


# Themes whose own stamper already handles landmark_variants — the
# generic variant pass must not double-stamp them.
_VARIANT_AWARE_THEMES = frozenset({"deep_cell"})


def _stamp_landmark_variant(game_map: world.GameMap, spec, origin: world.Position) -> bool:
    """Stamp one weighted authored landmark variant, if the floor has any.

    Isolated RNG (never the shared stream — seeded descents stay
    byte-identical) and a soft failure: a layout that does not fit or
    route on this map is skipped, leaving the sprinkle theme. The
    stamped footprint is unioned into ``landmark_footprint`` so panels,
    dormant placement, and stairs all respect it.
    """
    from . import landmark as landmark_module
    from .engine import seeded_rng

    variants = getattr(spec, "landmark_variants", ()) or ()
    if not variants or spec.feature_theme in _VARIANT_AWARE_THEMES:
        return False
    _layout_id = landmark_module.choose_weighted_variant(
        variants, seeded_rng(21, f"{spec.floor}").random(),
    )
    try:
        _asset = landmark_module.load_landmark(_layout_id)
        _stamp = landmark_module.stamp_landmark(game_map, _asset, origin)
    except ValueError:
        return False
    game_map.landmark_footprint = set(getattr(game_map, "landmark_footprint", ()) or ()) | set(_stamp.footprint)
    game_map.landmark_variant_id = _layout_id
    return True


def _stamp_floor_features(
    game_map: world.GameMap,
    spec,
    origin: world.Position,
) -> None:
    """Apply a data-selected procedural feature theme to a floor."""
    _stamp_landmark_variant(game_map, spec, origin)
    # Sprinkle features remain filler BETWEEN the authored structures.
    _feature_stamper = _FEATURE_STAMPERS.get(spec.feature_theme)
    if _feature_stamper is not None:
        _feature_stamper(game_map, origin, spec)


def _free_interaction_position(
    game_map: world.GameMap,
    cells: list[tuple[int, int]],
    *,
    forbidden_positions: tuple[world.Position, ...] = (),
    min_path_distance: int = 0,
    ignore_entity: world.Entity | None = None,
) -> world.Position | None:
    """Choose an unoccupied cell separated from other key anchors."""
    _occupied = {
        (e.pos.x, e.pos.y) for e in game_map.entities if e is not ignore_entity
    }
    _distances = {
        (_anchor.x, _anchor.y): _walkable_distances(game_map, _anchor)
        for _anchor in forbidden_positions
    }
    for _x, _y in cells:
        if (_x, _y) in _occupied:
            continue
        if game_map.tiles[_y][_x].kind in {"stairs_up", "stairs_down"}:
            continue
        if any(
            _dist.get((_x, _y), -1) < min_path_distance
            for _dist in _distances.values()
        ):
            continue
        return world.Position(_x, _y)
    return None


def _stamp_engineering_room(
    game_map: world.GameMap,
    center: world.Position,
) -> None:
    """Dress a small walkable engineering room around its console."""
    for _y in range(center.y - 1, center.y + 2):
        for _x in range(center.x - 2, center.x + 3):
            if not game_map.in_bounds(_x, _y):
                continue
            if game_map.tiles[_y][_x].kind in {"stairs_up", "stairs_down"}:
                continue
            if game_map.tiles[_y][_x].walkable:
                game_map.tiles[_y][_x] = world.ENGINEERING_FLOOR


from .dungeon_extension_interactions import (
    ensure_floor_interactions as _ensure_floor_interactions_impl,
    stamp_interactions as _stamp_interactions_impl,
)


def _stamp_interactions(
    game_map: world.GameMap,
    spec,
    origin: world.Position,
    interactions=None,
) -> None:
    """Compatibility wrapper for interaction placement helpers."""
    _stamp_interactions_impl(game_map, spec, origin, interactions)


def _ensure_floor_interactions(
    game_map: world.GameMap,
    spec,
    origin: world.Position,
) -> None:
    """Compatibility wrapper for cached interaction repair."""
    _ensure_floor_interactions_impl(game_map, spec, origin)


def _generate_floor(extension_id: str, floor: int, phase: str = "dormant"):
    """Generate one procedural floor and its stable extension anchors.

    Some maps cannot wire their landmark entrance no matter which
    origin stamps it (seed 2's F5: 307 candidates, zero routable).
    Generation must never die there — regenerate the base map and
    retry, bounded. The retry seed is drawn from the run's own RNG, so
    it stays deterministic per run and only fires in runs that would
    previously have crashed.
    """
    from .engine import RNG

    for _attempt in range(4):
        try:
            return _generate_floor_once(extension_id, floor, phase)
        except ValueError:
            if _attempt == 3:
                raise
            RNG.seed(int(RNG.random() * 2**31))


def _generate_floor_once(extension_id: str, floor: int, phase: str = "dormant"):
    """One generation attempt; raises when the landmark cannot wire."""
    _spec = _floor_spec(extension_id, floor)
    _game_map, _spawn = dungeon.generate_dungeon(_spec.params)
    _game_map.interior_cache_key = floor_key(extension_id, floor)
    _generated_spawn = _spawn
    # The generic generator creates an EXIT at its spawn wall. An extension
    # floor uses an explicit up-connection marker instead.
    _game_map.tiles[_spawn.y][_spawn.x] = world.STAIRS_UP
    _set_floor_metadata(_game_map, extension_id, floor, _spec, _spawn)
    _stamp_floor_features(_game_map, _spec, _spawn)
    _spawn = getattr(_game_map, "entry_spawn", _generated_spawn)
    _set_floor_metadata(_game_map, extension_id, floor, _spec, _spawn)
    if _game_map.in_bounds(_spawn.x, _spawn.y):
        _game_map.tiles[_spawn.y][_spawn.x] = world.STAIRS_UP
    # Populate before selecting the deeper connection so the stair tile is
    # guaranteed not to overlap a procedural enemy.
    dungeon.populate_dungeon(_game_map, _spec.params, _generated_spawn)
    if _spec.has_down_stairs:
        _down = _farthest_free_cell(_game_map, _spawn)
        if _down is not None:
            _game_map.tiles[_down.y][_down.x] = world.STAIRS_DOWN
            _game_map.down_stair_pos = _down
    _game_map.activation_positions = _activation_positions(
        _game_map, _spawn, _spec.activation_events,
    )
    _stock_dormant_security(_game_map, _spec, _spawn)
    # Phase-gated generation: a floor reached after the facility woke
    # generates in its lit state; post-lockdown floors spawn security
    # already active (doc 29/30 phase 3).
    _effective = dungeon_activation._effective_phase(phase, floor)
    if _effective != "dormant":
        dungeon_activation.refresh_prison_panels(_game_map, _effective, floor)
    if _effective == "lockdown":
        dungeon_activation.activate_dormant(_game_map)
    # The elevator anchor is stamped after the down stair is created so the
    # interaction entity occupies the connection and gates it cleanly.
    _stamp_interactions(_game_map, _spec, _spawn)
    return _game_map, _spawn


def _sync_event_positions(
    state: DungeonExtensionState,
    game_map: world.GameMap,
) -> None:
    """Refresh current-floor activation anchors from its cached map."""
    state.event_positions = {
        _event_id: [_position.x, _position.y]
        if isinstance(_position, world.Position) else [
            int(_position[0]), int(_position[1]),
        ]
        for _event_id, _position in getattr(
            game_map, "activation_positions", {},
        ).items()
    }


def _ensure_state(ctx, extension_id: str) -> DungeonExtensionState:
    """Return the current run state, creating a compatible one if needed."""
    _state = ctx.dungeon_extension
    if _state is None or _state.extension_id != extension_id:
        _state = DungeonExtensionState(extension_id=extension_id)
        ctx.dungeon_extension = _state
    return _state


def _resolve_parent_key(ctx, parent_map, parent_map_key: str) -> str:
    """Resolve and validate the cached parent map key."""
    if not parent_map_key:
        parent_map_key = next(
            (_key for _key, _map in ctx.interiors.items() if _map is parent_map),
            "",
        )
    if not parent_map_key or ctx.interiors.get(parent_map_key) is not parent_map:
        raise ValueError("Dungeon extension parent map is not cached")
    return parent_map_key


def _load_entry_floor(ctx, state, extension_id: str):
    """Load or generate the state's current extension floor."""
    _floor = state.current_floor
    _key = floor_key(extension_id, _floor)
    _game_map = ctx.interiors.get(_key)
    if _game_map is None:
        _game_map, _spawn = _generate_floor(extension_id, _floor)
        ctx.interiors[_key] = _game_map
    else:
        _ensure_floor_connections(_game_map, extension_id, _floor)
        _spawn = getattr(_game_map, "entry_spawn", None) or _first_walkable(_game_map)
    _sync_event_positions(state, _game_map)
    if _spawn is None:
        raise ValueError("Dungeon extension floor has no walkable entry")
    return _floor, _game_map, _spawn


def _install_entry_player(ctx, parent_map, game_map, spawn):
    """Move the player from the parent map onto an extension floor."""
    _remove_player(game_map)
    _remove_player(parent_map)
    _player = _make_player(spawn)
    game_map.entities.append(_player)
    ctx.game_map = game_map
    ctx.player = _player
    if game_map.seen is None:
        dungeon.init_fog(game_map)
    dungeon.reveal_around(game_map, spawn)
    return _player


def enter_extension(
    ctx,
    parent_map: world.GameMap,
    parent_player: world.Entity,
    *,
    extension_id: str,
    parent_map_key: str = "",
) -> tuple[world.GameMap, world.Entity]:
    """Enter or re-enter floor 1 from a parent dungeon connection."""
    if (extension_id == ALIEN_PRISON_EXTENSION_ID
            and getattr(ctx, "main_quest_progress", None) is not None):
        from .main_quest import start_prison_objective

        start_prison_objective(ctx)
    parent_map_key = _resolve_parent_key(ctx, parent_map, parent_map_key)
    _state = _ensure_state(ctx, extension_id)
    _state.active = True
    _state.parent_map_key = parent_map_key
    _state.parent_position = parent_player.pos
    _floor, _game_map, _spawn = _load_entry_floor(ctx, _state, extension_id)
    _player = _install_entry_player(ctx, parent_map, _game_map, _spawn)
    _show_first_entry_flavor(ctx, _state, _floor)
    return _game_map, _player


def _show_first_entry_flavor(
    ctx,
    state: DungeonExtensionState,
    floor: int,
) -> None:
    """Show and persist a floor's one-time entry flavor, if defined."""
    _flavor_key = _entry_flavor_key(floor)
    if _flavor_key in state.activated_events or (
        floor == 1 and _ENTRY_FLAVOR_KEY in state.activated_events
    ):
        return
    # Lightweight test contexts may omit the terminal context; real
    # GameContext instances always provide it for modal presentation.
    if getattr(ctx, "context", None) is None:
        return
    _flavor = _floor_spec(state.extension_id, floor).entry_flavor
    if _flavor is None:
        return
    from .main_quest import show_gate_popup

    show_gate_popup(
        ctx,
        _flavor.faction_label,
        _flavor.message,
        title=_flavor.title,
    )
    state.activated_events.add(_flavor_key)


def _valid_stair_position(
    game_map: world.GameMap,
    position,
    kind: str,
) -> bool:
    """Return whether metadata points to a matching in-bounds stair tile."""
    return (
        isinstance(position, world.Position)
        and game_map.in_bounds(position.x, position.y)
        and game_map.tiles[position.y][position.x].kind == kind
    )


def _find_stair_position(
    game_map: world.GameMap,
    kind: str,
) -> world.Position | None:
    """Find the first stair tile of ``kind`` in map order."""
    for _y, _row in enumerate(game_map.tiles):
        for _x, _tile in enumerate(_row):
            if _tile.kind == kind:
                return world.Position(_x, _y)
    return None


def _ensure_floor_connections(
    game_map: world.GameMap,
    extension_id: str,
    floor: int,
) -> None:
    """Repair connection metadata on a cached floor from an older save."""
    _spec = _floor_spec(extension_id, floor)
    _entry = getattr(game_map, "entry_spawn", None)
    if not _valid_stair_position(game_map, _entry, "stairs_up"):
        _entry = _find_stair_position(game_map, "stairs_up")
    if _entry is None:
        _entry = getattr(game_map, "up_stair_pos", None)
    if not _valid_stair_position(game_map, _entry, "stairs_up"):
        _entry = _first_walkable(game_map)
    if _entry is None or not game_map.in_bounds(_entry.x, _entry.y):
        return
    if game_map.tiles[_entry.y][_entry.x].kind != "stairs_up":
        game_map.tiles[_entry.y][_entry.x] = world.STAIRS_UP
    _set_floor_metadata(game_map, extension_id, floor, _spec, _entry)
    if not _spec.has_down_stairs:
        _ensure_floor_interactions(game_map, _spec, _entry)
        return
    _down = getattr(game_map, "down_stair_pos", None)
    if not _valid_stair_position(game_map, _down, "stairs_down"):
        _down = _find_stair_position(game_map, "stairs_down")
    if not _valid_stair_position(game_map, _down, "stairs_down"):
        _down = _farthest_free_cell(game_map, _entry)
        if _down is not None:
            game_map.tiles[_down.y][_down.x] = world.STAIRS_DOWN
    if _valid_stair_position(game_map, _down, "stairs_down"):
        game_map.down_stair_pos = _down
    _ensure_floor_interactions(game_map, _spec, _entry)


def _connection_position(
    game_map: world.GameMap,
    kind: str,
) -> world.Position | None:
    """Return a validated connection position from metadata or tile scan."""
    _position = getattr(
        game_map,
        "up_stair_pos" if kind == "stairs_up" else "down_stair_pos",
        None,
    )
    if _valid_stair_position(game_map, _position, kind):
        return _position
    return _find_stair_position(game_map, kind)


def _get_or_generate_floor(
    ctx,
    extension_id: str,
    floor: int,
) -> world.GameMap:
    """Return a cached extension floor, generating and caching it if absent."""
    _key = floor_key(extension_id, floor)
    _game_map = ctx.interiors.get(_key)
    if _game_map is None:
        _state = getattr(ctx, "dungeon_extension", None)
        _game_map, _ = _generate_floor(
            extension_id, floor,
            phase=dungeon_activation._facility_phase(_state) if _state else "dormant",
        )
        ctx.interiors[_key] = _game_map
    else:
        _ensure_floor_connections(_game_map, extension_id, floor)
    return _game_map


def _current_floor_spec(ctx):
    """Return the active extension's current floor definition."""
    _state = ctx.dungeon_extension
    if _state is None or not _state.active:
        return None
    return _floor_spec(_state.extension_id, _state.current_floor)


def interaction_spec_at(ctx, interaction_id: str):
    """Resolve a current-floor interaction definition by stable ID."""
    _spec = _current_floor_spec(ctx)
    if _spec is None:
        return None
    return next(
        (_interaction for _interaction in _spec.interactions
         if _interaction.id == interaction_id),
        None,
    )


def activate_interaction_state(ctx, interaction_id: str) -> bool:
    """Activate a data-defined current-floor interaction state flag."""
    _interaction = interaction_spec_at(ctx, interaction_id)
    if _interaction is None or not _interaction.state_key:
        return False
    _state = ctx.dungeon_extension
    if _interaction.state_key in _state.state_flags:
        return False
    _state.state_flags.add(_interaction.state_key)
    # Keep the legacy boolean mirror only for the original prison power flag;
    # state_flags remains canonical for every future extension interaction.
    if _interaction.state_key == "engineering_power":
        _state.power_restored = True
        ctx.game_map.power_restored = True
    if _interaction.state_key == "prison_data_extracted":
        # The payoff moment: every floor alarms, everything wakes (doc 30).
        dungeon_activation.apply_lockdown_all_floors(ctx)
    # Interactions that carry a main-quest objective type complete that
    # step on activation (generic — the runtime never names a step id).
    if _interaction.objective_type:
        from .main_quest import complete_step_by_type

        complete_step_by_type(ctx, _interaction.objective_type)
    return True


def interaction_state_active(ctx, interaction_id: str) -> bool:
    """Return whether an interaction's required state is active."""
    _interaction = interaction_spec_at(ctx, interaction_id)
    if _interaction is None or not _interaction.required_state:
        return True
    return _interaction.required_state in ctx.dungeon_extension.state_flags


def interaction_is_available(ctx, interaction_id: str) -> bool:
    """Return whether a current-floor interaction's gate is satisfied."""
    _interaction = interaction_spec_at(ctx, interaction_id)
    return _interaction is not None and interaction_state_active(ctx, interaction_id)


def restore_power(ctx) -> bool:
    """Backward-compatible helper for activating a stateful console."""
    _spec = _current_floor_spec(ctx)
    if _spec is None:
        return False
    _interaction = next(
        (_item for _item in _spec.interactions
         if _item.action == "activate_state"),
        None,
    )
    if _interaction is None:
        return False
    return activate_interaction_state(ctx, _interaction.id)


def elevator_is_powered(ctx) -> bool:
    """Backward-compatible helper for the current floor's gated elevator."""
    _state = ctx.dungeon_extension
    _spec = _current_floor_spec(ctx)
    if _spec is None:
        return False
    _interaction = next(
        (_item for _item in _spec.interactions
         if _item.action == "transition_floor"),
        None,
    )
    if _interaction is None:
        return False
    if interaction_state_active(ctx, _interaction.id):
        return True
    # Legacy saves only carried the boolean mirror. It is safe to accept it
    # for this known interaction while unrelated state flags remain ignored.
    return _interaction.required_state == "engineering_power" and bool(
        ctx.dungeon_extension.power_restored
    )


def _transition_target_floor(state, direction: int) -> int:
    """Validate direction and return the requested floor number."""
    if state is None or not state.active:
        raise ValueError("No active dungeon extension to traverse")
    if direction not in (-1, 1):
        raise ValueError("Floor transition direction must be -1 or 1")
    _target_floor = state.current_floor + direction
    if _target_floor < 1:
        raise ValueError("Already at the extension entrance")
    if direction > 0:
        _spec = _floor_spec(state.extension_id, state.current_floor)
        _gates = tuple(
            item for item in _spec.interactions
            if item.action == "transition_floor"
            and item.destination_floor == _target_floor
            and item.required_state
        )
        if _gates and not any(
            item.required_state in state.state_flags for item in _gates
        ):
            raise ValueError("The elevator is unpowered")
    return _target_floor


def _prepare_transition_target(ctx, state, target_floor: int, direction: int):
    """Load a target floor and resolve its arrival connection."""
    try:
        _target_map = _get_or_generate_floor(
            ctx, state.extension_id, target_floor,
        )
    except KeyError:
        raise ValueError("No extension floor at that depth") from None
    _ensure_floor_connections(_target_map, state.extension_id, target_floor)
    _kind = "stairs_up" if direction > 0 else "stairs_down"
    _position = _connection_position(_target_map, _kind)
    if _position is None:
        raise ValueError("Extension floor connection is unavailable")
    return _target_map, _position


def _install_transition(ctx, state, target_map, target_position, target_floor):
    """Move the player onto a target extension floor."""
    _remove_player(ctx.game_map)
    _remove_player(target_map)
    _player = _make_player(target_position)
    target_map.entities.append(_player)
    state.current_floor = target_floor
    _sync_event_positions(state, target_map)
    ctx.game_map = target_map
    ctx.player = _player
    if target_map.seen is None:
        dungeon.init_fog(target_map)
    dungeon.reveal_around(target_map, target_position)
    # Entry reconciliation: covers the floor-2 skip rule, post-load
    # drift, and phases that advanced while the floor was cached.
    dungeon_activation.refresh_prison_panels(
        target_map, dungeon_activation._facility_phase(state), target_floor,
    )
    _show_first_entry_flavor(ctx, state, target_floor)
    return target_map, _player


def transition_floor(
    ctx,
    direction: int,
) -> tuple[world.GameMap, world.Entity]:
    """Move one floor up or down inside the active extension."""
    _state = ctx.dungeon_extension
    _target_floor = _transition_target_floor(_state, direction)
    _target_map, _target_position = _prepare_transition_target(
        ctx, _state, _target_floor, direction,
    )
    return _install_transition(
        ctx, _state, _target_map, _target_position, _target_floor,
    )


def leave_extension(
    ctx,
    extension_map: world.GameMap,
) -> tuple[world.GameMap, world.Entity]:
    """Return from the active extension floor to its parent dungeon."""
    _state = ctx.dungeon_extension
    if _state is None or not _state.active:
        raise ValueError("No active dungeon extension to leave")
    _parent_map = ctx.interiors.get(_state.parent_map_key)
    if _parent_map is None:
        raise ValueError("Dungeon extension parent map is unavailable")
    _parent_pos = _state.parent_position or _first_walkable(_parent_map)
    if _parent_pos is None:
        raise ValueError("Dungeon extension parent map has no return position")
    _remove_player(extension_map)
    _remove_player(_parent_map)
    _player = _make_player(_parent_pos)
    _parent_map.entities.append(_player)
    _state.active = False
    ctx.game_map = _parent_map
    ctx.player = _player
    if _parent_map.seen is not None:
        dungeon.reveal_around(_parent_map, _parent_pos)
    return _parent_map, _player


def _make_player(position: world.Position) -> world.Entity:
    """Create the transient player entity used by extension handoffs."""
    return world.Entity(
        char="@", fg=(255, 255, 255), pos=position, name="Player",
    )


def _remove_player(game_map: world.GameMap) -> None:
    """Remove transient player entities from a cached map."""
    game_map.entities[:] = [
        _entity for _entity in game_map.entities if _entity.char != "@"
    ]


def _first_walkable(game_map: world.GameMap) -> world.Position | None:
    """Return the first walkable cell, or ``None`` for an empty map."""
    for _y, _row in enumerate(game_map.tiles):
        for _x, _tile in enumerate(_row):
            if _tile.walkable:
                return world.Position(_x, _y)
    return None


def _event_position(ctx, event_id: str) -> world.Position | None:
    """Resolve an activation anchor from serialized run state."""
    _state = ctx.dungeon_extension
    if _state is None:
        return None
    _raw = _state.event_positions.get(event_id)
    if isinstance(_raw, (list, tuple)) and len(_raw) >= 2:
        return world.Position(int(_raw[0]), int(_raw[1]))
    return None


def _progress_reached(
    game_map: world.GameMap,
    player_pos: world.Position,
    event,
    event_position: world.Position | None,
) -> bool:
    """Return whether the player crossed an event's route threshold.

    Descent events measure progress from the upper stairs toward the lower
    stairs. Escape events reverse that route and measure from the lower stairs
    back toward the upper stairs. The same monotonic distance rule supports
    both phases without relying on arbitrary generated coordinates.
    """
    _entry = getattr(game_map, "up_stair_pos", None)
    _down = getattr(game_map, "down_stair_pos", None)
    if (
        not isinstance(_entry, world.Position)
        or not isinstance(_down, world.Position)
        or not game_map.in_bounds(_entry.x, _entry.y)
        or not game_map.in_bounds(_down.x, _down.y)
    ):
        return _within_trigger_radius(player_pos, event_position, event.trigger_radius)
    _route_origin, _route_target = (
        (_down, _entry)
        if getattr(event, "route_direction", "down") == "up"
        else (_entry, _down)
    )
    _to_target = _walkable_distances(game_map, _route_target)
    _total = _to_target.get((_route_origin.x, _route_origin.y))
    _remaining = _to_target.get((player_pos.x, player_pos.y))
    if _total is None or _remaining is None:
        return _within_trigger_radius(player_pos, event_position, event.trigger_radius)
    _threshold = _total * (1.0 - min(max(event.distance_fraction, 0.0), 1.0))
    return _remaining <= _threshold


def _within_trigger_radius(
    player_pos: world.Position,
    event_position: world.Position | None,
    radius: int,
) -> bool:
    """Preserve proximity activation for legacy maps without stairs."""
    if event_position is None:
        return False
    return max(
        abs(player_pos.x - event_position.x),
        abs(player_pos.y - event_position.y),
    ) <= radius


def _activation_event_ready(ctx, state, event) -> bool:
    """Return whether an activation event should fire on this tick."""
    if event.id in state.activated_events:
        return False
    if event.required_state and event.required_state not in state.state_flags:
        return False
    if event.blocked_state and event.blocked_state in state.state_flags:
        return False
    return _progress_reached(
        ctx.game_map,
        ctx.player.pos,
        event,
        _event_position(ctx, event.id),
    )


def _fire_activation_event(ctx, state, event) -> None:
    """Persist, present, and log one activation event."""
    _spawned = dungeon_activation.activate_dormant(
        ctx.game_map, squad_prefix=f"{event.id}_security",
    )
    state.activated_events.add(event.id)
    # The facility's power story advanced — panels follow (doc 29).
    dungeon_activation.refresh_prison_panels(
        ctx.game_map, dungeon_activation._facility_phase(state), state.current_floor,
    )
    from .main_quest import show_gate_popup

    show_gate_popup(
        ctx,
        event.faction_label,
        event.message,
        title=event.title,
    )
    if _spawned:
        ctx.log.add(event.spawned_log.format(count=_spawned))
    else:
        ctx.log.add(event.no_deploy_log)


def tick_activation(ctx) -> bool:
    """Activate security as the player progresses toward the next floor."""
    _state = ctx.dungeon_extension
    if _state is None or not _state.active:
        return False
    _fired = False
    _spec = _floor_spec(_state.extension_id, _state.current_floor)
    for _event in _spec.activation_events:
        if not _activation_event_ready(ctx, _state, _event):
            continue
        _fire_activation_event(ctx, _state, _event)
        _fired = True
        if getattr(_event, "route_direction", "down") == "up":
            break
    return _fired
