# DESIGN: Mission System Overhaul

## Overview

Complete rebuild of the mission system from a single-slot, static-catalog model
to a multi-slot, tiered, clock-driven system with both hand-crafted and procedural
delivery missions. The existing two merchant delivery missions and one bounty
mission are replaced.

---

## Philosophy Alignment

| Principle | How it's met |
|-----------|-------------|
| Data-first | Static missions are frozen dataclasses in `data/missions/`. Procedural missions are pure functions that return specification dicts — no mutation, no side effects. |
| ctx-first | Mission board state, completed-mission tracking, and active mission list live on `GameContext`. No bare globals. |
| Roguelike RNG | All procedural generation uses `engine.RNG`. Same seed = same mission board. |
| Atomic commits | Phased implementation, one commit per phase. |

---

## Data Model

### 1. `MissionSpec` — static (hand-crafted) mission template

Replaces the existing `Mission` dataclass. Lives in `data/missions/__init__.py`.

```python
@dataclass(frozen=True)
class MissionSpec:
    id: str                           # "merchants_delivery_earth_mars"
    title: str                        # "Supply Run: Earth → Mars"
    description: str                  # Flavor text
    giver_npc_id: str                 # Which NPC offers this
    faction: str                      # "merchants", "bounty", "militia", "bar"
    mission_type: str                 # "delivery", "bounty", "patrol", "flavor"
    tier: int                         # 1-4, controls where it appears and reward scaling
    reward_credits: int               # Base payout
    reward_xp: int                    # Base XP
    deadline_days: int = 0            # 0 = no deadline
    early_bonus_pct: int = 0          # % bonus if completed in < 50% of deadline

    # --- Delivery-specific fields ---
    required_cargo_size: int = 0
    delivery_target_npc_id: str | None = None
    delivery_target_planet_id: str | None = None
    origin_planet_id: str | None = None  # NEW: source planet, used for tier gating

    # --- Bounty-specific fields ---
    target_enemy_id: str | None = None
    target_system_id: str | None = None

    # --- Recommendations (soft hints) ---
    recommended_class_id: str | None = None
    recommended_ship_min_cargo: int = 0
```

### 2. `ActiveMission` — player's accepted mission

Extended from the current single-slot dataclass. Lives in `mission.py`.

```python
@dataclass
class ActiveMission:
    mission_id: str                   # MissionSpec.id, or generated key for procedural
    is_procedural: bool = False
    status: MissionStatus = MissionStatus.IN_PROGRESS

    # Delivery fields (copied from spec for procedural, or looked up for static)
    required_cargo_size: int = 0
    delivery_target_npc_id: str | None = None
    delivery_target_planet_id: str | None = None

    # Bounty fields
    bounty_spawn_id: str | None = None
    target_enemy_id: str | None = None
    target_system_id: str | None = None

    # Deadline
    time_deadline: tuple[int, int, int] | None = None
    deadline_days: int = 0
    accept_day: int = 0               # Game day when accepted (for early-bonus calc)

    # Reward
    reward_credits: int = 0
    reward_xp: int = 0
    early_bonus_pct: int = 0

class MissionStatus(Enum):
    IN_PROGRESS = auto()
    COMPLETED = auto()    # NEW
    FAILED = auto()       # NEW (deadline expired)
```

### 3. `MissionBoard` — per-NPC offering state

Stored on `GameContext`. Keyed by NPC id.

```python
@dataclass
class MissionBoard:
    npc_id: str
    slots: list[str | None]           # Mission spec IDs or generated keys; None = empty
    max_slots: int                    # 3-5 depending on NPC/faction
    last_refresh_month: int           # Game month when last refreshed (0 = never)
```

### 4. Procedural delivery mission generator

Pure function that produces a dict of mission fields from RNG + parameters.

```python
def generate_delivery_mission(
    origin_planet_id: str,
    tier: int,
    rng: random.Random,
) -> dict:
    """Return a dict with all fields needed to construct an ActiveMission
    for a delivery contract. Picks a destination planet in a different system
    within tier-appropriate jump range, generates cargo, deadline, and reward."""
```

---

## GameContext Changes

| Field | Type | Purpose |
|-------|------|---------|
| `player_active_missions` | `list[ActiveMission]` | Replaces `player_active_mission`. Max 5. |
| `completed_mission_ids` | `set[str]` | Static mission IDs the player has finished. Prevents reruns. |
| `mission_boards` | `dict[str, MissionBoard]` | Per-NPC board state. Lazy-initialized on first talk. |

Remove:
- `player_active_mission: ActiveMission | None`

---

## Tier System

Tiers mirror weapon `tech_level` (1-4):

| Tier | Label | Example location | Cargo | Reward range | Deadline |
|------|-------|-----------------|-------|-------------|----------|
| 1 | Local | Earth, Mars | 5-10 | 50-150$ | 5-10 days |
| 2 | Regional | Alpha Centauri, Barnard's Star | 10-20 | 150-400$ | 10-20 days |
| 3 | Sector | Vega, Sirius, Procyon | 20-40 | 400-800$ | 20-35 days |
| 4 | Frontier | Wolf 359, Luyten's Star | 40-60 | 800-1500$ | 35-60 days |

**Per-planet tier availability**: Each planet has a `mission_tier` field (defaults to 1).
Mission givers on that planet only offer missions at that tier or below.
A tier-3 planet might offer tier 1-3 missions; a tier-1 planet only tier 1.

Uses a **separate** `mission_tier` field on `PlanetSpec` (not `tech_level`).
This keeps mechanics like shop inventory (tech_level) independent from
mission availability (mission_tier). A high-tech military outpost could have
high mission_tier even if its tech_level is moderate.

---

## Mission Board Lifecycle

### Initial population (first visit)
When the player first talks to an NPC giver:
1. Check if `ctx.mission_boards` has an entry for this NPC. If not, create one.
2. If `last_refresh_month == 0` (never refreshed), fill ALL slots:
   - Static hand-crafted missions for this NPC whose `tier <= planet_tier` AND
     whose `id` is NOT in `ctx.completed_mission_ids`
   - Remaining slots: generate procedural delivery missions
3. Set `last_refresh_month = ctx.time_month` (but NOT year — so first talk counts as refreshed)

### Month rollover refresh
In `_on_month_change`:
1. For each `MissionBoard` in `ctx.mission_boards`:
   - Count empty (None) slots
   - For each empty slot: pick a new mission (static first, then procedural)
   - Update `last_refresh_month`

### Player accepts a mission
1. Remove the mission from the board slot (set to None)
2. Add `ActiveMission` to `ctx.player_active_missions` (if < 5)

### Player completes a mission
1. Remove from `ctx.player_active_missions`
2. If static: add `mission_id` to `ctx.completed_mission_ids`
3. Grant reward (with early bonus if applicable)
4. Drop cargo

### Player abandons a mission
1. Remove from `ctx.player_active_missions`
2. Drop cargo
3. Static missions go back onto the board (NOT added to completed)

---

## Early Completion Bonus

When the player delivers before 50% of the deadline has elapsed:
- Bonus = `reward_credits * early_bonus_pct / 100` (default 25-50% for delivery missions)
- Logged: "Early delivery bonus: +X$"

Computed in `complete_mission`:
```python
if active.deadline_days > 0 and active.accept_day > 0:
    elapsed = current_game_day - active.accept_day
    if elapsed < active.deadline_days // 2:
        bonus = active.reward_credits * active.early_bonus_pct // 100
```

---

## Multi-Mission Display

### HUD changes
Instead of showing one mission title, show compact indicators:
```
Missions: [1] Supply Run: Earth→Mars     (Due: 3 days)
          [2] Bounty: Pirate Scout        (Barnard's)
          [+]  2 more...
```
Or: show count and use Q to open quest log for details.

### Quest log changes
Currently shows one mission. Needs to show a list of up to 5 with navigation.
Same modal pattern — arrow keys to select, Enter for details, A to abandon.

### Accept flow
Currently blocks if `player_active_mission is not None`. Change to block if
`len(ctx.player_active_missions) >= 5`.

### Delivery check
Currently checks the single `player_active_mission` for deliverability.
Change to iterate `ctx.player_active_missions` — the first deliverable one
is handed over. If multiple are deliverable at the same NPC, show a picker.

---

## Procedural Delivery Mission Generation

### Algorithm
```python
def generate_delivery(origin_planet_id: str, max_tier: int, rng: random.Random) -> dict:
    # 1. Roll tier: weighted random 1..max_tier (lower tiers more common)
    #    - tier = min(rng.randint(1, max_tier), rng.randint(1, max_tier))
    #      (min-of-two gives a weighted curve: tier 4 appears ~6% of the time
    #       at a tier-4 planet, tier 1 appears ~44%)
    #
    # 2. Pick a destination planet in a different system
    #    - Filter systems reachable within tier-appropriate jump range
    #    - Pick a planet in that system with a landable port
    #
    # 3. Generate cargo amount: rng.randint(tier_min, tier_max)
    #
    # 4. Generate deadline: based on jump distance
    #    - Jump count between origin and dest systems (BFS)
    #    - deadline_days = (jumps * 4) + rng.randint(2, 6)
    #
    # 5. Generate reward:
    #    - credits = cargo * 10 * tier
    #    - xp = cargo * 2 * tier
    #    - early_bonus_pct = 25
    #
    # 6. Pick a delivery target NPC on the destination planet
    #
    # Returns dict with all fields for ActiveMission construction
```

**Tier weighting** uses `min(rng.randint(1, max_tier), rng.randint(1, max_tier))` —
the min-of-two-rolls gives a natural curve where higher tiers are rarer.
At a tier-4 planet: tier 1 ~44%, tier 2 ~31%, tier 3 ~19%, tier 4 ~6%.
This makes lucrative high-tier missions feel special when they appear.

### Generated ID format
`"proc_delivery_{origin}_{dest}_{hash}"` — unique per run, deterministic from RNG.

---

## Implementation Plan

### Phase 1: Data model foundations

**What**: Create `MissionSpec`, extend `ActiveMission`, add multi-slot ctx fields,
update runtime functions. Remove flavor mission dead code.

- [x] Create `MissionSpec` dataclass in `data/missions/__init__.py` (replacing `Mission`)
- [x] Add `mission_tier` field to `PlanetSpec` (default 1)
- [x] Extend `ActiveMission` with: `is_procedural`, `required_cargo_size`,
      `delivery_target_npc_id`, `delivery_target_planet_id`, `deadline_days`,
      `accept_day`, `reward_credits`, `reward_xp`, `early_bonus_pct`
- [x] Add `MissionStatus.COMPLETED` and `FAILED` to the enum
- [x] Add `player_active_missions: list[ActiveMission]`, `completed_mission_ids: set[str]`,
      `mission_boards: dict[str, MissionBoard]` to `GameContext`
- [x] Remove `player_active_mission: ActiveMission | None` from `GameContext`
- [x] Update `try_accept_mission` → validates up to 5 slots + cargo. Split into try/commit.
- [x] Add `active_is_deliverable_at` + `find_deliverable_missions` helpers for multi-mission
- [x] Update `complete_mission` → takes `ActiveMission`, supports early/late modifiers
- [x] Update `abort_mission` → takes `ActiveMission`
- [x] Remove flavor-only mission data (merchants.py, bounty.py emptied)
- [x] Remove all flavor-mission references from docstrings and comments
- [x] Smoke test passes

---

### → DRY Evaluation 1 (Phase 1)

*Run before moving to Phase 2. Covers Phase 1 changes only.*

| Check | What to look for |
|-------|-----------------|
| Duplicated iteration | Is `player_active_missions` iterated identically in accept/deliver/complete/abandon? Extract a helper if so. |
| Dead imports | `bar.py`, `militia.py`, `bounty.py` imports in `_build_registry` — cleaned up? |
| Signature mismatches | All callers of `try_accept_mission`, `is_deliverable_at`, `complete_mission`, `abort_mission` updated for new signatures? |
| Inner functions | Any new inner functions that should be module-level? |
| `ctx` contract | All new state through `GameContext`? No bare globals? |

---

### Phase 2: Hand-crafted delivery missions (tiered)

**What**: Convert existing delivery missions to `MissionSpec`, add 3-4 more
across tiers 1-3. Wire `mission_tier` on planets.

- [ ] Convert `merchants_supply_run_alpha_centauri` to `MissionSpec` format
- [ ] Convert `merchants_supply_run_tau_ceti` to `MissionSpec` format
- [ ] Add 1-2 new tier-1 delivery missions (Earth ↔ Mars, Earth → Barnard's Star)
- [ ] Add 1-2 new tier-2 delivery missions (AC Station → Sirius, etc.)
- [ ] Add 1 new tier-3 delivery mission (long-haul, e.g. Vega → Wolf 359)
- [ ] Set `mission_tier` on each `PlanetSpec` (Earth=1, Mars=1, AC=2, Sirius=2, Vega=3, etc.)
- [ ] Wire `missions_offered_by(npc_id, planet_tier)` to filter by tier and completed status
- [ ] Smoke test

---

### → Playtest 1 (Phase 2)

*First user-visible missions. Verify the core loop works.*

| # | Test | Expected |
|---|------|----------|
| 1 | Boot game, talk to guild master on Earth | See tier-1 delivery missions (2-3 options) |
| 2 | Accept a delivery | Cargo loads, mission appears in quest log (Q) |
| 3 | Accept a second delivery | Both missions in quest log |
| 4 | Fly to destination, bump the delivery NPC | Deliver option appears, cargo drops, reward granted |
| 5 | Return to guild master | Completed mission is NOT re-offered |
| 6 | Talk to guild master on a tier-2 planet (e.g. Alpha Centauri) | Tier-2 missions appear in addition to tier-1 |
| 7 | Abandon a mission (Q → A) | Cargo released, mission gone from log |

---

### Phase 3: Mission board infrastructure

**What**: Per-NPC `MissionBoard` state — slots, population, month-rollover refill.

- [ ] Create `MissionBoard` dataclass in `mission.py` or `game_context.py`
- [ ] Board initialization: on first NPC talk, fill all slots from static pool
      (tier ≤ planet tier, not in completed_ids), then procedural fill for remaining
- [ ] Wire `_on_month_change` in `time.py` to refill empty board slots
- [ ] Accept: removes mission from board slot (set to None)
- [ ] Abandon: static mission returns to board; procedural is discarded
- [ ] Board slot tracking: `last_refresh_month` prevents double-fill within same month
- [ ] Smoke test

---

### → Playtest 2 (Phase 3)

*Verify board lifecycle: populate, drain, refill.*

| # | Test | Expected |
|---|------|----------|
| 1 | First talk to guild master | Board populates with N missions (all slots filled) |
| 2 | Accept one mission | Board now has N-1 missions. Slot shows empty. |
| 3 | Accept all missions | Board shows "no work available" |
| 4 | Fly around until month rollover | Board refills empty slots with new missions |
| 5 | Abandon a static mission | That mission reappears on the board |
| 6 | Complete a static mission | It does NOT reappear (added to completed_ids) |
| 7 | Month rollover with full board | No change — full board stays full |

---

### → DRY Evaluation 2 (Phase 3)

*Run after Phase 3. Covers board logic + time integration.*

| Check | What to look for |
|-------|-----------------|
| Board fill logic | Filling static slots vs procedural slots — shared helper or duplicated? |
| Month rollover | `_on_month_change` growing too large? Extract a `_refresh_mission_boards` helper? |
| Slot manipulation | Accept, abandon, complete all touch board slots — is the slot-update logic in one place? |
| `last_refresh_month` | Computed once, passed cleanly — no off-by-one edge cases? |

---

### Phase 4: Procedural delivery generation

**What**: `generate_delivery_mission()` pure function. Jump-distance BFS.
Destination picker. Wire into board fill.

- [ ] Create `generate_delivery_mission(origin_planet_id, tier, rng)` pure function
      in a new `data/missions/procedural.py` (or inline in `mission.py`)
- [ ] Build jump-gate graph from `data/solar_systems/` for BFS distance calculation
- [ ] Destination planet picker: different system, landable port, within tier range
- [ ] Cargo amount: `rng.randint(tier_min, tier_max)` from tier table
- [ ] Deadline: `(jump_count * 4) + rng.randint(2, 6)` days
- [ ] Reward: `credits = cargo * 10 * tier`, `xp = cargo * 2 * tier`
- [ ] Delivery target NPC: pick from destination planet's buildings
- [ ] Generated ID: `"proc_delivery_{origin}_{dest}_{counter}"` — unique per run
- [ ] Wire into board fill as fallback after static missions exhausted
- [ ] Accept/complete/abandon flow for procedural missions (no completed_ids tracking)
- [ ] Smoke test

---

### → Playtest 3 (Phase 4)

*Verify procedural missions generate sensibly and integrate cleanly.*

| # | Test | Expected |
|---|------|----------|
| 1 | Accept all static missions from guild master | Remaining slots filled with procedural deliveries |
| 2 | Inspect a procedural mission | Cargo, destination, deadline, reward all look reasonable |
| 3 | Accept a procedural delivery | Cargo loads, quest log shows it (marked as procedural or not distinguished visually) |
| 4 | Complete a procedural delivery | Reward grants, cargo drops, mission gone |
| 5 | Abandon a procedural mission | Gone forever — does NOT return to board |
| 6 | Month rollover after exhausting board | New procedural missions generate, different from last month's |
| 7 | Check quest log with mix of static + procedural | Both types show correctly |

---

### → DRY Evaluation 3 (Phase 4)

*Run after Phase 4. Covers procedural generation + jump graph.*

| Check | What to look for |
|-------|-----------------|
| Jump graph build | Built once and cached, or rebuilt per call? Should be lazy-cached. |
| Destination selection | Filter chain (different system → landable → tier range) — clean pipeline or nested loops? |
| Static vs procedural accept | Two code paths or one unified `_accept_mission` helper? |
| Generated ID format | Collision-safe? Includes counter or hash? |

---

### Phase 5: Deadlines & early bonuses

**What**: Early completion bonus (50% of deadline), late penalty (half reward).
Quest log deadline display.

- [ ] Add `early_bonus_pct` to `MissionSpec` static missions (25-50%)
- [ ] Store `accept_day` on `ActiveMission` — computed from `ctx.time_day/month/year`
- [ ] In `complete_mission`: compute elapsed days, grant early bonus if < deadline/2
- [ ] Log: `"Early delivery bonus: +X$"` or `"Late delivery — half pay: +X$"`
- [ ] Quest log: show days remaining; red EXPIRED when overdue
- [ ] Expired missions still deliverable — half reward (50% credits, no XP bonus)
- [ ] Smoke test

---

### → Playtest 4 (Phase 5)

*Verify deadline mechanics and reward scaling.*

| # | Test | Expected |
|---|------|----------|
| 1 | Accept a mission with a deadline | Quest log shows "Due: Day X, Month Y (N days)" |
| 2 | Deliver quickly (well within deadline) | "Early delivery bonus: +X$" in log |
| 3 | Fly around, watch days remaining decrease in quest log | Countdown updates each day |
| 4 | Let a deadline expire | Quest log shows "EXPIRED" in red |
| 5 | Deliver an expired mission | "Late delivery — half pay: +X$" in log. Half credits, no XP bonus. |
| 6 | Deliver a mission right at the 50% mark | No bonus (must be strictly < deadline/2) |
| 7 | Mission with no deadline (deadline_days=0) | No deadline shown, no bonus, no late penalty |

---

### Phase 6: Multi-mission UI polish

**What**: Quest log list view, HUD mission indicator, delivery picker, slots-full message.

- [ ] Quest log: list view with up to 5 missions, arrow-key navigation, Enter for detail,
      A to abandon (with confirmation)
- [ ] HUD: compact mission indicator — count + first mission title truncated
- [ ] Delivery picker: if multiple missions deliverable at same NPC, show modal to pick one
- [ ] Accept flow: `"Your mission log is full (5/5). Abandon one first."` when at cap
- [ ] Cargo check on accept: sum of all mission cargo vs available capacity
- [ ] Smoke test

---

### → Playtest 5 (Phase 6)

*Full UI stress test. Push all the edges.*

| # | Test | Expected |
|---|------|----------|
| 1 | Accept 5 missions | Quest log shows all 5, navigable with arrows |
| 2 | HUD shows mission count | e.g. "Missions: 3" or compact list |
| 3 | Try to accept a 6th | Blocked with "mission log full" message |
| 4 | Two missions deliverable at same NPC | Picker appears; choose one to deliver |
| 5 | Abandon from quest log | Two-step confirm, cargo released, slot freed |
| 6 | Accept mission that would exceed cargo cap | Blocked with cargo-shortfall message |
| 7 | Mix of static + procedural in quest log | Both display correctly |
| 8 | Deliver one of multiple missions at NPC | Only that mission completes; others stay active |

---

### → DRY Evaluation 4 (Phase 6)

*Run after Phase 6. Covers UI code + final integration.*

| Check | What to look for |
|-------|-----------------|
| Quest log render | List rendering reused between mission list and detail view? |
| Delivery picker | Shares modal pattern with mission offering screen? |
| HUD mission display | Compact formatting — shared helper with quest log? |
| Cargo cap check | Same formula as `try_accept_mission`? Not duplicated in UI layer? |

---

### Phase 7: In-game guide review + final audit

**What**: Update `help.py` with full mission system documentation.
Final DRY pass over ALL mission code. RNG audit. Dead code sweep.

- [ ] Update `help.py` Game Overview: mention mission tiers, multiple slots, procedural generation
- [ ] Update `help.py` Missions section: full rewrite — types, tiers, deadlines, early bonus,
      board refresh, procedural vs static, quest log, delivery flow
- [ ] Update `help.py` Ships section: note cargo capacity matters for multi-mission stacking
- [ ] Update `help.py` Navigation section: mention that longer trips affect deadlines
- [ ] Final DRY scan: all mission files — duplication, inner functions, dead code
- [ ] Final RNG audit: every random call in mission code confirmed through `engine.RNG`
- [ ] Dead code sweep: removed flavor missions, old `Mission` dataclass references,
      single-slot `player_active_mission` stragglers
- [ ] Smoke test

---

### → Playtest 6 — Final (Phase 7)

*Full end-to-end playtest. Every system working together.*

| # | Test | Expected |
|---|------|----------|
| 1 | Fresh game, talk to guild master | Board populates with tier-1 static + procedural missions |
| 2 | Accept 3 missions, fly to destinations | All deliverable, rewards grant correctly |
| 3 | Abandon one, accept another | Board refills abandoned static; procedural lost |
| 4 | Month rollover while holding missions | Board refills. No active mission disruption. |
| 5 | Deliver with early bonus | Bonus message appears, correct amount |
| 6 | Let one expire, deliver late | Half reward, EXPIRED label cleared on delivery |
| 7 | Open game guide (?) in space and city | All mission sections accurate and up-to-date |
| 8 | Quest log with 5 missions | Navigation, detail, abandon all work |
| 9 | Delivery picker with 2+ missions at same NPC | Correct mission completes, others stay |
| 10 | Smoke test passes | `python3 tools/smoke.py` exits 0 |

---

## Resolved Decisions

- [x] **Expired deadline** → Deliver for half reward (50% credits, no XP bonus). Cargo stays.
- [x] **Tier gating** → New `mission_tier` field on `PlanetSpec`, separate from `tech_level`.
- [x] **Scope** → Delivery-only pass. Bounty/flavor are follow-up work. Remove all flavor-only
      mission references from the codebase during Phase 1.
- [x] **Board slot counts** → Guild master: 5 slots. Other NPCs defined when their missions are added.
- [x] **Month rollover** → Fill empty slots only, never wipe the full board.
- [x] **Procedural memory** → Ephemeral. Abandon = gone. New missions generate in freed slots.
