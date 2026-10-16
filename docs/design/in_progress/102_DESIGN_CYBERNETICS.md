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
  Level-fed max: `6 + birth + (level - 1) // 3` (ruled
  2026-10-06, SETTLED 2; birth = flat per-species modifier,
  -1..+2 proposed) — pool 6 at L1, 15 at L30, 25 at L60 at
  birth 0. Growth buys chrome room, which delivers the
  accessibility curve organically: fresh character, teach-tier
  room; late game, six-shallow or two-or-three-deep. No class
  modifiers; nothing becomes the chrome stat.
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
  none, t2 25, t3 50, t4 75 (ruled 2026-10-06), reading the
  BASE skill raw: "military-grade jack: Piloting 75" means 75
  allocated pilot skill; module/gear stat modifiers never count.
  Build affinity lives here, not in budgets.

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
  Mechanism ruled 2026-10-06: per-planet valence = band shift
  +/-1, psycho anchored at burn >= 12 (SETTLED 4).
- **The dead zone:** burn <= 3 costs nothing anywhere — prices,
  rep, boards untouched (ruled 2026-10-06: width 3, lifetime —
  three teach pieces free, the fourth point of burn enters band
  1). The teaching tier must be consequence-free or the system
  teaches avoidance.
- **Full psycho / the Consortium gate:** a Consortium comms
  contact introduces itself; the line is exposed on the F
  screen. An intro, nothing more — corpo detail later. This
  gives the Consortium two reveal doors (doc 39's tower raid =
  force; the ego floor = courtship) — nothing exclusive, two
  rhyming paths. Anchored 2026-10-06 (SETTLED 5): the gate is
  burn >= 2 x birth pool (10/12/14/16), static for life — the
  latch is free (burn never recovers, the gate never moves);
  the world's psycho band stays 12+, species-blind.
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
- **No domination audit vs armor** (ruled 2026-10-15, phase 3):
  chrome is a new system, not an armor column — a character runs
  full armor slots AND chrome, so the two never share a cell and
  there is nothing to dominate. The old line was a placeholder-era
  leftover that predated the alongside-armor ruling (SETTLED 1).
  What, if anything, inherits the parts-ladder standard inside the
  chrome catalog is phase 3's open question (rider-vs-skill pricing
  is the live candidate).
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

## SETTLED 2 — the ego formula (2026-10-06; capacity rule
settled same day after two false starts)

- **Max ego is level-fed: `6 + birth + (level - 1) // 3`.**
  Birth is a flat per-species ego modifier in a small band
  (proposed -1..+2; exact values ride the species catalog pass).
  Pool 6 at L1, 9 at L10, 15 at L30, 25 at L60 at birth 0 (last
  increment lands at L58). No class modifiers; no skill keys
  the pool — nothing becomes the chrome stat.
- **Capacity rule C: the claim reads the pool; the burn is the
  stat.** Install checks `new load <= ego pool`; capacity
  recycles on uninstall. Burn = the high-water mark of total
  installed cost ever worn; it never recovers. Current ego =
  pool - burn — a room-side number that may lift off zero with
  level growth; it is NOT the psycho trigger. **The Consortium
  gate reads burn against twice the birth pool** (SETTLED 5);
  wearing the full pool merely means the room is gone.
- **Tier-cost ladder: t1 1, t2 4, t3 7, t4 11.** L60 identities
  at pool 25: six t2 = 24/25, exact-tight; three t3 = 21; two
  t4 = 22; three t4 = 33, impossible. Wide or deep, never both.
  Swap-ups pay the ratchet difference: six t1 worn (burn 6), a
  t4 replaces one bay = burn 16, ego 9.
- **Cost and burn are one number per piece** — the burn is the
  high-water mark of summed install costs; there is no separate
  burn stat to calibrate. Exact values stay working calibration
  until the catalog phase authors real pieces.
- Same-day errata, recorded for honesty: the ladder was first
  "corrected" to 1/2/5/8 under a double-charging capacity rule
  (installs checked against pool MINUS burn); the user's own
  framing ("amount of chrome you can wear before you hit full 0
  ego is not static") exposed the error and restored the
  original ladder under rule C.

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
- **The gates read BASE stats — raw** (user, 2026-10-06:
  "it's important that these are base stats. raw. not stats +
  modifiers from modules/gear."): the gate reads the skill
  container value (species/class start + allocated points
  only), never the effective value that modules and gear
  compose on top (`_module_bonus_sum` never counts). Gear
  cannot buy its way past a chrome gate.

## SETTLED 4 — the consequence bands (2026-10-06)

- **The frame: static scars.** Bands price burn COUNT, forever —
  consistent with the ruled static dead zone. Leveling and
  species birth mods grow room; they never re-price scars.
  Pool-relative bands were considered and declined: day-one
  clash with the dead zone (two t2s would read ~67% = psycho on
  day one — teaches avoidance), scars softening as the pool
  grows, and birth mods compounding (more room AND a milder
  read of the same burn).
- **Three bands above the dead zone** (burn spans 0-25 under
  rule C):
  - 4-7 flagged: lawful buy/sell/services x1.05; rep gain
    x0.95 merchant/militia, x1.05 pirate/Consortium; boards
    untouched.
  - 8-11 chromed: x1.15; rep x0.85 / x1.15; strict planets
    lose 1 board row.
  - 12+ psycho: x1.30; rep x0.70 / x1.30; pirate t3+ posts
    ONLY to psychos.
  Labs neutral throughout (SETTLED 1); services ride the price
  multiplier; magnitudes are starting values, tuned by
  playthrough feedback per house doctrine.
- **The psycho BAND anchors at burn >= 12** (species-blind).
  The Consortium GATE is separate and per-species — burn >=
  2 x birth pool, meeting the band exactly at birth 0 (SETTLED
  5).
- **Per-planet valence = band shift +/-1.** Tolerant planets
  (pirate havens, corporate campuses) read the burn one band
  milder; strict planets (lawful cores) one band harsher. One
  knob drives prices, rep, and boards together.

## SETTLED 5 — the Consortium gate (2026-10-06)

- **The full-psycho gate is `burn >= 2 x (6 + birth)`** — twice
  the birth pool: 10 / 12 / 14 / 16 for birth -1 / 0 / +1 / +2.
  Static, fixed at creation; level growth adds room and never
  moves the target (user: "your hardening as you level doesn't
  make it a moving target"). The Consortium knows your birth
  certificate; the world prices scars.
- **The latch is free.** Burn never recovers and the gate never
  moves, so once crossed the state is permanent — no separate
  latch machinery. This supersedes SETTLED 2's earlier
  "zero ego = wearing the full pool" trigger, which level-ups
  could un-hit.
- **The live ego number is room-side only**: pool - burn, a
  capacity display that may lift off zero after level growth.
  The gate reads BURN, like every other consequence.
- **Species variance, concrete:** birth -1 latches on ONE t4
  (burn 11 >= 10); birth +2 needs burn 16 (t4+t2 = 15 does
  not; t4+t2+t1 = 16 does). The gate is structurally
  unreachable before the pool can contain it — earliest possible
  psycho is L13 (birth -1) / L19 (birth 0) / L25 (+1) / L31
  (+2), and tier reqs push each later still: the deep end is
  late-game by construction.
- **Band vs gate:** the world's psycho BAND stays burn >= 12
  (SETTLED 4, species-blind); the Consortium GATE is per-species
  and meets the band exactly at birth 0 — for others they
  diverge by design (a -1 species is courted a band early; a +2
  species is courted deep inside it).
- The literal birth pool (5-8) was considered and declined: six
  t1 teach pieces on day one would have latched psycho (a trap
  under the dead zone), and one t3 (burn 7) would have latched
  it inside band 1 while the world still read "flagged, x1.05".

## SETTLED 6 — the crit system + Ocular t1 opens the teach
## catalog (2026-10-15)

Ruled with the user during phase-3 authoring:

- **Crit chance and crit damage are first-class stats, all three
  theaters** (ground melee, ground ranged, space). Base crit
  chance 0% everywhere; base crit damage 1.5x everywhere. Both
  are built to be modified from day one (ruled example:
  cybernetic arms granting ground melee crit damage +5% raises
  the multiplier to 1.55x — additive points on the multiplier).
- **Ocular t1 = Terminus Tech Optics: grants space crit chance
  15%.** The first — and currently only — source of any crit
  chance in the game. Space only; burn 1; cheap and shop-common
  per the teach tier. This supersedes the anatomy's t1 "+hit
  rider" sketch for Ocular (rider vocabulary stays available to
  t2+).
- **Player-side today, actor-symmetric by architecture:** only
  because no NPC wears chrome yet. An NPC pilot with the chrome
  crits by the same rules — the calc reads the actor's stats,
  never a hardcoded player branch.
- **Terminus Tech is the megacorp the Consortium's board operates
  through** — the brand on the teach catalog and the chrome-trail
  answer (doc 39's "who makes the chrome?"). The name is ruled,
  not working; the Consortium voice pass (phase 5) writes it.

Parked: aim-surplus-to-crit conversion (raw hit over the 95 clamp
becoming crit chance) — declined for t1 flat 15%, kept as t2+
vocabulary.

Open dependency for the Arms turn: crit damage is inert without a
crit chance source in the same theater (base 0%, and Ocular's
chance is space-only) — Arms t1 must grant melee crit chance (or
pair with a source) for its crit-damage example to fire.

## SETTLED 7 — the dodge amendment + Pilot jack t1 (2026-10-15)

Chrome births its second system stat (the crit system was the
first, SETTLED 6):

- **Movement dodge is exempt from the 60 total cap — for
  everyone, not just chrome users.** The cap now binds the
  piloting base only: base = min(folded piloting x 0.5, 60).
  The movement term rides on top, no total cap.
- **The movement term becomes min(cells moved, 6) x per-tile
  coefficient** — the first 6 cells (6 AP of movement) contribute;
  base coefficient 5. The old +30 points-cap on the term is
  replaced by this cells cap. Max at base coefficient: 60 + 30 =
  90. The per-tile coefficient is a first-class stat; chrome
  grants are additive raises on it.
- **Pilot jack t1 = TT Piloting Jack: +1 dodge per tile moved.**
  A capped-base pilot on a full-move round reads 60 + 36 = 96 —
  past the old 90 ceiling, under 100 on day one. The +2/tile
  deepening (crossing 100, where the 5-95 clamp floor becomes
  load-bearing) is t2+ vocabulary. Burn 1, shop-common. The name
  sets the catalog convention: pieces carry the TT prefix; the
  full "Terminus Tech" lives in vendor prose (phase 5).
- **Actor-symmetric like the crits:** the exemption, the base,
  and the coefficient all read the actor — an NPC pilot wearing
  the jack kites harder too.
- **Doctrine retired on purpose:** the old guard ("a clever
  kiter can never make the opponent literally invulnerable" —
  the total-60 cap) is dead; the 5-95 clamp floor is the sole
  invulnerability guard. Elite aim stacks still pierce (raw ~135
  reads 39% vs dodge 96); the accuracy-98 breach line is the
  catalog's dodge counter.

This supersedes the anatomy's jack t1 "+AP/dodge rider" sketch
(rider vocabulary stays available to t2+). The opening-salvo
evasion-window idea raised during authoring dies here, superseded
by the coefficient direction.

## SETTLED 8 — the core contract + the teaching OS (2026-10-15)

The spine's direction, ruled across the 2026-10-15 session:

- **The spine hosts the chrome core — the OS for the whole
  wardrobe.** Other pieces gain core-synergy lines from t2+
  ("+1/tile; Runner core: +2/tile instead"); the already-ruled
  t1 pieces are core-agnostic and gain lines in the t2 pass. The
  t2+ roster (space specialists, ground specialists, layer-
  agnostic generalists — Interdictor/Gunner, Ghost/Runner,
  Breacher, Vital-line, Operator as working shapes) is its own
  authoring sub-pass; the spine row goes three-wide and is the
  pass's biggest authoring surface. Spine gates stay on the
  engineering skill, including for ground cores.
- **The core contract: activated mode, one action key, both
  theaters, cooldown-based (not once-per-fight), default no
  activation cost, small passive garnish at t2+ only.** Hard nos,
  ruled: no RNG backfire (risk teaches timing, not distrust);
  no ego-per-pop ever (burn is install-time, SETTLED 2). NPC
  cores pop through the existing reserve/spend scorer —
  actor-symmetric bursts are half-built by the doc 57 AI work.
- **The teaching OS (t1): one factory OS, pure button, zero
  passive.** No fork at t1 — the archetype firmware is the t2+
  story. One button, both theaters, same burst and same cost
  everywhere.
- **Burst = the AP loan: +2 AP this round, −1 AP next round
  (the repayment). Cooldown 3 rounds**, usable any round — the
  outstanding loan itself discourages round-1 alpha pops. All
  numbers are starting values, tweaked on playtest.
- **Risk ruling: yes — the loan is the risk.** Opt-in,
  combat-layer, chosen at the button: doctrine-clean against
  "chrome enhances combat, always," and the recorded endgame
  intent (opt-in risk pricing power) in miniature.
- **Frame amendment:** the core action key is the one new t1 UI
  surface — the lesson IS the button; every t2 core reuses the
  keybind.
- **The mirror, recorded as design intent:** the Combat Stim
  (chem, ground-only) pays upfront — use_ap_cost then the burst
  same turn; the neural version pays deferred — burst now, −1
  next round — and runs in both theaters. Same family of
  borrowed action, opposite accounting, and the firmware crosses
  the cockpit door the chem cannot.
- Name: **TT Neural Stim** (ruled 2026-10-15). The chem-maker
  question (who makes the Combat Stim — TT's pharma wing vs
  street product) is deferred; the user has a consumables polish
  pass queued for the near future and it belongs there.

## SETTLED 9 — Vital t1: TT Nano Mesh (2026-10-15)

- **Effect: while HP is strictly below half, the worn armor's
  total DR is multiplied ×1.25.** A conditional coefficient on
  the armor read — never a flat DR add. It scales with armor
  investment by design (chrome rides alongside armor, SETTLED 1);
  an unarmored build gets nothing and that is accepted.
  Ground-only (Vital is the ground bay); actor-symmetric; 50%
  and ×1.25 are starting values.
- **Tuning law: consolation, never lifestyle.** If the multiplier
  ever grows enough that staying wounded on purpose is a
  strategy, the piece is mis-tuned — the number may move, the
  identity may not.
- **Naming rulings from this session:** the t1 register is plain
  function names (Optics, Jack, Neural Stim, Nano Mesh);
  colorful names are reserved for higher tiers. "Nullifier" is
  explicitly reserved for the future stabilization line — the
  piece that literally nullifies a killing blow (the parked
  survive-at-1 vocabulary, now with its name). "Second Heart" is
  parked as an emergency-HP-pool-shaped future piece (name plus
  mechanic seed).

Teach catalog: 4 of 6 (Optics, Piloting Jack, Neural Stim, Nano
Mesh).

## SETTLED 10 — Arms t1 (2026-10-15)

- **Effect: +15% ground melee crit chance (the Optics' mirror in
  the other theater) plus a flat +2 melee damage garnish.** The
  crit chance is the identity — this resolves the SETTLED 6
  dependency: ground melee crits now have their source, and the
  ruled +5% crit-damage example (1.5x -> 1.55x) fires as the t2
  deepening. The flat add is feel, sized at +2 (ten strength
  points' worth at the //5 step) — front-loaded early, fading
  with investment. Both numbers are starting values.
- **Family law, refined (user ruling): flat may garnish, never
  carry.** A piece's identity is always a rate, chance, charge,
  or conditional; small flat riders may ride along for feel.
- Ground ranged crit chance remains 0% with no source — no bay
  owns ground aim (declined, SETTLED 1). Noted gap, future
  vocabulary.
- **Invasiveness ladder (user ruling): tier = how much of you is
  still you.** T1 pieces ENHANCE existing flesh (the consumer
  line — grafts and weaves, never replacements); full
  replacements (a whole arm) are higher tiers at higher ego
  cost. The 1/4/7/11 burn ladder maps onto flesh-to-machine
  escalation. This also separates the line from the placeholder
  names, which claimed replacement they never earned.
- **Name: Terminus Muscle Fibers** (ruled 2026-10-15) — fibers
  are the muscle's own unit; enhancement, not prosthetic (TT
  Servo Arms rejected on exactly this ground).
- **Naming convention RESOLVED (2026-10-15): three registers,
  each ruled to a layer.** Item names (the catalog field) carry
  one mark, "Terminus X" — Terminus Optics, Terminus Piloting
  Jack, Terminus Neural Stim, Terminus Nano Mesh, Terminus
  Muscle Fibers (the Optics drops its "Tech"). "Terminus Tech"
  is the full corporate name, prose-only, at introduction
  points (vendor descriptions, lore). "TT" is compression and
  speech — stock lines, logs, rumors, dialogue — and which
  register an NPC uses characterizes the speaker (lawyer:
  Terminus Tech; dock hand: TT; the board: Terminus). Register
  variation teaches through prose position, never through the
  item-name field.

Teach catalog: 5 of 6 (Optics, Piloting Jack, Neural Stim, Nano
Mesh, Arms pending name).

## SETTLED 11 — Legs t1: Terminus SmartLink; the teach catalog
## completes (2026-10-15)

- **Effect: +15% ground ranged crit chance.** Clean, the Optics
  mirror — no garnish (ranged volleys are high-volume; a flat
  add compounds strongest there, and "your shots crit now" is
  the whole feel). The crit trio completes: space crits from
  the Optics, melee crits from the Muscle Fibers, ranged crits
  from the SmartLink — every theater the SETTLED 6 system
  defined has its teacher, and the catalog's coverage is total
  with zero overlap: space aim, space movement, core button,
  ground defense, ground melee, ground ranged.
- **The declined ground-aim bay resolved: it was Legs.** The
  SETTLED 1 decline was about the OCULAR going gunnery-only;
  reflexes is the ground aim stat (accuracy + attacker
  reflexes//2 − target reflexes//2), so the reflexes-keyed bay
  owns ground ranged after all. The bay fiction flexes from
  "the stride" to the platform: a marine shoots from the
  stride. The legacy +1 AP/round dies here (the Neural Stim
  owns burst AP; a passive AP/round next to the loan economy
  is muddled).
- **Name and fiction (user intent, recorded): "Terminus
  SmartLink" — the neural system linked with the ranged weapon;
  the weapon in the hand becomes part of the body, aim a reflex
  instead of a conscious set of actions.** The least invasive
  piece in the line — a link, not a limb — bottom rung of the
  invasiveness ladder, and chrome's first reach into a tool.
- **Parked:** ground movement-dodge coefficient (good t2+
  vocabulary or a future piece); the legacy +1 AP/round (t2+
  deepening, natural pair with a coefficient later); disengage
  and move-cost cuts (t2+ surfaces as always).

Teach catalog COMPLETE, 6 of 6: Terminus Optics, Terminus
Piloting Jack, Terminus Neural Stim, Terminus Nano Mesh,
Terminus Muscle Fibers, Terminus SmartLink.

## SETTLED 12 — the audit instruments; phase 3 closes
## (2026-10-15)

All three instruments ruled or spec'd with the user:

- **Rider-vs-skill pricing — RULED IN** (the parts-ladder
  standard's successor; proposed at phase-3 open, ruled at
  close): a chrome rider duplicating an effect skill points can
  buy must never price below the skill points that buy the same
  effect, at the engine's exchange rates (gunnery +0.5 hit/pt;
  piloting +0.5 dodge/pt and +0.05 AP/pt; strength +1 melee
  damage per 5 pts; stamina +1 HP per 2 pts; engineering +1 max
  power per 5 pts). Runs per-piece before numbers land, plus a
  catalog-wide regression pass. Chances with no skill analogue
  (crit chance — skills cannot buy crits) are exempt by
  construction: that is chrome's discrete-class territory.
  First exercised instances: the Muscle Fibers garnish (+2 ≈
  ten strength points), the Neural Stim loan vs chem-stim
  pricing.
- **Module-boundary audit spec** — two clauses. VOCABULARY:
  riders read like the skill, small and personal, never like
  module rows (gunnery_bonus / piloting_bonus / power_gen_bonus
  / max_shield_bonus / shield_recharge_bonus are module
  vocabulary). FUNCTION: no chrome piece duplicates a module
  row's function — chrome changes what YOU do (crits,
  coefficients, loans, the clench), modules change what the
  SHIP does. The t1 catalog passes trivially; the law binds the
  t2+ authoring, hardest at the spine (the most
  module-adjacent bay).
- **Dead-zone pin spec** — the instrument is a bit-identical
  diff, not an epsilon: two characters identical except burn 0
  vs burn 3 (three t1 installs); walk EVERY socioeconomic
  readout — vendor buy and sell on a strict planet, each
  service (repair, refit, restock, medical, docking), rumor
  dealer prices, rep gain per faction, board tier bands AND row
  counts — and require every value identical. Its real job is
  the consumer bug class: any read of raw burn instead of the
  band function ("if burnt > 0: surcharge"). Ships as a
  permanent regression test in the build scope.

## SETTLED 13 — capacity clarified: bays are sites, not slots
## (2026-10-15)

User catch: the session said "six slots"; the settled law says
no such thing.

- **A bay is an anatomical SITE, and installed chrome is
  limited solely by ego** (capacity rule C: install checks new
  load <= ego pool; the tier ladder 1/4/7/11 is per-piece). A
  reflexes t1 piece and a t2 joint replacement coexist in the
  legs region: load 1 + 4 = 5, burn ratchets, each piece's
  tier gate reads reflexes BASE raw. The invasiveness ladder
  becomes a per-bay accumulation story — a limb carrying weave
  AND joints is literally less you.
- **Same product line supersedes, different products stack**
  (SETTLED 2's own arithmetic — "a t4 replaces one bay"):
  installing the next tier of a line you wear is a SWAP priced
  by the ratchet; distinct products in one bay both claim
  capacity.
- **The one exception (flagged for user veto): the spine holds
  exactly one piece** — the core contract needs a singular OS
  (SETTLED 8); two firmwares is two personalities.
- UI consequence (cluster C sketch amended): the stats-tab bay
  detail is a LIST of installed pieces, not one; the row
  marker reads filled/empty.
- The numbers-pass wide ceiling ("six t2 = 24/25") remains
  true as the six-bay-wide shape, no longer the only shape —
  "deep" now also means stacked bays. The rider-vs-skill check
  (SETTLED 12) guards within-bay stacking too: same-domain
  riders priced against the same skill points whether spread
  across bays or piled into one.

## SETTLED 14 — unique per anatomy (2026-10-15)

User concept ("forced unique identifier"), named and ruled: every
piece declares its **anatomy** — the anatomical structure it
occupies — and **at most one installed piece per anatomy**;
installing over an occupied anatomy is a SWAP, never a stack and
never a rejection (the ratchet prices it).

- **Three orthogonal limiters, now explicit:** the bay (skill)
  gates WHAT STAT a piece extends and holds the tier gate; the
  ANATOMY gates the body (one per structure); EGO gates HOW
  MUCH. Quantity, identity, and flesh — one axis each.
- **The spine exception dissolves:** no special case — the OS is
  singular because it IS an anatomy (one spine), same as one
  pair of eyes. SETTLED 13's veto flag resolves itself.
- **Refines SETTLED 13's boundary:** "same line supersedes"
  becomes "same anatomy is exclusive" — broader and correct: a
  competitor's t3 ocular piece collides with the Terminus Optics
  (one eye system, any brand), while different structures stack
  within a region (gun link + leg joints).
- **t1 catalog keys:** Optics -> ocular; Piloting Jack -> jack
  (the neck wire port); Neural Stim -> os (the spine firmware);
  Nano Mesh -> dermal (the subdermal weave); Muscle Fibers ->
  arm_muscle (deliberately narrow so a future arm-joints piece
  stacks beside it); SmartLink -> hands (corrected from
  gun_link — the link lives in the hand, per the fiction: the
  weapon IN YOUR HAND becomes part of your body).
  Same-line tiers share their key by definition.
- **Subsumes doctrine (t2+ authoring law):** a piece occupies
  every anatomy its fiction covers — a full-arm replacement
  collides with (and swaps out) the fibers it replaces. Key
  replacement tiers accordingly when authored.
- **UI consequences (for the gated A/B discussion):** install
  becomes a three-check instrument — capacity, tier gate, and
  anatomy collision — each with its own message, collision being
  the SWAP flow ("replaces your Terminus Optics"), never a
  block. Two new agenda items: (1) replaced-piece disposition —
  recommendation: the surgeon hands it back, hold item,
  sellable (funds the upgrade path; disposal fees are very
  Consortium); (2) the consent moment should state the ratchet's
  reassurance — re-installing a piece within your historical
  peak costs zero new burn ("deeper costs, back is free").

## SETTLED 15 — band presentation: names, not numbers
## (2026-10-15)

- **The band NAMES carry the communication; the UI never states
  the consequences.** Multipliers, rep effects, and board
  effects are felt in the world (prices you're charged, rows
  that vanish, rep that moves) — never enumerated in a modal or
  on a screen. The consent modal shows the NAME transition
  ("You are Human. This will leave you Chromed.") alongside
  the permanence warning and the ego numbers already ruled in
  cluster B.
- **The player-facing ladder (RULED):** burn 0-3 = **Natural**
  (the dead zone's name — "Human" rejected, not everyone is
  human; the chrome trade's word for the unmodified); 4-7 =
  **Tainted** (the register is the world's escalating slur, not
  bureaucracy); 8-11 = **Chromed**; 12+ = **Psycho** (the
  street word the board-valence language already uses).
- **The C-screen ego line carries the current band NAME** —
  settling the label question: label yes, name only. Lean: the
  BASE band (you), not the planet-shifted local read — the
  local read is felt in prices; a name that changes when you
  travel reads as a bug first and a mechanic second.
- The guide (reference manual) documents the actual numbers
  when implemented — the game UI never does.

## Pre-implementation audit (Brief 4.1 — verified in code 2026-10-16)

Every advisor seam re-verified against the live tree before code;
anchors are current as of this session's recon.

### Existing modules to extend or reuse

- **Crit math** rides the two space direct-fire sites —
  `_rules_space.damage()` (player) and `_ai._resolve_enemy_shot`
  (enemy) — NEVER inside `_actions.resolve_damage` (missile
  arrivals call it bare; missiles never crit, pinned by test).
  Ground: inside `_rules_ground.damage()`, melee/ranged split on
  the existing `damage_type == "melee"` read. The multiplier
  threads `resolve_damage` as a `crit_mult` kwarg (default 1.0) so
  the shield/hull split stays one implementation; ground multiplies
  the post-armor dealt damage. Crit and glance stay independent
  multipliers (a crit-glance is legal arithmetic; crit wins the
  popup label). Blasts/explosions never crit (not direct fire,
  same ruling family as missiles). The Deadshot chain's shots are
  deliberately crit-less too (reviewer catch, recorded 2026-10-16):
  the chain resolves base-stat through `_ground_damage_raw` — no
  Deadshot bonus, no chrome riders; equipment bonuses don't ride
  the chain's base-stat resolution.
- **Crit feedback**: `_messages._result_clause` (the shared
  player/enemy attack-line factory — one wording, both theaters)
  + `_animations._damage_popup_for` (the single popup factory both
  fire paths already share).
- **Dodge amendment**: `_stats._calc_dodge_bonus` gains
  `tile_coefficient=5`; the 60-cap moves onto the piloting base
  only; movement = min(cells, 6) x coefficient (at coefficient 5
  the movement term is IDENTICAL to today — only the total-cap
  lift changes values, and only for piloting>120 movers). Defender
  containers: `player_state["dodge_tile_coefficient"]` stamped at
  `_space_init._stamp_dodge_coefficient` (amended at build, 
  2026-10-16: the `_stats` init builders are deliberately ctx-free,
  so the stamp lives where ctx is in scope — same contract, better
  home); `EnemyInstance.dodge_tile_coefficient`
  (default 5) declared in `combat/_types.py`. Threading: ONE shared
  player read `_stats.player_dodge_from_state` (reviewer DRY catch —
  the assembly was copy-pasted at 9 sites) + direct enemy-defender
  reads at `hit_chance`/`_build_hit_chances`/`_arrival_dodge`
  (merged-target getattr: in-flight missiles defend at base 5).
  The GROUND twin
  (`_ground_math.calc_ground_move_dodge`) is untouched.
- **Nano Mesh** hooks per-hit armor consumption — the enemy-shot
  resolution (`_ai_ground` via `_landed_shot_soak`), blast
  self-splash + blast enemy victims (`_ground_blast`), stare
  eruption (BOTH branches — player and enemy victims), the
  Deadshot chain's victims, and the enemy side in
  `_rules_ground.damage()` — every site routed through ONE pair:
  `soak_with_mesh` (the pure conditional) with `player_soak` /
  `enemy_soak` twins. NOT `_armor_defense_total` (stamped once at
  init; HP can cross half mid-burst, so the below-half read is
  per-hit). The AI EV scorers keep the RAW read (the bounty-hunter
  belief precedent: resolution-only, enemies misjudge by design).
  The chain's victims DO soak (the base-stat ruling excludes
  attacker bonuses, never the victim's armor read — reviewer
  catch, recorded 2026-10-16).
- **Core button**: keybind in `_loop._key_action`'s action table,
  dispatched through the optional-rules-hook pattern
  (`activate_core`). Ground loan rides
  `GroundCombatState.active_consumable_effects` (a −1-AP,
  1-turn-remaining entry consumed once by
  `advance_player_effects` at the next round start); ground
  cooldown = one int on the state, ticked at round start. Space
  loan + cooldown = `player_state` keys consumed/ticked at
  `_actions.start_player_turn` / `_reset_ap_carry`. HUDs: ground
  player panel (`_ground_render`), space `_paint_status_hud`.
- **Chrome container**: `GameContext.installed_chrome: list[str]`
  (piece ids; anatomy exclusivity enforced at install — dev grant
  in 4.1, kiosk in 4.2) + a sum-effect accessor in a new
  `chrome.py` mirroring `ground_equipment.sum_armor_bonus` (skip
  unknown ids silently, same contract). Save:
  `saveload._core_fields` + `_restore_core_fields` backfill
  (`data.get("installed_chrome", [])`), round-trip test.
  `saveload.py` is 992 lines — the save fields cross 1000, so the
  in-commit extraction fires ( cohesive split, ratchet doctrine).
  NO ego fields (4.2).
- **Catalog**: `data/chrome.py` — frozen `ChromeSpec` +
  `find_chrome`/`list_chrome` (data-first pattern); six t1 pieces,
  effect payloads as flat defaulted fields, anatomy keys per
  SETTLED 14 (ocular/jack/os/dermal/arm_muscle/hands).
- **Dev acquisition**: the `dev_mode` menu pattern
  (`ui.MenuScreen` + pygame frames), gated on `SPACEHACK_DEV` —
  grant/uninstall per piece for playtest.
- **Balance re-pins**: crit rolls guarded `chance > 0` —
  chrome-less fights consume ZERO new draws (kill-draws doctrine);
  the dodge cap lift moves piloting>120 movers with zero new
  draws. `tests/balance/` + `tools/balance_probe.py` are the
  instruments; re-measure tripped rows same-commit, cause noted.
  Old-formula pins to update: `tests/combat/test_stats.py`,
  `tests/combat/test_enemy_fire.py`.

### Duplication hotspots (three)

1. **Crit roll blocks copy-pasted across four fire sites** (space
   player + space enemy + ground player + ground enemy): the
   guarded roll, multiplier lookup, and flag plumbing.
2. **Defender-coefficient reads re-derived at 9+ dodge call
   sites** (the `int(x * 0.5)` pre-scale is already repeated at
   each).
3. **Mesh state peeked inline** at every armor-consumption site
   (worn? below half?) instead of one soak read.

### DRY strategy

1. One pure helper per side (`_stats`): the guarded roll +
   multiplier resolution; fire sites call it, never inline the
   RNG guard (state-table guardrail: one crit implementation per
   theater assembly, shared by both actors).
2. The coefficient threads the EXISTING `_calc_dodge_bonus`
   params — no parallel dodge formula anywhere; the pre-scale
   convention stays at the callers.
3. One `_player_soak(state)` helper in `_rules_ground` (+ the
   enemy twin at `enemy.armor`) — every consumption site calls
   the helper (the `_damage_popup_for` single-factory precedent).

## Prose ledger — Brief 4.1 (2026-10-16, the prose loop)

Keybind ruled the same session: **the core action key is `a`**
(SETTLED 8's "one action key" named; every t2 core reuses it).

1. Crit result clause (`_messages._result_clause`, all three
   theaters, both actors) — **SHIP IT**: "It critically hits for
   12 damage!"
2. Crit popup label (`_animations._damage_popup_for`, both
   theaters, both actors) — **SHIP IT**: "CRIT -12", bright red
   (hotter than the normal orange-red).
3. Neural Stim activation line (combat log, both theaters) —
   **USER EDIT, verbatim**: "You activate the Terminus Neural
   Stim and your senses heighten as energy courses through you."
   ("coarses" corrected to "courses" on an explicit follow-up
   ask.)
4. Repayment line (combat log at next round start, both
   theaters) — **USER EDIT, verbatim**: "Reality slows as the
   Neural Stim's effect wears off."
5. Stim unavailable lines — **SHIP IT**: cooldown "Neural Stim
   recharging: 2 rounds." / uninstalled "No neural core
   installed."
6. HUD Stim line (ground player panel + space status HUD,
   identical) — **SHIP IT, amended**: "STIM (a): READY" /
   "STIM (a): 2 ROUNDS". The debt line ("STIM (a): -1 NEXT
   ROUND") is **DECLINED** — user: "The player will learn the
   drain on their own. If that lands bad in gameplay we'll
   revisit." The repayment log line (#4) is the debt's only
   surface.

## Pre-implementation audit (Brief 4.2 — verified in code 2026-10-16)

### Existing modules to extend or reuse

- **Ego economy** (grows `chrome.py`, the domain home): pool =
  `6 + birth + (level−1)//3` — birth from a new
  `Species.ego_birth: int = 0` field (v1 all species 0; exact
  values ride the species catalog pass), level = `ctx.player_level`;
  **load = Σ installed burn costs (DERIVED, never stored — stored
  state is `ctx.ego_burn` only, the high-water ratchet)**; room =
  pool − burn. Install checks `load + cost ≤ pool`; burn moves to
  `max(burn, load_after)`. Save at `_core_fields` /
  `_restore_core_fields`; backfill = Σ installed costs (4.1-era
  dev-granted saves get the honest floor), 0 for pre-chrome saves.
- **Band function — ONE, in `chrome.py`**: `band(burn)` 0-3 with
  the ruled tables (names Natural/Tainted/Chromed/Psycho; price/
  service ×1.00/1.05/1.15/1.30). `local_band(ctx, planet_id)` =
  band shifted by the planet's valence (clamped 0-3). Consumers
  compose `chrome.local_band` + table reads, never raw burn, never
  inlined tables. Sell-side reads the SYMMETRIC composition
  ×(2−M) = 0.95/0.85/0.70 (recorded reading — the ruled numbers
  composed; vetoable).
- **Price consumers** (each ONE read): goods terminal buy/sell at
  the class-free cores `_terminal_buy_base`/`_sell_price`
  (trade.py:251/:281 — every goods path derives from these);
  NPC trade at `_npc_price_multipliers` (trade.py:534, the NPC
  fold — pirate/corpo NPCs exempt by `npc_spec.faction`); armory
  equipment + consumable buys (the `spec.price` reads in
  `menus/_armory_buy.py`); mechanic services INSIDE the preview
  functions (`_refuel_preview`/`_repair_preview`/ammo pricing in
  `menus/_mechanic.py` — preview/charge pairs share one read by
  construction); identity.py's three paper/ID spends; the kiosk's
  own prices. OUT (recorded): ship showroom prices (never read
  the goods core; not in SETTLED 4's list), mission rewards
  (ruled out), medical/docking (no charges exist), rumor prices
  (N/A v1, ruled).
- **Rep**: `faction.modify_rep` (faction.py:430) — positive
  deltas × the faction's band multiplier (merchant/militia
  0.95/0.85/0.70; pirate/consortium 1.05/1.15/1.30; labs 1.0)
  before the broadcast dispatch. Gains only — losses unchanged
  (the ruling says "rep GAIN multipliers"; recorded reading).
  NOT `_apply_rep_delta` (the spoofed-identity branch would
  silently miss it).
- **Boards**: `mission/_board.fill_empty_slots` is the one fill
  instrument — (a) strict valence + local band ≥ 2 → one fewer
  filled slot (the band-2 ruling extended monotonically to band
  3; recorded reading); (b) pirate-guild boards cap at t2 below
  psycho, full band at psycho (pirate t3+ posts ONLY to psychos).
- **Planet valence**: `PlanetSpec.ego_valence: int = 0` (−1
  strict / +1 tolerant) + a small assignment list for established
  planets (lawful cores −1, pirate/corpo ports +1, rest 0) —
  authored in the build commit with the planet meanings.
- **Kiosk**: `city_kit._TERMINAL_SPECS` gains a 4th entry + a
  `terminus_kiosk` blocker flag + a `_resolve_terminal_blocker`
  branch → a new `menus/_kiosk.py` (the armory-menu pattern).
  Stock = the six t1 pieces, always. Price = piece price × the
  local band's service multiplier (ruled: the kiosk itself rides
  it — the dead-zone lesson lands at the machine that sold the
  first pieces). One-step: select → checks → consent → installed.
  Placement: the 4th spec zips against each city's dxs (cities
  without a 4th dx keep the trio — placement completes city by
  city; earth + every authored port get the kiosk).
- **Three-check + consent**: checks as `chrome.py` pure helpers
  (capacity/tier/anatomy — SETTLED 14's ruled message forms
  verbatim); consent modal = the existing confirm family
  `_run_pygame_dungeon_confirm(title=, body=, accept_label=,
  cancel_label=, caption=)` — zero new UI families.
- **Swap-backs**: the replaced piece lands in the ARMORY terminal
  storage as `StoredGroundEquipment("chrome", piece_id, 0)` (the
  unlimited terminal-adjacent hold — "the hold" read as the
  storage you can sell from; kiosk-adjacent, pack slots never
  consumed); the armory's `_sell_price` gains a chrome family
  branch (catalog price // 2, quality-less — chrome doesn't
  tinker). No loose chrome exists any other way (F7 dev grants
  aside).
- **Migration**: one sweep at load (saveload restore path) over
  equipped/armory/expedition containers for the four retired ids
  → removed + credited at base price (worn AND stored — a retired
  id is dead anywhere; recorded reading), with a load-time log
  line. NPC side: the three consortium rungs' `worn_armor` become
  plain pieces (gunner: eyes→combat-helmet-class, arms→gloves;
  enforcer: arms→gloves, legs→greaves; executor: the four →
  plain t-band set — exact table in the build commit; the rungs'
  hit/melee/ap bonuses die with the fields, defense adjusts,
  their identity already lives in stat_weights/behavior), Mars
  `armory_armor` stock edited, the digs pool's eyes entry swapped
  to a plain piece. The four `GroundArmorSpec` bonus FIELDS
  retire with the entries — they are placeholder-exclusive
  (grep-verified) — taking `sum_armor_bonus`,
  `_ARMOR_BONUS_FIELDS`, `_worn_fold`'s hp_bonus, `enemy_ap_total`'s
  ap_bonus, `worn_bonuses`, and quality's bonus scaling with
  them.
- **Consortium gate**: DERIVED — `ego_burn ≥ 2 × (6 + birth)`
  (monotone burn, fixed target: no latch field). The one-time
  comms intro needs a shown flag: `ctx.consortium_intro_shown:
  bool` (saved), fired at install-time crossing. The F-screen
  line renders in `pygame_faction` when the gate is open.

### Duplication hotspots (three)

1. The band multiplier re-derived per consumer (eight+ sites)
   instead of composing the one band function.
2. Preview/charge drift in the mechanic services (three pairs)
   — the multiplier must sit inside the previews.
3. The retirement sweep duplicated across three containers and
   four ids.

### DRY strategy

1. `chrome.band_price_mult(band)` / `chrome.rep_gain_mult(faction,
   band)` / `chrome.local_band(ctx, planet_id)` — table reads in
   ONE module; consumers compose.
2. Previews remain the single price source (charges already call
   them).
3. One `_migrate_retired_armor(...)` helper sweeping every
   container; substitutes are data edits in one commit.

## Prose ledger — Brief 4.2 (2026-10-16, the prose loop; restart
## ruled by the user — the SETTLED 14/15 fragments were design-level
## and had never passed the gate)

**Vocabulary law (ruled at #8, feeds 4.3's C-screen line):** the
player-facing ego numbers are **Ego** (pool − burn), **Burnt Ego**
(the permanent ratchet), **Install Room** (pool − load) — and
**every chrome action shows the same Before/After table.**

7. Consent modal — **RULED through three rewrites**: flat numbers,
   the user's Before/After table form; title "Install Terminus
   Optics?"; rows `Ego: 6/5`, `Burnt Ego: 1/2`, `Install Room:
   5/4` (row added by #8's ruling), `State: Natural/Tainted` when
   crossing; swap line "Replaces Terminus Optics."; accept
   "Install" / cancel "Leave". A parenthetical permanence note was
   drafted and DROPPED — the permanence teaching moved to the
   removal moment (#8). The slash form is also CP437-safe (→
   is not).
8. Removal table + the vocabulary — **SHIP IT**: "Terminus Optics
   removed." + the same Before/After table (Ego 4/4, Burnt Ego
   2/2, Install Room 4/5). The `2/2` teaches permanence; the `4/5`
   teaches what removal returns. User direction verbatim: "let's
   make sure we teach it doesn't recover when a user tries to
   remove chrome."
9. Block messages — **USER EDIT (no em-dash)**: "Install Room 4
   required, you have 3." / "Piloting 75 required, you have 42
   (base, raw)."
10. Kiosk surface — **USER EDIT**: the terminal name is "Terminus
    Tech" (teaches the full corporate name at the introduction
    point, per the SETTLED 10 register law); install log
    "Terminus Optics installed."
11. Comms intro — **SHIP IT**: "Your Terminus Tech account is now
    active. We will be in touch."
12. F-screen line — **SHIP IT**: "Terminus Tech: account active"
    (echoes the intro's vocabulary).
13. Migration line — **SHIP IT**: "Cybernetic Eyes removed.
    Refunded 260$."

## Implementation briefs (written 2026-10-15; advisor pass
## below)

Three briefs, ordered so each lands on a playable checkpoint:
the body (combat felt), the economy (acquisition real), the
mirror (readable everywhere). Run order is strict — 2 builds on
1's container, 3 on both. `/implement-phase 102.4.1` and
following.

### Brief 4.1 — the body: crit system, dodge amendment, catalog
### effects, the core button

Goal: chrome's combat layer exists and is FELT, with a
development acquisition path (the kiosk is 4.2).

1. **The crit system** (SETTLED 6): crit chance + crit damage
   as actor-read stats — base 0% / ×1.5, all three theaters
   (ground melee, ground ranged, space direct fire). Resolution
   rides the existing hit/damage assemblies; damage
   multipliers are ADDITIVE POINTS on 1.5x (the arms example:
   +5% → ×1.55). Actor-symmetric by construction: the roll
   reads the actor's stat container — player chrome sums
   today, enemy containers when NPCs wear chrome. Crit
   feedback is part of scope: log lines both theaters plus
   damage-render treatment (the felt moment).
2. **The dodge amendment** (SETTLED 7), space only: piloting
   base = min(folded piloting × 0.5, 60); movement term =
   min(cells_moved, 6) × per-tile coefficient (base 5, a
   per-actor stat); no total cap on the sum. The GROUND twin
   (`calc_ground_move_dodge`) is unchanged in 4.1 — no t1
   source touches it (parked vocabulary). Update the doctrine
   comment: the 5-95 clamp floor is the sole invulnerability
   guard.
3. **Chrome container**: `ctx.installed_chrome` + a sum-effect
   accessor mirroring `sum_armor_bonus`; save fields with
   old-save backfill (empty list). NO ego fields yet (4.2).
4. **Catalog data**: the six t1 pieces (SETTLED 6-11) — id,
   name, bay skill, anatomy key (SETTLED 14: ocular / jack /
   os / dermal / arm_muscle / hands), tier 1, burn 1, price
   250-400cr calibration band, effect payloads.
5. **Effect wiring** (the five assembly points + the core):
   Optics +15% space crit chance; Piloting Jack +1 dodge/tile
   (space coefficient); **Neural Stim = the core button** —
   ONE keybind, both theaters, cd 3 rounds, +2 AP this round /
   −1 next round, cooldown + loan-debt visible in each HUD;
   Nano Mesh ×1.25 on the worn-armor DR total while HP
   strictly below half (ground, actor-symmetric — enemies wear
   armor too); Muscle Fibers +15% ground melee crit chance +
   flat +2 melee garnish; SmartLink +15% ground ranged crit
   chance.
6. **Dev acquisition**: a minimal grant/uninstall path
   (debug keybind or CLI flag — implementation choice) for
   playtest; the kiosk replaces it in 4.2.
7. **Tests/pins**: crit math (chance floor/ceiling, additive
   multiplier points), actor-symmetry shape, dodge pins (the
   96 composition, cells cap at 6, ground twin untouched),
   loan arithmetic (+2/−1/cd, both theaters), Nano Mesh
   conditionals (below-half only, multiplies the DR TOTAL),
   garnish seams — and **re-pin every seeded balance bar the
   new crit rolls trip** (kill-draws doctrine: new draws in
   the fight loops reshuffle streams; re-measure, same
   commit, cause noted). Gate: make check.

Checkpoint: a fight where you crit in all three forms, pop the
Stim, feel the repayment, kite past 90 dodge.

**Playtest checklist (handed to the user 2026-10-16; SPACEHACK_DEV
run, F7 = the chrome picker — grant BEFORE the fight: the dodge
coefficient stamps at encounter init):**

1. Crit trio (Optics + Muscle Fibers + SmartLink via F7): space
   fire ~15% "critically hits for" + bright-red CRIT popups; ground
   melee crits + the +2 garnish; ground ranged crits.
2. Neural Stim: press `a` in either theater — activation line, +2
   AP, HUD "STIM (a): 3 ROUNDS"; next round starts -1 AP with the
   "Reality slows" line; press during cooldown for the recharge
   line; without the Stim for the no-core line.
3. Piloting Jack: space kiting — Evade reads +1/tile higher than
   unjacked (96 composition needs folded piloting 120+).
4. Nano Mesh: ground, below half HP — incoming hits soak x1.25
   (the card's Armor number stays the BASE; watch the damage
   numbers); at/above half, unchanged.
5. F7 uninstall + save/continue round-trip — pieces persist.

**Playtest notes (2026-10-16):** the Stim burst landed its tactical
identity — user, verbatim: "stim burst was actually really great.
getting +2 AP to close a gap on a ranged to melee them was
surprisingly good." The emergent read is TEMPO (movement economy:
the loan buys the gap-close + the swing), not more dakka — first
tuning signal on the +2/−1/cd-3 numbers is positive; no change.

### Brief 4.2 — the economy: ego, the kiosk, consequences,
### migration

1. **Ego fields**: pool = 6 + birth + (level−1)//3 (species
   birth mods: field plumbed, v1 all species birth 0 — exact
   values ride the species catalog pass), load, burn
   (high-water ratchet), room. Save compat + backfill.
2. **The Terminus kiosk** joins the spaceport service
   terminals (cluster A): one-step stock + install; prices =
   piece price × the band's service multiplier. The
   **three-check instrument** runs first as BLOCKS (capacity:
   load + cost ≤ pool; tier gate: t1 none, the check exists;
   anatomy collision → swap flow, never a rejection).
3. **The consent modal** (clusters B + SETTLED 15): name
   transition ("You are Natural. This will leave you
   Tainted."), permanence warning, ego before/after with burn
   delta, "+0 — within your peak" when true, swap notice
   ("replaces your Terminus Optics — handed back"), Consortium
   gate crossing warning (lean YES, standing). Consequences
   are NEVER enumerated — names only.
4. **Swap-backs**: the replaced piece lands in the hold,
   sellable; no loose chrome parts exist any other way.
5. **Consequence bands live**: ONE band function (every
   consumer reads it, never raw burn); buy/sell/services
   ×1.05/1.15/1.30 on non-pirate/non-corpo vendors, Labs
   neutral; rep gains ×0.95/0.85/0.70 vs ×1.05/1.15/1.30;
   boards (strict planets −1 row at 8-11; pirate t3+ posts
   only at 12+); per-planet valence = band shift ±1; rumor
   dealer prices ride the multiplier; Consortium gate latch
   (burn ≥ 2× birth pool → the comms intro + F-screen line).
6. **Dead-zone pin** (SETTLED 12): the bit-identical
   burn-0-vs-burn-3 regression test across every
   socioeconomic readout.
7. **Placeholder migration** — the "decided at build" decision
   is now made: RETIRE the four vest entries; live saves
   migrate by UNWEAR + CREDIT REFUND at base price
   (grandfather rejected: dead stat-sticks contradict the
   retirement and the new system).
8. Tests: ratchet pins (swap within peak free; exceeding pays
   difference; uninstall frees load never burn), band-function
   pins, the dead-zone pin, migration pin (worn placeholder →
   unworn + credited). No new combat draws — economic tests
   only.

Checkpoint: install three pieces consequence-free, watch the
fourth Taint you — kiosk prices shift, a strict planet's board
loses its row.

### Brief 4.3 — the mirror: the C-screen split, the ego line,
### documentation

1. **The Stats tab adopts the split family** (cluster C;
   Equipment-tab precedent, pygame_split): left = the six
   stat rows + ×N piece counts; right = display-only chrome
   list for the selected bay, led by the skill description;
   ENTER stays SPEND; jk walks the stats.
2. **The ego line** in the body header: room | burn + the
   band NAME (base band — Natural/Tainted/Chromed/Psycho).
3. **Guide + annotation sync**: the chrome section (the guide
   DOCUMENTS the numbers per SETTLED 15 — names, multipliers,
   ego formula, kiosk flow), character-screen annotation
   lines, service-terminal help text.
4. Straggler polish from 4.1/4.2 (HUD hints, F-screen line
   formatting).
5. Tests: split-rendering pins (row budgets per the
   modal-font-ladder constraints), counts, HUD smoke tests.

Checkpoint: open C, walk the six stats, read your chrome, your
ego, and your name.

### Advisor pass (2026-10-15) — verdict SOUND-WITH-CATCHES;
### all 15 issues folded below, 3 open rulings flagged

**Folded into 4.1:** the "five assembly points" line was stale
— only the Fibers garnish lands on a legacy armor assembly.
The real seams: space crit at `_rules_space.damage()` (player)
+ `_ai._resolve_enemy_shot` (enemy) — NOT inside
`_actions.resolve_damage`, which missile arrivals also call
(missiles never crit; pinned); ground melee-vs-ranged split
INSIDE `_rules_ground.damage()` via the existing
`damage_type == "melee"` read; dodge threading = a
`tile_coefficient` param on `_calc_dodge_bonus` (60-base cap
applied inside — zero caller churn), `player_state` stamp at
`_player_state_dict`, an `EnemyInstance` field declared in
`combat/_types.py`; **Nano Mesh cannot ride `_armor_defense_total`**
(stamped once at init) — the ×1.25 hooks where `armor_defense`
is consumed per enemy turn, enemy side at `enemy.armor` in
`damage()`; the below-half read is PER-HIT (evaluated on each
incoming hit — HP can cross half mid-burst); **the re-pin scope
covers the DODGE AMENDMENT's bars, not just crit rolls** — the
formula change moves piloting-heavy movers (top-band folded
piloting > 120) with zero new draws; crit rolls guarded
`chance > 0` so chrome-less fights consume no new draws; the
loan rides the GROUND stim container
(`active_consumable_effects`, a −1 entry = the doc's parked
statuses sketch) + a space `player_state` key consumed at
`_reset_ap_carry`; cooldown = one int per theater state; the
keybind dispatches through the `_loop.py` rules-adapter; a
PROSE-SETTLEMENT precondition is added (crit log wording, HUD
cooldown labels — player-facing strings settle before the
phase runs; guide review deferred to 4.3, recorded); budget
notes: `saveload.py` crosses 1000 (extraction owed in-commit),
four combat modules sit near caps, `_rules_ground.damage()`
near the function limit; save site = `_ctx_to_dict._core_fields`
+ `load_game` backfill, round-trip test added; the
rider-vs-skill check is scheduled (t1: Fibers garnish +
Stim-vs-chem pricing).

**Folded into 4.2:** the placeholder retirement is bigger than
player saves — the four entries are LOAD-BEARING NPC data
(consortium gunner wears eyes+arms, enforcer arms+legs, a
stock tuple lists all four, Mars armory stock lists eyes+arms;
`sum_armor_bonus` skips unknown ids SILENTLY) plus six test
files pin them. **V1 disposition (proposed, confirm):**
stat-preserving plain-armor substitutes for NPC worn pieces
(the enemy chrome container stays deferred per SETTLED 6), the
Mars stock edited, the four bonus FIELDS on `GroundArmorSpec`
retire with the entries (quality scaling + sum paths updated).
Band consumer inventory recorded: terminal + NPC trader buys
(NPC prices have their OWN multiplier path, `_npc_price_multipliers`
— both wired), all sell paths, mechanic services (preview/charge
pairs share one read — the split-read bug class), rep hooks at
`faction.modify_rep` (NOT `_apply_rep_delta` — the
spoofed-identity branch would silently miss it), board
generation; `identity.py`'s three paper/ID credit spends are IN
scope (unnamed in SETTLED 4's service list); **mission REWARD
credits ruled OUT of the band (confirm)**; medical/docking
marked N/A (no credit charges exist today). **A second
dead-zone pin added:** burn 4 vs burn 0 on a strict planet
asserting exact ×1.05 per readout — the burn-0-vs-3 pin can't
catch consumers that never read the band at all.

**Folded into 4.3:** new frame code lives in
`character_screen_stats.py` (148 lines, room) —
`character_screen.py` is at 945.

**Ruled by the user (2026-10-15):**
1. **Rumor prices: N/A for v1.** The favor-price foundation is
   proof-of-concept only — nothing real consumes it yet; the
   multiplier ruling returns when the rumor system evolves.
   The dead-zone pin marks the readout N/A.
2. **Per-planet valence: the proposal stands** — PlanetSpec
   gains the field + a small assignment list for established
   planets (lawful cores strict, pirate havens/corpo campuses
   tolerant, rest 0); easily tuned in playtest. 4.2's
   strict-planet checkpoint works.
3. **Mission reward credits stay OUT of the band** — confirmed;
   payouts are never banded.

Verified clean by the advisor: the run order, all ruled
numbers composing (96 dodge, ×1.55 points, 4-AP ground base),
`installed_chrome` as a ctx field (no module-global contract),
dev-grant via `dev_mode.py`, the kiosk's one-flag home
(`city_kit.add_service_terminals` +
`game_interactions._resolve_terminal_blocker`), the ground
dodge twin genuinely untouched at base coefficient, and no
consumer depending on the total-cap-60 invariant (AI scorers
route through the 5-95 clamp; the pin risk is tests:
`tests/combat/test_stats.py` + `test_enemy_fire.py` pin the
old formula exactly).

## Open items

Phase 3 is COMPLETE (2026-10-15): teach catalog 6/6 (SETTLED
6-11) plus all three audit instruments (SETTLED 12). NEXT:
phase 4, the Implementation briefs (advisor pass per house
rule).

**GATED (user, 2026-10-15): the heavy UI surfaces — buying,
installing, and viewing your cybernetics — get a FULL design
discussion with the user before any brief covers them.** The
combat-HUD surfaces already ruled (the core keybind + cooldown
display, crit feedback, the F-screen Consortium line) are not
gated — they ride the first brief as designed. The first
brief's build scope otherwise: the chrome container (ctx field
+ sum function mirroring sum_armor_bonus, terms at the five
assembly points), the crit system, the dodge amendment, the
catalog data, the ego economy + consequence bands, and the
placeholder migration row (mechanism decided there, as always
intended).

Cluster A (the transaction) SHAPED and RULED (2026-10-15):
the install surface ESCALATES with the invasiveness ladder.
**T1 teach line: the spaceport service terminals** — the
Terminus kiosk joins the existing service counter (every port
has the trio, so "installable anywhere" is free; zero new UI
family; prices ride the service multiplier, so the dead-zone
lesson lands at the same machine that sold the first pieces —
dead-zone prices, then the flagged rate on the fourth). **T2+:
surgeons, escalating geographically** — Terminus clinic NPCs in
corpo-friendly ports, fringe ripperdocs at the edges, Venus at
the top; the refusal loop is human ("I won't operate at your
depth"), the travel pressure lives with them, and the consent
theater scales (a kiosk waiver for a weave, a facility for
your arms). **ONE-STEP transactions at both tiers** — kiosk
and clinic stock and install in one action; you never carry an
implant in a bag; the only owned-unworn chrome in the game is
swap-backs (the "buy the part as loose stock" fork is dead).
The lawful-refusal law covers kiosks too (same infrastructure
as the clinics) — moot at t1 (all six pieces = burn 6, still
band 1) but stated for when t2 lands.

Cluster C (viewing) SHAPED in discussion (2026-10-15): the
Stats tab adopts the SPLIT family — precedent on the same
screen (the Equipment tab embeds pygame_split, doc 52.3). Left
pane: the six stat rows as today + a ×N piece-count indicator
(stacking made counts meaningful). Right pane (display-only,
no actions — ENTER stays SPEND on the left): the selected
bay's chrome list, one line per piece, led by the existing
guide-synced skill description. Body header gains the ego line
(room | burn). Read-only by design; install/uninstall never
here.

Cluster B (the consent moment) RULED (2026-10-15): **any
OPTIONAL action that permanently depletes ego gets a confirm
modal first** — the law is general, not install-specific (any
future opt-in ego cost inherits it). The modal shows:
(1) the permanence warning in plain words; (2) **current ego
(pool − burn) before and after, burn delta explicit**
("burn 4 → 7"); (3) **if the new burn crosses a band boundary,
the band change is part of the warning** — band names become
player-facing vocabulary, which settles the ego-line question:
the C-screen line carries the current band label too (vetoable
if the hidden-lore reading should win there); (4) the zero-
drain case reads "+0 — within your peak" (the ratchet
reassurance delivered by the modal itself whenever true);
(5) anatomy swaps ride the same modal ("replaces your Terminus
Optics — handed back"). The three checks (capacity, tier gate)
are BLOCKS that run before the modal — the modal exists only
for when everything passes and consent is the sole question.
One micro-decision flagged with a lean: does the modal warn on
crossing the CONSORTIUM GATE (burn ≥ 2× birth pool — a
permanent one-way world latch)? Lean YES (one-way doors are
this modal's whole job); veto if the courtship should arrive
as a surprise.

**With B ruled, the heavy-UI gate is fully walked — A, B, and
C are all ruled, and the Implementation briefs may now cover
the acquisition/management UI.**

Routed elsewhere by this doc's own section markers: the tier-one
teach catalog (both layers — an ocular/jack piece a pilot meets,
a vital/legs piece a marine meets) rides the tier-catalog phase;
the placeholder migration mechanism is decided in the
implementation brief ("Migration and audit rules" says decided at
build).

## Phases

- [x] Skeleton ruled end to end (2026-10-06, this doc)
- [x] The numbers pass: formulas, curves, tier reqs (SETTLED
      1-5, 2026-10-06)
- [x] The tier catalog + audit instruments (SETTLED 6-12,
      2026-10-15: teach catalog 6/6 + all three instruments)
- [x] Implementation briefs (advisor pass per house rule) —
      briefs 4.1-4.3 written + ADVISE pass folded + all
      rulings closed 2026-10-15; `/implement-phase 102.4.1`
      is ready to run
- [x] 4.1 the body: crit system, dodge amendment, catalog effects,
      core button (Brief 4.1) — BUILT 2026-10-16 in six reviewed
      commits (container+catalog+save / crit system / dodge
      amendment / Nano Mesh / core button / F7 dev grant); gate
      green at 3827; PLAYTEST PASSED 2026-10-16 (crits, Stim,
      evade confirmed in play; the Mesh accepted on test evidence —
      the math is pinned at every layer in
      tests/combat/test_nano_mesh.py, including the exactly-half
      boundary and the integer truncation)
- [ ] 4.2 the economy: ego, the Terminus kiosk, consequence bands,
      migration (Brief 4.2)
- [ ] 4.3 the mirror: C-screen split, ego line, guide sync
      (Brief 4.3)
- [ ] Prose pass (descriptions, vendor/surgery flavor, the
      Consortium voice)
