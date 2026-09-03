# DESIGN: Space Combat Behaviors (deferred — needs design iteration)

> Seeded 2026-09-03 from the Wolf 359 b playtest discussion. The ground
> combat principle — **tactics come from the behavior × attack × terrain
> matrix, not stats** — validated hard (frost-spitter LOS-baiting vs
> melee AP-math corridors). User direction: "can ship combat benefit
> from something similar? right now ship combat is mostly about
> balancing AP/Energy/Ammo." This doc is the FIRST-PASS analysis;
> **the behavior set, counters, and pacing need hard thinking and
> iteration before implementation.**

## Current state (verified in code, 2026-09-03)

- **One universal enemy AI** (`combat/_ai.py::_run_enemy_turn`): close
  to `ai_preferred_range` (scalar 0–4 on `NpcShipSpec`), keep LOS,
  shoot. No behavior *type* — every ship plays identically except
  that number. Space combat is a resource ledger because the enemy
  has no learnable verb.
- **LOS terrain already exists**: `_has_los` respects the map, and
  planets/stations block fire. Ducking behind a planet makes the AI
  advance to re-acquire — the ground LOS-bait likely works in space
  TODAY, untaught and unrewarded (fights rarely start near cover).
  **PLAYTEST VERIFICATION PENDING.**
- **Attack asymmetry exists in data**: lasers (energy) vs missiles
  (ammo, longer range) — nothing makes enemy loadouts express it.

## Proposed matrix (first pass — iterate before building)

| Axis | Ground precedent | Space candidate |
|---|---|---|
| Behavior | hunter / guard / ambusher | kiter (retreats when closed on) · brawler (range 1, high AP) · artillery (holds position, fires on LOS) · swarm-flanker (later) |
| Attack | melee vs ranged | laser (energy, instant) vs missile (ammo, range) — behaviors PREFER one |
| Terrain | corridors / ice / LOS breaks | planet & station shadows (exists) · asteroid clusters (NEW terrain — only if shadows prove too rare) |

Emergent counters to verify in iteration: kiter → corner against map
edge or cut through a planet's shadow; brawler → kite + cover; artillery
→ mandatory LOS-bait. Each should feel like learning the enemy, per
the ground standard.

## Design questions to think hard about (the user's explicit ask)

1. **Does AP-kiting break?** Ground's counters work because enemies
   have small AP budgets. Space ships may have the movement AP to
   negate range bands — a kiter with 6 AP simply stays away forever.
   Band maintenance may need AP economics tuned per behavior, or
   retreat costs (disengage limits per turn).
2. **Player-side symmetry.** Should the player have counters that are
   tactical (terrain use, weapon choice) rather than loadout-only?
   If every counter is "buy missiles," that's stats, not tactics.
3. **Escorts/stations vs duels.** Artillery makes sense defending
   something (convoys, the blockade). Does the behavior set need
   multi-enemy coordination (guard escorts a kiter), or do solo verbs
   compose well enough on their own?
4. **Where terrain comes from.** If planet shadows are the only cover,
   encounters must SPAWN near planets to matter. That's encounter
   placement work (npc_ships spawn logic), possibly bigger than the
   AI itself. Asteroids are a cleaner answer but a new map feature.
5. **Missile travel/interception?** If missiles become interceptable
   or dodgeable (evade already exists), kiter duels gain a skill
   verb. Risk: scope creep; needs its own pass.
6. **Difficulty curve vs ground.** Player fights both modes with one
   character. Space behaviors should not front-load difficulty the
   ground track hasn't taught (the assault-drone lesson).

## Implementation sketch (when the design settles)

- `NpcShipSpec.ai_behavior: str = "hunter"` (default = current loop,
  zero regression) + a policy table in `_run_enemy_turn` — the
  ground registry pattern (`combat/handlers.py`) applied to AI.
- Encounter placement: guarantee cover near behavior-carrying spawns.
- Tests: each behavior's band maintenance / hold / retreat predicate
  as pure functions; regression that default ships fight identically.

## Phases (fill in after design iteration)

- [ ] Design iteration: answers to Q1–Q6, behavior shortlist
- [ ] Phase 1: `ai_behavior` field + hunter default (pure refactor)
- [ ] Phase 2: two contrasting verbs (kiter + brawler?) on existing
      pirate specs; playtest counters emerge?
- [ ] Phase 3: artillery + escort coordination (if Q3 says yes)
- [ ] Phase 4: terrain/encounter placement work (Q4 answer)
