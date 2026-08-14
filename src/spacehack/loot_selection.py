"""Nearby-loot discovery for the P pickup chooser."""

from __future__ import annotations

from . import world


def _search_positions(position: world.Position) -> tuple[world.Position, ...]:
    """Return pickup positions in current/cardinal/diagonal priority order."""
    return (
        position,
        world.Position(position.x, position.y - 1),
        world.Position(position.x + 1, position.y),
        world.Position(position.x, position.y + 1),
        world.Position(position.x - 1, position.y),
        world.Position(position.x - 1, position.y - 1),
        world.Position(position.x + 1, position.y - 1),
        world.Position(position.x - 1, position.y + 1),
        world.Position(position.x + 1, position.y + 1),
    )


def nearby_loot_entities(ctx) -> tuple[world.Entity, ...]:
    """Return every loot entity within the existing P pickup radius."""
    game_map = getattr(ctx, "game_map", None)
    player = getattr(ctx, "player", None)
    if game_map is None or player is None:
        return ()
    nearby: list[world.Entity] = []
    for position in _search_positions(player.pos):
        for entity in game_map.entities:
            if entity.loot_data is None:
                continue
            if (
                entity.pos.x <= position.x < entity.pos.x + entity.width
                and entity.pos.y <= position.y < entity.pos.y + entity.height
            ):
                nearby.append(entity)
    return tuple(nearby)
