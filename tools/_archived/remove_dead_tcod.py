#!/usr/bin/env python3
"""One-off codemod: delete the dead tcod modal machinery.

Removes the listed top-level functions/classes/constants from each file by
name (AST-driven, formatting-preserving) and drops dead names from any
``__all__`` lists. Run from the repo root:

    python3 tools/remove_dead_tcod.py

Prints every removed symbol. Does NOT touch imports or call sites — those
are fixed by hand afterwards (see the session notes).
"""
from __future__ import annotations

import ast
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

REMOVE: dict[str, list[str]] = {
    "src/spacehack/ui.py": [
        "render_selectable_list", "render_menu", "render_confirm",
        "render_title_menu", "update_title_menu", "render_title_splash",
        "update_menu", "update_confirm", "Modal",
        "content_metrics", "paint_text", "paint_centered", "paint_rule",
        "render_split_frame",
        "_safe_syms", "_UP_SYMS", "_DOWN_SYMS", "_ENTER_SYMS", "_ESCAPE_SYMS",
    ],
    "src/spacehack/comms.py": [
        "_CommsListOutcome", "_render_comms_panel", "_render_interaction_modal",
        "_pygame_comms_enabled",
        "_CONTACTS_TITLE_COLOR", "_CONTACTS_FLAVOR", "_CONTACTS_DIM",
        "_INTERACTION_TITLE", "_INTERACTION_FLAVOR", "_INTERACTION_OPTION",
        "_INTERACTION_HIGHLIGHT", "_INTERACTION_INSTRUCTION",
    ],
    "src/spacehack/menus/_missions.py": [
        "_offerings_to_menu", "render_mission_offerings",
        "update_mission_offerings", "_mission_navigate",
        "_pygame_interactive_enabled",
    ],
    "src/spacehack/menus/_ship_menu.py": [
        "SHIP_MENU_OPTIONS", "render_ship_menu", "_ship_menu_navigate",
        "update_ship_menu", "render_loadout_view", "_render_loadout_weapons",
        "_render_loadout_modules", "render_faction_view",
        "_pygame_readonly_enabled", "_pygame_ship_menu_enabled",
    ],
    "src/spacehack/menus/_ship_buy.py": [
        "render_ship_buy", "update_ship_buy", "_pygame_ship_buy_enabled",
    ],
    "src/spacehack/menus/_planet.py": [
        "render_planet_menu", "update_planet_menu", "_pygame_interactive_enabled",
    ],
    "src/spacehack/menus/_quest_log.py": [
        "update_quest_log", "_pygame_quest_log_enabled",
    ],
    "src/spacehack/menus/_mechanic.py": ["_pygame_mechanic_enabled"],
    "src/spacehack/menus/_loadout.py": ["_pygame_split_enabled"],
    "src/spacehack/menus/_armory.py": ["_pygame_split_enabled"],
    "src/spacehack/npc.py": [
        "render_npc_talk", "update_npc_talk", "_npc_talk_navigate",
        "_pygame_interactive_enabled",
    ],
    "src/spacehack/navigation.py": [
        "update_navigation", "render_jump_menu", "update_jump_menu",
        "_pygame_readonly_enabled",
    ],
    "src/spacehack/help.py": [
        "GuideOutcome", "GUIDE_SELECTED_MARKER", "_BODY_AVAIL_ROWS",
        "render_guide_list", "render_guide_page", "update_guide",
        "_pygame_help_enabled",
    ],
    "src/spacehack/character_screen.py": [
        "_render_stats", "_render_equipment", "_pygame_character_enabled",
    ],
    "src/spacehack/trade.py": [
        "_pygame_split_enabled", "_pygame_quantity_enabled",
        "_pygame_cargo_enabled",
    ],
    "src/spacehack/input_helpers.py": ["_pygame_character_enabled"],
    "src/spacehack/main_quest/_act0.py": [
        "_ModalOutcome", "_overlay_box", "_centered_print",
        "_modal_dismiss_update", "_OFFER_BODY_WIDTH",
        "render_incoming_transmission", "render_quest_summon",
        "render_gate_popup", "render_sealed_door_overlay",
        "render_help_offer", "render_quest_readout",
    ],
    "src/spacehack/main_quest/_act1.py": [
        "OrbitSceneOutcome", "_selected_disclosure", "_update_orbit_scene",
        "_render_disclosure_options", "_render_orbit_scene",
    ],
    "src/spacehack/engine.py": ["open_terminal"],
    "src/spacehack/pygame_batch.py": ["run_readonly"],
}

MISSING: list[str] = []


def _node_name(node: ast.AST) -> str | None:
    """Return the bound name for a top-level def/class/assign node."""
    if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
        return node.name
    if isinstance(node, ast.Assign):
        # Only simple single-target name assignments at module level.
        if len(node.targets) == 1 and isinstance(node.targets[0], ast.Name):
            return node.targets[0].id
    return None


def _strip_all(module: ast.Module, dead: set[str]) -> None:
    """Drop dead names from any module-level ``__all__`` list in place."""
    for node in module.body:
        if not isinstance(node, ast.Assign):
            continue
        if len(node.targets) != 1 or not isinstance(node.targets[0], ast.Name):
            continue
        if node.targets[0].id != "__all__":
            continue
        if not isinstance(node.value, (ast.List, ast.Tuple)):
            continue
        kept = [
            elt for elt in node.value.elts
            if not (isinstance(elt, ast.Constant) and isinstance(elt.value, str)
                    and elt.value in dead)
        ]
        node.value.elts = kept


def _removed_ranges(module: ast.Module, dead: set[str]) -> list[tuple[int, int]]:
    """Return (start, end) 1-based line ranges of removed top-level nodes."""
    ranges: list[tuple[int, int]] = []
    for node in module.body:
        name = _node_name(node)
        if name is not None and name in dead:
            ranges.append((node.lineno, getattr(node, "end_lineno", node.lineno)))
    return ranges


def rewrite(path: Path, dead: set[str]) -> None:
    source = path.read_text()
    tree = ast.parse(source)
    _strip_all(tree, dead)
    ranges = _removed_ranges(tree, dead)
    if not ranges:
        return
    lines = source.splitlines(keepends=True)
    drop: set[int] = set()
    for start, end in ranges:
        for lineno in range(start, end + 1):
            drop.add(lineno)
        # Also drop one following blank line so blocks don't leave gaps.
        if end + 1 <= len(lines) and lines[end - 1].strip() == "":
            drop.add(end + 1)
    kept = [line for i, line in enumerate(lines, start=1) if i not in drop]
    path.write_text("".join(kept))
    for name in sorted(dead):
        print(f"  removed {path.relative_to(ROOT)}: {name}")


def main() -> int:
    total = 0
    for rel, names in REMOVE.items():
        path = ROOT / rel
        if not path.is_file():
            print(f"  MISSING FILE: {rel}", file=sys.stderr)
            MISSING.append(rel)
            continue
        dead = set(names)
        rewrite(path, dead)
        total += len(names)
    print(f"Removed {total} symbols across {len(REMOVE)} files.")
    return 0 if not MISSING else 1


if __name__ == "__main__":
    sys.exit(main())
