"""The status catalog (doc 103) — timed, actor-attached effects.

A status is catalog content, not code (the ChromeSpec law): a frozen
:class:`StatusSpec` per row, flat defaulted payload fields a status
declares only what it carries, and the ruled string templates a row
authors only the lines it has. Polarity is presentation data (color,
wording) — never a code fork.

Design doc: ``docs/design/in_progress/103_DESIGN_STATUSES.md``.
"""

from __future__ import annotations

from dataclasses import dataclass


# Shared row ids (the ground_consumables KIT_*_ID precedent: one
# authored constant, never a scattered string compare).
REGEN_ID = "regen"
STIM_ID = "stim"
NEURAL_STIM_LOAN_ID = "neural_stim_loan"
PIRATE_OPENER_ID = "pirate_opener"
OPENER_WINDOW_ID = "opener_window"

# The loan's repay narration — the exact chrome bytes (doc 102 prose
# ledger 6; doc 103 Build A moves the canonical home to the row it
# belongs to). chrome.py re-exports it under its historical name;
# never re-author it elsewhere.
NEURAL_STIM_REPAY_LINE = "Reality slows as the Neural Stim's effect wears off."


@dataclass(frozen=True)
class StatusSpec:
    """One catalog status row.

    Attributes:
        id: registry key, e.g. ``regen``.
        name: display name (the sourceless tick-line fallback; the
            inspect overlay's title, doc 103 q7).
        polarity: True = buff, False = debuff — color and wording
            only, never logic.
        duration: rounds remaining at application (``rounds`` class
            only; ``fight``/``charges`` classes carry no countdown).
        duration_class: ``"rounds"`` (ticks down at the round
            boundary), ``"fight"`` (until fight end or consumed),
            ``"charges"`` (consumed on trigger).
        stacking: ``"refresh"`` (re-apply resets the duration, the
            default — doc 103 S2/S3) or ``"stacks"`` (independent
            stacks to ``stacks_max``).
        crossing: theater-crossing behavior (doc 103 q11 — pause
            default; STRUCTURAL in Build A, first read by Build C).
        persists_past_fight: whether fight end keeps the status
            (doc 103 q13 — persist default; STRUCTURAL in Build A,
            first read by Build C).
        regen_per_round: ground HP restored at each round boundary.
        ap_per_round: AP applied at each round boundary (negative
            for loans and staggers).
        dot_per_round: HP lost at each round boundary (the damage
            event vocabulary — structural, no v1 row authors it).
        hit_bonus / dodge_bonus / melee_bonus: standing percentage /
            damage terms the named assemblies sum (structural in v1,
            no row authors them).
        tick_line / apply_line / expire_line: ruled prose templates —
            a row declares only the lines it has. ``{source}``
            interpolates the deliverer's display name, ``{healed}``
            the adapter-clamped healed amount.
        hud_label: the terse HUD-line label (q7); empty rows never
            render on the status line.
        description: the inspect overlay's text (q7) — prose-gated,
            Build B.
    """

    id: str
    name: str
    polarity: bool
    duration: int
    duration_class: str
    stacking: str = "refresh"
    stacks_max: int = 1
    crossing: str = "pause"
    persists_past_fight: bool = True
    regen_per_round: int = 0
    ap_per_round: int = 0
    dot_per_round: int = 0
    hit_bonus: int = 0
    dodge_bonus: int = 0
    melee_bonus: int = 0
    blocks_dodge: bool = False
    blocks_melee: bool = False
    tick_line: str = ""
    apply_line: str = ""
    expire_line: str = ""
    hud_label: str = ""
    description: str = ""


# The regen tick line is TODAY'S ledger line bit-identical (copied
# from _ground_effects.advance_player_effects, never a doc quote):
# "Med Pack regeneration: +2 HP." with the source interpolated.
_REGEN_TICK_LINE = "{source} regeneration: +{healed} HP."


STATUSES: tuple[StatusSpec, ...] = (
    StatusSpec(
        id=REGEN_ID,
        name="Regeneration",
        polarity=True,
        duration=3,
        duration_class="rounds",
        regen_per_round=2,
        tick_line=_REGEN_TICK_LINE,
        hud_label="REGEN",
    ),
    StatusSpec(
        id=STIM_ID,
        name="Combat Stim",
        polarity=True,
        duration=3,
        duration_class="rounds",
        ap_per_round=1,
        hud_label="STIM",
    ),
    StatusSpec(
        id=NEURAL_STIM_LOAN_ID,
        name="Neural Stim Loan",
        polarity=False,
        duration=1,
        duration_class="rounds",
        # Combat tempo, not a condition (q13): the loan defuses at
        # fight end the day the boundary rules flip.
        persists_past_fight=False,
        ap_per_round=-1,
        expire_line=NEURAL_STIM_REPAY_LINE,
    ),
    StatusSpec(
        # Doc 49 SETTLED 5 via doc 103 q4: the player's unspent
        # opening attack — applied at fight init where the trait
        # arms, consumed by mark_opener_spent.
        id=PIRATE_OPENER_ID,
        name="Pirate Opener",
        polarity=True,
        duration=0,
        duration_class="fight",
    ),
    StatusSpec(
        # The enemy side of the opener window — no enemy has fired
        # yet. Collective by construction: applied to every engaged
        # enemy, any enemy volley consumes every copy.
        id=OPENER_WINDOW_ID,
        name="Opener Window",
        polarity=True,
        duration=0,
        duration_class="fight",
    ),
)


_BY_ID: dict[str, StatusSpec] | None = None


def _registry() -> dict[str, StatusSpec]:
    global _BY_ID
    if _BY_ID is None:
        _BY_ID = {spec.id: spec for spec in STATUSES}
    return _BY_ID


def find_status(status_id: str) -> StatusSpec:
    """Look up a :class:`StatusSpec` by id; raises :class:`KeyError`."""
    try:
        return _registry()[status_id]
    except KeyError:
        raise KeyError(f"unknown status id: {status_id!r}") from None


def list_status() -> tuple[StatusSpec, ...]:
    """All registered statuses, in catalog order."""
    return STATUSES
