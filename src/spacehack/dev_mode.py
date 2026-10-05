"""Dev-mode overrides for playtesting.

When the ``SPACEHACK_DEV`` environment variable is set, the player
starts with a super-powered frigate, maxed modules, 999,999 credits,
a two-set ground loadout (strongest ranged weapon active, strongest
melee holstered — doc 51), a pack of T4 weapons in the
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
from .ground_weapon_sets import weapon_set


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


def _menu_frames(menu: ui.MenuScreen, body: str):
    """Build the shared fixed-layout frames for a dev picker menu —
    one frame per selection, items wired to the menu's own
    descriptions and option ids (the faction/teleport/ship pickers'
    one builder)."""
    from . import pygame_menu

    items = tuple(
        pygame_menu.MenuItem(
            label=label,
            description=menu.descriptions.get(option_id, ""),
            action=option_id,
        )
        for option_id, label in menu.options
    )
    return tuple(
        pygame_menu.MenuFrame(
            title=menu.title.upper(),
            body=body,
            items=items,
            hints=(menu.instruction,),
            selected=selected,
        )
        for selected in range(len(items))
    )


def _pygame_faction_frames(menu: ui.MenuScreen):
    """Build the fixed-layout frames for the dev faction picker."""
    return _menu_frames(
        menu, "Choose the faction whose Act 0 path you want to test.",
    )


async def _run_pygame_menu_pick(
    context, frames, caption: str, valid_ids: set[str],
) -> tuple[Outcome, str | None] | None:
    """Run a dev picker modal; return (Outcome, action) or None to fall back."""
    from . import pygame_menu

    if not frames:
        return None
    while True:
        outcome, action, _selected = await pygame_menu.run_for_context(
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


async def _run_pygame_faction_pick(
    context, menu: ui.MenuScreen,
) -> tuple[Outcome, str | None] | None:
    """Run the dev faction picker in Pygame, or return None for fallback."""
    result = await _run_pygame_menu_pick(
        context, _pygame_faction_frames(menu),
        caption="spacehack - choose act 0 faction",
        valid_ids={faction_id for faction_id, _label in menu.options},
    )
    return result


async def choose_main_quest_faction(context) -> tuple[Outcome, str | None]:
    """Run the Act 0 faction picker in the shared Pygame window."""
    result = await _run_pygame_faction_pick(context, main_quest_faction_menu())
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
    """Build the fixed-layout frames for the city teleport picker."""
    return _menu_frames(menu, "Land on any port city for playtesting.")


async def choose_city_teleport(context) -> tuple[Outcome, str | None]:
    """Run the city teleport picker in the shared Pygame window."""
    menu = city_teleport_menu()
    result = await _run_pygame_menu_pick(
        context, _pygame_teleport_frames(menu),
        caption="spacehack - teleport to city",
        valid_ids={planet_id for planet_id, _label in menu.options},
    )
    if result is None:
        return Outcome.BACK, None
    return result


def _quicksave_path() -> Path:
    """Full path to the dev-mode quicksave checkpoint file."""
    from .saveload import _saves_dir

    return _saves_dir() / "quicksave.json"


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


def _best_ground_armor() -> dict[str, ground_equipment.StoredGroundEquipment]:
    """Return the strongest registered base armor entry for every slot."""
    _by_slot: dict[str, list] = {slot: [] for slot in _GROUND_ARMOR_SLOTS}
    for _armor in list_ground_armor():
        if _armor.slot in _by_slot:
            _by_slot[_armor.slot].append(_armor)
    return {
        _slot: ground_equipment.StoredGroundEquipment(
            "armor", max(
                _items,
                key=lambda _item: (_item.defense, _item.tech_level, _item.price),
            ).id,
        )
        for _slot, _items in _by_slot.items()
        if _items
    }


def _best_set_weapon(set_class: str) -> str:
    """Return the strongest registered weapon of one set class (doc 51).

    Shop-stockable only: the enemy-only rows (``shop_available=False``,
    the monsters + the ancients) must never leak into a dev grant —
    the same flag that keeps them out of armories."""
    return max(
        (
            _w for _w in list_ground_weapons()
            if weapon_set(_w.id) == set_class and _w.shop_available
        ),
        key=lambda _w: (_w.damage, _w.tech_level, _w.price),
    ).id


# T4 weapons seeded into the expedition backpack so the whole tier can
# be playtested without hunting armories. The active/holstered picks
# land in their own sets; the rest ride in the pack.
_DEV_PACK_WEAPONS: tuple[str, ...] = (
    "plasma_caster", "railgun", "power_fist", "power_fist",
    "ion_blaster", "mono_blade",
)


def _dev_ground_loadout() -> tuple[list[ground_equipment.GroundWeaponInstance], list[ground_equipment.GroundWeaponInstance], dict[str, ground_equipment.StoredGroundEquipment]]:
    """Return the developer two-set ground loadout (doc 51 SETTLED 2).

    Strongest ranged active, strongest melee holstered — every fresh
    dev game starts with a real two-set loadout. The strongest melee
    also riding the pack is harmless dev duplication.
    """
    return (
        [ground_equipment.weapon_instance(_best_set_weapon("ranged"))],
        [ground_equipment.weapon_instance(_best_set_weapon("melee"))],
        _best_ground_armor(),
    )


def apply_dev_ground_loadout(ctx) -> None:
    """Equip developer ground weapons, armor, and pack when dev mode is enabled."""
    import os as _os

    if not _os.environ.get("SPACEHACK_DEV"):
        return
    (
        ctx.equipped_ground_weapons,
        ctx.holstered_ground_weapons,
        ctx.equipped_ground_armor,
    ) = _dev_ground_loadout()
    ctx.ground_expedition_inventory = [
        ground_equipment.StoredGroundEquipment("weapon", _wid)
        for _wid in _DEV_PACK_WEAPONS
    ]
    # The pack holds all 6 T4 weapons; capacity is 4 + (strength - 10) // 10,
    # so raise strength to 30 so all 6 fit without breaking swaps.
    if ctx.ground_stats.strength < 30:
        ctx.ground_stats.strength = 30
    from .xp import refresh_ground_max_hp
    refresh_ground_max_hp(ctx)
    _ranged_name = find_ground_weapon(ctx.equipped_ground_weapons[0].weapon_id).name
    _melee_name = find_ground_weapon(ctx.holstered_ground_weapons[0].weapon_id).name
    ctx.log.add(
        f"[DEV MODE] {_ranged_name} active + {_melee_name} holstered "
        "+ T4 pack + best armor."
    )


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
    """Build the dev-mode frigate grant (doc 56 phase 2 re-author).

    The old 64-cell loadout cannot pack a 30-cell grid. Three plasmas
    fill rows 0-2 wall to wall (18 cells); compact reactor + shield
    mk1 sit in the remainder at 24/30 with net +8 (6 + 3 - 1). A
    fourth 2x3 plasma can never fit (only two rows remain) while a
    small part still installs — the playtest's geometry-refusal step
    has a live subject either way.
    """
    frigate = ship_module.find_ship("frigate")
    weapons, modules = ship_module.fitted_entries(
        frigate,
        ("plasma_cannon", "plasma_cannon", "plasma_cannon"),
        ("compact_reactor", "shield_mk1"),
    )
    return ship_module.OwnedShip(
        ship_id="frigate",
        weapons=weapons,
        modules=modules,
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


async def reveal_dev_dig_site(ctx) -> dict:
    """Shift+M: force-reveal a dig site (doc 42 phase 4 checklist
    instrument) — the full reveal idiom: derivation, record, readout."""
    from .digs import reveal_site

    return await reveal_site(ctx)


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


def _describe_weapon_set(instances) -> str:
    """One dev-dump row: ``name[loaded/capacity,quality]`` per instance."""
    if not instances:
        return "empty (fists)"
    parts = []
    for instance in instances:
        spec = find_ground_weapon(instance.weapon_id)
        total = str(spec.ammo_capacity) if spec.ammo_capacity > 0 else "-"
        loaded = "-" if instance.loaded_ammo is None else str(instance.loaded_ammo)
        parts.append(f"{spec.name}[{loaded}/{total},q{instance.quality}]")
    return ", ".join(parts)


def log_ground_weapon_sets(ctx) -> None:
    """Shift+W: dump both ground weapon sets (doc 51 phase 1) —
    magazine + quality per instance, the playtest's only pre-HUD
    visibility into the holstered set."""
    ctx.log.add("[DEV] Ground weapon sets:")
    ctx.log.add(f"  active: {_describe_weapon_set(ctx.equipped_ground_weapons)}")
    ctx.log.add(f"  holstered: {_describe_weapon_set(ctx.holstered_ground_weapons)}")


async def dump_ground_weapon_sets(state) -> None:
    """The game_loop dev-table dispatch body for Shift+W.

    game_loop sits two lines under the architecture limit, so the
    adapter lives here and the table entry points directly at it.
    """
    log_ground_weapon_sets(state.ctx)


def _adjacent_cells(game_map, player_pos, count: int) -> list:
    """The first ``count`` walkable cells beside the player, as
    ABSOLUTE coordinates (``_scatter_squad`` places on absolutes —
    the offset/absolute mismatch spawned both grant families out of
    bounds until the p9 review executed it; the phase-4 grant rode
    the same bug)."""
    return [
        (player_pos.x + dx, player_pos.y + dy)
        for dy in range(-2, 3)
        for dx in range(-2, 3)
        if (dx or dy)
        and game_map.in_bounds(player_pos.x + dx, player_pos.y + dy)
        and game_map.tiles[player_pos.y + dy][player_pos.x + dx].walkable
    ][:count]


def _spawn_dev_ground_faces(ctx, game_map, player_pos, faces, ring, label) -> int:
    """The shared Shift+grant loop (doc 48's per-phase instruments):
    disjoint per-face slices over ONE absolute-coordinate ring (the
    offsets-vs-absolutes lesson), each face at its authored band
    (``None`` reads the spec's ``fixed_band``), bold from the spec.
    ``faces`` is ``(spec_id, band, cells_per_face)``; ``ring`` sizes
    the pool (a drift-hungry face wants the wider ring)."""
    from .dungeon_population import _scatter_squad
    from .data.npc_chars import find_npc_char

    cells = _adjacent_cells(game_map, player_pos, ring)
    placed = 0
    cursor = 0
    for spec_id, band, width in faces:
        spec = find_npc_char(spec_id)
        placed += _scatter_squad(
            game_map.entities,
            {(e.pos.x, e.pos.y) for e in game_map.entities},
            enemy_id=spec_id, cells=cells[cursor:cursor + width],
            count=1,
            squad_id=f"dev_{spec_id}", char=spec.char, fg=spec.fg,
            band=band if band is not None else spec.fixed_band,
            bold=spec.elite,
        )
        cursor += width
    ctx.log.add(f"[DEV] Spawned {placed} {label}.")
    return placed


def spawn_dev_enemy_faces(ctx, game_map, player_pos) -> int:
    """Shift+V: spawn the doc-48 phase-4 faces beside the player.

    The brute/marine/sniper have no ambient consumer until the crew
    decks re-author (phase 6) — this is the playtest's only window
    onto them — the sniper at band 4 so the pin's railgun payoff
    reads through this instrument.
    """
    return _spawn_dev_ground_faces(
        ctx, game_map, player_pos,
        (("pirate_brute", 3, 2), ("militia_marine", 3, 2),
         ("militia_sniper", 4, 2)),
        6, "phase-4 faces",
    )


def spawn_dev_ancient_trio(ctx, game_map, player_pos) -> int:
    """Shift+A: spawn the ancient trio beside the player (doc 48 p9).

    Every machines checkpoint item (shriek, stare, drift, mend,
    field, slam, shot) runs without a descent — the Watcher needs
    breathing room for its drift, so the cells span a wider ring
    than the phase-4 grant; disjoint per-face slices as ever.
    """
    return _spawn_dev_ground_faces(
        ctx, game_map, player_pos,
        tuple((spec_id, 4, 4) for spec_id in ("watcher", "shredder", "warden")),
        24, "ancient machines",
    )


def spawn_dev_consortium_rungs(ctx, game_map, player_pos) -> int:
    """Shift+E: spawn the three consortium rungs beside the player
    (doc 48 phase 11) — every rung checkpoint item (the worn bonuses
    on the card, the floors' drops, the Executor's deck-clearing
    weight) runs without a hunt. Each rung stamps at its own FIXED
    band (the None band reads the spec)."""
    return _spawn_dev_ground_faces(
        ctx, game_map, player_pos,
        tuple((spec_id, None, 2) for spec_id in (
            "consortium_gunner", "consortium_enforcer", "consortium_executor",
        )),
        6, "consortium rungs",
    )


def apply_dev_tinker_kit(ctx) -> None:
    """Shift+Y: grant a full tinker-kit stack (doc 47 phase 5).

    Checklist instrument for a drop authored to be very rare — tops
    up a partial stack when one exists, else appends a full one.
    """
    from .data.ground_items import find_ground_consumable
    from .ground_consumables import KIT_ITEM_ID
    from .ground_equipment import GroundItemStack

    cap = find_ground_consumable(KIT_ITEM_ID).quantity_per_stack
    for index, stack in enumerate(ctx.ground_expedition_items):
        if stack.item_type == "consumable" and stack.item_id == KIT_ITEM_ID:
            if stack.quantity >= cap:
                return
            ctx.ground_expedition_items[index] = GroundItemStack(
                stack.item_type, stack.item_id, cap,
            )
            ctx.log.add("Dev: tinker kit stack granted.")
            return
    ctx.ground_expedition_items.append(
        GroundItemStack("consumable", KIT_ITEM_ID, cap),
    )
    ctx.log.add("Dev: tinker kit stack granted.")


def spawn_dev_consumable_carriers(ctx, game_map, player_pos) -> int:
    """Shift+C: spawn enemy consumable carriers beside the player.

    Two raiders, deterministically pre-stamped (doc 48 phase 5): one
    wounded med-pack carrier and one stim carrier — the playtest's
    window onto enemy consumable use (any carrier, used items never
    drop). The stamps bypass the pre-roll so the checklist is exact.
    """
    from .dungeon_population import _scatter_squad
    from .data.npc_chars import find_npc_char

    cells = _adjacent_cells(game_map, player_pos, 2)
    if len(cells) < 2:
        ctx.log.add("[DEV] No room for the carriers beside you.")
        return 0
    spec = find_npc_char("pirate_raider")
    grants = {
        "dev_carrier_0": [["consumable", "med_pack", 1]],
        "dev_carrier_1": [["consumable", "stim", 1]],
    }
    placed = 0
    for index, (squad_id, stamps) in enumerate(grants.items()):
        _before = len(game_map.entities)
        placed += _scatter_squad(
            game_map.entities,
            {(e.pos.x, e.pos.y) for e in game_map.entities},
            enemy_id="pirate_raider", cells=[cells[index]], count=1,
            squad_id=squad_id, char=spec.char, fg=spec.fg,
            band=2, bold=False,
        )
        # Stamp ONLY what this press added — a double-tap must never
        # re-supply or re-wound an earlier grant's carriers.
        for _e in game_map.entities[_before:]:
            _e.carried_items = [list(_s) for _s in stamps]
            if squad_id == "dev_carrier_0":
                _e.hp = 5  # wounded: the med trigger reads on sight
    ctx.log.add(f"[DEV] Spawned {placed} consumable carriers.")
    return placed


def _dev_pirate_cycle() -> tuple:
    """Shift+P's option list (doc 48.7's cycle; the 48.11 playtest
    ruling made the key a picker — this is its source): the six
    pirate classes in ladder order, then the missile-led captain the
    checklist's item 3 needs
    (its weapons[0] is a missile — the dry-then-step read), then the
    doc-48-phase-11 hunt ships (the pursuit hunter + the bold-F
    anchor). The variant registers as a dev-authored spec row at
    grant time: the encounter system is id-resolved, so it rides the
    ONE spawn path."""
    import dataclasses

    from .data.npc_ships import _registry, find_npc_ship

    _missile_led = dataclasses.replace(
        find_npc_ship("pirate_captain"),
        id="dev_missile_captain",
        weapons=("heavy_missile", "heavy_laser", "light_laser"),
    )
    _registry().setdefault(_missile_led.id, _missile_led)
    return tuple(find_npc_ship(spec_id) for spec_id in (
        "pirate_scout", "pirate_hound", "pirate_raider",
        "pirate_marauder", "pirate_captain", "pirate_warlord",
        "consortium_hunter", "consortium_dreadnought",
    )) + (_missile_led,)


def _describe_ship_spec(spec) -> str:
    """One ship option's menu description: hull, band, elite flag."""
    from .data.ships import find_ship

    _desc = f"{find_ship(spec.ship_id).name} hull, band {spec.band}"
    return f"{_desc}, BOLD" if spec.elite else _desc


def dev_ship_menu() -> ui.MenuScreen:
    """The Shift+P spec picker (doc 48.11 playtest ruling): cycling
    buried the hunt ships behind six spawns — the menu grants ANY
    cycle spec in one press. Options are the cycle itself (the
    missile-led captain included)."""
    specs = _dev_pirate_cycle()
    return ui.MenuScreen(
        title="Spawn NPC Ship",
        instruction=pygame_ui.modal_hint(
            pygame_ui.NAV_HINT, "ENTER select", "ESC cancel",
        ),
        options=tuple((spec.id, spec.name) for spec in specs),
        descriptions={spec.id: _describe_ship_spec(spec) for spec in specs},
    )


def _pygame_ship_frames(menu: ui.MenuScreen):
    """Build the fixed-layout frames for the ship spec picker."""
    return _menu_frames(menu, "Spawn the picked spec beside you (space mode).")


async def choose_dev_ship(context) -> tuple[Outcome, str | None]:
    """Run the ship spec picker in the shared Pygame window."""
    menu = dev_ship_menu()
    result = await _run_pygame_menu_pick(
        context, _pygame_ship_frames(menu),
        caption="spacehack - spawn npc ship",
        valid_ids={spec_id for spec_id, _label in menu.options},
    )
    if result is None:
        return Outcome.BACK, None
    return result


def spawn_dev_ship(ctx, game_map, player_pos, spec_id: str) -> int:
    """Spawn one picked spec beside the player (space mode). The
    spawn rides the ambient entity factory so detect-radius aggro
    pulls it into a real fight. The squad id keys off the spec —
    same-spec picks share one movement group, different specs stay
    distinct."""
    from .data.npc_ships import find_npc_ship
    from .npc_ships import _make_npc_entity
    from . import world as _world

    try:
        spec = find_npc_ship(spec_id)
    except KeyError:
        ctx.log.add(f"[DEV] Unknown ship id: {spec_id}.")
        return 0
    occupied = {(_e.pos.x, _e.pos.y) for _e in game_map.entities}
    cell = next(
        ((player_pos.x + dx, player_pos.y + dy)
         for dy, dx in ((0, 1), (0, -1), (1, 0), (-1, 0), (1, 1), (-1, -1))
         if game_map.in_bounds(player_pos.x + dx, player_pos.y + dy)
         and game_map.tiles[player_pos.y + dy][player_pos.x + dx].walkable
         and (player_pos.x + dx, player_pos.y + dy) not in occupied),
        None,
    )
    if cell is None:
        ctx.log.add("[DEV] No room beside you for the ship grant.")
        return 0
    game_map.entities.append(_make_npc_entity(
        spec, _world.Position(*cell), f"dev_pirate_{spec.id}",
    ))
    ctx.log.add(f"[DEV] Spawned {spec.name} (band {spec.band}) beside you.")
    return 1
