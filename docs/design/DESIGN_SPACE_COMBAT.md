# Space Combat Design

## Guiding Principles

Every new subsystem below follows the **same data-driven catalog pattern** the project already uses for solar systems, planets, NPCs, ships, species, and classes:

```
data/
  weapons/
    __init__.py    ← WeaponSpec catalog + _BY_ID registry
    lasers.py      ← module-level WEAPONS tuple
    missiles.py
  modules/
    __init__.py    ← ModuleSpec catalog + _BY_ID registry
    engines.py     ← module-level MODULES tuple
    systems.py
  enemies/
    __init__.py    ← EnemySpec catalog + _BY_ID registry
    pirates.py     ← module-level ENEMIES tuple
    militia.py
```

Each catalog:
- exports a **frozen dataclass** for specs (`WeaponSpec`, `ModuleSpec`, `EnemySpec`)
- defines a **module-level `TUPLES`** of entries
- builds a **`_BY_ID` lazy registry** via `_build_registry()`
- exposes a **`find_*(id)` function** that raises `KeyError` on unknowns
- puts **all fields inline** in each entry — no if/else chains, no type-dispatch logic

Adding a new weapon / module / enemy is **one new entry in one tuple** — no dispatcher rewrites, no engine changes, no special cases.

---

## 1. Weapons Catalog — `spacehack/data/weapons/`

### `__init__.py`

```python
@dataclass(frozen=True)
class WeaponSpec:
    id: str                            # e.g. "light_laser", "heavy_missile"
    name: str                          # e.g. "Light Laser", "Heavy Missile"
    slot_type: str                     # "energy" or "missile" (controls ammo/power rules)
    damage: int                        # base damage per hit (before skill/range modifiers)
    accuracy: int                      # base hit % (0-100)
    ap_cost: int = 1                   # action points to fire once
    power_cost: int = 0                # power drained per shot (energy weapons only)
    ammo_capacity: int = -1            # -1 = no ammo (energy weapon)
    ammo_per_shot: int = 1             # rounds consumed per shot (missile weapons)
    cargo_per_round: int = 0           # cargo space consumed per round of ammo
    min_range: int = 1                 # minimum cell distance to target
    max_range: int = 5                 # maximum cell distance to target

WEAPONS: tuple[WeaponSpec, ...] = (...)
_BY_ID: dict[str, WeaponSpec] = {w.id: w for w in WEAPONS}

def find_weapon(weapon_id: str) -> WeaponSpec: ...
```

### Example entries (`lasers.py`):

```python
WEAPONS = (
    WeaponSpec(
        id="light_laser", name="Light Laser", slot_type="energy",
        damage=3, accuracy=80, ap_cost=1, power_cost=2,
        min_range=1, max_range=4,
    ),
    WeaponSpec(
        id="heavy_laser", name="Heavy Laser", slot_type="energy",
        damage=8, accuracy=65, ap_cost=1, power_cost=6,
        min_range=1, max_range=5,
    ),
    WeaponSpec(
        id="plasma_cannon", name="Plasma Cannon", slot_type="energy",
        damage=12, accuracy=55, ap_cost=2, power_cost=10,
        min_range=1, max_range=6,
    ),
)
```

### Example entries (`missiles.py`):

```python
WEAPONS = (
    WeaponSpec(
        id="light_missile", name="Light Missile", slot_type="missile",
        damage=10, accuracy=75, ap_cost=2, power_cost=0,
        ammo_capacity=5, ammo_per_shot=1, cargo_per_round=1,
        min_range=1, max_range=6,
    ),
    WeaponSpec(
        id="heavy_missile", name="Heavy Missile", slot_type="missile",
        damage=20, accuracy=60, ap_cost=2, power_cost=0,
        ammo_capacity=3, ammo_per_shot=1, cargo_per_round=2,
        min_range=2, max_range=7,
    ),
    WeaponSpec(
        id="emp_missile", name="EMP Missile", slot_type="missile",
        damage=0, accuracy=70, ap_cost=2, power_cost=0,
        ammo_capacity=2, ammo_per_shot=1, cargo_per_round=2,
        min_range=1, max_range=5,
        # EMP effect handled by combat engine, not data
    ),
)
```

---

## 2. Modules Catalog — `spacehack/data/modules/`

### `__init__.py`

```python
@dataclass(frozen=True)
class ModuleSpec:
    id: str                              # e.g. "compact_reactor", "targeting_comp"
    name: str
    slot_type: str                       # "engine" or "system"
    description: str
    # All effects are additive bonuses. 0 = no bonus.
    power_gen_bonus: int = 0
    max_shield_bonus: int = 0
    shield_recharge_bonus: int = 0
    cargo_bonus: int = 0
    gunnery_bonus: int = 0
    piloting_bonus: int = 0
    engineering_bonus: int = 0
    max_hull_bonus: int = 0
    price: int = 0                       # gold cost to buy

MODULES: tuple[ModuleSpec, ...] = (...)
_BY_ID: dict[str, ModuleSpec] = {m.id: m for m in MODULES}

def find_module(module_id: str) -> ModuleSpec: ...
```

### Example entries (`engines.py`):

```python
MODULES = (
    ModuleSpec(
        id="compact_reactor", name="Compact Reactor",
        slot_type="engine", description="A small fusion plant. +3 power gen.",
        power_gen_bonus=3, price=50,
    ),
    ModuleSpec(
        id="heavy_reactor", name="Heavy Reactor",
        slot_type="engine", description="A massive plant. +6 power gen, -1 cargo.",
        power_gen_bonus=6, cargo_bonus=-1, price=120,
    ),
)
```

### Example entries (`systems.py`):

```python
MODULES = (
    ModuleSpec(
        id="shield_capacitor", name="Shield Capacitor",
        slot_type="system", description="+15 max shields.",
        max_shield_bonus=15, price=80,
    ),
    ModuleSpec(
        id="shield_recharger", name="Shield Recharger",
        slot_type="system", description="+3 shield regen per turn.",
        shield_recharge_bonus=3, price=100,
    ),
    ModuleSpec(
        id="targeting_computer", name="Targeting Computer",
        slot_type="system", description="+10 gunnery.",
        gunnery_bonus=10, price=70,
    ),
    ModuleSpec(
        id="gyro_stabilizer", name="Gyro Stabilizer",
        slot_type="system", description="+10 piloting.",
        piloting_bonus=10, price=70,
    ),
    ModuleSpec(
        id="expanded_cargo", name="Expanded Cargo Bays",
        slot_type="system", description="+30 cargo capacity.",
        cargo_bonus=30, price=40,
    ),
    ModuleSpec(
        id="armor_plating", name="Armor Plating",
        slot_type="system", description="-5% hull damage taken. -1 power gen.",
        max_hull_bonus=5, power_gen_bonus=-1, price=90,
    ),
)
```

---

## 3. Enemies Catalog — `spacehack/data/enemies/`

### `__init__.py`

```python
@dataclass(frozen=True)
class AIProfile:
    aggressiveness: int      # 0-100, chance to attack vs reposition each turn
    preferred_range: int     # tries to maintain this distance from target
    flee_threshold: float    # hull % below which AI tries to flee (0.0-1.0)
    accuracy_bonus: int = 0  # per-difficulty modifier
    dodge_bonus: int = 0

@dataclass(frozen=True)
class EnemySpec:
    id: str                              # e.g. "pirate_scout", "militia_patrol"
    name: str                            # e.g. "Pirate Scout"
    char: str                            # glyph on the solar system map
    fg: tuple[int, int, int]
    ship_id: str                         # hull reference (scout/hauler/cruiser)
    weapons: tuple[str, ...]             # weapon ids fitted at spawn
    modules: tuple[str, ...]             # module ids fitted at spawn
    ai: AIProfile
    detect_radius: int = 8               # cells before combat triggers
    min_power_gen: int = 3               # base power generated per turn
    pilot_skills: dict[str, int] = ...   # {"gunnery": X, "piloting": Y, "engineering": Z}

ENEMIES: tuple[EnemySpec, ...] = (...)
_BY_ID: dict[str, EnemySpec] = {e.id: e for e in ENEMIES}

def find_enemy(enemy_id: str) -> EnemySpec: ...
```

### Example entries (`pirates.py`):

```python
ENEMIES = (
    EnemySpec(
        id="pirate_scout", name="Pirate Scout",
        char="p", fg=(255, 100, 100),
        ship_id="scout",
        weapons=("light_laser",),
        modules=("compact_reactor",),
        ai=AIProfile(aggressiveness=60, preferred_range=3, flee_threshold=0.15),
        detect_radius=8,
        min_power_gen=3,
        pilot_skills={"gunnery": 20, "piloting": 25, "engineering": 10},
    ),
    EnemySpec(
        id="pirate_raider", name="Pirate Raider",
        char="P", fg=(220, 60, 60),
        ship_id="cruiser",
        weapons=("light_laser", "light_missile"),
        modules=("compact_reactor", "shield_capacitor"),
        ai=AIProfile(aggressiveness=75, preferred_range=4, flee_threshold=0.10),
        detect_radius=10,
        min_power_gen=4,
        pilot_skills={"gunnery": 30, "piloting": 20, "engineering": 15},
    ),
)
```

---

## 4. Ship Modifications — `spacehack/ship.py`

Two existing dataclasses get extended:

```python
@dataclass(frozen=True)
class Ship:
    # ... existing fields ...
    base_power_gen: int = 3          # NEW: power generated per turn
    base_shield_max: int = 0         # NEW: base shield HP (0 = no shields by default)
    base_shield_recharge: int = 0    # NEW: base shield regen per turn

@dataclass
class OwnedShip:
    ship_id: str
    cargo_used: int = 0
    hull_damage_pct: int = 0
    weapons: tuple[str, ...] = field(default_factory=tuple)
    modules: tuple[str, ...] = field(default_factory=tuple)
    fuel: int = 0

    # NEW combat state (resets per-encounter):
    hull_current: int = 100          # hit points (not %), computed from hull_damage_pct
    shields_current: int = 0         # shield HP
    shields_charged: bool = False    # whether player toggled shields on this turn
    power_pool: int = 0              # available power this turn
    ap_remaining: int = 0            # action points left this turn
    ap_total: int = 0                # action points per turn (computed from piloting)
    weapon_ammo: dict[str, int] = ...  # weapon_id -> remaining shots

# Computed stats (helpers, not stored):
def ship_max_hull(ship: Ship) -> int: ...
def ship_power_gen(ship: Ship, owned: OwnedShip) -> int: ...  # base + module bonuses
def ship_max_shields(ship: Ship, owned: OwnedShip) -> int: ...
def ship_ap_per_turn(ship: Ship, owned: OwnedShip, pilot_skills: dict) -> int: ...
```

---

## 5. Pilot Skills — `spacehack/character.py`

```python
@dataclass
class PilotSkills:
    gunnery: int = 30         # base accuracy, weapon mods can boost
    piloting: int = 30        # AP per turn = 3 + floor(piloting / 20), dodge bonus
    engineering: int = 30     # power efficiency, shield recharge rate

SPECIES_SKILL_BONUSES: dict[str, dict[str, int]] = {
    "human":   {"gunnery": 5,  "piloting": 0,  "engineering": 5},
    "martian": {"gunnery": 5,  "piloting": 10, "engineering": 5},
}

CLASS_SKILL_BONUSES: dict[str, dict[str, int]] = {
    "pirate":        {"gunnery": 15, "piloting": 10, "engineering": 0},
    "merchant":      {"gunnery": 0,  "piloting": 5,  "engineering": 15},
    "bounty_hunter": {"gunnery": 10, "piloting": 10, "engineering": 5},
}
```

---

## 6. Combat Engine — `spacehack/combat.py`

This is the **only module with imperative logic** — everything else is data.

```python
class CombatState:
    player_owned: OwnedShip
    player_ship: Ship
    player_pos: world.Position
    player_skills: PilotSkills
    enemies: list[EnemyInstance]    # mutable combat copies
    turn: int
    phase: CombatPhase              # PLAYER_TURN, ENEMY_TURN, VICTORY, DEFEAT, FLEE

class EnemyInstance:
    spec: EnemySpec
    hull: int
    shields: int
    shields_charged: bool
    power_pool: int
    ap_remaining: int
    pos: world.Position
    weapon_ammo: dict[str, int]
    pilot_skills: PilotSkills   # spec's base + any encounter modifiers
    threat_targets: list[int]   # which player positions it's seen

# Core loop functions:
def init_combat(player, enemy_spec, ...) -> CombatState: ...
def execute_player_action(state, action: CombatAction) -> CombatEvent: ...
def execute_enemy_turn(state) -> list[CombatEvent]: ...
def resolve_hit(attacker_skills, weapon, target_pos, attacker_pos, target_dodge) -> bool: ...
def resolve_damage(weapon, target) -> int: ...  # returns actual hull damage dealt
def check_victory(state) -> CombatPhase: ...
```

### Damage Formula (no if/else chains):

```python
def calc_hit_chance(
    weapon: WeaponSpec, gunnery: int,
    distance: int, target_dodge_bonus: int,
) -> int:
    """Returns 0-100 hit probability."""
    distance_penalty = max(0, distance - weapon.max_range) * 10 if distance > weapon.max_range else 0
    distance_bonus = 5 if distance <= weapon.max_range // 2 else 0  # close-range aim bonus
    return (
        weapon.accuracy
        + gunnery * 0.5
        + distance_bonus
        - distance_penalty
        - target_dodge_bonus
    )

def resolve_hit(chance: int) -> bool:
    return random.randint(1, 100) <= chance

def calc_dodge_bonus(cells_moved_this_turn: int) -> int:
    """+5% dodge per cell moved, capped at 30%."""
    return min(cells_moved_this_turn * 5, 30)
```

### Power Formula:

```python
def calc_power_gen(ship: Ship, owned: OwnedShip) -> int:
    total = ship.base_power_gen
    for mod_id in owned.modules:
        spec = find_module(mod_id)
        total += spec.power_gen_bonus
    return max(0, total)

def calc_ap_per_turn(piloting: int) -> int:
    return 3 + (piloting // 20)
```

---

## 7. Combat Flow (Turn Loop)

```
                      ┌──────────────────────┐
                      │    Enter combat       │
                      │  (auto-detect radius) │
                      └──────────┬───────────┘
                                 │
                      ┌──────────▼───────────┐
                      │  Roll initiative      │
                      │ (10 + piloting * 0.2) │
                      └──────────┬───────────┘
                                 │
            ┌────────────────────┼────────────────────┐
            ▼                    ▼                    ▼
    ┌───────────────┐   ┌───────────────┐   ┌───────────────┐
    │  PLAYER TURN   │   │  ENEMY TURN   │   │  COMBAT END   │
    │               │   │               │   │               │
    │ 1. Calc AP    │   │ 1. Evaluate   │   │ VICTORY       │
    │ 2. Calc power │   │    threat     │   │  - loot       │
    │ 3. Show HUD   │   │ 2. Move /     │   │  - XP         │
    │ 4. Wait input │   │    Attack     │   │ DEFEAT        │
    │ 5. Execute    │   │ 3. Check flee │   │  - game over  │
    │ 6. Check end  │   │ 4. Check end  │   │ FLEE          │
    └───────┬───────┘   └───────┬───────┘   │  - return to  │
            │                   │            │    space map  │
            └───────────────────┘            └───────────────┘
```

---

## 8. Combat HUD & Controls — `spacehack/hud.py`

During combat the right-side HUD is replaced by a **combat HUD** that shows
both ships' statuses, a list of available actions, and weapon details.
The combat grid viewport (left side of screen) adds **targeting overlays**
when the player is picking a target.

### 8a. Combat HUD Layout

```
+---------------------+----------------------+
|                     | > COMBAT <           |   ← title (gold, centered)
|                     | Turn 3               |   ← turn counter
|     COMBAT GRID     |                      |
|                     | PLAYER               |   ← player block
|   (scrollable       | Scout                |
|    tactical         | Hull 100% ████████   |   ← bar + %
|    viewport)        | Shd 100% ████░░░░    |   ← bar + %
|                     | AP: 2/4              |   ← action points
|                     | Pow: 5/8             |   ← power pool / max
|                     |                      |
|                     | ──── TARGET ────     |   ← selected enemy block
|                     | Pirate Scout         |   ← name (red-tinted)
|                     | Hull  85% ██████░░   |
|                     | Shd    0% ░░░░░░░░   |
|                     | Dist: 6 cells        |   ← distance from player
|                     |                      |
|                     | ──── WEAPONS ────    |   ← equipped list
|                     | [1] Light Laser      |   ← number = hotkey
|                     |      DMG 3  ACC 80%  |   ← stats line
|                     |      POW 2  AP 1     |   ← cost line
|                     | [2] Light Missile    |
|                     |      DMG 10 ACC 75%  |
|                     |      AMMO 5  AP 2    |   ← missile shows ammo instead of power
|                     |                      |
|                     | ──── ACTIONS ────    |
|                     | [m] Move             |   ← mode: highlights valid move tiles
|                     | [f] Fire Weapon      |   ← mode: highlights in-range enemies
|                     | [s] Shields On/Off   |   ← toggle, shows current state
|                     | [w] Wait (end turn)  |   ← skip, AP forfeited
|                     | [ESC] Try to Flee    |   ← attempt escape
|                     |                      |
|                     | arrow keys: navigate |
|                     | combat grid          |
|                     |                      |
|                     | Last: Laser hits!    |   ← combat log (last 1-2 events)
+---------------------+----------------------+
```

### 8b. HUD Sections (top to bottom)

**Player status block:**
- Ship name
- Hull bar — 8 chars wide, `█` = intact, `░` = damage. Color: green if >50%, yellow if >25%, red otherwise
- Shield bar — same 8-char bar. Cyan/teal color
- AP: current / total (yellow if any remaining, red if 0)
- Power: current pool / max capacity (blue-white)

**Target block:** (only shown when a target enemy is selected)
- Enemy name (red-tinted foreground)
- Hull bar + shield bar (same 8-char bar format)
- Distance in cells from player ship to target

**Weapons block:**
- Numbered list of each installed weapon (1, 2, 3...)
- Per weapon: damage, accuracy %, and either power cost or ammo count
- Weapon is grayed out / dimmed if:
  - Not enough AP remaining
  - Not enough power for energy weapons
  - Out of ammo for missile weapons
  - Target out of range (dims when no target, shows "OOR" when target is too far)
- The currently selected weapon (for firing) has `>` prefix

**Actions block:**
- Each action has a single-key hotkey shown in brackets
- Toggle actions (Shields) show current state inline: `[s] Shields: ON` or `[s] Shields: OFF`
- Flee option shows a 1-line hint about escape chance when highlighted

**Combat log line:**
- Bottom of HUD: last 1-2 events from that round
- Examples: `"Light Laser hits for 4 damage!"`, `"Pirate Scout misses!"`

### 8c. Combat Grid Overlay States

The left-side viewport (the combat grid) changes appearance based on the
player's current **mode**:

**Default mode** (no action selected):
- Player ship shown as `@` (bright yellow, same as space mode)
- Enemy ships shown as their `char` glyph (red-tinted)
- All ships have a **health bar** drawn directly beneath them on the grid:
  `[████░░]` — 6 cells wide, draws _under_ the tile row
- A thin `·` dotted line connects player to the currently selected enemy
  (so the player can see which enemy is targeted at a glance)
- Range rings (optional): faint `·` dots at weapon max_range distance
  intervals around the player, rendered as subtle colored dots on
  walkable cells only

**Move mode** (pressed `m`):
- Walkable cells within AP budget highlighted with `·` in player's color
- Player ship `@` blinks (inverted colors each frame? or just bright)
- Cost shown: each highlighted cell shows a small digit `1`/`2`/`3`
  indicating AP cost to reach that cell
- Enemy cells stay red; moving through an enemy cell is blocked
- Press `m` again or `ESC` to cancel movement mode

**Fire mode** (pressed `f`):
- Ship `@` blinks
- A reticle `+` appears at each in-range enemy cell
- Current target shown with a brighter `⊕` reticle
- A small readout near the reticle shows:
  `Light Laser: 80% / 6 cells`
- Arrow keys or `h/j/k/l` move the reticle between valid targets
- Press `1` / `2` / `3` to switch which weapon is selected for firing
- `ENTER` or space to confirm fire at current reticle target
- `ESC` to cancel fire mode

**Shields toggle** (`s`):
- Instant toggle, no mode change
- Shows a brief flash animation on the HUD when activated
- If insufficient power, logs a message and refuses the toggle

### 8d. Keyboard Controls Reference

| Key | Mode | Action |
|-----|------|--------|
| `h/j/k/l` | any | Move reticle / navigate grid (vim-style) |
| `y/u/b/n` | any | Diagonal movement / reticle |
| `m` | any | Enter Move mode (exit with `m` or `ESC`) |
| `f` | any | Enter Fire mode (exit with `f` or `ESC`) |
| `1`-`9` | Fire mode | Select which weapon to fire |
| `ENTER` | Fire mode | Confirm fire at current target |
| `s` | any | Toggle shields on/off |
| `w` | any | Wait (end turn, forfeit remaining AP) |
| `ESC` | Default | Attempt to flee combat |
| `ESC` | Move/Fire | Cancel mode, return to default |

### 8e. Flee Mechanic

Fleeing is **not guaranteed** — it's a contested check:

```python
def calc_flee_chance(
    player_piloting: int,
    enemy_piloting: int,
    player_hull_remaining: float,   # 0.0-1.0
    cells_to_map_edge: int,          # how far the player is from the solar system edge
    distance_to_enemy: int,          # current combat distance in cells
) -> int:  # returns 0-100
    base = 30                                   # 30% baseline
    base += (player_piloting - enemy_piloting) * 2  # skill difference
    base += max(0, (1.0 - player_hull_remaining) * 20)  # damaged ships flee more desperately
    base += max(0, cells_to_map_edge * 3)           # closer to edge = easier escape
    base -= max(0, 5 - distance_to_enemy) * 5       # harder to flee when close
    return max(5, min(95, base))                    # clamp 5%-95%
```

**Flee flow:**
1. Player presses `ESC` in default mode
2. HUD shows `"Attempting to flee..."` with computed % chance
   (e.g., `"Escape chance: 55%"`)
3. Press `ENTER` to confirm flee attempt, `ESC` to cancel
4. If successful: combat ends, player ship is moved `3-5` cells in
   the direction opposite to the enemy's approach on the solar system map
5. If failed: enemy gets a **free attack** on the fleeing ship (reaction
   shot), then combat continues with the player's turn forfeited
6. Multiple flee attempts in the same combat add a stacking `+10%`
   bonus per attempt (each failure makes the next attempt easier,
   representing the enemy's pursuit tiring)

### 8f. Combat End Screen

**Victory:**
- Brief overlay flashes `"VICTORY!"` centered on screen
- Loot summary shown for 3 seconds:
  ```
  VICTORY!
  ────────
  Scrap recovered: 25 gold
  Cargo salvaged: 3 units
  ```
- Player is returned to the solar system map at their current position
- Enemy entity is removed from the system map

**Defeat:**
- If hull reaches 0%, `"SHIP DESTROYED"` overlay
- Options: `[L] Load save` / `[ESC] Return to title`
- (Future: escape pod mechanic → respawn at last docked station)

**Flee success:**
- `"Escaped!"` overlay, 1 second
- Return to solar system map a few cells away
- Enemy remains on the system map (can re-engage)

---

### 8g. render_combat_hud() Signature

```python
def render_combat_hud(
    console: tcod.console.Console,
    *,
    screen_width: int,
    screen_height: int,
    combat_state: CombatState,
    selected_weapon_idx: int,
    mode: CombatMode,           # DEFAULT, MOVING, FIRING
    combat_log: list[str],      # last 2 event strings
    flee_chance: int | None,    # shown during flee confirmation
) -> None:
    """Paint the combat HUD into the right panel (HUD_WIDTH columns).

    Completely replaces :func:`render_hud` while a combat encounter
    is active. Clears the HUD region first, then paints each block
    from top to bottom. The caller (combat dispatcher in __main__)
    is responsible for calling this every frame instead of render_hud.
    """
```

---

## 9. Enemy Spawning — `spacehack/data/solar_systems/`

Extend `SolarSystem` with an optional enemy patrol list:

```python
@dataclass(frozen=True)
class EnemySpawn:
    enemy_id: str                # references EnemySpec.id
    pos: world.Position
    wandering: bool = True       # moves around patrol route
    patrol_radius: int = 5       # cells around spawn point it wanders

@dataclass(frozen=True)
class SolarSystem:
    # ... existing fields ...
    enemies: tuple[EnemySpawn, ...] = ()
```

### Example in `sol.py`:

```python
SYSTEM = SolarSystem(
    id="sol",
    # ... existing fields ...
    enemies=(
        EnemySpawn(enemy_id="pirate_scout", pos=world.Position(160, 50), patrol_radius=5),
        EnemySpawn(enemy_id="pirate_raider", pos=world.Position(50, 110), patrol_radius=8),
    ),
)
```

Enemies are rendered as `world.Entity` objects in the space map (using the `EnemySpec.char`/`fg`), move along their patrol routes when the player isn't nearby, and switch to combat engagement when the player enters `detect_radius`.

---

## 10. New File Summary

```
src/spacehack/
  combat.py                          ← Combat engine (combat.py)
  data/
    weapons/
      __init__.py                    ← WeaponSpec, find_weapon()
      lasers.py                      ← WEAPONS tuple
      missiles.py                    ← WEAPONS tuple
    modules/
      __init__.py                    ← ModuleSpec, find_module()
      engines.py                     ← MODULES tuple
      systems.py                     ← MODULES tuple
    enemies/
      __init__.py                    ← EnemySpec, AIProfile, find_enemy()
      pirates.py                     ← ENEMIES tuple
      militia.py                     ← ENEMIES tuple

Modified:
  ship.py                            ← Ship gains power/shield fields, OwnedShip gains combat state
  character.py                       ← PilotSkills dataclass + species/class skill bonuses
  hud.py                             ← render_combat_hud()
  data/solar_systems/__init__.py     ← EnemySpawn, SolarSystem.enemies field
  data/solar_systems/sol.py          ← pirate patrols in Sol
  __main__.py                        ← combat dispatch in space mode movement loop
```

---

## 11. Extensibility

### Adding a new weapon:
1. Create entry in the appropriate `data/weapons/*.py` tuple
2. Done. The combat engine reads all fields from the spec — no if/else.

### Adding a new module:
1. Create entry in the appropriate `data/modules/*.py` tuple
2. The generic `calc_*` helper functions (e.g. `calc_power_gen`) iterate all installed modules and sum bonuses by field name — no if/else.

### Adding a new enemy type:
1. Create entry in the appropriate `data/enemies/*.py` tuple
2. Reference an existing `ship_id`, existing `weapon_ids`, existing `module_ids`
3. Done. The `AIProfile` drives behaviour — no if/else.

### Adding a new solar system with enemies:
1. Create the system module as usual
2. Add an `enemies=` tuple with `EnemySpawn` entries
3. Done. The space-mode renderer shows them, the detection system triggers combat on approach.

### Adding a new pilot skill effect:
1. Add a new field to `PilotSkills`
2. Add its contribution formula to the relevant `calc_*` helper
3. Done. `SpeciesSpec` / `class` tables can reference it.
