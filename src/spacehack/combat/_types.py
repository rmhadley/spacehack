"""Combat data types — enums and the EnemyInstance dataclass.

Extracted from the monolithic ``combat.py`` to keep type definitions
in their own module with no runtime logic.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum, auto
from typing import TYPE_CHECKING, Any

from .. import world

if TYPE_CHECKING:
    from ..ship import StoredEquipment


class CombatPhase(Enum):
    PLAYER_TURN = auto()
    ENEMY_TURN = auto()
    VICTORY = auto()
    DEFEAT = auto()


class CombatMode(Enum):
    DEFAULT = auto()
    MOVING = auto()
    FIRING = auto()


@dataclass
class EnemyInstance:
    """Mutable copy of an enemy ship during combat."""
    spec_id: str
    name: str
    char: str
    fg: tuple[int, int, int]
    hull: int = 100
    max_hull: int = 100
    shields: int = 0
    max_shields: int = 0
    shields_charged: bool = False
    power_pool: int = 5
    ap_remaining: int = 3
    ap_total: int = 3
    # Fractional AP (TE4-style): gain per round in twentieths and the
    # banked fraction that rolls into the next round's pool.
    ap_gain_twentieths: int = 60
    ap_carry_twentieths: int = 0
    pos: world.Position = field(default_factory=lambda: world.Position(0, 0))
    # Flown equipment (doc 47.3 + 48.7): weapons AND modules roll
    # quality at combat entry — what flies against the player is what
    # a capture drops. Weapons are StoredEquipment instances now.
    weapons: tuple["StoredEquipment", ...] = ()
    modules: tuple["StoredEquipment", ...] = ()
    # Ammo keyed by weapon SLOT index (the player twin): duplicate
    # weapons keep independent magazines; -1 = energy (no ammo).
    weapon_ammo: dict[int, int] = field(default_factory=dict)
    pilot_gunnery: int = 20
    pilot_piloting: int = 20
    pilot_engineering: int = 10
    power_gen: int = 3
    max_power: int = 10
    cells_moved_this_turn: int = 0
    # Paid shield divert (doc 48 SETTLED 40 — Tier 1): the rate is the
    # spec's authored S-dial answer; the threshold gates it (divert
    # only while shields sit below threshold × max_shields).
    shield_regen_rate: int = 0
    shield_regen_threshold: float = 0.5
    # The spec's authored band (doc 48 SETTLED 39) — the LVL card line
    # reads it; skills and flown quality derive from it at build.
    band: int = 0
    # Free shield regen per turn: hull base + module bonus, folded at
    # build (doc 48 SETTLED 39). The paid divert above fires only
    # below the threshold while power lasts.
    shield_recharge_bonus: int = 0
    alive: bool = True


@dataclass(frozen=True)
class FleeExit:
    """One committed map-leaving exit chosen at an exit prompt (doc 54).

    Built by the exit menus' refusal-probed commit path
    (game_interactions); rides ``CombatResult.flee_exit`` so the
    CALLER runs the transition — the combat loop never does (the
    ``boarded_spec_id`` payload pattern). Space verbs: ``"land"`` /
    ``"explore"`` / ``"dig"`` / ``"jump"`` (a station dock is a
    ``"land"`` on the station's city planet). Ground (doc 54 phase
    2): the verb is the transition TILE KIND (``"stairs_up"`` /
    ``"stairs_down"`` / ``"exit"``) — the caller's ordinary tile
    dispatch derives everything else. Session-scoped presentation
    state, never serialized.
    """
    verb: str
    planet_id: str = ""
    site_id: str = ""
    jp: Any = None
    target_system_id: str = ""
    target_jp_id: str = ""


@dataclass
class CombatResult:
    """Bundles the outcome and defeated-entity tracking from a combat
    encounter. Returned by :func:`run_combat` so callers access named
    fields instead of unpacking a naked tuple."""
    outcome: str = "VICTORY"  # "VICTORY", "DEFEAT", or "DISENGAGED" (ground)
    defeated_names: list[str] = field(default_factory=list)
    defeated_bounty_ids: list[str] = field(default_factory=list)
    defeated_heist_ids: list[str] = field(default_factory=list)
    defeated_spec_ids: list[str] = field(default_factory=list)
    # BOARDED (space): the live ship the player boarded — the hull is
    # consumed at board entry (doc 40 phase 6a).
    boarded_spec_id: str = ""
    boarded_ent: Any = None
    # The boarded ship's flown module instances at their rolled
    # quality (doc 47.3 SETTLED 14/16) — the capture strip's source.
    boarded_modules: tuple = ()
    # The flown weapon instances beside them (doc 48.7): weapons are
    # quality-bearing now — what FLEW is what drops.
    boarded_weapons: tuple = ()
    # Doc 53: the written tombstone's full path on a DEFEAT (None when
    # no file landed — a failed write, or a non-death outcome).
    # Session-scoped presentation state, never serialized.
    tombstone_path: str | None = None
    # FLED (space, doc 54): the committed exit the player survived
    # the reaction volley for — begin_flee_transition executes it
    # caller-side, never inside the combat loop.
    flee_exit: FleeExit | None = None


@dataclass
class SpaceCombatState:
    """Encapsulates all mutable state for one space combat encounter.

    Declared here (the types module) so the kill-resolution sibling
    ``_space_kills`` takes it as a parameter without importing the
    rules module. The single module-level instance lives in
    ``_rules_space._state`` (the state contract).
    """

    ctx: Any = None
    console: Any = None
    game_map: Any = None
    log: Any = None
    player_state: dict = field(default_factory=dict)
    enemy_insts: list = field(default_factory=list)
    enemy_specs: list = field(default_factory=list)
    enemy_ents: dict = field(default_factory=dict)
    player_ent: Any = None
    weapons_list: list = field(default_factory=list)
    # Per-slot flown-weapon tiers (doc 48.7 player side), parallel to
    # weapons_list — quality multiplies player weapon damage exactly
    # as it multiplies enemy weapon damage.
    weapon_qualities: list = field(default_factory=list)
    active_weapons: list = field(default_factory=list)
    target_idx: int = 0
    view_w: int = 80
    view_h: int = 54
    cr: CombatResult | None = None
    active: bool = True
    # Doc 53 killer tracking: the last hostile damage source's label
    # ("Pirate Scout's Light Laser"); None until a hit lands. Per-fight
    # session state, never serialized.
    last_attacker: str | None = None
    # Presentation-only: target card shown by default, toggled with ``v``.
    show_target_card: bool = True
    # Pirate opener (doc 49 SETTLED 5): ``enemy_fired`` stamps True at
    # every enemy shot (hit or miss) and closes the window; the shared
    # fire loop spends ``opener_spent`` on the player's first attack.
    # Per-fight session state, never serialized.
    enemy_fired: bool = False
    opener_spent: bool = False
