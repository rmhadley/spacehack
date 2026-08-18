"""Persistent display preferences for the Pygame presentation.

Display preferences are user configuration, not save-game state. The parser is
intentionally small because the project supports Python 3.10 while the
standard-library TOML reader starts in Python 3.11; it accepts the small TOML
subset this application writes and safely falls back to defaults.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


DEFAULT_WINDOW_WIDTH = 1600
DEFAULT_WINDOW_HEIGHT = 960
MIN_WINDOW_WIDTH = 800
MIN_WINDOW_HEIGHT = 480
MAX_WINDOW_WIDTH = 7680
MAX_WINDOW_HEIGHT = 4320


@dataclass(frozen=True)
class DisplayConfig:
    """User-owned display preferences, independent of a save file."""

    fullscreen: bool = False
    window_width: int = DEFAULT_WINDOW_WIDTH
    window_height: int = DEFAULT_WINDOW_HEIGHT

    def normalized(self) -> "DisplayConfig":
        """Return this config with safe supported window dimensions."""
        return DisplayConfig(
            fullscreen=bool(self.fullscreen),
            window_width=max(MIN_WINDOW_WIDTH, min(MAX_WINDOW_WIDTH, int(self.window_width))),
            window_height=max(MIN_WINDOW_HEIGHT, min(MAX_WINDOW_HEIGHT, int(self.window_height))),
        )


def default_config_path() -> Path:
    """Return the per-user display configuration path."""
    return Path.home() / ".spacehack" / "config.toml"


def parse_display_config(contents: str) -> DisplayConfig:
    """Parse the display section of the project's small TOML config.

    Unknown sections and keys are ignored so future preferences can coexist
    with this version. Malformed values raise ``ValueError`` for the loader to
    convert into a safe default.
    """
    section = ""
    values: dict[str, object] = {}
    for raw_line in contents.splitlines():
        line = raw_line.split("#", 1)[0].strip()
        if not line:
            continue
        if line.startswith("[") and line.endswith("]"):
            section = line[1:-1].strip()
            continue
        if section != "display":
            continue
        if "=" not in line:
            raise ValueError("display config line is missing '='")
        key, raw_value = (part.strip() for part in line.split("=", 1))
        if key == "fullscreen":
            if raw_value == "true":
                values[key] = True
            elif raw_value == "false":
                values[key] = False
            else:
                raise ValueError("fullscreen must be true or false")
        elif key in {"window_width", "window_height"}:
            try:
                values[key] = int(raw_value)
            except ValueError as exc:
                raise ValueError(f"{key} must be an integer") from exc
    return DisplayConfig(
        fullscreen=values.get("fullscreen", False),
        window_width=values.get("window_width", DEFAULT_WINDOW_WIDTH),
        window_height=values.get("window_height", DEFAULT_WINDOW_HEIGHT),
    ).normalized()


def serialize_display_config(config: DisplayConfig) -> str:
    """Serialize display preferences as the config format we own."""
    _config = config.normalized()
    return (
        "[display]\n"
        f"fullscreen = {'true' if _config.fullscreen else 'false'}\n"
        f"window_width = {_config.window_width}\n"
        f"window_height = {_config.window_height}\n"
    )


def load_display_config(path: Path | None = None) -> DisplayConfig:
    """Load display preferences, falling back safely when unavailable."""
    _path = path or default_config_path()
    try:
        return parse_display_config(_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, ValueError):
        return DisplayConfig()


def save_display_config(config: DisplayConfig, path: Path | None = None) -> None:
    """Persist display preferences, creating the user config directory."""
    _path = path or default_config_path()
    _path.parent.mkdir(parents=True, exist_ok=True)
    _path.write_text(serialize_display_config(config), encoding="utf-8")
