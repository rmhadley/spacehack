"""Enemy identity lint (doc 48 phase 3, SETTLED 32/33/34).

Rules against the spec data, run by the standard gate:

* SHIP — every NPC ship flies its hull's own glyph, and every faction
  shares exactly ONE family color (neutral derelicts keep the
  amber/brass pair). Class twins render identical by design.
* SEPARATION — family colors of different identity groups in the same
  theater stay max-channel distance >=
  :data:`SEPARATION_MIN` apart. This is what legalizes reusing a char
  across families (SETTLED 34 addition): the (glyph, color) PAIR is
  the identity.
* CROSS-REGISTRY — ground/space glyph overlap among hostile-capable
  faces equals exactly the pinned set; a new overlap fails.
"""

from src.spacehack.data.npc_chars import list_npc_chars
from src.spacehack.data.npc_ships import list_npc_ships
from src.spacehack.data.ships import find_ship

# Pairwise family-color separation floor (max-channel RGB distance).
SEPARATION_MIN = 60

# The full tolerated ground/space glyph overlap among hostile-capable
# faces (doc 48 phase 3): the scout hull meets the rock scavenger.
CROSS_REGISTRY_PIN = {"s"}


def _hostile_capable(spec) -> bool:
    """Ground spec that can fight the player (fauna + faction rows)."""
    return spec.faction != "civilian" or spec.always_hostile


def _max_channel_distance(a, b) -> int:
    return max(abs(x - y) for x, y in zip(a, b))


def test_ship_glyph_is_its_hull_char():
    for spec in list_npc_ships():
        hull = find_ship(spec.ship_id)
        assert spec.char == hull.char, (
            f"{spec.id} char {spec.char!r} != hull {hull.id} char {hull.char!r}"
        )


def test_ship_faction_family_is_one_color():
    colors: dict[str, set[tuple[int, int, int]]] = {}
    for spec in list_npc_ships():
        colors.setdefault(spec.faction, set()).add(spec.fg)
    for faction, palette in sorted(colors.items()):
        if faction == "neutral":
            # Derelicts keep the amber/brass wreck pair (SETTLED 33).
            continue
        assert len(palette) == 1, (
            f"ship faction {faction!r} carries {len(palette)} colors: "
            f"{sorted(palette)} — family color must be exactly one"
        )


def test_ship_families_separate():
    palette: dict[str, set[tuple[int, int, int]]] = {}
    for spec in list_npc_ships():
        palette.setdefault(spec.faction, set()).add(spec.fg)
    factions = sorted(palette)
    for i, first in enumerate(factions):
        for second in factions[i + 1:]:
            for first_color in palette[first]:
                for second_color in palette[second]:
                    distance = _max_channel_distance(first_color, second_color)
                    assert distance >= SEPARATION_MIN, (
                        f"ship factions {first!r} and {second!r} sit "
                        f"{distance} apart (< {SEPARATION_MIN}): "
                        f"{first_color} vs {second_color}"
                    )


def test_cross_registry_glyph_overlap_is_pinned():
    ground = {spec.char for spec in list_npc_chars() if _hostile_capable(spec)}
    space = {spec.char for spec in list_npc_ships()}
    overlap = ground & space
    assert overlap == CROSS_REGISTRY_PIN, (
        f"ground/space glyph overlap {sorted(overlap)} != pinned "
        f"{sorted(CROSS_REGISTRY_PIN)}"
    )
