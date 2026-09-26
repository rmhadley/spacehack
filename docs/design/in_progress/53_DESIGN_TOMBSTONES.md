# DESIGN: Tombstones — death review files

**Status: DRAFT for review (2026-09-26) — proposed from the tuning
sessions; nothing implemented.**

## Overview

On every player death, the game writes a **tombstone** to disk: a
plain-text morgue file carrying the character, the kit, the
circumstances, and the **message log in full** — the roguelike
standard (DCSS morgue files, NetHack tombstones). Deaths are about to
get more informative as balance tightens (the doc-50 era: rifleman
coin-flips, brute one-shots, splash suicides); the tombstone turns
each death into a reviewable autopsy for the player — and a tuning
datum for the designer ("what actually killed people, wearing what").

User framing (2026-09-26): "now that the game is getting difficult as
we balance things, it needs a way to review how you died. usually in a
roguelike it saves a tombstone to disk with your message log in full."

## Proposed contents (v1 — tight)

```
================================================
  REST IN PEACE — <name>, <species> <class>
  Level <L> — died <YYYY-MM-DD HH:MM> (real time)
  <turn/day clock> — <map name / system+planet>
  Slain by: <killer line — the last hostile damage
            source, e.g. "a Pirate Rifleman's laser
            rifle"> / <non-combat cause>
================================================

  THE SHEET: pilot skills, ground stats, traits, HP
  THE KIT: both weapon sets (id + quality + loaded
           ammo), armor slots, bandolier state,
           expedition pack
  THE FIGHT: damage taken this session? (v2 maybe)

  --- MESSAGE LOG (full, oldest first) ---
  ... every entry, colours stripped ...
```

## Design decisions (proposed, for review)

1. **Location**: `saves/tombstones/` — beside the autosave
   (the `saves/` tree is already git-ignored and per-install).
   Alternative considered: `~/.spacehack/tombstones/` with the
   config; rejected for v1 because tombstones are playthrough
   artifacts, not settings, and discoverability next to the save is
   better.
2. **Naming**: `tombstone-<YYYYMMDD>-<HHMMSS>.txt` (monotonic,
   collision-free); the character name is inside the file, not the
   filename (names can contain spaces/punctuation).
3. **Format**: plain UTF-8 text, sections, log verbatim with colour
   runs stripped (the log carries `(text, colour-runs)` — text is
   authoritative, the tombstone takes the text).
4. **The killer line**: derived from the death path — combat deaths
   carry the last damaging enemy's name + weapon (the log already
   ends with the killing sequence; the header line is a summary).
5. **Write timing**: at death finalization, BEFORE autosave deletion
   (the ground/space DEFEAT paths funnel through the shared finish;
   the tombstone writer hooks there). Write failures never block the
   death screen (best-effort, logged to the real console).
6. **Log capacity honesty**: MessageLog is a 200-entry ring — a long
   run's early entries are gone by death. v1 ships the log's full
   CONTENTS (up to 200). Open question 1 proposes the bump.
7. **No in-game browser (v1)**: the files are the surface; any
   review UI is future scope.

## Phases

- [ ] 1. **The tombstone writer** — the module (format + sections +
  log export), the death-path hook (both theaters), file placement,
  tests (format pins, both death paths write, log stripping, killer
  line, failure-is-nonfatal). Brief at refine time.

## Open questions

1. **Log capacity**: raise MessageLog (200 → 500/1000) so tombstones
   capture more of long runs? (Render only shows the tail, so the
   cost is memory-trivial; the risk is nothing.)
2. **Should the death screen mention it?** One line on the existing
   death screen ("A tombstone was written to saves/tombstones/...") —
   UI state copy, not prose; propose yes for discoverability.
3. **Extra sections**: damage-taken-this-session tally, final HP/
   AP state, the map seed (for reproducing the death in the sim) —
   v2 candidates; the seed one is interesting for the balance loop.
