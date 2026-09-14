"""pygbag entry: boot the real game, marking boot progress in the URL hash.

This file runs only inside the browser bundle (``make web`` stages it
next to the ``spacehack`` package). The marks let a failed boot be read
off the page address alone — the error-report channel for the phase-3
fix loop (doc 46).
"""
import spacehack.__main__ as spacehack_main


def _mark(tag: str) -> None:
    """Record a boot milestone in the URL hash (diagnostics only)."""
    try:
        import platform

        mark = getattr(platform.window, "b46mark", None)
        if mark is not None:
            mark(tag)
    except Exception:
        pass


async def main() -> None:
    _mark("b46:main")
    await spacehack_main._amain()
    _mark("b46:done")
