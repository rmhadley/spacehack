# DESIGN: Bounty Missions

## Overview

Add bounty-hunting missions to the Bounty Master NPC (guild `bhguild`), matching the quality and feature set of the recently-completed merchant delivery mission system. Bounty missions ask the player to travel to a target system, locate a specific enemy NPC ship, and destroy it in combat.

Targets get unique flavor: custom names ("Vex Korr", "The Widowmaker"), upgraded ships with extra weapons/modules, danger levels scaling with tier, and squad-based encounters at higher tiers.

The existing data model already supports bounty missions (`target_enemy_id`, `target_system_id`, `bounty_spawn_id` on both `MissionSpec` and `ActiveMission`), and the `BountySpawn` + `ctx.bounty_spawns` infrastructure dynamically places targets on system maps. The accept flow in `__main__.py` already handles bounty spawn creation. What's missing is: hand-crafted entries, procedural generation with flavor, completion detection in combat, quest log display, and board integration.

## Philosophy alignment

| Principle | How it applies |
|-----------|---------------|
| **Data-first** | Hand-crafted bounty missions go in `data/missions/bounty.py` as frozen `MissionSpec` entries |
| **ctx-first** | Bounty completion detection reads `ctx.player_active_missions` in the combat loop |
| **Domain owns flow** | Bounty generation lives in `mission.py`; completion detection in `combat/_loop.py` |
| **Board-driven** | Same `MissionBoard` / `fill_empty_slots` / `refresh_all_boards` infrastructure |
| **Tiered** | Tiers 1-4, same rarity curve (min-of-two-rolls), planet `mission_tier` gating |
| **Seeded RNG** | All procedural generation uses `engine.RNG` |

## Data model

### Already exists (no changes needed)

- `MissionSpec.target_enemy_id: str | None` — NPC ship spec ID to kill
- `MissionSpec.target_system_id: str | None` — solar system to find them in
- `ActiveMission.bounty_spawn_id: str | None` — links to `BountySpawn`
- `ActiveMission.target_enemy_id: str | None`
- `ActiveMission.target_system_id: str | None`
- `BountySpawn(spawn_id, enemy_id, pos)` — dynamic placement
- `ctx.bounty_spawns: dict[str, list[BountySpawn]]` — keyed by system ID

### New fields on `MissionSpec`

- **`bounty_target_name: str | None = None`** — custom display name (e.g. "Vex Korr"). When set, overrides the base NpcShipSpec name for the spawned enemy.
- **`bounty_target_squad_size: int = 1`** — number of enemies in the target group (leader + wingmates). Tier 1-2 = 1, tier 3 = 1-2, tier 4 = 2-3.
- **`bounty_target_loadout_pct: int = 0`** — 0-100 representing how upgraded the target's weapons/modules are. 0 = base spec, 50 = +1 weapon, 100 = fully kitted.

### New fields on `ActiveMission`

- **`bounty_target_name: str | None = None`** — snapshot for quest log display
- **`bounty_target_squad_size: int = 1`** — for quest log ("+ 2 wingmates")
- **`bounty_target_loadout_pct: int = 0`** — for spawn-time customization

### New functions in `mission.py`

- **`generate_bounty_mission`** — procedural generator
- **`_generate_bounty_name(tier, rng) -> str`** — name generator
- **`_bounty_enemy_pool(tier) -> list[str]`** — eligible NpcShipSpec IDs per tier

## Bounty target flavor system

### Name generation

Procedural names are assembled from tier-gated prefix + title pools:

| Tier | Prefix pool | Title pool | Example |
|------|------------|-----------|---------|
| 1 | Rookie, Deserter, Wanted, Marked | Scavenger, Runner, Rat, Drifter | "Wanted Scavenger" |
| 2 | Fugitive, Smuggler, Outlaw, Notorious | Corsair, Hauler, Runner, Dealer | "Outlaw Corsair" |
| 3 | Hunted, Infamous, Vicious, Feared | Marauder, Raider, Enforcer, Reaver | "Infamous Marauder" |
| 4 | Dread, Warlord, Legendary, Cursed | Captain, Overlord, Wraith, Reaper | "Dread Captain" |

Hand-crafted missions set `bounty_target_name` explicitly (e.g. `"Crimson Jack"`).

### Ship + loadout scaling

Tier determines the base ship pool, loadout upgrades, and squad size:

| Tier | Base ship pool | `loadout_pct` range | Squad size | Reward multiplier |
|------|---------------|--------------------|-----------|-------------------|
| 1 | scout, light fighter | 0-25 | 1 | 1x |
| 2 | raider, interceptor | 25-50 | 1 | 1.5x |
| 3 | cruiser, gunship | 50-75 | 1-2 | 2x |
| 4 | frigate, heavy cruiser | 75-100 | 2-3 | 3x |

- **loadout_pct** determines extra weapons/modules beyond the base NpcShipSpec. At 50%: +1 weapon slot filled; at 100%: all slots filled with tier-appropriate gear.
- **Squad members** use the same ship type + loadout as the leader. Mission completes when the **leader** is destroyed — wingmates are bonus enemies (and bonus loot).
- **BountySpawn** stores `bounty_target_name`, `squad_size`, and `loadout_pct` so the spawner can create the right entities.

### Danger level display

Bounty descriptions include a danger rating based on tier + squad:
- Tier 1, solo: "Danger: Low"
- Tier 2, solo: "Danger: Moderate"
- Tier 3, solo/small squad: "Danger: High"
- Tier 4, squad: "Danger: Extreme"

Quest log shows: "Target: Vex Korr + 2 wingmates (Danger: High)"

## Domain changes

### Phase 1: Data model + hand-crafted missions

- [x] Add `bounty_target_name`, `bounty_target_squad_size`, `bounty_target_loadout_pct` to `MissionSpec`
- [x] Add `bounty_target_name`, `bounty_target_squad_size`, `bounty_target_loadout_pct` to `ActiveMission`
- [x] Add corresponding fields to `BountySpawn` (immutable, needs `frozen=True` check)
- [x] Add 6 hand-crafted bounty missions to `data/missions/bounty.py`:

| # | ID | Name | Tier | Target Enemy | System | Squad | Loadout% | Credits |
|---|-----|------|------|-------------|--------|-------|----------|---------|
| 1 | `bhguild_sol_scout` | Wanted: Crimson Jack | 1 | `pirate_scout` | Sol | 1 | 20 | 150 |
| 2 | `bhguild_ac_smuggler` | Smuggler's Run | 2 | `pirate_raider` | Alpha Centauri | 1 | 40 | 350 |
| 3 | `bhguild_sirius_fugitive` | Fugitive Hauler | 2 | `pirate_raider` | Sirius | 1 | 30 | 300 |
| 4 | `bhguild_wolf_marauder` | Wanted: Karrik the Red | 3 | `pirate_raider` | Wolf 359 | 1 | 60 | 700 |
| 5 | `bhguild_luyten_raider` | The Luyten Raider | 3 | `pirate_raider` | Luyten's Star | 2 | 70 | 900 |
| 6 | `bhguild_vega_dread` | Wanted: Dread Captain Vol | 4 | `pirate_cruiser`* | Vega | 3 | 100 | 2000 |

(*May need a new `pirate_cruiser` NpcShipSpec — or use `militia_blockade` as base.)

- [x] Set `faction="bhguild"`, `giver_npc_id="bounty_master"`, `mission_type="bounty"`
- [x] Set deadlines, early_bonus_pct, origin_planet_id per entry
- [x] Wire `bounty_target_name` etc. into `ActiveMission` during accept flow
- [x] Verify `missions_offered_by` filters by `giver_npc_id="bounty_master"`

### Phase 1.5: Playtest — static bounty missions

**Checklist:**
- [ ] Visit Earth bounty guild, talk to Bounty Master
- [x] Verify "View available work" shows hand-crafted bounty missions with custom names
- [ ] Accept "Crimson Jack" — verify target spawns in Sol with custom name
- [ ] Quest log shows "Target: Crimson Jack" with system and danger level
- [ ] Travel to target, engage, destroy — verify mission completes
- [ ] Accept "Dread Captain Vol" — verify 3-ship squad spawns
- [ ] Abandon a bounty — verify spawn cleanup works

### DRY eval #1

- [ ] Does `bounty_target_name` snapshot on `ActiveMission` duplicate the lookup pattern from `delivery_target_npc_id`? If so, extract a shared pattern.
- [ ] Are accept/complete/abandon paths in `__main__.py` shared or duplicated per mission type?
- [ ] Are quest log bounty entries reusing the same render code or duplicating it?

### Phase 2: Procedural bounty generation

- [x] Add `_generate_bounty_name(tier, rng)` — picks from tier-gated prefix/title pools
- [x] Add `_bounty_enemy_pool(tier)` — returns eligible NpcShipSpec IDs
- [x] Add `generate_bounty_mission` to `mission.py`:
  - Algorithm:
    1. Roll tier (min-of-two, same as delivery)
    2. Pick target system via hop-range gating (reuse `_hop_ranges` dict pattern)
    3. Pick `_bounty_enemy_pool(tier)` → pick one with `rng.choice`
    4. Roll `bounty_target_loadout_pct` within tier range
    5. Roll `bounty_target_squad_size` within tier range
    6. Generate name via `_generate_bounty_name`
    7. Generate reward: base = enemy_hull_strength * tier * 40, adjusted by squad size
    8. Generate deadline: hop_count * 6 + randint(3, 8)
    9. Build MissionSpec with `mission_type="bounty"`, `faction="bhguild"`
  - [ ] Generated ID: `proc_bounty_{origin}_{system}_{enemy_id}_{counter}_{tier}`
- [x] Wire into `fill_empty_slots` with guild gate (`guild == "bhguild"`)

### Phase 2.5: Playtest — procedural bounties

**Checklist:**
- [ ] Visit multiple Bounty Masters across different planets
- [x] Verify procedural bounties appear with generated names (not "Pirate Scout")
- [x] Verify tier gating and danger levels match expectations
- [ ] Accept a tier-3 bounty with squad — verify multiple enemies spawn
- [ ] Accept a tier-4 bounty with full loadout — verify target has extra weapons
- [ ] Complete it — verify reward scales with tier + squad

### DRY eval #2

- [ ] Does `generate_bounty_mission` share tier-roll, hop-range, reward-formula logic with `generate_delivery_mission`? Extract shared helpers.
- [ ] Is the `BountySpawn` creation path in the accept flow duplicating logic?

### Phase 3: Bounty completion in combat + comms

- [x] **Bounty-specific comms lines**: Set `comms_lines` on bounty target NpcShipSpec entries (or override at spawn time). Hand-crafted bounties get unique flavor lines; procedural bounties roll from tier-gated pools:
  - Tier 1: "You're making a mistake, hunter." / "I ain't worth the bounty, pal."
  - Tier 2: "You've got guts coming after me." / "Name your price. Everyone has one."
  - Tier 3: "I've killed better hunters than you." / "You want my head? Come take it."
  - Tier 4: "I am the price on your head, hunter." / "They sent YOU? I'm insulted."
- [x] **Bounty auto-hail**: When the player enters the bounty target's `comms_warning_range` (same field as militia), the comms panel opens automatically with the target's taunt line. This doubles as an "enemy spotted" indicator — the player knows they've found their target.
  - Add `comms_warning_range` to bounty target NpcShipSpec entries (e.g. 20 cells)
  - Reuse `_check_auto_comms_warning` pattern, or add a bounty-specific `_check_bounty_auto_hail` that checks `ctx.player_active_missions` for bounty targets in range
  - Auto-hail only fires once per target (track hailed bounty spawn IDs to prevent spam)
- [x] In `combat/_encounter.py`, when the **leader** enemy is destroyed:
  - Check `ctx.player_active_missions` for bounty missions targeting the enemy by `bounty_spawn_id`
  - If match found: mark complete, call `complete_mission`, remove spawn
  - Log: "Bounty complete: {bounty_target_name} destroyed."
- [x] Squad wingmate deaths do NOT complete the bounty
- [x] Clean up spawn data on abandon (already handled by `_remove_bounty_spawn`)

### Phase 3.5: Playtest — combat integration

**Checklist:**
- [ ] Accept a solo bounty, destroy the target — verify completion
- [ ] Accept a squad bounty, destroy a wingmate first — verify bounty does NOT complete yet
- [ ] Destroy the leader — verify bounty completes
- [ ] Get killed in combat — verify bounty persists
- [ ] Abandon mid-hunt — verify target despawns

### Phase 4: Quest log display

- [ ] Update `_quest_log.py` for bounty missions:
  - Show `bounty_target_name` (custom name)
  - Show target system (resolved from `find_solar_system`)
  - Show squad size: "+ 2 wingmates" (when > 1)
  - Show danger level text
  - Status: "Hunting"
  - Deadline and reward (same format as delivery)
- [ ] Bounty entries: replace "Deliver to:" with "Target:" line
- [ ] Distinct visual accent for bounty missions (no dev-facing labels)

### Phase 4.5: Playtest — quest log

**Checklist:**
- [ ] Quest log shows bounty with custom name, system, danger level, deadline
- [ ] Squad bounty shows "+ N wingmates"
- [ ] Complete bounty — verify it disappears from active list
- [ ] Abandon — verify cleanup

### Phase 5: Final polish + guide update

- [ ] Update `help.py` Bounty Guild section
- [ ] Final DRY scan over all bounty code paths
- [ ] RNG audit — all procedural calls use `engine.RNG`
- [ ] Dead code sweep

### Phase 5.5: Final playtest + guide

**Checklist:**
- [ ] Full run: accept bounty, travel, fight squad leader, complete
- [ ] All quest log displays verified
- [ ] Guide (?) covers bounty missions accurately
- [ ] Month rollover refreshes bounty boards
- [ ] No dev-facing labels in player UI

## Acceptance criteria

- [ ] 6 hand-crafted bounty missions across tiers 1-4 with custom names
- [ ] Procedural bounty generation with name generator, loadout scaling, squad sizes
- [ ] Danger levels displayed in mission descriptions and quest log
- [ ] Bounty completion detected in combat (leader destroyed)
- [ ] Squad bounty support — wingmates are bonus enemies, leader kill completes mission
- [ ] Bounty board uses same 5-slot system, month-rollover refill, guild-gated to bhguild
- [ ] All RNG through `engine.RNG`
- [ ] Help guide updated
- [ ] No dev-facing labels in player UI

## Open questions

1. ~~**New enemy types?**~~ → Add `pirate_captain` to `npc_ships/core.py` — heavy cruiser/frigate hull, multiple weapons, high AI stats, pirate faction.
2. **Loadout customization at spawn time:** How to apply `bounty_target_loadout_pct` to the spawned entity? Options: create a new NpcShipSpec on-the-fly (complex), or store weapon/module overrides on BountySpawn and read them during entity creation (simpler).
3. **Squad leader identification:** How does combat know which entity is the leader? Options: mark the BountySpawn with `is_leader=True`, or compare entity position to the spawn position.
4. **Bounty Hunter class synergy:** Should the Bounty Hunter class get bonus credits/XP from bounty missions?
5. **Name pool size:** Start with 4 prefixes + 4 titles per tier = 16 possible combos. Expand if the pool feels repetitive.
