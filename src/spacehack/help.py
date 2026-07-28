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
        "The year is 2200. Humankind has spread across a dozen star systems, "
        "linked by jump gates of unknown origin. You are a freelance pilot "
        "making a living on the frontier."
        "\n\n"
        "How it works:"
        "\n"
        "- Start in a city on Earth"
        "\n"
        "- Buy a ship at the spaceport"
        "\n"
        "- Launch into the Sol system"
        "\n"
        "- Travel to other systems via jump gates"
        "\n"
        "- Take missions and trade goods to earn credits"
        "\n"
        "- Upgrade your ship and repeat"
        "\n\n"
        "Death is permanent: when your ship is destroyed in combat,"
        "you start a fresh run from Earth."
        "\n\n"
        "Game time advances as you fly through space — every 10 or so"
        "moves (depending on your ship's speed) equals one day. Watch"
        "the date in the HUD; months rolling over trigger shop restocks"
        "and economy ticks."
        "\n\n"
        "City mode: walk around the city with h/j/k/l. Walk into entities"
        "to interact — ships at the spaceport (buy/launch), NPCs in guild"
        "halls (talk/missions), terminals (trade/repair)."
        "\n\n"
        "Space mode: fly your ship on the solar system map. Bump into"
        "planets to land, fly into jump gates to travel between systems."
    ),
)

_GUIDE_CONTROLS = GuideSection(
    title="Controls & Keybindings",
    body=(
        "Movement: h/j/k/l for cardinal directions, y/u/b/n for diagonals."
        "\n\n"
        "City mode:"
        "\n"
        "- Q: open quest log (view or abandon mission)"
        "\n"
        "- Walk into entities to interact: ships (buy/launch, view"
        "cargo, view loadout), NPCs (talk/missions), terminals"
        "(trade, mechanic: refuel/repair/manage loadout)"
        "\n"
        "- ESC: quit the game"
        "\n\n"
        "Space mode:"
        "\n"
        "- G: auto-nav (Go To) toward a selected target"
        "\n"
        "- M: navigation map showing planets, gates, your ship"
        "\n"
        "- C: cargo hold"
        "\n"
        "- T: comms panel (hail nearby ships)"
        "\n"
        "- Period (.): wait one turn (pirates move, shields regen)"
        "\n"
        "- ESC: ship menu"
        "\n"
        "- ?: this guide"
        "\n\n"
        "Combat keys:"
        "\n"
        "- h/j/k/l, y/u/b/n: move on the tactical grid"
        "\n"
        "- TAB: cycle targets"
        "\n"
        "- F: fire burst — all active weapons at current target"
        "\n"
        "- 1-9: toggle each weapon on/off ([x] = active, [ ] = inactive)"
        "\n"
        "- S: cycle shield regen rate (0-10)"
        "\n"
        "- W: wait (end your turn)"
        "\n"
        "- ESC: attempt to flee"
        "\n\n"
        "Modal keys (trade, cargo, menus):"
        "\n"
        "- Arrow keys or j/k: navigate"
        "\n"
        "- ENTER: confirm"
        "\n"
        "- ESC: cancel or go back"
        "\n"
        "- TAB: switch between panels (buy/sell in loadout)"
        "\n"
        "- +/-: adjust quantities"
    ),
)

_GUIDE_COMBAT = GuideSection(
    title="Combat System",
    body=(
        "Combat is turn-based on the space map. Each ship has Action Points"
        "(AP), power, shields, and hull hit points."
        "\n\n"
        "Action Points:"
        "\n"
        "- AP per turn = 3 + (Piloting // 20)"
        "\n"
        "- Move: 1 AP per cell"
        "\n"
        "- Fire: AP cost varies by weapon"
        "\n"
        "- When AP reaches 0, the enemy takes their turn"
        "\n\n"
        "Hit chance:"
        "\n"
        "chance = weapon_accuracy + (Gunnery * 0.5)"
        "\n"
        "       + close_bonus (5% if within half max range)"
        "\n"
        "       - dist_penalty (10% per cell beyond max range)"
        "\n"
        "       - min_penalty (5% per cell inside min range)"
        "\n"
        "       - target_dodge_bonus"
        "\n"
        "Result clamped to 5%-95% (always a chance to hit or miss)."
        "\n\n"
        "Dodge bonus:"
        "\n"
        "- +5% per cell moved this turn (cap 30%)"
        "\n"
        "- + (Piloting * 0.5), soft-capped at 60% total"
        "\n"
        "- Moving makes you harder to hit"
        "\n\n"
        "Damage:"
        "\n"
        "raw = weapon_damage * quality_mult (50%-100%)"
        "\n"
        "     * variance (80%-120%)"
        "\n"
        "Shields absorb damage before hull. Hull at 0 = ship destroyed."
        "\n"
        "Enemies with high Piloting skill may cause glancing hits that"
        "deal half damage."
        "\n\n"
        "Weapon burst fire:"
        "\n"
        "- Toggle weapons on/off with number keys (1-9)"
        "\n"
        "- Active weapons show [x] in the HUD; inactive show [ ]"
        "\n"
        "- F fires ALL active weapons in a single burst action"
        "\n"
        "- AP cost = highest AP cost among active weapons"
        "\n"
        "- Power cost = sum of all active energy weapons' power costs"
        "\n"
        "- Ammo is consumed per missile weapon fired"
        "\n"
        "- Each weapon rolls hit/damage independently"
        "\n"
        "- Tactical choice: burst for max damage, or deselect"
        "weapons to conserve power/ammo"
        "\n\n"
        "Shield regeneration:"
        "\n"
        "- Set rate 0-10 per turn with the S key"
        "\n"
        "- Each point of regen costs power (rate - Engineering/20)"
        "\n"
        "- Higher Engineering = cheaper shield regen"
        "\n"
        "- Certain modules (Shield Recharger) give free regen that"
        "stacks on top of the player-set rate"
        "\n\n"
        "Flee chance:"
        "\n"
        "base = 30% + (your Piloting - enemy Piloting) * 2"
        "\n"
        "     + hull_desperation (20% at 0 hull)"
        "\n"
        "     - close_dist_penalty (5%/cell under 5)"
        "\n"
        "     + 10% per previous failed attempt"
        "\n"
        "Result clamped 5%-95%."
        "\n\n"
        "Combat HUD layout (right-side panel):"
        "\n"
        "- Player block: shields (cyan bar), hull (green/yellow/red),"
        "AP with evade bonus, power with next-turn regen (+N)"
        "\n"
        "- Enemy block: each enemy shows name + distance, then"
        "shield bar (cyan) above hull bar with %"
        "\n"
        "- Weapons list: each weapon shows [x]/[ ] toggle, DMG,"
        "effective HIT %, and cost (POW or AMMO + AP)"
        "\n"
        "- Actions panel: keybindings for Target, Move, Fire,"
        "Shields, Wait, Flee"
        "\n"
        "Weapon types:"
        "\n"
        "- Energy (lasers): cost power, unlimited ammo"
        "\n"
        "- Missile: no power cost, limited ammo (takes cargo space)"
    ),
)

_GUIDE_TRADE = GuideSection(
    title="Trading & Economy",
    body=(
        "Trade terminals appear as = symbols on the city map. Walk into"
        "one to buy and sell goods."
        "\n\n"
        "Basic strategy:"
        "\n"
        "- Buy goods on planets that produce them (low price)"
        "\n"
        "- Sell on planets that consume them (high price)"
        "\n"
        "- Each planet has its own economic profile with supply/demand"
        "\n"
        "- Prices fluctuate based on current stock levels"
        "\n\n"
        "Cargo:"
        "\n"
        "- Your ship has a cargo capacity (shown in the HUD)"
        "\n"
        "- Each good takes up a certain amount of cargo space"
        "\n"
        "- Plan your loadout based on your destination"
        "\n"
        "- Current credits and cargo space are always visible in the"
        "HUD sidebar"
        "\n\n"
        "Stock levels:"
        "\n"
        "- Stock is tracked per-planet and replenishes over time"
        "\n"
        "- You cannot sell more than the planet demands"
        "\n"
        "- You cannot buy more than the planet has in stock"
        "\n\n"
        "The mechanic terminal (% on the city map) handles refueling,"
        "repairs, and loadout management, not trading."
    ),
)

_GUIDE_MISSIONS = GuideSection(
    title=        "Missions & Bounties",
    body=(
        "Talk to NPCs in guild halls (walk into them) and ask for work."
        "You can only hold one active mission at a time."
        "\n\n"
        "Mission types:"
        "\n"
        "- Delivery: take a package to a specific NPC on another planet."
        "Travel there, land, and talk to the recipient to complete."
        "\n"
        "- Bounty: destroy a specific enemy ship in a target system."
        "The target is marked on the space map. Engage and destroy to"
        "complete automatically."
        "\n\n"
        "Deadlines:"
        "\n"
        "- Missions may have a time limit — check the quest log (Q)"
        "for the due date and days remaining"
        "\n"
        "- Expired missions show in red in the quest log"
        "\n\n"
        "Managing missions:"
        "\n"
        "- Press Q in city mode to open the quest log"
        "\n"
        "- Press A to initiate abandon, ENTER to confirm, ESC to cancel"
        "\n"
        "- Abandoning frees the slot for a new mission"
        "\n\n"
        "Requirements:"
        "\n"
        "- Missions may require minimum cargo space (delivery)"
        "\n"
        "- Some are best suited for specific classes"
        "\n"
        "- Rewards include credits and experience points"
    ),
)

_GUIDE_SHIPS = GuideSection(
    title="Ships & Equipment",
    body=(
        "Buy a ship by walking into the ship entity at the spaceport."
        "Each ship has: speed (moves per day), hull strength, fuel capacity,"
        "cargo capacity, weapon slots, module slots, base shields,"
        "and power gen."
        "\n\n"
        "Ship speed affects travel time:"
        "\n"
        "- Scout (14): fastest — 14 moves per day"
        "\n"
        "- Starter (10): baseline pace"
        "\n"
        "- Hauler (7) / Freighter (6): slow but huge cargo"
        "\n"
        "- Cruiser (9) / Frigate (8): combat-focused, moderate speed"
        "\n"
        "- Speed determines how many space moves equal one game day"
        "\n\n"
        "Starting loadout:"
        "\n"
        "- Each ship comes with specific weapons and modules"
        "pre-installed (check View Loadout after buying)"
        "\n"
        "- Trade in your current ship for 50% of its purchase"
        "price when upgrading"
        "\n"
        "- Ships are distributed across planets by tier: basic"
        "models on Earth/Mars, advanced ships in deep space"
        "\n\n"
        "Viewing your loadout:"
        "\n"
        "- Bump your ship in the hangar, then choose"
        "'View Loadout'"
        "\n"
        "- Shows installed weapons (name, damage, accuracy,"
        "range) and modules (name + description)"
        "\n"
        "- Stats reflect module bonuses: shields, power gen,"
        "and cargo capacity all include installed modules"
        "\n\n"
        "Tech levels:"
        "\n"
        "- Each planet has a tech level (1-4) that determines"
        "what equipment the mechanic stocks"
        "\n"
        "- TL1 planets (Earth, Mercury): basic weapons and"
        "modules"
        "\n"
        "- TL2 planets (Mars, Venus, Tau Ceti, etc.): mid-tier"
        "weapons and modules"
        "\n"
        "- TL3 planets (Epsilon Eridani, Barnard's b): advanced"
        "gear"
        "\n"
        "- TL4 planets (Sirius Station, Blockade): cutting-edge"
        "military hardware"
        "\n"
        "- Planets with fixed inventories (Earth, Mars) always"
        "stock the same items"
        "\n\n"
        "Managing your loadout at the mechanic:"
        "\n"
        "- Walk into the % terminal on the city map, then"
        "choose 'Manage Loadout'"
        "\n"
        "- Left panel: buy new weapons and modules"
        "(sorted by price)"
        "\n"
        "- Right panel: your installed weapon and module"
        "slots, with sell prices"
        "\n"
        "- TAB: switch between buy and sell panels"
        "\n"
        "- ENTER: buy the selected item (left) or sell the"
        "installed part (right, 50% refund)"
        "\n"
        "- Cannot buy beyond your ship's slot limits"
        "\n\n"
        "Weapons:"
        "\n"
        "- Light Laser (TL1): 3 dmg, 80% acc, 1 AP, 2 power"
        "\n"
        "- Heavy Laser (TL2): 8 dmg, 65% acc, 1 AP, 6 power"
        "\n"
        "- Plasma Cannon (TL3): 15 dmg, 70% acc, 2 AP, 7 power"
        "\n"
        "- Light Missile (TL1): 10 dmg, 75% acc, 2 AP, 5 ammo"
        "\n"
        "- Heavy Missile (TL3): 20 dmg, 60% acc, 2 AP, 3 ammo"
        "\n"
        "- EMP Missile (TL4): 0 dmg (disables systems), 70% acc,"
        "2 AP, 2 ammo"
        "\n\n"
        "Modules (Mk.1-Mk.4 progression available at mechanic):"
        "\n"
        "- Reactors (engine slot): Compact Reactor Mk.1 (+3 power,"
        "TL1), Reactor Mk.2 (+5, TL2), Mk.3 (+8, TL3),"
        "Mk.4 (+12, TL4)"
        "\n"
        "- Heavy Reactor (TL3): +6 power, -1 cargo"
        "\n"
        "- Shields (system slot): Mk.1 (+20, TL1), Mk.2 (+40, TL2),"
        "Mk.3 (+65, TL3), Mk.4 (+95, TL4)"
        "\n"
        "- Targeting (system slot): Computer (+10 gunnery, TL2),"
        "Array Mk.2 (+15, TL3), Mk.3 (+20, TL4), Mk.4 (+30, TL4)"
        "\n"
        "- Gyro (system slot): Stabilizer (+10 piloting, TL2),"
        "Array Mk.2 (+15, TL3), Mk.3 (+20, TL4), Mk.4 (+30, TL4)"
        "\n"
        "- Cargo (system slot): Mk.1 (+30, TL1), Mk.2 (+60, TL2),"
        "Mk.3 (+100, TL3), Mk.4 (+160, TL4)"
        "\n"
        "- Armor (system slot): Mk.1 (+5 hull/-1 power, TL2),"
        "Mk.2 (+10/-2, TL3), Mk.3 (+15/-3, TL4), Mk.4 (+25/-4, TL4)"
        "\n"
        "- Shield Capacitor (TL2): +15 max shields (lightweight"
        "alternative to Mk.2)"
        "\n"
        "- Shield Recharger (TL3): +3 shield regen per turn"
        "(free regen, no power cost)"
        "\n\n"
        "Mechanic terminal (% on the city map):"
        "\n"
        "- Refuel: buy fuel cells at per-unit cost"
        "\n"
        "- Repair: restore hull integrity (cost scales with"
        "damage)"
        "\n"
        "- Manage Loadout: buy and sell weapons and modules"
    ),
)

_GUIDE_NAVIGATION = GuideSection(
    title="Navigation & Jump Gates",
    body=(
        "Space mode places you on a solar system map. Each system contains"
        "planets, jump gates, stations, and other ships. The view scrolls"
        "as you move."
        "\n\n"
        "Jump gates:"
        "\n"
        "- Connect star systems — fly into one to see where it leads"
        "\n"
        "- Jumping costs fuel per jump"
        "\n"
        "- Without enough fuel the jump is blocked"
        "\n"
        "- You arrive at the matching gate in the destination system"
        "\n\n"
        "G (Go To):"
        "\n"
        "- Opens a target-selection overlay"
        "\n"
        "- Pick a planet or jump gate to auto-navigate there"
        "\n"
        "- Combat triggers automatically if enemies cross your path"
        "\n"
        "- Time advances with distance — longer trips take more days"
        "\n\n"
        "M (Map):"
        "\n"
        "- Navigation overlay showing the system layout"
        "\n"
        "- Lists planet names, jump gate connections, and distance"
        "\n\n"
        "Period (.):"
        "\n"
        "- Wait one turn — pirates move, shields regenerate"
        "\n"
        "- Useful for letting enemies come to you"
        "\n\n"
        "Planets:"
        "\n"
        "- Fly into one to approach. Land if it has a port"
        "\n"
        "- Without a port you can only fly past"
        "\n"
        "- Landing triggers a cargo scan by local militia"
    ),
)

_GUIDE_CHARACTER = GuideSection(
    title="Character & Skills",
    body=(
        "At the start you choose a species and a class. These determine"
        "your starting skills. All skills begin at base 30, then species"
        "and class bonuses are added."
        "\n\n"
        "Species:"
        "\n"
        "- Human: +5 Gunnery, +0 Piloting, +5 Engineering"
        "\n"
        "- Martian: +5 Gunnery, +10 Piloting, +5 Engineering"
        "\n\n"
        "Classes:"
        "\n"
        "- Pirate: +15 Gunnery, +10 Piloting, +0 Engineering"
        "\n"
        "- Merchant: +0 Gunnery, +5 Piloting, +15 Engineering"
        "\n"
        "- Bounty Hunter: +10 Gunnery, +10 Piloting, +5 Engineering"
        "\n\n"
        "Skills:"
        "\n"
        "- Gunnery: +0.5% hit chance per point in combat"
        "\n"
        "- Piloting: determines AP/turn (3 + Piloting//20) and dodge"
        "(+0.5% per point, capped at 60%)"
        "\n"
        "- Engineering: reduces shield regen power cost (-1 per 20"
        "points) and increases max power pool (+1 per 5 points)"
        "\n\n"
        "Module bonuses from your ship (targeting computer, gyro"
        "stabilizer) stack on top of your base skills during combat."
    ),
)

_GUIDE_NPCS = GuideSection(
    title="NPCs & Factions",
    body=(
        "City guilds:"
        "\n"
        "- Spaceport: buy ships"
        "\n"
        "- Merchant guild: trade contacts and delivery missions"
        "\n"
        "- Militia guild: law enforcement missions"
        "\n"
        "- Bounty guild: bounty hunting missions"
        "\n"
        "- Bar: civilian contacts and rumors"
        "\n\n"
        "NPC interaction:"
        "\n"
        "- Walk into an NPC to open their dialog"
        "\n"
        "- Talk: flavor text and background"
        "\n"
        "- Work: browse available missions"
        "\n"
        "- Deliver: complete a delivery mission for this NPC"
        "\n\n"
        "Faction reputation:"
        "\n"
        "- Pirates: start at -100 (hostile)"
        "\n"
        "- Merchants: start at 0 (neutral)"
        "\n"
        "- Civilians: start at 0 (neutral)"
        "\n"
        "- Militia: start at 50 (friendly)"
        "\n\n"
        "- Destroying pirates improves militia/civilian rep"
        "\n"
        "- Attacking civilians damages all non-pirate factions"
        "\n\n"
        "Space mode:"
        "\n"
        "- T opens the comms panel to hail nearby ships"
        "\n"
        "- Hostile ships approaching may trigger combat"
        "\n"
        "- Some systems have NPC traffic (convoys, patrols)"
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


# Border frame around the entire guide.
_BORDER_RECT = (1, 1, SCREEN_WIDTH - 2, SCREEN_HEIGHT - 2)

# Left-edge x for left-aligned body text (inside border + padding).
_CONTENT_LEFT: int = 4

# Word-wrap width for body text — matches the space inside the border
# after accounting for 3-char left padding.
_CONTENT_WIDTH: int = SCREEN_WIDTH - 8

# Rows available for body text: room for title (3), divider (1), blank (1),
# then body, then blank (1), divider (1), hint (1), blank (1) before border.
# Shared between render_guide_page and update_guide so scroll logic stays
# consistent.
_BODY_AVAIL_ROWS: int = SCREEN_HEIGHT - 13


def render_guide_list(
    console: tcod.console.Console,
    sections: tuple[GuideSection, ...],
    selected: int,
) -> None:
    """Paint the topic-selection list. Clears console first."""
    console.clear()

    # Border frame (subtle dot-border)
    ui.paint_rect_border(console, _BORDER_RECT, fg=ui.COLOR_VALUE_DIM, char=".")

    # Title
    _title = "GAME GUIDE"
    console.print(
        x=ui.centered_x(_title, SCREEN_WIDTH), y=3,
        string=_title, fg=ui.COLOR_TITLE,
    )

    # Divider below title
    _div = "\u2500" * (SCREEN_WIDTH - 8)
    console.print(
        x=ui.centered_x(_div, SCREEN_WIDTH), y=4,
        string=_div, fg=ui.COLOR_VALUE_DIM,
    )

    # Section list — numbered, centered, with selection marker
    _list_top = 7
    for i, sec in enumerate(sections):
        _row = _list_top + i
        _is_sel = i == selected
        _num = f"{i + 1:02d}"
        _marker = "\u25b8" if _is_sel else " "  # ▸ for selected
        _text = f"{_marker} {_num}  {sec.title}"
        _fg = ui.COLOR_OPTION_HIGHLIGHT if _is_sel else ui.COLOR_OPTION
        console.print(
            x=ui.centered_x(_text, SCREEN_WIDTH),
            y=_row,
            string=_text,
            fg=_fg,
        )

    # Hint
    _hint = "\u2191\u2193 / jk  navigate  \u00b7  ENTER  open  \u00b7  ESC  close"
    console.print(
        x=ui.centered_x(_hint, SCREEN_WIDTH), y=SCREEN_HEIGHT - 5,
        string=_hint, fg=ui.COLOR_INSTRUCTION,
    )


def render_guide_page(
    console: tcod.console.Console,
    section: GuideSection,
    page_offset: int = 0,
) -> None:
    """Paint one section's body text, word-wrapped. Clears console first.

    ``page_offset`` is the first line to display (for scrolling long
    sections). Section title, dividers, and hint are always painted;
    the body text starts below the title divider and is left-aligned
    inside the border frame for easier reading of long passages.
    """
    console.clear()

    # Border frame
    ui.paint_rect_border(console, _BORDER_RECT, fg=ui.COLOR_VALUE_DIM, char=".")

    # Title
    console.print(
        x=ui.centered_x(section.title, SCREEN_WIDTH), y=3,
        string=section.title, fg=ui.COLOR_TITLE,
    )

    # Divider below title
    _div = "\u2500" * min(len(section.title) + 4, _CONTENT_WIDTH)
    console.print(
        x=ui.centered_x(_div, SCREEN_WIDTH), y=4,
        string=_div, fg=ui.COLOR_VALUE_DIM,
    )

    # Body text — word-wrapped, left-aligned, starting at row 6
    _lines = ui.wrap_text(section.body, _CONTENT_WIDTH)
    _start_y = 6
    for i in range(_BODY_AVAIL_ROWS):
        _idx = page_offset + i
        if _idx >= len(_lines):
            break
        console.print(
            x=_CONTENT_LEFT,
            y=_start_y + i,
            string=_lines[_idx],
            fg=ui.COLOR_VALUE_WHITE,
        )

    if not _lines:
        return

    # Bottom divider (same width as body text)
    _hint_y = _start_y + _BODY_AVAIL_ROWS + 1
    if _hint_y < SCREEN_HEIGHT - 2:
        _bd = "\u2500" * _CONTENT_WIDTH
        console.print(
            x=_CONTENT_LEFT, y=_hint_y,
            string=_bd, fg=ui.COLOR_VALUE_DIM,
        )
        _hint_y += 1

    # Hint — scroll indicator with page counter for multi-page sections
    _hint: str
    if len(_lines) > _BODY_AVAIL_ROWS:
        _total_pages = (len(_lines) + _BODY_AVAIL_ROWS - 1) // _BODY_AVAIL_ROWS
        _cur_page = page_offset // _BODY_AVAIL_ROWS + 1
        _hint = (
            f"\u2191\u2193 scroll  ({_cur_page}/{_total_pages})  "
            "\u00b7  ESC  back"
        )
    else:
        _hint = "ESC  go back"
    console.print(
        x=ui.centered_x(_hint, SCREEN_WIDTH), y=_hint_y,
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
        # Scrolling — page-down/page-up for full-page jumps
        _lines = ui.wrap_text(viewing.body, _CONTENT_WIDTH)
        if sym_name in ("pagedown",):
            _next = page_offset + _BODY_AVAIL_ROWS
            if _next < len(_lines):
                return GuideOutcome.IGNORE, selected, _next
            return GuideOutcome.IGNORE, selected, page_offset
        if sym_name in ("pageup",):
            _prev = page_offset - _BODY_AVAIL_ROWS
            if _prev > 0:
                return GuideOutcome.IGNORE, selected, _prev
            return GuideOutcome.IGNORE, selected, 0
        if sym_name in ("down", "j") and page_offset + _BODY_AVAIL_ROWS < len(_lines):
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
