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


@dataclasses.dataclass(frozen=True)
class ProceduralSpawn:
    """A procedurally-generated enemy spawn created on jump / launch.

    Rolled against the system's ``pirate_chance`` each time the
    player enters a system. Persists for the current visit only;
    fresh spawns are rolled on the next jump / launch. ``squad_id``
    groups multiple pirates into a single combat encounter.
    """
    enemy_id: str
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
      player gains gold, takes damage, etc.
    * :attr:`player_owned_ship` - ``OwnedShip | None``; ``None`` until the
      player buys their first ship, then mutated on refuel / sell-cargo.
    * :attr:`player_active_mission` - ``ActiveMission | None``; ``None``
      until the player accepts, then ``None`` again on abandon / complete.
    * :attr:`bounty_spawns` - mutable registry of dynamic bounty-target
      spawns, keyed by system id. Populated on mission accept, consumed
      by :func:`spacehack.solar_system.make_solar_system` and
      :func:`spacehack.__main__._detect_combat_encounter`.

    **Read/write contract**: two kinds of mutation exist, and
    they're independent:

    * **Field reassignment** (``ctx.player = X``,
      ``ctx.game_map = X``, ``ctx.player_owned_ship = X``,
      ``ctx.player_active_mission = X`` or ``None``) is
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
    ``player_active_mission`` are the only two with defaults (because they
    start as ``None``); everything else is required at construction.
    """

    context: tcod.context.Context
    character_info: CharacterInfo
    log: message_log.MessageLog
    game_map: world.GameMap
    player: world.Entity
    stats: hud.HudStats
    player_owned_ship: ship_module.OwnedShip | None = None
    player_active_mission: mission_module.ActiveMission | None = None
    bounty_spawns: dict[str, list[BountySpawn]] = dataclasses.field(default_factory=dict)
    procedural_spawns: dict[str, list[ProceduralSpawn]] = dataclasses.field(default_factory=dict)