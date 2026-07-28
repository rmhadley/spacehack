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

    ``cargo_used`` is a computed :func:`property` that sums
    ``cargo_ammo`` + ``mission_reserved`` + trade inventory volume,
    so callers read it the same way as before but can no longer
    assign to it directly — assign to the sub-fields instead.

    The dataclass is non-frozen so the player's stats (cargo, hull,
    weapons, modules, fuel) can mutate over time without needing a
    wrapper type or ``dataclasses.replace`` everywhere.
    """
    ship_id: str
    hull_damage_pct: int = 0
    weapons: tuple[str, ...] = field(default_factory=tuple)
    modules: tuple[str, ...] = field(default_factory=tuple)
    fuel: int = 0  # current fuel; reset to ship.max_fuel by the buy-ship flow
    cargo_ammo: int = 0           # cargo consumed by missile ammo (mutated by combat)
    mission_reserved: int = 0     # cargo reserved by active delivery missions
    inventory: dict[str, int] = field(default_factory=dict)  # trade_good_id -> crate count

    @property
    def cargo_used(self) -> int:
        """Total cargo used = ammo + mission reservations + trade goods."""
        from .data.trade_goods import find_trade_good as _ftg
        trade = sum(
            qty * _ftg(gid).volume
            for gid, qty in self.inventory.items()
        )
        return self.cargo_ammo + self.mission_reserved + trade

    def __post_init__(self) -> None:
        self.cargo_ammo = total_ammo_cargo(self.weapons)


# ---------------------------------------------------------------------------
# Ship mutation helpers (used by the mechanic loadout UI)
# ---------------------------------------------------------------------------


def _install_weapon(owned: OwnedShip, weapon_id: str, ship_spec: Ship) -> bool:
    """Install ``weapon_id`` into the first empty weapon slot.

    Returns True on success. Recalculates ``cargo_ammo`` if the
    weapon is a missile type (the caller must also sync).
    Returns False if all weapon slots are full.
    """
    if len(owned.weapons) >= ship_spec.weapon_slots:
        return False
    owned.weapons = owned.weapons + (weapon_id,)
    owned.cargo_ammo = total_ammo_cargo(owned.weapons)
    return True


def _remove_weapon(owned: OwnedShip, index: int) -> tuple[str, ...]:
    """Remove the weapon at ``index`` from the owned ship.

    Returns the new weapons tuple (caller must assign back).
    Recalculates ``cargo_ammo``. No-op if the index is out of
    range (returns the current tuple unchanged).
    """
    if index < 0 or index >= len(owned.weapons):
        return owned.weapons
    new = owned.weapons[:index] + owned.weapons[index + 1:]
    owned.weapons = new
    owned.cargo_ammo = total_ammo_cargo(owned.weapons)
    return new


def _install_module(owned: OwnedShip, module_id: str, ship_spec: Ship) -> bool:
    """Install ``module_id`` into the first empty module slot.

    Returns True on success. Returns False if all module slots
    are full.
    """
    if len(owned.modules) >= ship_spec.module_slots:
        return False
    owned.modules = owned.modules + (module_id,)
    return True


def _remove_module(owned: OwnedShip, index: int) -> tuple[str, ...]:
    """Remove the module at ``index`` from the owned ship.

    Returns the new modules tuple (caller must assign back).
    No-op if the index is out of range.
    """
    if index < 0 or index >= len(owned.modules):
        return owned.modules
    new = owned.modules[:index] + owned.modules[index + 1:]
    owned.modules = new
    return new


def _sell_price(item_type: str, item_id: str) -> int:
    """Sell-back value for an installed part: 50% of buy price.

    ``item_type`` is ``"weapon"`` or ``"module"``. Returns at
    least 1 credit.
    """
    if item_type == "weapon":
        from .data.weapons import find_weapon as _fw
        try:
            spec = _fw(item_id)
        except KeyError:
            return 0
        return max(1, spec.price // 2)
    elif item_type == "module":
        from .data.modules import find_module as _fm
        try:
            spec = _fm(item_id)
        except KeyError:
            return 0
        return max(1, spec.price // 2)
    return 0


def _find_weapon_slots(owned: OwnedShip, ship_spec: Ship) -> list[tuple[str | None, int]]:
    """Build a list of all weapon slots with their installed state.

    Returns ``[(weapon_id or None, slot_index), ...]`` so the UI
    can render each slot row. Empty slots show as ``(None, index)``.
    """
    result: list[tuple[str | None, int]] = []
    for i in range(ship_spec.weapon_slots):
        if i < len(owned.weapons):
            result.append((owned.weapons[i], i))
        else:
            result.append((None, i))
    return result


def _find_module_slots(owned: OwnedShip, ship_spec: Ship) -> list[tuple[str | None, int]]:
    """Build a list of all module slots with their installed state.

    Returns ``[(module_id or None, slot_index), ...]`` so the UI
    can render each slot row. Empty slots show as ``(None, index)``.
    """
    result: list[tuple[str | None, int]] = []
    for i in range(ship_spec.module_slots):
        if i < len(owned.modules):
            result.append((owned.modules[i], i))
        else:
            result.append((None, i))
    return result


# Fuel economics constants. JUMP_FUEL_COST is consumed by the
# gate-bump dispatcher before _jump_to_system fires. FUEL_COST_PER_UNIT
# is the credits price per unit the player pays at the hangar-menu
# Refuel option. Both are intentionally easy to retune from one place.
JUMP_FUEL_COST: int = 10
FUEL_COST_PER_UNIT: int = 1
