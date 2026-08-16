# Ground Weapon Balance Pass — explosive utility and hybrid ammunition

> **Status:** Complete. All phases implemented and playtested.
> **Depends on:** [Doc 19 — Ground Ammo and Field Items](../complete/19_DESIGN_GROUND_AMMO_AND_FIELD_ITEMS.md)
> and [Doc 22 — Ground Equipment Expansion](../complete/22_DESIGN_GROUND_EQUIPMENT_EXPANSION.md).

## Goal

Make finite ammunition meaningful without making infinite-ammo weapons feel like
mistakes. Ordinary ammunition is a sustainable expedition resource; rockets are
a scarce tactical resource. Weapon value is evaluated across accuracy, damage,
range, AP cost, magazine pressure, and the two-weapon volley rule (the active
volley pays its maximum weapon AP cost once).

## Explosive rules

- The selected enemy is the impact cell and uses the normal accuracy roll.
- The impact cell takes full post-armor weapon damage.
- Every enemy and the player in the eight neighboring cells takes half damage,
  rounded down with a minimum of 1.
- Explosions have friendly fire: the player can damage themself.
- Player splash damage uses equipped armor defense; enemy splash damage uses the
  enemy's armor. Plasma's armor-halving rule does not apply to explosives.
- One projectile is consumed for the complete blast, and the blast uses one
  weapon AP cost in the existing max-AP volley transaction.
- Every enemy killed by a blast gets the normal removal, loot, XP, and kill
  counter handling. A primary target may survive while a neighboring enemy dies.
- The existing explosive projectile animation remains centered on the selected
  target; this pass changes resolution and feedback, not animation timing.

## Balance direction

Infinite-ammo plasma is the dependable baseline: it should be useful every
fight, but not replace scarce burst tools. Explosives trade accuracy, range
constraints, and ammunition for group damage and tactical positioning.

### Tuned values

| Weapon | Damage | Accuracy | AP | Ammo | Special role |
|---|---:|---:|---:|---:|---|
| Grenade Launcher | 16 | 60% | 2 | 6 | Accessible area burst; 3–7 range |
| Rocket Launcher | 30 | 55% | 3 | 4 | High-impact area burst; 2–9 range; 2 AP reload |
| Plasma Pistol | 8 | 74% | 2 | ∞ | Reliable one-handed armor pressure |
| Plasma Rifle | 14 | 70% | 2 | ∞ | Reliable two-handed generalist |
| Plasma Caster | 21 | 66% | 3 | ∞ | Long-range endgame baseline |
| Laser Carbine | 9 | 76% | 2 | 100 | One-handed sustained-range option |
| Vibroblade | 8 | 80% | 2 | ∞ | High-accuracy melee sidearm |
| Power Fist | 12 | 72% | 2 | ∞ | Heavy melee sidearm |

The remaining kinetic and energy weapons retain their existing common-ammo
roles for this pass. The high-output one-handed weapons above pay enough AP
that pairing them does not create a near-free endgame volley; range and melee
risk remain part of their value.

## Acceptance / playtest checklist

- [x] Fire a Rocket Launcher at one enemy: primary takes full damage and one
      rocket is consumed from the loaded magazine.
- [x] Fire at two adjacent enemies: the selected target takes full damage and
      the neighbor takes half damage, including odd values rounded down to a
      minimum of 1.
- [x] Kill only a neighboring enemy with splash: it is removed, awards XP, and
      drops normal loot; the primary remains engaged.
- [x] Stand adjacent to the impact cell and fire: the player takes half damage.
- [x] Equip armor and repeat friendly fire: player damage reflects armor DR.
- [x] Confirm a missed explosive shot causes no splash damage and still consumes
      the shot/AP according to existing firing behavior.
- [x] Confirm one rocket/grenade is used for the whole blast, not one per target.
- [x] Compare a Rocket Launcher against a Plasma Caster over several fights:
      rockets feel like a scarce group-control decision, while plasma remains
      a dependable single-target fallback.
- [x] Verify Grenade Launcher range and Rocket Launcher minimum range still
      matter, including the existing emergency point-blank penalty.
- [x] Verify dual-wielding the revised one-handed weapons does not produce an
      unexpectedly dominant one-AP volley.
- [x] Save/Continue after firing and reloading explosives; magazines and reserve
      stacks retain exact values.

## Playtest result

Manual playtest passed (2026-08-16): all acceptance items above were verified
in-game, including the Rocket Launcher vs Plasma Caster feel comparison and the
save/continue magazine persistence. `make check` remains green.
