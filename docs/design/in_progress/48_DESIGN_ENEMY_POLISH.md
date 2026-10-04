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
(complete/ — player identity, interlocks via the faction rep
tables);
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
| Monsters (`""`) | 7 rows: contemporary drones + biome fauna + parasite; ancient: Watcher/Custodian/Warden (SETTLED 29) | — | none (`always_hostile`) | biome system (doc 11, stands); machine split (SETTLED 4/29) | fauna difficulty axis + expansion (F) |
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

## SETTLED 26 (2026-09-22) — universal ground range management (ladder #7)

User, verbatim: "7 is good."

Rulings:

- **The band is the weapon's own data** [min_range…max_range]:
  beyond max, close (1 A* step per AP); in band, hold and fire;
  inside min, **back off** — AP spent reaching the nearest cell that
  restores ≥ min_range, preferring LOS-keeping steps.
- **Cornering is the counter-play, by design:** open ground lets
  ranged faces skate away; pinned against a wall with no in-band
  cell, a ranged enemy is inert. The hug-a-rifleman exploit becomes
  a chase you must win.
- **Leftover AP after the one-shot cap goes to repositioning** — the
  skirmisher dance emerges from band + AP budget (no skirmisher
  flag). One-shot-per-turn cap unchanged.
- **Melee untouched by construction** (claw band [1…1]: adjacency is
  always in-band — no back-off, no knife-dancers).
- **Uniform across behaviors; leashes compose and win** — a guard's
  retreat drifts toward its post; beyond the leash (weapon max + 2,
  SETTLED 18) the post goal takes precedence.
- Space-side range management is Tier 1's move decision (SETTLED
  21); this ruling is ground-only. Ladder #7 CLOSED.

## SETTLED 27 (2026-09-22) — per-spec AP + enemy gear/consumable parity (ladder #8 — LADDER CLOSED)

User, verbatim:

> Yes, AP should default to 4. I think right now the only way to
> change AP in game is cybernetics or combat stims.
> So the question is ... for non-humans, should AP be different? I
> think for humans AP should be 4 + modifiers that exist. Later on
> we might decide that certain armor gives -AP. And in that case,
> when we add that feature, it should wrap in to the modifiers
> calculation and just work with enemies too. But I don't want to
> throw -AP on to armor yet. Later.
> But yes, AP should be a spec field. And wearing cybernetics should
> change the enemy accordingly. Should enemies be able to use combat
> stims if they have them? I don't see why not. In DCSS enemies can
> zap wands/etc. Enemies should be able to use consumables if
> they're carrying them.

Rulings:

- **AP is a spec field, default 4.** Humans: base 4 + existing
  modifiers (today: Ace Pilot trait +1 — the third modifier beyond
  cybernetic legs and stims — plus cybernetics' `ap_bonus`, plus
  stims' temp +1). **Non-humans: authored base** — the speed axis
  (predators 5-6, heavies/anchors 3; exact values brief-time).
  Flat integers, one-shot cap intact, band-unscaled.
- **Enemy gear flows through the same modifier math** — cybernetics
  an enemy wears change it accordingly (consortium cyber-legs make
  faster consortium; SETTLED 11's pieces go live on their wearers).
- **Future armor -AP: deferred.** When built, it wraps into the
  shared modifier calculation so enemies inherit it automatically —
  one mechanism, both sides, no enemy-side special case.
- **Enemy consumable use RULED IN** (user precedent: DCSS enemies
  zap wands): enemies use consumables they carry — stims, med packs.
  Carried-inventory shape + use triggers = brief-time; interplay
  with 47.1 kit drops (a used consumable is consumed, not dropped)
  noted.
- **The tactics ladder is CLOSED** — all eight rungs dispositioned
  across SETTLED 16-27. Q22 answered.

## SETTLED 28 (2026-09-22) — crew layouts via role tokens; topic D CLOSED

User, verbatim:

> My first concern with D is how we make the
> src/spacehack/data/layouts/*_crew.layout work with this system.
> these layouts determine enemies present chances and squad sizes.
> so right now they're calling out specifically pirates/etc.

> yes. all of this sounds good.

Rulings:

- **Markers name roles, not species.** The `ENEMY:` vocabulary
  becomes faction-neutral role tokens — `line` / `heavy` /
  `marksman` / `security_drone` / `stowaway` (elite later) — and a
  per-faction **CREW_ROLES data table** resolves role → spec id at
  load. One geometry serves every faction; the user-polished layouts
  are NOT forked per faction. Raw spec ids stay legal for authored
  specials (the survey wreck's consortium crew).
- **The merchant droid dial (SETTLED 7) = the `security_drone`
  role's weight**, tunable per deck — the caravan runs heavier drone
  markers than the hauler without touching geometry.
- **Kill deltas apply by crew faction** (answers Q9): militia
  marines → militia rep; merchant crew → merchant rep + the SETTLED
  8 honest-folk crime rule; consortium security → the hidden axis.
  Existing tables, correctly tagged — no new machinery.
- **Derelict squatters stay** — wrecks attract scavengers; the
  boarding economy keeps its risk. Topic D CLOSED; crew tables,
  role weights, and the marker migration are brief-time authoring.

## SETTLED 29 (2026-09-22) — the ancient machines: Watcher, Custodian, Warden (topic E CLOSED)

User, verbatim:

> help me think. ancient advanced alien tech.
> 1. some sort of floating round eye like droid with a precise and
> powerful laser
> 2. bipedal robot with multiple melee limbs
> 3. full assault droid, heavily armed

> for 2. the player can already attack with multiple weeapons if they
> are wielding 2 one handed weapons. the mechanic is already written.

> Watcher, Custodian, Warden are great. keep those

Rulings:

- **The ancient catalog is three rows, user-named:**
  - **Watcher** — the floating eye: precise, powerful laser; drifts
    to keep LOS; fragile (lens on a hover field). The sentinel cell.
  - **Custodian** — the multi-limb biped: melee pressure. **Wields a
    LIST of one-handed weapons through the existing multi-weapon
    attack** (the player's active-weapons pattern, reused enemy-side)
    — no flurry weapon, no one-attack-cap exception; the enemy
    weapon builder carries a loadout instead of picking one.
    One-handedness constraint verified at brief time.
  - **Warden** — the heavy assault anchor: armored, slow (low AP),
    devastating fire, holds ground.
- Their attacks are their OWN weapon family (never cross-resolves
  with human bands); difficulty = authored row-picking per site
  (entry floors seeded with Watchers, deep cells guarded by Wardens).
- Switchover when specs exist: the prison's floors/activation events
  re-pin from sentry/assault drones; the dormant-security fallback
  gains an authored override for alien sites; contemporary drones
  keep every non-alien job.
- **No usable drops** — the sites pay in alien tech; the machines
  aren't a farmable source (monster-weapon `loot_droppable` rule).
- The controller-node archetype is NAMED and deliberately not built
  (coordination machinery; a possible far-side boss shape later).
- Doc 43's inhabitants handoff: draws from this catalog. Topic E
  CLOSED.

## SETTLED 30 (2026-09-22) — fauna: every biome, bands, apexes guard the legendary (topic F CLOSED)

User, verbatim:

> 3. all biomes should have themed pools. because all biomes are
> capable of having a delve.
> 1 and 2 are good. An apex per biome theme is a great plan.
> something deep in a T4 delve making getting that legendary module
> a risk.

Rulings:

- **Every biome theme carries a native fauna pool** — any biome can
  host a delve, so every biome needs faces (LUSH, VOLCANIC,
  SCRAP_RING, CANYON join DESERT and ICE; theme→planet mapping is a
  brief-time survey).
- **Fauna join the band system** — no separate difficulty machinery:
  band-aware pool composition + stat derivation through the same
  band→effective-level mapping as humanoids (SETTLED 15).
- **One apex per biome theme**, prose-gated names — and the apex is
  the guardian pressure at delve bottoms: "something deep in a T4
  delve making getting that legendary module a risk" (ties directly
  to 47.4's delve-bottom legendary activation — the legendary
  finally has teeth in front of it).
- **Fauna stay `always_hostile`** (answers Q4: non-sentient, no
  faction, no rep; the LOS doctrine already treats them right).
- Topic F CLOSED. Names, row shapes, biome→planet wiring at brief
  time.

## SETTLED 31 (2026-09-22) — ship class ladders + themed modules (topic G CLOSED)

User, verbatim:

> Ladders sound good for first pass. consortium -- yes, nothing
> wild. two ships. one has to be a frigate class hull.

Rulings:

- **First-pass ladders confirmed:** pirate three classes over six
  specs (interceptor: scout + hound; line: raider + marauder;
  flagship: captain + warlord — pairs within a class differ by
  band/loadout, not role); militia's weight ladder (picket +
  light/standard/heavy patrol — pickets hold, heavies brawl);
  merchant's wealth ladder (cargo + armament + the droid dial —
  classes say how rich, not how scary).
- **Consortium fleet: two ships, one a frigate hull** ("nothing
  wild"). Frigate = the hunt's anchor/heavy; the second is the
  pursuit hunter (hull lean: cruiser — distinct from pirate scouts;
  brief-time call). Names PROSE GATE; more ships only when the
  hunt's full design demands them — two silhouettes stay
  unmistakable.
- **Themed modules confirmed** (the original seed addendum): pirates
  fly smuggler holds, merchants fly cargo holds + trade modules,
  militia fly military suites (largely already true), consortium
  flies top-quality everything (high-quality rolls — even their
  ships are loot). Data on the existing `modules=` field; the 47.3
  capture strip makes it capturable loot with zero new mechanics.
- Topic G CLOSED.

## SETTLED 32 (2026-09-22) — recognition & identity doctrine (topic B CLOSED; PHASE 1 CLOSED)

User, verbatim: "confirmed. Let's re-cut"

Rulings:

- **Glyph + color together are unique per hostile face within its
  spawn context.** Faction color families read at a glance (pirate
  warm/rust, militia blue, consortium corporate cold blue, merchant
  neutral trade tones, ancient machines one cold constructed
  family). Class-within-faction rides the existing case convention
  (lowercase common, uppercase serious: `r`/`R` extends to the new
  faces).
- **The collision lint** asserts no two hostile specs share
  glyph+color per context — permanent, in the test suite, against
  the single spec-data source (identity is single-sourced in
  `char`/`fg`; the doc-45 "three places" lesson applies to MARKER
  glyph constants, not enemy identity).
- Fix list: enforcer `c` vs bystander `c`; militia `M` vs the
  hauler's map glyph; `civillian` id cleanup rides the coherence
  phase.
- Topic B CLOSED. **Phase 1 (doctrine) CLOSED — SETTLED 1-32; all
  seven topics settled; build phases re-cut below.**

## SETTLED 33 (2026-09-22) — ship identity: hull glyph + faction color + bold flagship

User, verbatim:

> I like this better. You know what kind of ship you're up against
> because you know the ship glyphs from flying them yourself.

> Maybe for the boss glyphs we BOLD or something the glyph in addition
> to coloring them the family color?

> Let's call this as settled for ship glyphs. Do this with the bold
> variant work.

Rulings (anchors verified same day):

- **Glyph = the hull flown.** A ship spec's glyph names its hull
  (`ship_id` → the hull catalog), not an authored faction identity.
  Verified: the catalog is six hulls (`data/ships/core.py` — starter/
  scout/hauler/cruiser/frigate/freighter) and all 15 NPC specs fly
  five of them (scout ×4, cruiser ×4, frigate ×3, freighter ×3,
  hauler ×1; nothing flies the starter). The player learns the
  alphabet by flying the same hulls — SETTLED 19's "same kind of
  ships" mirror, made visible. Hull letters themselves = brief-time
  authoring.
- **Color = the faction family — now the SOLE at-a-glance faction
  carrier.** The SETTLED 32 color-family audit stops being
  documentation-only and becomes load-bearing: families must separate
  readably on the map. Flagged neighbor risk to check at brief time
  with real swatches: militia teal vs consortium corporate cold blue.
- **Bold = the flagship/elite class flag.** A data field on the spec
  (value 8 — any spec may carry it), rendered as a WIDENED glyph
  variant: the existing readability transform (`_widen_glyph_tile`,
  `engine.py:422`) applied +1 ink column at load into a second 16×16
  atlas; `GlyphAtlas.blit` (`pygame_engine.py:327`) picks the atlas;
  the flag rides the world draw command (`world_render.py`) through
  the single `render_world_view` path — one mechanism, both theaters.
  Wearing it: pirate captain + warlord (identical bold frigates that
  differ by band — SETTLED 31 verbatim); phase 11's consortium hunt
  anchor is the next intended wearer. NOT militia patrol_heavy —
  weight ≠ elite, and the hull glyph already carries weight.
- **Bold-bright ruled OUT** — lerping fg toward white bends the family
  color, the one channel carrying faction.
- Consequences: pirate interceptors (scout + hound) render identical;
  the line pair (raider + marauder) identical; the `D`/`W` boss
  glyphs retire. The militia `B` ladder reads as scout/cruiser/frigate
  in one teal — hull weight becomes readable pre-scan (today `B`
  spans three different hulls); blockade + patrol collapse to one
  identity (same weight class; the role difference is learned in
  play). Derelict wrecks keep their amber/brass and the glyph now
  honestly names the hull (already half-true today: `s`/`f`).
- **D1–D3 disposition:** D1's ship half is SUPERSEDED — no
  `SHIP_CLASS_FAMILIES` tables; the lint's ship rule becomes "spec
  `char` == its hull glyph" (keep the `char` field, pin equality — no
  consumer changes). D2 is dissolved (the ladder IS the hulls). D3's
  cross-registry pin list is re-derived against the chosen hull
  alphabet at the phase-3 brief re-cut — some overlaps dissolve for
  free (hauler `M`, captain `D`, pirate `p`/`P` all change); others
  persist wherever a hull letter meets a ground glyph (e.g. a `s`
  scout meets rock_scavenger `s`). SETTLED 32's case-convention line
  is amended for ships; it remains the GROUND rule. The ground half
  of D1 (`CHAR_CLASS_FAMILIES` for phase-4 faces) stays open.

## SETTLED 34 (2026-09-22) — ground identity: family letter + case variant + family color; bold for uniques

User, verbatim:

> I think we clearly have families here too. And the convention should
> be a glyph with a lower/upper case variant and a consistent color
> for that family, we can use bold when needed for calling out
> something unique (like the militia sniper or the pirate heavy).

Rulings:

- **Ground families are identity groups** — pirate, militia,
  consortium, civilian bystander, contemporary machines. One LETTER
  per family; members are case variants of it (SETTLED 32's
  lowercase-common / uppercase-serious convention promoted INTO the
  family mechanism); ONE consistent color per family. Live today as
  proof: pirate `r`/`R` and machine `d`/`D`. The machine pair's
  colors unify (sentry (150,185,255) vs assault (200,170,110) — one
  machine color, which wins is brief-time); pirate raider/rifleman
  likewise share one family color instead of today's rust-orange vs
  faded red.
- **Bold = the unique callout, theater-uniform** (SETTLED 33's flag):
  the pirate heavy and the militia sniper are the named wearers
  (user's examples). The phase-10 biome apexes and phase-9 ancients
  are the natural next — "calling out something unique" is exactly
  what an apex or a Warden is.
- **Case variants are distinct glyphs**, so the same-context
  uniqueness lint needs NO family exception ground-side. The
  `CHAR_CLASS_FAMILIES` table's job becomes enforcing family color
  consistency and reserving the family letter. `SHIP_CLASS_FAMILIES`
  is dead (SETTLED 33 — hull derivation replaced it).
- **Fauna are not letter-families** — no faction, no case structure;
  they keep species glyphs in biome palettes (SETTLED 30). Apexes
  wear bold.
- Concrete reads (letters/cases/colors brief-time): militia family
  letter `m` — trooper common-case, marine serious-case, sniper
  bold; consortium family letter `e` — enforcer's ruled `E` is the
  serious case, phase-11 rungs slot in as case/bold variants (the
  delisted `g` gunner re-authors then); the bystander keeps `c`.
  The trooper's `M` → common-case re-assignment rides phase 4 with
  the marine (no re-case before the pair exists).
- **D1 is now fully CLOSED** (ship half superseded by SETTLED 33,
  ground half ruled here). The phase-3 brief re-cut folds: lint =
  hull-glyph pin (ships) + family color consistency (ground) +
  cross-registry pin re-derivation; the flagged-decision block
  reduces to D3's re-derived pin list.

Addition (same day, user, verbatim):

> One quick note: with the char/color combo, this does open to the
> possibilty of using the same char across families as long as the
> color is distinct enough. If needed.

Ruling: the (glyph, color) PAIR is the identity — SETTLED 32's
uniqueness rule, read literally. Family letters need NOT be
globally unique: two families may share a char when their family
colors separate (the separation lint's threshold is the enabling
guard, not just a nicety). This relaxes the "reserving the family
letter" phrasing above — reservation matters only within a spawn
context. Ships already work this way (every faction's cruiser is
`C`); ground families may do the same where phase-4+ authoring
needs it — "if needed" is an allowance, not a goal.

## SETTLED 35 (2026-09-22) — phase-4 brief-time rulings (names, bands, ladder, pools)

User, verbatim:

> 1. "Pirate Brute"
> 2. these are fine bands to start with. we'll tweak as we playtest
> and tune.
> 3. good
> 4. sure. we can tune as we playtest.

(Same-day correction exchange: stat SCALE caps at 100; the LEVEL cap
is 60 with 5 points/level = 295 max points — band 4 at effective L30
is +145 ≈ half a maxed player's budget, two primaries near 100.)

Rulings:

- **Names:** the pirate heavy is **Pirate Brute** (user verbatim);
  Militia Marine + Militia Sniper stand. Glyphs complete SETTLED 34's
  plan: trooper re-cases `M`→`m` (common), marine `M` (serious),
  **sniper bold `M`**; pirate family `r`/`R` with **brute bold `R`**
  — bold rides the serious case as the unique callout. Ground
  identity key becomes (char, fg, elite) so a bold variant of a
  family letter never collides with its plain case (brute vs
  rifleman).
- **Band → effective level: 3 / 10 / 18 / 30** (budgets +10 / +45 /
  +85 / +145 points over base 10, all six stats). Distribution: the
  band budget splits by face archetype weights; space skills take a
  flat minor share (all six per SETTLED 19). Profiles: raider even,
  rifleman reflexes-biased, brute strength/stamina-heavy +
  reflexes-poor (the slow-hunter cell), marine reflexes/strength
  balanced, sniper reflexes-max. Tunable from playtest.
- **Family ladder:** humanoid specs name weapon FAMILIES (the ground
  catalog's own modules — melee, pistols, rifles, plasma,
  explosives); the band rolls the tier within the family, top-two
  window weighted up: band 1 {1}; band 2 {1,2} 70/30; band 3 {2,3}
  30/70; band 4 {3,4} 30/70. Picks: raider {melee, pistols},
  rifleman {rifles}, brute {explosives} (grenade→rocket), marine
  {rifles, pistols}, sniper {rifles} PINNED to the window's top
  (railgun at band 4 — the precision payoff). No fixed weapons=
  lists survive on humanoid rows (SETTLED 14); fauna keep organic
  fixed weapons (monster family is its own thing).
- **Quality rides band:** equip-time KILL rates step (5,11,25)% at
  band 1 → (10,20,40)% at band 4 (B2 (7,14,30), B3 (8,17,35));
  drop-time quality rolls shift with band identically.
- **Pools (bands 1-4, tunable):** densities 1.0 / 1.4 / 1.8 / 2.2;
  band 1 (raider, raider, trooper, sentry_drone); band 2 (raider,
  rifleman, rifleman, assault_drone); band 3 (rifleman, brute,
  assault_drone, hull_parasite); band 4 (rifleman, brute, brute,
  assault_drone). Militia = the flavor face (trooper seat band 1 +
  cities/authored content — never the difficulty carrier, SETTLED
  16); consortium absent (SETTLED 12); monsters keep their band-3/4
  seats.

## SETTLED 36 (2026-09-22) — phase-5 brief-time rulings (detect_radius, consumables, panic movement)

Rulings (user, option-pick 2026-09-22 — all four on the uniform path):

- **Ground `detect_radius` is RETIRED.** Authored on every ground spec
  (values 4-7) but consumed by nothing ground-side; ships keep their own
  live field. Hearing stays the flat per-weapon-radius check (SETTLED 17)
  — no per-spec hearing column is minted. Retirement follows the
  `ai_flee_threshold` precedent: the field and its authored values leave
  the dataclass (authoring one afterwards raises TypeError).
- **Enemy consumables are PRE-ROLLED, not re-authored.** What they drop
  is what they carry: the EXISTING `field_item_loot_pool` consumable
  entries resolve onto the enemy as live carried items; unused at death
  an item drops as loot, used it is consumed and never drops. Zero new
  authoring; no second carries= table.
- **ANY carrier can use them** — uniform, no humanoid/beast split:
  raiders pop stims mid-fight, beasts gobble scavenged med packs (the
  user's DCSS precedent: monsters quaff). Same effects and AP cost as
  the player's items.
- **Combat-time movement includes NON-COMBATANTS.** During a live
  ground fight every un-engaged entity moves at AP speed — bystanders
  included, reading as panic scattering. They still ignore gunfire (no
  attractor, SETTLED 22); once the fight ends everything folds back to
  the 1-tick stroll (SETTLED 25).

Build-shape consequence (from the doctrine, recorded here): the
`noise_hostiles` stub's OR-into-visible placement (`_encounter.py`) is
SUPERSEDED — heard entities are never combatants (SETTLED 16: LOS is the
only aggro). The stub retires; noise routes emission → attractor stamps →
the existing LOS join scans.

Addition (same day, user, verbatim):

> 1 is fine
> 2, instead, I'd rather communicate noise in game somehow, instead of
> having a guide entry that explains it. even just a combat log line
> would do for now?

> ok I like 3 but I also like the directional hint on 2. how can we
> combine both?

Rulings:

- **The consumable-use lines are APPROVED** as proposed: "{name} uses
  a Med Pack." / "{name} injects a Combat Stim."
- **NO guide entry for noise — the mechanic is communicated in play.**
  v1 = one reaction log line, **"Something to the {direction} heard
  that."** (COLOR_IMPORTANT_EVENT): fires once per new-hearer event
  when a not-already-investigating/engaged hostile first hears
  player-caused noise (firing report or blast), naming the 8-way
  direction to the NEAREST new hearer. Enemy fire never triggers it
  (their shots already log as attack lines); quiet weapons never
  trigger it — the line's absence is the stealth signal. A visual
  pulse at the shot origin (transit-arrival style) is a noted future
  polish, out of phase 5.

## SETTLED 37 (2026-09-22) — investigation is goal-based; guards are area guardians; squads follow noise as a unit

User, verbatim (ruling on the reviewer ADVISE pass over the phase-5
brief):

> 1A -- yes the idea of the guards are that they are guarding a
> specific area. like a vault in some cases.
> 2 -- I didn't realize there was a 5 tick memory. that explains some
> troubles I've had with kiting some mobs with line of sight. Can we
> drop that concept? A mob decides to investigate an area -- they move
> until they can have line of site on that area. full stop. once they
> get there if they see nothing, they continue as they were. if they
> see you, then line of sight combat rule interrupts.
> 3. if they are wandering as a unit, then they follow a noise as a
> unit.

Rulings:

- **Investigation is GOAL-BASED, not time-boxed.** The 5-tick memory
  is RETIRED — for the noise attractor AND the existing disengage
  investigation (amends SETTLED 24's recorded 5-tick behavior; the
  WITHDRAWAL of in-combat memory-chase stands untouched — this changes
  only the post-event walker). A mob that decides to investigate an
  area moves until it holds line of sight on that area — full stop.
  On arrival/LOS: sees the player → the normal LOS combat rule
  interrupts; sees nothing → continues as it was (patrol, post,
  wander). Give-up conditions: the goal is unreachable (no path), or
  a newer event re-stamps (latest-wins). Founding evidence: the
  user's kiting troubles ("that explains some troubles I've had with
  kiting some mobs with line of sight") — mobs giving up mid-corner.
- **Guards are area guardians** (1A confirmed — "guarding a specific
  area. like a vault in some cases"): hearing is LEASH-GATED — a
  guard gains the noise stamp only when it sits within its rolled
  weapon's max_range + 2 of the sound origin. The rolled weapon
  PERSISTS on the entity (idempotent first-resolution stamp,
  serialized), which also ends today's per-engagement weapon re-roll.
  A guard that investigates holds where the search ends — a new
  perch, bounded by the leash; return-to-post is a trivial future
  addition via the same goal-walker if vault-guard drift ever reads
  wrong in play.
- **Squads follow noise as a unit:** stamps land per-entity; squad
  pursuit keys on ANY member's goal — one hearing member draws the
  squad. LOS aggro stays individual (SETTLED 16 intact: no
  collective squad aggro).

## SETTLED 38 (2026-09-23) — phase-6 brief-time rulings (role tables, the Merchant row, hostility scope, authoring bounds)

User, verbatim (four batches in one pass):

> batch 1: merchant needs heavy/marksman/security_drone filled out.
> heavy = assault droid? marksman = droid that best matches.
> batch 2: 1 - "Merchant" alone is what's sitting best with me.
> Since it's merchants + droids, that should work? We can always come
> back around and rename it if needed. 2 - h and match ship color.
> 3 - agree
> batch 3: yes -- capture/derelict only. droid concern for merchant
> droid exception is covered in my batch 1 ruling.
> batch 4: yes color overrides retire (I suspect they already
> override). if you need to add a letter or move a letter, it's fine
> but as long as I'm the reviewer. it's too easy to mess up map
> geometry.

Rulings:

- **Merchant defense is DROIDS across the roles** (completes the
  merchant CREW_ROLES row): `heavy` = **assault_drone** (the armored
  anchor, ap 3 — SETTLED 18/27's machine anchor), `marksman` = the
  best-matching droid = **sentry_drone** (the only ranged machine —
  drone_laser), `security_drone` = **sentry_drone** (the namesake and
  the dial's target). Marksman and security_drone share a spec for
  now — the ROLES differ (marksman markers ride perch positions at
  fixed weight; security_drone markers carry the wealth dial); a
  future dedicated droid row can split them. The merchant table is
  the SETTLED 7 doctrine as data: honest light crew + droids as the
  entire defense shape.
- **The merchant crew row is named "Merchant"** (rename reserved —
  "we can always come back around and rename it"). Ground family:
  letter **`h`**, color = the fleet's merchant green (100,220,140)
  (theater-matching, like militia's blue). Cross-registry pin gains
  the `h` entry (ground Merchant vs space hauler — never co-rendered).
- **Merchant row shape stands as proposed** (batch 2 item 3 "agree"):
  band-exempt (all-zero weights), fixed light weapons
  (kinetic_pistol/combat_knife — no family ladder), hp ~16, ap 4,
  small loot, low xp.
- **The always-hostile override is CAPTURE/DERELICT INTERIORS ONLY**
  — cities, quest landmarks, and authored sites keep reading rep.
  The merchant-droid hostility question is covered by the batch-1
  table (droids are always_hostile rows; the Merchant crew row is
  what the override flips inside a boarded deck).
- **Marker COLOUR: overrides RETIRE** (crew identity renders from
  the resolved spec's family color — single-sourced; fixes today's
  off-rust riflemen). Tile colors (walls/floors/doors) untouched.
- **Grid edits are allowed with the USER AS REVIEWER** — new or moved
  marker letters are fine, called out for review ("it's too easy to
  mess up map geometry"): the brief lists every geometry-touching
  edit, and the playtest eyeballs each deck.
- Leans ruled by silence (no objection in the batch-1 response):
  militia `heavy` = marine (the strike face as the serious case);
  `stowaway` weight 0 for militia (marker legal, table omits it);
  pirate tables keep `security_drone` (repurposed hardware); derelict
  wrecks stay pirate-crewed via the pirate table.

Addition (2026-09-23, on the reviewer's editor finding, user
verbatim):

> The layout editor was an experiment. It turns out I edit way
> faster and better in vim.

Ruling: **the layout editor is a RETIRED EXPERIMENT — vim is the
layout authoring/review tool.** Role tokens get NO editor support
work; the editor's validity flags and palette are not consumers of
this phase. The only editor obligation is gate hygiene:
`test_layout_editor_model`'s pin on scout_a's parsed enemy specs
updates when the markers re-role (it reads real layout data).

## SETTLED 39 (2026-09-24) — phase-7 brief-time rulings (bands, parity, honest costs)

Rulings (user, option-pick 2026-09-24 — the space Tier-0 foundation):

- **Bands are SPEC-AUTHORED.** A `band` field on NpcShipSpec; the
  class ladder IS the band ladder (SETTLED 31's pairs differ by band
  because their rows say so). Systems gate danger by which specs their
  `npc_spawn_table` carries (environment-as-gate); deep ships author
  their own bands. No context derivation — nothing stamps a ship's
  band at spawn.
- **Everyone bands.** Pirates, deep ships, militia (the weight ladder
  maps onto bands — patrol_light 1 / patrol 2 / patrol_heavy 3), AND
  merchants. Amends SETTLED 31's "how rich, not how scary": merchant
  bands exist for parity (one mechanism, no exemptions) while wealth
  stays cargo + armament + the droid dial — the light profiles keep
  merchant encounters non-threats. Derelicts band 0 (boarded, not
  fought).
- **Pilot skills are BAND-DERIVED; authored constants retire.** The
  same band→effective-level mapping as ground (levels 3/10/18/30,
  `ground_scale`) distributes the budget over
  gunnery/piloting/engineering via per-spec skill weights
  (interceptor piloting-biased, line gunnery-biased, flagship
  balanced). `pilot_gunnery`/`pilot_piloting`/`pilot_engineering`
  leave the dataclass (the reflexes/strength/stamina precedent);
  deep.py re-authors via band.
- **Parity stats are the hull+module mirror.** Enemy
  shields/recharge/power read the player's own formulas: hull
  `base_shield_max` + module `max_shield_bonus`; free regen = hull
  `base_shield_recharge` + module `shield_recharge_bonus`; power =
  hull `base_power_gen` + module `power_gen_bonus`. `min_power_gen`
  RETIRES (TypeError pin, the detect_radius precedent) — specs re-tune
  via hull choice and modules. SETTLED 21's "authored shield-regen
  rates" resolves to this: the rates are the authored hull/module
  data, not a new spec field. The paid-regen divert machinery stays
  live but NO enemy sets a divert rate in Tier 0 — the when-to-divert
  decision is Tier 1's "regen when hurting".
- **Honest costs + step-to-first-affordable.** Enemy fire pays real
  `ap_cost`/`power_cost`/`ammo_per_shot`. When weapons[0] is
  unaffordable (dry missiles, short AP/power) the Tier-0 loop walks
  the weapon list and fires the FIRST affordable one — degenerate
  selection, never inert while something can fire. Real weapon
  selection stays Tier 1.
- **Quality rides band on modules AND weapons.** The fly-time rolls
  (47.3) read the band-indexed rates (band 1 = today's flat KILL
  ladder — nothing nerfs); weapons GAIN a fly-time quality roll they
  never had (damage already multiplies by quality; capture strips
  those exact instances — band-4 flagships fly near-overclocked gear).
  Uniform with ground SETTLED 14.
- **The space readout states the level.** The space TARGET CARD
  mirrors the ground card's title row — the "LVL 30 Pirate Raider"
  wording (`_ground_presentation` LVL line, space twin via
  `_space_presentation.title_row`; the hud enemy row keeps
  name + distance — reviewer fold, the card is the structural twin).

Addition (same day, user, verbatim — the Line ruling):

> sure. band 2. I'm not worried about it being too hard. I want it
> to be extremely hard. it's a brute force skip the run around
> shortcut for a super powered player. so if anything, even just
> making them frigate level marine hulls would even be an option.

Rulings:

- **militia_blockade carries band 2.** The harness
  (`test_line_tuning`) re-pins against the new numbers with the
  doc-39 contract's SHAPE intact — full watch unwinnable below 30 /
  a costly win at 30+, thin watch the mid-20s timing play.
- **The Line's difficulty doctrine: EXTREMELY hard is the design.**
  The full watch is the brute-force skip for a super-powered player
  — when the closed-form race lands marginal, the re-pin tunes
  TOWARD harder, never softer.
- **The frigate-hull escalation is a NAMED LEVER, not Tier-0
  scope:** if the fight ever reads soft in play (honest costs
  thinning picket volleys), re-authoring the pickets onto
  frigate-level militia hulls is the user-blessed next step — a
  ship_id/spec re-author with its own harness pass, not part of
  phase 7.

## SETTLED 40 (2026-09-24) — phase-8 brief-time rulings (the volley, the divert, back-off)

User, verbatim (six answers in one pass):

> 1. don't forget that this game's space combat is all about not just
> choosing which weapon, but which weapons, to fire. do you take an
> extra power draw hit and fire 4 lasers at once?
> 2. emergent is good for now
> 3. yeah, it can live on the npc spec. we can then tune it if
> gameplay makes it feel needed
> 4. I think this should also live on the npc spec? again, that makes
> it easily tunable per spec. so then we have another knob to tune if
> needed. default can be < 50% max for sure
> 5. yeah this is fine
> 6. we can defer dispositions. I can bring it up later if playtesting
> feels like it needs it.

Rulings (anchors verified same day):

- **The fire decision is a VOLLEY, not a weapon.** The enemy commits a
  SET of weapons per turn under the shared AP/power budget — "do you
  take an extra power draw hit and fire 4 lasers at once?" is the
  exact trade the AI makes. Verified: the player fires per slot, each
  weapon paying its own AP/power into the shared pool — there is NO
  per-volley surcharge; the cumulative draw IS the extra hit, and it
  competes with the regen divert for the same pool (the SETTLED 19
  example's engine). The volley is COMPOSED, not planned: each
  decision point fires the top-scoring affordable weapon until AP,
  power, or positive scores run out — a thin pool reads as the
  low-draw volley (lasers over plasma), a fat one dumps the rack.
- **Scoring:** expected value per AP — damage × hit-chance-at-current-
  distance (the min/max band penalties fold in through the same
  `calc_hit_chance` the shot resolves with) ÷ ap_cost; shield-strip
  weapons score by expected strip — `min(strip, target's current
  shields) × hit chance ÷ AP` — an EMP never fires on bare shields
  and outranks damage on a fat shield. No live loadout carries one;
  the rule future-proofs it.
- **Conservation is EMERGENT** — finite-ammo weapons simply win the
  scoring while tubes last (opening salvo, then the beam duel —
  today's list-order read, now principled); no reserve rule, no
  scarcity math.
- **`shield_regen_rate` is AUTHORED ON THE SPEC** — the AI answering
  the player's S-dial; personality, not band. Warships carry small
  rates; merchants and derelicts leave the default 0. Tunable per
  spec.
- **The low-shields gate is ALSO on the spec** — a per-spec threshold
  field, DEFAULT 50% of max shields. The divert fires only while
  shields sit below the threshold; power availability bounds it (the
  machinery's existing min). Two knobs, both per-spec.
- **Back-off + the bounded guard stand as proposed:** the authored
  `ai_preferred_range` STAYS (no weapon derivation — a ship carries
  multiple weapons spanning multiple bands; one authored stand-off is
  the honest shape); while inside the ACTIVE weapon's min_range the
  ship spends AP backing toward the nearest cell restoring ≥
  min_range, LOS-keeping steps preferred; the bound IS the guard —
  back-off fires only below min_range and stops at restoration, so no
  ship retreats beyond its own minimum engagement distance, and the
  in-band dodge-tank is SETTLED 23's blessed behavior. No per-turn
  step cap. **Closes doc-34 note 1.**
- **Doc-34 notes 3 (escort/guard coordination) and 4 (cover near
  spawns): dispositions DEFERRED** — no machinery in phase 8; the
  user holds the trigger ("I can bring it up later if playtesting
  feels like it needs it"). Note 4's mechanics half already works
  (unwalkable bodies block `_has_los` — baiting around a planet is
  live today); the open piece is encounter PLACEMENT, not LOS. Note 2
  (counters tactical, not loadout-only) is the phase's playtest LENS,
  not a build item.

Addition (same day, user, verbatim):

> I will confirm a, but also I will point out that I have better
> plans for combat simulation and balancing in a future design doc
> already stashed in design/future.

Rulings:

- **The Line harness EXTENDS with the real terms (treatment a).**
  `_picket_volley` gains the aggressiveness factor (agg 70 → ~30% of
  decision points reposition instead of firing), `_picket_regen`
  gains the threshold-gated paid divert term; the fits re-pin from
  whatever the honest numbers say, toward harder never softer
  (SETTLED 39). No Line-specific shortcut — the closed form derives
  from the one uniform loop ("once you aggro the blockade, you're in
  combat with the blockade").
- **The extension is INTERIM by design:**
  `future/50_DESIGN_COMBAT_BALANCE_SIMULATOR.md` (the user's stashed
  successor) supersedes closed-form pinning when it lands.

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
- **D. Crew & interior coherence** — CLOSED (SETTLED 28): role-token
  markers + per-faction CREW_ROLES tables; kill deltas by crew
  faction; derelict squatters stay.
- **E. Machine split** — CLOSED (SETTLED 4 + 29): the ancient catalog
  is Watcher / Custodian / Warden (user-named); own weapon family;
  authored-areas-only; prison re-pins on arrival; doc 43 draws from
  it.
- **F. Monster refinement** — CLOSED (SETTLED 30): every biome theme
  gets a native pool; fauna join the band system; one prose-gated
  apex per biome guarding delve-bottom legendaries; always_hostile
  stands.
- **G. Ship progression** — CLOSED (SETTLED 31): first-pass ladders
  confirmed; consortium = two ships, one a frigate hull; themed
  modules (smuggler/cargo/military/top-quality) capturable via 47.3
  (the 2026-09-20 seed addendum: capture strips whatever the spec
  flies).

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
4. ~~Fauna under value 3: stay `always_hostile`?~~ ANSWERED —
   SETTLED 30: they stay always_hostile; bands scale pools + stats.
5. ~~Band vocabulary~~ ANSWERED — SETTLED 14: one ladder
   (mission_tier = site band = tech_level ceiling), unclamped to 4;
   consortium excluded from ambient pools.
6. ~~Alien machines~~ ANSWERED — SETTLED 29 (Watcher/Custodian/
   Warden; phase 9; doc 43 draws from it).
7. ~~Recognition identity~~ ANSWERED — SETTLED 32 (glyph+color per
   context, families, lint; phases 3-onward).
8. Extensibility: what is still code that should be data — audited
   at phase 10's close against the "new enemy = data row" criterion.
9. ~~Interior kill deltas~~ ANSWERED — SETTLED 28: deltas apply by
   crew faction (militia/merchant+crime/hidden-consortium).
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
22. ~~Band-scaled tactics~~ ANSWERED — the tactics ladder CLOSED:
    composition + LOS doctrine (16), noise + combat-time movement
    (17), guard-artillery + leash (18), all-6 skills + resource AI
    (19), no fleeing (20), tiering + doc-34 fold (21), noise
    details (22), aggressiveness dial (23), in-combat memory
    withdrawn (24), movement modes (25), range management (26),
    per-spec AP + consumables (27).
23. ~~Full-kit resource-aware space AI~~ ANSWERED — SETTLED 19
    (ruled in), the space-systems audit (above) grounds it, SETTLED
    21 confirms the Tier 0 / Tier 1 split and folds doc 34.
    Decision-loop internals + the four ported design notes are
    brief-time.

## Phases (RE-CUT v2 2026-09-22 — reviewer ADVISE pass folded in; SETTLED 1-32)

- [x] 1. **Doctrine** — CLOSED 2026-09-22: all seven topics settled
  (SETTLED 1-32); audits landed (ecosystem, tactics, space-systems);
  doc 34 folded; doc 43 handoff recorded.
- [x] 2. **Faction mechanics & coherence** — consortium real:
  tables, hidden axis v1 (start −100, movers-only, log-suppressed,
  per-sheet), save migration, re-tags, the two-id pool de-list +
  substitution (keeps SETTLED 12 true in-window), militia crime +
  guild re-key, the full civilian-retirement blast radius. Brief
  below (APPROVED v2). LANDED 2026-09-22 (f5c3448a mechanics+re-tags,
  341c408b save migration, 0cbc03e1 sweep; reviewer APPROVE, four
  minors folded — clamp-test silence assert, load-path migration
  test, accidental bool() wrap reverted, fixture docstring).
  PLAYTEST PASSED 2026-09-22 (user: "Phase 2 is good") — SYSTEMS.md
  audited same commit.
- [x] 3. **Identity & cleanup** — RE-CUT (SETTLED 33/34): ship
  glyphs = the hull catalog's own chars + one family color per
  faction + the bold flagship wiring (widened atlas, `elite`
  field); ground family tables (letter + case variants + one
  family color; gunner `g`→`e`); the collision lint (hull pin,
  family conformance, family-color separation, one-entry
  cross-registry pin); enforcer `E`; `civillian` rename + alias;
  punch list (PROC_C dedup, `ai_flee_threshold` retirement,
  buy_ammo sync, dual-registry note). Brief below (APPROVED v2).
  LANDED 2026-09-22 (bfb49492 ship identity + lint, 0de395a2 ground
  families, c04026f1 bold wiring, f5ba6054 rename+alias, 3ecae95e
  PROC_C dedup, b730673a flee-threshold retirement, 6c752350
  buy_ammo sync, 4b47ce27 docstrings, c71fd603 reviewer minors;
  reviewer APPROVE — four minors folded: family-membership guard,
  elite test drives the real spawn factory, buy_ammo docstring +
  stale cargo_ammo comment, old-save glyph residue noted for the
  playtest). PLAYTEST PASSED 2026-09-22 (user: "playtest complete
  and passes") — mid-playtest rulings recorded below (militia
  blue + consortium navy; freighter F→B→h/H cargo pair);
  SYSTEMS.md audited same commit (new entries "Enemy ship
  identity" + "Ground identity families"; Combat AI flee line and
  Cargo model amended).
- [x] 4. **Band 4 + three-axis scaling + new faces** — band
  vocabulary unified (mission_tier = tech_level = dig band, band 4
  unclamped), full TIER_POOLS re-author (consortium out;
  hostile-weight rule), the family ladder, band→effective-level
  stat derivation (full 6-block), quality rides band, one resolver
  at every spawn; new rows: pirate heavy, militia marine + sniper
  (names in the brief; the merchant crew row moved to 6 with its
  consumer).
  LANDED 2026-09-22 in five builds (e64bbdc7 audit; ac42c7c7
  resolver+data, fb929f5e consumption+stamping, 72c10cd2 faces,
  1291b822 band wiring, 4611303c grant fix). Reviewer: five passes —
  build 1 REQUEST_CHANGES (bystander all-six-zero exemption fix,
  band-3 window pin, DRY minors) → APPROVE; build 2 REQUEST_CHANGES
  (the delve-camp stamp catch — wolf_b's camp read band 1 — plus
  planet_band DRY collapse, stale wield data) → APPROVE; builds 3-4
  REQUEST_CHANGES (dev grant starved the sniper on shared cells +
  untested; fixed with disjoint per-face slices, sniper at band 4,
  placement test). Build-order note: the faces build landed BEFORE
  the pools build (the band-3/4 pools name the brute row —
  dependency inverted from the brief's listing). The quest-guard
  ensure consumer named in the brief is ship-side (nothing ground to
  wire; phase 7 owns it). Prison activation security stamps band =
  floor (the dig formula at Mars T1); the mars_alien_prison floor-4
  events are the tree's only band-4 combat until a T4 dig. Same-day
  follow-up (user-directed): the ground target card's title states
  the band's effective level — "LVL 30 Pirate Raider" (user wording
  verbatim); no guide diff (the card explains itself in play).
  PLAYTEST PASSED 2026-09-22 ("This playtest is passing") —
  SYSTEMS.md audited same commit (new "Ground band scaling" entry;
  identity-families key amended to (char, fg, elite) with the four
  faces; kill-drop and delve entries note the band ladders and the
  four-band pools).
- [x] 5. **Ground tactics wave** — the noise system (per-weapon
  column, blast-at-impact, investigate attractor), combat-time AP
  movement + stepwise LOS join, range management + leash = weapon
  max + 2, per-spec AP field, enemy consumables (SETTLED 16-27 +
  36/37: `detect_radius` RETIRED, consumables pre-rolled +
  any-carrier, non-combatants join combat-time movement,
  investigation is GOAL-BASED — the 5-tick memory retires, guards
  hear leash-gated as area guardians, squads follow noise as a
  unit); owns the door-walkability verification. Brief below
  (PROPOSED v2 2026-09-22 — reviewer pass folded; APPROVED by the
  /implement-phase 48.5 run). LANDED 2026-09-22 in six builds
  (88d59a34 audit; 4251c505 data columns + detect_radius retirement,
  d2425bba noise + goal-based investigation + stamps/save, 45630d01
  combat-time movement + sight stop + the `_ground_effects` ratchet
  extraction, a2acbbac range management + derived leash, f81e0fc0 AP
  derivation + carried consumables, + the Shift+C carrier grant).
  Reviewer: five code passes — b1 APPROVE (two minors: the energy
  lever reading confirmed intended, a transitively-sound parametrize);
  b2 REQUEST_CHANGES (missing squad-any-member + blast-at-impact
  tests, tolerant parse, deadshot emission seam) → folded;
  b3 REQUEST_CHANGES (solo patrol path-pop bug, predicate order,
  leader-pace consistency, stale-session mode key, patrol pins) →
  folded; b4 REQUEST_CHANGES (a `_free_cell` DRY twin, off-path
  cache invalidation, close-leg + loop-level pins) → folded;
  b5 REQUEST_CHANGES (regen-resurrection guard, corrupt-save
  tolerance on the carried twin, empty-stamp survival) → folded.
  Build-landed readings (audit-amending): hearing's leash gate
  measures guard-position-to-sound (SETTLED 37); the investigation
  completes WITHOUT walking when the holder already has LOS on the
  goal (open-ground sounds are looked at, not walked to); squad
  patrol marches at the LEADER's AP (a unit moves together) while
  investigators budget per member; the deadshot chain emits through
  the same seam as every accepted shot. PLAYTEST PASSED 2026-09-23
  (user: "basic run through looks very good. mark this done. any
  tweaks can happen as I play more later") — tweaks deferred to live
  play; SYSTEMS.md audited same commit (new "Ground noise" /
  "Ground movement modes" / "Ground range management" / "Enemy
  consumables + AP" entries; Trigger, Guard leash, and Kill drops
  amended).
- [x] 6. **Crews + interiors** — role-token markers, CREW_ROLES
  tables, deck re-authoring (militia strike crews, merchant crew
  row + droid-dial weights, pirate crews incl. the heavy), the
  always-hostile-interiors override (SETTLED 3's boarding principle,
  currently unimplemented — militia decks must fight even at +50),
  guard-artillery deck placements (SETTLED 18), derelict squatters
  (SETTLED 28).
  LANDED 2026-09-23 in four builds (4e4eb3d3 seam: CREW_ROLES +
  crew_faction/security_drones kwargs + hostile_interior threaded at
  all five ground hostility read sites + wiring at all four boarding
  callers; cfa7fbf9 the Merchant row + merchant family + cross-registry
  `h` pin; deck re-authoring dec8cbbd COLOUR retirement + 3678ffe7/
  0d2b1699/433f9d21/83e46dde/68b242ca/5b5f682b/65ade4a2/93868260 —
  the seven decks + survey_a, DIRECTIVE BLOCKS ONLY, zero grid-line
  edits + 30d7b0d7 deck-correctness tests; b921edd3 the
  NpcShipSpec.security_drones dial, merchant trio 0.5/1.0/1.5).
  Reviewer: three code passes — build 1 APPROVE (three minors folded:
  occupied-set DRY, the merchant-cell integrity test landed with
  build 2, getattr shims collapsed in build 4); build 2 APPROVE (loot
  fields pinned); build 3 APPROVE over the whole range (grid
  invariance verified byte-identical at every intermediate commit;
  four minors folded: repro_autoexplore's bare scout_a load, seeded
  chance-roll tests, the merchant kill-delta + frigate-brute
  assertions, redundant imports); build 4 APPROVE (base chance parsed
  from the authored deck). Build-discovered readings recorded in the
  phase-6 audit below. PLAYTEST PENDING.
  Mid-playtest rulings (2026-09-23): (1) the abandon-interior confirm
  went GENERIC — "This ship won't survive a second breach, anything
  left behind is gone." (user wording verbatim) — one message for
  every leave-and-it's-gone hull, live captures included (5040518b).
  (2) Merchant decks re-tuned after the first H boarding read
  crew-heavy and drone-invisible (14 Merchants vs ~1 sentry): an H
  hull is the RICH TOP TIER and BIG inside — the dial now scales
  every sentry marker, the crews read light, and the H deck carries a
  STANDING assault complement (heavy@1.0#1-2, 2-4 per boarding;
  c84c0bbb). The heavy role stays outside the dial (SETTLED 38's
  scope stands — the complement is flat-authored). Simulated reads
  (400 loads): hauler 4 crew / 2.6 sentries / 0.7 assault; freighter
  3.2 / 8.5 / 3.0; caravan 3.1 / 12.5 / 3.0.
  (3) Big-interior PERF PASS (9ed83969..d608aa97, reviewer APPROVE
  with three minors folded): profiling a full 2,497-step auto-explore
  of the freightliner showed ~half the planning time in a per-step
  full-map light-source rescan (54.5M table lookups per exploration —
  crew decks contain ZERO emitting kinds), plus per-cell O(entities)
  blocker scans in the BFS and per-reveal hull-wall seed scans.
  Static sources + hull-wall cells now derive once per map
  (GameMap.replace_tile is the ONE runtime tile writer and drops both
  caches — every live-map write swept to it); the BFS reads blockers
  from a per-plan occupancy snapshot; lit-cell reveal intersects the
  source cache. Measured: 4.6 → 1.0 ms/step (4.5x) with an IDENTICAL
  step sequence under the same seed. (4) The faction-population sim
  (pirate/derelict unchanged by construction) caught MILITIA inverted
  — sniper-saturated decks (5.7-6.3 elite perch guards riding marksman
  markers authored for riflemen), marines nearly absent. User swap
  ruling: the sniper IS the heavy-hitting row (SETTLED 10) — sniper
  rides the single-slot heavy marker, marines ride marksman in their
  authored squads (8157856c). Simulated: cruiser 8.2 troopers / 5.7
  marines / 0.4 snipers; frigate 5.2 / 6.3 / 0.7; scout none.
  (5) Follow-up ruling: FRIGATES GUARANTEE their heavies (f5ecb7e5) —
  frigate_crew's g marker certain (0.35 -> 1.0, two single-slot
  stamps): pirate flagships always carry two brutes, the militia
  patrol-heavy two perched snipers. Cruisers keep the chance slot;
  scouts stay heavy-free.
  PLAYTEST PASSED 2026-09-23 (user: "much better performance. much
  better droid distribution. much better difficulty... 10/10") — the
  noise-alerted brute rocket kill cited as working-as-intended.
  SYSTEMS.md audited same commit (new "Crew roles" entry; Boarding,
  Ground identity families, Lighting, Auto-explore amended).
- [x] 7. **Space Tier 0: parity** — hull-catalog stats (base
  shields/recharge/power), module effects wired + honest costs,
  per-weapon AP/power/ammo, authored shield-regen rates, joiner
  spec verification, themed modules (smuggler/cargo holds —
  capturable), and the SHIP-SIDE band/loadout rolling (SETTLED 31's
  "pairs differ by band/loadout" — resolution lives here with the
  loadouts). Brief below (PROPOSED 2026-09-24).
  LANDED 2026-09-24 in seven builds (0ec9211e resolver+spec bands —
  reviewer APPROVE; 40103850 the parity swap (EnemyInstance
  StoredEquipment weapons, slot-keyed ammo, hull shields/recharge/
  power, band-derived skills + module bonuses + dials, field
  retirements with TypeError pins, line-harness re-pin) — reviewer
  REQUEST_CHANGES folded (start_enemy_turn contract tests, the
  hand-folded harness DRY, honest ~5x claim); 8caafe03 honest fire
  (weapon_costs shared economy table, first-affordable walk, real
  AP/power/ammo per shot incl. misses, weapon-quality damage —
  player bit-identical at 0) — reviewer REQUEST_CHANGES folded (the
  dropped LOS firing gate, regression-pinned + loop-level
  termination tests); a18ca042 joiner fix; c9f88707 the LVL card
  line; 0afe57f0 capture-strip weapons (the ship_weapon loot route —
  the bare 'weapon' namespace stays ground-only, pickups land in
  ship storage at flown quality); e6b11c02 themed loadouts
  (smuggler_hold, merchant wealth suites, blockade untouched);
  84310b75 the Shift+P dev grant (stateless cycle scout→warlord +
  the missile-led captain, a grant-time registry insert riding the
  one id-resolved path; identity elite lint scoped to production
  rows). PLAYTEST PENDING.
  Mid-playtest rulings (2026-09-24): (1) **DERELICTS SHOW NO SHIELD
  BUBBLE** (user report: "they're not active ships") — the parity
  change had credited every NPC hull with its base shields on the
  space map, wrecks included; the map read now zeroes capacity for
  hulls pinned `base_speed=0` (the derelicts' own stationary gate —
  a dead hull's deflector is down with the drive). Amends SETTLED 39's
  parity line: hull shields are honored for ships under way; derelicts
  are boarded, never fought, and the combat build is unreachable for
  them (detect_radius 0, boarding bypasses combat) — pinned
  (live pirate_scout still reads 5). (2) **NO NEW SMUGGLER MODULE**
  (user: "pirates should run smuggler's holds that already exist in
  the game. remove the new module") — the build's `smuggler_hold` id
  (cargo+speed stats) is REMOVED; SETTLED 31's "smuggler holds" means
  the catalog's own concealment family (`smuggler_hold_mk1-4`). The
  pirate captain flies mk3, the warlord mk4 (mk tier = the ship's
  band); capture strips the concealment hold that flew — the
  smuggler's-hold-as-pirate-loot seed resolves through existing data.
  The brief's "ONE new id" line is superseded; zero new module ids
  this phase.
  PLAYTEST PASSED 2026-09-24 (user: "alright this is playtesting
  fine") — SYSTEMS.md audited same commit (Space combat init /
  Combat math / Combat AI / Resources / Reinforcements / Boarding /
  Ship module loot amended; new "Ship band scaling" entry beside its
  ground twin).
- [x] 8. **Space Tier 1: the decision loop** — fire/regen/move per
  AP, `ai_aggressiveness` as fire-vs-reposition, weapon selection
  (EMP/conservation), the four ported doc-34 design notes
  (SETTLED 19/21/23). Brief below (FINAL 2026-09-24).
  LANDED 2026-09-24 in five builds (9b86c504 divert spec fields +
  authored rates — blockade/patrol_heavy 2, captain/warlord 3,
  threshold 0.5 default; a63304a7 the scorer + decision-point loop —
  `score_weapon` EV-per-AP through the same `calc_hit_chance` the
  shot resolves with, EMP scores expected strip, tie first-slot;
  `_first_affordable_weapon` retired, the seven walk pins migrated to
  scorer pins; d56f7d39 the threshold-gated paid divert in
  `start_enemy_turn` (free tier unconditional); ca7f0e58 back-off +
  reposition-in-band + the aggressiveness roll — `_apply_step` the
  one shared step tail, `_step_open` the one legality rule, the
  band-reference fallback (top scorer ignoring affordability) for
  power-dry dances; 8b3321cd the Line harness extension per the
  SETTLED 40 addition — volley ×0.70, regen 3+2 sustained below
  half, shape holds with NO fit moved, honest softening documented:
  the super sheet's costly win widened from the knife edge
  (die 12.6 / clear 12.25) to die 23.5 / clear 15.2, dense-watch
  caveat noted, frigate lever stands).
  Reviewer: build 1 REQUEST_CHANGES (stale Tier-0 comment, spec-fake
  DRY) folded; builds 2-3 APPROVE (gen-before-divert pin, `_run_turn`
  migration folded; the `_e_idx`/`_esp` dead-param seam declared for
  build 4); build 4 REQUEST_CHANGES — the stale-cached-path TELEPORT
  (back-off/reposition relocate the ship off its cached advance
  route; a stale head moves it multi-cell for 1 AP) — folded with
  off-route invalidation (head Chebyshev ≠ 1 recomputes) + a
  mixed-turn 8-adjacency pin; re-review REQUEST_CHANGES once more
  (the pin passed pre-fix by geometric luck) — re-geometry per the
  reviewer's traced scenario, pin PROVEN to fail pre-fix, plus the
  Chebyshev-0 own-cell hop hardening; build 5 APPROVE (net-gen 4
  constant corrected in harness + audit, threshold 0.5 pin,
  dense-watch calibration caveat).
  Build-discovered readings: the termination is RESTATED-live
  (power-dry ships spend leftover AP dodging — two Tier-0-era test
  expectations updated); the blocked-advance-beyond-pref fire and the
  blocked-no-LOS break both preserved; merchants' authored 10-15
  dials read as designed for the first time (rare fire,
  dodge-stack). PLAYTEST PENDING.
- [x] 9. **Ancient machines** — RE-CUT (SETTLED 41/42/43,
  2026-10-02). BUILD 1 (the volley loop + economy: one-shot cap
  dies; carried ammo + reload tells; ranged/melee sets with
  emergent switching incl. the cornered-switch; the
  aggressiveness-dial port) LANDED 2026-10-02 in seven builds
  (c63f3dcf stamps/loadout, 0c98f0b9 volley+scorer+ledger, 26d22366
  point-blank parity, 29e640ca reload+tell, 2686c69d the dial,
  4a615d09 the kit-drop law, 780e29d8 the last pins) with ZERO
  roster number changes; reviewer dispatched per build (three
  REQUEST_CHANGES, all reproduced + folded + re-approved); the
  two-save battery + starter standard re-measured and recorded above
  (the variance-not-mean read; the countered lane re-armed at 0.76).
  PLAYTEST PASSED 2026-10-03 (user: C ship boards + delves, "seems
  to be playing well"; the set-switch read in live play — "forced a
  laser pistol pirate to switch to melee"). Builds 2+ = the machines
  authored against the new loop: **Watcher** (shriek/stare/graded zone/
  drift-dodge), **Shredder** (was Custodian: in-combat mend/AP-6
  flurry/armor 10), **Warden** (per-tile-HP force field with
  start-of-turn regen, slam-with-pushback, anti-armor shot), their
  own weapon family, prison re-pin (+ the rock_scavenger
  prison-floor pin), dormant override for alien sites (SETTLED
  29/41/42/43). Design input attached: the 2026-09-29
  prison-build power audit + the 2026-10-02 two-chain arrival sim
  (both real arrivals converge ~lvl 36-37). All opens ruled
  2026-10-02: the two reference saves ARE the tuning target
  (final-build retest against both); exclusive FOR NOW (doc-43
  handoff deferred, not retired); considered T4 band, provisional
  until built. SETTLED 44 (2026-10-03): the Warden shot is a
  normal volley weapon (no telegraph/lane/charge, `ap_cost` 3);
  the machines' brief (builds 2+) sits after the BUILD 1 landing
  record — APPROVED 2026-10-03 (glyphs O/S/bold-W, SETTLED 45;
  the flagged leans ruled with the approval; reviewer ADVISE pass
  folded 14/6). BUILDS 2-7 LANDED 2026-10-03 in six commits
  (b2a family `98a85066`; b2b specs `ff8bc62e` + the dev-pick guard
  `a8a8b436`; b2c knockback+mend `7d877992`; b2d Watcher `2c2937a0`;
  b2e field `1dbd2914`; b2f prison re-pin `94ccbc26`; b2g instruments
  `8ef927df`) — reviewer dispatched per build and per fold round
  (three REQUEST_CHANGES rounds, each reproduced + folded +
  re-approved: the eruption rep back-door, the sibling-shell
  destruction, the falsified popup prose-exclusivity, the
  off-map dev grant). The machines' battery recorded in the builds
  2-6 landing section: standard rows bit-identical to build 1; the
  F4 authored trio alone = the tune's headline wall (labs 0.020 /
  merchants 0.200). PLAYTEST PASSED + PHASE CLOSED 2026-10-04
  (user: "this feels good. now I can pretty consistently survive
  as long as I play careful and exploit their behavior"; "rest is
  good. close out this phase"). The mid-playtest fix arc (findings
  1-9 in the landing section): the diagonal-adjacency melee
  deadlock (pre-existing since doc 51, every melee enemy — band
  gates int-truncate like the player's fire gate; the doc-50
  starter-batons bar retired permanently, the goal_2_lane_batons
  row ruled in the kit's true geometry), the radius-less
  investigation LOS (unbaitable Wardens), the walking-wall field
  (per-tick tracking, fresh-cells-full, tombstone regrow, death
  collapse to survivors), melee-reach-resolves-the-melee-set (the
  slam trade), the aim line stops at the shimmer, the shimmer
  renders in sight only, and SETTLED 46's prose (Serrated Blades
  / Energy Cannon / the slam's own hit+damage and miss lines /
  the shimmer-field lines). SYSTEMS.md audited same commit (the
  volley-loop entry rewritten; the ancient-machines entry added;
  noise/movement/families/band-scaling/kill-drops/extensions
  amended). DEFERRED, recorded not blocking: the six stale
  drone-named event popups (the user's own later pass), the
  F5-extraction warden gauntlet + parasite-only pool leans (tune
  dials), the field-as-entities design question (finding 8, the
  far-side handoff), doc-50's PlayerSheet quality/stat-spend gaps.
- [x] 10. **Biome expansion + apexes** — LUSH/VOLCANIC/SCRAP_RING/
  CANYON fauna + band-aware pools; one apex per biome guarding
  delve-bottom legendaries (SETTLED 30 + 47: per-biome fully
  authored pools with TIER_POOLS as the default, earth=lush,
  every bottom guarded — default biomes borrow the nearest apex,
  2 faces + 1 apex per biome, every row a distinct cell incl. the
  pack apex). Brief below (FINAL v4 — APPROVED 2026-10-04; names,
  pools, glyphs approved verbatim). At its close: the
  extensibility audit (acceptance criterion — adding an enemy is a
  data edit) against the whole campaign.
  LANDED 2026-10-04 in five builds (adc06b8e the seam + SETTLED 49
  re-tier; 6308cc76 the organic weapons; 8474c6f8 the fauna + tile
  lint; 792718ff the apexes + bottom guard + the hoist; 7d82963a
  the four new tables + battery + save/load row) — reviewer
  dispatched per build, five APPROVEs, every minor folded; the
  battery re-run is BIT-IDENTICAL pre/post (the landing record
  below). PLAYTEST PASSED 2026-10-04 (user: "Yes, I like that this
  limits the humanoids. the data pads were dropping TOO much
  before. This works for now. Playtest passes.") — the pad-door
  consequence ENDORSED as a balance improvement, not just a ruled
  consequence. SYSTEMS.md audited same commit (the dig entry
  amended for the biome axis + door-1 scope + the bottom apex; a
  new "Biome fauna + delve-bottom apexes" entry; the elite set and
  the tier-gate law folded into their entries). The extensibility
  audit (Q8, the acceptance criterion) is recorded below the
  landing record. PHASE CLOSED.
- [ ] 11. **Consortium content + the hunt** — cybernetic ground
  rungs, the two hunter ships (one frigate hull), the main-quest
  hunt reskinned as a new enemy class (with the `_heat.py`
  hired-pirate docstring cleanup), strictly-gated exposure
  (SETTLED 6/9/12/19 + 50/51/52; rep machinery NONE — SETTLED 53
  defers the up-movers + site/loot movers to future content; gates
  stay none). Depends on 2, 7-8.
- [ ] 12. **Loot-drop polish** — a full pass over the COMPLETE
  roster's drops (user ruling 2026-10-04, seeded by SETTLED 49's
  discovery — the assault drone's entire equipment pool was
  one re-tier away from silently dropping nothing): every row's
  `equipment_loot_pool` vs its `tier` (the tech_level filter),
  `loot_pool` goods + `loot_count` coherence, field-item pools,
  `xp_reward` sanity, quality-rides-band vs authored quality, and
  the every-kill-pays doctrine — VALUES only, no new payload
  shapes (the 47.x systems absorb, per the acceptance criteria).
  Placed after 11 so it polishes the finished roster; pullable
  forward by ruling if playtest pressure demands. Unbriefed —
  needs a /refine-design pass (survey the live drop tables first,
  then the brief).

Order rationale: mechanics before identity (lint needs final
factions); scaling before tactics; crews carry their own rows;
parity before brains; the hunt last (needs its body and its foes);
the loot polish after the roster completes (it audits every row's
drops).
Reviewer ADVISE 2026-09-22 folded in: phase split (old 2 → 2+3),
blocking fixes in the v2 brief, punch-list owners assigned,
merchant-crew row moved to its consumer, ship-band rolling homed at
Tier 0, placements homed at crews, ledger 6-7 struck.

## Phase 9 design input — the prison-build power audit (2026-09-29)

Measured with doc 50's exploration front (`tools/balance_probe.py`,
landed 11169f33): the user's real prison-descent save loaded through
the production deserializer and fought by the harness — 50 seeded
runs/row, open-floor arena (toggle_sets stance) + the pinned Mars
row + the space ladder (stand_and_trade). INPUT data for phase 9's
tuning conversation, not rulings.

The build under test (the sheet that found the prison trivial):
level-36 Sirian Bounty Hunter, REF 75 / STR 20 / STA 65 (52 HP),
railgun q3 (~62 dmg/hit logged) + mono blade, heavy set with q3
vest + q3 cybernetic eyes, longshot; cruiser with 3x plasma (2 at
q3). Lifetime counters corroborate: 500 kills, 9 hull damage taken
all game.

**Arrival-state provenance (user, 2026-09-29 — load-bearing for
the reference-sheet ruling): the sheet was not power-ground.** The
user played the merchant chain straight through and descended the
prison the moment the door opened. The forcing function is
mer_q4_bribe (`data/main_quest/act0_merchants.py:89`):
objective_type "payment", a BALANCE gate — hold 8,000 credits at
once (`_payment_option_gating` reads `ctx.stats.credits`, then
consumes it; "any income counts" = any source, not cumulative
income). Reaching an 8,000 balance forces heavy trade volume, and
the power arrives as side effects of that volume: delivery/mission
payouts (rewards_xp + `_lifecycle` add_xp), space kills at 2x
base_hull XP each (`_space_kills.py:171`) off the pirates the
routes spawn, and band-scaled kill/wreck drops along the way. No
credits->xp trickle exists in code — the correlation is the loop's
shape, and 500 lifetime kills is what "just playing the merchant
path to the prison" costs. CONSEQUENCE: the measured sheet is the
merchant route's DEFAULT prison-arrival state, not an outlier
ceiling.

| Matchup (ground, open floor) | Win | Mean dmg (worst) | Turns |
|---|---|---|---|
| 3x rock_scavenger b1 (pinned goal_2 fight) | 1.000 | 0.80 (2) | 4.0 |
| 5x pirate_rifleman b2 | 1.000 | 12.26 (44) | 3.6 |
| 5x pirate_brute b3 (grenade-armed) | **0.920** | 19.20 (48) | 3.2 |
| 5x assault_drone b4 | 1.000 | 0.00 (0) | 3.3 |
| 5x consortium_gunner b4 | 1.000 | 3.36 (6) | 3.2 |
| 10x assault_drone b4 | 1.000 | 0.06 (1) | 6.2 |
| Space: scout / raider / marauder / warlord / 2x marauder | 1.000 | 0.00 (0) | 1.0-2.4 |

Measured laws (why the prison read as the tutorial — its roster is
sentry/assault drones, band = floor, counts 1-3):

1. **Melee is zero threat at any band** vs a ranged build:
   arrival-AP denial + the railgun one-shotting 49-HP band-4 drones
   (49 = hp 34 + STA 46//3) means melee never swings. 10x band-4
   drones cost 0.06 HP.
2. **All remaining threat is ranged, and per-hit damage is the
   bar**: gunner rifles ~3/hit are invisible through the heavy set;
   the ONLY measured deaths were 5x band-3 grenade launchers
   focusing 16-26/hit = 58 ≥ 52 HP in two turns (4 deaths/50).
3. **The hit contest is reflexes**: band-4 melee archetypes resolve
   REF 25 vs the build's 75 (half-rate convention → always-hit /
   never-be-hit); the b4 gunner's REF 76 is the catalog's only real
   dodge check. Weapon accuracy must contest REF//2 dodge or be
   uncontestable (splash).

Per-machine input bars (against the god build; the reference-sheet
ruling below decides what actually gets pinned):

- **Watcher** — the threat carrier (ranged). Laser wants accuracy
  that contests REF 75 and per-hit damage over the heavy-armor
  soak; the grenade-brute's 16-26/hit is the only measured lethal
  bar.
- **Custodian** — pure melee stays worthless regardless of limb
  count (law 1). Its lever is the AP economy: per-spec AP high
  enough to close a corridor AND swing breaks the baiting play —
  measurable in lane geometry.
- **Warden** — needs to eat one 62-dmg railgun shot and stand (TTK
  step to 2+ shots) or the deep cell is a corridor of one-shots;
  the countered-lane row prices a held-ground ranged anchor at 45%
  of a starter's health.

**Chain arrival-spread data (2026-09-29, user question "how quickly
do I get to the door on the other factions" — code-verified
structures):** the time game IS balanced; the activity is not.

| Chain | Gate-days | Step XP | Systems on route | Forced activity beyond waits |
|---|---|---|---|---|
| merchants | 220 | 610 | 5 (sol/wolf/tc/eri/vega) | delve + smuggle + salvage/captain + **8,000-credit BALANCE gate** |
| militia | 220 | 520 | 4 (sol/luyten/eri/cygni) | delve + smuggle + visit + bounty/captain |
| bar | 200 | 480 | 3 (sol/barnards/wolf) | delve + 3 smuggles |
| labs | 225 | ~590 | 4 (sol/proc/ac/sirius) | delve + 3 smuggles + salvage/captain |

The clock (~200-225d + act1_prison's own 60d) and the scripted
fights (1 delve + 1 captain ± a smuggle) are equivalent across
chains — a minimal-activity run of any chain converges on roughly
the same weak arrival (~1,000-1,500 XP ≈ level 8-12, analytically).
The merchant differential is exactly two authored things: the only
economy gate in the four chains (hold 8,000 at once) and the
longest route — both convert calendar time into the XP engines
(mission payouts + route pirates at 2x base_hull XP/space kill).
Balance surfaces for the ruling, as INPUT: (a) equalize forced
floors — bound the bribe to chain-earned income, or give the other
three chains their own engagement gates; (b) authored-by-chain
prison banding — stamp the prison's band from the arrival chain
(no runtime player-scaling, keeps bands site-authored); (c) embrace
chain-as-difficulty (spread currently ~12-15x XP — likely too wide
to embrace knowingly); (d) the global lever — the 2x-hull space
kill XP rate that makes routine route defense hyper-profitable.

OPEN RULING for the phase conversation: the reference sheet the
prison is balanced FOR. The original framing (on-pace ~lvl 28-30
pin, god build as recorded ceiling — agent lean) predates the
arrival-state provenance above: if the merchant route's no-grind
arrival IS a level-36 q3 sheet, "on-pace" needs a chain-aware
definition — measure the other three chains' arrival states and pin
against the spread, or rule the merchant arrival the tuning target
outright (the deep cells then push back against THIS sheet).

Instrument notes for authoring: probe rows for the three specs as
data lands (include corridor geometry — the arena is open floor);
pinning the tuned matchups on the doc-50 board needs the harness
gap closed (PlayerSheet can't express ground stat spends or gear
qualities — build_ground_ctx ignores skill_spends for ground stats)
and a probe/board grid path for the mars_alien_prison extension
floors (build_planet_grid is planet-specs-only today).

## Phase 9 design input — the two-chain arrival sim (2026-10-02)

The user supplied two real post-prison saves (both Sirian Bounty
Hunter, both `act1_prison` completed):
`grid_labs_sirian_bountyhunter.json` (labs chain) and
`grid_merchant_sirian_bountyhunter.json` (merchants chain — the
09-29 audit's own sheet, ship since refit to a trade fit). Loaded
through the production deserializer via `tools/balance_probe.py`,
same rows as the 09-29 audit, 50 seeded runs/row. INPUT data for
the phase-9 conversation, not rulings.

**The two real arrivals CONVERGE — the spread is BUILD, not chain.**

| | labs | merchants |
|---|---|---|
| level / XP / lifetime kills | 37 / 19,529 / 565 | 36 / 18,823 / 501 |
| ground stats | REF 58 / STR 30 / STA 40 | REF 75 / STR 20 / STA 65 |
| HP / dodge (REF//2) / armor soak | 40 / 29 / 23 | 52 / 37 / 16 |
| kit | railgun q3 (6+121), 2x stun_baton q3 | railgun q3 (12+240), mono_blade |
| ship fit | war (plasma q3 + 3 lasers, mk2 suites) | trade (2 weapons, compact reactors + gyros) |

The sheets defend in OPPOSITE ways — labs soaks 23 armor at 40 HP,
merchant dodges 37 at 52 HP with 16 soak — while their offense is
IDENTICAL: railgun q3 = 64 damage at 105 accuracy, and quality puts
BOTH sheets at the 95% hit cap against every REF in the current
catalog (strength never enters ranged damage). Reference-sheet
ruling input: a full-play arrival on either chain lands ~level
36-37 with a q3 kit — "the merchant arrival" generalizes to "the
full-chain arrival," and the variance to tune across is the
40-HP-armor-tank vs 52-HP-dodge-tank axis, not chain identity. The
minimal-activity arrival (~level 8-12, analytic) is unmeasured by
these saves; bars below would read as a slog against it.

**Matchups (win / mean dmg taken, worst in parens, defeats noted):**

| Row | labs | merchants |
|---|---|---|
| 3x rock_scavenger b1 (true-sight cells) | 1.000 / 0.02 (1) | 1.000 / 0.00 (0) |
| 5x pirate_rifleman b2 | 1.000 / 4.66 (16) | 1.000 / 12.26 (44) |
| 5x pirate_brute b3 | 0.940 / 16.79 (38), 3 def | 0.920 / 19.20 (48), 4 def |
| 5x assault_drone b4 | 1.000 / 0.00 (0) | 1.000 / 0.00 (0) |
| 5x consortium_gunner b4 | 1.000 / 3.44 (7) | 1.000 / 3.36 (6) |
| 10x assault_drone b4 | 1.000 / 0.06 (1) | 1.000 / 0.06 (1) |
| space scout / raider / marauder / warlord / 2x marauder | 1.000 all; 2x marauder 0.900 (5 def) | warlord **0.280** (36 def), 2x marauder **0.140** (43 def) |

Ground reads the same for both sheets: brute explosives stay the
only lethal row (worst 38 vs 40 HP, 48 vs 52 — each sheet one bad
turn from death); band-4 melee stays zero threat (law 1 holds on
both); kinetic rifles sting the light soak harder (12.26 vs 4.66
into 16 vs 23). The merchant SPACE collapse vs the 09-29 audit
(was 1.000 across) has two confounds landing together: the doc-57
enemy-missile end gating (84bf8617, same day) and the save's refit
from the audit's 3x-plasma war cruiser to a 2-weapon trade fit —
unattributed, prison-irrelevant, flagged for the next space pass.

**Placeholder baseline (what the machines replace):** drone_laser
is 4 base damage — every sentry/assault drone at every band lands
exactly 1 dmg/hit into both sheets (67-75% hit at band 4), and
every drone dies to one railgun hit at every band (b4 assault: 49
HP + 3 armor vs 64 damage). The tutorial read, quantified.

**Per-machine bars re-read across BOTH defense models:**

- **Watcher** — the soak spread (23 vs 16) collapses to 11 vs 8 if
  the laser rides the plasma armor-halving rule (note: drone_laser's
  `energy` damage_type gets NO special math today — halving is
  plasma-only in `ground_damage_raw`; the family's type semantics
  are a conversation item). Accuracy is merchant-bound: authoring
  acc + REF//2 around 105-115 holds ~68-78% hit vs REF 75 and
  ~76-86% vs REF 58 — the squishier sheet eats ~8 points more, the
  correct direction. Landed per-hit wants the brute-grenade class
  (10-18 post-soak). Fragile by intent (TTK 1, the sentinel cell).
- **Custodian** — open floor stays free kills on both sheets (law
  1); the reachable bars: HP + armor > 64 (eats the opening railgun
  shot), AP ~6, and the deep cell's 1-wide bridge corridor as the
  real weapon. Energy-typed claws would get the same soak-equalizing
  effect as the laser.
- **Warden** — TTK-2 keys to the 64-damage railgun ceiling both
  saves carry: HP > 64 − effective armor, with plasma-halving the
  player's counter (HP must also clear 64 − armor//2). Armor 12 /
  HP 65 clears both (52-58 per hit, two to kill).

**Tooling note:** `balance_probe.py`'s `g_mars_pinned` row still
carries the pre-6cbddeb2 glow-revealed cells — instant-disengage
0.000 on both saves until re-run against scenarios.py's true-sight
cells (the corrected numbers above). The tool's copy of the row
needs that re-pin.

## SETTLED 41 (2026-10-02) — the ground volley amendment (one-shot cap dies)

User, verbatim:

> no, just like in space combat, ground enemies should be using
> their full AP potential strategically. maybe this is partly why
> ground combat turns in to a push over in late game? I'm firing
> multiple times per round.

> yes. we have to get them fighting correctly first before we can
> know what needs tuned.

Rulings:

- **The ground one-shot-per-turn cap is DEAD** — supersedes
  SETTLED 26's "One-shot-per-turn cap unchanged" and SETTLED 27's
  "one-shot cap intact". Ground enemies spend full AP
  strategically: the phase-8 decision-point loop ported
  ground-side — per-AP fire-vs-move, per-weapon `ap_cost` governs
  the volley (railgun 2 AP: a 3-AP rocket cannot triple-fire, a
  1-AP pistol can), scoring through the same hit math the shots
  resolve with, reposition and back-off competing for the same
  pool. Uniform across every spec — no per-machine carve-outs.
- Confirms the 2026-09-25 sweep's core bug (hands/AP volley
  economy ~4x) as designed-out: the player fires per AP; now
  everything does. SETTLED 29's "no one-attack-cap exception"
  clause dissolves with the cap it excepted from.
- **Build-first sequencing: the loop lands ALONE, no number
  changes** ("get them fighting correctly first"); the two-save
  probe battery + the starter-sheet standard re-measure against
  it; tuning follows the measurement; the machines' bars are
  authored against the POST-amendment loop. Rides phase 9 as its
  first build.
- On-the-record predictions (falsifiable by the post-loop
  battery): gunner/rifleman landed damage roughly triples; the
  brute row becomes genuinely terrifying; band 1-2 and the
  tutorial standard want a rebalance look. The parked
  tuning-doctrine thread (the five invariants, waiting since the
  doc-51 era) picks up here.

## SETTLED 42 (2026-10-02) — the ancient identities: Watcher / Shredder / Warden

User, verbatim (the reframe):

> This isn't going to be about tuning the existing enemies, we need
> fresh new enemies for this. things the player hasn't seen
> anywhere else and won't see anywhere else.

> watcher's shouldn't have lasers. this is new alien tech. we're
> supposed to be seeing things no one in the known universe has
> seen. we need something better and more unique to a laser.

Rulings (amend SETTLED 29's catalog: **Custodian is renamed**,
the **Watcher's "precise and powerful laser" is superseded**; the
trio frame, "own weapon family," authored-areas-only, and
no-usable-drops all stand):

- **Naming principle: player coinage.** A machine is named what a
  survivor would call it on first contact (user: "what would the
  player call it having never heard of it or seen it before?") —
  the Watcher watches, the **Shredder** shreds (user rename;
  "Custodian" rejected), the Warden wards. PROSE GATE on every
  player-facing string.
- **The family is a system — each machine revokes one player
  mercy and defeats one player defense.** The Watcher takes
  standing still, the Shredder takes hesitation, the Warden takes
  distance. Against the two reference sheets: labs (23 soak,
  melee kit) thrives vs stare rings and claws and is invalidated
  by the Warden's shot; merchant (52 HP, 16 soak) eats full-price
  cores. No machine pierces everything.

**The Watcher — shriek + stare + drift:**

- **Very high dodge** (user: "look at the accuracy we're
  bringing"): authored REF 90-100 plus a perpetual hover-drift —
  movement dodge (+5/cell, cap 30) is the other half, and SETTLED
  26's leftover-AP repositioning funds it: the drift IS the dodge.
  At the q3-railgun ceiling (acc 105 + REF//2): merchant ~62-77%
  hit, labs ~52-69% — the one-shot dream dies, the fight doesn't.
  Weak-sheet wall (q0 rifles floor at 5%); retreat stays their out.
- **The shriek** (user: "what if the watcher emitted a VERY loud
  noise that threatens to bring other nearby ancient machines to
  the fight?"): fires the round LOS opens and again as its FIRST
  AP every round it still sees you (user ruling; a 1-AP LEAD
  ACTION, not a weapon — the weapon volley must not pay for the
  alarm). A very loud noise event through the EXISTING noise
  system (family noise column ~25-40, where explosives top at
  10-12): nearby ACTIVE ancient machines gain investigate
  attractors — heard ≠ aggroed (SETTLED 16 intact), dormant stay
  deaf (SETTLED 22 intact: authored activations remain the only
  wake trigger), no spawns (SETTLED 21 intact). A charge/wind-up
  mechanic is DEFERRED as the softening lever if playtest says
  too aggressive (user: "playtesting is where we decide").
- **The stare** (user-approved replacement for the laser): the
  eye fixes on the player's cell at enemy phase; the zone is a
  **3x3, GRADED** (user: "center is most damage. edges of the 3x3
  are less damage?") — core full, ring half pre-soak; eruption at
  the end of the player's following turn (exactly one full turn
  to vacate); **no to-hit roll**; damage **respects armor** (own
  family column, full soak). Re-fixes every round it lives — the
  dance is perpetual; terrain is the trap. Anything IN the zone
  at eruption takes the damage — the first enemy-vs-enemy damage
  vector (baiting play; machines stay oblivious to marked cells).
  The eruption is a blast-class noise event at the cell (one
  deduped emission per cell per beat). Multiple Watchers: zones
  COINCIDE (all fix the same cell) and damage STACKS — count is
  the floor-authoring danger dial. Escape economy: 1 AP to the
  ring, 2 AP clear; with the railgun at 2 AP, full safety costs
  exactly one shot per round.
- **Numbers (brief-time dials):** core 32-42 pre-soak (lands
  16-26 vs merchant's 16 soak, 9-19 vs labs' 23; ring ~1-5);
  REF 90-100; tone radius 25-40.
- **Log lines (user drafts, PROSE GATE):** "The Watcher turns and
  looks at you, its eye flashing red." / "The floor beneath you
  begins to glow." / "The floor beneath you glows brighter." (each
  additional stack; repeats safely) / "The floor erupts in a
  violent explosion." / "The floor erupts in a violent explosion
  causing X damage to Y." (per victim). The mechanic is never
  named in the log; the player learns the pattern from the
  pattern.

**The Shredder (was Custodian):**

- **AP 6, claws 2 AP** (max three strikes in a full unload —
  maims, doesn't delete), **armor 10, high HP pool** (~80-100
  lean; the rugged-mass read — everything can hurt it, it doesn't
  care).
- **In-combat regen at the start of its turn** (user, overruling
  the out-of-combat lean — "I'm thinking like fighting annoying
  trolls in DCSS. in combat regen!... like a living machine that
  puts itself back together as it fights. Almost like
  Terminator"). NO out-of-combat tick: wounds persist between
  fights; it mends only while fighting. Line draft (PROSE GATE):
  "The Shredder's wounds begin to mend." — fires on the first
  successful mend per engagement; the target card's HP readout
  carries it after (wordless doctrine).
- **Power doctrine (user):** "we need these things to be powerful
  to make my characters find a challenge. this is the finale of
  act 0 after all." Start aggressive; dial back only if playtest
  says.
- Authoring lean: the cell-block ambusher (the existing
  bursts-out verb). Open floor stays free kills (law 1 holds —
  the prison's geometry is its ally).

**The Warden — the field + the slam:**

- **The field** (user: "what if the seal was around its own self.
  your ranged shots have to break through it first. more like a
  force field where each tile has its own hp... the alternative is
  advancing in to the force field so you can attack it in
  melee"): a personal force field, **one tile thick** (radius-2
  shell, empty interior), **each field tile carrying its own HP**
  (~30 lean = one railgun shot per tile). Projectiles crossing a
  tile hit the TILE, not the body; bodies pass freely; it stops
  everything both ways except the Warden's own fire. Geometry
  bonus: railgun min_range 3 makes the field's interior
  melee/pistol-only ground — the two attack roads (carve a lane
  from outside / walk in) are enforced by weapon bands, not just
  priced.
- **Field regen: in-combat, start of the Warden's turn, +10/turn
  minimum** (user: "just like shields in space regen at start of
  turn... minimum +10 regen per turn") — space-shield symmetry,
  ground-side. Destroyed tiles regrow from 0: a carved hole lives
  exactly ONE player volley round; blocking is binary (any HP > 0
  absorbs a full shot). The Warden's BODY does not mend — the
  field is its sustain, and self-repair belongs to the Shredder
  alone.
- **The slam** (user: "what if the slam did a pushback? making
  you have to move throught the force field again?"): heavy melee
  at adjacent range **with pushback** — knockback ~2 along the
  Warden→player vector (a wall stops the ride early), ejecting
  the melee player back through the shimmer onto the ranged road;
  closing becomes a loop (enter, swing, eat the slam, re-enter).
  The game's first involuntary-displacement mechanic; knockback
  authored as a WEAPON PROPERTY (data; player-side weapons may
  carry it someday). Deep-floor feature: ejected INTO a glowing
  stare zone — the machines combo.
- The devastating anti-armor shot STANDS (the family's
  armor-pierce holder — the one attack soak does nothing against;
  telegraphed lane; fires through its own field).
- The room-seal variant is NOT ruled out (a deep-vault Warden may
  also seal the door behind you — authoring, not identity).

Open items CLOSED (user rulings, same day):

- **Reference sheet: the two reference saves ARE the tuning
  target.** User: "we'll use these reference saves to tune. but
  first we need to build the systems. so in the final phase we'll
  retest with these saves and tune from there." Machinery builds
  first; the final build re-runs the battery against both saves
  and tunes from the measurement.
- **Exclusivity: "exclusive FOR NOW."** Prison-exclusive
  near-term; the doc-43 inhabitants handoff is not retired,
  merely deferred (the catalog may reach the far side someday, by
  later ruling).
- **Band: considered T4.** User: "they should be considered T4
  band. but, lets just build this and see where we end up.
  nothing is set in stone" — top-band threats, provisional until
  built. (The AP/dodge/item/reload conversation closed as
  SETTLED 43.)

## SETTLED 43 (2026-10-02) — the ground economy: carried ammo, weapon sets, the dial port

User, verbatim:

> They should carry and drop ammo (they already drop ammo for
> their weapon the are carrying). They shouldn't have a full stack.
> Maybe a little RNG in the ammo ammount they carry to reload from?

> I think NPCs should carry a range and a melee set. Just like the
> player. They should choose to switch to their melee set at times
> that make sense. much like we talked about in space combat, when
> they run out of missiles, they should stop trying to kite to
> missile range. when they run dry on ammo, they should switch to
> melee with 1 AP and choose melee.

> cornered-switch, yes. it's still the same tactic. consider
> centaurs in DCSS. they have devestating bow attacks, but if you
> get them in melee they switch to melee attacks. it's the
> strategy to beat that problem.

> yes. port the dial. their behavior changes (but predictably)
> based on combat circumstances.

Rulings:

- **Carried ammo — the SETTLED 36 pattern extended to ammunition.**
  Enemies carry AND drop ammo for their carried weapons: the
  existing death-roll becomes the magazine pool they shoot from.
  Pre-rolled at first resolution (the idempotent stamp), partial
  with a little RNG — NOT a full stack (lean: half to
  three-quarters of the old death-roll range). Reload pays AP when
  the magazine empties — the beat is the TELL (a reload log line
  is the player's window; PROSE GATE). Fully dry = the Tier-0 walk
  to first affordable action. Death drops the REMAINDER: the
  death-time ammo roll RETIRES (carried replaces rolled — what
  drops reflects the fight; shot-starving is a minor play).
- **Weapon sets — the player model mirrored (doc-51 parity).**
  Humanoid specs carry a RANGED set and a MELEE set. Dry → 1-AP
  swap → melee. The band governor keys the ACTIVE weapon, so a dry
  gunner stops kiting to gun range and closes — the
  raider-never-fires lesson (position governors key the fireable
  subset) applied ground-side with no special case. Switching is
  EMERGENT from the volley scorer — both sets scored by EV-per-AP,
  the swap cost folded in: dry (gun unaffordable), point-blank
  (the min-range penalty craters gun EV), cornered (no in-band
  cell exists — the knife outscores inertness).
- **CORNERED-SWITCH — amends SETTLED 26:** "pinned against a wall,
  a ranged enemy is inert" becomes "swaps to its melee set."
  Cornering stays the strategy (the DCSS centaur: melee the archer
  to beat the bow) but stops being free — a trade, not a
  shutdown. Both carried weapons DROP ("what they carry is what
  drops") — ECONOMY WATCH: a rifleman loots as rifle + knife +
  ammo remainder.
- **The aggressiveness dial PORTS ground-side — amends SETTLED
  23's "Space-only" line.** Ground specs gain the authored
  fire-vs-reposition dial (10-90); the behavior field keeps its
  out-of-combat job (hunter/guard/ambusher). One dial, one job,
  both theaters: low-aggression enemies dance and stack dodge,
  high-aggression ones sit and fire every AP; the Watcher's drift
  identity is the far end of the dial, not a special case.
- **Participation is by WEAPON DATA, not faction:** anything with
  a magazine carries ammo; claws, organic monster parts, and the
  stare don't. The ancient family is untouched unless an
  ammo-fed ancient weapon is authored someday.
- **Rides SETTLED 41's build-first rule:** the machinery — loop +
  carried ammo + sets + dial — lands as phase 9 build 1; the
  battery measures; number tuning follows the measurement.
  Brief-time corners: the dry guard's leash (an active-weapon
  leash reads as "a dry guard holds its post"), ammo pool ranges,
  default dial values before per-spec authoring.

## SETTLED 44 (2026-10-03) — the Warden's shot is a normal volley weapon

User, verbatim:

> this is just a normal shot. no charge up. no telegraph. just an
> advanced ancient alien tech that shoots with an AP cost. AP cost...
> 3? making the warden pretty stationary but hit hard.

Rulings:

- **No telegraph, no lane, no charge — supersedes SETTLED 42's
  "telegraphed lane" clause.** The anti-armor shot is an ORDINARY
  weapon in the build-1 volley economy: scored by EV-per-AP like
  every weapon, paid from the Warden's AP, resolved through the
  shared hit math. Its armor-pierce is a DAMAGE behavior (soak
  contributes zero), not a to-hit behavior.
- **`ap_cost` 3 (user lean)** — with the Warden's low authored AP,
  firing IS the round: "making the warden pretty stationary but hit
  hard." The Warden's own AP budget is a brief-time lean (3: a
  firing round leaves nothing for movement).
- Armor-pierce and fires-through-its-own-field STAND (SETTLED 42).

## SETTLED 45 (2026-10-03) — the ancient glyphs: O / S / W; brief approved

User, verbatim (on the proposal Watcher `o` / Shredder `S` / Warden
`W`):

> uppercase O works. approved brief

Rulings:

- **The ancient glyphs are Watcher `O`, Shredder `S`, Warden bold
  `W`** — three DISTINCT letters, each machine its own silhouette.
  Lowercase `o` was rejected mid-ruling for colliding with
  `prison_panel_normal`'s cyan `o` tile (`world.py:137`) on the
  machines' own panel-heavy floors. Cross-context shares (the sun
  `O`, Saturn `S`) are the tolerated space-map class (the
  dust_prowler-`p` precedent) — a ground face never co-renders
  with the space map. All three free in both live registries;
  `W` was the retired warlord boss glyph, unclaimed since phase 3.
- **The ancient family unifies by COLOR, not letter — amends
  SETTLED 34's one-letter+case convention for this family:** three
  utterly different machines read as three shapes in one cold
  violet (170,140,250, approved with the brief); the
  family-conformance lint expects the distinct-letter form for the
  ancients. Bold stays the Warden's unique callout — emphasis now,
  not disambiguation.
- **The brief's approval carries its three flagged leans as
  ruled:** the combat-scoped stare (pending zones fade on
  disengage and on the Watcher's death), the rock_scavenger →
  hull_parasite-only prison pools, and the three drafted lines
  (shriek / shimmer-absorb / shimmer-break) as written.

## Pre-implementation audit — phase 9 (2026-10-02)

**Reuse (verified):**

- **The AP loop skeleton stands — with FOUR `_fired` consumers, not
  one**: `_spend_ground_ap` (`combat/_ai_ground.py:100`) is
  while-per-AP with `_range_step` (close / hold / back-off / dance,
  SETTLED 26) and cached-path advance. The one-shot cap gate is the
  single check at `:110`, but the flag also feeds `_range_step`'s
  dance branch (`:158`), the "moves into position" log gate
  (`:129`), and — critically — the movement-dodge LEDGER:
  `_spent_as_movement` (`_rules_ground.py:753-762`) books
  everything except one fired weapon's AP as movement cells. A
  volley loop that does not return ACTUAL cells moved would book
  reloads and swaps as dodge and inflate enemy evasion (reviewer
  issue 2, folded: the loop returns real cells; all four consumers
  migrate together).
- **The scorer to port exists**: space `score_weapon`
  (`combat/_ai.py:271`) — damage × hit-chance-at-distance ÷
  ap_cost, the same hit math the shot resolves with. The ground
  twin scores through `ground_hit_chance_raw`; the shield-strip
  branch drops (no ground strip mechanic).
- **The set system is fully built player-side**
  (`ground_weapon_sets.py`): membership derives from
  `damage_type` alone (`_SET_BY_DAMAGE_TYPE` — kinetic/energy →
  ranged, melee → melee); the swap is 1 AP, never turn-ending
  (`swap_weapon_sets`, `_ground_actions.py:77`); magazines ride
  the instances. The enemy mirror classifies through the SAME
  table — no new set law.
- **The magazine model is weapon data**: `ammo_capacity` (−1 =
  infinite; melee/plasma), `ammo_type`, `reload_ap_cost`
  (default 1) on the ground weapon spec; the player reload action
  exists (`reload_weapon`, `_rules_ground.py:603`). The enemy
  reload charges the same weapon-data cost.
- **First-resolution stamps have a home**:
  `_build_enemy_instance` already stamps the rolled weapon
  (`noise.ensure_rolled_weapon` — idempotent, serialized) and the
  carried consumables (`_stamp_enemy_loadout` — SETTLED 36's
  pattern). The two-set loadout stamp and the carried-ammo pool
  stamp land at the same site, same shape. `roll_weapon`
  (`ground_scale.py:144`) rolls ONE weapon today — it gains a
  loadout sibling that fills BOTH sets through the same family
  windows.
- **Death drops retire cleanly — in BOTH branches** (reviewer
  issue 1, folded): the weapon-matched ammo stack the user's
  ruling cites is `_spawn_kit_drop` (`combat/_actions.py:197-236`
  — the resolved weapon + one matching ammo roll, `on_kill` passing
  the single `weapon_id/quality` at `_rules_ground.py:686-690`),
  SEPARATE from the authored-pool ammo entries in
  `_spawn_field_item_loot_at_position` (`:155-194`). The kit drop
  drops BOTH set weapons (the ranged slot's quality stamps as
  today; the melee slot rolls its own) and its ammo stack becomes
  remainder-of-carried; the authored ammo entry retires its
  death-time roll (the consumable precedent branch).
- **The dial exists to port**: `ai_aggressiveness: int = 50` on
  NpcShipSpec (`data/npc_ships/__init__.py:106`) with the
  fire-vs-reposition roll at `_ai.py:170` — the ground twin is
  the same field on NpcCharSpec + the same roll in the loop's
  fire branch.
- **Machines at T4**: `BAND_LEVELS` (3/10/18/30), `band_budget(4)`
  = 145; `derive_stats(spec, 4)` distributes over the spec's
  `stat_weights` — the ancient rows are ordinary band-4 rows with
  authored hp/armor/ap plus the new machine fields (builds 2+).

**Duplication hotspots:**

1. **The scorer twins** (space `_ai.score_weapon` / ground's):
   same EV shape, different hit math per theater — a forced share
   would couple the theaters; the DRY line is the SHAPE, not the
   code.
2. **Swap twins**: the player's `swap_weapon_sets` (ctx menus,
  logs) vs the enemy's set-switch (instance state, silent) —
   share the classification table, never the action.
3. **Reload twins**: player (bandolier store) vs enemy (carried
  pool store) — different stores by design; share only the
  weapon-data cost read.

**DRY strategy:**

1. `ground_scale.roll_loadout(spec, band, rng)` — both sets
   through the existing windows; fixed-weapon rows (fauna,
   machines) keep their `weapons` verbatim and never call it.
2. ONE `_score_ground_weapon` beside the loop; affordability =
   AP in bank + (magazine or carried pool) non-empty.
3. The loadout stamp EXTENDS `rolled_weapon` (old saves: the
   stamped pair maps to the ranged slot; the melee set resolves
   on first engagement — migration one line).

**Ratchet:** `_rules_ground.py` sits at 958/1000 — the stamp
extension pays line-neutral or the reload helper extracts
(alongside `_ground_effects`); every other touched module ≤ 835.

### Phase 9 Implementation brief — BUILD 1: the volley loop +
### economy (APPROVED 2026-10-02 — v2, reviewer ADVISE pass folded
### first: 11 issues / 4 blocking; SETTLED 41/43 + the amended
### 26/23; the machines are builds 2+, briefed after this measures)

**Scope (files / hook points):**

- **The loop** (`combat/_ai_ground.py`): kill the `_fired` gate —
  every decision point scores BOTH carried sets' weapons
  (EV-per-AP through `ground_hit_chance_raw`, quality folded in,
  **`shots_per_action` folded in** — burst weapons score their
  burst, else the smg halves against rifles), fires the top
  affordable scorer, repeats until AP, ammo, or positive scores
  run out. When the best score lives in the OTHER set: 1-AP swap
  (once, not per shot; silent — no log line), then proceed. In
  band with LOS, the aggressiveness roll (RNG vs the spec's RAW
  dial — the space `_effective_aggressiveness` shield/hull bend
  is deliberately NOT ported; re-rolled per decision point; roll
  below fires, at/above repositions) picks fire vs a reposition
  step. Leftover AP after nothing affordable goes to
  repositioning while a legal in-band step exists (SETTLED 40's
  termination shape). **The loop returns ACTUAL cells moved** —
  the `_spent_as_movement` ledger (753-762) books real movement
  only, never reloads/swaps; all four `_fired` consumers (the
  gate, `_range_step`'s dance branch, the log gate, the ledger)
  migrate together.
- **Resolution uniformity — enemy shots GAIN the point-blank
  penalty** (the reviewer's blocking contradiction, resolved
  toward parity): today `_roll_ground_shot` resolves WITHOUT
  `range_penalty` while the player's path pays it
  (`_rules_ground.py:434-450`). Build 1 adds the penalty to enemy
  resolution — ONE hit math, both sides — which is what makes the
  point-blank set-switch trigger real (a hugged gun's scores
  crater honestly, not vacuously). Called-out behavior change
  (enemies hit less when you stand inside their min range); NOT a
  roster number re-tune — the player's own rule mirrored.
- **The ammo economy** (`_ai_ground` + `_rules_ground` +
  `_actions`): every ammo-fed carried weapon fires from its
  magazine (per-weapon `loaded` state on the enemy instance — the
  player instance's `loaded_ammo` mirror); empty magazine →
  reload pays the weapon's `reload_ap_cost` from AP, the tell
  line fires (PROSE GATE, "{name} slams in a fresh
  magazine."-shape), refill drawn from the carried pool; pool
  empty → the weapon scores 0 and the walk goes to the first
  affordable action (the other set, by scorer). **The kit drop
  drops BOTH set weapons + the pool REMAINDER as its ammo stack**
  (`_spawn_kit_drop`, `on_kill` passes the loadout); the
  authored-pool ammo entries' death-time roll RETIRES.
- **The stamps** (`_rules_ground._build_enemy_instance` +
  `ground_scale` + `saveload_maps`): `rolled_weapon` extends to
  the two-set loadout + per-weapon magazine counts + the
  active-set flag (a mid-fight save after a cornered swap loads
  on melee) + the carried pool (the `carried_items` shape).
  Migration is a load-shim (the len-2 pair → ranged slot), NOT
  one line: readers to migrate are `noise.ensure_rolled_weapon`,
  `noise.guard_leash`, `_build_enemy_instance`, and the
  saveload len-2 load (`saveload_maps.py:269-274`).
  **`guard_leash` keys the RANGED slot's weapon, always** — a
  swapped-to-melee guard keeps its authored kingdom (SETTLED 43's
  dry-guard corner, resolved).
- **The dial** (`data/npc_chars/__init__.py`):
  `ai_aggressiveness: int = 50` on NpcCharSpec (no constructor or
  lint collisions — identity keys faction/glyph; SimpleNamespace
  test factories gain the attr).
- **The melee-set mechanism** (the reviewer's blocking authoring
  gap, resolved): a sibling field `melee_families:
  tuple[str, ...] = ()` — rolled through the SAME band windows as
  the ranged set, classified by the same table; empty = no melee
  set (fauna, machines with organic parts). The "families take
  precedence, never author both" law stays PER SET: ranged =
  `weapons`/`weapon_families` as today, melee = `melee_weapons`
  fixed or `melee_families` rolled. Data pass: humanoid rows
  author the melee set (the knife-class default where nothing
  better fits).
- **Noise untouched, but pinned** (reviewer minor): reloads and
  swaps emit NOTHING (SETTLED 22 holds); multi-fire multiplies
  per-shot emissions — the phase-5 regression pass gains an
  explicit volley-fire noise/investigation pin.

**Build order:** stamps + loadout roll incl. `melee_families`
(registry/stamp tests first) → the scorer + loop gate-kill +
ledger (volley pins) → resolution-uniformity penalty → reload +
dry-walk + the tell → the dial field + roll → kit-drop/field-drop
retirement → seeded-test repair → the battery re-measure (both
reference saves + the starter standard, recorded here) → full
gate.

**Binding rulings:** SETTLED 41 (the cap dies; loop lands ALONE,
NO roster number changes — measurement first; the point-blank
penalty is a math-parity change, not a number tune), 43 (carried
ammo, sets, cornered-switch, the dial, guard-leash-on-ranged),
26-as-amended (cornered swaps to melee), 23-as-amended (the RAW
dial both theaters; the space bend stays space), 22 (noise
untouched), 36/37 (the stamp patterns). The player's
fire/swap/reload paths are read-only mirrors — zero player
behavior changes.

**Stop point:** no machine specs or machinery (the stare, the
field, knockback, mend — builds 2+); no roster stat/damage
retunes; no noise changes; no new player-facing UI; no guide
entry.

**Required tests:** volley (per-AP multi-fire incl. same weapon;
scorer pins: EV ordering, quality folded, shots_per_action
folded, min-range penalty craters point-blank scores ON BOTH
SIDES); set-switch triggers (dry → melee + band governor keys
the knife — STOPS kiting; point-blank economy; cornered — no
in-band cell → knife); swap costs 1 AP once; reload (pays
weapon-data AP, tell fires, magazine/pool decrements, remainder
drops via the kit drop, no death-time ammo roll remains in
either branch); dry-with-no-melee walk behavior; aggressiveness
extremes (10 = dancer stacking REAL move dodge, 90 = sits and
fires); **the ledger pin (a volley+reload+swap turn books only
actual cells — dodge never inflates)**; resolution parity (the
point-blank penalty on enemy shots, pinned both directions);
stamp round-trips save/load incl. the migration shim (old-save
pair → ranged slot) + magazine counts + active-set flag +
guard-leash-keys-ranged; termination (no affordable weapon + no
legal step breaks — never spins); volley-fire noise/investigation
pin; **seeded-test repair** (first-resolution draws at hearing
time shift the global stream — `test_ground_tactics` seeds and
the `_rules_ground` seed-hunts re-pinned); regression: phase-5
tactics suite, band scaling, crews, city ambient.

**Ratchet:** BOTH limits bite `_rules_ground.py` (958/1000 lines;
`_build_enemy_instance` at 33 of the 40-line function cap will
not hold the three new stamps) — the stamp block extracts beside
its subject (a `_stamp_enemy_loadout` sibling in the same
module, cohesion-driven); the reload helper lives in
`_ground_actions.py` beside the player twin for the same reason.

**Playtest checkpoint:**

1. T2 dig (dev pin, pinned seed): riflemen fire 2-3 shots a
   round — the volley reads; one runs dry mid-fight, reloads
   (the tell line), keeps firing.
2. Bleed a rifleman's pool out (kite a few rounds): it swaps to
   its knife and CHARGES — no more kiting to gun range; the
   centaur read.
3. Hug a rifleman against a wall: he swaps to melee and swings —
   cornering still works (his weak set, AND his own point-blank
   penalty) but is no longer free.
4. Aggressiveness eyeball: default-50 v1; note any spec that
   reads wrong for the tuning pass's authored values.
5. Loot a fought rifleman vs an ambushed one: BOTH weapons drop;
   the ammo stack differs (remainder-of-carried).
6. Save/quit mid-fight → Continue: loadout, magazines, pools,
   active set, wounds identical; an OLD save loads with its
   stamped weapon in the ranged slot.
7. Regression: phase-5 noise/investigation, guard leashes,
   crews, bystanders unchanged.
8. Battery re-measure recorded in the doc: both reference saves
   across the standard rows + the starter-sheet standard — the
   before/after table IS the deliverable; roster tuning rides
   its numbers.
9. Guide-diff item: **LANDED WITH BUILD 6** — the loot line in the
   "Ground Gear" section (`data/guide/__init__.py`), exact
   before/after:
   BEFORE: "What an enemy fought with is what drops."
   AFTER: "What an enemy fought with is what drops: both weapons
   they carried and any ammo they had not spent."
   (The section's tail sentence "so deeper sites and tougher
   machines yield better gear" trimmed to keep the body under the
   3000-char conciseness cap; no other guide changes this phase.)

## Phase 9 BUILD 1 — LANDED + the battery re-measure (2026-10-02)

The volley loop + economy landed ALONE in seven builds (c63f3dcf
stamps + two-set loadout; 0c98f0b9 the volley loop + scorer + real
cells ledger; 26d22366 point-blank parity (ONE hit math, both sides,
the cornered-switch honest); 29e640ca reload-from-pool + the tell;
2686c69d the RAW dial at default-50; 4a615d09 the kit-drop law (both
weapons + remainder, the machines' authored ammo channel preserved);
780e29d8 the last required pins). Reviewer: every build dispatched —
three REQUEST_CHANGES (untested wrappers; the dry-mag statue + stale
magazine; the unreachable penalty; the zeroed machine channel) all
reproduced, folded, and re-approved. Zero roster number changes; the
player's fire/swap/reload paths are untouched mirrors.

**The battery (the deliverable): both reference saves, 50 seeded
runs/row, the same rows as the 2026-10-02 arrival sim.**

| Row | labs pre -> post | merchants pre -> post |
|---|---|---|
| 3x rock_scavenger b1 | 1.000 / 0.02 -> 1.000 / 0.02 | 1.000 / 0.00 -> 1.000 / 0.02 |
| 5x pirate_rifleman b2 | 1.000 / 4.66 -> **0.940 / 4.04** (3 def; worst 16 -> 26) | 1.000 / 12.26 -> **0.840 / 9.83** (8 def; worst 44 -> 46) |
| 5x pirate_brute b3 | 0.940 / 16.79 -> 0.960 / 11.62 (2 def; worst 38) | 0.920 / 19.20 -> 0.920 / 12.67 (4 def; worst 48 -> 42) |
| 5x assault_drone b4 | 1.000 / 0.00 -> 1.000 / 0.00 | 1.000 / 0.00 -> 1.000 / 0.00 |
| 5x consortium_gunner b4 | 1.000 / 3.44 -> 1.000 / 3.36 | 1.000 / 3.36 -> 1.000 / 3.14 |
| 10x assault_drone b4 | 1.000 / 0.06 -> 1.000 / 0.06 | 1.000 / 0.06 -> 1.000 / 0.06 |
| space warlord / 2x marauder | 1.000 / 0.900 -> bit-identical | 0.280 / 0.140 -> bit-identical |

Readings (input to the machines' authoring, not rulings):

1. **The dial trades sustained pressure for burst variance.** The
   prediction ("gunner/rifleman damage roughly triples") measured as
   a mean that FELL at default-50 (the dance halves fire rate:
   riflemen 12.26 -> 9.83 into the merchant sheet) while the WORST
   case rose and a death tail appeared (0 -> 8 defeats vs band-2
   riflemen): the volley's multi-shot turns spike where the one-shot
   era averaged. The terror is variance, not mean.
2. **Band-1 and the tutorial standard are UNCHANGED** (scavenger
   melee: dial-exempt, 2-turn fights) — law 1 stands; the reference
   saves still trivialize band 1 (0.02 dmg).
3. **The dry-switch caps the gunners**: ~3.2 dmg/hit sustained (vs
   the brute's spikes) — magazine + 2-4 pool rounds then the knife.
4. **Band-4 melee drones stay zero threat** (law 1 holds on both
   sheets) — the machines' bars (Watcher/Shredder/Warden) fill this
   hole, authored against THIS loop.
5. **Space is untouched** (bit-identical, including the merchant
   trade-fit collapse — still unattributed, still prison-irrelevant).
6. The doc-50 starter-standard rows re-measured + re-pinned at every
   build that moved them (the countered lane RE-ARMED at 0.76 after
   the dial halved the sentry's fire rate; the tuning pass re-authors
   against these reference saves). The probe's g_mars_pinned row
   re-pinned to the glow ruling's true-sight cells (the doc's
   tooling note, closed).

Instrument gaps (carried from the audit): PlayerSheet still cannot
express ground stat spends or gear qualities; the probe/board grid
path for the mars_alien_prison extension floors is still pending —
the machines' build re-runs THIS battery plus the extension rows.

### Phase 9 Implementation brief — BUILD 2+: the ancient machines
### (APPROVED 2026-10-03 — SETTLED 29-as-amended + 41/42/43/44/45;
### authored against the post-loop battery; reviewer ADVISE pass
### folded first: 14 issues / 6 blocking — the weaponless path's
### four gate sites, dial-on-drift, the stare's combat scoping,
### armor_bypass reuse, the eruption kill tail, the re-pin's test
### blast radius; glyphs O/S/bold-W + the flagged leans ruled with
### the approval)

**Scope (files / hook points):**

- **The weapon family** (new `data/ground_weapons/ancient.py` +
  registry): the family's own module, never cross-resolved with
  human bands (SETTLED 29); every row `loot_droppable=False` (no
  usable drops — the sites pay in alien tech). Rows: **shredder
  claws** (melee, 2 AP, no magazine — SETTLED 43: participation is
  by weapon data, nothing ancient is ammo-fed); **warden slam**
  (heavy melee, carries the NEW weapon field **`knockback: int
  = 0`**, authored 2 — data; player-side weapons may carry it
  someday); **warden shot** (ranged, **`ap_cost` 3**, armor-pierce
  via the EXISTING `armor_bypass: bool` weapon field (reviewer
  issue 4) — already read in the shared damage math beside
  plasma's halving (`_ground_math.py:67-70`; authored precedent +
  player UI in melee.py) — zero new math; fires through its own
  field; authored min/max band so the point-blank penalty
  composes honestly; damage dial lean 25-35 unsoaked; NO
  telegraph/lane/charge — SETTLED 44). The stare is NOT a weapon
  (a mechanic below). Soak semantics resolved per the 10-02 sim's
  flag: the family authors EXPLICIT per-weapon behavior (stare
  full soak, claws full soak, shot pierce) — no new energy-type
  math. Noise columns authored (dials: claws 1-2, slam 2-3, shot
  8; the shriek is the loud one).
- **The specs** (new `data/npc_chars/ancients.py` + registry +
  family): three `always_hostile` rows, mechanics data authored ON
  the rows (value 8 — stare/shriek/mend/field parameters as
  declared NpcCharSpec fields or one frozen profile field,
  owner-declared): **Watcher** — hp lean 14-20 (TTK 1 by intent),
  armor 0, ap 4, reflexes-max weights, dial lean 15 (the drift),
  authored REF 90-100; **Shredder** — hp 80-100, armor 10, ap 6,
  strength/stamina-heavy, mend lean 5/turn, cell-block ambusher
  (the bursts-out verb); **Warden** — hp 65, armor 12, ap lean 3,
  guard behavior (holds ground), field tiles lean 30 HP each.
  Stare dials per SETTLED 42's numbers section; shriek radius
  25-40. **Band resolution: the rows derive at band 4 FLAT** — the
  site's floor-band stamp never dilutes them (SETTLED 42
  T4-provisional; the difficulty axis is row-picking per floor,
  SETTLED 29). Mechanism: `fixed_band: int = 0` on NpcCharSpec
  (ancients author 4; 0 = the entity stamp) applied at the ONE
  choke point (reviewer issue 12): `entity_band` gains the spec
  param and BOTH spec-holding callers (`_build_enemy_instance`,
  `ground_loadout.ensure_loadout`) pass it — the ancients' loadout
  side is inert (fixed weapons, zero quality draws), but the param
  pins the twin shut for any future fixed-band row. RNG note: the
  ancients draw nothing at first resolution; stream shifts come
  from turn-time draws only.
- **The stare** (new `combat/_ancients.py` + `GameMap.stare_zones`
  declared at world.py, the `hostile_interior` precedent): a
  seeing Watcher fixes the player's cell at enemy phase (free
  action — the marking, not an attack) — a 3x3 GRADED zone (core
  full, ring half pre-soak); **eruption at the end of the player's
  following turn** (hook beside the round-end processing; exactly
  one full turn to vacate); **no to-hit roll; damage respects
  armor** (full soak); re-fixes every round it lives (the perpetual
  dance); anything in the zone at eruption takes it — the first
  enemy-vs-enemy damage vector (machines oblivious to marked
  cells); multiple Watchers coincide + STACK (count = the
  floor-authoring dial); the eruption is one deduped blast-class
  noise event per cell per beat. **The stare is COMBAT-SCOPED
  (reviewer issue 3 — v1's "erupts regardless of combat state"
  reading WITHDRAWN: out of combat there is no round clock, no
  ground_hp writer, no death path, and building them is machinery
  the doctrine never asked for):** breaking LOS ends the fight
  (SETTLED 24/25) and pending zones FADE with it — disengage
  defuses; a dead Watcher's zones fade too. Eruption victims
  beyond the player (the baiting vector; reviewer issue 5):
  victims resolve through the instance-build path (hp stamped on
  demand); an eruption kill runs the death handling — the victim's
  own drops land, but NO player XP/rep (no player attacker); a
  player killed by a stare carries the marking Watcher as the
  tombstone killer. Log lines: SETTLED 42's user drafts, verbatim.
  Zone state serializes; old saves tolerate absence.
- **The shriek** (volley-loop preamble + `noise.py`): fires the
  round LOS opens and again as the Watcher's FIRST AP every round
  it still sees you — a 1-AP LEAD ACTION before any scoring (not a
  weapon, never scored); emits through the EXISTING noise
  system's hearer machinery via ONE new radius-keyed entry point
  (reviewer issue 7: `noise.emit` is weapon-id-keyed today —
  `noise.emit_radius`; the shriek and the eruption share the one
  variant, no ad-hoc hearer loops) at radius 25-40; heard ≠
  aggroed (SETTLED 16), dormant stay deaf
  (SETTLED 22), no spawns (SETTLED 21). The charge/wind-up
  softening lever stays DEFERRED (SETTLED 42 — playtest decides).
- **The drift needs one loop generalization, at FOUR gate sites
  (reviewer issues 1-2):** the Watcher carries NO weapon row (the
  stare is its attack) — a weaponless spec statues today at
  `_rules_ground.py:745` (the `weapon_id` turn gate: no turn at
  all), `_ai_ground.py:63` (`has_any_weapon`), and the
  `_aws is None` inert decision point (`:237`); and the
  `not _fired` log gate (`:222`) would print "moves into
  position." every round. All four migrate together (the build-1
  four-consumer lesson): with nothing affordable to fire, leftover
  AP goes to drift steps — each a WALKABLE, LOS-KEEPING step
  ("legal" sans a weapon band), each gated by the SAME
  aggressiveness dial rolled per decision point (below → hold;
  at/above → one step) so the authored dial composes instead of
  reading dead. A weaponless turn LOGS NOTHING (wordless — no
  per-round position spam). Uniform across every spec, no machine
  carve-out; the Watcher's drift identity = this rule + its dial
  + authored REF.
- **The mend** (start-of-turn hook beside the round tick): the
  Shredder heals its mend rate at the START of its turn, IN-COMBAT
  ONLY (fight-live state); NO out-of-combat tick (wounds persist
  between fights); the line fires once per engagement (user
  draft), wordless thereafter (the target card carries it).
- **The force field** (`combat/_ancients.py` + GameMap field-tile
  state + the projectile seam): a radius-2 shell (one tile thick,
  empty interior) around the Warden, EACH tile its own HP (~30
  lean); **projectiles crossing a shell tile hit the TILE — binary
  blocking (any HP > 0 absorbs a full shot), both directions (the
  TWIN seams, reviewer issue 8: `_roll_player_shot`
  `combat/_loop.py:322` AND `_one_enemy_shot`
  `_ai_ground.py:508`; doc-57 ground flight missiles absorb too —
  they are projectiles, no exemption), exception: the Warden's
  own shot**; bodies pass freely (walkable); destroyed tiles
  regrow from 0, +10/turn at the start of the Warden's turn
  (in-combat) — a carved hole lives exactly one player volley
  round; the body never mends (the field is its sustain;
  self-repair belongs to the Shredder alone). State keyed by
  position, re-derived from the Warden's position each turn,
  serialized; render = a shimmer overlay through the world draw
  path (CP437-safe glyph + family color; exact char a playtest
  dial). Explosive splash is AREA, not projectile — but the
  blast's victim enumeration (`explosive_blast`) gains field
  tiles as a victim class: the code behind "a rocket at the shell
  carves multiple tiles" (the called-out counter). The player
  inside the shell shoots OUT
  through tiles (absorbed) — the interior is melee ground by
  geometry, enforced by economy, not exception.
- **Knockback application** (beside the ground step helpers): the
  slam displaces the victim ~2 along the attacker→victim vector; a
  wall stops the ride early; an occupied cell stops it (no
  stacking); pure displacement — NO collision damage (not ruled;
  keep it pure). The game's first involuntary displacement.
- **The prison re-pin** (`data/dungeon_extensions/__init__.py` +
  `dungeon_activation.py`): every activation event + monster pool
  swaps sentry_drone → **Watcher**, assault_drone → **Shredder**
  (the sentinel / melee-anchor mapping); **the deep-cell Wardens
  arrive via AUTHORED activation events** (new/edited events on
  the extension spec — reviewer issue 9: the sentry→Watcher
  mapping alone would deliver Watchers there too); the hardcoded
  dormant fallback (`dungeon_activation.py:639`,
  `["sentry_drone"]`) becomes AUTHORED DATA — the fallback
  security id lives on `DungeonExtensionSpec` (data-first, no
  alien-ness branch), the prison authoring its ancient row
  (SETTLED 29's dormant override, dissolved into data); **the
  rock_scavenger pin** (FLAGGED for user sign-off — a punch-list
  rider, not a SETTLED ruling): prison monster pools drop the
  desert fauna (lean → hull_parasite-only pools; station vermin).
  ZERO changes outside the prison — contemporary drones keep every
  non-alien job (pinned). Floor composition lean (tunable): F1
  Watchers; F2 Watchers + Shredders; F3 Shredder packs +
  Watchers; F4 Wardens at the deep cells + Shredders; counts stay
  ~1-3 per activation. Old-save story: a pre-build-2 mid-descent
  save keeps its live sentry/assault entities (the ids stay
  registered; they load as contemporary drones) — the "no drone
  id" pin scopes to GENERATION data, never live saves.
- **Identity** (`CHAR_CLASS_FAMILIES` + `tests/test_enemy_identity.py`
  + registry docstrings): the ancient family — **three DISTINCT
  letters, ONE cold constructed color, violet (170,140,250)
  (SETTLED 45)**: **Watcher `O`, Shredder `S`, Warden bold `W`**.
  The family unifies by COLOR, not letter — each machine is its
  own silhouette; the family-conformance lint expects the
  ancients' distinct-letter form (SETTLED 34's one-letter+case
  convention amended for this family). All three free in both live
  registries; the cross-context shares (sun `O`, Saturn `S`) are
  the tolerated space-map class, never co-rendered; lowercase `o`
  is REJECTED — `prison_panel_normal`'s cyan `o` tile collides on
  the machines' own floors. Fauna untouched (not families).
- **The battery + instruments** (final build): the probe gains the
  mars_alien_prison grid path (extension floors;
  `build_planet_grid` is planet-specs-only today) +
  corridor-geometry rows (the Shredder's lane and the Warden's
  corridor are the real weapons — the arena is open floor);
  re-run BOTH reference saves + the starter standard + the
  extension rows; the before/after table IS the deliverable; dials
  tune from the measurement (SETTLED 42's final-build retest).
  PlayerSheet's synthetic-sheet gaps close only if the tune needs
  them (the two real saves load whole).
- **Dev grants** (SPACEHACK_DEV, `dev_mode.py` + `test_dev_mode.py`):
  the trio spawned adjacent (disjoint per-face placement, the
  phase-4 precedent) so every checkpoint item runs without a
  descent.
- **PROSE GATE strings** (land only with user wording — drafts
  below for edit): SETTLED 42's five stare lines + the mend line
  land VERBATIM (user-drafted). NEW drafts: shriek — "The Watcher
  lets out a piercing shriek."; field absorb — "The shimmer
  swallows your shot."; field tile breaks — "A section of the
  shimmer breaks apart."; NO knockback line (the displacement is
  visible — wordless).

**Build order:** weapon family + `knockback` field (registry
tests) → specs + `fixed_band` + identity family + lint → knockback
application + the Shredder's mend → the Watcher (stare state +
fade-on-disengage + eruption hook + `emit_radius` + shriek
preamble + the four-site weaponless-dance unmute) → the Warden
(field state + both projectile seams + flight-missile absorption +
regen + the shot) → prison re-pin + authored fallback + Warden
events + scavenger pin (flagged) → probe extension + battery
re-measure + dial tune → full gate.

**Binding rulings:** SETTLED 29-as-amended (catalog, own weapon
family, authored-areas-only, no usable drops), 41 (machines run
the standard loop — no carve-outs; no roster number changes outside
the three rows), 42 (identities + mechanics + power doctrine:
start aggressive, soften only on playtest; the two reference saves
ARE the tuning target; exclusive FOR NOW; T4 provisional), **44
(the shot is a normal volley weapon — no telegraph, no lane, no
charge, `ap_cost` 3)**, 43 (participation by weapon data), 16/22/37
(shriek doctrine: heard ≠ aggroed, dormant deaf, goal-based
investigation), 34 (family letter + case + bold). The player's
action paths stay read-only mirrors; the field prices projectiles
uniformly, both sides' shots.

**Stop point:** no roster retunes beyond the three machines'
authored dials (roster tuning = the post-battery pass per SETTLED
41's measurement-first law); no far-side/doc-43 inhabitants wiring
(deferred, not retired); no room-seal Warden variant (a named
future authoring option); no shriek charge/wind-up (the deferred
softening lever); no biome fauna or apexes (10); no consortium
anything (11); no player-obtainable ancient weapons; no guide
entry (wordless doctrine — the machines teach by pattern;
confirm-grep); no player-behavior changes beyond the involuntary
displacement the slam authors.

**Required tests:** family (rows registered; `loot_droppable=False`
pinned; `knockback` default 0; `armor_bypass` authored True on the
shot — soak-zero through the EXISTING field, no new math); specs
(`fixed_band` 4 flat — a floor-1 stamp does NOT dilute; authored
hp/armor/ap; identity lint green incl. separation + bold wearers);
the stare (enemy-phase fix when seeing; graded core/ring; eruption
at end of the player's following turn — the vacate economy pinned:
1 AP to the ring, 2 AP clear; no to-hit roll; full soak; the
re-fix chain; stacked Watchers coincide + stack; enemy-vs-enemy
victims — hp-on-demand, the victim's drops land, NO player XP/rep,
a stare-killed player tombstones the Watcher; deduped eruption
noise through the `emit_radius` variant; pending zones FADE on
disengage and on the Watcher's death; zone state save/load
round-trip + old-save tolerance); the shriek (LOS-open round +
first-AP-every-seeing-round; costs 1 AP before scoring; the volley
proceeds after; radius; dormant deaf; heard ≠ aggro; no spawns);
the weaponless dance (no affordable weapon → leftover AP to
LOS-keeping steps while a legal step exists — never a statue; logs
NOTHING; the dial rolls on the weaponless path, extremes pinned;
build-1's never-spins termination re-pinned for weapon-CARRYING
specs; the ledger books real cells only); the mend (start of the
Shredder's turn; in-combat only; the line once per engagement;
wounds persist out of combat); the field (shell geometry radius-2
empty interior; per-tile HP; binary block — any HP > 0 absorbs a
full shot; both directions; own-shot exempt; flight missiles
absorb; walkable; +10 start-of-Warden-turn in-combat;
regrow-from-0 — the one-volley-round hole pinned: carve +
shoot-through in the same turn at base AP, blocked again after the
Warden's turn; destroyed tiles clear from the render;
serialization round-trip; field tiles as blast victims — the
multi-tile carve); knockback (property-driven; ~2 along the
vector; wall stop; occupant stop); the shot (3-AP cost;
volley-scored; unsoaked on both reference armor models;
through-field); the re-pin (every prison activation resolves
ancients; the fallback id reads the SPEC's authored field — the
`:639` hardcode dies; NO contemporary drone id remains in prison
GENERATION data, live old saves keep theirs; rock_scavenger gone
from prison pools; non-alien drone sites pinned unchanged —
landmarks, capture decks, cities; the named pin files re-pinned:
test_dungeon_extensions, test_main_quest_act1,
test_prison_dormant_security); integration (machines run the
build-1 loop; no one-shot-cap residue; seeded-test repair for
turn-time RNG shifts — the ancients draw nothing at first
resolution); the battery table recorded in the doc.

**Ratchet:** the new machinery lives in `combat/_ancients.py` +
fresh data modules; `_ai_ground.py` / `_rules_ground.py` touches
(preamble, eruption hook, projectile seam, damage behaviors) pay
line-neutral or extract beside their subject (the build-1
`_stamp_enemy_loadout` precedent) — counts checked at build start;
GameMap fields declare at world.py (cohesion).

**Playtest checkpoint:**

1. Dev grant the trio (SPACEHACK_DEV): the Watcher shrieks the
   round it sees you (line fires), the floor glows 3x3 under you;
   step out within the turn and the eruption hits nothing; it
   drifts — your railgun misses it like nothing you've fought
   (authored REF + drift dodge).
2. Stand still: the zone re-fixes every round; eat an eruption —
   armor soaks, still the 10-18 landed class; TWO stacked Watchers
   = move every round or die (the stacking dial).
3. Shriek chains: fight near dormant machines — active ones
   investigate (aggro only on LOS); dormant never stir.
4. Shredder: eats the opening railgun shot and stands; closes at
   6 AP; three claw strikes in a full round; wounds mend at its
   turn start (the line once per fight) and PERSIST between
   fights — flee, return, still wounded.
5. Warden (bold `W`): your shots vanish into the shimmer; carve a
   tile and shoot the body through the hole the SAME turn; next
   round the hole is closed.
6. Enter the field and swing: the slam throws you back out through
   the shimmer (~2, a wall stops you early); the loop reads
   (enter, swing, eat the slam, re-enter).
7. The shot: no warning — a hit that ignores armor entirely (the
   23-soak tank feels it full price); it barely moves the round it
   fires.
8. Rocket the shell: splash carves multiple tiles at once (the
   counter).
9. Prison descent: F1 Watchers → F4 Wardens at the deep cells;
   zero sentry/assault drones in the prison; zero rock scavengers;
   dormant security wakes ancient.
10. Save/quit mid-stare, mid-field → Continue: zones, tile HP,
    wounds identical; a pre-machines save loads clean.
11. Loot: the machines drop nothing usable — the site pays in
    alien tech.
12. The battery: both reference saves + the starter standard + the
    extension rows recorded in the doc; flag anything that reads
    wrong for the tune.
13. Guide-diff item: expected NONE (wordless doctrine, the SETTLED
    36 noise precedent — the mechanic is never named); confirm-grep
    `data/guide/`, any hit becomes a called-out before/after.
14. PROSE review: the user-drafted lines verbatim; the three new
    drafts (shriek / absorb / break) approved or reworded.

## Phase 9 BUILDS 2-6 — LANDED + the machines' battery (2026-10-03)

The ancient machines landed in five builds after the instruments
build: **b2a** the weapon family (`98a85066` — shredder claws /
warden slam / warden shot + the `knockback` weapon field; the
`armor_bypass` pierce through the EXISTING field, zero new math);
**b2b** the three specs (`ff8bc62e` — MachineMechanics dials +
`fixed_band` 4 flat + the violet distinct-glyph family O/S/bold-W;
+ `a8a8b436` the dev-pick shop-leak guard the review armed);
**b2c** knockback + the mend (`7d877992` — the slam's wordless
pushback through `_apply_hit_knockback` at the shot seam, live
ctx.player reads after displacement; the Shredder's in-combat mend,
once-per-engagement line verbatim); **b2d** the Watcher
(`2c2937a0` — `noise.emit_radius` sharing the one hearer walk; the
3x3 GRADED stare zones on GameMap with dead-Watcher pruning and
fade-on-every-end; the combat-scoped eruption hooked BEFORE enemy
turns in `_end_player_turn` so exactly one full turn to vacate
holds; eruption kills carry NO rep — the `stare_killed` flag shuts
the `get_combat_result` back-door the review caught; the four
weaponless-gate sites migrated together into the dial-gated
LOS-keeping drift — logs nothing, real ledger cells); **b2e** the
Warden's force field (`1dbd2914` — radius-2 Chebyshev shell of
walkable cells at full HP from combat entry; the ONE
`absorb_shot` read (Bresenham, endpoints excluded, field-carrier
exempt) shared by both projectile seams; binary blocking with the
overflow lost; +10/turn in-combat regen with destroyed tiles
regrowing from 0 — the one-volley-round hole; sibling shells
preserved through each other's re-derives (the review's empirical
catches: the wholesale replace destroyed them; a stare-killed
Warden left an ownerless shimmer); field tiles as blast victims —
the absorbed rocket detonates ON the shell and carves it without
ever touching the body); **b2f** the prison re-pin (`94ccbc26` —
every activation event + pool swaps to the machines, the deep-cell
Wardens arrive via AUTHORED SILENT events (the review falsified the
prose-reuse state-exclusivity: the wake is wordless, a dedicated
popup is the prose-pass question), the `:639` sentry fallback is
dead — `security_fallback_id` on the spec, the scavenger pin
FLAGGED below); **b2g** the instruments (`8ef927df` — Shift+A
trio grant + the probe's corridor/LIVE-floor rows; the review
EXECUTED the grant and caught `_adjacent_cells` returning offsets to
an absolutes consumer — both grant families (phase 4's included)
spawned off-map since their landings; fixed + placement-pinned, and
the lane's true 1-wide + the F4 row's populate purge re-measured
below).

Reviewer: dispatched per build (A: APPROVE, 3 minors folded incl.
the claws rename + the dev-pick guard; B+C one combined pass:
REQUEST_CHANGES (a stale dispatch — the tree moved mid-review, the
lesson: freeze during reviews; the mend wiring demanded in-commit)
then APPROVE after folds; D: REQUEST_CHANGES (the rep back-door +
the ordering pin that didn't discriminate hook position — the
reviewer proved it empirically) then APPROVE after the spy-pinned
fold; E: REQUEST_CHANGES (the sibling-shell destruction + the
orphan field, both reproduced by the reviewer in-memory) then
APPROVE; F: REQUEST_CHANGES (the falsified popup-exclusivity) then
APPROVE; G: APPROVE). Zero roster number changes outside the three
rows; the player's action paths are read-only mirrors beyond the
slam's authored displacement.

**The battery (50 seeded runs/row, both reference saves; the
standard rows re-measured for continuity, the machine rows are the
deliverable).**

| Row | labs (23 soak, 40 HP) | merchants (16 soak, 52 HP) |
|---|---|---|
| g_mars_pinned (continuity) | 1.000 / 0.02 | 1.000 / 0.02 |
| 5x rifleman b2 (continuity) | 0.940 / 4.04 (3 def) | 0.840 / 9.83 (8 def) |
| 5x brute b3 (continuity) | 0.960 / 11.62 (2 def) | 0.920 / 12.67 (4 def) |
| 5x / 10x b4 drones+gunners (continuity) | 1.000 all | 1.000 all |
| **2x watcher, open arena** | 1.000 / 0.00, 2.0 turns | 1.000 / 0.00, 2.0 turns |
| **2x shredder, the 1-wide lane** | 1.000 / 0.40, **15.5 turns** | 1.000 / 26.52 (worst 51) |
| **1x warden, the 5-wide hall** | 0.940 / 20.43 (3 def) | 0.960 / 20.00 (2 def) |
| **the F4 authored mix (live floor, ISOLATED trio)** | **0.020** (28 def / 21 dis) | **0.200** (16 def / 24 dis) |

Readings (input to the tune, not rulings):

1. **Continuity is bit-identical to build 1's post table** — the
   no-roster-changes law held through every build.
2. **The sentinel cell reads as designed**: lone Watchers are
   trivial at the 95%-hit railgun ceiling (TTK 1, 2 turns) — the
   threat is STACKING and what they herd you into, authored per
   floor.
3. **The lane differentiates the sheets exactly as SETTLED 42
   ruled**: labs (23 soak) grinds 15.5 turns for 0.8 damage — it
   thrives on claws; the merchant sheet (16 soak) eats 25.16 of 52
   in 3 turns — maims, doesn't delete.
4. **The Warden hall contests BOTH sheets** (~0.94-0.96, ~20 mean
   damage, worst 30 = the armor-bypassed shot landing full price on
   either soak model).
5. **THE TUNE'S HEADLINE — the F4 authored trio alone is a wall**:
   labs 0.020, merchants 0.200 — with the floor's own populate
   scatter PURGED (the isolated-fight doctrine; the review caught
   the row measuring trio+mob), the authored 2-shredder + 1-warden
   mix kills 80-98% of the engagements it starts. Caveat: the row
   compresses the floor into ONE simultaneous close-quarters
   encounter (the real descent wakes events sequentially along the
   route), so it reads as the breaking-point stress, not the
   descent simulation. Per SETTLED 42's own words the tune happens
   FROM this handoff ("in the final phase we'll retest with these
   saves and tune from there"): dials on the table = the F4/F5 mix
   + counts, the warden-heavy F5 extraction gauntlet (4 dormant
   wardens wake at the terminal — emergent from the extras
   round-robin, not authored), the shredder claws/slam/shot
   numbers.

MID-PLAYTEST FINDINGS (2026-10-03, the reset-save descent):

1. **"Enemy shredders never attack" — the diagonal-adjacency melee
   deadlock, FIXED (`712f795d`).** The user's report + the tombstone
   log ("Shredder moves into position. x30") reproduced instantly:
   every melee enemy deadlocked at DIAGONAL adjacency — the enemy
   band gates compared RAW Euclidean distance (1.414 > max_range 1)
   while the player's own fire gate int-truncates. Pre-existing
   (doc-51 era), first EXPOSED by the Shredder (the first melee
   enemy that reliably survives its approach). The fix int-truncates
   `_within_max` (the shared max-band law) + the gap-step close leg +
   the dance pool; the enemies-panel threat readout migrated with the
   gate (the reviewer's twin catch — it called swinging enemies
   safe). Consequence: the doc-50 `goal_2_mars_batons` ruled bars
   were calibrated against the broken scavengers (only the FIRST of
   a swarm could ever swing; post-fix all three do: win 0.000 / 50
   def in <=2 turns; was win 1.00 / 12.4 dmg / 4.04 turns) — the row
   is REPORT-ONLY pending the user's re-ruling, joining the p9 tune
   list (SETTLED 41's own prediction: "band 1-2 and the tutorial
   standard want a rebalance look"). Re-measured melee rows: the
   reference sheets' rows effectively unchanged (ranged builds kill
   melee before adjacency); the shredder lane gets realer (labs
   0.920, 4 def; merchants 0.980 / 28.1 dmg).
2. **The Warden's shimmer "hard to see" — the render dial ruled by
   playtest (`128edbc8`).** The thin `~` on the tile's own
   background became a medium-shade `▒` with its OWN violet-dark
   cell background (brighter visible fg, deeper shade when
   remembered) — a translucent curtain at a glance.

3. **The field lagged behind the W and stayed after its death, FIXED
   (`b50e0adf`).** Both reproduced: the shell re-derived only at turn
   START — before the Warden's movement — so it trailed the body a
   full round; and the merged-survivor rule kept the DEAD warden's
   ring while the survivor's never stood (F4/F5 author 2-4 Wardens —
   guaranteed to read as a bug). Now: a turn-END pass recenters the
   shell on where the W finished its move (fresh cells at 0, no
   regen double-dip — the +10 lands only at turn start, verified);
   a death REBUILDS the field as the survivors' current rings (kill
   a W and its cells always visibly collapse; last W = the whole
   field dies).
4. **The aim line overwrote the shimmer, FIXED (`31511423`).** The
   targeting line painted after the world view, scribbling `~` over
   the shell's cells (the user's "that's why I'm struggling to see
   it"). The line now STOPS at the first live field tile — the
   shimmer eats the line like it eats the shot; the blocked lane
   reads at a glance.

5. **Unbaitable Wardens, FIXED (`e1433047`).** The investigation's
   LOS-complete check read a RADIUS-LESS ray — on open ground a
   disengaged walker "held LOS" on goals far beyond the sight
   radius and ended the investigation with ZERO steps (the user's
   autosave: every Warden carried last_seen=None). The check now
   honors the map's sight radius (Chebyshev, the FOV cast's own
   metric): break LOS and the Warden walks to where it can see your
   last position — the door bait works (verified on the live save:
   the F5 Warden walked 16 cells through the entrance and settled a
   cell away). SETTLED 37's short-corner read (looked-at, not
   walked-to) preserved.
6. **The shell is a WALKING WALL (`cf055f84`) — three live catches
   folded:** (a) the field only re-derived on combat turns, so each
   re-engagement's add-only entry LITTERED rings along a bait path —
   a per-tick ambient tracker recenters every awake Warden's shell
   (idempotent stationary; old saves self-heal on the first tick);
   (b) entry once armed nothing (the tracker's 0-HP rings read as
   standing) — entry arms 0-HP full ("wakes with its shield up"),
   wounds persist; (c) THE RULING (user: "the SW hole makes no
   sense" + confirmed moving through does nothing): fresh-by-
   movement cells ARM FULL — the field never weakens by moving —
   while destroyed tiles TOMBSTONE at 0 (deletion is now
   indistinguishable from never-existed) and regrow +10 at combat
   turn starts. Known edge recorded: a hole the Warden paces fully
   off and back over returns at full, not +10.
7. **Melee reach resolves the melee set (`45ca4ea7`).** The hug
   gate read the ACTIVE shot's min-range (2), so an adjacent player
   made the Warden RUN instead of slamming. Now adjacency = the
   melee set's answer (affordable incl. the swap; the dance roll
   reads the PICKED weapon — melee holds); the hug back-off
   survives for no-pick pure-ranged rows. Verified: the adjacent
   Warden fires the Slam with zero movement and the knockback
   ejects the player back through the ring — the authored
   enter-swing-eat-re-enter loop, live.
8. **OPEN DESIGN QUESTION (user, 2026-10-03 — for the phase close /
   the doc-43 far-side handoff): FIELD TILES AS ENTITIES.** The
   user's instinct: each cell an entity like doc-57's space
   missiles — targetable, panel HP, hit%, +10/turn regen even from
   0, always moving with its W — and the system generic enough that
   a PLAYER personal force field (alien tech, Act 2) reuses it.
   Agent read (chat, not ruled): the entity model is the right
   long-term shape — it is the engine's existing pattern for
   combat-relevant non-characters (the merged-targets missile
   precedent), it solves the field's whole playtest pain class
   structurally (invisible state, unexplained holes — HP on the
   panel makes the shell legible), and it generalizes to the
   player-owned field. Costs to weigh at the ruling: ~16 extra
   entities per Warden in every entity scan (non_blocking keeps
   movement/pathing clean), the ground targeting space needs the
   missile-style merge + ordering so tab-cycling reaches the body
   first, and the eruption/victim/refresh-engaged scans must
   exclude the class. Timing recommendation: not mid-playtest — the
   dict-on-GameMap model just went stable through six live-fix
   rounds with all seams in ONE module (`combat/_ancients.py`); the
   entity migration re-homes state but keeps those seams.

9. **The field rendered through walls, FIXED (2026-10-04).** The
   shimmer's remembered-dim render (build E's "outlives the fight"
   choice) read as the full field 100% of the time — nothing else
   in the game shows through walls like that (the Warden itself
   never renders unseen). Ruled by playtest: the shimmer is AS
   VISIBLE AS THE MACHINE THAT MAKES IT — visible-only, full
   bright; no remembered trail.

**PLAYTEST READ (2026-10-04, user, after the bait-arc fixes): "this
feels good. now I can pretty consistently survive as long as I play
careful and exploit their behavior."** The machines' combat loop is
validated in live play — hard but fair, winnable through exactly the
behavioral counters the family was authored around. RECALIBRATION
FOR THE TUNE: the battery's F4-wall number (labs 0.020 / merchants
0.200) is the STANCE floor — the harness's toggle_sets bot can't
bait to a door, hold a choke, or trade inside the ring. The player
who does beats the row the bot loses. Tune flags should be read
against player-skill play, not the stance alone.

## SETTLED 46 (2026-10-04) — ancient prose renames + the slam's own lines

User, verbatim:

> Shredder Claws should be renamed. How about: Serated Blades? I'm
> imagining an alien machinery that is alive with shredding limbs
> whirring and slicing.
> The shimmer field absorbs your shot.
> The shimmer field collapses!
> Warden Shot rename: Energy Cannon
> Warden Slam rename: instead of "Warden swings its Warden Slam at
> you." Could we do "Warden slams hard in to you!" when it hits and
> "Warden attempts to slam in to you but misses." When it doesn't?

Rulings (landed verbatim, spelling flagged for the user in chat):

- **Renames**: Shredder Claws -> **Serrated Blades**; Warden Shot
  -> **Energy Cannon**. Ids unchanged; display names only. (Spellings
  corrected by the user's same-day follow-up: "yes you can fix my
  typos.")
- **The shimmer pair SUPERSEDES the SETTLED 45 drafts**: absorb is
  "The shimmer field absorbs your shot." and a destroyed tile is
  "The shimmer field collapses!" (was "swallows your shot" /
  "breaks apart").
- **The slam carries CUSTOM attack lines** (the first per-weapon
  feed override — a `_CUSTOM_ATTACK_LINES` table in
  `_messages.py`), amended the same day (typos fixed + the damage
  clause added): hit "Warden slams hard into you! You take X
  damage!" / miss "Warden attempts to slam into you but misses."
  The event popups (the six stale drone-named messages + the
  silent Warden wakes) are DEFERRED to a later user pass ("I'll
  probably do another pass some other night").

Instrument gaps (carried): PlayerSheet still cannot express ground
stat spends or gear qualities (both real saves load whole, so the
machines' rows didn't need it).

FLAGGED for the user at the checkpoint (leans awaiting sign-off):
the rock_scavenger → hull_parasite-only prison pools (F2 now
single-species at 1.8 density); the warden-heavy F5 gauntlet; the
machines' own popup prose (the six older event messages still name
sentry/assault drones — stale against the machines that now spawn;
the Warden events are SILENT pending a prose ruling).

## SETTLED 47 (2026-10-04) — phase-10 brief-time rulings: per-biome pools, earth=LUSH, the apex gate, the row census

User, verbatim (option-pick 2026-10-04, on the four phase-10 opens):

> "Per-biome pools, fully authored"
> "Earth = LUSH; rest default (Recommended)"
> "Every bottom, band-stamped (Recommended)"
> "2 faces + 1 apex per biome (Recommended)"

Rulings:

- **Dig pools become PER-BIOME and FULLY AUTHORED.** Each biome
  theme carries its own band-1-4 pool table (composition AND
  density authored per biome per band); `TIER_POOLS` demotes to the
  DEFAULT pool for undescribed themes. Digs are no longer
  pirate-flavored everywhere by construction — a LUSH delve reads
  lush, a VOLCANIC delve reads volcanic. `derive_dig_params`
  resolves pool by (theme, band); the floor band stays the clamped
  1-4 `_dig_tier` stamp.
- **Earth IS LUSH's planet** — its EARTH theme (warm green temperate)
  is the lush biome; no re-theming, no new planet. Unlisted themes
  that host digs (MARS_CITY = mars, CLOUD_CITY = venus / vega_b /
  ac_planet_3, PIRATE_OUTPOST = wolf_b) read the DEFAULT pool
  (today's TIER_POOLS shape) until their planets earn faces — six
  authored biomes, honest scope.
- **The apex guards EVERY delve bottom, band-stamped.** Every dig's
  deepest floor spawns its biome's apex beside the legendary cache,
  stamped at that floor's band (a T1 dig meets a band-scaled apex,
  a T4 dig meets the wall) — no special cases; the guardian scales
  with its delve like everything else. Same-day amendment (the
  brief's reviewer ADVISE pass caught the gap; user ruling
  2026-10-04): EVERY means every — default-biome digs BORROW the
  nearest biome's apex (wolf_b/lal_c→ice; mars→desert; venus /
  vega_b / ac_planet_3 / indi_b→lush; everything unlisted falls
  back to desert, tunable). No unguarded legendaries anywhere.
- **The census: 2 faces + 1 apex per biome** — 8 new fauna rows (2
  each for LUSH, VOLCANIC, SCRAP_RING, CANYON) + 6 apex rows (one
  per biome incl. DESERT and ICE). Matches existing biome density;
  each face a distinct behavior×attack cell (the doctrine: matrix
  cells, never stat walls).

Row-shape rulings (drafted from the doctrine, folded with the
batch): apexes are DATA-ONLY rows — bold glyph (`elite`), unique
(`squad_size` (1,1)), guard behavior at the cache, organic fixed
weapons, band-stamped stats. NO new mechanic machinery this phase
(the ancient dials stay ancient); if playtest shows an apex needs a
mechanic, it comes back as a proposal. Authored per-planet surface
`monster_pool` / `cache_guardian_pool` rows stay as authored
(SETTLED 14 law). Names + weapons + per-band compositions land in
the brief under the prose gate.

## SETTLED 48 (2026-10-04) — the pack apex: the Mesa Mauler hunts with a viper pack

User, verbatim:

> I woant one of the apexes to have a swarm. a hunting pack.
> apex + fauna.

Rulings:

- **ONE apex is a PACK apex** — the apex spawns WITH its biome's
  fauna as a hunting pack, ONE squad (SETTLED 37's
  squads-move-and-follow-noise-as-a-unit IS the pack behavior; zero
  new AI). Assigned: the **Mesa Mauler** (canyon — the roaming
  hunter apex) + 2-4 **Canyon Vipers**.
- **Authoring shape**: two new `NpcCharSpec` fields —
  `pack_pool: tuple[str, ...] = ()` + `pack_size: tuple[int, int]`
  — empty = solo (every other row unchanged); consumed at the ONE
  spawn site (the hoisted `_spawn_squad_near` composes apex + pack
  under one squad_id). Data-only: the pack is part of the ROW, so a
  future pack apex is a data edit (extensibility criterion holds).
- **Identity law intact**: the apex stays the ONE bold glyph; the
  pack renders as ordinary fauna. Counter shape: thin the pack,
  then duel the mauler.
- **The per-row census folds with this ruling** (the doctrine
  answer to "14 copy-paste rows" — every row a distinct
  behavior×attack cell, all existing fields): fauna cells = AP-6
  closer pack / guard-artillery nest / armored swarm / close-range
  brawler-caster / fast armored skirmisher / RANGED swarm / armored
  ambusher / dodge skirmisher; apex identities = anchor+knockback /
  soak-breaker / bombardier / ambush-at-the-cache / immovable
  switcher / roaming PACK. knockback and armor_bypass ride the
  EXISTING weapon fields (the Warden slam's precedent) — the
  data-only ruling stands.

## SETTLED 49 (2026-10-04) — the assault drone is T2

User, verbatim:

> at this point assault drones should probably be considered T2

Rulings:

- **assault_drone re-tiers 3 → 2** — the machine family reads as
  ruin-security T2 uniformly (sentry already 2; d/D are ONE family,
  SETTLED 34). A classification + seat ruling: NO stat numbers
  move (hp/armor/ap are its authored identity; the band stamp does
  the scaling, SETTLED 15).
- **Loot consequence (the tier-gate law):** its four
  equipment_loot_pool entries are ALL tech_level 3 (verified
  2026-10-04) — at tier 2 every one would SILENTLY stop dropping.
  The pool re-authors to t2 entries (the sentry's neighborhood:
  heavy_helmet / reinforced_gauntlets / smg class); the
  energy_cells/stim field items stay (field items are not
  tier-gated).
- **Seats:** TIER_POOLS keeps its band-2 assault seat; bands 3-4
  re-author WITHOUT it — supersedes SETTLED 35's listed b3/b4
  compositions and amends SETTLED 47's "TIER_POOLS verbatim"
  line. Opening drafts (tunable): b3 (rifleman, rifleman, brute,
  hull_parasite); b4 (rifleman, brute, brute, hull_parasite).
- **Biome tables:** machine seats live at bands 1-2 ONLY (sentry
  b1 / assault b2, in desert/ice/scrap; lush/volcanic/canyon stay
  fauna-forward with no drone seats); bands 3-4 are FAUNA-PURE —
  the strong face weighted up. Deeper delves read WILDER, not more
  mechanized.

## SETTLED 50 (2026-10-04) — the hunt reskinned: hunters only, the anchor is the q6 set-piece

User, verbatim (option-pick 2026-10-04, all four on the recommended line):

> "Pursuit hunters only (Recommended)"
> "Bold frigate anchor + pursuit escorts (Recommended)"
> "Retire it — hunters only (Recommended)"
> "q3 + q6 only, as today (Recommended)"

Rulings (the hunt's shape; grounded against the live code — the hunt
today spawns pirate_scout "leaders" + a merchant_hauler front + 1-4
pirate escorts at ~2%/tick with the log line "Sensor ping: consortium
operation detected - merchant hauler with N pirate escorts", and q6's
`mer_consortium_leader` is a pirate_captain + 2 pirate_raider escorts):

- **q3 roaming squads = PURSUIT HUNTERS ONLY** — 2-3 of the pursuit
  cruiser spec, one unmistakable corporate silhouette in navy. The
  merchant-hauler front and the pirate escorts RETIRE with the
  disguised-merchant fiction (SETTLED 5). A clean kill-squad read:
  they found you, they came for you.
- **q6's guarded wreck = the BOLD FRIGATE ANCHOR + 1-2 pursuit
  escorts** — the hunt's set-piece escalation (SETTLED 33's named next
  bold wearer). q3 you ran from hunters; q6 the heavy arrives.
- **Ambient-pirate auto-aggro during heat RETIRES.** "The consortium
  hires pirates" dies with the reskin; ambient pirates stay ambient.
  The hunt reads as a new enemy class exactly because nobody else
  behaves differently.
- **Hunt scope stays q3 + q6** — heat is step-scoped as today (expiry
  implicit); the reskin changes WHO hunts, not when. The q4 grind
  stays a breather between hunts.

## SETTLED 51 (2026-10-04) — the augmentation ladder: three rungs, fixed bands, quality floors

User, verbatim (option-pick 2026-10-04, all four on the recommended line):

> "3 rungs: e / E / bold E (Recommended)"
> "Fixed band per rung (Recommended)"
> "Quality floors per rung (Recommended)"
> "Wreck + boarded hunters (Recommended)"

Rulings:

- **The ladder is THREE rungs, realized as SETTLED 34's case/bold
  variants of family letter `e`:** Gunner `e` re-authors as the LIGHT
  rung (eyes/arms-class augments), Enforcer `E` as the MID rung
  (arms/legs), and ONE NEW bold-`E` row is the HIGH rung (the full
  set: eyes/torso/arms/legs — the heaviest augmentation). Exact piece
  assignments per rung are brief-time leans; the pieces are the
  EXISTING armor cybernetics (SETTLED 11) and their bonus fields go
  live on their wearers through the standard modifier math (SETTLED
  27 — cyber-legs make faster consortium).
- **Fixed band per rung** — the ancients' `fixed_band` precedent:
  each rung row authors its band (opening leans 2 / 3 / 4), and
  authored encounter difficulty decides which rung you meet (SETTLED
  12 verbatim). A rung reads identical wherever it appears.
- **Quality floors per rung** — consortium equipment NEVER rolls base
  quality: every rung floors at modded (q1); the top rung floors at
  overclocked (q2), rolling prototype in its distribution. "Decked
  out in HIGH QUALITY cyber gear" (SETTLED 6 correction) reads in
  every drop, and kit drops make their pieces premium loot.
- **Exposure = the two authored surfaces:** survey_a's wreck interior
  re-authors to the rungs (q6's corporate site, guarded outside by
  the anchor), and boarding a hunter ships a consortium-crewed deck
  through the existing crew_faction machinery (CREW_ROLES' consortium
  row re-points at the rungs: line/marksman resolve to the re-authored
  enforcer/gunner). Nothing procedural spawns consortium (SETTLED 12
  stands).

## SETTLED 52 (2026-10-04) — the hunters: navy cruiser pursuers + the bold band-3 frigate anchor

User, verbatim (option-pick 2026-10-04, all three on the recommended line):

> "Cruiser (Recommended)"
> "Pursuit b2, anchor b3 (Recommended)"
> "Module quality floor q1+ (Recommended)"

Rulings:

- **The pursuit hunter is a CRUISER** (`C` in consortium navy) —
  SETTLED 31's own lean confirmed; distinct from the pirate line pair
  and from every faction's `s` scouts. The anchor is the FRIGATE
  (bold `F`, SETTLED 33/50).
- **Bands: pursuit band 2 (eff. L10), anchor band 3 (eff. L18).**
  q3's packs scare a mid-chain player without walling them; q6's
  set-piece (b3 anchor + b2 escorts) is the finale without Line-tier
  difficulty. Skill weights and loadouts are brief-time leans
  (SETTLED 39 machinery).
- **Flown gear floors at modded (q1)** — modules AND weapons, the
  ground rungs' rule extended ship-side: every stripped piece from a
  captured hunter is premium loot (SETTLED 31's "even their ships are
  loot"). Band rates above the floor as usual.
- Hunters spawn ONLY in the two hunt beats (q3 squads, q6 guard) —
  no `npc_spawn_table` seats anywhere, nothing procedural (SETTLED 12
  stands).

## SETTLED 53 (2026-10-04) — hidden-rep v1 stands as landed; up-movers + site/loot movers are FUTURE content

User, verbatim (2026-10-04):

> earning consortium rep will be dealth with further down the road.
> (on site/loot movers) again, this is future content.
> (on hunt movers) Kills only, no special event
> (on gates) Gates stay none (Recommended)

Rulings:

- **NO up-movers, NO site/loot movers in phase 11** — both are future
  content ("dealt with further down the road"). The hidden axis stays
  exactly as v1 landed: direct kill movers (−3 per consortium-tagged
  kill) + the merchant-kill ripple (−1), hidden presentation, decay
  as landed. **Amends the phase-11 bullet** ("ADDS the up-movers +
  site/loot/hunt movers") — phase 11 ships NO rep machinery.
- **Hunt movers: kills only** — hunter kills ride the plain −3 direct
  mover; no anchor-kill event, no special hunt rep beats.
- **Gates stay none** (SETTLED 9's reservation stands; the hunt is
  authored beats, not a thermostat — SETTLED 50).

## SETTLED 54 (2026-10-04) — names + the ping line (PROSE GATE satisfied)

User, verbatim (option-pick 2026-10-04):

> "Consortium Executor" / "Consortium Hunter" / "Consortium Dreadnought"
> "Sensor ping: consortium hunters detected - N ships closing."

Rulings (names APPROVED verbatim):

- The bold-`E` high rung is the **Consortium Executor**; Enforcer and
  Gunner keep their names as the re-authored mid/light rungs.
- The pursuit hunter (navy `C` cruiser, band 2) is the **Consortium
  Hunter**; the anchor (bold navy `F` frigate, band 3) is the
  **Consortium Dreadnought**.
- The hunt's sensor-ping line lands VERBATIM: **"Sensor ping:
  consortium hunters detected - N ships closing."** (replaces the
  "consortium operation detected - merchant hauler with N pirate
  escorts" line).

## Pre-implementation audit — phase 11 (2026-10-04)

1. **Existing modules to extend or reuse:**

   - **The hunt's spawn machinery is ONE function + one data row.**
     `_spawn_consortium_squad` (`npc_ships.py:82`) composes via
     `_SquadPlacement` (place leader → escorts) and logs the ping line;
     `_tick_consortium_squads` (`:676`) fires it ~2%/tick, capped at
     density × 2 — cadence and cap stand, only the roster changes.
     `_squad_aggro` (`:729`) carries the retiring clause verbatim:
     `consortium_heat_active(ctx) and _faction == 'pirate'`.
   - **q6's guard is pure data**: `MainQuestStep.bounty_enemy_id` +
     `bounty_escort_ids` (`act0_merchants.py:120-122` — pirate_captain
     + 2 raiders today), consumed by `main_quest/_spawns.py:35-61`
     (leader + escort spawns under one squad_group). Re-author the
     ids; zero spawn-code changes.
   - **`fixed_band` already exists on NpcCharSpec** (phase 9,
     `data/npc_chars/__init__.py:229`) — the rungs author it; the
     `entity_band` choke point honors it today.
   - **The worn-armor bonus math exists as a shared helper**:
     `_sum_armor_bonus(pieces, field)` (imported at
     `_rules_ground.py:27`) already folds `ap_bonus`/`hit_bonus`/
     `melee_bonus` for the player (`:284,459,484`) — the enemy mirror
     calls the same helper over the rung's stamped pieces. `hp_bonus`
     folds at the instance HP build.
   - **The quality seams take `band`, not rates** (ADVISE-corrected):
     `roll_flown_equipment(item_type, ids, band, rng)`
     (`space_scale.py:45`) and the ground equip draw
     (`rolled_weapon_quality` via `roll_slot` in `ground_scale.py`)
     both derive rates internally — a per-spec floor threads as a new
     parameter at exactly these two sites (both signatures change;
     callers: `_stats.py:_enemy_flown_loadout` + tests, `roll_slot`
     has the spec in scope). NO player path calls either site
     (reviewer-verified) — floor 0 is bit-identical by construction,
     single RNG draw either way. The capture strip copies the flown
     `StoredEquipment` verbatim and the kit drop reads stamped
     qualities (no re-roll), so the floor flows into captured and
     dropped gear with no third site.
   - **The worn-stamp rides `rolled_loadout`** (ADVISE-verified
     cheapest route): a `worn` key inside the existing loadout stamp
     keeps `_spawn_kit_drop`/`spawn_kill_drops` signatures unchanged;
     serialization extends the `_loadout_dict`/`_loadout_from_dict`
     KEY WHITELIST (`saveload_maps.py:265-324` — a new key silently
     drops otherwise). The enemy AP seam is pre-built:
     `enemy_ap_total(spec, armor_entries=())`
     (`_ground_effects.py:75-82`) already accepts entries —
     `_stamp_enemy_loadout`'s call gains the one arg.
   - **`enemy.spec.armor` has SIX live readers** (ADVISE catch — the
     fold must land as INSTANCE state, every reader migrates):
     `_rules_ground.py:483` (damage soak), `_ground_deadshot.py:124`
     (preview), `_ground_blast.py:66` (blast), and the target card
     twice (`_ground_presentation.py:74,123`). The hit/melee bonus
     fold touches `_ai_ground.py` at BOTH the scorer
     (`_score_ground_weapon:117-141`) and the shot resolution
     (`_roll_ground_shot:761-792`) — SETTLED 41's same-math rule.
   - **Boarded hunter decks need zero new plumbing**:
     `capture_layout_id` on NpcShipSpec (hunters author cruiser_crew
     / frigate_crew) + `begin_capture_boarding` passing
     `crew_faction=spec.faction` (phase 6) → `CREW_ROLES["consortium"]`
     resolves; the row currently omits `heavy`. But cruiser_crew
     carries a shared chance-slot heavy (`ENEMY: z = heavy@0.4#1-1`,
     `cruiser_crew.layout:110`) — a consortium `heavy` role leaks a
     40% Executor onto every boarded Hunter. One geometry serves
     every faction (SETTLED 28); the EXPECTATION bends, not the
     layout (frigate_crew's guaranteed heavy marker delivers one on
     every boarded Dreadnought).
   - **survey_a re-points raw ids** (the authored-specials lane,
     SETTLED 28): its four ENEMY markers (`survey_a.layout:64-67`)
     name enforcer/gunner directly.
   - **Cyber pieces live data-side** (`ground_armor/vests.py`):
     cybernetic_eyes (head, t2, hit_bonus 8), cybernetic_arms (hands,
     t2, melee_bonus 2), cybernetic_torso (body, t3), cybernetic_legs
     (legs, t3) — tier-gate law: rung `tier` ≥ every worn piece's
     tech_level forces tier ≥ 2/3/3 for Gunner/Enforcer/Executor
     (the Executor's tier 4 is a difficulty choice, not a gate
     consequence).

2. **Duplication hotspots:**

   - Worn-piece bonus folding hand-rolled per stat site instead of
     one pass over the stamped pieces at instance build.
   - The quality floor applied at more than the two roll sites (a
     third ad-hoc clamp would drift).
   - The ping line's count grammar re-derived at the log call
     (singular/plural) instead of one f-string beside the spawn.

3. **DRY strategy:**

   - ONE `worn_armor: tuple[str, ...] = ()` field on NpcCharSpec +
     ONE stamp extension in the loadout path (the SETTLED 36/43
     pattern: idempotent first-resolution stamp, serialized); the
     instance build folds all four bonus fields + defense through
     `_sum_armor_bonus` in one place.
   - ONE `quality_floor: int = 0` field on BOTH NpcCharSpec and
     NpcShipSpec, consumed at exactly the two roll sites.
   - The kit drop (`_spawn_kit_drop`) gains the stamped worn pieces —
     what they wear is what drops, no second drop path.

### Phase 11 Implementation brief (PROPOSED v2 2026-10-04 — SETTLED
### 50/51/52/53/54 over 5/6/9/11/12/27/28/31/33/34/39; reviewer
### ADVISE pass folded first: 13 issues / 3 blocking — the
### cruiser_crew heavy-leak expectation (the layout stands, the
### test bends), the six `spec.armor` readers + the scorer/resolution
### same-math seam for the bonus fold, and the two-roll-site
### signature reality; awaiting user approval)

**Scope (files / hook points):**

- **The two hunter specs** (new `data/npc_ships/consortium.py` +
  registry): **Consortium Hunter** (`consortium_hunter`) — cruiser
  hull, consortium navy (90,120,200), faction consortium, band 2,
  piloting-biased skill weights (the pursuit read), elite False,
  `capture_layout_id="cruiser_crew"`, military-suite modules
  (targeting/gyro/shield — the existing military family, no new
  ids); **Consortium Dreadnought** (`consortium_dreadnought`) —
  frigate hull, navy, band 3, balanced flagship weights, elite True
  (bold `F`, SETTLED 33's named wearer), `capture_layout_id=
  "frigate_crew"`, warship module suite, `shield_regen_rate` lean 2
  (the captain/patrol_heavy class). Both: `quality_floor=1` (SETTLED
  52), ai dials authored (pursuit closes: preferred_range lean 2-3;
  aggression lean 60-70). NO `npc_spawn_table` seats anywhere — the
  two hunt beats are their only spawn surfaces (SETTLED 12).
- **The `quality_floor` field** (`data/npc_ships/__init__.py` +
  `data/npc_chars/__init__.py`): `quality_floor: int = 0` on both
  spec types; consumed at exactly the two roll sites —
  `space_scale.roll_flown_equipment` (ship modules AND weapons; the
  caller `_stats._enemy_flown_loadout` has the spec in scope) and
  the ground `roll_slot` equip draw — applied as **CLAMP semantics**:
  `max(floor, rolled)`, the below-floor mass lumping onto the floor
  rung, top-tier probability UNCHANGED (state, don't imply
  renormalization). No player path calls either site (verified) —
  floor 0 is bit-identical by construction. The floor flows into
  captured gear (the strip copies flown instances) and kit drops
  (stamped qualities, no re-roll) with no third site.
- **The three rungs** (new `data/npc_chars/consortium.py`; the two
  rows MOVE from core.py — ids unchanged, so old saves and survey_a
  load clean): **Consortium Gunner** `e` re-authors LIGHT —
  `fixed_band=2`, `worn_armor=("cybernetic_eyes", "cybernetic_arms")`
  (lean), `quality_floor=1`, guard behavior, pistols family;
  **Consortium Enforcer** `E` re-authors MID — `fixed_band=3`,
  `worn_armor=("cybernetic_arms", "cybernetic_legs")` (lean),
  `quality_floor=1`, hunter, melee/pistols; **Consortium Executor**
  `E` bold NEW — `fixed_band=4`, elite True, the FULL set
  `("cybernetic_eyes", "cybernetic_torso", "cybernetic_arms",
  "cybernetic_legs")`, `quality_floor=2` (overclocked floor,
  prototype in the rolls — SETTLED 51), hunter, rifles family lean,
  strength/stamina-heavy weights (the deck-clearing heavy). Rung
  `tier` ≥ every worn piece's tech_level (the tier-gate law —
  Executor tier 4, Enforcer tier 3, Gunner tier 2, pinned by test).
  Names VERBATIM (SETTLED 54).
- **The `worn_armor` mechanism** (`data/npc_chars/__init__.py` +
  the loadout stamp + the instance build): a `worn` key inside the
  `rolled_loadout` stamp resolves the pieces idempotently at first
  resolution (the SETTLED 36/43 pattern; serialization EXTENDS the
  `_loadout_dict`/`_loadout_from_dict` KEY WHITELIST in
  `saveload_maps.py:265-324` — a new key silently drops otherwise).
  The fold lands as INSTANCE state, and every consumer migrates:
  - the FOUR bonus fields via the shared `_sum_armor_bonus` —
    `ap_bonus` through `enemy_ap_total(spec, armor_entries=())`
    (already parameterized; `_stamp_enemy_loadout`'s call gains the
    arg), `hit_bonus`/`melee_bonus` into BOTH the volley scorer
    (`_score_ground_weapon`) AND the shot resolution
    (`_roll_ground_shot`) — SETTLED 41's same-math rule, the eyes'
    +8 hit moves pick and shot identically — and `hp_bonus` into
    the HP build;
  - each piece's DEFENSE adds to the armor read, and the SIX
    `spec.armor` readers migrate to the folded instance value
    (`_rules_ground.py:483` soak, `_ground_deadshot.py:124` preview,
    `_ground_blast.py:66` blast, `_ground_presentation.py:74,123`
    target card ×2) — what they wear is what they are (SETTLED 27),
    on the card and in every math.
  The kit drop (`_spawn_kit_drop`) drops the stamped pieces at
  their stamped qualities — what they wear is what drops; the
  rungs' `equipment_loot_pool` entries RETIRE **TOTAL on all three
  rungs** (a partial retirement would roll UNFLOORED gear at the
  drop-time site; goods/field-item pools stay).
- **CREW_ROLES re-point** (`data/npc_chars/crew_roles.py`): the
  consortium row gains `heavy: consortium_executor`; line/marksman
  stay enforcer/gunner. Boarded hunters resolve through it
  automatically — the shared one-geometry law (SETTLED 28) means
  cruiser_crew's CHANCE-slot heavy (`heavy@0.4`) puts an Executor on
  ~40% of boarded Hunters, and frigate_crew's GUARANTEED heavy
  marker puts one on EVERY boarded Dreadnought;
  security_drone/stowaway seats stand.
- **The hunt reskin** (`npc_ships.py` + `act0_merchants.py` +
  `main_quest/_heat.py`):
  - `_spawn_consortium_squad` places 2-3 `consortium_hunter` (RNG
    2-3) — the hauler front and pirate escorts die; the ping line
    lands VERBATIM: "Sensor ping: consortium hunters detected - N
    ships closing." (SETTLED 54).
  - `_squad_aggro`'s retiring clause re-keys `pirate` →
    `consortium` — ambient pirates go back to ambient; the hunters
    chase while heat is live (same expiry semantics as today).
  - q6 data: `bounty_enemy_id="consortium_dreadnought"`,
    `bounty_escort_ids=("consortium_hunter", "consortium_hunter")`
    (SETTLED 50's 1-2 escorts lands as the tuple's 2 — the existing
    shape).
  - The hired-pirate docstrings/comments retire across `_heat.py`,
    `act0_merchants.py` (q3/q6 comments), `npc_ships.py`, and the
    two ground rows' core.py comments (internal text, not
    prose-gated).
- **survey_a re-point** (`data/layouts/survey_a.layout`, directive
  blocks only — zero grid edits): `S` (the serious 2-slot marker)
  re-points to `consortium_executor`; `c`/`g`/`m` stay
  enforcer/gunner/parasite (the mid/light mix + vermin). Playtest
  dial.
- **Identity lint** (`tests/test_enemy_identity.py`): hull pin +
  one-fg-per-faction cover the hunters automatically; the elite
  census gains the Executor + Dreadnought; family conformance gains
  the bold case variant (the brute/sniper precedent).
- **Dev grants** (`dev_mode.py` + `test_dev_mode.py`): Shift+grant
  spawning the three rungs adjacent (disjoint per-face placement,
  the phase-4 precedent) + the Shift+P ship cycle extended with the
  two hunters — every checkpoint item without playing to q3.

**Build order:** ship specs + `quality_floor` (both registries) +
roll-site floors (registry/roll tests first) → rungs module +
`worn_armor` field + stamp extension + instance folding + kit-drop
pieces → CREW_ROLES `heavy` + survey_a re-point → the hunt reskin
(squad roster + ping line + aggro re-key + q6 data + docstring
sweep) → identity lint + dev grants → full gate.

**Binding rulings:** SETTLED 50 (hunters only; bold anchor at q6;
ambient-pirate aggro RETIRES; scope q3+q6), 51 (three rungs e/E/
bold-E, fixed bands 2/3/4, quality floors, wreck + boarded-hunter
exposure), 52 (cruiser pursuit b2 / frigate anchor b3; flown gear
floor q1+), 53 (NO rep machinery — the hidden axis stays v1-landed;
gates none), 54 (names + ping line VERBATIM), over 5/6/9/11/12/27
(worn cyber modifies its wearer), 28 (raw ids stay legal on
authored decks; one geometry per faction), 31 (two ships, themed
modules from existing families), 33/34 (hull glyphs + family navy +
bold elite), 39 (bands spec-authored, skills band-derived), 12
(authored-only exposure — nothing procedural spawns consortium).

**Required tests:** registry pins (hunter/dreadnought bands 2/3,
elite True on the Dreadnought, navy fg, hull chars C/F,
capture_layout_ids; rung fixed_bands 2/3/4 flat — a floor-1 stamp
does not dilute; Executor elite; tier-gate law per rung — 2/3/3
minimums, Executor 4 pinned);
`quality_floor` (both roll sites: floor 0 = bit-identical today —
single RNG draw; floor 1 never rolls base with the below-floor mass
on q1 and PROTOTYPE UNCHANGED — the clamp distribution pinned; floor
2 never rolls below overclocked — ship weapons/modules AND ground
equip draws); worn_armor (stamp idempotent + serialized THROUGH the
extended whitelist; bonus fields folded into AP/hit/melee/HP; the
scorer AND resolution move together — a cyber-eyes rung's +8 hit
changes pick and shot IDENTICALLY, the SETTLED 41 parity pin; the
six `spec.armor` readers all read the folded value — soak, deadshot
preview, blast, target card ×2; kit drop carries the pieces at
stamped qualities; equipment_loot_pool retirement TOTAL on all three
rungs; save/load round-trip incl. mid-fight quality state; old-save
tolerance); CREW_ROLES (heavy cell resolves; a boarded Dreadnought
GUARANTEES its Executor; a boarded Hunter carries the 40% chance-slot
Executor — the shared cruiser geometry, pinned as intended, never
edited); the reskin (squads compose 2-3 hunters, no hauler/pirate
ids; ping line VERBATIM; ambient pirates NOT aggro'd during heat —
the re-keyed clause; hunters chase while heat live and stop at
expiry; q6 spawns the anchor + 2 hunters under one squad group);
survey_a (markers resolve the rungs; the executor slot reads);
identity (elite census + family conformance + hull pin green);
regression (merchant chain end-to-end, bar-chain militia heat
untouched, ambient pirate behavior outside heat identical,
phase 9/10 suites).

**Stop point (do NOT start):** no rep machinery of any kind (up-
movers, site/loot movers, gates, expose-the-bar — SETTLED 53);
no new consortium exposure beyond the two hunt beats + survey_a +
boarded hunters (corporate digs, Act 2 beats, future content);
no new module or weapon ids (military suite + cyber pieces are
existing data); no rung MECHANICS beyond the standard build-1 loop
(the Executor is an ordinary humanoid row — no stare/field-class
dials); no hunt escalation/thermostat; phase 12 untouched.

**Ratchet note (counts at brief time, reviewer-verified):**
`combat/_rules_ground.py` sits at **998/1000** — the bonus/defense
fold CANNOT land line-neutral; the in-commit extraction beside
`_stamp_enemy_loadout` is certain, not contingent.
`npc_ships.py` sits at **997/1000** — the reskin likely nets
NEGATIVE (the hauler-front branch and escort loop die).
`_ai_ground.py` (847) joins the touched set with headroom; the
worn-stamp machinery prefers `ground_loadout.py`/`saveload_maps.py`
over `_rules_ground` where cohesion allows.

**PLAYTEST checkpoint (numbered, in-game):**

1. Merchants chain to q3 (dev: force the step live): the ping reads
   "Sensor ping: consortium hunters detected - N ships closing." —
   navy `C` cruisers in 2s and 3s, closing; no hauler fronts, no
   pirate tag-alongs.
2. During q3 heat: ambient pirates in the system stay ambient —
   fly past one and it does NOT aggro (the retired clause); the
   hunters themselves chase.
3. Fight a hunter pack: band-2 skills read (LVL 10 card line),
   piloting-biased pursuit; kill one — the −3 hidden rep moves
   (save-file check, no log line).
4. q6 at vega: the wreck guard is a BOLD navy `F` (LVL 18) + two
   hunters — the set-piece reads; killing the dreadnought is the
   finale.
5. Board the dead dreadnought: the deck crews consortium through
   CREW_ROLES — enforcers `E`, gunners `e`, sentries, and ONE
   guaranteed bold-`E` Executor (frigate_crew's heavy marker); a
   boarded HUNTER runs the cruiser mix with the ~40% chance-slot
   Executor. The executor's cyber bonuses read in its speed, AP,
   and hit chance — and on the TARGET CARD (armor/HP honest).
6. Kill the Executor: its kit drop = the full cyber set at
   overclocked-or-prototype quality (never base); the enforcer's =
   arms+legs at modded+. The pieces are premium loot.
7. survey_a (the calibration wreck): the `S` slots field Executors;
   the deck reads mid+high corporate, not t1 filler.
8. Faction standings: still three bars — the hidden axis moved
   (save check) but renders nowhere; killing merchant crews still
   ripples (v1 unchanged).
9. Save/quit mid-hunt and mid-deck → Continue: squad, deck crews,
   worn-piece state, qualities identical; a pre-phase-11 save loads
   clean (ids unchanged).
10. Regression: bar chain's militia heat untouched; ambient pirate
    behavior outside the hunt identical; phase 9/10 content
    (machines, biomes) unchanged.
11. Guide-diff item: expected NONE — the hunt explains itself in
    play (SETTLED 36 noise precedent); confirm-grep `data/guide/`
    for consortium/heat mentions, any hit becomes a called-out
    before/after.

## Pre-implementation audit — phase 10 (2026-10-04)

1. **Existing modules to extend or reuse:**
   - `derive_dig_params` (`digs.py:155-173`) — the ONE pool choke
     point; every RNG dig resolves its `monster_pool`/density here.
     The biome axis lands here, nowhere else.
   - `_place_population_anchor` + `_scatter_squad`
     (`dungeon_population.py:138-175`) — spawn machinery already
     carries `bold=spec.elite`; the apex needs zero new spawn code.
   - `_place_legendary_cache` (`digs.py:499-522`) — the cache picks
     its own free cell (returns None today; it exposes the chosen
     cell for the apex guard). The NEAR-cache spawn is
     `_spawn_squad_near` (`main_quest/_delve.py`), not
     `_free_floor_cell` — that walk is map-wide-uniform.
   - `data/npc_chars/monsters.py` + `data/ground_weapons/monsters.py`
     — the catalogs; registry auto-discovery means new rows are pure
     data edits (the extensibility criterion, already true today).
   - The phase-3 identity lint (family conformance, glyph collision)
     extends with a TILE-char overlap check (pin-list idiom) — the
     fauna glyph standard is (glyph, color) pair-uniqueness, not
     blanket freeness.
   - `_dig_tier` (`digs.py:227-230`) — the clamped floor band; the
     apex stamps through it.
2. **Duplication hotspots:**
   - BIOME_POOLS vs TIER_POOLS growing two parallel lookup paths in
     `derive_dig_params`.
   - The apex spawn forking its own entity-construction block
     instead of reusing the scatter machinery. The prior art that
     fits: `_spawn_squad_near` (`main_quest/_delve.py:75-112`) —
     nearest-first BFS, delegates to `_scatter_squad`, carries band
     + `bold`, KeyError-safe. HOIST it (with `_door_room_cells`) to
     `dungeon_population.py`; `_place_bottom_apex` becomes a thin
     call. `_free_floor_cell` is map-wide-uniform — it CANNOT pick
     a cell near the cache (reviewer issue 2), and
     `_place_legendary_cache` returns None today (it must expose
     its chosen cell).
   - Per-biome pool tables re-listing the density ladder four times
     each (authoring noise, drift risk).
3. **DRY strategy:**
   - ONE `_biome_pool(spec, band)` resolver: `BIOME_POOLS.get(
     spec.biome, TIER_POOLS)[band]` — TIER_POOLS stays the default
     table verbatim, the biome table is one new structure beside it.
   - Apex spawn = one `_place_bottom_apex` helper in `digs.py`,
     a thin call over the hoisted `_spawn_squad_near`; no second
     entity-construction site.
   - The row census is DATA — copy-shaped rows are the catalog's own
     idiom (frozen dataclass tuples); no factory extraction.

### Phase 10 Implementation brief (FINAL v4 — APPROVED 2026-10-04;
### SETTLED 30/47-as-amended + 48/49; reviewer ADVISE pass folded at
### v2: 8 issues / 2 blocking — the apex-scope contradiction ruled by
### the user (BORROW the nearest biome's apex), the adjacency
### mechanism re-based on the hoisted `_spawn_squad_near`; v3 folded
### the SETTLED 48 census (every row a distinct cell — the pack
### apex); v4 folded SETTLED 49 (the assault drone is T2); names,
### pools, and glyphs approved VERBATIM with the brief — the prose
### gate is satisfied; ready for /implement-phase 48.10)

**Scope (files / hook points):**

- **The biome axis** (`data/planets/__init__.py` + 12 planet files):
  new `PlanetSpec.biome: str = ""` — the fauna-pool key, decoupled
  from `theme` (earth keeps its EARTH palette and declares
  `biome="lush"`; derived themes like lal_c's VAULT read the default
  untouched). Declarations: lush=earth; desert=mercury, barnards_b,
  cygni_b, ac_planet_1; ice=procyon_c, lal_b, ac_planet_2,
  barnards_c; volcanic=ross_b; scrap_ring=ross_c;
  canyon=epsilon_eridani_b. Every other planet leaves it empty.
  Why a declared field over a theme→biome table (reviewer issue 3,
  ruled with the fold): `PlanetTheme` instances are unnamed values —
  identity keying breaks under `override_theme`/`derive_theme`
  copies, and a theme-keyed table would need a new name field on
  `PlanetTheme` (more machinery than one str field). The explicit
  declaration survives palette overrides; earth/lush is the live
  case that forces the decoupling.
- **The pool table** (`data/digs/__init__.py` + `digs.py`):
  `BIOME_POOLS: dict[str, dict[int, tuple[tuple[str, ...], float]]]`
  — six biomes × bands 1-4, composition AND density authored (drafts
  below); `TIER_POOLS` stays the undescribed-theme default with ONE
  amendment (SETTLED 49: the assault seat leaves bands 3-4 — b3
  (rifleman, rifleman, brute, hull_parasite), b4 (rifleman, brute,
  brute, hull_parasite), tunable) and the assault_drone row itself
  re-tiers 3 → 2 with its equipment pool re-authored to t2 entries
  (all four current entries are tech_level 3 and would silently
  stop dropping). Resolution: one
  `_biome_pool(spec, band)` helper inside `derive_dig_params` —
  pool still keyed by SITE band (`_site_tier`), floors still climb
  the stat band via `_dig_tier`.
- **The organic weapons** (`data/ground_weapons/monsters.py`): new
  enemy-only rows (all `shop_available=False`,
  `loot_droppable=False`), shaped per the census cells — fauna:
  **spore_burst** (long light ranged — the artillery nest),
  **magma_bolt** (short heavy, 2 AP — the brawler-caster),
  **rust_spines** (short swarm sting), **venom_fangs** (fast weak
  multi-bite — the viper's dodge weapon; hounds keep claws); apex:
  **behemoth_maul** (heavy melee carrying the EXISTING `knockback`
  field, authored 2 — Dune Behemoth, Canopy Maw, Scrap Colossus),
  **wyrm_breath** (ranged carrying the EXISTING `armor_bypass`
  field — the soak-breaker), **siege_bolt** (long heavy ranged —
  the bombardier; the Colossus reuses spines + maul). Names are
  drafts under the prose gate.
- **The fauna rows** (`data/npc_chars/monsters.py`): 8 new rows, 2
  per new biome — every row a DISTINCT behavior×attack cell
  (SETTLED 48 census; the anti-copy-paste doctrine: matrix cells,
  never stat walls), all via existing fields:
  **Vine Hound** (LUSH — AP-6 closer pack: weak fast multi-bite
  volley, pairs; pressure you can't out-walk) / **Spore Spitter**
  (LUSH — guard-artillery NEST: holds its patch, longest organic
  range, min_range 2, authored sting melee set so rushing it
  triggers the cornered-switch — the first two-set FAUNA, riding
  the SETTLED 43 loadout path); **Ember Crawler** (VOLCANIC —
  ARMORED swarm: armor 2 on volume 4-6, plasma/AoE bait, kinetic
  starves) / **Magma Spitter** (VOLCANIC — close-range
  brawler-caster: max range 4, heavy hits, 2 AP — the inverse of
  frost's long kite); **Scrap Hound** (SCRAP — fast ARMORED
  skirmisher, armor 1-2, ap 6, pairs; out-races you, pin and
  trade) / **Rust Wasp** (SCRAP — RANGED swarm: 3-5 stingers at
  short range, ap 6 — the new cell, volume of incoming fire);
  **Crag Lurker** (CANYON — ARMORED ambusher: armor 3 burst-out,
  the surprise wall) / **Canyon Viper** (CANYON — DODGE skirmisher:
  max-reflex weights, ap 6, low HP, solo/pair; the can't-hit-it
  problem with melee/accurate/AoE answers). All `always_hostile`,
  `faction=""`, fixed organic `weapons=` (never `weapon_families` —
  SETTLED 35 law; the spitter's sting set via `melee_weapons`),
  species glyphs in biome palettes, NOT identity families. Numbers
  lean on the existing rows (hp 12-26, tier 1-3, existing goods ids
  only in loot pools).
- **The apexes** (`data/npc_chars/monsters.py`, 6 rows): one per
  biome incl. DESERT/ICE — each guards DIFFERENTLY (SETTLED 48
  census; drafts, prose gate): **Dune Behemoth** (DESERT — the
  ANCHOR: guard, armor 5, knockback maul — the Warden slam's field
  reused on an organic weapon); **Glacier Wyrm** (ICE — the
  SOAK-BREAKER: armor_bypass breath + maul set; dodge answers what
  soak can't); **Caldera Tyrant** (VOLCANIC — the BOMBARDIER: long
  heavy siege bolts, holds at range, weak melee; close inside its
  band); **Canopy Maw** (LUSH — the AMBUSH apex: waits beside the
  cache, bursts out on approach; approach the legendary from
  range); **Scrap Colossus** (SCRAP — the IMMOVABLE OBJECT: highest
  HP, ap 2, both weapon sets — armor-piercing spines + knockback
  maul; no weak band, you pay at the range you choose); **Mesa
  Mauler** (CANYON — THE PACK APEX, SETTLED 48: hunter, roams the
  bottom with a hunting pack of 2-4 Canyon Vipers spawned as ONE
  squad; thin the pack, then duel the mauler — the heist math
  changes: bait the pack, not one body). DATA-ONLY rows (SETTLED
  47/48): FLAT bases — hp lean 55-75, armor 3-4, ap 2-5 — the band
  stamp does the scaling (reviewer issue 8: base + `stamina//3` at
  band is effective HP; heavy bases would wall T1 bottoms against
  playtest item 5); `elite=True` (bold), `squad_size (1,1)`,
  pack via the new `pack_pool`/`pack_size` fields (Mesa Mauler
  authors vipers; empty = solo on every other row), band-stamped
  (`fixed_band=0`) — NO new mechanic machinery; knockback and
  armor_bypass ride the EXISTING weapon fields. Authoring law: apex
  `tier` must be >= the tech_level of every entry in its
  `equipment_loot_pool` (drops filter by tier) or the kill pays
  nothing. Big `xp_reward` + authored
  equipment_loot_pool/field_item_loot_pool so the kill reads.
- **The bottom-floor guard** (`digs.py` + `dungeon_population.py`):
  `_place_legendary_cache` exposes its chosen cell (returns the
  pos); `_spawn_squad_near` (+ `_door_room_cells`) HOISTS from
  `main_quest/_delve.py` to `dungeon_population.py` (its act-0
  call site imports the new home; reviewer issue 2 — the
  nearest-first BFS is the existing adjacency machinery, a new
  `_free_floor_cell` walk CANNOT pick near-cache cells); new thin
  `_place_bottom_apex(game_map, spec, pos, band)` spawns the
  resolved apex at the cell beside the cache on the bottom floor
  only, stamped at `_dig_tier(spec, floor)`. Apex resolution
  honors the amended SETTLED 47: `spec.biome` when set, else
  `APEX_BORROW[spec.id]`, else `DEFAULT_APEX_BIOME` — both new
  rows in `data/digs/__init__.py`: borrow map
  {wolf_b, lal_c: ice; mars: desert; venus, vega_b, ac_planet_3,
  indi_b: lush}, fallback desert (tunable opening guesses — the
  themeless groom_b / proc_planet_1 / tau_ceti_b and the stations
  ride the fallback). NO dig anywhere has an unguarded legendary.
  Edge law: no cache cell (`pos is None`) or
  `legendary_bottom=False` → no apex, no crash, zero RNG draws.
- **System surfaces**: SYSTEMS.md entries (dig pools, fauna/apex
  rows) at phase close; guide reviewed with an expected NO-change
  ruling (fauna explain themselves in play; the dig sections
  already teach delve risk).

**Draft pool tables** (opening guesses, tunable — SETTLED 35
precedent; SETTLED 49: machine seats live at bands 1-2 only —
sentry b1 / assault b2 in desert/ice/scrap, lush/volcanic/canyon
fauna-forward with none — and bands 3-4 are FAUNA-PURE, the strong
face weighted up; deeper delves read wilder, not more mechanized):

| biome | band 1 | band 2 | band 3 | band 4 |
|-------|--------|--------|--------|--------|
| desert | scav×2, prowler, sentry | prowler×2, scav, assault | prowler×2, scav×2 | prowler×3, scav |
| ice | worm×2, spitter, sentry | spitter×2, worm, assault | spitter×2, worm×2 | spitter×3, worm |
| lush | hound×3, spore | spore×2, hound×2 | spore×3, hound | spore×3, hound×2 |
| volcanic | crawler×3, magma | magma×2, crawler×2 | magma×3, crawler | magma×4 |
| scrap | hound×2, wasp, sentry | wasp×2, hound, assault | wasp×2, hound×2 | wasp×3, hound |
| canyon | viper×2, lurker | lurker×2, viper×2 | viper×2, lurker×2 | lurker×2, viper |

Densities: the SETTLED 35 ladder (1.0/1.4/1.8/2.2) authored per
biome per band (uniform opening guess; per-biome tuning rides
playtest). hull_parasite stays OUT of biome pools (its seats are
the authored derelict/ancient content + the default TIER_POOLS
band 3). RULED CONSEQUENCE of the fauna pools (reviewer-noted at
build 1, recorded so playtest reads it as designed): biome dig
kills feed NO humanoid pad droppers — discovery door 1 (dig-reveal
pads from humanoid combat kills) is default-table-only; the 12
biome planets' digs reveal sites through doors 2-3 (derelict pads,
terminals).

**Glyph drafts** (species chars; apex = own char, bold). The
freeness standard is the SETTLED 32/34 identity law, not blanket
glyph-uniqueness (reviewer issue 4): the (glyph, color) PAIR is
unique in the ground context — automatic via the existing
`test_ground_context_glyph_color_pairs_unique` — plus one new
TILE-char overlap check with an explicit pin list (the
`CROSS_REGISTRY_PIN` precedent). Char drafts: hound `v`, spore
`i` (not `o` — the prison-panel tile owns it), crawler `x`, magma
`g`, scrap hound `k`, wasp `y`, lurker `l`, viper `n`; behemoth
`B`, wyrm `G`, tyrant `T`, maw `A`, colossus `Z`, mauler `U`.
The elite census lint extends the same commit
(`test_ground_elite_specs_carry_elite` pins its set — reviewer
issue 5).

**Build order:**

1. The seam: `biome` field + 12 declarations + `BIOME_POOLS`
   (DESERT/ICE authored from existing faces) + `_biome_pool`
   resolver + the SETTLED 49 re-tier in the same commit
   (assault_drone tier 3→2 + its equipment pool re-authored to t2
   entries + TIER_POOLS b3/b4 amended) + wiring tests (biome
   planet resolves its pool; `""` resolves the AMENDED default —
   bands 1-2 unchanged from today, b3/b4 the new composition;
   every id in
   every band of every biome resolves via `find_npc_char` and
   densities sit on the 1.0/1.4/1.8/2.2 ladder — the spawn path
   silently swallows unknown ids, so the table needs its own
   integrity row; plus the tier-gate law pin: every row's `tier`
   >= its equipment_loot_pool entries' tech_levels, catalog-wide).
2. The weapons: the 7 organic rows (4 fauna + 3 apex) + catalog law
   tests.
3. The fauna: 8 rows + the pair-uniqueness/tile-overlap lint +
   fauna-law census test (always_hostile, faction="", fixed
   weapons) + the elite-census extension.
4. The apexes: 6 rows + the `pack_pool`/`pack_size` fields +
   `APEX_BORROW`/`DEFAULT_APEX_BIOME` + the `_spawn_squad_near`
   hoist (act-0 call site re-imported) + `_place_bottom_apex` +
   spawn tests: bottom-only; band stamp = `_dig_tier`; apex
   resolves by biome → borrow → fallback (a mars bottom meets the
   Dune Behemoth, a wolf_b bottom the Glacier Wyrm); adjacency
   pins the near-cache cell; PACK composition (SETTLED 48 — a
   canyon bottom = mauler + 2-4 vipers under ONE squad_id, the
   mauler the only bold glyph; the other five apexes spawn solo);
   edges (no cache cell, `legendary_bottom=False`, empty room)
   spawn nothing and crash nowhere; non-bottom floors of every
   planet byte-identical pre/post (the hook consumes zero RNG
   draws when skipped — a generation-level pin, not just pool
   resolution).
5. The four new biome pool tables (LUSH/VOLCANIC/SCRAP_RING/CANYON)
   + the two-save battery re-run (standard rows bit-identical —
   zero drift on existing geometry) + a save/load round-trip row
   in `tests/test_saveload.py` (an apex + fauna floor save/continue
   with entities identical — the zero-new-save-state pin).
6. Prose lands ONLY here, after approval, in its own commit (names
   verbatim as ruled).

**Required tests:** the wiring/regression/lint/census/spawn tests
above (steps 1-5 each carry theirs); save/load sniff via the
headless session (enter a lush dig floor, save/continue, entities
identical — biome is static spec data, zero new save state); the
doc-50 battery rows re-measured once at step 5.

**Stop point (do NOT start):** phase 11 (consortium content, the
hunt); any apex MECHANIC (stare/shriek/field-style dials — data-only
rows, proposals return via refine); re-theming planets or assigning
biomes to unlisted themes; re-authoring surface `monster_pool` /
`cache_guardian_pool` rows (SETTLED 14 law — authored stays); dig
loot/economy changes (legendary axes, cache counts untouched); and
the extensibility audit RECORDS findings without fixing them
(fixes are follow-up proposals).

**Phase-close extras:** the extensibility audit (open question 8 /
acceptance criterion): walk "add one new enemy end-to-end" across
the whole campaign — every code-edit touchpoint found is recorded
in the doc as a punch-list row or a follow-up proposal. SYSTEMS.md
audited same commit (dig-pool entry amended, fauna/apex entry
added).

**PLAYTEST checkpoint (numbered, in-game):**

1. Earth dig (Shift+M force-reveals a site): the delve reads LUSH —
   Vine Hounds/Spore Spitters, no pirates; log lines carry the new
   names.
2. Delve to the bottom: a BOLD apex holds ground beside the
   legendary cache; it engages on LOS, hits hard, dies to a
   prepared player; the legendary is guarded — the risk beat reads.
3. One dig each on ross_b (volcanic), ross_c (scrap), epsilon
   (canyon): each biome's faces + apex read native; scrap feels
   machine-heavy (wasp swarms sting from range); the canyon bottom
   is the PACK read — the Mesa Mauler roams with its viper hunting
   pack as one unit (thin the pack, then duel the mauler; baiting
   one body no longer empties the cache).
4. A mars or venus dig (default biome): the pirate mix — drones at
   the SHALLOW bands only (SETTLED 49: assault sits band 2; bands
   3-4 read rifleman/brute/parasite) — and its bottom carries the
   BORROWED apex (mars: Dune Behemoth; venus: Canopy Maw). wolf_b's
   dig bottom meets the Glacier Wyrm (its authored surface ice fauna
   made the borrow natural).
5. Band read: a T1 dig's apex is beatable at starter level; a T4
   dig bottom (lal_b ice / ross_b volcanic) apex is a wall.
6. Behavior cells: Crag Lurker ambushes (holds, bursts), Rust Wasp
   swarms at range, Canyon Viper/Vine Hound close fast — each cell
   reads distinct in play.
7. Save/continue mid-delve: identical state (entities, positions,
   HP, the apex's aggression).
8. Guide diff: expected NONE (deliberate ruling — fauna and apexes
   explain themselves in play; review and confirm).
9. Loot read: fauna delves still pay (goods + occasional gear);
   the apex's own drop is memorable.

## Phase 10 — LANDED (2026-10-04) + the battery re-run

Five builds, reviewer dispatched per build — five APPROVEs, every
minor folded in-commit (the pad-door consequence recorded in the
brief's pool-table section; spore_burst min_range aligned to the
brief's 2; the build-order line's stale "5 organic rows" count
amended to 7; the wasp's hp into the brief's 12-26 envelope; the
tile lint extended to sweep per-planet DungeonParams dig palettes;
canopy_maw joined the solo-apex test; declared-biomes == the table
set pinned; the round-trip docstring made truthful + the legendary
seed pinned).

Build-discovered notes:

- **The names landed WITH their rows** (frozen dataclasses require
  `name` at construction; every name was approved verbatim with the
  brief, so the prose gate was satisfied BEFORE the build — the
  phase-9 ff8bc62e precedent). The brief's step-6 "own commit" line
  resolves as approval-before-build; the display names ride the
  checkpoint's PROSE review regardless.
- Two planets' registry ids differ from their module filenames
  (procyon_c.py → `proc_planet_2`; epsilon_eridani_b.py → `eri_b`)
  — the biome declarations landed in the right files; tests key on
  registry ids.
- The architecture ratchet fired once (build 4: the hoisted
  `_spawn_squad_near` at 44 lines) — paid in-commit by condensing
  the docstring, no dodge.
- The APEX tables live beside the pools (`BIOME_APEX` +
  `APEX_BORROW` + `DEFAULT_APEX_BIOME` in data/digs), resolution
  `spec.biome or APEX_BORROW.get(spec.id, DEFAULT_APEX_BIOME)` at
  the one choke point (`_place_bottom_apex`); the pack composes
  through the hoisted `_spawn_squad_near`'s explicit `squad_id`
  (act-0's door ambush + cache guardians re-import the new home,
  draw order unchanged).

**The battery (the deliverable): both reference saves, 50 seeded
runs/row, re-run from a git worktree at the pre-phase-10 commit
(b9cd1660) vs the landed tree — ALL rows on BOTH saves
BIT-IDENTICAL (diff empty): zero drift on existing geometry.**
Current reads for the record (labs / merchants): mars pinned 1.000/
0.02 both; 5x rifleman b2 1.000/3.00 (0 def) / 0.980/7.10 (1 def);
5x brute b3 0.940/10.09 / 0.940/11.40; b4 drones/gunners/swarm 1.000
all; watchers 1.000 both; shredder lane 0.940/0.43 / 1.000/26.52;
warden hall 0.940/19.79 / 0.960/19.38; F4 authored mix 0.000 (31
def/19 dis) / 0.040 (29 def/19 dis); space warlord 1.000 / 0.400,
2x marauder 1.000 / 0.180. These differ from the phase-9 recorded
table where the phase-9 MID-PLAYTEST fixes landed after that table
was recorded (712f795d's int-truncated band gates move ranged rows;
45ca4ea7's melee-reach slam makes the F4 mix hotter) — pre-existing
drift, not phase-10's (the worktree diff proves it).

## Phase 10 extensibility audit (2026-10-04 — Q8 answered at close)

The acceptance criterion — **adding an enemy is a data edit: spec
row (+ optional pool/crew wiring), never a code change** — HOLDS,
walked end-to-end per scenario against the landed tree:

- **Ground fauna row**: one `NpcCharSpec` in a `data/npc_chars`
  module (registry auto-discovers) + optional organic weapon row
  (`data/ground_weapons/monsters.py`) + a `BIOME_POOLS`/`TIER_POOLS`
  seat. Data only.
- **Humanoid face**: spec row + family conformance (faction
  families recruit by `faction` automatically; a NEW family is one
  `CHAR_CLASS_FAMILIES` row) + pool seat + `HUMANOID_PAD_DROPPERS`
  if it should feed door 1. Data only.
- **Ship spec**: `data/npc_ships` row + the system's
  `npc_spawn_table`. Data only.
- **A full biome** (the widest case — phase 10 itself is the
  proof): `biome=` declarations + `BIOME_POOLS` + `BIOME_APEX` (+
  optional `APEX_BORROW` row) + the 2-faces-1-apex rows. Data only.

The recurring companion edits are TEST PINS, not game code —
deliberate (pins force conscious changes): `EXPECTED_NOISE` (exact
dict), the elite census (exact set), the verbatim pool pins, the
biome-declaration dict, `CROSS_REGISTRY_PIN`/`TILE_CHAR_PIN`
overlap sets, the melee-set census dict.

Punch list (recorded, NOT fixed — each is a follow-up proposal):

1. The procedural MISSION target ladders are tier dicts in src
   (`mission/_proc_bar.py`, `mission/_proc_bounty.py`) — changing
   WHO missions field means editing code; candidate data
   extraction.
2. `_CUSTOM_ATTACK_LINES` lives in src (`combat/_messages.py`) — a
   new weapon wanting custom attack lines edits code; candidate
   data extraction (the SETTLED 46 seam).
3. The ancient machines' mechanics are code BY DESIGN
   (`combat/_ancients.py` + `MachineMechanics`) — a new MACHINE
   MECHANIC needs code; scoped out by SETTLED 47/48's data-only
   apex ruling (mechanic proposals return via refine).

Authored quest content pinning raw ids (the act-0 door ambush's
`pirate_raider`; survey_a's consortium crew) is SETTLED 28's
authored-specials lane, not a gap.

## Pre-implementation audit — phase 9 BUILD 2 (2026-10-03)

Codebase scan before the machines' code (anchors re-verified against
the post-build-1 tree; line numbers current).

**Reuse (verified):**

- **The build-1 volley loop + economy stand as the machines' engine**:
  `_volley_pick` / `_total_ev` / `_score_ground_weapon`
  (`combat/_ai_ground.py:81-165`), the ledger through returned cells,
  and `ground_loadout.roll_loadout` — which ALREADY stamps a
  weaponless row (both slots `None`): the Watcher's stamp side needs
  zero new code ("drops read the emptiness" is landed behavior).
- **The weaponless path's four gate sites, all live** (the brief's
  reviewer issues 1-2): the `has_any_weapon` early return
  (`_ai_ground.py:64-65`), the `not _gei.weapon_id` NO-TURN gate
  (`_rules_ground.py:745`), the `_aws is None` inert decision point
  (`_ai_ground.py:237-239`), and the `not _fired` "moves into
  position." log (`_spend_ground_ap:222-225`). All four migrate
  together (the build-1 four-consumer lesson).
- **`armor_bypass` already read in the shared damage math beside
  plasma's halving** (`_ground_math.py:67-70`) — the Warden shot
  authors the EXISTING field; zero new math (reviewer issue 4
  resolved by verification).
- **Projectile seams**: `_roll_player_shot` (`combat/_loop.py:322`)
  and `_one_enemy_shot` (`_ai_ground.py:508`); the shared
  `_bresenham_line` (the beam animation's own walk — what the player
  SEES cross the shell is what blocks). Ground flight missiles do
  not exist today (doc-57 flight is space-only; `is_flight_weapon`
  reads the ship registry) — the absorption check is written ONCE in
  `_ancients` and called at both seams, so any future ground
  projectile path inherits it without a third copy.
- **Round-end hook precedent**: the optional `advance_flights` rules
  hook (`_loop.py:716-719` inside `_end_player_turn`) — the eruption
  rides the same getattr pattern, resolving BEFORE enemy turns so the
  erupt-then-remark ordering keeps "exactly one full turn to vacate"
  exact.
- **Noise**: `emit` is weapon-id-keyed (`noise.py:119-154`); `_hears`
  already guards powered_down (dormant deaf — SETTLED 22 intact by
  construction), combat_locked (engaged ignore), hostile-only, and
  the guard leash. `emit_radius` = the same hearer walk with the
  radius as a parameter — one variant shared by shriek + eruption,
  no ad-hoc hearer loops (reviewer issue 7).
- **Enemy-victim path for the eruption**: `_build_enemy_instance`
  (hp stamped on demand) + `spawn_kill_drops` (the victim's own
  drops land) — but NOT `on_kill`'s `add_xp`/kill-counter tail (no
  player attacker).
- **Knockback**: application beside the ground step helpers
  (`move_entity` in `combat/_actions.py`; `world.try_move`'s
  walkable+unoccupied legality; the player displacement re-reveals
  through `reveal_around`, mirroring `try_move`).
- **Blast seam**: `_ground_blast.explosive_blast`'s victim
  enumeration gains field tiles as a victim class; the self-splash
  path is untouched.
- **Prison re-pin**: `data/dungeon_extensions/__init__.py` (all 10
  activation events + 3 monster pools inventoried); the hardcoded
  dormant fallback at `dungeon_activation.py:639` (`["sentry_drone"]`)
  becomes a `DungeonExtensionSpec` field; `_place_dormant_units`
  already stamps `bold=spec.elite` — the Warden's bold `W` rides the
  existing dormant path.
- **Identity**: `CHAR_CLASS_FAMILIES` + `tests/test_enemy_identity.py`.
  Separation pre-verified: violet (170,140,250) sits >= 60 max-channel
  from all six existing family colors (closest: militia, 70). The
  cross-registry pin stays `{"s","h"}` — no npc SHIP flies O/S/W, and
  the sun-`O` / Saturn-`S` shares are space-map TILES (never
  co-rendered with ground faces, the dust_prowler-`p` class).
  `test_ground_elite_specs_carry_elite` is a pin to re-author (the
  Warden joins the brute + sniper). The family lint gains the
  distinct-letters form for the ancients (SETTLED 45).
- **Serialization**: the `hostile_interior` precedent
  (`saveload_maps.py:151-174` save / `:477-497` load) — new GameMap
  fields (`stare_zones`, `field_tiles`) declare at `world.py`,
  serialize through `_optional_map_fields`, restore with
  dict-defaults so old saves tolerate absence.
- **Band pin**: `entity_band` (`ground_scale.py:340`) gains the spec
  param; both spec-holding callers (`_build_enemy_instance`,
  `ground_loadout.ensure_loadout`) pass it (reviewer issue 12's twin
  shut at the one choke point).

**Duplication hotspots:**

1. **The two projectile seams drifting** — two line-walk
   implementations would price the two sides' shots differently; ONE
   absorption helper in `_ancients`, both seams call it.
2. **Stare zone damage vs `_ground_blast` splash shares** — different
   laws (no to-hit roll, graded core/ring, full soak vs the blast's
   50% shares); they share the `_ground_damage_raw` call, never the
   enumeration.
3. **The drift step vs `_reposition_step`** — parameterize the band
   filter (min/max optional) rather than a second pool builder.
4. **The eruption kill tail vs `on_kill`** — shares `spawn_kill_drops`
   only; the XP/counter tail is the player-kill path and must not be
   called for stare victims.

**DRY strategy:** all new machinery (stare state + eruption, field
state + absorption + regen, shriek preamble helpers, mend) lives in
ONE new `combat/_ancients.py`; mechanics dials are DATA (one frozen
profile field + `fixed_band` on NpcCharSpec, owner-declared at
`data/npc_chars/__init__.py`); both overlays paint through one
world_render pass reading GameMap state.

**Ratchet (counts at build start):** `_ai_ground.py` 647,
`_rules_ground.py` 955, `_loop.py` 821, `world.py` 787 — every touch
pays line-neutral or extracts beside its subject (the build-1
`_stamp_enemy_loadout` precedent); the machinery lives in
`_ancients.py` + fresh data modules.

## Pre-implementation audit — phase 2 (2026-09-22)

**Structural reading (resolves the brief's "five factions" phrasing):**
`_ALL_FACTIONS` becomes the four REP AXES — pirate, merchant,
militia, consortium (three visible + one hidden). Civilian LEAVES
the axis set (never seeded, `modify_rep` no-ops it, no decay) but
STAYS as the bystander's accounting tag keying its kill-delta row —
the "five-faction table" is `_COMBAT_KILL_DELTAS`' five row keys.
Standings filter = `HIDDEN_FACTIONS` only; three bars render.

**Reuse (verified):**

- `faction.py` is table-driven end to end: `_ALL_FACTIONS` drives
  seeding (`starting_reputation`), `apply_monthly_decay`, and the
  `modify_rep` legality guard — the axis swap is data edits plus one
  suppression hook. `_apply_rep_delta` (`faction.py:425`) is the
  SINGLE log seam: every write funnels through it (kills, missions,
  decay, `identity.apply_worn_delta` for spoofed sheets), so hiding
  the log there covers all movers at once.
- `identity.effective_reputation` reads any faction via
  `.get(faction, 0)`; consortium hostility flows through
  `spec_is_hostile` with zero hostility-code changes once specs
  re-tag. `buy_scrubbed_id` (`identity.py:280`) and
  `roll_clone_sheet` (`identity.py:433`) iterate `_ALL_FACTIONS` —
  worn sheets pick up the consortium key automatically (blank paper
  reads 0, per the doc-40 scrub ruling; the true sheet's −100 is the
  "trusts no one" start, same asymmetry as militia +50).
- Both kill-delta paths exist and are symmetric table consumers:
  space `combat/_encounter._apply_kill_reputation` (`:97-122`, also
  the `merchant_kills` counter site — the ripple hooks beside it)
  and ground `game_flow._apply_ground_combat_rep` (`:132-150`).
  Both `.get(faction, {})` — the consortium row and the crime
  carve-outs land by table edit, inherited by both theaters.
- Save path: `_parse_save_header` restores `faction_reputation`
  verbatim (`saveload.py:690`), `collected_ids` at `:817` — the two
  migration points are single functions.
- Standings render: `pygame_faction._faction_rows` loops
  `_ALL_FACTIONS` (`:74`) — the ONLY standings renderer (the F-screen
  ship menu contributes only `_faction_progress_bar`; no twin).
- `trade.py:495` `getattr(npc_spec, "faction", "civilian")` is a
  read-side fallback only (specs all carry `faction`); the retired
  axis means the fallback key must change — `""` reads neutral, the
  monsters' convention.

**Duplication hotspots:**

1. Hidden suppression has TWO presentation surfaces (the log seam
   and the standings loop) — a future third surface (a modal listing
   factions) could forget the filter.
2. The civilian-key migration has TWO stores (top-level
   `faction_reputation` AND every `collected_ids[*].rep` sheet) —
   the classic parallel-paths drift: fix one, forget the other.
3. The kill-delta application is a twin (space `_encounter` /
   ground `game_flow`); the merchant militia −2 crime component must
   ride the TABLE so both inherit — while the merchant_kills ripple
   must live ONLY beside the space counter (ground merchant-crew
   kills are the direct mover's job, not the ripple's).

**DRY strategy:**

1. `HIDDEN_FACTIONS` defined once in `faction.py`;
   `_apply_rep_delta` suppresses the log for hidden axes;
   `_faction_rows` filters the same constant. No per-caller
   branches anywhere.
2. One `_sanitize_reputation` helper in `saveload.py` (drop retired
   keys, seed an absent consortium at the axis start value) applied
   to BOTH the top-level dict and each identity sheet — same
   function, two call sites.
3. Crime carve-outs live only in `_COMBAT_KILL_DELTAS`; the ripple
   is one line beside the existing counter increment.

**Called-out consequences (visible at playtest, one-line changes if
ruled otherwise):**

- Decay is uniform: the hidden axis ages like any enemy-zone axis
  (+3/month toward neutral from −100, invisible — no log). ~25
  months to leave hostility; excluding it would be the special case
  the no-special-cases ruling forbids.
- Killing a consortium enforcer still logs the pirate +1 component
  (a pirate-axis line); only the consortium line is suppressed.
- `TIER_POOLS` substitution is repetition-weighted (uniform draws
  over the tuple): gunner seat → `pirate_raider` (band 1), enforcer
  seat → `pirate_rifleman` (bands 2-3) — preserves each band's
  hostile share exactly, no new faces (band re-author is phase 4).
- Old-save consortium seeding: flat −100 (no species/class rows
  exist for it); a save that already carries the key is untouched.

### Phase 2 Implementation brief (APPROVED 2026-09-22 — reviewer v2
fixes folded in; the three flagged decisions confirmed by the user:
hidden-axis start −100, piracy-is-crime incl. the act0_bar re-key,
enforcer glyph `E`)

**Scope (files / hook points):**

- `faction.py` — consortium joins `_ALL_FACTIONS` (five factions);
  `_DEFAULT_REP` consortium = **−100** (preserves today's
  enforcer/gunner hostility exactly; flavor: the hidden hand trusts
  no one — flag for user confirmation); consortium row in
  `_COMBAT_KILL_DELTAS` (proposed: consortium −3, pirate +1 —
  in-family with existing magnitudes); `HIDDEN_FACTIONS =
  {"consortium"}` — excluded from the standings screen AND from
  the rep-delta LOG lines (`_apply_rep_delta`, `faction.py:450-457`
  — hidden is presentation-only everywhere, SETTLED 9 "renders
  nowhere"). Civilian retirement — the REP AXIS dies (start table,
  `_CLASS_REP`, `_SPECIES_REP`, `_MISSION_REP_DELTAS`,
  `_COMBAT_UNPROVOKED_DELTAS`), with TWO stated carve-outs: the
  `civilian` kill-delta row KEEPS `{militia: −2}` (the honest-folk
  crime ledger — bystander stays tagged `civilian`, a non-faction
  accounting tag) and the merchant kill row GAINS a militia −2
  component (piracy is crime — flag for user confirmation); guild
  map re-keys civilian → merchant INCLUDING the hardcoded
  `guild_to_faction` fallback (`faction.py:264` + its test).
- Hidden-rep movers v1 (SETTLED 9, hooked correctly): direct =
  killing consortium-tagged specs (kill-delta path); ripple = the
  existing `merchant_kills` counter (`combat/_encounter.py:114`,
  already saved at `saveload.py:625`) — each merchant-ship
  kill (including booked boardings) drops the hidden axis −1.
  NOT crew-kill-based (those are consortium-crew events — the
  direct mover already fires there).
- `data/npc_chars/core.py` — `consortium_enforcer`/`consortium_gunner`
  re-tag `faction="consortium"`.
- `data/digs/__init__.py` — **the two-id pool de-list rides THIS
  phase** (not phase 4's re-author): consortium_gunner out of band
  1, consortium_enforcer out of bands 2-3, substituted with
  pirate/militia weight per SETTLED 16 — so the re-tag window never
  has procedurally-spawned consortium (SETTLED 12 stays true) and
  bands never read peaceful (SETTLED 16).
- `identity.py` — verify `effective_reputation` carries consortium
  per sheet unchanged; sweep worn-ID sheets for civilian keys
  (migration consistency).
- `saveload.py` — load drops stored `"civilian"` rep keys (top
  level AND identity sheets); consortium persists via the existing
  dict.
- `pygame_faction.py` — the standings render filters
  `HIDDEN_FACTIONS` (render hook loops `_ALL_FACTIONS`, `:74`).
- Blast-radius sweep (reviewer-verified consumers): `trade.py:495`
  civilian fallback attr; `_MISSION_REP_DELTAS` civilian entries;
  quest reward `rewards_rep={"civilian": −5}` (`act0_bar.py:62` —
  re-key to merchant, user-flagged since it changes a live quest's
  rep payout); registry docstrings (`npc_chars/__init__.py:31`,
  `npc_ships/__init__.py:26`).
- `main_quest/_heat.py:77-83` docstrings stay AS-IS (hired-pirate
  fiction is true until phase 11 reskins the hunt) — annotated,
  not edited.

**Build order:** faction tables + hidden axis (start, suppression,
movers) + save migration → re-tags + the two-id pool de-list →
crime/guild rules + blast-radius sweep → full gate.

**Binding rulings:** SETTLED 5, 8, 9, 12, 16, 20, 32. Hidden axis
gates NOTHING, renders NOWHERE (standings AND log). No new
consortium spawns anywhere.

**Stop point:** no band-4 work, no family ladder, no weapon-family
changes, no glyph/color pass (phase 3), no heat reskin (phase 11).
The pool edit above is a two-id de-list, NOT the band re-author.

**Required tests:** five-faction table integrity; hidden axis
absent from standings AND from log output on a mover; consortium
kill deltas + ripple (merchant_kills counter → hidden −1);
civilian migration incl. identity sheets; crime row (bystander →
militia −2; merchant kill → merchant deltas + militia −2);
merchants-chain + militia suites green (heat squads unchanged,
act0_bar re-key covered).

**Playtest checkpoint:**

1. Faction standings: THREE bars (pirate/merchant/militia — no
   civilian, no consortium).
2. T1 delve (SPACEHACK_DEV, pinned seed): corporate guards fight on
   sight exactly as today (start −100 preserves behavior); their
   kills log NOTHING (no "Consortium faction" line anywhere) —
   quit and inspect the save's rep dict: the consortium key moved.
3. Destroy a merchant hauler in space: merchant rep drops AND the
   hidden counter ticks (save-file check); militia −2 fires.
4. Kill a city bystander: militia −2 fires; no civilian bar to
   move.
5. Save/quit → continue: old save loads clean, standings intact.
6. Regression: merchants chain heat squads spawn and fight
   (pirate hulls + fiction unchanged); militia scans unchanged;
   act0_bar's rep reward lands on merchant.
7. Guide-diff item: reviewer verified the guide contains NO
   civilian mentions — the checkpoint is a confirm-grep (expected
   no-op; any hit becomes a called-out before/after).

### Phase 3 Implementation brief (RE-CUT v2 2026-09-22 — SETTLED
### 33/34 + the char-reuse addition folded in; APPROVED same day)

**Verified foundations (2026-09-22):**

- **The hull alphabet already ships.** `data/ships/core.py` carries
  `char`/`fg` per hull: skiff `t` steel-blue, scout `s`, hauler `H`
  green, cruiser `C` red, frigate `F` purple, freighter `F` gold
  (the F-pair is color-distinguished in the shipyard today). Zero
  alphabet authoring — the player already learns these glyphs in
  the shop, and the lint rule "spec char == hull char" has a real
  single source.
- **The cross-registry pin collapses to ONE entry.** Ground glyphs
  in use (r R M E g c s d w p D f m) against t/s/H/C/F: only `s`
  meets rock_scavenger `s`. The M/D/p pins dissolve with the swap.
- `consortium_enforcer`/`consortium_gunner` are pinned in authored
  crew layouts (`freightliner_crew`, `hauler_crew`, `survey_a`) —
  the re-glyphs render on those decks. (The `ENEMY:` marker letters
  are layout geometry keys, not render glyphs — untouched until
  phase 6.)

**Scope (files / hook points):**

- **Ship identity data** (`data/npc_ships/core.py` + `deep.py`):
  every NpcShipSpec takes its hull's char (scout `s` ×4, cruiser
  `C` ×4, frigate `F` ×3, freighter `F` ×3, hauler `H` ×1) and its
  faction's ONE family color — pirate red (lean (220,60,60)),
  militia teal (130,230,220) stands, merchant green (lean
  (100,220,140)); derelicts keep amber (200,160,80) + brass
  (190,140,60) per SETTLED 33. `p`/`P`/`B`/`D`/`W`/`M`/`F`/`C` as
  faction marks retire. Class twins render identical — intended
  (SETTLED 31/33).
- **Bold wiring (SETTLED 33):** `elite: bool = False` on
  NpcShipSpec (captain + warlord True); `Entity` gains `bold:
  bool = False`, set at EVERY NPC-ship Entity construction site
  (spawn, mid-fight joiners, clones — parallel-paths sweep);
  `WorldDrawCommand` carries the flag; the engine builds a WIDENED
  glyph atlas at load (`_widen_glyph_tile` +1 ink column) and
  `GlyphAtlas.blit` picks the atlas by the flag; the command-dict
  serializer includes it. One mechanism, both theaters — ground
  wearers (sniper/heavy) take the same field at phase 4.
- **Ground family tables** (`CHAR_CLASS_FAMILIES` in
  `data/npc_chars/__init__.py` — letter + case variants + one
  color per SETTLED 34): pirate `r`/`R` (one color — lean
  rust-orange (220,120,80)); machine `d`/`D` (one color — LEAN
  BRONZE (200,170,110): the cold-blue options sit ~5 from
  consortium's family, the exact crowding the separation lint
  exists to catch); militia `m` (trooper `M` today; re-cases at
  phase 4 with the marine); consortium `e` (enforcer `E` = the
  serious case; **gunner `g` → `e`** the common case — delisted
  from pools, renders in the authored decks); civilian `c`.
  Fauna are not families (SETTLED 34) — untouched.
- **The collision lint** (new `tests/test_enemy_identity.py`):
  - SHIP (hard): `spec.char == find_ship(spec.ship_id).char`.
  - FAMILY (hard): every hostile-capable ground spec belongs to a
    family; members are case variants of the family letter; all
    members share the family color exactly.
  - SEPARATION (hard, tunable constant): pairwise max-channel
    distance between identity-group family colors ≥ 60 — the
    teal / consortium-blue / machine-blue neighborhood is why it
    exists, and it is what legalizes reusing a char across
    families where authoring needs it (SETTLED 34 addition).
  - CROSS-REGISTRY (pinned): ground/space glyph overlap among
    hostile-capable faces equals exactly {scout `s` vs
    rock_scavenger `s`}; a new overlap fails the pin. Case
    variants are distinct glyphs — the same-context uniqueness
    rule needs no family exception.
- **Enforcer `E`** (user-ruled, phase-2 brief) and **`civillian`
  → `civilian_bystander` rename** (~195 tuple refs, alias for
  save compat): unchanged from the prior cut.
- **Punch list** (unchanged): `PROC_C_POPULATION` dedup;
  `ai_flee_threshold` retirement (field + docstring + ~12 authored
  values); `buy_ammo` cargo_ammo recalc; dual-registry
  `pirate_raider` docstring note.
- **Color-family docstrings**: registries record the families;
  ancient machines land theirs in phase 9.

**Authoring leans (playtest-tunable — user, 2026-09-22: "I
imagine as I playtest we'll want to tweak glyph/colors as needed.
But this is good."):** the F-pair stands (frigate + freighter
share `F`, color-distinguished — the existing player vocabulary;
re-lettering the freighter breaks shipyard knowledge); machine
bronze; pirate red (220,60,60); merchant green (100,220,140);
gunner `e` now rather than phase 11. Every value is a single-point
data edit and the lint re-checks on every gate run — no blocking
fork remains.

**Playtest rulings (2026-09-22, mid-checkpoint):**

- **Militia teal → BLUE (100,200,255); consortium → navy
  (90,120,200).** User: "militia color and merchant color are very
  very close to each other... especially when the ship has the blue
  shield around it, it really stands out as merchant green." Teal
  was hue-adjacent to merchant green despite passing the ≥60 lint,
  and the cyan shield ring (80,210,255) compounded it. Militia
  reads true blue now (militia↔merchant 115, blue-vs-green hue
  split); consortium vacated the blue middle (any militia blue
  collides with the old corporate (120,160,220)) — militia↔
  consortium 80. Landed c60fb3a2.
- **Freighter re-lettered `F` → `B`; frigate keeps `F`.** User
  (after reading a Merchant Caravan's `F` and double-checking):
  "we need a new glyph for freighter's. I like F for frigate."
  Supersedes the brief's F-pair lean (shipyard knowledge loss
  accepted by this ruling). `B`: chunky bulk read, uppercase
  capital-ship convention, free of every space-map letter (Mars
  `M`, Jupiter `J`, Saturn `S`, stations `^`, gates `>`/`<`,
  planets `p/P/O/o`) and the ground-hostile set — cross-registry
  pin stays {s}. Hull catalog + 3 freighter-hulled specs
  (derelict_freighter, merchant_freighter, merchant_caravan); the
  hull-pin lint carried the change.
- **Refined same day: `B` → the h/H cargo pair.** User: "how about
  we make hauler h and freighter H?" — hauler `H` → `h`, freighter
  `B` → `H`. The case pair IS the cargo family: lowercase = the
  smaller hauler, uppercase = the massive freighter, matching the
  small-ships-lowercase convention (t, s) and freeing `B`. Alphabet
  now t/s/h/C/F/H; cross-registry pin still {s}; both h and H
  clear every planet/station glyph.

**Build order:** ship char/color data + lint ship rule → ground
families + `E`/`e` + lint family/separation/pin → bold wiring
(`elite` field → `Entity.bold` at every construction site →
command → widened atlas) → rename + alias → punch list → full gate.

**Binding rulings:** SETTLED 20, 32, 33, 34; values 1 + 8. No new
faces, no stat changes, no prose.

**Stop point:** no band-4/scaling (phase 4), no role-token markers
or crew re-authoring (phase 6 — the `ENEMY:` letters in layouts
are geometry keys and stay), no ancient-machine re-cut (phase 9),
no consortium ships (phase 11), no shipyard screen changes, no
ground bold wearers (the field lands with phase 4's faces), and
the trooper keeps `M`.

**Required tests:** the lint's four rules; elite renders bold
(command-level: flagship specs emit `bold=True`; a widen smoke test
— the bold atlas differs from the base atlas on a sample glyph);
rename — alias resolves, every population tuple references a live
spec id (existing `test_city_npcs` suites cover), no `civillian`
string survives outside the alias; `E`/`e` pinned;
`ai_flee_threshold` gone (authoring it raises TypeError — pinned
via registry build); `buy_ammo` cargo recalc (magazine buy →
`cargo_ammo` matches `total_ammo_cargo`); `PROC_C_POPULATION`
single definition (population tests cover); sweep existing tests
for pins of the retired ship glyphs (none found in the registry
suites — verify at build).

**Playtest checkpoint:**

1. Space sweep: pirate contacts read `s`/`C`/`F` in one red,
   captains + warlords BOLD `F`; militia `s`/`C`/`F` teal — the
   weight ladder light→standard→heavy legible as `s`→`C`/`C`→`F`;
   merchants `H`/`F` green; derelicts `s`/`F` amber/brass.
2. The F-pair wrinkle, judged with eyes: red `F` (warship) vs
   green `F` (cargo) read apart at a glance.
3. Board a merchant hauler/freighter: deck crew reads `E`/`e`
   corporate blue, drones in the machine family color.
4. City: bystanders look identical (corrected id), kills still
   cost militia −2 (phase 2 rule).
5. Save/quit → Continue on the phase-2-era save: clean load,
   tombstones honored.
6. Space: buy missile ammo → cargo HUD math consistent.
7. Guide-diff item: expected NONE (glyphs/ids are internal) —
   confirm-grep of `data/guide/`; any hit becomes a called-out
   before/after. Glyph/color values are single-point data edits —
   tweak freely in playtest; the lint re-checks on every gate run.

### Phase 4 Implementation brief (APPROVED 2026-09-22 — SETTLED 35
### + 13/14/15/16/19/30/34)

**Scope (files / hook points):**

- **The resolver** (new `spacehack/ground_scale.py`, pure functions):
  `band_budget(band) -> int` (5×(eff_level−1); levels 3/10/18/30),
  `derive_stats(spec, band) -> GroundStats-like 6-block` (base 10,
  budget split by the spec's archetype weights; space skills take
  the flat minor share), `roll_weapon(spec, band, rng) -> weapon_id`
  (family pick + top-two tier window per SETTLED 35), and the
  per-band quality-rate table (B1 (5,11,25) → B4 (10,20,40)).
  Consumed at EVERY NpcCharSpec spawn: digs (`digs.py`
  population), procgen mission dungeons + city ambient
  (`dungeon_population.py` / `city_npcs.py` sites), quest-guard
  ensure (`main_quest/_spawns.py` path), and capture-deck ENEMY
  markers (authored markers fix the SPEC; the site's band — parent
  planet `mission_tier` — still sizes stats/gear: uniform
  mechanism, no special case).
- **Spec data** (`data/npc_chars/__init__.py` + rows): humanoid rows
  replace fixed `weapons=`/`weapon_pick` with
  `weapon_families: tuple[str, ...]` (catalog module names); all
  rows gain `stat_weights: tuple[float, ...]` (six; archetype
  profiles per SETTLED 35) — authored reflexes/strength/stamina
  RETIRE (band derives them; fauna too, SETTLED 30; organic monster
  weapons stay fixed). `elite: bool = False` on NpcCharSpec (brute +
  sniper True — theater-uniform with ships). New rows: **Pirate
  Brute** (bold `R`, explosives family, strength/stamina-heavy
  slow-hunter, armor anchor), **Militia Marine** (`M`,
  strike-crew), **Militia Sniper** (bold `M`, reflexes-max, rifles
  pinned to window top). Trooper `M`→`m`.
- **Band wiring:** `_site_tier` unclamped to 4 (`digs.py`);
  `TIER_POOLS` re-authored to four bands + densities
  1.0/1.4/1.8/2.2 (`data/digs/__init__.py`); quality equip/drop
  rates read band (`data/quality.py` band-indexed table; drop paths
  in `ground_equipment`/kill-drop sites).
- **Entity/save contract:** ground entities stamp their band at
  spawn (`Entity.spawn_band: int = 0`); serialized in
  `_entity_to_dict` + load (0 = derive from context — legacy-save
  default). Combat stat reads go through the resolver output, not
  spec fields.
- **Lint amendment** (`tests/test_enemy_identity.py`): ground
  identity key becomes (char, fg, elite); family conformance covers
  the new rows (brute/sniper bold serious-case).

**Build order:** resolver + spec fields + row migration (pure core,
tests first) → band wiring (unclamp, pools, densities, quality) →
new faces + trooper re-case + ground bold at the four ground entity
construction sites → entity/save stamping → full gate.

**Binding rulings:** SETTLED 13, 14, 15, 16, 19, 30, 34, 35. Squad
sizes spec-authored (bands never scale them); bystanders exempt;
militia never the difficulty carrier; consortium absent from pools;
authored markers fix specs, not stats.

**Stop point:** no tactics-wave work (noise, combat-time AP
movement, range management, per-spec AP field, consumables — phase
5); no role-token crew markers or deck re-authoring (phase 6); no
ship-side band/loadout rolling (phase 7); no merchant crew row
(phase 6); no ancient machines (phase 9); `detect_radius`
disposition stays phase 5's.

**Required tests:** resolver purity (budget math, weight split,
window/weight tables per band, quality rates per band, sniper
top-pin); pools table shape (four bands, no consortium id,
densities); derived-stats migration (no spec reads the retired
fields — grep-pinned); entity band round-trips save/load; bold
ground render (brute/sniper emit bold=True commands); lint amended
key green with the new rows; existing dig/dungeon/city suites
updated to the resolver.

**Playtest checkpoint:**

1. T1 dig (dev planet pin): raiders/trooper feel like today (no
   nerf), all t1 gear, quality baseline.
2. T2 dig: riflemen with kinetic rifles/battle rifles at the 70/30
   window; stats visibly up (~30s primaries).
3. T3 dig: **brutes present** — bold `R`, grenade→rocket family,
   slow heavy hunters; T4 dig: brutes heavier still, rifleman
   railguns/ion blasters appear, band-4 quality rolls visible on
   wielded-drops.
4. Militia faces where authored/city: trooper now lowercase `m`,
   marine `M`, sniper **bold `M`** with the top-tier rifle.
5. Save/quit mid-delve → Continue: enemy stats, wounds, and
   band-stamped state identical.
6. Regression: capture decks crewed by their pinned specs; monsters
   scale by band (same scavenger row tougher at T4); bystanders
   identical everywhere.
7. Guide-diff item: expected NONE — the guide already promises
   "deeper sites and tougher machines yield better gear"; this
   phase makes it true. Confirm-grep; any hit becomes a called-out
   before/after.

### Phase 5 Implementation brief (PROPOSED v2 2026-09-22 — SETTLED
### 16-18, 22, 24-27 + 36/37; reviewer ADVISE pass and its rulings
### folded)

**Scope (files / hook points):**

- **Weapon noise data** (`data/ground_weapons/__init__.py` + family
  modules): `noise: int = 8` on the spec; authored leans
  (playtest-tunable): explosives 12, rifles 8, pistols/SMG 5-6, melee
  1-2 (knife kills stay quiet), plasma 4 (the energy lever — quieter
  than kinetic), organic monster weapons 4-5. Registry completeness
  test: every catalog weapon carries a value.
- **Per-spec AP + detect_radius retirement** (`data/npc_chars/
  __init__.py` + rows): `ap: int = 4` on NpcCharSpec; authored leans:
  predators 5-6 (dust_prowler 6; ice_worm, rock_scavenger,
  hull_parasite 5), armored anchors 3 (assault_drone, brute), all
  humanoids + sentry_drone 4. Ground `detect_radius` RETIRES per
  SETTLED 36 (field + ~15 authored values; authoring it raises
  TypeError — the `ai_flee_threshold` pin pattern). `NpcShipSpec`
  untouched (its field is live).
- **The noise system** (new `src/spacehack/noise.py` — pure emission
  and hearing scan, thin mutators):
  - `emit(ctx, game_map, origin, radius)` for the firing report;
    explosives ALSO `emit` at the impact cell (blast draws from where
    it lands, SETTLED 17/22). Hearing = flat Chebyshev radius check,
    walls do not block; the heard set is hostile-reading combatants
    only (`spec_is_hostile` | `always_hostile`) — skips `powered_down`
    (dormant deaf, SETTLED 22), skips engaged entities, non-hostile
    NPCs (bystanders) ignore gunfire.
  - Heard = the EXISTING last-seen machinery (`ground_npcs`) stamped
    at the sound origin — one attractor slot, latest event wins.
    Investigation is GOAL-BASED (SETTLED 37): the hearer moves until
    it holds LOS on the goal area — NO tick decay; arrival with
    nothing seen → revert to prior behavior; unreachable goal (no
    path) → give up. Stamp semantics include hunters, ambushers, and
    — leash-gated — guards (SETTLED 37: area guardians): a guard is
    stamped only when within its rolled weapon's max_range + 2 of the
    sound origin, and the rolled weapon PERSISTS on the entity
    (idempotent first-resolution stamp, serialized — also ends
    today's per-engagement weapon re-roll; a guard that investigates
    holds where the search ends, a leash-bounded new perch).
  - **Squads follow noise as a unit** (SETTLED 37): stamps are
    per-entity; `_move_squad` pursuit keys on ANY member's goal — one
    hearing member draws the squad; LOS aggro stays individual
    (SETTLED 16).
  - Emission sites, both sides symmetric: the player's ground fire
    resolution (with `consume_shot`, `combat/_rules_ground.py` / the
    fire action in `combat/_actions.py`) and enemy `_try_ground_fire`
    (`combat/_ai_ground.py`); blast events at `explosive_blast` /
    `_apply_explosive_enemy_hit` + the player-side explosive impact.
  - The `noise_hostiles` stub (`combat/_encounter.py:249`) RETIRES
    (SETTLED 36) — investigators reach combat only via the existing
    LOS join scans. Player-facing feedback (SETTLED 36 addition): ONE
    reaction line, "Something to the {direction} heard that."
    (COLOR_IMPORTANT_EVENT) — fires when an emission stamps at least
    one FRESH hearer (no active attractor goal, not combat-locked),
    player-relative 8-way direction to the nearest fresh hearer; once
    per new-hearer event (sustained fire never spams); enemy fire and
    quiet weapons never trigger it — the line's absence is the
    stealth signal.
- **Combat-time movement + stepwise LOS join** (`ground_npcs.py`):
  `move_ground_npcs` gains the mode — while a ground fight is live,
  every UN-engaged entity (bystanders included, SETTLED 36) moves up
  to its AP in tiles instead of 1; after EACH tile the mover
  re-checks the player's visible grid (the `_visible_hostile_entities`
  FOV logic) and STOPS on acquisition — investigators never overshoot
  past LOS (SETTLED 17). Mode key = ground combat fight-live state;
  the callers inherit (between-rounds `_rules_ground.py:937`, explore
  `game_flow.py:216`, debug `debug_session.py:556`); fight over →
  everything folds back to the 1-tick stroll (SETTLED 25). City
  bystanders flow through the between-rounds pass during a live fight
  (city NPCs carry `npc_char_id`) — `move_city_npcs` on explore ticks
  is NOT wired to the mode. Perf (repo rule: cache, don't recompute):
  one cached A* path per investigator per pass, walked up to AP tiles
  with the stepwise LOS re-check between tiles.
- **Range management + leash** (`combat/_ai_ground.py`): the universal
  loop takes the ROLLED weapon's [min_range…max_range] — beyond max,
  close (one A* step per AP); in band, hold and fire; inside min, back
  off to the nearest cell restoring ≥ min_range, LOS-keeping steps
  preferred (SETTLED 26). Leftover AP after the one-shot cap
  repositions. Melee untouched by construction (band [1…1]). Guard
  leash `_GUARD_LEASH_RADIUS = 8` dies → per-instance derivation from
  the rolled weapon (`max_range + 2`, SETTLED 18); hunters stay
  unbound.
- **AP derivation + enemy consumables** (`combat/_rules_ground.py` +
  `combat/_ai_ground.py`):
  - `ap=4, ap_total=4` in `_build_enemy_instance`'s return becomes
    spec-derived through a modifier-aware calc (spec AP + worn
    cybernetics `ap_bonus` seam + stim temp +1) so phase-11
    consortium wearers just work (SETTLED 27).
  - Carried consumables (SETTLED 36): resolved ONCE at first combat
    entry, stamped idempotently on the entity (new `world.Entity`
    field, serialized in `_entity_to_dict` + load — dataclass-field
    cohesion), seeded from the spec's `field_item_loot_pool`
    consumable entries with the same distribution the death roll uses.
    The death-drop site (`combat/_actions.py:198`) reads the stamp:
    unused items drop, used items never do — one resolution for the
    CONSUMABLE entries only (ammo/equipment entries keep their
    death-time roll); carried stack qty uses the same qty roll the
    death site uses today (a partly-used stack's remainder drops); an
    enemy dying without ever being instance-built falls back to
    today's death roll.
  - Use logic in the enemy turn (AP cost = the item's `use_ap_cost`):
    med_pack at HP ≤ 50% (heal 5 + regen 2×3 turns, mirroring
    `apply_consumable_effect`); stim when engaged with LOS and not
    already stimmed (+1 AP ×3 turns — instance temp fields, ticked
    per round; fight-scoped: not serialized, the once-per-fight
    trigger reads once per instance build). ANY carrier may use
    (SETTLED 36). Log lines in the
    house "{name} moves into position." format via
    `COLOR_ENEMY_ACTION` — wording APPROVED 2026-09-22 (SETTLED 36
    addition): "{name} uses a Med Pack." / "{name} injects a Combat
    Stim."
- **Door verification** (audit flag closed): a test pinning enemy A*
  through DOOR/DUNGEON_DOOR tiles (all `walkable=True` — verify no
  runtime state gate blocks the path; fix forward if one exists).
- **Ratchet note:** `_rules_ground.py` is at 999 of 1000 lines — the
  emission wirings that must land inside it (player fire beside
  `consume_shot`, `explosive_blast`, `_apply_explosive_enemy_hit`)
  make a same-commit extraction MANDATORY, not contingent. New logic
  lands in `noise.py` / `ground_npcs.py`; `_rules_ground` edits pay
  the debt in-commit.

**Build order:** weapon/spec data fields + detect_radius retirement
(registry tests) → `noise.py` + both emission wirings + attractor
stamps → combat-time movement + stepwise join → range management +
leash derivation → AP derivation + consumables (stamp, use, drop,
save/load) → dev grants + full gate.

**Binding rulings:** SETTLED 16, 17, 18, 22, 24 (the in-combat
memory-chase is WITHDRAWN — do not build), 25, 26, 27, 36, 37. LOS is
the only aggro; heard ≠ combatant, ever; investigation is goal-based
(no tick memory anywhere); guards hear leash-gated (area guardians,
weapon persisted on the entity); squads follow noise as a unit; no
collective squad aggro ground-side; no reinforcement mechanic
(SETTLED 21); the one-shot-per-turn cap stands; squad sizes never
band-scaled.

**Stop point:** no crew/role-token markers or deck re-authoring
(phase 6); no ship-side work of any kind — no space noise, no enemy
AP/energy/regen parity (phases 7-8); no ancient machines (phase 9);
no WEARERS of the cyber-AP seam — the seam lands, consortium content
doesn't (phase 11); no new pursuit/memory machinery beyond the
existing last-seen stamps.

**Required tests:** noise completeness (every weapon authored);
hearing-scan selectivity (combatants only, dormant deaf, engaged
skip, bystander ignore, latest-wins re-stamp); blast emits at the
impact cell; the reaction line (fires on fresh-hearer events only —
no active goal + not combat-locked — correct player-relative 8-way
direction, quiet weapons never trigger); goal-based investigation
(persists until LOS on the goal, arrival with nothing seen reverts,
unreachable gives up — NO tick countdown anywhere); guard leash gate
(stamped only within rolled max_range + 2; weapon persists on the
entity through save/load; re-engagement never re-rolls); squads
follow noise as a unit (any-member key; LOS aggro individual);
combat-time movement ≤ AP with the stepwise-join stop (never
overshoots) and peace mode = 1 tile; range management (close /
hold / back-off restores ≥ min_range; melee never backs off); leash =
rolled max_range + 2 per instance; AP default + authored values +
stim tick-down (fight-scoped, not serialized); consumables
(idempotent pre-roll, drop-if-unused incl. partly-used remainders,
consume-on-use, HP/stim triggers, no-stamp death fallback, save/load
round-trip of the carried stamp + attractor goal); `detect_radius`
gone (TypeError pin, ground registry only); door-path pin;
bystander AP movement during a live fight.

**Playtest checkpoint:**

1. T2 dig (dev planet pin, pinned seed): open a fight with a rifle —
   enemies from the next room arrive mid-fight (visible investigate
   movement), engaging only when YOU can see them, never through
   walls.
2. Kite check: break LOS around a corner and lurk — the pursuer keeps
   investigating until it gets eyes on where you vanished, then
   reverts to patrol when it finds nothing (the 5-tick retirement;
   no more giving up mid-corner).
3. Quiet knife kill: melee-kill a straggler without waking the next
   room; then fire a rocket into a pack — the blast draws the
   neighborhood from where it LANDED.
4. Hug a rifleman: he backs off to restore his min_range; corner him
   against a wall and he goes inert (counter-play by design). A guard
   holds its post; fire near one from beyond its weapon max + 2 and
   it does NOT come; within range it investigates — and settles at a
   new perch near the sound, then guards THERE.
5. (dev grant: adjacent enemies pre-stamped with med_pack/stim) The
   wounded one uses a Med Pack (log line, target-card HP visibly up);
   the stimmed one acts 5 AP for three rounds; unused items drop on
   death, used ones never do.
6. City fight: bystanders scatter at AP speed while the fight is
   live; none attack; end the fight → everyone strolls again.
7. Save/quit mid-investigation → Continue: attractor goals, wounds,
   carried items identical (the goal survives the round-trip).
8. Regression: dig/dungeon/city spawn suites + phase-4 band scaling
   unchanged; space combat untouched.
9. Noise feedback + guide-diff item: fire a loud weapon with an
   off-screen enemy in the next room — "Something to the {direction}
   heard that." fires once with the correct direction; knife-kill a
   straggler — NO line (quiet stays quiet). Guide: expected NONE —
   noise is communicated in play via the reaction line, never a guide
   entry (user ruling 2026-09-22); the confirm-grep stands as the
   checkpoint.

Dev grants: phase-4's disjoint per-face slices stand; add the
deterministic carrier grant for item 4 (SPACEHACK_DEV, `dev_mode.py`
+ `test_dev_mode.py`).

## Phase 6 Implementation brief (FINAL v2 2026-09-23 — SETTLED 3/5/7/
## 10/13/18/28/38; ADVISE reviewer pass + its folds + the editor
## ruling folded — ready for /implement-phase 48.6)

**Scope (files / hook points):**

- **The role-token grammar + CREW_ROLES** (new
  `data/npc_chars/crew_roles.py`, frozen table): `CREW_ROLES:
  dict[faction, dict[role, spec_id]]` resolving the SETTLED 28
  vocabulary (`line` / `heavy` / `marksman` / `security_drone` /
  `stowaway`) per faction — pirate {line: raider, heavy: brute,
  marksman: rifleman, security_drone: sentry_drone, stowaway:
  hull_parasite}; militia {line: trooper, heavy: marine, marksman:
  sniper, security_drone: sentry_drone — stowaway OMITTED (weight 0,
  SETTLED 38)}; merchant {line: Merchant, heavy: assault_drone,
  marksman: sentry_drone, security_drone: sentry_drone, stowaway:
  hull_parasite}; consortium {line: enforcer, marksman: gunner,
  security_drone: sentry_drone, stowaway: hull_parasite — authored
  decks only (SETTLED 12), raw ids stay legal}. Omitted role = the
  marker skips at load.
- **Marker resolution seam** (`dungeon_layout.py`): `load_layout`
  gains `crew_faction: str = ""` + `security_drones: float = 1.0`;
  `_scatter_layout_enemies` resolves a role token through
  `CREW_ROLES[crew_faction]` (raw spec ids pass through unchanged);
  the dial scales `security_drone`-role markers' spawn chance
  (`chance × weight`, capped 1.0). The SEAM build wires
  `crew_faction` at every ENEMY-bearing caller —
  `game_interactions.begin_capture_boarding` (the boarded spec's
  faction) and the three `boarding_wrecks` paths (pirate; survey_a's
  raw ids bypass) — BEFORE any deck re-authors (omitted-role-skips
  would load crewless decks at intermediate commits); `landmark.py` /
  `city_landmarks.py` raw-id layouts unchanged (grep-verified caller
  list — seven src sites; the tools/ layout editor is a retired
  experiment per SETTLED 38's addition — not a consumer).
- **The Merchant row** (`data/npc_chars/core.py` + family): id
  `merchant`, name **"Merchant"** (SETTLED 38), char `h`, fg
  (100,220,140), faction merchant, band-exempt (all-zero
  `stat_weights`), fixed light weapons
  (`weapons=("kinetic_pistol", "combat_knife")`), hp 16, ap 4, small
  loot pool, xp ~12. `CHAR_CLASS_FAMILIES` gains the merchant family
  (letter `h`, faction recruiter); the cross-registry lint pin gains
  the `h` entry (ground Merchant vs space hauler — never
  co-rendered).
- **The droid dial on the spec** (`data/npc_ships/`):
  `security_drones: float = 1.0` on NpcShipSpec — merchant_caravan
  1.5, merchant_freighter 1.0, merchant_hauler 0.5 (tunable leans);
  every other spec leaves the default.
- **Always-hostile capture/derelict interiors** (SETTLED 3/38):
  `GameMap.hostile_interior: bool = False` (declared field);
  `begin_capture_boarding` + the `boarding_wrecks` paths stamp it at
  load; `faction.spec_is_hostile` gains an optional `game_map` param
  that returns True when the flag is set (the one uniform seam —
  ground read sites `_entity_in_player_sight`, `ground_npcs`,
  `city_npcs` pass their map); serialized in
  `saveload_maps._optional_map_fields`. Crew specs KEEP their faction
  tags — rep deltas land by crew faction through the existing tables
  (SETTLED 28).
- **Deck re-authoring** (7 layout files — the marker blocks only;
  every geometry-touching edit called out for USER REVIEW, SETTLED
  38): scout/cruiser/frigate_crew → pirate role tokens (one
  single-slot marker per big deck becomes `heavy`; the small scout
  deck stays brute-free); hauler/freightliner_crew → merchant tokens
  (crew `line` markers, droid `security_drone` markers, one
  `heavy`=assault_drone slot, parasites → `stowaway`); derelict
  scout_a/freightliner_a → pirate tokens (same specs resolve);
  survey_a's markers stay raw-pinned. Chances/sizes MAY be retuned
  per role inside the user-reviewed blocks — the one required retune:
  merchant `security_drone` base chances rise to 0.6-0.8 so the dial
  reads (×1.5 caps at 1.0, ×0.5 still spawns — reviewer-caught: at
  today's 0.25, "the caravan is dronier" is not reliably observable).
  Marker-letter `COLOUR:` overrides RETIRE — `_scatter_layout_enemies`
  renders the resolved spec's `fg` (single-sourced identity), and the
  stale directives leave the files (tile colors untouched). The
  MECHANISM recolors every ENEMY-marker layout, not just the seven:
  landmark drone decks (wolf_camp/mercury_vault/barnards_cache) drop
  their fallback red for machine bronze, and survey_a's consortium
  crew shifts to family navy — the same fix extended, playtest line
  added.

**Build order:** CREW_ROLES + resolution seam + crew_faction
wiring at all four boarding callers + always-hostile flag (pure
core, tests first — the wiring lands BEFORE any deck re-authors) →
the Merchant row + family + lint pin → deck re-authoring (markers +
COLOUR retirement, per-file commits) → dial field + dial-read
chances → full gate. (Reviewer-caught inversion: decks re-authored
before the wiring would load crewless — the phase-4 lesson again.)

**Binding rulings:** SETTLED 3, 5, 7, 10, 13, 18 (perched marksmen
via marker placement), 28, 38. One geometry serves every faction —
never fork a layout; the user reviews every grid edit; interiors
hostile in capture/derelict scope only; merchant defense is droids
across heavy/marksman/security_drone.

**Stop point:** no space Tier 0/1 (phases 7-8), no ancient machines
(9), no biome fauna or machine expansion (10 — a second droid row to
split marksman/security_drone is FUTURE authoring), no consortium
exposure beyond the table row + survey_a as-is (11), no prison
re-pins.

**Required tests:** CREW_ROLES integrity (every cell a live spec id;
militia omits stowaway; merchant fills all five); role resolution
per faction at load + raw-id passthrough; deck crew correctness
(militia deck crews troopers/marines/snipers at +50 rep AND fights —
the hostile_interior read; merchant deck crews Merchants + sentry
droids; pirate decks include a brute; derelicts unchanged);
hostile_interior round-trips save/load and stays OUT of
cities/landmarks; the dial scales security_drone chances (caravan >
freighter > hauler, pinned); Merchant row band-exempt + fixed
weapons + family lint green; crew renders family colors (no COLOUR
override — a boarded rifleman reads family rust); kill-rep deltas by
crew faction (militia crew kills move militia rep); existing
boarding/layout-compile/city suites updated.

**Playtest checkpoint:**

1. Board a militia cruiser (dev: force a patrol fight at +50
   militia rep): the deck fights on entry — troopers, marines, and a
   perched sniper holding a sightline; wiping the crew visibly costs
   militia rep.
2. Board each merchant hull: Merchants (green `h`, light pistols)
   plus droids — the caravan noticeably dronier than the hauler
   (dial), one armored assault droid anchoring the bigger decks.
3. Board a pirate cruiser/frigate: pirates including a brute; a
   scout decks out with no brute (small boat).
4. Derelict wrecks feel unchanged (pirate squatters + parasites);
   the survey wreck still fields consortium rows.
5. Identity: every boarded crew reads its family color (no more
   off-color riflemen); ground `h` Merchant vs space `h` hauler
   never share a screen.
6. Save/quit inside a deck → Continue: crew, hostility, and dial
   state identical.
7. Identity beyond the decks: landmark drone sites (wolf camp,
   mercury vault) read machine bronze, and the survey wreck's
   consortium crew reads family navy — the color-fix extended; on
   merchant decks, eyeball the green `h` Merchant against the green
   `>` exit tile (35 apart, different glyphs — identity holds, feel
   rules).
8. Regression: dig/dungeon/city spawns, phase-4 band scaling, and
   phase-5 tactics unchanged; space combat untouched.
9. Guide-diff item: expected NONE — boarding is documented flow and
   crews explain themselves in play; confirm-grep of the guide, any
   hit becomes a called-out before/after.


### Phase 7 Implementation brief (FINAL 2026-09-24 — SETTLED 39 +
### its same-day addition + 14/15/19/21/31/33; reviewer ADVISE pass
### folded, 14 issues; blockade band 2 ruled — ready for
### /implement-phase 48.7)

**Scope (files / hook points):**

- **Spec data** (`data/npc_ships/__init__.py` + `core.py`/`deep.py`):
  `band: int = 0` + `skill_weights: tuple[float, float, float]`
  (gunnery/piloting/engineering) on NpcShipSpec;
  `pilot_gunnery`/`pilot_piloting`/`pilot_engineering`/`min_power_gen`
  RETIRE (authoring one raises TypeError — the registry pin pattern);
  `ai_accuracy_bonus`/`ai_dodge_bonus` SURVIVE as the per-spec
  reconciliation dials. Band leans (playtest-tunable): pirate scout 1
  / hound 2 / raider 2 / marauder 3 / captain 3 / warlord 4; militia
  patrol_light 1 / patrol 2 / patrol_heavy 3; **blockade 2 (SETTLED
  39 addition: the harness re-pin tunes TOWARD harder, never softer
  — the Line is the brute-force skip; the frigate-hull re-author is
  the named escalation lever if the fight ever reads soft)**;
  merchant hauler 1 /
  freighter 2 / caravan 3 with piloting-LIGHT weights (cornered
  merchants stay non-threats — pin the passive-dodge delta in the
  checkpoint); derelicts 0; deep ships 2-4 per system danger.
  Skill-weight leans: interceptors piloting-biased, line
  gunnery-biased, flagship balanced.
- **Skill totals MOVE — the honest claim** (reviewer issue 1): band
  1 preserves today's QUALITY rates, NOT today's skill sums (authored
  totals 40-115 vs band totals 40/75/115/175; patrol_light matches
  band 1 exactly, warlord/blockade/caravan move most — and piloting
  dips are doubly visible: AP `(60+piloting)//20`, dodge half-rate).
  The tuning dial: a ships-only skill base inside `derive_skills`
  (lean: chosen so band-1 totals ≈ today's fixed-roster sums 40-45),
  pinned by test; playtest tunes from there.
- **Themed modules** (SETTLED 31; `data/modules/`): ONE new id —
  `smuggler_hold`, name "Smuggler's Hold" (PROSE GATE — the trait
  catalog already says "concealed as smuggler's hold"; stats lean
  cargo_bonus + speed_bonus). Pirates fly it (captain/warlord at
  minimum); merchants fly expanded_cargo + shield/recharger suites;
  militia military suites (largely today's lists — re-authored where
  the theme reads thin). No other new ids.
- **The ship resolver** (new `spacehack/space_scale.py`, pure —
  imports `ground_scale.BAND_LEVELS`/`band_budget`/`quality_rates`,
  never re-derives): `derive_skills(spec) -> tuple[int, int, int]`
  and `roll_flown_equipment(ids, band, rng)` (StoredEquipment
  instances at band quality rates — ONE fly-time roll helper for
  weapons AND modules; `_roll_flown_modules` retires into it). The
  largest-remainder allocator lifts into ONE shared helper consumed
  by BOTH ground's `derive_stats` and ships' `derive_skills` (no
  band math re-derived, allocation loop included).
- **`EnemyInstance` type changes** (`combat/_types.py` — declared at
  the owner): `weapons` becomes the rolled `StoredEquipment` tuple
  (content-type change — consumers migrated below);
  `weapon_ammo` re-keys by SLOT INDEX to twin the player (id keys
  collide on today's duplicate light_lasers); new `band: int = 0`
  (the LVL line reads it); new `shield_recharge_bonus: int = 0` (the
  free-regen field = hull base + module bonus at build — the
  player_state twin's own key name).
- **`_build_enemy`** (`combat/_stats.py`): shields = hull
  `base_shield_max` + module `max_shield_bonus` (quality-scaled);
  `shield_recharge_bonus` = hull `base_shield_recharge` + module
  `shield_recharge_bonus`; power_gen/max_power = hull
  `base_power_gen` + module `power_gen_bonus`; module
  `gunnery_bonus`/`piloting_bonus` summed onto the derived skills
  (the `_player_skill_bonuses` twin — targeting/gyro go live
  enemy-side); weapons roll via the resolver; ammo seeds per slot
  from real `ammo_capacity`. `shield_regen_rate` stays 0 (paid
  divert = Tier 1 decision, SETTLED 39).
- **Weapon-quality damage path** (`combat/_actions.py`
  `resolve_damage` — reviewer issue 3: space damage has NO
  weapon-quality term today; player space weapons are quality-0):
  gains a shooter-weapon-quality parameter — the PLAYER path passes
  0 (bit-identical behavior, test-pinned), enemy fire passes the
  flown instance's rolled quality. Without this the weapons-quality
  ruling is cosmetic.
- **Honest fire** (`combat/_ai.py` `_take_enemy_turn`/
  `_enemy_attack`, plus the plain-id consumers `_ei.weapons[0]`
  (`_ai.py:179`) and the target card's `for _wid in enemy.weapons`
  (`_space_presentation.py:42-49`) — both resolve through the
  instances): pay real `ap_cost` from ap_remaining, `power_cost`
  from power_pool, decrement `weapon_ammo`; weapons[0] unaffordable
  → walk the list in order, SKIP unaffordable entries (a 2-AP
  missile at 1 AP is skipped, not waited on), fire the first
  affordable. TERMINATION RULE (reviewer issue 6): no affordable
  weapon AND no legal step (in range, holding LOS) → the existing
  break ends the turn — never spin, never move-while-in-band.
- **Free-regen mirror** (`combat/_actions.py` `start_enemy_turn`):
  the free tier reads `shield_recharge_bonus`; the paid tier stays
  dormant.
- **Joiner fix** (`combat/_rules_space.py`
  `_build_reinforcement_enemy` — reviewer issue 9, narrower than the
  audit first read): the build already flows to `_build_enemy` with
  the JOINER's spec; the live defect is the spurious `return None`
  when the PLAYER's hull-catalog read fails (drops legitimate
  joiners; the player-hull/skill reads feed a discarded player
  state). Delete the player reads + the None path — one enemy
  construction path remains.
- **Weapon capture strip** (reviewer issue 4: `CombatResult` carries
  `boarded_modules` only today): `boarded_weapons` beside it
  (`combat/_types.py` + `_space_boarding.py`); the strip seeds
  weapon entries (`dungeon_layout.py` beside the module seeding) —
  what FLEW is what drops, weapons now quality-bearing.
- **The LVL line** (`combat/_space_presentation.py:38` title_row —
  the ground card's true twin; reviewer issue 7):
  `f"LVL {band_level(band)} {name}"`. NO hud.py edit at all.

**Build order:** spec fields + retirements + band/weight authoring
(registry tests first) → `space_scale.py` resolver + shared allocator
(pure, tests first) → `EnemyInstance` fields + `_build_enemy` rewrite
→ quality param in resolve_damage (player pinned 0) → honest fire +
fallback + consumer migration → free-regen term → joiner fix → LVL
card line → capture-strip extension → themed module id + loadout
re-author (+ `test_line_tuning` re-pin once the blockade band is
ruled) → full gate.

**Binding rulings:** SETTLED 14 (quality rides band, now ship-side),
15/19 (band-derived skills), 21 (Tier 0 = parity only; every
decision-loop behavior is Tier 1), 31 (ladders + themes), 33 (hull
identity — no glyph changes here), 39. No context banding anywhere;
band-1 quality = KILL rates (skill totals move — the honest-claim
line); no new spec stat fields beyond `band` + `skill_weights`.

**Stop point:** no Tier-1 decision loop — no fire-BEST-affordable
selection (the walk is degenerate), no regen-when-hurting divert, no
move-to-band changes, no aggressiveness dial; no ancient machines
(9), no consortium ships (11), no biome fauna (10); no guide entry
(honest costs are the player's own rules mirrored); no player-side
BEHAVIOR changes (the shared resolver's quality param defaults the
player path to today's numbers).

**Required tests:** registry TypeError pins (pilot_* / min_power_gen
gone); band assignments pinned (warlord 4, merchant wealth ladder,
derelicts 0; blockade band 2); derive_skills purity (budget
math, weight splits, the ships-base dial landing band-1 ≈ today's
fixed-roster sums, band 0 = base); fly-time rolls (weapons AND
modules at band quality rates — band 1 equals KILL rates; the
quit-mid-fight re-roll gap stands, economy-watched); `_build_enemy`
parity (hull shields/recharge/power honored; targeting/gyro bonuses
land; ammo seeded per slot — duplicate weapons keyed apart); honest
fire (AP/power/ammo spent per shot; the walk SKIPS unaffordable
entries; in-range-nothing-affordable breaks the turn);
resolve_damage (player path bit-identical at quality 0; enemy damage
scales with rolled quality); `start_enemy_turn` free regen includes
the hull base; the joiner never returns None on a player-catalog
failure; `boarded_weapons` round-trips into the strip; the LVL card
line; smuggler_hold in the catalog + pirate loadouts reference it;
**`tests/test_line_tuning.py` updated for the field retirement +
re-pinned per the blockade ruling (absent from v1 — reviewer issue
2)**; existing combat/navigation suites green.

**Playtest checkpoint:**

1. Sol pirate scout (band 1, dev grant): the fight reads like today
   — skills within a hair of live, "LVL 3 Pirate Scout" on the
   target card; shields tick each turn (scout hull base + module
   recharge).
2. Deep warlord (band 4, bold F): "LVL 30"; derived skills bite
   (dodge, AP); board it — the strip carries what flew, weapons
   quality-bearing (near-overclocked at band 4).
3. Missile-LED ship (dev grant variant whose weapons[0] is a
   missile): after its real missile count it steps to the next
   affordable weapon mid-fight — never inert, never infinite. (The
   captain leads heavy_laser — its missiles fire in power troughs,
   not after a count.)
4. Power honesty: an energy-heavy ship's output visibly thins when
   its pool drains (heavy laser costs 2/shot → it steps to the
   1-power light laser); pool refills at hull+module rate.
5. Joiner: fight beside a second squad and let it join mid-fight —
   with the player's ship in ANY state the joiner still joins (the
   None path is gone) and reads its own spec's stats.
6. Militia patrol_heavy: LVL 18, military suite — realer than
   today's flat skills, no pirate gear. The Line (blockade band 2):
   still EXTREMELY hard by design — full watch unwinnable below 30,
   a costly win at 30+, thin watch the mid-20s timing play; if the
   re-pinned fight reads SOFT in play, say so — the frigate-hull
   lever is the user's named escalation.
7. Merchant caravan: light (its wealth band, piloting-light weights
   — cornering one stays easy; PIN the passive-dodge delta vs
   today's ~7%), flees; droid dial unchanged; capture strip = cargo
   modules + light arms + (pirate decks) a Smuggler's Hold.
8. Regression: The Line pickets per item 6; bounty leaders,
   derelicts (band 0, amber), phase 4-6 ground, merchant chains
   unchanged; save/quit on the map → Continue identical.
9. Economy watch: quit-mid-fight → Continue re-rolls a band-4
   flagship's flown gear (save-scum avenue for near-overclocked
   weapons once stripping lands) — accepted ground-precedent gap;
   note anything absurd.
10. Guide-diff item: expected NONE — honest costs are the player's
   own rules; confirm-grep the SPACE-COMBAT and CAPTURE guide
   sections specifically (weapon stripping extends "what flew is
   what drops"), any hit becomes a called-out before/after.

Dev grants: Shift+P (SPACEHACK_DEV) spawns a chosen pirate spec
adjacent (cycles scout→warlord, incl. the missile-led variant for
item 3) (`dev_mode.py` + `test_dev_mode.py` pin).

### Phase 8 Implementation brief (FINAL 2026-09-24 — SETTLED 40 +
### 19/20/21/23/39; reviewer ADVISE pass folded, 10 issues; ready for
### /implement-phase 48.8)

**Scope (files / hook points):**

- **Volley selection** (`combat/_ai.py`): `_first_affordable_weapon`
  retires into a scorer — `score_weapon(weapon_spec, distance,
  target_shields) -> float`: normal weapons score damage ×
  hit-chance-at-distance ÷ ap_cost (the SAME `calc_hit_chance` the
  shot resolves with — band penalties fold in); shield-strip weapons
  score `min(shield_strip, target_shields) × hit chance ÷ ap_cost`
  (an EMP on bare shields scores 0, never picked). The turn loop
  becomes decision-point based, evaluated per spend of AP:
  1. no LOS or beyond `ai_preferred_range` → advance one step
     (existing);
  2. inside the ACTIVE weapon's min_range → back off one step;
  3. in band with LOS → the aggressiveness roll (RNG vs
     `ai_aggressiveness`, re-rolled each decision point): roll BELOW
     the dial → fire the top-scoring AFFORDABLE weapon; roll at/above
     → one reposition step inside the band (agg 85 fires ~85% of
     decision points — merchants at 10-15 rarely fire, SETTLED 23's
     no-re-authoring consequence). The volley composes greedily —
     fire top scorer, re-evaluate under the remaining AP/power/ammo —
     a thin pool reads as the low-draw set, a fat one dumps the rack
     (SETTLED 40).
  The ACTIVE weapon = the current top-scoring affordable entry; it
  governs the band (min_range for back-off, the [min…max] window for
  reposition steps). A weaponless spec (derelicts, the hauler) has no
  active weapon and no decision point 3 — it breaks at once.
  **Termination, restated for the new step semantics** (supersedes
  the Tier-0 "never move-while-in-band" line): with nothing
  affordable to fire, remaining AP goes to reposition steps while a
  legal in-band step exists (a power-dry ship dodges while it
  recharges); the turn breaks when no verb is legal — no affordable
  weapon, no positive score, no legal step.
- **Reposition-in-band** (`combat/_ai.py`): a step that stays within
  the active weapon's [min…max] band and keeps LOS; movement dodge
  accrues through the existing `cells_moved` economy (+5%/cell, cap
  30) — the SETTLED 23 dodge-tank. No step cap; authored values fire
  as-is.
- **Back-off** (`combat/_ai.py`): while distance < active weapon
  min_range, ONE greedy adjacent step — the walkable neighbor that
  most increases distance, LOS-keeping preferred — stopping at
  restoration (O(1) per step, the `_advance_one_step` single-step
  economics; NOT a nearest-cell search). Cornered (no step restores
  min_range — map edge, bodies): fall through to the fire branch and
  shoot through the min-penalty, today's blocked-advance behavior.
  The bound IS the dancer guard (SETTLED 40): back-off fires only
  below min_range and stops at restoration — no ship retreats beyond
  its own minimum engagement distance. Never triggers for min-1
  loadouts (all-laser ships, merchants included; verified live
  carriers of a min>1 weapon: raider + militia_patrol light_missile
  min 2; captain, patrol_heavy, marauder, warlord heavy_missile min
  3). **Authoring invariant (pinned by test):**
  `ai_preferred_range` ≥ the carried min-2+ weapon's min_range —
  advance and back-off share one axis; not violated by any live spec
  (closest: patrol_heavy/captain/warlord sit exactly at 3 = 3).
- **Regen divert data** (`data/npc_ships/__init__.py` +
  `core.py`/`deep.py`): `shield_regen_rate: int = 0` +
  `shield_regen_threshold: float = 0.5` on NpcShipSpec, stamped onto
  `EnemyInstance` at build (the rate field exists, pinned 0 since
  Tier 0; the threshold field is NEW — declared at the owner). No
  conflict with SETTLED 39's "no new spec field": that ruling covered
  the FREE tier (the rates are the hull/module data); the paid
  divert's two fields are the Tier-1 decision SETTLED 39 itself
  deferred. Authored leans BY SPEC ID (playtest-tunable; both knobs
  per spec): militia_blockade 2, militia_patrol_heavy 2,
  pirate_captain 3, pirate_warlord 3; every other spec leaves the
  defaults (rate 0 = no divert). `start_enemy_turn` gates the PAID
  tier on the threshold (divert only while shields < threshold ×
  max_shields; power availability already bounds it) — the FREE tier
  (hull base + module bonus) stays unconditional, the player's
  mirror.
- **Doc-34 notes 3/4: NO WORK** (SETTLED 40 — deferred, user-held
  trigger); note 2 is the playtest lens, note 1 closed by back-off's
  bound.

**Build order:** spec fields + authored rates/thresholds (registry
tests first) → the scorer + decision-point loop (retire
`_first_affordable_weapon`) → divert threshold gating in
`start_enemy_turn` → back-off + reposition-in-band + the
aggressiveness roll → `test_line_tuning` per the harness extension
ruling (SETTLED 40 addition) → full gate.

**Binding rulings:** SETTLED 19 (full-kit, resource-aware), 20 (no
fleeing — nothing here may disengage), 21 (Tier 0/Tier 1 boundary),
23 (aggressiveness semantics — regen NEVER touched by the dial; the
roll applies only in-band with LOS), 39 (honest costs stand), 40.
Authored `ai_aggressiveness`/`ai_preferred_range` values fire as-is —
no re-authoring. Player-side fire/Focus/costs are read-only mirrors —
zero player behavior changes.

**Stop point:** no coordination machinery (note 3 deferred), no
encounter-placement work (note 4 deferred), no ancient machines (9),
no consortium ships (11), no biome fauna (10), no new weapons or
loadout re-authoring beyond the divert rates, no guide entry (enemy
brains mirror the player's own rules).

**Required tests:** scorer purity (band-folded EV via
`calc_hit_chance`; EMP zero on bare shields, top on fat; ammo/AP/
power affordability filter); volley composition under budgets —
missiles-then-beams ordering, thin-power pool prefers the low-draw
set (deterministic under seeded RNG); aggressiveness roll (aggressive
spec fires ~every affordable AP; passive spec repositions — both
pinned at the roll extremes, direction correct); back-off (triggers
only below min_range, greedy neighbor step, stops at restoration,
never exceeds it; cornered falls through to fire; min-1 loadouts
never trigger); the authoring invariant (every spec's
`ai_preferred_range` ≥ its min-2+ weapon's min_range); reposition
steps stay in-band and accrue `cells_moved`; termination restated
(power-dry ship repositions leftover AP while a legal step exists;
breaks only when no verb is legal; weaponless specs break at once);
divert gating (below threshold fires with power spend + engineering
discount; at/above does not; free tier unconditional; threshold
default 0.5 + per-spec override); merchants/derelicts pinned (rate 0
→ no divert, never back off);
`tests/combat/test_enemy_fire.py`'s seven first-affordable walk pins
migrate to scorer pins (the import dies with the function);
`test_line_tuning` per the harness ruling below; existing combat/
navigation suites green.

**Line harness — SETTLED (SETTLED 40 addition, treatment a):** the
pickets never back off (light_laser ×2, min 1 — verified), so phase
8's Line effects are exactly the two terms the closed form does not
model: the aggressiveness roll (blockade 70 converts ~30% of
decision points to reposition steps, thinning the full-AP-volley
assumption of `_picket_volley`) and the threshold-gated paid divert
(blockade rate 2 raises effective regen below half shields;
`_picket_regen` models the free tier only). The harness EXTENDS with
both terms — `_picket_volley` × the aggro factor, `_picket_regen` +
the paid term below the threshold — and the fits re-pin from the
honest numbers, toward harder never softer (SETTLED 39). INTERIM by
design: `future/50_DESIGN_COMBAT_BALANCE_SIMULATOR.md` supersedes
closed-form pinning when it lands.

**Playtest checkpoint:**

1. Pirate captain (Shift+P cycle): opens with the missile volley,
   then settles into the heavy/light laser duel — target-card ammo
   visibly drains; no list-order artifacts.
2. Hug a missile carrier at dist 1 — a raider or militia patrol
   (light_missile min 2), or a captain/warlord (heavy_missile min 3):
   it backs off to its min_range and resumes fire — never retreats
   past the band; corner it against a body and it fires through the
   min-penalty instead.
3. Push a cruiser's shields below half: its fire visibly THINS (the
   divert — shields tick back up while its shots sparse out); let it
   climb above the threshold and the fire returns. The drain economy
   is the counter (note-2 lens).
4. Aggressiveness read: the hound (85, 6 AP) mixes reposition steps
   between shots — your hit chance drops as it moves; a brute-force
   ship (90 warlord) sits and fires every AP, eating your return
   fire.
5. Power trough: the warlord's plasma turns thin when its pool drains
   — it steps down to lasers, never inert.
6. The Line: still EXTREMELY hard. The pickets never back off
   (light lasers) — what changes is the ~30% reposition thinning
   (agg 70) and the below-half divert (rate 2); the harness treatment
   is the open ruling above. If the full watch reads SOFT from the
   thinning, say so — the frigate-hull lever stands (SETTLED 39).
7. Merchants: still non-threats — no divert, never back off, and now
   rarely fire (aggressiveness 10-15 live for the first time — the
   SETTLED 23 no-re-authoring consequence; they dodge-stack instead
   of shooting). Patrols scan unchanged.
8. Save/quit on the map mid-fight-adjacent state → Continue:
   identical state (combat never serializes — instances rebuild from
   specs per fight; the divert reads spec-authored fields, nothing
   new serializes).
9. Regression: phase 4-7 suites; the dev missile-led variant now
   scores its EMP-less rack properly; first-affordable is gone.
10. Guide-diff item: expected NONE — enemy decision-making mirrors
    the player's own rules; confirm-grep the SPACE-COMBAT guide
    section, any hit becomes a called-out before/after.

Dev grants: the phase-7 Shift+P cycle stands (items 1-2 targets); no
new grants.

## Pre-implementation audit — phase 3 (2026-09-22)

**Reuse (verified):**

- **The hull alphabet ships as data** (`data/ships/core.py`): skiff
  `t`, scout `s`, hauler `H`, cruiser `C`, frigate `F` purple,
  freighter `F` gold. `find_ship(spec.ship_id).char` is the lint's
  single source; no alphabet is authored.
- **NPC-ship Entity construction is SEVEN spec-driven sites** (the
  `Entity.bold` sweep): `_make_npc_entity` (`npc_ships.py:58`),
  derelict spawn (`npc_ships.py:245`), `make_static_entity`
  (`navigation_line.py:253`, shared by the Line pickets),
  bounty/quest leader+wings + salvage wreck (`navigation_spawns.py:93`
  and `:112`), and the two load rebuilders (`saveload_maps.py:420`
  bounty, `:457` procedural). Mid-fight joiners reuse the AMBIENT
  entity (`_join_reinforcements` attaches to `_found_entity`,
  `_rules_space.py:815` — no new Entity built); clones are SHEETS,
  not entities (`clone_transponder` rolls rep dicts). Seven sites,
  each with its spec in scope — `bold=spec.elite` rides beside
  `char=`/`fg=`.
- **The bold flag's render chain** (five seams, all defaulted so
  nothing else breaks): `WorldDrawCommand` (`world_render.py`) →
  `FrameCell`/`print`/`write_cell` + `commands` reconstruction
  (`framebuffer.py` — the `preserve_underlay` precedent) →
  `_paint_world_commands` (`pygame_runtime.py:44`) → `GlyphAtlas.blit`
  (`pygame_engine.py:327`). Two side doors carry it too:
  `_command_from_data` (`pygame_world.py:20`, dict+object normalizer)
  and `_map_console` (`pygame_combat.py:146`, combat's cell-by-cell
  copy — the field-enumeration path that historically drops fields).
- **The widen transform exists**: `_widen_glyph_tile` (engine.py:422,
  nearest-neighbour ink-bounds resize) reused at +1 column.
  `GlyphAtlas.from_processed_tileset` (`pygame_engine.py:288`) is the
  ONE atlas construction site (`PygameEngine.open` + two test
  callers) — the bold atlas builds there from the same processed
  tiles, so bold letters compose with the +3 text-spacing pass.
- **Registries expose the lint surface**: `list_npc_ships()` exists;
  npc_chars gets the symmetric `list_npc_chars()` sibling (its
  `_registry()` is private today).
- **The alias seam for the rename is `find_npc_char`** — saves persist
  `npc_char_id` verbatim (`saveload_maps.py:80,225`), so one
  id-alias resolution point covers old saves and any straggler
  reference.

**Duplication hotspots:**

1. **The seven-site bold sweep is parallel-paths drift by nature**
   (spawn stampers vs load rebuilders are twins: navigation_spawns ↔
   saveload_maps). A future eighth site that forgets `bold=` silently
   drops flagship rendering — no crash, no lint.
2. **The command chain repeats the field at five seams** — the
   combat copy path (`_map_console` → `write_cell`) enumerates fields
   by hand and is the one most likely to drop the new one.
3. **Family colors exist in two theaters** (ship faction colors live
   in each `NpcShipSpec.fg`; ground family colors live in
   `CHAR_CLASS_FAMILIES`). Pirate + militia span both; drift between
   the theater tables could quietly re-create the cold-blue crowding
   the separation rule exists to catch.

**DRY strategy:**

1. `Entity.bold: bool = False` (defaulted) + the lint's elite render
   test (flagship specs → `bold=True` on their world command through
   the REAL draw path) — a forgotten site fails the gate, not the
   playtest.
2. `bold` threads the chain exactly as `preserve_underlay` does
   today: one defaulted keyword, stored on `FrameCell`, reconstructed
   in `commands`, passed through the normalizer and the combat copy.
3. ONE ground table (`CHAR_CLASS_FAMILIES`: letter + case + color);
   ships keep NO family table (SETTLED 33) — the lint derives ship
   family colors from the data itself (all specs of a faction share
   exactly one fg; neutral keeps its amber/brass pair). The
   separation rule runs per theater over each table — cross-theater
   pairs (ground rust vs derelict amber) never share a spawn context,
   matching SETTLED 32's per-context uniqueness.

**Build-discovered decisions (called out for the playtest):**

- **Ground militia family color = teal (130,230,220), same as
  space.** The trooper's live (120,200,255) sits max-channel 40 from
  consortium's corporate blue — exactly the cold-blue crowding the
  separation rule exists to catch; the family doctrine (one color per
  family, SETTLED 32/34) resolves to the established militia teal.
- **Machine bronze leans (200,180,110), not (200,170,110).** The
  brief's stated pair — pirate rust (220,120,80) vs bronze
  (200,170,110) — is max-channel 50 apart, failing the brief's own
  ≥ 60 constant. The +10 green-channel nudge (imperceptible against
  the live assault-drone bronze) satisfies the stated rule at the
  stated constant; the rule and constant are the durable parts, the
  tuple a playtest-tunable lean.
- **Ship-side family color pin**: the brief's lint names only the
  hull-pin for ships; without a one-fg-per-faction assertion the
  "class twins render identical" intent (SETTLED 31/33) is unpinned
  data drift. The lint adds it as part of the SHIP rule — faction
  grouping off the spec data, no `SHIP_CLASS_FAMILIES` table (D1
  stays superseded).

## Pre-implementation audit — phase 4 (2026-09-22)

**Reuse (verified):**

- **`_build_enemy_instance` (`combat/_rules_ground.py:174`) is the ONE
  combat-entry resolution point** (init + refresh_engaged mid-fight
  joins): weapon pick, quality roll, and stat reads all funnel there.
  The resolver lands once, inside it; wound persistence (`entity.hp`)
  and the guard-post stamp already work per-entity.
- **`_scatter_squad` (`dungeon_population.py:48`) is the shared ground
  factory** for dig population AND authored-layout ENEMY markers;
  city ambient, prison activation, and the save-load path are the
  three local constructions — six stamping surfaces total (below).
- **`load_layout(...)` keyword seam** (`dungeon_layout.py:626`) reaches
  every authored interior: capture decks, derelict/mission wrecks
  (game_interactions ×4), dig + quest landmarks (landmark.py), city
  interiors (city_landmarks.py). Callers hold the parent context.
- **The player math anchors the budget**: 5 pts/level, cap 60
  (`xp.py:27-30`), base 10 (`character.py:34,39`) — SETTLED 35's
  budgets are that system read at levels 3/10/18/30.
- **Quality needs no new mechanism**: `roll_quality(rates, rng)`
  already takes an arbitrary ladder; the band table is a new ladder
  whose band-1 row EQUALS `KILL_QUALITY_RATES` — unstamped sites and
  legacy saves read exactly today's rates.
- **The dig floor-climb formula covers the prison with no special
  case**: activation security stamps `min(4, mission_tier + floor − 1)`
  — Mars T1 → band = floor, the same math digs use.
- **The weapons registry auto-discovers family modules** (`WARES`);
  the family→tier table derives from the catalog filtered on
  `loot_droppable=True` (fists + organic parts excluded by the
  existing doc-47.1 flag — no new exclusion list).
- Ground stat reads are exactly THREE sites (`_rules_ground.py:378`,
  `_ground_deadshot.py:109`, `_ai_ground.py:176,182`); the AI's
  `enemy_spec` param carries name+stats mixed — stats move to the
  instance (`GroundEnemyInstance.stats`), the name stays on spec.
- `Entity.bold` + the whole render chain shipped in phase 3; ground
  wearers only set `spec.elite` at the construction sites. Bold is
  NOT serialized — the ground load path restores it from the spec
  (as the ship rebuilders already do).

**Duplication hotspots:**

1. **Band stamping across six spawn surfaces + the load path**
   (digs populate / authored decks+derelicts / landmarks+city
   interiors / city ambient / prison activation / saveload) — a
   forgotten site silently spawns base-stat enemies: no crash, no
   lint.
2. **The floor-climb formula** exists in `digs._dig_tier` and would
   be re-derived by the legacy-context fallback — a twin by
   construction.
3. **Straggler reads of the retiring fields**: `reflexes` /
   `strength` / `stamina` / `weapon_pick` have consumers in combat
   rules, AI, deadshot, and tests; leaving any read behind compiles
   fine and silently reads nothing.

**DRY strategy:**

1. `ground_scale.py` owns every band question: `band_budget`,
   `derive_stats`, `roll_weapon`, `quality_rates`, and
   `entity_band(entity, game_map)` — the legacy-context fallback
   reuses `digs.parse_cache_key` + the same climb formula (lazy
   import; the `from .dungeon_extensions import _farthest_free_cell`
   precedent) rather than re-deriving it.
2. The retiring fields leave the DATACLASS (a straggler read raises
   AttributeError at once, not silently) + a grep test pins zero
   `weapon_pick`/spec-stat reads; the resolution is dataclass-field
   cohesion, not runtime attachment.
3. `roll_weapon` is the only tier-window implementation;
   `data/ground_weapons` owns `family_tiers()` beside the catalog.

**Build-discovered decisions (called out for the playtest):**

- **The brief's "quest-guard ensure" consumer is ship-side**
  (`main_quest/_spawns.py` builds `npc_ship_id` entities) — nothing
  ground-side to wire; ship banding is phase 7. Noted, dropped.
- **Landmark/city-interior ENEMY markers stamp the parent planet
  tier at their `load_layout` call sites** — the brief named capture
  decks, but the same loader serves mercury_vault-class quest
  landmarks and dig landmarks; one keyword threads all of them.
- **Band 0 semantics**: base-10 stats, B1 quality. The bystander
  exemption is DATA — all-zero `stat_weights` (scale-invariant), so
  cities may stamp uniformly. Unstamped legacy saves fall back to
  `entity_band` (dig keys re-derive the floor band; anything else
  reads band 1 ≈ today's numbers).
- **Prison security bands = the dig formula** (band = floor, cap 4):
  F1 ≈ today (sentries ~equal; the F1 assault drone's strength reads
  below today's flat 25), F3+ hotter. Phase 9 re-pins these machines
  wholesale; exact numbers on the playtest checklist.
- **The new militia faces have no ambient consumer until phase 6** —
  a SPACEHACK_DEV Shift+grant (marine + sniper + brute adjacent to
  the player) makes checkpoint item 4 checkable (dev-mode precedent).
- **T4 dig support rows**: `TIER_EQUIPMENT_POOLS` gains band 4;
  `legendary_axes_weights` gains a 4th row (the ladder's
  continuation, (5, 25, 70)); `_MONSTER_TIERS` gains (2.2, 34) —
  all three would IndexError/KeyError today at tier 4.
- **Ratchet headroom**: `game_interactions.py` (998) and
  `_rules_ground.py` (993) sit at the module ceiling — the band
  threading must land line-neutral or with a small same-commit
  extraction.

## Pre-implementation audit — phase 5 (2026-09-22)

**Reuse (verified):**

- **`consume_shot` is the ONE per-accepted-player-shot seam**
  (`combat/_rules_ground.py:578`): both fire paths call it
  (`_finish_player_weapon` for normal shots, `_fire_explosive_weapon`
  directly). The firing-report emission rides it at `ctx.player.pos`
  with the slot's weapon — melee included (it flows through the same
  [f] action), so the authored melee noise 1-2 is the quiet dial. The
  blast emission rides `explosive_blast` (`:473`) whose impact cell is
  `primary.pos` — ONE site covers `_apply_explosive_enemy_hit` (it
  runs per-enemy INSIDE `explosive_blast`; emitting there would
  multi-fire). Enemy-side report at `_try_ground_fire`
  (`combat/_ai_ground.py:108`).
- **The last-seen machinery is the attractor slot**
  (`ground_npcs.py:204-282`): `last_seen_pos` repurposed as the
  investigation goal (SETTLED 37), `last_seen_ticks` retires; the
  goal-walker replaces `_move_toward_last_seen` (give-up = unreachable
  or LOS-on-goal — never a tick countdown). `remember_last_seen` stays
  the single stamper for BOTH sources (disengage via `on_disengage`,
  noise via the new emit).
- **`faction.spec_is_hostile` folds `always_hostile`** (`faction.py:128`)
  — the ONE hostility predicate already shared by encounter, ground
  NPCs, and city NPCs; the hearer filter reuses it. City bystanders
  carry `npc_char_id` (`city_npcs.py:69`, verified) — they flow through
  `move_ground_npcs` between rounds exactly as the brief assumes.
- **`world.find_path` walkability is tile-only** (`is_walkable` reads
  `tiles[y][x].walkable`; DOOR/DUNGEON_DOOR author `walkable=True`,
  no runtime state gate found in `world_path.py`) — the door-path test
  pins the audit flag CLOSED with a fixture, no fix expected.
- **The resolver owns weapon identity**: `ground_scale.roll_weapon` +
  `entity_band` resolve the rolled weapon idempotently at FIRST
  resolution — `_build_enemy_instance` (combat entry) and the guard
  hearing gate call the same helper; the stamp lands on the entity.
- **`_build_enemy_instance` (`:177`) is the single combat-entry point**
  for weapon persist + consumable pre-roll + AP derivation;
  `reset_turn` (`:972`) is the per-round tick site for stim/regen.
  Consumable catalog: med_pack (use_ap_cost 1, heal 5, regen 2,
  duration 3), stim (use_ap_cost 1, AP +1, duration 3) — names match
  the approved log lines verbatim ("Med Pack" / "Combat Stim").
- **`ActiveConsumableEffect` / `effect_from_spec`**
  (`ground_consumables.py`) shape the enemy-side mirror — heal 5 +
  regen 2×3 and +1 AP ×3 are exactly the catalog values.
- **Save path**: `_entity_to_dict`/`_entity_from_dict`
  (`saveload_maps.py:70,246`) — carried stamp, rolled weapon, and goal
  serialize beside the existing `last_seen_pos`. `guard_post` is an
  UNDECLARED runtime attribute today (grandfathered) — declaring it on
  `Entity` while paying the cohesion debt is in-scope.
- **Dev-grant pattern**: `spawn_dev_enemy_faces` (`dev_mode.py`) —
  Shift+key, `test_dev_mode.py` pin; the carrier grant follows it.

**Duplication hotspots:**

1. **The hostile-combatant check is about to become a THIRD twin**
   (`_encounter._is_hostile_combatant`, `ground_npcs._is_hostile`, and
   an inline hearer filter) — plus the stepwise-stop predicate would
   duplicate `_visible_hostile_entities`' per-entity logic.
2. **Weapon/quality resolution**: `_build_enemy_instance` rolls today;
   the guard leash gate needs the SAME rolled weapon — an inline
   re-roll would fork the resolver and double-draw RNG.
3. **Three emission sites** (player report, enemy report, blast)
   hand-assembling (origin, radius) pairs + the reaction line; and the
   movement pass would re-derive AP/step semantics per caller.

**DRY strategy:**

1. `noise.py` owns `emit(...)` (the only emitter constructor — origin,
   radius, blast flag — reaction line inside), the hearer scan
   (reusing `spec_is_hostile` via `_encounter`'s single predicate), and
   the per-entity stepwise-stop helper that `_encounter` exposes and
   `ground_npcs` consumes (mode + stop predicate imported, not
   re-derived).
2. ONE `ensure_rolled_weapon(entity, game_map, rng)` in `noise.py`
   (lazy `ground_scale` import) — the idempotent first-resolution
   stamp both consumers call; quality stamps beside it.
3. Combat-time movement is ONE mode branch inside `move_ground_npcs`
   (per-entity AP walk with the shared stop predicate); callers
   (`check_reinforcements`, explore tick, debug session) inherit
   unchanged.

**Build-discovered decisions (called out for the playtest):**

- **Weapon quality persists beside the weapon** (same first-resolution
  stamp) — otherwise a persisted weapon could drop at a different
  quality than it fired with, breaking doc-47.2 SETTLED 13's
  "what fired is what drops".
- **Enemy explosives have NO blast resolution today** (single-target
  `_roll_ground_shot`) — enemy-side emission is the firing report
  only; there is no enemy blast site to wire (player-side
  `explosive_blast` is the only blast emitter, and it is one site).
- **Reaction-line quiet gate**: melee/organic noise ≤ 2 never logs the
  line even when an adjacent fresh hearer exists — SETTLED 36 verbatim
  ("quiet weapons never trigger it"), a named tunable constant.
- **Guard post re-stamps where the investigation ends** (playtest item
  4: "settles at a new perch near the sound, then guards THERE") —
  keeps the combat leash coherent with the new perch.
- **Stationary behaviors hold during fights unless investigating**: a
  guard without a goal does NOT pace at AP during a live fight (it
  holds its post; playtest item 4's "does NOT come"), hunters and
  bystanders move — the uniform reading of SETTLED 17's "every
  un-engaged entity" against SETTLED 18's area-guardian doctrine.
- **`last_seen_ticks` retirement is load-compatible**: old saves
  carrying the field load clean (ticks ignored, a live goal restored
  by position alone); the pursuit give-up becomes unreachable/LOS.

**Ratchet plan:** `_rules_ground.py` sits at 999/1000 — the player
consumable-effect pass (`apply_consumable_effect` +
`_advance_consumable_effects` + `_consumable_name_for_effect`, ~60
lines) extracts to a new `combat/_ground_effects.py`, which is also
the natural home for the enemy-side effect mirror (stim/regen tick);
the emission wirings inside `_rules_ground` stay line-neutral against
that extraction, paying the debt in-commit per the brief.

## Pre-implementation audit — phase 6 (2026-09-23)

**Reuse (verified):**

- **The marker pipeline is ONE seam and stays value-agnostic**:
  `layout_format._parse_enemy` treats a role token exactly like a raw
  spec id (`enemy_spawn_specs[glyph] = (id, chance, min, max)` — no
  parser change needed); `_scatter_layout_enemies`
  (`dungeon_layout.py:243`) is the single resolution + scatter site.
  Role resolution, the drone dial, and the fg single-sourcing all land
  inside it; `load_layout` → `_populate_build` → scatter threads two
  new kwargs (`crew_faction: str = ""`, `security_drones: float =
  1.0`) exactly as `spawn_band` already threads (phase-4 precedent).
- **Four ENEMY-bearing boarding callers hold their spec** (verified
  by grep): `begin_capture_boarding` (`game_interactions.py:657` —
  the boarded spec's faction + dial), `_build_generic_derelict`
  (scout_a), the mission-salvage branch, and `_build_main_quest_wreck`
  (`boarding_wrecks.py:51,78,115` — pirate; survey_a's raw ids
  bypass). `landmark.py`/`city_landmarks.py` are raw-id callers —
  the only other ENEMY directives in data/ are the three landmark
  drone decks (wolf_camp/mercury_vault/barnards_cache, raw
  `sentry_drone@1.0`, NO marker COLOUR lines — they render the
  scatter seam's hardcoded fallback red today, so the fg
  single-sourcing recolors them bronze with zero landmark edits).
- **The hostility seam is shared by exactly five ground read sites**:
  `faction.spec_is_hostile` (`faction.py:128`) feeds
  `_encounter._is_hostile_combatant` (via `_entity_in_player_sight`,
  game_map in scope at the caller), `ground_npcs._is_hostile` /
  `steps_aside`, `city_npcs.is_hostile`, `noise._hears` (game_map
  already a param), and `autoexplore.steps_aside_ids`. An optional
  `game_map` param threads all five; every caller has its map in
  scope (verified: `swap_step`, `move_ground_npcs`/`_move_solo`,
  `_resolve_city_bump` via `state.game_map`, `_hears`, the
  steps_aside loop).
- **Map-field serialization is table-driven**:
  `GameMap.hostile_interior` declares beside `derelict_interior`
  (`world.py:429`); `_optional_map_fields` (`saveload_maps.py:154`)
  and `_apply_dungeon_attributes` (`:407`) are the two single-function
  touch points.
- **The Merchant row is a pure data row**: NpcCharSpec +
  `CHAR_CLASS_FAMILIES["merchant"]` recruits by `faction="merchant"`
  (the phase-3 family machinery needs zero code); the lint pin
  `CROSS_REGISTRY_PIN` gains `"h"` (space hauler `h` —
  merchant_hauler flies it; never co-rendered with the ground row).
- **The dial is one spec field**: `NpcShipSpec.security_drones:
  float = 1.0` beside `capture_layout_id`
  (`data/npc_ships/__init__.py:125`) — `begin_capture_boarding`
  already reads the boarded spec there.

**Duplication hotspots:**

1. Role resolution inlined at more than one site (scatter loop +
   any future consumer) would fork the token vocabulary.
2. The two new kwargs thread through three layers (load_layout →
   _populate_build → scatter) — a shortcut (module-global set by
   callers) would be parallel-paths drift.
3. The five hostility sites could each read
   `game_map.hostile_interior` directly — that forks the override
   across five files and mints a sixth reader later.

**DRY strategy:**

1. `data/npc_chars/crew_roles.py` owns `CREW_ROLES` +
   `CREW_ROLE_TOKENS` (the vocabulary set) — one frozen table, one
   source; `_scatter_layout_enemies` imports both; no other module
   resolves roles. Raw ids pass through unchanged; an omitted role
   skips its markers; a role token with no faction table raises
   ValueError (caught by the boarding callers' existing except →
   "breaks away" — the authoring-error surface).
2. Kwargs thread exactly as `spawn_band` does (three layers,
   defaulted); the boarding callers pass
   `crew_faction=spec.faction`-equivalents inline.
3. `spec_is_hostile(ctx, spec, game_map=None)` returns True when the
   flag is set; all five sites pass their map; no site reads the
   flag directly.

**Ratchet headroom:** every touched module sits ≤ 869 of 1000 lines
(dungeon_layout 669, game_interactions 869, boarding_wrecks 177,
faction 477, world 750, saveload_maps 810, ground_npcs 578,
city_npcs 443, noise 194, autoexplore 813, _encounter 371) — no
same-commit extraction is forced this phase; keep additions small.

**Build-discovered decisions (called out for the playtest):**

- **Marker-letter reuse keeps every grid edit OUT of this phase's
  re-authoring**: each deck's existing letters re-point their ENEMY
  directives to role tokens (marker letters are geometry keys, not
  render glyphs). The only directive-level retunes beyond the token
  swap: cruiser `z` and frigate `g` (the single-slot #1-1 markers)
  become `heavy`; hauler/freightliner `h` becomes `heavy`
  (assault_drone); merchant `q` chances 0.25 → 0.7 (the required
  dial-read retune). NO map-grid lines change in any of the seven
  files — the SETTLED 38 grid-edit review applies to the marker
  BLOCKS, and the playtest checklist says so.
- **Sniper counts ride the marksman markers unchanged**: cruiser/frigate
  marksman markers keep today's squad sizes (up to 2-4 per marker) —
  pirate riflemen and militia snipers share the geometry (one geometry
  serves every faction, SETTLED 28); militia sniper count tuning is a
  playtest knob (chances/sizes, user-reviewed).
- **Survey_a keeps raw ids but loses its dead marker COLOUR lines**
  (c/g/m) — the mechanism single-sources its consortium crew to
  family navy and the parasite to its spec mauve; leaving stale
  directives would be exactly the retirement this phase performs.

## Pre-implementation audit — phase 7 (2026-09-24)

**Reuse (verified):**

- **The band machinery ships**: `ground_scale.py` owns `BAND_LEVELS`
  (3/10/18/30), `band_budget` (5×(L−1)), `quality_rates(band)`, and
  `band_level` — the ship resolver imports them; one band vocabulary,
  both theaters, no local level table.
- **`start_enemy_turn`** (`combat/_actions.py:486`) ALREADY mirrors
  both regen tiers — the paid divert verbatim plus the quality-scaled
  module free tier. Only the build side keeps it inert
  (`shield_regen_rate` never set, no hull-base free term). Tier 0 is
  a build-side change plus one free-tier term.
- **`_roll_flown_modules`** (`combat/_stats.py:221`) is the fly-time
  quality precedent — weapons take the same roll into
  `StoredEquipment`; the 47.3 capture strip already handles that
  type, and combat math already multiplies damage by quality.
- **The player formulas are the spec**: `_player_free_regen`,
  `_player_skill_bonuses`, `_calc_max_shields` (`_stats.py`) are
  exactly what the enemy twin reads — hull base + module bonus at
  quality. `_calc_hull_for_enemy` already honors hull + modules (the
  one wired half today).
- **`EnemyInstance`** (`combat/_types.py`) carries the resource
  fields Tier 0 needs — `power_gen`/`max_power`/`shield_regen_rate`/
  `weapon_ammo`/`modules` — but NOT with zero type changes (v1's
  claim, corrected per the reviewer): `weapons` changes content type
  (ids → rolled StoredEquipment), `weapon_ammo` re-keys by slot
  (id keys collide on duplicate light_lasers), and two fields are
  NEW — `band` (the LVL line) and `shield_recharge_bonus` (the
  free-regen term; `start_enemy_turn` recomputes only the module
  bonus today, so the hull base has nowhere to live without it). All
  declared at the owner (dataclass cohesion).
- **The joiner defect is ONE function, and NARROWER than first
  read** (`_rules_space._build_reinforcement_enemy`): the build
  already flows to `_build_enemy` with the JOINER's spec — the
  player-hull read and the 30-default skill clone feed a DISCARDED
  player state; the live bug is the spurious `return None` when the
  player-catalog read fails, silently dropping legitimate joiners.
  Deleting the player reads + the None path completes it.
- **The LVL seam**: the space TARGET CARD title row
  (`_space_presentation.py:38`, the `_ground_presentation.py:62`
  twin) — no hud.py involvement at all.

**Duplication hotspots:**

1. Weapon vs module fly-time rolls hand-rolled separately would fork
   the quality path (rates, RNG draw order, capture strip).
2. `_build_enemy` vs `_player_combat_values` drifting into
   copy-paste twins (shields/power/regen/skill-bonus formulas).
3. A second band-derivation implementation (ship skills vs ground
   stats) drifting from `BAND_LEVELS`/`band_budget`.

**DRY strategy:**

1. ONE `roll_flown_equipment(ids, band, rng)` in `space_scale.py` —
   modules and weapons both; `_roll_flown_modules` retires into it.
2. The shared formulas lift to module level in `_stats.py`
   (hull+module regen, shield, power, skill-bonus helpers) consumed
   by BOTH the player and enemy paths — the mirror is one
   implementation read twice.
3. A second band-derivation implementation (ship skills vs ground
   stats) drifting from `BAND_LEVELS`/`band_budget` — INCLUDING the
   largest-remainder allocation loop itself (`derive_stats`'s
   splitter): lift it into one shared helper both resolvers call.

**Ratchet note:** no hud.py edit remains (the LVL line lives in the
target card); `_rules_space.py` (870) has headroom for the joiner
fix; every other touched module ≤ 900.

**Build-discovered decisions (called out for the playtest):**

- **THE MOVED BRACKET (the Line):** the parity numbers make the
  band-2 picket ~70% hotter than the doc-41 tuning (derived gunnery
  44 vs 15 — the targeting computer now counts; cruiser hull shields
  25 + free regen 3/turn; AP 4). Under the closed form the old
  level-30 knife-edge fit loses the full watch ~5x; the re-pinned
  harness derives FIT_25/29 honestly and gives the costly win to
  FIT_SUPER — the max sheet the ruling itself names ("a brute force
  skip... for a super powered player"). If the watch reads too hard
  in play, that is a user ruling, not a lever — the named
  frigate-hull escalation only goes harder. Parity pins: g44/p32/e22,
  EHP 125, regen 3 (`test_line_tuning.py`).
- **AP now reads the folded piloting** (uniform with the player):
  the hound derives piloting 34 + gyro 10 + dial 28 = 72 → 6 AP
  (today 4). The interceptor got FAST. Playtest-tunable via the
  dials/weights; flagged because it is the largest single live-delta
  outside the Line.
- **Merchant weights are engineering-heavy** (0.20/0.10/0.70): the
  brief's "piloting-light" could have spiked caravan gunnery to ~59
  on a 45% share; the engineering split keeps merchants non-threats
  and reads wealth in the reactor (engineering feeds max_power).
  Passive-dodge delta pinned: caravan 10 vs today's 7.
- **The unknown-hull fallback is now zero, not 100** (modules-only
  stats): unreachable on real data (all 15 specs resolve their
  hulls) — a data error degrades instead of granting a free
  frigate-grade hull.
- **The dev missile-led variant registers at grant time**
  (SPACEHACK_DEV-gated `dev_missile_captain`): the encounter system
  is id-resolved, so a variant spec row is the only way it rides the
  ONE spawn path; the identity lint excludes the `dev_` namespace
  from production-exactness pins.
- **The ships-only skill base is 11** (band-1 three-skill total 43,
  inside today's authored 40-45): band totals read 43/78/118/178 —
  band-3 cruisers/captains land ABOVE their old authored sums (the
  honest-claim line); playtest tunes via the one constant.

## Pre-implementation audit — phase 8 (2026-09-24)

**Reuse (verified):**

- **The Tier-0 loop skeleton is the whole foundation** (`_take_enemy_turn`,
  `combat/_ai.py:77`): the while-per-AP shape, cached-path advance,
  blocked-step break, LOS firing gate, and cost payment
  (`_pay_fire_costs`, `weapon_costs`) all stand — phase 8 replaces the
  weapon PICK (`_first_affordable_weapon` → the scorer) and adds two
  step verbs around the fire branch. `_advance_one_step`'s move
  application (pos, cells_moved, AP, entity sync, render frame)
  extracts into the ONE shared step helper all three verbs call.
- **`calc_hit_chance` (`_stats.py:160`) is the scorer's hit term
  verbatim** — the SAME function the shot resolves with
  (`_resolve_enemy_shot` → `calc_hit_chance`), so min/max band penalties
  fold into the EV with zero new math. Clamped 5-95, so a normal weapon
  always scores > 0; the only zero-score case is strip-on-bare-shields
  (`min(strip, 0) = 0`) — exactly SETTLED 40's EMP rule.
- **`start_enemy_turn` (`_actions.py:509`) already contains the paid
  divert verbatim** (power spend, engineering discount, proportional
  bounding) — Tier 8 adds ONE gate line: the paid tier fires only while
  `shields < shield_regen_threshold × max_shields`. The free tier
  (hull base + module bonus, folded at build) stays unconditional.
- **`EnemyInstance.shield_regen_rate` exists** (`_types.py:66`, pinned
  0 since Tier 0) — only `shield_regen_threshold: float = 0.5` is NEW
  (declared at BOTH owners: NpcShipSpec + EnemyInstance, stamped in
  `_build_enemy`, the one enemy construction path — joiner and dev
  grant flow through it).
- **Authored aggressiveness/preferred-range values are complete**:
  `ai_aggressiveness` has ZERO live consumers today (dead since
  authoring — phase 8 is its first read); `ai_preferred_range` has
  exactly one (`_ai.py:94`). No re-authoring (SETTLED 23/40).
- **The strip weapon exists for tests**: `emp_missile` (strip 20,
  damage 0, min 2 / max 10, ap 2 — `data/weapons/missiles.py:30`);
  no live loadout carries it, matching SETTLED 40's future-proofing.
- **The Line harness functions are parameter-local**:
  `_picket_volley` / `_picket_regen` are pure spec-readers — the aggro
  factor (×0.70; agg 70) and the paid divert term (+2 below half
  shields, power-sustained: ~2.8 laser power + 1 divert = 3.8 vs the
  flown build's net gen 4 — cruiser 5 base minus armor plating 1)
  extend them in place; the parity pin test names both terms.

**Duplication hotspots:**

1. Three step verbs (advance / back-off / reposition) each hand-rolling
   the move application (pos write, cells_moved, AP spend, entity sync,
   render frame) — the classic parallel-paths drift.
2. The affordability filter existing twice: `_select_fire_weapon`'s
   scan and any back-off/band logic re-deriving "what can this ship
   still fire".
3. The volley selection re-implemented in the Line harness
   (`_picket_volley` walks weapons by list order — the phase-8 loop
   walks them by score; the harness must mirror the LOOP's semantics,
   not grow its own).

**DRY strategy:**

1. ONE `_apply_step` helper (the extraction of `_advance_one_step`'s
   tail) consumed by all three verbs; each verb only chooses the
   destination cell.
2. ONE `_select_fire_weapon(_ei, distance, ..., affordable_only=)`
   — the scorer scan with an affordability switch; the band reference
   for a power-dry ship is the SAME call with the switch off (top
   scorer ignoring cost — the weapon it wants, so the dance happens in
   the band it will fight from when power returns). No second picker.
3. The harness's volley term derives from the same numbers the loop
   uses (agg factor = the spec's dial / 100 applied to the full-AP
   volley; the divert term = spec rate below the spec threshold) —
   constants read off the spec, never re-derived locally.

**Build-time decisions (called out; within the brief's bounds):**

- **`score_weapon` signature concretized**: the brief's
  `(weapon_spec, distance, target_shields)` omits the inputs its own
  parenthetical requires — the same `calc_hit_chance` the shot
  resolves with needs gunnery + target dodge. Real signature:
  `score_weapon(ws, distance, target_shields, gunnery, target_dodge)`.
  Damage is the CATALOG damage (brief formula verbatim — flown quality
  is not folded into ranking; it multiplies the resolved shot, not the
  choice); duplicate weapons tie-break first-slot.
- **The reposition destination** (legality is specified; preference is
  not): best-scoring legal in-band LOS-keeping step, tie → first scan
  order — no directional artifact, the skirmisher drifts toward its
  ideal firing distance while dodge-stacking. Back-off destination per
  the brief: the distance-maximizing neighbor, LOS-keeping preferred.
- **Decision 1's blocked step breaks the turn** (existing cover rule,
  pinned by `test_blocked_enemy_without_los_never_fires`); a ship at
  dist beyond `ai_preferred_range` with a blocked path but weapon-LOS
  still fires (today's behavior — preserved by "in band" meaning the
  ACTIVE weapon's [min…max], and pref ≤ every live weapon's max).
- **Weaponless specs break at once BY CONSTRUCTION**: no weapons → no
  scorer pick → no band → no legal step → the termination clause fires.
  No special case for derelicts/the hauler.
- **Authoring invariant holds today** (verified across all 15 specs):
  every min-2+ weapon carrier has pref ≥ that min (raider/patrol 4 ≥ 2;
  captain/patrol_heavy/marauder/warlord 3 = 3); min-1-only loadouts
  (blockade, hound, scouts, merchants) never trigger back-off.

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
