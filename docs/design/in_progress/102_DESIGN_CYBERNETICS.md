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
- **Bays are worn alongside armor, never instead of it** (made
  explicit 2026-10-06; implied until then by zero-DR-is-correct
  and placeholder retirement): chrome occupies no armor slot and
  never competes with one. The cost axis is ego, credits, and
  consequences — the armor-slot competition the placeholders
  suffered is removed by design.
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
- **Chrome does not tinker** (ruled 2026-10-06): implants aren't
  user-serviceable, the Consortium seals them; the ladder lives in
  catalog tiers, which sidesteps the dead-scaling problem instead
  of patching it.

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

*Ocular keys GUNNERY (ruled 2026-10-06, numbers pass): space aim;
one bay per skill, 3 space / 3 ground. Reflexes (ground aim) and
the both-layers aim rider were considered and declined.

Legacy mapping: eyes→Ocular, torso→Vital, arms→Arms, legs→Legs.
No feet placeholder; no sixth bay in v1.

Fiction: they don't sell you a better ship — they sell you a
better pilot. The jack is the marquee product.

## The ego economy (ruled)

- **The stat's name is EGO (ruled 2026-10-06):** keep it — other
  systems reach for humanity or empathy; ego is unique, and it is
  literally the sense of self being spent.
- **Ego is the single global pool** every bay draws on.
  Level-fed max: `6 + (level - 1) // 3` (ruled 2026-10-06,
  SETTLED 2) — pool 6 at L1, 15 at L30, 25 at L60. Growth buys
  chrome room, which delivers the accessibility curve
  organically: fresh character, teach-tier room; late game,
  six-shallow or two-or-three-deep. No species or class
  modifiers: level-fed only, nothing becomes the chrome stat.
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
- Skill reqs per bay gate tiers on the 0-100 skill scale — t1
  none, t2 25, t3 50, t4 75 (ruled 2026-10-06):
  "military-grade jack: Piloting 75." Build affinity lives here,
  not in budgets.

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
  merchant/militia harder. Labs: NEUTRAL (ruled 2026-10-06).
  Positive and negative per faction.
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
- **The dead zone:** burn <= 3 costs nothing anywhere — prices,
  rep, boards untouched (ruled 2026-10-06: width 3, lifetime —
  three teach pieces free, the fourth point of burn enters band
  1). The teaching tier must be consequence-free or the system
  teaches avoidance.
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

## SETTLED 1 — the numbers pass opens (2026-10-06)

Ruled with the user at the numbers-pass checkpoint:

- **Ocular keys gunnery** — space aim; the one-bay-per-skill map
  and the 3-space/3-ground split stand as authored. Reflexes
  (ground aim) and the both-layers aim rider declined.
- **Labs valence: NEUTRAL** — no ego-driven rep multiplier for
  Labs; the assumption is now a ruling.
- **Chrome does not tinker** — implants are sealed; the upgrade
  ladder lives in catalog tiers.
- **Bays are worn alongside armor, never instead of it** — made
  explicit (was the implied reading); chrome occupies no armor
  slot, and the armor-slot competition the placeholders suffered
  is removed by design.

## SETTLED 2 — the ego formula (2026-10-06)

- **Max ego is level-fed: `6 + (level - 1) // 3`.** Pool 6 at L1,
  9 at L10, 15 at L30, 25 at L60 (last increment lands at L58).
  No species or class modifiers — level-fed only; nothing becomes
  the chrome stat.
- **The cap encodes the wide-or-deep identity.** With the working
  tier-cost ladder (t1 1, t2 4, t3 7, t4 11): six shallow (t2) =
  24/25 — tight; three deep (t3) = 21/25; two marquee (t4) =
  22/25; three marquee (33) impossible at cap. Wide or deep,
  never both — the level-60 budget is a real choice.
- **Cost and burn are one number per piece.** The burn is the
  ratchet (high-water mark) of summed install costs, per the ego
  economy section — there is no separate burn stat to calibrate.
- The tier-cost ladder is the working calibration the user chose
  with the formula; exact values may still be nudged by the
  remaining numbers-pass questions, the formula is the ruling.

## SETTLED 3 — dead zone and tier gates (2026-10-06)

- **The dead zone is burn <= 3, lifetime.** Prices, rep rates,
  and boards untouched at 3 or lower burn, forever — three teach
  pieces free; the fourth point of burn enters band 1.
- **Tier req gates read the bay's skill on the 0-100 scale:
  t1 none, t2 25, t3 50, t4 75.** Build affinity lives here —
  the marquee jack demands Piloting 75 (specialist territory on
  the 295-point L60 budget), and a marine's path to it runs
  through pilot skills. The old illustrative "Piloting 16"
  example retired (it predated the 0-100 anchoring).

## Open items

The numbers pass (open):

1. Multiplier curves (rep gain per faction, buy/sell, services)
   and board valence bands, keyed to burn bands above the dead
   zone. Ruled so far: formula (SETTLED 2), cost ladder 1/4/7/11,
   dead zone <= 3, tier gates 0/25/50/75.

Routed elsewhere by this doc's own section markers: the tier-one
teach catalog (both layers — an ocular/jack piece a pilot meets,
a vital/legs piece a marine meets) rides the tier-catalog phase;
the placeholder migration mechanism is decided in the
implementation brief ("Migration and audit rules" says decided at
build).

## Phases

- [x] Skeleton ruled end to end (2026-10-06, this doc)
- [ ] The numbers pass: formulas, curves, tier reqs
- [ ] The tier catalog + audit instruments (domination, module
      boundary, dead-zone pins)
- [ ] Implementation briefs (advisor pass per house rule)
- [ ] Prose pass (descriptions, vendor/surgery flavor, the
      Consortium voice)
