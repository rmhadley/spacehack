"""Ambient city NPCs — placement, deterministic movement, and bump interaction.

Ambient NPCs are the streets' pedestrian layer (Phase 3 of the planet-city
expansion). They are lightweight: each stays within a small wander radius of
its authored anchor, takes at most one deterministic step per city tick, and
either holds still (movement chance = 0) or drifts along the pavement.

Design principles (matching the rest of the project):

* **Data-first** — every ambient NPC is a :class:`~spacehack.data.city_npcs.CityNpc`
  catalog entry; this module only places/moves/interacts with them.
* **Deterministic** — movement uses ``engine.seeded_rng`` keyed on ``INIT_SEED``
  + city + npc id, so save/load and re-entry never reshuffle routes.
* **Reuse** — hostility reuses ``faction.spec_is_hostile`` via the NPC's
  ``npc_char_id``; direct-contact combat reuses the existing ground combat
  entry point; talk reuses the guild NPC persona.
* **One step per city tick** — called from the city move/wait handler exactly
  once per accepted action, mirroring ``ground_npcs.move_ground_npcs``.
"""

from __future__ import annotations

from . import world
from .engine import INIT_SEED, seeded_rng
from .data.npc_chars import find_npc_char as _find_npc_char
from .faction import spec_is_hostile as _spec_is_hostile


def is_hostile(ctx, entity: world.Entity) -> bool:
    """True if a city NPC's faction is hostile toward the player."""
    _charid = getattr(entity, "npc_char_id", "")
    if not _charid:
        return False
    try:
        _spec = _find_npc_char(_charid)
    except KeyError:
        return False
    return _spec_is_hostile(ctx, _spec)


def place_city_npcs(game_map: world.GameMap, population) -> None:
    """Place one ambient NPC entity per catalog entry at its anchor.

    Each NPC carries its ``city_npc_id`` and anchor metadata so the
    movement pass keeps it near its district and save/load can identify
    it across rebuilds.
    """
    for template in population:
        try:
            _cspec = _find_npc_char(template.npc_char_id)
        except KeyError:
            continue
        rng = seeded_rng(INIT_SEED, "city_npc", template.id)
        entity = world.Entity(
            char=_cspec.char,
            fg=_cspec.fg,
            pos=world.Position(*template.spawn),
            name=_cspec.name,
            city_npc_id=template.id,
            npc_char_id=template.npc_char_id,
            npc_id=template.npc_id,
            blocked_message=f"You bump into {_cspec.name}.",
        )
        entity.city_spawn = world.Position(*template.spawn)
        entity.city_wander_radius = template.wander_radius
        entity.city_move_chance = template.move_chance
        entity.city_rng = rng
        game_map.entities.append(entity)


def _adjacent_walkable(
    entity: world.Entity,
    game_map: world.GameMap,
) -> list[tuple[int, int]]:
    """Adjacent walkable, unblocked cells for the next step (no stay)."""
    out: list[tuple[int, int]] = []
    for dx, dy in ((-1, 0), (1, 0), (0, -1), (0, 1)):
        nx, ny = entity.pos.x + dx, entity.pos.y + dy
        if not game_map.in_bounds(nx, ny):
            continue
        if not game_map.tiles[ny][nx].walkable:
            continue
        if game_map.blocking_entity_at(nx, ny, exclude=entity) is not None:
            continue
        out.append((nx, ny))
    return out


def _take_one_step(entity: world.Entity, game_map: world.GameMap) -> None:
    """Move ``entity`` one cell, biasing toward its wander anchor.

    Prefer the reachable neighbor nearest the anchor so ambient NPCs drift
    back toward their district instead of wandering off; only hold still
    when every neighbor is blocked.
    """
    spawn = entity.city_spawn
    candidates = _adjacent_walkable(entity, game_map)
    if not candidates:
        return
    if len(candidates) == 1:
        nx, ny = candidates[0]
        entity.pos = world.Position(nx, ny)
        return
    candidates.sort(
        key=lambda c: (c[0] - spawn.x) ** 2 + (c[1] - spawn.y) ** 2,
    )
    # Shuffle a small near-anchor pool so routes stay organic yet bounded;
    # the first element after the shuffle is the chosen step.
    if entity.city_rng is not None:
        entity.city_rng.shuffle(candidates[:min(3, len(candidates))])
    nx, ny = candidates[0]
    entity.pos = world.Position(nx, ny)

def run_city_fight(ctx, console, game_map: world.GameMap, hostiles) -> None:
    """Run a direct-contact ground fight vs the engaged hostile citizens.

    Wired from the occupied (bump) dispatch when the player walks into a
    faction-enemy citizen. Reuses the shared ground-combat runtime so the
    encounter plays out with the exact same combat AI as a dungeon fight.
    Hands defeat over to the shared defeat-presentation flow.
    """
    from . import tutorial as _tutorial
    from .combat import _rules_ground as _rg
    from .combat._loop import run_combat as _run_combat
    from .game_flow import _apply_ground_combat_rep as _apply_rep
    _tutorial.maybe_ground_combat_intro(ctx)
    _rg.init(ctx, hostiles, game_map, console=console)
    _result = _run_combat(console, ctx, game_map, _rg)
    _apply_rep(ctx, _result)
    _tutorial.notify_ground_combat_ended(ctx)
    if _result is not None and _result.outcome == 'DEFEAT':
        raise SystemExit()


def save_city_npc_positions(ctx) -> dict:
    """Serialize current ambient city NPC positions by ``city_npc_id``.

    City maps rebuild deterministically on load, so NPC identity and seed
    persist for free; only their in-progress positions need saving (the
    Phase 3 persistence contract). Called from ``saveload.save_game``;
    the reverse (``saveload_maps._restore_city_npc_positions``) reapplies
    them onto the rebuilt city map.
    """
    _positions: dict = {}
    _map = getattr(ctx, "game_map", None)
    if _map is None:
        return _positions
    for _e in getattr(_map, "entities", ()):
        _cid = getattr(_e, "city_npc_id", "")
        if _cid:
            _positions[_cid] = [_e.pos.x, _e.pos.y]
    return _positions


def move_city_npcs(ctx, game_map: world.GameMap) -> None:
    """Advance ambient city NPCs one step (each rolls its move chance once).

    Called once per accepted city action (movement or wait). Each NPC uses
    its own seeded RNG so route choice is deterministic per run. NPCs in an
    active combat encounter (``combat_locked``) are skipped so the combat AI
    owns their position.
    """
    for entity in game_map.entities:
        if not getattr(entity, "city_npc_id", ""):
            continue
        if getattr(entity, "combat_locked", False):
            continue
        if getattr(entity, "city_move_chance", 0) <= 0:
            continue
        rng = entity.city_rng
        if rng.random() >= entity.city_move_chance:
            continue
        _take_one_step(entity, game_map)


__all__ = [
    "place_city_npcs", "move_city_npcs", "is_hostile", "run_city_fight",
    "save_city_npc_positions",
]
