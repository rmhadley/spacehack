#!/usr/bin/env python3
"""Run the pytest suite, auto-mounting .venv/bin/python3 if needed.

Passes all extra arguments through to pytest so you can run a single file:

    python3 tools/test.py tests/test_xp.py -v

Run from the project root.  Falls back to ``python3 -m pytest`` and
temp-installs pytest if the module isn't already available.
"""

import os
import subprocess
import sys
from pathlib import Path


def _ensure_venv() -> None:
    """Re-launch using the project venv if not already running in one."""
    if sys.prefix != sys.base_prefix:
        return
    venv_py = Path(__file__).resolve().parent.parent / ".venv" / "bin" / "python3"
    if venv_py.exists():
        os.execv(str(venv_py), [str(venv_py), __file__, *sys.argv[1:]])


def _ensure_pytest() -> None:
    """pip-install pytest into the current environment if missing."""
    try:
        import pytest  # noqa: F401
    except ImportError:
        subprocess.check_call(
            [sys.executable, "-m", "pip", "install", "pytest"],
        )


def main() -> int:
    _ensure_venv()
    _ensure_pytest()

    root = Path(__file__).resolve().parent.parent
    args = [sys.executable, "-m", "pytest", str(root / "tests"), *sys.argv[1:]]
    return subprocess.call(args)


if __name__ == "__main__":
    sys.exit(main())
