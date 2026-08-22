"""Editable directive details for the layout editor inspector."""

from __future__ import annotations

from dataclasses import replace

from .model import ColourDirective, EditorDocument, EnemyDirective
from .palette import PaletteEntry, apply_palette_entry


_COLOR_FIELDS = ("fg_r", "fg_g", "fg_b", "bg_r", "bg_g", "bg_b")
_ENEMY_FIELDS = ("chance", "squad_min", "squad_max")


def _colour(document: EditorDocument, glyph: str) -> ColourDirective:
    """Return an existing color directive or derive a foreground default."""
    current = document.colour_directives.get(glyph)
    if current is not None:
        return current
    tile = document.tile_directives.get(glyph)
    if tile is not None:
        from src.spacehack import layout_format

        try:
            foreground = layout_format.tile_for_name(tile.tile_name).fg
        except KeyError:
            foreground = (180, 190, 205)
    else:
        foreground = (180, 190, 205)
    return ColourDirective(glyph, foreground)


def _ensure_enemy(document: EditorDocument, entry: PaletteEntry) -> EnemyDirective:
    """Return the selected enemy directive, creating its default if needed."""
    if entry.enemy_id is None:
        raise ValueError("selected palette entry is not an enemy")
    current = document.enemy_directives.get(entry.glyph)
    if current is None:
        apply_palette_entry(document, entry)
        current = document.enemy_directives[entry.glyph]
    return current


def _enemy_value(document: EditorDocument, entry: PaletteEntry) -> EnemyDirective:
    """Return an enemy directive without changing the document."""
    if entry.enemy_id is None:
        raise ValueError("selected palette entry is not an enemy")
    return document.enemy_directives.get(
        entry.glyph,
        EnemyDirective(glyph=entry.glyph, enemy_id=entry.enemy_id),
    )


def detail_fields(document: EditorDocument, entry: PaletteEntry) -> tuple[str, ...]:
    """Return inspector fields supported by one palette entry."""
    if entry.enemy_id is not None:
        return _ENEMY_FIELDS
    colour = document.colour_directives.get(entry.glyph)
    if entry.tile_name is not None or colour is not None:
        return _COLOR_FIELDS if colour is not None and colour.bg is not None else _COLOR_FIELDS[:3]
    return ()


def field_value(document: EditorDocument, entry: PaletteEntry, field: str):
    """Return the current value of one inspector field."""
    if entry.enemy_id is not None:
        enemy = _enemy_value(document, entry)
        return getattr(enemy, field)
    colour = _colour(document, entry.glyph)
    if field.startswith("fg_"):
        return colour.fg["rgb".index(field[-1])]
    if colour.bg is None:
        return None
    return colour.bg["rgb".index(field[-1])]


def _replace_rgb(values: tuple[int, int, int], channel: int, value: int) -> tuple[int, int, int]:
    """Return an RGB tuple with one clamped channel replaced."""
    updated = list(values)
    updated[channel] = max(0, min(255, value))
    return tuple(updated)


def adjust_field(
    document: EditorDocument,
    entry: PaletteEntry,
    field: str,
    direction: int,
) -> None:
    """Adjust one selected numeric inspector field in place."""
    if entry.enemy_id is not None:
        enemy = _ensure_enemy(document, entry)
        if field == "chance":
            updated = replace(enemy, chance=max(0.0, min(1.0, enemy.chance + direction * 0.05)))
        elif field == "squad_min":
            updated = replace(enemy, squad_min=max(1, min(enemy.squad_max, enemy.squad_min + direction)))
        else:
            updated = replace(enemy, squad_max=max(enemy.squad_min, enemy.squad_max + direction))
        document.enemy_directives[entry.glyph] = updated
        document.dirty = True
        return
    colour = _colour(document, entry.glyph)
    if field.startswith("fg_"):
        channel = "rgb".index(field[-1])
        foreground = _replace_rgb(colour.fg, channel, colour.fg[channel] + direction * 5)
        document.colour_directives[entry.glyph] = replace(colour, fg=foreground)
    elif colour.bg is not None:
        channel = "rgb".index(field[-1])
        background = _replace_rgb(colour.bg, channel, colour.bg[channel] + direction * 5)
        document.colour_directives[entry.glyph] = replace(colour, bg=background)
    document.dirty = True


def toggle_background(document: EditorDocument, entry: PaletteEntry) -> bool:
    """Toggle the selected color's explicit background and return its state."""
    colour = _colour(document, entry.glyph)
    if colour.bg is None:
        tile = document.tile_directives.get(entry.glyph)
        background = None
        if tile is not None:
            from src.spacehack import layout_format

            try:
                background = layout_format.tile_for_name(tile.tile_name).bg
            except KeyError:
                background = None
        document.colour_directives[entry.glyph] = replace(
            colour,
            bg=background or (0, 0, 0),
        )
        enabled = True
    else:
        document.colour_directives[entry.glyph] = replace(colour, bg=None)
        enabled = False
    document.dirty = True
    return enabled
