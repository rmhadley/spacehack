# Design: Time-Varying Per-Cell Light and Animated Map Overlays

## Overview

Build a reusable, time-aware per-cell overlay system so that persistent
map features — neon signs, beacons, dungeon glow, river currents,
shimmering water — can vary over time, and transient effects — weapon
flashes, explosions, muzzle flash — can appear and fade. The system is
mode-agnostic: every map type that renders through `world_render` benefits
once a time-varying grid is seeded and a frame clock exists.

The first concrete use cases are Venus's neon signs (a persistent,
flickering cyberpunk glow on the avenues) and Earth's river current
(an animated water overlay). Both are instances of the same primitive:
a cell grid whose contents are a pure function of time. The reusable
foundation is the **animation clock** + the **time-varying grid** +
the **blend/overlay seams**. Static light is the special case where
`f(t) = constant`.

The core realisation driving this design: **flickering neon is the proof
point that the clock is load-bearing, not optional.** Shipping a static
neon glow would produce a foundation that must be rebuilt the moment
flicker, current, or shimmer is wanted. So the primitive is designed,
from the start, as time-varying — a steady glow is `flicker = const`.

## Scope: this is an overlay foundation, not just lighting

This design deliberately covers more than "Venus neon." It establishes
the shared infrastructure that several future features need:

| Feature | Light type | Animated? | Layer |
|---|---|---|---|
| Venus neon glow + flicker | Persistent, flickering | Yes (buzz/flicker) | Bitmap blend |
| Earth river current | Persistent animation | Yes (flowing) | Overlay or bitmap |
| Dungeon ambient glow | Persistent | No (steady) | Bitmap blend |
| Beacon / pad light | Persistent | No | Bitmap blend |
| Weapon flash / explosion | Transient | Yes (fade) | Overlay |
| Cloud deck shimmer | Persistent animation | Yes | Bitmap blend |

All of these read from a shared per-frame clock and use one
`propagate_light(t)` primitive. Designing the foundation now avoids the
per-domain duplication that building them piecemeal would produce (the
cardinal DRY risk flagged in the audit).

## Rendering model — two layers, one clock

The engine paints a frame in **two layers**, and the animation clock
feeds both:

### Layer A — bitmap/cell layer (`engine.logical_surface`)

1. `world_render._tile_render_colors(game_map, x, y, tile, *, t)` returns
   `(fg, bg)` — the tile's colours, dimmed for dungeon fog, **then
   blended toward the light grid**.
2. `_append_tile_commands()` emits one `WorldDrawCommand` per cell.
3. `pygame_runtime.present()` calls `_paint_world_commands()` →
   `GlyphAtlas.blit()` paints each glyph with `BLEND_RGBA_MULT`.

Single-pass, one-cell-at-a-time, no alpha compositing. This is where
**persistent, time-varying light** (flickering neon, river tint, steady
beacon) lives — it tints the tile colours, so it survives save/load and
doesn't re-run from scratch every frame.

### Layer B — native Pygame overlay (on top of the bitmap)

After Layer A, `pygame_overlay.draw_map_effects()` paints onto the same
`logical_surface`, and `engine.present(physical_overlay=...)` paints
HUD/log panels onto the scaled window. The overlay already carries
`FloatingText` (floating damage numbers), `ShieldBubble`, `TargetCard`.
These are per-frame, native-Pygame-font, transient by nature (floaters
clear each frame via consume-on-read).

This is where **transient effects** (weapon flashes, explosions) live —
they're the same kind of thing as floaters: queued per frame, drawn on
top, consumed on read.

### The animation clock (new — the shared foundation)

Today there is **no frame clock in the render path**. `FloatingText.age`/
`lifetime` are per-effect spawn counters, not a global clock. The
overlay layer is stateless between frames. A river current, a flickering
neon, and a shimmering cloud deck all need a global monotonic frame
counter threaded into the render path. This is the one piece of
infrastructure that doesn't exist yet and that multiple features need.

```python
# The clock is a single integer advanced once per presented frame.
# It lives on the Pygame runtime adapter (presentation-only, not game
# state — it does not advance on save/load and is not serialized).
# pygame_runtime.py — PygameContext
_frame_clock: int = 0

def present(self, console, *, overlay=None):
    self._frame_clock += 1
    # ... rest of present, passing t=self._frame_clock to:
    #   - world_render (for the bitmap light blend)
    #   - pygame_overlay.draw_map_effects (for overlay effects)
```

**Why on the runtime adapter, not `GameContext`:** the clock is a
presentation concept (frames presented), not a gameplay concept (ticks
elapsed). Game time already lives on `ctx` (`time_day`/`time_month`/
`time_year` via `time.advance_time`); the frame clock is distinct and
must not conflate with it. Putting it on `PygameContext` keeps it out of
save data and out of game logic, matching the "runtime boundary" rule.

**Determinism for flicker:** flicker profiles are pure functions of
`(source, t)`. Since `t` is monotonic and the source's identity is
stable, the flicker is deterministic for a given clock value. On
save/load, the clock resets to 0 — but since the *light grid* is
recomputed from tiles (which are saved) + the clock (which restarts),
the visual continues smoothly. Flicker that "jumps" on load is
acceptable (the player can't perceive a phase reset in a 60fps flicker).

## Philosophy alignment

| Project rule | Application |
|---|---|
| Data-first | Light sources and animation profiles are authored data (neon tiles + flicker profile, river kind + flow profile); no definitions in `__main__` or render modules. |
| ctx-first | The light grid lives on `GameMap`; the frame clock lives on `PygameContext` (presentation state, not game state). |
| Pure computation is tested | `propagate_light(t)` and the flicker/flow profiles are pure functions; they ship with pytest coverage in the same commit. |
| Reuse before duplication | One `lighting.propagate_light(t)` + one clock serves neon, river, dungeon, combat. No per-domain flood or clock reimplementation. |
| Save/load contract | Light grid is derived (recomputed on load); frame clock is presentation-only (never serialized). Audited explicitly below. |
| Performance awareness | Persistent light recomputes only when `t` changes meaningfully (throttle: flicker every N frames, steady light cached). Transient light is overlay-only, never touches the bitmap grid. No per-tick full-map BFS. |
| SRP / ≤40-line functions | Clock advance, grid propagation, blend, and overlay draw are each one verb phrase. |
| Atomic commits | Each phase is independently testable and committed separately. |

## Data model

### `GameMap` field — the time-varying light grid

```python
# world.py — GameMap dataclass
light_grid: list[list[tuple[int, int, int]]] | None = None
```

A 2-D array of additive `(r, g, b)` light colours, same shape as
`tiles`. `None` = no light grid → render as today (the fallback every
mode uses until a builder seeds it). Matches the `seen`/`visible`
precedent: derived, optional, recomputed.

The grid is **recomputed each presented frame** for flickering sources,
but the recompute is cheap (see Performance) and only runs when the map
is on screen. A `None` grid skips all light work.

### Light sources with animation profiles

```python
# lighting.py
@dataclass(frozen=True)
class LightSource:
    x: int
    y: int
    colour: tuple[int, int, int]
    radius: int
    intensity: float = 1.0
    flicker: str = "steady"   # profile key, looked up in the table below

# A flicker profile is a pure function (source, t) -> intensity multiplier.
FlickerProfile = Callable[[LightSource, int], float]

FLICKER_PROFILES: dict[str, FlickerProfile] = {
    "steady":   lambda s, t: 1.0,
    "buzz":     lambda s, t: 0.85 + 0.15 * ((hash((s.x, t // 4)) % 2)),
    "flicker":  lambda s, t: 0.7 + 0.3 * ((hash((s.x, s.y, t // 7)) % 3) / 2),
    "pulse":    lambda s, t: 0.8 + 0.2 * math.sin(t * 0.3),
}
```

A steady neon uses `"steady"`; a cyberpunk buzzing sign uses `"buzz"`;
a dying or faulty sign uses `"flicker"`. The profiles are pure and
deterministic given `t`, so they're fully testable. The table is
data-first (extensible without touching `lighting.py` logic).

### Transient overlay effects (Layer B)

Transient light (weapon flashes) joins the overlay layer as `LightGlow`,
alongside `FloatingText` — it does **not** live on `GameMap`:

```python
# pygame_overlay.py — joins FloatingText / ShieldBubble in OverlayFrame
@dataclass(frozen=True)
class LightGlow:
    x: int               # viewport-relative cell x
    y: int               # viewport-relative cell y
    colour: tuple[int, int, int]
    radius: int          # in cells
    age: int             # frame age (0 = spawn)
    lifetime: int        # total frame count

# OverlayFrame gains: glows: tuple[LightGlow, ...] = ()
```

Same consume-on-read per-frame queue as floaters. No `GameMap` field,
no serialization, no per-tick grid recompute.

## The lighting primitive (`lighting.py`)

```python
def propagate_light(
    width: int, height: int,
    sources: Iterable[LightSource],
    *,
    falloff: float = 0.5,
    t: int = 0,
) -> list[list[tuple[int, int, int]]]:
    """Return an additive colour grid from sources at time ``t``.

    Each source's intensity is its base ``intensity`` multiplied by its
    flicker profile at time ``t``. Intensity falls off by ``falloff``
    per cell of Chebyshev distance. Overlapping sources add (clamped to
    255/channel). Pure: no I/O, no mutation, deterministic given ``t``.
    """
```

**Falloff:** Chebyshev distance, linear per-cell `falloff`. Cheap and
readable on 16×16 cells; inverse-square isn't worth the cost here.

### Render integration (Layer A)

```python
# world_render.py
def _tile_render_colors(game_map, x, y, tile, *, t=0) -> tuple[tuple, tuple]:
    fg, bg = _base_colors(game_map, x, y, tile)   # existing fog-dim logic
    light = _light_at(game_map, x, y)
    if light == (0, 0, 0):
        return fg, bg
    return _blend_toward_light(fg, bg, light)

def _light_at(game_map, x, y) -> tuple[int, int, int]:
    if game_map.light_grid is None:
        return (0, 0, 0)
    return game_map.light_grid[y][x]
```

`t` is passed from the runtime adapter's `present()` call. For maps with
no `light_grid`, the path is unchanged (the `None` fallback).

## Animation profiles beyond light (river current)

The same clock + pure-`f(t)` pattern extends to non-light overlays.
A river current is a time-varying overlay on water cells — either a
bitmap tint (shifting the water's `fg`/`bg` along a flow pattern over
time) or a Pygame-drawn motion overlay (arrows/streaks moving
downstream). The design supports both:

- **Bitmap tint:** the river cells' colours shift per-frame based on
  `t` and a flow profile (pure function of cell position + `t`). This
  reads as the water surface rippling. Same seam as neon, different
  profile function.
- **Overlay motion:** `LightGlow`'s sibling — a `MapAnimation` overlay
  effect (moving streaks) drawn on Layer B. Same queue, same clock.

The foundation (clock + pure `f(t)` + the two layers) covers both
without redesign. Phase 5 picks the visual that reads best in playtest.

## Domain seeding cadence

| Domain | When grid is (re)computed | Source types | Perf note |
|---|---|---|---|
| Cities | Each presented frame (cheap — see below) | Static tiles w/ flicker | Flicker needs per-frame recompute, but only over the on-screen viewport and only when sources have non-steady profiles. Steady-only cities skip. |
| Dungeons | On `reveal_around` (player move) | Static tiles + player torch | No flicker in first pass; grid cached between moves. |
| Space | Static cached; transient via overlay | Static (star/drive) on grid + flashes as `LightGlow` | Static recomputed on ship move only; flashes never touch the bitmap grid. |
| Ground combat | Static cached; transient via overlay | Entity lights on grid + flashes as `LightGlow` | Turn-based; flashes are overlay-only. |

**Throttle rule:** a city with all-steady light sources sets a
`_light_static` flag and skips the per-frame recompute entirely (the grid
is cached). A city with any flickering source recomputes, but only over
the visible viewport (not the full 160×100 map). This is the performance
guardrail: never O(n) full-map per frame when the sources are steady, and
viewport-cull when they flicker.

## Save/load contract treatment

| State | Serialized? | Why |
|---|---|---|
| `GameMap.light_grid` | **No** | Derived from tiles + clock; recomputed on load. Matches `visible`/`seen`. |
| `PygameContext._frame_clock` | **No** | Presentation-only; resets to 0 on load. Not game state. |
| `LightGlow` (overlay) | **No** | Transient, overlay-only, never on `GameMap`. |
| Authored light source data (tile kinds, flicker profile keys) | **Yes** (via existing tile/entity serialization) | Already saved as part of the map. |

**Checklist:**
- [ ] `saveload._ctx_to_dict()` and `load_game()` do **not** reference
      `light_grid` or `_frame_clock`.
- [ ] On `load_game()`, the city rebuild path seeds the light grid (so a
      loaded city has neon glow immediately).
- [ ] Sniff test: save in a flickering-neon city → quit → continue → the
      glow is visible immediately; flicker resumes (phase reset is
      imperceptible).

## Pre-implementation audit

### 1. Existing classes / modules to extend or reuse

- **`world.GameMap`** (`world.py:339`) — add `light_grid` field. The
  `seen`/`visible` fields are the precedent for derived, non-serialized
  grid state.
- **`pygame_runtime.PygameContext`** (`pygame_runtime.py`) — add the
  `_frame_clock` field and thread `t` through `present()`. This is the
  one new piece of shared infrastructure.
- **`world_render._tile_render_colors()`** (`world_render.py:54`) — gains
  a `t` param; the bitmap-layer light blend (Layer A) lives here.
- **`world_render._dim_color()`** (`world_render.py:41`) — the existing
  colour-manipulation helper; `_blend_toward_light` follows its shape.
- **`pygame_overlay.OverlayFrame`** (`pygame_overlay.py:103`) — gains
  `glows` field, joining `shields`/`floaters`/`target` (Layer B).
- **`pygame_overlay._draw_floaters()`** (`pygame_overlay.py:699`) — the
  template for `_draw_glows()`: per-frame, consume-on-read, clipped to
  map region, Pygame-blitted.
- **`combat/_animations.py` `_set_floaters`/`active_floaters`** — the
  per-frame queue pattern `LightGlow` will mirror.
- **`dungeon_fov.reveal_around()`** (`dungeon_fov.py`) — the FOV cast
  dungeon lighting hooks into (Phase 4).
- **`data/planets/themes.py`** — neon/beacon tiles already exist; the
  source table reads `tile.kind`, so no new `Tile` fields.
- **`earth_city.py` `_paint_water_and_shore()`** — where the river
  current overlay will hook in (Phase 5).

### 2. Three potential duplication hotspots

- **Per-domain clocks.** If each domain threads its own frame counter,
  that's N copies. The clock must live in one place (`PygameContext`).
- **Per-domain flood loops.** If each domain reimplements "iterate
  sources, paint falloff into a grid," that's four copies of the
  algorithm. One `propagate_light(t)` serves all.
- **Colour-blend arithmetic.** `_blend_toward_light` must live in one
  module (`lighting.py`) and be imported, not copied into the overlay
  or framebuffer.

### 3. DRY strategy

- **One clock** on `PygameContext`, threaded to both layers via
  `present()`.
- **One `lighting.propagate_light(t)`** pure function; every domain
  calls it with its own sources.
- **`_blend_toward_light`** in `lighting.py`, imported everywhere.
- **`collect_light_sources(game_map)`** discovers static tile + entity
  light in one pass; transient `LightGlow` bypasses it (overlay queue).

## Phased implementation plan

### Phase 1 — Animation clock and lighting primitive (the foundation)

- [x] `pygame_runtime.PygameContext`: add `_frame_clock`, advance in
      `present()`, expose via `frame_clock` property.
- [x] `lighting.py`: `LightSource` (with `flicker` profile key),
      `propagate_light(t)` pure function, `FLICKER_PROFILES` table,
      `blend_toward_light`.
- [x] `tests/test_lighting.py`: single/overlapping sources, radius zero,
      falloff edge, empty sources, flicker profile determinism,
      steady = constant, `t` advances intensity, independent flicker.
- [x] `world.GameMap`: add `light_grid` field (default `None`).
- [x] `world_render._tile_render_colors()`: consult `light_grid`, blend
      via `blend_toward_light`, `None` → no-tint fallback.
- [x] Gate: smoke + architecture + Ruff + pytest (1515 tests).

### Phase 2 — City static light (Venus steady neon)

- [ ] `data/planets/themes.py` or new `data/lighting.py`: static-light
      source table (`neon` → pink/cyan, `beacon` → warm gold, radius).
- [ ] `lighting.collect_light_sources(game_map)`: scan tiles by kind.
- [ ] Venus `build_venus_layout()`: seed `light_grid` via
      `propagate_light(collect_light_sources(game_map), t)`.
- [ ] `tests/test_venus_city.py`: neon-adjacent avenue cells carry
      non-zero light; far cells carry zero.
- [ ] Save/load sniff test: lit city survives save/quit/continue.
- [ ] Gate.

### Phase 3 — Venus neon flicker (the cyberpunk signature)

- [ ] Assign `"buzz"`/`"flicker"` profiles to Venus neon sources in data.
- [ ] City render: recompute `light_grid` per frame when sources have
      non-steady profiles (viewport-culled, steady-only shortcut).
- [ ] `tests/test_venus_city.py`: flicker sources vary intensity with
      `t`; steady sources don't.
- [ ] Playtest: the neon reads as buzzing/flickering, not seizure-fast.
- [ ] Gate.

### Phase 4 — Dungeon ambient light and sight extension

- [ ] `dungeon_fov`: after `reveal_around`, call `propagate_light` over
      static dungeon sources (glow fungus, reactor cores).
- [ ] `dungeon_fov.reveal_lit_sources()`: cast short rays from lit cells
      to extend `seen`/`visible` (the gameplay hook).
- [ ] `tests/test_dungeon_fov.py`: lit cell reveals neighbours beyond
      base sight radius; unlit corridor stays dark.
- [ ] Save/load: dungeon light recomputed on `reveal_around` after load.
- [ ] Gate.

### Phase 5 — Earth river current and transient overlay light

- [ ] Earth river: time-varying water tint (bitmap) or `MapAnimation`
      overlay (Layer B) — pick the visual that reads best in playtest.
- [ ] `pygame_overlay.LightGlow` + `OverlayFrame.glows` field.
- [ ] `pygame_overlay._draw_glows()`: radial `BLEND_RGBA_ADD` blit,
      clipped to map region, fading with `age` (mirrors `_draw_floaters`).
- [ ] `combat/_animations.py`: `_set_glows`/`active_glows` queue; combat
      queues a `LightGlow` on weapon fire / explosion.
- [ ] Wire `draw_map_effects` to call `_draw_glows`.
- [ ] `tests/`: river animates with `t`; glow queued/consumed/fades.
- [ ] Gate.

### Phase 6 — Polish and guide

- [ ] `help.py` / `data/guide/`: "Lighting" entry (neon glow, dungeon
      sight extension) and river-current flavour.
- [ ] Performance check: no per-frame full-map pass in space mode; steady
      cities skip recompute.
- [ ] Final gate + city + dungeon playtest.

## Acceptance criteria

- A reusable, pure, tested `propagate_light(t)` primitive that no domain
  reimplements.
- A single animation clock on `PygameContext` threaded to both render
  layers.
- `_tile_render_colors(t)` blends toward light with a `None`-grid fallback
  that preserves today's rendering exactly.
- Venus neon signs visibly tint adjacent avenue cells, with optional
  flicker/buzz profiles that vary with `t`.
- Dungeon light sources extend the player's sight near them (tested).
- Earth river shows a time-varying current animation.
- Space/ground combat weapon fire produces brief coloured light flashes
  via the overlay layer.
- The light grid is never serialized; the frame clock is never serialized.
- `make check` passes with focused regression coverage at each phase.
- No per-frame full-map O(n) pass in space mode; steady-light cities skip.

## Open questions

- **Flicker speed:** what reads as "buzzing" vs. "seizure-inducing"?
  Defer to a playtest in Phase 3; the profile functions are tunable.
- **River visual:** bitmap water tint vs. overlay motion streaks. Defer
  to a Phase 5 playtest A/B.
- **Light through walls:** stop at blockers (match FOV) or leak under
  doors? Propose: stop at blockers, revisit if it reads wrong.
- **Entity light fields:** `light_colour`/`light_radius` fields on
  `Entity`/`OwnedShip` (data-first) vs. inferred from kind. Propose:
  declared fields, seeded from data in Phase 5.
