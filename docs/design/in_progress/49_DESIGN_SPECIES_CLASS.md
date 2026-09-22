# DESIGN: Player species & class identity

**Status: SEED DUMPED 2026-09-22 from the doc 48 roster audit — short
blurb by user request; no phases yet. `/refine-design 49` shapes it.
Nothing settled.**

Companion: `48_DESIGN_ENEMY_POLISH.md` (the roster revamp — this doc's
origin; the two interlock through the faction rep tables).

## The seed (user, 2026-09-22, verbatim)

> A player that has two barely different options for species:
> human/martian and 3 barely different options for class: pirate/
> merchant/bounty hunter.

> Yes, dump a short blurb for doc 49 -- player species/class design.

## Current state (from the 2026-09-22 audit, code-anchored)

- The tables pre-date the repo with a literal "cosmetic only - they
  don't affect gameplay yet" comment (`character.py` @ `976d172`);
  migrated to `data/species/` + `data/classes/` the next day. No
  differentiation doc ever existed.
- **Species:** Human vs Martian = +1 hp and ±2-4 stat/skill points plus
  a small rep table (militia +10 / pirate −10). `SpeciesSpec` has no
  mechanics fields — bonuses only.
- **Class:** stat spreads (pirate: gunnery/strength spikes, 25cr;
  merchant: 75cr + engineering/stamina; bounty hunter: +4 all three
  skills/stats), rep tables, nothing else. No starting-kit field, no
  class-locked gear or abilities.
- **The tell:** the Pirate class's +30 pirate rep starts at −70 — still
  inside the engage band — so even a pirate fights pirates on turn
  one. The class fantasy buys nothing observable at start.
- Doc 07's "species/class combos see different angles and endings" is
  aspiration, not mechanics. SYSTEMS.md absent list: "species beyond
  human/martian, classes beyond pirate/merchant/bounty_hunter".

## First-pass directions (for discussion — nothing settled)

- Unique mechanics per species/class — the missing layer.
- Starting kits and class-locked equipment.
- Deeper rep interlock with doc 48's faction matrix (doc 48 SETTLED 3
  makes ground aggression faction-based, so class rep tables become
  load-bearing there).
- Whether more species/classes come now or the existing five deepen
  first.

## Open questions (for `/refine-design 49`)

1. What SHOULD a species mean — biology (stat/skill identity), origin
   (rep/faction standing), or both?
2. What should a class mean — profession (kit + missions + rep) or
   archetype (stats), and how far from each other?
3. Does pirate-class kinship need to be real (cross a hostility
   threshold at start, or a path to it)?
4. Are five options enough for launch, or does the roster revamp's
   faction matrix imply more (e.g. consortium-adjacent classes)?
5. Starting kits / class-locked gear — in scope here or with trade?
