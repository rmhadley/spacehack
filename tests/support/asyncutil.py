"""Bridge for doc 46's one-async-path: drive or pass through.

``run`` lets sync tests call presentation-flow functions that are
coroutines under the unified async loop while remaining no-ops for
sync fakes.  ``as_async`` turns a sync stub into a coroutine function
so it can stand in for an async seam at ``await`` sites.
"""
import asyncio


def run(value):
    """Drive ``value`` if it is a coroutine, else return it unchanged."""
    return asyncio.run(value) if asyncio.iscoroutine(value) else value


def as_async(fn):
    """Return an async wrapper around a sync (or async) stub."""
    async def wrapper(*args, **kwargs):
        result = fn(*args, **kwargs)
        if asyncio.iscoroutine(result):
            return await result
        return result
    return wrapper
