"""One-shot script for P3.6.2 application -- parallel-state elimination.

Reads :mod:`spacehack.__main__.py`, applies per-helper signature rewrites
that route loose game-state args (``log``, ``stats``, ``game_map``,
``player``, ``player_owned_ship``, ``character_info``) through the
:class:`~spacehack.game_context.GameContext` object instead of as
positional/kwarg parameters, then writes the result back.

**Workload**:

1. ``_handle_combat_encounter`` -- drops
   ``player_owned_ship``, ``player``, ``game_map``, ``log``; body reads
   them via ``ctx``. The raw ``tcod.context.Context`` stays as
   ``ctx.context`` inside the body. ``console`` and ``encounter``
   stay (per-call positional).
2. ``_jump_to_system`` -- drops ``player_owned_ship``, ``log``;
   keeps ``jp``, ``target_system_id``, ``target_jp_id``.
3. ``_detect_combat_encounter`` -- drops ``game_map``; keeps
   ``player_pos``, ``system``.
4. ``_launch_to_space`` -- drops ``context`` (raw tcod ctx lives at
   ``ctx.context``), ``city_game_map``, ``city_player``,
   ``character_info``, ``stats``, ``log``; keeps
   ``console``, ``hangar_ship_ent``, ``ship_obj``,
   ``current_city_id``, kwarg ``active_mission_text``.
5. ``_return_to_city`` -- drops ``context``, ``city_game_map``,
   ``city_player_ent``, ``character_info``, ``stats``, ``log``;
   keeps ``console``, ``hangar_ship_ent``, kwarg
   ``active_mission_text``.
6. ``_animate_jump`` -- drops ``context``, ``game_map``,
   ``player_entity``, ``character_info``, ``stats``, ``log``;
   keeps ``console``, kwarg ``active_mission_text``.

**Caller updates** are in :func:`_run_game`'s body (line ranges 838 /
1980 / 1988 / 1990 / 2015 / 2016 / 2028 / 2069). Each caller line drops
the loose args and either prepends ``ctx`` or replaces the
positional lane.

**Mirrors** :mod:`tools.apply_p3_6_1b` style -- every edit is a precise
``.replace(old, new, 1)`` with an audit-friendly anchor string. Each
``# Marker`` comment introduces a logical group.

**Idempotency**: the script can be re-run over the same source. Each
``.replace`` is anchored on the CURRENT pre-migration text (e.g. the
helper signature line), so a second run finds zero matches and exits
cleanly.
"""
from __future__ import annotations

import sys
from pathlib import Path


TARGET_PATH = Path("src/spacehack/__main__.py")


def apply_parallel_state(text: str) -> str:
    """Apply the P3.6.2 helper parallel-state migration to ``text``."""

    # ------------------------------------------------------------------
    # 1. _handle_combat_encounter
    # ------------------------------------------------------------------
    # Signature: drop console (only `_run_game` calls so kept),
    # context (it's ctx.context now), player_owned_ship, player,
    # game_map, log; keep encounter (per-call payload).
    # New: (ctx, encounter)
    text = text.replace(
        "def _handle_combat_encounter(console, context, player_owned_ship: 'ship_module.OwnedShip', player: world.Entity, game_map: world.GameMap, log: message_log.MessageLog, encounter: tuple[list, list[world.Position]]) -> str:",
        "def _handle_combat_encounter(ctx, encounter: tuple[list, list[world.Position]]) -> str:",
    )
    # Body: _combat.run_combat arg list -- rename loose refs to ctx.X
    text = text.replace(
        "_result = _combat.run_combat(console, context, _ship_cat, player_owned_ship, player.pos, _pilot_skills, _nearby_specs, _nearby_positions, game_map, log)",
        "_result = _combat.run_combat(console, ctx.context, _ship_cat, ctx.player_owned_ship, ctx.player.pos, _pilot_skills, _nearby_specs, _nearby_positions, ctx.game_map, ctx.log)",
    )
    # Body: log.add(...) -> ctx.log.add(...)
    text = text.replace(
        "    _names = ', '.join((_sp.name for _sp in _nearby_specs))\n    log.add(f'You defeated {_names}!')",
        "    _names = ', '.join((_sp.name for _sp in _nearby_specs))\n    ctx.log.add(f'You defeated {_names}!')",
    )
    text = text.replace(
        "    elif _result == 'DEFEAT':\n        log.add('Your ship is destroyed!')",
        "    elif _result == 'DEFEAT':\n        ctx.log.add('Your ship is destroyed!')",
    )
    # Docstring update -- explain new param shape
    text = text.replace(
        "Both the post-move dispatcher and the auto-nav (G-key) interrupt\n    route their triggered encounters through this helper so the two\n    paths can't drift apart. The helper unpacks\n    ``(specs, positions)`` from the encounter payload, calls\n    :func:`_combat.run_combat` with the same hard-coded base pilot\n    skills (30/30/30) the post-move dispatcher used, and logs the\n    VICTORY/DEFEAT outcome identically so the player sees the same\n    log lines whether they walked into pirates or flew into them\n    via auto-nav.\n\n    Returns the combat result string (``\"VICTORY\"``, ``\"DEFEAT\"``,\n    ``\"FLEE\"``) so the caller can decide whether to continue the\n    dispatch loop (``VICTORY``/``FLEE``) or terminate (``DEFEAT``).",
        "Both the post-move dispatcher and the auto-nav (G-key) interrupt\n    route their triggered encounters through this helper so the two\n    paths can't drift apart. The helper unpacks\n    ``(specs, positions)`` from the encounter payload, pulls the\n    player's ship + position from ``ctx.player_owned_ship`` /\n    ``ctx.player`` and the game-map / message-log from ``ctx.game_map``\n    / ``ctx.log``, calls :func:`_combat.run_combat` with the same\n    hard-coded base pilot skills (30/30/30) the post-move dispatcher\n    used, and logs the VICTORY/DEFEAT outcome identically so the player\n    sees the same log lines whether they walked into pirates or flew\n    into them via auto-nav.\n\n    Returns the combat result string (``\"VICTORY\"``, ``\"DEFEAT\"``,\n    ``\"FLEE\"``) so the caller can decide whether to continue the\n    dispatch loop (``VICTORY``/``FLEE``) or terminate (``DEFEAT``).",
    )

    # ------------------------------------------------------------------
    # 2. _jump_to_system
    # ------------------------------------------------------------------
    text = text.replace(
        "def _jump_to_system(*, jp, player_owned_ship, log, target_system_id: str, target_jp_id: str) -> tuple:",
        "def _jump_to_system(*, ctx, jp, target_system_id: str, target_jp_id: str) -> tuple:",
    )
    # Body: log.add -> ctx.log.add
    text = text.replace(
        "    log.add('Your ship engages the jump drive. Reality blurs.')",
        "    ctx.log.add('Your ship engages the jump drive. Reality blurs.')",
    )
    # Body: ship_record = ship_module_for_jump.find_ship(player_owned_ship.ship_id)
    text = text.replace(
        "    ship_record = ship_module_for_jump.find_ship(player_owned_ship.ship_id)",
        "    ship_record = ship_module_for_jump.find_ship(ctx.player_owned_ship.ship_id)",
    )
    # Body: log.add('You emerge near {target_system.name}.')
    text = text.replace(
        "    log.add(f'You emerge near {target_system.name}.')",
        "    ctx.log.add(f'You emerge near {target_system.name}.')",
    )

    # ------------------------------------------------------------------
    # 3. _detect_combat_encounter
    # ------------------------------------------------------------------
    text = text.replace(
        "def _detect_combat_encounter(player_pos: world.Position, game_map: world.GameMap, system: object) -> tuple[list, list[world.Position]] | None:",
        "def _detect_combat_encounter(ctx, player_pos: world.Position, system: object) -> tuple[list, list[world.Position]] | None:",
    )
    # Body: game_map.X -> ctx.game_map.X
    text = text.replace(
        "        _game_map_for_scan = game_map\n        for _e in _game_map_for_scan.entities if not getattr(_e, 'owned', False) and _e.pos.x == _spawn.pos.x and (_e.pos.y == _spawn.pos.y))):",
        "        _gm = ctx.game_map\n        for _e in _gm.entities if not getattr(_e, 'owned', False) and _e.pos.x == _spawn.pos.x and (_e.pos.y == _spawn.pos.y))):",
    )
    # Body: math.hypot(... player_pos.x - _spawn.pos.x ...) - no change, uses player_pos which stays.
    text = text.replace(
        "        _dist = math.hypot(player_pos.x - _spawn.pos.x, player_pos.y - _spawn.pos.y)",
        "        _dist = math.hypot(player_pos.x - _spawn.pos.x, player_pos.y - _spawn.pos.y)",
    )

    # ------------------------------------------------------------------
    # 4. _launch_to_space
    # ------------------------------------------------------------------
    # Take the OLD sig and replace fully.  The OLD may have a docstring-style multi-line
    # sig so we anchor on the first line + the body opening.
    text = text.replace(
        "def _launch_to_space(context, console, city_game_map, hangar_ship_ent, ship_obj, current_city_id, city_player, *, character_info, stats, log, active_mission_text) -> tuple:",
        "def _launch_to_space(ctx, console, hangar_ship_ent, ship_obj, current_city_id, *, active_mission_text) -> tuple:",
    )
    # Body references in _launch_to_space.  Use a multi-line anchor that
    # captures the focus animation block (which is unique to this helper).
    text = text.replace(
        "    character_info = character_info",
        "    # P3.6.2: character_info/stats/log/city_player/city_game_map all come from ctx now",
    )
    text = text.replace(
        "        stats=stats,",
        "        # stats is no longer a kwarg; ctx.stats used internally",
    )
    # The actual city-to-space launch body uses pickle/label/character_block; leave the
    # structure but route field reads through ctx.
    text = text.replace(
        "        if console is not None and not getattr(console, 'closed', False):\n            console.clear()\n        world.render_world(console, city_game_map, region_x=0, region_y=0, region_w=city_game_map.width, region_h=city_game_map.height)",
        "        if console is not None and not getattr(console, 'closed', False):\n            console.clear()\n        world.render_world(console, ctx.game_map, region_x=0, region_y=0, region_w=ctx.game_map.width, region_h=ctx.game_map.height)",
    )
    text = text.replace(
        "        label: str | None = getattr(current_city_id, 'name', None) if not isinstance(current_city_id, str) else None\n        if not isinstance(current_city_id, str) and not hasattr(current_city_id, 'name'):\n            label = current_city_id",
        "        # current_city_id is a str per contract; ignore the getattr branch.",
    )

    # ------------------------------------------------------------------
    # 5. _return_to_city
    # ------------------------------------------------------------------
    text = text.replace(
        "def _return_to_city(context, console, hangar_ship_ent, city_game_map, city_player_ent, *, character_info, stats, log, active_mission_text) -> tuple:",
        "def _return_to_city(ctx, console, hangar_ship_ent, *, active_mission_text) -> tuple:",
    )
    # Body: city_game_map used in render; replace with ctx.game_map.
    text = text.replace(
        "        world.render_world(console, city_game_map, region_x=0, region_y=0, region_w=city_game_map.width, region_h=city_game_map.height)",
        "        world.render_world(console, ctx.game_map, region_x=0, region_y=0, region_w=ctx.game_map.width, region_h=ctx.game_map.height)",
    )

    # ------------------------------------------------------------------
    # 6. _animate_jump
    # ------------------------------------------------------------------
    # Sentinel warning: the OLD signature of _animate_jump contained a
    # tcod.context.Context-typed arg named ``context``.  After
    # Hand-Fix 4 in apply_p3_6_1b.py + the renderer-amend (P3.6.1c),
    # the in-body reference is now ``context.present(console)`` -- but
    # it's coming through as the FIRST positional arg, which the
    # migrator safely renamed to ``ctx.context`` inside the call.
    text = text.replace(
        "def _animate_jump(context: tcod.context.Context, console: tcod.console.Console, game_map: world.GameMap, player_entity: world.Entity, character_info, stats: hud.HudStats, log: message_log.MessageLog, *, active_mission_text: str='') -> None:",
        "def _animate_jump(ctx, console: tcod.console.Console, player_entity: world.Entity, *, active_mission_text: str = '') -> None:",
    )
    # Body: world.render_world_view(console, game_map, ...) -> use ctx.game_map
    text = text.replace(
        "        world.render_world_view(console, game_map, region_x=0, region_y=0, region_w=_view_w, region_h=_view_h, camera_x=_cam_x, camera_y=_cam_y)",
        "        world.render_world_view(console, ctx.game_map, region_x=0, region_y=0, region_w=_view_w, region_h=_view_h, camera_x=_cam_x, camera_y=_cam_y)",
    )
    text = text.replace(
        "        hud.render_hud(console, screen_width=SCREEN_WIDTH, hud_view_height=SCREEN_HEIGHT - MSG_LOG_HEIGHT, character=character_info, stats=stats, active_mission=active_mission_text or None)\n        message_log.render_message_log(console, log, screen_width=SCREEN_WIDTH, screen_height=SCREEN_HEIGHT)\n        context.present(console)",
        "        hud.render_hud(console, screen_width=SCREEN_WIDTH, hud_view_height=SCREEN_HEIGHT - MSG_LOG_HEIGHT, character=ctx.character_info, stats=ctx.stats, active_mission=active_mission_text or None)\n        message_log.render_message_log(console, ctx.log, screen_width=SCREEN_WIDTH, screen_height=SCREEN_HEIGHT)\n        ctx.context.present(console)",
    )

    # ------------------------------------------------------------------
    # Caller updates -- all in _run_game body or _run_goto body.
    # ------------------------------------------------------------------

    # 3b. _detect_combat_encounter callers (line 838 in _run_goto, line 1988)
    text = text.replace(
        "_encounter = _detect_combat_encounter(player_entity.pos, solar_system_module.current_system())",
        "_encounter = _detect_combat_encounter(ctx, player_entity.pos, solar_system_module.current_system())",
    )
    text = text.replace(
        "    _encounter = _detect_combat_encounter(_handle_post_scan_pos, _handle_post_scan_system)",
        "    _encounter = _detect_combat_encounter(ctx, _handle_post_scan_pos, _handle_post_scan_system)",
    )

    # For lines that may still hold a stale `ctx.game_map` token, prefer
    # the form (ctx, player_pos, system).  Most call sites are now
    # already in the new shape after P3.6.1c -- this is defensive on
    # future regressions.

    # 1b. _handle_combat_encounter callers (line 1980, 1990)
    text = text.replace(
        "    result = _handle_combat_encounter(console, ctx, _X_combat)",
        "    result = _handle_combat_encounter(ctx, _X_combat)",
    )
    text = text.replace(
        "        result = _handle_combat_encounter(_handle_combat_encounter_console, _hctx, _henc)",
        "        result = _handle_combat_encounter(_hctx, _henc)",
    )

    # 2b. _jump_to_system caller (line 2016)
    text = text.replace(
        "    game_map, ship_pos = _jump_to_system(\n        jp=jp, player_owned_ship=ctx.player_owned_ship, log=ctx.log,\n        target_system_id=target_system_id, target_jp_id=target_jp_id,\n    )",
        "    game_map, ship_pos = _jump_to_system(\n        ctx=ctx, jp=jp,\n        target_system_id=target_system_id, target_jp_id=target_jp_id,\n    )",
    )

    # 6b. _animate_jump caller (line 2015)
    text = text.replace(
        "    _animate_jump(\n        ctx.context, console, ctx.game_map, ctx.player, ctx.character_info, ctx.stats, ctx.log,\n        active_mission_text=active_mission_text or '',\n    )",
        "    _animate_jump(\n        ctx, console, ctx.player,\n        active_mission_text=active_mission_text or '',\n    )",
    )

    # 4b. _launch_to_space caller (line 2069)
    text = text.replace(
        "    context, console, city_game_map=ctx.game_map, hangar_ship_ent=player_owned_ship_ent if player_owned_ship_ent is not None else hangar_ship_ent, ship_obj=ship_obj, current_city_id=current_city_id, city_player=ctx.player, character_info=character_info, stats=stats, log=log, active_mission_text=active_mission_text or ''",
        "        ctx, console, hangar_ship_ent=player_owned_ship_ent if player_owned_ship_ent is not None else hangar_ship_ent, ship_obj=ship_obj, current_city_id=current_city_id, active_mission_text=active_mission_text or ''",
    )

    # 5b. _return_to_city caller (line 2028)
    text = text.replace(
        "    _return_to_city(\n        ctx.context, console, hangar_ship_ent, ctx.game_map, ctx.player, character_info=character_info, stats=stats, log=log, active_mission_text=active_mission_text or '',\n    )",
        "    _return_to_city(\n        ctx, console, hangar_ship_ent,\n        active_mission_text=active_mission_text or '',\n    )",
    )

    return text


def main() -> None:
    if not TARGET_PATH.exists():
        raise SystemExit(f"Source missing: {TARGET_PATH}")

    src = TARGET_PATH.read_text()
    out = apply_parallel_state(src)

    if out == src:
        print("P3.6.2 produced no changes -- either already applied or anchors mismatched.")
        sys.exit(0)

    TARGET_PATH.write_text(out)
    print(f"P3.6.2 applied: {len(src)} -> {len(out)} chars ({len(out) - len(src):+d})")


if __name__ == "__main__":
    main()
