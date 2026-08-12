"""Regression checks for the Pygame-only runtime boundary."""

from pathlib import Path

from tools.smoke import _assert_backend_independence


_PROJECT_ROOT = Path(__file__).resolve().parents[1]


def _dependency_text() -> str:
    return (_PROJECT_ROOT / "pyproject.toml").read_text()


def test_package_imports_with_retired_backend_blocked():
    """The supported package import must not need the retired backend."""
    assert _assert_backend_independence(_PROJECT_ROOT)


def test_project_uses_pygame_community_edition_distribution():
    """The import name stays pygame while installs use pygame-ce wheels."""
    text = _dependency_text()

    assert '"pygame-ce>=2.5.8"' in text
    assert '"pygame>=2.5"' not in text
    requirements = (_PROJECT_ROOT / "requirements.txt").read_text()
    assert "pygame-ce>=2.5.8" in requirements
