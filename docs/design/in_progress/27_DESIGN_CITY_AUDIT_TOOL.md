# DESIGN: City Audit Tool — Source of Truth for City Quality

## Overview

A standalone audit tool (`tools/city_audit.py` + reusable library
`src/spacehack/city_audit/`) that discovers **every** city builder in the
codebase dynamically (no hardcoded list), builds each city through the real
`city_builder.build_city` pipeline, then runs a registry of **validation
rules** against the built `GameMap` using real pathing/adjacency logic.

The tool's output is a structured violation report designed to be consumed
by any agent in a single parse: machine-readable JSON by default, with an
optional human-readable text overlay per city.

**Purpose:** replace the current scattered, hand-written per-city regression
tests with a single authoritative gate. A city "passes" when zero blocking
violations are reported. This tool becomes the enforcement mechanism for the
city quality rule set, and can be wired into `make check` once the rule set
stabilizes.

## Philosophy alignment

| Principle | How this tool follows it |
|---|---|
| Data-first | Rules are registered in a static table (`RULES` dict), not chained conditionals |
| Pure functions | Every rule is pure: `(GameMap, PlanetSpec) -> list[Violation]`, no I/O, no mutation |
| Table-driven | Rule dispatch via `_RULES: dict[str, RuleFn]`, lookup by rule_id |
| ctx-first | Rules take `GameMap` + `PlanetSpec` as explicit inputs, no hidden globals |
| Reuse | Connectivity helpers wrap `world`-style BFS; spatial checks reuse `city_kit` metadata (`city_buildings`, `transit_stations`, `landmark_stamps`) |
| SRP | One rule = one check = one verb phrase; rules never mutate the map |

## Scope

**In scope:**
- Dynamic discovery of all city builders (glob `src/spacehack/*_city.py`, resolve each module's registered builder via `city_builder` dispatch table)
- Building each city through the real `build_city` pipeline (same path the game uses)
- Running registered validation rules against built `GameMap` + `PlanetSpec`
- Reporting violations in JSON (default) and text (optional `--format text`)

**Out of scope:**
- Fixing violations (the tool reports; the agent fixes the city module)
- Interior map auditing (Phase 2 candidate — interiors are separate `GameMap`s built on demand)
- NPC behavior simulation (out of scope; only placement is checked)

## Tool architecture

```
tools/city_audit.py              # CLI: --all | --city <id>, --format json|text, --rules r1,r2,...
src/spacehack/city_audit/
    __init__.py                  # exports run_audit(), discover_cities()
    discovery.py                 # dynamic city discovery via city_builder dispatch table
    connectivity.py              # BFS helpers: reachable_cells(), connected_components(), shortest_path()
    rules.py                     # _RULES registry: dict[rule_id, RuleFn]; each RuleFn is pure
    report.py                    # Violation dataclass + JSON/text formatter
```

### CLI contract

```bash
python3 tools/city_audit.py --all                     # audit every discovered city
python3 tools/city_audit.py --city ross_c             # audit one city
python3 tools/city_audit.py --all --rules R1,R2       # run subset of rules
python3 tools/city_audit.py --all --format text       # human-readable output
```

Exit codes: `0` = zero blocking violations across all audited cities;
`1` = at least one blocking violation. This lets `make check` wire it in
as a fifth gate step once the rule set is stable.

### Core data model

```python
@dataclass(frozen=True)
class Violation:
    rule_id: str          # e.g. "R1"
    severity: str         # "blocking" | "warning"
    city_id: str          # e.g. "ross_c"
    location: tuple[int, int] | None   # offending cell, if applicable
    message: str          # human-readable description of the violation

@dataclass(frozen=True)
class CityReport:
    city_id: str
    passed: bool          # True iff zero blocking violations
    violations: tuple[Violation, ...]
```

### Rule registry pattern (table-driven, guardrail #1)

```python
# rules.py
RuleFn = Callable[[world.GameMap, PlanetSpec], list[Violation]]

_RULES: dict[str, RuleFn] = {
    "R1": _check_transit_station_placement,
}

def get_rules(ids: list[str] | None) -> dict[str, RuleFn]:
    if ids is None:
        return dict(_RULES)
    return {rid: _RULES[rid] for rid in ids if rid in _RULES}  # KeyError on unknown id
```

Adding a new rule = adding one entry to `_RULES` + one pure function.
No dispatcher changes, no CLI changes.

## Output format (JSON, default)

```json
{
  "tool_version": "1.0",
  "cities_audited": 27,
  "cities_passed": 25,
  "reports": [
    {
      "city_id": "ross_c",
      "passed": false,
      "violations": [
        {
          "rule_id": "R1",
          "severity": "blocking",
          "location": [42, 17],
          "message": "transit stop 'dock' at (42,17) sits on road tile; must be on plain floor"
        }
      ]
    }
  ]
}
```

Text format (`--format text`) renders the same data as a per-city block with
an ASCII legend line, violations grouped by rule, and a final summary line:
`ROSS_C: FAIL (1 blocking, 0 warnings)`.

## Rule 1 — Transit station placement (fully specified)

**Rule ID:** `R1`

**Statement:** Every transit station defined in `spec.transit_stations`
must satisfy ALL of the following:

1. The station cell itself (`station.pos`) must be a **plain walkable floor
   tile** — specifically its `tile.kind` must NOT be any of:
   `"road"`, `"sidewalk"`, `"landing_pad"`, `"transit_bay"` (pre-existing bay
   from a prior call is fine — R1 runs on the map state BEFORE
   `paint_transit_bays` is called, i.e. on the spec-consistent pre-bay state;
   see sequencing below), or any building/flavor/decor tile kind
   (`city_building_wall`, `city_building_door`, `city_building_floor`,
   `city_plaza`, `city_ornament`, `monument`, `city_water`, `city_shore`,
   `city_bridge`, or any theme-specific decor kind).
2. The 3×3 bay area around the station (the cells that
   `paint_transit_bays` would touch) must not overlap ANY of:
   - building footprints (from `spec.buildings` x_lo/x_hi/y_lo/y_hi ranges)
   - landing pad cells (any tile with `kind == "landing_pad"`)
   - road cells (any tile with `kind == "road"`)
   - sidewalk cells (any tile with `kind == "sidewalk"`)
   - door forecourt cells (computed from `spec.buildings` door positions
     using the same logic as `city_kit.paint_door_forecourts`)
   - non-walkable terrain (water, shore, crevasse, void, or any tile with
     `walkable=False`)

   In other words: the bay must only overwrite plain floor/theme-base tiles.
   This is the invariant `paint_transit_bays`'s `overwrite_kinds` parameter
   was designed to enforce — R1 verifies the *spec-level geometry* guarantees
   it, independent of what painters actually did.
3. The station cell must be **reachable** from the hangar anchor
   (`spec.hangar_anchor`) via a walkable path that does not pass through
   building interiors or walls (BFS on `walkable=True` tiles, treating
   `city_building_door` as passable only if it connects to a forecourt).
4. The station cell must not coincide with any entity position already
   placed on the map (terminals, showroom ships, NPCs, doors).

**Sequencing:** R1 runs against the tile grid at the point in `build_city`
**after** terrain painters and door forecourts but **before**
`paint_transit_bays` executes. This checks the *geometric intent* of the
spec, not the painter's output. A second sub-check (`R1b`, added later)
will verify the painter's actual output.

**Validation logic (pure, pathing-based):**

```python
def _check_transit_station_placement(
    game_map: world.GameMap, spec: PlanetSpec,
) -> list[Violation]:
    violations = []
    forbidden_center = _FORBIDDEN_CENTER_KINDS   # static frozenset
    forbidden_bay = _FORBIDDEN_BAY_KINDS         # static frozenset
    building_cells = _collect_building_cells(spec)      # set[(x,y)]
    forecourt_cells = _collect_forecourt_cells(spec)    # set[(x,y)]
    entity_cells = {(e.pos.x, e.pos.y) for e in game_map.entities}
    reachable = bfs_walkable(game_map, spec.hangar_anchor)  # set[(x,y)]

    for station in spec.transit_stations:
        x, y = station.pos.x, station.pos.y
        tile = game_map.tiles[y][x]
        # Check 1: center cell kind
        if tile.kind in forbidden_center:
            violations.append(Violation("R1", "blocking", spec.id, (x, y),
                f"transit stop '{station.id}' at ({x},{y}) sits on '{tile.kind}' tile"))
        # Check 2: 3x3 bay area
        for dyc in (-1, 0, 1):
            for dxc in (-1, 0, 1):
                nx, ny = x + dxc, y + dyc
                if not _in_bounds(nx, ny, game_map): continue
                nt = game_map.tiles[ny][nx]
                if (nx, ny) in building_cells or (nx, ny) in forecourt_cells:
                    violations.append(Violation("R1", "blocking", spec.id, (nx, ny),
                        f"bay of '{station.id}' overlaps building/forecourt at ({nx},{ny})"))
                elif nt.kind in forbidden_bay or not nt.walkable:
                    violations.append(Violation("R1", "blocking", spec.id, (nx, ny),
                        f"bay of '{station.id}' overlaps '{nt.kind}' at ({nx},{ny})"))
        # Check 3: reachability from hangar
        if (x, y) not in reachable:
            violations.append(Violation("R1", "blocking", spec.id, (x, y),
                f"transit stop '{station.id}' at ({x},{y}) unreachable from hangar"))
        # Check 4: entity collision
        if (x, y) in entity_cells:
            violations.append(Violation("R1", "blocking", spec.id, (x, y),
                f"transit stop '{station.id}' at ({x},{y}) collides with existing entity"))
    return violations
```

**Static kind tables (defined once, reused by future rules):**

```python
_FORBIDDEN_CENTER_KINDS = frozenset({
    "road", "sidewalk", "landing_pad", "city_building_wall",
    "city_building_door", "city_building_floor", "city_plaza",
    "city_ornament", "monument", "city_water", "city_shore",
    "city_bridge", "void",
})

_FORBIDDEN_BAY_KINDS = frozenset({
    "road", "sidewalk", "landing_pad", "city_water", "city_shore",
    "city_bridge", "void", "city_building_wall",
})
```

(Theme-specific decor kinds are caught by the `walkable=False` check and by
the building-footprint/forecourt overlap checks, so the tables stay
theme-agnostic. If a new theme introduces a hard-blocked decor kind that is
walkable, it gets added to `_FORBIDDEN_BAY_KINDS` explicitly.)

## Phased implementation plan

### Phase 1 — Core tool + R1

- [ ] Create `src/spacehack/city_audit/` package (`__init__.py`, `discovery.py`, `connectivity.py`, `rules.py`, `report.py`)
- [ ] Implement `discovery.py`: resolve all cities via `city_builder` dispatch table (dynamic, no hardcoded list)
- [ ] Implement `connectivity.py`: `bfs_walkable(game_map, start) -> set[tuple[int,int]]` (pure, reusable)
- [ ] Implement `rules.py` with R1 exactly as specified above (pure function + static kind tables)
- [ ] Implement `report.py`: `Violation`/`CityReport` dataclasses + JSON/text formatters
- [ ] Implement `tools/city_audit.py` CLI (`--all`/`--city`/`--rules`/`--format`, exit code contract)
- [ ] Write `tests/test_city_audit.py`: unit tests for R1 (pass case, each violation type, multi-station city, edge: station at map edge), discovery test (asserts all `*_city.py` modules resolve), connectivity BFS test
- [ ] Run audit on all cities; record baseline violations in the doc
- [ ] `make check` + commit

**PLAYTEST (Phase 1):** run `python3 tools/city_audit.py --all --format text`; verify output lists every city (count matches `ls src/spacehack/*_city.py | wc -l`); verify JSON output parses with `python3 -m json.tool`; verify exit code matches pass/fail counts; verify a deliberately broken spec (temporarily move a transit stop onto a road in a test fixture) produces an R1 blocking violation.

### Phase 2 — Rules R2+ (one at a time, discussed with user before implementation)

- [ ] R2: Road network connectivity (one connected component, 3-tile width)
- [ ] R3: Door forecourt reachability + no overlap with transit bays
- [ ] R4: Landing pad surface quality + showroom ship placement
- [ ] R5: Interior conventions (spawn/exit adjacency, no void perimeter)
- [ ] R6: CP437 glyph safety (all placed chars in charmap)
- [ ] Each rule: discuss spec with user → implement → test → commit → run audit → record results

## Per-city checklist

Populated from Phase 1 baseline run. One row per discovered city; updated
after each rule is added. Cities are discovered dynamically, so this table
regenerates via `python3 tools/city_audit.py --all --format text` — the doc
records the latest snapshot, the tool is the source of truth.

| # | City | R1 | R2 | R3 | R4 | R5 | R6 |
|---|------|----|----|----|----|----|----|
| 1 | earth | — | — | — | — | — | — |
| 2 | mercury | — | — | — | — | — | — |
| … | *(populated after Phase 1 baseline run)* | | | | | | |

## Acceptance criteria

- `python3 tools/city_audit.py --all` discovers every `*_city.py` module (count matches glob) and audits each without crashing
- R1 catches all violation types listed in its spec (verified by unit tests)
- JSON output is valid JSON (parses with `json.tool`); text output is readable
- Exit code contract works (`0` clean, `1` violations)
- `make check` passes with the new tests included
- No existing behavior changes (the tool is additive; it does not modify `build_city` or any city module)

## Open questions

1. Should R1's reachability check treat `city_building_door` as passable (it connects forecourt to interior) or impassable (interior is a separate map)? Current proposal: passable only when adjacent to a forecourt cell.
2. Should severity levels exist beyond "blocking" vs "warning"? E.g. "info" for stylistic observations?
3. Should the tool cache built maps across rules (build once, run all rules) or rebuild per rule? (Proposal: build once per city, pass the same `GameMap` to all rules.)
4. How should the tool handle cities whose builder requires external state (e.g. quest-tagged variants)? (Proposal: audit the default/base build only.)

## Pre-implementation audit

1. **Existing modules to reuse.** `city_kit.py` (all shared helpers, `_TERMINAL_SPECS` pattern for table-driven design), `city_builder.py` (dispatch table = discovery source), `city_layout.py` (`building_records`, `stamp_metadata` for spatial metadata), `world.py` (`Tile.walkable`, `TransitStation`, `CityBuilding`), existing per-city tests (`test_venus_city.py::test_venus_circulation_is_planned`, `test_proc_c_city.py::test_proc_c_circulation_is_planned` — their BFS patterns become `connectivity.py`).
2. **Duplication hotspots.** (a) BFS implementations exist scattered in per-city tests — extract into `connectivity.py` once, reuse everywhere. (b) Building footprint iteration (`for building in spec.buildings: range(x_lo, x_hi+1)`) appears in `paint_door_forecourts` and several city painters — centralize in `spatial.py`. (c) Tile-kind forbidden-set logic is currently implicit in `overwrite_kinds` parameters — make it explicit in static tables.
3. **DRY strategy.** One `bfs_walkable` in `connectivity.py`; one `_collect_building_cells` + `_collect_forecourt_cells` in `spatial.py`; all kind tables as module-level frozensets in `rules.py`; rules registered in `_RULES` dict (guardrail #1 table-driven).
