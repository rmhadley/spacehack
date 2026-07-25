"""One-shot migration of `_animate_ship_to_y` + `_launch_to_space` +
`_return_to_city` to ctx-based field access.

Closes P3.6.2.5: the last 3 deferred helpers (P3.6.2.2) get the same
shape treatment applied to the 4 helpers in the P3.6.2 chain. Body
rewrites replace loose-arg reads with ``ctx.X`` access; signatures
drop the loose kwargs (``character_info``, ``stats``, ``log``,
``active_mission_text``). The 3 callers (2 inside the migrated
helpers + 1 inside ``_run_game`` body at the Launch return path) also
collapse to ``ctx``-only invocations.

Idempotent. Anchors target post-P3.6.2 text exactly. Re-running on
already-migrated code produces 0 changes and prints a count.
"""
from __future__ import annotations

import sys
from pathlib import Path

TARGET = Path("src/spacehack/__main__.py")


def apply(text: str) -> tuple[str, int]:
    """Apply all P3.6.2.5 rewrites. Returns ``(new_text, applied_count)``."""
    applied = 0

    # --- _animate_ship_to_y: signature --------------------------------
    old = (
        "def _animate_ship_to_y(context: tcod.context.Context, console: tcod.console.Console, "
        "ship_ent: world.Entity, game_map: world.GameMap, *, "
        "character_info: dict, stats: hud.HudStats, log: message_log.MessageLog, "
        "active_mission_text: str | None, target_y: int, frame_seconds: float=0.08) -> None:"
    )
    new = (
        "def _animate_ship_to_y(ctx, console: tcod.console.Console, ship_ent: world.Entity, "
        "game_map: world.GameMap, *, target_y: int, frame_seconds: float = 0.08) -> None:"
    )
    if old in text:
        text = text.replace(old, new, 1)
        applied += 1

    # --- _animate_ship_to_y: body (hud.render_hud kwargs + msg-log + present)
    old = (
        "        hud.render_hud(console, screen_width=SCREEN_WIDTH, "
        "hud_view_height=solar_system_module.SOL_VIEW_H, "
        "character=character_info, stats=stats, "
        "active_mission=active_mission_text)\n"
        "        message_log.render_message_log(console, log, "
        "screen_width=SCREEN_WIDTH, screen_height=SCREEN_HEIGHT)\n"
        "        context.present(console)"
    )
    # Replace === the active-mission line picks the title from ctx inside
    # the helper so callers no longer pre-compute and pass it as a kwarg.
    new = (
        "        _active_mission_text = ctx.player_active_mission.title "
        "if ctx.player_active_mission else None\n"
        "        hud.render_hud(console, screen_width=SCREEN_WIDTH, "
        "hud_view_height=solar_system_module.SOL_VIEW_H, "
        "character=ctx.character_info, stats=ctx.stats, "
        "active_mission=_active_mission_text)\n"
        "        message_log.render_message_log(console, ctx.log, "
        "screen_width=SCREEN_WIDTH, screen_height=SCREEN_HEIGHT)\n"
        "        ctx.context.present(console)"
    )
    if old in text:
        text = text.replace(old, new, 1)
        applied += 1

    # --- _launch_to_space: signature + drop kwarg-only TODO comment block
    old = (
        "# TODO(P3.6.2): NOT migrated to ctx -- body still takes raw tcod context\n"
        "#   + loose game-state args. Deferred from P3.6.2 scope because the 80+-line\n"
        "#   body (launch animation + label rect + render) is more complex than the\n"
        "#   4 helpers that DID migrate (_handle_combat_encounter, _jump_to_system,\n"
        "#   _detect_combat_encounter, _animate_jump). Will tackle in P3.7.\n"
        "def _launch_to_space(context: tcod.context.Context, console: tcod.console.Console, "
        "city_game_map: world.GameMap, hangar_ship_ent: world.Entity, ship_obj: ship_module.Ship, "
        "current_city_id: str, city_player: world.Entity, *, "
        "character_info: dict, stats: hud.HudStats, log: message_log.MessageLog, "
        "active_mission_text: str | None) -> tuple[world.GameMap, world.Entity]:"
    )
    new = (
        "def _launch_to_space(ctx, console: tcod.console.Console, city_game_map: world.GameMap, "
        "hangar_ship_ent: world.Entity, ship_obj: ship_module.Ship, "
        "current_city_id: str, city_player: world.Entity) -> tuple[world.GameMap, world.Entity]:"
    )
    if old in text:
        text = text.replace(old, new, 1)
        applied += 1

    # --- _launch_to_space: body -- drop 4 loose kwargs in _animate_ship_to_y call
    old = (
        "        _animate_ship_to_y(context, console, hangar_ship_ent, city_game_map, "
        "character_info=character_info, stats=stats, log=log, "
        "active_mission_text=active_mission_text, target_y=offscreen_y)\n"
        "        log.add(f'You launch the {ship_obj.name} into space.')"
    )
    new = (
        "        _animate_ship_to_y(ctx, console, hangar_ship_ent, city_game_map, target_y=offscreen_y)\n"
        "        ctx.log.add(f'You launch the {ship_obj.name} into space.')"
    )
    if old in text:
        text = text.replace(old, new, 1)
        applied += 1

    # --- _return_to_city: drop TODO comment block + signature
    old = (
        "# TODO(P3.6.2): NOT migrated to ctx -- mirrors _launch_to_space above.\n"
        "#   Both would migrate cleanly as a pair; left deferred so P3.6.2 lands\n"
        "#   first without overcrowding the audit.\n"
        "def _return_to_city(context: tcod.context.Context, console: tcod.console.Console, "
        "hangar_ship_ent: world.Entity, city_game_map: world.GameMap, city_player_ent: world.Entity, "
        "*, character_info: dict, stats: hud.HudStats, log: message_log.MessageLog, "
        "active_mission_text: str | None) -> tuple[world.GameMap, world.Entity]:"
    )
    new = (
        "def _return_to_city(ctx, console: tcod.console.Console, hangar_ship_ent: world.Entity, "
        "city_game_map: world.GameMap, city_player_ent: world.Entity) -> tuple[world.GameMap, world.Entity]:"
    )
    if old in text:
        text = text.replace(old, new, 1)
        applied += 1

    # --- _return_to_city: body -- drop 4 loose kwargs + log.add -> ctx.log.add
    old = (
        "    _animate_ship_to_y(context, console, hangar_ship_ent, city_game_map, "
        "character_info=character_info, stats=stats, log=log, "
        "active_mission_text=active_mission_text, target_y=world.HANGAR_ANCHOR.y)\n"
        "    if city_player_ent not in city_game_map.entities:\n"
        "        city_game_map.entities.append(city_player_ent)\n"
        "    log.add('You return to Earth and dock at your hangar.')"
    )
    new = (
        "    _animate_ship_to_y(ctx, console, hangar_ship_ent, city_game_map, target_y=world.HANGAR_ANCHOR.y)\n"
        "    if city_player_ent not in city_game_map.entities:\n"
        "        city_game_map.entities.append(city_player_ent)\n"
        "    ctx.log.add('You return to Earth and dock at your hangar.')"
    )
    if old in text:
        text = text.replace(old, new, 1)
        applied += 1

    # --- _run_game: caller L2079 _launch_to_space -- drop loose kwargs
    old = (
        "_launch_to_space(context, console, city_game_map, hangar_ship, ship, "
        "current_city_id=current_city_id, city_player=city_player, "
        "character_info=character_info, stats=stats, log=log, "
        "active_mission_text=active_mission_text)"
    )
    new = (
        "_launch_to_space(ctx, console, city_game_map, hangar_ship, ship, "
        "current_city_id=current_city_id, city_player=city_player)"
    )
    if old in text:
        text = text.replace(old, new, 1)
        applied += 1

    # --- _run_game: caller L2038 _return_to_city -- drop loose kwargs
    old = (
        "_return_to_city(context, console, hangar_ship, city_game_map, city_player, "
        "character_info=character_info, stats=stats, log=log, "
        "active_mission_text=active_mission_text)"
    )
    new = (
        "_return_to_city(ctx, console, hangar_ship, city_game_map, city_player)"
    )
    if old in text:
        text = text.replace(old, new, 1)
        applied += 1

    # --- _run_game: caller L2055 _animate_ship_to_y -- drop loose kwargs
    old = (
        "_animate_ship_to_y(context, console, hangar_ship, new_city_map, "
        "character_info=character_info, stats=stats, log=log, "
        "active_mission_text=active_mission_text, target_y=new_anchor.y)"
    )
    new = (
        "_animate_ship_to_y(ctx, console, hangar_ship, new_city_map, target_y=new_anchor.y)"
    )
    if old in text:
        text = text.replace(old, new, 1)
        applied += 1

    return text, applied


def main() -> int:
    text = TARGET.read_text()
    new_text, n = apply(text)
    if n != 9:
        print(f"WARN: expected 9 rewrites, applied {n}", file=sys.stderr)
    if new_text != text:
        TARGET.write_text(new_text)
    print(f"P3.6.2.5: applied {n}/9 rewrites ({len(text)} -> {len(new_text)} chars)")
    return 0 if n == 9 else 1


if __name__ == "__main__":
    sys.exit(main())
