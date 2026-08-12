"""spacehack - a traditional ASCII-art roguelike powered by Pygame.

The package entry point is :mod:`spacehack.__main__` (run with
``python -m spacehack``).
"""

from __future__ import annotations

import os as _os

# SDL3 reads SDL_RENDER_SCALE_QUALITY from the environment when the SDL
# library initialises. Set the hint at package-init time, before the shared
# Pygame runtime opens SDL, so LINEAR scaling takes effect on fractional-DPI
# displays where NEAREST can drop glyph pixels. A user shell export works for
# exactly the same reason.
_os.environ.setdefault("SDL_RENDER_SCALE_QUALITY", "linear")

__version__ = "0.0.1"

__all__ = ["__version__"]
