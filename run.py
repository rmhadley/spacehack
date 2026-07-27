#!/usr/bin/env python3
"""One-command launcher: installs spacehack if needed, then runs it.

Place this file alongside ``spacehack-*.whl`` in the same directory.
The ``.bat`` / ``.command`` / shell wrappers in the dist package all
call this script.
"""
import importlib
import subprocess
import sys
from pathlib import Path


def _find_wheel() -> Path | None:
    """Return the first ``spacehack-*.whl`` in this script's directory."""
    here = Path(__file__).resolve().parent
    for f in sorted(here.glob("spacehack-*.whl")):
        return f
    return None


def main() -> int:
    # If spacehack isn't installed yet, install from the local wheel.
    try:
        importlib.import_module("spacehack")
    except ImportError:
        wheel = _find_wheel()
        if wheel is None:
            print(
                "ERROR: spacehack not installed and no spacehack-*.whl "
                "found in this directory.",
                file=sys.stderr,
            )
            return 1
        print(f"Installing spacehack from {wheel.name}...")
        subprocess.check_call(
            [sys.executable, "-m", "pip", "install", str(wheel)]
        )

    # Launch the game.
    from spacehack.__main__ import main as game_main
    return game_main()


if __name__ == "__main__":
    sys.exit(main())
