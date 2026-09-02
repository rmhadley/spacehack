# DESIGN: Prison Descent Polish

## Overview

A feel pass over F1–F5 evaluated against the narrative spine:

> Signal → Mars cave door → ancient prison waking as you descend →
> escalating containment levels → the deep elevator → abyss bridge →
> the broken special cell → download → gauntlet escape.

**Verdict by beat:**

| Beat | State | Verdict |
|---|---|---|
| Signal → cave → alien door | landmark + pulse light + console | DONE (polished this session) |
| Prison wakes as you descend | panels + dormant security + phases | DONE (docs 29/30) |
| Containment escalation F1→F4 | sprinkle stampers only | **WEAK — the core gap** |
| Elevator = going DEEP | instant floor transition | **WEAK — no descent feel** |
| Abyss → bridge → broken cell → claw marks → terminal | `alien_prison_deep_cell` layout | GOOD bones; minor polish |
| Download → gauntlet → escape | lockdown + ascent events | DONE |

## Findings (what's weak, specifically)

1. **F1–F4 read as samey caves.** Each floor's "theme" is 3–10
   single-tile markers sprinkled by `_stamp_features` (cell doors,
   barriers, nodes). No authored structures — no cell BLOCKS, no
   containment architecture. F1 has no theme at all. Floor names are
   flat ("Alien Prison F1"), and F2–F4 have no entry flavor.
2. **The deep elevator is a teleport.** The `deep_elevator`
   interaction jumps F4→F5 with the same transition as any stair —
   nothing communicates "you are going FAR down."
3. **Text beats that are now visually true should say so.**
   alpha/beta narrate "panels brighten" — that's real now; entry
   flavors can carry the escalation arc.

## Phases

### Phase A — identity & text (data only, high value)
- [x] Floor names carry containment tiers: F1 "Intake Level",
      F2 "Prisoner Quarters", F3 "Defensive Layer", F4 "High-Risk
      Containment", F5 "The Deep Cell"
- [x] Entry flavors for F2/F3/F4 (only F1/F5 have them), each
      escalating: quarters ("rows of cells... doors torn open"),
      defensive layer ("the architecture itself turns hostile"),
      high-risk ("built for things larger than the cells below")
- [x] Small event-text pass: alpha/beta/ascent lines reference the
      waking light and dormant frames becoming active (now true)

PLAYTEST: v1 checklist delivered 2026-09-02. (Phase A also surfaced a
latent headless crash — the shared menu unpacked a dummy surface size
as a raw ValueError; it now raises PygameMenuUnavailable, and the
phase-two saveload test patches the popup like its siblings.)

### Phase B — cell-block landmarks (the feel win)
Authored multi-tile stamps per tier, using the existing
`landmark_variants` machinery (deep-cell precedent):
- [ ] `prison_intake_block.layout` — holding pens + carrier rails
      (the sentries' "ceiling rails" made physical), F1, 1–2 variants
- [ ] `prison_cell_block.layout` — a row/arc of barred cells with
      doors ajar, F2, 2 variants (intact / breached)
- [ ] `prison_checkpoint.layout` — barrier line + security nodes
      crossing a corridor, F3
- [ ] `prison_high_risk_block.layout` — oversized cells, heavy doors,
      F4, 1–2 variants
- [ ] Wire via `ExtensionFloorSpec.landmark_variants`; keep the
      sprinkle stampers as filler between structures; stairs/panels/
      dormant placement all already landmark-aware (footprint
      exclusions landed in doc 30)

PLAYTEST: each floor should be identifiable from one screenshot.

### Phase C — the descent interstitial
- [ ] `deep_elevator` transition plays a short full-screen descent:
      dark frame, depth counter ticking down (−0.4 km … −2.1 km),
      2–3 text beats ("The cables hum. The dark rises."), then the F5
      entry flavor — built on the shared modal frame machinery
      (`pygame_screen`/story screens), skippable with a key
- [ ] Log line on arrival carries the depth ("You are 2 km beneath
      the Martian dust.")

PLAYTEST: the elevator should feel like the longest moment of the
descent.

### Phase D — deep-cell micro-polish
- [ ] Terminal landing emits faint light (light-table row) so the
      bridge approach reads as "one light still answers"
- [ ] Evaluate in playtest: bridge edge glow, claw-scar color pop —
      only if the abyss reads flat

PLAYTEST: the F5 arrival frame should be screenshot-worthy.

### Phase E — closeout
- [ ] Full descent playtest A–D
- [ ] Guide check (names/flavor only — no mechanic changes expected)
- [ ] Corpus audit + `make check`; ask user: move doc to complete?

## Acceptance criteria

- Every floor's name, flavor, and geometry agree on its containment
  tier; escalation is legible without reading design docs.
- The elevator moment communicates depth.
- No regression to placement invariants (dormant/panels/stairs) —
  all landmark additions respect the existing footprint exclusions.
- `make check` green throughout.

## Open questions

- Phase B variant counts (1 vs 2 per floor) — start at 2 where
  variety is cheap, cut what doesn't read.
- Descent interstitial length — target ~2–3 s, skippable.
