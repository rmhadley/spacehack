"""Guild NPCs the player can talk to in the city.

Each entry ties to a building label on Earth/Mars/etc. via
``guild`` so a planet-local building 'bar' resolves to NPC id
``barkeep``. Planet overrides (e.g. Mars Barkeep) live in the
``PlanetSpec.npc_overrides`` tuple, not here - this file is the
default catalog the :func:`spacehack.data.planets._resolve_npc_entity`
loader falls back to when no planet-local override matches.

Char + fg chosen so each NPC is visually distinct (bright yellow
bar, gold guild master, teal militia, magenta bounty, science-cyan
research officer).
"""
from . import NPC


NPCS: tuple[NPC, ...] = (
    NPC(
        id="barkeep",
        name="Bartender",
        guild="bar",
        char="b",
        fg=(255, 210, 110),                            # bright yellow
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
        fg=(255, 230, 110),                            # bright gold
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
        fg=(130, 230, 220),                            # vivid teal
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
        fg=(255, 130, 200),                            # vivid magenta
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
        id="research_officer",
        name="Research Officer",
        guild="lab",
        char="S",
        fg=(150, 220, 200),                            # teal / science-cyan
        flavor_text=(
            "Long-baseline stellar studies, mostly. Every so "
            "often the data asks us a question - that is when "
            "the pay gets interesting."
        ),
    ),
    # Depot attendant — generic refueling-station NPC found at deep-space
    # depots (Epsilon Eridani, Tau Ceti). Warm grey palette so the depot
    # reads as 'maintenance / utility' rather than a guild hall.
    NPC(
        id="depot_attendant",
        name="Attendant",
        guild="depot",
        char="A",
        fg=(200, 200, 180),                         # warm grey
        flavor_text=(
            "Fuel pumps are online. The deep-space run is long — "
            "make sure your tanks are topped before you push further out."
        ),
    ),
    # Militia blockade officer — stationed at Luyten's Star, the edge
    # of charted space. Reuses the "depot" city layout (so the player
    # lands at the same interior) but the NPC override on Luyten's
    # Star replaces the standard attendant with this militia face.
    NPC(
        id="blockade_officer",
        name="Blockade Officer",
        guild="militia",
        char="K",
        fg=(130, 230, 220),                         # teal (militia colour)
        flavor_text=(
            "This is the line. Past Luyten's Star is uncharted space — "
            "no patrols, no beacons, no backup. Turn back while you still can."
        ),
    ),
)
