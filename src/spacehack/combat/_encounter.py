"""Combat encounter dispatcher and death screen.

_handle_combat_encounter is the wrapper called from __main__.py
to start combat and handle victory/defeat outcomes (bounty
completion, death screen).

_render_death_screen displays the dramatic "ship destroyed" overlay
when the player loses.
"""

from __future__ import annotations

import tcod.event

from ..engine import SCREEN_WIDTH, SCREEN_HEIGHT
from ._loop import run_combat


def _handle_combat_encounter(ctx, console, encounter) -> str:
    """Resolve a combat encounter triggered by the dispatcher.

    Was inlined in __main__._handle_combat_encounter pre-N1; promoted
    to combat.py so the dispatcher stays combat-unaware. The
    encounter param is normally a tuple ``(specs, positions)``
    produced by ``navigation._detect_combat_encounter``.

    Returns ``"VICTORY"``, ``"DEFEAT"``, or ``"FLEE"``.
    """
    from .. import ui as _ui_module

    # Already dead from a previous defeat — no-op.
    if getattr(ctx, 'player_dead', False):
        return "DEFEAT"

    if not encounter:
        ctx.log.add("Encounter data missing.")
        return "FLEE"

    try:
        _specs, _positions = encounter
    except (ValueError, TypeError):
        ctx.log.add("Corrupted encounter data.")
        return "FLEE"

    # Resolve pilot skills — use ctx defaults if available, else
    # hard-coded 30/30/30 as a fallback for test/legacy callers.
    _pilot_skills = getattr(ctx, 'pilot_skills', None)
    if _pilot_skills is None:
        from ..data.pilot_skills import PilotSkills
        _pilot_skills = PilotSkills(gunnery=30, piloting=30, engineering=30)

    # Sanity: player must have a ship catalog and owned ship.
    if ctx.player_owned_ship is None:
        ctx.log.add("No ship — cannot start combat.")
        return "FLEE"

    _ship_cat = None
    from ..data.ships import find_ship as _find_ship_catalog
    try:
        _ship_cat = _find_ship_catalog(ctx.player_owned_ship.ship_id)
    except (KeyError, AttributeError):
        ctx.log.add("Ship catalog mismatch — cannot start combat.")
        return "FLEE"

    _combat_result, _defeated_ids, _defeated_names = run_combat(
        console, ctx.context,
        _ship_cat, ctx.player_owned_ship,
        ctx.player.pos, _pilot_skills,
        _specs, _positions,
        ctx.game_map, ctx.log, ctx,
    )

    if _combat_result == "VICTORY":
        if len(_defeated_names) == 1:
            ctx.log.add(f"Victory! {_defeated_names[0]} destroyed.")
        else:
            ctx.log.add(f"Victory! {len(_defeated_names)} enemies destroyed.")

        # Check bounty completion: if the player has an active bounty
        # mission and the defeated enemy matches, complete it.
        _missions = getattr(ctx, 'player_active_missions', [])
        for _m in _missions:
            if getattr(_m, 'target_enemy_id', None) is not None:
                _bounty_target = _m.target_enemy_id
                if _bounty_target in _defeated_ids:
                    from ..mission import complete_mission as _complete
                    _today = ctx.time_day + (ctx.time_month - 1) * 30
                    _complete(_m, ctx.player_owned_ship, ctx.stats, ctx.log, current_day=_today)
                    if not _m.is_procedural:
                        ctx.completed_mission_ids.add(_m.mission_id)
                    try:
                        _missions.remove(_m)
                    except ValueError:
                        pass
                    ctx.player_active_missions = _missions
                    ctx.log.add(f"Bounty complete! {_m.title}")
                    # Clean up bounty spawn if present.
                    _bounty_spawn_data = getattr(ctx, 'bounty_spawn_data', None)
                    if _bounty_spawn_data is not None:
                        _bx, _by, _bspec_id = _bounty_spawn_data
                        for _e in list(ctx.game_map.entities):
                            if getattr(_e, 'npc_ship_id', None) == _bspec_id:
                                ctx.game_map.entities.remove(_e)
                        ctx.bounty_spawn_data = None
                    break

        # Remove dead enemies from the game map.
        # Enemy world.Entity objects store their spec reference via
        # npc_ship_id (set by npc_ships.py / solar_system.py).
        for _e in list(ctx.game_map.entities):
            _e_spec = getattr(_e, 'npc_ship_id', None)
            if _e_spec is not None and _e_spec in _defeated_ids:
                ctx.game_map.entities.remove(_e)

    elif _combat_result == "DEFEAT":
        ctx.player_dead = True
        _render_death_screen(console, ctx.context, ctx.log)

    return _combat_result


def _render_death_screen(console, context, log) -> None:
    """Display a dramatic full-screen death overlay and wait for input.

    Renders a red-tinted screen with a final message and the message
    log so the player can review how they died.
    """
    from .. import message_log as _ml

    _lines = [
        "",
        "╔══════════════════════════════════════╗",
        "║          SHIP DESTROYED              ║",
        "╚══════════════════════════════════════╝",
        "",
        "Your ship has been destroyed.",
        "All crew lost. All cargo lost.",
        "",
        "Press any key to return to the main menu...",
    ]

    while True:
        console.clear()
        console_bg = (40, 0, 0)  # dark red background
        for y in range(SCREEN_HEIGHT):
            for x in range(SCREEN_WIDTH):
                console.print(x=x, y=y, string=" ", fg=(255, 255, 255), bg=console_bg)

        # Centre the death message
        _msg_y = SCREEN_HEIGHT // 2 - len(_lines) // 2
        for _i, _line in enumerate(_lines):
            _x = (SCREEN_WIDTH - len(_line)) // 2
            console.print(x=_x, y=_msg_y + _i, string=_line, fg=(255, 80, 80))

        # Show recent log entries at the bottom
        _ml.render_message_log(
            console, log,
            screen_width=SCREEN_WIDTH,
            screen_height=SCREEN_HEIGHT,
        )

        context.present(console)

        for event in tcod.event.wait():
            if isinstance(event, tcod.event.Quit):
                raise SystemExit()
            if isinstance(event, tcod.event.KeyDown):
                return
