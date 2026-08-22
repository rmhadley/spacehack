"""Interactive Pygame application for editing authored layout documents."""

from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory
import time

from src.spacehack import dungeon_layout, layout_format, world
from src.spacehack.engine import TILE_HEIGHT, TILE_WIDTH
from src.spacehack.framebuffer import FrameBuffer
from src.spacehack.pygame_engine import logical_position

from .format import document_to_text, save_document
from .model import AssetMode, EditorDocument
from .palette import PaletteEntry, apply_palette_entry, build_palette
from .validation import ValidationIssue, validate_document


SCREEN_COLUMNS = 100
SCREEN_ROWS = 60
CANVAS_X = 1
CANVAS_Y = 3
CANVAS_COLUMNS = 75
CANVAS_ROWS = 34
PALETTE_X = 77
PALETTE_Y = 3
PALETTE_ROWS = 32
PALETTE_PAGE_SIZE = 28


class EditorApp:
    """Own one editing session without adding state to the game runtime."""

    def __init__(self, context, document: EditorDocument):
        self.context = context
        self.document = document
        self.palette = build_palette(document)
        self.palette_index = 0
        self.palette_page = 0
        self.selected = self._initial_selection()
        self.view_x = 0
        self.view_y = 0
        self.preview = False
        self.preview_map: world.GameMap | None = None
        self.status = "Ready. Click a palette entry, then paint the canvas."

    def _initial_selection(self) -> tuple[int, int]:
        """Select the authored player marker or the top-left cell."""
        for y, row in enumerate(self.document.grid.rows):
            for x, glyph in enumerate(row):
                if glyph == "P":
                    return x, y
        return 0, 0

    def _refresh_palette(self, selected_glyph: str | None = None) -> None:
        """Rebuild palette entries after a semantic marker is added."""
        previous = selected_glyph or self._selected_entry().glyph
        self.palette = build_palette(self.document)
        self.palette_index = next(
            (index for index, entry in enumerate(self.palette) if entry.glyph == previous),
            min(self.palette_index, max(0, len(self.palette) - 1)),
        )
        self.palette_page = self.palette_index // PALETTE_PAGE_SIZE

    def _selected_entry(self) -> PaletteEntry:
        """Return the selected palette entry, clamped to current contents."""
        if not self.palette:
            raise RuntimeError("the editor palette cannot be empty")
        self.palette_index = min(self.palette_index, len(self.palette) - 1)
        return self.palette[self.palette_index]

    def _select_palette(self, index: int) -> None:
        """Select one absolute palette index."""
        if not self.palette:
            return
        self.palette_index = max(0, min(index, len(self.palette) - 1))
        self.palette_page = self.palette_index // PALETTE_PAGE_SIZE

    def _paint(self, x: int, y: int) -> None:
        """Paint one grid cell with the selected palette semantics."""
        if not (0 <= x < self.document.grid.width and 0 <= y < self.document.grid.height):
            return
        entry = self._selected_entry()
        apply_palette_entry(self.document, entry)
        self.document.grid.set_char(x, y, entry.glyph)
        self.document.dirty = True
        self._refresh_palette(entry.glyph)
        self.status = f"Painted {entry.label} at {x},{y}."

    def _sample(self, x: int, y: int) -> None:
        """Sample a cell's raw glyph into the palette selection."""
        if not (0 <= x < self.document.grid.width and 0 <= y < self.document.grid.height):
            return
        glyph = self.document.grid.char_at(x, y)
        for index, entry in enumerate(self.palette):
            if entry.glyph == glyph:
                self._select_palette(index)
                self.status = f"Selected {entry.label}."
                return
        self.status = f"Glyph {glyph!r} has no palette entry."

    def _move_selection(self, dx: int, dy: int) -> None:
        """Move the keyboard selection and keep it inside the document."""
        width, height = self.document.grid.width, self.document.grid.height
        x = max(0, min(self.selected[0] + dx, width - 1))
        y = max(0, min(self.selected[1] + dy, height - 1))
        self.selected = x, y
        self._follow_selection()

    def _follow_selection(self) -> None:
        """Scroll the authored grid enough to show the selection."""
        x, y = self.selected
        self.view_x = max(0, min(self.view_x, max(0, self.document.grid.width - CANVAS_COLUMNS)))
        self.view_y = max(0, min(self.view_y, max(0, self.document.grid.height - CANVAS_ROWS)))
        if x < self.view_x:
            self.view_x = x
        if x >= self.view_x + CANVAS_COLUMNS:
            self.view_x = x - CANVAS_COLUMNS + 1
        if y < self.view_y:
            self.view_y = y
        if y >= self.view_y + CANVAS_ROWS:
            self.view_y = y - CANVAS_ROWS + 1

    def _load_preview(self) -> None:
        """Parse the in-memory document through the production loader."""
        try:
            with TemporaryDirectory() as directory:
                path = Path(directory) / "preview.layout"
                path.write_text(document_to_text(self.document), encoding="utf-8")
                self.preview_map, _ = dungeon_layout.load_layout(
                    "preview",
                    layout_dir=Path(directory),
                    require_spawn=self.document.mode is AssetMode.SHIP,
                )
            self.status = "Preview loaded through the production layout loader."
        except (OSError, ValueError, KeyError) as error:
            self.preview_map = None
            self.status = f"Preview error: {error}"

    def _toggle_preview(self) -> None:
        """Switch between raw editing and parsed runtime preview."""
        self.preview = not self.preview
        if self.preview:
            self._load_preview()
        else:
            self.status = "Editing raw layout grid."

    def _save(self) -> None:
        """Validate and save the document when no errors are present."""
        issues = validate_document(self.document)
        errors = [issue for issue in issues if issue.severity == "error"]
        if errors:
            self.status = f"Cannot save: {errors[0].message}"
            return
        try:
            save_document(self.document)
            self.status = f"Saved {self.document.path.name}."
        except (OSError, ValueError) as error:
            self.status = f"Save error: {error}"

    def _logical_cell(self, position: tuple[int, int]) -> tuple[int, int] | None:
        """Convert a physical mouse position into an editor grid coordinate."""
        runtime = getattr(self.context, "_runtime", None)
        engine = getattr(runtime, "engine", None)
        if engine is None:
            return None
        logical = logical_position(
            position,
            engine.viewport,
            engine.config.logical_width,
            engine.config.logical_height,
        )
        if logical is None:
            return None
        x, y = logical[0] // TILE_WIDTH, logical[1] // TILE_HEIGHT
        if CANVAS_X <= x < CANVAS_X + CANVAS_COLUMNS and CANVAS_Y <= y < CANVAS_Y + CANVAS_ROWS:
            return x - CANVAS_X + self.view_x, y - CANVAS_Y + self.view_y
        return None

    def _handle_mouse(self, event) -> None:
        """Handle palette selection or canvas paint/sample clicks."""
        if event.position is None:
            return
        runtime = getattr(self.context, "_runtime", None)
        engine = getattr(runtime, "engine", None)
        if engine is None:
            return
        logical = logical_position(
            event.position,
            engine.viewport,
            engine.config.logical_width,
            engine.config.logical_height,
        )
        if logical is None:
            return
        x, y = logical[0] // TILE_WIDTH, logical[1] // TILE_HEIGHT
        if PALETTE_X <= x < SCREEN_COLUMNS and PALETTE_Y <= y < PALETTE_Y + PALETTE_ROWS:
            self._select_palette(self.palette_page * PALETTE_PAGE_SIZE + y - PALETTE_Y)
            return
        cell = self._logical_cell(event.position)
        if cell is None or self.preview:
            return
        if event.button == 3:
            self._sample(*cell)
        else:
            self.selected = cell
            self._paint(*cell)

    def _handle_key(self, event) -> bool:
        """Handle one key and return whether the application should close."""
        if event.kind == "quit" or event.key_name == "escape":
            return True
        if event.kind != "keydown":
            return False
        key = event.key_name
        if key in {"v", "f5"}:
            self._toggle_preview()
        elif key == "s":
            self._save()
        elif key == "tab":
            direction = -1 if event.shift else 1
            self._select_palette((self.palette_index + direction) % len(self.palette))
        elif key == "[":
            self._select_palette(self.palette_index - PALETTE_PAGE_SIZE)
        elif key == "]":
            self._select_palette(self.palette_index + PALETTE_PAGE_SIZE)
        elif key in {"left", "h"}:
            self._move_selection(-1, 0)
        elif key in {"right", "l"}:
            self._move_selection(1, 0)
        elif key in {"up", "k"}:
            self._move_selection(0, -1)
        elif key in {"down", "j"}:
            self._move_selection(0, 1)
        elif key in {"enter", "space"} and not self.preview:
            self._paint(*self.selected)
        elif key in {"=", "+"} and not self.preview:
            self.document.grid.resize(self.document.grid.width + 1, self.document.grid.height)
            self.document.dirty = True
            self.status = "Expanded the layout width."
        elif key in {"-", "_"} and not self.preview and self.document.grid.width > 1:
            self.document.grid.resize(self.document.grid.width - 1, self.document.grid.height)
            self.selected = (
                min(self.selected[0], self.document.grid.width - 1),
                self.selected[1],
            )
            self.document.dirty = True
            self.status = "Reduced the layout width."
        elif key in {"page up", "pageup"} and not self.preview:
            self.document.grid.resize(self.document.grid.width, self.document.grid.height + 1)
            self.document.dirty = True
            self.status = "Expanded the layout height."
        elif key in {"page down", "pagedown"} and not self.preview and self.document.grid.height > 1:
            self.document.grid.resize(self.document.grid.width, self.document.grid.height - 1)
            self.selected = (
                self.selected[0],
                min(self.selected[1], self.document.grid.height - 1),
            )
            self.document.dirty = True
            self.status = "Reduced the layout height."
        elif key.isdigit() and key != "0":
            self._select_palette(self.palette_page * PALETTE_PAGE_SIZE + int(key) - 1)
        return False

    def _handle_event(self, event) -> bool:
        """Dispatch one project-owned input event."""
        if event.kind == "mousebuttondown":
            self._handle_mouse(event)
            return False
        return self._handle_key(event)

    def _issue_text(self, issues: tuple[ValidationIssue, ...]) -> str:
        """Format the first validation issue for the status panel."""
        if not issues:
            return "Validation: OK"
        issue = issues[0]
        location = f" at {issue.cell[0]},{issue.cell[1]}" if issue.cell else ""
        return f"Validation: {issue.severity.upper()} {issue.message}{location}"

    def _cell_appearance(self, glyph: str) -> tuple[tuple[int, int, int], tuple[int, int, int] | None]:
        """Resolve an editor cell's authored colors from its directives."""
        colour = self.document.colour_directives.get(glyph)
        if colour is not None:
            return colour.fg, colour.bg
        directive = self.document.tile_directives.get(glyph)
        if directive is not None:
            try:
                tile = layout_format.tile_for_name(directive.tile_name)
                return tile.fg, tile.bg
            except KeyError:
                pass
        return (180, 190, 205), None

    def _render_grid(self, console: FrameBuffer) -> None:
        """Render the editable raw grid in the canvas panel."""
        for row in range(CANVAS_ROWS):
            for col in range(CANVAS_COLUMNS):
                x, y = col + self.view_x, row + self.view_y
                if x >= self.document.grid.width or y >= self.document.grid.height:
                    continue
                glyph = self.document.grid.char_at(x, y)
                display = "." if glyph == " " else glyph
                fg, bg = self._cell_appearance(glyph)
                if (x, y) == self.selected and not self.preview:
                    fg, bg = (255, 220, 100), (55, 45, 20)
                console.write_cell(CANVAS_X + col, CANVAS_Y + row, display, fg=fg, bg=bg)

    def _render_palette(self, console: FrameBuffer) -> None:
        """Render the current page of palette entries."""
        start = self.palette_page * PALETTE_PAGE_SIZE
        for row in range(PALETTE_ROWS):
            index = start + row
            if index >= len(self.palette):
                break
            entry = self.palette[index]
            marker = ">" if index == self.palette_index else " "
            glyph = "_" if entry.glyph == " " else entry.glyph
            text = f"{marker}{row + 1:02d} {glyph} {entry.label}"
            fg = (255, 220, 100) if index == self.palette_index else (190, 200, 215)
            console.print(x=PALETTE_X, y=PALETTE_Y + row, string=text[:23], fg=fg)

    def _render_preview(self, console: FrameBuffer) -> None:
        """Render the parsed production map in the canvas panel."""
        if self.preview_map is None:
            return
        world.render_world(
            console,
            self.preview_map,
            region_x=0,
            region_y=0,
            region_w=CANVAS_X + CANVAS_COLUMNS,
            region_h=CANVAS_Y + CANVAS_ROWS,
        )

    def render(self) -> FrameBuffer:
        """Build the current editor frame."""
        console = FrameBuffer(SCREEN_COLUMNS, SCREEN_ROWS, background=(5, 8, 12))
        console.print(x=1, y=0, string="SPACEHACK LAYOUT EDITOR", fg=(255, 210, 100))
        mode = "PREVIEW" if self.preview else "EDIT"
        dirty = " *" if self.document.dirty else ""
        console.print(x=1, y=1, string=f"{mode}  {self.document.mode.value.upper()}  {self.document.grid.width}x{self.document.grid.height}{dirty}", fg=(170, 190, 210))
        if self.preview:
            self._render_preview(console)
        else:
            self._render_grid(console)
        console.print(x=PALETTE_X, y=0, string="PALETTE", fg=(255, 210, 100))
        self._render_palette(console)
        issues = validate_document(self.document)
        console.print(x=1, y=39, string=self.status[:75], fg=(255, 180, 110) if issues else (170, 220, 170))
        console.print(x=1, y=40, string=self._issue_text(issues)[:75], fg=(255, 140, 120) if issues else (150, 210, 170))
        console.print(x=1, y=42, string="Mouse: left paint  right sample | V/F5 preview | S save | Esc quit", fg=(150, 165, 180))
        console.print(x=1, y=43, string="Arrows/HJKL move  Enter/Space paint  +/- width  PgUp/PgDn height  Tab/[ ] palette", fg=(150, 165, 180))
        return console

    def run(self) -> None:
        """Run the editor until Escape or window close."""
        while True:
            if any(self._handle_event(event) for event in self.context.events()):
                return
            self.context.present(self.render())
            time.sleep(0.01)


def run_editor(context, document: EditorDocument) -> None:
    """Run an editor session in an already-open project runtime."""
    EditorApp(context, document).run()
