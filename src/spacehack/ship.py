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


@dataclass(frozen=True)
class StoredEquipment:
    """One ship weapon or module held in the player's global storage."""

    item_type: str
    item_id: str
    ammo: int | None = None


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


def _seed_missile_ammo(owned: OwnedShip) -> None:
    """Top off :attr:`OwnedShip.weapon_ammo` for installed missiles.

    Every installed missile weapon with no recorded ammo gets a full
    magazine. Weapons already tracked keep their remaining rounds
    (persistent ammo survives save/load and combat). Energy weapons
    are never added (-1 capacity means infinite).
    """
    from .data.weapons import find_weapon as _fw
    for i, wid in enumerate(owned.weapons):
        try:
            ws = _fw(wid)
        except KeyError:
            continue
        if ws.slot_type == "missile" and i not in owned.weapon_ammo:
            owned.weapon_ammo[i] = ws.ammo_capacity


def buy_ammo(
    owned: OwnedShip,
    slot_index: int,
    rounds: int,
    credits: int,
) -> tuple[bool, int, str]:
    """Buy ``rounds`` of ammo for the missile launcher in ``slot_index``.

    Mutates ``owned.weapon_ammo`` (keyed by slot) and returns
    ``(ok, cost, reason)``. Caps rounds at magazine capacity minus
    current, and clamps to what the player can afford. ``credits`` is
    the player's current balance (read-only — the caller deducts the
    returned cost so the credits mutation stays with the caller).
    """
    from .data.weapons import find_weapon as _fw
    if not (0 <= slot_index < len(owned.weapons)):
        return False, 0, "Unknown weapon slot."
    weapon_id = owned.weapons[slot_index]
    try:
        ws = _fw(weapon_id)
    except KeyError:
        return False, 0, "Unknown weapon."
    if ws.slot_type != "missile":
        return False, 0, f"{ws.name} doesn't use ammo."
    current = owned.weapon_ammo.get(slot_index, 0)
    room = ws.ammo_capacity - current
    if room <= 0:
        return False, 0, f"{ws.name} magazine is already full."
    if ws.ammo_price <= 0:
        return False, 0, f"{ws.name} ammo isn't sold here."
    buy = min(rounds, room)
    affordable = credits // ws.ammo_price
    buy = min(buy, affordable)  # clamp to what the player can actually pay
    if buy <= 0:
        return False, 0, f"Need {ws.ammo_price}$ for 1 round."
    cost = buy * ws.ammo_price
    owned.weapon_ammo[slot_index] = current + buy
    return True, cost, ""


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
    # Persistent missile ammo: weapon SLOT index -> rounds remaining.
    # Keyed by installed slot (not weapon id) so two launchers of the
    # same type keep independent magazines. Spent rounds stay spent after
    # combat until rebought at the mechanic. Seeded to a full magazine
    # for every installed missile weapon (see __post_init__) so old
    # saves / newly bought ships start topped off.
    weapon_ammo: dict[int, int] = field(default_factory=dict)

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
        _seed_missile_ammo(self)


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


def hull_integrity_pct(owned: OwnedShip) -> int:
    """Return hull integrity as a percentage: 100% pristine, 0% destroyed.

    The inverse of :attr:`OwnedShip.hull_damage_pct` — combat and the
    mechanic write damage; repair pricing reads integrity.
    Status displays should show :func:`hull_cur_max` (cur/max points)
    instead of a percentage.
    """
    return max(0, min(100, 100 - getattr(owned, 'hull_damage_pct', 0)))


def hull_cur_max(owned: OwnedShip, ship_spec: Ship) -> tuple[int, int]:
    """Return ``(current, max)`` hull for ``owned`` in hull points.

    Mirrors the combat hull model exactly — ``base_hull`` plus the sum
    of ``max_hull_bonus`` from equipped modules, damage applied as a
    percentage of that max — so every status display (HUD, hangar,
    mechanic, cargo) reads the same numbers combat does. Pure.
    """
    from .data.modules import find_module as _fms

    _max = getattr(ship_spec, 'base_hull', 100)
    for _mod_id in getattr(owned, 'modules', ()) or ():
        if not _mod_id:
            continue
        try:
            _max += _fms(_mod_id).max_hull_bonus
        except KeyError:
            pass
    _dmg = getattr(owned, 'hull_damage_pct', 0)
    _cur = max(1, _max * (100 - _dmg) // 100)
    return _cur, _max


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
    weapon is a missile type (the caller must also sync) and seeds
    a FRESH full magazine — a newly installed missile launcher
    never inherits stale ammo left behind by a previously sold
    launcher of the same type. Returns False if all weapon slots
    are full.
    """
    if len(owned.weapons) >= ship_spec.weapon_slots:
        return False
    owned.weapons = owned.weapons + (weapon_id,)
    owned.cargo_ammo = total_ammo_cargo(owned.weapons)
    from .data.weapons import find_weapon as _fw
    try:
        _ws = _fw(weapon_id)
    except KeyError:
        _ws = None
    if _ws is not None and _ws.slot_type == "missile":
        # New launcher lives in the last slot; give it a fresh magazine.
        owned.weapon_ammo[len(owned.weapons) - 1] = _ws.ammo_capacity
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
    # Re-index ammo: slots above the removed one shift down by one so
    # each launcher's magazine stays attached to the right slot.
    _ammo: dict[int, int] = {}
    for _k, _v in owned.weapon_ammo.items():
        if _k < index:
            _ammo[_k] = _v
        elif _k > index:
            _ammo[_k - 1] = _v
        # _k == index: the sold weapon's magazine goes with it.
    owned.weapon_ammo = _ammo
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


def can_install_stored_equipment(
    owned: OwnedShip,
    stored: StoredEquipment,
    ship_spec: Ship,
) -> bool:
    """Return whether ``stored`` fits an available slot on ``owned``.

    Invalid catalog ids and unknown storage item types are rejected without
    mutating either the ship or storage. Module slot type is represented by
    the stored item type; the catalog lookup verifies the module itself.
    """
    if stored.item_type == "weapon":
        try:
            from .data.weapons import find_weapon as _fw
            _fw(stored.item_id)
        except KeyError:
            return False
        return len(owned.weapons) < ship_spec.weapon_slots
    if stored.item_type == "module":
        try:
            from .data.modules import find_module as _fm
            _fm(stored.item_id)
        except KeyError:
            return False
        return len(owned.modules) < ship_spec.module_slots
    return False


def store_weapon(
    owned: OwnedShip,
    storage: list[StoredEquipment],
    slot_index: int,
) -> bool:
    """Move one installed weapon into storage, preserving missile ammo."""
    if not (0 <= slot_index < len(owned.weapons)):
        return False
    weapon_id = owned.weapons[slot_index]
    ammo: int | None = None
    try:
        from .data.weapons import find_weapon as _fw
        weapon = _fw(weapon_id)
    except KeyError:
        return False
    if weapon.slot_type == "missile":
        ammo = owned.weapon_ammo.get(slot_index, weapon.ammo_capacity)
    storage.append(StoredEquipment("weapon", weapon_id, ammo))
    _remove_weapon(owned, slot_index)
    return True


def store_module(
    owned: OwnedShip,
    storage: list[StoredEquipment],
    slot_index: int,
) -> bool:
    """Move one installed module into storage."""
    if not (0 <= slot_index < len(owned.modules)):
        return False
    module_id = owned.modules[slot_index]
    try:
        from .data.modules import find_module as _fm
        _fm(module_id)
    except KeyError:
        return False
    storage.append(StoredEquipment("module", module_id))
    _remove_module(owned, slot_index)
    return True


def install_stored_equipment(
    owned: OwnedShip,
    storage: list[StoredEquipment],
    storage_index: int,
    ship_spec: Ship,
) -> bool:
    """Install one stored part and remove it from storage on success."""
    if not (0 <= storage_index < len(storage)):
        return False
    stored = storage[storage_index]
    if not can_install_stored_equipment(owned, stored, ship_spec):
        return False
    if stored.item_type == "weapon":
        if not _install_weapon(owned, stored.item_id, ship_spec):
            return False
        slot_index = len(owned.weapons) - 1
        if stored.ammo is not None:
            from .data.weapons import find_weapon as _fw
            capacity = _fw(stored.item_id).ammo_capacity
            owned.weapon_ammo[slot_index] = max(0, min(stored.ammo, capacity))
    else:
        if not _install_module(owned, stored.item_id, ship_spec):
            return False
    storage.pop(storage_index)
    return True


def move_installed_equipment_to_storage(
    owned: OwnedShip,
    storage: list[StoredEquipment],
) -> None:
    """Move every installed weapon and module into storage.

    This is the shared transfer primitive for ship upgrades and a future
    explicit "store all" action. The loop always removes slot zero so the
    existing weapon-ammo re-indexing remains the single source of truth.
    All catalog IDs are validated before the first mutation so a corrupt
    legacy loadout cannot produce a partial transfer.
    """
    from .data.modules import find_module as _fm
    from .data.weapons import find_weapon as _fw
    try:
        for weapon_id in owned.weapons:
            _fw(weapon_id)
        for module_id in owned.modules:
            _fm(module_id)
    except KeyError as exc:
        raise ValueError("Cannot store an unknown installed item") from exc
    while owned.weapons:
        if not store_weapon(owned, storage, 0):
            raise ValueError("Cannot store an installed weapon")
    while owned.modules:
        if not store_module(owned, storage, 0):
            raise ValueError("Cannot store an installed module")


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
