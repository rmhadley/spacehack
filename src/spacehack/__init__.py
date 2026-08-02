"""spacehack - a traditional ASCII-art roguelike built on python-tcod.

The actual libtcod wiring lives in :mod:`spacehack.engine`. The package
entry point is :mod:`spacehack.__main__` (run with ``python -m spacehack``).
"""

from __future__ import annotations

import os as _os

# SDL3 (bundled by python-tcod 21.x) reads SDL_RENDER_SCALE_QUALITY from the
# environment when the SDL library initialises — which happens during the
# first ``import tcod.*``, i.e. BEFORE ``engine.open_terminal()`` runs its own
# setdefault (that one is therefore a no-op; verified empirically with
# SDL_GetHint). Setting the hint here, at package-init time and before any
# tcod import, is what makes LINEAR scaling actually take effect — the fix
# for fractional-DPI displays where NEAREST drops glyph pixels. A user shell
# export works for exactly the same reason.
_os.environ.setdefault("SDL_RENDER_SCALE_QUALITY", "linear")

__version__ = "0.0.1"

__all__ = ["__version__"]
