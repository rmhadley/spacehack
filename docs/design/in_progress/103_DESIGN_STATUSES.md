# DESIGN: Statuses — the durable buff/debuff system

**Status: BUILD C BRIEF APPROVED (2026-10-19 — the four boundary
rulings settled and the Implementation brief drafted,
advisor-folded, and user-approved this session). Two phases
remain: Build C (ready for `/implement-phase 103.6`) and the
Close.**

Companions: `complete/102_DESIGN_CYBERNETICS.md` (the Parked sketch
this doc inherits — "a general statuses container (`id → rounds
remaining`) shipping one entry; one severity seam function
re-keyable from burnt ego through willpower later"; the recorded
endgame: "develop a debuff system that is robust and extensible,
and chrome then trades combat advantages for certain risky
disadvantages — opt-in risk pricing power, never shrinking the
effect"); `SYSTEMS.md` (the standing rulings this doc must obey);
`knowledge.md` (data-first, cohesion, ratchet, prose-gate laws).

## The problem (measured, 2026-10-17)

Timed combat effects exist today through FIVE coexisting ad-hoc
mechanisms, none data-driven, none available to enemies in space,
each with its own tick site:

| # | Mechanism | Anchor | Carries |
|---|---|---|---|
| 1 | Ground typed ledger: `dict[effect_id → ActiveConsumableEffect(remaining_turns, regen, ap_bonus)]` | `combat/_ground_effects.py:17-98`; state at `combat/_ground_types.py:116-118` | med-pack regen, combat stim, PLUS the synthetic `"neural_stim"` −1 AP loan entry — a chrome effect borrowing the consumable container |
| 2 | Space bare `player_state` keys, popped inline | `stim_loan_ap` / `stim_cooldown` at `combat/_rules_space.py:834-871` | the SAME loan's space twin — a hand-rolled parallel of #1 |
| 3 | Latch booleans + int countdowns on the state dataclasses | opener flags (`enemy_fired`/`opener_spent`), `core_cooldown`, enemy `stim_turns`/`stim_ap_bonus`/`regen_turns`/`regen_amount` (`_ground_types.py:53-56, 128-141`) | once-per-fight windows, cooldowns, enemy stim/regen |
| 4 | Stateless conditionals (while-equipped) | chrome sums, traits, Focus, Charger, Nano Mesh | permanent passives — recomputed per read, NO duration |
| 5 | Map-anchored zones | `game_map.stare_zones`, `game_map.field_tiles` (saved via `saveload_maps.py:177-183`) | Watcher stare, Warden field — world geometry, not actor state |

**Named adjacent, deliberately NOT among the five (advisor census
additions, 2026-10-18):** the movement-dodge ledgers
(`cells_moved_this_turn` on all four actor homes —
`_ground_types.py:57, :102`, `_types.py:65`, space
`player_state["_stats.py:421"]`, reset at each round boundary) are
a timed, fight-scoped, actor-attached modifier that STAYS a ledger:
its magnitude is recomputed per move within the round, which a
fixed-payload status cannot express. The Shredder's in-combat mend
(`_ancients.py:61-81`) is fight-scoped conditional regen that stays
spec-mechanics data (one `regen_per_round` away from being a status
— it migrates the day content wants machine heal-over-time, not
before). These are boundary rulings, not census rows: they exist,
they are timed, and they keep their current homes.

And the poster child of what this costs: the Stun Baton's effect is
a hardcoded id branch — `enemy.ap = max(0, enemy.ap -
int(weapon_id == "stun_baton"))` at `combat/_rules_ground.py:443` —
a guaranteed per-hit AP drain with no data home, no duration, no
HUD surface. It is the ONE on-hit rider in the tree that is neither
a spec field nor instant (knockback, `armor_bypass`, and the space
strip weapons ARE data-driven on-hit riders — instant and
durationless; the baton is the only one that lingers and the only
one written as a branch). It violates the standing ruling ("Data
opt-ins over id lists") in miniature, and every "more complicated"
effect we have wanted (suppression, stagger, damage-over-time,
disruption) has nowhere to live.

What does NOT exist at all: enemy-side timed effects in space
(`EnemyInstance` has no container), a stacking model, an
application chance, any debuff vocabulary, any severity/potency
notion. (`EnemyInstance.shields_charged` — declared
`_types.py:43`, stamped `_stats.py:408`, read NOWHERE — is dead
code and a retire candidate this pass is already walking past; its
name is exactly the kind that would confuse a status later.)

## Identity and doctrines

- **A status is a timed, ACTOR-ATTACHED effect.** PLAYER statuses
  are DURABLE across combat boundaries (ruled 2026-10-18, below);
  enemy statuses are fight-scoped. One mechanism for buffs and
  debuffs alike; polarity is presentation data (color, wording),
  never a code fork.
- **Actor-symmetric by construction** (the chrome precedent, doc
  102 SETTLED 6): the player container and the enemy containers are
  the same type; every read takes a container, never an is-player
  branch. An NPC that quaffs a stim or eats a stagger reads by the
  same rules as the player.
- **Statuses are catalog content, not code.** A new stat-shape
  status = a `data/statuses.py` entry (plus, only if it needs a term
  no assembly reads yet, ONE assembly term). The ChromeSpec idiom:
  frozen spec, flat defaulted payload fields, `find_status` /
  `list_status`, silent-skip on unknown ids (a retired entry never
  raises mid-combat). **The assembly term is the gate that keeps
  the flat table honest: a payload field without a read site is
  inert by construction — dead content, and it fails review**
  (advisor 2026-10-18).
- **The engine is pure and RNG-free.** `combat/_statuses.py` never
  rolls, never logs, never touches HP directly — ticks RETURN
  events as data and the rules adapters apply them (kill-draws
  doctrine: the engine alone cannot reshuffle a seeded stream; the
  only new draws are application rolls at delivery sites, guarded,
  below).
- **The severity seam exists from day one** (inherited sketch): a
  per-instance `potency` multiplier on payload fields, re-keyable
  from burnt ego through willpower later. The seam is structural in
  v1 even where nothing keys it yet.
- **NOT statuses, by boundary ruling** (the line that keeps this
  from eating the game):
  - While-equipped passives (chrome, traits) stay stateless sums —
    no duration, no fight scope.
  - Map-anchored zones (stare, Warden field, the field-tile
    regrow) stay world state.
  - **Movement-dodge ledgers stay ledgers** — recomputed per move,
    reset at the boundary; a status cannot express a magnitude
    that changes within a round.
  - **Spec-authored per-turn regen/regrow/divert behaviors stay
    spec data** (Shredder mend, Warden regrow, the enemy shield
    economy's free regen + threshold-gated paid divert) until
    content demands the container.
  - **On-hit INSTANT riders stay weapon data** (knockback,
    `armor_bypass`, `shield_strip`/`shield_strip_pct`/EMP) — the
    debut's `status_id`/`status_chance` fields join this family as
    its first lingering member.
  - Ability cooldowns (the Stim's `core_cooldown`) are ability
    gating, not conditions on the actor (open question 3).
  - Permanent world-layer states (ego bands) are consequences, not
    combat timers.
- **Player statuses are DURABLE; enemy statuses are fight-scoped
  (RULED 2026-10-18 — see the Durability section).** The player's
  container lives at the ctx level and is SAVED; enemy containers
  die with the enemy's fight and never serialize. Combat QUIT
  still never persists mid-fight (no mid-fight saves exist; saves
  happen only at the exploration exit seam, `game_flow.py:119-138`
  — advisor-verified), but a regen ticking while you walk survives
  save/quit/continue by the save contract.

## Application is ROLLED, not guaranteed (RULED 2026-10-17)

User ruling at plan approval, recorded: **"debuffs shouldn't always
be guaranteed on hit. You'd have a % chance to apply a debuff, and
that % chance could possibly be adjusted by things like burnt
ego. This is where the ego drain was going to come in to play."**

- **The application chance lives on the DELIVERY VEHICLE** (weapon
  spec, consumable, ability), not the StatusSpec — the same
  condition can arrive from sources of different reliability.
  `status_id: str = ""` + `status_chance: int = 0` on
  `GroundWeaponSpec` is the data home the
  `int(weapon_id == "stun_baton")` branch never had.
- **Burnt ego adjusts the chance through ONE seam function, keyed
  on the VICTIM (RULED 2026-10-18, q5)** — the ego drain's combat
  entry, exactly where doc 102's recorded endgame parked it
  ("chrome trades combat advantages for certain risky
  disadvantages"). Burn reduces the victim's ability to resist an
  applied status: zero burn = identity ("full ego, full resist"),
  susceptibility monotone up with burn; the attacker's burn NEVER
  reads. The seam IS exercised in the debut — by ORGANIC enemy
  baton wielders (see the debut section: the `melee` family
  already contains the baton; the enemy's fire site makes the
  player the victim). **Supersession recorded (advisor catch,
  2026-10-18):
  doc 102 explicitly rejected combat-axis consequences of low ego
  ("the world reprices you; it does not dim your aim and does not
  open fire," lines 176-180). THIS SEAM supersedes that rejection,
  and only this seam — debuff-susceptibility IS the "certain
  risky disadvantage" the recorded endgame priced, and everything
  else socioeconomic stays exactly as 102 ruled it.** Slope, cap,
  and dead-zone flatness are semantics-pass rows. The seam's home:
  `chrome.py`, beside `band`.
- **The roll sits at the fire site, after the hit resolves**,
  guarded `chance > 0` (the crit precedent): fights without a
  chance-carrying delivery consume ZERO new draws, bit-identical;
  fights WITH one (every Stun Baton fight, on debut) draw once per
  connecting hit → tripped balance rows re-pinned same-commit,
  cause noted. **Direct fire only, same family as crits** (advisor
  catch): missiles and blasts never roll application (missile
  arrivals call `resolve_damage` bare, `_missile_flight.py:315,
  468, 521` — the crit ruling's exact reasoning); AoE status
  delivery, if ever wanted, is its own future ruling with its own
  draw-count law. **Killing hits do not roll** (working lean, open
  question 10): a hit that kills leaves no victim — rolling anyway
  burns a draw to no effect and shifts every subsequent stream
  draw.
- **The Stun Baton is the debut** (user: "I love the idea of taking
  the stun rod and making it the first debuff in the new system...
  a great one to use to test"): the first real DEBUFF in the game,
  the first rolled application, the first enemy-side timed status —
  three firsts in one piece, on ground where the behavior is
  already live and pinned.

## Durability — statuses survive the fight (RULED 2026-10-18)

User ruling, recorded: **"I want them to be durable and persist.
But it'll need careful planning and consideration. Having a damage
tick on the player after they got in their ship and switched to
space mode might be the wrong choice. But ending ground combat
shouldn't immediately remove your current buff/debuff."**

- **Ending combat does NOT clear the player's statuses.** Today
  leftover effects simply evaporate (`sync_state` discards the
  fight state; a med pack's unfinished regen is LOST — verified;
  the earlier draft's "redundant with the outside-combat
  full-heal" claim was wrong, conflating two different use
  moments). The correct end-state (user): an in-combat med pack's
  regen CONTINUES ticking outside combat.
- **Theater crossing is the careful-planning case**: a ground
  damage tick following the player into space combat "might be the
  wrong choice" (user instinct, agreed) — RULED 2026-10-18 (q11):
  statuses tick only in their home theater; crossing PAUSES by
  default. AMENDED 2026-10-19: q11's smother enum value is
  SUPERSEDED by the transition-removal system (statuses declare
  WHICH transitions remove them; landing removes all debuffs by
  default; the future fire debuff adds board-removal — see the
  Build C rulings SETTLED section). No damage tick ever follows
  you into the cockpit.
- **Sequencing ruling (the efficiency question, answered by
  split-by-layer):** the Build A migration stays BEHAVIOR-identical
  (fight end still defuses the player container, exactly as
  today's ledger evaporates) — that is the proof layer, and
  bundling boundary changes into it would make every diff and
  every tripped balance row ambiguous between "harness wrong" and
  "new rule working." But the STRUCTURAL placement happens up
  front: the player container lands in its final home at Build A
  (ctx-level, save-wired, empty backfill) so it never moves twice.
  Build C flips the rules — carry-over at combat end, the
  exploration tick hook, crossing rules — as pure rule changes on
  the placed structure. Enemy containers stay fight-scoped
  throughout (an enemy's staggered dies with its fight; nothing to
  carry).

## The data model

### StatusSpec (frozen, `data/statuses.py`)

- `id`, `name` — registry key + display.
- `polarity: bool` — buff vs debuff; color and wording only, never
  logic.
- `duration: int` + `duration_class: str` — `"rounds"` (ticks down
  at the round boundary), `"fight"` (until fight end or consumed —
  the once-per-fight class), `"charges"` (consumed on trigger).
- `stacking: str = "refresh"`, `stacks_max: int = 1` — re-apply
  resets the duration (today's behavior) vs independent stacks to a
  cap.
- Boundary fields (RULED q11/q13; AMENDED 2026-10-19): the q11
  `crossing: str = "pause"` field was REPLACED pre-first-live-read
  by `removed_on: tuple[str, ...] = ()` — the transition-removal
  system: the named transitions that drop this status ("land",
  "board"; landing's remove-all-debuffs default is stamped
  CATALOG-side, every polarity=False row carries "land").
  Non-removed statuses PAUSE through a transition (statuses tick
  only in their home theater). `persists_past_fight: bool = True`
  stands (RULED q13; the ground and space stim loans author
  `False` — combat tempo).
- Flat defaulted additive payload — a status declares only what it
  carries (the ChromeSpec law; the fold stays table-driven). The
  migrations need exactly TWO terms (`regen_per_round` for the med
  pack; `ap_per_round` for stim, the loan, and staggered); the rest
  of the working set — `hit_bonus`, `dodge_bonus`, `melee_bonus`,
  `dot_per_round` — is the FIRST DISCRETIONARY TIER, authored with
  their assembly terms when content first demands them (advisor
  catch: the original "exactly what they need" claim was false).
- Behavior flags for discrete states (the "complicated" tier):
  `blocks_dodge = False`, `blocks_melee = False` (future
  suppression/disarm families).
- Ruled string templates, prose-gated: apply / tick / expire lines
  — a status declares only the lines it HAS (stim has no tick line
  today and settles none); tick/apply templates interpolate the
  SOURCE's display name (the `ActiveStatus.source` carries it), so
  today's "Med Pack regeneration: +2 HP." survives migration
  bit-identically ("Regeneration" stays the sourceless fallback).
  Plus the inspect overlay's DESCRIPTION text (q7) — same prose
  gate, same declare-only-what-you-have law.

### ActiveStatus (runtime, engine-home)

`status_id`, `remaining_turns`, `stacks = 1`, `potency = 1`,
`source = None`, `theater = None`. Potency multiplies additive
payload at sum time; source carries the deliverer for attribution
(log lines, future AI reads); theater is stamped at application
from the delivery vehicle's theater — the crossing rule (q11)
reads it: statuses tick only in their home theater.

### One container type — the durable player home + the fight-scoped enemy homes

- THE PLAYER: `ctx.active_statuses: dict[str, ActiveStatus]` — ONE
  durable home for both theaters (the 2026-10-18 ruling), declared
  on `GameContext`, wired into `_core_fields` /
  `_restore_core_fields` with an empty-dict backfill; the combat
  states READ this container (theater tags and crossing rules are
  the refine pass). The structural placement lands in Build A so
  the container never moves twice; Build A's fight-end defuse
  keeps behavior bit-identical until Build C flips it.
- `GroundEnemyInstance.statuses` (declared in `_ground_types.py`)
- `EnemyInstance.statuses` (declared in `_types.py` — space enemies
  gain their first timed container)

The cohesion law owns the GameContext field and the two dataclass
declarations. Nothing attaches at runtime.

### The engine (`combat/_statuses.py`)

- `apply(container, status_id, potency=1, source=None)` — enforces
  the spec's stacking policy; returns what happened (applied /
  refreshed / stacked) for the caller's log decision. **RAISES
  KeyError on an unknown id** (advisor ruling adopted: a delivery
  site naming a dead id is an authoring error, not a retire case —
  the silent-skip contract belongs to `sum_effects` reading OLD
  SAVE-shaped data, never to authoring).
- `advance(container) -> tuple[TickEvent, ...]` — decrements, drops
  expired, returns DATA events: `("heal", id, n)` / `("damage", id,
  n)` / `("ap", id, n)` / `("expire", id)`. The rules adapters
  mutate HP/AP and compose the ruled lines. Pure, deterministic,
  RNG-free.
- `sum_effects(container) -> StatusEffects` — the one-pass fold
  (payload × stacks × potency over active ids, silent-skip on
  unknown ids), frozen result, one flat field per payload term.
- `has(container, id)` / `potency_of` / `consume(container, id)`
  (the charges/fight class) / `dispel(container, predicate)`.

**The adapter contract (advisor catches folded):**

- **Tick-deaths route through the SAME kill path as shot deaths**
  (XP, drops, counters, tombstone bookkeeping) — and a dead actor
  skips the rest of its reset (no AP refresh for corpses). Today's
  advance paths cannot kill; the event vocabulary ships `dot`
  anyway, so the clause ships with it.
- **Clamping is the adapter's**: the engine is container-only and
  cannot know `hp`/`max_hp`/`ap_total`. Heal events clamp at max,
  the log line fires only on healed > 0 (today's shape,
  `_ground_effects.py:51-62`); the space loan applies
  twin-field-independently (`max(0, ap_total + loan)` and
  `max(0, ap_remaining + loan)`, popped exactly once,
  `_rules_space.py:840-844`); the ground fold adds
  `20 × ap_per_round` to the gain BEFORE `_roll_ap`
  (`_rules_ground.py:877-884`) — and a general fold can now go
  NEGATIVE (multiple negative statuses, untested by today's
  single-loan arithmetic); the gain guards at zero; the ENEMY
  reset is a direct add (`_gei.ap = _gei.ap_total + advance(...)`,
  `_rules_ground.py:891-893` — no `_roll_ap`, no twentieths) and
  takes its own `max(0, ...)` guard for negative folds (advisor
  2026-10-18) — the three shapes stay distinct, never
  homogenized.
- **The two loan wirings are DIFFERENT code shapes and stay that
  way** (advisor catch): ground folds the −1 into the next round's
  GAIN before the fractional roll; space applies it AFTER the AP
  reset to both fields. Both are "once at next round start." The
  migration must not homogenize them — `test_core_button.py` pins
  both shapes.

### Read-site wiring (assemblies gain status terms, zero-defaulted)

| Assembly | Anchor | Terms |
|---|---|---|
| Ground AP gain | `_rules_ground.reset_turn` | `+ 20 × ap_per_round` |
| Ground hit / melee / dodge | `hit_chance` (`_rules_ground.py:345-369`), `_player_melee_bonus` (:384), `_player_ground_dodge` (:694) | `hit_bonus`, `melee_bonus`, `dodge_bonus` |
| Space hit / dodge | `_player_hit_bonus` (`_rules_space.py:306`), `player_dodge_from_state` | `hit_bonus`, `dodge_bonus` |
| Space AP | `_rules_space.reset_turn` loan application | `ap_per_round` as events |
| Enemy reads | the symmetric instance reads | the same sums off their containers |

(Anchor corrected 2026-10-18: the ground hit assembly is
`hit_chance`, not `_player_hit_bonus` — that is the space name.)
Choke-point defaults, not seam threading: each assembly resolves
`sum_effects` itself from the state it already holds.

### Known limits, named on purpose (advisor 2026-10-18)

Where this shape strains first — recorded as limits, not
discoveries:

- **Mandated-action statuses** (102's parked cyberpsychosis) need
  AI-loop reads, not sums — no flag family covers them; they are
  the first request this shape cannot serve without new AI seams.
- **Incoming/outgoing damage modifiers** (a "vulnerable" debuff, a
  status-keyed Nano-Mesh-like multiplier) reach
  `resolve_damage`/`_ground_damage_raw` — the deepest sites in
  BOTH theaters; the "data edit plus at most one assembly term" bar
  (acceptance criterion 2) breaks first here.
- **AoE application** (a status-carrying explosive, stare-eruption
  victims) means N rolled applications per shot — a draw-count law
  that does not exist yet; ruled out until its own pass (the
  direct-fire clause above).
- **Assemblies are the AI's status interface**: enemy aiming reads
  the player's dodge through the shared dodge assembly, so a
  dodge-carrying status is played around automatically;
  staggered needs no read (it lands at the enemy's reset). The one
  LIVE AI-side status read is the stim trigger — see the migration
  table.

## Migration (behavior-identical, bit-pinned)

| Today | Becomes | Pin |
|---|---|---|
| med-pack `restore_hp` entry | `regen` status (2/turn, 3 rounds) | existing consumable unit pins + fresh bit-identity run |
| combat `stim` entry | `stim` status (+1 AP/round, 3 rounds) | same |
| ground `"neural_stim"` loan entry | `neural_stim_loan` status (−1 AP, 1 round) — the container stops being "consumable"; ground keeps the gain-fold wiring | `test_core_button.py` loan pins |
| space `stim_loan_ap` / `stim_cooldown` keys | the loan joins the space player container with its twin-field POST-RESET application preserved; the cooldown stays a cooldown (open q.3) | same, space side |
| enemy `stim_turns`/`regen_turns` fields | enemy containers, `apply` from `use_carried_consumable` — AND the trigger read: `_triggered`'s `stim_turns <= 0` (`_ground_effects.py:110-114`) becomes `has(container, "stim")`; the one live AI-side status read moves with the field (advisor catch) | enemy stim/regen tests |
| `GroundConsumableSpec.effect_id` | points at `find_status` — the "effect registry" its own docstring has promised since authoring (EXCEPT `tinker`: a quality-bump transaction with no timed effect; the id stays exempt) | round-trip |
| `ActiveConsumableEffect` + `effect_from_spec` | RETIRED | — |
| fight-state opener latches `enemy_fired`/`opener_spent` | fight-class opener statuses (RULED, q4), consumed at the respective first actions; trait reads become `has()` reads | `test_enemy_fire.py`, `test_class_traits.py` + fresh bit-identity run |

Chrome conditionals, traits, map zones: NOT migrated (boundary
doctrines above).

**Proof law (advisor-corrected):** the balance harness drives real
seeded ground fights including enemy weapon AND carried-consumable
rolls (`tests/balance/harness.py:847-874`) with baton rows
(`scenarios.py:353, 467`) — the harness IS the instrument for enemy
carriers and the baton; player-side med pack/stim/loan have NO
harness rows and are pinned by the existing unit tests
(`test_ground_consumables.py`, `test_core_button.py`,
`test_ground_tactics.py`). The pre/post worktree diff runs both:
harness rows for carriers + baton, unit pins for the player side.
Build B's baton unit tests (`test_rules_ground.py:282-349`) are
REWRITTEN — a deliberate behavior change — not re-pinned.

## The debut content: STAGGERED (the Stun Baton)

Live today: guaranteed −1 current AP per hit, hardcoded
(`_rules_ground.py:443`), no duration, no surface.

Working shape (numbers = the semantics pass):

- `staggered` — debuff, `ap_per_round: -1`, `rounds: 2` (RULED,
  S4), on the ENEMY container (ground) — and, two-sided, on the
  PLAYER container when an enemy wielder connects. The felt
  upgrade: the baton
  stops being a per-hit drain and becomes a real timed condition
  the HUD can show.
- Delivery: the baton carries `status_id="staggered"` +
  `status_chance: 50` (RULED, S4) on its spec.
- The application roll: after the hit resolves, guarded, one draw
  per connecting SURVIVING hit → Stun Baton fights re-pin their
  balance rows same-commit (the crit precedent's discipline).
- The ego seam is victim-side susceptibility (q5): one function
  (`chrome.py`, beside `band`), identity at zero burn, exercised
  in the debut by enemy wielders (below).
- Enemy-side symmetry: staggered on enemies IS the actor-symmetry
  proof — the same container, ticked by `advance_enemy_effects`'
  successor.

**The debut is TWO-SIDED (verified 2026-10-18):** enemies draw
weapons from the same catalog by family — the baton is `melee`
family, tech_level 2 — so tier-2+ melee-family enemies (pirates,
militia) can ALREADY organically come up holding it; today nothing
happens because the AP-drain branch sits in the player's damage
function (`_rules_ground.py:443`). Under the new system the enemy's
fire site rolls application actor-symmetrically: PLAYER wields →
staggered on the enemy (enemy container + HUD suffix); ENEMY
wields → staggered on the PLAYER (player container, the ego seam
EXERCISED — burnt ego raises the player's susceptibility, "full
ego, full resist" feel-able in live play). Build B's playtest
instrumentation: the dev burn dial or a kiosk buy (F7 grants are
burn-neutral by design — `dev_mode.py` calls `install_chrome`,
never `ratchet_install`); playtest reliability of meeting a
wielder = brief row.

Later debuffs (suppression, damage-over-time, disruption — the
chrome-risk family) join as catalog rows on these rails; that
content is NOT this doc's build scope beyond the debut.

## HUD surface (both panels — and the enemy side, ruled open)

A compact status line (RULED one row, q7): per active status, the
spec's terse label + remaining (`STAGGERED 2`, `REGEN 1` —
polarity-colored), read from the container, on both theaters'
player panels (the ground panel has a free row at ~y8 before
WEAPONS, `_ground_render.py:259-291`; `HUD_TEXT_MAX` truncation is
already the pattern). The ENEMY surface (RULED, q7): a status
suffix on the ground enemy panel rows / target card. The existing
regen/temp-AP suffixes stay (they read the same sums now). Strings
prose-gated; CP437-safe.

**The status INSPECT overlay (RULED, q7 — user):** a keypress
opens a scrollable window of current statuses WITH DESCRIPTIONS,
for the player's own container AND for enemies (selection rides
the existing enemy-examine/target flow). Descriptions are a new
prose-gated StatusSpec string field; the keybind fires the guide
contract. Exact key + wiring are Build B brief material.

**The guide row (advisor catch, blocking per the guide contract):
the debut falsifies a LIVE guide entry** — "The Stun Baton reduces
an enemy's AP by 1 on its next turn whenever it hits"
(`data/guide/__init__.py:308-310`). Build B rewrites that entry and
adds the statuses/debuff documentation if the HUD line ships
player-facing — prose-gated, and the edit is called out in Build
B's playtest checklist.

## Phases

- [x] The rulings pass (COMPLETE 2026-10-18 — all 13 open
      questions settled; see the SETTLED section)
- [x] The semantics pass (COMPLETE 2026-10-18 — the tick law, the
      three stacking edges, and the roll-law numbers all confirmed;
      see the Semantics pass section)
- [x] Implementation briefs (APPROVED 2026-10-18: the engine +
      migrations brief and the debut brief, both drafted, advisor
      ADVISE-folded — verdict ADVICE, 16 issues, 6 blocking, all
      folded — and user-approved; budget note verified:
      total-line headroom only, zero oversized functions in
      either touched module)
- [x] Build A: the engine + catalog + the migrations (incl. the
      Pirate opener, q4) — BUILT 2026-10-18 (8 commits: engine +
      catalog + 18 unit pins; ctx home + save wiring; ground
      player-side; enemy-side; opener; space loan; render pin;
      reviewer fix pass — round 1 REQUEST_CHANGES with 2 blockers
      [the expiring heal tick's KeyError + expire-line log order],
      both fixed + minors folded, round 2 APPROVE). Bit-identity
      PROVEN: worktree pre/post balance-report diff EMPTY on every
      deterministic number (31 scenarios; the only moving lines are
      the flight-telemetry crossing-rounds means, run-nondeterministic
      in the PRE tree itself) + the full suite green + unit pins
      rewritten behavior-first with exact numbers preserved. The
      med pack's effect_id renamed restore_hp→regen; the enemy
      instance construction and space position-sync moves paid the
      ratchet in-commit; the opener plumbing lives in
      combat/_opener.py. PLAYTEST PASSED (user, 2026-10-18): the
      checklist read clean — behavior indistinguishable, the HUD
      line reads. Mid-playtest events, both folded same-day: (1)
      the swallowed-keyup input bug (user report: "press c twice in
      a fight", also f after pickers — modal pumps drained SDL raw,
      leaving the opening key stuck in the runtime's held-key set
      so the next press misread as a repeat; one shared
      pygame_runtime.drain_sdl feed + every raw drain routed
      through it, commit 390333bd); (2) the opener's HUD label
      RULED and landed early — OPENER, the label-only fight-class
      row (commit f6874484; the reviewer's fixture-artifact width
      catch folded with it). GUIDE EDITS: none — Build A
      deliberately deferred all guide work to Build B's guide row
      (the decision recorded in the brief; the falsified Stun
      Baton entry rewrites in Build B).
- [x] Build B: the staggered debut (two-sided: player wields →
      enemy staggered; enemy wielder → player staggered) + the
      rolled application + the ego seam (exercised via organic
      enemy baton wielders, q5) + the HUD line + the status
      inspect overlay + the guide row + the dev burn dial; baton
      balance rows re-pinned, baton unit tests rewritten.
      PLAYTEST: the baton staggers sometimes, the enemy wears it
      and shows it, an enemy baton hit staggers YOU and deep burn
      makes it land more (dial or kiosk).
      BUILT 2026-10-18 (8 commits: the prose-gate ledger; the
      staggered row + the status_id/status_chance spec fields + all
      ruled descriptions; the chrome seam; the player fire-site
      roll with the retired id branch deleted + rewritten baton
      pins + the lane_batons re-pin; the enemy fire-site symmetry
      with the pending-damage counter + projection; the surfaces —
      the `v` overlay (Tab cycles subjects, no turn cost), the
      enemy panel suffix + target-card row, the guide edits, the
      card toggle moved to `e` (`i` reserved for inventory, user
      ruling mid-build); the F8 playtest instruments — the burn
      dial + the enemy-baton arming hook). Key build events, all
      folded: the `or-{}` write-orphan on an EMPTY container
      caught by trace (the getattr-None pattern replaces it); the
      conjugated apply subject ("You are"/"X is" — the rendered
      strings stay the ruled ones); the floating card's own
      `[V] hide` hint falsified by the key move (reviewer round 3,
      swept with its pins); the twin-site band_name bug in the
      dial label (round 4). BALANCE: lane_batons re-pinned
      0.94→0.90 fresh-measured (the player-site roll reshuffles
      the stream, the crit precedent's law; the enemy site moved
      nothing — no balance enemy carries a rider);
      mars_batons reads 0.00 at BOTH trees (its bars were retired
      2026-10-04; report-only — pre-existing drift the tuning
      pass owns, verified not this build's). The med pack guide's
      "fully heal outside combat" sentence stands until Build C
      retires the full heal (q12b). PLAYTEST PASSED (user,
      2026-10-19): all five checklist items read clean — the
      two-sided stagger, the refresh, the survivors-only guard,
      the seam's full-ego/deep-burn spread, and the `v` window
      with Tab cycling; no mid-playtest rulings, no fixes.
- [ ] Build C: the durable boundaries — ALL RULED 2026-10-19 (the
      Build C rulings SETTLED section + the Implementation brief
      below, APPROVED 2026-10-19): the
      fight-end defuse flips to field-keyed carry-over (leftover
      regen keeps healing while you explore); the exploration tick
      = DUNGEON TURNS (steps, waits, goto, auto-explore — cities
      outside status time); the transition-removal system replaces
      the smother shape (`removed_on` over {land, board}; landing
      keeps its full heal and removes ALL DEBUFFS by the
      catalog-side default, buffs survive landing, the future fire
      row adds board); the carry surface = the exploration HUD row
      + `v` wired in exploration; the med pack keeps its in-combat
      instant 5 (out-of-combat = the regen only, the full heal
      RETIRES, the full-HP refusal stands; economy watch row).
      Save round-trip of a mid-tick container pinned (the ctx home
      + wiring already landed in Build A). WATCH ROW (reviewer
      round-2 minor, 2026-10-18): the space reset_turn event walk
      still logs expire lines mid-walk — unreachable-divergent
      today, and Build C lands NO space persisting rounds row, so
      the row stays open for the first space content that shares a
      boundary with the loan (not triggered this build). PLAYTEST:
      the brief's seven-item checkpoint (disengage mid-regen and
      keep healing while walking; save/quit/continue mid-tick;
      board with a ground status active; end a fight staggered and
      feel it carry; land and watch the debuff die at the rest
      line; the med pack out of combat regens over steps; the loan
      never bleeds).
- [ ] Close (SYSTEMS.md inventory amended same-commit; move to
      complete/)

## Pre-implementation audit (Build A, 2026-10-18 — written before code)

Every anchor below re-verified against the tree this session (commit
`68bf1b71`). The advisor pass already census-verified the mechanism
table; this audit covers the REUSE map, the duplication traps, and
the build-session's own design decisions where the brief left "exact
modeling" open.

### 1. Existing classes / modules to extend or reuse

- **The catalog idiom**: `data/ground_items/__init__.py` (frozen
  spec + lazy `_BY_ID` + `find_*`/`list_*` raising `KeyError`) is the
  template for `data/statuses.py`; `GroundConsumableSpec.effect_id`
  gains the docstring pointing at `find_status` (tinker exempt,
  beside the `KIT_EFFECT_ID` constant precedent in
  `ground_consumables.py` for id constants).
- **The engine home**: `combat/_statuses.py` follows the pure-module
  pattern of `combat/_stats.py` (deterministic, no ctx). The
  `ActiveStatus` runtime type follows `ActiveConsumableEffect`
  (`ground_consumables.py:58`, retiring) — same field shape idea,
  plus stacks/potency/source/theater.
- **Container declarations** (cohesion law): `GroundEnemyInstance`
  (`_ground_types.py`), `EnemyInstance` (`_types.py`), `GameContext`
  (`game_context.py`, TYPE_CHECKING annotation only — combat imports
  game_context, so the import must stay type-only to avoid a cycle).
- **Save wiring**: `_core_fields`/`_restore_core_fields`
  (`saveload.py:222/:679`) + the chrome empty-backfill precedent at
  `:703`; `_d()` already serializes nested dataclasses recursively —
  the container serializes through entry-level helpers, restore-side
  reconstructs `ActiveStatus` instances (never a bare `data.get`).
- **Adapters**: `_ground_effects.py` keeps its module role —
  `apply_player_effect` / `advance_player_effects` /
  `advance_enemy_effects` / `use_carried_consumable` / `_triggered`
  become engine adapters in place (same names, same homes — the
  doc's "rules adapters apply events" layer).
- **The opener plumbing** reuses `xp.pirate_opener_armed` /
  `_opener_hit_bonus` / `_opener_damage_pct` UNCHANGED (pure, bool
  params — brief item 12) and the `_loop.py:599`
  `mark_opener_spent` hook seam UNCHANGED.
- **HUD**: the ground panel's conditional stim row
  (`_ground_render.py:287-290`) is the pattern for the status row;
  shared formatting lives in `hud.py` per its docstring — but the
  status-line SEGMENT builder cannot live there (`hud.py` cannot
  import combat without a cycle through `combat/__init__`), so the
  pure builder lives in `combat/_statuses.py` and the polarity color
  pair lives in `ui.py` (the single-palette source).

### 2. Duplication hotspots (predicted traps)

1. **Ground vs space event walks** — both theaters walk
   `advance()` events with different apply shapes (gain-fold vs
   twin-field post-reset). The doc RULES the shapes stay distinct
   (`_ground_effects` gain-fold; `_rules_space.reset_turn` inline
   twin-field); homogenizing them into one generic walker is the
   trap the advisor catch 9 exists to prevent — do NOT share.
2. **The opener collective-window logic** — `_opener_flags` exists
   TWICE today (ground `:271`, space `:296`) and the stamp/consume
   sites are three; a per-theater reimplementation of the
   collective all/apply/consume window would be a third copy of one
   concept.
3. **Expire/tick line formatting** — the ruled-line composition
   (source interpolation + the sourceless fallback) is needed by the
   ground adapter now and the space walk for the loan's expire;
   string duplication of ruled prose is the drift trap the
   ruled-strings law exists for.

### 3. DRY strategy per hotspot

1. Event walks stay separate BY RULING (the doc's "never
   homogenized"); the shared part — event tuples + row lookup — is
   the engine's, already single-sourced.
2. **Build decision: NEW `combat/_opener.py`** — the whole opener
   status plumbing in one shared module (`flags(enemies,
   player_container)`, `arm(...)`, `consume_player_window(...)`,
   `consume_enemy_windows(enemies)`, `inherit(joined, enemies)`),
   with thin wrappers in both rules modules. This is also the
   in-commit ratchet split the budget note forecasts for
   `_rules_ground.py` (974 lines, ~+30 of opener/assembly edits
   would cross 1000): the opener window is one cohesive concept,
   currently smeared across `_rules_ground`/`_rules_space`/`_ai`/
   `_ai_ground`/`_ground_blast` — cohesion, not counter-dodging,
   picks this home.
3. **Build decision: the loan's repay line moves canonically to its
   status row** (`data/statuses.py`, constant
   `NEURAL_STIM_REPAY_LINE` — the exact chrome bytes); `chrome.py`
   re-exports it as `STIM_REPAY_LINE` so the ruled-prose home name
   keeps working for every existing importer. One definition,
   bit-identical bytes, no data→runtime import (the catalog stays a
   leaf; chrome reading the catalog is the healthy direction — and
   doc 103's own template law puts expire lines on rows).

### Build-session design decisions (brief's "exact modeling" leaves-overs, recorded before code)

- **Two opener rows, two containers** (brief: "one per container"):
  `pirate_opener` (fight class, PLAYER container — applied at fight
  init iff `pirate_opener_armed(ctx, enemy_fired=False,
  opener_spent=False)`, consumed by `mark_opener_spent`) and
  `opener_window` (fight class, EVERY enemy container — collective
  semantics: init applies to all, any enemy volley/attack/burst
  consumes ALL copies, the read is `enemy_fired = not
  all(enemies hold one)`). The `all()` read makes an empty enemy
  list read window-open (today's fresh-fight default) and dead
  instances staying in the state lists is load-bearing (a death
  never closed today's window).
- **Mid-fight joiners inherit** `opener_window` while the window is
  open: ground `refresh_engaged` and space
  `_space_reinforce._join_reinforcements` both append joiners
  mid-fight — without inheritance a joiner's missing copy would
  read as an enemy volley that never happened (a bit-identity
  break, not a cosmetic one).
- **`ctx.active_statuses` is cleared at BOTH fight inits** (not
  just sync_state): today a new fight means a fresh fight-state
  object (empty ledger by construction); the ctx container
  outlives fights, so init-clear is the faithful mirror, and it
  also covers the abnormally-ended-previous-fight recovery path
  (`_rules_ground.init`'s stale-session branch).
- **`advance` silently skips unknown ids** (like `sum_effects`):
  the KeyError law is authoring-side (`apply`) only; a container is
  saved data and reads of retired ids must skip, not raise.
- **The `dot` vocabulary ships structurally** (`dot_per_round` field
  + `("damage", id, n)` events, synthetic-row unit test) but NO
  adapter damage branch ships in Build A — no row can fire one, and
  the tick-death kill-path clause needs async plumbing that only
  becomes real with the first live damage row (Build B+). Recording
  this as the deliberate line between "vocabulary ships" and "dead
  adapter branch" (the self-audit's own dead-code rule).
- **StatusSpec ships the discretionary-tier fields structurally in
  Build A** (`hit_bonus`/`dodge_bonus`/`melee_bonus` wired at the
  brief's named assemblies; `dot_per_round` event-side) — the brief's
  read-site table wires the terms; no v1 ROW authors them (same
  structural-only status as potency, q8).
- **The med pack's `effect_id` renames `"restore_hp"` → `"regen"`**
  (consumables data edit): hook 13's "`effect_id` resolves against
  `find_status`" + the catalog-resolution pin require the id to BE
  a status id; the string appears nowhere else in src (grep
  verified). The spec's numeric fields (`combat_regen_amount`,
  `duration_turns`…) become descriptive (character-screen detail
  text); the STATUS ROW owns the applied numbers — the catalog law.
- **The HUD line renders only rows carrying `hud_label`**
  (declare-only-what-you-have): `regen` → `REGEN n`, `stim` →
  `STIM n` (both approved by the q7 ruling's example + this brief's
  checkpoint 5); the loan row declines a label (the debt-line
  decline, doc 102 prose ledger). AMENDED at the Build A playtest
  (2026-10-18): the opener row's LABEL is ruled — `OPENER` (user,
  verbatim pick from the offered options); a labelled fight-class
  row renders label-only (its class carries no countdown — the
  build's mechanical consequence, not part of the ruling).
  `opener_window` stays unlabelled (the enemy panel suffix is
  Build B's surface). Reviewer note folded: the row's glyph budget
  is the panel's standard HUD_TEXT_MAX like every sibling row —
  the combat console is one HUD-width wider than the window (the
  ~40 half-width chars), and the render pins build fixtures at
  that real width.

## Implementation brief — Build A: the engine + catalog + the migrations

### Scope (files + hook points)

1. NEW `combat/_statuses.py` — the pure engine: `apply(container,
   status_id, potency=1, source=None, theater=None)` (stacking law:
   refresh default, NEW-WINS metadata, refresh-at-cap; RAISES
   KeyError on unknown ids), `advance(container) -> tuple[
   TickEvent, ...]` (events fire THEN decrement; drops expired),
   `sum_effects(container) -> StatusEffects` (silent-skip on
   unknown ids), `has` / `potency_of` / `consume` / `dispel`. No
   RNG, no logging, no HP/AP writes — ever.
2. NEW `data/statuses.py` — the frozen catalog + `find_status` /
   `list_status`. v1 rows: `regen` (regen_per_round 2, 3 rounds),
   `stim` (ap_per_round +1, 3 rounds), `neural_stim_loan`
   (ap_per_round −1, 1 round, `persists_past_fight=False`), and
   the two `fight`-class opener rows (exact ids follow the doc-49
   trait math at build: one per container, consumed at the
   respective first action). Boundary fields ship STRUCTURAL
   (`crossing="pause"`, `persists_past_fight=True` defaults) — no
   boundary BEHAVIOR until Build C. String templates reproduce
   TODAY's lines bit-identically — copy from CODE, not doc quotes
   (the regen tick line pinned from `_ground_effects.py`; source
   interpolation + the sourceless fallback).
3. `combat/_ground_types.py` — `GroundEnemyInstance.statuses`
   declared; the enemy `stim_turns`/`stim_ap_bonus`/`regen_turns`/
   `regen_amount` fields RETIRED; the opener latch pair removed
   from the ground fight state.
4. `combat/_types.py` — `EnemyInstance.statuses` declared; the
   opener pair removed from the space fight state.
   (`shields_charged` untouched — the retire candidate this doc
   deliberately walks past.)
5. `game_context.py` — `ctx.active_statuses: dict[str,
   ActiveStatus]` declared (the FINAL home, placed now so it
   never moves twice).
6. `saveload.py` — the ctx field wired into `_core_fields` /
   `_restore_core_fields`, empty-dict backfill, through
   entry-level serialize/reconstruct helpers (the container is a
   `dict[str, ActiveStatus]`, not a scalar — the restore side is
   never a bare `data.get`; advisor catch 11; the chrome
   empty-backfill precedent sits at `:703`).
7. `combat/_ground_effects.py` — `ActiveConsumableEffect` +
   `effect_from_spec` RETIRED; advance/read logic becomes engine
   adapters; `_triggered`'s `stim_turns <= 0` read becomes
   `has(container, "stim")` (the one live AI-side status read
   moves WITH the field).
8. `combat/_rules_ground.py` — `reset_turn`: fold `20 ×
   ap_per_round` into the gain BEFORE `_roll_ap`, guard the gain
   at zero (a general fold can go negative — multiple negative
   statuses); hit/melee/dodge assemblies read `sum_effects`;
   fight end DEFUSES the player container (behavior-identical to
   today's evaporation — Build C flips it); the baton branch at
   `:443` UNTOUCHED (Build B deletes it).
9. `combat/_rules_space.py` — `stim_loan_ap` migrates to the
   container with the twin-field POST-RESET application preserved
   (`max(0, ap_total + loan)` / `max(0, ap_remaining + loan)`,
   popped exactly once — the `_rules_space.py:840-844` shape);
   `stim_cooldown` STAYS a cooldown key (q3); the opener flag
   reads become `has()` reads. AND the fight-end DEFUSE (advisor
   catch 4): the container now OUTLIVES the fight, so `sync_state`
   (`_rules_space.py:874-884`) explicitly clears fight-born
   entries — without it a popped loan bleeds −1 AP into the
   player's next space fight.
10. Opener consumption + birth (advisor catches 3/5): the
    implementations are `mark_opener_spent` at
    `_rules_ground.py:455` and `_rules_space.py:465` (`_loop.py`'s
    hook call at `:599` needs NO change) — each consumes the
    player-side opener status. The statuses are APPLIED at both
    theaters' fight init where the trait arms
    (`pirate_opener_armed`, `xp.py:332-338` — positive modeling:
    window-open statuses from fight construction; reads at the
    `_opener_flags` sites `_rules_ground.py:271-278` /
    `_rules_space.py:296-303`).
11. `combat/_ai.py` + `_ai_ground.py` — the `enemy_fired` stamp
    sites (`_ai.py:791,843`, `_ai_ground.py:611`) consume the
    enemy-side opener status.
12. `xp.py` — signatures UNCHANGED (pure, bool params); the call
    sites (`_rules_ground.py:278,359,420`, `_rules_space.py:303,
    314,355`, `_ground_blast.py:164`) compute the pair from
    `has()` and pass bools.
13. `data/ground_items/__init__.py:50` — `GroundConsumableSpec.
    effect_id` resolves against `find_status` (tinker exempt).
14. HUD (the migration-observable slice): the player one-row
    status line on the ground panel (`_ground_render.py`, the
    free row ~y8 before WEAPONS) + the space panel twin in
    `hud_combat.py` (its `stim_cooldown` read at `:144` stays —
    cooldowns keep their homes); the existing regen/temp-AP
    suffixes re-derive from `sum_effects` (same output). The
    inspect overlay is Build B. GUIDE (advisor catch 12): the
    statuses documentation is DEFERRED to Build B's guide row —
    this brief records the no-change decision per the contract.

### Build order

engine + catalog + unit tests (pure, unwired) → ctx field + save
wiring (empty backfill) → ground player-side migration (med pack,
stim, loan) + assemblies + the HUD line → enemy-side migration
(carriers + the trigger read) → the opener migration (both
theaters) → the space loan migration. Each retirement rides ITS
OWN migration commit (atomic discipline — no terminal dead-code
sweep; advisor ordering note) → bit-identity proofs + full gate.

### Binding rulings

Bit-identical, ZERO new draws (the engine is RNG-free; every
today-string reproduced from code). S1/S2/S3 laws (tick order,
new-wins, refresh-at-cap). Fight end defuses the PLAYER container
(C flips). Enemy containers fight-scoped, never serialized.
`apply` raises on unknown ids; `sum_effects` silently skips them.
Polarity never forks logic. The cohesion law owns every new field
(GameContext + both instance types, declared in their homes).
BUDGET NOTE: `_rules_ground.py` (974 lines) and `_rules_space.py`
(966) each sit one touched-file growth from the in-commit
extraction ratchet — the build pays the split in-commit, per the
gate's law. (Advisor-verified refinement: ZERO functions over 40
lines in either module — the exposure is total-line headroom
only; `_ai.py` is also touched at 954 lines with line-neutral
consume changes.)

### Required tests

Engine unit tests same-commit: apply/advance/sum_effects +
the ACTOR-SYMMETRY pin (the same tests drive a player-shaped and
an enemy-shaped container); the S1 pins (3-tick regen, 1-tick
loan, same-boundary refresh never double-ticks); the KeyError /
silent-skip pair; new-wins + refresh-at-cap. The
representation-coupled pins are REWRITTEN same-commit, behavior
assertions preserved (advisor catch 7):
`test_ground_consumables.py` (reads `active_consumable_effects`
directly), `test_ground_tactics.py` (constructs the retiring
enemy fields), `test_core_button.py` (reads the loan keys),
`test_enemy_fire.py` + `test_class_traits.py` (opener window
semantics). NEW catalog-resolution pin: every non-tinker
`effect_id` resolves via `find_status` (advisor catch 8).
Worktree pre/post FULL-suite harness diff (advisor catch 2: NO
pirate-class player exists in the scenarios — the opener has no
dedicated rows; the full suite organically covers the stamp
mechanics and carrier rolls through seeded init). Save
round-trip: empty container backfill + a mid-fight container
(unchanged: defused), through the entry-level helpers.

### Stop point

No staggered / baton changes (Build B). No boundary flips — no
carry-over, crossing, exploration ticks (Build C). No inspect
overlay (Build B). No prose beyond today's strings. No potency
keying.

### Playtest checkpoint

1. Med pack in combat: same log lines, same +2/round × 3; a
   re-drink resets duration.
2. Combat stim: +1 AP/round same; the core-button loan −1 next
   round same (both theaters).
3. An enemy stim/regen carrier: same behavior, same trigger
   timing.
4. A Pirate opener fight: the opener bonus is identical.
5. The HUD status line reads REGEN n / STIM n correctly; enemy
   suffixes unchanged.
6. The Stun Baton behaves EXACTLY as today (guaranteed instant
   −1 AP, no roll).
7. Save/quit/continue: clean, no status residue.

## Implementation brief — Build B: the staggered debut

### Pre-build gate (prose)

ALL new strings settle through the prose loop BEFORE any land:
staggered apply/expire lines, the HUD label, the inspect
overlay's title + per-status descriptions (staggered, regen,
stim, the loan), both guide edits. A build session never authors
unapproved strings. (The opener's HUD label settled EARLY at the
Build A playtest, 2026-10-18: OPENER — landed with the
label-only fight-class row shape; not re-litigated here.)

### Scope (files + hook points)

1. `data/statuses.py` — the `staggered` row (debuff,
   ap_per_round −1, duration 2, refresh).
2. `GroundWeaponSpec` + `data/ground_weapons/melee.py` — new
   `status_id: str = ""` + `status_chance: int = 0` fields (the
   instant-rider family's first lingering member); the baton
   carries staggered / 50.
3. `combat/_rules_ground.py` — DELETE the `:443` hardcoded
   branch; after the hit resolves (guarded `chance > 0`, victim
   survives) roll ONCE → `apply` to the enemy container; log per
   the ruled templates.
4. `combat/_ai_ground.py` `_resolve_enemy_shot` (`:663-690`) —
   the symmetric site (melee and ranged resolve at the SAME
   site, via `_melee_reach_pick` → `_fire_the_pick` →
   `_fire_enemy_burst` → `_one_enemy_shot`; the `if _hit:`
   knockback branch at `:686` is the existing on-hit-rider
   template): the enemy's connecting hit rolls the same guarded
   law → `apply` to `ctx.active_statuses` THROUGH THE SEAM.
   SURVIVORS-ONLY MECHANISM (advisor catch 1, blocking): player
   HP is applied per enemy TURN at `_apply_enemy_hit`
   (`_rules_ground.py:734-744`), so the roll site cannot see
   survival — add a per-turn accumulated-damage counter on
   `GroundCombatState` (declared in `_ground_types.py` per
   cohesion; set/cleared by `_spend_one_enemy_turn`), read by a
   projection helper (`player_hp − turn_damage − this_hit > 0`)
   at the roll. Draws are never refunded (kill-draws); hooking
   `_apply_enemy_hit` instead would break the per-hit draw law
   (per-turn roll; `_dmg > 0` only approximates "connected" — DR
   can zero a landed hit).
5. `chrome.py` — the seam beside `band`:
   `status_chance_adjusted(base, victim_band)` — identity at
   band 0, +10/+20/+30 at bands 1/2/3 (S4). Pure, unit-pinned.
6. The enemy round reset folds staggered at
   `_rules_ground.py:891-893` — a DIRECT ADD (`_gei.ap =
   _gei.ap_total + advance_enemy_effects(_gei)`), NOT the
   player's gain-fold; a negative fold takes its own
   `max(0, ...)` guard; the distinct shapes stay distinct, never
   homogenized (advisor catch 9 — same law as the loan ruling).
   A dead actor skips its reset (the tick-death clause).
7. HUD: the enemy panel rows + target card gain the status
   suffix; the player line (shipped in A) shows STAGGERED n.
8. The inspect overlay: a scrollable status window (name,
   remaining, description) — player container directly, enemies
   via the existing examine/target flow. Keybind = build row:
   sweep the live keymap for a free key, propose WITH the prose.
9. `data/guide/__init__.py` — REWRITE the falsified Stun Baton
   entry (`:308-310`); add the statuses + inspect-key
   documentation. Both edits called out on the playtest
   checklist.
10. Playtest instrumentation: a dev burn dial (dev_mode.py — F7
    stays burn-neutral; the dial explicitly ratchets) OR the
    kiosk path, ruled at build; plus an enemy-baton arming hook so
    "an enemy staggers me" is reliably encounterable.
11. `tests/combat/test_rules_ground.py:282-349` — the baton unit
    tests REWRITTEN (deliberate behavior change): the 50 roll
    (seeded), duration 2, survivors-only, refresh, the four-band
    seam pins.

### Build order

prose gate first → spec fields + the staggered row → the player
fire-site roll + branch deletion + rewritten unit tests → the
seam + the enemy-site symmetry → HUD suffix + inspect overlay +
guide → the dial + the arming hook. RE-PINS RIDE THE
DRAW-CHANGING COMMITS (advisor catch 6, blocking: the balance
gate is inside `make check` — the moment the player-site roll
lands, the baton rows (`scenarios.py:353,467`) trip and every
later commit sits gate-red; re-pin in THAT commit, and again for
the enemy-site commit; fresh measurement, cause noted).

### Binding rulings

One draw per connecting SURVIVING hit, direct fire only
(missiles/blasts never roll application — their arrivals call
`resolve_damage` bare). Killing hits never roll. Fights without a
chance-carrying weapon consume ZERO new draws. The seam is the
ONLY ego read (victim-side, band-keyed, identity at band 0 — S4).
Staggered on the player DEFUSES at fight end in Build B
(carry-over is Build C). AP arrives at the victim's next round
reset, not instantly — the felt upgrade, a deliberate behavior
change (the baton goes from instant drain to a timed condition;
the balance re-pins own the delta).

### Required tests

The rewritten baton pins; the seam unit pins (four bands +
identity); the survivors-only guard; the zero-draw pin (no
chance-carrier → stream unchanged); the enemy-site symmetry pin;
`make check` + reviewer REVIEW.

### Stop point

No carry-over / crossing / exploration ticks (Build C). No new
statuses (suppression / DOT / disruption are later catalog rows).
No slope re-tuning beyond S4. No AoE application (its own future
ruling).

### Playtest checkpoint

1. Wield the baton: connecting hits stagger enemies about half
   the time; a staggered enemy wears the suffix; its next TWO
   round-starts each lose 1 AP (not instant).
2. Re-hits while staggered refresh the duration, never stack.
3. Killing hits stagger nothing.
4. An enemy baton wielder (the arming hook) staggers YOU: the
   player line shows STAGGERED n, your next resets dip; deep
   burn (dial/kiosk) pushes application toward 80 at band 3;
   full ego holds the base 50.
5. The inspect window opens for you AND for an enemy; the
   descriptions read; both guide entries are correct (the baton
   rewrite + the statuses/key).

## Pre-implementation audit (Build B, 2026-10-18 — written before code)

Every anchor below re-verified against the tree this session (commit
`92623186`, post-Build-A). Build A's audit covers the engine/catalog
layer Build B builds ON; this one covers the debut's own ground: the
two fire sites, the seam, the HUD/overlay surfaces, the instruments.

### 1. Existing classes / modules to extend or reuse

- **The engine needs NOTHING** — `apply` (refresh law), `advance`
  (the AP event + expire), `sum_effects`, `hud_segments` all serve
  staggered as-is: the debut is a ROW plus adapters, exactly the
  acceptance bar. The staggered row joins `data/statuses.py` with
  `ap_per_round=-1`, `duration=2`, `polarity=False`, prose-gated
  `apply_line`/`expire_line`/`hud_label`/`description`.
- **The guarded-roll precedent**: `_stats._roll_crit`'s law (zero
  chance → zero draws) is the template; the application roll is
  `RNG.randint(1, 100) <= adjusted` at the fire sites, drawn only
  when `status_chance > 0` AND the victim survives.
- **The on-hit-rider template**: `_ai_ground._resolve_enemy_shot`'s
  `if _hit: _apply_hit_knockback(...)` branch — the enemy-side
  status tail lands beside it (knockback first, then the roll: the
  displacement is wordless, the status speaks).
- **The seam's home**: `chrome.py` beside `band` —
  `status_chance_adjusted(base, victim_band)`, pure, banded
  (+10/band from band 1, +30 cap). The victim-band read at the
  enemy site is `base_band(ctx)` (the victim's OWN burn;
  `local_band` stays out — susceptibility is not the port's
  business). The player→enemy direction passes band 0 (q5: only
  the player gets burnt ego — no is-player branch, the seam stays
  victim-keyed).
- **The enemy reset already folds staggered** (Build A's generic
  law): `reset_turn`'s direct add + `advance_enemy_effects`' ap
  fold need NO staggered-specific code; Build B adds only the
  dead-skip guard (the adapter contract's tick-death clause —
  observably neutral today, load-bearing the day a dot row lands).
- **HUD**: the player line ships (`hud_segments` +
  `_render_status_row`); the enemy suffix joins the panel name rows
  (`_render_enemies_panel`) and the target card
  (`_ground_presentation.enemy_detail_lines` /
  `_ground_card_rows`), both REUSING `hud_segments`'s row walk.
- **The overlay's vehicle**: `pygame_screen.ScreenFrame(
  scrollable=True)` via the `console_log.open_console_log` pattern
  (rebuild-and-reopen while-loop); the combat wiring point is
  `_loop._handle_meta_action`'s HISTORY shape — opens, costs no
  turn, returns.
- **Dev instruments**: `dev_mode.py`'s picker pattern
  (`_run_pygame_menu_pick` + `ui.MenuScreen`, the F7 chrome
  precedent) carries both the burn dial and the arming toggle; the
  arming hook lands at `_ground_build._build_enemy_instance`
  (post-`ensure_loadout`, rewrite the melee pair under the flag —
  both init and mid-fight joins route through it).
- **Guide**: `data/guide/__init__.py`'s melee bullet (the falsified
  baton sentence) rewrites in place; the statuses + key
  documentation joins the guide near the combat text.

### 2. Duplication hotspots (predicted traps)

1. **The two application-roll sites** — player `damage()`'s tail
   and `_resolve_enemy_shot`'s tail run the SAME law (guard →
   seam → roll → apply → log). Two hand-copied blocks would fork
   the draw guard and the seam read on day one.
2. **The survivors-only projection** — the pending-damage
   bookkeeping touches the shot tail, the shared hit tail, and the
   state field; any second "will the player die" read (or an
   increment without its drain) double-subtracts and silently
   skips legal rolls.
3. **Status formatting drift** — enemy panel suffix, target-card
   line, and overlay rows all render "(label/name, remaining)";
   three hand-rolled formatters drift (the `hud_segments` law
   exists to prevent exactly this).

### 3. DRY strategy per hotspot

1. ONE shared adapter helper in `_rules_ground`
   (`_apply_hit_status(ctx, container, weapon_id, source_label,
   victim_label, victim_band, victim_survives)`) — both fire sites
   call it; `_ai_ground` already lazy-imports `_rules_ground`
   (the `_fire_enemy_burst` precedent). The seam call, the draw
   guard, and the apply/refresh log decision live once.
2. ONE counter, ONE drain: `GroundCombatState` gains the
   per-turn pending-damage field; `_resolve_enemy_shot`'s tail
   PENDS its returned damage; `_apply_enemy_hit` DRAINS what it
   applies. This refines the brief's "set/cleared by
   `_spend_one_enemy_turn`" to cover the REACTION VOLLEY too
   (verified: `_ground_flee.reaction_volley` applies per SHOT
   through the same `_apply_enemy_hit`, while the enemy turn
   applies the per-TURN total — a turn-scoped-only counter would
   go stale during the volley and double-subtract). The projection
   helper sits beside `_apply_enemy_hit`.
3. `hud_segments` IS the formatter: the enemy suffix paints its
   segments after the name (same `paint_hud_segments` ink, bound
   to the panel edge); the card line and the overlay rows derive
   from the same walk (the overlay reads `spec.name` +
   `description`, not the label — it is the reader, not the glyph
   budget).

### Build-session design decisions (brief's "ruled at build" rows, recorded before code)

- **The instrumentation ruling: the DIAL, not the kiosk** — a dev
  picker that SETS `ctx.ego_burn` to a representative value per
  band (Natural 0 / Tainted 5 / Chromed 9 / Psycho 13), because the
  playtest needs quick band flips mid-session; the Terminus kiosk
  stays the organic economy path and F7 stays burn-neutral
  (`install_chrome`, never `ratchet_install`). Both instruments
  live behind ONE new dev key (F8 — F3/F5/F6/F7/F9 are taken, F4
  is reserved by window managers): a small "playtest instruments"
  picker with the burn dial + the enemy-baton arming toggle.
- **The arming hook shape**: a dev flag (default off) that makes
  `_build_enemy_instance` rewrite the loadout stamp's melee pair
  to `stun_baton` — every enemy built while the flag lives wields
  one (init AND mid-fight joins), so "an enemy staggers me" is
  reliably encounterable without touching any content pool.
  (AMENDED at the build: the hook landed at the two ENGAGED build
  sites — `init` + `refresh_engaged`, via the shared
  `_arm_dev_batons` helper — not inside `_build_enemy_instance`;
  the third build site (stare-eruption zone victims,
  `_ancients._cell_victims`) never joins the fight, and arming it
  would rewrite bystanders' persisted stamps and drop payloads.
  Reviewer round 4 endorsed the as-built cut as the better shape.)
- **The overlay's wiring**: `i` (free in the combat map — swept:
  not an action key, not movement, not wait, not a weapon number;
  `e`/`g`/`m`/`o`/`p`/`t`/`z` also free, `i` wins on mnemonic).
  `i` opens the scrollable frame on the PLAYER's container; TAB
  inside cycles the subject (you → alive enemies in panel order →
  you — the target-cycle muscle memory, per "selection rides the
  existing enemy-examine/target flow"); ESC closes; costs no turn
  (the HISTORY shape). Handled in the SHARED `_handle_meta_action`
  so both theaters get the self-inspect (the loan is space-live);
  enemy subjects come from `rules.get_enemies(ctx)` — no theater
  branch.
- **The apply line's subjects**: the template interpolates
  `{victim}` (pre-cased by the site: "You" / the enemy's name);
  `{source}` stays available but the drafted line is
  victim-anchored (an object-anchored "Stun Baton staggers you!"
  personifies the weapon — prose tell 4). The line logs on every
  LANDED roll, fresh apply or refresh (the refresh is honest
  feedback; the countdown visibly resets).
- **The expire line logs player-side only** — `advance_player_
  effects` already logs the row's `expire_line` after the walk
  (zero new adapter code); the enemy adapter stays silent (Build
  A's law), the suffix's disappearance is the enemy-side signal.
- **The staggered suffix shape**: the enemy panel name row and the
  target card both carry the SAME segments the player line renders
  (`STAGGERED 2`), polarity-colored — one row walk, three
  presentations.

## Build B prose ledger (2026-10-18 — every string settled through the loop; silence never read as acceptance)

| # | Surface | Ruled text | Verdict |
|---|---|---|---|
| 1 | staggered apply_line (combat log, every landed roll, fresh or refresh; `{victim}` pre-cased by the site) | `{victim} is staggered!` — rendered "You are staggered!" / "Rock Scavenger is staggered!" (mechanical amendment at the enemy-site build: the placeholder carries the conjugated subject — "You are" / "X is" — template `"{victim} staggered!"`; the RENDERED strings are the ruled ones bit-identical, "You is" never was) | Ship it |
| 2 | staggered expire_line (combat log, PLAYER-side only — the enemy adapter stays silent, the suffix's disappearance is the signal) | `The stagger wears off.` | Ship it |
| 3 | staggered hud_label (player status line renders `STAGGERED 2`; same label rides the enemy panel name-row suffix + target card) | `STAGGERED` | Ship it |
| 4 | inspect overlay title (scrollable frame header; TAB cycles subjects) | `STATUSES - YOU` / `STATUSES - {NAME}` | Ship it |
| 5 | staggered description (overlay) | `-1 AP per round.` | My edit |
| 6 | regen description (overlay) | `+2 HP per round.` | Ship it |
| 7 | stim description (overlay) | `+1 AP per round.` | Ship it |
| 8 | neural_stim_loan description (overlay) | `-1 AP next round.` | Ship it |
| 9 | opener descriptions (overlay; added beyond the brief's list — bare rows read broken) | pirate_opener: `+10% hit and +25% damage on your first attack this fight.` / opener_window: `No enemy has fired yet.` | Rewrite w/ direction (direct detail, ruled numbers from xp.py) |
| 10 | guide: the Stun Baton entry rewrite | `The Stun Baton has a 50% chance to stagger on hit. A staggered victim gets -1 AP per round for 2 rounds.` | My edit (refresh clause dropped: "the status refresh will teach itself") |
| 11 | guide: the statuses paragraph (new; ruled "closes the Combat section" — placement AMENDED at the build: Combat sat at 2991 chars and the paragraph would breach the guide's 3000-char conciseness bar, so it ships as its own `Statuses` GuideSection directly after Combat; the ruled TEXT is bit-exact including 12a's "Press V") | `Statuses are timed effects on a combatant, shown on the right-hand panel (REGEN 2, STAGGERED 2). Enemy statuses display beside their names. Press V in combat to open the status window; Tab inside switches between you and each enemy. Burnt Ego makes you more susceptible to status ailments.` | My edit (two sentences; "their" typo fix confirmed by the user same exchange) |
| 12 | inspect keybind | `I` (free in combat + exploration; Tab inside cycles subjects) | ruled |
| 12a | inspect keybind AMENDED mid-build (user, 2026-10-18: "i... feels more like inventory -- I could see maybe using it for inventory") | `V` = the status window ("view"); the floating target-card toggle MOVES to `E`; `I` reserved for a future inventory shortcut. Guide consequences: ledger #11's "Press I" becomes "Press V" (mechanical), and the two shipped card sentences ("Press V to hide it and V again to bring it back") rewrite to E — both called out on the playtest checklist | ruled |
| 13 | the status window's empty state (settled mid-build through the loop; the row recorded same-commit per the e9f805b7 precedent) | `No statuses.` | Ship it |

Direct register ruling (user, #5): descriptions are sign + number +
unit + cadence, nothing else. Guide register (#10): lead with the
direct fact (the chance), then the flat numbers.

## SETTLED — the Build C boundary rulings (2026-10-19)

Four rulings through the question loop; all fold into the brief
below. Every code anchor verified against the tree this session
(commit `6fd2b374`, post-Build-B).

### The exploration tick: DUNGEON TURNS (cities outside status time)

One completed dungeon/interior turn = one status tick — movement
steps, waits, goto, and auto-explore all tick (the one shared seam
`game_flow._dungeon_post_move_tick:383` already equates them for
NPC movement; a wait is not free pre-buffing time). CITIES are
outside status time: the hub's STREETS freeze your statuses —
nothing threatens you there, and the freeze is what lets a
staggered survive the walk to the landing pad, making the
board/land playtest reachable. City INTERIORS tick (bars,
showrooms — they are dungeon-mode maps dispatching through the
same seam; the ruling's own "dungeon/interior turn" wording). The
hook fires at the TOP of the seam, before the combat check — the
step happened; a fight the step starts then continues the ticking
at its own round boundaries. ADVISOR CATCH (2026-10-19, folded):
tick-site placement alone does NOT enforce the pause — the space
round walk (`_rules_space.reset_turn:865-872`) advances the same
container with no filter, so a carried ground row would tick (and
staggered's −1 AP would bleed onto the SPACE AP fields) on the
first space round after the defuse flip. The home-theater law is
therefore ENGINE-enforced: `advance` takes the theater and skips
mismatched rows (advisor-endorsed shape — one live read,
centralized; `theater` is serialized today, `saveload.py:247`, so
a mid-flight save/quit/continue preserves the filter's input).

### The transition-removal system (user ruling, verbatim)

"Currently when you land on a planet you are fully healed. I think
landing on a planet should remove all debuffs. But also, some
debuffs should be removed in other cases, like transitioning to
space. I feel like we could make a generic system that lets us
define which buffs/debuffs are removed during which transitions?
Then we use that system in the future to add on fire debuff being
removed when entering ship in addition to the default land on a
planet to heal/remove debuff"

- Statuses declare WHICH transitions remove them:
  `removed_on: tuple[str, ...]` — replacing q11's `crossing` enum
  pre-first-live-read (nothing ever read it; the field is
  catalog-side, so no save carries it — a free swap). The v1
  vocabulary: `"land"` (the landing rest seam —
  `_enter_city_landing`'s heal block at `:402-405`, the
  production path via `_resolve_planet_land` —
  the landing full heal STAYS, the user named it approvingly) and
  `"board"` (the launch-to-space seam, `_launch_owned_ship`'s
  success path at `:487`). No v1 row authors "board" — the future
  fire debuff is the first, and it lands with land-removal free
  via the default.
- **Landing removes ALL DEBUFFS by default; buffs survive
  landing.** The default is stamped CATALOG-side — every
  polarity=False row carries "land" — so the engine never forks on
  polarity AND a forgotten debuff row still reads removed (regen
  and stim pause through the flight and resume on the ground;
  staggered dies at the rest line). An explicit opt-out (a future
  curse that survives land) joins when content wants it — a named
  limit, not authored now.
- Removal is SILENT (dispel semantics — no expire events, no
  lines; the HUD row's disappearance is the signal, the enemy-side
  law's twin). Non-removed statuses PAUSE through the crossing
  (q11's standing half): ground statuses simply stop ticking while
  you fly, resuming in the next ground theater.
- The seam inventory (advisor-corrected 2026-10-19): land =
  `_enter_city_landing`'s heal block
  (`game_interactions.py:402-405` — the production path via
  `_resolve_planet_land`; the dev teleport `land_at_city` delegates
  into it, so one wiring covers both); board = the launch success
  path (`_launch_owned_ship`, `:487`) AND the dungeon-exit-to-space
  flip (`game_flow._handle_dungeon_exit:874-906`, adopted at
  `game_loop.py:650-657` — exiting a derelict/salvage interior is
  the most common way the player re-enters the ship, and a future
  fire row surviving THAT exit is the exact scenario the
  vocabulary exists to prevent — advisor catch 3, blocking). The
  flee adoptions (`space_flee.py:53-68`) and the capture-boarding
  path (`_adopt_capture_boarding`) are NOT land (no rest, no heal
  today) — new transitions are future rulings, never silent
  additions. The capture edge is recorded: a capture interior IS
  ground theater, so paused ground statuses resume ticking inside
  a capture fight (consistent with home-theater ticking; no
  special handling).

### The carry surface: v + the exploration HUD row

The exploration ground panel gains the same one-row status line
the combat panels carry (REGEN 2, STAGGERED 1 — polarity-colored),
and `v` opens the inspect overlay while exploring (a you-only
subject; no enemies exist to cycle out of combat). The q7 one-row
law extended to the surface where the carry lives.

### The med pack: the in-combat instant 5 KEPT

q12b's retirement names the instant FULL heal (the out-of-combat
one); the in-combat shape (5 now + regen 2×3, Build A's
bit-identical migration) stands untouched. The out-of-combat use
becomes the regen status only (+6 over steps). The out-of-combat
full-HP refusal ("Ground HP is already full.") STAYS — waste
protection; q12b's "regen at max HP is a no-op" describes the tick
clamp, not the use gate.

## Pre-implementation audit (Build C, 2026-10-19 — written before code)

### 1. Existing classes / modules to extend or reuse

- **The engine needs `advance`'s theater filter plus two small
  helpers**, all pure and unit-pinned: `advance(container,
  theater=...)` (skip mismatched rows — the home-theater law made
  mechanical; advisor catch 1), `defuse_at_fight_end(container)`
  — the field-keyed predicate (fight-class rows +
  `persists_past_fight=False` rows, AND unknown ids DROP: a
  retired row can never resolve a spec, so it defuses — immortal
  save-carried garbage is the one behavior the silent-skip read
  contract must NOT extend to the defuse; advisor catch 7) — and
  `remove_at_transition(container, transition)` — the
  `removed_on` read. No engine polarity read anywhere: the debuff
  default is catalog-side.
- **The exploration adapter's home**:
  `combat/_ground_effects.py` (the adapter family home, 251 lines
  — headroom): `advance_exploration_statuses(ctx)` applies heal
  events to `ctx.ground_hp` clamped at the REFRESHED max (the
  ground-max-HP staleness law — `xp.refresh_ground_max_hp` before
  clamping), DROPS ap events (no AP pool exists out of combat),
  and logs tick/expire lines per the adapter contract (tick lines
  only on healed > 0; the staggered expire line reads while
  exploring; the stim/regen expire silently — they decline
  expire lines).
- **The tick seam**: `game_flow._dungeon_post_move_tick (:383)` —
  shared by the dungeon move, wait, goto, and auto-explore paths
  via the `post_step_tick` threading. Hook at the top, before
  `_run_ground_combat_tick`.
- **The transition seams**: land = `_enter_city_landing`'s heal
  block (`game_interactions.py:402-405`, the production path via
  `_resolve_planet_land`; the dev teleport's `land_at_city`
  delegates into it — advisor catch 4's anchor fix) and board =
  the launch success path (`:487`) PLUS the dungeon-exit-to-space
  flip (`game_flow._handle_dungeon_exit:874-906`, adopted at
  `game_loop.py:650-657` — advisor catch 3).
- **The four defuse sites to flip**: `_rules_ground.sync_state`
  (`:932`) + `_defuse_stale_session` (`:116-129`); `_rules_space`
  init (`:130`) + sync (`:911`). All four call the shared engine
  helper — carried statuses then survive fight init AND the
  abnormal-end recovery path (the q13 law: you keep your burns).
- **The consumable seam**: `ground_consumables._use_outside_combat`
  (`:69-78`) + the spec field rename sweeping
  `character_screen.py:352` and the spec docstring (the
  every-consumer law — but NOT a mechanical rename at the screen:
  the detail-text branch uses the field to choose its FORMAT
  (`if outside_full_heal:` HP text `elif combat_ap_bonus:` AP
  text), and both items carrying True post-re-scope would render
  the stim as "+0 HP" — the branch re-keys on `combat_ap_bonus`
  first or on `effect_id`, and the changed detail text is
  player-facing, prose-gated; advisor catch 2, blocking). The med
  pack's in-combat path (`apply_player_effect`) is UNTOUCHED.
- **HUD**: `hud.py`'s ground exploration panel — the lazy-import
  precedent (`bandolier_hud_lines`, `:279-286`) solves the
  combat-cycle law for `hud_segments` / `paint_hud_segments`
  (function-body import; the Build A audit's cycle finding stands
  for module level).
- **`v` in exploration**: the exploration handler
  (`game_loop._handle_non_movement_event:517`) dispatches;
  `status_inspect` needs a you-only entry (its current signature
  takes a live `rules` for enemy subjects — none exist out of
  combat).
- **Guide**: the two falsified sentences at
  `data/guide/__init__.py:337-343` (med pack "fully heal outside
  combat… In combat they restore 5 HP immediately…"; stim "cannot
  be used while exploring").

### 2. Duplication hotspots (predicted traps)

1. **Four defuse sites hand-rolling four predicates** — the
   field-keyed law must not fork per theater (the exact drift the
   shared-helper law exists for).
2. **The exploration adapter vs `advance_player_effects`** — both
   walk events and compose ruled lines; copy-pasting the line
   composition is the ruled-prose drift trap (hotspot 3 from
   Build A's audit, back for the third time).
3. **Two transition seams growing bespoke removal loops** — each
   seam must be ONE call to the engine helper, never its own
   iteration.

### 3. DRY strategy per hotspot

1. ONE engine helper (`defuse_at_fight_end`); the four sites each
   become a one-line call (also the line-neutral shape the
   999-line `_rules_space.py` budget needs).
2. The tick/expire line composition extracts to a shared
   `_ground_effects` helper both adapters call — the APPLY shapes
   stay three DISTINCT laws (gain-fold in combat, twin-field
   post-reset in space, direct clamp at the refreshed max while
   exploring; the never-homogenize ruling).
3. `remove_at_transition` is the single iteration; the vocabulary
   is one constant beside the rows (`data/statuses.py`).

### Build-session design decisions (recorded before code)

- **The catalog-side debuff stamp**: `removed_on` defaults to
  `("land",)` for polarity=False rows via a construction-time
  stamping pass beside `STATUSES` — the engine stays
  polarity-blind and a forgotten debuff row still reads removed
  at land (fail-open; an explicit-authoring shape was considered
  and declined — its forgotten-row failure mode is the WRONG
  default). Recorded semantics (advisor catch 6): the stamp UNIONS
  with explicit authoring (the fire row's future
  `("land", "board")` never duplicates); the survive-land opt-out
  joins as an explicit named field the day content wants it (a
  documented sentinel, not accidental); and the stamp is the
  tree's FIRST polarity-keyed behavioral default — it lives at
  the catalog construction site, and every READ site stays
  polarity-blind (the presentation-only doctrine holds where it
  always applied).
- **`theater` goes LIVE in Build C** (advisor catch 1, blocking —
  the structural-only plan was falsified by the tree): the space
  round walk advances the shared container with no filter, so
  placement-only pause fails the moment the defuse flip lets a
  carried ground row reach it. `advance(container, theater=...)`
  skips mismatched rows; every advance site passes its theater
  (the ground walk, the exploration adapter, the space walk). A
  None tag matches every theater (legacy-proof; today's applies
  always stamp). This also settles `saveload.py:229-234`'s
  deferred boundary comment.
- **Board fires with zero removals in v1**: one live call through
  the live handler at the launch seam — symmetric and generic,
  not dead code (the handler is live at land; the call site makes
  the system real for the fire row's future authoring).
- **The full-HP refusal stays** (flagged default at the ruling
  batch; the brief approval is its gate).
- **No new draws anywhere**: the exploration tick applies
  deterministic events (the engine is RNG-free), transitions are
  drawless dispels, the consumable rewrite applies statuses
  without rolls (consumables ship 100%, q6). The worktree pre/post
  harness diff should read IDENTICAL — run it as insurance,
  expect zero moved rows, and investigate any that move.

## Implementation brief — Build C: the durable boundaries (APPROVED 2026-10-19 — drafted, advisor ADVISE-folded (verdict ADVICE, 9 issues, 3 blocking, all folded), user-approved)

### Pre-build gate (prose)

The two falsified guide sentences (med pack, stim) rewrite through
the prose loop BEFORE any land; the Statuses section's "Press V in
combat" amends (v becomes usable while exploring). The stim's
character-screen DETAIL TEXT changes with the branch re-key
(player-facing, prose-gated — advisor catch 2). Retiring strings
are called out on the checklist; verify the "can only be used in
ground combat" line's remaining gated items (the tinker kit
stays) before retiring it.

### Scope (files + hook points)

1. `data/statuses.py` — `crossing` RETIRED; `removed_on:
   tuple[str, ...] = ()` + the catalog-side debuff stamp (every
   polarity=False row carries "land") + the transition vocabulary
   constant.
2. `combat/_statuses.py` — `advance` gains the THEATER filter
   (`advance(container, theater=...)` skips mismatched rows; None
   matches every theater); `defuse_at_fight_end(container)`
   (fight-class + loans + UNKNOWN IDS drop) and
   `remove_at_transition(container, transition)`: dispel-based,
   silent, pure, unit-pinned.
3. `combat/_rules_ground.py` — `sync_state` (`:932`) and
   `_defuse_stale_session` (`:126-129`) call the shared helper
   (the inline dispel-all goes); the ground round walk passes
   `theater="ground"`.
4. `combat/_rules_space.py` — the init (`:130`) and sync (`:911`)
   sites, same; the space round walk (`:865-872`) passes
   `theater="space"` (a carried ground row FREEZES there — the
   pause made mechanical; advisor catch 1, blocking). BUDGET
   NOTE: 999 lines — the theater filter ADDS lines here, so the
   build REALISTICALLY trips the 1000 ratchet and pays the
   in-commit split as the EXPECTED path (advisor catch 8), not a
   fallback.
5. `combat/_ground_effects.py` — `advance_exploration_statuses
   (ctx)` (passes `theater="ground"`) + the shared tick/expire
   line-composer extraction.
6. `game_flow.py` — the hook call at the TOP of
   `_dungeon_post_move_tick` (988 lines — thin headroom; a 1-2
   line call fits, nothing else joins this module).
7. The transition wirings — land: `remove_at_transition` beside
   the `_enter_city_landing` heal block (`:402-405`; the dev
   teleport delegates in); board: the call at the launch success
   path (`game_interactions.py:487`) AND at the
   dungeon-exit-to-space flip (`_handle_dungeon_exit` /
   `game_loop.py:650-657` — advisor catch 3, blocking).
8. `ground_consumables.py` — `_use_outside_combat` rewritten: the
   gate re-scopes from `outside_full_heal` to exploration-legality
   (working rename `exploration_legal`); the med pack applies the
   regen status and the stim applies the stim status (source =
   spec.name, theater="ground"); the full heal RETIRES; the
   full-HP refusal STAYS.
9. `data/ground_items/__init__.py` + `consumables.py` +
   `character_screen.py` — the field rename sweep (docstring +
   both reads), with the screen's detail-text branch RE-KEYED
   (combat_ap_bonus first, or effect_id — never the renamed
   legality flag, which both items now carry True; advisor catch
   2, blocking).
10. `hud.py` — the exploration one-row status line (lazy import,
    the bandolier precedent; renders only rows carrying
    `hud_label`).
11. `game_loop.py` + `status_inspect.py` — `v` wired in
    exploration (`_handle_non_movement_event`), the you-only
    overlay entry WITHOUT the "TAB next" footer hint (one subject
    — TAB would mislead; advisor note); no turn cost.
12. `data/guide/__init__.py` — the prose-gated rewrites above.

### Build order

prose gate first → engine helpers + unit pins → catalog swap +
the debuff-stamp pin → the four defuse flips + carry pins → the
exploration adapter + the seam hook + tick pins → the two
transition wirings + their pins → the consumables rewrite + pins
→ HUD row + `v` → guide → the save round-trip live-entries pin +
the worktree pre/post FULL-suite harness diff (expect IDENTICAL).

### Binding rulings

The tick law (dungeon turns; city STREETS outside status time,
city interiors tick — they are dungeon-mode maps; the hook at the
seam top — the step happened before any fight it starts). The
transition system (`removed_on`; vocabulary exactly {land, board}
with board firing at BOTH the launch seam and the
dungeon-exit-to-space flip — new transitions are future rulings,
never silent additions; landing keeps its heal and removes all
debuffs by the catalog-side default; buffs survive land; removal
silent). The home-theater law is ENGINE-enforced (`advance`'s
theater filter at every walk — a carried ground row never ticks,
and never touches space AP, while you fly). The defuse flip
(field-keyed at all four sites; fight-class rows, the loans, AND
unknown retired ids defuse; carried rows survive fight init AND
the abnormal-end recovery — q13's "you keep your burns"). The med
pack edges (in-combat instant 5 KEPT; out-of-combat = regen only;
full-HP refusal stands). The loan never bleeds (silent defuse,
no repay line on an unconsumed loan). Enemy containers unchanged
(fight-scoped). The capture edge (a capture interior is ground
theater — paused ground statuses resume inside a capture fight).
ZERO new draws — the harness diff must read identical (advisor
verified: every named site is drawless, and each harness run is a
single fight); the space expire-line watch row stays UNTRIGGERED
and open for the first space content.

### Required tests

Engine pins for both helpers (defuse predicate: fight-class +
loans drop, carried rows survive, UNKNOWN retired ids drop;
transition removal: land drops staggered, keeps regen/stim, board
drops nothing in v1 — at BOTH board seams). The catalog stamp pin
(every polarity=False row carries "land"; the stamp unions with
explicit authoring). The theater-filter pins (a ground-tagged row
does not tick — and never touches space AP — at the space walk;
None matches every theater). The exploration tick pins (regen
heals 2/step clamped at the refreshed max, tick line only on
healed > 0; waits tick; city STREETS do not tick; city INTERIORS
do; auto-explore ticks; staggered decrements and its expire line
logs; the stim decrements with NO ap effect). The carry pins
(staggered with rounds left applies at the next fight's resets;
the container survives the abnormal-end recovery path). The
consumable rewrite pins (med pack out-of-combat = regen apply, no
full heal, refused at full HP; stim legal + applied; the screen's
detail text renders the stim's AP format, never "+0 HP"). The
save round-trip pin (live mid-tick entries: remaining, theater
tag, source). The worktree pre/post harness diff + the full gate
+ reviewer REVIEW.

### Stop point

No fire-type row ("board" ships removed-by-nothing). No space
exploration tick. No new transitions (station docking, flee,
capture are future rulings). No new statuses. No potency keying.
No cooldown work. No AoE.

### Playtest checkpoint

1. Disengage mid-regen: the tick lines fire on dungeon steps
   (clamped at max); a dungeon WAIT also ticks; city steps freeze
   it.
2. Save/quit/continue mid-tick: resumes exactly (the HUD row and
   remaining both survive).
3. End a fight staggered: the HUD row carries out, walks off on
   steps (the expire line reads); re-engage with rounds left and
   it applies (your resets dip).
4. Carry a status to the pad (city steps freeze it), board: it
   pauses in space; land: the debuff is gone at the rest line,
   buffs survive and resume.
5. Med pack out of combat: no full heal — REGEN ticks on steps;
   refused at full HP. Stim out of combat: legal, and the walk
   spends it.
6. The core-button loan never bleeds: end a fight right after
   pressing core — no −1 AP in the next fight's first round.
7. Both rewritten guide sentences read correct; the exploration
   HUD row and `v` work while exploring.

## Acceptance criteria

1. **One mechanism**: no new ad-hoc timed-effect field, key, or
   branch lands outside the containers — grep-able law, enforced at
   review, WITH the boundary carve-outs above (the ledgers, the
   spec-mechanics regen family, the instant riders) named so the
   grep reads clean.
2. **Easy by construction**: authoring a new stat-shape status is a
   data-file edit plus at most one assembly term; no combat module
   rewrite. (The bar the user named: "easy to use... support even
   more... and more complicated ones." Named limit: deep
   damage-site terms break this bar first — they cost a term at
   `resolve_damage` in both theaters.)
3. Migrations bit-identical (worktree pre/post proof per the proof
   law, zero new draws).
4. Engine RNG-free; application rolls guarded and re-pinned where
   they land.
5. Actor symmetry pinned: the same tests drive player and enemy
   containers.
6. Save round-trip: the player container round-trips from Build A
   (empty backfill, defused at fight end per today) and carries
   live entries from Build C; enemy containers unaffected
   (fight-scoped); no new blessed globals.
7. **Durability correct by the end of the doc** (user, 2026-10-18):
   ending combat does not remove the player's statuses; the med
   pack's unfinished regen keeps ticking outside combat; theater
   crossings behave per the ruled crossing rules.

## Advisor pass (2026-10-18) — verdict SOUND-WITH-CATCHES; all 29 issues folded

The advisor verified every census anchor against the tree
(including the `effect_id` docstring promise and the tinker-kit
exemption) and endorsed the core architecture (catalog + per-actor
containers + pure event-returning engine + delivery-vehicle chance;
"no simpler shape meets the brief" — the parked sketch's bare
`id → rounds` cannot carry payload, stacks, or potency). The 29
issues, folded above:

- **Census/boundary (5)**: movement-dodge ledgers named (23, the
  strongest miss); Shredder mend named (24); the on-hit instant
  rider family named + the poster-child paragraph corrected (25);
  spec-authored per-turn regen/regrow/divert swept (26);
  `shields_charged` flagged as a retire candidate (27).
- **Design (5)**: the assembly-term-is-the-gate sentence (2); the
  payload "exactly" claim corrected to migrations-two +
  discretionary tier (3); the 102 supersession paragraph (5); the
  known-limits list — mandated actions, damage-site terms, AoE
  draws, assemblies-as-AI-interface (7); the ground hit anchor fix
  (8).
- **Contracts (8)**: tick-death kill-path clause (9); clamping
  order pins (10); the loan's two wirings preserved (11); the
  killing-hit roll guard → open q.10 (12); the stim-trigger read
  moves with the field (13); direct-fire-only rolls (14); enemy HUD
  surface → open ruling (15); the guide row in Build B (16).
- **Prose/process (6)**: source-name interpolation + per-status
  line opt-in (17); the three refresh edges enumerated for the
  semantics pass (18); the dev burn dial (19); the proof law
  re-worded + baton tests rewritten-not-repinned (20); the four
  homes wording fix (21); the budget note + engine tests named
  (22).
- **Contract point (29)**: `apply` RAISES on unknown ids (authoring
  error) — the silent-skip contract belongs to `sum_effects` alone.
- **Verified clean (1, 4, 6, 28)**: the architecture, the
  delivery-vehicle chance, the boundary cuts, and every
  out-of-scope candidate the sweep checked (glancing,
  `plasma_ap_discount`, trait conditionals, opener, passives,
  Momentum, six-block, line latches, flee states; no
  morale/suppression/stagger/disruption vocabulary anywhere in src
  — the "What does NOT exist" claim holds).

## SETTLED — the refine pass (2026-10-18)

### q1 — Naming: STATUSES

The parked sketch's word is the law: module `combat/_statuses.py`,
catalog `data/statuses.py`, ctx field `active_statuses`, and the
player-facing word "status". "Conditions" rejected (a rename sweep
of the working vocabulary for no gain); "effects" rejected (the
retiring mechanism's word — `_ground_effects.py`, `effect_id`).

### q2 — Stacking default: REFRESH

Re-apply resets the remaining duration; the stack count stays 1.
Bit-matches every live behavior (med pack re-drink, stim re-use,
the single-round loan). Independent stacks remain a per-status
catalog override (`stacking="stacks"`, `stacks_max`), authored
when content first needs them. The three refresh edges (re-apply
at `stacks_max`; re-apply at different potency; two sources, one
id) are SEMANTICS-PASS rows — the ruled law is the default only.

### q3 — Cooldowns: SEPARATE, with the bridge

Ability cooldowns (`core_cooldown`, `stim_cooldown`) keep their
latch/countdown homes — ability gating is a different axis from
actor conditions ("when may I use it" vs "what is on me"), on the
ability's own clock and its own surface ("ready in N" on the
ability, not the actor's status line). **The bridge (user-voiced,
ruled):** a future debuff that PREVENTS a buff — or jams an
ability — is a STATUS with a behavior flag (the
`blocks_dodge`/`blocks_melee` family), read at `engine.apply` /
the ability gate; those sites are container-reading assemblies,
so such debuffs land as catalog rows plus at most one read-site
term. The unification is available as a READ, never a home
change. A cooldown unification doc, if ever wanted, designs
ready-at-zero and ability-UI semantics into duration classes —
not this doc.

### q5 — The ego seam: VICTIM-SIDE susceptibility (user, 2026-10-18)

User ruling, verbatim: **"The idea here is that having burnt ego
makes one more susceptible to status effects. It reduces your
ability to resist. Full ego, full resist. Right now only the
player gets burnt ego. Right now no enemies apply a status to
the player. So while this is the plan, there is nothing in game
right now that exercises it."**

- The seam keys the VICTIM's burn ONLY: burn reduces the victim's
  ability to resist an applied status; the attacker's burn NEVER
  reads (no aim-dimming read on your own attacks, no desperation
  inversion). Ruled shape constraints: zero burn = identity
  ("full ego, full resist" — the delivery's base chance stands
  unmodified); susceptibility is monotone up with burn. Slope,
  cap, and dead-zone flatness remain semantics-pass rows.
- **Exerciser CORRECTED same day (user: "I misspoke actually. We
  can test this by giving a stun baton to an enemy, right?"):**
  enemies author `weapon_families` against the SAME catalog, and
  the baton lives in the `melee` family (`data/ground_weapons/
  melee.py`, tech_level 2) — so tier-2+ melee-family enemies
  (pirate raiders/riflemen/brutes, militia troopers) can ALREADY
  organically draw it. The enemy's fire site rolls application
  through the same actor-symmetric law, making the PLAYER the
  victim: the seam IS exercised in the debut. The dev burn dial /
  kiosk buy returns as playtest instrumentation and the F7
  burn-neutral catch (`dev_mode.py` grants via `install_chrome`,
  never `ratchet_install`) is live again. No content change
  required (RULED: organic); playtest reliability — whether a
  baton wielder is reliably ENCOUNTERED vs family-roll luck — is
  a Build B brief row (dev arming hook vs a specific pool tweak).
- The seam stays ONE function in `chrome.py`, beside `band`.
- The 102 supersession is re-scoped to match: what supersedes is
  debuff-SUSCEPTIBILITY — see the Application section.

### q6 — Universal chance

The application roll is a delivery-vehicle property, blind to
polarity: any delivered status can carry `status_chance`. Our
consumables ship at 100% (you paid — the med pack's regen lands);
a chance-carrying buff vehicle is authorable when content wants
one.

### q10 — The killing-hit guard: SURVIVORS ONLY

Roll application only when the victim survives the hit — a
killing hit leaves no victim; rolling anyway burns a draw to no
effect and shifts every subsequent stream draw.

### q4 — Pirate opener: MIGRATE — the `fight` class ships with a real consumer

The once-per-fight opener window (`enemy_fired` + `opener_spent`,
doc 49 SETTLED 5) joins Build A as the `fight` duration class's
first consumer. Verified shape (2026-10-18): the latch pair lives
on the FIGHT state in BOTH theaters (`_types.py:183-188` space,
`_ground_types.py:128-133` ground) — not on the enemy instance —
stamped at the enemy's first volley (`_ai.py:791,843`,
`_ai_ground.py:611`) and the player's first attack
(`_loop.py:599`), and read by the trait math
(`xp._opener_hit_bonus` / `_opener_damage_pct`, kwarg-threaded
through both theaters' `hit_chance`). The migration: fight-class
statuses consumed by the respective first actions, the trait reads
becoming `has()` reads; the exact modeling (status type per
container, window semantics) is brief material. Build A's
bit-identity proof grows the opener rows (unit pins:
`test_enemy_fire.py`, `test_class_traits.py`; no harness rows).
The lean ("leave the trait math") was considered and overridden:
proving the class early beats zero-risk.

### q7 — HUD: one row + enemy suffix + the status INSPECT overlay

Player line (user: "One Row, yes"): ONE row of terse
polarity-colored labels + remaining on both theaters' player
panels. Enemy surface (user: "Panel Suffix"): a status suffix on
the ground enemy panel rows / target card, joining the
regen/temp-AP suffixes (which stay — they read the same sums
now). AND a ruled NEW surface, user verbatim: **"I feel like we
need a key we can press that opens a scrollable window of current
statuses with descriptions? The player will need to be able to
not just inspect their own statuses, but also inspect an
enemy."** — a status-inspect overlay: scrollable, per-status
DESCRIPTION text (a new prose-gated StatusSpec string field),
covering the player's own container AND enemies' (selection
rides the existing enemy-examine/target flow; exact keybind and
wiring are brief material). The new key fires the guide contract;
descriptions settle through the prose loop before landing.

### q9 — Regen stays ground vocabulary in v1

`regen_per_round` is ground-only vocabulary in v1. No space
content delivers regen (the med pack is ground-only); what a
regen tick would heal in space is the theater-crossing ruling's
business (q11), not the catalog's. A hull-repair status family
lands theater-symmetric the day space content delivers one.

### q11 — Theater crossing: PAUSE default, per-status catalog field

User ruling (2026-10-18): statuses tick ONLY in their home
theater. Boarding PAUSES ground statuses (they resume on return
to the ground); docking pauses space statuses (the same rule,
structurally unexercised in v1 — no space statuses exist). The
crossing behavior is a per-status StatusSpec field, DEFAULT
"pause", polarity-blind (the doctrine: polarity is presentation,
never a code fork) — a fire/burn-type status AUTHORS "smother"
(dies at the airlock; the thematic death). The home-theater tag
rides application (the delivery vehicle knows its theater). The
user's instinct is honored by construction: a damage tick never
follows you into the cockpit.

**AMENDED (user, 2026-10-19 — the Build C ruling):** the smother
enum value is SUPERSEDED by the generic transition-removal system
(user, verbatim: "I feel like we could make a generic system that
lets us define which buffs/debuffs are removed during which
transitions? Then we use that system in the future to add on fire
debuff being removed when entering ship in addition to the default
land on a planet to heal/remove debuff"). The PAUSE half of the
ruling STANDS unchanged (non-removed statuses freeze through a
crossing; home-theater ticking). Removal becomes per-status
`removed_on` data over a named transition vocabulary ("land" =
the landing rest seam, which today full-heals — landing now ALSO
removes all debuffs by default; "board" = the launch-to-space
seam, removed-by-nothing in v1 until the fire row). The debuff
default is stamped CATALOG-side (every polarity=False row carries
"land"), so the engine never forks on polarity — the
presentation-only doctrine holds at every read site. Full shape
in the Build C rulings SETTLED section.

### q12 — Out-of-combat consumables: stim LEGAL; med pack = REGEN EVERYWHERE

- **q12a (user: legal, ticks):** the Combat Stim becomes
  exploration-legal; exploration steps tick its duration — the
  approach spends it (pre-buffing with a walking cost). The
  asymmetry is gone: a mid-fight sip already outlives the fight
  (the durability ruling), so a fresh out-of-combat use being
  illegal was the odd shape.
- **q12b (user: REGEN EVERYWHERE — the keep-full-heal lean was
  considered and OVERRIDDEN):** EVERY med pack use applies the
  regen status. The out-of-combat instant full heal RETIRES (a
  Build C behavior change: healing is always over time, in or out
  of combat; out of combat the regen ticks on exploration
  steps). Consequences recorded: the med pack's out-of-combat
  value drops from a full top-up to the regen's total (+6 at the
  working numbers) — a live-economy WATCH ROW for Build C's
  playtest; regen at max HP is a no-op; a re-drink refreshes
  (q2). Any full-heal strings change — prose-gated, called out
  in Build C's checklist.

### q8 — Potency: structural only in v1

Nothing sets potency ≠ 1 in v1 — the field ships structural
(day-one seam, the inherited sketch: re-keyable from burnt ego
through willpower later) and chrome pass #2 owns the first re-key
(tiered chrome delivering stronger statuses), per doc 102's
succession. The debut reads burn through the application seam,
never potency.

### q13 — Fight end: PERSIST default, per-status field; the loans defuse

User ruling (2026-10-18): fight-end behavior is a per-status
catalog field PARALLEL to q11's crossing field — DEFAULT persist
(ending combat does not remove statuses, the durability ruling's
spirit). The ground AND space stim loans AUTHOR defuse (combat
tempo, not conditions — a −1 AP loan must never bleed into a next
fight's first rounds). Staggered PERSISTS on the player (revived
by the two-sided debut: enemy baton wielders put it on YOU) — it
carries out of the fight, ticks down on exploration steps, and
re-engaging with rounds left, it applies (the enemy-wound doctrine
pointed at the player: you keep your burns). Regen persists
(ruled with durability itself, 2026-10-18).

### Semantics pass (2026-10-18, user-confirmed)

- **Tick law (S1, confirmed)**: `rounds`-class statuses are active
  on apply; at each round boundary `advance` fires the payload
  events THEN decrements; remaining = 0 expires (a 3-round regen
  heals exactly 3 times; the 1-round loan fires exactly once at
  the next round start). A re-apply landing in the same boundary
  as a tick refreshes first — never a double-tick. `fight`-class
  never decrements (consumed explicitly, or dropped at fight
  end); `charges`-class never decrements (consumed on trigger).
- **Re-apply metadata (S2, confirmed — NEW WINS)**: on refresh,
  the NEW application's potency AND source overwrite; the duration
  resets. The fresher application is the truth; log attribution
  names the most recent deliverer. (Nothing in v1 sets potency
  ≠ 1; the law exists for chrome pass #2's tiered re-keys.)
- **Stacks at cap (S3, confirmed)**: for authored stacking
  statuses, re-apply while at `stacks_max` refreshes the duration
  and grants no new stack. No stacking status ships in v1.
- **The roll-law numbers (S4, confirmed package)**: base
  application chance **50** on the baton; the seam reads the
  victim's existing band (`_BAND_MAX_BURN = (3, 7, 11)`): band 0
  (burn 0–3) is the DEAD ZONE reading identity ("full ego, full
  resist" plus shallow burn), **+10 chance points per band from
  band 1, capped at +30** (band 3 → 80 effective). Staggered
  duration **2 rounds**. At deep burn an enemy baton that
  connects staggers the player 4 times in 5.

## Open questions (the refine pass)

1. **Naming** — SETTLED 2026-10-18: **statuses** (SETTLED section
   above).
2. **Stacking default** — SETTLED 2026-10-18: **refresh**; the
   three edges are semantics-pass rows (SETTLED section above).
3. **Cooldowns** — SETTLED 2026-10-18: separate, with the
   blocking/jamming-debuff bridge (SETTLED section above).
4. **Pirate opener migration** — SETTLED 2026-10-18: **migrate
   now**; the opener is the `fight` class's first consumer
   (SETTLED section above).
5. **The ego seam's shape** — SETTLED 2026-10-18: victim-side
   susceptibility only, identity at zero burn, unexercised in the
   debut (SETTLED section above); slope/cap/dead-zone = semantics
   rows; Build B structural-vs-deferred = brief row.
6. **Do buffs roll too** — SETTLED 2026-10-18: universal chance,
   consumables at 100% (SETTLED section above).
7. **HUD line shape** — SETTLED 2026-10-18: one row + enemy panel
   suffix + the status INSPECT overlay (player and enemy;
   descriptions prose-gated) — SETTLED section above.
8. **Potency wiring** — SETTLED 2026-10-18: structural only,
   nothing keys it in v1 (SETTLED section above).
9. **Regen in space** — SETTLED 2026-10-18: ground-only vocabulary
   in v1 (SETTLED section above).
10. **The killing-hit guard** — SETTLED 2026-10-18: survivors
    only (SETTLED section above).
11. **Theater crossing** — SETTLED 2026-10-18 (pause default +
    per-status field, home-theater ticking), AMENDED 2026-10-19:
    the smother enum value superseded by the transition-removal
    system (SETTLED sections above).
12. **Out-of-combat consumable use** — SETTLED 2026-10-18: stim
    exploration-legal (ticks on steps); med pack = regen
    everywhere, the instant full heal RETIRES (SETTLED section
    above).
13. **What survives fight end vs defuses** — SETTLED 2026-10-18:
    persist default + per-status field; the loans author defuse;
    staggered carries (SETTLED section above).
