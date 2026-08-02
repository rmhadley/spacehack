"""Ships: purchasable starships and owned-ship state.

The static ship catalog (``Ship`` dataclass + ``find_ship()``) now
lives in ``data/ships/`` for data-first consistency with the rest
of the project. This module keeps everything mutating or stateful:

* ``OwnedShip`` — mutable player-owned ship state.
* ``total_ammo_cargo()`` — ammo volume calculation.
* Ship mutation helpers for the mechanic loadout UI.
* Fuel-economics constants.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from .data.ships import Ship, find_ship


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
    it — :class:`OwnedShip` only stores the per-ship mutable variables:
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
    # Player-facing name. The free starting ship rolls a colorful name
    # from data/ships/core.STARTER_NAMES at new-game setup; bought ships
    # leave this None and fall back to the catalog name. Stored here so
    # the name survives save/load (see saveload.OwnedShip round-trip).
    display_name: str | None = None
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
# Effective stat helpers (used by mechanic UI, trade, HUD, missions)
# ---------------------------------------------------------------------------


def ship_display_name(owned: OwnedShip | None) -> str:
    """Player-facing ship name: the rolled display name, else the
    catalog class name.

    The free starting ship gets a colorful per-run name (rolled from
    ``data/ships/core.STARTER_NAMES`` at new-game setup and stored on
    :attr:`OwnedShip.display_name`). Bought ships leave ``display_name``
    ``None`` and read their class name from the catalog. All player-
    facing UI (HUD, hangar menu, cargo screen, loadout) should call
    this instead of reading ``Ship.name`` directly so the rolled name
    is honoured everywhere. ``None`` (no ship) falls back to "Ship".
    """
    if owned is None:
        return "Ship"
    if owned.display_name:
        return owned.display_name
    return find_ship(owned.ship_id).name


def effective_speed(ship_spec: Ship, owned: OwnedShip) -> int:
    """Sum base ship speed + all module speed_bonuses.

    This is the moves-per-day value used by tick_move() to
    determine when to advance the game clock.
    """
    from .data.modules import find_module as _fm
    total = ship_spec.speed
    for mid in getattr(owned, 'modules', ()) or ():
        try:
            total += _fm(mid).speed_bonus
        except KeyError:
            pass
    return max(1, total)


def effective_max_cargo(ship_spec: Ship, owned: OwnedShip) -> int:
    """Sum base max cargo + all module cargo_bonuses."""
    from .data.modules import find_module as _fm
    total = ship_spec.max_cargo
    for mid in getattr(owned, 'modules', ()) or ():
        try:
            total += _fm(mid).cargo_bonus
        except KeyError:
            pass
    return max(0, total)


def smuggler_hold_capacity(owned: OwnedShip) -> int:
    """Sum of installed modules' smuggler_cargo bonuses.

    This is the volume of contraband the player's ship can conceal
    from militia scans. 0 with no smuggler's hold installed.
    """
    from .data.modules import find_module as _fm
    total = 0
    for mid in getattr(owned, 'modules', ()) or ():
        try:
            total += _fm(mid).smuggler_cargo
        except KeyError:
            pass
    return total


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
