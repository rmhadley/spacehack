"""The movement-credit kernel (doc 44): NPCs move at their own
hull speed, not the player's.

Per player step every moving squad accrues ``map_speed / player_
speed`` tiles of credit; whole tiles are spent sub-stepping the
cached path cell-by-cell; fractions carry. Deterministic — the old
80% throttle is gone and stepping consumes no RNG.

The clamp (settled ruling 4): BEFORE committing each cell, if the
cell about to be entered lies inside the mover's encounter trigger
(its ``detect_radius`` around the player), the mover ENTERS that
cell, parks there, and spends no further credit. Stop ≠ fire —
the encounter opens at the top of the NEXT movement pass; this
kernel never opens modals.

Retained credit settles at <= 1.0 tiles: fractions carry, bursts
don't bank (a long-blocked mover unblocks with one pending tile,
not a teleport). Phase 3's day-granular wait SPENDS its full day
of movement — the cap bounds only what is retained.

Persistence mirrors the path-dict lifecycle (doc 44's ADVISE
ruling): current-system patrol mids round-trip; watch spawn keys
and other systems' squads default 0.0.
"""

from __future__ import annotations

import math

from . import world


def credit_rate(npc_speed: int, player_speed: int) -> float:
    """Tiles of credit one mover earns per player step — its own
    speed over the player's (the world advances 1/player_speed
    days per step)."""
    return npc_speed / player_speed


def rate_for(npc_speed: int, player_speed: int, day_pass: bool = False) -> float:
    """One mover's credit for this action: a whole day of travel on
    a wait (doc 44 ruling 4 — the player's speed is irrelevant to a
    full day), else its share of one player step."""
    return float(npc_speed) if day_pass else credit_rate(npc_speed, player_speed)


def player_moves_per_day(ctx) -> int:
    """The player's speed stat (moves/day) — the same read
    ``time.tick_move`` makes; fallback 10 when no ship resolves
    (lightweight doubles included)."""
    from .ship import effective_speed, find_ship
    if getattr(ctx, "player_owned_ship", None) is None:
        return 10
    try:
        return effective_speed(
            find_ship(ctx.player_owned_ship.ship_id), ctx.player_owned_ship,
        )
    except KeyError:
        return 10


def enter_trigger(cell: tuple[int, int], player_pos, radius: int) -> bool:
    """Pure clamp predicate: the cell about to be entered lies
    inside the mover's encounter trigger around the player."""
    return radius > 0 and math.hypot(
        cell[0] - player_pos.x, cell[1] - player_pos.y,
    ) <= radius


def settle(ctx, key: str, credit: float) -> None:
    """Bank one mover's retained credit, capped at one pending
    tile (anti-burst; spent movement is never banked)."""
    ctx.npc_credit[key] = min(credit, 1.0)


def spend_credit(ctx, game_map, *, entity, key: str, credit: float,
                 player_pos, radius: int) -> tuple[float, str]:
    """Walk ``entity`` along its cached path (``ctx.npc_paths[key]``)
    spending whole tiles of credit. Returns ``(retained_credit,
    outcome)``; the CALLER settles or pops the credit per the
    outcome:

    ``moving`` — credit exhausted mid-path, or the path went stale
    (popped for recompute — retain the fraction);
    ``blocked`` — the direct step failed (retain; retry next pass —
    the kept-path collision idiom). NOTE: a successful perpendicular
    SLIP also reports blocked, with the entity moved one cell off
    the path — blocked never implies the mover stood still;
    ``clamped`` — entered the encounter-trigger cell and parked
    (retain; the encounter opens at the top of the next pass);
    ``arrived`` — the path is exhausted or empty at entry (the
    caller's arrival/target logic runs; typically pop);
    ``no-path`` — nothing to walk (``npc_paths`` has no entry).
    """
    _path = ctx.npc_paths.get(key)
    if not _path:
        return (credit, "no-path" if _path is None else "arrived")
    while credit >= 1.0:
        _next = _path[0]
        _dx, _dy = _next[0] - entity.pos.x, _next[1] - entity.pos.y
        if abs(_dx) > 1 or abs(_dy) > 1:
            ctx.npc_paths.pop(key, None)  # stale: recompute next pass
            return (credit, "moving")
        _clamped = enter_trigger(_next, player_pos, radius)
        if not world.try_step_with_slip(entity, game_map, _dx, _dy):
            return (credit, "blocked")
        ctx.npc_paths[key].pop(0)
        credit -= 1.0
        if _clamped:
            return (credit, "clamped")
        if not ctx.npc_paths[key]:
            return (credit, "arrived")
    return (credit, "moving")


def pick_synced_credits(credits: dict, synced_mids: dict) -> dict:
    """The save-side shape (mirrors the path sync's population):
    credit for exactly the synced current-system patrol mids."""
    return {
        _mid: _credit
        for _mids in synced_mids.values()
        for _mid in _mids
        if _mid
        and (_credit := credits.get(_mid)) is not None
    }
