"""Enemy identity lint (doc 48 phase 3, SETTLED 32/33/34).

Rules against the spec data, run by the standard gate:

* SHIP — every NPC ship flies its hull's own glyph, and every faction
  shares exactly ONE family color (neutral derelicts keep the
  amber/brass pair). Class twins render identical by design.
* FAMILY — every faction-tagged ground spec and every listed machine
  belongs to a :data:`CHAR_CLASS_FAMILIES` family: its char is a case
  variant of the family letter and its fg is the family color
  exactly. Fauna (factionless monsters) are not families.
* SEPARATION — family colors of different identity groups in the same
  theater stay max-channel distance >=
  :data:`SEPARATION_MIN` apart. This is what legalizes reusing a char
  across families (SETTLED 34 addition): the (glyph, color) PAIR is
  the identity.
* CROSS-REGISTRY — ground/space glyph overlap among hostile-capable
  faces equals exactly the pinned set; a new overlap fails.
"""

from src.spacehack import world
from src.spacehack.data.npc_chars import (
    CHAR_CLASS_FAMILIES,
    CharClassFamily,
    list_npc_chars,
)
from src.spacehack.data.npc_ships import list_npc_ships
from src.spacehack.data.ships import find_ship
from src.spacehack.framebuffer import FrameBuffer
from src.spacehack.world_render import world_draw_commands

# Pairwise family-color separation floor (max-channel RGB distance).
SEPARATION_MIN = 60

# The full tolerated ground/space glyph overlap among hostile-capable
# faces (doc 48 phase 3 + phase 6): the scout hull meets the rock
# scavenger; the hauler hull meets the ground Merchant row (never
# co-rendered — a boarded deck replaces the space map).
CROSS_REGISTRY_PIN = {"s", "h"}


def _hostile_capable(spec) -> bool:
    """Ground spec that can fight the player (fauna + faction rows)."""
    return spec.faction != "civilian" or spec.always_hostile


def _max_channel_distance(a, b) -> int:
    return max(abs(x - y) for x, y in zip(a, b))


def _family_for(spec) -> CharClassFamily | None:
    for family in CHAR_CLASS_FAMILIES.values():
        if family.faction and spec.faction == family.faction:
            return family
        if spec.id in family.members:
            return family
    return None


def test_ground_family_membership_and_shape():
    faction_families = {
        family.faction for family in CHAR_CLASS_FAMILIES.values()
        if family.faction
    }
    listed_members = {
        spec_id
        for family in CHAR_CLASS_FAMILIES.values()
        for spec_id in family.members
    }
    for spec in list_npc_chars():
        family = _family_for(spec)
        if spec.faction:
            # Every faction-tagged row MUST belong to a family — a new
            # faction (merchant crew, phase-11 rungs) fails the lint
            # until its family is authored, never silently.
            assert family is not None, (
                f"{spec.id} (faction {spec.faction!r}) has no family — "
                "author its CHAR_CLASS_FAMILIES entry"
            )
        if spec.faction in faction_families or spec.id in listed_members:
            assert spec.char in (
                family.letter.lower(), family.letter.upper(),
            ), (
                f"{spec.id} char {spec.char!r} is not a case variant of "
                f"family letter {family.letter!r}"
            )
            assert spec.fg == family.color, (
                f"{spec.id} fg {spec.fg} != family color {family.color}"
            )
        else:
            assert family is None, (
                f"{spec.id} unexpectedly matches a family — fauna must "
                "stay out of CHAR_CLASS_FAMILIES"
            )


def test_ground_family_members_exist():
    ids = {spec.id for spec in list_npc_chars()}
    for name, family in CHAR_CLASS_FAMILIES.items():
        for spec_id in family.members:
            assert spec_id in ids, (
                f"family {name!r} lists unknown member {spec_id!r}"
            )


def test_ground_context_glyph_color_pairs_unique():
    # SETTLED 35: the identity key is (char, fg, elite) — a bold
    # variant of a family letter never collides with its plain case
    # (the brute vs the rifleman, the sniper vs the marine).
    pairs: dict[tuple[str, tuple[int, int, int], bool], str] = {}
    for spec in list_npc_chars():
        if not _hostile_capable(spec):
            continue
        key = (spec.char, spec.fg, spec.elite)
        assert key not in pairs, (
            f"{spec.id} and {pairs[key]} share identity {key} "
            "in the ground context"
        )
        pairs[key] = spec.id


def test_ground_families_separate():
    names = sorted(CHAR_CLASS_FAMILIES)
    for i, first in enumerate(names):
        for second in names[i + 1:]:
            distance = _max_channel_distance(
                CHAR_CLASS_FAMILIES[first].color,
                CHAR_CLASS_FAMILIES[second].color,
            )
            assert distance >= SEPARATION_MIN, (
                f"ground families {first!r} and {second!r} sit {distance} "
                f"apart (< {SEPARATION_MIN}): "
                f"{CHAR_CLASS_FAMILIES[first].color} vs "
                f"{CHAR_CLASS_FAMILIES[second].color}"
            )


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


def _map_with(entity: world.Entity) -> world.GameMap:
    tile = world.Tile("floor", ".", True, (200, 210, 220), (10, 20, 30))
    return world.GameMap(
        width=4, height=3,
        tiles=[[tile for _ in range(4)] for _ in range(3)],
        entities=[entity],
    )


def _ship_entity(spec_id: str) -> world.Entity:
    """Build through the REAL spawn factory so a dropped `bold=`
    at any construction site fails this test, not a playtest."""
    from src.spacehack import npc_ships
    from src.spacehack.data.npc_ships import find_npc_ship

    spec = find_npc_ship(spec_id)
    return npc_ships._make_npc_entity(spec, world.Position(1, 1), "lint_squad")


def _entity_commands(entity: world.Entity):
    game_map = _map_with(entity)
    return world_draw_commands(
        game_map, region_x=0, region_y=0, region_w=4, region_h=3,
    )


def test_flagship_specs_carry_elite():
    elite = {spec.id for spec in list_npc_ships() if spec.elite}
    assert elite == {"pirate_captain", "pirate_warlord"}


def test_ground_elite_specs_carry_elite():
    # SETTLED 34/35: the brute and the sniper are the named wearers.
    elite = {
        spec.id for spec in list_npc_chars() if spec.elite
    }
    assert elite == {"pirate_brute", "militia_sniper"}


def _ground_entity(spec_id: str) -> world.Entity:
    """Build through the REAL squad factory so a dropped `bold=`
    at any ground construction site fails this test, not a playtest."""
    from src.spacehack.data.npc_chars import find_npc_char
    from src.spacehack.dungeon_population import _scatter_squad

    spec = find_npc_char(spec_id)
    entities: list = []
    _scatter_squad(
        entities, set(),
        enemy_id=spec_id, cells=[(1, 1)], count=1,
        squad_id="lint_squad", char=spec.char, fg=spec.fg,
        band=3, bold=spec.elite,
    )
    return entities[0]


def test_elite_ground_entity_renders_bold_command():
    from src.spacehack.data.npc_chars import find_npc_char

    for spec_id in ("pirate_brute", "militia_sniper"):
        commands = _entity_commands(_ground_entity(spec_id))
        glyph = find_npc_char(spec_id).char
        entity_commands = [c for c in commands if c.char == glyph]
        assert entity_commands and all(c.bold for c in entity_commands), (
            f"{spec_id} must render its glyph bold"
        )


def test_normal_ground_entity_renders_plain_command():
    commands = _entity_commands(_ground_entity("militia_marine"))
    entity_commands = [c for c in commands if c.char == "M"]
    assert entity_commands and not any(c.bold for c in entity_commands)


def test_elite_entity_renders_bold_command():
    for spec_id in ("pirate_captain", "pirate_warlord"):
        commands = _entity_commands(_ship_entity(spec_id))
        entity_commands = [c for c in commands if c.char == "F"]
        assert entity_commands and all(c.bold for c in entity_commands), (
            f"{spec_id} must render its glyph bold"
        )


def test_normal_entity_renders_plain_command():
    commands = _entity_commands(_ship_entity("pirate_raider"))
    entity_commands = [c for c in commands if c.char == "C"]
    assert entity_commands and not any(c.bold for c in entity_commands)


def test_bold_survives_console_round_trip():
    console = FrameBuffer(4, 3)
    for command in _entity_commands(_ship_entity("pirate_warlord")):
        console.print(
            x=command.x, y=command.y, string=command.char, fg=command.fg,
            preserve_underlay=command.preserve_underlay,
            underlay_char=command.underlay_char,
            underlay_fg=command.underlay_fg,
            underlay_bg=command.underlay_bg,
            bold=command.bold,
        )
    rebuilt = [
        c for c in console.to_commands() if c.preserve_underlay
    ]
    assert rebuilt and all(c.bold for c in rebuilt)


def test_bystander_rename_alias_resolves_old_saves():
    from src.spacehack.data.npc_chars import find_npc_char

    old = find_npc_char("civillian_bystander")
    new = find_npc_char("civilian_bystander")
    assert old is new
    assert new.id == "civilian_bystander"


def test_misspelled_bystander_id_survives_only_as_alias():
    """The typo lives in exactly one place: the alias table."""
    from pathlib import Path

    repo = Path(__file__).resolve().parents[1]
    strays = [
        str(path.relative_to(repo))
        for path in sorted((repo / "src").rglob("*.py"))
        if "civillian" in path.read_text()
    ]
    assert strays == ["src/spacehack/data/npc_chars/__init__.py"], (
        f"stray 'civillian' refs outside the alias file: {strays}"
    )


def test_flee_threshold_field_is_retired():
    """Fleeing is ruled out (doc 48 SETTLED 20) — the field is gone."""
    import pytest

    from src.spacehack.data.npc_ships import NpcShipSpec

    with pytest.raises(TypeError):
        NpcShipSpec(
            id="x", name="X", char="s", fg=(1, 2, 3),
            ship_id="scout", faction="pirate",
            ai_flee_threshold=0.15,
        )
