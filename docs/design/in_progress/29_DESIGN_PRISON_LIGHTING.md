# DESIGN: Prison Facility Lighting

## Overview

The alien prison's panels tell the facility's story through light:

- **Descent (F1 → deep):** power rises from 0 toward normal. F1 starts
  dark; the `security_alpha` / `security_beta` activation events bump
  it; deeper floors are progressively more powered.
- **The console:** downloading the data (`prison_data_extracted`) is
  the payoff moment — the ENTIRE prison immediately caps out into
  full alarm: flashing reds, blinking, everywhere.
- **Ascent:** lights stay at maximum alarm (the *threat* escalates per
  floor via the existing ascent events; the lighting is already maxed
  and stays there).

Two user rulings (2026-09-02):

1. Console download → max alarm everywhere, immediately. No gradual
   per-floor light escalation on ascent.
2. Skipping an F1 power event does not stall the wake-up: entering F2
   implies the facility powered up just the same. Power follows
   maximum progress, not strict event sequence.

## Philosophy alignment

| Repo principle | How this applies |
|---|---|
| Data-first | Panel kinds + light specs + phase table are frozen data; no per-instance state |
| Table over conditionals | `(phase, floor) → panel kind` is one frozen lookup, never an if-chain |
| Pure computation / explicit mutation | `_facility_phase()` is pure over persisted flags; `refresh_prison_panels()` is the sole mutator |
| Save/load sacred | Phase is DERIVED from already-persisted extension state (`activated_events`, `state_flags`); panel kinds serialize with dungeon tiles; refresh after load is idempotent |
| Gates beat playtests | Every pure function and the mutator ship pytest'd in the same commit |

## Light source: panel tiles, three states + alarm

Panels are floor-standing fixtures scattered at generation like glow
fungus (walkable, so lit panels extend sight; the opaque-emitter rule
doesn't bite). CP437-safe glyphs only.

| Kind | In light table? | Spec | Narrative |
|---|---|---|---|
| `prison_panel_off` | no | — | dormant: "terminals dot the floor, dark and silent" |
| `prison_panel_dim` | yes | radius 2, intensity 0.35, `pulse`, amber | emergency trickle (post-alpha) |
| `prison_panel_mid` | yes | radius 3, intensity 0.6, `pulse`, warm white | systems rising (post-beta, F2 entry) |
| `prison_panel_normal` | yes | radius 5, intensity 0.9, `steady`, cool teal | mains on (deep floors) |
| `prison_panel_alarm` | yes | radius 5, intensity 1.0, `alarm` (NEW profile), red | lockdown: flashing, blinking |

New flicker profile `alarm` in `FLICKER_PROFILES`: a hard strobe —
sharp multiplier swings (≈0.3↔1.0) on a ~4-frame cadence, keyed by
position so panels blink out of phase. This is the "flashing reds,
blinking" ruling made mechanical.

## Phase model (derived, never stored)

```python
def _facility_phase(state, floor: int) -> str:
    """Pure: 'dormant' | 'waking' | 'rising' | 'lockdown'."""
```

- `prison_data_extracted` in `state.state_flags` → `lockdown` (ALL
  floors, no per-floor variation).
- else `security_beta` in `state.activated_events` → `rising`.
- else `security_alpha` … → `waking`.
- else `dormant`.

Skip rule (ruling 2): entering floor N ≥ 2 counts as at least
`rising`, regardless of which F1 events fired. Encoded in the table
below, not in the phase function.

### Panel state table (frozen data)

| Phase | F1 | F2 | F3 | F4 (deep) |
|---|---|---|---|---|
| dormant | off | off | off | off |
| waking | dim | off | off | off |
| rising | mid | mid | mid | normal |
| lockdown | alarm | alarm | alarm | alarm |

(Exact floor count read from the extension spec at implementation;
table generalized as `{phase: {floor: kind}}` with a default.)

## Domain changes

| File | Change |
|---|---|
| `world.py` | 5 panel Tile constants |
| `lighting.py` | `alarm` flicker profile |
| `data/lighting.py` | 4 STATIC_LIGHT_TABLE rows |
| `dungeon_bsp.py` | parameterize the fungus scatter pass (density + kind) so prison floors scatter panels; prison floors generate `prison_panel_off` |
| `dungeon_extensions.py` | `_facility_phase()` (pure), `refresh_prison_panels()` (mutator), hooks: floor generation, `_fire_activation_event` (alpha/beta/console), floor-entry transitions, post-load |
| extension spec data | `panel_density` per floor (0 for non-prison floors) |
| serialization | none new — kinds ride the existing dungeon tile encoding; phase derives on load |

## Pre-implementation audit

**Reuse:**
- glow-fungus scatter in `dungeon_bsp.py` — parameterize, don't copy.
- `STATIC_LIGHT_TABLE` + `FLICKER_PROFILES` — rows/profile only.
- `_fire_activation_event` (`dungeon_extensions.py`) — the single
  dispatch point; `power_restored` (engineering console, lines ~603)
  is the precedent for event → state + map mutation.
- `_seed_dungeon_light_grid` + per-frame recompute — already
  fog-aware and animated (alien-door work).
- `state.activated_events` / `state.state_flags` — persisted; phase
  needs NO new saved state.

**Duplication hotspots:**
1. Copying the fungus placement loop instead of parameterizing it.
2. Phase logic leaking into event handlers instead of one pure
   function + table.
3. Refresh calls sprinkled at call sites instead of exactly three
   chokepoints (floor generation, phase change, post-load).

**DRY strategy:** parameterized scatter; single frozen table; single
mutator invoked from the three chokepoints only.

## Playtest findings (2026-09-02, session 2)

- Combat froze ambient animations — the light recompute lived only in
  the explore render path. Fixed: shared `recompute_frame_light(ctx,
  map)` in `lighting.py`, called by both `_render_active_map` and the
  ground-combat world render. Flicker/pulse/strobe now animate during
  fights.

## Phased implementation

### Phase 1 — vocabulary — COMPLETE 2026-09-02
- [x] 5 panel Tile constants (CP437-safe glyphs)
- [x] `alarm` flicker profile + 4 light-table rows
- [x] tests: table entries, alarm profile swings and varies with t/position

PLAYTEST: none (data only); `make check`.

### Phase 2 — scatter — COMPLETE 2026-09-02
- [x] Panel scatter pass in `populate_dungeon` (`_scatter_panels`,
      `_floor_cells` eligibility; isolated seeded RNG so the shared
      stream is untouched — seeded descents are byte-identical)
- [x] Prison floors generate `prison_panel_off` at density 0.02
- [x] Fungus opt-out (`DungeonParams.scatter_fungus`): prison floors
      carry NO ambient green — panels are the only light story
- [x] tests: panels present on every prison floor, absent elsewhere;
      all-off floors produce no light grid (dark start holds)

PLAYTEST: see session checklist — dark start confirmed pending user.

### Phase 3 — wake-up (descent) — COMPLETE 2026-09-02
- [x] `_facility_phase()` pure fn + `_PANEL_STATES`/`_PANEL_DEFAULTS`
- [x] `refresh_prison_panels()` mutator (kind rewrite + cache
      invalidation; per-step FOV reveal reseeds)
- [x] Hooks: alpha/beta (event firing), generation (phase-gated),
      every floor entry (skip rule + post-load reconciliation)
- [x] tests: phase derivation, skip rule, per-floor kinds, idempotent
      refresh, phase-gated generation (dormant F2 wakes to mid;
      lockdown floor alarms with active security)

PLAYTEST: pending user (session checklist v2).

### Phase 4 — lockdown (console)
- [x] `prison_data_extracted` → refresh every cached floor + current
- [x] tests: extract flips all floors to `prison_panel_alarm`; grid
      animates (alarm profile varies with frame clock); save/quit/
      continue preserves alarm everywhere

PLAYTEST: download at the console — red strobe everywhere instantly;
save/quit/continue — still strobing; ascend — every floor maxed,
threat (not light) escalates via existing ascent events.

### Phase 5 — closeout
- [x] Guide check (visual-only feature; no guide change expected)
- [x] Full corpus audit + `make check`
- [ ] Ask user: move doc to complete?

## Acceptance criteria

- F1 starts with zero light grid (true dark) before any event.
- alpha → F1 dim pulse; beta → F1/F2 mid, deep floors normal.
- Entering F2 without beta lights F2 at mid (skip rule).
- Console → every floor `prison_panel_alarm`, strobing, immediately.
- Save/load preserves the exact visual state on every floor.
- No new persisted state; phase derived; refresh idempotent.
- `make check` green throughout.

## Open questions

- Panel density: match fungus (~4%) or sparser (~2%, prison reads
  barer)? Default 2%, tweak in playtest.
- Should `alarm` panels also tint the HUD/log red during lockdown?
  (Out of scope here; note for a future pass.)
