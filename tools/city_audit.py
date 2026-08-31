#!/usr/bin/env python3
"""City audit tool — dump a city's final built map and validate rules against it.

Step 1: build the city through the real ``city_builder.build_city`` pipeline
        (the exact path the game uses) and print the final ``GameMap`` as
        structured JSON.
Step 2: run validation rules against that map. Currently one rule:

        R1 — transit stations (including their pads / full footprints) must
             not clip or be clipped by any other entity.

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
        entities.append(entry)
    return {
        "city_id": city_id,
        "width": game_map.width,
        "height": game_map.height,
        "tiles": [[tile.kind for tile in row] for row in game_map.tiles],
        "entities": entities,
    }


# ----- Step 2: R1 — transit station clipping --------------------------


def _footprint(entity: world.Entity) -> set[tuple[int, int]]:
    """Full rectangle footprint of an entity (pads and ships included)."""
    return {
        (entity.pos.x + dx, entity.pos.y + dy)
        for dx in range(entity.width)
        for dy in range(entity.height)
    }


def check_station_clipping(game_map: world.GameMap) -> list[Violation]:
    """R1: every transit station (full footprint, pad included) must be
    free of overlaps with any other entity's footprint."""
    stations = [e for e in game_map.entities if e.transit_station_id]
    others = [e for e in game_map.entities if not e.transit_station_id]

    violations: list[Violation] = []
    for station in stations:
        station_cells = _footprint(station)
        for other in others:
            overlap = station_cells & _footprint(other)
            if overlap:
                cell = min(overlap)
                violations.append(Violation(
                    "R1",
                    station.name,
                    other.name,
                    cell,
                    f"'{station.name}' clips '{other.name}' at {cell}",
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
    else:
        for v in violations:
            lines.append(f"  [{v.rule_id}] {v.message}")
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

    violations = check_station_clipping(game_map)

    if args.format == "text":
        print(report_text(args.city, game_map, violations))
    else:
        print(report_json(args.city, game_map, violations))

    return 0 if not violations else 1


if __name__ == "__main__":
    raise SystemExit(main())
