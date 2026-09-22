# DESIGN: Enemy roster revamp — doctrine, scaling, coherence

**Status: DESIGN IN PROGRESS — phase 1 is a discovery/discussion/planning
phase; nothing is implemented until a build phase carries an approved
brief.**

Reframed 2026-09-22 from "enemy polish — difficulty-scaled enemies" into
the whole-roster campaign (same file, wider scope). The 2026-09-20 seed
and its scaling audit are preserved below; they became the
difficulty-doctrine topic (C).

Companions: `47_DESIGN_LOOT.md` (complete/ — kit drops + quality make
scaled loadouts scale loot automatically); `49_DESIGN_SPECIES_CLASS.md`
(player identity — interlocks via the faction rep tables);
`SYSTEMS.md` "Ground combat" / "Kill drops" / "RNG delve sites" /
"Space spawns" entries. Doc 34 (space combat behaviors, seeded
2026-09-03) is FOLDED into this campaign — SETTLED 21; file removed
from `future/`.

## SETTLED 1 (2026-09-22) — the reframe

User, verbatim:

> I don't want all of this to feel like it was just cobbled together. we
> need a plan. ... We never made a decision about enemies in this game --
> they just got added as needed as we kept pushing the concept of enemies
> to the back burner so we could get other features.
>
> We need to approach this with purpose.

> I want phase 1 to just be a discovery/discussion/planning phase. I want
> the universe to be rich and that includes enemy design.

Rulings:

- Doc 48 owns the WHOLE enemy roster: ground specs, ship specs, capture
  interiors, fauna, machines, spawn tables, bands.
- Phase 1 = doctrine (discovery/discussion/planning only). It runs in
  `/refine-design` sessions, not `/implement-phase`; its output is
  settled SETTLED sections here plus re-cut build phases with briefs.
- Player species/class differentiation split to doc 49.
- The 2026-09-20 loadout-scaling seed survives as topic C input.

## The ecosystem audit (2026-09-22, code-anchored)

**Three ladders grew independently; none was ever designed as a layer.**

1. **Difficulty = spec swap only.** Bands pick WHICH row spawns, never
   what it wields. `TIER_POOLS` has bands 1-3; `_site_tier` clamps to 3,
   so the six `mission_tier=4` planets run the band-3 pool. All humanoid
   rows wield t1/t2 gear regardless of their own tier field. Band 4 does
   not exist.
2. **Faction strong in space, hollow on the ground.** Space-side each
   faction behaves (patrols scan, merchants flee, pickets converge).
   Ground-side everything combatant is pirate-tagged or a monster:
   `consortium_*` rows are `faction="pirate"`
   (`data/npc_chars/core.py:24,53`); merchant has ZERO ground rows;
   civilian is a ghost faction (one bystander row, no ships). Killing a
   merchant freighter's consortium crew RAISES merchant rep (kill deltas
   key off the crew's pirate tag, `faction.py:216-241`).
3. **Theme = intentional fauna + two borrowed drones.** Doc 11's biome
   system is the one deliberate roster work. The game owns exactly two
   machine specs (`sentry_drone`, `assault_drone`) and they serve dig
   bands, all five capture decks, "Militia watch drone" landmarks, AND
   the ancient-alien prison branded "ALIEN SECURITY"
   (`data/text/00_runtime.json:77,88`). No lore distinguishes ancient
   from contemporary machines. Doc 43's inhabitants are an open
   question — the double duty would deepen.

**Capture-deck crew map (every boarded interior funnels into pirate or
consortium rows regardless of hull faction):**

| Layout | Crew rows | Flown by |
|---|---|---|
| `scout_crew` | pirate_raider/rifleman | pirate_scout, **militia_patrol_light**, pirate_hound |
| `cruiser_crew` | pirate_raider/rifleman | pirate_raider, **militia_blockade, militia_patrol**, pirate_marauder |
| `frigate_crew` | pirate_raider/rifleman | pirate_captain, **militia_patrol_heavy**, pirate_warlord |
| `hauler_crew` | consortium (pirate-tagged) | merchant_hauler |
| `freightliner_crew` | consortium (pirate-tagged) | merchant_freighter, merchant_caravan |
| derelicts (generic `scout_a`) | pirate_raider/rifleman | "no crew" derelicts spawn pirates anyway |

Board a militia cruiser → fight pirates, militia pays +4 rep/kill
(`faction.py` militia kill delta). Net: the boarding layer (doc 40)
inherited the faction gap wholesale.

**Archaeology verdict (git + doc history):** intent lived in per-feature
docs (monsters→11, militia→06, city ambient→26, consortium→32,
captain→bounty doc); filler landed wherever a feature needed bodies
(ground pirates = renames of a doc-less prototype pair, `ea31d5a`; deep
trio hound/marauder/warlord = one Codebuff-generated commit `6341318`,
adopted retroactively by docs 39/40). The only whole-roster docs (34,
48) were both pending until this reframe; the one roster-wide rule
("fill behavior×attack×terrain cells, no stat-wall squads", doc 35 §8)
post-dates most of the roster.

**Roster counts (2026-09-22):** ground 13 rows — pirate-tagged 4
(incl. both consortium rows), monsters 7, civilian 1, militia 1,
merchant 0. Ships 15 — pirate 6, militia 4, merchant 3, neutral
derelicts 2, civilian 0.

**Incoherence + cleanup punch list (verified, rides a build phase):**

- Consortium = pirate reskin everywhere (no faction tables, pirate kill
  deltas, heat squads are pirate ships).
- Militia decks crewed by pirates; merchant decks by pirate-tagged
  consortium; rep math contradicts fiction.
- Glyph collisions: `consortium_enforcer` 'c' = `civillian_bystander'
  'c' (same context); militia_trooper 'M' = the map's Merchant Hauler
  glyph (cross-context).
- `civillian_bystander` typo (id + all 24 city population tuples).
- `PROC_C_POPULATION` defined twice (`city_npcs.py:376,393`) — first is
  dead data.
- `rock_scavenger` on prison floor 2 (desert fauna in a station prison).
- `pirate_raider` id exists in both registries (NpcCharSpec +
  NpcShipSpec) — works, but bare-id consumers are ambiguous.
- Faction vocabulary off-contract: "neutral" (derelicts) and ""
  (monsters) are not in `_ALL_FACTIONS`.

## Design values (user, 2026-09-22, verbatim — the doctrine's pillars)

1. "you learn an enemy by playing the game. but once you learn the enemy
   you recognize it clearly in game and know how to handle it"
2. "enemy scaling is something viable and usable. better stats, better
   gear, better tactics"
3. "just like ships -- ground enemies should be aggressive only based on
   your faction"
4. "ships need to follow a progression path too. for any enemy type that
   is space faring -- it should have clearly identifiable ship classes."
5. "the interriors of a ship should be populated with the correct
   enemies. interriors should always be hostile though, since to get on
   one you have to start combat and aggro it yourself"
6. "ancient alien tech needs to be a separate thing that is only used
   for ancient alien areas."
7. "themed monsters are in a better spot, but I think we can refine and
   expand the concept. we need a way to up the difficulty"
8. "easily extended system. we have more things we haven't gotten to
   yet. I want all this to be data driven and extensible. even down to
   the npc's char and color."

## SETTLED 2 (2026-09-22) — scaling is three axes

Value 2 supersedes the 2026-09-20 seed's loadout-only framing: scaling
means **stats AND gear AND tactics**. Answers open question 3 from the
original dump (stats: loadouts-only vs scaled) — stats scale too. The
mechanism questions (how each axis scales, where) are topic C work.

## SETTLED 3 (2026-09-22) — hostility + interior doctrine (direction)

- Ground aggression is **faction-based only** (value 3) — mirrors the
  space model; the broadcasting-ID sheet reads rep. Whether fauna stay
  `always_hostile` (presumably yes — non-sentient) is a topic A/F
  detail.
- Capture interiors are populated with **the hull's correct enemies**
  (value 5) — militia decks crewed by militia, merchant decks by
  merchant-side crews.
- Capture interiors are **always hostile** (value 5) — boarding is the
  player's aggression; crews fight regardless of faction rep. Whether
  kill rep deltas still apply (killing a boarded militia crew costs
  militia rep?) is a topic D detail.

## SETTLED 4 (2026-09-22) — the machine split

Ancient alien tech is a **separate authored thing, used only in ancient
alien areas** (value 6). The contemporary sentry/assault drones stop
doubling as alien security; alien machines get their own specs (names
PROSE GATE). Pre-answers doc 43's open inhabitants question — authoring
shape is topic E.

## SETTLED 5 (2026-09-22) — merchant/consortium clean separation

User, verbatim:

> I want to separate merchant and consortium cleanly. right now
> they're mingled together in a bit of a confusing way.
>
> Merchants: everyday joes just trying to make a living with honest
> work. they only work for consortium through layers of upper
> management without ever knowing it.
>
> Consotrium: the hidden corporate overlords pulling the strings
> behind the scenes. when you see consortium you know it's not just
> regular merchants.

Rulings:

- Merchant and consortium separate CLEANLY. The current mingling
  (consortium crews aboard merchant haulers, corporate flavor riding
  on trade content) is the bug this doctrine fixes.
- **Merchants are honest, ordinary working folk.** No corporate
  identity. Their ships' crews are their OWN people — everyday crew,
  not soldiers, not consortium. Merchant decks get honest-crew rows
  (names PROSE GATE; shape = Q10).
- **Consortium is the hidden corporate layer**: a real faction with a
  HIDDEN rep axis (no visible bar), unmistakable when encountered —
  "when you see consortium you know it's not just regular merchants"
  (visual identity = topic B). Encounters happen at corporate
  operations, never as "just merchants" (surface = Q11).
- The management-layers fiction (merchants serving consortium
  interests unknowingly) is plot/lore texture — candidate doc 42
  rumor substrate — NOT a mechanic unless ruled.
- Supersedes the audit-era option "merchant decks crewed by
  consortium security". SETTLED 3 stands, sharper: every deck crewed
  by the hull's own people.

## SETTLED 6 (2026-09-22) — consortium is a real faction (cybernetic, gated)

User, verbatim:

> I know there's lore that says it but that's because we had pirates
> so we threw pirates in so we could playtest. I want consortium to
> be a real separate faction. think -- enemies with overclocked
> cybernetic equipement. But still running in to them will be strictly
> gated. There's a part of the main quest where the consortium hunts
> you. How cool would that be if it were a new class of enemy you
> haven't encountered before instead of just a merchant ship with a
> pirate escort.

Rulings:

- Consortium fields its OWN specs — ground and space. The
  hired-pirate heat fiction ("the consortium hires pirates") is
  retired filler; the main-quest hunt becomes an encounter with a new
  enemy class, the showcase use case.
- Signature identity: **overclocked cybernetic equipment** — the
  combat flavor seed (stats/gear shape at brief time). Names PROSE
  GATE.
- Encounters are **strictly gated** — never ambient spawn-table filler;
  you meet consortium where the game deliberately places them (quest
  beats, corporate sites). Open detail (topic C): whether ambient dig
  bands may still field consortium guards or that violates the gate —
  folded into Q5.
- Replaces the audit-era "ground-only consortium" option. With
  SETTLED 5: hidden REP axis + real, unmistakable BODY.

Correction (same day, user, verbatim):

> note: overclocked is not a consortium adj. overclocked landed in
> the loot polish doc. it's a tier of quality. and it goes up to
> prototype. I just meant decked out in HIGH QUALITY cyber gear.

The signature is **cyber gear at high quality** — the doc-47 quality
ladder (base → modded → overclocked → prototype,
`data/quality.py` `QUALITY_TOKENS`), not an "overclocked" faction
adjective or row name. Consortium rows are distinguished by degree of
augmentation; their equipment rolls at the top of the quality ladder.
Whether cyber gear is a droppable player category or spec-side flavor
is Q15.

## SETTLED 7 (2026-09-22) — merchant difficulty is droids

User, verbatim:

> Yes, merchant crew doesn't need to be as kitted out as pirates.
> Maybe the way we distinguish difficulty with a well off merchant is
> through droid presence with the merchants?

Rulings:

- Merchant crews are LIGHT — honest workers, lighter gear than
  pirates, not a difficulty axis (no band scaling).
- The wealth dial is **security-droid presence**: a well-off
  merchant's deck carries more contemporary security droids alongside
  the light crew (SETTLED 4's contemporary side of the machine split).
  Droid complement authored per spec/deck — value 8 data.

## SETTLED 8 (2026-09-22) — civilian rep retired (the organization principle)

User, verbatim:

> yes, civilian rep makes no sense. civilians have zero organization.
> how do you have rep with just random folk? pirates have an
> unorganized system and guild through the bar. merchants are
> organized. militia is organized. civilian rep makes no sense.

Rulings:

- **Reputation requires an organization to hold the opinion.** Pirate
  (bar guild), merchant, militia, consortium qualify; civilians do
  not. The civilian rep axis is RETIRED; bystanders stay ambient-only
  city dressing.
- Honest-folk harm and the guild re-key, ruled the same day, verbatim:
  "yes, militia notices crime. yes, merchant rep should scale
  merchant pay, I didn't know civilian rep scaled merchant guild
  pay" — killing bystanders or merchant crew costs militia rep; guild
  mission-pay scaling re-keys from civilian to merchant. (The user
  was unaware it read civilian — further evidence for the
  retirement.) Save migration (dropping stored civilian keys) is a
  coherence-build-phase detail.

## SETTLED 9 (2026-09-22) — hidden rep v1: movers only

User, verbatim:

> What moves it: yes. we can go with your list here at the start.
> just to get it in the system and get knobs to tune.
> What it gates: I want to keep this part for later. Right now it
> gates nothing.
> What the player sees: No bar at first. I reserve the future decision
> of having a gate that allows the player to expose the bar.
> spoofed transponder: I think we're going to need to treat it like
> any other, yeah. just -- it's hidden on each spoofed transponder.

Rulings:

- **Movers adopted (v1 — knobs to tune):** direct encounters (killing
  consortium crews/specs and looting corporate sites move it down;
  serving corporate operations moves it up) plus the merchant ripple —
  sustained harm to merchant interests (murdered crews, taken cargo)
  slowly drops it; the ripple is slow and quiet, direct contact loud.
- **Gates nothing in v1.** The axis lands as state + movers; gating
  (the hunt thermostat, access locks) is a reserved future decision.
- **No bar.** Hidden presentation; a future diegetic gate may EXPOSE
  the bar (reserved).
- **Identity layer: uniform, no special case** — consortium rep lives
  on each identity sheet like any other faction, simply hidden per
  sheet ("it's hidden on each spoofed transponder"); a worn ID carries
  its own corporate standing.

## The faction matrix (topic A working table — settled vs open)

| Faction | Ground | Space | Rep axis | Settled identity | Open |
|---|---|---|---|---|---|
| Pirate | raider + rifleman (rename-legacy; three-axis scaling in C) + band-4 faces (Q17) | 6 specs today; class ladders in G | visible, starts −100 | the outlaw economy; organized through the bar guild; loses the heat-squad role to consortium (SETTLED 6) | band-4 faces; pirate-class kinship (doc 49) |
| Militia | trooper + organized strike/defender crews + a heavy-hitting row (lean: sniper, precision not explosive) — all PROSE GATE (SETTLED 10) | 4 specs (doc-06 intent, stands) | visible, starts +50 | the state's arm; notices crime (harming honest folk costs militia rep) | row shape at brief time; dig-band guard role (Q5) |
| Merchant | light honest crews (PROSE GATE) + security-droid wealth-dial | 3 specs (flee, don't fight — stands) | visible; guild mission pay scales it (SETTLED 8) | honest everyday folk; the trade economy; interests ripple to hidden consortium rep (SETTLED 9) | crew-row shape at brief time |
| Consortium | NEW cybernetic specs (PROSE GATE) | NEW hunter ships (PROSE GATE) | HIDDEN — movers-only v1, no gates, no bar; per-identity hidden standing | the corporate layer behind everything; strictly gated encounters; cyber gear = the existing armor cybernetics at high quality (SETTLED 11 — droppable, quality-rollable); rungs = authored bands, AUTHORED-ONLY exposure (SETTLED 12); the main-quest hunt is the showcase | spec roster + authored exposure beats (user-held plans); dig presence (Q5 — lean now "no"); gates + expose-the-bar (reserved); Act 2 / doc 42 substrate (reserved) |
| Civilian | bystander, ambient-only | none | RETIRED (SETTLED 8) | the population — no organization | — |
| Monsters (`""`) | 7 rows: contemporary drones + biome fauna + parasite | — | none (`always_hostile`) | biome system (doc 11, stands); contemporary-vs-ancient machine split (SETTLED 4) | fauna difficulty axis + expansion (F); ancient machines (E) |
| Neutral (derelicts) | — | 2 derelict specs | non-faction | stationary wrecks; the boarding loot path | vocabulary cleanup (punch list); derelict crews (D) |

## SETTLED 10 (2026-09-22) — militia ground doctrine; topic A closed

User, verbatim:

> Militia: organized strike/defender crews, well equipped, work
> together.

Rulings:

- Militia's ground identity: **organized strike/defender crews — well
  equipped, working together** (squad-coordination feel). Row shape
  (strike vs defender split, count, stats) at brief time; names PROSE
  GATE. The earlier disciplined-defender lean is subsumed: these are
  crews that fight as a unit.
- **Topic A is CLOSED** (SETTLED 5-10). The rep-inversion punch-list
  items ride the coherence build phase.

Addition (same day, user, verbatim):

> Militia should also have a heavy hitting row. Maybe not the same
> explosive force of pirate. maybe this is the sniper row.

Militia fields THREE rows: trooper, the strike/defender crew, and a
heavy-hitting row — lean: sniper (long-range precision), explicitly
NOT the pirate heavy's explosive profile. Names PROSE GATE; matrix
cell tuning at brief time.

## SETTLED 11 (2026-09-22) — cyber gear IS the existing armor cybernetics

User, verbatim:

> cybernetics is already a concept in game. it counts as armor and
> yes that means it can be dropped. Skip the leg armor heavy pads and
> equip cybernetic legs giving you + AP per turn.

Rulings (anchors verified same day):

- Cyber gear is the EXISTING cybernetic armor subfamily
  (`data/ground_armor/vests.py`): cybernetic_eyes (head, T3-T4+),
  cybernetic_torso (body, T4+), cybernetic_arms (hands, T2-T3+),
  cybernetic_legs (legs, T3-T4+) — with the dedicated bonus fields on
  `GroundArmorSpec` (`ap_bonus` / `hit_bonus` / `melee_bonus` /
  `hp_bonus`, `ground_armor/__init__.py:24-27`). No new equipment
  category; more pieces may be authored later as content.
- **Droppable, quality-rollable**: armor-category drops and the 47.x
  quality ladder (armor-family multipliers) apply as-is. The
  consortium signature = these pieces at high quality — and via 47.1
  kit drops, killing them can hand the pieces over. Answers Q15.

## SETTLED 12 (2026-09-22) — consortium rungs = authored bands; authored-only exposure

User, verbatim:

> consortium rings... authored encounter difficulty. yes. there's
> lots of things about the consortium and how they'll be exposed that
> are still just in my head. so keep it authored stuff only for now.

Rulings:

- The augmentation ladder maps to BANDS — authored encounter
  difficulty decides which rung you meet. Answers Q14.
- **Authored-only exposure guard:** consortium presence appears ONLY
  in authored content (quest beats, authored sites). Nothing
  procedural or systemic spawns them — the user holds unshared plans
  for how the consortium gets revealed, and no system may expose them
  ahead of that. Strengthens SETTLED 6's strict gate; the Q5 dig-band
  consortium lean is now effectively "no" (formal ruling stays in C2).

## SETTLED 13 (2026-09-22) — the type catalogs close (C1)

User, verbatim: "1 and 2: good as is."

Rulings:

- **PIRATE — three faces:** raider (stays; mixed melee/ranged
  opportunist) + rifleman (stays; becomes a real rifleman under the
  scaling mechanism) + heavy (NEW, PROSE GATE: slow, explosive, the
  band-4 face, fills the slow-heavy-hunter matrix cell). Answers Q17:
  existing specs scale AND one new face.
- **MILITIA — three rows** (SETTLED 10): trooper, organized
  strike/defender crew, heavy/sniper (precision, not explosive).
- **MERCHANT — one row + dial** (SETTLED 5/7): light honest crew
  (PROSE GATE); wealth scaling is the security-droid complement.
- **CONSORTIUM — the augmentation ladder** (SETTLED 6/11/12): rungs =
  authored bands, authored-only exposure, cyber gear = existing
  armor cybernetics at high quality.
- **C1 CLOSED.** Names, statblocks, matrix-cell tuning, rung counts =
  brief-time authoring.

## SETTLED 14 (2026-09-22) — the difficulty doctrine core (C2)

User, verbatim:

> 1. yes. this is good.
> 2. yes, we can name a family instead of a weapon in the spec. and
> then the difficulty t# tier rolls higher tiered weapons. ...
> 5. this sounds good.
> 6. ... I think quality items should be more likely on higher t#
> enemies at the minimum.

Rulings:

- **ONE band vocabulary** (answers Q5): planet `mission_tier` (1-4) =
  site band = equipment `tech_level` ceiling. `_site_tier` unclamped
  to 4; floor climb (`tier + floor - 1`) capped at 4. Band-4 dig
  pools are pirate/militia/monsters only — **consortium formally
  excluded** (SETTLED 12). Pool contents + densities = brief-time.
- **Family ladder confirmed** (answers Q16, Q18): specs name weapon
  FAMILIES in their pick lists; the band rolls the tier within the
  family (top-two-tier window weighted to the top — weights
  brief-time). No fixed `weapons=` lists survive; characterization =
  the family mix.
- **Quality rides band** (answers Q19; reverses the defer lean):
  higher bands roll higher quality more often — at minimum the
  equip-time KILL ladder and drop-time rolls shift toward rarer
  tiers with band ("at the minimum" — richer interplay may come
  later). Exact rates brief-time; economy watch in the build
  playtest.
- **One resolver at every spawn** (answers Q20): digs (site band),
  procgen mission dungeons (their tier), city ambient (planet
  `mission_tier`). Authored-layout `ENEMY:` markers stay fixed.
- **Bystanders exempt** (answers Q21).
- Tactics axis: v1 mechanism = pool composition + squad shape; the
  deeper ruling awaits the honest mechanics look (Q22, audit
  dispatched same day).

## SETTLED 15 (2026-09-22) — stats mirror the player system

User, verbatim:

> Stats need to better mirror player stats and player stat
> progression. how this looks, I don't know. maybe we look at
> effective level we want the bands to be at and use that to
> determine stat points to distribute? I don't know that NPC
> pilots/ground stats are fully used in the game mechanics yet. if
> they're not then we need to wire them up. An ace pirate pilot
> should have a high piloting skill just like an ace player pilot.

Rulings:

- **No flat multiplier table.** NPC stats derive from the PLAYER
  progression system: each band maps to an effective level; stat and
  skill points distribute by the same math players use. Level-per-
  band mapping + distribution shape = brief-time (needs the player
  progression curves as input).
- **Wiring state (verified same day; corrected by the tactics audit
  below):** ground stats ARE live — enemy reflexes feed hit math
  (`_rules_ground.py:378,393`), strength feeds damage
  (`_ai_ground.py:182`), `stamina//3` feeds HP
  (`_rules_ground.py:191`). **Pilot skills are ALSO wired** — the
  audit corrected an earlier truncated-grep claim ("no consumers"
  read from a cut-off result list): `_build_enemy`
  (`combat/_stats.py:275-279`) folds all three into live math —
  gunnery (+`ai_accuracy_bonus`) into `calc_hit_chance`
  (`_stats.py:144-180`); piloting (+`ai_dodge_bonus`) into defender
  dodge, the damage-quality glancing floor, AND enemy AP per round
  (`(60+piloting)/20`, `_stats.py:87-105`); engineering into
  `max_power` (its regen discount inert — enemy `shield_regen_rate`
  pinned 0). The ace pilot is already real: `deep.py`'s warlord
  piloting=38 buys AP, dodge, and glancing reduction. What REMAINS
  of the mirroring work: skills are hand-authored constants, not
  level-derived (the band→effective-level mapping above), and enemy
  resource ledgers are cosmetic (no ammo/power spent, never
  reloads).
- Scaling-eligible: pirate + militia faces. Merchant crew and
  bystanders exempt (SETTLED 7, Q21).

## SETTLED 16 (2026-09-22) — band composition rulings + the LOS-aggro doctrine

User, verbatim:

> 1. squad growth: spec defined. tier bands don't change squad sizes.
> 2. replacing with militia may have consequences in that the militia
> are highly likely to be non-aggressive. let's just make sure we're
> not making some delve bands that are real easy to make too
> peaceful.
> 3. confirmed, we can tune later after we finish balancing and
> polishing based off of playtest feels
> 4. yes, we can tune from the playtest. important bit is that we
> have the knobs.
>
> One thing to remember in all this for ground combat: Even if it's a
> squad you've confronted, player LOS is still the aggro mechanic.
> It's what feels natural. Other squad members can "hear" the fight
> if it's loud, sure. But that would mean they move to investigate
> (non-combat enemies do move between rounds) and can aggro if they
> get in LOS. We tried the ship system where aggroing a single ship
> in a squad aggros the whole squad and that just does not play
> naturally in dark cooridors.

Rulings:

- **Squad sizes are spec-authored; bands never scale them.** Pack
  feel comes from WHICH specs live in a band, not band-scaled squad
  math.
- **Hostile weight constraint:** a band's pool must carry enough
  hostile-for-typical-players faces that no delve band reads
  peaceful. The militia-backfill lean for the consortium seats is
  WITHDRAWN — militia start liked (+50) and mostly won't fight;
  their pool presence stays the SETTLED 39 flavor face
  (fight-or-step-aside), never the difficulty carrier. Exact band
  re-author (pirate/monster weighting) at brief time.
- Densities 1.0/1.4/1.8/~2.2 confirmed; uniform pool proportions
  confirmed — both tuned from playtest; the knobs are the point.
- **THE GROUND AGGRO DOCTRINE (binding on every tactics idea):**
  player LOS is THE aggro mechanic — it is what feels natural. Noise
  may cause un-engaged enemies to INVESTIGATE (out-of-combat movement
  toward the sound), aggroing only on LOS acquisition. Collective
  squad aggro — the ship system, where aggroing one member aggros
  the wing — is explicitly REJECTED for ground: "does not play
  naturally in dark corridors." Ship-style collective aggro remains
  space-only.

## SETTLED 17 (2026-09-22) — combat-time movement + the noise system

User, verbatim:

> a. yes - uniform combat-time ap movement. but move ap tiles until
> they're in LOS. if they have 4 AP and in 2 AP they are in LOS,
> then it stops and they join combat.
> b. yes. but also explosives probably need to emit a noise at where
> it explodes?

Rulings:

- **Two movement modes, uniform (no special cases):** peace time —
  everything moves 1 tile per tick (the stroll); combat time (any
  live fight on the map) — every un-engaged entity moves its AP in
  tiles.
- **Stepwise LOS acquisition:** the approach checks LOS after EACH
  tile; the moment an entity sees the player it STOPS and joins the
  engaged set mid-approach — investigators never overshoot past LOS.
  Composes with per-spec AP (ladder #8): a 6-AP predator hearing a
  fight arrives fast.
- **The noise system (minimal, diegetic):**
  - Per-weapon `noise` radius as a data column (value 8 — data-driven,
    tunable). Firing emits at the shot's origin. Loudness sketch:
    rockets/grenades 10-12, rifles 8, pistols/SMGs 5-6, melee 1-2
    (knife kills stay quiet — a real tactical choice); a flavor lever
    exists (lasers near-silent vs kinetic loud), tuned at brief time.
  - **Explosives emit TWICE** (user addendum): the firing report at
    the shooter AND a blast event at the impact cell — the blast
    draws entities from where it LANDS, not where it was fired.
  - Hearing = flat radius check; sound ignores walls (one room over
    draws, two away doesn't). No attenuation/propagation sim — add
    only if the playtest begs.
  - Heard ≠ aggroed, ever (SETTLED 16): the heard entity gains an
    investigate attractor at the sound's origin, moves at combat-time
    AP, aggros only via LOS. Reuses the last-seen machinery pointed
    at a noise instead of a disengagement.
- This settles ladder item #4's design ahead of the walkthrough.

## SETTLED 18 (2026-09-22) — guard-artillery + leash + range management (ladder #2)

User, verbatim:

> for 3 -- maybe this is for ladder 7, shouldn't enemies try to move
> within their ideal range for the weapon they are using? I know
> that's what I try to do as I fight them.
> for 4. leash should maybe match max range of their current weapon?
>
> this is good. on to 3

Rulings:

- **Cell ownership:** drones carry ambient guard-artillery (sentry
  band 1, assault bands 2-3 — the armored anchor); humanoid
  guard-artillery lives in AUTHORED content — the consortium gunner
  at corporate sites, the militia sniper as a guard (perched,
  holds sightlines, precision — SETTLED 10's doctrine, minus the
  chasing). Pirate stays three faces; no fourth face minted.
- **The heavy is a slow hunter** (the slow-heavy-hunter cell): it
  comes to you, ponderously.
- **Leash = weapon max_range + 2**, derived per instance from the
  rolled weapon — authority is reach plus reposition room; snipers
  get big kingdoms, pistol guards small ones; the hardcoded 8 dies;
  the just-outside-range dead zone (plink a short-gunned guard
  forever with zero response) is designed out.
- **Range management is the universal principle** (ladder #7's
  settled shape, arrived early): enemies move to their weapon's
  ideal band — too far, close; too close, back off; in band, hold
  and fire. The mirror of player kiting ("I know that's what I try
  to do as I fight them"). The hug-a-rifleman exploit is the missing
  half, not a special case. Detail lands at ladder #7.

## SETTLED 19 (2026-09-22) — all six skills + full-kit resource-aware space AI

User, verbatim:

> just to be clear: "pilot skills fully live" -- I mean all 6
> skills. NPCs should have all 6 skills. So even in ground combat
> their 3 ground skills shape their difficulty.
> 2. no -- we need ships using their full kit. we're supposed to
> feel like we're fighting others in the same kind of ships that we
> are in. the AI needs to look at all the factors, range, AP, energy,
> shields. and make decisions on how to spend each resource. This is
> much more complicated than now, but it will make space combat so
> much deeper. Get the edge on them draining their shields and now
> they're not firing as much because they have their energy going to
> shield regen.

Rulings:

- **All six skills on every NPC** (extends SETTLED 15): the 6-block
  — gunnery/piloting/engineering + reflexes/strength/stamina — is
  the universal character model; each theater's difficulty derives
  from its three. Band→effective-level derivation distributes
  across the full block.
- **Full-kit, resource-aware space AI RULED IN.** Enemy ships use
  their whole weapon kit and decide how to spend AP, energy, and
  shields through the same systems the player flies: "we're supposed
  to feel like we're fighting others in the same kind of ships that
  we're in." Design north star, user's example: drain their shields
  → they divert energy to regen → they fire less. Supersedes the
  weapons[0]-only acceptance in ladder #3; the cosmetic enemy
  ledgers (SETTLED 15's remainder) become real systems — energy
  pools, authored shield-regen rates, per-weapon costs.
- **Boundary change:** resource-decision AI enters THIS campaign's
  territory (the old "space AI behavior OUT, doc-34" boundary no
  longer holds for it). Whether doc-34's movement verbs (kiting,
  fleeing) fold into this design or stay separate = open (Q23).
- Mechanics land only after the space-systems audit (dispatched same
  day): the PLAYER-side economy is the mirror target — every
  spendable, rate, and dial an enemy AI must learn to spend.

## SETTLED 22 (2026-09-22) — noise detail confirmations (ladder #4)

User, verbatim: "Yes, #4 is good."

Rulings (SETTLED 17's design confirmed in detail):

- **Emitters are symmetric:** both sides' weapon fire emits at origin
  per the weapon's noise column, plus the blast event at impact
  cells — third parties converge on the fight, not on a side.
  Movement/waiting never emit.
- **No cap, latest-wins:** the radius is the only limiter (tuned per
  weapon); engaged entities ignore new noise; investigators re-target
  to the newest sound.
- **Combatants only hear:** hostile-reading monsters and NPCs gain
  the investigate attractor; dormant security stays deaf (authored
  activations remain the only wake trigger); non-hostile-reading NPCs
  ignore gunfire. Ladder #4 CLOSED.

## SETTLED 23 (2026-09-22) — the aggressiveness dial's semantics (ladder #5)

User, verbatim: "this is good as is. all sounds logical."

Rulings:

- **One dial, one job: fire-vs-reposition.** When in weapon band with
  LOS (both firing and moving legal), `ai_aggressiveness` (10-90,
  already authored) weights the choice: aggressive ships fire every
  affordable AP (damage-tanks — sitting still forfeits movement
  dodge); low-aggression ships reposition within the band
  (dodge-tanks stacking +5%/cell at damage cost). The existing
  movement-dodge economy does the balancing.
- **Regen is never touched by it** — regen stays state-driven
  (shields low + power available). Personality and survival each get
  one clean input; if cowardly-regen ships are ever wanted, that is
  a separate authored field.
- Authored 10-90 values come alive as-is; no re-authoring.
- The band-maintenance guard (ported note 1, SETTLED 21) owns the
  high-piloting-dancer risk; aggressiveness is the per-spec knob.
- **Space-only** — ground personality stays the `behavior` field's
  job. Ladder #5 CLOSED.

## SETTLED 24 (2026-09-22) — ladder #6 withdrawn (the disengage mechanic already does it)

User, verbatim:

> hmm. but if you break LOS you break combat don't you? doesn't all
> this just happen to work right now because of that simple mechanic?

Verified — the user is right. Ground `combat_should_end` is pure
player-LOS (`_rules_ground.py:945-957`): the fight ends the round no
hostile is in view; survivors get the last-seen stamp
(`on_disengage`) and investigate where LOS broke for 5 ticks, then
revert to post/patrol, re-triggering via normal LOS aggro. The
break-LOS-to-escape play already works. **The in-combat memory-chase
proposal is WITHDRAWN** — no new pursuit machinery.

Residual (narrow, left as-is unless ruled otherwise): mixed
visibility — while the player still sees ONE hostile the fight stays
live, and an unseen squadmate's chase goal is the player's live
position (pathing "through walls" until it turns a corner and
becomes visible). Brief window, judged not worth machinery.

Open detail surfaced by this step: SETTLED 17's movement modes key
on "any live fight" — after disengage there is no fight, so
investigating survivors move at the 1-tick peace rate (today's
tuned behavior, 5 ticks ≈ 5 tiles). If hotter post-disengage
pursuit is wanted, the mode boundary extends to "or any entity
holds an active memory/attractor" — one-line change, awaiting
ruling.

## SETTLED 25 (2026-09-22) — movement modes confirmed; post-disengage folds to ambient

User, verbatim:

> right. once an enemy leaves combat it just gets folded in to the
> systems already in place. so if you're in combat with nothing,
> back to 1 tile movement. if you're still in combat, then it follow
> in combat non-aggrod movement rules

Rulings:

- **The mode boundary stands as SETTLED 17 wrote it** — keyed on
  "any live fight on the map": during a live fight, un-engaged
  entities (investigators included) move at AP; once the fight ends,
  everything folds back into the existing ambient systems (1-tick
  movement, memory investigation, posts). No extension to
  memory-holders; closes SETTLED 24's open detail.

## The tactical mechanics audit (2026-09-22 — grounds the Q22 ruling)

**Ground AI:** exactly three behavior verbs (hunter/guard/ambusher),
and the differences live mostly OUT of combat — hunter patrols,
guard holds a persisted post, ambusher is stationary with a
"bursts out" log line. IN combat one universal loop serves everyone
(`combat/_ai_ground.py:65-104`): fire if in range+LOS (max one shot
per turn), else A* one tile toward the player — pursuit is
omniscient (paths to the live position; LOS only gates firing).
Guards alone branch, via the leash (chase only within 8 of post).

- **Last-known-position memory EXISTS, out-of-combat only**: stamped
  at disengage (`on_disengage`, `_rules_ground.py:933-943`) so
  survivors investigate where the fight broke; hunters then path to
  the remembered cell for 5 ticks (`ground_npcs.py:229-282`). No
  IN-combat memory — mid-fight the AI reads the live position.
- **Aggro = the player's own vision** (`_encounter.py:336-347`,
  sight_radius 8, symmetric by design); NO propagation — one
  alerted enemy alerts nobody; `noise_hostiles` is a wired EMPTY
  stub, the single OR-in seam for gunfire-drawn mobs
  (`_encounter.py:244-265`). `detect_radius` on NpcCharSpec is DEAD
  data (no consumer).
- **Squads move together only out of combat** (`_move_squad`); in
  combat every enemy runs the independent loop. Pack feel is
  emergent bodies, not coordination.
- **AP hardcoded 4 for every enemy** (`_rules_ground.py:204`); one
  shot/turn; infinite ammo, never reloads (the player's reload
  economy has no enemy mirror). No trait verbs exist on enemies
  (charger/deadshot are player-only).
- **Live exploit:** an enemy inside its own weapon `min_range` can
  neither fire nor retreat — hugging a kinetic rifleman (min 2)
  shuts him down completely.
- No cover/chokepoint/door logic in AI; movement is plain A*.

**Space AI:** per-enemy loop (`combat/_ai.py:80-113`): advance while
beyond `ai_preferred_range` or no LOS, else fire — multi-fire and
move+fire mix allowed; first weapon only; fights run to destruction.
`ai_preferred_range` (0-4) is the ONLY behavioral differentiator
between specs. `ai_aggressiveness`/`ai_flee_threshold`/`comms_range`
confirmed dead. Pilot skills fully wired (SETTLED 15 correction);
enemy power/ammo ledgers cosmetic. Squad trigger IS collective
space-side (any member's detection pulls the wing;
`navigation_combat.py:125-130`); in combat, zero coordination — one
target, each ship independently closes.

**The proposal seeds (each tagged BUILT = data-only today /
CHEAP = primitive exists, needs wiring / NEW = new mechanics):**

1. BUILT — band pack-composition pressure (already v1, SETTLED 14).
2. BUILT — guard-artillery faces: guard + long rifle holds a room at
   8 tiles, leash guarantees no chase (band 2+).
3. BUILT — space brawler (preferred_range 1 + high piloting + short
   heavy gun) and artillery (preferred_range = weapon max) as pure
   data on the live loop.
4. CHEAP — noise aggro: fill the `noise_hostiles` stub; gunfire
   draws mobs within a band-scaled radius. Converts squad linkage
   from none to gunfire-mediated; loud fights snowball.
5. CHEAP — revive `ai_aggressiveness` as per-AP attack-vs-reposition
   (~10 lines in `_take_enemy_turn`): juking ships. NOTE: this is
   doc-34 territory (space behavior verbs) — boundary call.
6. CHEAP — in-combat last-seen memory: stamp the existing primitive
   on LOS loss and chase the memory, not the live position.
   Band-independent fairness change — breaking LOS starts working.
7. NEW — ranged back-off step (step toward max_range when target
   inside min/half-range): fixes the inert-rifleman exploit AND
   mints skirmishers. Small.
8. NEW — per-spec ground AP field (fast predators 6 AP, bruisers 3):
   trivial diff. Space flee is NOT cheap (combat runs to victory;
   no disengage machinery) — stays out with doc 34.

**Audit flags:** door walkability for enemy A* unverified; the
gunner's inline comment cites "doc 34" for the ground behavior
matrix but the ground rule lives in doc 35 §8 (comment mislabel);
enemy power regens with no spender found.

## SETTLED 20 (2026-09-22) — fleeing is not a thing in space combat

User, verbatim: "Fleeing is not a thing in space combat."

Rulings:

- **In-combat flee is RULED OUT.** Space fights run to their
  conclusion — death or boarding. No flee decision, no flee
  behavior, no escape-outcome machinery will be built; the
  encounter system keeps its single outcome family.
- `ai_flee_threshold` retires as dead data (coherence build phase):
  nothing reads it today and nothing ever will. Out-of-combat map
  avoidance (merchants steering away from nearby pirates) is not
  fleeing-in-combat and stays as-is.
- Closes Q23's second call. Doc 34's disposition question (fold its
  remaining scope into 48 vs leave it in `future/`) stays open — its
  brawler/artillery verbs arrived via data (ladder #3), resource AI
  via SETTLED 19, retreat-to-band rides Tier 1's range management,
  and flee — its last unclaimed piece — is now ruled out entirely.

## SETTLED 21 (2026-09-22) — tiering confirmed; no-reinforcement doctrine; doc 34 folded

User, verbatim:

> 1. yes, that's fine.
> 2. mid-fight reinforcements aren't a real thing. other ships flying
> by can aggro you and join in combat. but there is no reinforcement
> mechanic.
> 3. I guess we're doing this doc now but way more detailed. yes,
> fold its remaining scope in to 48. I didn't realize what this
> doc 34 you kept mentioning was.

Rulings:

- **Tiering confirmed (closes Q23's core):** Tier 0 = parity wiring
  (hull-catalog stats, module effects + honest costs, per-weapon
  AP/power/ammo, authored shield-regen rates) as its own build phase
  and playtest; Tier 1 = the decision loop (fire best affordable /
  regen when hurting / move to preferred band;
  `ai_aggressiveness` = fire-vs-reposition bias). Decision-loop
  internals are brief-time.
- **The no-reinforcement doctrine:** there is NO reinforcement
  mechanic and none is built. Mid-fight joins are ambient ships
  flying by and aggroing through normal detection. The audit's
  joiner flag is reframed as a Tier-0 verification: whatever code
  constructs a joining ship must carry THAT ship's own spec/hull —
  player-catalog + cloned-player-skill construction, if real, is a
  bug to fix, not a mechanic.
- **Doc 34 folded into this campaign; file removed.** (History: doc
  34 was a deferred first-pass from the 2026-09-03 Wolf 359 playtest
  proposing space behavior verbs; seeded this campaign's whole
  tactics thread.) Its verbs and dead fields are all dispositioned
  above; its four unclaimed design questions port into Tier 1:

  1. **Band-maintenance AP economics** — does a high-AP ship
     retreating to its preferred band simply stay away forever?
     Range management needs a tuning guard.
  2. **Counters must be tactical, not loadout-only** — if every
     answer is "buy missiles," that's stats, not tactics.
  3. **In-combat coordination** — escort/guard interplay (an
     artillery ship defending a leader) — open; solo verbs may
     compose well enough.
  4. **Cover near spawns** — LOS-baiting only matters if encounters
     place near planets/stations; encounter-placement work, possibly
     bigger than the AI itself.
  (Missile interception stays out — 34 flagged it "needs its own
  pass" and nothing here claims it.)

## The space-systems audit (2026-09-22 — grounds the Q23 ruling)

**The player's economy is a three-resource turn**: AP (fractional
carry, wired identically both sides), power (hull + module
generation; two sinks — energy/plasma shots and the paid S-dial
shield regen with engineering discount), shields (module-built max +
paid dial + free module recharge), finite missiles, positional
dodge/range bands. Full weapon cost table + hull table in the audit
record (six hulls — Skiff exists beyond the five).

**The mirror is half-built (the headline):**

- `EnemyInstance` carries fields for ALL of it; `start_enemy_turn`
  contains the paid-regen power spend VERBATIM but unreachable
  (`shield_regen_rate` pinned 0, `combat/_actions.py:437-445`).
- The enemy `weapon_ammo` dict is built and never read — infinite
  missiles. Enemy power fills and is never spent on weapons.
- **Enemy modules are half-honored**: shields-from-modules wired
  (the ONLY enemy shield source); reactor `power_gen`,
  `targeting_computer` gunnery, and `gyro` piloting all UNWIRED —
  the hound's gyro and the militia targeting computers are
  decorative today.
- **Enemy hulls are half-honored**: hull HP yes, but no base
  shields/recharge/power — an enemy Cruiser flies WITHOUT its hull's
  25 shields, 3 recharge, 5 power (`NpcShipSpec` lacks the fields).
  "The same kind of ships we're in" is currently false at the stat
  layer.
- The AI reads almost none of it: advance + `weapons[0]` at a flat
  1 AP (a 2-AP plasma costs the enemy 1); no power/ammo checks, no
  weapon choice, no regen, no EMP-strip decision.
- `ai_aggressiveness` / `ai_flee_threshold` re-confirmed dead.

**Audit flags:** mid-fight reinforcement joiners are built from the
PLAYER's hull catalog and cloned player skills
(`_rules_space.py:765-788`) — joiner stats may not match their spec;
`buy_ammo` does not update `cargo_ammo` (observed inconsistency,
out of scope — punch list). Both to the punch list.

## Phase-1 discussion map (DRAFT — the planning agenda)

Seven topics; each becomes dated SETTLED sections, then the build phases
re-cut with briefs. Order: A (closed) → **C next** (D's crew tables
draw from C's row catalogs) → D → E → F → G → B.

- **A. Faction matrix** — CLOSED (SETTLED 5-10; see the working table
  above): consortium real + hidden + cybernetic + strictly gated,
  hidden rep v1 movers-only, honest merchant crews with a droid
  wealth-dial, civilian retired on the organization principle,
  militia notices crime + organized strike/defender crews, guild pay
  re-keys to merchant. Rep-inversion punch-list items ride the
  coherence build phase; dig-pool consortium presence rides Q5.
- **C. Roster catalogs + difficulty doctrine** — promoted 2026-09-22
  (the user asked where NPC scaling + per-faction NPC types live; the
  catalogs were implicit brief-time detail, now explicit). **C1, the
  type catalogs: CLOSED (SETTLED 13).** **C2, how everything
  scales:** ONE band vocabulary (mission_tier = tech_level = dig
  band, extended to 4), the three axes (SETTLED 2) and where each
  applies (digs, dungeons, cities, ships). **C2 core CLOSED (SETTLED
  14-15)**; the tactics ruling awaits the Q22 audit.
- **D. Crew & interior coherence** — SETTLED 3's details: crew tables
  per hull (drawn from C1's catalogs), always-hostile interiors,
  kill-delta handling, what crews derelicts carry.
- **E. Machine split** — SETTLED 4's details: alien-machine authoring,
  which areas count as ancient, doc 43 handoff.
- **F. Monster refinement** — value 7: refine/expand the biome concept;
  a difficulty axis for fauna (bigger-fauna bands? new rows,
  prose-gated).
- **G. Ship progression** — value 4: identifiable class ladders per
  spacefaring faction; themed modules per hull (the 2026-09-20 seed
  addendum folds in here — capture strips whatever the spec flies, so
  authored modules become capturable loot with zero new mechanics).

## Later-phase topics (user, 2026-09-22, verbatim)

- "civilian rep. where did it even come from? I never green lighted
  this. it must have snuck in to a design doc at some point and escaped
  my review. is there a need for it?"
  - Archaeology answer (2026-09-22): civilian entered as one of the four
    original factions in doc 01 Phase 1 (`f8d2f98`, 5-zone attitudes +
    starting rep) and as a planned `civilian_transport` ship class in
    `DESIGN_NPC_SHIPS_COMMS.md` (never built — zero ship rows). A later
    commit scrubbed "spurious civilian/militia deltas" from delivery
    missions (`cb4f779`). Whether it EARNS its rep bar is a topic A
    ruling.
- "consortium rep. what if we had a hidden rep. and it was the
  consortium. the corporate overloads running things behind the scenes.
  might be worth it's own design doc, but I'd like to explore this
  concept in the roster revamp."
  - Explored in topic A — SETTLED 5 made it real + hidden, SETTLED 6
    gave it the cybernetic body and the hunt showcase; mechanics in
    Q12. If it grows beyond the roster it spawns a dedicated doc.

## The 2026-09-20 seed (preserved verbatim)

> Alright, before we refine phase 3, let's dump a new design doc:
> enemy polish. we need better enemies that scale with difficulty.
> If I'm in a t4 delve, I should be going against pirates with
> monoblades and rocket launchers.

> I agree with you that we need more detailed ship specs that
> have modules installed that make sense for them and their hull.
> Capturing a pirate ship would definitely be a solid path to
> finding a smugglers hold. Capturing a merchant would be a solid
> path to finding a cargo hold.

## The scaling audit (2026-09-20, code-anchored — feeds topic C)

- Humanoid fighters are ~6 `NpcCharSpec` rows; every one wields t1/t2
  gear regardless of spec tier: raider/enforcer/militia pick from
  `(combat_knife, kinetic_pistol)`; gunner and rifleman carry a fixed
  `kinetic_pistol` — the rifleman is a tier-2 spec with a t1 weapon and
  no rifle. Resolution is `RNG.choice(weapon_pick)` at spawn
  (`combat/_rules_ground.py:189-190`).
- `NpcCharSpec.tier` gates DROPS only (`tier_filtered_equipment`,
  `ground_equipment.py:72`); it never touches the wielded weapon.
- Catalogs already carry the full ladder: weapons t1-t4 (t4 = rocket
  launcher, mono blade, power fist, plasma caster, railgun, ion
  blaster), armor to t4. The catalog files ARE families (melee
  knife→baton→vibroblade→mono blade/power fist; rifles shotgun→kinetic
  rifle→battle rifle→railgun/ion blaster; explosives t3-t4 only).
- Doc 47 wired the diegetic consequences: the wielded weapon always
  drops and rolls quality at NPC equip time — scaled loadouts scale
  loot automatically; the economies are one system.
- Stats (`hp`, `reflexes`, `strength`, `armor`) are per-spec authored
  constants — now ruled a scaling axis (SETTLED 2).
- Authored-layout `ENEMY:` markers pin fixed spec ids.

**Warts:** difficulty invisible in the enemy's hands; the t4 equipment
band exists but almost nothing wields it; the guide already promises
"deeper sites and tougher machines yield better gear" (true today only
via spec swap + drop gates); rifleman breaks its own name.

## Open questions

Doctrinal (phase-1 topics):

1. ~~Consortium: fifth faction, pirates-on-contract, or hidden rep?~~
   ANSWERED — SETTLED 5: real faction, hidden rep axis, clean
   merchant separation.
2. ~~Civilian: keep as a rep bar, fold into ambient-only, or retire?~~
   ANSWERED — SETTLED 8: retired; rep requires an organization.
3. ~~Merchant ground presence: crews of their own,
   consortium-as-crew, or none?~~ ANSWERED — SETTLED 5: honest crews
   of their own; row shape is Q10.
4. Fauna under value 3: stay `always_hostile`, or do biome sites get
   faction flavor?
5. ~~Band vocabulary~~ ANSWERED — SETTLED 14: one ladder
   (mission_tier = site band = tech_level ceiling), unclamped to 4;
   consortium excluded from ambient pools.
6. Alien machines: authoring shape, which areas count as ancient, doc
   43 handoff.
7. Recognition identity: which glyph/color scheme per enemy; where it
   lives in data (value 8).
8. Extensibility: what is still code that should be data (spawn
   tables? bands? crew wiring?) so a new enemy is a new data row only.
9. Interior kill deltas: does killing a boarded (hostile-by-boarding)
   crew move rep as today?
10. ~~Merchant crew shape~~ ANSWERED — SETTLED 7: light crews, fixed
    light gear, no band scaling; the wealth dial is security-droid
    presence.
11. ~~Consortium encounter surface~~ ANSWERED — SETTLED 6: own specs
    ground + space, cybernetic identity, strictly gated encounters;
    the main-quest hunt is the showcase; dig-band presence rides Q5.
12. ~~Hidden consortium rep mechanics~~ ANSWERED — SETTLED 9: movers
    adopted (direct encounters + merchant ripple); gates NOTHING in
    v1 (reserved); no bar (a diegetic expose-gate reserved);
    per-identity hidden standing on the identity layer.
13. ~~Honest-folk harm + guild re-key~~ ANSWERED — SETTLED 8
    (same-day amendment): militia notices crime; guild mission pay
    re-keys to merchant.

14. ~~Consortium rungs: bands or escalation tiers?~~ ANSWERED —
    SETTLED 12: authored bands; authored-only exposure guard.
15. ~~Cyber gear: new category or flavor?~~ ANSWERED — SETTLED 11:
    the existing armor cybernetics subfamily — droppable,
    quality-rollable, no new category.

Scaling (topic C — carried from the 2026-09-20 dump; original 3 and 6
answered by the design values; renumbered 16-21 to clear the collision
with doctrinal 10-13):

16. ~~Mechanism~~ ANSWERED — SETTLED 14: the family ladder — specs
    name families, bands roll the tier.
17. ~~Band-4 faces: existing specs with better kit, new rows, or
    both?~~ ANSWERED — SETTLED 13: both — raider/rifleman scale, the
    heavy is the new band-4 face.
18. ~~Fixed `weapons=` lists~~ ANSWERED — SETTLED 14: none survive;
    everything resolves by family + band.
19. ~~Quality floors by band~~ ANSWERED — SETTLED 14: quality rides
    band (user reversed the defer lean — "at the minimum").
20. ~~Site scope~~ ANSWERED — SETTLED 14: one resolver at every
    spawn; authored ENEMY: markers fixed.
21. ~~Bystanders~~ ANSWERED — SETTLED 14: exempt.
22. Band-scaled tactics: audit LANDED (the tactical mechanics
    audit above). v1 = pool composition + squad shape (SETTLED 14);
   the ladder walkthrough is mid-flight (SETTLED 16-18: composition
   + LOS doctrine, noise + combat-time movement, guard-artillery +
   leash + range management; SETTLED 17 pre-settled noise aggro).
23. ~~Full-kit resource-aware space AI~~ ANSWERED — SETTLED 19
    (ruled in), the space-systems audit (above) grounds it, SETTLED
    21 confirms the Tier 0 / Tier 1 split and folds doc 34.
    Decision-loop internals + the four ported design notes are
    brief-time.

## Phases

- [ ] 1. **Doctrine — discovery/discussion/planning** — the seven
  topics A-G above, settled with the user in `/refine-design` sessions;
  build phases re-cut with briefs at close. No implementation.
- [ ] 2+. **Re-cut at phase-1 close.** Candidate order (DRAFT, to be
  ruled): coherence + cleanup (crew correctness, consortium tag, punch
  list) → band vocabulary + three-axis scaling → ancient machines →
  monster expansion → new faces (behavior-matrix cells, PROSE GATE) →
  ship class ladders.

## REVIEW — phase 1 checkpoint (planning phase; no in-game items)

1. Every topic A-G carries a dated SETTLED section (or an explicit
   deferred note with a home).
2. Build phases re-cut from the settled doctrine; each proposed phase
   has an Implementation brief ready for approval.
3. Doc 43's inhabitants question pre-answered by the machine split (or
   explicitly handed to 43).
4. Doc 49 consulted wherever the faction-matrix rulings change the rep
   interlock.
5. The cleanup punch list is assigned to a phase.
6. SYSTEMS.md untouched until build phases land (inventory updates at
   phase closes, per contract).

## Acceptance criteria (DRAFT)

- The roster reads as designed: every enemy has a faction home, a
  recognizable identity, and a place in the difficulty ladder.
- Site difficulty reads in the enemy's hands before the first punch
  lands — stats, gear, and tactics all scale.
- Interiors are crewed by the hull's faction and are hostile on
  boarding; rep math matches fiction.
- Ancient alien content is its own authored thing, used only in
  ancient areas.
- Adding an enemy is a data edit: spec row (+ optional pool/crew
  wiring), never a code change.
- The 47.x loot systems absorb everything with no new payload shapes.

## Philosophy alignment

| Guardrail | How this doc obeys it |
|-----------|----------------------|
| No special cases — uniform mechanisms | One band vocabulary, one hostility model, one resolver (topic C's mechanism) |
| Data-first | Bands, pools, crews, identities, class ladders live in data specs; extensibility is value 8 |
| Knowledge gates access, not existence | Gear/roster exist; bands gate who wields/meets them |
| Diegetic economy (47.1/47.2) | Scaled loadouts drop scaled loot through the existing kit-drop path |
| Behavior×attack×terrain (stored ruling) | New faces fill matrix cells, never stat walls |
| Prose gate | New spec names / any strings land only post-approval |
| Uniform hostility model | Ground mirrors space: faction rep decides (SETTLED 3) |
