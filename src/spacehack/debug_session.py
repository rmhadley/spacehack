"""Headless savegame inspection and deterministic debugging scenarios.

This module is deliberately separate from :mod:`spacehack.saveload`: the
normal save/load path remains the authority for reconstructing a run, while
this module supplies the tooling seams that are useful when diagnosing a
reported save.  A :class:`HeadlessSaveSession` never writes its source save.

Scenario actions are small, explicit tokens:

``move:left`` / ``move:right`` / ``move:up`` / ``move:down``
    Attempt one movement through :func:`spacehack.world.try_move`.
``wait`` or ``tick``
    Run one mode-appropriate simulation turn without moving the player.
``reveal`` or ``reveal:radius``
    Recompute dungeon line of sight.
``explore[:count]``
    Take up to ``count`` existing auto-explore steps.
``goto:x,y``
    Take one existing goto step toward a map coordinate.
``advance:days``
    Advance the shared game clock by an explicit number of days.

The headless runner intentionally does not open combat or modal UI.  It
runs movement, NPC, fog, activation, economy, and clock helpers directly and
records an action result so a bug-specific scenario can stop before the UI
boundary and inspect state precisely.
"""

from __future__ import annotations

import argparse
import contextlib
import copy
import hashlib
import json
import sys
import threading
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterator

from . import autoexplore, dungeon, dungeon_extensions, ground_npcs, npc_ships
from . import saveload, solar_system, time, world
from .game_context import GameContext


_SAVELOAD_PATH_LOCK = threading.RLock()


_DIRECTION_DELTAS: dict[str, tuple[int, int]] = {
    "up": (0, -1),
    "down": (0, 1),
    "left": (-1, 0),
    "right": (1, 0),
    "upleft": (-1, -1),
    "upright": (1, -1),
    "downleft": (-1, 1),
    "downright": (1, 1),
    "north": (0, -1),
    "south": (0, 1),
    "west": (-1, 0),
    "east": (1, 0),
    "nw": (-1, -1),
    "ne": (1, -1),
    "sw": (-1, 1),
    "se": (1, 1),
    "h": (-1, 0),
    "j": (0, 1),
    "k": (0, -1),
    "l": (1, 0),
    "y": (-1, -1),
    "u": (1, -1),
    "b": (-1, 1),
    "n": (1, 1),
}


class SaveSessionError(RuntimeError):
    """A user-facing failure while opening or inspecting a save."""


@dataclass
class HeadlessPygameContext:
    """Minimal presentation boundary accepted by :func:`saveload.load_game`.

    Loading does not need SDL, an event queue, or a display.  Keeping this
    adapter explicit makes accidental presentation calls visible in a debug
    scenario instead of silently opening a window.
    """

    presented_frames: int = 0
    _runtime: None = None

    def present(self, *_args: Any, **_kwargs: Any) -> None:
        """Count a presentation request without creating a display."""
        self.presented_frames += 1

    def events(self) -> tuple[()]:
        """Return no queued input events."""
        return ()

    def wait_events(self) -> tuple[()]:
        """Return no events; headless scenarios are script-driven."""
        return ()


@dataclass(frozen=True)
class ValidationReport:
    """Structural and post-load diagnostics for one save file."""

    path: str
    errors: tuple[str, ...] = ()
    warnings: tuple[str, ...] = ()

    @property
    def valid(self) -> bool:
        """Whether the save passed all blocking checks."""
        return not self.errors

    def as_dict(self) -> dict[str, Any]:
        """Return a stable JSON-friendly report."""
        return {
            "path": self.path,
            "valid": self.valid,
            "errors": list(self.errors),
            "warnings": list(self.warnings),
        }


@dataclass
class HeadlessSaveSession:
    """A loaded, mutable-in-memory, read-only savegame debugging session."""

    source_path: Path
    ctx: GameContext
    raw_data: dict[str, Any]
    context: HeadlessPygameContext = field(repr=False)

    @classmethod
    def load(cls, path: str | Path) -> "HeadlessSaveSession":
        """Load *path* through the production deserializer without writing it."""
        source_path = Path(path).expanduser().resolve()
        raw_data = _read_save(source_path)
        context = HeadlessPygameContext()
        try:
            with _temporary_autosave_path(source_path):
                loaded = saveload.load_game(context)  # type: ignore[arg-type]
        except Exception as exc:
            raise SaveSessionError(f"could not load {source_path}: {exc}") from exc
        if loaded is None:
            raise SaveSessionError(f"could not load {source_path}: the save is missing or invalid")
        return cls(source_path, loaded, raw_data, context)

    @property
    def mode(self) -> str:
        """Return the mode restored by the production loader."""
        return str(getattr(self.ctx, "_loaded_mode", self.raw_data.get("current_mode", "city")))

    def summary(self) -> dict[str, Any]:
        """Return concise mode-aware diagnostics for a loaded session."""
        return _summary(self.ctx, self.raw_data, self.source_path, self.mode)

    def validate(self) -> ValidationReport:
        """Validate raw save structure and the reconstructed context."""
        return _validate_loaded(self.source_path, self.raw_data, self.ctx, self.mode)

    def snapshot(self) -> dict[str, Any]:
        """Return a stable JSON-safe snapshot suitable for before/after diffing."""
        return _snapshot(self.ctx, self.raw_data, self.source_path, self.mode)

    def run(self, actions: list[str]) -> list[dict[str, Any]]:
        """Execute actions, stopping when an unsupported combat UI is pending."""
        results = []
        for action in actions:
            result = _execute_action(self, action)
            results.append(result)
            if result.get("result") == "combat_pending":
                break
        return results


@contextlib.contextmanager
def _temporary_autosave_path(path: Path) -> Iterator[None]:
    """Redirect one synchronous load while serializing in-process callers."""
    with _SAVELOAD_PATH_LOCK:
        original = saveload._autosave_path
        saveload._autosave_path = lambda: path
        try:
            yield
        finally:
            saveload._autosave_path = original


def _read_save(path: Path) -> dict[str, Any]:
    """Read one JSON object, converting file errors into tool errors."""
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise SaveSessionError(f"save not found: {path}") from exc
    except (OSError, json.JSONDecodeError) as exc:
        raise SaveSessionError(f"could not read {path}: {exc}") from exc
    if not isinstance(raw, dict):
        raise SaveSessionError(f"could not load {path}: top-level JSON value is not an object")
    return raw


def _summary(
    ctx: GameContext,
    raw_data: dict[str, Any],
    path: Path,
    mode: str,
) -> dict[str, Any]:
    """Build a concise summary from restored state and save metadata."""
    entities = [entity for entity in ctx.game_map.entities if entity is not ctx.player]
    npc_entities = [entity for entity in entities if entity.npc_char_id or entity.npc_ship_id]
    loot = [entity for entity in entities if entity.loot_data is not None]
    seen = _seen_count(ctx.game_map)
    return {
        "source": str(path),
        "source_sha256": _file_sha256(path),
        "mode": mode,
        "city": ctx.current_city_id,
        "system": raw_data.get("current_system_id", "sol"),
        "player": {"x": ctx.player.pos.x, "y": ctx.player.pos.y},
        "map": {"width": ctx.game_map.width, "height": ctx.game_map.height},
        "seen_cells": seen,
        "entities": len(entities),
        "npc_entities": len(npc_entities),
        "loot": len(loot),
        "active_missions": len(ctx.player_active_missions),
        "ship": None if ctx.player_owned_ship is None else ctx.player_owned_ship.ship_id,
        "hull_damage_pct": (
            None if ctx.player_owned_ship is None
            else ctx.player_owned_ship.hull_damage_pct
        ),
        "hp": ctx.stats.hp,
        "credits": ctx.stats.credits,
        "date": {
            "day": ctx.time_day,
            "month": ctx.time_month,
            "year": ctx.time_year,
        },
        "rng_restored": "rng_state" in raw_data,
    }


def _validate_loaded(
    path: Path,
    raw_data: dict[str, Any],
    ctx: GameContext,
    mode: str,
) -> ValidationReport:
    """Validate raw metadata and restored map invariants."""
    metadata_errors, metadata_warnings = _validate_metadata(raw_data, ctx, mode)
    map_errors, map_warnings = _validate_map(ctx, raw_data, mode)
    return ValidationReport(
        str(path),
        tuple(metadata_errors + map_errors),
        tuple(metadata_warnings + map_warnings),
    )


def _validate_metadata(
    raw_data: dict[str, Any],
    ctx: GameContext,
    mode: str,
) -> tuple[list[str], list[str]]:
    """Validate required fields and loader normalization."""
    errors: list[str] = []
    warnings: list[str] = []
    required = ("character_info", "stats", "current_mode", "current_city_id", "current_system_id")
    errors.extend(f"missing required field: {key}" for key in required if key not in raw_data)
    raw_mode = raw_data.get("current_mode")
    if raw_mode not in {"city", "space", "dungeon"}:
        errors.append(f"unknown current_mode: {raw_mode!r}")
    elif raw_mode != mode:
        errors.append(f"loader restored mode {mode!r} from save declaring {raw_mode!r}")
    restored_system = solar_system.current_solar_system_id
    raw_system = raw_data.get("current_system_id")
    if raw_system != restored_system:
        errors.append(
            f"loader restored system {restored_system!r} from save declaring {raw_system!r}"
        )
    raw_city = raw_data.get("current_city_id")
    if raw_city != ctx.current_city_id:
        errors.append(
            f"loader restored city {ctx.current_city_id!r} from save declaring {raw_city!r}"
        )
    if "rng_state" not in raw_data:
        warnings.append("save has no rng_state; future random outcomes cannot be reproduced exactly")
    return errors, warnings


def _validate_map(
    ctx: GameContext,
    raw_data: dict[str, Any],
    mode: str,
) -> tuple[list[str], list[str]]:
    """Validate restored map dimensions, positions, and dungeon metadata."""
    errors: list[str] = []
    warnings: list[str] = []
    if len(ctx.game_map.tiles) != ctx.game_map.height:
        errors.append("restored map row count does not match map height")
    for row in ctx.game_map.tiles:
        if len(row) != ctx.game_map.width:
            errors.append("restored map column count does not match map width")
            break
    if not ctx.game_map.in_bounds(ctx.player.pos.x, ctx.player.pos.y):
        errors.append(
            f"player position is outside restored map: ({ctx.player.pos.x}, {ctx.player.pos.y})"
        )
    for entity in ctx.game_map.entities:
        if not ctx.game_map.in_bounds(entity.pos.x, entity.pos.y):
            errors.append(f"entity {entity.name!r} is outside restored map")
    if mode == "dungeon":
        dungeon_data = raw_data.get("dungeon")
        if not isinstance(dungeon_data, dict):
            errors.append("dungeon mode has no dungeon object")
        elif not isinstance(dungeon_data.get("seen"), list):
            warnings.append("dungeon has no permanent seen grid")
    return errors, warnings


def _snapshot(
    ctx: GameContext,
    raw_data: dict[str, Any],
    path: Path,
    mode: str,
) -> dict[str, Any]:
    """Create a canonical diagnostic snapshot without runtime objects."""
    return {
        "snapshot_version": 1,
        "source": str(path),
        "mode": mode,
        "city": ctx.current_city_id,
        "system": raw_data.get("current_system_id", "sol"),
        "player": {"x": ctx.player.pos.x, "y": ctx.player.pos.y},
        "map": {
            "width": ctx.game_map.width,
            "height": ctx.game_map.height,
            "seen_cells": _seen_count(ctx.game_map),
        },
        "entities": _snapshot_entities(ctx.game_map),
        "missions": sorted(
            str(mission.mission_id) for mission in ctx.player_active_missions
        ),
        "stats": {
            "hp": ctx.stats.hp,
            "credits": ctx.stats.credits,
        },
        "date": [ctx.time_day, ctx.time_month, ctx.time_year],
        "move_counter": ctx.move_counter,
    }


def _snapshot_entities(game_map: world.GameMap) -> list[dict[str, Any]]:
    """Return stable entity records for a diagnostic snapshot."""
    entities = [
        {
            "char": entity.char,
            "name": entity.name,
            "x": entity.pos.x,
            "y": entity.pos.y,
            "npc_char_id": entity.npc_char_id,
            "npc_ship_id": entity.npc_ship_id,
            "squad_id": entity.squad_id,
            "loot_data": copy.deepcopy(entity.loot_data),
            "hp": entity.hp,
        }
        for entity in game_map.entities
    ]
    return sorted(
        entities,
        key=lambda item: (item["y"], item["x"], item["char"], item["name"]),
    )


def _seen_count(game_map: world.GameMap) -> int | None:
    """Count permanent fog memory cells, or return None for no-fog maps."""
    if game_map.seen is None:
        return None
    return sum(sum(bool(cell) for cell in row) for row in game_map.seen)


def _file_sha256(path: Path) -> str:
    """Return a content hash for identifying the inspected source save."""
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _execute_action(session: HeadlessSaveSession, token: str) -> dict[str, Any]:
    """Execute one scenario token through existing game helpers."""
    name, _, argument = token.partition(":")
    handler = _ACTION_HANDLERS.get(name.strip().lower())
    if handler is None:
        raise SaveSessionError(
            f"unknown action {token!r}; use move, wait, tick, reveal, explore, goto, or advance"
        )
    return handler(session, token, argument.strip())


def _action_move(session: HeadlessSaveSession, _token: str, argument: str) -> dict[str, Any]:
    """Dispatch a directional movement action."""
    return _move(session, argument)


def _action_tick(session: HeadlessSaveSession, token: str, _argument: str) -> dict[str, Any]:
    """Dispatch a wait/tick action."""
    result = _tick(session)
    return {"action": token, "result": "combat_pending" if result else "ticked"}


def _action_reveal(session: HeadlessSaveSession, token: str, argument: str) -> dict[str, Any]:
    """Dispatch a dungeon reveal action."""
    radius = session.ctx.game_map.sight_radius if not argument else _positive_int(argument, "reveal radius")
    if session.ctx.game_map.seen is None:
        return {"action": token, "result": "not_applicable", "reason": "map has no fog"}
    dungeon.reveal_around(session.ctx.game_map, session.ctx.player.pos, radius=radius)
    return {"action": token, "result": "revealed", "radius": radius}


def _action_explore(session: HeadlessSaveSession, token: str, argument: str) -> dict[str, Any]:
    """Dispatch up to a bounded number of existing auto-explore steps."""
    _require_dungeon(session)
    count = 1 if not argument else _positive_int(argument, "explore count")
    steps = 0
    for _ in range(count):
        delta = autoexplore.next_explore_step(session.ctx.game_map, session.ctx.player.pos)
        if delta is None:
            break
        combat_pending = _apply_dungeon_step(session, delta)
        steps += 1
        if combat_pending:
            return {"action": token, "result": "combat_pending", "steps": steps}
    return {"action": token, "result": "explored", "steps": steps}


def _action_goto(session: HeadlessSaveSession, token: str, argument: str) -> dict[str, Any]:
    """Dispatch one existing auto-goto step."""
    _require_dungeon(session)
    target = _parse_coordinate(argument)
    delta = autoexplore.next_goto_step(session.ctx.game_map, session.ctx.player.pos, *target)
    if delta is None:
        return {"action": token, "result": "unreachable", "target": list(target)}
    combat_pending = _apply_dungeon_step(session, delta)
    return {
        "action": token,
        "result": "combat_pending" if combat_pending else "moved",
        "delta": list(delta),
        "target": list(target),
    }


def _action_advance(session: HeadlessSaveSession, token: str, argument: str) -> dict[str, Any]:
    """Dispatch an explicit shared-clock advance."""
    days = _positive_int(argument, "advance days")
    time.advance_time(session.ctx, days)
    return {"action": token, "result": "advanced", "days": days}


def _require_dungeon(session: HeadlessSaveSession) -> None:
    """Reject dungeon-only actions on city or space saves."""
    if session.mode != "dungeon":
        raise SaveSessionError("explore and goto actions require a dungeon save")


_ACTION_HANDLERS = {
    "move": _action_move,
    "wait": _action_tick,
    "tick": _action_tick,
    "reveal": _action_reveal,
    "explore": _action_explore,
    "goto": _action_goto,
    "advance": _action_advance,
}


def _move(session: HeadlessSaveSession, direction: str) -> dict[str, Any]:
    """Attempt movement and run non-visual mode updates."""
    try:
        dx, dy = _DIRECTION_DELTAS[direction.lower()]
    except KeyError as exc:
        raise SaveSessionError(f"unknown movement direction: {direction!r}") from exc
    before = session.ctx.player.pos
    if session.mode == "space" and _space_combat_pending(session):
        return _movement_result(direction, "combat_pending", before, before, None)
    code, blocker = world.try_move(session.ctx.player, session.ctx.game_map, dx, dy)
    combat_pending = code == "moved" and _post_player_step(session)
    return _movement_result(
        direction,
        "combat_pending" if combat_pending else code,
        before,
        session.ctx.player.pos,
        blocker,
    )


def _movement_result(
    direction: str,
    result: str,
    before: world.Position,
    after: world.Position,
    blocker: object | None,
) -> dict[str, Any]:
    """Build a stable movement action result."""
    return {
        "action": f"move:{direction}",
        "result": result,
        "from": [before.x, before.y],
        "to": [after.x, after.y],
        "blocker": None if blocker is None else getattr(blocker, "name", getattr(blocker, "kind", "?")),
    }


def _tick(session: HeadlessSaveSession) -> bool:
    """Run one non-visual simulation turn and report pending combat."""
    return _run_turn(session)


def _post_player_step(session: HeadlessSaveSession) -> bool:
    """Apply non-visual updates and report pending combat."""
    return _run_turn(session, notify_city=True)


def _run_turn(session: HeadlessSaveSession, *, notify_city: bool = False) -> bool:
    """Run the mode's turn ordering, preserving the UI loop semantics."""
    handler = _TURN_HANDLERS.get(session.mode)
    if handler is not None:
        return handler(session)
    if notify_city:
        from . import tutorial
        tutorial.notify_move(session.ctx)
    return False


def _run_space_turn(session: HeadlessSaveSession) -> bool:
    """Check existing space combat before moving NPCs and time."""
    if _space_combat_pending(session):
        return True
    npc_ships.move_npcs(session.ctx, session.ctx.game_map)
    time.tick_move(session.ctx)
    return False


def _run_dungeon_turn(session: HeadlessSaveSession) -> bool:
    """Move dungeon NPCs, refresh LOS, then gate activation on combat."""
    game_map = session.ctx.game_map
    ground_npcs.move_ground_npcs(session.ctx, game_map)
    dungeon.reveal_around(game_map, session.ctx.player.pos, radius=game_map.sight_radius)
    if _ground_combat_pending(session):
        return True
    dungeon_extensions.tick_activation(session.ctx)
    return False


def _space_combat_pending(session: HeadlessSaveSession) -> bool:
    """Query the existing space encounter detector without opening combat."""
    from . import navigation
    return navigation._detect_combat_encounter(
        session.ctx,
        session.ctx.player.pos,
        solar_system.current_system(),
    ) is not None


def _ground_combat_pending(session: HeadlessSaveSession) -> bool:
    """Query the existing ground LOS detector without opening combat."""
    from .combat._encounter import detect_ground_combat
    return bool(detect_ground_combat(
        session.ctx,
        session.ctx.game_map,
        session.ctx.player.pos,
    ))


_TURN_HANDLERS = {
    "space": _run_space_turn,
    "dungeon": _run_dungeon_turn,
}


def _apply_dungeon_step(session: HeadlessSaveSession, delta: tuple[int, int]) -> bool:
    """Move one dungeon step and run its production post-step ordering."""
    if session.mode != "dungeon":
        raise SaveSessionError("explore and goto actions require a dungeon save")
    code, _ = world.try_move(session.ctx.player, session.ctx.game_map, *delta)
    if code != "moved":
        raise SaveSessionError(f"planned dungeon step was blocked: {code}")
    return _run_dungeon_turn(session)


def _positive_int(raw: str, label: str) -> int:
    """Parse a positive integer action argument."""
    try:
        value = int(raw)
    except ValueError as exc:
        raise SaveSessionError(f"{label} must be a positive integer") from exc
    if value <= 0:
        raise SaveSessionError(f"{label} must be a positive integer")
    return value


def _parse_coordinate(raw: str) -> tuple[int, int]:
    """Parse ``x,y`` for a goto action."""
    parts = raw.split(",")
    if len(parts) != 2:
        raise SaveSessionError("goto target must be written as x,y")
    try:
        return int(parts[0]), int(parts[1])
    except ValueError as exc:
        raise SaveSessionError("goto target must contain integer coordinates") from exc


def snapshot_diff(before: dict[str, Any], after: dict[str, Any]) -> list[dict[str, Any]]:
    """Return stable leaf-level differences between two snapshots."""
    changes: list[dict[str, Any]] = []
    _diff_values(before, after, (), changes)
    return changes


def _diff_values(
    before: Any,
    after: Any,
    path: tuple[str, ...],
    changes: list[dict[str, Any]],
) -> None:
    """Recursively collect changed snapshot leaves."""
    if isinstance(before, dict) and isinstance(after, dict):
        for key in sorted(set(before) | set(after)):
            _diff_values(before.get(key), after.get(key), path + (str(key),), changes)
        return
    if before != after:
        changes.append({"path": ".".join(path), "before": before, "after": after})


def _load_json_or_snapshot(path: Path) -> dict[str, Any]:
    """Load a snapshot JSON directly or derive one from a save JSON."""
    raw = _read_save(path)
    if raw.get("snapshot_version") == 1:
        return raw
    return HeadlessSaveSession.load(path).snapshot()


def validate_path(path: str | Path) -> ValidationReport:
    """Validate a save path without exposing internal tracebacks."""
    source = Path(path).expanduser().resolve()
    try:
        raw_data = _read_save(source)
    except SaveSessionError as exc:
        return ValidationReport(str(source), (str(exc),))
    missing = tuple(
        f"missing required field: {key}"
        for key in ("character_info", "stats", "current_mode", "current_city_id", "current_system_id")
        if key not in raw_data
    )
    if missing:
        return ValidationReport(str(source), missing)
    if raw_data.get("current_mode") == "dungeon" and not isinstance(raw_data.get("dungeon"), dict):
        return ValidationReport(str(source), ("dungeon mode has no dungeon object",))
    try:
        session = HeadlessSaveSession.load(source)
    except SaveSessionError as exc:
        return ValidationReport(str(source), (str(exc),))
    return session.validate()


def _print_json(value: Any) -> None:
    """Print stable, human-readable JSON."""
    print(json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False))


def _build_parser() -> argparse.ArgumentParser:
    """Build the command-line parser used by ``tools/save_debug.py``."""
    parser = argparse.ArgumentParser(description="Inspect and simulate a spacehack save headlessly.")
    sub = parser.add_subparsers(dest="command", required=True)
    for command in ("summary", "validate", "snapshot"):
        child = sub.add_parser(command)
        child.add_argument("save", type=Path)
        if command == "snapshot":
            child.add_argument("--out", type=Path)
    simulate = sub.add_parser("simulate")
    simulate.add_argument("save", type=Path)
    simulate.add_argument("actions", nargs="+", help="scenario tokens such as move:left or wait")
    simulate.add_argument("--snapshot-out", type=Path)
    diff = sub.add_parser("diff")
    diff.add_argument("before", type=Path)
    diff.add_argument("after", type=Path)
    return parser


def main(argv: list[str] | None = None) -> int:
    """Run the save-debug CLI and return a process status code."""
    args = _build_parser().parse_args(argv)
    try:
        if args.command == "summary":
            _print_json(HeadlessSaveSession.load(args.save).summary())
        elif args.command == "validate":
            report = validate_path(args.save)
            _print_json(report.as_dict())
            return 0 if report.valid else 1
        elif args.command == "snapshot":
            session = HeadlessSaveSession.load(args.save)
            _write_or_print(session.snapshot(), args.out, protected_path=session.source_path)
        elif args.command == "simulate":
            session = HeadlessSaveSession.load(args.save)
            before = session.snapshot()
            result = {"actions": session.run(args.actions), "before": before, "after": session.snapshot()}
            if args.snapshot_out is not None:
                _write_or_print(result, args.snapshot_out, protected_path=session.source_path)
            else:
                _print_json(result)
        else:
            value = snapshot_diff(
                _load_json_or_snapshot(args.before),
                _load_json_or_snapshot(args.after),
            )
            _print_json(value)
    except (OSError, SaveSessionError) as exc:
        print(f"save-debug: {exc}", file=sys.stderr)
        return 1
    return 0


def _write_or_print(
    value: Any,
    output: Path | None,
    *,
    protected_path: Path | None = None,
) -> None:
    """Write JSON, refusing to overwrite the inspected source save."""
    text = json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False) + "\n"
    if output is None:
        print(text, end="")
        return
    if protected_path is not None and output.expanduser().resolve() == protected_path.resolve():
        raise SaveSessionError("output path must differ from the inspected save")
    output.write_text(text, encoding="utf-8")
    print(output)
