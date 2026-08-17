"""Market-intel presentation for the trade terminal (merchant-guild intel).

Terminal rows are colour-coded by a good's role at the current station so the
player can read at a glance what to buy/sell — no multipliers shown. The cues
and the Market tab's detail ramp with the player's merchant reputation:

  enemy/disliked → flat catalog, no grouping, no colours (guild withholds)
  neutral        → grouped WANTS / SELLS CHEAP / OTHER with colour cues
  liked          → adds per-good headroom detail
  allied         → adds the guild network (best sell destination per held good)

All trade-domain helpers live in :mod:`spacehack.trade` and are imported
lazily here to avoid a load-time import cycle (the trade terminal imports
this module for its frame builders).
"""
from __future__ import annotations


def _withheld_rows(station_goods):
    """Flat catalog shown while the guild withholds market intel."""
    from . import pygame_split
    from .data.trade_goods import find_trade_good

    rows = [pygame_split.SplitRow(
        "The guild shares no market data with you.", "",
        "Improve your standing with the Merchant Guild to unlock market intel.",
        "MARKET:INFO",
    )]
    rows.extend(
        pygame_split.SplitRow(
            find_trade_good(gid).name, "", find_trade_good(gid).description,
            "MARKET:INFO",
        )
        for gid in station_goods
    )
    return tuple(rows)


def _role_group_rows(ctx, planet_id, spec, station_goods, role, header, liked):
    """Rows for one market section (wants / sells cheap / other)."""
    from . import pygame_split
    from .data.trade_goods import find_trade_good
    from .trade import _good_headroom, good_market_role

    group = [gid for gid in station_goods if good_market_role(spec, gid) == role]
    if not group:
        return []
    rows = [pygame_split.section_header(header)]
    for gid in group:
        good = find_trade_good(gid)
        detail = _good_headroom(ctx, planet_id, gid) if liked else good.description
        rows.append(pygame_split.SplitRow(
            good.name,
            _ROLE_LABEL[role],
            detail,
            "MARKET:INFO",
            fg=_ROLE_FG.get(role),
        ))
    return rows


def _market_rows(ctx, planet_id: str) -> tuple:
    """Left-panel rows for the MARKET tab; detail ramps with merchant rep."""
    from .data.planets import find_planet_spec
    from .trade import _market_intel_enabled, _merchant_attitude, _station_goods_for

    spec = find_planet_spec(planet_id)
    station_goods = _station_goods_for(spec)
    if not _market_intel_enabled(ctx):
        return _withheld_rows(station_goods)
    attitude = _merchant_attitude(ctx)
    liked = attitude in ("liked", "allied")
    rows = []
    for role, header in (
        ("demand", "STATION WANTS"),
        ("surplus", "SELLS CHEAP"),
        ("neutral", "OTHER GOODS"),
    ):
        rows.extend(
            _role_group_rows(ctx, planet_id, spec, station_goods, role, header, liked)
        )
    if attitude == "allied":
        rows.extend(_guild_network_rows(ctx, planet_id, ctx.player_owned_ship))
    return tuple(rows)


def _network_row(ctx, planet_id: str, gid: str, visited):
    """One guild-network row for a held good, or None when it has no buyers."""
    from . import pygame_split
    from .data.planets import find_planet_spec
    from .data.trade_goods import find_trade_good
    from .trade import _best_sell_planet, _can_sell_here, good_market_role

    good = find_trade_good(gid)
    best = _best_sell_planet(ctx, planet_id, gid, visited)
    if best is None:
        return None
    detail = " ".join(
        f"{find_planet_spec(pid).name}: {_ROLE_LABEL[good_market_role(find_planet_spec(pid), gid)]}"
        for pid in visited if _can_sell_here(pid, gid)
    )
    return pygame_split.SplitRow(
        good.name,
        find_planet_spec(best).name,
        detail,
        "MARKET:INFO",
        fg=_ROLE_FG.get(good_market_role(find_planet_spec(best), gid)),
    )


def _guild_network_rows(ctx, planet_id: str, owned) -> list:
    """Allied-tier guild-network rows: best sell destination per held good."""
    from . import pygame_split

    rows = [pygame_split.section_header("GUILD NETWORK (VISITED)")]
    visited = [pid for pid in ctx.economy_state if pid != planet_id]
    if not visited:
        rows.append(pygame_split.SplitRow(
            "No other market data yet", "",
            "Fly to more ports to build the guild's price network.",
            "MARKET:INFO",
        ))
        return rows
    placed = False
    for gid, _qty in (owned.inventory.items() if owned is not None else ()):
        row = _network_row(ctx, planet_id, gid, visited)
        if row is None:
            continue
        placed = True
        rows.append(row)
    if not placed:
        rows.append(pygame_split.SplitRow(
            "Nothing in your hold to place", "",
            "Fill your hold to see where the guild would route it.",
            "MARKET:INFO",
        ))
    return rows


def _trade_hint(mode: str) -> str:
    """Trade-terminal hint, advertising the Market tab in both modes."""
    from . import pygame_ui

    parts = ("T trade", "M market", pygame_ui.NAV_HINT, "TAB switch panel")
    if mode == "TRADE":
        parts = (*parts, "ENTER buy/sell")
    return pygame_ui.modal_hint(*parts, "ESC back", pygame_ui.GUIDE_HINT)


# Colour cues + role labels live here so the frame builders and the Market
# tab share one source of truth (see trade.good_market_role for the rules).
_ROLE_FG: dict[str, tuple[int, int, int]] = {
    "demand": (255, 190, 80),     # amber — the station wants this (sell it here)
    "surplus": (120, 220, 230),   # cyan — the station has plenty (buy it here)
}

_ROLE_LABEL: dict[str, str] = {
    "demand": "paying well",
    "surplus": "plentiful",
    "neutral": "fair",
}


__all__ = ["_market_rows", "_trade_hint"]
