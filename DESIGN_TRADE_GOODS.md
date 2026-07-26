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
    base_price: int             # reference price in gold
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
| 0% (empty) | 2.0× base | Shortage — desperate demand |
| 25% (low) | 1.5× base | Tight supply — good to sell |
| 50% (mid) | 1.0× base | Equilibrium — fair price |
| 75% (high) | 0.8× base | Surplus — good to buy |
| 100% (full) | 0.6× base | Oversupply — firesale |

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
 │  │   Fuel Cells      28g │ │ Gold: 320     │ │
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
- [x] Run `python3 tools/smoke.py` + `python3 tools/audit_loose_refs.py`
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

**PLAYTEST** — Buy black market weapons at Luyten Blockade. Fly to Earth with them. Land → 40% scan chance. If caught: goods confiscated, fine deducted. If not: try selling at Earth terminal → "No one here deals in Black Market Weapons — contraband." Fly back to Blockade → sell successfully at the black market.

> **Note**: Contraband profit margins depend on Blockade's stock level. Currently `weapons_blackmarket` is only in Blockade's `produces` (starts at full stock → cheap to buy, low sell price). For proper contraband profit, a future planet should `demand` black market goods, creating a price gradient. This is Phase 6 balance work.

### Phase 5 — Combat loot

- [ ] Add `loot_data` field to `world.Entity`
- [ ] Generate loot entities on ship destruction in `combat.py`
- [ ] Render loot entities on space map (gold `*`)
- [ ] Implement `open_loot_pickup(ctx, entity)` modal
- [ ] Wire bump + loot entity → open loot pickup
- [ ] Run audit + smoke

**PLAYTEST** — Engage a pirate squad in combat. Destroy a ship. Verify gold `*` entities appear in space near the wreck. Bump one → loot modal opens. Select items → they appear in cargo. Verify cargo capacity check works (can't take more than free space).

### Phase 6 — Polish

- [ ] Update HUD cargo line to show breakdown (trade / mission / ammo)
- [ ] Balance trade route profits (adjust target stocks, regen rates, neutral-good target formula)
- [ ] Add 2-3 more trade goods for variety
- [ ] Run audit + smoke

**PLAYTEST** — Fly a full trade circuit: Earth → Procyon C → Vega B → Earth. Verify you can make a profit that justifies the fuel cost and travel time. Try the same route with different ships (Scout's 40 cargo vs Hauler's 120). Verify the Hauler's extra cargo space translates to proportionally more profit.

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
