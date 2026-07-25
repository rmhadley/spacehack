"""Ships: purchasable starships at the city space port.

Ships live in two places:

  * Here (``Ship`` + ``SHIPS``) - static catalog entries describing
    what's for sale.
  * :mod:`spacehack.world` - :class:`spacehack.world.Entity` instances
    that point back at a catalog entry via ``entity.ship_id``.

The shop dialog reads the catalog entry from the entity's ``ship_id``;
collision logic uses ``width`` / ``height`` from the entity; rendering
draws only the catalog's ``char`` at the anchor tile of the footprint
(every cell of the footprint gets the same char so a 2x2 cruiser
reads as a tight ``CC`` / ``CC`` cluster). The footprint width /
height intentionally do NOT expand the visible glyph - see
:class:`spacehack.world.Entity` for why.

Each catalog entry also carries ``weapon_slots``, ``module_slots``,
``max_cargo``, and ``max_fuel`` so that the ship-details panel in the
player's hangar shows visually-distinct configurations per class.
"""
from __future__ import annotations

from dataclasses import dataclass, field


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
    max_fuel: int = 100  # tank capacity; consumed by jump gates (see JUMP_FUEL_COST below)
    # Combat stats
    base_power_gen: int = 3       # power generated per turn
    base_shield_max: int = 0      # base shield HP (0 = no shields)
    base_shield_recharge: int = 0 # base shield regen per turn
    base_hull: int = 100         # base hull hit points


SHIPS: tuple[Ship, ...] = (
    Ship(
        id="scout",
        name="Scout",
        char="s",
        fg=(130, 220, 255),                                          # bright sky-blue (scout is greyscale-brightest of the 3)
        price=80,
        width=1, height=1,
        description=(
            "A small, fast scoutship - quick on cargo runs, lightly armed."
        ),
        weapon_slots=6,
        module_slots=1,
        max_cargo=40,
        max_fuel=100,
        base_power_gen=3,
        base_shield_max=0,
        base_hull=20,
    ),
    Ship(
        id="hauler",
        name="Hauler",
        char="H",
        fg=(140, 210, 140),                                          # medium saturated green (mean-luma ~165, matches cruiser)
        price=140,
        width=2, height=1,
        description=(
            "A long-range cargo hauler with roomy cargo bays."
        ),
        weapon_slots=2,
        module_slots=2,
        max_cargo=120,
        max_fuel=80,
        base_power_gen=4,
        base_shield_max=10,
        base_hull=30,
    ),
    Ship(
        id="cruiser",
        name="Cruiser",
        char="C",
        fg=(235, 130, 130),                                          # saturated red - mean-luma ~165, matches hauler for colorblind contrast
        price=240,
        width=2, height=2,
        description=(
            "A well-armed cruiser - capable in a fight, slow in dock."
        ),
        weapon_slots=6,
        module_slots=4,
        max_cargo=40,
        max_fuel=60,
        base_power_gen=5,
        base_shield_max=20,
        base_hull=50,
    ),
)


_BY_ID: dict[str, Ship] = {s.id: s for s in SHIPS}


def find_ship(ship_id: str) -> Ship:
    """Look up a :class:`Ship` catalog entry by id.

    Raises :class:`KeyError` if no ship has that id - this matches the
    look-up-by-id contract used elsewhere in the project (see
    :func:`spacehack.character.find_species`).
    """
    try:
        return _BY_ID[ship_id]
    except KeyError:
        raise KeyError(f"unknown ship id: {ship_id!r}") from None


def total_ammo_cargo(weapons: tuple[str, ...]) -> int:
    """Cargo cells consumed by ammo for the supplied weapon list.

    Sums ``weapon.cargo_per_round * weapon.ammo_capacity`` across
    missile weapons; energy weapons consume 0 cargo. Used to seed
    :attr:`OwnedShip.cargo_used` so the cargo HUD reflects the
    starting missile loadout. Imported function-level so this
    module's own imports are kept dependency-free (and to avoid a
    circular import if any future weapon module ever needs to
    reverse-look-up ship records).
    """
    from .data.weapons import find_weapon as _fw
    total = 0
    for wid in weapons:
        try:
            ws = _fw(wid)
        except KeyError:
            continue
        if ws.slot_type == "missile":
            total += ws.cargo_per_round * ws.ammo_capacity
    return total


@dataclass
class OwnedShip:
    """Mutable state of a ship the player owns.

    Lives next to the :class:`Ship` catalog because the player
    references a catalog entry by ``ship_id`` and reads the cap fields
    (weapon_slots / module_slots / max_cargo / max_fuel) directly from
    it - :class:`OwnedShip` only stores the per-ship mutable variables:
    cargo in use, current hull damage, current fuel, and the named
    weapons / modules attached. Empty-tuple defaults mean newly-bought
    ships start with no equipment attached but a full tank (set by the
    buy-ship flow at the space port).

    The dataclass is non-frozen so the player's stats (cargo, hull,
    weapons, modules, fuel) can mutate over time without needing a
    wrapper type or ``dataclasses.replace`` everywhere.
    """
    ship_id: str
    hull_damage_pct: int = 0
    weapons: tuple[str, ...] = field(default_factory=tuple)
    modules: tuple[str, ...] = field(default_factory=tuple)
    fuel: int = 0  # current fuel; reset to ship.max_fuel by the buy-ship flow
    cargo_used: int = field(default=0, init=False)
    # ``cargo_used`` is a *derived* attribute: every construction
    # path reruns :func:`total_ammo_cargo` over ``self.weapons`` so
    # the cargo HUD readout and the actual missile count can never
    # drift. ``init=False`` prevents callers from passing it (the
    # buy-ship flow used to do this redundantly) at construction
    # time. The cargo value is MUTATED at runtime by:
    #   * :func:`spacehack.mission.try_accept_mission` — adds
    #     ``mission.required_cargo_size``
    #   * :func:`spacehack.mission.abort_mission` — subtracts
    #     ``mission.required_cargo_size``
    #   * :func:`spacehack.mission.complete_mission` — subtracts
    #     ``mission.required_cargo_size``
    #   * the player fire handler in :mod:`spacehack.combat` —
    #     decrements by ``ammo_per_shot * cargo_per_round`` on each
    #     missile shot
    # so the construction-time value is only the starting point.
    # Module-level ``total_ammo_cargo`` is forward-referenced inside
    # the body and does its own deferred import, so the ordering is
    # safe regardless of how :class:`OwnedShip` is built.

    def __post_init__(self) -> None:
        self.cargo_used = total_ammo_cargo(self.weapons)


# Fuel economics constants. JUMP_FUEL_COST is consumed by the
# gate-bump dispatcher before _jump_to_system fires. FUEL_COST_PER_UNIT
# is the gold price per unit the player pays at the hangar-menu
# Refuel option. Both are intentionally easy to retune from one place.
JUMP_FUEL_COST: int = 10
FUEL_COST_PER_UNIT: int = 1
