"""Skill/stats/cargo frames for the character screen.

The Stats- and Cargo-tab presentation builders plus the skill tables
and expedition capacity helpers — split from character_screen to pay
the 1000-line ratchet (2026-09-23). character_screen re-exports the
surface so callers keep their import paths.
"""
from __future__ import annotations

from .game_context import GameContext


def _trait_names(trait_ids) -> list[str]:
    from .data.traits.core import trait_name
    return [trait_name(t) for t in trait_ids]


_SKILLS: tuple[str, ...] = (
    "gunnery", "piloting", "engineering",
    "reflexes", "strength", "stamina",
)
# One-line general description per skill, shown at the bottom of the
# Stats tab. Kept in sync with the guide's Character & Skills section.
_SKILL_DESCRIPTIONS: dict[str, str] = {
    "gunnery": "+0.5% hit chance per point in space combat",
    "piloting": "AP per round (3 + Piloting/20, fractional with carry) and +0.5% dodge/pt",
    "engineering": "+1 max power per 5 pts; paid shield regen -1 power per 20 pts",
    "reflexes": "+0.5% accuracy and +0.5% dodge per point on foot",
    "strength": "+1 melee damage per 5 pts; +1 pack slot per 5 pts above 10",
    "stamina": "max ground HP 20 + Stamina//2 (+1 HP per 2 pts)",
}


def _skill_base(ctx: GameContext, index: int, skill: str) -> int:
    """One skill's base value — ship skills read ctx.stats, ground
    stats ctx.ground_stats (the first three _SKILLS are the ship set)."""
    return getattr(ctx.stats if index < 3 else ctx.ground_stats, skill, 10)


def _skill_value_display(ctx: GameContext, index: int, skill: str) -> str:
    """One skill's value cell: ship skills read base + installed-module
    bonuses — the same effective sum combat uses — with the bonus
    annotated ("36 (+9)", "13 (-12)"); ground stats and bonus-less
    skills show the plain value (doc 47.4 SETTLED 29)."""
    from .combat._stats import _skill_bonuses

    base = _skill_base(ctx, index, skill)
    owned = getattr(ctx, "player_owned_ship", None)
    if index >= 3 or owned is None:
        return f"{base:>3}"
    effective = _skill_bonuses(
        ctx.stats, getattr(owned, "modules", ()) or (),
    )[index]
    bonus = effective - base
    # The number keeps its right-aligned width-3 column when the
    # bonus rides along, so tiered rows stay in line with plain ones.
    return f"{effective:>3} ({bonus:+d})" if bonus else f"{base:>3}"


def _skill_spend_marker(ctx: GameContext, index: int, skill: str) -> str:
    """The [+]/MAX spend marker — base-value driven, as spending is."""
    base = _skill_base(ctx, index, skill)
    if ctx.player_skill_points > 0 and base < 100:
        return "[+]"
    return "MAX" if base >= 100 else ""


def _stats_header_lines(ctx: GameContext, current_xp: int, needed: int) -> tuple[str, ...]:
    """The informational header rows above the stats (the old
    ScreenFrame body, verbatim — Brief 4.3 moves them into the
    pane; the strings are unchanged)."""
    _gear = [
        _name for _flag, _name in (
            (getattr(ctx, "transponder_cutout", False), "transponder cut-out"),
            (getattr(ctx, "transponder_rig", False), "clone rig"),
        ) if _flag
    ]
    return (
        f"XP: {current_xp} / {needed}    Skill points available: {ctx.player_skill_points}",
        f"Traits: {', '.join(_trait_names(ctx.player_traits)) or 'None'}",
        *(("Gear: " + ", ".join(_gear),) if _gear else ()),
    )


def _skill_value_cell(ctx: GameContext, index: int, skill: str) -> str:
    """The stat row's value cell (ledger 16): the skill display,
    the xN chrome count for the bay, and the spend marker."""
    from .chrome import installed_for_skill

    cell = _skill_value_display(ctx, index, skill)
    _count = len(installed_for_skill(
        getattr(ctx, "installed_chrome", ()), skill,
    ))
    if _count:
        cell += f" x{_count}"
    marker = _skill_spend_marker(ctx, index, skill)
    if marker:
        cell += f"  {marker}"
    return cell


def _info_row(label: str):
    """One display-only pane row (the right pane carries no actions)."""
    from . import pygame_split

    return pygame_split.SplitRow(label, "", "", "", selectable=False)


# The piece sub-line's slight indent (2026-10-17 playtest revision:
# the name row with the ruled detail indented below reads as one
# unit without a leader line).
_PIECE_DETAIL_INDENT = "   "


def _chrome_pane_rows(ctx: GameContext, skill: str) -> tuple:
    """The right pane (display-only): each installed piece as its
    name with the ruled detail line slightly indented below. The
    skill description moved to the left pane's pinned detail
    (2026-10-17 playtest revision)."""
    from .chrome import installed_for_skill
    from .data.chrome import find_chrome

    pieces = installed_for_skill(
        getattr(ctx, "installed_chrome", ()), skill,
    )
    if not pieces:
        return (_info_row("Nothing installed."),)
    rows = []
    for piece_id in pieces:
        spec = find_chrome(piece_id)
        rows.append(_info_row(spec.name))
        rows.append(_info_row(_PIECE_DETAIL_INDENT + spec.detail))
    return tuple(rows)


def _selected_skill(left_rows, selected: int) -> str:
    """The stat row the cursor sits on (header rows clamp to the
    nearest stat; the runner only ever returns selectable indices,
    but the first build seeds arbitrary values)."""
    indices = [i for i, row in enumerate(left_rows) if row.selectable]
    if not indices:
        return _SKILLS[0]
    if selected not in indices:
        selected = min(indices, key=lambda index: abs(index - selected))
    return left_rows[selected].action.partition(":")[2]


def _stats_frame(ctx: GameContext, title: str, current_xp: int, needed: int, selected: int):
    """Build the Stats-tab split frame (Brief 4.3, cluster C): the
    six stat rows + xN piece counts on the left (the selected row's
    guide-synced skill description pins below the pane, as the old
    Stats tab did), each installed piece as name-over-detail on the
    right, the ruled ego readout under both panes. ENTER stays
    SPEND; the right pane never takes focus."""
    from . import pygame_split, pygame_ui
    from .chrome import ego_readout_line, state_line

    header = tuple(
        pygame_split.SplitRow(line, "", "", "", selectable=False)
        for line in _stats_header_lines(ctx, current_xp, needed)
    )
    stats = tuple(
        pygame_split.SplitRow(
            f"{skill.title():<12}",
            _skill_value_cell(ctx, index, skill),
            _SKILL_DESCRIPTIONS[skill],
            f"SPEND:{skill}",
        )
        for index, skill in enumerate(_SKILLS)
    )
    left = header + stats
    return pygame_split.SplitFrame(
        title, "Skills", "Chrome",
        left, _chrome_pane_rows(ctx, _selected_skill(left, selected)),
        ego_readout_line(ctx), state_line(ctx),
        pygame_ui.modal_hint(
            pygame_ui.NAV_HINT, "ENTER spend", "TAB equipment",
            "ESC close", pygame_ui.GUIDE_HINT,
        ),
        selected=selected,
        screen_tabs=("STATS", "EQUIPMENT", "CARGO"), active_screen_tab=0,
    )




def _cargo_character_frame(ctx: GameContext, title: str, selected: int):
    """Build the Cargo tab by reusing the cargo manifest presentation."""
    from . import ship as ship_module
    from .trade import _cargo_body, _cargo_rows
    from . import pygame_screen, pygame_ui

    owned = ctx.player_owned_ship
    if owned is None:
        return pygame_screen.ScreenFrame(
            title, ("No ship available.",), (),
            (pygame_ui.modal_hint("TAB next tab", "ESC close", pygame_ui.GUIDE_HINT),),
            tabs=("STATS", "EQUIPMENT", "CARGO"), active_tab=2,
        )
    ship_spec = ship_module.find_ship(owned.ship_id)
    max_cargo = ship_module.effective_max_cargo(ship_spec, owned, ctx)
    body = _cargo_body(ctx, owned, max_cargo)
    return pygame_screen.ScreenFrame(
        title, body, _cargo_rows(owned),
        (pygame_ui.modal_hint(
            pygame_ui.NAV_HINT, "ENTER jettison selected", "TAB equipment", "ESC close", pygame_ui.GUIDE_HINT,
        ),),
        selected, tabs=("STATS", "EQUIPMENT", "CARGO"), active_tab=2,
    )


def _expedition_capacity(ctx: GameContext) -> int:
    """Return the current Expedition Pack capacity."""
    from . import ground_equipment

    from .xp import pack_mule_capacity_bonus

    strength = int(getattr(getattr(ctx, "ground_stats", None), "strength", 10))
    strength += pack_mule_capacity_bonus(ctx) * 10
    return ground_equipment.expedition_capacity(strength)


def _expedition_used_slots(ctx: GameContext) -> int:
    """Return Expedition Pack slot usage (equipment + item stacks)."""
    return len(ctx.ground_expedition_inventory) + len(
        getattr(ctx, "ground_expedition_items", []),
    )


