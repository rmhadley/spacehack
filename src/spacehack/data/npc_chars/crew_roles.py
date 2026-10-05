"""Per-faction crew role tables (doc 48 SETTLED 28/38).

One geometry serves every faction: authored ``ENEMY:`` markers name
faction-neutral ROLE tokens, and these tables resolve role -> spec id
at layout load (``dungeon_layout._resolve_crew_marker``). Raw spec ids
stay legal for authored specials (the survey wreck's pinned consortium
crew). An omitted role means the faction fields no such face — its
markers skip at load (militia stowaways).
"""

from __future__ import annotations

# The marker vocabulary (SETTLED 28). A directive id in this set is a
# role token, never a spec id.
CREW_ROLE_TOKENS: frozenset[str] = frozenset({
    "line", "heavy", "marksman", "security_drone", "stowaway",
})

CREW_ROLES: dict[str, dict[str, str]] = {
    "pirate": {
        "line": "pirate_raider",
        "heavy": "pirate_brute",
        "marksman": "pirate_rifleman",
        "security_drone": "sentry_drone",
        "stowaway": "hull_parasite",
    },
    "militia": {
        "line": "militia_trooper",
        # The sniper IS the heavy-hitting row (SETTLED 10): one
        # perched elite per deck's heavy slot; the marksman markers
        # field the strike-crew marines in their authored squads
        # (user swap ruling, 2026-09-23 — amends SETTLED 38's lean).
        "heavy": "militia_sniper",
        "marksman": "militia_marine",
        "security_drone": "sentry_drone",
        # stowaway omitted (weight 0, SETTLED 38) — the marker stays
        # legal; a militia deck simply never boards parasites.
    },
    "merchant": {
        # SETTLED 7/38: honest light crew + droids as the entire
        # defense shape — the droid dial rides the security_drone role.
        "line": "merchant",
        "heavy": "assault_drone",
        "marksman": "sentry_drone",
        "security_drone": "sentry_drone",
        "stowaway": "hull_parasite",
    },
    "consortium": {
        # Authored decks only (SETTLED 12): nothing procedural resolves
        # through this table. The heavy IS the Executor (SETTLED 51):
        # cruiser_crew's CHANCE slot (~40% of boarded Hunters) and
        # frigate_crew's GUARANTEED marker (every boarded Dreadnought)
        # both resolve here — one geometry serves every faction.
        "line": "consortium_enforcer",
        "heavy": "consortium_executor",
        "marksman": "consortium_gunner",
        "security_drone": "sentry_drone",
        "stowaway": "hull_parasite",
    },
}
