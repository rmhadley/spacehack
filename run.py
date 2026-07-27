#!/usr/bin/env python3
"""One-command launcher: installs spacehack if needed, then runs it.

Placed alongside ``spacehack-*.whl`` in the dist package.  The
``.bat`` and shell wrappers all call this script.

On first run this creates a local ``.venv/`` inside the app directory
and installs the wheel into it — no system Python modification needed.
Subsequent launches skip straight to the game.
"""
import importlib
import os
import subprocess
import sys
from pathlib import Path


def _find_wheel() -> Path | None:
    """Return the first ``spacehack-*.whl`` in this script's directory."""
    here = Path(__file__).resolve().parent
    for f in sorted(here.glob("spacehack-*.whl")):
        return f
    return None


def _venv_python(venv_dir: Path) -> Path:
    """Return the path to the Python executable inside *venv_dir*."""
    if sys.platform == "win32":
        return venv_dir / "Scripts" / "python.exe"
    return venv_dir / "bin" / "python3"


def _ensure_venv(venv_dir: Path) -> Path:
    """Create *venv_dir* if it doesn't exist, install the wheel, return venv python."""
    venv_py = _venv_python(venv_dir)
    if venv_py.exists():
        return venv_py  # already set up

    wheel = _find_wheel()
    if wheel is None:
        print(
            "ERROR: spacehack not installed and no spacehack-*.whl "
            "found in this directory.",
            file=sys.stderr,
        )
        sys.exit(1)

    print("Setting up local environment (first run)...")
    subprocess.check_call([sys.executable, "-m", "venv", str(venv_dir)])
    subprocess.check_call([str(venv_py), "-m", "pip", "install", str(wheel)])
    return venv_py


def main() -> int:
    here = Path(__file__).resolve().parent
    venv_dir = here / ".venv"
    venv_py = _venv_python(venv_dir)

    # If we're not already running inside the app's own venv, set it up
    # and re-launch using the venv Python so imports resolve correctly.
    if sys.prefix != str(venv_dir):
        _ensure_venv(venv_dir)
        # Re-launch under the venv (replaces this process on Unix,
        # spawns a child on Windows).
        if sys.platform == "win32":
            sys.exit(subprocess.call([str(venv_py), __file__]))
        else:
            os.execv(str(venv_py), [str(venv_py), __file__])

    # We're inside the venv — spacehack is installed, just launch it.
    from spacehack.__main__ import main as game_main

    return game_main()


if __name__ == "__main__":
    sys.exit(main())
