# DESIGN: Player XP & Leveling

## Overview

Add a leveling system that gives meaning to the XP already being awarded by missions and combat. Currently `reward_xp` is computed and displayed but immediately discarded — levels would make it a real progression driver.

### What levels unlock

Leveling grants **5 skill points per level** (each point adds +1 to any of the six skills — ship or ground). Skills are viewed and points spent via the **Character screen** (`C` hotkey, accessible from city or space). The only other unlock milestones are trait choices at 40 and 50 — both draw from the **same shared pool** — with level 60 reserved for a future capstone specialization built on the two traits locked in. No hull/fuel/cargo/shield/slot bonuses — progression is purely about stat growth.

> **Update (base-10 rebalance):** The original design shipped with base 30 stats and 2 skill points per level (sized for the then-3-stat pilot-skill system). With six stats sharing the budget, the start was lowered to **base 10** (fresh nobody) and the grant raised to **9 SP/level**.

> **Update (60-level expansion):** Max level raised to **60** and the grant cut to **5 SP/level** (59 levels × 5 = 295 total) — the same total budget as before, but stretched across the full main-story length instead of the first quarter of it. Each level is exactly **one 5-point step**, matching the per-5 stat granularity. A dedicated L60 specialist still **maxes out 3 of the 6 stats** at the 100 cap.

**Keybinding:** `C` opens the Character screen. Cargo was moved to `I` (Inventory) to free up `C`. The Character screen is NOT in the ship hangar menu — it's a global hotkey like `F` for Factions.

- **Gunnery** → weapon accuracy (`gunnery * 0.5` added to hit chance)
- **Piloting** → AP per round (`3 + piloting / 10`, fractional with carry), dodge bonus (`piloting * 0.5`)
- **Engineering** → max power pool (`power_gen * 2 + engineering // 5`)

> **Update (per-5 stat steps):** every stat effect steps at 5-point
> granularity so a 5-point investment is always visible. Piloting's AP
> formula was `3 + piloting // 20` (dead zones of 19 points), then
> `3 + piloting // 10` (dead zones of 9 points); it is now **fractional
> with carry** (see below) so every single point shifts the average.
> Pilot dodge still moves every 2 points. Player Strength now adds +1
> melee damage per 5 points (was per 10) and +1 Expedition Pack slot
> per 5 points above 10 (was per 10); monsters keep the legacy
> 10-point divisor so their tuned damage is unchanged.
> Gunnery/Reflexes (per 2), Engineering power (per 5), and Stamina HP
> (per 3) already satisfied the rule.

### Fractional AP (speed with carry)

AP regenerates **fractionally with carry** — a TE4/DCSS-style speed
system that keeps the current round structure. Each round an actor
banks a gain of `3 + piloting / 10` AP (in tenths, so the math is
exact), spends the integer part, and the leftover tenths roll into the
next round's pool:

- Piloting 15 → gain 4.5 AP/round → rounds of **4, 5, 4, 5, …** (avg 4.5)
- Piloting 10 → gain 4.0 AP/round → a flat **4** every round
- Piloting 5 → gain 3.5 AP/round → rounds of **3, 4, 3, 4, …** (avg 3.5)

Every 5 piloting points is worth an extra action every two rounds, and
every single point shifts the long-run average — no dead zones. The
combat HUD shows the real pool as the denominator: `AP: 3/4.5` means
3 spendable AP plus 0.5 banked. Ground combat uses the same mechanism
with its flat gain (`4 + Ace Pilot + armor` bonuses); today those
bonuses are integers so ground rounds stay whole.

Unspent AP is still forfeited at round end (waiting ends the turn);
only the *fraction* carries, never banked whole AP.

| Level | Unlock |
|-------|--------|
| Every level | +5 skill points (+5 to distribute across the six skills at +1 each) |
| 40 | **Trait choice** — pick one from the shared pool |
| 50 | **Trait choice** — pick another from the SAME pool (cannot repeat) |
| 60 | **Capstone (future)** — specialization based on the two traits locked in at 40/50; design pending |

**Shared trait pool** (available at both level 40 and 50):

| Trait | Milestone | Requires | Effect |
|-------|-----------|----------|--------|
| Sharpshooter | 40/50 | 40+ gunnery | +10% hit chance |
| Hauler | 40/50 | 20+ merchant missions | Merchant mission tier band shifts up one (T1→T2, capped at T4) |
| Fixer | 40/50 | 20+ Bar missions | Bar mission tier band shifts up one (T1→T2, capped at T4) |
| Hunter | 40/50 | 20+ bounty missions | Bounty mission tier band shifts up one (T1→T2, capped at T4) |
| Ace Pilot | 40/50 | 40+ piloting | +1 AP per turn |
| Juggernaut | 40/50 | 30+ total kills | Take 1 less damage from each ground attack |
| Charger | 40/50 | 40+ melee kills | Melee weapons reach current AP; charges gain +5 hit and +1 damage per tile |
| Evasive | 40/50 | 40+ reflexes | +5% baseline ground evade |
| Pack Mule | 40/50 | 40+ strength | +2 Expedition Pack slots |
| Ironclad | 40/50 | 40+ stamina | +6 maximum ground HP |
| Systems Expert | 40/50 | 40+ engineering | +10 maximum ship power |
| Demolitionist | 40/50 | 15 explosive hits | +25% explosive splash damage |
| Laser Specialist | 40/50 | 100 laser shots | +10% laser hit chance |
| Missileer | 40/50 | 15 missile shots | +10% missile hit chance |
| Plasma Savant | 40/50 | 100 plasma shots | Plasma weapons cost 1 less AP |

The unlock requirements are intentionally **easy to meet by level 40** —
the point is not to grind gates but to prove a build: a laser user has
fired 100 laser shots, a melee specialist has 40 melee kills, and a
focused pilot has hit 40 piloting. The gates stop gating; they
*suggest* the playstyle that earned them. The skill-40 requirements
(Sharpshooter, Ace Pilot, Evasive, Pack Mule, Ironclad, Systems
Expert) are the ones that keep forcing real decisions, since they
require deliberately concentrated stat investment.

The pool rewards focused ship skills, ground stats, equipment usage, and combat style. A player can choose only one trait at each milestone, so specialization remains a meaningful tradeoff.

## Philosophy alignment

| Principle | How it applies |
|-----------|---------------|
| **ctx-first** | XP total and level tracked on `GameContext` as `player_xp: int` and `player_level: int` |
| **Data-first** | Level thresholds live in a simple table, not scattered logic |
| **Live-by-side-effect** | XP earned via `add_xp(ctx, amount)` that levels up and applies bonuses immediately |
| **Simple > clever** | Max level 60, 5 skill points per level, playstyle-gated traits at 40 and 50, capstone slot reserved at 60 |

## Starting skill rebalance (base 10)

Starting stats sit low (a fresh nobody) so the growth arc is long and species/class bonuses land with real weight — a flagship +12 is 2.5-3x the base 10. With 295 skill points over a full run, a dedicated specialist can **max 3 of the 6 stats**; the rest stay partial.

### Design target

Level 1 stats sit in the 10-26 range. At level 60 with focused investment, a specialist maxes out 3 stats at the 100 cap. Class identity is unmistakable at creation — a Pirate's Gunnery is ~2.4x a Merchant's — and the gap narrows with leveling as the player chooses where to invest.

### Rebalance (applied with the base-10 change)

**Species bonuses** (small flavor adjustments; total ~4 across each domain):

| Species | G | P | E | REF | STR | STA |
|---------|---|---|---|-----|-----|-----|
| Human | +2 | 0 | +2 | +2 | 0 | +2 |
| Martian | 0 | +4 | 0 | +4 | 0 | 0 |

**Class bonuses** (clear identity, no negatives):

| Class | G | P | E | REF | STR | STA |
|-------|---|---|---|-----|-----|-----|
| Pirate | +12 | 0 | 0 | 0 | +12 | 0 |
| Merchant | 0 | 0 | +12 | 0 | 0 | +12 |
| Bounty Hunter | +4 | +4 | +4 | +4 | +4 | +4 |

**Resulting starting totals** (base 10 + species + class):

| Combo | G | P | E | REF | STR | STA |
|-------|---|---|---|-----|-----|-----|
| Human Pirate | **24** | 10 | 12 | 12 | **22** | 12 |
| Human Merchant | 12 | 10 | **24** | 12 | 10 | **22** |
| Human BH | 16 | 14 | 16 | 16 | 14 | 16 |
| Martian Pirate | **22** | 14 | 10 | 14 | **22** | 10 |
| Martian Merchant | 10 | 14 | 22 | 14 | 10 | 22 |
| Martian BH | 14 | **18** | 14 | **18** | 14 | 14 |

At level 60: a Human Pirate dumping all 295 points maxes 3 stats (e.g. Gunnery 100, Strength 100, Engineering 100: 76 + 78 + 88 = 242 ≤ 295). A balanced BH reaches ~85-90 in three stats. The remaining three stats stay at base 10 — every point spent is a real tradeoff.

This rebalance was applied alongside the XP tracking update so the new starting values went live with the leveling system.

## Data model

### New fields on `GameContext`

- **`player_xp: int = 0`** — total XP earned (cumulative, never resets)
- **`player_level: int = 1`** — current level (starts at 1)
- **`player_skill_points: int = 0`** — unspent skill points (earned on level-up)
- **`player_gunnery_bonus: int = 0`** — bonus added to gunnery from skill points
- **`player_piloting_bonus: int = 0`** — bonus added to piloting from skill points
- **`player_engineering_bonus: int = 0`** — bonus added to engineering from skill points
- **`player_traits: list[str] = field(default_factory=list)`** — chosen trait IDs
- **`player_counters: PlayerCounters = field(default_factory=PlayerCounters)`** — playstyle and faction-career tracking (see below)

### PlayerCounters dataclass

Single structure on ctx instead of 9 individual fields:

```python
@dataclass
class PlayerCounters:
    """Playstyle tracking counters for trait qualification.
    
    All counters reset on death (fresh run). Incremented during
    normal gameplay by the combat loop, mission completion, and
    trade paths.
    """
    laser_shots: int = 0
    missile_shots: int = 0
    plasma_shots: int = 0
    merchant_kills: int = 0
    total_kills: int = 0
    bounties_completed: int = 0
    deliveries_completed: int = 0  # legacy merchant-delivery counter
    merchant_missions_completed: int = 0
    bar_missions_completed: int = 0
    bounty_missions_completed: int = 0
    total_damage_taken: int = 0
    melee_kills: int = 0
    explosive_hits: int = 0
```

Incremented via: `ctx.player_counters.total_kills += 1`. One field on ctx. Extensible — add a counter to the dataclass, update the trait catalog, done.

### Upgrade from reading

The current skill formula is: `PILOT_SKILL_BASE (10) + species_bonus + class_bonus + module_bonuses`

With leveling it becomes: `PILOT_SKILL_BASE (10) + species_bonus + class_bonus + module_bonuses + level_bonus + skill_point_bonus`

Where:
- `level_bonus` = `(player_level - 1) * 5` (5 skill points per level)
- `skill_point_bonus` = manually assigned bonus from `player_*_bonus` fields

Note: `level_bonus` is auto-assigned — each level gives 5 skill points, spent via the UI. The formula above shows total growth from leveling.

### XP rewards

| Source | XP formula | Notes |
|--------|-----------|-------|
| Mission completion | Based on tier + distance (already computed as `reward_xp`) | Already exists, just needs to feed into `add_xp()` |
| Combat kill | `enemy_base_hull * 2` | New — adds XP for non-mission kills too |

### Level thresholds (max level 60)

Each level costs `40 + level * 25` XP:

| Level | XP to reach | Cumulative XP | Skill points (5/level) | Trait choice |
|-------|------------|---------------|------------------------|--------------|
| 1 | 0 | 0 | 0 | |
| 2 | 90 | 90 | 5 | |
| 3 | 115 | 205 | 10 | |
| 4 | 140 | 345 | 15 | |
| 5 | 165 | 510 | 20 | |
| 6 | 190 | 700 | 25 | |
| 7 | 215 | 915 | 30 | |
| 8 | 240 | 1,155 | 35 | |
| 9 | 265 | 1,420 | 40 | |
| 10 | 290 | 1,710 | 45 | |
| 11-19 | 315-515 | 2,025-5,445 | 50-90 | |
| 20 | 540 | 5,985 | 95 | |
| 21-29 | 565-765 | 6,550-11,970 | 100-140 | |
| 30 | 790 | 12,760 | 145 | |
| 31-39 | 815-1,015 | 13,575-20,995 | 150-190 | |
| 40 | 1,040 | 22,035 | 195 | **Trait choice** |
| 41-49 | 1,065-1,265 | 23,100-32,520 | 200-240 | |
| 50 | 1,290 | 33,810 | 245 | **Trait choice** |
| 51-59 | 1,315-1,515 | 35,125-46,545 | 250-290 | |
| 60 | 1,540 | 48,085 | 295 | **Capstone (future)** |

Formula: `xp_for_level(n) = 40 + n * 25` for n > 1. Level 2 costs 90 XP —
identical to the old curve, so the tutorial top-up to level 2 lands exactly
where it did before.

**Why this curve:**
- Early levels (2-5) cost ~90-165 XP — a mission or two, or 3-5 combat kills (nearly unchanged from the old curve)
- Mid levels (10-20) cost ~290-540 XP — steeper than before, so levels stop "rolling in" around level 10
- Late levels (30-60) cost ~790-1,540 XP — the back half is genuinely expensive
- Cumulative XP to reach cap is ~48,085 — about 4.5x the old 10,730, roughly matching the main story's full length (the old cap landed at ~25% of the game)

A T1 mission gives ~20 XP. A T4 mission gives ~300 XP. A combat kill gives ~30-200 XP.

At level 40, the player has earned **195 skill points** and must choose their first trait. A Human Pirate who funnels them into gunnery and strength would cap both (24 + 76 → 100, 22 + 78 → 100) with a little left over — a real tradeoff, since 195 points can't stretch across all six stats.

### Character screen (C hotkey)

A new **Character screen** accessed via the `C` hotkey from city or space mode. This is the start of an RPG-style character sheet that will grow with future features. For this feature, it shows:

- Current level and XP progress
- Skill ratings with available points to spend
- Chosen traits (once earned)

The screen is NOT in the ship menu — it's a global hotkey like `F` for Factions.

**Keybinding note:** `C` is already taken by Cargo in space mode, so the Character screen uses `C`.

```
══════════════════════════════════════════════
           CHARACTER — Level 3 Pirate
══════════════════════════════════════════════

  XP: 320 / 480  [████████░░░░]  Next: 160 XP

  Skill Points Available: 5

  > Gunnery:     24  [+]
    Piloting:    10  [+]
    Engineering: 12  [+]
    Reflexes:    12  [+]
    Strength:    22  [+]
    Stamina:     12  [+]

  Traits: (none yet — unlock at level 40)

══════════════════════════════════════════════
  ENTER spend  TAB cycle  ESC back
```

Each point spent adds +1 to that skill. The "max" is soft-capped at 100 (diminishing returns on hit chance make going beyond 100 pointless). At the cap, `[+]` shows `MAX`.

### PilotSkills integration

The existing skill pipeline: `character.starting_pilot_skills()` → stored in `ctx.stats.gunnery/piloting/engineering` (a `HudStats` object) → read by combat init (`_encounter.py`).

Level-up bonuses feed into this pipeline via `ctx.player_*_bonus` fields. When the player spends a skill point, the bonus field is incremented and `ctx.stats` is immediately updated:

```python
def _apply_skill_point(ctx, skill: str) -> None:
    """Spend one skill point on *skill* (gunnery/piloting/engineering).
    
    Each point adds +1 to the skill. Soft-capped at 100.
    """
    if ctx.player_skill_points <= 0:
        return
    current_val = getattr(ctx.stats, skill)
    if current_val >= 100:
        return  # soft cap
    bonus_field = f"player_{skill}_bonus"
    setattr(ctx, bonus_field, getattr(ctx, bonus_field, 0) + 1)
    ctx.player_skill_points -= 1
    # Immediately update HudStats so combat + HUD see the change.
    setattr(ctx.stats, skill, current_val + 1)
```

This keeps the single source of truth (`ctx.stats`) in sync with the persistent bonus counters (`ctx.player_*_bonus`) without requiring every combat read site to sum multiple fields.

### Trait catalog (data-first)

Traits follow the existing data catalog pattern (like weapons/ships/modules). New file `data/traits/core.py`:

```python
from dataclasses import dataclass

@dataclass(frozen=True)
class Trait:
    """One player trait — earned at level 40 or 50 if counters qualify."""
    id: str
    name: str
    description: str
    # Counter requirements: list of (counter_field, min_value) pairs.
    # ALL must be met for the trait to appear at a milestone.
    counters: tuple[tuple[str, int], ...]
    # Optional: (faction, attitude) — faction rep gate.
    rep_required: tuple[str, str] | None = None

# Registry — shared pool for both level 40 and 50.

SHARPSHOOTER = Trait(
    id="sharpshooter",
    name="Sharpshooter",
    description="+10% hit chance in combat",
    counters=(("gunnery", 40),),
)

HAULER = Trait("hauler", "Hauler", "Merchant boards shift one mission tier higher", (("merchant_missions_completed", 20),))
FIXER = Trait("fixer", "Fixer", "Bar boards shift one mission tier higher", (("bar_missions_completed", 20),))
HUNTER = Trait("hunter", "Hunter", "Bounty boards shift one mission tier higher", (("bounty_missions_completed", 20),))

ACE_PILOT = Trait(
    id="ace_pilot",
    name="Ace Pilot",
    description="+1 AP per turn in combat",
    counters=(("piloting", 40),),
)

JUGGERNAUT = Trait(
    id="juggernaut",
    name="Juggernaut",
    description="Take 1 less damage from each ground attack",
    counters=(("total_kills", 30),),
)

CHARGER = Trait(
    id="charger",
    name="Charger",
    description="Melee weapons reach current AP; charging grants +5 hit and +1 damage per tile",
    counters=(("melee_kills", 40),),
)

EVASIVE = Trait("evasive", "Evasive", "+5% baseline ground evade", (("reflexes", 40),))
PACK_MULE = Trait("pack_mule", "Pack Mule", "+2 Expedition Pack slots", (("strength", 40),))
IRONCLAD = Trait("ironclad", "Ironclad", "+6 maximum ground HP", (("stamina", 40),))
SYSTEMS_EXPERT = Trait("systems_expert", "Systems Expert", "+10 maximum ship power", (("engineering", 40),))
DEMOLITIONIST = Trait("demolitionist", "Demolitionist", "+25% explosive splash damage", (("explosive_hits", 15),))
LASER_SPECIALIST = Trait("laser_specialist", "Laser Specialist", "+10% laser hit chance", (("laser_shots", 100),))
MISSILEER = Trait("missileer", "Missileer", "+10% missile hit chance", (("missile_shots", 15),))
PLASMA_SAVANT = Trait("plasma_savant", "Plasma Savant", "Plasma weapons cost 1 less AP", (("plasma_shots", 100),))

ALL_TRAITS: tuple[Trait, ...] = (
    SHARPSHOOTER, HAULER, FIXER, HUNTER, ACE_PILOT, JUGGERNAUT, CHARGER,
    EVASIVE, PACK_MULE, IRONCLAD, SYSTEMS_EXPERT, DEMOLITIONIST,
    LASER_SPECIALIST, MISSILEER, PLASMA_SAVANT,
)
```

**Selection at milestone:** `_qualifying_traits(ctx)` scans `ALL_TRAITS`, checks each against `ctx.player_counters` (and optionally `ctx.faction_reputation`), returns list. Player picks one. Stored in `ctx.player_traits`.

**Effect application:** `has_trait(ctx, trait_id)` checks `ctx.player_traits`. Called at point of use (e.g. `if has_trait(ctx, 'ace_pilot'): ap += 1` in combat).

### XP gain notification

When the player gains XP, the message log adds: `"+40 XP"`. On level-up: `"Level 4! 5 skill points earned."` At level 40/50: `"Level 40! Choose a trait (C key)."`

### Phase 1: XP tracking + skill rebalance

#### Pre-implementation audit (guardrail 5)

**Existing modules to extend/reuse:**
- `input_helpers.py` — add `_is_c_press()` for Character screen hotkey (reuses the freshly-freed C key)
- `__main__.py` — wire C hotkey for Character screen, I hotkey for cargo (already done in keybinding refactor)
- `game_context.py` — add `PlayerCounters` dataclass + `player_counters`, `player_traits` fields
- `character.py` — `starting_pilot_skills()` already computes base+species+class; modify bonuses per rebalance table. `starting_stats()` feeds `HudStats`.
- `data/species/core.py` + `data/classes/core.py` — update frozen `PilotSkills` values per rebalance table
- `mission.py` — `complete_mission()` already has `reward_xp`; feed into `add_xp()`
- `combat/_encounter.py` — VICTORY path: add combat XP per kill
- `hud.py` — add level/XP bar
- `menus/_ship_menu.py` — NOT touched (Character screen uses C hotkey, not ship menu)

**Three duplication hotspots:**
1. **XP award duplicated across mission completion and combat kill.** Fix: single `add_xp(ctx, amount)` function in new `xp.py` module that handles level-up logic, logging, and trait triggers.
2. **Skill total formula scattered across combat/HUD/character.** Fix: all skill values flow through `ctx.stats` (HudStats) — `_apply_skill_point()` updates `ctx.stats` directly, combat reads from `ctx.stats`, HUD reads from `ctx.stats`. Single source of truth.
3. **Counter increments copy-pasted across combat actions.** Fix: `ctx.player_counters` is a single dataclass — increment via `ctx.player_counters.total_kills += 1`. No helper needed; the attribute access is clean enough.

**DRY strategy:**
- `xp.py` owns: `add_xp()`, `xp_for_level()`, level-up logic, `_apply_skill_point()`, `_qualifying_traits()`
- `ctx.stats` is the single source of truth for current skill values
- `ctx.player_counters` is the single structure for all playstyle counters
- Species/class rebalance: edit the frozen `PilotSkills` values in data files only

#### Checklist

- [x] Add `player_xp`, `player_level`, `player_skill_points`, `player_*_bonus` fields to `GameContext`
- [x] Add `PlayerCounters` dataclass + `player_counters` field to `GameContext`
- [x] Create `xp.py` with `add_xp(ctx, amount)`, `xp_for_level(level)`, `_apply_skill_point()`
- [x] Update species skill bonuses in `data/species/core.py` (new values per rebalance table)
- [x] Update class skill bonuses in `data/classes/core.py` (new values per rebalance table)
- [x] Wire `add_xp()` into `mission.complete_mission()` call path
- [x] Wire `add_xp()` into `combat/_encounter.py` VICTORY path (per-kill)
- [x] Add `_is_c_press()` to `input_helpers.py`, wire C hotkey in `__main__.py`
- [x] Smoke test + commit

#### Playtest checklist

- [ ] Start new game → verify starting skills match rebalance table (e.g. Human Pirate: 24/10/12)
- [ ] Complete a delivery mission → XP gain logged, level-up if threshold crossed
- [ ] Kill an enemy in combat → XP gain logged
- [ ] Level up → "Level N! 5 skill points earned." message
- [ ] Press C → Character screen opens (shows level/XP, skills section with available points)
- [ ] Character screen accessible from both city and space modes

---

### Phase 2: Skill point UI (Character screen)

#### Pre-implementation audit

**Existing modules to extend/reuse:**
- `help.py` — existing guide modal pattern (render + update + Modal.run)
- `menus/_ship_menu.py` — `_run_faction_view()` is the closest analogue: read-only stats modal opened via hotkey, with ESC to close. Follow the same pattern.
- `hud.py` — `_render_help_lines()` for key hints; already shows `K - Character` (added in Phase 1)
- `faction.py` — `_ALL_FACTIONS` tuple pattern for cycling UI elements

**Three duplication hotspots:**
1. **Skill display repeated across Character screen + HUD.** Fix: Character screen calls `ctx.stats` (single source of truth); HUD already reads from `ctx.stats`.
2. **Modal close-on-ESC pattern.** Fix: reuse existing `ui.Modal(ctx.context, console).run(render, update)` pattern from `_run_faction_view()`.
3. **Keybinding wired in two places.** Fix: `_is_k_press()` in `input_helpers.py` + `__main__.py` handler (single pattern, same as F).

**DRY strategy:**
- Character screen is a self-contained modal in its own file: `src/spacehack/character_screen.py`
- `_apply_skill_point()` is called from the modal's update function
- Follows the exact pattern of `_run_faction_view()`: standalone function taking `ctx`, called from hotkey handler

#### Checklist

- [ ] Create `character_screen.py` with `open_character_screen(ctx)` entry point
- [ ] Build modal: show level, XP bar, skill values with [+], available points, trait slots
- [ ] TAB cycles between Gunnery/Piloting/Engineering; ENTER spends a point
- [ ] Wire `_apply_skill_point()` to update both `ctx.player_*_bonus` and `ctx.stats`
- [ ] Soft-cap visual: highlight skills at 100 to indicate diminishing returns
- [ ] Smoke test + commit

#### Playtest checklist

- [ ] Press K → Character screen shows current level, XP bar, skill values, available points
- [ ] Have 2+ skill points → TAB to Gunnery, ENTER → gunnery increases by 2, points decrease by 1
- [ ] Spend all points → [+] indicators disappear
- [ ] Launch into space → check combat HUD: new skill values reflected in hit chance / AP / power
- [ ] Character screen from space mode → same values, consistent

---

### Phase 3: HUD display + polish

#### Pre-implementation audit

**Existing modules to extend/reuse:**
- `hud.py` — `render_hud()` already shows species/class/HP/credits/skills; add compact level indicator
- `message_log.py` — level-up messages use existing `add_colored()` with event color
- `xp.py` — `add_xp()` already logs XP gain; add level-up message with skill point count

**Three duplication hotspots:**
1. **Level indicator drawn differently in city vs space HUD.** Fix: single helper `_render_xp_bar()` called from both branches. Uses `#` for filled, `-` for empty (CP437-safe characters that render on the tcod tilesheet — same as faction bars).
2. **XP progress bar duplicated between Character screen and HUD.** Fix: both call the same `_render_xp_bar()` helper in `hud.py`; Character screen imports it.
3. **Level-up message format duplicated.** Fix: single format string in `xp.py` `add_xp()`, not in HUD.

**DRY strategy:**
- `_render_xp_bar(value, max_val, width)` is a pure helper in `hud.py` — returns a string like `"[#####-----]"`
- Character screen and HUD both call it
- All level-up logic in `xp.py`; HUD only reads `ctx.player_level` and `ctx.player_xp`

**Tcod-safe characters:** Bar uses `#` (filled) and `-` (empty) — both in CP437 (the tilesheet character set). Avoid `█` (U+2588), `░` (U+2591), and other Unicode block chars that may not render. Same convention as faction reputation progress bars.

#### Checklist

- [x] Add compact XP bar to city HUD: `"LV 4 [#####-----]"` between key hints and footer
- [x] Add compact XP bar to space HUD: same format, same position
- [x] Extract `_render_xp_bar(value, max_val, width)` helper in `hud.py`
- [x] `add_xp()` logs `"+N XP"` on gain, `"Level N! 5 skill points earned."` on level-up
- [x] Character screen shows detailed XP progress bar using same helper
- [x] Add `C` to HUD key hints in both city and space modes
- [x] Verify XP bar renders with CP437-safe `#`/`-` chars on the tilesheet
- [x] Smoke test + commit

#### Playtest checklist

- [ ] City HUD shows `"LV 1 [----------]"` for a new character (0 XP)
- [ ] Gain XP from a mission → XP bar fills, "+NN XP" in message log
- [ ] Level up → bar resets to empty for new level, "Level N!" message is colored
- [ ] Character screen shows XP progress bar with same format
- [ ] Both city and space HUDs show `C` in key hints

---

### Phase 4: Traits at 40/50

#### Pre-implementation audit

**Existing modules to extend/reuse:**
- `xp.py` — `add_xp()` already fires on level-up; add trait-check trigger when level == 40 or 50
- `data/traits/core.py` — new: frozen `Trait` dataclass + `ALL_TRAITS` registry
- `mission.py` — `deliveries_completed` / `bounties_completed` incremented in `complete_mission()` via `ctx.player_counters`
- `combat/_rules_space.py` and `combat/_loop.py` — per-shot counters (laser/missile/plasma) and explosive-hit counters incremented at the accepted fire boundary
- `combat/_encounter.py` — per-kill counters (`total_kills`, `merchant_kills`) incremented via `ctx.player_counters` in VICTORY path
- `combat/_loop.py` — `total_damage_taken` incremented on damage
- `faction.py` — reputation-gated traits (future) check `ctx.faction_reputation`

**Three duplication hotspots:**
1. **Trait threshold checking duplicated for counter + rep-gated traits.** Fix: `xp.py` has single `_qualifying_traits(ctx)` that iterates `ALL_TRAITS`, evaluates against `ctx.player_counters` (and `ctx.faction_reputation` if `rep_required` is set), returns list.
2. **Trait effect application scattered across combat/trade.** Fix: `xp.py` exports `has_trait(ctx, trait_id) -> bool`; each domain checks the flag at point of use (e.g. `if has_trait(ctx, 'ace_pilot'): ap += 1`).
3. **Counter increments copy-pasted.** Fix: direct attribute access on `ctx.player_counters` is clean enough — no helper needed. `ctx.player_counters.total_kills += 1` is one line.

---

### Phase 5: Guide update + final polish

#### Pre-implementation audit

**Existing modules to extend/reuse:**
- `help.py` — add leveling/traits section to `GUIDE_SECTIONS` or expand existing Character section
- `character_screen.py` — trait descriptions visible on the Character screen

**Three duplication hotspots:**
1. **Trait descriptions duplicated between guide and trait selection modal.** Fix: guide references trait names, not full descriptions; trait modal shows full text.
2. **Level threshold formula duplicated.** Fix: `xp_for_level()` is the single source; guide references it conceptually.
3. **Guide section structure.** Fix: follow existing pattern — one `GuideSection` with title + body, appended to `GUIDE_SECTIONS` tuple.

**DRY strategy:**
- Guide is a separate text layer; all game logic stays in `xp.py`
- No code duplication between guide and game systems

#### Checklist

- [ ] Add "Leveling & Traits" section to `_GUIDE_CHARACTER` or as a new `_GUIDE_LEVELING` section
- [ ] Guide explains: XP sources, level curve, skill points, trait system, soft cap at 100
- [ ] Full DRY audit on all new code
- [ ] Re-verify starting skill rebalance numbers match actual gameplay
- [ ] Smoke test + commit

## Open questions

1. **Max level is 60.** (Answered) Tiers 40 and 50 have trait choices; 60 is reserved for the capstone specialization.
2. **Should skill point allocation be respec-able?** For v1, no. Make each point count.
3. **Do enemies scale with player level?** Not directly — tier-based missions already provide the right difficulty curve. A level 60 player fighting a T1 pirate_scout should feel like a god.
4. **Should there be class-specific bonuses on level-up?** Not in v1 — keep it simple. Class identity comes from starting skill bonuses.
5. **Should XP be lost on death?** No — roguelike death means the run is over anyway. The player starts fresh at level 1.
