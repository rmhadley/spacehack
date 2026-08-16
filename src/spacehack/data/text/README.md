# Editable story text (runtime overlay)

The game's story text lives in the JSON files in this directory. Edit a
string, relaunch (or press **F5** when `SPACEHACK_DEV` is set), and the
change is in-game. No code edits, no sync step.

There are two tiers:

- **`step.*` (main-quest steps + dialogue) — JSON is the single source
  of truth.** Titles, descriptions, completion flavor, and dialogue text
  are authored *only* here. A step missing its `title` (or its
  `description`, unless the step is marked descriptionless) fails the
  build loudly instead of rendering blank text.
- **`npc.*` / `good.*` / `runtime.*` / `disclosure.*` — JSON overrides
  the Python default.** Delete one of these keys to fall back to the
  shipped default.

## Keys

| Key | Shows up as |
|---|---|
| `step.<id>.title` | Quest-log step title |
| `step.<id>.description` | Quest-log objective text (L) |
| `step.<id>.completion_flavor` | Completion log line + wait-gate popup + waiting breadcrumb |
| `step.<id>.ready_message` | The "INCOMING MESSAGE" summon when a wait gate elapses |
| `step.<id>.dialogue.<npc>.intro` | NPC talk while the step is on offer |
| `step.<id>.dialogue.<npc>.active` | NPC talk while the step is in progress |
| `step.<id>.dialogue.<npc>.complete` | NPC talk after the step is done |
| `step.<id>.dialogue.<npc>.locked` | NPC talk when another faction was chosen |
| `step.<id>.dialogue.<npc>.option_label` | The quest menu row in the talk modal |
| `npc.<id>.flavor_text` | NPC idle chatter when no quest is live |
| `runtime.<name>` | Overlay text: transmissions, log lines, popups (file `00_runtime.json`) |
| `disclosure.<key>.<field>` | Orbit archive-disclosure choices (file `06_end.json`) |
| `good.<id>.name` | Trade-good display name (inventory, trade, loot, quest log) |
| `good.<id>.description` | Trade-good tooltip blurb (file `07_goods.json`) |

## Rules

- `step.<id>.title` and `step.<id>.description` are required — the game
  refuses to start without them. Deleting any other `step.*` key removes
  that line/variant; there is no fallback prose to surface.
- For `npc.*` / `good.*` / `runtime.*` / `disclosure.*`, **delete a key**
  to fall back to the shipped default text.
- `{placeholders}` like `{good}`, `{faction}`, `{max}` are filled in by
  the game — keep them verbatim.
- In `00_runtime.json`, `\n` inside a string becomes a line break
  in-game.
- JSON is strict: no trailing commas, no comments.

## Syncing the files

Run `python3 tools/extract_act0_text.py` when steps, dialogue NPCs,
NPCs, or goods are added to or removed from the code. It keeps every
value here (writer edits always win), prunes keys for structure that no
longer exists, and scaffolds empty `title`/`description` keys for new
steps so the build check points at them. It never overwrites a writer
edit.
