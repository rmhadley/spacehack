"""Dev-mode overrides for playtesting.

When the ``SPACEHACK_DEV`` environment variable is set, the player
starts with a super-powered frigate, maxed modules, 999,999 credits,
the strongest ground weapon equipped, a pack of T4 weapons in the
expedition backpack, and the best available armor in every slot. Call
:func:`apply_dev_overrides` and :func:`apply_dev_ground_loadout` during
new-game setup so the overrides are in place before the game loop starts.

Extracted from ``__main__.py`` to keep the entry point clean and
make dev-mode easy to extend (debug overlay, god-mode toggle, etc.)
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from . import ground_equipment
from . import ship as ship_module
from . import ui
from . import pygame_ui
from .game_context import GameContext
from .input_helpers import Outcome
from .pygame_runtime import PygameContext
from .data.ground_armor import list_ground_armor
from .data.ground_weapons import find_ground_weapon, list_ground_weapons


_DEV_FACTION_OPTIONS = (
    ("militia", "Militia", "Order, procedure, and a sanctioned breach."),
    ("merchants", "Merchants", "Routes, leverage, and a quiet way through."),
    ("bar", "Free Captains", "Rumors, favors, and the outlaw route."),
    ("lab", "Research Lab", "Evidence, analysis, and dangerous questions."),
)
_DEV_FACTION_LABELS = {option[0]: option[1] for option in _DEV_FACTION_OPTIONS}


def main_quest_faction_menu() -> ui.MenuScreen:
    """Return the faction picker used by the Act 0 dev shortcut."""
    return ui.MenuScreen(
        title="Choose Act 0 Faction",
        instruction=pygame_ui.modal_hint(
            pygame_ui.NAV_HINT, "ENTER select", "ESC cancel",
        ),
        options=tuple(
            (faction_id, label)
            for faction_id, label, _ in _DEV_FACTION_OPTIONS
        ),
        descriptions={
            faction_id: description
            for faction_id, _, description in _DEV_FACTION_OPTIONS
        },
    )


def _dev_faction_label(faction_id: str) -> str:
    """Return the display label for a registered developer faction."""
    return _DEV_FACTION_LABELS[faction_id]


def _pygame_faction_frames(menu: ui.MenuScreen):
    """Build the shared fixed-layout frames for the dev faction picker."""
    from . import pygame_menu

    items = tuple(
        pygame_menu.MenuItem(
            label=label,
            description=menu.descriptions.get(faction_id, ""),
            action=faction_id,
        )
        for faction_id, label in menu.options
    )
    return tuple(
        pygame_menu.MenuFrame(
            title=menu.title.upper(),
            body="Choose the faction whose Act 0 path you want to test.",
            items=items,
            hints=(menu.instruction,),
            selected=selected,
        )
        for selected in range(len(items))
    )


def _run_pygame_menu_pick(
    context, frames, caption: str, valid_ids: set[str],
) -> tuple[Outcome, str | None] | None:
    """Run a dev picker modal; return (Outcome, action) or None to fall back."""
    from . import pygame_menu

    if not frames:
        return None
    while True:
        outcome, action, _selected = pygame_menu.run_for_context(
            context, frames, caption=caption,
        )
        if outcome == "GUIDE":
            continue
        if outcome == "QUIT":
            return Outcome.QUIT, None
        if outcome == "BACK":
            return Outcome.BACK, None
        if outcome == "SELECT" and action in valid_ids:
            return Outcome.CONFIRM, action
        return None


def _run_pygame_faction_pick(
    context, menu: ui.MenuScreen,
) -> tuple[Outcome, str | None] | None:
    """Run the dev faction picker in Pygame, or return None for fallback."""
    result = _run_pygame_menu_pick(
        context, _pygame_faction_frames(menu),
        caption="spacehack - choose act 0 faction",
        valid_ids={faction_id for faction_id, _label in menu.options},
    )
    return result


def choose_main_quest_faction(context) -> tuple[Outcome, str | None]:
    """Run the Act 0 faction picker in the shared Pygame window."""
    result = _run_pygame_faction_pick(context, main_quest_faction_menu())
    if result is None:
        raise RuntimeError("Developer faction picker returned no outcome")
    return result


def city_teleport_options() -> tuple[tuple[str, str], ...]:
    """``(planet_id, "City — System")`` for every landable port city,
    sorted by label so the picker reads as one alphabetical list."""
    from .data.planets import has_landable_port, list_planet_specs
    from .data.solar_systems import system_for_planet

    options = [
        (spec.id, f"{spec.name} - {system_for_planet(spec.id).name}")
        for spec in list_planet_specs()
        if has_landable_port(spec.id)
    ]
    return tuple(sorted(options, key=lambda option: option[1]))


def city_teleport_menu() -> ui.MenuScreen:
    """Return the city picker used by the dev teleport shortcut."""
    options = city_teleport_options()
    return ui.MenuScreen(
        title="Teleport to City",
        instruction=pygame_ui.modal_hint(
            pygame_ui.NAV_HINT, "ENTER select", "ESC cancel",
        ),
        options=options,
        descriptions={planet_id: "" for planet_id, _label in options},
    )


def _pygame_teleport_frames(menu: ui.MenuScreen):
    """Build the shared fixed-layout frames for the city teleport picker."""
    from . import pygame_menu

    items = tuple(
        pygame_menu.MenuItem(label=label, description="", action=planet_id)
        for planet_id, label in menu.options
    )
    return tuple(
        pygame_menu.MenuFrame(
            title=menu.title.upper(),
            body="Land on any port city for playtesting.",
            items=items,
            hints=(menu.instruction,),
            selected=selected,
        )
        for selected in range(len(items))
    )


def choose_city_teleport(context) -> tuple[Outcome, str | None]:
    """Run the city teleport picker in the shared Pygame window."""
    menu = city_teleport_menu()
    result = _run_pygame_menu_pick(
        context, _pygame_teleport_frames(menu),
        caption="spacehack - teleport to city",
        valid_ids={planet_id for planet_id, _label in menu.options},
    )
    if result is None:
        return Outcome.BACK, None
    return result


def _quicksave_path() -> Path:
    """Full path to the dev-mode quicksave checkpoint file."""
    return Path.home() / ".spacehack" / "saves" / "quicksave.json"


def quick_save(
    ctx: GameContext,
    *,
    mode: str = "city",
    city_id: str = "earth",
    system_id: str = "sol",
    space_player_pos: tuple[int, int] | None = None,
) -> None:
    """Write the dev-mode quicksave checkpoint (same payload as autosave).

    Unlike the autosave, the quicksave is *not* deleted on load or on
    death — it is a reusable dev checkpoint. Each call overwrites it.
    """
    from .saveload import save_game as _save_game
    _save_game(
        ctx,
        mode=mode,
        city_id=city_id,
        system_id=system_id,
        space_player_pos=space_player_pos,
        path=_quicksave_path(),
    )


def quick_load(context: PygameContext) -> GameContext | None:
    """Load the dev-mode quicksave checkpoint, or None if absent/corrupt."""
    from .saveload import load_game as _load_game
    return _load_game(context, path=_quicksave_path())


_GROUND_ARMOR_SLOTS = ("head", "body", "hands", "legs", "feet")


def _best_ground_armor() -> dict[str, str]:
    """Return the strongest registered armor id for every armor slot."""
    _by_slot: dict[str, list] = {slot: [] for slot in _GROUND_ARMOR_SLOTS}
    for _armor in list_ground_armor():
        if _armor.slot in _by_slot:
            _by_slot[_armor.slot].append(_armor)
    return {
        _slot: max(
            _items,
            key=lambda _item: (_item.defense, _item.tech_level, _item.price),
        ).id
        for _slot, _items in _by_slot.items()
        if _items
    }


def _best_ground_weapon() -> str:
    """Return the strongest registered ground weapon id (highest damage)."""
    return max(
        list_ground_weapons(),
        key=lambda _w: (_w.damage, _w.tech_level, _w.price),
    ).id


# T4 weapons seeded into the expedition backpack so the whole tier can
# be playtested without hunting armories. The rocket launcher (the
# strongest weapon) is equipped directly; the rest ride in the pack.
_DEV_PACK_WEAPONS: tuple[str, ...] = (
    "plasma_caster", "railgun", "power_fist", "power_fist",
    "ion_blaster", "mono_blade",
)


def _dev_ground_loadout() -> tuple[list[ground_equipment.GroundWeaponInstance], dict[str, str]]:
    """Return the standard developer starting ground loadout."""
    return [ground_equipment.weapon_instance(_best_ground_weapon())], _best_ground_armor()


def apply_dev_ground_loadout(ctx) -> None:
    """Equip developer ground weapons, armor, and pack when dev mode is enabled."""
    import os as _os

    if not _os.environ.get("SPACEHACK_DEV"):
        return
    ctx.equipped_ground_weapons, ctx.equipped_ground_armor = _dev_ground_loadout()
    ctx.ground_expedition_inventory = [
        ground_equipment.StoredGroundEquipment("weapon", _wid)
        for _wid in _DEV_PACK_WEAPONS
    ]
    # The pack holds all 6 T4 weapons; capacity is 4 + (strength - 10) // 10,
    # so raise strength to 30 so all 6 fit without breaking swaps.
    if ctx.ground_stats.strength < 30:
        ctx.ground_stats.strength = 30
    _best_name = find_ground_weapon(_best_ground_weapon()).name
    ctx.log.add(f"[DEV MODE] {_best_name} equipped + T4 pack + best armor.")


def advance_main_quest(ctx, faction_id: str) -> None:
    """Put Act 0 immediately before the Mars door-opening interaction.

    ``faction_id`` mirrors the normal Act 0 lock-in choice, so post-prison
    dialogue and faction-gated objectives behave like a real run. The
    caller must gate this action behind ``SPACEHACK_DEV``.
    """
    if faction_id not in _DEV_FACTION_LABELS:
        raise ValueError(f"Unknown developer faction: {faction_id}")
    if ctx.main_quest_chain and ctx.main_quest_chain != faction_id:
        raise ValueError("Developer faction cannot replace an existing quest chain")
    _progress = ctx.main_quest_progress
    ctx.main_quest_chain = faction_id
    ctx.main_quest_backing.add(faction_id)
    _progress.update({
        "prologue_signal": "completed",
        "prologue_mars_unlocked": "completed",
        "prologue_mars_entrance": "completed",
        "prologue_seek_help": "completed",
    })
    if _progress.get("prologue_open") != "completed":
        _progress["prologue_open"] = "active"
    ctx.log.add(
        f"[DEV MODE] Act 0 skipped as {_dev_faction_label(faction_id)} - "
        "the Mars door can now be opened."
    )


def _dev_owned_ship() -> Any:
    """Build the super-powered frigate loadout granted in dev mode."""
    return ship_module.OwnedShip(
        ship_id="frigate",
        weapons=(
            "plasma_cannon", "plasma_cannon", "plasma_cannon", "plasma_cannon",
            "heavy_missile", "heavy_missile", "heavy_missile", "heavy_missile",
        ),
        modules=(
            "reactor_mk4", "shield_mk4", "shield_recharger",
            "targeting_mk4", "gyro_mk4", "armor_mk4",
        ),
        fuel=999,
    )


def apply_dev_overrides(
    starter_ship: Any,
    starter_entity: Any,
    player_owned_ship: Any,
    stats: Any,
    log: Any,
) -> tuple[Any, Any, Any]:
    """If ``SPACEHACK_DEV`` is set, grant a super-powered frigate.

    Mutates ``stats`` and ``log`` in-place (they're mutable objects)
    and returns ``(starter_ship, starter_entity, player_owned_ship)``
    with the frigate override applied. If the env var is not set,
    returns the same objects unchanged.

    Call this right before :class:`GameContext` construction so the
    overridden values flow into ctx without the caller needing to
    know whether dev mode is active.
    """
    import os as _os

    if not _os.environ.get("SPACEHACK_DEV"):
        return starter_ship, starter_entity, player_owned_ship

    frigate = ship_module.find_ship("frigate")
    starter_ship = frigate
    starter_entity.char = frigate.char
    starter_entity.fg = frigate.fg
    starter_entity.name = f"Your Ship: {frigate.name}"
    starter_entity.ship_id = frigate.id
    player_owned_ship = _dev_owned_ship()
    stats.credits = 999999
    log.add("[DEV MODE] Super-powered frigate + 999,999 credits.")
    return starter_ship, starter_entity, player_owned_ship


def dev_transponder_library() -> list[dict]:
    """Three maxed-rep IDs for dev-mode new games (doc 40).

    Each sheet maxes ONE faction (+100, allied) and leaves the rest
    at 0 (neutral) — a per-faction test instrument for the transponder
    layer: wear the face, receive that faction's allied treatment.
    """
    from .faction import _ALL_FACTIONS
    from .identity import generate_registration

    library = []
    for faction, label in (
        ("pirate", "Pirate ally"),
        ("merchant", "Merchant ally"),
        ("militia", "Militia ally"),
    ):
        library.append({
            "id": generate_registration(),
            "kind": "cloned",
            "label": label,
            "faction": faction,
            "origin": "dev mode",
            "rep": {f: 100 if f == faction else 0 for f in _ALL_FACTIONS},
        })
    return library


def apply_dev_identity_library(ctx) -> None:
    """Seed the transponder library in dev mode (no-op otherwise).

    Also installs the cut-out (doc 41 playtest item 6: the dark run
    needs D to work without flying to Ember's depot first).
    """
    import os as _os

    if not _os.environ.get("SPACEHACK_DEV"):
        return
    ctx.collected_ids = dev_transponder_library()
    ctx.transponder_cutout = True
    ctx.log.add("Dev mode: 3 allied transponder IDs filed - TAB cycles them. "
                "Cut-out installed - D goes dark.")


def _apply_dev_line_marker(ctx, trait: str, note: str) -> None:
    """Grant one Line marker trait (doc 41 phase 1) — the Shift+L /
    Shift+K dev shortcuts, SPACEHACK_DEV-gated at the caller.

    Timed for the playtest, not new-game: the checklist's early
    items need an unpapered crossing, and the sweep's precedence
    (manifest outranks rank and service) needs the papers granted
    one checklist step at a time. Idempotent. No real grant path
    exists yet — the methods own their acquisition.
    """
    import os as _os

    if not _os.environ.get("SPACEHACK_DEV"):
        return
    if trait not in ctx.player_traits:
        ctx.player_traits.append(trait)
    ctx.log.add(f"[DEV MODE] Line kit: {note} granted.")


def apply_dev_blockade_manifest(ctx) -> None:
    """Shift+L: grant the manifest marker (the waving paper)."""
    from .navigation_line import MANIFEST_TRAIT
    _apply_dev_line_marker(ctx, MANIFEST_TRAIT, "blockade manifest")


def apply_dev_service_run(ctx) -> None:
    """Shift+K: grant the service-run marker (consumed at the wave).

    The militia dev face (+100) doubles as the rank-eligible
    impersonation entry: it clears the column's ``rank_rep``
    threshold (80) with no trait needed.
    """
    from .navigation_line import SERVICE_TRAIT
    _apply_dev_line_marker(ctx, SERVICE_TRAIT, "blockade service run")


def apply_dev_warrant_license(ctx) -> None:
    """Shift+G: grant the warrant-license quest perk (doc 42 playtest
    — the militia captain's thin-month tier is trait-gated). Idempotent."""
    _apply_dev_line_marker(ctx, "warrant_license", "warrant license")


def toggle_dev_cutout(ctx) -> bool:
    """Shift+B: toggle the transponder cut-out (doc 42 playtest).

    Dev saves pre-install the cut-out (``apply_dev_identity_library``),
    and every install storefront hides for owners — the one-time row
    only shows for non-owners. Toggling revokes/restores it in place.
    Returns the new state; mutates nothing without SPACEHACK_DEV."""
    import os as _os

    if not _os.environ.get("SPACEHACK_DEV"):
        return bool(getattr(ctx, "transponder_cutout", False))
    ctx.transponder_cutout = not getattr(ctx, "transponder_cutout", False)
    ctx.log.add(
        "[DEV MODE] Cut-out installed."
        if ctx.transponder_cutout
        else "[DEV MODE] Cut-out revoked - install rows visible again."
    )
    return ctx.transponder_cutout


def advance_to_shift_boundary(ctx) -> int:
    """Shift+J: advance the clock to the next shift boundary (doc 41
    phase 2 — Shift+D's 30 days is too coarse to time a watch
    rotation). Uses the current column's ``shift_days`` (the dataclass default 30 outside
    column systems). Returns the days advanced; 0 when not in dev
    mode.
    """
    import os as _os

    if not _os.environ.get("SPACEHACK_DEV"):
        return 0
    from . import solar_system as _solar
    from .navigation_line import next_boundary_gap
    from .time import advance_time as _advance_time

    _shift = getattr(
        getattr(_solar.current_system(), "sensor_column", None),
        "shift_days", 30,
    )
    _days = next_boundary_gap(ctx.time_day, ctx.time_month, ctx.time_year, _shift)
    _advance_time(ctx, _days)
    ctx.log.add(f"[DEV MODE] Clock advanced {_days} days to the shift boundary.")
    return _days


def log_rumor_routing(ctx) -> None:
    """Shift+N: log the run's live rumor routing (doc 42 phase 3) —
    carriers per entry, the live exclusive holder, the dark share."""
    from .engine import INIT_SEED
    from .rumor_routing import DARK_GROUP_SHARE, live_holdings, live_routes

    ctx.log.add(f"[DEV] Rumor routing (seed {INIT_SEED}):")
    for _entry_id, _pairs in sorted(live_routes(INIT_SEED).items()):
        _carriers = ", ".join(f"{_n}@{_p}" for _n, _p in sorted(_pairs))
        ctx.log.add(f"  {_entry_id}: {_carriers}")
    for _dealer, _rows in sorted(live_holdings(INIT_SEED).items()):
        for _rumor_id, _price in _rows:
            ctx.log.add(f"  exclusive {_rumor_id}: held by {_dealer} @ {_price}")
    _map = getattr(ctx, "game_map", None)
    _dark_hulls = sorted({
        getattr(_e, "name", "?")
        for _e in getattr(_map, "entities", ()) or ()
        if getattr(_e, "flies_dark", False)
    })
    ctx.log.add(
        "  dark pirate groups: 1 in "
        f"{DARK_GROUP_SHARE} (seeded per system)"
    )
    ctx.log.add(
        "  dark hulls here: " + (", ".join(_dark_hulls) if _dark_hulls else "none")
    )
