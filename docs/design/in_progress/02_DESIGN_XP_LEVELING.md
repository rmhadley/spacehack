# DESIGN: Player XP & Leveling

## Overview

Add a leveling system that gives meaning to the XP already being awarded by missions and combat. Currently `reward_xp` is computed and displayed but immediately discarded — levels would make it a real progression driver.

### What levels unlock

Leveling grants **2 skill points per level** (each point adds +2 to one pilot skill). Skills are viewed and points spent via the **Character screen** (`C` hotkey, accessible from city or space). The only other unlock milestones are trait choices at 20 and 30. No hull/fuel/cargo/shield/slot bonuses — progression is purely about pilot skill growth.

**Keybinding:** `C` opens the Character screen. Cargo was moved to `I` (Inventory) to free up `C`. The Character screen is NOT in the ship hangar menu — it's a global hotkey like `F` for Factions.

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

  Skill Points Available: 2

  > Gunnery:     42  [+]
    Piloting:    37  [+]
    Engineering: 35  [+]

  Traits: (none yet — unlock at level 20)

══════════════════════════════════════════════
  ENTER spend  TAB cycle  ESC back
```

Each point spent adds +2 to that skill. The "max" is soft-capped at 100 (harder to justify spending beyond that due to diminishing returns on hit chance).

### PilotSkills integration

The existing skill pipeline: `character.starting_pilot_skills()` → stored in `ctx.stats.gunnery/piloting/engineering` (a `HudStats` object) → read by combat init (`_encounter.py`).

Level-up bonuses feed into this pipeline via `ctx.player_*_bonus` fields. When the player spends a skill point, the bonus field is incremented and `ctx.stats` is immediately updated:

```python
def _apply_skill_point(ctx, skill: str) -> None:
    """Spend one skill point on *skill* (gunnery/piloting/engineering)."""
    if ctx.player_skill_points <= 0:
        return
    bonus_field = f"player_{skill}_bonus"
    current_bonus = getattr(ctx, bonus_field, 0)
    setattr(ctx, bonus_field, current_bonus + 2)
    ctx.player_skill_points -= 1
    # Immediately update HudStats so combat + HUD see the change.
    setattr(ctx.stats, skill, getattr(ctx.stats, skill) + 2)
```

This keeps the single source of truth (`ctx.stats`) in sync with the persistent bonus counters (`ctx.player_*_bonus`) without requiring every combat read site to sum multiple fields.

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
| **Bounty Network** | +15% bounty mission credit rewards | 10+ bounties completed | 25+ bounties completed | Bounty hunter |
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

### Phase 1: XP tracking + skill rebalance

#### Pre-implementation audit (guardrail 5)

**Existing modules to extend/reuse:**
- `game_context.py` — add `player_xp`, `player_level`, `player_skill_points`, `player_*_bonus` fields, plus playstyle counters
- `character.py` — `starting_pilot_skills()` already computes base+species+class; modify to halve bonuses. `starting_stats()` feeds `HudStats` — add level-related fields.
- `data/species/core.py` + `data/classes/core.py` — skill_bonus fields (frozen `PilotSkills`), reduce values per rebalance table
- `mission.py` — `complete_mission()` already has `reward_xp`; feed into `add_xp()`
- `combat/_encounter.py` — VICTORY path: add combat XP per kill
- `combat/_weapons.py` — increment playstyle counters on shot/hit/damage events
- `menus/_ship_menu.py` — NOT touched (Character screen uses hotkey, not ship menu)
- `hud.py` — add level/XP display
- `input_helpers.py` — add `_is_c_press()` for Character screen hotkey (renamed from old cargo key)
- `__main__.py` — wire C hotkey for Character screen, I hotkey for cargo

**Three duplication hotspots:**
1. **XP award duplicated across mission completion and combat kill.** Fix: single `add_xp(ctx, amount)` function in new `xp.py` module that handles level-up logic, logging, and trait triggers.
2. **Skill total formula scattered across combat/HUD/character.** Fix: all skill values flow through `ctx.stats` (HudStats) — `_apply_skill_point()` updates `ctx.stats` directly, combat reads from `ctx.stats`, HUD reads from `ctx.stats`. Single source of truth.
3. **Playstyle counter increments copy-pasted across combat actions.** Fix: helper functions in `xp.py` for `_increment_weapon_counter(ctx, weapon_type)` and `_increment_kill_counter(ctx, faction)` called from the combat loop.

**DRY strategy:**
- `xp.py` owns: `add_xp()`, `xp_for_level()`, level-up logic, trait qualification checks, playstyle counter helpers
- `ctx.stats` is the single source of truth for current skill values
- Species/class rebalance: edit the frozen `PilotSkills` values in data files only

#### Checklist

- [ ] Add `player_xp`, `player_level`, `player_skill_points`, `player_*_bonus` fields to `GameContext`
- [ ] Add playstyle counter fields to `GameContext` (9 counters)
- [ ] Create `xp.py` with `add_xp(ctx, amount)`, `xp_for_level(level)`, `_apply_skill_point()`
- [ ] Halve species skill bonuses in `data/species/core.py`
- [ ] Halve class skill bonuses in `data/classes/core.py`
- [ ] Wire `add_xp()` into `mission.complete_mission()` call path
- [ ] Wire `add_xp()` into `combat/_encounter.py` VICTORY path (per-kill)
- [ ] Add `_is_k_press()` to `input_helpers.py`, wire C hotkey in `__main__.py`
- [ ] Smoke test + commit

#### Playtest checklist

- [ ] Start new game → verify starting skills match rebalance table (e.g. Human Pirate: 41/5/3)
- [ ] Complete a delivery mission → XP gain logged, level-up if threshold crossed
- [ ] Kill an enemy in combat → XP gain logged
- [ ] Level up → "Level N! 2 skill points earned." message
- [ ] Press K → Character screen opens (blank skills section for now, just shows level/XP)
- [ ] New character screen accessible from both city and space modes

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
1. **Level indicator drawn differently in city vs space HUD.** Fix: single helper `_render_level_line()` called from both branches.
2. **XP progress bar duplicated between Character screen and potential HUD element.** Fix: Character screen owns the detailed XP bar; HUD shows compact "Lv.N" only.
3. **Level-up message format duplicated.** Fix: single format string in `xp.py` `add_xp()`, not in HUD.

**DRY strategy:**
- Level display: one line in HUD, one detailed view in Character screen
- All level-up logic in `xp.py`; HUD only reads `ctx.player_level`

#### Checklist

- [ ] Add "Lv.N" to city HUD (near species/class, or below HP/credits)
- [ ] Add "Lv.N" to space HUD (near ship name or below fuel/hull)
- [ ] `add_xp()` logs `"+N XP"` on gain, `"Level N! 2 skill points earned."` on level-up
- [ ] Character screen shows "Next level: 400/500 XP" with progress bar
- [ ] Add `C` to HUD key hints in both city and space modes
- [ ] Smoke test + commit

#### Playtest checklist

- [ ] City HUD shows "Lv.1" for a new character
- [ ] Gain XP from a mission → "+NN XP" in message log, HUD level updates if threshold crossed
- [ ] Level up → "Level N! 2 skill points earned." message is colored distinctly
- [ ] Character screen shows XP progress bar "320/480" with visual fill
- [ ] Both city and space HUDs show K in key hints

---

### Phase 4: Traits at 20/30

#### Pre-implementation audit

**Existing modules to extend/reuse:**
- `xp.py` — `add_xp()` already fires on level-up; add trait-check trigger when level == 20 or 30
- `mission.py` — `bounties_completed` / `deliveries_completed` already incremented in `complete_mission()`
- `combat/_weapons.py` — per-shot counters (laser/missile/plasma) incremented in fire path
- `combat/_encounter.py` — per-kill counters (total_kills, merchant_kills) incremented in VICTORY path
- `combat/_loop.py` — `combat_flees` incremented on flee; `total_damage_taken` incremented on damage
- `trade.py` — `Scavenger` trait affects loot drop quantities
- `faction.py` — reputation-gated traits check `ctx.faction_reputation`

**Three duplication hotspots:**
1. **Trait threshold checking duplicated for playstyle + rep-gated traits.** Fix: `xp.py` has single `_qualifying_traits(ctx, milestone_level)` that evaluates ALL traits against counters + rep, returns list.
2. **Trait effect application scattered across combat/trade/comms.** Fix: `xp.py` exports `has_trait(ctx, trait_name) -> bool`; each domain checks the flag where the effect applies.
3. **Counter increments copy-pasted.** Fix: `_increment_weapon_counter()` and `_increment_kill_counter()` helper functions (already from Phase 1).

**DRY strategy:**
- `xp.py` is the single source of truth for: trait pool, thresholds, qualification, selection tracking
- Trait effects are checked via `has_trait()` at point of use (e.g. `if has_trait(ctx, 'Ace Pilot'): ap += 1`)
- Trait selection modal follows the existing modal pattern (render + update + Modal.run)

#### Checklist

- [ ] Add `player_traits: list[str]` field to `GameContext`
- [ ] Build trait selection modal in `xp.py` (or `trait_screen.py`): shows qualifying traits, pick one
- [ ] Wire `_qualifying_traits()` — evaluates all 13 playstyle + 4 rep-gated traits
- [ ] Wire playstyle counter increments in combat (`_weapons.py`, `_loop.py`, `_encounter.py`)
- [ ] Wire mission counter increments in `mission.py` (`complete_mission()`)
- [ ] Trigger trait selection when `add_xp()` detects level 20 or 30
- [ ] Wire trait effects: `Ace Pilot` (+1 AP), `Overcharge` (+25% shields), `Laser Mastery` (+20% laser dmg), `Scavenger` (+50% loot), `Sharpshooter` (+10% hit), `Evasive` (+15% dodge), `Power Surge` (+5 max power), `Juggernaut` (-50% missile dmg taken), `Hardened` (-10% all dmg), `Trade Route` (-5% buy/+5% sell), `Bounty Network` (+15% bounty credits)
- [ ] Wire reputation-gated traits: `Merchant Alliance`, `Pirate King`, `Militia Commission`, `Galaxy's Most Wanted`
- [ ] Soft-cap skills at 100 in `_apply_skill_point()` and `add_xp()` auto-assignment
- [ ] Smoke test + commit

#### Playtest checklist

- [ ] Play through enough content to reach level 20 → trait selection modal appears
- [ ] Modal shows ALL qualifying traits (e.g. if you have 500+ laser shots AND 60+ gunnery, see both Laser Mastery + Sharpshooter)
- [ ] Pick a trait → effect is immediately active (e.g. Ace Pilot → +1 AP in next combat)
- [ ] Reach level 30 → second trait modal, first trait is excluded
- [ ] Allied with merchants at level 20 → Merchant Alliance available alongside playstyle traits
- [ ] Skill at 100 → "[+]" button disabled or shows "MAX"
- [ ] Trait effects persist across saves/loads for the same run

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

1. **Max level is 30.** (Answered) Tiers 20 and 30 have major trait choices.
2. **Should skill point allocation be respec-able?** For v1, no. Make each point count.
3. **Do enemies scale with player level?** Not directly — tier-based missions already provide the right difficulty curve. A level 30 player fighting a T1 pirate_scout should feel like a god.
4. **Should there be class-specific bonuses on level-up?** Not in v1 — keep it simple. Class identity comes from starting skill bonuses.
5. **Should XP be lost on death?** No — roguelike death means the run is over anyway. The player starts fresh at level 1.
