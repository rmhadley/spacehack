"""The ``~/.spacehack`` user-data root and its web persistence mirror.

Desktop: the root is a plain directory and the sync layer is a no-op —
byte-identical paths and formats, nothing changes.

Web (emscripten): the emscripten filesystem is memory-only (doc 46
phase-2 probe: ``FS.filesystems.IDBFS`` is not linked, and writes at
every root die with the page), so this module mirrors user-data files
into the browser's IndexedDB through the page-injected ``window.sh46``
shim shipped by the web template. :func:`restore` materializes
persisted files into the in-memory filesystem before the runtime
opens; :func:`sync_persistence` fires one just-written or
just-deleted path out after each mutation.

Two interpreter constraints shape the bridge (both probe-verified
2026-09-13): awaiting a JS promise directly hard-aborts this build,
and a JS callback re-entering python outside the main await chain
(i.e. from a background task) aborts it too. So restore() — which
runs in the main coroutine — uses the callback bridge, while
sync_persistence fires-and-forgets with NO callback at all: the
IndexedDB transaction needs no reply, and python never re-enters.
"""
from __future__ import annotations

import asyncio
from pathlib import Path
import sys

_SHIM_TIMEOUT_S = 10


def spacehack_root() -> Path:
    """The user-data root — same logical path on every target."""
    return Path.home() / ".spacehack"


def _is_web() -> bool:
    return sys.platform == "emscripten"


def _shim():
    """The page-injected IndexedDB shim, or ``None`` when absent."""
    import platform

    return getattr(platform.window, "sh46", None)


async def _shim_call(fn, *args):
    """Invoke one shim method with a python callback and await it.

    Only safe from the main await chain (see module docstring).
    """
    done = asyncio.Event()
    box: list = []

    def cb(value):
        box.append(value)
        done.set()

    fn(*args, cb)
    await asyncio.wait_for(done.wait(), _SHIM_TIMEOUT_S)
    return box[0] if box else None


async def restore() -> None:
    """Materialize persisted user-data files into the in-memory FS.

    Runs before the runtime opens so config loads and save detection
    see the previous session's files. No-op off-web or without a shim.
    A hung shim times out gracefully (ruling: storage breakage never
    blocks play — the session continues without cross-reload
    persistence).
    """
    if not _is_web():
        return
    sh = _shim()
    if sh is None:
        return
    root = spacehack_root()
    try:
        keys = await _shim_call(sh.keys) or ()
        for key in keys:
            text = await _shim_call(sh.get, key)
            if text is None:
                continue
            target = root / key
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(text)
    except asyncio.TimeoutError:
        return


def sync_persistence(path: Path) -> None:
    """Mirror one user-data mutation into durable storage (web only).

    A present file is pushed; an absent one is removed remotely. Paths
    outside the user-data root are not mirrored. Callback-less
    fire-and-forget: the transaction commits in JS with no python
    re-entry, so this is safe to call from synchronous save code.
    """
    if not _is_web():
        return
    sh = _shim()
    if sh is None:
        return
    try:
        rel = path.relative_to(spacehack_root()).as_posix()
    except ValueError:
        return
    if path.is_file():
        sh.put(rel, path.read_text())
    else:
        sh.remove(rel)
