# DESIGN: Comms RP Expansion

## Status: STUB — deferred from bounty missions design

## Overview

Expand the comms system with dialogue branches, negotiation, and bribe mechanics. Currently comms is a flat list of options (Attack/Trade/Scan/End). This design would add multi-turn dialogue with NPC ships, bribe/negotiation flows, and faction reputation impacts.

## Key features (sketched)

- **Bribe mechanic**: When hailing a bounty target, a "Negotiate" option appears. The target offers a % of the mission reward to be left alone. Accept → credits awarded, mission auto-fails, faction rep hit with bounty guild. Reject → combat.
- **Multi-turn dialogue**: NPCs respond to player choices with branching flavor text. Not a full dialogue tree engine — just 2-3 turns with state tracked in the modal closure.
- **Faction reputation impacts**: Killing targets vs. taking bribes vs. letting them go all affect faction standing with bounty guild, pirates, and militia.
- **Bounty hunters come after YOU**: If you take too many bribes, the bounty guild puts a price on your head. Bounty hunter NPCs spawn and hunt you in space.

## When to revisit

After bounty missions (DESIGN_BOUNTY_MISSIONS.md) is complete and the bounty gameplay loop feels solid. The bribe mechanic needs the bounty mission lifecycle to be stable first.

## Contracts compliance (MANDATORY — see knowledge.md)

- [ ] **Save/load:** New dialogue state → added to both `_ctx_to_dict()` AND `load_game()`
- [ ] **Game guide:** New comms options (bribe, multi-turn dialogue) → updated `_GUIDE_NPCS` and `_GUIDE_CONTROLS`
- [ ] **Module-level state:** No new module-level globals expected

## Open questions

1. Should bribe amounts be a % of mission reward (simple) or rolled independently (more varied)?
2. Should taking a bribe be a one-time "fail mission, get credits" or a multi-step negotiation?
3. Should faction reputation be visible to the player, or hidden/internal?
4. How does the player know a bounty hunter is hunting THEM vs. just another pirate spawn?
