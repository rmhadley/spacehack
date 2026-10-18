# DESIGN: Statuses — the durable buff/debuff system

**Status: DESIGN IN PROGRESS — the architecture is shaped and
plan-approved (2026-10-17); the advisor ADVISE pass is folded
(2026-10-18, verdict SOUND-WITH-CATCHES, all 29 issues below); the
open rulings are this doc's refine pass. No implementation until
the user explicitly requests it.**

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

- **A status is a timed, fight-scoped, ACTOR-ATTACHED effect.** One
  mechanism for buffs and debuffs alike; polarity is presentation
  data (color, wording), never a code fork.
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
- **Fight-scoped, never serialized** — identical to every mechanism
  being replaced (no mid-fight saves exist; combat QUIT never
  persists; saves happen only at the exploration-mode exit seam,
  `game_flow.py:119-138` — advisor-verified). A persistent
  across-fight condition (disease, a long wound) is a future
  ctx-level extension reusing the same container type; out of scope
  here, recorded as the durability seam.

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
- **Burnt ego adjusts the chance through ONE seam function** — the
  ego drain's combat entry, exactly where doc 102's recorded
  endgame parked it ("chrome trades combat advantages for certain
  risky disadvantages"). **Supersession recorded (advisor catch,
  2026-10-18): doc 102 explicitly rejected combat-axis
  consequences of low ego ("the world reprices you; it does not dim
  your aim and does not open fire," lines 176-180). THIS SEAM
  supersedes that rejection, and only this seam — the recorded
  endgame ("chrome then trades combat advantages for certain risky
  disadvantages") is the re-opening, and everything else
  socioeconomic stays exactly as 102 ruled it.** Slope, direction,
  and which sides (attacker's burn aiding their own application vs
  the victim's burn raising susceptibility — or both) are open
  rulings below. The seam's home: `chrome.py`, beside `band`.
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

### ActiveStatus (runtime, engine-home)

`status_id`, `remaining_turns`, `stacks = 1`, `potency = 1`,
`source = None`. Potency multiplies additive payload at sum time;
source carries the deliverer for attribution (log lines, future AI
reads).

### One container per actor — four homes, one type

- `GroundCombatState.statuses: dict[str, ActiveStatus]`
- space `player_state["statuses"]` — a dict KEY stamped in the
  `_player_state_dict` builder (`_stats.py:397-434`), not a
  `_types` field; same principle (declared at init, never attached
  at runtime), different home (advisor catch: only two of the four
  homes are `_types` modules).
- `GroundEnemyInstance.statuses` (declared in `_ground_types.py`)
- `EnemyInstance.statuses` (declared in `_types.py` — space enemies
  gain their first timed container)

The cohesion law owns the two dataclass declarations; the dict homes
are stamped by their init builders. Nothing attaches at runtime.

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
  single-loan arithmetic); the gain guards at zero.
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

The Pirate opener (once-per-fight booleans) is a CANDIDATE for the
`fight` duration class — included iff the bit-identity proof is
cheap; open ruling 4. Chrome conditionals, traits, map zones: NOT
migrated (boundary doctrines above).

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

- `staggered` — debuff, `ap_per_round: -1`, `rounds: 2` (working),
  on the ENEMY container (ground). The felt upgrade: the baton
  stops being a per-hit drain and becomes a real timed condition
  the HUD can show.
- Delivery: the baton carries `status_id="staggered"` +
  `status_chance ~50` (working) on its spec.
- The application roll: after the hit resolves, guarded, one draw
  per connecting SURVIVING hit → Stun Baton fights re-pin their
  balance rows same-commit (the crit precedent's discipline).
- The ego seam adjusts the roll through ONE function
  (`chrome.py`, beside `band`); dead-zone reads flat (working lean,
  open ruling 5). **Playtest instrumentation (advisor catch): F7
  grants are burn-NEUTRAL by design (`dev_mode.py:196-215` calls
  `install_chrome`, never `ratchet_install`) — Build B adds a dev
  burn dial, or the playtest buys its burn at a kiosk; ruled in
  the brief.**
- Enemy-side symmetry: staggered on enemies IS the actor-symmetry
  proof — the same container, ticked by `advance_enemy_effects`'
  successor.

Later debuffs (suppression, damage-over-time, disruption — the
chrome-risk family) join as catalog rows on these rails; that
content is NOT this doc's build scope beyond the debut.

## HUD surface (both panels — and the enemy side, ruled open)

A compact status line: per active status, the spec's terse label +
remaining (`STAGGERED 2`, `REGEN 1` — polarity-colored), read from
the container, on both theaters' player panels (the ground panel
has a free row at ~y8 before WEAPONS, `_ground_render.py:259-291`;
`HUD_TEXT_MAX` truncation is already the pattern). **The ENEMY
surface is its own open ruling (advisor catch: the debut's only
debuff lives on the enemy container — a player-panel-only plan
would never show it): lean = a status suffix on the ground enemy
panel rows / target card, alternative = apply/expire log lines
only.** The existing regen/temp-AP suffixes stay (they read the
same sums now). Strings prose-gated; CP437-safe.

**The guide row (advisor catch, blocking per the guide contract):
the debut falsifies a LIVE guide entry** — "The Stun Baton reduces
an enemy's AP by 1 on its next turn whenever it hits"
(`data/guide/__init__.py:308-310`). Build B rewrites that entry and
adds the statuses/debuff documentation if the HUD line ships
player-facing — prose-gated, and the edit is called out in Build
B's playtest checklist.

## Phases

- [ ] The rulings pass (refine sessions with the user: every open
      question below)
- [ ] The semantics pass (duration classes' exact tick boundaries,
      the stacking table INCLUDING the three refresh edges —
      re-apply at `stacks_max`, re-apply at different potency,
      two-source attribution; the payload vocabulary; the roll
      law's numbers: base chance, ego slope, staggered duration,
      the killing-hit guard)
- [ ] Implementation briefs (the engine + migrations brief; the
      debut brief; advisor ADVISE pass per house rule; budget
      note: `_rules_ground.py` sits at 974 lines and
      `_rules_space.py` at 966 — both one touched-file growth from
      the in-commit extraction ratchet)
- [ ] Build A: the engine + catalog + the migrations — bit-identity
      proof (harness rows + unit pins, per the proof law) + gate
      green + the engine's own unit tests (apply/advance/sum_effects
      are mutation-wrappers: same-commit tests, plus the
      actor-symmetry pin). PLAYTEST: a med pack, a stim, the Stim
      loan, an enemy carrier — behavior indistinguishable, the HUD
      line reads.
- [ ] Build B: the staggered debut + the rolled application + the
      ego seam + the HUD line + the dev burn dial + the guide row;
      baton balance rows re-pinned, baton unit tests rewritten.
      PLAYTEST: the baton staggers sometimes, deep burn moves the
      odds (dial or kiosk), the enemy wears it and shows it.
- [ ] Close (SYSTEMS.md inventory amended same-commit; move to
      complete/)

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
6. Save/round-trip unaffected (fight-scoped); no new blessed
   globals.

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

## Open questions (the refine pass)

1. **Naming**: "statuses" (working; the parked sketch's word) vs
   "effects" vs "conditions" — module, catalog, and the
   player-facing word.
2. **Stacking default**: `refresh` matches today's behavior —
   confirm as the law, with the three edges ruled (re-apply at
   `stacks_max`; re-apply at different potency — overwrite or
   keep; two sources, one id — last-writer attribution?).
3. **Cooldowns**: stay separate (lean — ability gating is a
   different axis) or unify as a timers container later?
4. **Pirate opener migration**: adopt the `fight` duration class
   now (proves the class early) or leave the trait math (lean:
   leave — zero behavior risk; the class ships when content needs
   it)?
5. **The ego seam's shape** (the big one): which sides read burn —
   attacker's application, victim's susceptibility, or both (lean:
   both eventually; the debut wires attacker-side only, the
   staggered victim being an enemy)? Slope and cap; dead-zone
   flatness.
6. **Do buffs roll too**, or is the application chance a
   debuff-only law (lean: any DELIVERED status can carry a chance;
   consumables stay 100%)?
7. **HUD line shape**: one row of terse labels (lean) vs
   per-status rows — AND the enemy-side surface (lean: a suffix on
   the ground enemy panel rows / target card vs apply/expire log
   lines only).
8. **Potency wiring**: the field exists day one; does anything key
   it in v1 (lean: no — chrome pass #2 owns the first re-key, per
   doc 102's succession)?
9. `regen_per_round` in space (a hull-repair status family): v1
   ground-only (lean) or theater-symmetric vocabulary now?
10. **The killing-hit guard** (advisor): roll application only if
    the victim survives (lean yes — a killing hit has no victim,
    and the wasted draw shifts every subsequent stream draw)?
