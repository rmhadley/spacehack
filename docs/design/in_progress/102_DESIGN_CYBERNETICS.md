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
- [ ] Implementation briefs (advisor pass per house rule)
- [ ] Prose pass (descriptions, vendor/surgery flavor, the
      Consortium voice)
