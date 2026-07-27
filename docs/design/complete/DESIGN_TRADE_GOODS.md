# Trade Goods & Economy — Design Doc

## Overview

Add a player-driven economy. Planets/stations produce specialized goods and have demands for others. Players buy low, sell high, and scavenge cargo from destroyed ships. Cargo capacity gets real economic weight — load up on valuable goods vs. save space for mission cargo vs. keep room for loot.

### Philosophy alignment

| Principle | How this design follows it |
|-----------|---------------------------|
| **Data-first** | `TradeGood` is a frozen dataclass in `data/trade_goods/`. `PlanetSpec` gets new `produces`/`demands` fields. No economy logic in `__main__.py`. |
| **Cross-cutting state through `ctx`** | `economy_state` lives on `GameContext`. All trade helpers read/write through `ctx`. |
| **Domains own their flow** | Trade gets its own module (`trade.py`) with setup, buy/sell logic, and loot generation. Dispatcher hands off with 1 call. |
| **Atomic commits** | Each phase below is one commit. Each commit passes audit + smoke before landing. |

---

## 1. Data — TradeGood catalog

`src/spacehack/data/trade_goods/core.py`

```python
@dataclass(frozen=True)
class TradeGood:
    id: str
    name: str
    description: str
    base_price: int             # reference price in credits
    category: str               # "industrial" | "biological" | "luxury" | "raw_material" | "tech" | "contraband"
    volume: int                 # cargo units per crate (1 typical, 2 for bulk)
    rarity: float = 0.5         # 0.0 = always available, 1.0 = very rare (loot spawn weight)
```

`src/spacehack/data/trade_goods/__init__.py` — auto-discovers `TRADE_GOODS` tuples (mirrors weapons/planets pattern). Exports `find_trade_good(id)`.

### Catalog (v1)

| id | name | base_price | category | volume | rarity |
|---|---|---|---|---|---|
| `food_rations` | Food Rations | 20 | biological | 1 | 0.6 |
| `medical_supplies` | Medical Supplies | 60 | biological | 1 | 0.4 |
| `electronics` | Consumer Electronics | 80 | industrial | 1 | 0.5 |
| `machine_parts` | Machine Parts | 50 | industrial | 2 | 0.5 |
| `fuel_cells` | Fuel Cells | 40 | raw_material | 1 | 0.6 |
| `ore_processed` | Processed Ore | 30 | raw_material | 2 | 0.7 |
| `luxury_goods` | Luxury Goods | 150 | luxury | 1 | 0.3 |
| `rare_earth_metals` | Rare Earth Metals | 200 | luxury | 1 | 0.2 |
| `research_data` | Research Data | 120 | tech | 1 | 0.3 |
| `weapons_blackmarket` | Black Market Weapons | 250 | contraband | 1 | 0.1 |

---

## 2. Data — Planet economy profiles

`PlanetSpec` gets new fields:

```python
produces: dict[str, int] = {}    # good_id -> target stock
demands: dict[str, int] = {}     # good_id -> target stock (0 = shortage)
trade_npc_id: str = ""           # which NPC offers trade ("guild_master", etc.)
                                 # empty = no NPC trade (terminal only)
```

Stock starts at different levels depending on the profile:
- **Produced goods**: start at target stock (high = surplus → cheap)
- **Demanded goods**: start at 0 (shortage → expensive)
- **Neutral goods** (neither produced nor demanded): start at target_stock/2 (equilibrium → base price)
- **Target stock** for neutral goods defaults to `max_visitors * 2` (see § Runtime state)

### Price curve — one formula

```python
def trade_price(base_price, current_stock, target_stock):
    ratio = current_stock / max(1, target_stock)
    if ratio < 0.5:
        return int(base_price * (2.0 - ratio * 2.0))           # 2.0x → 1.0x
    else:
        return int(base_price * (1.0 - (ratio - 0.5) * 0.8))   # 1.0x → 0.6x
```

| Stock level | Price | Situation |
|---|---|---|
| 0% (empty) | 2.0x base | Shortage — desperate demand |
| 25% (low) | 1.5x base | Tight supply — good to sell |
| 50% (mid) | 1.0x base | Equilibrium — fair price |
| 75% (high) | 0.8x base | Surplus — good to buy |
| 100% (full) | 0.6x base | Oversupply — firesale |

### Stock evolution

- **Player buys**: stock -= quantity → price ↑
- **Player sells**: stock += quantity → price ↓
- **Passive regen** (ticked on jump/launch): stock drifts 1–2 units toward target per tick:
  ```python
  if stock < target: stock = min(target, stock + 1)
  if stock > target: stock = max(target, stock - 1)
  ```

Aggressive trading has real short-term impact, but markets recover.

### Planet profiles (v1)

| Planet | Produces (target) | Demands (target) | Trade happens through |
|---|---|---|---|
| Earth | electronics(20), food_rations(30) | luxury_goods(5), rare_earth_metals(3) | Terminal + Guild Master |
| Mars | ore_processed(25), machine_parts(15) | food_rations(20), medical_supplies(10) | Terminal + Guild Master |
| Alpha Centauri Station | research_data(10), medical_supplies(8) | food_rations(15), electronics(8) | Terminal + Research Officer |
| Sirius Station | luxury_goods(10) | machine_parts(12), fuel_cells(15) | Terminal only (future: exchange NPC) |
| Wolf B | fuel_cells(20) | electronics(5), medical_supplies(5) | Terminal + Attendant |
| Vega B | rare_earth_metals(8) | food_rations(15), machine_parts(10) | Terminal only |
| Tau Ceti Depot | machine_parts(10) | fuel_cells(8), food_rations(10) | Terminal + Attendant |
| Procyon C | food_rations(25) | electronics(5), medical_supplies(5) | Terminal only |
| Luyten Blockade | — | weapons_blackmarket(5) | Blockade Officer (black market) |
| Barnard's B | ore_processed(20) | food_rations(10), medical_supplies(5) | Terminal only |
| Epsilon Eridani B | electronics(10) | food_rations(15), fuel_cells(10) | Terminal + Attendant |
| Solar Research Station | research_data(8) | food_rations(10), electronics(5) | Terminal only |

---

## 3. Runtime — Cargo inventory

### Current state

`OwnedShip.cargo_used` is a single int: ammo cargo + mission cargo. No itemized inventory.

### Changes

```python
@dataclass
class OwnedShip:
    ...
    inventory: dict[str, int] = field(default_factory=dict)  # good_id -> crate count

    # cargo_used becomes computed:
    @property
    def cargo_used(self) -> int:
        ammo = total_ammo_cargo(self.weapons)
        mission = self._mission_reserved  # new field
        trade = sum(
            qty * find_trade_good(gid).volume
            for gid, qty in self.inventory.items()
        )
        return ammo + mission + trade
```

`ActiveMission` gets:

```python
@dataclass
class ActiveMission:
    ...
    cargo_reserved: int = 0   # set on accept, cleared on abort/complete
```

**Migration**: existing `try_accept_mission`/`complete_mission`/`abort_mission` change their `cargo_used +=/-=` to operate on `_mission_reserved` instead. The HUD still reads `cargo_used` (now a property).

### Economy state on GameContext

```python
@dataclass
class GameContext:
    ...
    economy_state: dict[str, dict[str, int]] = field(default_factory=dict)
    # economy_state[planet_id][good_id] = current_stock
```

Seeded on first visit to each planet. Persists for the session (resets on new game).

---

## 4. Domain — Trade module

`src/spacehack/trade.py` — owns the entire trade domain.

### Entry point: `open_trade(ctx, planet_id)`

Called from the dispatcher when:
- Player bumps a **trade terminal** entity in the spaceport
- Player selects `> Trade goods <` from an NPC talk dialog

### Trade terminal

Every spaceport gets a terminal Entity auto-placed by `load_planet` (if the PlanetSpec has any `produces`/`demands` data):

```python
# In load_planet, after showroom ships:
if spec.produces or spec.demands:
    port = spec.buildings[0]
    entities.append(world.Entity(
        char="=",                    # reads as a terminal/kiosk
        fg=(100, 220, 255),          # bright cyan
        pos=world.Position(port.door_x, port.y_hi - 1),  # just inside door
        name="Trade Terminal",
        npc_id="trade_terminal",     # dispatcher routes to trade module
    ))
```

**Two-tier trade:**
- **Terminal**: basic market. All goods the planet produces + neutral goods at equilibrium. No missions. Always available.
- **NPC trader** (when `trade_npc_id` matches): premium market. Same goods + exclusive ones + missions. Small price bonus vs terminal.

### Trade modal — split-screen (mockup)

```
 ┌──────────────────────────────────────────────┐
 │  TRADE — EARTH MARKET                        │
 │                                              │
 │  ┌─ Station Inventory ───┐ ┌─ Your Hold ──┐ │
 │  │ > Food Rations    14g │ │ Food Rations   │ │
 │  │   Electronics     56g │ │    2 crates   │ │
 │  │   Machine Parts   35g │ │               │ │
 │  │   Medical Sup.    42g │ │ Cargo: 12/40  │ │
 │  │   Fuel Cells      28g │ │ Credits: 320     │ │
 │  └───────────────────────┘ └───────────────┘ │
 │                                              │
 │  ENTER buy  SHIFT sell  TAB switch panel     │
 │  ESC back                                    │
 └──────────────────────────────────────────────┘
```

### Black market

- Some planets have a hidden black market sub-menu (contraband category goods)
- Contraband greyed out at normal markets
- Cargo scanning on landing: planets with a militia building have a `militia_presence%` scan chance
- If caught: goods confiscated, fine = 50% of goods' value

---

## 5. Domain — Combat loot (future phase)

When a ship is destroyed in combat:

```python
# In combat.py, at enemy death:
for good_id, tg in TRADE_GOODS.items():
    if rng.random() < tg.rarity * enemy_wealth_factor:
        # Spawn a loot entity near the wreck
        game_map.entities.append(world.Entity(
            char="*", fg=(255, 220, 80),
            pos=wreck_pos + random_offset,
            name=f"Cargo: {tg.name}",
            loot_data={"good_id": good_id, "quantity": rng.randint(1, 3)},
        ))
```

Bumping a loot entity opens **loot pickup modal** — checkbox list + "Take Selected" button. Items go to player inventory or stay in space if no room.

---

## 6. Implementation checkboxes

Checkboxes are updated as each sub-step lands.

### Phase 1 ✅ — Data + inventory (safest, no UI needed)

- [x] Create `src/spacehack/data/trade_goods/` package (`__init__.py` + `core.py`) with `TradeGood` dataclass + `TRADE_GOODS` catalog + `find_trade_good()`
- [x] Add `inventory` dict to `OwnedShip`, compute `cargo_used` as property summing ammo + mission + trade
- [x] Add `cargo_reserved` to `ActiveMission`, refactor `try_accept_mission`/`complete_mission`/`abort_mission` to use it
- [x] Add `economy_state` dict to `GameContext`
- [x] Run `python3 tools/smoke.py`
- [x] **PLAYTEST** ✅ — Cargo HUD shows correct numbers, mission accept/deliver reserves/frees cargo correctly.

### Phase 2 ✅ — Planet economy data

- [x] Add `produces`/`demands`/`trade_npc_id` fields to `PlanetSpec`
- [x] Wire `trade_price()` helper function (pure — no I/O)
- [x] Seed economy profiles for all 14 landable planets/stations
- [x] Auto-place trade terminal entity in `load_planet` when spec has economy data
- [x] Route `trade_terminal` bump → placeholder log message in dispatcher
- [x] Run audit + smoke

**PLAYTEST** ✅ — Terminal (`=`) visible outside spaceport door. Bump logs placeholder without crashing.

### Phase 3 ✅ — Trade UI (biggest)

- [x] Create `src/spacehack/trade.py` with `open_trade(ctx, planet_id)` entry point
- [x] Implement split-screen layout with station + player panels
- [x] Enter buys on station panel, sells on hold panel
- [x] Arrow-key quantity prompt, `$` currency, column separator
- [x] Wire trade terminal bump → `open_trade()` (NPC trade removed — 100% terminal)
- [x] Run audit + smoke

**PLAYTEST** ✅ — Trade modal works end-to-end. Terminal on every spaceport.

### Phase 4 ✅ — Black market + cargo scanning

- [x] Add `_can_sell_here()` helper in `trade.py` — rejects contraband sales at normal planets, allows at black-market (Blockade)
- [x] Contraband hold-panel indicator — shows `---$` and dimmed color for unsellable contraband items
- [x] Add `_run_cargo_scan()` in `__main__.py` — checks militia building presence, rolls 40% scan, confiscates + fines
- [x] Wire cargo scan into landing flow — called before city load on planetary landings
- [x] Run audit + smoke ✅

**PLAYTEST** ✅ — Cargo scan fires on Earth landing (~40% chance). Contraband confiscated + fined when caught. Contraband blocked at normal terminals. Blockade sells and buys contraband correctly.

> **Note**: Contraband profit margins depend on Blockade's stock level. Currently `weapons_blackmarket` is only in Blockade's `produces` (starts at full stock → cheap to buy, low sell price). For proper contraband profit, a future planet should `demand` black market goods, creating a price gradient. This is Phase 6 balance work.

### Phase 5 ✅ — Combat loot

- [x] Add `loot_data` field to `world.Entity`
- [x] Generate loot entities on ship destruction in `combat.py`
- [x] Render loot entities on space map (gold `*`)
- [x] Implement `open_loot_pickup(ctx, entity)` modal
- [x] Wire bump + loot entity → open loot pickup
- [x] Run audit + smoke

**PLAYTEST** ✅ — Engage a pirate squad in combat. Destroy a ship. Verify gold `*` entities appear in space near the wreck. Bump one → loot modal opens. Take items → they appear in cargo. Verify cargo capacity check works (can't take more than free space). Combat stacking fix playtested: enemies no longer occupy the same tile (post-turn dedup removed, per-move collision prevention verified).

### Phase 6 — Polish

#### Sub-phase 6a — Cargo Menu

A full-screen modal to view and manage the player's cargo inventory. Replaces the basic `Cargo: X/Y` stats line in the current View panel with an interactive cargo viewer that also supports jettisoning items.

##### Entry points

- **On a planet** (hangar): The existing `View` option in the ship-menu now opens the **Cargo Menu** instead of the bare stats panel. Ship stats (hull, weapons, modules) are still shown but as a header — the focus is the cargo breakdown.
- **In space**: Press `C` while in space mode to open the Cargo Menu. `C` is unused by vim movement so no key conflict. The cargo menu is an overlay modal that pauses the space game loop while open (same pattern as `M` for navigation overlay).

##### Layout (mockup)

```
 ┌──────────────────────────────────────────────┐
 │  CARGO — SCOUT (10/40)                       │
 │  Hull: 12% damage  |  Wpn: 2/2  |  Mod: 1/2 │
 │──────────────────────────────────────────────│
 │                                              │
 │  TRADE GOODS:                                │
 │  > Food Rations            20 crates (20u)   │
 │    Electronics              5 crates ( 5u)   │
 │    Luxury Goods             3 crates ( 3u)   │
 │                                              │
 │  MISSION CARGO (reserved):  8 units          │
 │    Active: Deliver Electronics to Vega B     │
 │                                              │
 │  AMMO:                       2 units          │
 │                                              │
 │  FREE:                       2 units          │
 │                                              │
 │  [J] jettison selected  [C] close             │
 └──────────────────────────────────────────────┘
 ```

##### Jettison flow

- UP/DOWN to navigate the list of trade goods in cargo
- Press `J` on a selected good → quantity prompt (like trade's arrow-key adjustment, max = held qty)
- Confirm → goods are **destroyed** (no profit, no log message about selling — they're gone)
- If mission cargo or ammo slot is selected, jettison is **not available** (dimmed text) — those have dedicated management flows
- Jettisoning frees cargo space immediately

##### Breakdown display

The cargo menu shows a clear breakdown of what's taking up space:

| Section | Content |
|---------|---------|
| **Header** | Ship name, `cargo_used / max_cargo`, hull damage pct, weapon/module slots |
| **Trade Goods** | Itemized list with good name, quantity, and volume used. Selected item highlighted with `>`. |
| **Mission Cargo** | (If active mission) Reserved space + mission title. Read-only. |
| **Ammo** | Computed ammo cargo total from installed weapons. Read-only. |
| **Free** | Remaining available cargo space. Highlighted green if >0, red if 0. |

##### Key bindings

| Key | Action |
|-----|--------|
| UP/DOWN or j/k | Navigate trade goods list |
| J | Jettison selected good (quantity prompt) |
| C or ESC | Close cargo menu |
| Any other key | Close cargo menu (same as ESC — read convenience) |

##### Implementation notes

- `open_cargo(ctx)` lives in `trade.py` alongside the trade modal — it's a cargo-domain UI function
- Reuses `_run_quantity_prompt()` from trade.py for the jettison quantity input
- On jettison: calls `del owned.inventory[good_id]` or decrements, logs to message log
- The space mode dispatcher in `__main__.py` gets a `_is_c_press()` helper (mirrors `_is_m_press`)
- The planet hangar `View` option's sub-modal is replaced: instead of `render_ship_view`, call `open_cargo()`
- The old `render_ship_view` function can be removed or kept for reference — the cargo menu's header serves the same purpose

##### Checklist

- [x] Implement `open_cargo(ctx)` in `trade.py` with full layout + jettison
- [x] Add `_is_c_press()` helper in `__main__.py` for space-mode entry
- [x] Wire `C` key in space dispatcher → `open_cargo()`
- [x] Replace View sub-modal in `_run_ship_menu` → `open_cargo()`
- [x] Added `C` - Cargo to HUD help lines in space mode
- [x] Removed dead code (`_run_ship_view`, `render_ship_view`, `update_ship_view`, `ShipViewOutcome`)
- [x] Run audit + smoke ✅

**PLAYTEST** ✅ — Load up with various goods from trade terminals + loot. Open cargo menu on a planet (View option) and in space (C key). Jettison some goods. Cargo count updates immediately, free space recalcs correctly.

#### Sub-phase 6b — Balance trade route profits + combat loot

##### Combat loot balancing (priority)

**Problem**: Pirates drop ~4.2 goods per kill on average (10 goods × 0.1-0.7 rarity), each 1-3 crates. A single pirate can drop 10+ crates worth hundreds of credits. Players get rich too fast.

**Changes to current loot logic** (in `combat.py`):

1. **Cap items per kill**: Only roll for 1-2 random goods per destroyed ship instead of iterating all 10.
   ```python
   # Instead of:
   for _tg in _TRADE_GOODS:
       if RNG.random() >= _tg.rarity: continue
       # spawn 1-3 crates...
   
   # Do:
   _loot_count = RNG.randint(1, 2)
   _loot_pool = list(_TRADE_GOODS)
   for _ in range(_loot_count):
       _tg = RNG.choice(_loot_pool)
       if RNG.random() >= _tg.rarity:
           continue
       _qty = RNG.randint(1, 2)  # reduced from 1-3
       # spawn loot...
   ```

2. **Reduce quantity**: Change `RNG.randint(1, 3)` → `RNG.randint(1, 2)` — crates per good.

3. **Drop rich loot less often**: Rare/high-value goods (`weapons_blackmarket` 250$, `rare_earth_metals` 200$, `luxury_goods` 150$) already have low rarity (0.1-0.3), so their spawn chance is naturally lower. With the per-kill cap they'll appear in roughly 1 in 10 kills instead of every other kill.

4. **Future: enemy loot tables** (not in this phase): Different enemy types could have different drop pools (pirates drop weapons/contraband, militia drops basic supplies, merchants drop luxury goods). Postponed to avoid over-engineering.

**Expected results**:

| Metric | Before | After |
|--------|--------|-------|
| Avg items per kill | ~4.2 | ~0.6-1.2 |
| Avg crates per kill | ~8.4 | ~0.9-2.4 |
| Avg value per kill | ~400-600$ | ~30-100$ |
| Kills to fill Scout (40 cargo) | ~5 | ~20-40 |

Loot still feels rewarding (every kill has a decent shot at dropping something) but players need to work for a full cargo hold rather than filling up from one squad engagement.

- [x] Adjust combat loot: cap items per kill to 1-2, reduce crate quantity to 1-2
- [x] Run audit + smoke ✅

**PLAYTEST** — Engage a pirate squad. Verify loot drops are 1-4 crates total (not 10+). Fly 3 consecutive combat encounters. Verify cargo doesn't fill up immediately. Verify the kill-to-profit ratio feels rewarding but not OP.

##### Trade route balancing

- [x] Add passive stock regen (`tick_economy`) — called on jump/launch
- [x] Add neutral goods to all trade terminals (seeded at equilibrium)
- [x] Add contraband demand to Barnard's b (`weapons_blackmarket, 8`) for profit gradient
- [x] Tuned target stocks (added NEUTRAL_TARGET=8, updated planet profiles)
- [x] Run audit + smoke ✅

**PLAYTEST** — Fly a full trade circuit: Earth -> Procyon C -> Vega B -> Earth. Verify you can make a profit that justifies the fuel cost and travel time. Try the same route with different ships (Scout's 40 cargo vs Hauler's 120). Verify the Hauler's extra cargo space translates to proportionally more profit.

#### Sub-phase 6c — More trade goods

- [x] Add 3 new trade goods (pharmaceuticals, ship_components, textiles)
- [x] Run audit + smoke ✅

#### Phase 6 — Complete

All Phase 6 sub-phases are implemented. See the commit history for the full set of changes.

---

## 7. Open questions / future

| Question | Decision needed when |
|---|---|
| Should pirate ships drop better loot than militia ships? | Phase 5 implementation |
| What's the militia scan % for each planet? Flat 40% for any planet with militia, or per-planet? | Phase 4 implementation |
| Do loot entities persist across player jumps? (Current design: no — fresh system = fresh loot) | Phase 5 implementation |
| Dynamic NPC trader ships that move goods between systems? | Post-v1 |
| Faction reputation affecting prices? | Post-v1 |
| Cargo insurance (pay gold to protect goods on death)? | Post-v1 |
