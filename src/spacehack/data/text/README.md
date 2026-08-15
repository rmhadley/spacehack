# Editable story text (runtime overlay)

The game's main-quest story text lives in the JSON files in this
directory. The game loads them at startup and overrides the Python
defaults with whatever is here — edit a string, relaunch (or press
**F5** when `SPACEHACK_DEV` is set), and the change is in-game.
No code edits, no sync step.

## Keys

| Key | Shows up as |
|---|---|
| `step.<id>.title` | Quest-log step title |
| `step.<id>.description` | Quest-log objective text (L) |
| `step.<id>.dialogue.<npc>.intro` | NPC talk while the step is on offer |
| `step.<id>.dialogue.<npc>.active` | NPC talk while the step is in progress |
| `step.<id>.dialogue.<npc>.complete` | NPC talk after the step is done |
| `step.<id>.dialogue.<npc>.locked` | NPC talk when another faction was chosen |
| `step.<id>.dialogue.<npc>.option_label` | The quest menu row in the talk modal |
| `npc.<id>.flavor_text` | NPC idle chatter when no quest is live |
| `runtime.<name>` | Overlay text: transmissions, log lines, popups (file `00_runtime.json`) |
| `disclosure.<key>.<field>` | Orbit archive-disclosure choices (file `06_end.json`) |

## Rules

- **Delete a key** to fall back to the shipped default text.
- Set a value to `""` to blank a line intentionally.
- `{placeholders}` like `{good}`, `{faction}`, `{max}` are filled in by the game — keep them verbatim.
- In `00_runtime.json`, `\n` inside a string becomes a line break in-game.
- JSON is strict: no trailing commas, no comments.

## Regenerating the baseline

These files are generated from the Python data. Run
`python3 tools/extract_act0_text.py` ONLY when new story content lands
in the code — it overwrites everything. Writer edits live here.
