"""NPC catalog: guild NPCs that stand inside city buildings.

Each NPC is a frozen :class:`NPC` dataclass. Adding a new NPC is one
entry in the :data:`_NPC_TUPLES` list (or a new file under this
package) - no if/else chains, no dispatcher rewrites.

The :mod:`spacehack.world.Entity` system references a catalog entry
by id via ``entity.npc_id``. Planet-specific dialogue overrides live
on the planet (``PlanetSpec.npc_overrides``) and the loader in
:mod:`spacehack.data.planets` resolves an npc_id through the
override map first, then through this global catalog.
"""

from __future__ import annotations

from dataclasses import dataclass, replace


@dataclass(frozen=True)
class NPC:
    """A guild NPC the player can talk to in the city.

    Attributes:
        id: registry key, e.g. ``\"barkeep\"``.
        name: display name shown in the dialog header.
        guild: thematic guild (matches the building's label).
        char: ASCII glyph drawn at the NPC's tile.
        fg: foreground colour for ``char``.
        flavor_text: one short line of dialog shown in the modal.
    """
    id: str
    name: str
    guild: str
    char: str
    fg: tuple[int, int, int]
    flavor_text: str


# Per-file NPC tuples — append an import + line in
# ``_build_registry`` when adding a new file (mirrors how
# ``data/weapons/__init__.py`` picks up new weapon modules).


def _build_registry() -> dict[str, "NPC"]:
    from . import guilds as guilds_module
    from ...text import overlay as _text_overlay
    _text = _text_overlay()
    combined: dict[str, NPC] = {}
    for n in guilds_module.NPCS:
        _key = f"npc.{n.id}.flavor_text"
        combined[n.id] = (
            replace(n, flavor_text=_text[_key]) if _key in _text else n
        )
    return combined


_BY_ID: dict[str, NPC] | None = None


def _registry() -> dict[str, NPC]:
    global _BY_ID
    if _BY_ID is None:
        _BY_ID = _build_registry()
    return _BY_ID


def find_npc(npc_id: str) -> NPC:
    """Look up an :class:`NPC` by id; raises :class:`KeyError` on miss.

    Mirrors the look-up-by-id contract used by every other catalog
    so call sites don't have to special-case missing bodies.
    """
    try:
        return _registry()[npc_id]
    except KeyError:
        raise KeyError(f"unknown npc id: {npc_id!r}") from None


def list_npcs() -> tuple[NPC, ...]:
    """All registered NPCs (undefined order)."""
    return tuple(_registry().values())


def reload_text_overlay() -> None:
    """Re-parse the text overlay and rebuild the catalog (dev F5)."""
    global _BY_ID
    from ...text import reload as _reload_text
    _reload_text()
    _BY_ID = None


__all__ = ["NPC", "find_npc", "list_npcs", "reload_text_overlay"]
