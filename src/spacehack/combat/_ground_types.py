"""Ground combat state types (doc 48 phase 2's encapsulation pass).

Extracted from :mod:`_rules_ground` when the worn-cyber fold's ratchet
fired (doc 48 phase 11): the per-enemy instance and the per-fight
session dataclasses live at their own address; ``_rules_ground``
re-exports both (tests and the seam modules import them there).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from .. import world
from ..game_context import GameContext
from ..ground_consumables import ActiveConsumableEffect
from ._types import FleeExit


# ---------------------------------------------------------------------------
# GroundEnemyInstance — per-enemy state during combat
# ---------------------------------------------------------------------------

@dataclass
class GroundEnemyInstance:
    """Per-enemy combat state."""

    entity: world.Entity
    spec: Any
    weapon_id: str = ""
    weapon_quality: int = 0
    # The band this enemy spawned at (doc 48 SETTLED 35) and its
    # derived six-block — combat math reads these, never spec fields.
    band: int = 0
    stats: Any = None
    hp: int = 30
    max_hp: int = 30
    ap: int = 4
    ap_total: int = 4
    # The FOLDED armor read (doc 48 SETTLED 51/27): spec armor + every
    # worn piece's defense — what they wear is what they are, on the
    # card and in every math (the six soak readers read this field,
    # never ``spec.armor``).
    armor: int = 0
    # Enemy-side consumable effect state (doc 48 SETTLED 36) —
    # fight-scoped, never serialized: a new fight re-derives from the
    # entity's pre-rolled carried stamp.
    stim_turns: int = 0
    stim_ap_bonus: int = 0
    regen_turns: int = 0
    regen_amount: int = 0
    cells_moved_this_turn: int = 0
    # Doc 48 p9: stare-eruption victims are NOT player kills — the
    # flag excludes them from the CombatResult's defeated lists so no
    # faction rep flows (drops landed; XP/counter already withheld).
    stare_killed: bool = False

    @property
    def alive(self) -> bool:
        return self.hp > 0

    @property
    def pos(self) -> world.Position:
        return self.entity.pos

    @pos.setter
    def pos(self, value: world.Position) -> None:
        self.entity.pos = value

    @property
    def name(self) -> str:
        return self.spec.name if self.spec else "Unknown"

# ---------------------------------------------------------------------------
# GroundCombatState — all session state in one place
# ---------------------------------------------------------------------------

@dataclass
class GroundCombatState:
    """Encapsulates all mutable state for one ground combat encounter."""

    ctx: GameContext
    game_map: world.GameMap
    enemies: list[GroundEnemyInstance] = field(default_factory=list)
    player_hp: int = 30
    player_max_hp: int = 30
    player_ap: int = 4
    player_ap_total: int = 4
    # Fractional AP (TE4-style): per-round gain in twentieths and the
    # banked fraction that rolls into the next round's pool. Ground
    # gains are integer today (4 + trait/armor bonuses), so the carry
    # stays 0 — the mechanism is uniform with ship combat for future
    # fractional bonuses.
    player_ap_gain_twentieths: int = 80
    player_ap_carry_twentieths: int = 0
    armor_defense: int = 0
    cells_moved_this_turn: int = 0
    active_weapon_list: list[bool] = field(default_factory=list)
    target_idx: int = 0
    console: Any = None
    # Presentation-only: the floating target card shows by default and
    # can be toggled off with ``v``.
    show_target_card: bool = True
    # Session-liveness flag, mirroring SpaceCombatState: cleared by
    # ``sync_state`` so presentation functions stop returning stale cards.
    active: bool = True
    # Presentation-only: while True, ``render_frame`` skips the player's
    # range/accuracy line. Set during shot animations and the whole enemy
    # turn so the line never clutters frames the player isn't acting on.
    range_line_hidden: bool = False
    active_consumable_effects: dict[str, ActiveConsumableEffect] = field(
        default_factory=dict,
    )
    # Doc 53 killer tracking: the last hostile damage source's label
    # (enemy + wielded variant), or the settled self-splash line.
    # Per-fight session state, never serialized.
    last_attacker: str | None = None
    # Doc 54 phase 2: the committed stair-dance exit (verb = the
    # transition tile kind) — set when the fight ends DISENGAGED at a
    # world exit; get_combat_result copies it onto the CombatResult.
    # Session-scoped, never serialized.
    flee_exit: "FleeExit | None" = None
    # Pirate opener (doc 49 SETTLED 5): ``enemy_fired`` stamps True at
    # every enemy shot (hit or miss) and closes the window; the shared
    # fire loop spends ``opener_spent`` on the player's first attack.
    # Per-fight session state, never serialized.
    enemy_fired: bool = False
    opener_spent: bool = False
    # The Shredder's mend line fires once per engagement (doc 48
    # SETTLED 42) — fight-scoped entity ids, never serialized.
    mend_told: set = field(default_factory=set)
