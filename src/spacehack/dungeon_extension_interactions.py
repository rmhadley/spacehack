"""Interaction-anchor helpers for themed dungeon extensions.

The runtime module keeps the public compatibility wrappers; this sibling owns
placement and repair so the extension generator remains focused on transitions
and state changes.
"""

from __future__ import annotations

from . import world
from .dungeon_extension_layout import (
    _preferred_interaction_cells,
    _separate_room_cells,
)


def _runtime():
    """Return the runtime module for compatibility-patchable helpers."""
    from . import dungeon_extensions

    return dungeon_extensions


def _landmark_cells(game_map) -> tuple[set[tuple[int, int]], set[tuple[int, int]]]:
    """Return the footprint and explicit interaction cells for a landmark."""
    _footprint = set(getattr(game_map, "landmark_footprint", ()))
    _interactions = {
        (_cell.x, _cell.y) if isinstance(_cell, world.Position) else _cell
        for _cell in getattr(game_map, "landmark_interaction_cells", ())
    }
    return _footprint, _interactions


def _interaction_cells(game_map, interaction, cells, down, footprint, authored):
    """Narrow candidate cells for an interaction's authored anchor."""
    _runtime_module = _runtime()
    _candidates = _preferred_interaction_cells(
        game_map, cells, down, _runtime_module._walkable_distances,
    )
    if interaction.id != "deep_cell_data_terminal" or not footprint:
        return _candidates
    _candidates = [cell for cell in _candidates if cell in footprint]
    if not _candidates:
        _candidates = [cell for cell in cells if cell in footprint]
    if authored:
        _candidates = [cell for cell in _candidates if cell in authored] or list(authored)
    return _candidates


def _choose_position(game_map, interaction, cells, down, footprint, authored, used):
    """Choose a valid position for one non-transition interaction."""
    _runtime_module = _runtime()
    _anchors = (down,) if down is not None else ()
    _candidates = _interaction_cells(
        game_map, interaction, cells, down, footprint, authored,
    )
    _position = _runtime_module._free_interaction_position(
        game_map, _candidates, forbidden_positions=_anchors, min_path_distance=8,
    )
    if interaction.id == "deep_cell_data_terminal" and authored:
        _position = next(
            (world.Position(*cell) for cell in authored if cell not in used),
            _position,
        )
    if _position is None:
        _position = _runtime_module._free_interaction_position(
            game_map, _candidates, forbidden_positions=_anchors, min_path_distance=1,
        )
    return _position or _runtime_module._free_interaction_position(
        game_map, cells, forbidden_positions=(),
    )


def _position_for_interaction(game_map, interaction, cells, footprint, authored, used):
    """Resolve a transition anchor or a free interaction position."""
    _down = getattr(game_map, "down_stair_pos", None)
    if interaction.action == "transition_floor":
        return _down
    return _choose_position(
        game_map, interaction, cells, _down, footprint, authored, used,
    )


def _place_interaction(game_map, interaction, position, used) -> bool:
    """Place one interaction, reusing an authored landmark terminal if present."""
    if position is None:
        return False
    if interaction.action != "transition_floor":
        _authored = next(
            (
                entity for entity in game_map.entities
                if entity.name == "Landmark Terminal" and entity.pos == position
            ),
            None,
        )
        if _authored is not None:
            _authored.name = interaction.name
            _authored.dungeon_interaction = interaction.id
            _authored.interaction_flavor = ""
            if getattr(interaction, "emits_light", False):
                game_map.tiles[position.y][position.x] = world.LIVE_TERMINAL
            return True
    if interaction.action != "transition_floor" and (position.x, position.y) in used:
        return False
    used.add((position.x, position.y))
    if getattr(interaction, "emits_light", False):
        game_map.tiles[position.y][position.x] = world.LIVE_TERMINAL
    game_map.entities.append(world.Entity(
        char=interaction.char,
        fg=(180, 240, 255),
        pos=position,
        name=interaction.name,
        dungeon_interaction=interaction.id,
    ))
    if interaction.feature_theme == "engineering_room":
        _runtime()._stamp_engineering_room(game_map, position)
    return True


def stamp_interactions(game_map, spec, origin, interactions=None) -> None:
    """Place data-defined interactive anchors after procedural population."""
    _items = spec.interactions if interactions is None else interactions
    _existing = {
        getattr(entity, "dungeon_interaction", "") for entity in game_map.entities
    }
    _items = tuple(item for item in _items if item.id not in _existing)
    if not _items:
        return
    _runtime_module = _runtime()
    _cells = _runtime_module._feature_cells(game_map, origin)
    _footprint, _authored = _landmark_cells(game_map)
    _used = {
        (position.x, position.y)
        for position in (
            getattr(game_map, "up_stair_pos", None),
            getattr(game_map, "down_stair_pos", None),
        )
        if position is not None
    }
    for _interaction in sorted(_items, key=lambda item: item.action != "transition_floor"):
        _position = _position_for_interaction(
            game_map, _interaction, _cells, _footprint, _authored, _used,
        )
        _place_interaction(game_map, _interaction, _position, _used)


def _existing_entity(game_map, interaction):
    """Find an interaction entity by stable id."""
    return next(
        (
            entity for entity in game_map.entities
            if getattr(entity, "dungeon_interaction", "") == interaction.id
        ),
        None,
    )


def _reposition_existing(game_map, entity, cells, down):
    """Move a stale interaction back into its valid room."""
    _runtime_module = _runtime()
    _anchors = (down,) if down is not None else ()
    _position = _runtime_module._free_interaction_position(
        game_map, cells, forbidden_positions=_anchors,
        min_path_distance=8, ignore_entity=entity,
    )
    _position = _position or _runtime_module._free_interaction_position(
        game_map, cells, forbidden_positions=_anchors,
        min_path_distance=1, ignore_entity=entity,
    )
    entity.pos = _position or _runtime_module._free_interaction_position(
        game_map, cells, forbidden_positions=(), ignore_entity=entity,
    ) or entity.pos


def _repair_existing(game_map, interaction, entity, origin, authored):
    """Repair one cached interaction and report whether it is missing."""
    _runtime_module = _runtime()
    if interaction.action == "transition_floor":
        _expected = getattr(game_map, "down_stair_pos", None)
        if entity is not None and _expected is not None:
            entity.pos = _expected
        return entity is None
    if entity is None:
        return True
    _down = getattr(game_map, "down_stair_pos", None)
    _cells = _runtime_module._feature_cells(game_map, origin)
    _authored_anchor = (
        interaction.id == "deep_cell_data_terminal"
        and (entity.pos.x, entity.pos.y) in authored
    )
    _separate = (
        _separate_room_cells(
            game_map, _down, _runtime_module._walkable_distances,
        )
        if _down is not None else []
    )
    _distance = (
        _runtime_module._walkable_distances(game_map, _down).get(
            (entity.pos.x, entity.pos.y), -1,
        )
        if _down is not None else -1
    )
    _wrong_room = bool(_separate and (entity.pos.x, entity.pos.y) not in _separate)
    if not _authored_anchor and (_distance < 8 or _wrong_room):
        _reposition_existing(game_map, entity, _separate or _cells, _down)
    if interaction.feature_theme == "engineering_room":
        _runtime_module._stamp_engineering_room(game_map, entity.pos)
    return False


def ensure_floor_interactions(game_map, spec, origin) -> None:
    """Repair missing interactive anchors on a cached extension floor."""
    _authored = _landmark_cells(game_map)[1]
    _missing = [
        interaction for interaction in spec.interactions
        if _repair_existing(
            game_map, interaction, _existing_entity(game_map, interaction),
            origin, _authored,
        )
    ]
    if _missing:
        stamp_interactions(game_map, spec, origin, interactions=tuple(_missing))
