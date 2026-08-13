"""Mission board creation, offering, filling, and refresh lifecycle."""
from __future__ import annotations

import dataclasses
import random

from ..data.missions import MissionSpec, find_mission, missions_offered_by
from ._models import MissionBoard
from ._helpers import board_key


def _procedural_generators():
    """Return board generator dispatch without importing during package load."""
    from ._legacy import (
        generate_bar_mission,
        generate_bounty_mission,
        generate_delivery_mission,
    )
    return {
        "merchants": generate_delivery_mission,
        "bhguild": generate_bounty_mission,
        "bar": generate_bar_mission,
    }


def ensure_board(
    ctx, npc_id: str, max_slots: int = 5, planet_id: str = "",
) -> MissionBoard:
    """Get or create a :class:`MissionBoard` for ``npc_id`` on
    ``planet_id``.

    Boards are keyed by ``(npc_id, planet_id)`` so every city has its
    own mission list — two cities sharing an NPC id never share a
    board. If no board exists, creates one with ``max_slots`` empty
    slots and stores it in ``ctx.mission_boards``. Returns the
    existing board if one already exists.
    """
    _key = board_key(npc_id, planet_id)
    if _key not in ctx.mission_boards:
        board = MissionBoard(
            npc_id=npc_id,
            slots=[None] * max_slots,
            max_slots=max_slots,
            planet_id=planet_id,
        )
        ctx.mission_boards[_key] = board
    return ctx.mission_boards[_key]


def board_offerings(
    board: MissionBoard,
    generated: dict[str, MissionSpec] | None = None,
) -> tuple[MissionSpec, ...]:
    """Return :class:`MissionSpec` objects for non-empty slots on
    ``board``. Checks the static catalog first, then falls back to
    ``generated`` (procedural missions). Skips slots whose ID is
    unresolvable in both registries.
    """
    if generated is None:
        generated = {}
    result: list[MissionSpec] = []
    for slot_id in board.slots:
        if slot_id is not None:
            try:
                result.append(find_mission(slot_id))
            except KeyError:
                gen = generated.get(slot_id)
                if gen is not None:
                    result.append(gen)
    return tuple(result)


def _tutorial_live(ctx) -> bool:
    """True while the scripted tutorial flow is live (boards suppressed).

    Mirrors :func:`tutorial._active` — ``tutorial_mode`` alone stays True
    for the whole run, so mission suppression must also respect
    ``tutorial_complete`` or every non-bounty board would stay empty
    forever after the finale.
    """
    from ..tutorial import _active as _tutorial_active
    return bool(ctx is not None and _tutorial_active(ctx))


def fill_empty_slots(
    board: MissionBoard,
    planet_tier: int,
    completed_ids: frozenset[str],
    active_ids: frozenset[str],
    planet_id: str,
    *,
    generated: dict[str, MissionSpec] | None = None,
    rng: random.Random | None = None,
    ctx = None,
) -> None:
    """Fill empty (None) slots on ``board`` with available missions.

    First evicts any slot whose ID is in ``completed_ids`` or
    ``active_ids`` (stale slots from completed/accepted missions).
    Then fills the resulting empties with static missions first,
    using :func:`missions_offered_by` for the pool. Remaining empty
    slots are filled with procedurally-generated delivery missions.

    Generated missions are stored in ``generated`` (typically
    ``ctx.generated_missions``) so :func:`board_offerings` can
    resolve them later.
    """
    if generated is None:
        generated = {}
    if rng is None:
        from ..engine import RNG
        rng = RNG

    # Evict completed/active missions from board slots.
    for i in range(len(board.slots)):
        _sid = board.slots[i]
        if _sid is not None and (_sid in completed_ids or _sid in active_ids):
            board.slots[i] = None

    available = missions_offered_by(
        board.npc_id,
        planet_tier=planet_tier,
        completed_ids=completed_ids,
        active_ids=active_ids,
        planet_id=planet_id,
    )
    # Tutorial mode (design doc 14): while the scripted tutorial flow is
    # live only the tutorial's single contract is offered, and procedural
    # generation is suppressed below so the guided first run isn't
    # flooded with extra work.
    if _tutorial_live(ctx):
        from ..tutorial import TUTORIAL_MISSION_IDS as _tutorial_ids
        available = [_m for _m in available if _m.id in _tutorial_ids]
    available_ids = [m.id for m in available]
    rng.shuffle(available_ids)
    # Track which IDs are already on the board to avoid duplicates.
    existing = set(s for s in board.slots if s is not None)
    for i in range(len(board.slots)):
        if board.slots[i] is None and available_ids:
            for mid in available_ids:
                if mid not in existing:
                    board.slots[i] = mid
                    existing.add(mid)
                    break

    # Tutorial mode: never generate procedural missions (the guided run
    # teaches one contract at a time). Static whitelist fill above is all
    # the tutorial board shows.
    if _tutorial_live(ctx):
        return

    # Resolve guild for procedural generation dispatch.
    _guild = ""
    try:
        from ..data.npcs import find_npc as _fnpc
        _guild = _fnpc(board.npc_id).guild
    except KeyError:
        pass

    # Table-driven dispatch: guild → procedural generator function.
    _generator_fn = _procedural_generators().get(_guild)
    if _generator_fn is None:
        return  # no procedural missions for this guild

    # --- Faction reputation: pay scaling only (never gates access) ---
    # Every guild offers missions at any reputation; standing only
    # adjusts pay (disliked -15%, liked +10%, allied +20%). The hard
    # gates (enemy refusal, tier cuts) were removed by design.
    _pay_pct = 0
    if ctx is not None:
        from ..faction import guild_to_faction, adjust_reward_pct, get_attitude
        _board_faction = guild_to_faction(_guild)
        _board_rep = ctx.faction_reputation.get(_board_faction, 0)
        _board_attitude = get_attitude(_board_rep)
        _pay_pct = adjust_reward_pct(_board_attitude)

    # Fill remaining empty slots with procedural missions.
    _proc_counter = 0
    for i in range(len(board.slots)):
        if board.slots[i] is not None:
            continue
        _proc = _generator_fn(
            origin_planet_id=planet_id,
            max_tier=planet_tier,
            rng=rng,
            counter=_proc_counter,
            giver_npc_id=board.npc_id,
        )
        if _proc is not None:
            # Apply faction attitude pay scaling (never blocks the mission).
            if _pay_pct != 0:
                _proc = dataclasses.replace(
                    _proc,
                    reward_credits=max(1, _proc.reward_credits * (100 + _pay_pct) // 100),
                )
            generated[_proc.id] = _proc
            board.slots[i] = _proc.id
            existing.add(_proc.id)
            _proc_counter += 1


def board_remove(board: MissionBoard, mission_id: str) -> None:
    """Remove ``mission_id`` from ``board.slots`` (set to None).
    No-op if the ID isn't on the board.
    """
    for i in range(len(board.slots)):
        if board.slots[i] == mission_id:
            board.slots[i] = None
            return


def board_return_static(board: MissionBoard, mission_id: str) -> None:
    """Return a static mission ID to the first empty slot on
    ``board``. If no empty slot exists, bumps the last slot to
    make room (the bumped mission goes back into the candidate pool
    for future fills).
    """
    for i in range(len(board.slots)):
        if board.slots[i] is None:
            board.slots[i] = mission_id
            return
    # Board is full — bump the last slot to make room.
    board.slots[-1] = mission_id


def refresh_all_boards(ctx) -> None:
    """Called on month rollover. Fills empty slots on all boards.

    Uses each board's stored ``planet_id`` to compute tier filtering.
    Skips boards whose ``last_refresh_month`` matches the current month
    (already refreshed this month).
    """
    from ..engine import RNG
    active_ids = frozenset(m.mission_id for m in ctx.player_active_missions)
    completed_ids = frozenset(ctx.completed_mission_ids)

    for board in ctx.mission_boards.values():
        if board.last_refresh_month == ctx.time_month:
            continue
        # Resolve planet tier from stored planet_id.
        _tier = 1
        if board.planet_id:
            try:
                from ..data.planets import find_planet_spec as _fps
                _tier = _fps(board.planet_id).mission_tier
            except KeyError:
                pass
        fill_empty_slots(
            board,
            planet_tier=_tier,
            completed_ids=completed_ids,
            active_ids=active_ids,
            planet_id=board.planet_id,
            generated=ctx.generated_missions,
            rng=RNG,
            ctx=ctx,
        )
        board.last_refresh_month = ctx.time_month


