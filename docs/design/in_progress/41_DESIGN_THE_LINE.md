# DESIGN: The Line — the Blockade as a System

**Status: DESIGN IN PROGRESS — no implementation until the user
explicitly requests it.** Second of doc 39's four feature docs,
forked in the agreed order (transponder → the Line → lore/rumor →
far side).

Companions: `39_DESIGN_ACT1_BLOCKADE.md` (the act + its five
methods); `40_DESIGN_TRANSPONDER_ID.md` (the identity layer the
Line reads); `future/37_DESIGN_POST_ACT0_CAMPAIGN.md` (roadmap).

## The ruling this doc serves (user, 2026-09-06)

> Design it right — rock solid. Maybe future acts reuse the tech.
> The Line is a SYSTEM, not a menu: patrol patterns, a scan
> checkpoint, convoy-free traffic, signatures. Methods are ways
> THROUGH the system, discovered by research, enabled by
> preparation, executed and tested.

## What exists today (tested, doc 39)

Four static militia_blockade cruisers (60 hull, heavy laser +
light missiles, one shared squad) at x=150, y=25/55/85/115, detect
7 — a wall with gaps (y 33-47, 63-77, 93-107 + both map edges).
Warning-only comms. The restricted-sector marker east of the wall.
No crossing logic anywhere.

## First-pass shape (for review)

**The sensor line.** The wall becomes edge-to-edge detection with
no free geometric gaps — the Line's defining property. Detection
triggers THE hail: identify yourself. Every crossing resolution
flows through one checkpoint encounter with one rules table:

| The sweep reads | Result |
|---|---|
| Manifest trait (papers) | Waved through, logged |
| Militia ID at blockade rank+ (impersonation) | Waved through, logged AS that ID |
| Dark hull (no broadcast) | Never hailed — but patrols that physically spot it challenge; the ghost run lives here |
| Valid service-run listing (the bribe) | Waved through as cargo/contractor |
| Anything else / defies the warning | Turn back — or the whole Line converges (method 5) |

**One combat response, everywhere.** Dark players ignoring the
challenge, unplanned runners, fight-seekers — all arrive at the
same convergence: the picket squad + system patrols, tuned to the
30-floor contract (provably unwinnable below 30, significant at
it). No per-method variants.

**The manifest registry** is data: the checkpoint reads one trait
(`blockade_manifest`) + the transponder state (doc 40). The Line
itself knows nothing about HOW you got legitimate — the methods
stay decoupled from the wall.

**Reusability.** The checkpoint (read → resolve → converge) is a
pattern: future acts' quarantines, customs lines, faction
checkpoints all reuse it. The Line is the first instance, not a
one-off.

## Open questions (the review agenda)

1. Simulation scope: how live are the patrols? (Authored picket +
   routine patrol movement — today's move_npcs — vs. scheduled
   rotations the player can learn, feeding dark's timing and the
   rumor system's schedule-finds.)
2. What does crossing UNLOCK mechanically — the restricted sector
   becomes approachable? A far-side site? How does arrival at the
   east side present?
3. The challenge hail for dark hulls: same comms options as
   today's scan hail (comply = retreat, defy = converge)?
4. Does the Line ever change state — alerts after incidents,
   quiet watches, the maintenance window fiction (or was that
   purely the toll's dead idea)?
5. How much Line state persists (a "heat" on the Line after
   incidents?) vs. fiction-only in v1?
