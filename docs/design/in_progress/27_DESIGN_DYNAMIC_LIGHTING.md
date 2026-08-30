# Design: Dynamic Per-Cell Coloured Lighting

## Overview

Add a reusable per-cell coloured light map to the game so that light
sources — neon signs, beacons, weapon flashes, glowing dungeon features,
engine exhaust — tint the cells around them with falloff. The system is
mode-agnostic: every map type that renders through `world_render` benefits
once a light grid is seeded. The first concrete use case is Venus's neon
signs spilling coloured light onto the avenues; the reusable primitive then
extends to dungeon delves (where light can extend the player's sight),
space combat (weapon flashes, drive glow), and ground combat (muzzle flash,
explosions).

The light map is a **derived, presentation-only** concern. It is never
serialized and never affects game logic — it only changes the `(fg, bg)`
colours that `_tile_render_colors()` returns. The only gameplay-facing
interaction (dungeons: light extending sight radius) is an explicit, separate
flag, not a side effect of the tint.

## Rendering model — two layers, not one

The engine paints a frame in **two distinct layers**:

### Layer A — the bitmap/cell layer (`engine.logical_surface`)

1. `world_render._tile_render_colors(game_map, x, y, tile)` returns
   `(fg, bg)` — the tile's own colours, dimmed when a cell is remembered but
   not currently visible (dungeon fog only).
2. `_append_tile_commands()` emits one `WorldDrawCommand(x, y, char, fg, bg)`
   per visible cell.
3. `pygame_runtime.present()` calls `_paint_world_commands()` →
   `GlyphAtlas.blit()` paints each glyph with `BLEND_RGBA_MULT` onto its
   background fill.

This layer is single-pass, one-cell-at-a-time, no alpha compositing.

### Layer B — the native Pygame overlay (on top of the bitmap)

After Layer A, `pygame_runtime.present()` calls
`pygame_overlay.draw_map_effects()` which paints onto the *same*
`logical_surface`, and then `engine.present(physical_overlay=...)` paints
HUD/message-log panels onto the *scaled physical window*. The overlay layer
already carries:

- **`ShieldBubble`** — shield rings drawn over ships/entities.
- **`FloatingText`** — floating damage numbers, drawn with a real Pygame
  font (`pygame_ui.cell_font`), rising + fading per frame, with a 1px
  shadow. Explicitly documented as *"rendered by Pygame, not the bitmap."*
- **`TargetCard`** — the combat target readout.

These are per-frame, native-Pygame-font, and **transient by nature** —
floaters are cleared each frame via `active_floaters()` (consume-on-read).

### Which layer gets lighting, and why

The two light types have different lifetimes, so they belong in different
layers:

| Light type | Lifetime | Layer | Why |
|---|---|---|---|
| **Static ambient light** (neon signs, beacons, dungeon glow, drive exhaust) | Persistent, map-owned | **Layer A — bitmap colour blend** in `_tile_render_colors()` | It should tint the city/dungeon 100% of the time, survive save/load, and not re-run every frame. It is a property of the map's tiles, so tinting the tile colours is the persistent, save-stable home. |
| **Transient effect light** (weapon flashes, explosions, muzzle flash) | 1–3 frames, ephemeral | **Layer B — overlay glow** alongside `FloatingText`/`ShieldBubble` | This is the established, consistent home for ephemeral combat map effects. A flash is the same kind of thing as a floater — queued per frame, drawn on top, consumed on read. |

**Static light (Layer A):** `_tile_render_colors()` consults the
`light_grid` and blends the tile's `fg`/`bg` toward the light colour by the
cell's light intensity. No new framebuffer/engine blit path, no alpha
support needed — it is a colour manipulation on the existing seam, like the
existing `_dim_color()` fog dimming.

**Transient light (Layer B):** a new `LightGlow` effect (a coloured radial
blit) joins `OverlayFrame` as a field, drawn by a new
`pygame_overlay._draw_glows()` in the same place `_draw_floaters()` runs.
This reuses the overlay plumbing (`active_*()` consume-on-read, per-frame
queue) that combat already uses, instead of forcing transient effects into
the bitmap layer where they'd have to be recomputed and reseeded every tick.

The two layers compose: a static neon tint (Layer A) plus a transient
weapon-flash glow (Layer B) both apply — the flash brightens an already
neon-tinted cell, exactly as expected.

## Philosophy alignment

| Project rule | Lighting application |
|---|---|
| Data-first | Light sources are authored data (neon tiles, beacon tiles, dungeon feature kinds); no light definitions live in `__main__` or render modules. |
| ctx-first | The light grid lives on `GameMap` (the map owns its derived presentation state), not on a bare module global. |
| Pure computation is tested | The falloff/propagation primitive is a pure function over a grid; it ships with pytest coverage in the same commit. |
| Reuse before duplication | One shared `lighting.py` primitive is seeded by every domain; no per-domain flood reimplementation. |
| Save/load contract | The light grid is **derived state** (recomputable from tiles + entities), so it is never serialized — audited explicitly below. |
| Performance awareness | Static light (cities) is computed once at build; transient light (combat/space) is clear-and-reseed of affected cells only, never full-map BFS per tick. |
| SRP / ≤40-line functions | The blend, propagation, and seeding helpers are each one verb phrase; the top-level orchestrator stays thin. |
| Atomic commits | Each phase is independently testable and committed separately. |

## Data model

### `GameMap` field

```python
# world.py — GameMap dataclass
light_grid: list[list[tuple[int, int, int]]] | None = None
```

A 2-D array of `(r, g, b)` additive-light colours, the same shape as
`tiles`. `None` means "no light grid — render as today" (the fallback every
mode uses until a builder or domain seeds it). This matches the
`seen`/`visible` precedent: derived, optional, recomputed on load.

**Why RGB tuples, not a scalar intensity:** coloured light is the motivating
feature (pink/cyan neon, red emergency lighting). A scalar would force
monochrome and lose the signature visual. Additive RGB tuples let multiple
sources combine (a red flash on a cyan-lit corridor).

**Why not a separate intensity grid:** colour already encodes intensity
(brightness is the max channel). A pure-colour grid is one structure to
seed, blend, and clear, not two.

### Light source records

Static light sources are not a new persisted type. They are discovered from
existing tile kinds and entity flags:

| Source kind | Where it lives | How it's found |
|---|---|---|
| Static tile light | `tile.kind` (`neon`, `beacon`, `glow_fungus`, …) | scan the map's tiles |
| Entity-carried light | `entity.light_colour` / `entity.light_radius` fields | scan the map's entities |

Transient effect light is **not** stored on `GameMap` — it lives in the
overlay layer (Layer B), alongside floaters, because it is per-frame and
ephemeral (see Transient effect light below).

For tile-based static light, the colour/radius come from a table in
`data/` (see Domain seeding), not from new `Tile` fields — tiles stay
pure render data.

### Transient effect light (overlay layer, Layer B)

Transient light (weapon flashes, explosions) follows the existing
`FloatingText` pattern exactly — it is an overlay effect, not `GameMap`
state:

```python
# pygame_overlay.py — joins FloatingText / ShieldBubble in OverlayFrame
@dataclass(frozen=True)
class LightGlow:
    """One native radial light glow drawn by Pygame over the map region."""
    x: int               # viewport-relative cell x
    y: int               # viewport-relative cell y
    colour: tuple[int, int, int]
    radius: int          # in cells
    age: int             # frame age (0 = spawn)
    lifetime: int        # total frame count

# OverlayFrame gains: glows: tuple[LightGlow, ...] = ()
```

Combat/space queue `LightGlow`s via a `combat._animations` helper (same
module-level `_set_floaters` pattern). `pygame_overlay._draw_glows()`
paints them with a radial alpha-blended blit (a small pre-built glow
surface, `BLEND_RGBA_ADD`), clipped to the map region, fading with `age`.
This is the same consume-on-read per-frame queue floaters use — no
`GameMap` field, no serialization, no per-tick grid recompute.

## The lighting primitive (`lighting.py`)

A new `src/spacehack/lighting.py` owns the pure, testable core:

```python
def propagate_light(
    width: int, height: int,
    sources: Iterable[LightSource],
    *,
    falloff: float = 0.5,   # intensity multiplier per cell of distance
) -> list[list[tuple[int, int, int]]]:
    """Return an additive colour grid from the given light sources.

    Each source colours cells within its Chebyshev radius; intensity
    falls off by ``falloff`` per cell of distance from the source.
    Colours from overlapping sources add (clamped to 255 per channel).
    Pure: no I/O, no mutation of arguments, deterministic.
    """

@dataclass(frozen=True)
class LightSource:
    x: int
    y: int
    colour: tuple[int, int, int]
    radius: int
    intensity: float = 1.0
```

**Falloff model:** Chebyshev distance, linear per-cell `falloff` (e.g.
`0.5` means a source of intensity `1.0` at distance 2 contributes
`0.5 * 0.5 = 0.25`). Linear is cheap and readable; a real inverse-square
isn't worth the cost on a 16×16 grid cell. The function is pure and ships
with tests covering: single source, overlapping sources (additive clamp),
radius zero, falloff edge, and empty sources → all-black grid.

### Render integration

```python
# world_render.py
def _tile_render_colors(game_map, x, y, tile) -> tuple[tuple, tuple]:
    fg, bg = _base_colors(game_map, x, y, tile)   # existing logic, renamed
    light = _light_at(game_map, x, y)
    if light == (0, 0, 0):
        return fg, bg
    return _blend_toward_light(fg, bg, light)

def _light_at(game_map, x, y) -> tuple[int, int, int]:
    if game_map.light_grid is None:
        return (0, 0, 0)
    return game_map.light_grid[y][x]
```

`_blend_toward_light` is a pure additive blend: each channel is
`min(255, base + (light_channel * intensity))`. Kept simple — this is a
tint, not a hue shift.

## Domain seeding cadence

| Domain | When light grid is (re)computed | Source types | Perf note |
|---|---|---|---|
| Cities | Once, at `build_*_layout` build time | Static tiles (neon, beacon) | Zero per-tick cost; grid is frozen after build. |
| Dungeons / derelicts | On every `reveal_around` (player move) | Static tiles + player torch | Same cadence as FOV; the propagation runs alongside the existing BFS, not in addition. |
| Space | Static glow cached; transient via overlay layer | Static (star/ship drive) on grid + transient flashes as `LightGlow` | Static grid recomputed on ship move only; transient flashes never touch the bitmap grid — they are overlay-blitted per frame, like floaters. |
| Ground combat | Static glow cached; transient via overlay layer | Entity-carried lights on grid + transient flashes as `LightGlow` | Combat is turn-based; transient flashes are overlay-blitted per frame. |

**Static-light caching rule:** when a domain's light sources don't change
between frames (city at rest, dungeon between moves), the grid is not
recomputed. A `_light_dirty` flag (or simply recomputing on the events that
move sources) governs this. This is the performance guardrail from
`knowledge.md`: never add an O(n) full-map pass every tick when the sources
are static.

## Dungeon sight extension (the gameplay hook)

In dungeon mode, a light source can extend the player's effective sight
radius near it. This is **not** a side effect of the colour tint — it's a
separate, explicit behaviour:

- `dungeon_fov.reveal_around()` already casts rays to `sight_radius`.
- A new optional pass, `dungeon_fov.reveal_lit_sources()`, casts additional
  short rays from each lit cell (e.g. a glow-fungus patch with
  `light_radius >= 3` reveals a 3-cell bubble around itself), marking those
  cells `seen=True` even if outside the player's base radius.
- This is gameplay-relevant (the player can navigate toward light to see
  further), so it is tested and documented, not incidental.

This phase is deliberately last so the pure-lighting primitive is stable
before it gains a gameplay dependency.

## Save/load contract treatment

| State | Serialized? | Why |
|---|---|---|
| `GameMap.light_grid` | **No** | Derived from tiles + entities; recomputed on load. Matches `visible`/`seen` precedent. |
| `GameMap.light_effects` | — | **Removed**: transient light is now `LightGlow` on the overlay layer (`OverlayFrame`), not a `GameMap` field. Nothing to serialize. |
| Authored light source data (tile kinds, entity fields) | **Yes** (via existing tile/entity serialization) | These are already saved as part of the map; no new serialization. |

**Checklist for the save/load contract:**
- [ ] `saveload._ctx_to_dict()` and `load_game()` do **not** reference
      `light_grid` — it is recomputed. (`LightGlow` is overlay-only and
      never touches `GameMap` or save data.)
- [ ] On `load_game()`, the city/dungeon rebuild path calls the lighting
      seed pass (so a loaded city has its neon glow without a player move).
- [ ] The sniff test: save in a lit city → quit → continue → the neon
      glow is visible immediately, not after the first move.

## Pre-implementation audit

### 1. Existing classes / modules to extend or reuse

- **`world.GameMap`** (`world.py:339`) — add the `light_grid` field only.
  The `seen`/`visible` fields (`world.py:348-349`) are the architectural
  precedent for derived, non-serialized grid state. (`light_effects` is
  gone — transient light lives on the overlay layer.)
- **`world_render._tile_render_colors()`** (`world_render.py:54`) — the
  single colour-resolution seam for the static-light blend (Layer A).
  Renaming the existing body to `_base_colors()` and wrapping it keeps the
  fog-dimming path intact.
- **`world_render._dim_color()`** (`world_render.py:41`) — the existing
  colour-manipulation helper; `_blend_toward_light` follows its shape.
- **`pygame_overlay.OverlayFrame`** (`pygame_overlay.py:103`) — gains a
  `glows` field, joining `shields`/`floaters`/`target`. The overlay layer
  (Layer B) is the home for transient `LightGlow` effects.
- **`pygame_overlay._draw_floaters()`** (`pygame_overlay.py:699`) — the
  template for the new `_draw_glows()`: per-frame, consume-on-read,
  clipped to the map region, Pygame-blitted.
- **`combat/_animations.py` `_set_floaters`/`active_floaters`** — the
  per-frame queue pattern `LightGlow` will mirror for transient flashes.
- **`dungeon_fov.reveal_around()`** (`dungeon_fov.py`) — the FOV cast that
  dungeon lighting hooks into (Phase 3).
- **`data/planets/themes.py`** — the neon/beacon tile definitions already
  exist; the static-light source table reads `tile.kind`, so no new fields
  on `Tile`.

### 2. Three potential duplication hotspots

- **Per-domain flood loops.** If each domain (city, dungeon, space, combat)
  reimplements "iterate sources, paint falloff into a grid," that is four
  copies of the same algorithm. This is the cardinal DRY risk.
- **Colour-blend arithmetic.** `_blend_toward_light` could be duplicated in
  the framebuffer or a debug overlay if those want to show light; the
  helper must live in `lighting.py` and be imported.
- **Source discovery.** Scanning `tiles` for lit kinds and `entities` for
  light fields could be copy-pasted per domain; one
  `collect_light_sources(game_map)` helper serves all.

### 3. DRY strategy for each hotspot

- **One `lighting.propagate_light()`** pure function; every domain calls it
  with its own source list. No domain reimplements the flood. (Guardrail:
  pure functions for computation.)
- **`_blend_toward_light`** lives in `lighting.py` (or `world_render.py`
  if it must stay renderer-adjacent); imported, not copied.
- **`collect_light_sources(game_map)`** in `lighting.py` discovers static
  tile light and entity-carried light in one pass for the bitmap grid.
  Transient `LightGlow` effects bypass this entirely — they are queued
  directly to the overlay layer, like floaters, and never touch
  `light_grid`. (Guardrail: batch entity iteration, avoid quadratic passes.)

## Phased implementation plan

### Phase 1 — Lighting primitive and render blend

- [ ] `lighting.py`: `LightSource` dataclass, `propagate_light()` pure
      function with Chebyshev-falloff additive blend.
- [ ] `tests/test_lighting.py`: single source, overlapping sources, radius
      zero, falloff edge, empty sources.
- [ ] `world.GameMap`: add the `light_grid` field (default `None`).
      No `light_effects` field — transient light is overlay-only.
- [ ] `world_render._tile_render_colors()`: consult `light_grid`, blend
      via `lighting._blend_toward_light`, with `None` → no-tint fallback.
- [ ] Gate: smoke + architecture + Ruff + pytest.

### Phase 2 — City static light (Venus neon)

- [ ] `data/planets/themes.py` or a new `data/lighting.py`: static-light
      source table (`neon` → pink/cyan, `beacon` → warm gold, with radius).
- [ ] `lighting.collect_light_sources(game_map)`: scan tiles by kind.
- [ ] Venus `build_venus_layout()`: seed `light_grid` once at build via
      `propagate_light(collect_light_sources(game_map))`.
- [ ] `tests/test_venus_city.py`: assert neon-adjacent avenue cells carry
      non-zero light; far cells carry zero.
- [ ] Save/load sniff test: lit city survives save/quit/continue.
- [ ] Gate.

### Phase 3 — Dungeon ambient light and sight extension

- [ ] `dungeon_fov`: after `reveal_around`, call `propagate_light` over
      static dungeon light sources (glow fungus, reactor cores).
- [ ] `dungeon_fov.reveal_lit_sources()`: cast short rays from lit cells
      to extend `seen`/`visible` (the gameplay hook).
- [ ] `tests/test_dungeon_fov.py` (or new): lit cell reveals neighbours
      beyond base sight radius; unlit corridor stays dark.
- [ ] Save/load: dungeon light recomputed on `reveal_around` after load.
- [ ] Gate.

### Phase 4 — Space and ground combat transient light (overlay layer)

- [ ] `pygame_overlay.LightGlow` dataclass + `OverlayFrame.glows` field.
- [ ] `pygame_overlay._draw_glows()`: radial alpha-blended blit
      (`BLEND_RGBA_ADD`) using a small pre-built glow surface, clipped to
      the map region, fading with `age` — mirrors `_draw_floaters()`.
- [ ] `combat/_animations.py`: a `_set_glows`/`active_glows` queue
      (same module-level pattern as `_set_floaters`/`active_floaters`);
      combat/space queue a `LightGlow` on weapon fire / explosion.
- [ ] Wire `draw_map_effects` to call `_draw_glows` alongside
      `_draw_floaters`.
- [ ] `tests/test_lighting.py` (or `test_pygame_overlay.py`): glow is
      queued on fire, consumed on read, fades with age.
- [ ] Save/load: nothing to do — `LightGlow` is overlay-only, never on
      `GameMap`, never serialized.
- [ ] Gate.

### Phase 5 — Polish and guide

- [ ] `help.py` / `data/guide/`: add a "Lighting" guide entry explaining
      that light extends sight in dungeons and that neon signs glow.
- [ ] Performance check: no new O(n) full-map pass per tick in space mode.
- [ ] Final gate and city + dungeon playtest.

## Acceptance criteria

- A reusable, pure, tested `lighting.propagate_light()` primitive that no
  domain reimplements.
- `_tile_render_colors()` blends toward light with a `None`-grid fallback
  that preserves today's rendering exactly.
- Venus neon signs visibly tint adjacent avenue cells with coloured falloff.
- Dungeon light sources extend the player's sight near them (gameplay-relevant,
  tested).
- Space/ground combat weapon fire produces brief coloured light flashes.
- The light grid is never serialized; loaded maps recompute their light.
- `make check` passes with focused regression coverage at each phase.
- No new per-tick O(n) full-map pass in the perf-sensitive space mode.

## Open questions

- **Falloff curve:** linear-per-cell (cheap, proposed) vs. inverse-square
  (smoother, costlier). Defer to a playtest visual comparison in Phase 2.
- **Light through walls:** should dungeon light propagate through walls
  (leaking under doors) or stop at blockers? Propose: stop at blockers
  (match FOV), revisit if the visual reads wrong.
- **Entity light fields:** do ships/characters get `light_colour`/`light_radius`
  fields (data-first) or is entity light inferred from kind (like tiles)?
  Propose: fields on `Entity`/`OwnedShip`, declared in `world.py`, seeded
  from data in Phase 4.
