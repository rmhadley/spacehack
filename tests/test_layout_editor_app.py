"""Renderer-neutral behavior tests for the layout editor application."""

from __future__ import annotations

from types import SimpleNamespace

from tools.layout_editor.app import EditorApp
from tools.layout_editor.model import AssetMode, new_document
from tools.layout_editor.palette import build_palette


def test_editor_painting_updates_grid_and_directives():
    document = new_document(AssetMode.SHIP)
    app = EditorApp(SimpleNamespace(), document)
    enemy = next(entry for entry in app.palette if entry.enemy_id == "pirate_raider")
    app._select_palette(app.palette.index(enemy))

    app._paint(1, 0)

    assert document.grid.char_at(1, 0) == enemy.glyph
    assert document.enemy_directives[enemy.glyph].enemy_id == "pirate_raider"
    assert document.dirty


def test_editor_right_sample_selection_uses_raw_grid_glyph():
    document = new_document(AssetMode.SHIP)
    app = EditorApp(SimpleNamespace(), document)
    blank = next(index for index, entry in enumerate(app.palette) if entry.glyph == " ")
    app._select_palette(blank)
    app._paint(0, 0)
    app._select_palette(0)

    app._sample(0, 0)

    assert app._selected_entry().glyph == " "


def test_editor_shift_tab_selects_previous_palette_entry():
    document = new_document(AssetMode.SHIP)
    app = EditorApp(SimpleNamespace(), document)
    app._select_palette(2)

    assert not app._handle_key(SimpleNamespace(kind="keydown", key_name="tab", shift=True))

    assert app.palette_index == 1


def test_editor_keyboard_resize_marks_document_dirty():
    document = new_document(AssetMode.SHIP)
    app = EditorApp(SimpleNamespace(), document)

    assert not app._handle_key(SimpleNamespace(kind="keydown", key_name="+"))

    assert document.grid.width == 4
    assert document.dirty


def test_editor_frame_contains_controls_and_validation_state():
    document = new_document(AssetMode.SHIP)
    app = EditorApp(SimpleNamespace(), document)

    frame = app.render()
    text = "\n".join(
        "".join(frame.cell(x, y).char for x in range(frame.width))
        for y in range(frame.height)
    )

    assert "SPACEHACK LAYOUT EDITOR" in text
    assert "Validation: OK" in text
    assert "Mouse: left paint" in text


def test_palette_is_data_driven_and_contains_runtime_tile_choices():
    document = new_document(AssetMode.LANDMARK)
    palette = build_palette(document)

    assert any(entry.tile_name == "DUNGEON_WALL" for entry in palette)
    assert any(entry.tile_name == "DUNGEON_DOOR" for entry in palette)
    assert any(entry.enemy_id == "pirate_raider" for entry in palette)
    assert any(entry.loot_room_type == "cargo_bay" for entry in palette)
