# Missiles: Long-Range Punch + Persistent Ammo

## Overview

Missiles were the weak link of the weapon ladder: Light Missile (10 dmg, 75% acc)
and Heavy Missile (20 dmg, 60% acc) were both worse per-AP than same-tier lasers,
and their only edge was +1-2 range. Worse, the guide claims the EMP Missile
"disables systems" — but no such mechanic exists in the combat engine; it's a
0-damage weapon that deals the 1-damage floor.

The goal: **missiles become long-range, ammo-scarce, big-punch weapons** with a
real ongoing ammo cost, and the EMP missile becomes a genuine shield-stripper.

## Philosophy alignment

| Principle | Adherence |
|-----------|-----------|
| **Data-first** | All new fields live on `WeaponSpec` (`ammo_price`, `shield_strip`); stats are data-only changes |
| **ctx-first** | Persistent ammo lives on `OwnedShip` (reached via `ctx.player_owned_ship`), not globals |
| **Save/load contract** | `OwnedShip.weapon_ammo` dict must serialize + restore; old saves fall back to full magazines |
| **Pure/side-effect split** | Ammo buy-price math is pure (`ammo_buy_cost`); mechanic mutation applies it |
| **Guide contract** | `help.py` weapon table + combat bullets updated |

## Data model changes

### `WeaponSpec` (data/weapons/__init__.py) — two new fields

```python
ammo_price: int = 0      # credits per round of ammo (missiles); 0 = not sold per-round
shield_strip: int = 0    # shields stripped on hit (EMP); 0 = normal damage weapon
```

### New missile stats (data/weapons/missiles.py)

Design: long range, scarce ammo, high per-shot damage, per-round ammo cost.

| Weapon | dmg | acc | AP | pow | ammo | cr/rd | range | ammo_price | price | TL |
|--------|-----|-----|----|-----|------|-------|-------|-----------|-------|-----|
| Light Missile | 14 | 72 | 2 | 0 | 4 | 2 | 2–9 | 8$ | 40$ | 1 |
| Heavy Missile | 28 | 65 | 2 | 0 | 3 | 3 | 3–11 | 20$ | 90$ | 3 |
| EMP Missile | 0 | 75 | 2 | 0 | 2 | 2 | 2–10 | 25$ | 120$ | 4 (shield_strip=20) |

Rationale:
- **Long range**: 2–9 / 3–11 / 2–10 vs lasers' 1–5 and plasma's 1–8. Missiles
  are the only way to open a fight from extreme range; min_range 2-3 means
  point-blank firing eats the min-range accuracy penalty (you must kite).
- **Big punch**: Light 14×72% = 10.1 expected/shot vs Medium Laser 4.32;
  Heavy 28×65% = 18.2 vs Plasma 16.8 — heavier per shot than the same-tier
  energy option, earned because ammo is scarce (4/3/2 rounds).
- **High cost (ammo)**: ammo is now *persistent* (spent rounds stay spent) and
  costs credits to rebuy at the mechanic (8$/20$/25$ per round). Cargo tax also
  rises (2/3/2 cr per round × mag = 8/9/4 cargo permanently reserved).
- **EMP shield-stripper**: 0 hull damage, strips 20 shields per hit (2 rounds =
  40 strip — enough to gut a cruiser's shields). Ignores armor/hull entirely.

## Domain changes

### 1. Persistent ammo on `OwnedShip` (ship.py)

```python
@dataclass
class OwnedShip:
    ...
    weapon_ammo: dict[str, int] = field(default_factory=dict)  # weapon_id -> rounds left
```

- `__post_init__`: seed `weapon_ammo[wid] = ammo_capacity` for missile weapons
  (full magazine on install / buy / load-from-old-save).
- New pure helper `ammo_buy_cost(owned, weapon_id, rounds) -> int` (rounds × ammo_price).
- New mutation helper `_buy_ammo(owned, weapon_id, rounds, stats, log)` — validates
  rounds ≤ capacity−current, deducts credits, increments weapon_ammo, logs.

### 2. Combat consumes persistent ammo (combat/_stats.py, _actions.py, _rules_space.py)

- `init_combat_state`: player's `w_ammo` now reads `owned.weapon_ammo` instead of
  always `ammo_capacity` (enemies keep full mags — they're ephemeral).
- `consume_shot` already decrements `player_state["weapon_ammo"]` per shot —
  unchanged, but `sync_state` (via `_sync_back_hull` path) must now write the
  remaining `weapon_ammo` back to `owned.weapon_ammo` after combat so the spent
  rounds stick.
- `total_ammo_cargo` (ship.py) stays the *maximum* cargo for the loadout
  (used at install); persistent ammo doesn't change the reserved cargo tax.

### 3. Mechanic "Buy Ammo" (menus/_mechanic.py)

- New `_MECH_OPTIONS` entry "Buy Ammo" (after "Manage Loadout").
- Modal lists installed missile weapons with current/max ammo + price/round;
  arrow keys select, ENTER buys a round (or + to buy more), ESC back.
- Empty state (no missiles installed): log "No missile weapons installed."
- Credits/cargo HUD line in the mechanic menu now shows ammo counts.

### 4. EMP shield-strip (combat/_actions.py resolve_damage)

```python
if ws.shield_strip > 0:
    strip = min(ws.shield_strip, target_shields)
    return (0, strip, target_hull, False)   # no hull damage, shields stripped
```
- Must run BEFORE the normal damage path (EMP is slot_type "missile", so it
  never enters the energy path — but the strip check is explicit).
- Log line in `_loop._handle_fire` needs an EMP-aware message ("strips X shields"
  instead of "hits for 0!").

### 5. HUD (hud.py)

- Weapon row for missiles: show `AMMO {current}/{max}` instead of bare count
  (the combat state already carries remaining ammo).

## Phased implementation plan

- [x] Phase 1 — WeaponSpec fields + missile data rebalance
- [x] Phase 2 — Persistent ammo: OwnedShip field, combat init/sync-back, saveload
- [x] Phase 3 — Mechanic "Buy Ammo" modal + ship.py helpers
- [x] Phase 4 — EMP shield-strip in resolve_damage + HUD ammo display
- [x] Phase 5 — Guide updates (help.py)
- [x] Smoke test + review, then commits per phase

## Implementation notes (post-phase)

- **EMP is symmetrical**: enemy AI fire goes through the same
  ``resolve_damage`` shield-strip path, so any enemy carrying an EMP
  will strip the player's shields too (no enemy currently does).
- **Enemy magazines**: enemies still seed full ammo per encounter
  (``_stats.init_combat_state``) — they're ephemeral spawns.
- **Buy Ammo modal**: ENTER buys 1 round, SPACE fills to capacity,
  ESC backs out. Empty state logs "No missile weapons installed."
- **HUD**: missile rows now show ``AMMO 3/4`` instead of a bare count.

## Playtest checklist

- [ ] Buy Light Missile on Earth, launch, engage pirate — missile hits hard from
      range 2-9; after 4 shots it's dry
- [ ] Land, mechanic → Buy Ammo — rounds refill at 8$/rd, credits deducted
- [ ] Save & Continue — ammo count survives (persistent ammo save/load contract)
- [ ] Equip EMP Missile vs a shielded militia cruiser — hull damage 0, shields
      drop 20/hit, no "hits for 0!" log
- [ ] Missile at point-blank (inside min_range) — accuracy penalty applies

## Open questions

- Should enemies also track persistent ammo? (No — they're per-encounter spawns;
  full mags keep AI simple.)
