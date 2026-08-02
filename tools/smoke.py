#!/usr/bin/env python3
"""Smoke test entry points to verify import correctness and signature shapes.

If invoked outside a virtual environment, re-executes via
``.venv/bin/python3`` if available, to avoid spurious
``ModuleNotFoundError: No module named 'tcod'`` failures (the runtime
deps including tcod are installed only in the project venv).

Pass: prints ``PASS: Smoke tests OK.`` and exits 0.
Fail: prints ``FAIL: <reason>`` to stderr and exits 1.

Run from the project root:

    python3 tools/smoke.py

This is the canonical pattern for verifying a refactor preserved
module-level entry points without triggering the tcod-not-installed
false positive that bare ``python3 -c 'import spacehack.combat'``
produces.
"""
import os
import sys
from pathlib import Path


def _ensure_venv() -> None:
    """Re-launch using the project venv if not already running in one.

    Compares ``sys.prefix`` against ``sys.base_prefix`` -- they diverge
    when the interpreter is inside a virtualenv. Bare ``python3`` has
    them equal, so we detect that case and replace the process with
    the venv python via ``os.execv``. If ``.venv/bin/python3`` is
    missing, fail loudly rather than silently re-launching.
    """
    if sys.prefix != sys.base_prefix:
        return
    venv_py = Path(__file__).resolve().parent.parent / ".venv" / "bin" / "python3"
    if venv_py.exists():
        os.execv(str(venv_py), [str(venv_py), __file__, *sys.argv[1:]])
    print(
        "FAIL: smoke test must run from venv; .venv/bin/python3 not found.",
        file=sys.stderr,
    )
    sys.exit(1)


def smoke_test() -> int:
    _ensure_venv()

    # Make src/ importable regardless of cwd.
    root = Path(__file__).resolve().parent.parent
    sys.path.insert(0, str(root))

    try:
        from src.spacehack import (
            character,
            combat,
            game_context,
            hud,
            main_quest,
            message_log,
            mission,
            npc,
            ship,
            solar_system,
            ui,
            world,
        )
    except ModuleNotFoundError as exc:
        print(f"FAIL: import error during smoke test: {exc}", file=sys.stderr)
        return 1

    # Verify key entry points survived their respective refactors.
    checks = [
        (combat, "_handle_combat_encounter"),
        (combat, "run_combat"),
        (game_context, "GameContext"),
        (world, "GameMap"),
        (world, "MOVE_KEYS"),
        (ui, "Modal"),
    ]
    for mod, attr in checks:
        if not hasattr(mod, attr):
            print(f"FAIL: {mod.__name__}.{attr} is missing.", file=sys.stderr)
            return 1

    # Main quest infra (docs/design/in_progress/07_DESIGN_MAIN_QUEST.md):
    # runtime entry points + the data catalog's step chain integrity.
    _mq_checks = [
        (main_quest, "resolve_npc_dialogue"),
        (main_quest, "trigger_dialogue"),
        (main_quest, "quest_option_for"),
        (main_quest, "maybe_trigger_signal"),
        (main_quest, "show_prologue_transmission"),
        (main_quest, "show_sealed_door_overlay"),
        (main_quest, "show_help_offer"),
        (main_quest, "render_help_offer"),
        (main_quest, "mars_exploration_unlocked"),
        (main_quest, "prepare_mars_surface"),
        (main_quest, "bump_mars_door"),
        (main_quest, "current_main_quest_objective"),
    ]
    for mod, attr in _mq_checks:
        if not hasattr(mod, attr):
            print(f"FAIL: main_quest.{attr} is missing.", file=sys.stderr)
            return 1
    # Dataclass fields with default_factory are NOT set as class
    # attributes, so use dataclasses.fields() rather than hasattr.
    import dataclasses as _dc
    _mq_fields = [
        "main_quest_progress",
        "main_quest_unlocked_items",
        "main_quest_path",
        "main_quest_backing",
        "main_quest_complete",
    ]
    _ctx_field_names = {f.name for f in _dc.fields(game_context.GameContext)}
    for _f in _mq_fields:
        if _f not in _ctx_field_names:
            print(
                f"FAIL: GameContext.{_f} is missing (save/load contract).",
                file=sys.stderr,
            )
            return 1
    # Step-chain integrity: every requires_step must exist; every
    # dialogue npc_id must resolve; option rows need trigger_on_talk.
    from src.spacehack.data.main_quest import list_main_quest_steps
    from src.spacehack.data.npcs import find_npc
    _mq_steps = list_main_quest_steps()
    _mq_ids = {s.id for s in _mq_steps}
    if not _mq_steps:
        print("FAIL: main quest catalog is empty.", file=sys.stderr)
        return 1
    for _s in _mq_steps:
        if _s.requires_step and _s.requires_step not in _mq_ids:
            print(
                f"FAIL: main quest step {_s.id!r} requires unknown "
                f"step {_s.requires_step!r}.",
                file=sys.stderr,
            )
            return 1
        for _npc_id, _d in _s.dialogues.items():
            try:
                find_npc(_npc_id)
            except KeyError:
                print(
                    f"FAIL: main quest step {_s.id!r} dialogue references "
                    f"unknown npc {_npc_id!r}.",
                    file=sys.stderr,
                )
                return 1
            if _d.option_label and not _d.trigger_on_talk:
                print(
                    f"FAIL: main quest step {_s.id!r} dialogue for "
                    f"{_npc_id!r} has option_label but no trigger_on_talk.",
                    file=sys.stderr,
                )
                return 1

    # Verify the merged movement table covers vim + arrows + numpad
    # and that each maps to the expected delta.
    _move_checks = {
        "h": (-1, 0), "j": (0, 1), "k": (0, -1), "l": (1, 0),  # vim cardinals
        "y": (-1, -1), "u": (1, -1), "b": (-1, 1), "n": (1, 1),  # vim diagonals
        "up": (0, -1), "down": (0, 1), "left": (-1, 0), "right": (1, 0),  # arrows
        "kp_7": (-1, -1), "kp_8": (0, -1), "kp_9": (1, -1),       # numpad NW/N/NE
        "kp_4": (-1, 0), "kp_6": (1, 0),                            # numpad W/E
        "kp_1": (-1, 1), "kp_2": (0, 1), "kp_3": (1, 1),           # numpad SW/S/SE
    }
    for _key, _expected in _move_checks.items():
        if world.MOVE_KEYS.get(_key) != _expected:
            print(
                f"FAIL: world.MOVE_KEYS[{_key!r}] = "
                f"{world.MOVE_KEYS.get(_key)!r}, expected {_expected!r}.",
                file=sys.stderr,
            )
            return 1

    # Validate the jump-gate graph: every gate's connects_to
    # target must exist and be bidirectional.
    from src.spacehack.data.solar_systems import validate_gate_graph
    gate_errors = validate_gate_graph()
    if gate_errors:
        for err in gate_errors:
            print(f"GATE ERROR: {err}", file=sys.stderr)
        print(
            f"FAIL: {len(gate_errors)} gate graph error(s).",
            file=sys.stderr,
        )
        return 1

    print("PASS: Smoke tests OK.")
    return 0


if __name__ == "__main__":
    sys.exit(smoke_test())
