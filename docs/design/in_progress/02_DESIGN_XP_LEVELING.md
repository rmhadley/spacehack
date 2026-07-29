# DESIGN: Player XP & Leveling

## Overview

Add a leveling system that gives meaning to the XP already being awarded by missions and combat. Currently `reward_xp` is computed and displayed but immediately discarded — levels would make it a real progression driver.

### What levels unlock

Leveling grants **2 skill points per level** (each point adds +2 to one pilot skill). The only other unlock milestones are trait choices at 20 and 30. No hull/fuel/cargo/shield/slot bonuses — progression is purely about pilot skill growth.

- **Gunnery** → weapon accuracy (`gunnery * 0.5` added to hit chance)
- **Piloting** → AP per turn (`3 + piloting // 20`), dodge bonus (`piloting * 0.5`)
- **Engineering** → max power pool (`power_gen * 2 + engineering // 5`)

| Level | Unlock |
|-------|--------|
| Every level | +2 skill points (+4 to distribute across skills) |
| 20 | **Major trait** — pick one from all playstyle-qualifying options |
| 30 | **Capstone trait** — pick one from all playstyle-qualifying options (cannot repeat) |

**Trait choices (level 20):**

| Trait | Effect |
|-------|--------|
| Overcharge | +25% max shield capacity |
| Ace Pilot | +1 AP per turn |
| Scavenger | +50% cargo from loot drops |

**Capstone traits (level 30):**

| Trait | Effect |
|-------|--------|
| Ghost | Enemy detect radius halved |
| Juggernaut | -50% missile damage taken |
| Maverick | Unlock unique ship dialogue + faction interactions |

## Philosophy alignment

| Principle | How it applies |
|-----------|---------------|
| **ctx-first** | XP total and level tracked on `GameContext` as `player_xp: int` and `player_level: int` |
| **Data-first** | Level thresholds live in a simple table, not scattered logic |
| **Live-by-side-effect** | XP earned via `add_xp(ctx, amount)` that levels up and applies bonuses immediately |
| **Simple > clever** | Max level 30, 2 skill points per level, playstyle-gated traits at 20 and 30 |

## Starting skill rebalance

Currently species and class skill bonuses are inflated to feel impactful because they're static (Pirate: gunnery+15; Merchant: engineering+15; Bounty Hunter: gunnery+10, piloting+10). With leveling adding +2 per skill point, these would stack into OP territory. Starting bonuses should be cut roughly in half so that:

- **Leveling feels meaningful** — a level 5 player with spent points noticeably outskills a level 1
- **Class identity is preserved** — Pirates still have the best gunnery, Merchants the best engineering, etc.
- **No stat bloat** — a level 10 Pirate shouldn't have gunnery 70+ just from base + class

### Proposed rebalance (not yet implemented — done during Phase 1)

**Species bonuses** (currently small, just trim a bit):

| Species | Current | Proposed |
|---------|---------|----------|
| Human | gunnery+5, piloting+0, engineering+5 | gunnery+3, piloting+0, engineering+3 |
| Martian | gunnery+5, piloting+10, engineering+5 | gunnery+3, piloting+5, engineering+3 |

**Class bonuses** (currently chunky — cut roughly in half):

| Class | Current | Proposed |
|-------|---------|----------|
| Pirate | gunnery+15, piloting+10, engineering+0 | gunnery+8, piloting+5, engineering+0 |
| Merchant | gunnery+0, piloting+5, engineering+15 | gunnery+0, piloting+3, engineering+8 |
| Bounty Hunter | gunnery+10, piloting+10, engineering+5 | gunnery+5, piloting+5, engineering+3 |

**Resulting starting totals** (base 30 + species + class):

| Combo | Gunnery | Piloting | Engineering |
|-------|---------|----------|-------------|
| Human Pirate | 41 (was 50) | 5 (was 10) | 3 (was 5) |
| Human Merchant | 33 (was 35) | 3 (was 5) | 11 (was 20) |
| Human Bounty Hunter | 38 (was 45) | 5 (was 10) | 6 (was 10) |
| Martian Pirate | 41 (was 50) | 10 (was 20) | 3 (was 5) |
| Martian Merchant | 33 (was 35) | 8 (was 15) | 11 (was 20) |
| Martian Bounty Hunter | 38 (was 45) | 10 (was 15) | 6 (was 10) |

These numbers keep clear class identity (Pirates hit hardest, Merchants run systems best, Bounty Hunters are balanced) while leaving 30+ points of growth via leveling before hitting end-game power.

This rebalance is applied in **Phase 1** alongside the XP tracking so the new starting values go live at the same time as the leveling system.

## Data model

### New fields on `GameContext`

- **`player_xp: int = 0`** — total XP earned (cumulative, never resets)
- **`player_level: int = 1`** — current level (starts at 1)
- **`player_skill_points: int = 0`** — unspent skill points (earned on level-up)
- **`player_gunnery_bonus: int = 0`** — bonus added to gunnery from skill points
- **`player_piloting_bonus: int = 0`** — bonus added to piloting from skill points
- **`player_engineering_bonus: int = 0`** — bonus added to engineering from skill points

### Upgrade from reading

The current skill formula is: `PILOT_SKILL_BASE (30) + species_bonus + class_bonus + module_bonuses`

With leveling it becomes: `PILOT_SKILL_BASE (30) + species_bonus + class_bonus + module_bonuses + level_bonus + skill_point_bonus`

Where:
- `level_bonus` = `(player_level - 1) * 2` (2 skill points per level)
- `skill_point_bonus` = manually assigned bonus from `player_*_bonus` fields

Note: `level_bonus` is auto-assigned — each level gives 2 skill points, spent via the UI. The formula above shows total growth from leveling.

### XP rewards

| Source | XP formula | Notes |
|--------|-----------|-------|
| Mission completion | Based on tier + distance (already computed as `reward_xp`) | Already exists, just needs to feed into `add_xp()` |
| Combat kill | `enemy_base_hull * 2` | New — adds XP for non-mission kills too |

### Level thresholds (max level 30)

Each level costs `50 + level * 20` XP:

| Level | XP to reach | Cumulative XP | Skill points (2/level) | Stat points earned | Trait choice |
|-------|------------|---------------|----------------------|-------------------|--------------|
| 1 | 0 | 0 | 0 | 0 | |
| 2 | 90 | 90 | 2 | 4 | |
| 3 | 110 | 200 | 4 | 8 | |
| 4 | 130 | 330 | 6 | 12 | |
| 5 | 150 | 480 | 8 | 16 | |
| 6 | 170 | 650 | 10 | 20 | |
| 7 | 190 | 840 | 12 | 24 | |
| 8 | 210 | 1,050 | 14 | 28 | |
| 9 | 230 | 1,280 | 16 | 32 | |
| 10 | 250 | 1,530 | 18 | 36 | |
| 11-19 | 270-430 | 2,070-6,930 | 20-36 | 40-72 | |
| 20 | 450 | 7,380 | 38 | 76 | **Major trait** |
| 21-29 | 470-630 | 7,850-12,210 | 40-56 | 80-112 | |
| 30 | 650 | 12,860 | 58 | 116 | **Capstone trait** |

Formula: `xp_for_level(n) = 50 + n * 20` for n > 1.

**Why this curve:**
- Early levels (2-5) cost ~90-150 XP — a mission or two, or 3-5 combat kills
- Mid levels (10-15) cost ~250-350 XP — a T2/T3 mission worth of effort
- Late levels (20-30) cost ~450-650 XP — significant but achievable with T3/T4 missions
- Cumulative XP to reach cap is ~12,860 — achievable in a long successful run

A T1 mission gives ~20 XP. A T4 mission gives ~300 XP. A combat kill gives ~30-200 XP.

At level 20, the player has earned **38 skill points (76 stat points invested)** and must choose their major trait. A Human Pirate who invested everything in gunnery would have gunnery = 41 + 76 = 117 (but soft-capped at 100), with piloting=5 and engineering=3. A balanced build would be roughly gunnery=79, piloting=43, engineering=41.

### Skill point allocation

When the player levels up, they earn 2 skill points. They can spend them via a new "Skills" option in the ship menu (accessible from the hangar menu in city mode):

```
═══════════════════════════
       SKILLS (Level 3)
═══════════════════════════
Skill Points Available: 2

> Gunnery:     42 [+]
  Piloting:    37 [+]
  Engineering: 35 [+]

[H]elp  [Enter] spend  [Tab] cycle  [ESC] back
```

Each point spent adds +2 to that skill. The "max" is soft-capped at 100 (harder to justify spending beyond that due to diminishing returns on hit chance).

### Trait choices — playstyle-gated pool

Both level 20 and level 30 draw from the **same shared trait pool**. At each milestone, the game scans your playstyle counters and shows **every trait you qualify for** (no RNG). You pick one per milestone, and you cannot pick the same trait twice.

**Design goal:** Players can learn the thresholds and *play toward* a specific trait. "If I want Overcharge, I need to take 2000+ damage by level 20."

#### Full trait pool

| Trait | Effect | Threshold (Level 20) | Threshold (Level 30) | Playstyle |
|-------|--------|---------------------|---------------------|-----------|
| **Overcharge** | +25% max shield capacity | 2000+ damage taken | 5000+ damage taken | Survivor |
| **Ace Pilot** | +1 AP per turn | 10+ combat flees | 25+ combat flees | Aggressive pilot |
| **Scavenger** | +50% cargo from loot drops | 15+ merchant kills | 40+ merchant kills | Pirate |
| **Laser Mastery** | +20% laser damage | 500+ laser shots fired | 1500+ laser shots | Lasers specialist |
| **Missile Barrage** | +25% missile velocity | 300+ missile shots fired | 1000+ missile shots | Missiles specialist |
| **Plasma Overload** | +15% plasma crit chance | 200+ plasma shots fired | 800+ plasma shots | Plasma specialist |
| **Sharpshooter** | +10% hit chance | 60+ gunnery (after skill points) | 80+ gunnery | Gunnery focus |
| **Evasive** | +15% dodge chance | 40+ piloting (after skill points) | 60+ piloting | Piloting focus |
| **Power Surge** | +5 max power | 40+ engineering (after skill points) | 60+ engineering | Engineering focus |
| **Bounty Network** | +15% mission credit rewards | 10+ bounties completed | 25+ bounties completed | Bounty hunter |
| **Trade Route** | -5% buy / +5% sell prices | 20+ deliveries completed | 50+ deliveries completed | Merchant |
| **Juggernaut** | -50% missile damage taken | 30+ kills (any) | 80+ kills (any) | Veteran |
| **Hardened** | -10% all damage taken | 2000+ damage taken + 50+ kills | 5000+ damage taken + 150+ kills | Battle-scarred |

#### How selection works

```
at level 20:
  > For each trait in pool:
  >   Evaluate threshold against current playstyle counters
  >   If threshold met -> add to available list
  > Show ALL available traits (no randomization)
  > Player picks one
  > Mark trait as taken (cannot repeat at 30)

at level 30:
  > Same process, using level 30 thresholds
  > Filter out already-picked trait
  > Player picks one
```

#### Reputation-gated traits

In addition to the playstyle counters, the trait system also checks the player's **faction reputation** (see `DESIGN_FACTION_REPUTATION.md`). Allied status with a faction unlocks unique faction-themed traits, while being universally hated unlocks a renegade capstone:

| Trait | Effect | Threshold (Level 20) | Threshold (Level 30) | Playstyle |
|-------|--------|---------------------|---------------------|-----------|
| **Merchant Alliance** | -15% buy / +15% sell prices at all shops | Allied with merchants (+76+ rep) | Allied with merchants (+76+ rep) | Diplomat |
| **Pirate King** | +20% loot from ships, pirate NPCs never aggro | Allied with pirates (+76+ rep) | Allied with pirates (+76+ rep) | Outlaw |
| **Militia Commission** | -20% scan chance, militia patrols give waypoints | Allied with militia (+76+ rep) | Allied with militia (+76+ rep) | Lawful |
| **Galaxy's Most Wanted** | +1 AP per turn, +15% all damage, but EVERYONE attacks on sight — no docking at faction stations, no missions, no trade | Enemy with ALL four factions (< -76 each) | Enemy with ALL four factions (< -76 each) | Renegade |

**How rep-gated selection works:**
- These are checked alongside the playstyle counters at level 20 and level 30
- If you're Allied with merchants AND qualify for normal playstyle traits, you see both
- `Galaxy's Most Wanted` is a special case — it only shows if you're literally enemy with EVERYONE, and picking it locks you out of normal gameplay. It's a true "burn it all down" capstone
- Rep-gated traits cannot repeat across levels 20 and 30 (same rule as playstyle traits)

#### Playstyle tracking counters

These lightweight counters live on `GameContext` and are incremented during normal gameplay:

| Counter | Type | Incremented when |
|---------|------|-----------------|
| `times_fired_lasers` | `int` | Each laser shot in combat |
| `times_fired_missiles` | `int` | Each missile shot in combat |
| `times_fired_plasma` | `int` | Each plasma shot in combat |
| `merchant_kills` | `int` | Merchant-type enemy defeated |
| `bounties_completed` | `int` | Bounty mission turned in |
| `deliveries_completed` | `int` | Delivery mission turned in |
| `total_kills` | `int` | Any enemy defeated (combat) |
| `total_damage_taken` | `int` | Damage received in combat |
| `combat_flees` | `int` | Player fled from combat |

These counters persist throughout a run and reset on death (fresh start).

#### How selection works (full)

```
at level 20:
  > For each trait in pool (playstyle + rep-gated):
  >   Evaluate threshold against current playstyle counters + faction rep
  >   If threshold met -> add to available list
  > Show ALL available traits (no randomization)
  > Player picks one
  > Mark trait as taken (cannot repeat at 30)

at level 30:
  > Same process, using level 30 thresholds
  > Filter out already-picked trait
  > Player picks one
```

**Edge case:** A player who is Allied with merchants AND has 500+ laser shots AND 60+ gunnery at level 20 would see:
```
Level 20 — Choose a Major Trait:
> Laser Mastery       — +20% laser damage
> Sharpshooter        — +10% hit chance
> Merchant Alliance   — -15% buy / +15% sell prices
```

They can pick whichever fits their build — no restrictions other than thresholds.

### XP gain notification

When the player gains XP, the message log adds: `"+40 XP"`. On level-up: `"Level 4! 2 skill points earned."` At level 20/30: `"Level 20! Choose a major trait."`

### Phase 1.5: Playtest

**Checklist:**
- [ ] Complete a mission → XP gain logged
- [ ] Kill an enemy in combat → XP gain logged
- [ ] Level up → 2 skill points awarded
- [ ] Open ship menu → "Skills" option visible
- [ ] Spend skill points → skills change
- [ ] Enter combat → new skill values reflected in hit chance / AP / power

### Phase 2: Skill point UI

- [ ] Add "Skills" option to the ship menu (hangar)
- [ ] Build skill allocation modal: show current skills + available points, allow spending
- [ ] Wire skill point bonuses into `starting_pilot_skills` and combat init formulas
- [ ] Add visual feedback on point spend

### Phase 3: HUD display + polish

- [ ] Add XP bar or level indicator to the HUD (compact: "Lv.3" near stats)
- [ ] Add "Next level: 400/500 XP" to the skills screen
- [ ] Log messages on level-up with details
- [ ] Level-up screen flash or banner effect

### Phase 4: Traits at 20/30

- [ ] Trait selection modal at level 20
- [ ] Trait selection modal at level 30
- [ ] Wire trait effects into combat formulas
- [ ] Apply soft-cap at 100 for skills

### Phase 5: Guide update + final polish

- [ ] Update in-game guide with leveling system docs
- [ ] DRY audit on all new code
- [ ] Re-verify starting skill rebalance numbers

## Open questions

1. **Max level is 30.** (Answered) Tiers 20 and 30 have major trait choices.
2. **Should skill point allocation be respec-able?** For v1, no. Make each point count.
3. **Do enemies scale with player level?** Not directly — tier-based missions already provide the right difficulty curve. A level 30 player fighting a T1 pirate_scout should feel like a god.
4. **Should there be class-specific bonuses on level-up?** Not in v1 — keep it simple. Class identity comes from starting skill bonuses.
5. **Should XP be lost on death?** No — roguelike death means the run is over anyway. The player starts fresh at level 1.
