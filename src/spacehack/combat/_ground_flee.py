"""Ground flee — the stair-dance machinery (doc 54 phase 2).

The implementation sibling of ``_rules_ground``'s one-line flee hooks
(the ``_ground_blast`` / ``_ground_charger`` pattern): the reaction
volley (every enemy that can hit the player right now attacks once,
from where it stands) and the in-combat exit attempt (probe the
stair's refusal conditions, refund the step on refusal, otherwise eat
the volley and end the fight DISENGAGED with the exit payload — the
CALLER runs the transition; the loop never does).
"""

from __future__ import annotations

from .. import world
from ._types import FleeExit
from ._ai_ground import _try_ground_fire
from ._ground_math import calc_ground_move_dodge as _calc_ground_move_dodge
from ._ground_render import render_frame
from ..data.ground_weapons import find_ground_weapon as _find_gw
from ..xp import ground_evade_bonus as _ground_evade_bonus


async def reaction_volley(state, ctx, game_map: world.GameMap) -> bool:
    """The flee reaction volley (doc 54): every live enemy that can
    hit the player RIGHT NOW — weapon band plus LOS — attacks once
    from where it stands; no movement, no repositioning. The shot
    pays its AP; the damage lands through the shared enemy-hit tail.
    Returns True when the player died (death wins: the transition
    never runs)."""
    from . import _rules_ground

    _dodge = (
        _calc_ground_move_dodge(state.cells_moved_this_turn)
        + _ground_evade_bonus(ctx)
    )
    # The volley is enemy-shot presentation, not the player's aiming
    # phase: hide the range line for its frames like the enemy turn
    # does (the _rules_ground context manager restores it after).
    with _rules_ground._range_line_hidden():
        for _gei in (e for e in state.enemies if e.alive and e.weapon_id):
            try:
                _ews = _find_gw(_gei.weapon_id)
            except KeyError:
                continue
            _shot = await _try_ground_fire(
                ctx, state.console, render_frame, game_map,
                _gei.entity, ctx.player.pos, _gei.weapon_id, _ews,
                _gei.spec, _gei.stats, state.armor_defense, _dodge,
                _gei.weapon_quality,
            )
            if _shot is None:
                continue  # out of band or no LOS: no parting shot
            _dmg, _ap_cost = _shot
            _gei.ap = max(0, _gei.ap - _ap_cost)
            if _dmg > 0:
                _rules_ground._apply_enemy_hit(ctx, _gei, _dmg)
                if state.player_hp <= 0:
                    return True
        return False


async def attempt_exit(state, ctx, game_map: world.GameMap,
                       dx: int, dy: int) -> str | None:
    """The in-combat stair-step exit (doc 54 phase 2).

    Called by the loop right after a MOVE lands on a transition tile
    — the step itself is the commit (SETTLED 1; no extra prompt).
    The stair's refusal conditions are probed BEFORE anything fires:
    a refusing stair refunds the step (position restored, AP back,
    same turn — SETTLED 3). Otherwise the reaction volley resolves,
    survivors get the stairs as their last-seen memory, and the fight
    ends DISENGAGED with the exit payload — the caller's ordinary
    tile dispatch runs the transition. Returns ``None`` (not on a
    transition tile), ``"HELD"`` (refused: full no-op), 
    ``"DISENGAGED"`` (survived), or ``"DEFEAT"`` (the volley killed
    the player — death wins)."""
    from . import _rules_ground

    _tile = game_map.tiles[ctx.player.pos.y][ctx.player.pos.x]
    if _tile.kind not in world.TRANSITION_KINDS:
        return None
    if _stair_transition_refuses(ctx, game_map, _tile.kind):
        # Refund the step: previous cell, AP returned, same turn. The
        # momentary sight reveal from the step may persist — position,
        # AP, and turn state are what restore (SETTLED 3 build note).
        ctx.player.pos = world.Position(
            ctx.player.pos.x - dx, ctx.player.pos.y - dy,
        )
        state.player_ap += 1
        state.cells_moved_this_turn = max(0, state.cells_moved_this_turn - 1)
        return "HELD"
    if await reaction_volley(state, ctx, game_map):
        _rules_ground.on_player_death(ctx)
        return "DEFEAT"
    state.flee_exit = FleeExit(verb=_tile.kind)
    _rules_ground.on_disengage(ctx, game_map)
    return "DISENGAGED"


def _dig_stair_refuses(game_map, direction: int) -> bool:
    """The dig-floor stair bounds: no floor above the entrance, no
    floor below the site's seeded depth (derived on read — the
    isolated seeded RNG draws nothing from the shared stream). An
    unknown planet id refuses, mirroring the handler's except."""
    from ..digs import parse_cache_key, site_depth
    from ..data.planets import find_planet_spec as _fps

    _planet_id, _site_id, _floor = parse_cache_key(
        game_map.interior_cache_key,
    )
    try:
        _depth = site_depth(_fps(_planet_id), _site_id)
    except KeyError:
        return True
    if _floor + direction < 1:
        return True  # the dig entrance is the top floor
    return direction > 0 and _floor + 1 > _depth


def _stair_transition_refuses(ctx, game_map, tile_kind: str) -> bool:
    """The out-of-combat stair handlers' refusal conditions, probed
    WITHOUT running any transition (doc 54 phase 2: a refusing stair
    refunds the step and fires no volley — SETTLED 3). Mirrors
    ``game_loop._handle_stairs_down``/``_handle_stairs_up``'s branch
    order and calls the same pure validators; the handlers' own
    try/except stays the runtime net for what a static probe cannot
    see (a floor load failing at transition time)."""
    from ..digs import is_dig_floor

    if tile_kind == "exit":
        return False  # the only gate is the player's own abandon choice
    _direction = 1 if tile_kind == "stairs_down" else -1
    if is_dig_floor(game_map):
        return _dig_stair_refuses(game_map, _direction)
    _ext = getattr(ctx, "dungeon_extension", None)
    if _ext is not None and _ext.active:
        if tile_kind == "stairs_down" or _ext.current_floor > 1:
            try:
                from ..dungeon_extensions import _transition_target_floor

                _transition_target_floor(_ext, _direction)
            except (KeyError, ValueError):
                # The handlers' own tuple: sealed gate / entrance
                # floor / no such depth / a missing floor definition.
                return True
            return False
        # stairs_up at the extension's floor 1: leave_extension's checks.
        return ctx.interiors.get(_ext.parent_map_key) is None
    if tile_kind == "stairs_down":
        from ..dungeon_extensions import extension_id_at

        return extension_id_at(game_map, ctx.player.pos) is None
    return True  # stairs_up with no dig and no extension: sealed
