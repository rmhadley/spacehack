"""Small deterministic Pygame-shaped doubles for renderer-neutral tests."""


class FakeFont:
    """Monospace font metrics for pure layout tests."""

    def __init__(self, *, char_width: int = 10, line_height: int = 24):
        self.char_width = char_width
        self.line_height = line_height

    def size(self, text: str) -> tuple[int, int]:
        return len(text) * self.char_width, self.line_height

    def get_linesize(self) -> int:
        return self.line_height
