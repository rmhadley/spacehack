"""One-shot script for P3.6.2.1 application -- caller-site fixup after b3779bd.

The P3.6.2 commit (b3779bd) successfully migrated 4 of 6 helper signatures
to ctx-based form (``_handle_combat_encounter``, ``_jump_to_system``,
``_detect_combat_encounter``, ``_animate_jump``). Two helpers
(``_launch_to_space``, ``_return_to_city``) were left at their loose-arg
signatures -- their callers still match those loose-arg shapes, so the
game still runs.

The 6 caller lines for the 4 migrated helpers however were NOT updated
by the b3779bd apply (the anchors I supplied were based on assumed text
shapes, not the actual line content). Playtest would fail with
``TypeError: _handle_combat_encounter() takes 2 positional arguments
but 7 were given`` (and similar for the other 3).

This script updates ONLY the 6 caller lines + the loose-arg references
inside the 4 migrated helper bodies so the runtime matches the new
sigs. ``_launch_to_space`` and ``_return_to_city`` are explicitly
deferred (their bodies are large and complex; safer to land a focused
helper-all-migrated commit later).

**Edits**:

Caller updates (precise anchored ``.replace`` per line):

  L1982: ``_handle_combat_encounter(console, context, player_owned_ship, player, game_map, log, _goto_combat)``
       -> ``_handle_combat_encounter(ctx, _goto_combat)``
  L1992: ``_handle_combat_encounter(console, context, player_owned_ship, player, game_map, log, _encounter)``
       -> ``_handle_combat_encounter(ctx, _encounter)``
  L2018: ``_jump_to_system(jp=jp, player_owned_ship=player_owned_ship, log=log, target_system_id=target_system_id, target_jp_id=target_jp_id)``
       -> ``_jump_to_system(ctx=ctx, jp=jp, target_system_id=target_system_id, target_jp_id=target_jp_id)``
  L840:  ``_detect_combat_encounter(player_entity.pos, ctx.game_map, solar_system_module.current_system())``
       -> ``_detect_combat_encounter(ctx, player_entity.pos, solar_system_module.current_system())``
  L1990: ``_detect_combat_encounter(player.pos, game_map, solar_system_module.current_system())``
       -> ``_detect_combat_encounter(ctx, player.pos, solar_system_module.current_system())``
  L2017: ``_animate_jump(context, console, game_map, player, character_info, stats, log, active_mission_text=active_mission_text or '')``
       -> ``_animate_jump(ctx, console, ctx.player, active_mission_text=active_mission_text or '')``

Body field-reference fixups in the 4 migrated helpers (replace loose
refs with ``ctx.X`` instances inside the new compact scope).

**Idempotency**: anchored on the CURRENT pre-fixup text for caller
lines + body. Second run finds zero matches and reports no changes.
"""
from __future__ import annotations

import sys
from pathlib import Path


TARGET_PATH = Path("src/spacehack/__main__.py")


def apply_caller_fixups(text: str) -> str:
    """Apply the P3.6.2.1 caller-site + body fixups to ``text``."""

    # ------------------------------------------------------------------
    # CALLER UPDATES -- 6 lines, EXACT content copied from the post-b3779bd
    # __main__.py dump. Each anchor includes the call + the FULL arg list
    # so it's unambiguous.
    # ------------------------------------------------------------------

    # 1. _handle_combat_encounter caller (L1982)
    text = text.replace(
        "_handle_combat_encounter(console, context, player_owned_ship, player, game_map, log, _goto_combat)",
        "_handle_combat_encounter(ctx, _goto_combat)",
    )
    # 2. _handle_combat_encounter caller (L1992)
    text = text.replace(
        "_handle_combat_encounter(console, context, player_owned_ship, player, game_map, log, _encounter)",
        "_handle_combat_encounter(ctx, _encounter)",
    )
    # 3. _jump_to_system caller (L2018)
    text = text.replace(
        "_jump_to_system(jp=jp, player_owned_ship=player_owned_ship, log=log, target_system_id=target_system_id, target_jp_id=target_jp_id)",
        "_jump_to_system(ctx=ctx, jp=jp, target_system_id=target_system_id, target_jp_id=target_jp_id)",
    )
    # 4. _detect_combat_encounter caller (L840)
    text = text.replace(
        "_detect_combat_encounter(player_entity.pos, ctx.game_map, solar_system_module.current_system())",
        "_detect_combat_encounter(ctx, player_entity.pos, solar_system_module.current_system())",
    )
    # 5. _detect_combat_encounter caller (L1990)
    text = text.replace(
        "_detect_combat_encounter(player.pos, game_map, solar_system_module.current_system())",
        "_detect_combat_encounter(ctx, player.pos, solar_system_module.current_system())",
    )
    # 6. _animate_jump caller (L2017)
    text = text.replace(
        "_animate_jump(context, console, game_map, player, character_info, stats, log, active_mission_text=active_mission_text or '')",
        "_animate_jump(ctx, console, ctx.player, active_mission_text=active_mission_text or '')",
    )

    # ------------------------------------------------------------------
    # BODY FIELD FIXES -- replace loose Name refs inside the migrated
    # helpers with ctx.X. Each anchor is multiline when needed for
    # uniqueness (e.g. the run_combat call uses many slack-styled refs).
    # ------------------------------------------------------------------

    # _handle_combat_encounter body -- run_combat arg list (was 7 loose
    # refs: console, context, _ship_cat, player_owned_ship, player.pos,
    # _pilot_skills, _nearby_specs, _nearby_positions, game_map, log).
    # After: console, ctx.context (raw ctx.context for tcod API), _ship_cat,
    # ctx.player_owned_ship, ctx.player.pos, _pilot_skills, _nearby_specs,
    # _nearby_positions, ctx.game_map, ctx.log
    text = text.replace(
        "_result = _combat.run_combat(console, context, _ship_cat, player_owned_ship, player.pos, _pilot_skills, _nearby_specs, _nearby_positions, game_map, log)",
        "_result = _combat.run_combat(console, ctx.context, _ship_cat, ctx.player_owned_ship, ctx.player.pos, _pilot_skills, _nearby_specs, _nearby_positions, ctx.game_map, ctx.log)",
    )

    # _jump_to_system body -- player_owned_ship.ship_id and log.add calls
    text = text.replace(
        "    log.add('Your ship engages the jump drive. Reality blurs.')",
        "    ctx.log.add('Your ship engages the jump drive. Reality blurs.')",
    )
    text = text.replace(
        "    ship_record = ship_module_for_jump.find_ship(player_owned_ship.ship_id)",
        "    ship_record = ship_module_for_jump.find_ship(ctx.player_owned_ship.ship_id)",
    )
    text = text.replace(
        "    log.add(f'You emerge near {target_system.name}.')",
        "    ctx.log.add(f'You emerge near {target_system.name}.')",
    )

    # _detect_combat_encounter body -- any `game_map.X` or `_game_map_for_scan`
    # references need to map to `ctx.game_map.X`. The body was already
    # partially rewritten by the b3779bd script, but the second anchor
    # (`_gm.entities`) didn't exist there -- so we need a gentle rewrite.
    text = text.replace(
        "        _game_map_for_scan = game_map\n        _alive_spawns: list = []",
        "        _alive_spawns: list = []",
    )
    text = text.replace(
        "        for _e in _game_map_for_scan.entities",
        "        for _e in ctx.game_map.entities",
    )

    # _animate_jump body -- running:
    #   world.render_world_view(console, game_map, ...)
    #   hud.render_hud(console, ..., character=character_info, stats=stats, ...)
    #   message_log.render_message_log(console, log, ...)
    #   context.present(console)
    text = text.replace(
        "        world.render_world_view(console, game_map, region_x=0, region_y=0, region_w=_view_w, region_h=_view_h, camera_x=_cam_x, camera_y=_cam_y)",
        "        world.render_world_view(console, ctx.game_map, region_x=0, region_y=0, region_w=_view_w, region_h=_view_h, camera_x=_cam_x, camera_y=_cam_y)",
    )
    text = text.replace(
        "        hud.render_hud(console, screen_width=SCREEN_WIDTH, hud_view_height=SCREEN_HEIGHT - MSG_LOG_HEIGHT, character=character_info, stats=stats, active_mission=active_mission_text or None)\n        message_log.render_message_log(console, log, screen_width=SCREEN_WIDTH, screen_height=SCREEN_HEIGHT)\n        context.present(console)",
        "        hud.render_hud(console, screen_width=SCREEN_WIDTH, hud_view_height=SCREEN_HEIGHT - MSG_LOG_HEIGHT, character=ctx.character_info, stats=ctx.stats, active_mission=active_mission_text or None)\n        message_log.render_message_log(console, ctx.log, screen_width=SCREEN_WIDTH, screen_height=SCREEN_HEIGHT)\n        ctx.context.present(console)",
    )

    return text


def main() -> None:
    if not TARGET_PATH.exists():
        raise SystemExit(f"Source missing: {TARGET_PATH}")

    src = TARGET_PATH.read_text()
    out = apply_caller_fixups(src)

    if out == src:
        print("P3.6.2.1 produced no changes -- either already applied or anchors mismatched.")
        sys.exit(0)

    TARGET_PATH.write_text(out)
    print(
        f"P3.6.2.1 applied: {len(src)} -> {len(out)} chars ({len(out) - len(src):+d})"
    )


if __name__ == "__main__":
    main()
