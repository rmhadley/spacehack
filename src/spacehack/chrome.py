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
from .data.species import find_species

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
    """Remove one installed piece. Frees the Install Room claim;
    the Burnt Ego never recovers (SETTLED 2's ratchet — the removal
    table teaches this). Returns whether the piece was installed."""
    try:
        ctx.installed_chrome.remove(piece_id)
        return True
    except ValueError:
        return False


# ---------------------------------------------------------------------------
# The ego economy (doc 102 SETTLED 2/3/5) — pool and load are DERIVED,
# never stored; the only stored state is ctx.ego_burn (the high-water
# ratchet).
# ---------------------------------------------------------------------------

def ego_pool(ctx: "GameContext") -> int:
    """Max ego: ``6 + birth + (level - 1) // 3`` (SETTLED 2). Birth
    is the species' flat modifier (v1 all 0); level growth buys
    chrome room — pool 6 at L1, 15 at L30, 25 at L60 at birth 0."""
    try:
        _birth = find_species(
            ctx.character_info.get("species_id", ""),
        ).ego_birth
    except KeyError:
        _birth = 0
    return 6 + _birth + (max(1, getattr(ctx, "player_level", 1)) - 1) // 3


def ego_load(ctx: "GameContext") -> int:
    """Current claim: the sum of installed pieces' burn costs.
    Recycles on uninstall (SETTLED 2 rule C)."""
    total = 0
    for piece_id in ctx.installed_chrome:
        spec = _spec_or_none(piece_id)
        if spec is not None:
            total += spec.burn
    return total


def install_room(ctx: "GameContext") -> int:
    """Install Room: how much chrome can still go in
    (``pool - load`` — the claim reads the pool, rule C)."""
    return ego_pool(ctx) - ego_load(ctx)


def predicted_burn_after(ctx: "GameContext", piece_id: str) -> int:
    """The ratchet's next value if ``piece_id`` installs: the
    high-water mark of load-after. Pure — the consent table reads
    it without mutating. A same-anatomy install is a SWAP
    (SETTLED 14): the replaced piece's claim leaves first, so its
    burn nets out of the load-after."""
    spec = find_chrome(piece_id)
    _load = ego_load(ctx)
    _worn = worn_anatomy_piece(ctx.installed_chrome, spec.anatomy)
    if _worn is not None:
        _replaced = _spec_or_none(_worn)
        if _replaced is not None:
            _load -= _replaced.burn
    return max(getattr(ctx, "ego_burn", 0), _load + spec.burn)


def ratchet_install(ctx: "GameContext", piece_id: str) -> str:
    """Install one piece AND advance the ratchet (the one mutation
    path — install_chrome alone never moves burn). Returns the
    replaced piece id, mirroring :func:`install_chrome`."""
    replaced = install_chrome(ctx, piece_id)
    # Post-install the load already includes the piece: the
    # high-water mark is simply burn vs the new load.
    ctx.ego_burn = max(getattr(ctx, "ego_burn", 0), ego_load(ctx))
    return replaced


# ---------------------------------------------------------------------------
# The consequence bands (doc 102 SETTLED 3/4/15) — static scars keyed
# on BURN, never the live room. ONE function set; every consumer
# composes these, never raw burn, never inlined tables.
# ---------------------------------------------------------------------------

# The dead zone is band 0: burn <= 3 costs nothing, lifetime.
_BAND_MAX_BURN: tuple[int, ...] = (3, 7, 11)
BAND_NAMES: tuple[str, ...] = ("Natural", "Tainted", "Chromed", "Psycho")
# Lawful buy/sell/service multiplier per band (SETTLED 4). The sell
# side reads the symmetric composition (2 - M) = .95/.85/.70.
_BAND_SERVICE_MULT: tuple[float, ...] = (1.00, 1.05, 1.15, 1.30)
# Rep-GAIN multipliers per faction axis (gains only — losses
# unchanged, the literal ruling). Labs is a board guild, not a rep
# faction; unknown factions read neutral.
_BAND_REP_GAIN: dict[str, tuple[float, ...]] = {
    "merchant": (1.00, 0.95, 0.85, 0.70),
    "militia": (1.00, 0.95, 0.85, 0.70),
    "pirate": (1.00, 1.05, 1.15, 1.30),
    "consortium": (1.00, 1.05, 1.15, 1.30),
}


def band(burn: int) -> int:
    """The BASE consequence band for a burn total: 0 Natural
    (dead zone), 1 Tainted, 2 Chromed, 3 Psycho (>= 12)."""
    for _i, _cap in enumerate(_BAND_MAX_BURN):
        if burn <= _cap:
            return _i
    return 3


def band_name(band_index: int) -> str:
    """The player-facing band name (names carry the communication,
    SETTLED 15 — consequences are never enumerated in UI)."""
    return BAND_NAMES[max(0, min(3, band_index))]


def local_band(ctx: "GameContext", planet_id: str) -> int:
    """The planet-shifted band read (SETTLED 4): strict cores read
    the burn one band HARSHER (+1), tolerant havens one band milder
    (-1) — ONE knob driving prices, boards, and the kiosk together.
    The dead zone is absolute (SETTLED 3): burn <= 3 reads free
    ANYWHERE, no port's valence can price the teach tier."""
    _base = band(getattr(ctx, "ego_burn", 0))
    if _base == 0:
        return 0
    _valence = 0
    if planet_id:
        from .data.planets import find_planet_spec
        try:
            _valence = getattr(find_planet_spec(planet_id), "ego_valence", 0)
        except KeyError:
            _valence = 0
    return max(0, min(3, _base + _valence))


def base_band(ctx: "GameContext") -> int:
    """The unshifted band read (rep, the F-screen name)."""
    return band(getattr(ctx, "ego_burn", 0))


def planet_valence(planet_id: str) -> int:
    """One port's ego valence (0 on unknown ids)."""
    if not planet_id:
        return 0
    from .data.planets import find_planet_spec
    try:
        return getattr(find_planet_spec(planet_id), "ego_valence", 0)
    except KeyError:
        return 0


def banded_price(ctx: "GameContext", price: int) -> int:
    """The ONE pay-side composition: a credit price at the current
    port's local band (what every lawful counter charges)."""
    return max(1, int(price * service_multiplier(
        local_band(ctx, getattr(ctx, "current_city_id", "")),
    )))


def service_multiplier(band_index: int) -> float:
    """The lawful price/services multiplier for a band (what you
    PAY; the receive side composes ``2 - M``)."""
    return _BAND_SERVICE_MULT[max(0, min(3, band_index))]


def rep_gain_multiplier(faction: str, band_index: int) -> float:
    """The rep-GAIN multiplier for one faction at a band. The base
    band, not a local read — rep moves everywhere, not on a planet."""
    return _BAND_REP_GAIN.get(faction, (1.00, 1.00, 1.00, 1.00))[
        max(0, min(3, band_index))
    ]


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
