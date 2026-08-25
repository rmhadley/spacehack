"""Regression: every glyph used by live map content must render.

``GlyphAtlas._source_rect`` resolves a character through
``engine.CP437_CHARMAP``; an unmapped character silently draws nothing
(only its background fill). This suite sweeps every source of map
glyphs — planet themes, world/city tile constants, transit stops, and
authored landmark layouts — and fails if any character falls outside
the charmap. The original bug: ♣/♦/♥/█/· had procedural tiles that
never rendered because the codepoints were missing from the charmap.
"""

from __future__ import annotations

import glob
from dataclasses import fields, is_dataclass
from pathlib import Path

from spacehack import city_tiles, engine, world
from spacehack.data.planets import themes as theme_module


_SRC = Path(__file__).resolve().parents[1] / "src" / "spacehack"
_MAPPED = set(engine.CP437_CHARMAP)


def _is_tile(obj) -> bool:
    return (
        hasattr(obj, "char") and isinstance(getattr(obj, "char"), str)
        and hasattr(obj, "kind")
    )


def _theme_tile_chars() -> dict[str, list[str]]:
    found: dict[str, list[str]] = {}
    for name in dir(theme_module):
        preset = getattr(theme_module, name)
        if not (is_dataclass(preset) and not isinstance(preset, type)):
            continue
        for field in fields(preset):
            value = getattr(preset, field.name)
            if _is_tile(value):
                found.setdefault(value.char, []).append(
                    f"themes.{name}.{field.name}"
                )
    return found


def _module_tile_chars() -> dict[str, list[str]]:
    found: dict[str, list[str]] = {}
    modules = {"world": world, "city_tiles": city_tiles}
    city_paths = sorted(glob.glob(str(_SRC / "*_city.py")))
    for path in city_paths:
        mod_name = f"spacehack.{Path(path).stem}"
        modules[mod_name] = __import__(mod_name, fromlist=["x"])
    for mod_name, module in modules.items():
        for attr_name, value in vars(module).items():
            if _is_tile(value):
                found.setdefault(value.char, []).append(f"{mod_name}.{attr_name}")
    return found


def _layout_art_chars() -> dict[str, list[str]]:
    """Every non-space character in landmark MAP art blocks."""
    found: dict[str, list[str]] = {}
    for layout_path in sorted(glob.glob(str(_SRC / "data" / "landmarks" / "*.layout"))):
        short = Path(layout_path).name
        in_map = False
        for line in open(layout_path, encoding="utf-8"):
            line = line.rstrip("\n")
            if line.strip() == "MAP":
                in_map = True
                continue
            if line.strip() == "ENDMAP":
                in_map = False
                continue
            if in_map:
                for char in line:
                    if char != " ":
                        found.setdefault(char, []).append(short)
    return found


def test_every_used_glyph_is_in_the_charmap():
    used: dict[str, list[str]] = {}
    for source in (_theme_tile_chars(), _module_tile_chars(), _layout_art_chars()):
        for char, locations in source.items():
            used.setdefault(char, []).extend(locations)
    # Transit stops render their own default glyph.
    used.setdefault(world.TransitStation.glyph, []).append("TransitStation.glyph")

    unmapped = {
        char: locations
        for char, locations in sorted(used.items())
        if ord(char) not in _MAPPED
    }
    assert not unmapped, (
        "Glyphs used by live map content but absent from CP437_CHARMAP "
        f"(they would silently draw as empty cells): {unmapped!r}"
    )


def test_charmap_has_no_duplicate_mapped_codepoints():
    nonzero = [cp for cp in engine.CP437_CHARMAP if cp]
    assert len(nonzero) == len(set(nonzero))
