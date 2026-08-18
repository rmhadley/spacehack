# Main-quest authoring guide

This directory contains the structural data for the reusable main quest. A
new chain should normally be a new `STEPS` tuple here plus story text in
`src/spacehack/data/text/`. Runtime code should not need to change.

## Add a chain

1. Create `act<N>_<name>.py` in this directory.
2. Import `MainQuestStep` and `QuestDialogue` from `.`.
3. Export a `STEPS` tuple.
4. Add `__all__ = ["STEPS"]` at the end of the module, matching the existing
   quest catalogs.
5. Give each step a unique `id` and link it with `requires_step`.
6. Set `chain`, `objective_type`, locations, rewards, gates, and any objective
   fields needed by the handler.
7. Add the matching `step.<id>.*` text keys to the appropriate JSON file in
   `src/spacehack/data/text/`.
8. Run `make check`.

Step prose does not belong in the Python catalog. Titles and required
objective descriptions must exist in JSON; optional dialogue, completion
flavor, and summon text are also authored there when used.

A minimal chain looks like this:

```python
from . import MainQuestStep, QuestDialogue

STEPS = (
    MainQuestStep(
        id="cult_q1_lead",
        requires_step="prologue_seek_help",
        chain="cult",
        objective_type="talk",
        trigger_planet_id="earth",
        trigger_system_id="sol",
        dialogues={
            "guild_master": QuestDialogue(
                npc_id="guild_master",
                trigger_on_talk=True,
                backing_faction="cult",
                option_label="Ask about the lead",
            ),
        },
    ),
    MainQuestStep(
        id="cult_q2_relic",
        requires_step="cult_q1_lead",
        chain="cult",
        objective_type="delve",
        trigger_planet_id="mercury",
        trigger_system_id="sol",
        delve_good_ids=(("cult_reliquary", 1),),
    ),
)

__all__ = ["STEPS"]
```

The catalog is auto-discovered. Do not add a central registry entry. Keep the
`__all__` export so the module follows the existing quest-catalog convention.

## Objective types

The current handler table supports:

- `talk` — default dialogue completion
- `goods` — require and consume listed cargo
- `smuggle` — load or hand over mission-hold cargo
- `delve` — secure quest-tagged surface-dungeon loot
- `salvage` — secure quest-tagged derelict loot
- `visit` — recruit or meet a target NPC
- `bounty` — defeat a quest-tagged spawn
- `bump` — complete on a configured bump interaction
- `prison` — complete on the themed prison interaction

Adding a new objective type requires one cohesive handler module/implementation
and one entry in `src/spacehack/main_quest/handlers.py`. The generic dispatch
modules should not gain a new conditional branch.

## Scenes

A step can name a bespoke scene with `scene="scene_id"`. Add the implementation
to `src/spacehack/main_quest/_scenes.py` first, then reference its ID from the
data step. Scene presentation remains code; the trigger belongs in data.

Every scene ID must be registered. The validator reports an unregistered ID.

## Quest NPC presence

For an additive quest NPC:

1. Add or reuse the NPC in `src/spacehack/data/npcs/`.
2. Add a `(npc_id, building_label)` row to the destination planet's
   `quest_npc_spots`.
3. Put `npc_presence=("npc_id",)` on the live step(s).

The NPC is present only while one of those steps is available or active. It
must have a valid catalog entry and a valid guild-building spot.

## Heat and other flags

Use the registered heat tags in `MainQuestStep.heat` rather than adding step
IDs to runtime conditionals. Scene IDs, `auto_load_next_smuggle`, and other
static flags likewise belong on the step. The validator rejects unknown heat
tags.

## Story text

Use the JSON overlay files under `src/spacehack/data/text/`:

- `step.<id>.title`
- `step.<id>.description`
- `step.<id>.dialogue.<npc>.<variant>`
- `step.<id>.completion_flavor`
- `step.<id>.ready_message`
- `runtime.<name>` for non-step popups and logs

Keep placeholders such as `{faction}`, `{credits}`, and `{good}` unchanged.
For new runtime prose, add a default to `src/spacehack/text.py`, then run:

```bash
python3 tools/extract_act0_text.py
```

Writer edits in JSON are preserved by the extractor.

## Validation

`make check` runs `tools/check_main_quest.py`. It rejects unknown objective
handlers, broken prerequisite/unlock references, unknown heat tags,
unregistered scenes, and missing required title/description text. It does not
currently enforce chain termination or reward balance.

For a quick local check without the full suite:

```bash
python3 tools/check_main_quest.py
```
