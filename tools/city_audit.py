#!/usr/bin/env python3
"""City audit tool — dump a city's final built map and validate rules against it.

Step 1: build the city through the real ``city_builder.build_city`` pipeline
        (the exact path the game uses) and print the final ``GameMap`` as
        structured JSON.
Step 2: run validation rules against that map. Currently one rule:

        R1 — a transit station is only valid when it AND its 3x3 pad
             actually exist and are clean: the station cell and every cell
             of its pad zone must be transit_bay tiles (the pad was really
             painted, not skipped), no road/sidewalk/building/landing-pad
             tile may intrude into the pad, the station footprint must not
             clip or be clipped by any other entity, and the pad zone must
             not contain any other entity either.

Usage:
    python3 tools/city_audit.py --city earth
    python3 tools/city_audit.py --city earth --format text

Exit codes: 0 = no violations, 1 = violations found.
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

# Allow direct execution from the repository root without requiring an
# editable install, matching the existing tools/*.py conventions.
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from spacehack import world  # noqa: E402
from spacehack.data.planets import find_planet_spec, load_planet  # noqa: E402


# ----- Data model -----------------------------------------------------


@dataclass(frozen=True)
class Violation:
    rule_id: str
    station: str
    other: str
    location: tuple[int, int]
    message: str
    recommendation: dict | None = None
    remediation: str | None = None


# ----- Step 1: build the final map ------------------------------------


def build_final_map(city_id: str) -> world.GameMap:
    """Build the city through the real production pipeline."""
    find_planet_spec(city_id)  # KeyError on unknown id
    return load_planet(city_id)


def dump_map(game_map: world.GameMap, city_id: str) -> dict[str, Any]:
    """Serialize the final ``GameMap`` into a JSON-friendly dict."""
    entities = []
    for e in game_map.entities:
        entry = {
            "name": e.name,
            "char": e.char,
            "pos": [e.pos.x, e.pos.y],
            "width": e.width,
            "height": e.height,
        }
        if e.transit_station_id:
            entry["transit_station_id"] = e.transit_station_id
        if getattr(e, "serves", ""):
            entry["serves"] = e.serves
        entities.append(entry)
    # Building records (from city_buildings metadata): label, display name
    # and the entrance/door cell the station was meant to bring you to.
    buildings = {}
    for label, rec in getattr(game_map, "city_buildings", {}).items():
        entrance = rec.get("entrance")
        buildings[label] = {
            "display_name": rec.get("display_name", label),
            "entrance": list(entrance) if entrance is not None else None,
        }
    # Landmark stamps (fountains, monuments, ...) keyed with the
    # ``<city_id>_city_`` prefix stripped so ``serves`` can target them.
    landmarks = {}
    for key, rec in (getattr(game_map, "landmark_stamps", None) or {}).items():
        short = key.split("_city_", 1)[-1]
        entrance = rec.get("entrance")
        landmarks[short] = {
            "origin": list(rec["origin"]) if rec.get("origin") else None,
            "entrance": list(entrance) if entrance is not None else None,
        }
    return {
        "city_id": city_id,
        "width": game_map.width,
        "height": game_map.height,
        "tiles": [[tile.kind for tile in row] for row in game_map.tiles],
        "entities": entities,
        "buildings": buildings,
        "landmarks": landmarks,
    }


# ----- Step 2: R1 — transit station pad integrity ---------------------


# Remediation text for the "old authoring method" diagnosis: emitted once
# per station when the map has no transit_bay tiles at all.
_OLD_METHOD_REMEDIATION = (
    "This city module authors transit stations the old way (station entity "
    "only, no bay painting). The correct method is to import "
    "paint_transit_bays from city_kit and call it in the layout builder "
    "AFTER terrain painters and door forecourts, passing the bay tile, map "
    "dimensions, and overwrite_kinds covering the base ground kinds the "
    "stations sit on (e.g. frozenset({'floor', 'plaza'})). Stations placed "
    "on terrain not covered by overwrite_kinds will silently get no pad - "
    "this is the failure R1 detects."
)


# Tile kinds a pad zone may never overlap (shared by R1 checks and the
# recommendation search).
_FORBIDDEN_PAD_KINDS = frozenset({
    "road", "sidewalk", "landing_pad", "wall", "door",
    "city_building_wall", "city_building_door", "city_building_floor",
    "city_water", "city_shore", "city_bridge", "void",
})


def _footprint(entity: world.Entity) -> set[tuple[int, int]]:
    """Full rectangle footprint of an entity (pads and ships included)."""
    return {
        (entity.pos.x + dx, entity.pos.y + dy)
        for dx in range(entity.width)
        for dy in range(entity.height)
    }


def check_station_clipping(
    game_map: world.GameMap,
    *,
    pad_radius: int = 1,
) -> list[Violation]:
    """R1: every transit station must sit on a real, clean pad.

    Per station, on the final built map:

    1. The station cell itself must be a ``transit_bay`` tile — if the
       bay painter skipped it (station authored on a tile kind the
       painter won't overwrite), the station has no pad at all.
    2. Every cell of the pad zone (the ``2*pad_radius+1`` square around
       the footprint — the area ``city_kit.paint_transit_bays`` carves)
       must also be ``transit_bay``. A non-bay tile in the zone means the
       painter skipped it (station too close to road/sidewalk/building)
       or something painted over the bay afterwards — either way the pad
       is clipped or was never carved.
    3. No other entity's footprint may touch the station footprint or
       the pad zone — the station must not clip or be clipped by any
       entity, pad included.

    Stations are not checked against each other. Every failing station
    gets a recommended alternative location; stations diagnosed as
    authored the old way (no bay tiles at all) also get the remediation
    text describing the correct authoring method.
    """
    stations = [e for e in game_map.entities if e.transit_station_id]
    others = [e for e in game_map.entities if not e.transit_station_id]

    # All non-station entity footprint cells block candidate locations.
    blocked_cells: set[tuple[int, int]] = set()
    for e in others:
        blocked_cells |= _footprint(e)

    violations: list[Violation] = []
    for station in stations:
        station_cells = _footprint(station)
        pad_zone = _pad_zone(station_cells, game_map, pad_radius)
        first = len(violations)

        # Check 1 + 2: the pad must actually exist — station cell and
        # every pad-zone cell must be transit_bay tiles.
        for x, y in sorted(station_cells | pad_zone):
            kind = game_map.tiles[y][x].kind
            if kind != "transit_bay":
                violations.append(Violation(
                    "R1",
                    station.name,
                    kind,
                    (x, y),
                    f"'{station.name}' pad is not transit_bay at {x},{y}: "
                    f"tile is '{kind}' (pad never painted or clipped)",
                ))

        # Check 3: no other entity may clip the station or its pad.
        protected = station_cells | pad_zone
        for other in others:
            overlap = protected & _footprint(other)
            if overlap:
                cell = min(overlap)
                violations.append(Violation(
                    "R1",
                    station.name,
                    other.name,
                    cell,
                    f"'{station.name}' clips '{other.name}' at {cell}",
                ))

        # Remediation: attach a recommendation + (when the whole map has
        # no bay tiles at all -> old authoring method) remediation text to
        # the station's FIRST violation.
        if len(violations) > first:
            rec = _recommend_location(
                game_map, (station.pos.x, station.pos.y),
                blocked_cells, pad_radius,
            )
            has_any_bay = any(
                game_map.tiles[y][x].kind == "transit_bay"
                for y in range(game_map.height)
                for x in range(game_map.width)
            )
            remediation = None if has_any_bay else _OLD_METHOD_REMEDIATION
            fv = violations[first]
            violations[first] = Violation(
                fv.rule_id, fv.station, fv.other, fv.location, fv.message,
                recommendation=rec, remediation=remediation,
            )
    return violations


def _pad_zone(
    cells: set[tuple[int, int]],
    game_map: world.GameMap,
    radius: int,
) -> set[tuple[int, int]]:
    """Cells within ``radius`` of any footprint cell, clipped to the map
    (the area ``city_kit.paint_transit_bays`` would carve)."""
    zone: set[tuple[int, int]] = set()
    for x, y in cells:
        for dyc in range(-radius, radius + 1):
            for dxc in range(-radius, radius + 1):
                nx, ny = x + dxc, y + dyc
                if game_map.in_bounds(nx, ny):
                    zone.add((nx, ny))
    return zone


def _cell_pad_ok(
    game_map: world.GameMap,
    x: int,
    y: int,
    radius: int,
    blocked_cells: set[tuple[int, int]],
) -> bool:
    """Whether a ``(2*radius+1)`` pad centred at ``(x, y)`` would be valid:
    every zone cell in bounds, walkable, not a forbidden kind, and free of
    other entity footprints."""
    for dyc in range(-radius, radius + 1):
        for dxc in range(-radius, radius + 1):
            nx, ny = x + dxc, y + dyc
            if not game_map.in_bounds(nx, ny):
                return False
            tile = game_map.tiles[ny][nx]
            if tile.kind in _FORBIDDEN_PAD_KINDS or not tile.walkable:
                return False
            if (nx, ny) in blocked_cells:
                return False
    return True


def _recommend_location(
    game_map: world.GameMap,
    origin: tuple[int, int],
    blocked_cells: set[tuple[int, int]],
    radius: int,
) -> dict | None:
    """Closest valid pad location to ``origin``, or ``None``.

    Deterministic: straight-line distance, ties broken by lower y then
    lower x. One pass over the map; non-station entity footprints block
    candidates.
    """
    best_key = None
    best_pos = None
    for y in range(game_map.height):
        for x in range(game_map.width):
            if not _cell_pad_ok(game_map, x, y, radius, blocked_cells):
                continue
            key = ((x - origin[0]) ** 2 + (y - origin[1]) ** 2, y, x)
            if best_key is None or key < best_key:
                best_key = key
                best_pos = (x, y)
    if best_pos is None:
        return None
    dist = best_key[0] ** 0.5
    return {
        "pos": list(best_pos),
        "distance": round(dist, 1),
        "note": (
            f"closest valid {2 * radius + 1}x{2 * radius + 1} pad location; "
            f"move the station to {best_pos} and ensure "
            f"paint_transit_bays overwrite_kinds covers the ground there"
        ),
    }


def _pad_zone(
    cells: set[tuple[int, int]],
    game_map: world.GameMap,
    radius: int,
) -> set[tuple[int, int]]:
    """Cells within ``radius`` of any footprint cell, clipped to the map
    (the area ``city_kit.paint_transit_bays`` would carve)."""
    zone: set[tuple[int, int]] = set()
    for x, y in cells:
        for dyc in range(-radius, radius + 1):
            for dxc in range(-radius, radius + 1):
                nx, ny = x + dxc, y + dyc
                if game_map.in_bounds(nx, ny):
                    zone.add((nx, ny))
    return zone


# ----- Step 3: R2 — station must declare and reach what it serves ------


_MAX_SERVES_DISTANCE = 15.0


def _resolve_target(game_map: world.GameMap, serves: str):
    """Resolve a ``serves`` value to an entrance cell on the built map.

    Checks ``city_buildings`` (by label) and ``landmark_stamps`` (key with
    the ``<city_id>_city_`` prefix stripped). Returns ``(entrance, source)`
    where source is 'building' or 'landmark', or ``(None, None)``.
    """
    rec = (getattr(game_map, "city_buildings", {}) or {}).get(serves)
    if rec is not None:
        return rec.get("entrance"), "building"
    for key, rec in (getattr(game_map, "landmark_stamps", None) or {}).items():
        if key.split("_city_", 1)[-1] == serves:
            return rec.get("entrance"), "landmark"
    return None, None


def check_serves(game_map: world.GameMap, *, max_distance: float = _MAX_SERVES_DISTANCE) -> list[Violation]:
    """R2: every transit station must declare what it serves and that
    target must exist with an entrance near the station.

    1. ``serves`` must be present and non-empty (authored intent, never
       guessed by the tool).
    2. The target must resolve to a building label or landmark key.
    3. The target must have an entrance (door cell).
    4. The entrance must be within ``max_distance`` cells of the station.
    """
    violations: list[Violation] = []
    for station in game_map.entities:
        if not station.transit_station_id:
            continue
        serves = getattr(station, "serves", "") or ""
        if not serves:
            violations.append(Violation(
                "R2",
                station.name,
                "(no serves field)",
                (station.pos.x, station.pos.y),
                f"'{station.name}' does not declare 'serves' — add "
                f"serves=\"<building-or-landmark>\" to its TransitStation "
                f"in the planet spec",
                remediation=(
                    "Add serves=\"<label>\" to this TransitStation in the "
                    "planet spec, naming the building label (see "
                    "city_buildings, e.g. 'bar', 'militia') or the landmark "
                    "key without the <city_id>_city_ prefix (see "
                    "landmark_stamps, e.g. 'plaza' for the fountain). The "
                    "audit tool fails any station without an explicit "
                    "serves declaration."
                ),
            ))
            continue
        entrance, source = _resolve_target(game_map, serves)
        if entrance is None:
            valid = sorted(
                set(getattr(game_map, "city_buildings", {}) or {})
                | {
                    k.split("_city_", 1)[-1]
                    for k in (getattr(game_map, "landmark_stamps", None) or {})
                }
            )
            violations.append(Violation(
                "R2",
                station.name,
                serves,
                (station.pos.x, station.pos.y),
                f"'{station.name}' serves='{serves}' does not match any "
                f"building or landmark (valid: {', '.join(valid)})",
            ))
            continue
        if entrance is None:
            violations.append(Violation(
                "R2",
                station.name,
                serves,
                (station.pos.x, station.pos.y),
                f"'{station.name}' serves='{serves}' ({source}) has no "
                f"entrance/door cell",
            ))
            continue
        dist = ((station.pos.x - entrance[0]) ** 2 + (station.pos.y - entrance[1]) ** 2) ** 0.5
        if dist > max_distance:
            violations.append(Violation(
                "R2",
                station.name,
                serves,
                (station.pos.x, station.pos.y),
                f"'{station.name}' is {dist:.1f} cells from its target "
                f"'{serves}' entrance {tuple(entrance)} (max {max_distance:g})",
                recommendation={
                    "pos": list(entrance),
                    "distance": round(dist, 1),
                    "note": f"target '{serves}' entrance — move the station "
                            f"closer to it",
                },
            ))
    return violations


# ----- Output ---------------------------------------------------------


def report_json(city_id: str, game_map: world.GameMap, violations: list[Violation]) -> str:
    """Full JSON report: map dump + violations."""
    payload = dump_map(game_map, city_id)
    payload["violations"] = [
        {
            "rule_id": v.rule_id,
            "station": v.station,
            "other": v.other,
            "location": list(v.location),
            "message": v.message,
            "recommendation": v.recommendation,
            "remediation": v.remediation,
        }
        for v in violations
    ]
    payload["passed"] = not violations
    return json.dumps(payload, ensure_ascii=False, indent=2)


def report_text(city_id: str, game_map: world.GameMap, violations: list[Violation]) -> str:
    """Human-readable report."""
    lines = [
        f"CITY: {city_id}  ({game_map.width}x{game_map.height}, "
        f"{len(game_map.entities)} entities)",
    ]
    if not violations:
        lines.append("  PASS - no violations.")
        return "\n".join(lines)
    printed_remediation: set[str] = set()
    for v in violations:
        lines.append(f"  [{v.rule_id}] {v.message}")
        if v.recommendation and v.station not in printed_remediation:
            rec = v.recommendation
            lines.append(
                f"      -> recommended: move to {tuple(rec['pos'])} "
                f"(distance {rec['distance']}) — {rec['note']}"
            )
        if v.remediation and v.station not in printed_remediation:
            lines.append(f"      -> REMEDIATION: {v.remediation}")
            printed_remediation.add(v.station)
    lines.append(f"  FAIL - {len(violations)} violation(s).")
    return "\n".join(lines)


# ----- CLI ------------------------------------------------------------


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Audit one city: dump its final built map and validate rules.",
    )
    parser.add_argument("--city", required=True, help="city id, e.g. earth")
    parser.add_argument(
        "--format", choices=("json", "text"), default="json",
        help="output format (default: json)",
    )
    args = parser.parse_args()

    try:
        game_map = build_final_map(args.city)
    except KeyError:
        print(f"Unknown city id: {args.city}", file=sys.stderr)
        return 1

    violations = check_station_clipping(game_map) + check_serves(game_map)

    if args.format == "text":
        print(report_text(args.city, game_map, violations))
    else:
        print(report_json(args.city, game_map, violations))

    return 0 if not violations else 1


if __name__ == "__main__":
    raise SystemExit(main())
