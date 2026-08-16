"""Trade goods catalog: the "what" of the economy system.

Each trade good is a frozen :class:`TradeGood` dataclass. Adding a
new good is one entry in the ``TRADE_GOODS`` tuple in
:mod:`core` — no if/else chains, no dispatcher rewrites.

Mirrors the pattern established by ``data/weapons/__init__.py``
(module-level registry with lazy build + find helper + KeyError
on miss).
"""

from __future__ import annotations

from dataclasses import dataclass, replace


@dataclass(frozen=True)
class TradeGood:
    """One purchasable / sellable / lootable trade good.

    Attributes:
        id:          registry key, e.g. ``"food_rations"``.
        name:        display name, e.g. ``"Food Rations"``.
        description: short flavour blurb for tooltips.
        base_price:  reference price in credits before supply/demand modifiers.
        category:    ``"industrial"`` | ``"biological"`` | ``"luxury"``
                     | ``"raw_material"`` | ``"tech"`` | ``"contraband"``.
        volume:      cargo units consumed per crate (1 typical, 2 for bulk).
        rarity:      0.0 = always available, 1.0 = very rare (loot weight).
    """
    id: str
    name: str
    description: str
    base_price: int
    category: str
    volume: int = 1
    rarity: float = 0.5


# Lazy-built registry
_BY_ID: dict[str, TradeGood] | None = None


def _build_registry() -> dict[str, TradeGood]:
    from . import core as _core
    from ...text import overlay as _text_overlay
    _text = _text_overlay()
    combined: dict[str, TradeGood] = {}
    for g in _core.TRADE_GOODS:
        _name_key = f"good.{g.id}.name"
        _desc_key = f"good.{g.id}.description"
        _name = _text[_name_key] if _name_key in _text else g.name
        _desc = _text[_desc_key] if _desc_key in _text else g.description
        if _name != g.name or _desc != g.description:
            g = replace(g, name=_name, description=_desc)
        combined[g.id] = g
    return combined


def _registry() -> dict[str, TradeGood]:
    global _BY_ID
    if _BY_ID is None:
        _BY_ID = _build_registry()
    return _BY_ID


def find_trade_good(good_id: str) -> TradeGood:
    """Look up a :class:`TradeGood` by id; raises :class:`KeyError` on miss."""
    try:
        return _registry()[good_id]
    except KeyError:
        raise KeyError(f"unknown trade good id: {good_id!r}") from None


def display_name(good_id: str) -> str:
    """Return a good's display name, falling back to a title-cased id.

    Virtual mission cargo (e.g. the lab chain's ``door_data``) has no
    catalog entry, so the raw id is title-cased instead.
    """
    try:
        return _registry()[good_id].name
    except KeyError:
        return good_id.replace("_", " ").title()


def reload_text_overlay() -> None:
    """Re-parse the text overlay and rebuild the catalog (dev F5)."""
    global _BY_ID
    from ...text import reload as _reload_text
    _reload_text()
    _BY_ID = None


def neutral_goods(spec) -> list[str]:
    """Return non-contraband goods in the full catalog that aren't
    in this planet's produces or demands."""
    from . import core as _core
    _seen = set(gid for gid, _ in spec.produces) | set(gid for gid, _ in spec.demands)
    return [_g.id for _g in _core.TRADE_GOODS if _g.id not in _seen and _g.category != "contraband"]


__all__ = ["TradeGood", "find_trade_good", "display_name", "neutral_goods", "reload_text_overlay"]
