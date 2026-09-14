# /// script
# requires-python = ">=3.12"
# dependencies = ["pygame-ce"]
# ///
"""pygbag entry: boot the real game, marking boot progress as we go.

Runs only inside the browser bundle (``make web`` stages it next to
the ``spacehack`` package). Milestones print to the xterm (python
stdout) — the error-report channel for the phase-3 fix loop: paste
the terminal text verbatim on any failure (doc 46).

Both the PEP 723 header and the trailing ``asyncio.run`` are
load-bearing: the runtime resolves packages from the header
(pygame-ce -> the pinned wasm wheel), and pygbag's aio layer
intercepts ``asyncio.run`` to schedule ``main()`` on its green
loop — a bare ``async def main`` is imported but never started.
"""
import asyncio
import sys

import spacehack.__main__ as spacehack_main


async def main() -> None:
    print("b46:main")
    try:
        await spacehack_main._amain()
    except Exception:
        import traceback

        traceback.print_exc(file=sys.stdout)  # stdout reaches the xterm
        raise
    print("b46:done")


asyncio.run(main())

