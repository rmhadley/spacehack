# DESIGN: Statuses — the durable buff/debuff system

**Status: DESIGN IN PROGRESS — the architecture is shaped and
plan-approved (2026-10-17); the open rulings below are this doc's
refine pass. No implementation until the user explicitly requests
it.**

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

And the poster child of what this costs: the Stun Baton's effect is
a hardcoded id branch — `enemy.ap = max(0, enemy.ap -
int(weapon_id == "stun_baton"))` at `combat/_rules_ground.py:443` —
a guaranteed per-hit AP drain with no data home, no duration, no
HUD surface, no way to give any other weapon a similar behavior
without another branch. It violates the standing ruling ("Data
opt-ins over id lists") in miniature, and it is not alone: every
"more complicated" effect we have wanted (suppression, stagger,
damage-over-time, disruption) has nowhere to live.

What does NOT exist at all: enemy-side timed effects in space
(`EnemyInstance` has no container), a stacking model, an
application chance, any debuff vocabulary, any severity/potency
notion.

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
  raises mid-combat).
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
  - Map-anchored zones (stare, Warden field) stay world state.
  - Ability cooldowns (the Stim's `core_cooldown`) are ability
    gating, not conditions on the actor (open question 3).
  - Permanent world-layer states (ego bands) are consequences, not
    combat timers.
- **Fight-scoped, never serialized** — identical to every mechanism
  being replaced (no mid-fight saves exist; combat QUIT never
  persists). A persistent across-fight condition (disease, a long
  wound) is a future ctx-level extension reusing the same container
  type; out of scope here, recorded as the durability seam.

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
  risky disadvantages"). Slope, direction, and which sides
  (attacker's burn aiding their own application vs the victim's
  burn raising susceptibility — or both) are open rulings below.
- **The roll sits at the fire site, after the hit resolves**,
  guarded `chance > 0` (the crit precedent): fights without a
  chance-carrying delivery consume ZERO new draws, bit-identical;
  fights WITH one (every Stun Baton fight, on debut) draw once per
  connecting hit → tripped balance rows re-pinned same-commit,
  cause noted.
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
  carries (the ChromeSpec law; the fold stays table-driven):
  `hit_bonus`, `dodge_bonus`, `melee_bonus`, `ap_per_round`,
  `regen_per_round`, `dot_per_round` — all `= 0`.
- Behavior flags for discrete states (the "complicated" tier):
  `blocks_dodge = False`, `blocks_melee = False` (future
  suppression/disarm families).
- Ruled string templates, prose-gated: apply / tick / expire lines.

The payload vocabulary is the WORKING set — exactly what the
migrations plus the staggered debut need. New fields join the same
flat-defaulted table as content demands, each with its assembly
term.

### ActiveStatus (runtime, engine-home)

`status_id`, `remaining_turns`, `stacks = 1`, `potency = 1`,
`source = None`. Potency multiplies additive payload at sum time;
source carries the deliverer for attribution (log lines, future AI
reads).

### One container per actor — four homes, one type

- `GroundCombatState.statuses: dict[str, ActiveStatus]`
- space `player_state["statuses"]` (the same dict-of-ActiveStatus
  shape)
- `GroundEnemyInstance.statuses` (declared in `_ground_types.py`)
- `EnemyInstance.statuses` (declared in `_types.py` — space enemies
  gain their first timed container)

The cohesion law owns the field declarations in the `_types`
modules; nothing attaches at runtime.

### The engine (`combat/_statuses.py`)

- `apply(container, status_id, potency=1, source=None)` — enforces
  the spec's stacking policy; returns what happened (applied /
  refreshed / stacked) for the caller's log decision.
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

### Read-site wiring (assemblies gain status terms, zero-defaulted)

| Assembly | Anchor | Terms |
|---|---|---|
| Ground AP gain | `_rules_ground.reset_turn` | `+ 20 × ap_per_round` |
| Ground hit / melee / dodge | `_player_hit_bonus`, `_player_melee_bonus`, `_player_ground_dodge` | `hit_bonus`, `melee_bonus`, `dodge_bonus` |
| Space hit / dodge | `_player_hit_bonus`, `player_dodge_from_state` | `hit_bonus`, `dodge_bonus` |
| Space AP | `_rules_space.reset_turn` loan application | `ap_per_round` as events |
| Enemy reads | the symmetric instance reads | the same sums off their containers |

Choke-point defaults, not seam threading: each assembly resolves
`sum_effects` itself from the state it already holds.

## Migration (behavior-identical, bit-pinned)

| Today | Becomes | Pin |
|---|---|---|
| med-pack `restore_hp` entry | `regen` status (2/turn, 3 rounds) | existing consumable tests + fresh bit-identity run |
| combat `stim` entry | `stim` status (+1 AP/round, 3 rounds) | same |
| ground `"neural_stim"` loan entry | `neural_stim_loan` status (−1 AP, 1 round) — the container stops being "consumable" | `test_core_button.py` loan pins |
| space `stim_loan_ap` / `stim_cooldown` keys | the loan joins the space player container; the cooldown stays a cooldown (open q.3) | same, space side |
| enemy `stim_turns`/`regen_turns` fields | enemy containers, `apply` from `use_carried_consumable` | enemy stim/regen tests |
| `GroundConsumableSpec.effect_id` | points at `find_status` — the "effect registry" its own docstring has promised since authoring | round-trip |
| `ActiveConsumableEffect` + `effect_from_spec` | RETIRED | — |

The Pirate opener (once-per-fight booleans) is a CANDIDATE for the
`fight` duration class — included iff the bit-identity proof is
cheap; open ruling 4. Chrome conditionals, traits, map zones: NOT
migrated (boundary doctrines above).

**Proof law:** the pre/post worktree diff — run the instrument at
the pre-change commit and diff outputs (med pack, stim, loan, enemy
carrier fights all bit-identical; zero new draws anywhere — the
migrations add no rolls).

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
  per connecting hit → Stun Baton fights re-pin their balance rows
  same-commit (the crit precedent's discipline).
- The ego seam adjusts the roll through ONE function; dead-zone
  reads flat (working lean, open ruling 5).
- Enemy-side symmetry: staggered on enemies IS the actor-symmetry
  proof — the same container, ticked by `advance_enemy_effects`'
  successor.

Later debuffs (suppression, damage-over-time, disruption — the
chrome-risk family) join as catalog rows on these rails; that
content is NOT this doc's build scope beyond the debut.

## HUD surface (both panels)

A compact status line: per active status, the spec's terse label +
remaining (`STAGGERED 2`, `REGEN 1` — polarity-colored), read from
the container, on both theaters' player panels; the existing
regen/temp-AP suffixes stay (they read the same sums now). Strings
prose-gated; CP437-safe.

## Phases

- [ ] The rulings pass (refine sessions with the user: every open
      question below)
- [ ] The semantics pass (duration classes' exact tick boundaries,
      the stacking table, the payload vocabulary, the roll law's
      numbers: base chance, ego slope, staggered duration)
- [ ] Implementation briefs (the engine + migrations brief; the
      debut brief; advisor ADVISE pass per house rule)
- [ ] Build A: the engine + catalog + the migrations — bit-identity
      proof + gate green. PLAYTEST: a med pack, a stim, the Stim
      loan, an enemy carrier — behavior indistinguishable, the HUD
      line reads.
- [ ] Build B: the staggered debut + the rolled application + the
      ego seam + the HUD line; baton balance rows re-pinned.
      PLAYTEST: the baton staggers sometimes, deep burn moves the
      odds, the enemy wears it.
- [ ] Close (SYSTEMS.md inventory amended same-commit; move to
      complete/)

## Acceptance criteria

1. **One mechanism**: no new ad-hoc timed-effect field, key, or
   branch lands outside the containers — grep-able law, enforced at
   review.
2. **Easy by construction**: authoring a new stat-shape status is a
   data-file edit plus at most one assembly term; no combat module
   rewrite. (The bar the user named: "easy to use... support even
   more... and more complicated ones.")
3. Migrations bit-identical (worktree pre/post proof, zero new
   draws).
4. Engine RNG-free; application rolls guarded and re-pinned where
   they land.
5. Actor symmetry pinned: the same tests drive player and enemy
   containers.
6. Save/round-trip unaffected (fight-scoped); no new blessed
   globals.

## Open questions (the refine pass)

1. **Naming**: "statuses" (working; the parked sketch's word) vs
   "effects" vs "conditions" — module, catalog, and the
   player-facing word.
2. **Stacking default**: `refresh` matches today's behavior —
   confirm as the law; when does `stack` earn its keep (potency
   stacking? DoT intensity?).
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
   per-status rows.
8. **Potency wiring**: the field exists day one; does anything key
   it in v1 (lean: no — chrome pass #2 owns the first re-key, per
   doc 102's succession)?
9. `regen_per_round` in space (a hull-repair status family): v1
   ground-only (lean) or theater-symmetric vocabulary now?
