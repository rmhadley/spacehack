# DESIGN: Enemy polish — difficulty-scaled enemies

**Status: DESIGN IN PROGRESS — no implementation until the user
explicitly requests it.** Dumped 2026-09-20 from the user's seed;
nothing below is settled — open questions feed `/refine-design 48`.

Companions: `47_DESIGN_LOOT.md` (the kit-drop + quality systems this
doc builds on — phases 1-2 landed); `SYSTEMS.md` "Ground combat" /
"Kill drops" / "RNG delve sites" entries; the stored behavior-tactics
ruling (tactics come from behavior×attack×terrain combos, not stats).

## The seed (user, 2026-09-20, verbatim)

> Alright, before we refine phase 3, let's dump a new design doc:
> enemy polish. we need better enemies that scale with difficulty.
> If I'm in a t4 delve, I should be going against pirates with
> monoblades and rocket launchers.

## Seed addendum — ship-side loadouts (user, 2026-09-20, verbatim)

From the doc 47.3 refinement (SETTLED 17 there): themed ship
loadouts are wanted and live HERE. Space-side LOADOUT authoring
joins this doc's territory; space AI behavior stays out (doc-34
seed, unchanged — see G).

> I agree with you that we need more detailed ship specs that
> have modules installed that make sense for them and their hull.
> Capturing a pirate ship would definitely be a solid path to
> finding a smugglers hold. Capturing a merchant would be a solid
> path to finding a cargo hold.

Grounding: no NPC ship spec flies a smuggler hold today (the only
catalog-adjacent reference is wolf_b's fixed mechanic stock); the
47.3 capture strip drops whatever the spec flies at fly-time
quality, so authored themed modules become capturable loot with
zero new mechanics — this doc just decides the authoring shape
(which hulls fly what, and whether band scaling applies
ship-side). Joins the open-question pass below.

## Current state — the audit (2026-09-20, code-anchored)

**How enemies scale today: by spec swap, not by loadout.**

- The humanoid fighters are ~8 `NpcCharSpec` rows
  (`data/npc_chars/core.py`), and every one of them wields
  tier-1 gear regardless of the spec's own tier field: pirate
  raiders/enforcers/militia pick from `(combat_knife,
  kinetic_pistol)`, consortium gunners and pirate riflemen carry a
  fixed `kinetic_pistol` — the rifleman is a **tier-2 spec with a
  t1 weapon and no rifle**.
- Site difficulty picks WHICH specs spawn: `data/digs.TIER_POOLS`
  bands 1-3 (raider/drone → rifleman/enforcer → rifleman/enforcer/
  parasite) plus a density scalar. `_site_tier` clamps
  `mission_tier` to 3 — and six planets are `mission_tier=4`, so
  **the t4 delve the user describes currently runs the tier-3
  pool**. Floors do climb (`_dig_tier` = tier + floor - 1, clamped
  the same way), so deep floors of low-tier planets top out at 3
  too. The band-4 the seed asks for does not exist.
- `NpcCharSpec.tier` gates DROPS only (`tier_filtered_equipment`:
  equipment pool entries filter to `tech_level <= tier`); it never
  touches the wielded weapon.
- Catalogs already carry the full ladder: shop weapons band t1-t4
  (t4 = rocket launcher, mono blade, power fist, plasma caster,
  railgun, ion blaster), armor to t4 (assault helmet, powered
  vest…). Nothing new needs authoring for gear to scale INTO.
- Doc 47 wired the diegetic consequences: the wielded weapon
  always drops (47.1 kit drops) and rolls quality at NPC equip
  time with site-independent KILL rates (47.2). Scaled loadouts
  therefore scale loot automatically — the economies are one
  system now.
- Stats (`hp`, `reflexes`, `strength`, `armor`) are per-spec
  authored constants; scaling them is a separate axis from
  loadouts.
- Authored-layout `ENEMY:` markers pin fixed spec ids — hand-tuned
  interiors (wrecks, mission dungeons) don't route through any
  band.

**The warts:**

1. Difficulty is invisible in the enemy's hands — a t4 planet's
   delve fight looks identical to a t1's, then ends faster.
2. The t4 equipment band exists but almost nothing in the world
   wields it; the player's own t4 gear has no mirror.
3. The guide (newly landed, user-approved) already PROMISES
   "deeper sites and tougher machines yield better gear" — today
   that's only true via spec swap + drop-tier gates.
4. `pirate_rifleman` breaks its own name: tier-2 rifleman, t1
   pistol.

## First-pass shape (for review — nothing settled)

### A. Loadout scaling — the headline

A site-band → gear-band mapping so high-tier sites field high-tier
kit. Candidate mechanisms (open question 1):

- **(a) Uniform band filter** — every weaponed spec's
  `weapon_pick` resolves at spawn against the site band
  (`tech_level <= band`, biased toward the band's top). One rule,
  every spec, no per-spec tables; the favorite per the
  no-special-cases ruling. Fixed `weapons=` lists are
  characterization vs scalably-wrong — open question 4.
- **(b) Per-spec tier-indexed picks** — each spec authors
  pick-lists per band (raider t1: knife/pistol; raider t4:
  mono blade/rocket launcher). Most control, most authoring,
  drifts toward special cases.
- **(c) New high-tier specs** — a veteran/heavy row per faction
  (the "t4 pirate" as its own statblock). Overlaps with the
  behavior-matrix phase below.

### B. The band-4 itself

Extend `TIER_POOLS` to a fourth band (which specs, what density)
and unclamp `_site_tier` — t4 planets and deep floors reach it.
Band vocabulary question: `mission_tier` 1-4 vs equipment
`tech_level` 1-4 vs dig bands 1-3 are three overlapping ladders;
this doc should settle ONE mapping.

### C. Stat scaling — separate axis, separate ruling

Do hp/reflexes/armor scale with band too, or do the same bodies
just carry better gear (deadlier via loadout + quality, not
bigger numbers)? The seed's framing is loadout-only.

### D. Quality interplay (47.2)

High bands could roll better quality FLOORS (e.g. the site band
shifts the equip-time KILL ladder from 1-in-5/11/25 toward
1-in-3/7/15). "Deeper sites yield better gear" becomes true on
both axes.

### E. Economy watch-items

Kit drops mean t4 pirates drop t4 weapons — intended, but the
power curve needs a playtest look: free mono blades vs armory
prices, XP vs risk, whether delve income still tracks the 47.2
watch-item ("bottom-runs must not out-earn their risk").

### F. Behavior/tactics — the matrix axis (companion, its own phase)

Stored ruling: tactics come from behavior×attack×terrain combos;
open cells include ambusher+ranged, zone-guard, slow-heavy
hunter. A band-4 "pirate heavy" (slow hunter, rocket launcher)
fills the slow-heavy cell AND gives the t4 band a face. New spec
names are PROSE GATE.

### G. Scope boundary

Space-side AI behavior is OUT (the space behavior-matrix
proposal is its own pending decision, doc-34 seed) — but
ship-side LOADOUT authoring is IN per the seed addendum above
(user, 2026-09-20): themed installed modules per hull. Authored-
layout `ENEMY:` markers are hand-tuned and presumably stay
fixed — open question 7 confirms.

## Philosophy alignment

| Guardrail | How this doc obeys it |
|-----------|----------------------|
| No special cases — uniform mechanisms | Band filter over per-spec exception tables (mechanism a) if ruled |
| Data-first | Bands, picks, densities live in `data/npc_chars` + `data/digs` specs; no code dicts |
| Knowledge gates access, not existence | Gear exists in catalogs; bands gate who WIELDS it |
| Diegetic economy (47.1/47.2) | Scaled loadouts drop scaled loot through the existing kit-drop path |
| Prose gate | New spec names / any new strings land only post-approval |
| No prose without discussion | This dump is chat-first; data strings settle at refine |

## Open questions (for `/refine-design 48`)

1. **Mechanism:** uniform band filter (a), per-spec tier tables
   (b), new specs (c), or a mix (e.g. (a) + a few (c) faces)?
2. **Band-4 faces:** does t4 reuse existing specs with better
   gear, add veteran/heavy rows, or both?
3. **Stats:** do hp/reflexes/armor scale with band, or loadouts
   only?
4. **Fixed `weapons=` lists** (gunner's pistol, rifleman's…):
   scaled by band or respected as characterization?
5. **Quality floors by band** (D): in scope here or deferred to a
   47 tune pass?
6. **Monsters** (organic specs): flat forever, or bigger-fauna
   variants per band (new rows, prose-gated names)?
7. **Scope of "site":** RNG delves only, or also procgen
   dungeons/city sewers? Authored interiors stay fixed?
8. **Bystanders/civilians:** exempt from scaling (presumably yes)?
9. **Phasing:** what splits into separate implement+playtest
   cycles (candidate: band+loadouts → stats/quality → new specs)?

## Phases (DRAFT — refined after the open-question pass)

- [ ] 1. **Band 4 + loadout scaling** — `TIER_POOLS` t4 band,
  `_site_tier` unclamped, site-band loadout resolution per the
  ruled mechanism, kit-drop/quality interplay verified, economy
  watch pass.
- [ ] 2. **Stat and/or quality scaling** (if ruled in) — band-
  scaled stats and/or quality floors, power-curve check.
- [ ] 3. **New high-tier specs** — behavior-matrix cells filled
  (pirate heavy etc.), PROSE GATE on names, band pools refreshed.

## PLAYTEST — phase 1 (DRAFT; concretized at brief time)

1. A tier-4 planet's delve: pirates wield band-appropriate gear
   (mono blades, rocket launchers at the top), visibly different
   from a t1 planet's delve.
2. Deep floors of lower-tier planets climb toward the same band.
3. Corpse drops mirror the new loadouts (diegetic kit, 47.1).
4. Regression: t1 sites unchanged; authored interiors unchanged;
   monsters unchanged (unless ruled); save/load clean.

## Acceptance criteria (DRAFT)

- Site difficulty reads in the enemy's hands before the first
  punch lands.
- One uniform mechanism, no per-spec special cases (or per-spec
  authoring ruled explicitly over it).
- The full t1-t4 equipment catalog is mirrored by something in
  the world that wields it.
- The 47.x loot systems absorb the change with no new payload
  shapes.
