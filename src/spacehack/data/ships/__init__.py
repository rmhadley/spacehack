"""Player ship catalog — frozen dataclass + lookup registry.

Migrated from ``ship.py`` to ``data/ships/`` following the data-first
pattern established by ``data/weapons/``, ``data/modules/``, and
``data/npc_ships/``.

The ``Ship`` dataclass and ``find_ship()``/``list_ships()`` helpers
live here; mutating owned-ship state (``OwnedShip``, install/remove
helpers, fuel constants) stays in ``ship.py``.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Ship:
    """A purchasable starship, as listed in the space-port catalog."""
    id: str
    name: str
    char: str
    fg: tuple[int, int, int]
    price: int
    width: int       # footprint width in tiles; >= 1; collision only
    height: int      # footprint height in tiles; >= 1; collision only
    description: str
    weapon_slots: int   # how many weapons this hull can mount
    module_slots: int   # how many ship modules this hull can install
    max_cargo: int      # cargo capacity of the hull
    max_fuel: int = 100  # tank capacity; consumed by jump gates
    # Travel speed — moves per day in overworld space travel.
    # tick_move() divides move_counter by this to advance the clock.
    # Fast ships (scout: 14) cover more ground per day; slow ships
    # (freighter: 6) take longer per cell.
    speed: int = 10
    # Combat stats
    base_power_gen: int = 3       # power generated per turn
    base_shield_max: int = 0      # base shield HP (0 = no shields)
    base_shield_recharge: int = 0 # base shield regen per turn
    base_hull: int = 100         # base hull hit points
    # Starting loadout when purchased — empty tuples = no free equipment.
    start_weapons: tuple[str, ...] = ()
    start_modules: tuple[str, ...] = ()


from .core import SHIPS  # noqa: E402

_BY_ID: dict[str, Ship] = {s.id: s for s in SHIPS}


def find_ship(ship_id: str) -> Ship:
    """Look up a :class:`Ship` catalog entry by id.

    Raises :class:`KeyError` if no ship has that id.
    """
    try:
        return _BY_ID[ship_id]
    except KeyError:
        raise KeyError(f"unknown ship id: {ship_id!r}") from None


def list_ships() -> list[Ship]:
    """Return all ship catalog entries, ordered by id."""
    return sorted(_BY_ID.values(), key=lambda s: s.id)
