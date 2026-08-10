"""Tests for the optional text-rendering comparison spike."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

from tools.text_render_spike import (
    SpikeConfig,
    choose_font_path,
    clamp_config,
    panel_rects,
    _bitmap_tile_or_none,
)


def test_spike_does_not_eagerly_import_numpy():
    """Help and configuration remain usable before visual dependencies load."""
    source = Path("tools/text_render_spike.py").read_text(encoding="utf-8")
    assert "import numpy as np" not in source


def test_bitmap_tile_lookup_treats_spaces_as_blank_cells():
    """The comparison raster preserves spacing for unmapped characters."""
    tileset = {ord("A"): "glyph"}
    assert _bitmap_tile_or_none(tileset, " ") is None
    assert _bitmap_tile_or_none(tileset, "?") is None
    assert _bitmap_tile_or_none(tileset, "A") == "glyph"


def test_panel_rects_split_the_window_with_a_gap():
    """Comparison panels fit inside the requested window without overlap."""
    left, right = panel_rects(1280, 760)
    assert left.x == 24
    assert left.y == right.y == 24
    assert left.x + left.width < right.x
    assert right.x + right.width == 1256
    assert left.height == right.height == 712


def test_clamp_config_limits_unsafe_visual_dimensions():
    """CLI values are bounded while the font choice and AA flag survive."""
    config = SpikeConfig(
        width=100,
        height=100,
        font_size=200,
        bitmap_scale=0,
        font_name="Example Mono",
        antialias=False,
    )
    clamped = clamp_config(config)
    assert clamped.width == 800
    assert clamped.height == 520
    assert clamped.font_size == 96
    assert clamped.bitmap_scale == 1
    assert clamped.font_name == "Example Mono"
    assert clamped.antialias is False


def test_choose_font_path_prefers_a_requested_match():
    """The requested family wins when the Pygame font registry finds it."""
    calls = []

    def match_font(name):
        calls.append(name)
        return "/fonts/example.ttf" if name == "Example Mono" else None

    pygame = SimpleNamespace(font=SimpleNamespace(match_font=match_font))
    assert choose_font_path(pygame, "Example Mono") == "/fonts/example.ttf"
    assert calls == ["Example Mono"]


def test_choose_font_path_uses_preferred_monospace_fallbacks():
    """Without a request, the first installed preferred family is selected."""
    pygame = SimpleNamespace(
        font=SimpleNamespace(
            match_font=lambda name: "/fonts/dejavu.ttf" if name == "DejaVu Sans Mono" else None,
        ),
    )
    assert choose_font_path(pygame, None) == "/fonts/dejavu.ttf"


def test_choose_font_path_accepts_a_direct_font_file(tmp_path):
    """A valid font path bypasses family-name lookup."""
    font_path = tmp_path / "custom.ttf"
    font_path.write_bytes(b"font placeholder")
    pygame = SimpleNamespace(
        font=SimpleNamespace(match_font=lambda _name: None),
    )
    assert choose_font_path(pygame, str(font_path)) == str(font_path)
