"""Ship hangar — tabbed modal runner.

One ``pygame_screen`` modal with SHIP / CARGO / LOADOUT tabs for the
player's owned ship while in city mode (the C-screen pattern): TAB
cycles tabs, ENTER launches on the SHIP tab or jettisons a selected
good on the CARGO tab, ESC walks away. Also exports ``_find_hangar_ship``
used by the landing animation code in ``__main__.py``.

Extracted from the old ``menus.py`` during the package refactor.
"""

from __future__ import annotations
from enum import Enum, auto

from .. import world
from .. import ship as ship_module

class ShipMenuAction(Enum):
    """Which sub-modal of the hangar menu the player triggers."""
    IGNORE = auto()
    VIEW = auto()
    LOADOUT = auto()
    REFUEL = auto()
    SELL = auto()
    LAUNCH = auto()
    BACK = auto()
    QUIT = auto()

_HANGAR_TABS: tuple[str, ...] = ("SHIP", "CARGO", "LOADOUT")
"""The single source of truth for the hangar tab names and count."""

# ---------------------------------------------------------------------------
# Effective-stat helpers (sums base + module bonuses)
# ---------------------------------------------------------------------------

def _effective_shields(ship_spec, owned) -> int:
    """Sum base shield max + effective module max_shield_bonuses."""
    from ..combat._stats import _calc_max_shields
    return _calc_max_shields(
        ship_spec, getattr(owned, 'modules', ()) or (),
    )

def _effective_power_gen(ship_spec, owned) -> int:
    """Sum base power gen + effective module power_gen_bonuses."""
    from ..combat._stats import _calc_power_gen
    return _calc_power_gen(
        ship_spec, getattr(owned, 'modules', ()) or (),
    )


def _overview_lines(ctx, owned, ship) -> tuple[str, str]:
    """The overview's important numbers (in-play 2026-09-30), read
    through combat's own derivation — ``_player_combat_values`` — so
    the hangar can never drift from the fight: hull, shields + free
    regen, AP, and the power pool with its per-turn regen."""
    from ..combat._stats import _free_shield_regen, _player_combat_values
    from ..data.pilot_skills import PilotSkills
    from ..hud import ap_pool_str
    from ..xp import ace_pilot_ap_bonus, systems_expert_power_bonus

    (_gun, _pil, _eng, ap, ap_gain, power_regen, max_shields,
     hull, max_hull, max_power) = _player_combat_values(
        ship, owned,
        PilotSkills(
            gunnery=ctx.stats.gunnery,
            piloting=ctx.stats.piloting,
            engineering=ctx.stats.engineering,
        ),
        ace_pilot_ap_bonus(ctx),
        systems_expert_power_bonus(ctx),
    )
    return (
        f"Hull {hull}/{max_hull}   Shields {max_shields}   "
        f"Shield regen {_free_shield_regen(ship, owned.modules)}/turn",
        f"AP {ap_pool_str(ap, ap_gain % 20)}   Max power {max_power}   "
        f"Power regen {power_regen}/turn",
    )


def _gear_list_lines(owned) -> tuple[list[str], list[tuple | None]]:
    """The WEAPONS/MODULES sections: tier-coloured names with their
    stat lines attached (doc 56 SETTLED 20)."""
    from .. import pygame_ui
    from ..menus._grid_editor import entry_view

    muted = pygame_ui.DEFAULT_PALETTE.muted
    lines: list[str] = []
    runs: list[tuple | None] = []
    for label, entries in (
        ("WEAPONS", getattr(owned, "weapons", ()) or ()),
        ("MODULES", getattr(owned, "modules", ()) or ()),
    ):
        if not entries:
            continue
        lines.append(label)
        runs.append(((label, muted),))
        for entry in entries:
            try:
                name, stats, color = entry_view(entry)
            except KeyError:
                continue
            lines.append(f"{name} - {stats}")
            runs.append(((name, color), (f" - {stats}", None)))
    return lines, runs


def loadout_readout(ctx, owned, ship) -> tuple[tuple[str, ...], tuple]:
    """The shared LOADOUT readout (doc 56 SETTLED 20/21): the OVERVIEW
    block, then the active weapons and modules with their stats — the
    hangar tab's whole body, and the mechanic tab's body under its
    Manage row."""
    from .. import pygame_ui

    body = ["OVERVIEW", *_overview_lines(ctx, owned, ship)]
    runs: list[tuple | None] = [
        (("OVERVIEW", pygame_ui.DEFAULT_PALETTE.muted),), None, None,
    ]
    gear_lines, gear_runs = _gear_list_lines(owned)
    body.extend(gear_lines)
    runs.extend(gear_runs)
    if not gear_lines:
        body.append("Nothing installed.")
        runs.append(None)
    return tuple(body), tuple(runs)


def _loadout_section(ctx, owned, ship):
    """Build the LOADOUT tab's body, rows, and footer.

    Doc 56 SETTLED 20 (playtest 2026-09-30, amends 19 for the hangar):
    the overview's important numbers, then a list of the active
    weapons and modules with their stats attached. The letter grid
    lives in the mechanic's editor (SETTLED 21)."""
    from .. import pygame_ui

    body, body_runs = loadout_readout(ctx, owned, ship)
    rows = ()
    footer = (pygame_ui.modal_hint(
        pygame_ui.NAV_HINT, "TAB ship", "ESC back", pygame_ui.GUIDE_HINT,
    ),)
    return body, rows, footer, body_runs

def _faction_progress_bar(rep: int, width: int = 31) -> str:
    """Return the CP437-safe centered faction reputation bar."""
    half = width // 2
    neg_fill = int((abs(rep) / 100) * half) if rep < 0 else 0
    pos_fill = int((rep / 100) * half) if rep >= 0 else 0
    neg_fill = max(0, min(half, neg_fill))
    pos_fill = max(0, min(half, pos_fill))
    left = ["#" if neg_fill >= half - index else "-" for index in range(half)]
    right = ["#" if pos_fill >= index + 1 else "-" for index in range(half)]
    return "".join(left + ["|"] + right)

async def _run_faction_view(ctx) -> None:
    """Show faction standings with the refreshed Pygame presentation."""
    from .. import pygame_faction

    while True:
        outcome = await pygame_faction.run_for_context(ctx.context, ctx)
        if outcome == "GUIDE":
            from ..help import _open_context_guide
            await _open_context_guide(ctx, "NPCs & Factions")
            continue
        return

def _launch_row():
    """Build the Launch row that lives at the bottom of the SHIP tab."""
    from .. import pygame_screen

    return pygame_screen.ScreenRow(
        "Launch", "Leave the hangar and enter space.", "LAUNCH",
    )

def _ship_section(ctx, owned, ship):
    """Build the SHIP tab's body, rows, and footer."""
    from .. import pygame_ui

    max_cargo = ship_module.effective_max_cargo(ship, owned, ctx)
    _hull_cur, _hull_max = ship_module.hull_cur_max(owned, ship)
    body = (
        ship.description,
        "",
        f"Fuel: {owned.fuel} / {ship.max_fuel}",
        f"Hull: {_hull_cur} / {_hull_max}",
        f"Speed: {ship_module.effective_speed(ship, owned)}",
        f"Shields: {_effective_shields(ship, owned)}",
        f"Power: {_effective_power_gen(ship, owned)}",
        f"Cargo: {owned.cargo_used} / {max_cargo}",
        pygame_ui.credits_label(ctx.stats.credits),
        "",
    )
    rows = (_launch_row(),)
    footer = (pygame_ui.modal_hint(
        pygame_ui.NAV_HINT, "ENTER launch", "TAB cargo",
        "ESC back", pygame_ui.GUIDE_HINT,
    ),)
    return body, rows, footer


def _cargo_section(ctx, owned, ship):
    """Build the CARGO tab's body, rows, and footer."""
    from .. import pygame_ui
    from ..trade import _cargo_body, _cargo_rows

    max_cargo = ship_module.effective_max_cargo(ship, owned, ctx)
    rows = _cargo_rows(owned)
    body = _cargo_body(ctx, owned, max_cargo)
    footer = (pygame_ui.modal_hint(
        pygame_ui.NAV_HINT, "ENTER jettison", "TAB loadout",
        "ESC back", pygame_ui.GUIDE_HINT,
    ),)
    return body, rows, footer


def _ship_hangar_frame(ctx, ship: ship_module.Ship, tab: int, selected: int):
    """Build one tabbed hangar snapshot (SHIP / CARGO / LOADOUT tabs)."""
    from .. import pygame_screen, pygame_ui

    owned = ctx.player_owned_ship
    if owned is None:
        return pygame_screen.ScreenFrame(
            "YOUR SHIP", ("No ship equipped.",), (),
            (pygame_ui.modal_hint("ESC back", pygame_ui.GUIDE_HINT),),
        )
    title = f"YOUR {ship_module.ship_display_name(owned).upper()}"
    sections = {
        0: _ship_section,
        1: _cargo_section,
        2: _loadout_section,
    }
    body, rows, footer, *extra = sections.get(tab, _loadout_section)(ctx, owned, ship)
    body_runs = extra[0] if extra else ()
    return pygame_screen.ScreenFrame(
        title, body, rows, footer, selected,
        tabs=_HANGAR_TABS, active_tab=tab, body_runs=body_runs,
        # The LOADOUT tab's overview + gear list can outgrow one
        # screen on a full rack — it pages (UP/DOWN at the ends)
        # instead of dropping the font off the shared ladder top.
        scrollable=tab == 2,
    )

async def _run_pygame_ship_hangar(ctx, ship: ship_module.Ship) -> ShipMenuAction | None:
    """Run the tabbed hangar through the shared Pygame screen.

    TAB cycles SHIP → CARGO → LOADOUT → SHIP; ENTER launches from the
    SHIP tab or jettisons a selected good on the CARGO tab; ``?`` reopens
    the guide; ESC walks away.
    """
    from .. import pygame_screen

    tab = 0
    selected = 0
    while True:
        outcome, action, selected = await pygame_screen.run_for_context(
            getattr(ctx, "context", ctx),
            _ship_hangar_frame(ctx, ship, tab, selected),
            caption="spacehack - ship hangar",
        )
        if outcome == "GUIDE":
            from ..help import _open_context_guide
            await _open_context_guide(ctx, "Ships & Equipment")
            continue
        _next_tab = pygame_screen.cycled_tab(outcome, tab, len(_HANGAR_TABS))
        if _next_tab is not None:
            tab, selected = _next_tab, 0
            continue
        if outcome in {"PAGE_UP", "PAGE_DOWN"}:
            continue
        if outcome == "QUIT":
            return ShipMenuAction.QUIT
        if outcome == "SELECT":
            if action == "LAUNCH":
                return ShipMenuAction.LAUNCH
            if tab == 1:
                from ..trade import _apply_jettison
                owned = ctx.player_owned_ship
                if owned is not None and await _apply_jettison(ctx, owned, action):
                    continue
            return None
        return ShipMenuAction.BACK

async def _run_ship_menu(ctx, ship: ship_module.Ship) -> ShipMenuAction:
    """Show the tabbed hangar modal for ``ship``; return the chosen action.

    One tabbed screen (SHIP / CARGO / LOADOUT, the C-screen pattern): no
    nested sub-modals. TAB cycles tabs, ENTER launches on the SHIP tab
    or jettisons on the CARGO tab, ESC walks away.
    """
    return await _run_pygame_ship_hangar(ctx, ship)

def _find_hangar_ship(city_game_map: world.GameMap, player_owned_ship: ship_module.OwnedShip | None) -> world.Entity | None:
    """Return the player's owned hangar ship entity in ``city_game_map``."""
    if player_owned_ship is None:
        return None
    return next((e for e in city_game_map.entities if e.owned and e.ship_id == player_owned_ship.ship_id), None)
