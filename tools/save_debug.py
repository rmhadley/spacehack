#!/usr/bin/env python3
"""Inspect and simulate a spacehack save without opening Pygame."""

from __future__ import annotations

import sys
from pathlib import Path

# Allow direct execution from the repository root without requiring an
# editable install, matching the existing tools/*.py conventions.
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from spacehack.debug_session import main


if __name__ == "__main__":
    raise SystemExit(main())
