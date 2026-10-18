"""Renderer-neutral tests for the PygameRuntime facade.

The engine derives its ``display_config`` from the live window only, so
these tests pin the stitching that keeps ``animation_speed`` round-tripping
through Apply and re-reading — plus the animation_timing sync — and the
``wait_events`` batch contract: each call returns the whole drained SDL
batch, with a released key's repeat keydowns dropped at its keyup.
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from src.spacehack import animation_timing, pygame_engine, pygame_runtime
from src.spacehack.display_config import DisplayConfig
from tests.support.asyncutil import run
from tests.support.fake_pygame import FakeSdlEventQueue, raw_event


@pytest.fixture(autouse=True)
def _restore_speed_scale():
    yield
    animation_timing.set_speed_scale(1.0)


def _runtime_with_fake_engine(config: DisplayConfig) -> pygame_runtime.PygameRuntime:
    runtime = pygame_runtime.PygameRuntime(tileset=None, display_config=config)
    runtime.engine = SimpleNamespace(
        display_config=config.normalized(),
        apply_display_config=lambda _config: None,
    )
    return runtime


_KEY_NAMES = {40: "j", 41: "k"}
_EVENT_TYPES = {"down": FakeSdlEventQueue.KEYDOWN, "up": FakeSdlEventQueue.KEYUP}


def _raw_event(kind: str, key: int, repeat: bool = False):
    return raw_event(_EVENT_TYPES[kind], key=key, repeat=repeat)


def _input_runtime(batches: list[list]):
    """A PygameRuntime whose fake SDL queue serves one batch per poll."""
    queue = FakeSdlEventQueue(_KEY_NAMES, batches)
    runtime = pygame_runtime.PygameRuntime(tileset=None, display_config=DisplayConfig())
    runtime.engine = SimpleNamespace(
        pygame=queue,
        events=lambda: tuple(
            pygame_engine.translate_event(queue, event)
            for event in queue.event.get()
        ),
    )
    return runtime


def test_held_key_repeats_flow_and_release_purges_its_batch():
    batches = [
        [_raw_event("down", 40)],
        [_raw_event("down", 40, repeat=True), _raw_event("down", 40, repeat=True)],
        [_raw_event("down", 40, repeat=True), _raw_event("up", 40)],
    ]
    runtime = _input_runtime(batches)

    pressed = run(runtime.wait_events())
    held = run(runtime.wait_events())
    released = run(runtime.wait_events())

    assert [(e.kind, e.repeat) for e in pressed] == [("keydown", False)]
    assert [(e.kind, e.repeat) for e in held] == [
        ("keydown", True), ("keydown", True),
    ]
    assert [(e.kind, e.repeat) for e in released] == [("keyup", False)]


def test_release_purge_keeps_other_keys_repeats():
    batches = [
        [_raw_event("down", 40), _raw_event("down", 41)],
        [_raw_event("down", 41, repeat=True), _raw_event("up", 40)],
    ]
    runtime = _input_runtime(batches)

    pressed = run(runtime.wait_events())
    after_release = run(runtime.wait_events())

    assert [e.key_name for e in pressed] == ["j", "k"]
    assert [(e.kind, e.key_name) for e in after_release] == [
        ("keydown", "k"), ("keyup", "j"),
    ]


def test_same_batch_tap_still_delivers_its_press():
    runtime = _input_runtime([[_raw_event("down", 40), _raw_event("up", 40)]])

    delivered = run(runtime.wait_events())

    assert [(e.kind, e.repeat) for e in delivered] == [
        ("keydown", False), ("keyup", False),
    ]


def _event(kind: str, key_name: str = "", repeat: bool = False):
    return pygame_engine.PygameInputEvent(kind=kind, key_name=key_name, repeat=repeat)


def test_drop_released_repeats_keeps_batches_without_a_keyup_whole():
    batch = (_event("keydown", "j", repeat=True), _event("keydown", "j", repeat=True))

    assert pygame_runtime._drop_released_repeats(batch) == batch
    assert pygame_runtime._drop_released_repeats(()) == ()


def test_drop_released_repeats_drops_only_repeats_of_released_keys():
    batch = (
        _event("keydown", "j"),
        _event("keydown", "j", repeat=True),
        _event("keydown", "k", repeat=True),
        _event("keyup", "j"),
    )

    assert pygame_runtime._drop_released_repeats(batch) == (
        _event("keydown", "j"),
        _event("keydown", "k", repeat=True),
        _event("keyup", "j"),
    )


def test_drain_sdl_batch_filters_irrelevant_events():
    queue = FakeSdlEventQueue(
        key_names={40: "j"},
        batches=[(SimpleNamespace(type=99), _raw_event("down", 40))],
    )

    batch = pygame_runtime._drain_sdl_batch(queue, set())

    assert [(e.kind, e.key_name) for e in batch] == [("keydown", "j")]


def test_repeats_are_stamped_by_keydown_keyup_pairing():
    """pygame never exposes SDL's repeat flag — the runtime derives it.

    A keydown for a key already held (keydown seen, no keyup since) is
    a repeat, including a second keydown within the same batch.
    """
    runtime = _input_runtime([
        [_raw_event("down", 40)],
        [_raw_event("down", 40, repeat=True)],
        [_raw_event("down", 40), _raw_event("down", 40)],
        [_raw_event("up", 40)],
        [_raw_event("down", 40)],
    ])

    first = run(runtime.wait_events())
    held_press = run(runtime.wait_events())
    same_batch = run(runtime.wait_events())
    release = run(runtime.wait_events())
    fresh = run(runtime.wait_events())

    assert [(e.kind, e.repeat) for e in first] == [("keydown", False)]
    assert [(e.kind, e.repeat) for e in held_press] == [("keydown", True)]
    assert [(e.kind, e.repeat) for e in same_batch] == [
        ("keydown", True), ("keydown", True),
    ]
    assert [e.kind for e in release] == ["keyup"]
    assert [(e.kind, e.repeat) for e in fresh] == [("keydown", False)]
    assert runtime._held_keys == {"j"}


def test_sync_events_stamp_repeats_and_note_drained_clears_held():
    runtime = _input_runtime([
        [_raw_event("down", 41), _raw_event("up", 41)],
        [_raw_event("down", 41)],
    ])

    flushed = runtime.events()
    held_press = runtime.events()

    assert [(e.kind, e.repeat) for e in flushed] == [
        ("keydown", False), ("keyup", False),
    ]
    assert [(e.kind, e.repeat) for e in held_press] == [("keydown", False)]
    assert runtime._held_keys == {"k"}

    runtime.note_drained((_raw_event("up", 41),))
    assert runtime._held_keys == set()
    runtime.note_drained((_raw_event("down", 40),))
    assert runtime._held_keys == {"j"}


def test_display_config_property_stitches_animation_speed_onto_engine_state():
    runtime = _runtime_with_fake_engine(DisplayConfig(animation_speed=2.0))
    runtime.engine.display_config = DisplayConfig(fullscreen=True)

    assert runtime.display_config.fullscreen is True
    assert runtime.display_config.animation_speed == 2.0


def test_apply_display_config_keeps_animation_speed_and_syncs_timing():
    runtime = _runtime_with_fake_engine(DisplayConfig())

    runtime.apply_display_config(DisplayConfig(animation_speed=4.0))

    assert runtime.display_config.animation_speed == 4.0
    assert animation_timing.speed_scale() == 4.0


def test_drain_sdl_returns_events_and_feeds_held_state():
    """The shared modal-drain contract: raw events come back for the
    pump's own dispatch while the runtime's held-key state sees them —
    and a context without the hook degrades to the raw drain."""
    runtime = _input_runtime([[_raw_event("down", 40)]])
    context = SimpleNamespace(note_drained=runtime.note_drained)

    drained = pygame_runtime.drain_sdl(runtime.engine.pygame, context)

    assert [e.key for e in drained] == [40]  # raw SDL shape, not translated
    assert runtime._held_keys == {"j"}
    # A hook-less context (headless doubles) skips the feed silently.
    runtime.engine.pygame  # the fake queue is now empty
    assert pygame_runtime.drain_sdl(runtime.engine.pygame, None) == ()


def test_modal_drain_releases_the_opening_key_so_the_next_press_is_fresh():
    """THE press-c-twice bug, pinned at the seam it happens: the combat
    loop stamps the opening keydown (held), a modal's drain swallows
    the keyup while it owns the window, and the NEXT press of that key
    must read fresh — never as a dropped repeat."""
    from src.spacehack.pygame_runtime import PygameContext

    runtime = _input_runtime([
        [_raw_event("down", 40)],   # the press that opens the modal
        [_raw_event("up", 40)],     # released while the modal pumps
        [_raw_event("down", 40)],   # the "first c" that must work
    ])
    context = PygameContext(runtime)

    opened = run(runtime.wait_events())
    assert [(e.kind, e.repeat) for e in opened] == [("keydown", False)]
    assert runtime._held_keys == {"j"}

    # The modal pump drains raw through the helper; the keyup feeds
    # held-state on its way past.
    drained = pygame_runtime.drain_sdl(runtime.engine.pygame, context)
    assert [e.type for e in drained] == [FakeSdlEventQueue.KEYUP]
    assert runtime._held_keys == set()

    fresh = run(runtime.wait_events())
    assert [(e.kind, e.repeat) for e in fresh] == [("keydown", False)]


def test_no_raw_sdl_drains_outside_the_runtime_and_engine():
    """Invariant: every SDL drain flows through the stamping pair —
    pygame_runtime's collector or the engine's events() (which the
    runtime stamps over) — or through drain_sdl, which feeds held
    state. A new raw pygame.event.get() in a pump re-introduces the
    swallowed-keyup bug silently."""
    from pathlib import Path

    src = Path(__file__).resolve().parent.parent / "src" / "spacehack"
    offenders = sorted(
        f"{path.relative_to(src)}:{i + 1}"
        for path in src.rglob("*.py")
        for i, line in enumerate(path.read_text().splitlines())
        if "pygame.event.get()" in line
        and path.relative_to(src).as_posix()
        not in {"pygame_runtime.py", "pygame_engine.py"}
    )
    assert offenders == []
    # The scan bans raw drains only; drain_sdl(pygame, None) would be
    # exactly as buggy — which is why _responsive_sleep's ctx param is
    # REQUIRED (a missed caller TypeErrors instead of regressing).


def test_drain_sdl_probes_the_gamecontext_shape():
    """GameContext passes its .context; the feed must survive the probe
    (a bare PygameContext passes itself)."""
    runtime = _input_runtime([[_raw_event("down", 40)]])
    inner = SimpleNamespace(note_drained=runtime.note_drained)
    game_context = SimpleNamespace(context=inner)

    pygame_runtime.drain_sdl(runtime.engine.pygame, game_context)

    assert runtime._held_keys == {"j"}
