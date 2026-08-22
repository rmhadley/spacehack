"""Command-line entry point for the layout editor."""

from __future__ import annotations

import argparse
from pathlib import Path

from src.spacehack.engine import load_tileset
from src.spacehack.pygame_runtime import open_runtime

from .app import run_editor
from .format import asset_directories
from .model import AssetMode, infer_mode, load_document, new_document


def _parser() -> argparse.ArgumentParser:
    """Build the editor command-line parser."""
    parser = argparse.ArgumentParser(
        description="Create and edit spacehack .layout assets",
    )
    parser.add_argument("path", nargs="?", help="existing .layout file to open")
    parser.add_argument(
        "--mode",
        choices=tuple(mode.value for mode in AssetMode),
        default=AssetMode.SHIP.value,
        help="asset family for a new document",
    )
    parser.add_argument(
        "--output",
        help="repository data path to use when saving a new document",
    )
    return parser


def _document(args: argparse.Namespace):
    """Load the requested file or create a new document."""
    if args.path:
        path = Path(args.path)
        return load_document(path, infer_mode(path))
    mode = AssetMode(args.mode)
    output = Path(args.output) if args.output else asset_directories()[mode] / "new_layout.layout"
    return new_document(mode, output)


def main(argv: list[str] | None = None) -> int:
    """Open the standalone Pygame editor."""
    args = _parser().parse_args(argv)
    document = _document(args)
    tileset = load_tileset()
    with open_runtime(tileset) as context:
        run_editor(context, document)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
