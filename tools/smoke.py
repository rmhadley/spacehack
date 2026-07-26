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
        (ui, "Modal"),
    ]
    for mod, attr in checks:
        if not hasattr(mod, attr):
            print(f"FAIL: {mod.__name__}.{attr} is missing.", file=sys.stderr)
            return 1

    print("PASS: Smoke tests OK.")
    return 0


if __name__ == "__main__":
    sys.exit(smoke_test())
