# DESIGN: City Audit Tool

## Overview

A single tool, `tools/city_audit.py`, that audits **one city at a time**
(no batch mode yet). It has two steps:

1. **Build and dump the final map** — build the city through the real
   `city_builder.build_city` pipeline (the exact path the game uses) and
   output the resulting `GameMap` as structured data.
2. **Validate R1** — transit stations and their pads must not clip, or be
   clipped by, any other entity on the map.

The map dump is the substrate: it is the final map exactly as generated
in game, emitted as data so the rules we create (now and later) validate
against the same artifact.

## CLI contract

```bash
python3 tools/city_audit.py --city ross_c
```

- `--city <id>` — required. The single city to audit.
- Output: JSON to stdout (default). Exit code `0` = no violations, `1` = at
  least one violation.

## Step 1 — Final map dump

Build the city via `city_builder.build_city(spec, resolve_npc, resolve_ship)`
with the same resolvers the game uses, then serialize the final `GameMap`:

```json
{
  "city_id": "ross_c",
  "width": 100,
  "height": 60,
  "tiles": [["floor", "floor", "..."], ...],
  "entities": [
    {
      "name": "Transit: Spaceport",
      "char": "T",
      "pos": [42, 17],
      "width": 1,
      "height": 1,
      "transit_station_id": "spaceport"
    }
  ]
}
```

- `tiles` — per-row list of tile kinds (the data rules need; not glyphs).
- `entities` — every entity with name, glyph, position, and full
  `width`/`height` footprint, plus the flags rules need to identify them
  (e.g. `transit_station_id`).

## Step 2 — R1: transit station clipping

**Rule ID:** `R1`

**Statement:** On the final built map, every transit station entity —
including its pad (its full `width × height` footprint rectangle) — must
not overlap any other entity's footprint. A station must not sit on top
of, clip, or be clipped by any other entity. Footprints are full
rectangles: `pos.x .. pos.x + width - 1` × `pos.y .. pos.y + height - 1`.
Checking only the anchor cell is not enough.

**Pad zone:** besides its own footprint, each station protects its pad
zone — the `3×3` square around every footprint cell (the area
`city_kit.paint_transit_bays` carves). Any entity whose footprint touches
the pad zone is also a violation: the bay painter would overwrite the
cell under that entity. Pad zone cells are clipped to map bounds.

At this stage R1 is station-centric only: it checks transit stations
against everything else. Entity-vs-entity clipping between non-station
entities is not checked yet.

**Validation logic (pure):**

```python
def _check_station_clipping(game_map) -> list[Violation]:
    stations = [e for e in game_map.entities if e.transit_station_id]
    others = [e for e in game_map.entities if not e.transit_station_id]

    def footprint(e):
        return {
            (e.pos.x + dx, e.pos.y + dy)
            for dx in range(e.width)
            for dy in range(e.height)
        }

    violations = []
    for station in stations:
        s_cells = footprint(station)
        for other in others:
            overlap = s_cells & footprint(other)
            if overlap:
                cell = min(overlap)
                violations.append(Violation(
                    "R1", station.name, other.name, cell,
                    f"'{station.name}' clips '{other.name}' at {cell}",
                ))
    return violations
```

## Data model

```python
@dataclass(frozen=True)
class Violation:
    rule_id: str            # "R1"
    station: str            # station entity name
    other: str              # entity it clips
    location: tuple[int, int]
    message: str
```

## Acceptance criteria

- `python3 tools/city_audit.py --city <id>` builds the city through the real
  pipeline and prints the final-map JSON without crashing.
- R1 catches station clipping including multi-cell footprints and the 3×3
  pad zone (verified by unit tests: pass case, station-on-terminal,
  ship-overlapping-station-pad, entity-inside-pad-zone, map-edge station)
- Earth baseline (verified): `Transit: Bar District` clips `Civilian
  Bystander` at (118,17); `Transit: Militia Center` clips `Militia
  Trooper` at (65,77) — both are NPCs standing inside the pad zone.
- Exit code contract works (`0` clean, `1` violations).
- `make check` passes with the new tests included.
- No existing behavior changes (the tool is additive).
