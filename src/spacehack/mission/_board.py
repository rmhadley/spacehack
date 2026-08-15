"""Mission board creation, offering, filling, and refresh lifecycle."""
from __future__ import annotations

import dataclasses
import random

from ..data.missions import MissionSpec, find_mission, missions_offered_by
from ._models import MissionBoard
from ._helpers import board_key


def _procedural_generators():
    """Return board generator dispatch without importing the package shim."""
    from ._proc_bar import generate_bar_mission
    from ._proc_bounty import generate_bounty_mission
    from ._proc_delivery import generate_delivery_mission
    return {
        "merchants": generate_delivery_mission,
        "bhguild": generate_bounty_mission,
        "bar": generate_bar_mission,
    }


_GUILD_TRAITS: dict[str, str] = {
    "merchants": "hauler",
    "bar": "fixer",
    "bhguild": "hunter",
}


def _board_guild(npc_id: str) -> str:
    """Resolve the faction guild for a mission board NPC."""
    try:
        from ..data.npcs import find_npc
        return find_npc(npc_id).guild
    except KeyError:
        return ""


def _faction_tier_band(ctx, guild: str, planet_tier: int) -> tuple[int, int]:
    """Return the mission tier band available to one faction board."""
    _base_max = max(1, min(4, planet_tier))
    _trait_id = _GUILD_TRAITS.get(guild)
    if _trait_id:
        from ..xp import has_trait
        if has_trait(ctx, _trait_id):
            return 2, min(4, _base_max + 1)
    return 1, _base_max


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


def _evict_unavailable_slots(
    board: MissionBoard,
    completed_ids: frozenset[str],
    active_ids: frozenset[str],
    generated: dict[str, MissionSpec],
    min_tier: int,
    max_tier: int,
) -> None:
    """Remove completed, active, or out-of-band missions from a board."""
    for i, _sid in enumerate(board.slots):
        if _sid is None:
            continue
        if _sid in completed_ids or _sid in active_ids:
            board.slots[i] = None
            continue
        try:
            _spec = find_mission(_sid)
        except KeyError:
            _spec = generated.get(_sid)
        if _spec is not None and not min_tier <= _spec.tier <= max_tier:
            board.slots[i] = None


def _fill_static_slots(board: MissionBoard, available_ids: list[str]) -> None:
    """Place shuffled static mission IDs into empty board slots."""
    _existing = {slot for slot in board.slots if slot is not None}
    for i, slot in enumerate(board.slots):
        if slot is not None:
            continue
        for _mid in available_ids:
            if _mid not in _existing:
                board.slots[i] = _mid
                _existing.add(_mid)
                break


def _available_static_ids(
    board: MissionBoard,
    max_tier: int,
    min_tier: int,
    completed_ids: frozenset[str],
    active_ids: frozenset[str],
    planet_id: str,
    ctx,
) -> list[str]:
    """Return static mission IDs allowed by the active tier band."""
    available = missions_offered_by(
        board.npc_id, planet_tier=max_tier, min_tier=min_tier,
        completed_ids=completed_ids, active_ids=active_ids, planet_id=planet_id,
    )
    if _tutorial_live(ctx):
        from ..tutorial import TUTORIAL_MISSION_IDS as _tutorial_ids
        available = [mission for mission in available if mission.id in _tutorial_ids]
    return [mission.id for mission in available]


def _generate_eligible_procedural(
    generator,
    planet_id: str,
    max_tier: int,
    min_tier: int,
    rng: random.Random,
    counter: int,
    giver_npc_id: str,
) -> MissionSpec | None:
    """Generate a procedural mission inside the shifted tier band."""
    for _attempt in range(32):
        _proc = generator(
            origin_planet_id=planet_id,
            max_tier=max_tier,
            rng=rng,
            counter=counter,
            giver_npc_id=giver_npc_id,
        )
        if _proc is None or _proc.tier >= min_tier:
            return _proc
    return None


def _faction_pay_pct(ctx, guild: str) -> int:
    """Return the current reputation reward adjustment for a guild."""
    if ctx is None:
        return 0
    from ..faction import guild_to_faction, adjust_reward_pct, get_attitude
    _faction = guild_to_faction(guild)
    _rep = ctx.faction_reputation.get(_faction, 0)
    return adjust_reward_pct(get_attitude(_rep))


def _fill_procedural_slots(
    board: MissionBoard,
    generator,
    planet_id: str,
    min_tier: int,
    max_tier: int,
    rng: random.Random,
    generated: dict[str, MissionSpec],
    pay_pct: int,
) -> None:
    """Fill remaining slots with eligible procedural missions."""
    _counter = 0
    for i, slot in enumerate(board.slots):
        if slot is not None:
            continue
        _proc = _generate_eligible_procedural(
            generator, planet_id, max_tier, min_tier, rng, _counter,
            board.npc_id,
        )
        if _proc is None:
            continue
        if pay_pct:
            _proc = dataclasses.replace(
                _proc,
                reward_credits=max(1, _proc.reward_credits * (100 + pay_pct) // 100),
            )
        generated[_proc.id] = _proc
        board.slots[i] = _proc.id
        _counter += 1


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
    """Fill empty slots with static and faction-appropriate work."""
    if generated is None:
        generated = {}
    if rng is None:
        from ..engine import RNG
        rng = RNG
    _guild = _board_guild(board.npc_id)
    _min_tier, _max_tier = _faction_tier_band(ctx, _guild, planet_tier)
    _evict_unavailable_slots(
        board, completed_ids, active_ids, generated, _min_tier, _max_tier,
    )
    _available_ids = _available_static_ids(
        board, _max_tier, _min_tier, completed_ids, active_ids, planet_id, ctx,
    )
    rng.shuffle(_available_ids)
    _fill_static_slots(board, _available_ids)
    if _tutorial_live(ctx):
        return
    _generator = _procedural_generators().get(_guild)
    if _generator is None:
        return
    _fill_procedural_slots(
        board, _generator, planet_id, _min_tier, _max_tier, rng, generated,
        _faction_pay_pct(ctx, _guild),
    )


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


def refresh_all_boards(ctx, *, force: bool = False) -> None:
    """Called on month rollover. Fills empty slots on all boards.

    Uses each board's stored ``planet_id`` to compute tier filtering.
    Skips boards whose ``last_refresh_month`` matches the current month
    (already refreshed this month).
    """
    from ..engine import RNG
    active_ids = frozenset(m.mission_id for m in ctx.player_active_missions)
    completed_ids = frozenset(ctx.completed_mission_ids)

    for board in ctx.mission_boards.values():
        if not force and board.last_refresh_month == ctx.time_month:
            continue
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


