"""NPCs: guild NPCs that stand inside the city's labeled buildings.

NPCs live in two places:

  * Here (``NPC`` + ``NPCS``) - static catalog entries describing the
    character (name, guild, flavor line, glyph).
  * :mod:`spacehack.world` - :class:`spacehack.world.Entity` instances
    that point back at a catalog entry via ``entity.npc_id``.

The talk dialog reads the catalog entry from the entity's ``npc_id``;
collision / rendering use the entity's normal ``width`` / ``height`` /
``char``. Job-pick UI, accept/reward flow, and class-gated catalogs
are intentionally out of scope for this iteration: walking onto an
NPC opens a short flavor dialog and the player presses ESC to leave.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class NPC:
    """A guild NPC you can talk to in the city."""
    id: str         # catalog key
    name: str       # display name shown in the dialog header
    guild: str      # thematic guild (matches the building's label)
    char: str       # ASCII glyph drawn at the NPC's tile
    fg: tuple[int, int, int]
    flavor_text: str  # one short line of dialog shown in the modal


# The four starting NPCs, each one matches a building in make_city.
# Char + fg chosen so each is visually distinct.
NPCS: tuple[NPC, ...] = (
    NPC(
        id="barkeep",
        name="Bartender",
        guild="bar",
        char="b",
        fg=(255, 210, 110),                                          # bright yellow
        flavor_text=(
            "I hear things. Rumors, contracts, the names of folk in "
            "trouble. Ask around."
        ),
    ),
    NPC(
        id="guild_master",
        name="Guild Master",
        guild="merchants",
        char="G",
        fg=(255, 230, 110),                                          # bright gold
        flavor_text=(
            "Trade routes open, trade routes close. Coin flows. "
            "Mind the tariffs."
        ),
    ),
    NPC(
        id="militia_captain",
        name="Captain",
        guild="militia",
        char="K",
        fg=(130, 230, 220),                                          # vivid teal
        flavor_text=(
            "Order above all. Walk the beat, report what you see, "
            "and keep your weapon sheathed until it isn't."
        ),
    ),
    NPC(
        id="bounty_master",
        name="Bounty Master",
        guild="bhguild",
        char="D",
        fg=(255, 130, 200),                                          # vivid magenta
        flavor_text=(
            "Wanted: fugitives, smugglers, debt-skippers. Bring "
            "them in alive if you can, dead if you must."
        ),
    ),
    # Science officer stationed at Alpha Centauri's Science
    # Port (see data/planets/ac_station.py). Future missions
    # with giver_npc_id='research_officer' route through this
    # NPC. Char 'S' + faint teal contrast with the other guild
    # NPCs so the lab reads as separate from the bar / guild
    # hall / militia / bounty rooms.
    NPC(
        id='research_officer',
        name='Research Officer',
        guild='lab',
        char='S',
        fg=(150, 220, 200),                                   # teal / science-cyan
        flavor_text=(
            'Long-baseline stellar studies, mostly. Every so '
            'often the data asks us a question - that is when '
            'the pay gets interesting.'
            ),
    ),
)


_BY_ID: dict[str, NPC] = {n.id: n for n in NPCS}


def find_npc(npc_id: str) -> NPC:
    """Look up a :class:`NPC` catalog entry by id.

    Raises :class:`KeyError` if no NPC has that id - mirrors the
    look-up-by-id contract used elsewhere in the project (see
    :func:`spacehack.character.find_species`).
    """
    try:
        return _BY_ID[npc_id]
    except KeyError:
        raise KeyError(f"unknown npc id: {npc_id!r}") from None
