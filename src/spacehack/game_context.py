"""Game state bundle passed to every modal + render function.

Existed as scattered locals (``log``, ``stats``, ``owned_ship``, ...) threaded
through 11 modal call sites in :mod:`spacehack.__main__`. The closure-capture
pattern (each ``_run_X`` + ``_render`` closure wiring its own parameters)
silently broke when a refactor added a new dependency but forgot to wire it
through one of the closures — the rendered NameError surfaced at the first
modal open in the new shape. Bundling the universally-shared state into one
typed :class:`GameContext` object makes that class of bug structurally
impossible: closures close over ``ctx`` (typed, single reference) instead of
3-5 loose parameters, so adding a new dependency is a one-spot edit on the
dataclass instead of threading through 3 call layers.

**Why not put the ``tcod.console.Console`` on ctx?**  :func:`Modal.run`
creates its own per-call console so :func:`spacehack.__main__._run_game` and
each modal can own independent framebuffers. Sharing one console across both
would cause a 1-frame flicker when a modal returns and the next
:func:`_run_game` render hasn't repainted yet. The cost (one extra
``make_console()`` allocation per modal) is negligible vs. the safety win.

**Why not put ``SCREEN_WIDTH`` / ``SCREEN_HEIGHT`` on ctx?**  They are
immutable constants — pulling them off :mod:`spacehack.engine` is a static
import, not a closure-capture risk, so putting them on ctx would only bloat
the dataclass without preventing a single bug. Render functions import them
from :mod:`spacehack.engine` directly.
"""
from __future__ import annotations

import dataclasses
from typing import TypedDict

import tcod.context

from . import hud
from . import message_log
from . import mission as mission_module
from . import ship as ship_module
from . import world


class CharacterInfo(TypedDict):
    """The ``{species_id, species_name, class_id, class_name}`` map stored on :class:`GameContext`.

    TypedDict (rather than a plain ``dict[str, str]``) so future
    contributors get a type error if they typo the key, omit a
    field, or pass a non-str value. Lives next to
    :class:`GameContext` because it IS the value of
    ``GameContext.character_info``; splitting it into its own
    module would force a circular import.

    ``species_id`` / ``class_id`` were added alongside the
    ``species_name`` / ``class_name`` display strings so combat
    paths (notably :func:`spacehack.combat._handle_combat_encounter`)
    can resolve the player's actual pilot skills via
    :func:`spacehack.character.starting_pilot_skills` without
    having to reverse-lookup by name (which would be slower and
    would break the moment two species shared a localised name).
    ``species_name`` / ``class_name`` are kept so HUD render code
    that only needs the display string keeps the same call site.
    """
    species_id: str
    species_name: str
    class_id: str
    class_name: str


@dataclasses.dataclass
class NpcFlashEvent:
    """A one-shot visual event on the space map (jump gate flash).

    Pushed by :func:`spacehack.npc_ships.move_npcs` when a merchant
    ship arrives at or departs from a jump gate. The render layer
    draws expanding rings at ``pos`` for ``lifetime`` frames, then
    discards it. Events outside the current viewport expire silently.

    Not frozen because :attr:`lifetime` is mutated (decremented) by
    :func:`spacehack.npc_ships.render_npc_flash_events` each frame.
    """
    pos: world.Position
    lifetime: int = 4  # frames remaining; decremented each render. Must match _NPC_FLASH_RINGS entry count in npc_ships.py.


@dataclasses.dataclass(frozen=True)
class BountySpawn:
    """A dynamically-placed bounty target enemy spawn.

    Created when the player accepts a bounty mission and stored on
    :attr:`GameContext.bounty_spawns` so the target persists across
    system transitions. The ``spawn_id`` is a unique key that links
    back to :attr:`mission_module.ActiveMission.bounty_spawn_id`.
    """
    spawn_id: str
    enemy_id: str
    pos: world.Position
    bounty_target_name: str | None = None
    squad_size: int = 1
    loadout_pct: int = 0


@dataclasses.dataclass(frozen=True)
class ProceduralSpawn:
    """A procedurally-generated NPC spawn created on jump / launch.

    Rolled against the system's ``npc_spawn_chance`` each time the
    player enters a system. Persists for the current visit only;
    fresh spawns are rolled on the next jump / launch. ``squad_id``
    groups multiple NPCs into a single combat encounter.
    """
    npc_id: str                      # references NpcShipSpec.id
    pos: world.Position
    squad_id: str | None = None


@dataclasses.dataclass
class GameContext:
    """Bundles the universally-shared game state for modals + render functions.

    Field-ownership contract (mutated by :func:`spacehack.__main__._run_game`
    + a few helper functions):

    * :attr:`context` - libtcod terminal context; immutable for game lifetime.
    * :attr:`character_info` - ``{species_name, class_name}``; immutable for
      game lifetime.
    * :attr:`log` - message log; mutated as events fire.
    * :attr:`game_map` - current map (city OR space); reassigned on
      launch / land / jump.
    * :attr:`player` - current player entity (city ``@`` OR ship entity);
      reassigned on launch / land / jump.
    * :attr:`stats` - HUD stats (``HudStats`` dataclass); mutated as the
      player gains credits, takes damage, etc.
    * :attr:`player_owned_ship` - ``OwnedShip | None``; ``None`` until the
      player buys their first ship, then mutated on refuel / sell-cargo.
    * :attr:`player_active_missions` - ``list[ActiveMission]``; up to
      :data:`mission.MAX_ACTIVE_MISSIONS` entries. Empty until the player
      accepts work, grows/shrinks on abandon / complete.
    * :attr:`completed_mission_ids` - ``set[str]``; static MissionSpec IDs
      the player has finished. Prevents re-offering the same hand-crafted
      mission.
    * :attr:`mission_boards` - ``dict[str, MissionBoard]``; per-NPC board
      state, keyed by NPC id. Lazy-initialized on first talk.
    * :attr:`bounty_spawns` - mutable registry of dynamic bounty-target
      spawns, keyed by system id. Populated on mission accept, consumed
      by :func:`spacehack.solar_system.make_solar_system` and
      :func:`spacehack.__main__._detect_combat_encounter`.

    **Read/write contract**: two kinds of mutation exist, and
    they're independent:

    * **Field reassignment** (``ctx.player = X``,
      ``ctx.game_map = X``, ``ctx.player_owned_ship = X``,
      ``ctx.player_active_missions = X`` or ``None``) is
      intentional and rare - only ~5 sites do it: the
      launch / land / jump dispatchers in
      :func:`spacehack.__main__._run_game`, the ship-buy
      site, and the mission-accept / mission-abandon /
      mission-complete sites. Anywhere else,
      ``ctx.X = ...`` is almost certainly a bug. (The
      helpers :func:`_jump_to_system` and
      :func:`_launch_to_space` are *value producers* -
      they return ``(new_map, new_player)`` and the
      ``_run_game`` callers do the actual reassignment.)

    * **Object mutation** (``ctx.stats.hp -= X``,
      ``ctx.log.add(...)``) is the normal mutation pattern:
      any code path can call methods on the objects
      ``ctx`` points to without reassigning the field.
      :func:`_handle_combat_encounter` uses this pattern
      freely (combat drains HP + appends log lines without
      ever doing ``ctx.stats = ...``).

    Modals + render functions are READ-ONLY for *both* kinds
    - a render closure doing ``ctx.player = X`` or
    ``ctx.log.add(...)`` would silently corrupt game state.
    The dataclass is not ``frozen`` so the legitimate write
    sites can mutate in place, but those are the only places
    that should.

    The order of fields is significant for the dataclass: non-default fields
    must precede defaulted fields. ``player_owned_ship`` and
    ``player_active_missions`` are the only two with defaults (because they
    start as ``None``); everything else is required at construction.
    """

    context: tcod.context.Context
    character_info: CharacterInfo
    log: message_log.MessageLog
    game_map: world.GameMap
    player: world.Entity
    stats: hud.HudStats
    player_owned_ship: ship_module.OwnedShip | None = None
    player_active_missions: list[mission_module.ActiveMission] = dataclasses.field(
        default_factory=list,
    )
    completed_mission_ids: set[str] = dataclasses.field(default_factory=set)
    mission_boards: dict[str, mission_module.MissionBoard] = dataclasses.field(
        default_factory=dict,
    )
    bounty_spawns: dict[str, list[BountySpawn]] = dataclasses.field(default_factory=dict)
    procedural_spawns: dict[str, list[ProceduralSpawn]] = dataclasses.field(default_factory=dict)
    npc_targets: dict[str, tuple[int, int]] = dataclasses.field(default_factory=dict)
    npc_paths: dict[str, list[tuple[int, int]]] = dataclasses.field(default_factory=dict)
    economy_state: dict[str, dict[str, int]] = dataclasses.field(default_factory=dict)
    # economy_state[planet_id][good_id] = current_stock; seeded on first visit
    faction_reputation: dict[str, int] = dataclasses.field(
        default_factory=lambda: {
            "pirate": -100,
            "merchant": 0,
            "civilian": 0,
            "militia": 50,
        }
    )
    # Systems where the player has already received an NPC auto-comms
    # warning. Reset on map change (jump / launch).
    militia_warned_systems: set[str] = dataclasses.field(default_factory=set)
    # Set to True when the player's ship is destroyed in combat.
    # Checked by _run_game to break out of the main loop and return
    # to the title screen for a fresh run.
    player_dead: bool = False
    # One-shot visual events on the space map (jump gate flashes, etc.).
    # Each entry is rendered by the space-mode render loop for its
    # remaining lifetime, then removed. Empty by default.
    npc_flash_events: list[NpcFlashEvent] = dataclasses.field(default_factory=list)
    # Game time: day/month/year clock. Advanced every 10 space moves
    # (manual + auto-nav). Month wraps at 30, year wraps at 12.
    time_day: int = 1
    time_month: int = 1
    time_year: int = 2200
    move_counter: int = 0  # increments per space move; ticks a day at 10
    # Runtime-generated procedural missions, keyed by generated ID.
    # Procedural MissionSpec entries are built at generation time and
    # stored here so board_offerings can resolve them without the
    # static catalog.
    generated_missions: dict = dataclasses.field(default_factory=dict)