# DESIGN: Flee — the world's exits work during combat

**Status: DRAFT for review (2026-09-26) — rulings captured in
conversation; nothing implemented.**

## Overview

Combat gets a flee mechanic by unlocking the world's existing exits
rather than adding a new action: **landing on planets and jumping
through gates during space combat, using stairs during ground
combat.** No "flee" button, no special-case mechanic — the exits are
always the exits. The risk is the **reaction volley**: everything that
could hit you right now gets one parting shot as you go.

User rulings (2026-09-26, conversation):

> "I've finally thought of a way to 'flee' during space combat:
> allow landing on planets/using jump points while in combat."

> (1) adjacent escape allowed; (2) landing/jumping already resets
> the map — clean exit; (3) cost is fine (fuel/time); (4) no chase
> through jumps; (5) ground combat gets stair dancing.

> "to add some risk to it. anything in range gets 1 AP worth of
> reaction time to react"

> "yes. the reaction shots can kill you. that's the risk. dcss works
> this way."

## The mechanic (uniform, both theaters)

### Space: land or jump while in combat

- The planet-approach menu and jump-gate bump fire from inside the
  combat loop — same interaction, same prompts, no combat-state gate
  blocking them.
- **Adjacent escape is allowed**: you can trigger the exit with
  hostiles at point-blank range. No disengage requirement.
- **Map reset = clean exit**: landing/jumping regenerates the space
  map (existing behavior); the pirate vanishes with it. No chase, no
  memory, no waiting hostile at the destination.
- **Cost is existing**: jumps burn 10 fuel; landing puts you on a
  surface where you must lift off through the same space. The
  economic pressure is already tuned.

### Ground: stair dancing during combat

- The stairs tile fires its floor transition from inside the combat
  loop — bump the stairs during a fight, spend the AP to step
  through, the fight ends, the transition runs.
- **The fight ends at the stairs**, not at VICTORY/DEFEAT: survivors
  on the exited floor revert to patrol (locks released, combat state
  cleaned up). The delve attrition economy keeps its wounds — you
  arrive on the next floor at whatever HP you fled with.
- Uses the existing stairs/exit machinery — no new interaction, no
  new UI.

### The reaction volley (the risk)

- **When an exit is triggered during combat, every enemy that could
  hit you right now gets one attack.** In range + LOS, one shot or
  swing each, then you're out.
  - Space: every hostile ship in weapons range fires once.
  - Ground: every enemy in range and LOS attacks once.
- **Reaction shots CAN KILL.** Death on the stairs or at the gate is
  the gamble — fleeing at low HP from multiple adjacent enemies is a
  coin flip on their damage rolls. "I fled with 8 HP into three
  parting shots" is a story, not a gotcha (user ruling, DCSS
  precedent).
- No movement in the reaction — enemies don't chase or reposition,
  they just get their parting shot from where they stand.
- Clean calculation: the player can see who's in range and roughly
  what they'll dish out before committing to the exit.

## Design intent

- **Fleeing is a decision, not a bail-out.** Without the reaction
  volley, "am I losing? press the exit" collapses the decision.
  With it, the calculation is "can I afford what the room will dish
  out in one volley?"
- **Surrounding is the punishment.** One enemy at range = one
  parting shot = usually fine. Three adjacent = three hits = the
  real cost of getting flanked. Teaches the same lesson as the
  shotgun rifleman: don't get surrounded.
- **The delve economy gets a pressure valve.** Stair dancing lets
  you skip a guardian you can't fight, at the cost of the XP/loot
  and the wounds you carry down. It makes delve depth a choice
  rather than a commitment.
- **No new machinery.** Landing, jumping, stairs, enemy fire — all
  existing. The only new code is the unlock (exits fire from inside
  combat) and the volley (one filtered round of enemy attacks).

## Phases

- [ ] 1. **Space flee** — unlock landing + jump interactions from
  inside the space combat loop; the reaction volley (every hostile
  in range fires once before the transition); the volley CAN kill.
- [ ] 2. **Ground stair dancing** — the stairs tile fires its
  transition from inside the ground combat loop; combat cleanup on
  exit (locks released, survivors revert to patrol); the reaction
  volley (every enemy in range + LOS attacks once); death on the
  stairs.

Each phase gets its Implementation brief at its own refine time.

## Open questions

1. **Volley ordering in space**: does the volley happen before or
   after the confirm prompt? (Lean: after confirm — you commit, then
   they shoot, then the transition runs. You see the damage before
   the map changes.)
2. **Does the volley break the exit?** If the reaction shots would
   kill you, does the exit still fire (you die at the threshold) or
   does death cancel the transition? (Lean: death wins — you never
   make it through. DCSS behavior.)
3. **Boarding interiors**: can you stair-dance out of a boarded
   hull? (Lean: yes — the stairs up are the hull's exit, same rule.)
4. **Does the tutorial need to teach this?** (Lean: no — it's
   discoverable, and the guide can mention it in one line.)
