"""Public dungeon API assembled from focused implementation modules.

The compatibility imports preserve the historical ``spacehack.dungeon``
entry points while keeping layout loading, procedural generation, population,
line of sight, and animation independently maintainable.
"""

from .dungeon_animation import animate_breach
from .dungeon_bsp import generate_dungeon
from .dungeon_fov import DUNGEON_SIGHT_RADIUS, init_fog, reveal_around
from .dungeon_fov import _cast_ray as _cast_ray  # noqa: F401
from .dungeon_fov import _propagate_flags as _propagate_flags  # noqa: F401
from .dungeon_layout import load_layout
from .dungeon_params import DungeonParams
from .dungeon_population import _scatter_squad  # noqa: F401
from .dungeon_population import populate_dungeon

__all__ = [
    "DUNGEON_SIGHT_RADIUS",
    "DungeonParams",
    "animate_breach",
    "generate_dungeon",
    "init_fog",
    "load_layout",
    "populate_dungeon",
    "reveal_around",
]
