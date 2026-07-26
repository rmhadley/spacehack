"""NPC runtime layer: dialog helpers and data facade.

NPCs live in two layers:

  * :mod:`spacehack.data.npcs` — the static catalog (the :class:`NPC`
    dataclass + per-guild tuples + :func:`find_npc` / :func:`list_npcs`
    lookup helpers). Adding a new NPC is a one-file edit there.
  * Here — the facade that re-exports the data-layer symbols so
    consumers (e.g. ``spacehack.__main__``) can keep using
    ``npc_module.NPC`` / ``npc_module.find_npc`` without a second
    import line. Future iterations will add runtime dialog helpers
    here when they are extracted from ``__main__.py``.

Mirrors the pattern established by :mod:`spacehack.mission`, which
re-exports its data module's symbols identically.
"""

from .data.npcs import NPC, find_npc, list_npcs


# IDENTITY GUARANTEE: ``npc_module.NPC is NPC`` (and ditto for
# find_npc / list_npcs). Smoke-verified at the registry build site
# so a future refactor that accidentally drops the re-exports (or
# wraps the symbol in a proxy) breaks the identity check rather
# than silently changing consumer semantics.
__all__ = [
    "NPC",
    "find_npc",
    "list_npcs",
]
