"""Small deterministic Pygame-shaped doubles for renderer-neutral tests."""

from types import SimpleNamespace


class FakeFont:
    """Monospace font metrics for pure layout tests."""

    def __init__(self, *, char_width: int = 10, line_height: int = 24):
        self.char_width = char_width
        self.line_height = line_height

    def size(self, text: str) -> tuple[int, int]:
        return len(text) * self.char_width, self.line_height

    def get_linesize(self) -> int:
        return self.line_height


class FakeSdlEventQueue:
    """Scriptable SDL queue for ``wait_events`` harnesses.

    Serves one pre-loaded batch of raw events per ``event.get`` poll
    (``raw_event`` builds them); later polls return empty. Key codes
    resolve through ``key.name`` via ``key_names``.
    """

    QUIT = 1
    KEYDOWN = 2
    KEYUP = 3
    MOUSEMOTION = 4
    MOUSEBUTTONDOWN = 5
    MOUSEBUTTONUP = 6
    KMOD_SHIFT = 3

    def __init__(self, key_names: dict[int, str] | None = None, batches=()):
        self._polls = iter(batches)
        self.key = SimpleNamespace(name=(key_names or {}).get)
        self.event = SimpleNamespace(get=self._next_batch)

    def _next_batch(self):
        return next(self._polls, ())


def raw_event(event_type: int, key: int = 0, repeat: bool = False):
    """Build one raw SDL-shaped event for ``FakeSdlEventQueue`` batches."""
    return SimpleNamespace(type=event_type, key=key, mod=0, text="", repeat=repeat)
