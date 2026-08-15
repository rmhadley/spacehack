"""Pygame capture helpers for renderer-neutral world commands.

The game's framebuffers emit renderer-neutral draw commands from ``world.py``.
This module provides the capture console used to snapshot existing cell
renderers for native Pygame painting (quest log, combat, exploration HUD) and
the command normalizer shared by those capture paths.
"""
from __future__ import annotations

from typing import Any

from . import world
from .framebuffer import FrameBuffer


class CaptureConsole(FrameBuffer):
    """FrameBuffer compatibility name for existing capture callers."""


def _command_from_data(data: Any) -> world.WorldDrawCommand:
    """Normalize one renderer-neutral command from an object or mapping."""
    if isinstance(data, dict):
        return world.WorldDrawCommand(
            x=int(data["x"]),
            y=int(data["y"]),
            char=str(data["char"]),
            fg=tuple(data["fg"]),
            bg=None if data.get("bg") is None else tuple(data["bg"]),
        )
    return world.WorldDrawCommand(
        x=int(data.x),
        y=int(data.y),
        char=str(data.char),
        fg=tuple(int(value) for value in data.fg),
        bg=None if data.bg is None else tuple(int(value) for value in data.bg),
    )
