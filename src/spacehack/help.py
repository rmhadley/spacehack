"""Interactive game guide — the ``?`` key.

Press ``?`` at any time to open a browsable menu of topic sections
explaining every system in spacehack. The guide pauses game state
while open; dismiss with ESC from the topic list or ESC from any
section page.

Covers combat formulas, trade mechanics, mission flow, ship systems,
navigation, character skills, factions, and keybindings.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum, auto

import tcod.console
import tcod.context
import tcod.event

from . import ui
from .engine import SCREEN_WIDTH, SCREEN_HEIGHT, make_console
from .game_context import GameContext


# ---------------------------------------------------------------------------
# Data
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class GuideSection:
    """One topic in the game guide.

    ``title`` is shown in the topic list and as the page heading.
    ``body`` is plain text, word-wrapped at render time via
    :func:`spacehack.ui.wrap_text`. Keep sections self-contained;
    cross-references use plain English ("see Trading & Economy").
    """
    title: str
    body: str


class GuideOutcome(Enum):
    """What happened during a guide update call.

    ``IGNORE`` means keep polling (no relevant event).
    ``CLOSED`` means the player dismissed the guide entirely.
    ``BACK_TO_LIST`` means the player pressed ESC from a section
    page and wants to return to the topic list.
    """
    IGNORE = auto()
    CLOSED = auto()
    BACK_TO_LIST = auto()


# ---------------------------------------------------------------------------
# Section content
# ---------------------------------------------------------------------------

_GUIDE_GAME_OVERVIEW = GuideSection(
    title="Game Overview",
    body=(
        "The year is 2156. Humankind has spread across a dozen star systems, "
        "linked by jump gates of unknown origin. You are a freelance pilot "
        "making a living on the frontier — trading, bounty hunting, and "
        "surviving where the law is what you make of it."
        "\n\n"
        "The core loop: start in a city on Earth -> buy a ship at the "
        "spaceport -> launch into the Sol system -> travel to other star "
        "systems via jump gates -> take on missions and trade goods -> earn "
        "credits -> upgrade your ship -> repeat. The game ends when your "
        "ship is destroyed in combat; you then start a fresh run."
        "\n\n"
        "In city mode you walk around a map with h/j/k/l. Interact with "
        "entities by walking into them: ships at the spaceport can be "
        "bought, NPCs in guild halls offer missions and dialog, terminals "
        "let you trade or repair. In space mode you fly your ship on a "
        "solar system map. Bump into planets to land, fly into jump gates "
        "to travel between systems."
    ),
)

_GUIDE_CONTROLS = GuideSection(
    title="Controls & Keybindings",
    body=(
        "Movement: h/j/k/l for cardinal directions, y/u/b/n for diagonals. "
        "These work in city mode, space mode, and during combat."
        "\n\n"
        "City mode keys: Q opens the quest log (view or abandon your active "
        "mission). Walk into entities to interact — ships (buy/launch), NPCs "
        "(talk/missions), terminals (trade/repair). ESC quits the game."
        "\n\n"
        "Space mode keys: G activates auto-nav (Go To) toward a selected "
        "target. M opens the system navigation map showing planets, jump "
        "gates, and your position. C opens the cargo hold. T opens the "
        "comms panel to hail nearby ships. Period (.) waits one turn "
        "(pirates move, shields regen). ESC opens the ship menu."
        "\n\n"
        "Combat keys: h/j/k/l and y/u/b/n move your ship on the tactical "
        "grid. TAB cycles targets. F fires the selected weapon at the "
        "current target. 1-9 select which weapon to fire. S cycles the "
        "shield regeneration rate (0-10). W waits (ends your turn). "
        "ESC attempts to flee combat."
        "\n\n"
        "Modal keys (trade, cargo, menus): Arrow keys or j/k navigate. "
        "ENTER confirms. ESC cancels or goes back. +/- adjusts quantities "
        "where applicable."
    ),
)

_GUIDE_COMBAT = GuideSection(
    title="Combat System",
    body=(
        "Combat is turn-based and plays out on the space map as a tactical "
        "grid. Each combatant has Action Points (AP), a power pool, shields, "
        "and hull hit points."
        "\n\n"
        "AP per turn = 3 + (Piloting // 20). You spend AP to move (1 AP per "
        "cell) and fire weapons (variable cost per weapon). When AP reaches "
        "0, the enemy takes their turn."
        "\n\n"
        "Hit chance formula: weapon.accuracy + (Gunnery * 0.5) + "
        "close-range bonus (5% if within half max range) - distance penalty "
        "(10% per cell beyond max range) - minimum range penalty (5% per "
        "cell inside min range) - target dodge bonus. Result is clamped "
        "between 5% and 95%."
        "\n\n"
        "Dodge bonus: +5% per cell moved this turn (cap 30%) + (Piloting "
        "* 0.5), soft-capped at 60%. Moving during combat makes you "
        "harder to hit."
        "\n\n"
        "Damage: weapon base damage * a quality multiplier (50%-100% based "
        "on a random roll, with a chance of glancing hits at half damage "
        "if the target's Piloting is high) * a variance factor (80%-120%). "
        "Shields absorb damage before hull. When hull reaches 0, the ship "
        "is destroyed."
        "\n\n"
        "Shield regen: set a rate of 0-10 per turn (S key cycles it). Each "
        "point of regen costs power proportional to the rate, with an "
        "Engineering discount (reduces power cost)."
        "\n\n"
        "Flee formula: base 30% + (your Piloting - enemy Piloting) * 2 + "
        "hull desperation bonus (20% at 0 hull) - close distance penalty "
        "(5% per cell under 5 distance) + 10% per previous failed attempt. "
        "Clamped 5%-95%. Each failed flee attempt makes the next one easier."
        "\n\n"
        "Weapon types: Energy weapons (lasers) cost power per shot but have "
        "unlimited ammo. Missile weapons cost no power but consume ammo that "
        "must be purchased and takes up cargo space."
    ),
)

_GUIDE_TRADE = GuideSection(
    title="Trading & Economy",
    body=(
        "Trade terminals appear as = symbols on the city map. Walk into one "
        "to open the trade interface where you can buy and sell goods."
        "\n\n"
        "Each planet has a different economy with supply and demand for "
        "various goods. Buying goods on planets that produce them (low price) "
        "and selling on planets that consume them (high price) is the basic "
        "profit strategy. Prices fluctuate based on the planet's economic "
        "profile."
        "\n\n"
        "Your ship has a cargo capacity (max_cargo). Each trade good takes "
        "up a certain amount of cargo space. Plan your cargo loadout based "
        "on your destination — fill up with goods that will sell well there."
        "\n\n"
        "The current stock of each good on a planet is tracked per-visit "
        "and replenishes over time. You cannot sell more of a good than the "
        "planet demands, and you cannot buy more than it has in stock."
        "\n\n"
        "Your current credits and cargo space are shown in the HUD. The "
        "mechanic terminal (% on the city map) handles ship refueling and "
        "repairs, not trading."
    ),
)

_GUIDE_MISSIONS = GuideSection(
    title="Missions & Bounties",
    body=(
        "Talk to NPCs in guild halls (walk into them) and ask for work. "
        "Each NPC may offer one or more missions. You can only hold one "
        "active mission at a time."
        "\n\n"
        "Mission types:\n"
        "- Delivery: take a package to a specific NPC on another planet. "
        "Travel to the target system, land at the city, and talk to the "
        "recipient NPC to complete.\n"
        "- Bounty: destroy a specific enemy ship in a target system. "
        "The bounty target is marked on the space map. Fly there and "
        "engage in combat. Destroying the target completes the mission "
        "automatically."
        "\n\n"
        "To view or abandon your active mission, press Q in city mode. "
        "The quest log shows the mission details. Press A to initiate "
        "abandon, then ENTER to confirm or ESC to cancel."
        "\n\n"
        "Missions have recommended class and ship cargo requirements. "
        "Check the mission details before accepting — a delivery mission "
        "may require more cargo space than your ship has. Rewards include "
        "credits and experience points."
    ),
)

_GUIDE_SHIPS = GuideSection(
    title="Ships & Equipment",
    body=(
        "Buy a ship by walking into the ship entity at the spaceport in "
        "city mode. Each ship has stats: hull strength, fuel capacity, "
        "cargo capacity, weapon slots, and module slots."
        "\n\n"
        "Weapons are fitted into weapon slots:\n"
        "- Light Laser: 3 damage, 80% accuracy, 1 AP, 2 power\n"
        "- Heavy Laser: 8 damage, 65% accuracy, 1 AP, 6 power\n"
        "- Plasma Cannon: 12 damage, 55% accuracy, 2 AP, 10 power\n"
        "- Light Missile: 10 damage, 75% accuracy, 2 AP, 5 ammo\n"
        "- Heavy Missile: 20 damage, 60% accuracy, 2 AP, 3 ammo\n"
        "- EMP Missile: 0 damage, 70% accuracy, 2 AP, 2 ammo (disables "
        "target systems)"
        "\n\n"
        "Modules fit into module slots and provide bonuses:\n"
        "- Engines (compact_reactor, heavy_reactor): bonus power generation\n"
        "- Systems (shield_capacitor, shield_recharger, targeting_computer, "
        "gyro_stabilizer, expanded_cargo, armor_plating, shield_mk1): "
        "bonuses to shields, gunnery, piloting, cargo, or hull"
        "\n\n"
        "The mechanic terminal (% on the city map) lets you refuel (buy "
        "fuel cells at a per-unit cost) and repair hull damage. Repair "
        "cost scales with damage percentage and ship price."
    ),
)

_GUIDE_NAVIGATION = GuideSection(
    title="Navigation & Jump Gates",
    body=(
        "Space mode places you on a solar system map. Each system contains "
        "planets, jump gates, stations, and potentially other ships. The "
        "view scrolls as you move."
        "\n\n"
        "Jump gates connect star systems. Fly into a jump gate to see where "
        "it connects. Jumping costs fuel (JUMP_FUEL_COST units). If you "
        "don't have enough fuel, the jump is blocked. After jumping, you "
        "arrive at the corresponding jump gate in the destination system."
        "\n\n"
        "G (Go To): opens a target-selection overlay. Pick a planet or "
        "jump gate and your ship auto-navigates there. If you encounter "
        "enemies along the path, combat triggers automatically."
        "\n\n"
        "M (Map): the navigation overlay shows system information, "
        "planet names, jump gate connections, and areas of interest."
        "\n\n"
        "Period (.): wait one turn. Pirates move, shields regenerate, "
        "and NPC ships navigate. Useful for letting enemies come to you "
        "or waiting for shield regen."
        "\n\n"
        "Planets: fly into a planet to approach it. If it has a landing "
        "port, you can land and explore the city. If not, you can only "
        "fly past. Landing triggers a cargo scan."
    ),
)

_GUIDE_CHARACTER = GuideSection(
    title="Character & Skills",
    body=(
        "At the start of the game you choose a species and a class. "
        "These determine your starting skills and flavor."
        "\n\n"
        "Species:\n"
        "- Human: +5 Gunnery, +0 Piloting, +5 Engineering\n"
        "- Martian: +5 Gunnery, +10 Piloting, +5 Engineering"
        "\n\n"
        "Classes:\n"
        "- Pirate: +15 Gunnery, +10 Piloting, +0 Engineering\n"
        "- Merchant: +0 Gunnery, +5 Piloting, +15 Engineering\n"
        "- Bounty Hunter: +10 Gunnery, +10 Piloting, +5 Engineering"
        "\n\n"
        "All skills start at a base of 30, then species and class bonuses "
        "are added on top. Three skills affect gameplay:\n"
        "- Gunnery: improves hit chance in combat (each point = +0.5% "
        "accuracy)\n"
        "- Piloting: determines AP per turn (3 + Piloting//20) and "
        "dodge bonus in combat (each point = +0.5% dodge)\n"
        "- Engineering: reduces power cost of shield regeneration "
        "(each 20 points reduces cost by 1) and increases max power pool "
        "(Engineering // 5 bonus)"
        "\n\n"
        "Module bonuses from your ship (targeting computer, gyro "
        "stabilizer) are added on top of your base skills during combat."
    ),
)

_GUIDE_NPCS = GuideSection(
    title="NPCs & Factions",
    body=(
        "City maps have guild halls with NPCs you can talk to:\n"
        "- Spaceport: buy ships\n"
        "- Merchant guild: trade-related NPCs\n"
        "- Militia guild: law enforcement missions\n"
        "- Bounty guild: bounty hunter missions\n"
        "- Bar: civilian contacts and rumors"
        "\n\n"
        "Walking into an NPC opens a dialog with options: Talk (flavor "
        "text), Work (browse missions), or Deliver (if you have a delivery "
        "mission for that NPC)."
        "\n\n"
        "Faction reputation tracks how each group views you:\n"
        "- Pirates: start at -100 (hostile)\n"
        "- Merchants: start at 0 (neutral)\n"
        "- Civilians: start at 0 (neutral)\n"
        "- Militia: start at 50 (friendly)"
        "\n\n"
        "Reputation changes based on your actions — destroying pirates "
        "improves militia and civilian reputation, attacking civilians "
        "damages all non-pirate factions."
        "\n\n"
        "In space mode, T opens the comms panel. You can hail nearby "
        "ships to identify them. Hostile ships that approach may trigger "
        "combat. Some systems have NPC ship traffic (merchant convoys, "
        "pirate patrols) that move and respond to your presence."
    ),
)

# All sections in order. Add new sections here (insert or append).
GUIDE_SECTIONS: tuple[GuideSection, ...] = (
    _GUIDE_GAME_OVERVIEW,
    _GUIDE_CONTROLS,
    _GUIDE_COMBAT,
    _GUIDE_TRADE,
    _GUIDE_MISSIONS,
    _GUIDE_SHIPS,
    _GUIDE_NAVIGATION,
    _GUIDE_CHARACTER,
    _GUIDE_NPCS,
)


# ---------------------------------------------------------------------------
# Rendering
# ---------------------------------------------------------------------------


# Left-column content width — full screen minus margins.
_CONTENT_WIDTH: int = SCREEN_WIDTH - 6


def render_guide_list(
    console: tcod.console.Console,
    sections: tuple[GuideSection, ...],
    selected: int,
) -> None:
    """Paint the topic-selection list. Clears console first."""
    console.clear()

    # Title
    _title = "GAME GUIDE"
    console.print(
        x=ui.centered_x(_title, SCREEN_WIDTH), y=2,
        string=_title, fg=ui.COLOR_TITLE,
    )

    # Section list — centered vertically, with selection markers
    _list_top = 6
    _n = len(sections)
    for i, sec in enumerate(sections):
        _row = _list_top + i
        _is_sel = i == selected
        _marker = "> " if _is_sel else "  "
        _end = " <" if _is_sel else "  "
        _fg = ui.COLOR_OPTION_HIGHLIGHT if _is_sel else ui.COLOR_OPTION
        console.print(
            x=ui.centered_x(_marker + sec.title + _end, SCREEN_WIDTH),
            y=_row,
            string=_marker + sec.title + _end,
            fg=_fg,
        )

    # Hint
    _hint = "Up/Down navigate - ENTER open - ESC close"
    console.print(
        x=ui.centered_x(_hint, SCREEN_WIDTH), y=SCREEN_HEIGHT - 4,
        string=_hint, fg=ui.COLOR_INSTRUCTION,
    )


def render_guide_page(
    console: tcod.console.Console,
    section: GuideSection,
    page_offset: int = 0,
) -> None:
    """Paint one section's body text, word-wrapped. Clears console first.

    ``page_offset`` is the first line to display (for scrolling long
    sections). Section title, a short divider, and a hint are always
    painted; the body text starts below the divider.
    """
    console.clear()

    # Title
    console.print(
        x=ui.centered_x(section.title, SCREEN_WIDTH), y=2,
        string=section.title, fg=ui.COLOR_TITLE,
    )

    # Subtle divider below title
    _divider = "\u2500" * min(len(section.title) + 4, _CONTENT_WIDTH)
    console.print(
        x=ui.centered_x(_divider, SCREEN_WIDTH), y=3,
        string=_divider, fg=ui.COLOR_VALUE_DIM,
    )

    # Body text — word-wrapped, starting at row 5
    _lines = ui.wrap_text(section.body, _CONTENT_WIDTH)
    _start_y = 5
    _avail_rows = SCREEN_HEIGHT - _start_y - 3  # leave room for hint
    for i in range(_avail_rows):
        _idx = page_offset + i
        if _idx >= len(_lines):
            break
        console.print(
            x=ui.centered_x(_lines[_idx], SCREEN_WIDTH),
            y=_start_y + i,
            string=_lines[_idx],
            fg=ui.COLOR_VALUE_WHITE,
        )

    # Hint — shows page info if multi-page
    _hint: str
    if len(_lines) > _avail_rows:
        _total_pages = (len(_lines) + _avail_rows - 1) // _avail_rows
        _cur_page = page_offset // _avail_rows + 1
        _hint = (
            f"Up/Down scroll  ({_cur_page}/{_total_pages})  "
            "ESC to go back"
        )
    else:
        _hint = "ESC to go back"
    console.print(
        x=ui.centered_x(_hint, SCREEN_WIDTH), y=SCREEN_HEIGHT - 2,
        string=_hint, fg=ui.COLOR_INSTRUCTION,
    )


# ---------------------------------------------------------------------------
# Update
# ---------------------------------------------------------------------------


def update_guide(
    event: tcod.event.Event,
    sections: tuple[GuideSection, ...],
    selected: int,
    viewing: GuideSection | None,
    page_offset: int,
) -> tuple[GuideOutcome, int, int | None]:
    """Handle input for the guide. Returns ``(outcome, new_selected, new_page_offset_or_section_idx)``.

    When the player opens a section, ``new_page_offset_or_section_idx`` is
    the section index (viewing). When they close or navigate the list, it's
    ``None`` for non-section events. The caller applies the state changes.
    """
    if not isinstance(event, tcod.event.KeyDown):
        return GuideOutcome.IGNORE, selected, None if viewing is None else page_offset

    sym_name: str = getattr(event.sym, "name", "").lower()

    if viewing is not None:
        # We are on a section page
        if sym_name in ("escape",):
            return GuideOutcome.BACK_TO_LIST, selected, None
        # Scrolling
        _lines = ui.wrap_text(viewing.body, _CONTENT_WIDTH)
        _avail = SCREEN_HEIGHT - 5 - 3
        if sym_name in ("down", "j") and page_offset + _avail < len(_lines):
            return GuideOutcome.IGNORE, selected, page_offset + 1
        if sym_name in ("up", "k") and page_offset > 0:
            return GuideOutcome.IGNORE, selected, page_offset - 1
        # Any other key closes the page
        return GuideOutcome.BACK_TO_LIST, selected, None
    else:
        # We are on the topic list
        if sym_name in ("escape",):
            return GuideOutcome.CLOSED, selected, None
        if sym_name in ("up", "k") and selected > 0:
            return GuideOutcome.IGNORE, selected - 1, None
        if sym_name in ("down", "j") and selected < len(sections) - 1:
            return GuideOutcome.IGNORE, selected + 1, None
        if sym_name in ("return", "enter", "kp_enter", "kp_5"):
            return GuideOutcome.IGNORE, selected, 0  # page_offset = 0
        # Any other key is ignored on the list
        return GuideOutcome.IGNORE, selected, None


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


def _run_help_guide(ctx: GameContext) -> None:
    """Open the game guide as a modal. Returns when the player closes it.

    Called from ``__main__.py``'s city/space loop and from any modal's
    update function. Game state is paused while the guide is open.
    """
    console = make_console()
    selected = 0
    viewing: GuideSection | None = None
    page_offset: int = 0

    def _render() -> None:
        if viewing is not None:
            render_guide_page(console, viewing, page_offset)
        else:
            render_guide_list(console, GUIDE_SECTIONS, selected)

    def _update(event: tcod.event.Event) -> GuideOutcome:
        nonlocal selected, viewing, page_offset

        if isinstance(event, tcod.event.Quit):
            return GuideOutcome.CLOSED

        outcome, new_sel, new_data = update_guide(
            event, GUIDE_SECTIONS,
            selected if viewing is None else 0,
            viewing, page_offset,
        )

        if outcome is GuideOutcome.CLOSED:
            return GuideOutcome.CLOSED

        if outcome is GuideOutcome.BACK_TO_LIST:
            viewing = None
            page_offset = 0
            return GuideOutcome.IGNORE

        if viewing is not None:
            # On a section page — new_data is page_offset or None
            if new_data is not None:
                page_offset = new_data
            return GuideOutcome.IGNORE

        # On the topic list
        if new_sel != selected:
            selected = new_sel
        if new_data is not None:
            # Open section at new_data index (which is page_offset = 0)
            viewing = GUIDE_SECTIONS[selected]
            page_offset = 0
        return GuideOutcome.IGNORE

    ui.Modal(ctx.context, console).run(_render, _update)
