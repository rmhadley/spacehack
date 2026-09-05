"""Shared fake quest-context factory (doc 33 Phase 3).

One factory satisfying the whole completion path — complete_step
reaches stats, xp fields, time, backing, and the message log — so new
quest tests never grow attributes one failure at a time. Extended by
kwargs; anything the factory sets can be overridden.
"""

from __future__ import annotations

from types import SimpleNamespace

from src.spacehack.message_log import MessageLog


def quest_ctx(
    *,
    chain: str = "merchants",
    progress: dict[str, str] | None = None,
    gate: dict | None = None,
    credits: int = 0,
    missions: list | None = None,
    ship: SimpleNamespace | None = None,
    city_id: str = "earth",
    day: int = 1,
    month: int = 1,
    year: int = 2200,
    **extra,
) -> SimpleNamespace:
    """A ctx with every field complete_step / gates / triggers touch."""
    ctx = SimpleNamespace(
        main_quest_chain=chain,
        main_quest_progress=dict(progress or {}),
        main_quest_gate=dict(gate or {}),
        main_quest_backing=set(),
        main_quest_disclosure="",
        main_quest_disposition="",
        main_quest_pending_message="",
        main_quest_pending_objective="",
        main_quest_complete=False,
        main_quest_unlocked_items=set(),
        player_traits=[],
        mission_boards={},
        generated_missions={},
        completed_mission_ids=set(),
        faction_reputation={},
        player_active_missions=list(missions or []),
        player_owned_ship=ship
        or SimpleNamespace(
            inventory={}, mission_reserved=0, ship_id="scout",
            weapons=(), modules=(), cargo_ammo=0,
        ),
        stats=SimpleNamespace(credits=credits),
        player_xp=0,
        player_level=1,
        player_skill_points=0,
        time_day=day,
        time_month=month,
        time_year=year,
        current_city_id=city_id,
        log=MessageLog(capacity=40),
    )
    for key, value in extra.items():
        setattr(ctx, key, value)
    return ctx
