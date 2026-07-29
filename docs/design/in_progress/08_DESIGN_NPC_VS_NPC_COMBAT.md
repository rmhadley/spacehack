# DESIGN: NPC vs NPC Combat (Experimental)

## Overview

NPC ships that can fight each other — pirates ambushing merchants, militia cracking down on pirates, and the player caught in the middle. This is **highly experimental** because it touches the core combat loop, the NPC movement system, and introduces background simulation mechanics the game has never needed before.

### What already exists

- **Combat system** (`combat/_loop.py`): Full turn-based combat between player + enemy NPCs. Enemy AI (`_ai.py`) can move, target, and fire at the player.
- **NPC movement** (`npc_ships.py`): Pirates patrol, merchants travel between bodies and despawn at gates/planets, merchants flee from nearby pirates
- **Faction awareness**: NPCs have `faction` field (`pirate`, `merchant`, `militia`), and merchants already flee from pirates within `_MERCHANT_FLEE_RANGE`
- **Combat encounter detection** (`navigation._detect_combat_encounter`): Finds enemy NPCs near the player
- **Combat reinforcement** (`_loop.py`): New enemies can join mid-combat (used for militia call-for-help)
- **Loot drops** (`_loop._spawn_loot_drops`): Dead ships drop cargo items
- **Enemy combat stats** (`NpcShipSpec`): Full combat AI parameters exist for all NPC types

### What's experimental

NPC vs NPC combat opens several hard design questions:

1. **Simulation vs player-view:** Do NPC fights resolve in the background (simulation tick) or only when the player is watching? Background simulation would need its own mini combat system — a huge undertaking. Player-view-only is simpler but creates immersion gaps.
2. **Player intervention:** If the player is in a fight and NPCs also fight, whose turn is it? Does the player act in real time while NPCs fight around them?
3. **Performance:** Running full turn-based combat for every NPC pair every tick would be very expensive.

## Design decisions

### Approach: Player-witnessed only

NPC vs NPC fights only resolve **when the player can see them** (within viewport or detect radius). The game runs a lightweight simulation between NPC pairs when:

1. Two NPCs of opposing factions are within `detect_radius` of each other AND within the player's viewport
2. The player is in space mode (not in combat themselves)
3. The simulation runs on each player move tick (not in real-time)

This avoids background simulation complexity while still making the world feel alive.

### Resolution method: Fast combat simulation

Instead of running the full turn-based combat loop, NPC vs NPC fights use a **fast auto-resolve** that completes in ~3-5 frames:

```
Tick 1: NPC_A and NPC_B enter combat
  - Log: "Pirate Raider engages Merchant Hauler near Mars!"
  - Roll initiative (higher piloting wins)
  - Quick resolve: compare AI stats, hull, weapons, dice rolls
  - Apply damage each "round" (1 tick ≈ 3 combat rounds)

Tick 2-4: Animated exchange
  - Show laser flashes / explosions on the space map
  - Ships take damage each tick
  - One ship may flee (check ai_flee_threshold)

Tick 5: Outcome
  - Victor continues patrol
  - Loser explodes → loot drops
  - Log: "Pirate Raider destroyed Merchant Hauler near Mars!"
```

### Player intervention

The player can intervene at any point during the auto-resolve:

| Action | How | Effect |
|--------|-----|--------|
| **Join** | Move toward the fight and press F (fire) or T (comms) | Opens combat with both NPC factions present. Player picks a side or attacks both. |
| **Loot** | Wait for the fight to end, then fly to the corpse | Loot drops spawn like normal combat loot |
| **Flee** | Move away | Fights resolve out of viewport — player sees the log message but no animation |
| **Hail** | Press T at a participating NPC | Can interact during the fight (e.g., "Need help?" "Stay out of this, pilot.") |

### What fights who

Faction aggression is based on existing faction relationships:

| Attacker | Defender | When | Notes |
|----------|----------|------|-------|
| Pirate | Merchant | Always (merchants = prey) | Pirates attack merchants on sight |
| Pirate | Militia | If militia is in range | Pirates flee from militia unless cornered |
| Militia | Pirate | Always | Militia patrols engage pirates |
| Militia | Merchant | Never | Militia protects merchants |
| Merchant | Anyone | Never | Merchants flee, never fight |

**Faction alignment check table:**

| This faction | Fights this | When |
|-------------|-------------|------|
| `pirate` | `merchant` | always (prey) |
| `pirate` | `militia` | if militia attacks first OR pirate has 2:1 numbers |
| `militia` | `pirate` | always (duty) |
| `merchant` | none | flee only |
| `civilian` | none | flee only |

Future expansions (with faction rep system):
- A player with Allied pirate rep could have pirates ignore them during fights
- A player with Enemy militia rep could be targeted alongside pirates

### Visual feedback

Instead of re-rendering the full combat UI, NPC vs NPC fights are shown on the space map:

- **Laser flashes:** Brief `#` or `*` glyph at the fight location (reuse `NpcFlashEvent` system)
- **Ship icons pulse:** Participating NPCs' chars alternate between normal and brighter/higher contrast
- **Debris:** Dead ships leave a `%` loot entity (reuse loot system)
- **Log messages:** Colored text for fight start, hits, kills, and outcomes

Example visual on the space map:

```
     .  .  .  *  .  .  .
  .  M  #  P  .  .  .  .     ← M (Merchant) and P (Pirate) exchanging fire
     .  #  #  .  .  .  .        The `#` are flash particles
  .  .  .  .  .  *  .  .
```

## Data model

### New fields on `NpcShipSpec`
- `hostile_targets: tuple[str, ...] = ("pirate",)` — faction IDs this NPC type attacks on sight
- `ally_targets: tuple[str, ...] = ("militia",)` — faction IDs this NPC type protects/aligns with

### New fields on `GameContext`
- `npc_combats: dict[str, NpcCombatInstance]` — active NPC vs NPC fights keyed by a unique ID. Each entry tracks participants, round count, and accumulated damage.

### New dataclass `NpcCombatInstance`
```python
@dataclass
class NpcCombatInstance:
    combat_id: str
    entity_a_id: str  # movement_id / entity reference
    entity_b_id: str
    spec_a_id: str
    spec_b_id: str
    pos: world.Position
    round: int = 0
    damage_a: int = 0  # accumulated damage to entity_a
    damage_b: int = 0  # accumulated damage to entity_b
    resolved: bool = False
    winner_id: str | None = None
    loser_id: str | None = None
```

## Implementation phases

### Phase 1: Detection + faction hostility

- [ ] Add `hostile_targets` and `ally_targets` fields to `NpcShipSpec`
- [ ] Set defaults on all existing specs:
  - Pirates: `hostile_targets=("merchant",)`, no allies
  - Militia: `hostile_targets=("pirate",)`, `ally_targets=("merchant", "civilian")`
  - Merchants: empty (no hostility)
- [ ] Add `npc_combats: dict[str, NpcCombatInstance]` to `GameContext`
- [ ] Add detection in `move_npcs`: after moving all NPCs, check each pair within `detect_radius` of each other for hostile faction match
- [ ] If hostile pair found AND both within player viewport, create `NpcCombatInstance` and start auto-resolve
- [ ] Smoke test + commit

#### Playtest checklist

- [ ] Spawn in Sol with pirates + merchants in same system → watch for detection
- [ ] Verify pirates don't fight each other (same faction)
- [ ] Verify merchants don't fight anyone
- [ ] Verify militia engages pirates when in range

### Phase 2: Auto-resolve + animation

- [ ] Implement fast combat resolution in `npc_ships.py` — compare hull, weapons, skills, apply damage
- [ ] On each player move tick while fight is active, advance 1 round (≈ 3 combat cycles)
- [ ] On kill: remove dead entity, spawn loot, update `NpcCombatInstance.resolved = True`
- [ ] On flee: loser moves away at double speed, fight ends
- [ ] Add space-map visual feedback: `NpcFlashEvent` for laser exchanges, pulsing entity glyphs
- [ ] Add log messages for each phase (start, hit, kill, flee, outcome)
- [ ] Clean up resolved fights from `npc_combats` after 5 ticks
- [ ] Smoke test + commit

#### Playtest checklist

- [ ] Watch a pirate vs merchant fight → see laser flashes and log messages
- [ ] Watch a pirate merchant fight → merchant dies, loot spawns
- [ ] Watch militia vs pirate → militia wins (higher stats), loot spawns
- [ ] Watch pirate vs militia with pirate having 2:1 numbers → pirate may win
- [ ] Fight runs for 3-5 ticks then resolves

### Phase 3: Player intervention

- [ ] If player moves into range of an active `NpcCombatInstance`, add a new option to the comms list: "Active fight at {position}"
- [ ] If player presses F (fire) while near an active fight, the nearest combatant becomes a combat target
- [ ] When player enters combat near an NPC fight, ALL participants join the combat instance
- [ ] Player can choose a side by attacking one faction → the other faction becomes passive/non-hostile
- [ ] Player can attack both → everyone is hostile
- [ ] Log special messages: "You join the fray!" "The pirates break off to engage you!" "The militia hails you: 'Thanks for the assist!'"
- [ ] Smoke test + commit

#### Playtest checklist

- [ ] See pirate attacking merchant → press F → combat starts with both present
- [ ] Attack the pirate → merchant is non-hostile (green in combat HUD?)
- [ ] Attack both → everyone hostile
- [ ] Watch from distance → fight resolves without player involvement
- [ ] Move away mid-fight → fight continues (may resolve before player leaves viewport)

### Phase 4: Reputation + consequences

- [ ] If player kills a merchant during NPC vs NPC combat → `modify_rep(ctx, "merchant", -8)`
- [ ] If player kills a pirate during NPC vs NPC combat → `modify_rep(ctx, "militia", +3)`, `modify_rep(ctx, "pirate", -3)`
- [ ] If player saves a merchant (kills the pirate attacking it) → `modify_rep(ctx, "merchant", +5)` (bonus for rescue)
- [ ] If player attacks the militia → `modify_rep(ctx, "militia", -12)`, future alert on system entry
- [ ] Additional rep changes mirror the faction rep design doc tables
- [ ] Smoke test + commit

#### DRY eval

- [ ] Are NPC vs NPC rep changes using the same `modify_rep` helper as missions + combat?
- [ ] Is the "rescue bonus" hardcoded or table-driven?

#### Playtest checklist

- [ ] Save a merchant from a pirate → verify +5 merchant rep bonus
- [ ] Kill both pirate and merchant → verify both rep penalties apply
- [ ] Verify rep change messages in log match mission/combat format

### Phase 5: Background simulation (optional stretch)

- [ ] Optionally extend NPC vs NPC combat to off-screen NPCs (outside viewport)
- [ ] Simplified: off-screen fights resolve instantly without animation, just a log message on the next player tick: "A fight between Pirate Raider and Merchant Hauler near Venus ended."
- [ ] Results affect procedural spawn counts (dead NPCs don't respawn until the next spawn tick)
- [ ] This is the most experimental part — may be cut if performance or complexity is too high

**Note:** Phase 5 may be deferred indefinitely. The core experience is watching the fight happen in the viewport, not background simulation.

## Open questions

1. **Should NPCs use ammo?** Currently `ammo_per_shot` is a weapon stat, but NPCs don't track ammo. For NPC vs NPC, we'd need to either ignore ammo (simplification) or add ammo tracking to enemy instances. Recommend ignoring for v1 — NPCs have infinite ammo.
2. **Should the player be able to join a fight already in progress via comms?** "Hail combatants" option could let the player contact one side and offer assistance. Nice flavor but complex. Defer.
3. **Can NPC vs NPC combat happen while the player is in their own combat?** Logically yes, but resolving two combats simultaneously is very complex. For v1: no — NPCs don't start new fights while the player is in combat (paused).
4. **Should the victor loot the loser?** In-world, yes. Mechanically, loot drops on the space map are already accessible to the player. If an NPC victor loots the corpse, the loot disappears — which is realistic but frustrating. For v1: loot stays and is player-accessible.
5. **Merchant fleet mechanics — should merchants ever win?** A merchant with no weapons has zero chance. But some high-tier merchants (T4 intercept targets) are armed. Merchants with `weapons` should be able to fight back. For v1: only armed merchants fight back; unarmed merchants flee.
