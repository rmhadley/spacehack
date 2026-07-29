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
| Disliked | Not hostile by default, but a % chance (based on how disliked: 10-40%) to go hostile when scanned at close range. |
| Neutral | Never hostile unless provoked. |
| Liked | Never hostile. May hail with greetings. |
| Allied | Never hostile. Hail with friendly dialogue. May offer tips/trade before being asked. |

**Implementation:** `npc_ships._tick_npcs` checks attitude via `get_attitude(ctx.faction_reputation[spec.faction])`. For `"enemy"` attitude, NPCs set a target toward the player's position and enter combat range.

### Trade access

| Attitude | Trade effect |
|----------|-------------|
| Enemy | Cannot trade at faction-owned shops or stations. |
| Disliked | -10% sell price, +10% buy price. Higher scan chance. |
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

### Phase 1: Attitude zones + starting rep

- [ ] Update `faction.get_attitude()` to return 5 zones instead of 3
- [ ] Add `faction.starting_reputation(species_id, class_id) -> dict[str, int]`
- [ ] Update `GameContext` default — remove hardcoded lambda, set to None, initialize in `__main__.py` at char creation
- [ ] Update existing defaut-rep call sites that rely on the hardcoded pirate=-100/etc
- [ ] Update `comms.py` to use new attitude zones (the "hostile" check becomes "enemy" or "disliked")
- [ ] Smoke test + commit

#### Playtest checklist

- [ ] Start a new game as Human Merchant → verify starting reps: pirate=-90, merchant=+10, civilian=+5, militia=+55
- [ ] Start a new game as Human Pirate → verify starting reps: pirate=-70, merchant=-10, civilian=-10, militia=-30
- [ ] Open comms with various NPCs → verify attitude labels match
- [ ] Migrate an existing save (not possible — new run required)

### Phase 2: Mission rep changes

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

#### Playtest checklist

- [ ] Complete a delivery mission → verify +5 merchant rep
- [ ] Complete a bounty mission → verify -2 pirate, +3 merchant, +3 civilian, +5 militia
- [ ] Complete a delivery early → verify +5 (base) + 50% = +8 merchant rep
- [ ] Abort a mission → verify no rep change

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

#### Playtest checklist

- [ ] Kill a pirate in combat → verify rep changes (pirate -3, merchant +2)
- [ ] Kill a merchant in combat → verify rep changes (merchant -8)
- [ ] Flee from combat → verify -1/-2 to lawful factions
- [ ] Kill a pirate squad of 3 → verify extra +1 per squad

### Phase 4: Hostility + mission gating

- [ ] Add `modify_mission_tier(planet_tier, attitude) -> int` helper to `faction.py`
- [ ] Wire attitude-adjusted tiers into `fill_empty_slots` for procedural missions
- [ ] Wire attitude-adjusted pay scaling into mission generation (apply % bonus/penalty to `reward_credits`)
- [ ] Add enemy hostility to NPC movement: in `npcs_ships.py`, check attitude and set hostile target for `"enemy"` factions
- [ ] Add `"disliked"` chance check in NPC movement (10-40% based on score) to go hostile
- [ ] Smoke test + commit

#### DRY eval

- [ ] Is the hostility check duplicated between `_tick_npcs` and `_detect_combat_encounter`? Should be one helper.
- [ ] Are the pay-scaling and tier-modification formulas centralized in `faction.py`?

#### Playtest checklist

- [ ] As a Human Merchant (militia Liked) → Earth militia should offer mission tier +1 (if planet supports it)
- [ ] As a Human Pirate (militia Disliked, pirate Enemy) → militia missions should be penalized or removed
- [ ] As a Human Merchant (pirate Enemy) → no missions from pirate-adjacent NPCs (none exist yet, but bar missions are gated by pirate rep in Phase 5)
- [ ] Enemy NPCs approach and attack on sight
- [ ] Disliked NPCs have a % chance to go hostile at close range

### Phase 5: Faction UI viewer

- [ ] Add "Factions" option to the ship menu (hangar mode)
- [ ] Build reputation viewer modal showing: faction name, current score, progress bar, attitude label
- [ ] Wire zone-boundary logging into `modify_rep` (already defined in Phase 2, just ensure messages are formatted)
- [ ] Smoke test + commit

#### Playtest checklist

- [ ] Open ship hangar → "Factions" option visible
- [ ] Select "Factions" → viewer shows all 4 factions with correct scores and bars
- [ ] Complete a mission → rep changes → viewer reflects updated values
- [ ] Cross a zone boundary → log message fires

### Phase 6: Monthly decay + trade pricing

- [ ] Wire `modify_rep` into `time._on_month_change` for decay logic (only for non-neutral zones)
- [ ] Add trade price modifiers to `faction.py` helpers: `buy_price_modifier(attitude) -> float` and `sell_price_modifier(attitude) -> float`
- [ ] Wire price modifiers into `trade.py` (city trade) and `open_npc_trade` (ship-to-ship trade)
- [ ] Smoke test + commit

#### DRY eval

- [ ] Is the month-change decay logic a single loop over all factions, or duplicated per faction?
- [ ] Are trade price modifiers centralized (one function each for buy/sell) or duplicated across city and ship trade?

#### Playtest checklist

- [ ] Become Allied with militia → verify +10% sell / -10% buy at militia stations
- [ ] Become Enemy with merchants → verify can't trade at merchant shops
- [ ] Advance one month → verify decay (if Liked, -2 towards neutral)
- [ ] Verify decay stops at zone boundary (+1/-1)

### Phase 7: Guide + final polish

- [ ] Update in-game guide with faction reputation section
- [ ] Full DRY/RNG audit on all new code
- [ ] Final playtest pass

## Open questions

1. ~~**Should bar missions be gated on pirate rep?**~~ Deferred — will align when bar missions are implemented.
2. **Should there be a "max" rep that resets on death like XP?** Yes — same as XP, rep resets on fresh run.
3. **Can the player be Enemy with every faction?** Theoretically yes, but that would mean everyone attacks on sight and no one offers work — effectively game over without reset. The system should allow this (player choice) with a clear log message: "With no faction willing to work with you, the galaxy has closed its doors."
4. ~~**Should militia always start friendly?**~~ Deferred to starting-rep table (above).
5. **Trade pricing: should allied discounts stack with existing piloting skill bonuses?** Yes — they're multiplicative: base_price × skill_discount × rep_discount.
