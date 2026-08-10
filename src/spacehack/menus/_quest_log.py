"""Quest log overlay — render, update, and modal runner.

Extracted from the old ``menus.py`` during the package refactor.
Supports up to 5 active missions with arrow-key navigation.
"""

from __future__ import annotations
from enum import Enum, auto

import tcod.console
import tcod.event

from .. import ui
from .. import pygame_ui
from .. import mission as mission_module
from ..game_context import GameContext
from ..engine import MSG_LOG_HEIGHT, SCREEN_HEIGHT, SCREEN_WIDTH, make_console
from ..input_helpers import _try_open_guide


def _pygame_quest_log_enabled() -> bool:
    """Return whether the Pygame Quest Log can render in this runtime."""
    return pygame_ui.presentation_enabled()


def _run_pygame_quest_log(ctx) -> tuple[QuestLogOutcome, int | None] | None:
    """Run the Quest Log in the shared Pygame screen."""
    from ..pygame_quest_log import PygameQuestLogUnavailable, run_for_context

    selected = 0
    confirm_abandon = False
    while True:
        outcome, selected, confirm_abandon = run_for_context(
            ctx, selected, confirm_abandon,
        )
        if outcome == "ABANDONED":
            return QuestLogOutcome.ABANDONED, selected
        if outcome == "QUIT":
            return QuestLogOutcome.QUIT, None
        if outcome == "GUIDE":
            from ..help import _run_help_guide
            _run_help_guide(ctx)
            continue
        return QuestLogOutcome.BACK, None


class QuestLogOutcome(Enum):
    """What the player chose in the city quest log.

    ``ABANDONED`` carries the abandoned mission's index back so
    :func:`_run_game` can log a "You abandoned ..." line and
    remove the mission from the list.
    """
    IGNORE = auto()
    BACK = auto()
    ABANDONED = auto()
    QUIT = auto()


def render_quest_log(console: tcod.console.Console, ctx: GameContext, *, selected: int = 0, confirm_abandon: bool = False, screen_width: int, screen_height: int) -> None:
    """Paint the quest-log overlay — unified terminal look."""
    console.clear()
    missions = ctx.player_active_missions
    col_x = 2
    max_w = ui.rule_width(screen_width)

    # --- Screen header ---
    cy = ui.screen_header(console, screen_width, "QUEST LOG")

    # --- Main quest breadcrumb ---
    from .. import main_quest as _mq
    _mq_obj = _mq.current_main_quest_objective(ctx)
    _mq_started = bool(ctx.main_quest_progress)
    if _mq_obj is not None:
        _mq_title, _mq_desc = _mq_obj
        ui.paint_line(console, col_x, cy, "MAIN QUEST", fg=ui.COLOR_TITLE)
        cy += 1
        ui.paint_line(console, col_x, cy, ui.fit_text(_mq_title, max_w), fg=ui.COLOR_OPTION_HIGHLIGHT)
        cy += 1
        for _line in ui.wrap_text(_mq_desc, max_w):
            if cy >= screen_height - MSG_LOG_HEIGHT - 3:
                break
            ui.paint_line(console, col_x, cy, ui.fit_text(_line, max_w), fg=ui.COLOR_VALUE_DIM)
            cy += 1
    elif _mq_started and ctx.main_quest_complete:
        ui.paint_line(console, col_x, cy, "MAIN QUEST", fg=ui.COLOR_TITLE)
        cy += 1
        ui.paint_line(console, col_x, cy, "(main quest complete)", fg=ui.COLOR_VALUE_DIM)
        cy += 1

    cy += 1

    # --- Active missions ---
    if not missions:
        ui.paint_line(console, col_x, cy, "(no active missions)", fg=ui.COLOR_DESCRIPTION)
        cy += 2
        ui.paint_line(console, col_x, cy, "Press ESC to close.", fg=ui.COLOR_INSTRUCTION)
        from .. import message_log
        message_log.render_message_log(console, ctx.log, screen_width=screen_width, screen_height=screen_height)
        return

    ui.paint_line(console, col_x, cy, f'{len(missions)} / {mission_module.MAX_ACTIVE_MISSIONS} missions', fg=ui.COLOR_VALUE_DIM)
    cy += 1

    list_top = cy
    for i, am in enumerate(missions):
        row = list_top + i * 2
        is_sel = i == selected
        marker = '> ' if is_sel else '  '
        end_marker = ' <' if is_sel else '  '
        console.print(
            x=col_x, y=row, string=f'{marker}{am.title}{end_marker}',
            fg=ui.COLOR_OPTION_HIGHLIGHT if is_sel else ui.COLOR_OPTION,
        )
    if 0 <= selected < len(missions):
        am = missions[selected]
        detail_top = list_top + len(missions) * 2 + 1
        _salv_wreck = getattr(am, 'salvage_wreck_enemy_id', None)
        # Out-and-back missions (intercept, salvage) carry heist_target_good_id
        # — loot the player must bring BACK to the giver. They are NOT bounties
        # (which complete on kill); exclude them so the "Return to" line renders.
        _is_out_and_back = getattr(am, 'heist_target_good_id', None) is not None
        _is_bounty = (
            am.target_enemy_id is not None
            and am.target_system_id is not None
            and _salv_wreck is None  # salvage missions have their own display
            and not _is_out_and_back  # intercept missions have their own display
        )            # Delivery-specific fields.
        if not _is_bounty:
            if am.delivery_target_planet_id:
                _planet_name = am.delivery_target_planet_id
                try:
                    from ..data.planets import find_planet_spec as _fps_q
                    _planet_name = _fps_q(am.delivery_target_planet_id).name
                except (KeyError, ImportError):
                    pass
                _npc_name = ""
                if am.delivery_target_npc_id:
                    _local = _npc_display_name(
                        am.delivery_target_planet_id,
                        am.delivery_target_npc_id,
                    )
                    if _local:
                        _npc_name = f" ({_local})"
                _label = "Return to" if _is_out_and_back else "Deliver to"
                _secured = _is_out_and_back and getattr(am, 'heist_good_secured', False)
                _fg = (120, 220, 120) if _secured else ui.COLOR_VALUE_WHITE
                _sys_name = mission_module.system_name_for_planet(am.delivery_target_planet_id)
                _sys_txt = f" in {_sys_name}" if _sys_name else ""
                ui.paint_line(console, col_x, detail_top, ui.fit_text(f'{_label}: {_planet_name}{_sys_txt}{_npc_name}', max_w), fg=_fg)
                detail_top += 1
            if am.required_cargo_size > 0 and not getattr(am, 'is_smuggle', False):
                ui.paint_line(console, col_x, detail_top, ui.fit_text(f'Cargo: {am.required_cargo_size} units', max_w), fg=ui.COLOR_VALUE_WHITE)
                detail_top += 1

        # Bounty-specific display.
        if _is_bounty:
            # Status: Hunting (gold accent).
            ui.paint_line(console, col_x, detail_top, 'Hunting', fg=ui.COLOR_OPTION_HIGHLIGHT)
            detail_top += 1
            # Danger level based on tier.
            # NOTE: Keep in sync with _bounty_danger_text() in mission.py.
            _t = getattr(am, 'tier', 1)
            if _t >= 4:
                _danger = "Extreme"
                _danger_fg = (255, 60, 60)
            elif _t >= 3:
                _danger = "High"
                _danger_fg = (255, 140, 60)
            elif _t >= 2:
                _danger = "Moderate"
                _danger_fg = (255, 200, 100)
            else:
                _danger = "Low"
                _danger_fg = (140, 200, 140)
            ui.paint_line(console, col_x, detail_top, ui.fit_text(f'Danger: {_danger}', max_w), fg=_danger_fg)
            detail_top += 1
            _target_name = am.bounty_target_name or _npc_ship_name(am.target_enemy_id)
            _target_sys_name = mission_module.system_display_name(am.target_system_id)
            _wing_count = am.bounty_target_squad_size - 1
            _wing_id = getattr(am, 'bounty_wingmate_enemy_id', None)
            _wing_label = "wingmates"
            if _wing_count > 0 and _wing_id and _wing_id != am.target_enemy_id:
                _wing_name = _npc_ship_name(_wing_id)
                _wing_label = (
                    f"{_wing_name} escort" if _wing_count == 1
                    else f"{_wing_name} escorts"
                )
            _squad_str = f" + {_wing_count} {_wing_label}" if _wing_count > 0 else ""
            ui.paint_line(console, col_x, detail_top, ui.fit_text(f'Target: {_target_name} ({_target_sys_name}){_squad_str}', max_w), fg=ui.COLOR_VALUE_WHITE)
            detail_top += 1

        if _salv_wreck is not None:
            _patrol_name = _npc_ship_name(am.target_enemy_id)
            _patrol_count = am.bounty_target_squad_size
            _wing_id = getattr(am, 'bounty_wingmate_enemy_id', None)
            if _patrol_count > 1:
                if _wing_id and _wing_id != am.target_enemy_id:
                    _wing_name = _npc_ship_name(_wing_id)
                    _wing_label = (
                        f"{_wing_name}" if _patrol_count - 1 == 1
                        else f"{_wing_name}s"
                    )
                    _patrol_label = f'{_patrol_name} + {_patrol_count - 1} {_wing_label}'
                else:
                    _patrol_label = f'{_patrol_count}x {_patrol_name}'
            else:
                _patrol_label = _patrol_name
            _sys_txt = f" ({mission_module.system_display_name(am.target_system_id)})"
            ui.paint_line(console, col_x, detail_top, ui.fit_text(f'Patrol: {_patrol_label}{_sys_txt}', max_w), fg=ui.COLOR_VALUE_WHITE)
            detail_top += 1
            _wreck_name = _npc_ship_name(_salv_wreck)
            _comp = _good_display_name(am.heist_target_good_id)
            _secured = getattr(am, 'heist_good_secured', False)
            _status = 'SECURED' if _secured else 'SOMEWHERE IN THE WRECK'
            _sfg = (120, 220, 120) if _secured else (255, 180, 80)
            ui.paint_line(console, col_x, detail_top, ui.fit_text(f'Recover: {_comp} ({_status})', max_w), fg=_sfg)
            detail_top += 1
            ui.paint_line(console, col_x, detail_top, ui.fit_text(f'Board the {_wreck_name} to search it', max_w), fg=ui.COLOR_VALUE_DIM)
            detail_top += 1

        _heist_good = getattr(am, 'heist_target_good_id', None)
        if _heist_good is not None and _salv_wreck is None:
            _target_name = _npc_ship_name(am.target_enemy_id)
            _target_sys = mission_module.system_display_name(am.target_system_id)
            ui.paint_line(console, col_x, detail_top, ui.fit_text(f'Target: {_target_name} ({_target_sys})', max_w), fg=ui.COLOR_VALUE_WHITE)
            detail_top += 1
            _good_name = _good_display_name(_heist_good)
            _secured = getattr(am, 'heist_good_secured', False)
            _status = 'SECURED' if _secured else 'NOT SECURED'
            _sfg = (120, 220, 120) if _secured else (255, 180, 80)
            ui.paint_line(console, col_x, detail_top, ui.fit_text(f'Cargo: {_good_name} ({_status})', max_w), fg=_sfg)
            detail_top += 1

        if getattr(am, 'is_smuggle', False):
            _sgid = getattr(am, 'smuggle_good_id', None)
            _sgood = _good_display_name(_sgid)
            ui.paint_line(console, col_x, detail_top, ui.fit_text(f'Cargo: {_sgood} ({am.required_cargo_size} units)', max_w), fg=ui.COLOR_VALUE_WHITE)
            detail_top += 1
            _risk, _risk_fg = _smuggle_scan_risk(ctx, am)
            ui.paint_line(console, col_x, detail_top, ui.fit_text(f'SCAN RISK: {_risk}', max_w), fg=_risk_fg)
            detail_top += 1

        ui.paint_line(console, col_x, detail_top, ui.fit_text(f'Reward: {am.reward_credits}$ + {am.reward_xp}xp', max_w), fg=ui.COLOR_VALUE_WHITE)
        detail_top += 1
        if am.time_deadline is not None:
            _d, _m, _y = am.time_deadline
            _total_days = (_y - ctx.time_year) * 360 + (_m - ctx.time_month) * 30 + (_d - ctx.time_day)
            _date_str = f'{_y}{_m:02d}{_d:02d}'
            if _total_days >= 0:
                ui.paint_line(console, col_x, detail_top, ui.fit_text(f'Due: {_date_str} ({_total_days} days)', max_w), fg=ui.COLOR_OPTION_HIGHLIGHT)
            else:
                ui.paint_line(console, col_x, detail_top, ui.fit_text(f'EXPIRED - Due: {_date_str}', max_w), fg=(255, 80, 80))
            detail_top += 1

    detail_top += 2
    if confirm_abandon:
        ui.paint_line(console, col_x, detail_top, 'Press ENTER to abandon. ESC cancels.', fg=ui.COLOR_OPTION_HIGHLIGHT)
    else:
        ui.paint_line(console, col_x, detail_top, 'ARROW KEYS navigate - A abandon - ESC close.', fg=ui.COLOR_INSTRUCTION)

    from .. import message_log
    message_log.render_message_log(console, ctx.log, screen_width=screen_width, screen_height=screen_height)


def update_quest_log(event: tcod.event.Event, *, confirm_abandon: bool) -> QuestLogOutcome:
    """Map a single event for the quest-log overlay.

    Two states:
      * ``confirm_abandon`` False — ESC -> BACK, A -> ABANDONED.
      * ``confirm_abandon`` True — ENTER -> ABANDONED, ESC -> BACK.
    """
    if isinstance(event, tcod.event.Quit):
        return QuestLogOutcome.QUIT
    if not isinstance(event, tcod.event.KeyDown):
        return QuestLogOutcome.IGNORE
    sym = event.sym
    sym_name: str = getattr(sym, 'name', '').lower()
    if sym in ui._ESCAPE_SYMS:
        return QuestLogOutcome.BACK
    if confirm_abandon:
        if sym in ui._ENTER_SYMS:
            return QuestLogOutcome.ABANDONED
        return QuestLogOutcome.IGNORE
    if sym_name == 'a':
        return QuestLogOutcome.ABANDONED
    return QuestLogOutcome.IGNORE


# Scan-risk bands: ``(hold_divisor, label, fg)`` evaluated in order.
# Low when the hold covers the full cargo (hold >= cargo // 1), Medium
# at half coverage (hold >= cargo // 2), else High. Divisors preserve
# the exact integer semantics of the original thresholds.
_SCAN_RISK_STEPS: tuple[tuple[int, str, tuple[int, int, int]], ...] = (
    (1, "Low",    (120, 220, 120)),
    (2, "Medium", (255, 200, 100)),
)


def _npc_ship_name(ship_id: str | None) -> str:
    """Resolve an NpcShipSpec id to its display name, with fallback.

    Falls back to a title-cased version of the raw id when the
    catalog lookup fails. ``None`` resolves to ``"unknown"``.
    """
    if not ship_id:
        return "unknown"
    try:
        from ..data.npc_ships import find_npc_ship as _fns
        return _fns(ship_id).name
    except (KeyError, ImportError):
        return ship_id.replace('_', ' ').title()


def _npc_display_name(planet_id: str, npc_id: str) -> str:
    """Resolve the planet-local NPC display name (e.g. 'Mars Barkeep').

    Checks the planet's ``npc_overrides`` first so a bartender on Mars
    shows as "Mars Barkeep" rather than the generic "Barkeep", then
    falls back to the global NPC catalog. Returns "" if unresolvable.
    """
    try:
        from ..data.planets import find_planet_spec as _fps_dn
        _spec = _fps_dn(planet_id)
        for _oid, _npc in getattr(_spec, 'npc_overrides', ()) or ():
            if _oid == npc_id:
                return _npc.name
    except (KeyError, ImportError):
        pass
    try:
        from ..data.npcs import find_npc as _fnpc_dn
        return _fnpc_dn(npc_id).name
    except (KeyError, ImportError):
        return ""


def _good_display_name(good_id: str | None) -> str:
    """Resolve a trade-good id to its display name, with fallback.

    Falls back to a title-cased version of the raw id when the
    catalog lookup fails (unknown / procedural goods). ``None``
    resolves to ``"contraband"`` (generic smuggled cargo label).
    """
    if not good_id:
        return "contraband"
    try:
        from ..data.trade_goods import find_trade_good as _ftg
        return _ftg(good_id).name
    except (KeyError, ImportError):
        return good_id.replace('_', ' ').title()


def _smuggle_scan_risk(ctx, am) -> tuple[str, tuple[int, int, int]]:
    """Return ``(label, fg)`` for a smuggling mission's scan risk.

    Compares the mission's cargo volume against the player's current
    smuggler's hold capacity (sum of installed ``smuggler_cargo``
    module bonuses). Looked up from :data:`_SCAN_RISK_STEPS`; falls
    back to High when coverage drops below half.
    """
    from .. import ship as _ship_sm
    _cargo = am.required_cargo_size
    _hold = _ship_sm.smuggler_hold_capacity(ctx.player_owned_ship)
    for _div, _label, _fg in _SCAN_RISK_STEPS:
        if _hold >= _cargo // _div:
            return _label, _fg
    return "High", (255, 80, 80)


def _quest_log_navigate(event: tcod.event.Event, selected: int, n: int) -> int | None:
    """If ``event`` drives quest log nav, return the new ``selected`` index."""
    if n <= 0:
        return None
    if not isinstance(event, tcod.event.KeyDown):
        return None
    sym = event.sym
    sym_name: str = getattr(sym, 'name', '').lower()
    if sym in ui._UP_SYMS or sym_name == 'k':
        return (selected - 1) % n
    if sym in ui._DOWN_SYMS or sym_name == 'j':
        return (selected + 1) % n
    return None


def _run_quest_log(ctx) -> tuple[QuestLogOutcome, int | None]:
    """Show the city quest-log overlay and return the outcome.

    Returns ``(outcome, abandoned_index)``: ``abandoned_index`` is
    the index of the abandoned mission (for removal from the list),
    or ``None``.
    """
    result = _run_pygame_quest_log(ctx)
    if result is None:
        raise RuntimeError("Quest Log returned no outcome")
    return result
