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

**Why not put the ``FrameBuffer`` on ctx?**  :func:`Modal.run`
creates its own per-call framebuffer so :func:`spacehack.__main__._run_game` and
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

from .pygame_runtime import PygameContext

from . import hud
from . import message_log
from . import mission as mission_module
from . import ship as ship_module
from . import world
from . import ground_equipment as ground_equipment_module
from .character import GroundStats as _GroundStats


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


@dataclasses.dataclass
class PlayerCounters:
    """Playstyle tracking counters for trait qualification.

    All counters reset on death (fresh run). Incremented during
    normal gameplay by combat, missions, and trade paths.

    One field on :class:`GameContext` (``player_counters``)    instead of individual fields — extendable by adding a counter to

    this dataclass and updating the trait catalog.
    """
    laser_shots: int = 0
    missile_shots: int = 0
    plasma_shots: int = 0
    merchant_kills: int = 0
    total_kills: int = 0
    bounties_completed: int = 0
    deliveries_completed: int = 0
    # Faction-career counters used by Hauler, Fixer, and Hunter.
    merchant_missions_completed: int = 0
    bar_missions_completed: int = 0
    bounty_missions_completed: int = 0
    total_damage_taken: int = 0
    melee_kills: int = 0
    explosive_hits: int = 0


@dataclasses.dataclass(frozen=True)
class BountySpawn:
    """A dynamically-placed bounty target enemy spawn.

    Created when the player accepts a bounty mission and stored on
    :attr:`GameContext.bounty_spawns` so the target persists across
    system transitions. The ``spawn_id`` is a unique key that links
    back to :attr:`mission_module.ActiveMission.bounty_spawn_id`.

    For squad bounties (``squad_size > 1``), the leader's
    ``spawn_id`` is stored on the mission while wingmates have
    distinct ``spawn_id`` values and reference the leader via
    ``squad_group_id`` so they can be cleaned up together.
    """
    spawn_id: str
    enemy_id: str
    pos: world.Position
    bounty_target_name: str | None = None
    squad_size: int = 1
    loadout_pct: int = 0
    squad_group_id: str | None = None
    comms_warning_range: int = 0   # distance-based auto-hail; 0 = viewport-based
    heist_spawn_id: str | None = None  # links to ActiveMission for intercept loot drop
    salvage_wreck: bool = False    # True = non-combatant mission wreck (boardable, persists until secured)


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
class DungeonExtensionState:
    """Persistent state for one themed dungeon extension run."""

    extension_id: str
    current_floor: int = 1
    active: bool = False
    parent_map_key: str = ""
    parent_position: world.Position | None = None
    activated_events: set[str] = dataclasses.field(default_factory=set)
    event_positions: dict[str, list[int]] = dataclasses.field(default_factory=dict)
    power_restored: bool = False
    state_flags: set[str] = dataclasses.field(default_factory=set)


@dataclasses.dataclass
class GameContext:
    """Bundles the universally-shared game state for modals + render functions.

    Field-ownership contract (mutated by :func:`spacehack.__main__._run_game`
    + a few helper functions):

    * :attr:`context` - shared Pygame presentation context; immutable for game lifetime.
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
    * :attr:`ship_storage` - global stored weapons/modules independent of the
      active ship; mutated by storage actions and preserved across upgrades.
    * :attr:`player_active_missions` - ``list[ActiveMission]``; up to
      :data:`mission.MAX_ACTIVE_MISSIONS` entries. Empty until the player
      accepts work, grows/shrinks on abandon / complete.
    * :attr:`completed_mission_ids` - ``set[str]``; static MissionSpec IDs
      the player has finished. Prevents re-offering the same hand-crafted
      mission.
    * :attr:`mission_boards` - ``dict[str, MissionBoard]``; per-NPC,
      per-city board state, keyed by ``(npc_id, planet_id)`` so each
      city keeps its own mission list. Lazy-initialized on first talk.
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

    context: PygameContext
    character_info: CharacterInfo
    log: message_log.MessageLog
    game_map: world.GameMap
    player: world.Entity
    stats: hud.HudStats
    player_owned_ship: ship_module.OwnedShip | None = None
    ship_storage: list[ship_module.StoredEquipment] = dataclasses.field(
        default_factory=list,
    )
    player_active_missions: list[mission_module.ActiveMission] = dataclasses.field(
        default_factory=list,
    )
    completed_mission_ids: set[str] = dataclasses.field(default_factory=set)
    mission_boards: dict[str, mission_module.MissionBoard] = dataclasses.field(
        default_factory=dict,
    )
    bounty_spawns: dict[str, list[BountySpawn]] = dataclasses.field(default_factory=dict)
    # Persistent wreck interiors, keyed by the wreck's BountySpawn spawn id.
    # First board caches the layout; exit keeps it; re-board reuses it so
    # crew stay dead, loot stays taken, fog stays revealed (anti-farm).
    interiors: dict[str, world.GameMap] = dataclasses.field(default_factory=dict)
    dungeon_extension: DungeonExtensionState | None = None
    procedural_spawns: dict[str, list[ProceduralSpawn]] = dataclasses.field(default_factory=dict)
    npc_targets: dict[str, tuple[int, int]] = dataclasses.field(default_factory=dict)
    npc_paths: dict[str, list[tuple[int, int]]] = dataclasses.field(default_factory=dict)
    economy_state: dict[str, dict[str, int]] = dataclasses.field(default_factory=dict)
    # economy_state[planet_id][good_id] = current_stock; seeded on first visit
    faction_reputation: dict[str, int] = dataclasses.field(default_factory=dict)
    # Per-entity tracking for militia auto-hail scan attempts.
    # Keyed by "npc_ship_id:x:y" so each patrol gets its own roll.
    # Reset on jump/launch.
    militia_scanned: set[str] = dataclasses.field(default_factory=set)
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
    # XP & leveling (docs/design/in_progress/02_DESIGN_XP_LEVELING.md)
    player_xp: int = 0
    player_level: int = 1
    player_skill_points: int = 0
    player_gunnery_bonus: int = 0
    player_piloting_bonus: int = 0
    player_engineering_bonus: int = 0
    player_traits: list[str] = dataclasses.field(default_factory=list)
    player_counters: PlayerCounters = dataclasses.field(default_factory=PlayerCounters)
    # Ground combat stats (reflexes, strength, stamina).
    ground_stats: _GroundStats = dataclasses.field(default_factory=_GroundStats)
    # Equipped ground weapon instances. Two-handed specs occupy both
    # logical weapon slots while remaining one entry in this normalized
    # list. Each instance carries its own magazine (design doc 19, Phase 2).
    equipped_ground_weapons: list[ground_equipment_module.GroundWeaponInstance] = dataclasses.field(
        default_factory=list,
    )
    # Equipped ground armor by slot: slot -> GroundArmorSpec id.
    # Slots: head, body, hands, legs, feet.
    equipped_ground_armor: dict[str, str] = dataclasses.field(default_factory=dict)
    # Unlimited terminal-only warehouse for owned ground equipment.
    ground_armory_storage: list[ground_equipment_module.StoredGroundEquipment] = dataclasses.field(
        default_factory=list,
    )
    # Limited reserve carried into dungeons. Capacity is derived from
    # ground_stats.strength; equipped items do not consume these slots.
    ground_expedition_inventory: list[ground_equipment_module.StoredGroundEquipment] = dataclasses.field(
        default_factory=list,
    )
    # Field-item stacks (ammo + consumables) owned in the unlimited
    # terminal warehouse and the limited Expedition Pack. Kept separate
    # from StoredGroundEquipment so equipment validation stays strict;
    # each stack consumes one pack slot (design doc 19, Q1).
    ground_armory_items: list[ground_equipment_module.GroundItemStack] = dataclasses.field(
        default_factory=list,
    )
    ground_expedition_items: list[ground_equipment_module.GroundItemStack] = dataclasses.field(
        default_factory=list,
    )
    # Ground combat HP — set on dungeon entry, persisted across
    # combat encounters in the same dungeon visit. Default matches
    # the new-game formula 20 + stamina//3 at the base-10 start.
    ground_hp: int = 23
    ground_max_hp: int = 23
    # Current city the player is on (for save/load).  Updated on
    # planet landing; used by the title-menu Continue path to
    # restore the correct city map.
    current_city_id: str = "earth"
    # --- Main quest state (docs/design/in_progress/07_DESIGN_MAIN_QUEST.md) ---
    # step_id -> "available" / "active" / "completed" for the main
    # quest line. Breadcrumbs are shown in the quest log; steps are
    # never on mission boards.
    main_quest_progress: dict[str, str] = dataclasses.field(default_factory=dict)
    # Items + dialogue flags unlocked by main quest steps (e.g. the
    # faction's door-opening tool or later story discoveries).
    main_quest_unlocked_items: set[str] = dataclasses.field(default_factory=set)
    # Which blockade path was taken ("diplomatic" / "smuggler" /
    # "combat" / ""), read by the Act 3 epilogue.
    main_quest_path: str = ""
    # Faction claim flags planted by backing quests + the Act 0
    # faction choice. "Last claim wins" decides the Act 3 epilogue.
    main_quest_backing: set[str] = dataclasses.field(default_factory=set)
    # The faction chain locked in when the player Accepts a faction's
    # door help ("militia" / "merchants" / "bar" / "lab" / ""). Set by
    # the accept flow; read to close the other factions' offer rows and
    # to gate the faction tool. Survives save/load.
    main_quest_chain: str = ""
    # next_step_id -> (day, month, year) when its minimum-wait gate
    # elapses. Set on step completion via time.add_days_to_date; the
    # per-frame check flips the step to "available" + queues the summon.
    # Survives save/load.
    main_quest_gate: dict[str, tuple[int, int, int]] = dataclasses.field(
        default_factory=dict,
    )
    # Queued one-way summon text awaiting delivery at the next safe
    # frame (same overlay as the prologue transmission). Cleared on
    # delivery. Survives save/load.
    main_quest_pending_message: str = ""
    main_quest_pending_objective: str = ""
    # Set when Act 3 resolves (definitive ending; sandbox continues).
    main_quest_complete: bool = False
    # First post-prison orbit beat: the player's disclosure choice is
    # one of OrbitDisclosure's persisted string values, or empty before
    # the Mars launch scene is resolved.
    main_quest_disclosure: str = ""
    post_prison_orbit_seen: bool = False
    # True after leaving the Mars prison until the first-reading modal
    # resolves. This preserves the prison provenance across an interrupted
    # modal and Continue; current_city_id is only landing/save bookkeeping.
    post_prison_orbit_pending: bool = False
    # --- Tutorial mode (docs/design/in_progress/14_DESIGN_TUTORIAL_MODE.md) ---
    # True for tutorial runs (started from the title menu); gates the
    # scripted popup flow in spacehack.tutorial. Survives save/load so
    # Continue resumes a tutorial run mid-script.
    tutorial_mode: bool = False
    # Step ids already shown (idempotent popups — each fires once).
    tutorial_steps: set[str] = dataclasses.field(default_factory=set)
    # True after the final popup; the tutorial tick then stops firing.
    tutorial_complete: bool = False
