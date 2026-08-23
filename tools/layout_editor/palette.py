"""Palette entries for tile, marker, loot, and enemy authoring."""

from __future__ import annotations

from dataclasses import dataclass

from src.spacehack import layout_format
from src.spacehack.dungeon_layout import LOOT_ROOM_TYPES
from src.spacehack.data.npc_chars import _registry

from .model import EditorDocument, EnemyDirective, LootDirective, TileDirective


_RESERVED_MARKERS = frozenset({"P", "C", "E", "T", "r", "R", "S"})


@dataclass(frozen=True)
class PaletteEntry:
    """One selectable cell/semantic authoring choice."""

    glyph: str
    label: str
    category: str
    tile_name: str | None = None
    enemy_id: str | None = None
    loot_room_type: str | None = None


def _tile_entries(document: EditorDocument) -> list[PaletteEntry]:
    """Return existing tile directives followed by unused world tiles."""
    entries = [
        PaletteEntry(glyph, directive.tile_name, "tile", tile_name=directive.tile_name)
        for glyph, directive in document.tile_directives.items()
    ]
    used = {entry.glyph for entry in entries} | _RESERVED_MARKERS
    for name in layout_format.tile_names():
        tile = layout_format.tile_for_name(name)
        glyph = tile.char
        if len(glyph) != 1 or glyph == " " or glyph in used:
            continue
        entries.append(PaletteEntry(glyph, name, "tile", tile_name=name))
        used.add(glyph)
    return entries


def _marker_entries() -> list[PaletteEntry]:
    """Return the fixed runtime marker choices."""
    return [
        PaletteEntry(" ", "blank space", "marker"),
        PaletteEntry("P", "player spawn", "marker"),
        PaletteEntry("C", "computer / console", "marker"),
        PaletteEntry("E", "engine terminal", "marker"),
        PaletteEntry("T", "landmark terminal", "marker"),
    ]


def _enemy_entries(document: EditorDocument) -> list[PaletteEntry]:
    """Return catalog-backed enemy marker choices."""
    existing = {directive.enemy_id: glyph for glyph, directive in document.enemy_directives.items()}
    entries: list[PaletteEntry] = []
    for enemy_id, spec in sorted(_registry().items()):
        glyph = existing.get(enemy_id, spec.char)
        entries.append(PaletteEntry(glyph, f"enemy {enemy_id}", "enemy", enemy_id=enemy_id))
    return entries


def _loot_entries(document: EditorDocument) -> list[PaletteEntry]:
    """Return existing and available loot-room marker choices."""
    existing = {
        directive.room_type: glyph
        for glyph, directive in document.loot_directives.items()
    }
    fallback_glyphs = iter("1234567890qwerty")
    entries: list[PaletteEntry] = []
    for room_type in sorted(LOOT_ROOM_TYPES):
        glyph = existing.get(room_type)
        if glyph is None:
            glyph = next((candidate for candidate in fallback_glyphs if candidate not in existing.values()), "?")
        entries.append(PaletteEntry(glyph, f"loot {room_type}", "loot", loot_room_type=room_type))
    return entries


def build_palette(document: EditorDocument) -> tuple[PaletteEntry, ...]:
    """Build a stable palette whose selections update document directives."""
    return tuple(
        _tile_entries(document)
        + _marker_entries()
        + _enemy_entries(document)
        + _loot_entries(document)
    )


def apply_palette_entry(document: EditorDocument, entry: PaletteEntry) -> None:
    """Ensure a selected semantic entry has the directive it needs."""
    if entry.tile_name is not None:
        document.tile_directives[entry.glyph] = TileDirective(entry.glyph, entry.tile_name)
    if entry.enemy_id is not None:
        existing = document.enemy_directives.get(entry.glyph)
        document.enemy_directives[entry.glyph] = existing or EnemyDirective(
            glyph=entry.glyph,
            enemy_id=entry.enemy_id,
            chance=1.0,
        )
    if entry.loot_room_type is not None:
        document.loot_directives[entry.glyph] = LootDirective(
            glyph=entry.glyph,
            room_type=entry.loot_room_type,
        )
