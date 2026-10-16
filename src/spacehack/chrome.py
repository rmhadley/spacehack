"""Chrome ownership and worn-effect reads (doc 102).

The backend contract for installed cybernetics: the one-pass
effect sums every combat assembly reads, and the
install/uninstall primitives the dev grant (4.1) and the Terminus
kiosk (4.2) call. Anatomy is the exclusivity axis (SETTLED 14):
installing over an occupied anatomy is a SWAP — the old piece
comes out, never a stack, never a rejection.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Iterable

from .data.chrome import find_chrome

if TYPE_CHECKING:
    from .game_context import GameContext


# The additive payload fields — spec field names match the sums
# one-to-one so the fold stays table-driven.
_ADDITIVE_FIELDS: tuple[str, ...] = (
    "crit_chance_space", "crit_chance_melee", "crit_chance_ranged",
    "crit_damage_points", "dodge_tile_bonus", "melee_damage_bonus",
)


@dataclass(frozen=True)
class ChromeEffects:
    """Summed worn-chrome effects — the one read the assemblies share."""

    crit_chance_space: int = 0
    crit_chance_melee: int = 0
    crit_chance_ranged: int = 0
    crit_damage_points: int = 0
    dodge_tile_bonus: int = 0
    melee_damage_bonus: int = 0
    nano_mesh: bool = False
    has_core: bool = False


def _spec_or_none(piece_id: str):
    """The piece's spec, or ``None`` for a stale/unknown id — the
    silent-skip contract in one place."""
    try:
        return find_chrome(piece_id)
    except KeyError:
        return None


def installed_effects(installed: Iterable[str]) -> ChromeEffects:
    """Sum every installed piece's effect payload in one pass.

    Unknown ids are skipped silently — the stale-save contract
    ``sum_armor_bonus`` already holds: a retired catalog entry
    never raises mid-combat.
    """
    totals = dict.fromkeys(_ADDITIVE_FIELDS, 0)
    nano_mesh = False
    has_core = False
    for piece_id in installed:
        spec = _spec_or_none(piece_id)
        if spec is None:
            continue
        for field_name in _ADDITIVE_FIELDS:
            totals[field_name] += getattr(spec, field_name)
        nano_mesh = nano_mesh or spec.nano_mesh
        has_core = has_core or spec.core
    return ChromeEffects(**totals, nano_mesh=nano_mesh, has_core=has_core)


def worn_anatomy_piece(installed: Iterable[str], anatomy: str) -> str | None:
    """The installed piece id occupying ``anatomy``, if any."""
    for piece_id in installed:
        spec = _spec_or_none(piece_id)
        if spec is not None and spec.anatomy == anatomy:
            return piece_id
    return None


def install_chrome(ctx: "GameContext", piece_id: str) -> str:
    """Install one piece; returns the swapped-out piece id (""
    when the anatomy was free). SETTLED 14: same anatomy is
    exclusive — the swap prices itself in 4.2's ego ratchet; the
    caller decides the replaced piece's disposition."""
    spec = find_chrome(piece_id)
    replaced = worn_anatomy_piece(ctx.installed_chrome, spec.anatomy)
    if replaced is not None:
        ctx.installed_chrome.remove(replaced)
    ctx.installed_chrome.append(piece_id)
    return replaced or ""


def uninstall_chrome(ctx: "GameContext", piece_id: str) -> bool:
    """Remove one installed piece. Frees the capacity claim; the
    burn never recovers (4.2's ratchet). Returns whether the
    piece was installed."""
    try:
        ctx.installed_chrome.remove(piece_id)
        return True
    except ValueError:
        return False


# ---------------------------------------------------------------------------
# Ruled player-facing strings (doc 102, prose ledger items 3-6) — ONE
# home so the theater twins cannot drift. Verbatim; never reworded
# in a module.
# ---------------------------------------------------------------------------

STIM_ACTIVATE_LINE = (
    "You activate the Terminus Neural Stim and your senses heighten "
    "as energy courses through you."
)
STIM_REPAY_LINE = "Reality slows as the Neural Stim's effect wears off."
STIM_NO_CORE_LINE = "No neural core installed."


def stim_recharge_line(rounds: int) -> str:
    """Ledger 5: the cooldown refusal line."""
    return f"Neural Stim recharging: {rounds} rounds."


def stim_hud_label(cooldown: int) -> str:
    """Ledger 6: the HUD row's text — READY / N ROUNDS. The debt
    line is DECLINED by ruling (the player learns the drain on
    their own; revisit clause in the doc)."""
    if cooldown > 0:
        return f"STIM (a): {cooldown} ROUNDS"
    return "STIM (a): READY"
