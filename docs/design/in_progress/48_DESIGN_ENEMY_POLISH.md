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
- [ ] 7. **Space Tier 0: parity** — hull-catalog stats (base
  shields/recharge/power), module effects wired + honest costs,
  per-weapon AP/power/ammo, authored shield-regen rates, joiner
  spec verification, themed modules (smuggler/cargo holds —
  capturable), and the SHIP-SIDE band/loadout rolling (SETTLED 31's
  "pairs differ by band/loadout" — resolution lives here with the
  loadouts).
- [ ] 8. **Space Tier 1: the decision loop** — fire/regen/move per
  AP, `ai_aggressiveness` as fire-vs-reposition, weapon selection
  (EMP/conservation), the four ported doc-34 design notes
  (SETTLED 19/21/23).
- [ ] 9. **Ancient machines** — Watcher / Custodian / Warden, their
  weapon family, the Custodian's multi-weapon loadout, prison
  re-pin (+ the rock_scavenger prison-floor pin), dormant override
  for alien sites (SETTLED 29).
- [ ] 10. **Biome expansion + apexes** — LUSH/VOLCANIC/SCRAP_RING/
  CANYON fauna + band-aware pools; one apex per biome guarding
  delve-bottom legendaries (SETTLED 30). Names in the brief. At its
  close: the extensibility audit (acceptance criterion — adding an
  enemy is a data edit) against the whole campaign.
- [ ] 11. **Consortium content + the hunt** — cybernetic ground
  rungs, the two hunter ships (one frigate hull), the main-quest
  hunt reskinned as a new enemy class (with the `_heat.py`
  hired-pirate docstring cleanup), strictly-gated exposure; ADDS
  the up-movers + site/loot/hunt movers over v1's landed down-
  movers (SETTLED 6/9/12/19). Depends on 2, 7-8.

Order rationale: mechanics before identity (lint needs final
factions); scaling before tactics; crews carry their own rows;
parity before brains; the hunt last (needs its body and its foes).
Reviewer ADVISE 2026-09-22 folded in: phase split (old 2 → 2+3),
blocking fixes in the v2 brief, punch-list owners assigned,
merchant-crew row moved to its consumer, ship-band rolling homed at
Tier 0, placements homed at crews, ledger 6-7 struck.

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
