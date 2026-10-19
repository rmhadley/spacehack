"""The status engine (doc 103) — pure, RNG-free, container-only.

The ONE mechanism for timed, actor-attached effects on both sides of
every theater: the player container (``ctx.active_statuses``) and the
enemy containers (``GroundEnemyInstance.statuses`` /
``EnemyInstance.statuses``) are the same ``dict[str, ActiveStatus]``
and read by the same rules here — actor-symmetric by construction,
never an is-player branch.

The engine never rolls, never logs, never writes HP/AP: ticks RETURN
events as data and the rules adapters apply them (the kill-draws
doctrine — the engine alone cannot reshuffle a seeded stream).
Serialization note: containers are save-shaped data on the read side,
so every read (``advance``/``sum_effects``) silently skips unknown
ids; only ``apply`` — authoring — raises on an unknown id.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from ..data.statuses import StatusSpec, find_status

# One tick's returned event: ("heal" | "damage" | "ap", id, n) or
# ("expire", id). Events fire BEFORE the round decrements (S1); the
# "damage" tag is the dot vocabulary (structural — no v1 row carries
# dot_per_round, and adapter damage routing ships with the first live
# row, doc 103's adapter contract).
TickEvent = tuple[str, str, int] | tuple[str, str]

# The additive payload terms sum_effects folds (one flat result field
# per term; dot stays event-side — a damage tick is not a standing
# modifier).
_SUM_FIELDS: tuple[str, ...] = (
    "regen_per_round", "ap_per_round",
    "hit_bonus", "dodge_bonus", "melee_bonus",
)


@dataclass
class ActiveStatus:
    """One live status on one actor's container.

    ``potency`` multiplies additive payload at sum time (structural
    in v1 — nothing keys it, doc 103 q8); ``source`` carries the
    deliverer's display name for attribution; ``theater`` is stamped
    at application from the delivery vehicle's theater (the crossing
    rule's read — doc 103 q11, first live in Build C).
    """

    status_id: str
    remaining_turns: int = 0
    stacks: int = 1
    potency: float = 1.0
    source: str | None = None
    theater: str | None = None


@dataclass(frozen=True)
class StatusEffects:
    """The one-pass fold over a container — one flat field per
    additive payload term (payload x stacks x potency)."""

    regen_per_round: int = 0
    ap_per_round: int = 0
    hit_bonus: int = 0
    dodge_bonus: int = 0
    melee_bonus: int = 0


def _payload_mag(spec: StatusSpec, active: ActiveStatus, field: str) -> int:
    """One additive term scaled by stacks and potency."""
    return int(getattr(spec, field) * active.stacks * active.potency)


def _rounds_remaining(spec: StatusSpec) -> int:
    """Rounds left at a fresh application — only the rounds class
    carries a countdown (fight/charges never decrement)."""
    return spec.duration if spec.duration_class == "rounds" else 0


def apply(
    container: dict[str, ActiveStatus],
    status_id: str,
    potency: float = 1.0,
    source: str | None = None,
    theater: str | None = None,
) -> str:
    """Apply one status, enforcing the row's stacking policy.

    Returns ``"applied"`` / ``"refreshed"`` / ``"stacked"`` for the
    caller's log decision. RAISES :class:`KeyError` on an unknown id
    — a delivery site naming a dead id is an authoring error, never
    a retire case. Re-apply is NEW WINS (S2): the new application's
    potency and source overwrite and the duration resets; a stacking
    row below its cap also grants one stack, and at the cap grants
    none — the duration still refreshes (S3).
    """
    spec = find_status(status_id)
    existing = container.get(status_id)
    if existing is None:
        container[status_id] = ActiveStatus(
            status_id=status_id,
            remaining_turns=_rounds_remaining(spec),
            potency=potency,
            source=source,
            theater=theater,
        )
        return "applied"
    stacked = spec.stacking == "stacks" and existing.stacks < spec.stacks_max
    if stacked:
        existing.stacks += 1
    existing.potency = potency
    existing.source = source
    if spec.duration_class == "rounds":
        existing.remaining_turns = spec.duration
    return "stacked" if stacked else "refreshed"


def _payload_events(
    status_id: str, spec: StatusSpec, active: ActiveStatus,
) -> tuple[TickEvent, ...]:
    """One rounds-class row's payload events for this boundary (S1:
    they fire BEFORE the decrement); a row carrying several terms
    fires each."""
    events: list[TickEvent] = []
    if spec.regen_per_round:
        events.append(
            ("heal", status_id, _payload_mag(spec, active, "regen_per_round")),
        )
    if spec.dot_per_round:
        events.append(
            ("damage", status_id, _payload_mag(spec, active, "dot_per_round")),
        )
    if spec.ap_per_round:
        events.append(
            ("ap", status_id, _payload_mag(spec, active, "ap_per_round")),
        )
    return tuple(events)


def advance(
    container: dict[str, ActiveStatus], theater: str | None = None,
) -> tuple[TickEvent, ...]:
    """Advance one round boundary: fire payload events, THEN
    decrement; remaining 0 expires and drops (S1 — a 3-round regen
    heals exactly 3 times, a 1-round loan fires exactly once).
    ``fight``/``charges`` classes never decrement here. Re-apply
    resets the duration, so a refresh landing between ticks can
    never double-tick. Unknown ids are skipped silently (containers
    are read-side save data).

    ``theater`` is the HOME-THEATER filter (doc 103 Build C, the
    pause law made mechanical): a row tagged for another theater is
    skipped — a carried ground row never ticks, and never touches
    space AP, while you fly. A row tagged ``None`` matches every
    theater (legacy-proof — today's applies always stamp); a walk
    passing ``None`` filters nothing.
    """
    events: list[TickEvent] = []
    for status_id, active in list(container.items()):
        if theater is not None and active.theater not in (None, theater):
            continue
        try:
            spec = find_status(status_id)
        except KeyError:
            continue
        if spec.duration_class != "rounds":
            continue
        events.extend(_payload_events(status_id, spec, active))
        active.remaining_turns -= 1
        if active.remaining_turns <= 0:
            del container[status_id]
            events.append(("expire", status_id))
    return tuple(events)


def sum_effects(container: dict[str, ActiveStatus]) -> StatusEffects:
    """Fold every active row's additive payload into one flat result
    (payload x stacks x potency), silently skipping unknown ids."""
    totals = {field: 0 for field in _SUM_FIELDS}
    for status_id, active in container.items():
        try:
            spec = find_status(status_id)
        except KeyError:
            continue
        for field in _SUM_FIELDS:
            totals[field] += _payload_mag(spec, active, field)
    return StatusEffects(**totals)


def has(container: dict[str, ActiveStatus] | None, status_id: str) -> bool:
    """Whether one status is currently active on the container."""
    return status_id in (container or {})


def potency_of(
    container: dict[str, ActiveStatus], status_id: str,
) -> float | None:
    """The live instance's potency multiplier, or None when absent
    (the chrome pass #2 re-key's read — structural in v1, q8)."""
    active = container.get(status_id)
    return active.potency if active is not None else None


def consume(container: dict[str, ActiveStatus], status_id: str) -> bool:
    """Remove one status outright (the ``fight``/``charges``
    consumption primitive — the opener's first-action spends).
    Returns whether anything was consumed."""
    return container.pop(status_id, None) is not None


def dispel(
    container: dict[str, ActiveStatus],
    predicate: Callable[[ActiveStatus], bool],
) -> tuple[str, ...]:
    """Remove every entry matching the predicate; returns the
    removed ids. The fight-end defuse is a :func:`defuse_at_fight_end`
    call — removal is silent, never an expire event."""
    removed = tuple(
        status_id for status_id, active in container.items()
        if predicate(active)
    )
    for status_id in removed:
        del container[status_id]
    return removed


def _dies_at_fight_end(active: ActiveStatus) -> bool:
    """Whether one entry dies at fight end (doc 103 q13, the
    field-keyed law): the ``fight`` class, every
    ``persists_past_fight=False`` row (the loans — combat tempo,
    never a carried condition), and UNKNOWN ids — a retired row can
    never resolve a spec, so it defuses; immortal save-carried
    garbage is the one behavior the silent-skip read contract must
    NOT extend to the defuse."""
    try:
        spec = find_status(active.status_id)
    except KeyError:
        return True
    return spec.duration_class == "fight" or not spec.persists_past_fight


def defuse_at_fight_end(container: dict[str, ActiveStatus]) -> tuple[str, ...]:
    """Fight-end defuse (doc 103 Build C, the carry flip): drop the
    fight class and the loans, KEEP every carried row — staggered
    walks out, regen keeps healing, and the defuse's own shape at
    fight INIT means carried rows survive the abnormal-end recovery
    path too (q13: you keep your burns). Silent (dispel semantics —
    no expire events, so an unconsumed loan never pays its line)."""
    return dispel(container, _dies_at_fight_end)


def _removed_at(
    active: ActiveStatus, transition: str,
) -> bool:
    """Whether one row DECLARES this transition in ``removed_on``
    (unknown ids declare nothing — they stay; inert at every read,
    they die at the next fight-end defuse, never immortal)."""
    try:
        spec = find_status(active.status_id)
    except KeyError:
        return False
    return transition in spec.removed_on


def remove_at_transition(
    container: dict[str, ActiveStatus], transition: str,
) -> tuple[str, ...]:
    """The transition-removal system's one iteration (doc 103 Build
    C): drop every row declaring this transition — silent (dispel
    semantics; the HUD row's disappearance is the signal, the
    enemy-side law's twin). Non-removed statuses PAUSE through the
    crossing (the home-theater law). ``board`` fires with zero
    removals in v1: no row authors it until the future fire debuff,
    and the live board seams make the system real for that row."""
    return dispel(container, lambda active: _removed_at(active, transition))


def hud_segments(
    container: dict[str, ActiveStatus],
) -> tuple[tuple[str, bool], ...]:
    """The one-row status line's segments (q7): one ``(text,
    polarity)`` per active row carrying a ``hud_label`` — rounds rows
    render ``LABEL n``; a labelled fight/charges row renders the
    label ALONE (no countdown to show — the ruled OPENER token).
    Label-less rows never render (the loan's debt-line decline)."""
    segments: list[tuple[str, bool]] = []
    for status_id, active in container.items():
        try:
            spec = find_status(status_id)
        except KeyError:
            continue
        if not spec.hud_label:
            continue
        if spec.duration_class == "rounds":
            segments.append(
                (f"{spec.hud_label} {active.remaining_turns}", spec.polarity),
            )
        else:
            segments.append((spec.hud_label, spec.polarity))
    return tuple(segments)


def paint_hud_segments(console, x: int, y: int, segments, bound_x: int) -> None:
    """Paint :func:`hud_segments` output at ``(x, y)`` — the one ink
    both theaters' panels share (polarity through the ui pair, two
    spaces between segments, nothing past ``bound_x``). Panels own
    their flow semantics (the ground gap row vs the space consumed
    row); this owns the drawing."""
    from ..ui import COLOR_STATUS_BUFF, COLOR_STATUS_DEBUFF
    for _text, _is_buff in segments:
        if x + len(_text) > bound_x:
            break
        console.print(
            x=x, y=y, string=_text,
            fg=COLOR_STATUS_BUFF if _is_buff else COLOR_STATUS_DEBUFF,
        )
        x += len(_text) + 2
