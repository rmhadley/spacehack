"""Dev-mode overrides for playtesting.

When the ``SPACEHACK_DEV`` environment variable is set, the player
starts with a super-powered frigate, maxed modules, and 999,999
credits. Call :func:`apply_dev_overrides` right before building
:class:`GameContext` so the overrides are in place before the
game loop starts.

Extracted from ``__main__.py`` to keep the entry point clean and
make dev-mode easy to extend (debug overlay, god-mode toggle, etc.)
"""

from __future__ import annotations

from typing import Any

from . import ship as ship_module


def apply_dev_overrides(
    starter_ship: Any,
    starter_entity: Any,
    player_owned_ship: Any,
    stats: Any,
    log: Any,
) -> tuple[Any, Any, Any]:
    """If ``SPACEHACK_DEV`` is set, grant a super-powered frigate.

    Mutates ``stats`` and ``log`` in-place (they're mutable objects)
    and returns ``(starter_ship, starter_entity, player_owned_ship)``
    with the frigate override applied. If the env var is not set,
    returns the same objects unchanged.

    Call this right before :class:`GameContext` construction so the
    overridden values flow into ctx without the caller needing to
    know whether dev mode is active.
    """
    import os as _os

    if not _os.environ.get("SPACEHACK_DEV"):
        return starter_ship, starter_entity, player_owned_ship

    frigate = ship_module.find_ship("frigate")
    starter_ship = frigate
    starter_entity.char = frigate.char
    starter_entity.fg = frigate.fg
    starter_entity.name = f"Your Ship: {frigate.name}"
    starter_entity.ship_id = frigate.id
    player_owned_ship = ship_module.OwnedShip(
        ship_id="frigate",
        weapons=(
            "plasma_cannon", "plasma_cannon", "plasma_cannon", "plasma_cannon",
            "heavy_missile", "heavy_missile", "heavy_missile", "heavy_missile",
        ),
        modules=(
            "reactor_mk4", "shield_mk4", "shield_recharger",
            "targeting_mk4", "gyro_mk4", "armor_mk4",
        ),
        fuel=999,
    )
    stats.credits = 999999
    log.add("[DEV MODE] Super-powered frigate + 999,999 credits.")
    return starter_ship, starter_entity, player_owned_ship
