#!/usr/bin/env python3
"""City audit tool — dump a city's final built map and validate rules against it.

Step 1: build the city through the real ``city_builder.build_city`` pipeline
        (the exact path the game uses) and print the final ``GameMap`` as
        structured JSON (``--format json``; the default ``summary`` output
        is verdict + violations only, no tile dump).
Step 2: run validation rules against that map:

        R0 — every transit station must declare ``serves``. Fail-fast
             gate: R1/R2 are skipped until it passes. The ``--fix-plan``
             refusal includes the exact per-station ``serves`` edit to
             apply (plus a duplicate flag when two stations would serve
             the same target — a redundant stop the author must resolve).
        R1 — a transit station is only valid when it AND its 3x3 pad
             actually exist and are clean: the station cell and every cell
             of its pad zone must be transit_bay tiles (the pad was really
             painted, not skipped), no road/sidewalk/building/landing-pad
             tile may intrude into the pad, the station footprint must not
             clip or be clipped by any other entity, and no two stations
             may share a pad.
        R2 — every station's declared ``serves`` target must resolve to a
             building/landmark and be walkable-reachable near the station;
             a target gets ONE stop (duplicate ``serves`` declarations are
             refused with an explicit delete-or-re-target decision).

Usage:
    python3 tools/city_audit.py --city earth                   # summary
    python3 tools/city_audit.py --city earth --format json     # + tile dump
    python3 tools/city_audit.py --city earth --format text
    python3 tools/city_audit.py --city earth --fix-plan   # verified edit plan

Exit codes: 0 = no violations, 1 = violations found.

With ``--fix-plan`` the tool goes one step further: it applies its own
recommendations to the in-memory map (move stations to the recommended
pad locations, carve transit bays with the parameters it validated,
relocate clipped ambient NPCs to the nearest clear walkable cell),
re-runs every check on the patched map, and emits the ordered edit plan
**only if the patched map passes**. Every emitted op is therefore a
claim the tool has personally executed and verified — not advice. Ops
name the exact file each edit belongs in (spec positions, builder bay
call, NPC spawn anchors); pads are reserved as decided so two ops can
never resolve to the same pad. Plans and refusals also list the tests
that pin the city.
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
    # Interior/dungeon tiles (e.g. leaked by a layout glyph with no TILE
    # directive): paint_transit_bays' default overwrite_kinds can never
    # cover them, so recommending a pad on top of one yields an unverifiable
    # plan.
    "dungeon_floor", "dungeon_wall", "mine_shaft", "mine_rock",
})


def _footprint(entity: world.Entity) -> set[tuple[int, int]]:
    """Full rectangle footprint of an entity (pads and ships included)."""
    return {
        (entity.pos.x + dx, entity.pos.y + dy)
        for dx in range(entity.width)
        for dy in range(entity.height)
    }


def _door_approach_cells(game_map: world.GameMap) -> set[tuple[int, int]]:
    """Orthogonal neighbours of every building entrance (the front walk).

    A transit pad may never cover one: the stop sits beside the door's
    approach, not on it. Entrances without a recorded door are skipped.
    """
    cells: set[tuple[int, int]] = set()
    for rec in (getattr(game_map, "city_buildings", {}) or {}).values():
        entrance = rec.get("entrance")
        if not entrance:
            continue
        x, y = entrance
        for dx, dy in ((0, -1), (1, 0), (0, 1), (-1, 0)):
            if game_map.in_bounds(x + dx, y + dy):
                cells.add((x + dx, y + dy))
    return cells


def _station_serves(game_map: world.GameMap, station: world.Entity) -> str:
    """Authored ``serves`` for a station entity (entity attr, else the
    ``city_transit`` lookup ``place_transit_stations`` populated)."""
    lookup = (getattr(game_map, "city_transit", None) or {}).get(
        station.transit_station_id
    ) or {}
    return getattr(station, "serves", "") or lookup.get("serves", "") or ""


def _decorate_with_recommendation(
    game_map: world.GameMap,
    station: world.Entity,
    blocked_cells: set[tuple[int, int]],
    pad_radius: int,
    violation: Violation,
) -> Violation:
    """Attach a move recommendation to a station's first violation.

    Candidates are ranked by walkable steps to the building/landmark the
    station serves (BFS, not straight-line) so the recommended spot is on
    the same side of any walls as the target entrance. When the whole map
    has no bay tiles at all the old-authoring-method remediation is
    attached too.
    """
    serves = _station_serves(game_map, station)
    target, _src = _resolve_target(game_map, serves) if serves else (None, None)
    rec = _recommend_location(
        game_map, (station.pos.x, station.pos.y),
        blocked_cells, pad_radius, target=target,
    )
    has_any_bay = any(
        game_map.tiles[y][x].kind == "transit_bay"
        for y in range(game_map.height)
        for x in range(game_map.width)
    )
    return Violation(
        violation.rule_id, violation.station, violation.other,
        violation.location, violation.message,
        recommendation=rec,
        remediation=None if has_any_bay else _OLD_METHOD_REMEDIATION,
    )


def _check_station_overlaps(station_pads) -> list[Violation]:
    """R1 check 4: no two stations may share a pad.

    A station's footprint may never sit on — or inside the pad zone of —
    another station. Two stops stacked on one cell make checks 1-3 lie:
    the pad looks painted and clean while the stations are unusable.
    """
    violations: list[Violation] = []
    for i in range(len(station_pads)):
        for j in range(i + 1, len(station_pads)):
            a, a_cells, a_zone = station_pads[i]
            b, b_cells, b_zone = station_pads[j]
            shared = (a_cells & (b_cells | b_zone)) | (b_cells & (a_cells | a_zone))
            if not shared:
                continue
            cell = min(shared)
            violations.append(Violation(
                "R1", a.name, b.name, cell,
                f"'{a.name}' and '{b.name}' share a pad at {cell} — two "
                "transit stations may never sit on or inside each other's "
                "pad zone; move one away or delete the redundant stop",
            ))
    return violations


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
    4. No two stations may share a pad (footprint on the other's
       footprint or pad zone).
    5. The pad may not cover a building's door approach — the cells
       orthogonally adjacent to an entrance. A stop sits BESIDE the
       door's front walk, never on it (found on groom_b/ross_b, where
       proximity-ranked pads landed directly under doors).

    Every failing station gets a recommended alternative location,
    ranked away from every other station's pad and from all door
    approaches; stations diagnosed as authored the old way (no bay
    tiles at all) also get the remediation text describing the correct
    authoring method.
    """
    stations = [e for e in game_map.entities if e.transit_station_id]
    others = [e for e in game_map.entities if not e.transit_station_id]

    station_pads = []
    for s in stations:
        cells = _footprint(s)
        station_pads.append((s, cells, _pad_zone(cells, game_map, pad_radius)))

    door_cells = _door_approach_cells(game_map)

    # All non-station entity footprint cells block candidate locations;
    # every OTHER station's footprint+pad zone blocks them too, so a
    # recommendation can never create a new check-4 violation.
    entity_blocked: set[tuple[int, int]] = set()
    for e in others:
        entity_blocked |= _footprint(e)

    def _other_station_cells(station) -> set[tuple[int, int]]:
        cells: set[tuple[int, int]] = set()
        for s, fp, zone in station_pads:
            if s is not station:
                cells |= fp | zone
        return cells

    violations: list[Violation] = []
    decorated: set[str] = set()
    for station, station_cells, pad_zone in station_pads:
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

        # Check 5: the pad may not cover a building door approach —
        # the stop belongs beside the front walk, never on it.
        approach = protected & door_cells
        if approach:
            cell = min(approach)
            violations.append(Violation(
                "R1",
                station.name,
                "door approach",
                cell,
                f"'{station.name}' pad covers a building door approach at "
                f"{cell} — move the stop beside the door, not in front of it",
            ))

        # Remediation: attach a recommendation to the station's FIRST
        # violation (checks 1-3, 5).
        if len(violations) > first:
            blocked = entity_blocked | door_cells | _other_station_cells(station)
            violations[first] = _decorate_with_recommendation(
                game_map, station, blocked, pad_radius, violations[first],
            )
            decorated.add(station.name)

    # Check 4: station pairs. A station stacked on a fully painted pad
    # passes checks 1-3 — decorate its pair violation so the fix plan can
    # move it clear of the other stop.
    for pair in _check_station_overlaps(station_pads):
        if pair.station not in decorated:
            station = next(s for s, _c, _z in station_pads if s.name == pair.station)
            blocked = entity_blocked | door_cells | _other_station_cells(station)
            pair = _decorate_with_recommendation(
                game_map, station, blocked, pad_radius, pair,
            )
            decorated.add(pair.station)
        violations.append(pair)
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


# Ground kinds ``city_kit.paint_transit_bays`` (and this tool's in-memory
# patch) can actually carve. Candidate pads are validated against THIS set,
# not mere walkability: a walkable-but-unpaintable kind (e.g. 'tree') would
# pass a walkable check yet leave the pad uncarvable — an unverifiable plan
# (found on tau_ceti_b, where a recommended pad zone contained a tree).
_PAINTABLE_PAD_KINDS = frozenset({
    "floor", "grass", "grass_accent", "plaza", "city_plaza",
    "sidewalk", "landing_pad", "transit_bay",
})


def _cell_pad_ok(
    game_map: world.GameMap,
    x: int,
    y: int,
    radius: int,
    blocked_cells: set[tuple[int, int]],
) -> bool:
    """Whether a ``(2*radius+1)`` pad centred at ``(x, y)`` would be valid:
    every zone cell in bounds and a paintable ground kind (the bay painter
    could carve it), and free of other entity footprints."""
    for dyc in range(-radius, radius + 1):
        for dxc in range(-radius, radius + 1):
            nx, ny = x + dxc, y + dyc
            if not game_map.in_bounds(nx, ny):
                return False
            if game_map.tiles[ny][nx].kind not in _PAINTABLE_PAD_KINDS:
                return False
            if (nx, ny) in blocked_cells:
                return False
    return True


def _recommend_location(
    game_map: world.GameMap,
    origin: tuple[int, int],
    blocked_cells: set[tuple[int, int]],
    radius: int,
    *,
    target: tuple[int, int] | None = None,
) -> dict | None:
    """Closest valid pad location to ``origin``, or ``None``.

    Deterministic: when ``target`` is given, candidates are ranked by
    walkable BFS steps from the candidate to the target (a candidate that
    cannot reach the target on foot is disqualified — straight-line
    closeness is not enough, a pad on the wrong side of a building must
    never be recommended). Without ``target``, ranking falls back to
    straight-line distance. Ties break by lower y then lower x. One pass
    over the map; non-station entity footprints block candidates.
    """
    best_key = None
    best_pos = None
    for y in range(game_map.height):
        for x in range(game_map.width):
            if not _cell_pad_ok(game_map, x, y, radius, blocked_cells):
                continue
            if target is not None:
                steps = bfs_walkable(game_map, (x, y), target, max_steps=_RECOMMEND_BFS_BUDGET)
                if steps is None:
                    continue
                key = (steps, y, x)
            else:
                key = ((x - origin[0]) ** 2 + (y - origin[1]) ** 2, y, x)
            if best_key is None or key < best_key:
                best_key = key
                best_pos = (x, y)
    if best_pos is None:
        return None
    if target is not None:
        metric = f"{best_key[0]} walkable steps to the target"
        dist: int | float = best_key[0]
    else:
        metric = "closest valid pad location"
        dist = round(best_key[0] ** 0.5, 1)
    return {
        "pos": list(best_pos),
        "distance": dist,
        "note": (
            f"valid {2 * radius + 1}x{2 * radius + 1} pad location ({metric}); "
            f"move the station to {best_pos} and ensure "
            f"paint_transit_bays overwrite_kinds covers the ground there"
        ),
    }


# ----- Step 3: R2 — station must declare and reach what it serves ------


_MAX_SERVES_DISTANCE = 15.0
_RECOMMEND_BFS_BUDGET = 60


def bfs_walkable(
    game_map: world.GameMap,
    start: tuple[int, int],
    goal: tuple[int, int],
    *,
    max_steps: int = 200,
) -> int | None:
    """Shortest walkable path length from ``start`` to ``goal`` (8-dir), or
    ``None`` when unreachable within ``max_steps``.

    Walkability = the tile's own ``walkable`` flag (doors are passable:
    the player walks through them). The goal cell is reachable even if the
    path ends ON it; the start cell does not need to be walkable (the
    station entity stands on it).
    """
    if not game_map.in_bounds(*start) or not game_map.in_bounds(*goal):
        return None
    if start == goal:
        return 0
    from collections import deque

    visited: set[tuple[int, int]] = {start}
    queue: deque[tuple[tuple[int, int], int]] = deque([(start, 0)])
    while queue:
        (x, y), steps = queue.popleft()
        if steps >= max_steps:
            continue
        for dy in (-1, 0, 1):
            for dx in (-1, 0, 1):
                if dx == 0 and dy == 0:
                    continue
                nxt = (x + dx, y + dy)
                if nxt in visited or not game_map.in_bounds(*nxt):
                    continue
                if nxt == goal:
                    return steps + 1
                if not game_map.tiles[nxt[1]][nxt[0]].walkable:
                    continue
                visited.add(nxt)
                queue.append((nxt, steps + 1))
    return None


def bfs_path(
    game_map: world.GameMap,
    start: tuple[int, int],
    goal: tuple[int, int],
    *,
    max_steps: int = 200,
) -> list[tuple[int, int]] | None:
    """Shortest walkable path from ``start`` to ``goal`` (8-directional), or
    ``None`` when the goal is unreachable within ``max_steps``.

    Walkability is the tile's own ``walkable`` flag — doors are passable,
    since the game lets the player walk through them. Returns the full
    path including both endpoints, or ``None`` when unreachable.
    """
    if not game_map.in_bounds(*start) or not game_map.in_bounds(*goal):
        return None
    if not game_map.tiles[start[1]][start[0]].walkable:
        return None
    from collections import deque

    prev: dict[tuple[int, int], tuple[int, int] | None] = {start: None}
    queue: deque[tuple[int, int]] = deque([start])
    steps = 0
    while queue and steps <= max_steps:
        cell = queue.popleft()
        if cell == goal:
            path: list[tuple[int, int]] = []
            cur: tuple[int, int] | None = cell
            while cur is not None:
                path.append(cur)
                cur = prev[cur]
            path.reverse()
            return path
        x, y = cell
        for dy in (-1, 0, 1):
            for dx in (-1, 0, 1):
                if dx == 0 and dy == 0:
                    continue
                nxt = (x + dx, y + dy)
                if nxt in prev or not game_map.in_bounds(*nxt):
                    continue
                if not game_map.tiles[nxt[1]][nxt[0]].walkable:
                    continue
                prev[nxt] = cell
                queue.append(nxt)
        steps += 1
    return None


def bfs_steps(
    game_map: world.GameMap,
    start: tuple[int, int],
    goal: tuple[int, int],
    *,
    max_steps: int = 200,
) -> int | None:
    """Walkable-path length from ``start`` to ``goal``, or ``None`` when
    unreachable within ``max_steps``. Doors are passable."""
    path = bfs_path(game_map, start, goal, max_steps=max_steps)
    return None if path is None else len(path) - 1


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


def _landmark_footprint(game_map: world.GameMap, serves: str) -> set[tuple[int, int]]:
    """Footprint cells of a landmark matched by prefix-stripped key."""
    for key, rec in (getattr(game_map, "landmark_stamps", None) or {}).items():
        if key.split("_city_", 1)[-1] == serves:
            return set(rec.get("footprint") or ())
    return set()


def _suggested_serves(game_map: world.GameMap, pos: tuple[int, int]) -> str | None:
    """Best-guess ``serves`` value for a station at ``pos``.

    Ranks every resolvable target (building label or prefix-stripped
    landmark key) by straight-line distance from ``pos`` to its
    entrance (or nearest footprint cell for doorless landmarks) and
    returns the closest. This makes the R0 remediation a copy-paste
    edit instead of a research task.
    """
    candidates: list[tuple[float, str]] = []
    for label, rec in (getattr(game_map, "city_buildings", {}) or {}).items():
        entrance = rec.get("entrance")
        if entrance is None:
            continue
        d = ((pos[0] - entrance[0]) ** 2 + (pos[1] - entrance[1]) ** 2) ** 0.5
        candidates.append((d, label))
    for key, rec in (getattr(game_map, "landmark_stamps", None) or {}).items():
        short = key.split("_city_", 1)[-1]
        fp = rec.get("footprint") or ()
        if not fp:
            continue
        near = min(
            ((pos[0] - fx) ** 2 + (pos[1] - fy) ** 2) ** 0.5
            for fx, fy in fp
        )
        candidates.append((near, short))
    if not candidates:
        return None
    return min(candidates)[1]


# ----- Step 0: R0 — serves declared (fail-fast gate) ------------------


def check_serves_declared(game_map: world.GameMap) -> list[Violation]:
    """R0: every transit station must explicitly declare what it serves.

    This is a fail-fast gate: authored intent must exist before any
    geometric rule (R1/R2) is evaluated, because R1's recommendation
    ranking (BFS toward the served target) is only meaningful when the
    target is known. A station without ``serves`` yields one R0
    violation; R1/R2 are skipped entirely while any R0 violation
    exists.
    """
    violations: list[Violation] = []
    for station in game_map.entities:
        if not station.transit_station_id:
            continue
        serves = _station_serves(game_map, station)
        if not serves:
            pos = (station.pos.x, station.pos.y)
            suggested = _suggested_serves(game_map, pos)
            violations.append(Violation(
                "R0",
                station.name,
                "(no serves field)",
                pos,
                f"'{station.name}' does not declare 'serves' — add "
                f"serves=\"{suggested}\" to its TransitStation "
                f"in the planet spec",
                recommendation=(
                    {"serves": suggested, "pos": list(pos),
                     "note": "nearest resolvable building/landmark to this "
                             "station; add serves=\"" + suggested + "\" to "
                             "its world.TransitStation(...)"}
                    if suggested else None
                ),
                remediation=(
                    "Add serves=\"" + (suggested or "<label>") + "\" to this "
                    "TransitStation in the planet spec "
                    "(src/spacehack/data/planets/<city>.py, in the "
                    "transit_stations tuple). The suggested value is the "
                    "nearest resolvable building label or landmark key to "
                    "this station's position; override it if authored "
                    "intent differs. After adding serves to every station, "
                    "re-run this audit; R1/R2 checks are skipped until the "
                    "gate passes."
                ),
            ))
    return violations


def _flag_duplicate_serves(
    declared: list[tuple[world.Entity, str]],
    violations: list[Violation],
) -> None:
    """R2: a serves target gets one stop. Two stations declaring the same
    target is a redundant stop — station moves can never fix it, so it is
    an explicit author decision: delete the redundant TransitStation or
    re-target it to a distinct building/landmark."""
    by_target: dict[str, list[world.Entity]] = {}
    for station, serves in declared:
        by_target.setdefault(serves, []).append(station)
    for serves, group in sorted(by_target.items()):
        if len(group) < 2:
            continue
        first, *rest = group
        others = ", ".join(s.name for s in rest)
        violations.append(Violation(
            "R2", first.name, rest[0].name,
            (first.pos.x, first.pos.y),
            f"'{first.name}' and {others} all serve '{serves}' — a target "
            f"gets one stop; delete the redundant TransitStation (and "
            f"scrub it from every destinations tuple) or re-target it to "
            f"a distinct building/landmark",
            remediation=(
                "Redundant stop: in the planet spec's transit_stations "
                "tuple, delete one of the stations naming this target and "
                "remove its id from every other station's destinations. "
                "Move recommendations cannot resolve a duplicate serves "
                "declaration — re-run the audit after the edit."
            ),
        ))


def check_serves(game_map: world.GameMap, *, max_distance: float = _MAX_SERVES_DISTANCE) -> list[Violation]:
    """R2: every transit station's declared ``serves`` target must exist
    with an entrance near the station.

    1. The target must resolve to a building label or landmark key.

    2. The target must have an entrance (door cell).

    3. The station must be reachable from the entrance by a walkable path
       (BFS over walkable tiles, doors passable) of at most
       ``max_distance`` steps — Euclidean closeness is not enough: a
       station on the wrong side of a building can sit one cell from the
       entrance through a wall.

    (Whether ``serves`` is declared at all is R0's job; R2 only runs
    when the R0 gate passes.)
    """
    violations: list[Violation] = []
    declared: list[tuple[world.Entity, str]] = []
    for station in game_map.entities:
        if not station.transit_station_id:
            continue
        serves = _station_serves(game_map, station)
        if not serves:
            # R0 territory — should not happen when the gate is honored,
            # but keep the guard so R2 standalone runs stay correct.
            violations.append(Violation(
                "R0",
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
        declared.append((station, serves))
        entrance, source = _resolve_target(game_map, serves)
        if entrance is None:
            # Landmarks may legitimately have no door — check the station
            # sits near the landmark footprint (or its origin) instead.
            if source == "landmark":
                fp = _landmark_footprint(game_map, serves)
                near = min(
                    ((station.pos.x - fx) ** 2 + (station.pos.y - fy) ** 2) ** 0.5
                    for fx, fy in fp
                ) if fp else None
                if near is not None and near <= max_distance:
                    continue
                violations.append(Violation(
                    "R2",
                    station.name,
                    serves,
                    (station.pos.x, station.pos.y),
                    f"'{station.name}' serves='{serves}' (landmark without "
                    f"door) is {near:.1f} cells from the landmark footprint"
                    if near is not None else
                    f"'{station.name}' serves='{serves}' (landmark without "
                    f"door) has no footprint data",
                ))
                continue
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
        # R2-4: the station must be REACHABLE from the target entrance by
        # walking (BFS over walkable tiles) — Euclidean distance is not
        # enough: a station on the wrong side of a building can be one cell
        # away from the entrance through a wall.
        steps = bfs_walkable(
            game_map,
            (entrance[0], entrance[1]),
            (station.pos.x, station.pos.y),
            max_steps=max_distance,
        )
        if steps is None:
            violations.append(Violation(
                "R2",
                station.name,
                serves,
                (station.pos.x, station.pos.y),
                f"'{station.name}' is not walkable-reachable from its target "
                f"'{serves}' entrance {tuple(entrance)} (walls/roads block "
                f"the path)",
                recommendation={
                    "pos": list(entrance),
                    "distance": None,
                    "note": f"target '{serves}' entrance — move the station "
                            f"to the same walkable area (no walls/roads "
                            f"between them)",
                },
            ))
        elif steps > max_distance:
            violations.append(Violation(
                "R2",
                station.name,
                serves,
                (station.pos.x, station.pos.y),
                f"'{station.name}' is {steps} walkable steps from its target "
                f"'{serves}' entrance {tuple(entrance)} (max {max_distance:g})",
                recommendation={
                    "pos": list(entrance),
                    "distance": steps,
                    "note": f"target '{serves}' entrance — move the station "
                            f"closer to it (walkable steps)",
                },
            ))
    _flag_duplicate_serves(declared, violations)
    return violations


# ----- Step 4: verified fix plan --------------------------------------


def _make_bay_tile() -> world.Tile:
    """Canonical transit bay tile used by the authored cities."""
    return world.Tile(
        kind="transit_bay", char="=", walkable=True,
        fg=(0, 229, 255), bg=(30, 68, 92),
    )


def _patch_paint_bays(
    game_map: world.GameMap,
    station_cells: dict[str, tuple[int, int]],
) -> None:
    """Carve a 3x3 transit bay around every (moved) station cell.

    ``force_center`` semantics: the centre cell is written
    unconditionally; the 8 neighbours only when their kind is a
    paintable ground kind (never roads, pads, sidewalks, buildings,
    water — those would corrupt the city's street network).
    """
    bay = _make_bay_tile()
    paintable = {
        "floor", "grass", "grass_accent", "plaza", "city_plaza",
        "sidewalk", "landing_pad", "transit_bay",
    }
    for x, y in station_cells.values():
        for dyc in (-1, 0, 1):
            for dxc in (-1, 0, 1):
                nx, ny = x + dxc, y + dyc
                if not game_map.in_bounds(nx, ny):
                    continue
                if dxc == 0 and dyc == 0:
                    game_map.tiles[ny][nx] = bay
                    continue
                if game_map.tiles[ny][nx].kind in paintable:
                    game_map.tiles[ny][nx] = bay


def _patch_move_station(
    game_map: world.GameMap,
    station: world.Entity,
    new_pos: tuple[int, int],
) -> None:
    """Move one station entity (1x1 footprint) to ``new_pos``."""
    station.pos = world.Position(new_pos[0], new_pos[1])


def _patch_move_npc(
    game_map: world.GameMap,
    npc: world.Entity,
    new_pos: tuple[int, int],
) -> None:
    """Move one ambient NPC entity to ``new_pos``."""
    npc.pos = world.Position(new_pos[0], new_pos[1])


def _nearest_clear_cell(
    game_map: world.GameMap,
    origin: tuple[int, int],
    protected: set[tuple[int, int]],
    max_radius: int = 20,
) -> tuple[int, int] | None:
    """Nearest walkable, unblocked cell outside ``protected`` by ring
    distance (deterministic: ring order, then lower y, then lower x)."""
    for r in range(1, max_radius + 1):
        candidates = []
        for dyc in range(-r, r + 1):
            for dxc in range(-r, r + 1):
                if max(abs(dxc), abs(dyc)) != r:
                    continue
                nx, ny = origin[0] + dxc, origin[1] + dyc
                if not game_map.in_bounds(nx, ny):
                    continue
                tile = game_map.tiles[ny][nx]
                if not tile.walkable or tile.kind in _FORBIDDEN_PAD_KINDS:
                    continue
                if (nx, ny) in protected:
                    continue
                candidates.append((ny, nx))
        if candidates:
            y, x = min(candidates)
            return (x, y)
    return None


def build_fix_plan(
    game_map: world.GameMap,
    *,
    pad_radius: int = 1,
    city_id: str | None = None,
) -> dict | None:
    """Apply recommendations to the in-memory map, verify, emit the plan.

    Returns ``None`` when the map already passes (nothing to fix) or when
    the patched map still fails (the tool refuses to emit an unverified
    plan). On success the returned dict contains an ordered ``ops`` list
    naming the exact file each edit belongs in (spec positions, builder
    bay call, NPC spawn anchors), plus the final check summary.
    """
    spec_path = (
        _spec_relpath(city_id) if city_id
        else "src/spacehack/data/planets/<city>.py"
    )
    # R0 gate: without authored ``serves`` on every station the plan's
    # station-move recommendations have no BFS target and cannot be
    # verified. Refuse with a verbose self-contained instruction instead
    # of emitting an unverifiable plan (see main() for the emitted JSON).
    if check_serves_declared(game_map):
        return None
    r1_violations = check_station_clipping(game_map)
    violations = r1_violations + check_serves(game_map)
    if not violations:
        return None

    ops: list[dict] = []
    station_moves: dict[str, tuple[int, int]] = {}
    npc_moves: list[tuple[world.Entity, tuple[int, int], tuple[int, int]]] = []

    stations = [e for e in game_map.entities if e.transit_station_id]
    others = [e for e in game_map.entities if not e.transit_station_id]

    # Phase A: decide every station move first (recommendations were
    # computed against the ORIGINAL map; applying them in one batch keeps
    # the decisions consistent with what the tool reported). A station
    # moves when ANY of its R1 checks failed — missing/clipped pad or a
    # pad shared with another station. Pads are reserved as decided, and
    # every other station's pad blocks candidates, so two ops can never
    # resolve to the same pad (or onto a staying station's pad).
    moving = {v.station for v in r1_violations}
    entity_blocked: set[tuple[int, int]] = set()
    for e in others:
        entity_blocked |= _footprint(e)
    # Door approaches block candidates: a recommended pad must sit beside
    # the front walk, never on it (R1 check 5).
    entity_blocked |= _door_approach_cells(game_map)
    station_zones = {
        s.transit_station_id: (
            _footprint(s) | _pad_zone(_footprint(s), game_map, pad_radius)
        )
        for s in stations
    }
    reserved: set[tuple[int, int]] = set()
    for station in stations:
        if station.name not in moving:
            continue
        serves = _station_serves(game_map, station)
        target, _src = _resolve_target(game_map, serves) if serves else (None, None)
        blocked = set(entity_blocked)
        for sid, zone in station_zones.items():
            if sid != station.transit_station_id:
                blocked |= zone
        blocked |= reserved
        rec = _recommend_location(
            game_map, (station.pos.x, station.pos.y),
            blocked, pad_radius, target=target,
        )
        if rec is None:
            return None  # no valid location: refuse to emit a partial plan
        new_pos = tuple(rec["pos"])
        reserved |= {new_pos} | _pad_zone({new_pos}, game_map, pad_radius)
        station_moves[station.transit_station_id] = new_pos
        ops.append({
            "seq": len(ops) + 1,
            "op": "move_station",
            "stage": f"{spec_path} transit_stations pos",
            "file": spec_path,
            "station": station.name,
            "station_id": station.transit_station_id,
            "from": [station.pos.x, station.pos.y],
            "to": list(new_pos),
            "basis": rec,
        })

    # Phase B: apply station moves + paint bays on the in-memory map.
    by_id = {s.transit_station_id: s for s in stations}
    for sid, new_pos in station_moves.items():
        _patch_move_station(game_map, by_id[sid], new_pos)
    _patch_paint_bays(game_map, station_moves)
    if station_moves:
        builder = _builder_entry(getattr(game_map, "city_layout_id", ""))
        ops.append({
            "seq": len(ops) + 1,
            "op": "paint_transit_bays",
            "stage": "layout builder, after terrain painters and door forecourts",
            "target": builder,
            "args": {
                "overwrite_kinds": [
                    "floor", "grass", "grass_accent", "plaza",
                    "city_plaza", "sidewalk", "landing_pad",
                ],
                "force_center": True,
                "bay_tile": {
                    "kind": "transit_bay", "char": "=", "walkable": True,
                },
            },
        })

    # Phase C: relocate clipped ambient NPCs (pad zones recomputed on the
    # patched map). Only entities that actually sit inside a protected
    # zone move, and only to the nearest clear walkable cell.
    stations = [e for e in game_map.entities if e.transit_station_id]
    others = [e for e in game_map.entities if not e.transit_station_id]
    protected_all: set[tuple[int, int]] = set()
    for station in stations:
        protected_all |= _footprint(station)
        protected_all |= _pad_zone(_footprint(station), game_map, pad_radius)
    for npc in others:
        if not getattr(npc, "city_npc_id", None):
            continue  # terminals/ships are authored fixtures, not roamed
        overlap = protected_all & _footprint(npc)
        if not overlap:
            continue
        cell = min(overlap)
        new_pos = _nearest_clear_cell(game_map, (npc.pos.x, npc.pos.y), protected_all)
        if new_pos is None:
            return None
        npc_moves.append((npc, (npc.pos.x, npc.pos.y), new_pos))
        ops.append({
            "seq": len(ops) + 1,
            "op": "move_npc",
            "stage": "src/spacehack/data/city_npcs.py spawn anchor",
            "file": "src/spacehack/data/city_npcs.py",
            "entity": npc.name,
            "entity_id": npc.city_npc_id,
            "from": [npc.pos.x, npc.pos.y],
            "to": list(new_pos),
            "reason": f"clips station pad zone at {list(cell)}",
        })
    for npc, _old, new_pos in npc_moves:
        _patch_move_npc(game_map, npc, new_pos)

    # Phase D: verify. The plan is only emitted if the patched map passes.
    residual = check_station_clipping(game_map) + check_serves(game_map)
    if residual:
        return {
            "verified": False,
            "residual_violations": [
                {
                    "rule_id": v.rule_id,
                    "station": v.station,
                    "message": v.message,
                }
                for v in residual[:10]
            ],
            "ops": ops,
        }
    return {
        "verified": True,
        "note": "all R1/R2 checks pass on the patched in-memory map",
        "ops": ops,
    }


# ----- Authoring locations + test impact -------------------------------


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def _spec_relpath(city_id: str) -> str:
    """Exact repo-relative path of the planet spec defining ``city_id``.

    Imports every ``data/planets`` submodule (all already imported by the
    spec registry) and returns the one whose ``SPEC.id`` matches.
    """
    import importlib
    import pkgutil

    from spacehack.data import planets as pkg

    for m in pkgutil.iter_modules(pkg.__path__):
        mod = importlib.import_module(f"spacehack.data.planets.{m.name}")
        spec_obj = getattr(mod, "SPEC", None)
        if spec_obj is not None and getattr(spec_obj, "id", None) == city_id:
            return str(
                Path(mod.__file__).resolve().relative_to(_repo_root())
            )
    return "src/spacehack/data/planets/<unknown>.py"


def _builder_entry(city_layout_id: str) -> dict | None:
    """Module + function of the layout builder for ``city_layout_id``."""
    import importlib

    from spacehack import city_builder

    entry = (getattr(city_builder, "_LAYOUTS", None) or {}).get(city_layout_id)
    if not entry:
        return None
    mod_name, func_name = entry[0], entry[1]
    mod = importlib.import_module(f"spacehack.{mod_name}")
    path = str(Path(mod.__file__).resolve().relative_to(_repo_root()))
    return {"module": mod_name, "function": func_name, "file": path}


def _tests_referencing(city_id: str, *, limit: int = 40) -> list[dict]:
    """Tests that pin this city: every ``file:line`` in tests/ whose source
    line mentions the quoted city id (count pins, grandfather tables,
    per-city test names). Station-id pins on the same lines are covered;
    the city id is the stable anchor."""
    hits: list[dict] = []
    for path in sorted((_repo_root() / "tests").rglob("*.py")):
        try:
            lines = path.read_text().splitlines()
        except OSError:
            continue
        rel = str(path.relative_to(_repo_root()))
        for n, text in enumerate(lines, start=1):
            if f'"{city_id}"' in text or f"'{city_id}'" in text:
                hits.append(
                    {"file": rel, "line": n, "text": text.strip()}
                )
                if len(hits) >= limit:
                    return hits
    return hits


# ----- Output ---------------------------------------------------------


def _violation_dicts(violations: list[Violation]) -> list[dict]:
    """JSON-ready violation entries (shared by every report format)."""
    return [
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


def report_json(city_id: str, game_map: world.GameMap, violations: list[Violation], *, skipped: list[str] | None = None) -> str:
    """Full JSON report: map dump + violations."""
    payload = dump_map(game_map, city_id)
    payload["violations"] = _violation_dicts(violations)
    if skipped:
        payload["skipped_checks"] = skipped
        payload["gate"] = "R0"
    payload["passed"] = not violations
    return json.dumps(payload, ensure_ascii=False, indent=2)


def report_summary(city_id: str, game_map: world.GameMap, violations: list[Violation], *, skipped: list[str] | None = None) -> str:
    """Compact JSON report: verdict + violations, no tile/entity dump."""
    payload: dict = {
        "city_id": city_id,
        "width": game_map.width,
        "height": game_map.height,
        "passed": not violations,
        "violation_count": len(violations),
        "violations": _violation_dicts(violations),
    }
    if skipped:
        payload["skipped_checks"] = skipped
        payload["gate"] = "R0"
    return json.dumps(payload, ensure_ascii=False, indent=2)


def report_fix_plan(city_id: str, plan: dict) -> str:
    """JSON report for ``--fix-plan`` (ordered, machine-readable ops)."""
    payload = {"city_id": city_id, **plan}
    return json.dumps(payload, ensure_ascii=False, indent=2)


def r0_refusal_payload(city_id: str, r0: list[Violation]) -> dict:
    """JSON payload for the ``--fix-plan`` R0 refusal.

    Self-contained and copy-paste ready: per-station suggested ``serves``
    edits (the R0 check already computed them — never make the caller
    re-derive), duplicate-suggestion flags (two stations pointed at the
    same target is a redundant stop — a delete-or-re-target decision the
    author must make before R1/R2 can produce a consistent plan), the
    exact spec file, and the tests that pin this city.
    """
    suggestions = [
        (v.recommendation or {}).get("serves") if v.recommendation else None
        for v in r0
    ]
    dupes = sorted({
        s for s in suggestions if s and suggestions.count(s) > 1
    })
    stations = []
    for v, serves in zip(r0, suggestions):
        entry: dict = {"station": v.station, "station_pos": list(v.location)}
        if serves:
            entry["serves"] = serves
            entry["edit"] = f'serves="{serves}"'
        stations.append(entry)
    payload: dict = {
        "city_id": city_id,
        "verified": False,
        "gate": "R0",
        "note": (
            "R0 failed: some transit stations do not declare 'serves'. "
            "Fix-plan is refused: station-move recommendations are ranked "
            "by walkable distance to the served target, which is unknown "
            "without 'serves'. Apply each suggested edit below (override "
            "if authored intent differs), then re-run this command."
        ),
        "how_to_fix": {
            "file": _spec_relpath(city_id),
            "place": "transit_stations tuple, inside each "
                     "world.TransitStation(...)",
            "edit": "add serves=\"<label>\" to each world.TransitStation(...)",
            "value": "a building label from spec.buildings or a landmark "
                     "key without the <city_id>_city_ prefix — the "
                     "suggested value per station is below",
            "stations_missing_serves": stations,
            "next_step": f"re-run: python3 tools/city_audit.py "
                         f"--city {city_id} --fix-plan",
        },
        "ops": [],
    }
    if dupes:
        payload["duplicate_serves_suggestions"] = dupes
        payload["decision_required"] = (
            "Multiple stations suggest the same serves target "
            f"({', '.join(dupes)}): the network has a redundant stop. "
            "Delete one TransitStation (and scrub it from every "
            "destinations tuple) or re-target it to a distinct building/"
            "landmark. A verified fix-plan cannot be produced while two "
            "stations serve the same target."
        )
    tests = _tests_referencing(city_id)
    if tests:
        payload["tests_referencing_city"] = tests
    return payload


def report_text(city_id: str, game_map: world.GameMap, violations: list[Violation], *, skipped: list[str] | None = None) -> str:
    """Human-readable report."""
    lines = [
        f"CITY: {city_id}  ({game_map.width}x{game_map.height}, "
        f"{len(game_map.entities)} entities)",
    ]
    if skipped:
        lines.append("  GATE: R0 failed — skipped: " + ", ".join(skipped))
    if not violations:
        lines.append("  PASS - no violations.")
        return "\n".join(lines)
    printed_remediation: set[str] = set()
    for v in violations:
        lines.append(f"  [{v.rule_id}] {v.message}")
        if v.recommendation and v.station not in printed_remediation:
            rec = v.recommendation
            if "serves" in rec:
                lines.append(
                    f"      -> recommended: serves=\"{rec['serves']}\" — {rec['note']}"
                )
            else:
                lines.append(
                    f"      -> recommended: move to {tuple(rec['pos'])} "
                    f"(distance {rec.get('distance')}) — {rec['note']}"
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
        "--format", choices=("summary", "json", "text"), default="summary",
        help="output format (default: summary — verdict + violations, no "
             "tile dump; json adds the full map dump)",
    )
    parser.add_argument(
        "--fix-plan", action="store_true",
        help="apply recommendations to the in-memory map, verify, and emit "
             "a machine-readable edit plan (JSON only)",
    )
    args = parser.parse_args()

    try:
        game_map = build_final_map(args.city)
    except KeyError:
        print(f"Unknown city id: {args.city}", file=sys.stderr)
        return 1

    if args.fix_plan:
        # R0 gate: without authored ``serves`` the fix plan cannot rank or
        # verify station moves (BFS target unknown). Fail fast with a
        # verbose, self-contained instruction instead of a partial plan.
        r0 = check_serves_declared(game_map)
        if r0:
            print(json.dumps(
                r0_refusal_payload(args.city, r0),
                ensure_ascii=False, indent=2,
            ))
            return 1
        plan = build_fix_plan(game_map, city_id=args.city)
        if plan is None:
            print(json.dumps({
                "city_id": args.city,
                "verified": True,
                "note": "map already passes; nothing to fix",
                "ops": [],
            }, ensure_ascii=False, indent=2))
            return 0
        tests = _tests_referencing(args.city)
        if tests:
            plan["tests_referencing_city"] = tests
        print(report_fix_plan(args.city, plan))
        return 0 if plan.get("verified") else 1

    # R0 gate: authored intent first. While any station lacks ``serves``,
    # R1/R2 are skipped entirely — their recommendations and target checks
    # depend on knowing what each station serves.
    r0 = check_serves_declared(game_map)
    violations: list[Violation]
    skipped: list[str] = []
    if r0:
        violations = r0
        skipped = ["R1 (station pad integrity)", "R2 (serves target validity)"]
    else:
        violations = check_station_clipping(game_map) + check_serves(game_map)

    if args.format == "text":
        print(report_text(args.city, game_map, violations, skipped=skipped))
    elif args.format == "json":
        print(report_json(args.city, game_map, violations, skipped=skipped))
    else:
        print(report_summary(args.city, game_map, violations, skipped=skipped))

    return 0 if not violations else 1


if __name__ == "__main__":
    raise SystemExit(main())
