# DESIGN: Faction Reputation System

## Overview

A unified reputation system that tracks the player's standing with each major faction and gates gameplay consequences: mission quality, NPC hostility, trade access, and combat responses.

### What already exists

- `ctx.faction_reputation: dict[str, int]` with defaults: `pirate=-100`, `merchant=0`, `civilian=0`, `militia=50`
- `faction.get_attitude(rep)` — returns `"hostile"`, `"neutral"`, or `"friendly"` based on threshold ranges
- Used in `comms.py` for NPC ship hails (hostile tag, attitude-gated options)

### What needs to be built

1. **5-tier attitude zones** (replacing 3-tier)
2. **Reputation change sources** — missions, combat, faction alignment
3. **Missions gating** — higher rep → better missions
4. **Hostility system** — hostile NPCs attack on sight
5. **Starting rep** based on species/class
6. **UI viewer** — see current standings
7. **Reputation carrry-over** — stored per-run, reset on death

## Design decisions

### Factions

| Faction | Default rep | Description |
|---------|-------------|-------------|
| `pirate` | -100 | Outlaws, raiders, bar clients |
| `merchant` | 0 | Trade guilds, haulers, freight companies |
| `civilian` | 0 | Independent pilots, stations, local governments |
| `militia` | 50 | System police, blockade patrols, station security |

These four cover all existing NPC ship specs and guild NPCs. No new factions needed for v1.

### 5 attitude zones (replacing the current 3)

| Zone | Range | Label | Effects |
|------|-------|-------|---------|
| **Enemy** | -100 to -76 | `"enemy"` | Attacks on sight. No missions, no trade, no docking at faction stations. |
| **Disliked** | -75 to -26 | `"disliked"` | Won't attack unless provoked. Fewer missions, worse pay. Higher scan chance. |
| **Neutral** | -25 to +25 | `"neutral"` | Default state. Standard missions, standard trade prices. |
| **Liked** | +26 to +75 | `"liked"` | Better missions, better pay, 5% trade discount. |
| **Allied** | +76 to +100 | `"allied"` | Best missions, bonus rewards, 10% trade discount, unique dialogue. |

**Upgrade path:** Current 3-zone threshold was -51:hostile / -50 to 50:neutral / 51+:friendly. The new 5-zone model keeps the same outer bounds but splits the mid-range for more granular progression.

**Update needed:** `faction.py` — replace `get_attitude()` with a 5-zone lookup.

### Starting reputation

Reputation starts at a baseline determined by **species + class**:

| Species | Baseline adjustments |
|---------|---------------------|
| Human | None — all factions at defaults |
| Martian | +10 militia (Martians serve in system patrols), -10 pirate (Mariner Valley raids) |

| Class | Pirate | Merchant | Civilian | Militia |
|-------|--------|----------|----------|---------|
| Pirate | **+30** | -10 | -10 | -20 |
| Merchant | +10 | **+10** | +5 | +5 |
| Bounty Hunter | -20 | +5 | +5 | +15 |

**Resulting starting reputations:**

| Species + Class | Pirate | Merchant | Civilian | Militia |
|-----------------|--------|----------|----------|---------|
| Human Pirate | **-70** | -10 | -10 | -30 |
| Human Merchant | -90 | **+10** | +5 | +55 |
| Human Bounty Hunter | -120 | +5 | +5 | +65 |
| Martian Pirate | **-70** | -10 | -10 | -10 |
| Martian Merchant | -90 | **+10** | +5 | +60 |
| Martian Bounty Hunter | -120 | +5 | +5 | +70 |

**Key gameplay effects:**
- A Human Pirate starts in **Enemy** territory with pirates (-70) — pirates don't attack them on sight, but merchants (merchant=-10, disliked) scan them more aggressively
- A Human Bounty Hunter starts **Liked** by militia (+65) — easier patrol access, but pirates are deeply hostile (-120, enemy)
- A Human Merchant starts Neutral with everyone — the diplomatic option

## Reputation change sources

### 1. Mission completion

| Mission type | Pirate | Merchant | Civilian | Militia | Notes |
|-------------|--------|----------|----------|---------|-------|
| Delivery (merchant) | 0 | +5 | +2 | +1 | Successful trade route |
| Bounty (pirate target) | -2 | +3 | +3 | +5 | Removing a pirate threat |
| Intercept (bar) | +5 | -10 | -2 | -5 | Attacking merchants |
| Smuggling (bar) | +2 | -5 | -5 | -8 | Running contraband — hurts civilian trust + militia |
| Extortion (bar) | +5 | -5 | -3 | -3 | Shaking down neutral ships |
| Salvage rights (bar) | +3 | -3 | 0 | -2 | Claiming wreck — no civilian impact |

**Early bonus:** Completing a mission early (within < 50% of deadline) adds **+50% rep gain** (rounded up).

### 2. Space combat

| Action | Pirate | Merchant | Civilian | Militia |
|--------|--------|----------|----------|---------|
| Kill a pirate ship | -3 | +2 | +2 | +3 |
| Kill a merchant ship | +5 | -8 | -3 | -5 |
| Kill a militia ship | +8 | -5 | -5 | -12 |
| Kill a civilian ship | +5 | -5 | -8 | -5 |
| Flee from combat | 0 | -1 | -1 | -2 | Cowardice — all lawful factions look down on it |
| Initiate unprovoked attack (comms) | +2 | -2 | -2 | -3 | Player attacks first via comms |

**Squad bonus:** Killing all members of a squad adds +1 bonus rep to the relevant faction (e.g. clearing a pirate squad gives +1 extra pirate rep hit, +1 extra merchant/militia gain).

### 3. Monthly decay

Reputation drifts toward 0 slowly to prevent grinding to max and forgetting:

| Zone | Decay per month |
|------|----------------|
| Enemy (-100 to -76) | +3 (moving toward neutral) |
| Disliked (-75 to -26) | +2 |
| Neutral (-25 to +25) | 0 |
| Liked (+26 to +75) | -2 |
| Allied (+76 to +100) | -3 |

Reputation can never cross from positive to negative (or vice versa) from monthly decay alone — decay stops at +1 or -1 on the boundary. Only player actions can change the sign of a reputation.

## Consequences

### Mission gating

Mission boards check the player's reputation with that faction when deciding what to offer:

| Attitude | Mission quality | Effect |
|----------|----------------|--------|
| Enemy | None | No missions offered. NPC refuses to talk. |
| Disliked | Reduced | -1 effective tier (T3 planet offers T2 max). 10-20% pay cut. |
| Neutral | Standard | Full mission pool. |
| Liked | Improved | +1 effective tier (T2 planet offers T3). 5-10% pay bonus. |
| Allied | Premium | +2 effective tier. 15-25% pay bonus. Rare special missions. |

**Implementation:** `fill_empty_slots()` checks `ctx.faction_reputation[guild]` and adjusts `planet_tier` and reward scaling before generating/assigning procedural missions.

### NPC hostility on sight

When entering a system or when NPC ships are moved by `move_npcs`:

| Attitude | Ships of that faction |
|----------|----------------------|
| Enemy | Immediate hostile approach — they move toward the player and engage at detect range. |
| Disliked | Shows `(hostile)` tag in comms, but does NOT attack on sight. |
| Neutral | Never hostile unless provoked. Trade available. |
| Liked | Never hostile. May hail with greetings. |
| Allied | Never hostile. Hail with friendly dialogue. May offer tips/trade before being asked. |

**Design decision (2026-07-29):** Hostility is deterministic. "Enemy" = attacks on sight. "Disliked" = hostile-tagged in comms but no auto-aggression. The "disliked hostility % chance" was dropped for simplicity.

**Implementation:** `npc_ships._tick_npcs` checks attitude via `get_attitude(ctx.faction_reputation[spec.faction])`. For `"enemy"` attitude, NPCs set a target toward the player's position and enter combat range.

### Comms behavior

| Attitude | Hostile tag | Trade available | Scan available |
|----------|------------|----------------|---------------|
| Enemy | ✅ `(hostile)` | ❌ | ✅ |
| Disliked | ✅ `(hostile)` | ❌ | ✅ |
| Neutral | ❌ | ✅ | ✅ |
| Liked | ❌ | ✅ | ✅ |
| Allied | ❌ | ✅ | ✅ |

**Design decision (2026-07-29):** Hostile tag shows for both Enemy and Disliked. Trade is gated to Neutral+. Scan is always available (future: richer scan mechanics).

### Trade access

| Attitude | Trade effect |
|----------|-------------|
| Enemy | Cannot trade at faction-owned shops or stations. |
| Disliked | Cannot trade at faction-owned shops or stations. |
| Neutral | Standard prices. |
| Liked | +5% sell price, -5% buy price. |
| Allied | +10% sell price, -10% buy price. Access to restricted goods. |

### Cargo scan interaction

When a patrol scans the player's cargo (future mechanic), militia attitude affects outcomes. Not implemented yet — defer to a future pass.

## Data model

### New fields on `GameContext`

No new fields needed! The existing `ctx.faction_reputation` dict works. The only change is that starting values become dynamic (species/class gated) instead of hardcoded defaults.

### Change to existing code

**`game_context.py`** — Remove the hardcoded `default_factory` dict. Replace with a `None` default. The value is set in `__main__.py` at character creation time via a new `init_faction_reputation(species_id, class_id) -> dict[str, int]` function.

**New function** `faction.starting_reputation(species_id, class_id) -> dict[str, int]` — returns the dict based on the tables above.

## UI

### Reputation viewer

New option in the ship menu (hangar): **"Factions"** — shows a list of factions with current attitude, current score, and progress bar to next tier:

```
═══════════════════════════════════
         FACTION STANDINGS
═══════════════════════════════════

Pirate       -32  ███░░░░░░░░  Disliked
Merchant     +18  ██████░░░░░  Neutral
Civilian      +5  █████░░░░░░  Neutral
Militia      +62  █████████░░  Liked

[H]elp  [ENTER] back  [ESC] back
```

Reuses the existing modal pattern and the `ui.render_selectable_list` helper.

### Message log notifications

When reputation changes significantly (crosses a zone boundary), a colored message is logged:

```
+5 rep with Merchant faction (now +23, Liked)
-8 rep with Militia faction (now -15, Neutral → Disliked)
```

## Implementation phases

### Phase 1: Attitude zones + starting rep ✅

- [x] Update `faction.get_attitude()` to return 5 zones instead of 3
- [x] Add `faction.starting_reputation(species_id, class_id) -> dict[str, int]`
- [x] Update `GameContext` default — remove hardcoded lambda, initialize in `__main__.py` at char creation
- [x] Update existing default-rep call sites that rely on the hardcoded pirate=-100/etc
- [x] Update `comms.py`: hostile tag = `"enemy"` or `"disliked"`, trade gated to neutral+, scan always available
- [x] Smoke test + commit (`dffab7d`)
- [x] Playtest: all faction/class combos verified, comms behavior matches design
- [x] Fix: End Transmission always last in comms options (`7e7889c`)

#### Playtest checklist *(living — update as implementation reveals edge cases)*

- [ ] Start new game as **Human Merchant** → verify starting faction window shows correct values. *(Can't see it yet — Phase 5 adds the UI. For now, trust the code: pirate=-90, merchant=+10, civilian=+5, militia=+55.)*
- [ ] Start new game as **Human Pirate** → pirate=-70 (disliked), militia=-30 (disliked)
- [ ] Start new game as **Human Bounty Hunter** → pirate=-100 (enemy), militia=+65 (liked)
- [ ] Start new game as **Martian Pirate** → militia=-10 (disliked) vs human pirate's -30
- [ ] Open comms (T) with any **pirate** ship → `(hostile)` tag visible (pirates are enemy for merchants/bounty hunters, disliked for pirates)
- [ ] Comms with a pirate: verify **Attack** and **Scan Cargo** are available, **Open Trade** is hidden (enemy/disliked = no trade)
- [ ] Comms with a **merchant** ship (as Human Merchant, merchant +10 neutral): verify **Open Trade** IS available
- [ ] Comms with a **merchant** ship (as Human Pirate, merchant -10 disliked): verify **Open Trade** is hidden
- [ ] Migrate an old save — not possible, new run required *(expected behavior)*

---

### Phase 2: Mission rep changes

#### Pre-implementation audit (guardrail 5)

**1. Existing modules to extend/reuse:**
- ``faction.py`` — hosts ``modify_rep()`` and rep delta tables; ``get_attitude()`` already detects zone crossings
- ``mission.py`` — ``complete_mission()`` is the single completion path for all mission types; already computes early/late bonus logic
- ``message_log.py`` — ``add_colored()`` for colored rep change messages
- ``__main__.py`` — TalkOutcome.DELIVER calls ``complete_mission()``; add rep changes right after
- ``combat/_encounter.py`` — bounty mission completion calls ``complete_mission()``; add rep changes right after

**2. Three duplication hotspots:**
- **(a) Rep delta values copied per call site.** The per-mission-type rep tables could get copy-pasted into both ``__main__.py`` (delivery) and ``combat/_encounter.py`` (bounty). Fix: store in ``faction.py`` as ``_MISSION_REP_DELTAS: dict[str, dict[str, int]]`` keyed by mission type.
- **(b) Zone-boundary detection duplicated.** Checking "was attitude X, now attitude Y" could be re-implemented at every rep change site. Fix: ``modify_rep()`` handles it internally via ``get_attitude()`` before/after comparison.
- **(c) ``complete_mission()`` bypass.** If rep changes are added to ``complete_mission()`` callers instead of the function itself, the pattern gets duplicated. Fix: add ``ctx`` parameter to ``complete_mission()`` and apply rep changes inside it based on mission type — one edit, both call sites covered.

**3. DRY strategy:**
- All rep delta tables live in ``faction.py`` as module-level constants
- ``modify_rep(ctx, faction, delta)`` handles clamping (-100..100), colored logging, and zone-boundary messages in ONE place
- ``complete_mission()`` takes ``ctx`` and applies rep deltas based on mission type, reusing existing early/late bonus logic

---

- [ ] Add `modify_rep(ctx, faction, delta)` helper to `faction.py` — handles logging, zone-boundary messages
- [ ] Wire `modify_rep` into all four mission completion paths in `mission.py`:
  - Delivery → merchant rep
  - Bounty (pirate target) → militia rep + merchant rep
  - Bar missions (intercept/smuggling/extortion/salvage) → pirate rep + merchant rep
- [ ] Early bonus: +50% rep gain on early delivery
- [ ] Smoke test + commit

#### DRY eval

- [ ] Are the rep change tables duplicated anywhere? Should live ONLY in `faction.py` as constants.
- [ ] Are all 4 mission completion paths using the same `modify_rep` helper?
- [ ] Check for hardcoded rep changes that bypass `modify_rep`.

#### Playtest checklist *(living — update as implementation reveals edge cases)*

**Delivery missions:**
- [ ] Complete a **delivery** mission → log shows `+5 rep with Merchant faction`
- [ ] Complete a delivery **early** (within 50% of deadline) → log shows base + 50% bonus (e.g. +5 → +8 merchant)

**Bounty missions:**
- [ ] Complete a **bounty** mission (pirate target) → log shows `-2 pirate, +3 merchant, +3 civilian, +5 militia`
- [ ] Complete a bounty early → +50% bonus on all deltas

**Bar missions:**
- [ ] Complete an **intercept** mission → `+5 pirate, -10 merchant, -2 civilian, -5 militia`
- [ ] Complete a **smuggling** mission → `+2 pirate, -5 merchant, -5 civilian, -8 militia`
- [ ] Complete an **extortion** mission → `+5 pirate, -5 merchant, -3 civilian, -3 militia`
- [ ] Complete a **salvage** mission → `+3 pirate, -3 merchant, 0 civilian, -2 militia`

**Edge cases:**
- [ ] **Abort** a mission (Q → abandon) → **no rep change** logged
- [ ] Complete a mission that crosses a zone boundary → zone-crossing message fires
- [ ] Rep clamped at +100 / -100 (complete a mission while already at cap)

---

### Phase 3: Combat rep changes

- [ ] Wire `modify_rep` into `_handle_combat_encounter` (or death handler) — check the dead entity's spec faction
- [ ] Kill a pirate → adjust rep per table
- [ ] Kill a merchant → adjust rep per table
- [ ] Kill a militia ship → adjust rep per table
- [ ] Flee from combat → small rep penalty to lawful factions
- [ ] Squad kill bonus: +1 bonus rep per squad cleared
- [ ] Smoke test + commit

#### DRY eval

- [ ] Are combat rep changes using the same `modify_rep` helper as missions?
- [ ] Is there a single function that handles all kill-based rep changes, or is it duplicated per faction?

#### Playtest checklist *(living — update as implementation reveals edge cases)*

**Kills:**
- [ ] Kill a **pirate** ship → log shows `-3 pirate, +2 merchant, +2 civilian, +3 militia`
- [ ] Kill a **merchant** ship → log shows `+5 pirate, -8 merchant, -3 civilian, -5 militia`
- [ ] Kill a **militia** ship → log shows `+8 pirate, -5 merchant, -5 civilian, -12 militia`
- [ ] Kill a **civilian** ship → log shows `+5 pirate, -5 merchant, -8 civilian, -5 militia`

**Other combat actions:**
- [ ] **Flee** from combat → log shows `-1 merchant, -1 civilian, -2 militia` (cowardice penalty)
- [ ] Initiate **unprovoked attack** via comms → log shows `+2 pirate, -2 merchant, -2 civilian, -3 militia`

**Squad bonus:**
- [ ] Kill an entire **pirate squad** (e.g. 3 ships) → verify extra `+1` bonus rep to relevant factions per squad cleared
- [ ] Kill a **bounty squad** → verify squad bonus applies

**Edge cases:**
- [ ] Kill a ship whose faction isn't in the 4 tracked factions → no rep change, no crash
- [ ] Kill multiple ships in one combat → all deltas logged individually

---

### Phase 4: Hostility + mission gating

- [ ] Add `modify_mission_tier(planet_tier, attitude) -> int` helper to `faction.py`
- [ ] Wire attitude-adjusted tiers into `fill_empty_slots` for procedural missions
- [ ] Wire attitude-adjusted pay scaling into mission generation (apply % bonus/penalty to `reward_credits`)
- [ ] Add enemy hostility to NPC movement: in `npcs_ships.py`, check attitude and set hostile target for `"enemy"` factions (deterministic, no probability check)
- [ ] Smoke test + commit

#### DRY eval

- [ ] Is the hostility check duplicated between `_tick_npcs` and `_detect_combat_encounter`? Should be one helper.
- [ ] Are the pay-scaling and tier-modification formulas centralized in `faction.py`?

#### Playtest checklist *(living — update as implementation reveals edge cases)*

**Mission gating:**
- [ ] As Human Merchant (militia **Liked** +55): visit Earth → militia mission board offers **+1 tier** better missions (if planet tier supports it)
- [ ] As Human Pirate (militia **Disliked** -30): militia missions are **penalized** (reduced tier/pay)
- [ ] As Human Merchant (pirate **Enemy** -90): no pirate-faction missions offered *(bar missions not yet gated — future)*
- [ ] As Human Bounty Hunter (militia **Liked** +65): verify +1 tier on militia bounty boards

**NPC hostility (deterministic):**
- [ ] Pirate NPCs as Human Bounty Hunter (pirate **Enemy** -100): pirates **attack on sight** — they move toward you and engage at detect range
- [ ] Pirate NPCs as Human Pirate (pirate **Disliked** -70): pirates show `(hostile)` in comms but do **NOT auto-attack**
- [ ] Merchant NPCs as Human Merchant (merchant **Neutral** +10): never hostile unless player attacks first
- [ ] Militia NPCs as Human Bounty Hunter (militia **Liked** +65): never hostile, may hail with greetings

**Edge cases:**
- [ ] Enemy NPCs in a different system — when player jumps in, they immediately move toward player
- [ ] Disliked NPCs at close range — verify they do NOT engage (no probability check)

---

### Phase 5: Faction UI viewer

- [ ] Add "Factions" option to the ship menu (hangar mode)
- [ ] Build reputation viewer modal showing: faction name, current score, progress bar, attitude label
- [ ] Wire zone-boundary logging into `modify_rep` (already defined in Phase 2, just ensure messages are formatted)
- [ ] Smoke test + commit

#### Playtest checklist *(living — update as implementation reveals edge cases)*

**Basic UI:**
- [ ] Open ship hangar (bump your ship in city) → **"Factions"** option visible in menu
- [ ] Select "Factions" → viewer shows all 4 factions with correct scores
- [ ] Verify each faction shows: name, current score, progress bar, attitude label

**Progress bars:**
- [ ] Enemy zone (-100 to -76) → bar rendered in / with correct fill
- [ ] Disliked zone (-75 to -26) → bar rendered correctly
- [ ] Neutral zone (-25 to +25) → bar rendered correctly
- [ ] Liked zone (+26 to +75) → bar rendered correctly
- [ ] Allied zone (+76 to +100) → bar rendered correctly

**Live updates:**
- [ ] Complete a mission → reopen Factions → viewer reflects updated rep values
- [ ] Kill a ship in combat → reopen Factions → viewer reflects updated values

**Zone-boundary messages:**
- [ ] Cross from Neutral → Liked: log message `+N rep with X faction (now +26, Neutral → Liked)`
- [ ] Cross from Liked → Neutral: log message with zone change noted
- [ ] Cross from Disliked → Enemy: log message with zone change
- [ ] Rep change within same zone: log message without zone-change suffix

**Navigation:**
- [ ] ENTER / ESC closes the viewer and returns to ship menu
- [ ] Guide (?) works from within the viewer

---

### Phase 6: Monthly decay + trade pricing

- [ ] Wire `modify_rep` into `time._on_month_change` for decay logic (only for non-neutral zones)
- [ ] Add trade price modifiers to `faction.py` helpers: `buy_price_modifier(attitude) -> float` and `sell_price_modifier(attitude) -> float`
- [ ] Wire price modifiers into `trade.py` (city trade) and `open_npc_trade` (ship-to-ship trade)
- [ ] Smoke test + commit

#### DRY eval

- [ ] Is the month-change decay logic a single loop over all factions, or duplicated per faction?
- [ ] Are trade price modifiers centralized (one function each for buy/sell) or duplicated across city and ship trade?

#### Playtest checklist *(living — update as implementation reveals edge cases)*

**Monthly decay:**
- [ ] Become **Allied** with militia (+76+): advance one month → verify **-3 decay** toward neutral
- [ ] Become **Liked** with merchants (+26 to +75): advance one month → verify **-2 decay**
- [ ] Become **Disliked** with pirates (-75 to -26): advance one month → verify **+2 decay** (toward neutral)
- [ ] Become **Enemy** with pirates (-100 to -76): advance one month → verify **+3 decay**
- [ ] **Neutral** zone (-25 to +25): advance one month → verify **no decay** at all

**Decay boundary stops:**
- [ ] At +26 (bottom of Liked): decay stops at **+1** — cannot cross from positive to negative via decay alone
- [ ] At -26 (top of Disliked): decay stops at **-1** — cannot cross from negative to positive via decay alone
- [ ] Only player actions can change the sign of a reputation

**Trade pricing:**
- [ ] Become **Allied** with militia (+76+) → verify **+10% sell / -10% buy** at militia faction stations
- [ ] Become **Enemy** with merchants (-76 or lower) → verify **cannot trade** at merchant shops at all
- [ ] Become **Liked** with merchants → verify **+5% sell / -5% buy**
- [ ] **Neutral** with a faction → verify **standard prices** (no modifier)

**Stacking:**
- [ ] Trade price modifiers stack correctly: `base_price × skill_discount × rep_discount` (multiplicative)
- [ ] Price modifiers apply to both city trade (trade terminals) and ship-to-ship trade (comms → Open Trade)

---

### Phase 7: Guide + final polish

- [ ] Update in-game guide with faction reputation section
- [ ] Full DRY/RNG audit on all new code
- [ ] Final playtest pass

#### Final playtest checklist *(living — update as implementation reveals edge cases)*

**Guide:**
- [ ] Open guide (?) → faction reputation section present and accurate
- [ ] Guide explains: 5 attitude zones with thresholds, how rep changes (missions/combat/decay), what each zone means for gameplay (hostility/trade/missions)

**Full run smoke test:**
- [ ] Start as Human Merchant → complete several missions → see rep values change over time
- [ ] Cross at least 3 zone boundaries during a session → verify all log messages are clear and correctly formatted
- [ ] Advance multiple months → verify decay is working and stops at boundaries
- [ ] Trade at stations with different faction attitudes → verify price modifiers apply

**Extreme states:**
- [ ] Become **Enemy with ALL four factions** (< -76 each) → log says *"With no faction willing to work with you, the galaxy has closed its doors"*
- [ ] Become **Allied with ALL four factions** (+76+ each) → verify all allied bonuses stack correctly

**No regressions:**
- [ ] Smoke test passes before final commit
- [ ] All existing mission types work (delivery, bounty, bar if implemented)
- [ ] Combat works with all faction combos
- [ ] Comms panel works for all attitude zones

---

## Open questions

1. ~~**Should bar missions be gated on pirate rep?**~~ Deferred — will align when bar missions are implemented.
2. **Should there be a "max" rep that resets on death like XP?** Yes — same as XP, rep resets on fresh run.
3. **Can the player be Enemy with every faction?** Theoretically yes, but that would mean everyone attacks on sight and no one offers work — effectively game over without reset. The system should allow this (player choice) with a clear log message: "With no faction willing to work with you, the galaxy has closed its doors."
4. ~~**Should militia always start friendly?**~~ Deferred to starting-rep table (above).
5. **Trade pricing: should allied discounts stack with existing piloting skill bonuses?** Yes — they're multiplicative: base_price × skill_discount × rep_discount.
