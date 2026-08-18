"""Shared gameplay actions and transitions used by the main loop.

This module owns reusable combat, dungeon-transition, ship-launch, and
save/exit orchestration for the gameplay loop in :mod:`spacehack.game_loop`.
"""

from __future__ import annotations

from . import combat
from . import main_quest as main_quest_module
from . import ship as ship_module
from . import solar_system as solar_system_module
from . import tutorial as tutorial_module
from . import world
from .text import get as t_get
from .city import _build_space_return, _launch_to_space
from .combat import _rules_ground
from .combat._loop import run_combat as _run_combat_unified
from .combat._rules_ground import init as _ground_init
from .combat._types import CombatResult
from .menus import ShipBuyOutcome, ShipMenuAction
from .navigation import (
    _check_auto_comms_warning,
    _detect_combat_encounter,
    _remove_bounty_spawn,
)
from .npc_ships import move_npcs as _move_npcs
from .saveload import save_game as _save_game

# ---------------------------------------------------------------------------
# Space-mode helpers (combat + NPC movement shared by multiple input paths)
# ---------------------------------------------------------------------------

def _run_combat_loop(ctx, console, player, *, also_move_npcs: bool = False) -> None:
    """Run combat encounters in a loop until no more are detected.

    Checks auto-comms warnings, runs the detection→combat loop, and
    optionally moves NPCs afterward.  Combat handlers mutate
    ``ctx.player_active_missions`` in place — callers sync their
    local copy after this returns.
    """
    _auto_result = _check_auto_comms_warning(
        ctx, player.pos, solar_system_module.current_system(),
    )
    if _auto_result is not None:
        _, _attack_data = _auto_result
        if _attack_data is not None:
            combat._handle_combat_encounter(ctx, console, _attack_data)

    while True:
        _encounter = _detect_combat_encounter(
            ctx, player.pos, solar_system_module.current_system(),
        )
        if _encounter is None:
            break
        _result = combat._handle_combat_encounter(ctx, console, _encounter)
        if _result != "VICTORY":
            break

    if also_move_npcs:
        _move_npcs(ctx, ctx.game_map)


# --- End space-mode helpers ---


def _save_and_exit(ctx, current_mode, current_city_id, space_player, *, save_game=None) -> None:
    """Save the active run using the current exploration mode."""
    if save_game is None:
        save_game = _save_game
    if current_mode == "dungeon":
        save_game(
            ctx,
            mode="dungeon",
            city_id=current_city_id,
            system_id=solar_system_module.current_solar_system_id,
            space_player_pos=(space_player.pos.x, space_player.pos.y)
            if space_player else None,
        )
        return
    save_game(
        ctx,
        mode=current_mode,
        city_id=current_city_id,
        system_id=solar_system_module.current_solar_system_id,
    )


# ---------------------------------------------------------------------------
# Ground-mode helpers (dungeon move + wait share one combat tick)
# ---------------------------------------------------------------------------

def _apply_ground_combat_rep(ctx, ground_result) -> None:
    """Apply per-kill ground-combat rep deltas from a combat result.

    No squads under LOS aggro — the old "killed the whole squad"
    bonus is gone. Kills award their faction deltas whether the fight
    ended in victory or disengagement (monsters: faction "" → no-op).
    """
    if ground_result.outcome not in ("VICTORY", "DISENGAGED") or not ground_result.defeated_spec_ids:
        return
    from .data.npc_chars import find_npc_char as _fnc
    from .faction import modify_rep, _COMBAT_KILL_DELTAS
    for _dsid in ground_result.defeated_spec_ids:
        try:
            _npc = _fnc(_dsid)
            _deltas = _COMBAT_KILL_DELTAS.get(_npc.faction, {})
            for _fac, _delta in _deltas.items():
                modify_rep(ctx, _fac, _delta)
        except (KeyError, ImportError):
            pass


def _open_character_for_mode(ctx) -> int:
    """Open the Character screen with carried-gear management enabled."""
    from .character_screen import open_character_screen

    return open_character_screen(ctx, equipment_management=True)


def _pickup_loot_near(ctx) -> bool:
    """Open pickup for loot on or next to the current player."""
    _loot = world.find_loot_near(ctx.game_map, ctx.player.pos)
    if _loot is None:
        ctx.log.add("No loot nearby.")
        return False
    from .trade import open_loot_pickup as _open_loot
    _open_loot(ctx, _loot)
    return True


def _run_pygame_dungeon_confirm(
    ctx,
    *,
    title: str,
    body: str,
    accept_label: str,
    cancel_label: str,
    caption: str,
) -> str | None:
    """Run a dungeon confirmation in the shared Pygame window."""
    from . import pygame_story

    return pygame_story.confirm(
        ctx,
        title=title,
        body=body,
        accept_label=accept_label,
        cancel_label=cancel_label,
        caption=caption,
    )


def _run_pygame_exit_confirm(ctx) -> bool:
    """Ask before saving and returning to the main menu (ESC).

    Returns True when the player confirms; the caller then saves and
    leaves. Any dismissal (ESC, window close) keeps the run going.
    """
    from . import pygame_story

    result = pygame_story.confirm(
        ctx,
        title="EXIT TO MAIN MENU",
        body="Save your progress and return to the main menu?",
        accept_label="Save & Exit",
        cancel_label="Keep Playing",
        caption="spacehack",
    )
    return result == "CONFIRM"


def _ground_combat_hostiles(ctx, game_map) -> list:
    """Move ground NPCs, refresh the LOS frame, and return hostiles now visible."""
    from .ground_npcs import move_ground_npcs as _move_ground_npcs
    _move_ground_npcs(ctx, game_map)
    from .dungeon import reveal_around as _reveal_around
    _reveal_around(game_map, ctx.player.pos, radius=game_map.sight_radius)
    from .combat._encounter import detect_ground_combat as _dgc
    return _dgc(ctx, game_map, ctx.player.pos)


def _show_ground_defeat(ctx, ground_result) -> None:
    """Show the full-screen death frame when a ground fight ends in defeat."""
    if ground_result is None or ground_result.outcome != "DEFEAT":
        return
    # Ground death shows the same full-screen death frame as space
    # defeat: no HUD, no console log, any key returns to the main
    # menu immediately, and no save is written.
    from .combat._encounter import _render_death_screen as _show_death
    _show_death(
        ctx,
        lines=(
            "YOU DIED",
            "You collapse from your wounds.",
        ),
    )


def _run_ground_combat_tick(
    ctx,
    console,
    game_map,
    *,
    ground_init=None,
    apply_rep=None,
    run_combat=None,
) -> CombatResult | None:
    """Move ground NPCs, refresh the LOS frame, then detect + run
    ground combat if any hostile is now visible.

    Shared by the dungeon move and wait handlers so both keep the
    current-LOS ``visible`` grid in sync with NPC movement (waiting
    previously left it stale, so a pirate that stepped onto a
    not-yet-revealed cell vanished from the render even though it was
    genuinely in line of sight) and both honour LOS aggro (combat
    triggers on sight, not just on movement).

    Returns the :class:`CombatResult` when combat ran, else ``None``.
    Callers check ``outcome == "DEFEAT"`` to exit the game loop.
    """
    _hostiles = _ground_combat_hostiles(ctx, game_map)
    if ground_init is None:
        ground_init = _ground_init
    if apply_rep is None:
        apply_rep = _apply_ground_combat_rep
    if run_combat is None:
        run_combat = _run_combat_unified
    if not _hostiles:
        return None
    # Tutorial: explain ground combat before the combat UI takes over,
    # and fire the finale once the first fight resolves.
    tutorial_module.maybe_ground_combat_intro(ctx)
    ground_init(ctx, _hostiles, game_map, console=console)
    _ground_result = run_combat(console, ctx, game_map, _rules_ground)
    apply_rep(ctx, _ground_result)
    tutorial_module.notify_ground_combat_ended(ctx)
    _show_ground_defeat(ctx, _ground_result)
    return _ground_result


def _dungeon_post_move_tick(
    ctx,
    console,
    game_map,
    *,
    ground_init=None,
    apply_rep=None,
    run_combat=None,
) -> str | None:
    """Run the shared post-step dungeon tick: move ground NPCs, refresh
    the LOS frame, auto-start ground combat on sight, then fire tile
    activations when no combat ran.

    Shared by the dungeon move, wait, and auto-explore paths so every
    player step (or wait) keeps NPC movement, LOS, and activation
    state identical.

    Returns ``"DEFEAT"`` (death screen shown — exit the game loop),
    ``"COMBAT"`` (a fight ran and was resolved — re-render and
    continue), or ``None`` (no combat — caller continues normal
    post-step handling like stairs checks).
    """
    _ground_result = _run_ground_combat_tick(
        ctx,
        console,
        game_map,
        ground_init=ground_init,
        apply_rep=apply_rep,
        run_combat=run_combat,
    )
    if _ground_result is not None:
        if _ground_result.outcome == "DEFEAT":
            return "DEFEAT"
        return "COMBAT"
    from .dungeon_extensions import tick_activation
    tick_activation(ctx)
    return None


def _first_walkable(game_map) -> world.Position | None:
    """Return the first walkable tile in ``game_map``, or ``None``.

    Used as the fallback spawn for cached interiors that predate
    ``entry_spawn`` recording (salvage wrecks + planet surfaces).
    """
    for _yy in range(game_map.height):
        for _xx in range(game_map.width):
            if game_map.tiles[_yy][_xx].walkable:
                return world.Position(_xx, _yy)
    return None


def _adopt_dungeon_transition(ctx, game_map, player) -> None:
    """Install a dungeon transition result on the shared game context."""
    ctx.game_map = game_map
    ctx.player = player
    ctx.ground_hp = ctx.ground_max_hp


def _maybe_show_post_prison_orbit(
    ctx,
    current_city_id: str,
    *,
    from_mars_prison: bool = False,
) -> bool:
    """Show the one-time Mars departure scene from a confirmed path."""
    if from_mars_prison or getattr(ctx, "post_prison_orbit_pending", False):
        ctx.post_prison_orbit_pending = True
        _shown = main_quest_module.play_scene(
            ctx, "act1_prison", from_mars_prison=True,
        )
        if _shown:
            ctx.post_prison_orbit_pending = False
        return _shown
    if current_city_id != "mars":
        return False
    return main_quest_module.play_scene(ctx, "act1_prison")


def _maybe_show_post_prison_orbit_in_space(ctx, current_mode: str) -> bool:
    """Deliver the orbit scene at the first confirmed space-mode frame."""
    if current_mode != "space":
        return False
    return _maybe_show_post_prison_orbit(ctx, ctx.current_city_id)


def _is_mars_surface_map(ctx, game_map) -> bool:
    """Return whether ``game_map`` is the cached Mars surface dungeon."""
    if getattr(game_map, "interior_cache_key", "") == "surface:mars":
        return True
    return ctx.interiors.get("surface:mars") is game_map


def _is_wreck_interior(game_map) -> bool:
    """Return whether a dungeon map belongs to a boarded wreck."""
    return getattr(game_map, "wreck_spawn_id", None) is not None


def _is_mars_facility_map(ctx, game_map) -> bool:
    """Return whether a map belongs to Mars surface or its prison."""
    if _is_mars_surface_map(ctx, game_map):
        return True
    return getattr(game_map, "extension_id", "") == "mars_alien_prison"


def _notify_surface_exit(ctx, exited_map, *, show_orbit=None) -> bool:
    """Deliver the post-prison scene when a Mars facility reaches orbit."""
    if show_orbit is None:
        show_orbit = _maybe_show_post_prison_orbit
    if _is_wreck_interior(exited_map) or not _is_mars_facility_map(ctx, exited_map):
        return False
    return show_orbit(
        ctx,
        "mars",
        from_mars_prison=True,
    )


def _launch_from_city(
    ctx,
    console,
    city_game_map,
    hangar_ship,
    ship,
    current_city_id: str,
    city_player,
    *,
    launch_to_space=None,
    show_orbit=None,
) -> tuple[world.GameMap, world.Entity]:
    """Launch from a city and deliver any pending Mars-orbit scene."""
    if launch_to_space is None:
        launch_to_space = _launch_to_space
    if show_orbit is None:
        show_orbit = _maybe_show_post_prison_orbit
    _space_map, _space_player = launch_to_space(
        ctx,
        console,
        city_game_map,
        hangar_ship,
        ship,
        current_city_id=current_city_id,
        city_player=city_player,
    )
    show_orbit(ctx, current_city_id)
    return _space_map, _space_player


def _launch_owned_ship(
    ctx,
    console,
    result,
    player_owned_ship,
    city_game_map,
    city_player,
    current_city_id: str,
    ship,
    *,
    launch_to_space=None,
    show_orbit=None,
) -> tuple[world.GameMap, world.Entity] | None:
    """Handle the selected owned-ship launch from a city hangar."""
    if result is not ShipMenuAction.LAUNCH or player_owned_ship is None:
        return None
    _hangar_ship = next(
        (
            _entity for _entity in city_game_map.entities
            if _entity.owned and _entity.ship_id == player_owned_ship.ship_id
        ),
        None,
    )
    if _hangar_ship is None:
        return None
    return _launch_from_city(
        ctx,
        console,
        city_game_map,
        _hangar_ship,
        ship,
        current_city_id,
        city_player,
        launch_to_space=launch_to_space,
        show_orbit=show_orbit,
    )


def _apply_ship_buy_result(
    ctx,
    city_game_map,
    blocker,
    ship,
    player_owned_ship,
    result,
    effective_price: int,
    trade_in_value: int,
):
    """Apply one ship-buy modal result and return the replacement ship."""
    if result is ShipBuyOutcome.BUY:
        return _complete_ship_purchase(
            ctx,
            city_game_map,
            blocker,
            ship,
            player_owned_ship,
            effective_price,
            trade_in_value,
        )
    if result is ShipBuyOutcome.TOO_EXPENSIVE:
        short = effective_price - ctx.stats.credits
        ctx.log.add(
            f"You cannot afford the {ship.name} - need {effective_price}$ "
            f"(including {trade_in_value}$ trade-in), {short}$ short."
        )
    return None


def _relocate_old_ship(ctx, city_game_map, player_owned_ship) -> bool:
    """Move the trade-in's equipment to storage and remove its hangar entity.

    Returns False (and logs) when the equipment cannot transfer safely;
    the purchase is aborted so no credits are spent.
    """
    if player_owned_ship is None:
        return True
    try:
        ship_module.move_installed_equipment_to_storage(
            player_owned_ship,
            ctx.ship_storage,
        )
    except ValueError:
        ctx.log.add("The trade-in could not safely transfer its equipment.")
        return False
    _old_entity = next(
        (
            entity for entity in city_game_map.entities
            if entity.owned and entity.ship_id == player_owned_ship.ship_id
        ),
        None,
    )
    if _old_entity is not None:
        city_game_map.entities.remove(_old_entity)
    return True


def _build_owned_ship(blocker, ship, old_reserved: int):
    """Park the purchased ship in the hangar and build its OwnedShip record."""
    blocker.pos = world.HANGAR_ANCHOR
    blocker.owned = True
    blocker.name = f"Your Ship: {ship.name}"
    return ship_module.OwnedShip(
        ship_id=ship.id,
        weapons=ship.start_weapons,
        modules=ship.start_modules,
        fuel=ship.max_fuel,
        mission_reserved=old_reserved,
    )


def _log_ship_purchase(
    ctx,
    ship,
    effective_price: int,
    trade_in_value: int,
    old_reserved: int,
    storage_before: int,
) -> None:
    """Log the purchase outcome (reserved warning, storage, trade-in)."""
    _new_cap = ship_module.effective_max_cargo(ship, ctx.player_owned_ship)
    if old_reserved > _new_cap:
        ctx.log.add(
            f"WARNING: {ship.name} cannot hold your mission cargo "
            f"({old_reserved}/{_new_cap}). Some missions may be undeliverable."
        )
    if len(ctx.ship_storage) > storage_before:
        ctx.log.add("Your old ship's equipment was moved to Storage.")
    if trade_in_value > 0:
        ctx.log.add(
            f"Traded in for the {ship.name} - paid "
            f"{effective_price}$ (trade-in {trade_in_value}$)."
        )
    else:
        ctx.log.add(
            f"You bought the {ship.name} for {ship.price}$ and parked it in your hangar."
        )


def _complete_ship_purchase(
    ctx,
    city_game_map,
    blocker,
    ship,
    player_owned_ship,
    effective_price: int,
    trade_in_value: int,
):
    """Complete an affordable ship purchase without losing old equipment."""
    if ctx.stats.credits < effective_price:
        return None
    _old_reserved = player_owned_ship.mission_reserved if player_owned_ship else 0
    _storage_before = len(ctx.ship_storage)
    if not _relocate_old_ship(ctx, city_game_map, player_owned_ship):
        return None
    ctx.stats.credits -= effective_price
    _new_owned = _build_owned_ship(blocker, ship, _old_reserved)
    ctx.player_owned_ship = _new_owned
    _log_ship_purchase(
        ctx, ship, effective_price, trade_in_value,
        _old_reserved, _storage_before,
    )
    return _new_owned


def _dungeon_exit_space_map(
    ctx,
    game_map,
    space_game_map,
    space_player,
    player_owned_ship,
    player_active_missions,
    log,
    build_space_return,
):
    """Resolve the space map to return to (rebuild Mars or clean up a wreck)."""
    if space_game_map is not None and space_player is not None:
        _wsid = getattr(game_map, "wreck_spawn_id", None)
        if _wsid is not None:
            _secured = _is_salvage_secured(
                ctx, _wsid, player_active_missions,
            )
            if _secured:
                _remove_salvage_wreck(
                    ctx, _wsid, space_game_map,
                )
        return space_game_map, space_player
    if not _is_mars_facility_map(ctx, game_map) or player_owned_ship is None:
        log.add("You have no ship waiting outside.")
        return None
    _return_ship = ship_module.find_ship(player_owned_ship.ship_id)
    return build_space_return(ctx, "mars", _return_ship)


def _dungeon_exit_log(ctx, exited_map, log) -> None:
    """Log the appropriate return line for the exited map type."""
    if _is_wreck_interior(exited_map):
        log.add("You exit through the hull breach and return to your ship.")
    elif _is_mars_facility_map(ctx, exited_map):
        log.add(t_get("runtime.prison.leave_orbit_log"))
    else:
        log.add("You return to your ship.")


def _leave_dungeon_to_space(
    ctx,
    game_map,
    space_game_map,
    space_player,
    player_owned_ship,
    player_active_missions,
    log,
    *,
    build_space_return=None,
    show_orbit=None,
):
    """Return from a dungeon exit to space and notify the orbit scene."""
    if build_space_return is None:
        build_space_return = _build_space_return
    if show_orbit is None:
        show_orbit = _notify_surface_exit
    _exited_map = game_map
    _space_transition = _dungeon_exit_space_map(
        ctx,
        game_map,
        space_game_map,
        space_player,
        player_owned_ship,
        player_active_missions,
        log,
        build_space_return,
    )
    if _space_transition is None:
        return None
    space_game_map, space_player = _space_transition
    _dungeon_exit_log(ctx, _exited_map, log)
    show_orbit(ctx, _exited_map)
    return space_game_map, space_player


def _handle_dungeon_exit(
    ctx,
    game_map,
    space_game_map,
    space_player,
    player_owned_ship,
    player_active_missions,
    log,
    *,
    build_space_return=None,
    show_orbit=None,
):
    """Handle an exit tile and return the next space-mode state."""
    _space_transition = _leave_dungeon_to_space(
        ctx,
        game_map,
        space_game_map,
        space_player,
        player_owned_ship,
        player_active_missions,
        log,
        build_space_return=build_space_return,
        show_orbit=show_orbit,
    )
    if _space_transition is None:
        return None
    _space_map, _space_player = _space_transition
    ctx.game_map = _space_map
    ctx.player = _space_player
    return _space_map, _space_player, "space"


def _handle_dungeon_exit_tile(
    ctx,
    tile_kind: str,
    game_map,
    space_game_map,
    space_player,
    player_owned_ship,
    player_active_missions,
    log,
    *,
    build_space_return=None,
    show_orbit=None,
):
    """Dispatch an actual dungeon exit tile to the space transition."""
    if tile_kind != "exit":
        return None
    return _handle_dungeon_exit(
        ctx,
        game_map,
        space_game_map,
        space_player,
        player_owned_ship,
        player_active_missions,
        log,
        build_space_return=build_space_return,
        show_orbit=show_orbit,
    )


def _is_salvage_secured(ctx, wreck_spawn_id: str, active_missions) -> bool:
    """Return whether a wreck's mission component has been secured."""
    for _mission in active_missions:
        if (
            getattr(_mission, "salvage_wreck_spawn_id", None) == wreck_spawn_id
            and getattr(_mission, "heist_good_secured", False)
        ):
            return True
    if not wreck_spawn_id.endswith("_wreck"):
        return False
    _step = main_quest_module.find_salvage_step_for_spawn(
        ctx, wreck_spawn_id[:-6],
    )
    return (
        _step is not None
        and ctx.main_quest_progress.get(_step.id) == "completed"
    )


def _remove_salvage_wreck(ctx, wreck_spawn_id: str, space_game_map) -> None:
    """Remove a secured wreck from space and its cached interior."""
    _system_id = solar_system_module.current_solar_system_id
    space_game_map.entities[:] = [
        _entity for _entity in space_game_map.entities
        if getattr(_entity, "salvage_wreck_spawn_id", None) != wreck_spawn_id
    ]
    _remove_bounty_spawn(ctx, wreck_spawn_id, _system_id)
    ctx.interiors.pop(wreck_spawn_id, None)
    ctx.log.add("The secured wreck drifts away - its component is yours.")


def _prep_cached_dungeon(game_map) -> world.Position | None:
    """Clear the stale player entity from a cached interior and return
    its entry spawn (first walkable tile when unrecorded).

    Shared by the salvage-wreck reboard path and the planet-surface
    re-entry path so both reuse cached maps the same way: no lingering
    ``@`` from the previous visit, and the player spawns where they
    entered last time.
    """
    for _oe in list(game_map.entities):
        if _oe.char == '@':
            game_map.entities.remove(_oe)
    _spawn = getattr(game_map, 'entry_spawn', None)
    if _spawn is None:
        _spawn = _first_walkable(game_map)
    return _spawn


