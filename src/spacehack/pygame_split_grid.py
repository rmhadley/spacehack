"""The split family's grid-pane key table (doc 56 phase 3).

Split from pygame_split to pay the 1000-line ratchet ahead of the
suffix tag column (doc 102 Brief 4.3): the fitting-grid editor's
key mapping is a self-contained concern — arrows plus the vim cross
move the cursor, D/X/ENTER act, TAB surfaces to the host, ESC is
two-stage while the editor holds a part.
"""
from __future__ import annotations

from dataclasses import replace
from typing import Any

from . import pygame_split


def _grid_moves(pygame: Any) -> dict[Any, tuple[int, int]]:
    """The grid cursor's key table: arrows plus the vim cross."""
    return {
        getattr(pygame, name): delta
        for name, delta in (
            ("K_UP", (0, -1)), ("K_DOWN", (0, 1)),
            ("K_LEFT", (-1, 0)), ("K_RIGHT", (1, 0)),
            ("K_k", (0, -1)), ("K_j", (0, 1)),
            ("K_h", (-1, 0)), ("K_l", (1, 0)),
        )
        if getattr(pygame, name, None) is not None
    }


def _handle_grid_key(pygame: Any, event: Any, frame) -> tuple[str, int, int] | None:
    """One key on the focused grid pane (doc 56 phase 3) — a key-table
    GRID:* outcome routed through the host's keep-open apply path, or
    None to fall through to the shared split handling.

    TAB surfaces to the host (today it is swallowed here with a focus
    flip) so the SETTLED-12 auto-return can fire; ESC only becomes
    GRID:ESC while the editor holds a part (two-stage ESC — empty-hand
    ESC still exits through the shared BACK).
    """
    keys = {
        name: getattr(pygame, name, None)
        for name in ("K_RETURN", "K_KP_ENTER", "K_d", "K_x", "K_TAB")
    }
    delta = _grid_moves(pygame).get(event.key)
    if delta is not None:
        return f"GRID:MOVE:{delta[0]}:{delta[1]}", frame.focus, frame.selected
    if event.key in (keys["K_RETURN"], keys["K_KP_ENTER"]):
        return "GRID:ENTER", frame.focus, frame.selected
    if event.key == keys["K_d"]:
        return "GRID:STORE", frame.focus, frame.selected
    if event.key == keys["K_x"]:
        return "GRID:SELL", frame.focus, frame.selected
    if event.key == keys["K_TAB"]:
        # The host resolves any held part, then the pane flips.
        other = replace(frame, focus=0, selected=0)
        return "GRID:TAB", 0, pygame_split._clamp_selected(other)
    if event.key == pygame.K_ESCAPE and frame.grid_holding:
        return "GRID:ESC", frame.focus, frame.selected
    return None
