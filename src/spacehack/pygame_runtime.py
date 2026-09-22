"""Shared Pygame-owned runtime for the complete game flow.

The game uses project-owned framebuffers during the Phase 2 migration.
Input is fully project-owned in this phase: the runtime
polls Pygame and returns :class:`pygame_engine.PygameInputEvent` values without
patching a foreign event queue.
"""
from __future__ import annotations

import asyncio
import time
from pathlib import Path
from typing import TYPE_CHECKING, Any
from dataclasses import replace

from . import animation_timing, pygame_engine
from .display_config import (
    DisplayConfig,
    load_display_config,
    save_display_config,
)
from .engine import SCREEN_HEIGHT, SCREEN_WIDTH, TILE_HEIGHT, TILE_WIDTH
from .framebuffer import FrameBuffer

if TYPE_CHECKING:
    from .game_context import GameContext


def is_shared_context(context: PygameContext) -> bool:
    """Return whether ``context`` belongs to the active shared runtime."""
    runtime = getattr(context, "_runtime", None)
    return getattr(runtime, "engine", None) is not None


def _inherited_backgrounds(commands: tuple[Any, ...]) -> dict[tuple[int, int], Any]:
    """Return explicit cell backgrounds available to later glyph commands."""
    return {
        (int(command.x), int(command.y)): command.bg
        for command in commands
        if command.bg is not None
    }


def _paint_world_commands(engine, commands: tuple[Any, ...]) -> None:
    """Paint map commands, restoring terrain underlays beneath entities."""
    inherited = _inherited_backgrounds(commands)
    for command in commands:
        background = command.bg
        if background is None:
            background = inherited.get((command.x, command.y))
        if command.preserve_underlay and command.underlay_char is not None:
            engine.glyphs.blit(
                engine.logical_surface, command.underlay_char,
                int(command.x) * engine.glyphs.tile_width,
                int(command.y) * engine.glyphs.tile_height,
                fg=tuple(command.underlay_fg or (255, 255, 255)),
                bg=command.underlay_bg,
            )
            background = None
        elif command.preserve_underlay:
            background = None
        engine.glyphs.blit(
            engine.logical_surface, command.char,
            int(command.x) * engine.glyphs.tile_width,
            int(command.y) * engine.glyphs.tile_height,
            fg=tuple(command.fg), bg=background,
            bold=bool(getattr(command, "bold", False)),
        )


def _drain_sdl_batch(
    pygame: Any, held: set[str],
) -> tuple[pygame_engine.PygameInputEvent, ...]:
    """Drain the SDL queue once, stamping repeats and dropping irrelevant events.

    pygame-ce never exposes SDL's repeat flag on KEYDOWN events (its
    own ``set_repeat`` timer posts plain keydowns), so the runtime
    derives it: a keydown for a key already in ``held`` — keydown
    seen, no keyup since — is a repeat. ``held`` is updated in place;
    every SDL drain must flow through this stamping or its keyups go
    stale and the next real press misreads as a repeat.
    """
    batch = []
    for event in pygame.event.get():
        translated = pygame_engine.translate_event(pygame, event)
        if translated.kind == "other":
            continue
        batch.append(_stamp_held_state(translated, held))
    return tuple(batch)


def _stamp_held_state(
    event: pygame_engine.PygameInputEvent, held: set[str],
) -> pygame_engine.PygameInputEvent:
    """Return the event with its repeat flag derived from ``held``."""
    if event.kind == "keydown":
        repeated = event.key_name in held
        held.add(event.key_name)
        return replace(event, repeat=True) if repeated else event
    if event.kind == "keyup":
        held.discard(event.key_name)
    return event


def _drop_released_repeats(
    batch: tuple[pygame_engine.PygameInputEvent, ...],
) -> tuple[pygame_engine.PygameInputEvent, ...]:
    """Drop repeat keydowns whose key is released later in the same batch.

    The repeat timer emits keydowns only while the key is held and
    every poll drains the full queue, so a stale repeat can only ever
    coexist with its keyup inside one batch. Taps (non-repeat presses)
    keep their press.
    """
    released = {event.key_name for event in batch if event.kind == "keyup"}
    return tuple(
        event for event in batch
        if not (
            event.kind == "keydown"
            and event.repeat
            and event.key_name in released
        )
    )


class PygameContext:
    """Project-owned presentation context backed by the shared Pygame runtime."""

    def __init__(self, runtime: "PygameRuntime"):
        self._runtime = runtime
        # Monotonic frame clock for time-varying presentation effects
        # (see :mod:`spacehack.lighting`). Presentation-only state: it
        # is never serialised and resets to 0 on load. Advanced once
        # per presented frame in :meth:`present`.
        self._frame_clock: int = 0

    @property
    def frame_clock(self) -> int:
        """The current frame clock value for time-varying rendering."""
        return self._frame_clock

    def present(self, console: FrameBuffer, *, overlay: Any | None = None) -> None:
        """Paint one console and optional native text overlay into Pygame.

        Advances the frame clock once per presented frame so time-varying
        effects (flickering neon, river currents) read the next ``t`` value
        on the next render.
        """
        if overlay is None:
            self._runtime.present(console)
        else:
            self._runtime.present(console, overlay=overlay)
        self._frame_clock += 1

    def events(self) -> tuple[pygame_engine.PygameInputEvent, ...]:
        """Poll all currently queued project-owned input events."""
        return self._runtime.events()

    def note_drained(self, raw_events: tuple[Any, ...]) -> None:
        """Keep held-key state accurate when a loop drains SDL directly."""
        self._runtime.note_drained(raw_events)

    async def wait_events(
        self, *, timeout_ms: int | None = None,
    ) -> tuple[pygame_engine.PygameInputEvent, ...]:
        """Yield to the host until relevant input events arrive, or time out.

        ``timeout_ms=None`` (the default) parks until an event arrives.
        A finite timeout polls for input and returns an empty
        tuple when no event arrives in time, so the caller can redraw
        time-varying effects (flickering neon) while the player is idle.
        """
        return await self._runtime.wait_events(timeout_ms=timeout_ms)

    async def pump(self, seconds: float = 0.0) -> None:
        """Yield once to the host event loop, pausing ``seconds``.

        The single cooperative yield point for frame loops: under wasm
        the full JS-stack return is what lets SDL commit the presented
        frame and deliver input (doc 46); on desktop it is a plain
        asyncio sleep.
        """
        await asyncio.sleep(seconds)

    @property
    def display_config(self) -> DisplayConfig:
        """Return the active user-facing display preferences."""
        return self._runtime.display_config

    def apply_display_config(self, config: DisplayConfig) -> None:
        """Apply display preferences through the active engine."""
        self._runtime.apply_display_config(config)

    def save_display_config(self) -> None:
        """Persist the active display preferences outside save-game state."""
        self._runtime.save_display_config()

def _physical_overlay_callback(
    engine: pygame_engine.PygameEngine,
    overlay: Any,
):
    """Build a callback that paints HUD/log text after logical scaling."""
    columns = engine.config.logical_width // TILE_WIDTH
    rows = engine.config.logical_height // TILE_HEIGHT

    def _draw(
        pygame: Any,
        window: Any,
        viewport: pygame_engine.Viewport,
    ) -> None:
        """Paint the overlay using the viewport's physical cell dimensions."""
        cell_width = max(1, viewport.width // columns)
        cell_height = max(1, viewport.height // rows)
        from . import pygame_overlay
        pygame_overlay.draw_panels(
            pygame,
            window,
            overlay,
            logical_width=viewport.width,
            logical_height=viewport.height,
            tile_width=cell_width,
            tile_height=cell_height,
            origin_x=viewport.x,
            origin_y=viewport.y,
        )

    return _draw


class PygameRuntime:
    """Own the single Pygame engine for the whole game."""

    def __init__(
        self,
        tileset: Any,
        display_config: DisplayConfig | None = None,
        config_path: Path | None = None,
    ):
        self.tileset = tileset
        self._display_config = display_config or DisplayConfig()
        self.config_path = config_path
        self.engine: pygame_engine.PygameEngine | None = None
        self.game_context: "GameContext | None" = None
        # Keys whose keydown was drained without a keyup since — the
        # basis for stamping repeat keydowns (pygame hides SDL's flag).
        self._held_keys: set[str] = set()
        self.context = PygameContext(self)

    @property
    def display_config(self) -> DisplayConfig:
        """Return the engine's current display preferences.

        The engine only knows windowing; the runtime stitches the
        animation speed back in so the preference round-trips.
        """
        if self.engine is not None:
            return replace(
                self.engine.display_config,
                animation_speed=self._display_config.animation_speed,
            )
        return self._display_config

    def apply_display_config(self, config: DisplayConfig) -> None:
        """Apply preferences: windowing to the engine, pacing to timing."""
        if self.engine is None:
            raise RuntimeError("PygameRuntime must be open before applying display config")
        self.engine.apply_display_config(config)
        self._display_config = replace(
            self.engine.display_config, animation_speed=config.animation_speed
        )
        animation_timing.set_speed_scale(self._display_config.animation_speed)

    def save_display_config(self) -> None:
        """Persist the current display preference to the user config."""
        save_display_config(self.display_config, self.config_path)

    def __enter__(self) -> PygameContext:
        """Open the shared window without modifying global event functions."""
        pygame = pygame_engine._load_pygame()
        try:
            self.engine = pygame_engine.PygameEngine(
                pygame,
                pygame_engine.PygameEngineConfig(
                    logical_width=SCREEN_WIDTH * TILE_WIDTH,
                    logical_height=SCREEN_HEIGHT * TILE_HEIGHT,
                    window_width=self._display_config.window_width,
                    window_height=self._display_config.window_height,
                    fullscreen=self._display_config.fullscreen,
                ),
                tileset=self.tileset,
            )
            self.engine.open()
        except Exception:
            self.close()
            raise
        animation_timing.set_speed_scale(self._display_config.animation_speed)
        return self.context

    def __exit__(self, exc_type, exc_value, traceback) -> None:
        """Close the shared window."""
        self.close()

    def events(self) -> tuple[pygame_engine.PygameInputEvent, ...]:
        """Poll Pygame once, stamping repeats, and return input events."""
        if self.engine is None:
            return ()
        return tuple(
            _stamp_held_state(event, self._held_keys)
            for event in self.engine.events()
        )

    def note_drained(self, raw_events: tuple[Any, ...]) -> None:
        """Update held-key state from raw SDL events drained elsewhere.

        Animation loops drain SDL directly to stay responsive; without
        this call their swallowed keyups would leave keys stuck in
        ``_held_keys`` and the next real press would misread as a
        repeat. The events themselves stay consumed by the drainer.
        """
        if self.engine is None:
            return
        pygame = self.engine.pygame
        for event in raw_events:
            translated = pygame_engine.translate_event(pygame, event)
            if translated.kind in ("keydown", "keyup"):
                _stamp_held_state(translated, self._held_keys)

    async def wait_events(
        self, *, timeout_ms: int | None = None,
    ) -> tuple[pygame_engine.PygameInputEvent, ...]:
        """Yield until relevant events arrive, or time out.

        ``timeout_ms=None`` (the default) parks until a relevant event arrives; a
        finite timeout polls every frame quantum and returns ``()``
        when no relevant event arrives in time, so the caller can
        redraw idle animations. Polling (never blocking) keeps the
        host event loop running, which wasm presentation requires.

        ``pygame.event.get()`` drains the whole SDL queue per poll and
        the batch is returned whole: nothing is retained between
        calls, so events can never leak from one screen into the next
        (the stale keypresses after modals, doc 46). Repeats are
        stamped by keydown/keyup pairing (pygame hides SDL's repeat
        flag) and a keyup drops earlier repeat keydowns of the same
        key within its batch — repeats queued while a frame ran long
        are stale the moment the key is released (the doc 46 held-key
        momentum fix); taps keep their press.
        """
        if self.engine is None:
            return ()
        pygame = self.engine.pygame
        quantum = 0.016
        deadline = None if timeout_ms is None else (
            time.monotonic() + timeout_ms / 1000.0
        )
        while True:
            batch = _drain_sdl_batch(pygame, self._held_keys)
            if batch:
                return _drop_released_repeats(batch)
            if deadline is not None and time.monotonic() >= deadline:
                return ()
            await asyncio.sleep(quantum)

    def present(self, console: FrameBuffer, *, overlay: Any | None = None) -> None:
        """Render a console, then an optional native Pygame overlay."""
        if self.engine is None or self.engine.logical_surface is None or self.engine.glyphs is None:
            raise RuntimeError("Pygame runtime is not open")
        self.engine.clear(console.default_background() or (0, 0, 0))
        _paint_world_commands(self.engine, console.to_commands())
        if overlay is None:
            self.engine.present()
            return

        from . import pygame_overlay
        pygame_overlay.draw_map_effects(
            self.engine.pygame,
            self.engine.logical_surface,
            overlay,
            logical_width=self.engine.config.logical_width,
            logical_height=self.engine.config.logical_height,
        )
        self.engine.present(
            physical_overlay=_physical_overlay_callback(self.engine, overlay),
        )

    def close(self) -> None:
        """Release Pygame resources idempotently."""
        if self.engine is not None:
            self.engine.close()
            self.engine = None


class GameRuntime:
    """Own the mandatory shared Pygame runtime for the complete game."""

    def __init__(
        self,
        tileset: Any,
        display_config: DisplayConfig | None = None,
        config_path: Path | None = None,
    ):
        self.tileset = tileset
        self.display_config = display_config
        self.config_path = config_path
        self._pygame: PygameRuntime | None = None

    def __enter__(self) -> PygameContext:
        """Open the mandatory Pygame runtime."""
        _kwargs: dict[str, Any] = {}
        if self.display_config is not None:
            _kwargs["display_config"] = self.display_config
        if self.config_path is not None:
            _kwargs["config_path"] = self.config_path
        self._pygame = PygameRuntime(self.tileset, **_kwargs)
        return self._pygame.__enter__()

    def __exit__(self, exc_type, exc_value, traceback) -> None:
        """Close whichever renderer was selected."""
        if self._pygame is not None:
            self._pygame.__exit__(exc_type, exc_value, traceback)
            self._pygame = None


def open_runtime(
    tileset: Any,
    *,
    display_config: DisplayConfig | None = None,
    config_path: Path | None = None,
) -> GameRuntime:
    """Return the mandatory full-game Pygame runtime."""
    return GameRuntime(
        tileset,
        display_config=display_config or load_display_config(config_path),
        config_path=config_path,
    )
