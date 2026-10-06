# DESIGN: Cybernetics — the Chrome Pass

**Status: DESIGN IN PROGRESS — the skeleton is ruled (2026-10-06,
with the user, end to end); numbers, curves, and the tier catalog
are this doc's own audit passes. No implementation until the user
explicitly requests it.**

Companions: `in_progress/39_DESIGN_ACT1_BLOCKADE.md` (Branch D's
chrome trail is GATED on this pass — "who makes the chrome?" needs
an answer worth hunting); `in_progress/42_DESIGN_LORE_RUMOR.md`
(the rumor economy chrome reprices); `complete/47*` quality/tinker
(chrome's relationship to kits, below); doc 101 (the Venus tower —
the makers' headquarters).

## The problem (measured, 2026-10-06)

The four placeholder pieces (`cybernetic_eyes/_torso/_arms/_legs`
in `data/ground_armor/vests.py`) are armor-slot stat-sticks, and
the DR math dominates them at every tier:

- body is the worst: Cybernetic Torso trades 4 flat DR per hit
  (Heavy Vest 5 vs 1) for +3 max HP;
- arms: −2 DR/hit for +2 melee on your hits; legs: −3 DR/hit for
  +1 AP; eyes: 0 DR at 260cr (+8 hit) — the only competitive line;
- feet has no chrome at all; one option per slot elsewhere;
- quality/tinker scaling (100/115/130/145/220, ceiling) moves the
  small fields once then flat-lines (`melee_bonus 2`→3 forever;
  `ap_bonus 1`→2 forever) while five armor slots climb ~+1/step
  each — the domination WIDENS with investment.

User verdict: placeholders. Underpowered, don't scale with tinker,
one per slot, dominated by armor #.

## Identity and doctrines (ruled)

- **Chrome = the discrete-effect class.** Armor = passive flat DR;
  modules = the ship's gear; chrome = YOU (marine and pilot). Each
  piece does a THING; no piece is a stat-bump wearing a sci-fi
  name. Zero/near-zero defense on chrome is CORRECT (cross-axis
  cost doctrine) — what was missing was a payoff DR can't
  replicate.
- **Chrome extends a stat the body already has.** The bay's skill
  key is automatic, not arbitrary: chrome is the artificial
  version of a stat, sold by the Consortium.
- **Combat doctrine: chrome ENHANCES combat, always.** No stat
  debuff, no dodge dimming, no combat-axis consequence of low ego
  (user: "chrome is supposed to enhance your combat ability").
  Every consequence lives in the socioeconomic layer.
- **The recorded endgame (user, verbatim intent):** develop a
  debuff system that is robust and extensible, and chrome then
  trades combat advantages for certain risky disadvantages —
  opt-in risk pricing power, never shrinking the effect.
- **Stats gate WHAT (tier reqs); ego gates HOW MUCH (one global
  pool).** No skill becomes "the chrome stat."
- **Scarcity balances power** (Consortium product, priced like
  the surgery it is).
- **Chrome does not tinker** (proposed, unobjected — confirm at
  the numbers pass): implants aren't user-serviceable, the
  Consortium seals them; the ladder lives in catalog tiers, which
  sidesteps the dead-scaling problem instead of patching it.

## Anatomy — six bays, one per skill (ruled)

Every skill on the character ledger gets exactly one bay:

| Bay | Skill | Layer | Extends | Effects, teach → top |
|---|---|---|---|---|
| Ocular | gunnery* | space | the aiming eye | +hit rider → lock/band effects, missile-guidance / flak-focus interactions |
| Pilot jack | piloting | space | the wire to the ship | AP/dodge rider → evasion and AP-economy effects |
| Systems spine | engineering | space | the power instinct | max-power/regen riders → discrete power-and-shield effects |
| Vital | stamina | ground | the body | +HP rider → once-per-fight stabilization, wound/bleed immunity |
| Arms | strength | ground | the melee muscle | +melee rider → AP-on-kill, reach/dance interactions |
| Legs | reflexes | ground | the stride | +1 AP (the legacy model — already the right KIND of effect) → disengage, move-cost cuts |

*Ocular key is the one flagged call: gunnery (space aim, tabled)
vs reflexes (ground aim); a both-layers aim-rider ocular is the
alternative teaching piece. Decide at the numbers pass.

Legacy mapping: eyes→Ocular, torso→Vital, arms→Arms, legs→Legs.
No feet placeholder; no sixth bay in v1.

Fiction: they don't sell you a better ship — they sell you a
better pilot. The jack is the marquee product.

## The ego economy (ruled)

- **The stat's name is EGO (ruled 2026-10-06):** keep it — other
  systems reach for humanity or empathy; ego is unique, and it is
  literally the sense of self being spent.
- **Ego is the single global pool** every bay draws on.
  Level-fed max (formula = numbers pass) — growth buys chrome
  room, which delivers the accessibility curve organically: fresh
  character, teach-tier room; late game, six-shallow or
  two-or-three-deep.
- **Installing claims capacity AND burns ego.** The claim occupies
  room; the burn is permanent.
- **The burn is the HIGH-WATER MARK of total installed cost ever
  worn** (user's worked example, verbatim semantics: install −4 →
  max ego −4 permanently; remove → still −4; replace with a −2 →
  still −4). Swapping within your historical peak costs nothing
  new; exceeding it burns the difference. Swaps are priced by the
  ratchet itself — no separate fee mechanic.
- **Uninstall frees the claim, never the burn.** Capacity
  recycles; the stat does not recover.
- **Threshold consequences read BURN, not current load** — a
  stripped-clean character with a deep history still suffers.
- Skill reqs per bay gate tiers ("military-grade jack: Piloting
  16") — build affinity lives here, not in budgets.

## Acquisition and the scarcity ladder (ruled)

- **Tier 1 teach tier:** cheap, shop-common, small discrete
  effects, installable anywhere. Doubles as Act 1's chrome-trail
  surface — the player already OWNS chrome when Branch D asks who
  makes it.
- **Higher tiers:** Consortium-scarce, Venus-centric, skill-gated,
  priced like surgery.
- **The surgery loop:** at low ego, legitimate doctors stop
  operating — no lawful station installs NEW chrome on someone
  already too deep. Remaining surgeons are fringe and corpo (and,
  eventually, Venus). The deeper you go, the further you travel to
  go deeper — a consequence that pushes toward the map's edges.

## Consequences — socioeconomic only (ruled)

One ego-read (burnt points); per-faction and per-planet valences
translate it into multipliers:

- **Faction rep gain multipliers:** pirate/Consortium easier,
  merchant/militia harder. Labs: NEUTRAL (assumed — correct if
  wrong). Positive and negative per faction.
- **Buy prices rise** on non-pirate/non-corpo vendors;
  **sell offers drop** on non-pirate/non-corpo planets.
- **Services ride the same multiplier:** repairs, refits,
  restock, medical, docking — one ruling, the whole service
  counter.
- **Rumor costs scale with low ego** (dealer prices under the same
  multiplier — covered by the price ruling, ZERO new prose).
  Rumor POOL shifts are parked (prose cost — delicate, depends on
  volume of new good writing).
- **Board valences:** per-planet like/dislike of chromed psychos
  shifts BOTH the tier bands that post (high-tier work is trust
  work; pirate t3+ posts only to psychos) AND the row count.
- **The dead zone:** the first band of burn costs nothing
  anywhere — prices, rep, boards untouched. The teaching tier must
  be consequence-free or the system teaches avoidance.
- **Zero ego / full psycho:** a Consortium comms contact
  introduces itself; the line is exposed on the F screen. An
  intro, nothing more — corpo detail later. This gives the
  Consortium two reveal doors (doc 39's tower raid = force; the
  ego floor = courtship) — nothing exclusive, two rhyming paths.
- **Emergent, never keyed:** the blockade methods self-select by
  ego drift (low ego → Whisper/ghost feel natural; high ego →
  papers feel natural). No method requires or reads chrome.

**Explicitly rejected:** combat stat consequences of low ego, AND
forced hostility (lawful-space guards auto-attacking deep-burn
characters — floated, declined: the rep multipliers ARE the whole
of the lawful-world response). The world reprices you; it does not
dim your aim and does not open fire.

## Migration and audit rules

- The four placeholder armor entries retire; live saves need an
  unwear-and-refund (or grandfather) migration row — mechanism
  decided at build.
- **Domination audit vs armor** per slot/tier before numbers land
  (the parts-ladder standard: same-cell-stack check; the
  placeholder sin is the documented counterexample).
- **Module-boundary audit:** modules upgrade the ship, chrome
  upgrades you. Riders read like the skill (small, personal), never
  like module rows (`gunnery_bonus` etc. is module vocabulary).
- **Dead-zone guard** gets a pin: light installs change no price,
  no rep rate, no board.
- No chrome piece may be required by any Act 1 method.

## Parked (each with its reason and future home)

- **Disruption/EMP, piece suppression, stagger, willpower — the
  debuff system's doc** (not written yet; its own serious pass).
  Inheritable sketch from this conversation: a general statuses
  container (`id → rounds remaining`) shipping one entry; one
  severity seam function re-keyable from burnt ego through
  willpower later; disruption as one weapon flag growing into a
  damage-type family. The user's plan: robust and extensible, and
  chrome trades combat advantages for opt-in risky disadvantages
  there.
- **Rumor pool shifts** — prose volume (user: "delicate and
  heavily relies on me being able to write a lot of new good
  prose").
- **Dermal sixth bay** (flat-DR-as-flesh) — not ruled in.
- **Escalating width tax** (each additional bay costs more
  tolerance) — v2 spice.
- **Permanent-stat-loss surcharge** ("the metal eats flesh": top
  tier chrome claiming stamina points, −½ max HP each) — a very
  Consortium future move.
- **Mandated-action cyberpsychosis** (the machine lunges when you
  meant to aim) — zero-band spice, debuff-doc territory.
- **Engineering cross-domain neural bay** — arrived instead as
  architecture (the spine); the over-spec version returns as
  content someday.

## Open items (the numbers pass)

1. Ego max formula; per-tier install costs and burns; multiplier
   curves; board valence bands; tier reqs per skill.
2. The tier-one teach catalog (both layers — an ocular/jack piece
   a pilot meets, a vital/legs piece a marine meets).
3. Ocular key: gunnery vs reflexes vs both-layers rider.
4. Labs valence confirm (neutral assumed).
5. Chrome-vs-tinker confirm (does not tinker, assumed).
6. Migration mechanism for the four placeholders.

## Phases

- [x] Skeleton ruled end to end (2026-10-06, this doc)
- [ ] The numbers pass: formulas, curves, tier reqs
- [ ] The tier catalog + audit instruments (domination, module
      boundary, dead-zone pins)
- [ ] Implementation briefs (advisor pass per house rule)
- [ ] Prose pass (descriptions, vendor/surgery flavor, the
      Consortium voice)
