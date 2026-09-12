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
| `rumor.<id>.text` | Rumor text — the readout modal and the Q-log Rumors pane (file `08_rumors.json`) |
| `rumor.<id>.topic` | Short askable label — hearing rows and Ask Around topics (file `08_rumors.json`) |
| `rumor.<id>.witness.<npc>` | Per-source delivery override, conversation flavor only; the ledger keeps `rumor.<id>.text` (file `08_rumors.json`) |
| `dig.reveal.title` | Discovered-site readout title (file `09_digs.json`) |
| `dig.reveal.text` | Discovered-site readout body; `{name}` / `{planet}` filled by the game (file `09_digs.json`) |
| `dig.pointer_line` | The site's pointer line in the Q-log Rumors pane; `{name}` / `{planet}` filled by the game (file `09_digs.json`) |

## Rules

- `step.<id>.title` and `step.<id>.description` are required — the game
  refuses to start without them. Deleting any other `step.*` key removes
  that line/variant; there is no fallback prose to surface.
- `rumor.*` keys are single-source like `step.*` — every key the lore
  catalog needs must exist in `08_rumors.json` (and only there);
  `tests/test_rumor_catalog.py` fails loudly on a missing or
  misplaced key.
- `dig.*` keys are single-source like `rumor.*` — every key in
  `spacehack.digs.TEXT_KEYS` must exist in `09_digs.json`; the
  orphan-key test unions that set, so an unclaimed or missing key
  fails loudly.
- For `npc.*` / `good.*` / `runtime.*` / `disclosure.*`, **delete a key**
  to fall back to the shipped default text.
- `{placeholders}` like `{good}`, `{faction}`, `{max}` are filled in by
  the game — keep them verbatim.
- In `00_runtime.json`, `\n` inside a string becomes a line break
  in-game.
- JSON is strict: no trailing commas, no comments.

## Authoring directly

These JSON files are the single authoring surface for story prose
(the code-side extractor was retired — doc 33). When steps, dialogue
NPCs, or goods are added or removed, edit the JSON by hand and let
the checks catch mistakes: `tools/check_main_quest.py` fails on
missing required `title`/`description`, and `tools/quest_lint.py`
reports orphaned keys (structure removed, text left behind). New
`runtime.*` keys also need their NAME (not the prose) in the
`RUNTIME` registry in `src/spacehack/text.py`, which powers the
shipped-keys validation.
