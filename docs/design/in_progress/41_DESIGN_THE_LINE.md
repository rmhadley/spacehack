# DESIGN: The Line — the Blockade as a System

**Status: DESIGN IN PROGRESS — no implementation until the user
explicitly requests it.** Second of doc 39's four feature docs,
forked in the agreed order (transponder → the Line → lore/rumor →
far side).

Companions: `39_DESIGN_ACT1_BLOCKADE.md` (the act + its five
methods); `../complete/40_DESIGN_TRANSPONDER_ID.md` (the identity layer the
Line reads); `future/37_DESIGN_POST_ACT0_CAMPAIGN.md` (roadmap).

## The ruling this doc serves (user, 2026-09-06)

> Design it right — rock solid. Maybe future acts reuse the tech.
> The Line is a SYSTEM, not a menu: patrol patterns, a scan
> checkpoint, convoy-free traffic, signatures. Methods are ways
> THROUGH the system, discovered by research, enabled by
> preparation, executed and tested.

## What exists today (tested, doc 39)

Four static militia_blockade cruisers (60 hull, heavy laser +
light missiles, one shared squad) at x=150, y=25/55/85/115, detect
7 — a wall with gaps (y 33-47, 63-77, 93-107 + both map edges).
Warning-only comms. The restricted-sector marker east of the wall.
No crossing logic anywhere.

## First-pass shape (for review)

**The sensor line.** The wall becomes edge-to-edge detection —
the Line's defining property, and a PER-LAYER one (settled
2026-09-09; amended in the reviewer round): the BROADCAST SWEEP —
a virtual sensor column at x≈150; any hull crossing it with a
live/spoofed transponder is swept, because transponders read at
range — is edge-to-edge, with no free geometric gaps. PHYSICAL
SPOTTING — dark hulls never broadcast, so only a patrol within
its detect radius sees them — is patrolled coverage whose gaps
are real by design; the ghost run's gate is kit + timing/lure
skill, not impossibility. Detection triggers THE hail: identify
yourself. Every crossing resolution flows through one checkpoint
encounter with one rules table:

| The sweep reads | Result |
|---|---|
| Manifest trait (papers) | Waved through, logged |
| Militia ID at blockade rank+ (impersonation) | Waved through, logged AS that ID (rank read off the worn sheet — doc 40) |
| Dark hull (no broadcast) | Never swept — but patrols that physically spot it challenge; the ghost run lives here |
| Valid service-run listing (the bribe) | Waved through as cargo/contractor — a consumed `blockade_service_run` trait, 100k per crossing |
| Anything else — INCLUDING allied/liked stance with no papers | Turn back — or the whole Line converges (method 5). The sweep hails ALL unpapered hulls; the doc-40 statics stand-down is superseded inside the column |

**One combat response, everywhere.** Dark players ignoring the
challenge, unplanned runners, fight-seekers — all arrive at the
same convergence: the picket squad + system patrols, tuned to the
30-floor contract (provably unwinnable below 30, significant at
it). No per-method variants.

**The manifest registry** is data: the checkpoint reads one trait
(`blockade_manifest`) + the transponder state (doc 40). The Line
itself knows nothing about HOW you got legitimate — the methods
stay decoupled from the wall.

**Reusability.** The checkpoint (read → resolve → converge) is a
pattern: future acts' quarantines, customs lines, faction
checkpoints all reuse it. The Line is the first instance, not a
one-off.

## Settled — the Line's system mechanics (refine session, 2026-09-09)

All five review-agenda questions ruled, plus three the agenda had
not named. The first-pass shape above stands as amended.

1. **Detection is two-layer.** The BROADCAST SWEEP is a virtual
   sensor column at x≈150: any hull crossing it with a live or
   spoofed transponder is swept — identity reads at range;
   transponders broadcast. Ship spacing stops mattering; the
   geometric gaps close by construction. Dark hulls never
   broadcast, so the sweep cannot see them: only a patrol within
   its detect radius physically spots them (today's detect 7) →
   the challenge hail. **Amendment (reviewer round, 2026-09-09):
   per-layer coverage.** Edge-to-edge belongs to the sweep alone.
   The dark layer's geometric gaps are real by design — the ghost
   run's gate is kit + timing/lure skill (doc 39's closed
   hail-lure), and phase 2's rotations own sweeping the corridors
   with waypoints so dark passage is timed, never free-feeling.
2. **Full shift rotations.** Line traffic runs on a real schedule:
   ships rotate in/out on a clock — spawn/despawn shifts,
   maintenance windows. The maintenance-window fiction is
   MECHANICS: a thin watch the dark run can time. The schedule is
   also what doc 42's rumor system can later sell. (The heaviest
   of the offered scopes — chosen deliberately.)
3. **One hail shape everywhere.** Every detection — sweep-hit or
   dark physical spot — triggers the same two-option checkpoint
   hail: Comply (= turn back) / Defy (= the whole Line converges).
   No third inspection option. Asking/talking stays free via the
   existing comms panel; the checkpoint itself is binary.
   **Amendment (reviewer round, 2026-09-09): column-scoped.** The
   shipped doc-40 dark-spot challenge (``_dark_spot_challenge`` —
   fires for ANY militia patrol anywhere; Identify/Attack, ESC =
   open fire) is superseded INSIDE the column only: a dark hull
   physically spotted by the Line opens the same Comply/Defy
   checkpoint. Outside the column the doc-40 challenge stands
   untouched (Sol keeps it as shipped).
4. **Static Line v1.** No alert levels, no incident heat —
   convergence is the response and resets after. The checkpoint
   pattern documents an alert-field extension point (the
   reusability ruling) but does not wire one. Sol's charged-cell
   heat stays the precedent if a later act wants escalation.
5. **Crossing is positional + symmetric.** You fly through; no
   arrival ceremony, no teleport for checkpoint crossings (the
   hidden gate keeps its own far-east arrival ruling). Return
   crossings resolve through the same table. The Line stops
   engaging once you're past the column; the restricted sector's
   content and behavior are doc 43's territory.
6. **The sweep reads IDENTITY ONLY** — transponder state, the
   manifest trait, the service-run trait, the worn sheet's rank.
   Never cargo. Cargo stays the militia-scan system's business
   (smuggler's hold, confiscation modals live there). Note the
   consequence for the scrub: a scrubbed ID holds no rank,
   manifest, or service-run — at the column it reads "anything
   else" and turns back. The scrub stays what it is everywhere
   else (neutral-rate patrol scans); doc 39's tramp-hauler combo
   described a cargo-reading checkpoint that this ruling
   deliberately does not build.
7. **The bribe's marker is a consumed trait.** Paying the
   Commandant grants `blockade_service_run` (registered like
   `blockade_manifest`, outside milestone picks); the sweep
   consumes it — one crossing per 100k, per doc 39. The
   Commandant's ledger stays fiction (doc 39's wording): the trait
   is the token. Consume is SYMMETRIC — a return crossing consumes
   again (follows from ruling 5). Grant-side content (Commandant
   NPC, rumor chain) is method 4's, not the Line's; the sweep only
   reads.
8. **The sweep hails ALL unpapered hulls — allied stance
   included.** The Line trusts manifests, not attitude: doc 40
   phase 4's statics stand-down is superseded inside the sensor
   column (at the Line only — everywhere else the stand-down
   stands). Allied standing buys the SIGNATURE cheaply, not a
   free pass; doc 39's method 1 stays the gate.

## Settled — phase 2: the watch (refine session, 2026-09-09)

Six rulings (round 1: shift length, garrison size, displacement,
presentation; round 2: cadence, rosters, handover; round 3: the
relief leg). The watchbill is cycling DATA on the SensorColumn —
every number below is retunable after the playtest.

1. **7-day shifts (user)**: "You fly out and spend a week on the
   blockcade, then rotate out with your replacement shift."
   Tenure = ``(total_days - 1) // 7`` — a pure function of the day
   clock (no new mutable schedule state; save/load stays free).
   Boundaries land on days 8, 15, 22, … **AMENDED (playtest
   round 3, 2026-09-10 — see below): 30-day shifts.**
2. **Every 4th shift is the maintenance watch** — the cycle runs
   full/full/full/thin (28 days). The thin watch is the minimum:
   today's shipped four stations (user: "4 should probably be the
   minimum"), whose wide gaps are the ghost window by design.
3. **The full watch closes the current gaps with ships, not
   sensors** (user: "we need more than what we have right now to
   close current gaps"). Ten pickets at spacing 14 = detect 7 × 2:
   y = 7, 21, 35, 49, 63, 77, 91, 105, 119, 133 — edge-to-edge
   physical coverage with zero slack (luring opens a real hole).
   Luyten c (150,95–96) checked clear. detect stays 7.
4. **Rotations FLY** (user: "fly in/out is definitely the right
   choice … the only extra bit we're adding is once they get to the
   blockcade line they park for x days until they fly back to the
   blockcade station to land"). The journey rides the merchant
   machinery (spawn → A* → arrive): relief launches at its base,
   flies to its station, PARKS for the shift, then flies back to
   the blockade station and lands. Wordless: no boundary log line —
   the schedule is observable by watching (UI text economy).
5. **Reliefs launch from the blockade stations, EARLY** — each
   station's data carries a launch lead (days before the boundary)
   so relief arrives ≈ shift end; the outgoing picket departs at
   shift end REGARDLESS (user chose this over waiting for relief):
   a boundary's coverage dip lasts until relief lands on station.
   Ship-speed slop is accepted — slow ships see late reliefs and
   longer dips; fast ships see relief loitering on station ahead of
   its tenure (early arrivals park and hold their station).
   Northern reliefs transit 80+ tiles (≈ 10 days at speed 10), so
   leads are per-station data, initially ≈ measured transit, tuned
   in playtest.
6. **Displaced pickets serve until destroyed** (user) — relief
   takes only ships AT their stations. A lured picket is never
   despawned or flown home mid-lure; a displaced picket of an ended
   tenure stays where it is (killable, spotting) until destroyed.
   The dark loop survives shift boundaries.

Mechanical consequences (binding):

- **Tenure keys.** Rotation spawns stamp ``static_spawn_key`` with
  a MONOTONIC tenure suffix — ``sys:enemy_id:x:y:t<k>`` — so the
  phase-1 tombstones do their job per tenure: killed this tenure,
  dark for the tenure; re-manned next tenure (the fight method's
  re-manning, per station). The ledger format is unchanged.
  ``total_days`` is a pure derivation from the wrapping clock
  triple: ``year*360 + (month-1)*30 + day`` (reviewer round).
- **Legacy migration.** A pre-phase-2 save's unqualified picket
  tombstones are re-stamped ONCE at load with the current tenure's
  key — killed stays dead through the current tenure, re-mans at
  the next boundary. No silent resurrection of phase-1 kills.
  SCOPE (reviewer round): Luyten picket keys only — column systems
  × their ``picket_enemy_id``; ross_154 / lalande_21185 also ship
  unqualified static kill keys and are never touched. Rewritten at
  the top of ``load_game`` so both consumers (the ctx ledger
  restore and the raw-dict map rebuild) see the same keys.
- **Everything derivable (reviewer round).** A picket's role is a
  function of THREE readable facts — tenure vs current, at its OWN
  station (the x:y embedded in its key, not any roster station;
  arrival = path exhausted / within a cell — exact equality
  misreads a picket slipped aside off an occupied station), and a
  live flight target in the existing path dicts: parked = tenure ≥
  current, at own station, no target; flying in = tenure ≥ current
  (or not yet current — loitering), has target; flying home =
  tenure < current AND has target (the target is what
  discriminates a departing picket from a displaced one — a
  displaced picket is never GIVEN a target, so it stays put);
  displaced = tenure < current, no target, not at station. No new
  Entity fields, no new globals, no persisted schedule state.
- **Murdered reliefs stay dead** for the tenure: a launch is
  skipped when its tenure key is already tombstoned — killing a
  relief costs a squad fight and buys one station-tenure of
  darkness on that station.
- **The sweep counts every alive picket** — parked or in flight —
  as shipped; a relief wave keeps the column swept from launch.
- **Squad combat semantics untouched** — phase 2 changes only who
  stands where, when. The full-watch garrison (10 full / 4 thin) is
  phase 3's convergence-payload input, not this phase's problem.
- **Statics rebuild from the watchbill at EVERY map build AND at
  load** (reviewer round — the load path rebuilds the map from
  system data + tombstones; entities do not round-trip
  individually). Build-side reconciliation: overdue reliefs (launch
  day passed, key not tombstoned) stamp at their bases. So: parked
  pickets restore exactly; in-flight state is session-scoped and
  re-launches on schedule; a displaced picket snaps back to its row
  on jump away/back or load — shipped phase-1 static behavior,
  making "serve until destroyed" SESSION-SCOPED. The full and thin
  rosters are disjoint, so every full↔thin boundary rotates the
  entire line (14 flights), and with leads 9–10 > shift 7, two
  relief waves are routinely airborne at once — both tolerated by
  construction.
- **Line traffic is silent and invisible to move_npcs** (reviewer
  round): watch flights carry NO ``procedural_squad_id`` (never
  enter ``_squad_groups``/patrol), launch and home-despawn log
  NOTHING (the merchant paths' "Sensor ping"/"docks at" lines would
  telegraph the schedule — wordless ruling), and the stepper skips
  ``combat_locked`` pickets.
- **Moving pickets keep one hail key** (reviewer round):
  ``_entity_hail_key``'s position fallback assumes statics never
  move — a flying picket would get a fresh key every step and the
  positional re-arm would re-open the dark-spot challenge every
  step. ``_entity_hail_key`` prefers the stamped
  ``static_spawn_key`` when present (watch pickets always carry
  one; procedural NPCs are untouched).

## Phases

Build queue — unchecked in order; `/implement-phase 41.<p>` works
top-down. Grant-side method content (the Commandant, the Whisper
barkeep, the heist, the gate tech) is NOT the Line's: the sweep
only reads markers.

### Phase 1 — The sweep (the sensor line + the checkpoint)
- [x] Sensor-column spec in the blockade data (data-first)
- [x] Pure sweep resolver + tests (the rules table; identity reads)
- [x] Crossing-edge tripwire wired into the per-step pass
- [x] The checkpoint hail: Comply / Defy (Defy sets the LINE-scoped
      interdiction flag — ``_gate_engages`` reads it like
      charged-cell aggro: local, stance-independent, resets on
      leaving the system; no rep writes. Minimal teeth; full
      convergence is phase 3)
- [x] Dark path: sweep skip + physical spotting → the checkpoint
      hail (the doc-40 challenge superseded INSIDE the column
      only)
- [x] Service-run trait consumed at the wave
- [x] Guide: UPDATE the comms section (the Line's hail replaces its
      option-matrix row) and Identity & Transponder; a new Line
      section only if the checkpoint needs discoverable controls

LANDED 2026-09-09 — **PLAYTEST PASSED** (user, same day; two fix
rounds inside the phase: reviewer blockers + playtest-round-1/2
bugs and rulings, all recorded below). Reviewer round (REQUEST_CHANGES
→ fixed): (1) the doc-39 warning-only comms are SUPERSEDED in column
systems — ``_spec_distance_hail``'s militia_blockade branch returns
None when the system owns a ``sensor_column``; the checkpoint is the
Line's only hail, waved hulls included (elsewhere the warning stands,
and player-initiated comms with a picket are untouched). (2) The
interdiction flag's real teeth are WIDER than first audited: the
radius floor rides the same aggro flag, so a defiance engages ALL
Luyten militia (pickets + the 4–5 patrols) at detect ≥30 for the
rest of the stay — charged-cell precedent, phase 3's convergence
preview. The defiance is SESSION-LOCAL: save/quit/Continue drops it
(an escape hatch pending phase 3, which owns the permanent response
and the persist-or-not call). (3) A hailed step OWNS the step: the
detection loop and the NPC-drift tail are skipped that step (a
Comply freezes NPCs one step; a Defy-VICTORY does not chain further
detection until the next step). (4) The crossing tracker fully
resets on every jump (``reset_session`` beside the system swap) so a
stale side can never read as a crossing — future column systems and
the hidden-gate materialization covered. (5) Dev-hook deviation from
the brief's text: the marker traits are NOT auto-granted at new game
— the checklist's first three items need an unpapered crossing —
they arrive via SPACEHACK_DEV Shift+L (manifest) and Shift+K
(service run), one paper per key so the sweep's precedence
(manifest outranks rank and service) never blocks a checklist step
(the rank-eligible militia face still files at new game; wear it
with TAB). Playtest-order consequence: the rank wave (item 7) and
the service consume (item 5) must be demoed BEFORE the manifest is
granted (item 4) — the manifest outranks them and, having no
consumption path, would mask both.

### Playtest round 1 (2026-09-09) — mechanics PASS, presentation +
one save/load bug fixed

Items 1–5, 7, 8 exercised (6/9/10 unremarked); the only bug: **a
defeated blockade resurrected on load** — statics re-stamped from
``system.enemies`` on every map build. Fix: a persisted tombstone
ledger ``ctx.defeated_static_spawns`` (keys ``sys:enemy_id:x:y`` —
statics never move) — written in the kill chain
(``_space_kills.mark_static_spawn_defeated``, beside the quest-guard
tombstone), honored at every map build (``make_solar_system``'s
``skip_static_spawns``, threaded from jump/launch/load), serialized
both ways. Consequence: after the squad dies, crossings still
challenge (the Line is the system, not just its ships) and Defy
raises the flag with NO combat payload — the flag's patrols carry
it until phase 3's convergence.

Presentation rulings (user wording VERBATIM; "targetting"→
"targeting" and "You're ID"→"Your ID" fixed as typos):

1. **Naming ban**: "the Line" is an INTERNAL concept — never
   player-facing. Player-facing copy says "the blockade" /
   "forbidden space"; the column's comms label is "Militia
   Blockade". Binds all phase 2/3 copy and SYSTEMS.md wording.
2. **Every sweep resolution is a comms modal addressed to the
   hull's broadcast ID** ("Unidentified hull" when dark); all
   message templates are column data with an ``{id}`` placeholder:
   - challenge (Comply/Defy): "{id}, this is forbidden space.
     You're not on our list, turn back now or else."
   - manifest wave: "{id}, this is forbidden space. Your ID checks
     out, continue through."
   - rank wave: "{id}, this is forbidden space. Oh, sorry. Didn't
     recognize your ID, sir. Continue through."
   - service wave: "{id}, this is forbidden space. Your ID checks
     out, this time. Continue through." — Acknowledge (or ESC)
     consumes the contract.
3. Waves open ONE option (Acknowledge; ESC counts) and return
   ``(False, None)`` — GO TO CONTINUES through a wave (the hull is
   through); only the challenge breaks auto-nav. Post-modal logs
   stay terse: "The blockade waves you through." (+ "The
   service-run contract is spent.").
4. Convergence line: "The blockade's targeting lasers focus on
   you!" (was "The Line converges on you!"). Comply: "You turn
   back from the blockade."

### Playtest round 2 (2026-09-09) — two rulings + the retest list

1. **Turn-back re-hail (user bug #1)**: the first-pass rule counted
   every edge transit as a crossing, so complying and stepping off
   the column re-hailed the retreat. Fixed statelessly: the sweep
   fires on ENTERING the column (``new_x == column.x`` and
   ``prev_x != column.x``), from either side; leaving is always
   free. Every west↔east traversal still steps onto the column, so
   coverage stays edge-to-edge.
2. **The sweep is MANNED (user, round 2)**: fighting through and
   winning must end the broadcast line — fight is doc 39's fifth
   method, and an eternal sweep would make it unable to ever open
   the Line. With no picket alive the column is dark: no hail, no
   waves, no defiance (supersedes round 1's "crossings still
   challenge" consequence and its empty-payload Defy branch). The
   hole is temporary by construction: phase 2's rotations re-man
   the column on the next shift.
3. **Comply-and-run confirmed deferred** (user asked): a hull that
   answers Comply and keeps east draws no aggro in phase 1 — the
   audit's pinned phase-1 hole; phase 3's convergence closes it
   (the Comply latch converting to Defy on the eastward exit is
   the named mechanic for the phase-3 brief). Also clarified for
   the user: proximity aggro against a broadcasting hull requires
   a disliked/enemy sheet or the flag — every dev-loadout stance
   reads neutral-or-better, so pickets stand down by design.
4. **Dark-spot challenges are POSITIONAL (user's final round-2
   bug)**: the doc-40 one-shot-per-patrol-per-visit rule let a
   complying hull blind the whole line picket by picket — comply
   once per B and no picket ever challenged again. The challenge
   now stays answered only while the dark hull remains in that
   patrol's detect range; leaving re-arms it (``dark:``-namespaced
   keys in ``militia_scanned``, so the scan-hail paths keep their
   one-shot-per-visit semantics). Applies in and out of the
   column; the out-of-column challenge's Identify/Attack
   semantics are unchanged — only its engagement lifecycle is
   positional.

### Playtest round 3 (2026-09-10) — 30-day shifts

**"Now we have to tweak the rotation schedule. it's all happening
too fast so we have constant rotating shifts."** (user; "Let's try
30 day shifts.") With 7-day shifts and 2-9-day transits each way,
a picket's standing time was at most a week against a comparable
commute — barely settling before the boundary packed it home, and
the north leads (9 ≥ 7) kept a second wave permanently airborne.
`shift_days` 7 → **30** (data; the cycle stays tenure-indexed, so
the thin watch is now a 30-day window every 120 days — flag for
the playtest: a long ghost season). Structural consequence: with
every lead < shift, two same-roster relief waves can NEVER overlap
— one wave airborne at most; the "two waves routinely airborne"
consequence above is superseded, and the same-station base
stacking case no longer exists (its test is retired with a note).
The commute:watch ratio inverts to ≤9 commuting vs 30 standing.

### Playtest round 4 (2026-09-10) — watch right-of-way

**User report:** reliefs "fighting over their place as they fly
out — a tight group that almost seems like there are B's just
rotating around a central B." Stepping the autosave exposed three
defects (all reproduced via debug_session; ADVISE-reviewed before
building):

- **(A) Launch jostle** — same-base reliefs stamp on ONE dock
  cell and share one corridor; same-rate independent flights
  mutually block and slip into an orbit (the south base piled up
  SEVEN heal-launched reliefs, ships drifting 5 cells off-course).
- **(B) Sticky off-station parking — the DEFAULT, not an edge
  case**: per-step credit 0.9 < 1 means every flight stops at the
  first cell within Chebyshev 1 of its target, so EVERY flown-in
  picket parks one cell off-station for its whole tenure — and
  ``_trigger_static_spawns`` reads exact row positions, so a
  flown-in line is invisible to the interdiction trigger (0 of 14
  rows alive, measured). Supersedes the phase-2 audit's "trigger
  pass unchanged" claim (it held only for build-stamped watches).
- **(C) Permanent blocker deadlock** — a flight whose next cell
  holds a parked hull retries that cell forever (kept-path idiom),
  slipping back and forth; observed (150,92)<->(149,93) for 30+
  passes with credit pinned at 1.0. Slip-and-retry cannot pass a
  stationary obstacle; only the watch makes month-long stands on
  other flights' corridors.

**The fix (three mechanisms, watch-side only; ADVISE-amended):**
(1) **Launch spacing** via one shared ``dock_spacing_cells(base)``
helper (deterministic dock/+2E/+4E by roster index per base) used
by ALL THREE sites — build-side muster, runtime launch, and the
order gate (a spaced relief must still take orders after load);
(2) **station re-centering** as a DIRECT one-cell step in the
per-step scan (never a flight target — the within-a-cell arrival
check would self-cancel it): a targetless picket of tenure >=
current, Chebyshev 1 from its OWN station, exact cell free, steps
onto it. Amends the "parked pickets never move" pin for this case
only — the HOLD survives (it stays at its post); displaced
(ended-tenure) pickets are untouched, preserving that ruling;
(3) **blocked flights re-route** ONLY past effectively-parked
blockers (no live target or combat_locked) — head-on movers pass
under the current idiom (verified: 23 passes, zero recomputes)
and each A* costs ~16ms; a failed recompute KEEPS the flight on
its old path (unreachable-drop stays assign-time only — a dropped
home-bound flight is exactly the stray class this round removes).
Consequence to note: a +4-spaced north relief's real transit is
one day shorter than its lead (corner-cut) — early arrivals park
and hold by ruling; the self-verifying lead pin still measures
from the dock.

**Residual risk (user's intuition, confirmed by the ADVISE round):
this class could trigger very rarely OUTSIDE watch traffic** —
human-piloted ships would give each other space. Verified
self-healing today: squads re-target on arrival (short path
lifetimes), merchants despawn at goals, derelicts are avoided at
A*-time. The one live exposure: Luyten patrols cross the packed
column on fixed ~75-cell paths and could transiently stall. If
ever observed, generalize mechanism 3's parked-blocker re-route
into the movement kernel — not before (no general wedge
demonstrated; the kernel's determinism pins stay untouched).
REVIEW note (round 4's code pass): a fully sealed corridor makes
each blocked flight pay one failed A* (~16ms) per pass until the
seal clears — collision-triggered and rare (a seal needs a
complete wall; goal cells are occupancy-exempt); if it ever
surfaces, bound it by skipping the recompute while the path head
is unchanged since the last failure.

Guide ruling (user, round-1 follow-up): **the guide carries nothing
about the Line at all.** The checkpoint explains itself in play —
the hail IS the teacher — so guide coverage telegraphs an encounter
arc, which the guide contract bans. The brief's "Guide: UPDATE…"
step is superseded; both phase-1 guide additions were removed and
the guide's transponder sections stand as doc 40 shipped them.

Reviewer round 2 (REQUEST_CHANGES → fixed): the tombstone's
position match was UNSOUND — combat moves hulls (AI advance), so a
moved kill never matched its spawn row and the bug survived every
real fight. Fix: the spawn key is STAMPED ON THE ENTITY at map
build (``world.Entity.static_spawn_key``, declared on the type) and
the kill side reads it; ``_picket_payload`` uses the same key
identity, so a lured-but-alive picket is in the payload at its LIVE
position (position matching had also let the empty-squad branch
fire for a merely displaced squad). Wave steps now fall through
normally in BOTH movement-pass consumers (the wave's ``(False,
None)`` was being flattened into hail-owns-the-step in
``game_flow``); the challenge modal's hint says "ESC defy" again;
the guide no longer says "the Line" player-facing; the data test
formats every template (stray-brace guard) and the load path's
ledger threading is pinned.

### Phase 2 — The watch (shift rotations)
- [x] Watchbill data on the SensorColumn: ``shift_days``, the
      full/full/full/thin cycle, and the full/thin rosters as
      ``(y, lead_days, base_id)`` station tuples; 10 new
      ``EnemySpawn`` rows for the full-watch stations in
      ``system.enemies`` (the shipped 4 stay — they are the thin
      roster) (data-first)
- [x] Pure watchbill helpers + tests: tenure / shift kind / roster
      from the clock; per-station launch day
- [x] Map build spawns the CURRENT watchbill as parked, tenure-keyed
      pickets (tombstones honored); off-duty stations never spawn
- [x] The per-step watch pass: reliefs launch early at their base,
      fly in and park; outgoing pickets depart at shift end and fly
      home to land; displaced pickets are never moved; murdered
      reliefs stay dead for the tenure; launches and home-despawns
      are SILENT and watch flights stay out of move_npcs
- [x] ``_entity_hail_key`` prefers the stamped ``static_spawn_key``
      when present — a flying picket keeps one hail key (the
      positional re-arm must not re-open the challenge per step)
- [x] ``_picket_payload`` (manned sweep + Defy payload) reads all
      alive pickets by id — parked, in flight, displaced
- [x] Legacy tombstone migration at load (one-time re-stamp to the
      current tenure key)
- [x] Dev hook: advance the clock to the next shift boundary
      (Shift+key) — Shift+D's +30 days is too coarse to time a
      window
- [x] Guide + playtest: guide diff is NONE (round-1 ruling — the
      guide carries nothing about the Line); playtest observes a
      rotation, times the maintenance month, crosses dark through
      one, and lures across a boundary

**PLAYTEST PASSED** (user, 2026-09-10): "working fantastic now.
clean paths. shifts. holes appearing for dark mode. . waits a day.
this feels good." Four fix rounds inside the phase: round 1
(presentation + the tombstone ledger), round 2 (entry-only
crossing, the manned sweep, positional dark-spot challenges),
round 3 (30-day shifts), round 4 (watch right-of-way: convoy
spacing, on-row re-centering, re-route past parked hulls — plus
the doc-44 sidequest underneath: own-speed movement, day-granular
waits, self-verifying leads). PHASE 2 CLOSED — phase 3 (the
convergence) is next; its brief is unwritten and its rulings
unsettled (/refine-design 41).

LANDED 2026-09-09 (all eight build steps; the playtest was parked
behind `../complete/44_SIDEQUEST_NPC_WORLD_SPEED.md` — now LANDED
AND CLOSED, so this checklist is LIVE on its movement math; round
3's 30-day shifts came out of this run). Checklist below stands
as written). Three reviewer dispatches (steps 1, 2, 4-5, 6-7):
every verdict addressed in-commit; the step-4-5 dispatch ran a
six-start-date × 400-step stress sim over the flight invariants
(zero violations: no double-launch, no orphaned target/path pairs).
**Mid-playtest ruling (user, 2026-09-10): a SPACE-wait passes a
full day** — pressing ``.`` moved NPCs (and watch flights) while
the clock stood still, decoupling flight progress from schedule
days ("this can really break the blockade line mechanics"). Fix:
``_handle_wait_event`` advances the clock 1 day after the per-step
passes (movement ordering kept — passes on the old day, flip
after; a BOARDED wait is a fight, no day). Dungeon and city waits
tick their NPCs but not the clock (unchanged). Consequence to
watch in the playtest: waits advance DAYS at day-granularity while
flights still step per-press — waiting across a boundary makes
reliefs visibly late (they fly ~1 cell per wait). **SUPERSEDED by
doc 44's settled ruling 4 (2026-09-10): a wait pays every mover a
full day of movement with carry-over — the asymmetry this note
flagged is doc 44's phase 3, and this playtest (parked behind 44)
runs under that math.**
Deviations + surprises recorded in the phase-2 audit's judgment
calls (epoch anchor; accepted one-time legacy re-hail) and one
observable worth knowing for the playtest: **on run-day 1 the
column also shows reliefs MUSTERING at the two blockade stations**
— every relief whose launch day predates the game's first day
stamps at its base at the first build and flies in over the coming
days, so a day-1 arrival sees the ten-picket line PLUS ships
loitering at the bases. In-fiction: the next shift mustering.
**(Post-sidequest re-measure, doc 44 phase 4: the leads are now
the ceiling of each station's real transit at the picket's own
hull speed 9; the wait asymmetry above is closed by 44's phase 3.
Round 3's 30-day shifts then removed the day-1 muster entirely —
the first relief launches run-day 22 at the earliest — and this
playtest runs under that math.)**
Ratchet paid twice in-phase (``_row_placements`` /
``_static_rebuild_kwargs`` extractions; ``_handle_dev_shift_keys``
refactored to the matcher→action dispatch table). One process
slip self-caught: a ``make check | tail`` pipe let one commit land
gate-red (a wrong expected day in the new Shift+J test) — fixed
and amended while unpushed; gate green at every pushed state.

  Implementation brief (2) — APPROVED (refine session 2026-09-09,
    amended per the ADVISE reviewer round; user invoked
    ``/implement-phase 41.2``):

  - **Scope.** Data: ``SensorColumn`` (``data/solar_systems/
    __init__.py``) grows ``shift_days: int = 7``, ``watch_cycle:
    tuple[str, ...] = ("full", "full", "full", "thin")``,
    ``full_watch`` / ``thin_watch`` rosters of ``(y, lead_days,
    base_id)``. ``luyten_star.py``: 10 new ``EnemySpawn`` rows
    (y = 7, 21, 35, 49, 63, 77, 91, 105, 119, 133) + the watchbill
    on ``_sensor_column``. Initial leads (days, estimated at speed
    10 — steps ≈ dist/0.8, days ≈ steps/10; data, tuned at
    playtest; Blockade Station North (70,22) serves y ≤ 35, South
    (130,115) the rest — measured crossover y≈36):
    full = ((7,10,N),(21,10,N),(35,10,N),(49,9,S),(63,7,S),
    (77,5,S),(91,4,S),(105,3,S),(119,3,S),(133,3,S));
    thin = ((25,10,N),(55,8,S),(85,5,S),(115,3,S)).
    Code: ``navigation_line.py`` owns the watch — pure watchbill
    helpers, the per-step traffic pass, flight stepping (80%
    throttle + ``try_step_with_slip``, A* via the existing path
    machinery, ``combat_locked`` skipped); tenure-keyed spawn +
    build-side reconciliation (overdue reliefs stamp at their
    bases) in ``solar_system._system_enemy_entities``; the
    watch-pass call site beside ``check_crossing`` in both movement
    passes; ``navigation_combat._entity_hail_key`` prefers the
    stamped ``static_spawn_key``; the load-path migration helper
    lives in ``navigation_line.py`` (pure) with a ~2-line call at
    the top of ``load_game`` — ``saveload.py`` sits at 980/1000
    lines and takes no new logic (reviewer round); silent
    spawn/despawn for line traffic (never the merchant "Sensor
    ping"/"docks at" paths); watch flights carry no
    ``procedural_squad_id``. Dev grant in ``dev_mode.py`` +
    ``test_dev_mode.py``. At phase close: amend SYSTEMS.md's
    tombstone entry (the key format gains the tenure suffix).
  - **Build order.** (1) Watchbill data + pure helpers
    (tenure/kind/roster/launch-day over the wrapping clock triple)
    + tests; (2) tenure-keyed watchbill spawn + build-side
    reconciliation in the map build + tests; (3) ``_entity_hail_key``
    prefers the stamped key + test; (4) the per-step watch pass —
    O(1) idle steps (pure day-arithmetic due-check; full census +
    launches + departures only on exact launch/boundary days),
    flight stepping with cached A*, arrivals → park, boundary
    departures → fly home (live flight target discriminates
    outgoing from displaced), displaced immunity, tombstoned-launch
    skip, silent launches/despawns — + tests; (5) ``_picket_payload``
    by id + tests; (6) legacy tombstone migration (Luyten-scoped,
    top of ``load_game``) + tests; (7) dev grant; (8) playtest
    checkpoint.
  - **Binding rulings.** The phase-2 SETTLED section (all six +
    mechanical consequences, incl. the reviewer-round amendments)
    and phase 1's standing rulings — the manned sweep (any alive
    picket), the checkpoint's one hail shape, the naming ban. NO
    combat-semantics changes; no new Entity fields, globals, or
    persisted schedule state (role derives from tenure key +
    watchbill + position + live flight target); no log lines on
    boundaries or flights (wordless); the guide carries nothing
    about the Line — the checklist's guide-diff item is "none".
  - **Required tests.** Watchbill helpers (tenure boundaries days
    8/15/22; kind per shift; roster + launch day per station;
    derivations hold across month AND year wraps); tenure-keyed
    spawn (current watchbill only; tombstone honored; monotonic
    tenure suffix); boundary behavior (at-station outgoing flies
    home; displaced stays — never given a target; relief parks;
    early arrival holds its station despite a slip aside); two
    relief waves airborne (tenure ≥ current+2 keys coexist;
    launch-skip strictly per key); full↔thin boundary rotates the
    whole disjoint roster; murdered relief stays dead for the
    tenure and re-mans next tenure; payload by id counts parked +
    in-flight + displaced; hail key stable across steps for a
    moving picket (positional re-arm does not re-open per step);
    line traffic absent from ``_squad_groups``; ``combat_locked``
    pickets not stepped; silent launch/despawn (no log lines);
    migration re-stamps ONLY luyten picket keys (a ross_154 /
    lalande_21185 ledger is untouched) and runs before both
    consumers (legacy save loads with the station dead through the
    current tenure); save/load round-trip = schedule-consistent
    (mid-tenure load rebuilds parked exactly; overdue reliefs
    relaunch from base); dev grant in ``test_dev_mode.py``.
  - **Stop point.** NOTHING from phase 3 — no convergence
    choreography, no 30-floor tuning (the garrison size is that
    phase's input), no interdiction changes. No grant-side method
    content; no doc-42 rumor hooks (the schedule is observable,
    not yet sold); no restricted-sector changes (doc 43).
  - **Playtest checkpoint** (numbered; SPACEHACK_DEV run, jump
    wolf_359 → luyten_star; the dev grant advances the clock to
    the next shift boundary):
    1. Arrival: the full watch mans the line — 10 pickets spaced
       along x=150 (was 4); the sweep/challenge behave exactly as
       phase 1 against them.
    2. Jump near a boundary: reliefs arrive from the blockade
       stations ≈ on time; outgoing pickets depart at shift end
       and fly home to land; the line's dip lasts only until
       relief lands.
    3. Fast-ship check: a relief parks early and holds its station
       ahead of its tenure (loitering is intended).
    4. Jump into the maintenance watch (tenure 3): the line thins
       to the shipped four stations; the wide gaps reopen.
    5. Cross dark through a thin-watch gap dead-center: no hail
       (the ghost window).
    6. Lure a picket off-station and hold the lure across a
       boundary (STAY IN SYSTEM — jumping away and back snaps a
       lured picket back to its station: shipped static-rebuild
       behavior, not a bug): the displaced picket stays exactly
       where it is — never flies home; the dark loop completes.
    7. Murder a relief in transit: its station stays dark for that
       tenure; at the next boundary a fresh relief launches (new
       tenure) and re-mans it.
    8. Kill the ENTIRE line: the column goes dark (no hail, no
       waves — the phase-1 manned ruling); at the next boundary
       reliefs launch and the sweep returns.
    9. Save mid-tenure → load: SCHEDULE-CONSISTENT restoration
       (reviewer round — statics rebuild from the watchbill):
       parked pickets exact at their stations; an in-flight relief
       relaunches from its base on schedule; a lured picket snaps
       back to its row. Save just before a boundary → load → step
       across: the rotation fires identically to an unbroken
       session.
    10. Legacy save (pre-phase-2, a picket killed): on load the
        station stays dead through the current tenure and re-mans
        at the next boundary — no silent resurrection.
    11. Regression: a live unpapered crossing waves/challenges
        exactly as phase 1 (manifest/rank/service/consume
        untouched); guide diff: NONE.

### Phase 3 — The convergence (the interdiction response)
- [ ] Defy/dark-defy → picket squad + on-duty patrols converge at
      strength read off the ON-DUTY roster (escalation
      choreography; reinforcement machinery is close)
- [ ] The Line stops engaging past the column (positional escape
      west — or through)
- [ ] The convergence engages REGARDLESS of stance (the
      interdiction supersedes the statics gate; charged-cell
      precedent)
- [ ] Tuned to doc 39's 30-floor contract — provably unwinnable
      below 30, a real costly fight at 30+ — verified against
      min-maxed sub-30 fits (doc 39's last Phase 0 method item
      lands here)

  Implementation brief (1) — APPROVED (drafted in the refine session
  2026-09-09; user invoked ``/implement-phase 41``):
  - Scope: NEW ``src/spacehack/navigation_line.py`` — the Line
    domain: sweep, resolver, hail (the reusable checkpoint
    pattern's first instance). Data: the blockade spec in
    ``data/solar_systems/luyten_star.py`` grows the sensor-column
    fields (column x, labels) — data-first. Marker traits
    ``blockade_manifest`` / ``blockade_service_run`` defined +
    registered in QUEST_PERKS (outside ALL_TRAITS — milestone
    screens never offer them, per doc 39's settled tracking
    ruling; ``trait_name`` resolves them for the character screen;
    no grant path yet — grant-side content is the methods').
    Hook points: the per-step pass that already runs encounter
    detection + auto-hail (``navigation_combat``
    ``_auto_hail_entity`` neighborhood — the pre-implementation
    audit pins the exact seam); the sweep hail must break GO TO
    like comms warnings do (``_goto_step_interrupt``); the comms
    modal pattern for the hail; ``identity.resolved_identity`` /
    ``effective_reputation`` for reads; ``has_trait`` for markers.
    Dev hooks: SPACEHACK_DEV grants both marker traits + a
    rank-eligible worn library entry for the playtest
    (``dev_mode.py`` + ``test_dev_mode.py``). Log line wording
    drafted at build, user-dictatable.
  - Build order: column spec data → pure resolver
    (``resolve_sweep`` — table lookup, no ctx) + tests →
    crossing-edge tripwire in the per-step pass (fires once per
    crossing, both directions) → checkpoint hail modal
    (Comply/Defy; Defy flips the picket squad hostile) → dark path
    (sweep skip; physical spot → the same hail) → service-run
    consumption at the wave → dev grants → guide.
  - Binding rulings: the eight SETTLED items above are the
    contract — two-layer detection (1); one hail shape,
    Comply/Defy only (3); identity-only reads, never cargo (6);
    service-run trait consumed at the wave, manifest trait never
    consumed (7); sweep hails all unpapered incl. allied — the
    doc-40 stand-down superseded INSIDE the column only (8);
    crossing positional + symmetric, no arrival event (5); no
    alert/heat state, no new GameContext fields, NO persisted
    tripwire state — the crossing edge is prev-x vs new-x inside
    the movement pass, prev initialized from the player's
    position at arrival/first step, so every entry path (jump,
    load, hidden-gate east materialization) stamps naturally and
    the first westbound return crossing hails (4); one hail shape
    INSIDE the column, the doc-40 dark-spot challenge untouched
    outside (3, amended).
  - Required tests: resolver per row (papers wave; rank+ wave
    logged AS that ID; service-run wave + consume; plain
    live/spoofed → challenge; dark → never sweeps); crossing-edge
    fires exactly once per crossing in both directions, no
    re-trigger while past the column; consumption (service-run
    gone after the wave, manifest persists); dark physical spot →
    challenge; Defy → the interdiction flag engages the squad at
    the gate regardless of stance, adopted at every
    state-bearing caller; GO TO breaks when the sweep hail
    fires; tripwire zero-state (after load on either side the
    next actual crossing fires exactly once; an east
    materialization stamps the side — the first westbound
    crossing hails); dev grants tested in ``test_dev_mode.py``; affected
    guide sections updated (comms option-matrix line, Identity &
    Transponder).
  - Stop point: NOTHING from phase 2 — no rotations, no schedule,
    no spawn/despawn changes (the four statics stay as they are);
    NOTHING from phase 3 — no convergence choreography or tuning
    beyond the minimal squad teeth; no grant-side content
    (Commandant, Whisper, heist, gate tech); no far-side or
    restricted-sector changes (doc 43).
  - Playtest checkpoint (numbered; SPACEHACK_DEV run, jump
    wolf_359 → luyten_star):
    1. Cross the column live (broadcasting) — the checkpoint hail
       appears (was: warning-only log).
    2. Comply — turn-back log; cross again — hailed again.
    3. Defy — the picket squad engages (dev-loadout fight).
    4. Dev-grant ``blockade_manifest`` — cross live: waved through,
       logged, no hail; cross back — waved again (trait persists).
    5. Dev-grant ``blockade_service_run`` — cross: waved through
       AND trait consumed; the next crossing hails again.
    6. Go dark (dev install the cut-out); cross a geometric gap
       dead-center — no hail (the sweep is blind to you); let a
       picket's detect radius touch you — the challenge fires.
    7. Wear a rank-eligible militia ID (dev-granted library entry)
       — cross live: waved through, the log names THAT ID.
    8. Save east of the column → load: no re-hail. Save west →
       load → cross: the hail fires.
    9. Regression: a liked hull meeting OTHER militia statics
       (e.g. Sol patrols) still enjoys the doc-40 stand-down — the
       amendment is the column only.
    10. Regression (column-scope amendment): a dark hull spotted
        by a militia patrol OUTSIDE the column (e.g. a Sol patrol)
        still opens the shipped doc-40 challenge — Identify /
        Attack, ESC = open fire.

## Pre-implementation audit — phase 1 (2026-09-09)

**Seams to extend (all verified in code during the audit):**

- **Movement pass** — two state-bearing per-step passers:
  ``game_flow._run_combat_loop`` (space steps + wait; callers
  ``game_loop.py`` 415/443/700) and ``_goto_step_interrupt``
  (``navigation_travel.py``). The sweep check wires into BOTH,
  before ``_check_auto_comms_warning``, returning its payload
  shape; a hailed step skips the comms-warning pass that step
  (the hail replaces the warning-only log at the column — and
  per the reviewer round, ``militia_blockade``'s spec-distance
  warning is suppressed entirely in column systems).
- **Crossing edge** — the sweep fires on ENTERING the column
  (``new_x == column.x`` and ``prev_x != column.x``), from either
  side; leaving is always free. (Supersedes the first-pass
  edge-transit rule: hailing the retreat re-hailed complying
  hulls — user playtest bug #1, round 2.) Every west↔east
  traversal must step onto the column, so coverage stays
  edge-to-edge. ``_prev_x`` lives in the new module; on ``None``
  (first step of any session/entry) it stamps from the position
  — no persisted state, no new ctx fields (brief ruling 4).
- **Spawn gate** — ``navigation_combat._gate_engages`` keeps its
  signature; the three ``_trigger_*`` passes swap
  ``_charged_cell_aggro(...)`` for a combined ``_aggro_override``
  (charged-cell heat OR Line interdiction). Charged-cell
  precedent, no rep writes, no radius floor (phase-1 minimal).
- **Dark spot** — ``navigation_combat._dark_spot_challenge``
  grows the column branch: a picket spotter inside the column
  opens the Line's checkpoint; any other militia spotter keeps
  ``comms.open_challenge_direct`` untouched (regression item 10).
- **Hail modal** — reuse ``comms._pygame_interaction_outcome``
  with a Comply/Defy dispatch (challenge-shaped: two options, no
  run). ESC/window-close = Defy — silence is defiance (doc-40
  precedent: refusing the conversation is an answer too).
  Private cross-imports comms↔navigation are established
  (``comms`` already imports ``navigation._calc_flee_chance``).
- **Reads** — ``identity.broadcast_mode`` /
  ``resolved_identity`` / ``identity_label``; ``xp.has_trait``;
  service-run consumption = ``ctx.player_traits.remove`` (a
  list, already serialized — ``saveload.py`` 170/827).
- **Data** — ``SensorColumn`` frozen dataclass in
  ``data/solar_systems/__init__.py``;
  ``SolarSystem.sensor_column: SensorColumn | None = None``
  (every other system untouched). ``luyten_star.py`` stamps
  x=150, squad ``luyt_blockade_picket``, picket id
  ``militia_blockade``, hail lines, ``rank_rep=80``.
- **Dev + resets** — ``dev_mode.apply_dev_line_kit`` called from
  ``game_loop._configure_new_context`` (the New Game hook that
  already applies the dev identity library); module-global
  resets go there too. Every jump runs ``reset_session()`` in
  ``_jump_to_system`` (interdiction cleared AND the tracker
  re-stamped — a stale side can never read as a crossing).
  Neither global is serialized — by design: the tripwire
  self-stamps (brief ruling 4), and the flag's defiance is
  session-local (see the phase-1 LANDED note for its real,
  reviewer-corrected teeth).

**Duplication hotspots + DRY strategy:**

1. Crossing/encounter dispatch duplicated across two movement
   passes → one ``check_crossing`` entry point; each caller adds
   ~4 lines.
2. Defy squad payload → read the system's own ``enemies`` table
   (squad filter + ``_alive_entity_at`` from navigation_combat);
   no new ``world.Entity(...)`` construction blocks (known trap).
3. Checkpoint modal → the shared comms runner, never a bespoke
   menu loop (pygame pattern guardrail).

**Judgment calls pinned (all one-line data/log changes if the
user dictates otherwise):**

- ``rank_rep = 80``: "blockade rank+" carried no number in docs
  39/41. 80 sits above liked, below the dev face's +100, inside
  the clone tier-3 band (25–100) — a good clone can pass, a
  mediocre one cannot.
- Row 2 (rank wave) reads a WORN FALSE face only (``kind !=
  "true"``): ruling 8 turns back live-allied unpapered hulls —
  impersonation is a face, not your own standing.
- Comply is answer-then-see: phase 1 has no re-check when a
  complying hull keeps east. Flagged for phase 3 (runners are
  the convergence's business).

## Pre-implementation audit — phase 2 (2026-09-09)

**Seams to extend (all verified in code during the audit):**

- **Clock** — ``time.py``: the wrapping triple ``ctx.time_day/
  month/year`` with ``advance_time`` as sole mutator (day-granular;
  ``tick_move`` runs per manual + goto step at speed moves/day).
  ``total_days = year*360 + (month-1)*30 + day`` is a PURE
  derivation — no new schedule state anywhere. The wait path
  (period in space) runs the NPC passes without a day flip; the
  watch rides the same cadence (flights move on waits; days only
  flip on movement).
- **Watchbill data** — ``SensorColumn``
  (``data/solar_systems/__init__.py``) grows ``shift_days=7``,
  ``watch_cycle=("full","full","full","thin")``,
  ``full_watch``/``thin_watch`` tuples of a new frozen
  ``WatchStation(y, lead_days, base_id)``. ``luyten_star.py``:
  10 new ``EnemySpawn`` rows at x=150, y = 7…133 (the shipped 4
  at y=25/55/85/115 are the thin roster) + the watchbill on
  ``_sensor_column``. Rows not in any roster keep phase-1
  semantics (unqualified keys) — ross_154 / lalande_21185
  statics and every non-column system untouched.
- **Build** — ``solar_system.make_solar_system`` grows
  ``watch_day: int | None = None``; a watch-active system without
  it raises ``ValueError`` (the alternative — silently spawning
  no watch — is a dark column, the exact silent bug class this
  repo guards against). ``_system_enemy_entities`` delegates
  placement to ``navigation_line`` via LAZY import (module-level
  would cycle: navigation_line already imports solar_system).
  Placement: current-kind roster rows spawn PARKED on station
  with ``…:t<tenure>`` keys (tombstones honored; off-duty rows
  never spawn); overdue future reliefs (launch day ≤ watch_day,
  key not tombstoned) stamp AT THEIR BASES and the stepper flies
  them in. Production callers all have the day:
  ``navigation_travel._jump_to_system`` (ctx),
  ``saveload_maps._build_space_map`` (save data; threaded from
  ``rebuild_game_map`` which owns ``data``),
  ``city._build_space_return`` (ctx).
- **Per-step pass** — beside ``move_npcs`` at BOTH of its call
  sites: ``game_flow._run_combat_loop``'s ``also_move_npcs`` tail
  and ``navigation_travel._goto_step`` (after the interrupt
  check — a hailed step freezes the watch with everything else).
  Idle gate is pure day arithmetic, O(1): boundary
  (``(total - total_days(1,1,2200)) % shift_days == 0`` —
  epoch-anchored like tenure) OR any horizon launch day ==
  total. Due WORK is overdue-inclusive (``<=``), so skipped days
  (dev Shift+D) self-heal at the next due day; the new Shift+J
  lands exactly ON a boundary (heals immediately). Horizon =
  current + 2 tenures: leads ≤ 10 < 2×7 means a C+3 launch day
  is always in the future during C.
- **Flights** — ``ctx.npc_targets`` / ``ctx.npc_paths`` keyed by
  the tenure key: EXISTING ctx fields (no new state), and the
  save sync (``saveload._sync_procedural_spawns``) only
  round-trips mids tied to ``ctx.procedural_spawns`` — watch
  keys are dropped at save BY CONSTRUCTION = session-scoped
  flights, exactly the reviewer ruling. Stepping mirrors
  ``_step_squad``'s single-member mechanics: 80% throttle,
  ``world.find_path`` computed once at target-assign,
  ``world.try_step_with_slip``, ``combat_locked`` skipped. Watch
  entities carry NO ``procedural_squad_id`` → invisible to
  ``_squad_groups``/``move_npcs`` patrols by construction.
- **Hail key** — ``navigation_combat._entity_hail_key`` prefers
  the stamped ``static_spawn_key`` (empty for procedural hulls;
  the position fallback stays for keyless statics).
- **Payload** — ``navigation_line._picket_payload`` rewrites to
  by-id (``npc_ship_id == column.picket_enemy_id``): parked,
  in-flight, and displaced all count; the picket id is unique to
  the column system (``line_dark_hail``'s existing claim).
- **Trigger pass unchanged** — ``_trigger_static_spawns`` gates
  on ``_alive_entity_at`` per ``system.enemies`` row: off-duty
  rows read empty (no entity at the row position), in-flight
  reliefs are never at row positions — static trigger semantics
  survive rotations with zero changes. In-flight reliefs do not
  chase (no squad id) — convergence choreography is phase 3's.
- **Load migration** — pure helper in ``navigation_line``;
  ``load_game`` (``saveload.py``, 980/1000 lines — takes no new
  logic) rewrites ``data["defeated_static_spawns"]`` at its top,
  BEFORE both consumers read it (``rebuild_game_map`` →
  ``_build_space_map``, and ``_assemble_context``'s ctx restore).
  Luyten-scoped: unqualified keys matching a column system ×
  its ``picket_enemy_id`` only; re-stamped with the CURRENT
  tenure (from the save's clock triple).
- **Dev** — the ``input_helpers._is_shift_*_press`` +
  ``game_loop._handle_dev_shift_keys`` + ``dev_mode.apply_dev_*``
  pattern; new Shift+J advances the clock to the next shift
  boundary (the current column's ``shift_days``; 7 outside
  column systems). J is unclaimed.

**Duplication hotspots + DRY strategy:**

1. Picket entity construction would be duplicated between the
   build path and runtime launches → one
   ``navigation_line._make_picket_entity(spec, pos, key)``
   factory; ``_system_enemy_entities`` lazily imports it.
2. Flight stepping vs ``npc_ships._step_squad`` — same
   80%/path/slip mechanics. Full reuse would drag squad cohesion
   and aggro machinery into the Line; the PRIMITIVES are the
   designed seam (``world.find_path`` /
   ``world.try_step_with_slip``) and the watch stepper uses only
   those — no slip/path logic is copied.
3. Base-cell arithmetic (east-of-body +1, mid-height) duplicates
   ``_build_body_goals``' convention → one
   ``navigation_line.station_dock_cell`` helper documented as
   the same convention.

**Judgment calls pinned (all data/log-level, user-dictatable):**

- Runtime launches fire on the step whose DAY equals the launch
  day (the clock is day-granular; sub-day precision is invented
  precision).
- A stale dict entry (flight killed mid-air) lingers in
  ``npc_targets``/``npc_paths`` until session end — never read
  (the stepper is entity-driven), never saved. Accepted leak.
- Shift+J lands ON the next boundary day (strictly future): the
  rotation is then observable on the very next step.
- **Epoch anchor (implementation round)**: the settled ``total_days
  = year*360 + (month-1)*30 + day`` is dense and monotonic, but a
  360-day year is NOT divisible by 7 — the shorthand
  ``(total_days - 1) // 7`` would put the first boundary on
  game-day 2, not 8. Tenure is epoch-anchored instead:
  ``(total - total_days(1,1,2200)) // shift_days`` — tenure 0 is
  the game's first week and boundaries land on the ruled days
  8/15/22. (Key format, cycle, rosters unaffected.)
- **Accepted one-time re-hail on legacy loads (reviewer round)**:
  the hail-key preference for stamped keys renames a keyed static's
  hail key (``pid:x:y`` → the stamped ``sys:pid:x:y[:tN]``, ``dark:``
  namespace included), so a pre-phase-2 save's ``militia_scanned``
  entries orphan — a keyed static that already hailed or challenged
  re-hails ONCE after that load. Bounded (the set clears on every
  system departure) and one-time; recorded here rather than
  re-keyed at load. Per-tenure key changes are the intended design
  (a new crew has not challenged you yet).
