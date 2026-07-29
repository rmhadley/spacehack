# DESIGN: Player XP & Leveling

## Overview

Add a leveling system that gives meaning to the XP already being awarded by missions and combat. Currently `reward_xp` is computed and displayed but immediately discarded — levels would make it a real progression driver.

### What levels unlock

Leveling grants **2 skill points per level** (each point adds +1 to one pilot skill — finer control, simpler math). Skills are viewed and points spent via the **Character screen** (`C` hotkey, accessible from city or space). The only other unlock milestones are trait choices at 20 and 30 — both draw from the **same shared pool**. No hull/fuel/cargo/shield/slot bonuses — progression is purely about pilot skill growth.

**Keybinding:** `C` opens the Character screen. Cargo was moved to `I` (Inventory) to free up `C`. The Character screen is NOT in the ship hangar menu — it's a global hotkey like `F` for Factions.

- **Gunnery** → weapon accuracy (`gunnery * 0.5` added to hit chance)
- **Piloting** → AP per turn (`3 + piloting // 20`), dodge bonus (`piloting * 0.5`)
- **Engineering** → max power pool (`power_gen * 2 + engineering // 5`)

| Level | Unlock |
|-------|--------|
| Every level | +2 skill points (+2 to distribute across skills at +1 each) |
| 20 | **Trait choice** — pick one from the shared pool |
| 30 | **Trait choice** — pick another from the SAME pool (cannot repeat) |

**Initial trait set** (minimal — just enough to test the counter system; full trait design pass later):

| Trait | Milestone | Requires | Effect |
|-------|-----------|----------|--------|
| Sharpshooter | 20/30 | 40+ gunnery | +10% hit chance |
| Trade Route | 20/30 | 10+ deliveries | -5% buy / +5% sell prices |
| Ace Pilot | 20/30 | 10+ combat flees | +1 AP per turn |
| Juggernaut | 20/30 | 30+ total kills | -50% missile damage taken |

These 4 traits test 4 different counter types: skill value, delivery count, flee count, kill count.

## Philosophy alignment

| Principle | How it applies |
|-----------|---------------|
| **ctx-first** | XP total and level tracked on `GameContext` as `player_xp: int` and `player_level: int` |
| **Data-first** | Level thresholds live in a simple table, not scattered logic |
| **Live-by-side-effect** | XP earned via `add_xp(ctx, amount)` that levels up and applies bonuses immediately |
| **Simple > clever** | Max level 30, 2 skill points per level, playstyle-gated traits at 20 and 30 |

## Starting skill rebalance

Currently species and class skill bonuses are inflated to feel impactful because they're static (Pirate: gunnery+15; Merchant: engineering+15; Bounty Hunter: gunnery+10, piloting+10). With leveling, these need to leave ~60 points of headroom to the 100 soft cap (58 skill points from leveling 1→30).

### Design target

Level 1 skills sit in the 30-40 range. At level 30 with focused investment, a specialist reaches ~98 (just shy of cap). Class identity is clear but not overpowered — a Merchant has noticeably better engineering than a Pirate, but the gap narrows with leveling as the player chooses where to invest.

### Proposed rebalance (done during Phase 1)

**Species bonuses** (small flavor adjustments):

| Species | G | P | E |
|---------|---|---|---|
| Human | +2 | 0 | +2 |
| Martian | 0 | +5 | 0 |

**Class bonuses** (clear identity, no negatives):

| Class | G | P | E |
|-------|---|---|---|
| Pirate | +8 | 0 | 0 |
| Merchant | 0 | 0 | +8 |
| Bounty Hunter | +3 | +3 | +3 |

**Resulting starting totals** (base 30 + species + class):

| Combo | Gunnery | Piloting | Engineering |
|-------|---------|----------|-------------|
| Human Pirate | **40** | 30 | 32 |
| Human Merchant | 32 | 30 | **40** |
| Human BH | 35 | 33 | 35 |
| Martian Pirate | 38 | **35** | 30 |
| Martian Merchant | 30 | 35 | 38 |
| Martian BH | 33 | 38 | 33 |

At level 30: a Pirate dumping all 58 points in gunnery hits 98 (just shy of 100). A balanced BH reaches ~60-65 all around. A Merchant maxing engineering hits 98.

This rebalance is applied in **Phase 1** alongside the XP tracking so the new starting values go live at the same time as the leveling system.

## Data model

### New fields on `GameContext`

- **`player_xp: int = 0`** — total XP earned (cumulative, never resets)
- **`player_level: int = 1`** — current level (starts at 1)
- **`player_skill_points: int = 0`** — unspent skill points (earned on level-up)
- **`player_gunnery_bonus: int = 0`** — bonus added to gunnery from skill points
- **`player_piloting_bonus: int = 0`** — bonus added to piloting from skill points
- **`player_engineering_bonus: int = 0`** — bonus added to engineering from skill points
- **`player_traits: list[str] = field(default_factory=list)`** — chosen trait IDs
- **`player_counters: PlayerCounters = field(default_factory=PlayerCounters)`** — playstyle tracking (see below)

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
    deliveries_completed: int = 0
    total_damage_taken: int = 0
    combat_flees: int = 0
```

Incremented via: `ctx.player_counters.total_kills += 1`. One field on ctx. Extensible — add a counter to the dataclass, update the trait catalog, done.

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
    """One player trait — earned at level 20 or 30 if counters qualify."""
    id: str
    name: str
    description: str
    # Counter requirements: list of (counter_field, min_value) pairs.
    # ALL must be met for the trait to appear at a milestone.
    counters: tuple[tuple[str, int], ...]
    # Optional: (faction, attitude) — faction rep gate.
    rep_required: tuple[str, str] | None = None

# Registry — add new traits here. Shared pool for both level 20 and 30.
# Full trait design pass will come later; initial set is minimal.

SHARPSHOOTER = Trait(
    id="sharpshooter",
    name="Sharpshooter",
    description="+10% hit chance in combat",
    counters=(("gunnery", 40),),
)

TRADE_ROUTE = Trait(
    id="trade_route",
    name="Trade Route",
    description="-5% buy / +5% sell prices",
    counters=(("deliveries_completed", 10),),
)

ACE_PILOT = Trait(
    id="ace_pilot",
    name="Ace Pilot",
    description="+1 AP per turn in combat",
    counters=(("combat_flees", 10),),
)

JUGGERNAUT = Trait(
    id="juggernaut",
    name="Juggernaut",
    description="-50% missile damage taken",
    counters=(("total_kills", 30),),
)

ALL_TRAITS: tuple[Trait, ...] = (
    SHARPSHOOTER, TRADE_ROUTE, ACE_PILOT, JUGGERNAUT,
)
```

**Selection at milestone:** `_qualifying_traits(ctx)` scans `ALL_TRAITS`, checks each against `ctx.player_counters` (and optionally `ctx.faction_reputation`), returns list. Player picks one. Stored in `ctx.player_traits`.

**Effect application:** `has_trait(ctx, trait_id)` checks `ctx.player_traits`. Called at point of use (e.g. `if has_trait(ctx, 'ace_pilot'): ap += 1` in combat).

### XP gain notification

When the player gains XP, the message log adds: `"+40 XP"`. On level-up: `"Level 4! 2 skill points earned."` At level 20/30: `"Level 20! Choose a major trait."`

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

- [ ] Add `player_xp`, `player_level`, `player_skill_points`, `player_*_bonus` fields to `GameContext`
- [ ] Add `PlayerCounters` dataclass + `player_counters` field to `GameContext`
- [ ] Create `xp.py` with `add_xp(ctx, amount)`, `xp_for_level(level)`, `_apply_skill_point()`
- [ ] Update species skill bonuses in `data/species/core.py` (new values per rebalance table)
- [ ] Update class skill bonuses in `data/classes/core.py` (new values per rebalance table)
- [ ] Wire `add_xp()` into `mission.complete_mission()` call path
- [ ] Wire `add_xp()` into `combat/_encounter.py` VICTORY path (per-kill)
- [ ] Add `_is_k_press()` to `input_helpers.py`, wire C hotkey in `__main__.py`
- [ ] Smoke test + commit

#### Playtest checklist

- [ ] Start new game → verify starting skills match rebalance table (e.g. Human Pirate: 40/30/32)
- [ ] Complete a delivery mission → XP gain logged, level-up if threshold crossed
- [ ] Kill an enemy in combat → XP gain logged
- [ ] Level up → "Level N! 2 skill points earned." message
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

- [ ] Add compact XP bar to city HUD: `"LV 4 [#####-----]"` between key hints and footer
- [ ] Add compact XP bar to space HUD: same format, same position
- [ ] Extract `_render_xp_bar(value, max_val, width)` helper in `hud.py`
- [ ] `add_xp()` logs `"+N XP"` on gain, `"Level N! 2 skill points earned."` on level-up
- [ ] Character screen shows detailed XP progress bar using same helper
- [ ] Add `C` to HUD key hints in both city and space modes
- [ ] Verify XP bar renders with CP437-safe `#`/`-` chars on the tilesheet
- [ ] Smoke test + commit

#### Playtest checklist

- [ ] City HUD shows `"LV 1 [----------]"` for a new character (0 XP)
- [ ] Gain XP from a mission → XP bar fills, "+NN XP" in message log
- [ ] Level up → bar resets to empty for new level, "Level N!" message is colored
- [ ] Character screen shows XP progress bar with same format
- [ ] Both city and space HUDs show `C` in key hints

---

### Phase 4: Traits at 20/30

#### Pre-implementation audit

**Existing modules to extend/reuse:**
- `xp.py` — `add_xp()` already fires on level-up; add trait-check trigger when level == 20 or 30
- `data/traits/core.py` — new: frozen `Trait` dataclass + `ALL_TRAITS` registry
- `mission.py` — `deliveries_completed` / `bounties_completed` incremented in `complete_mission()` via `ctx.player_counters`
- `combat/_weapons.py` — per-shot counters (laser/missile/plasma) incremented via `ctx.player_counters` in fire path
- `combat/_encounter.py` — per-kill counters (`total_kills`, `merchant_kills`) incremented via `ctx.player_counters` in VICTORY path
- `combat/_loop.py` — `combat_flees` incremented on flee; `total_damage_taken` incremented on damage
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

1. **Max level is 30.** (Answered) Tiers 20 and 30 have major trait choices.
2. **Should skill point allocation be respec-able?** For v1, no. Make each point count.
3. **Do enemies scale with player level?** Not directly — tier-based missions already provide the right difficulty curve. A level 30 player fighting a T1 pirate_scout should feel like a god.
4. **Should there be class-specific bonuses on level-up?** Not in v1 — keep it simple. Class identity comes from starting skill bonuses.
5. **Should XP be lost on death?** No — roguelike death means the run is over anyway. The player starts fresh at level 1.
