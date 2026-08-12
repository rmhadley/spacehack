"""Regression checks for the Pygame-only runtime boundary."""

from pathlib import Path

from tools.smoke import _assert_backend_independence


def test_package_imports_with_retired_backend_blocked():
    """The supported package import must not need the retired backend."""
    root = Path(__file__).resolve().parents[1]

    assert _assert_backend_independence(root)
