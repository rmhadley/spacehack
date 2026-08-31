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
- `buildings` — per building label: `display_name` and `entrance` (the
  door cell as `[x, y]`, from the `city_buildings` metadata the pipeline
  already computes). Empty map if the city has no building records.
  This is the station→destination link: a station may serve a building
  with a door (check proximity to `entrance`) or a landmark without one
  (e.g. Earth's Central Hub serving the fountain) — entrance is `null`
  only if the record lacks one.

## Step 2 — R1: transit station clipping

**Rule ID:** `R1`

**Statement:** On the final built map, every transit station must sit on
a real, clean pad. Three checks per station:

1. **Pad existence (station cell):** the station cell itself must be a
   `transit_bay` tile. If the bay painter skipped it (station authored on
   a tile kind the painter's `overwrite_kinds` doesn't cover, e.g.
   `city_plaza` or `grass`), the station has no pad at all.
2. **Pad integrity (3×3 zone):** every cell of the pad zone — the
   `2*pad_radius+1` square around the footprint, the area
   `city_kit.paint_transit_bays` carves — must also be `transit_bay`.
   A non-bay tile in the zone means the painter skipped it (station too
   close to road/sidewalk/building) or something painted over the bay
   afterwards — either way the pad is clipped or was never carved.
3. **Entity clipping:** no other entity's footprint may touch the
   station footprint or the pad zone.

Footprints are full rectangles: `pos.x .. pos.x + width - 1` ×
`pos.y .. pos.y + height - 1`. Checking only the anchor cell is not
enough. Stations are not checked against each other.

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

## Remediation guidance (part of R1 output)

When R1 fails for a station, the tool must do two things using the SAME
map data (no rebuild, no extra passes):

### A. Recommend a valid location

Search the built map for a placement that would satisfy all R1 checks and
attach it to the station's violations:

- **Candidate search:** scan the map for cells where a `3×3` square around
  the cell is entirely `transit_bay`-paintable ground — i.e. all 9 cells
  are walkable, none is `road`/`sidewalk`/`landing_pad`/wall/building/water
  kind, and no entity footprint (station entities excluded) touches any of
  the 9 cells.
- **Score candidates by distance** to the station's authored position
  (straight-line); the closest valid candidate wins. Ties break by lower
  `y` then lower `x` for determinism.
- **Never recommend** a cell that would put the pad on top of the station's
  current pad problem (e.g. don't recommend a cell whose pad would overlap
  the very road/building that caused the original violation).
- The recommendation is attached to the FIRST violation of that station as
  `recommendation: {"pos": [x, y], "distance": n, "note": "..."}`. If no
  valid cell exists on the map, `recommendation` is `null` and the note
  says the station must be moved to a larger open area.

### B. Report the correct way to author the station

When the diagnosis is "station has no pad because the city module uses the
older authoring method" (station cell is not `transit_bay` AND the module
never calls `paint_transit_bays`), the tool must report HOW it should be
done — the remediation text is generic and city-agnostic:

> This city module authors transit stations the old way (station entity
> only, no bay painting). The correct method is to import
> `paint_transit_bays` from `city_kit` and call it in the layout builder
> AFTER terrain painters and door forecourts, passing the bay tile, map
> dimensions, and `overwrite_kinds` covering the base ground kinds the
> stations sit on (e.g. `frozenset({"floor", "plaza"})`). Stations placed
> on terrain not covered by `overwrite_kinds` will silently get no pad —
> this is the failure R1 detects.

The remediation text is attached to every "pad is not transit_bay"
violation as `remediation` (text format: printed under the violation;
JSON format: `"remediation": "..."` field). It is emitted once per
station, not per violating cell.

## Step 3 — R2: station must declare and reach what it serves

**Rule ID:** `R2`

**Statement:** every transit station must declare, in authored data,
which place it brings the player to — and that place must actually exist
and be near the station.

**`serves` field (new, required by the audit):** `world.TransitStation`
gains `serves: str = ""`. It names the building label or landmark the
station was authored to serve (e.g. `serves="bar"`, `serves="plaza"` for
the fountain on the plaza). It is deliberately NOT defaulted from the
station id: the audit FAILs any station that does not declare `serves`
explicitly, so intent is always authored in the planet spec, never
guessed by the tool.

**Target registry:** the tool resolves `serves` against the union of:

- `buildings` — keyed by building label (`bar`, `militia`, …); entrance
  from `city_buildings`.
- `landmarks` — keyed by landmark key with the `<city_id>_city_` prefix
  stripped (`earth_city_plaza` → `plaza`); entrance from
  `landmark_stamps` (may be `None` for landmarks without a door).

**Checks per station (on the final built map):**

1. `serves` must be present and non-empty → otherwise violation
   `"... does not declare 'serves'"` with remediation text telling the
   author to add `serves="<building-or-landmark>"` to the
   `TransitStation` in the planet spec.
2. The resolved target must exist → otherwise a typo violation listing
   the valid target ids.
3. The target must have an entrance → landmarks without one are flagged.
4. Straight-line distance from the station pos to the target entrance
   must be ≤ `max_serves_distance` (default 15) → otherwise a violation
   reporting the measured distance and the target entrance coordinates.

**Dump additions:** station entities carry `"serves"`; the dump gains a
top-level `"landmarks"` map (`key → {"origin": [x,y], "entrance":
[x,y] | null}`) so rules can resolve landmark targets from the same
artifact.

## Data model

```python
@dataclass(frozen=True)
class Violation:
    rule_id: str            # "R1"
    station: str            # station entity name
    other: str              # entity it clips (or offending tile kind)
    location: tuple[int, int]
    message: str
    recommendation: dict | None = None   # {"pos": [x,y], "distance": n, "note": str}
    remediation: str | None = None       # how-to-fix text (old-method diagnosis)
```

## Acceptance criteria

- `python3 tools/city_audit.py --city <id>` builds the city through the real
  pipeline and prints the final-map JSON without crashing.
- Every failing station carries a `recommendation` (closest valid 3×3
  location) and, when diagnosed as old-method authoring, a `remediation`
  text explaining the correct `city_kit.paint_transit_bays` authoring method.
- R1 catches missing pads (station cell not `transit_bay`), partial pads
  (road/sidewalk/building intrusion into the pad zone), and entity
  clipping including multi-cell footprints (verified by unit tests)
- Earth baseline (verified): **zero `transit_bay` tiles exist on the map**
  — `earth_city.py` never calls `paint_transit_bays`, so every station is
  flagged for a missing pad; Central Hub additionally sits against a road
  (pad zone contains 3 road tiles). Two entity-clipping hits also remain
  (Bar District × Civilian Bystander at 118,17; Militia Center × Militia
  Trooper at 65,77).
- R2: every station must declare `serves`; the target must resolve to a
  building or landmark with an entrance within `max_serves_distance`.
- Earth baseline (R2, verified): all six Earth stations now declare
  `serves` (`port`→`spaceport`, `hub`→`plaza` landmark, `bar`→`bar`,
  `bounties`→`bounties`, `merchants`→`merchants`, `militia`→`militia`);
  all targets resolve and sit within the 15-cell threshold, so R2 passes
  on Earth. R2 is the enforcement mechanism: any city without `serves`
  declarations FAILs until its spec is updated.
- Exit code contract works (`0` clean, `1` violations).
- `make check` passes with the new tests included.
- No existing behavior changes (the tool is additive).
