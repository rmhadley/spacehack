# DESIGN: Main Quest Storyline

## Overview

A **non-linear main quest** the player follows alongside sandbox play. Builds toward the blockade at Luyten's Star and what lies beyond: research the anomaly, find a way past the blockade, explore beyond charted space through alien tech, and survive a final battle against an ancient force.

### Existing story hooks

- **Blockade Officer** at Luyten's Star: "This is the line. Past Luyten's Star is uncharted space — no patrols, no beacons, no backup. Turn back while you still can."
- **Research Officers** at 5+ science stations (Mercury, Sirius, Alpha Centauri, Procyon C, AC Planet 2)
- **Vega's hidden Sol Gate**: commented in `data/solar_systems/vega.py` — a story-side shortcut
- **The Science Port** at Alpha Centauri (near Proxima) — lab building with research officer
- **Luyten's Star blockcade**: the frontier — what lies beyond?
- **Depot Attendant** flavor: "The deep-space run is long — make sure your tanks are topped."

### Design goals

- Discovery-driven: quest steps found by exploring and talking to NPCs
- No fail states: story adapts to player choices
- Replayable: different species/class combos see different angles
- 3-path blockade breach: diplomatic / smuggler / combat

## Quest-aware NPC dialogue system

### The problem

Currently NPC talk (`npc.py`) shows a static `npc.flavor_text` string and a fixed menu (deliver / work). The main quest needs NPCs that:
- Check `ctx.main_quest_progress` and show different dialogue based on current step
- Reveal new options when certain quest steps are active
- Trigger step advancement on conversation
- Show multi-line dialogue trees, not just one flavor text

### How it works

Each NPC gets an optional `quest_dialogues` mapping that overrides their `flavor_text` based on quest progress. The mapping is keyed by the quest step ID the dialogue is for.

```python
# NPC has a new field:
quest_dialogues: dict[str, str] = {}  # step_id -> dialogue_line
```

When the player talks to an NPC with quest dialogue configured:

```
1. Look up the highest-priority active quest step for this NPC
2. If a matching quest_dialogue entry exists, use it INSTEAD of flavor_text
3. If no match, fall back to the default flavor_text (NPC is just a regular NPC now)
4. If the step should auto-complete on talk, advance it
```

### Priority order:

1. Active (in-progress) quest step with dialogue for this NPC → show it, maybe advance
2. Available (unstarted) quest step → show it, maybe start it
3. Completed quest step → show "post-completion" dialogue variant
4. Nothing → fall back to `flavor_text`

### Dialogue variants per step

Each quest step can define up to 4 dialogue variants for its NPC:

| Variant | When | Example |
|---------|------|---------|
| `intro` | Step becomes available, first talk | "Heard the transmission? The militias are jamming it." |
| `active` | Step is active (already triggered) | "Find the Research Officer at Alpha Centauri." |
| `complete` | Step is completed (player reports back) | "You're back from Alpha Centauri? What did you learn?" |
| `locked` | Prerequisites not met | "Busy with the signal analysis. Check back later." |

### Data model addition to `MainQuestStep`

```python
@dataclass(frozen=True)
class QuestDialogue:
    npc_id: str
    trigger_on_talk: bool = False          # True = advance step on conversation
    intro: str = ""                         # shown when step becomes available
    active: str = ""                        # shown while step is in progress
    complete: str = ""                      # shown after step is completed
    locked: str = ""                        # shown if prerequisites not met
```

### Integration with existing NPC talk

The existing `render_npc_talk` function in `npc.py` already accepts an `NPC` object. The change is minimal:

1. A new `resolve_npc_dialogue(npc_id, ctx) -> str` function checks quest progress and returns the right dialogue string
2. `render_npc_talk` calls this instead of using `npc.flavor_text` directly
3. The deliver / work options remain — quest dialogue is layered on top, not replacing the menu
4. A new `TalkOutcome.QUEST` option may appear ("Discuss the signal") that triggers step advancement

### Example flow

```
# After first launch, player talks to Earth Guild Master:
# ctx.main_quest_progress = {"prologue_launch": "completed"}
# Guild Master has quest_dialogues for "prologue_sol":
#   intro = "Heard that transmission? Something's happening past Luyten's Star."
#
# NPC talk renders:
#   ┌─────────────────────────────────────────┐
#   │        Guild Master (merchants)          │
#   │                                          │
#   │ "Heard that transmission? Something's    │
#   │  happening past Luyten's Star. You might │
#   │  start at the Science Port near Alpha    │
#   │  Centauri."                              │
#   │                                          │
#   │ > Discuss the signal <                   │
#   │   View available work                    │
#   └─────────────────────────────────────────┘
#
# Player selects "Discuss the signal" -> step "prologue_sol" completes
# ctx.main_quest_progress["prologue_sol"] = "completed"
# ctx.main_quest_progress["research_alpha"] = "available"
```

### Resolve dialogue helper

```python
def resolve_npc_dialogue(ctx: GameContext, npc_id: str) -> tuple[str, str | None]:
    """Return (dialogue_text, trigger_step_id or None) for this NPC.
    
    Scans all defined main quest steps. Returns the first match
    where the NPC has a dialogue entry for the current step state.
    If no match, returns (default_flavor_text, None).
    """
    for step_id, status in ctx.main_quest_progress.items():
        step = find_main_quest_step(step_id)
        dialogue = step.dialogues.get(npc_id)
        if dialogue is None:
            continue
        if status == "available":
            return (dialogue.intro, step_id if dialogue.trigger_on_talk else None)
        if status == "active":
            return (dialogue.active, step_id if dialogue.trigger_on_talk else None)
        if status == "completed":
            if dialogue.complete:
                return (dialogue.complete, None)
    # Fall back to NPC's default flavor_text
    return (find_npc(npc_id).flavor_text, None)
```

## Data model

### New dataclass: `MainQuestStep`

```python
@dataclass(frozen=True)
class QuestDialogue:
    npc_id: str
    trigger_on_talk: bool = False
    intro: str = ""
    active: str = ""
    complete: str = ""
    locked: str = ""

@dataclass(frozen=True)
class MainQuestStep:
    id: str
    title: str
    description: str
    trigger_npc_id: str | None       # which NPC gives this step
    trigger_planet_id: str | None    # which planet / system
    trigger_system_id: str | None
    requires_step: str | None        # must complete this step first
    requires_level: int = 1
    requires_rep: dict[str, int] | None = None
    dialogues: tuple[QuestDialogue, ...] = ()  # per-NPC dialogue overrides
    rewards_credits: int = 0
    rewards_xp: int = 0
    rewards_rep: dict[str, int] | None = None
    rewards_item: str | None = None
```

### New fields on `GameContext`
- `main_quest_progress: dict[str, str]` — step_id → `"available"`, `"active"`, `"completed"`
- `main_quest_unlocked_items: set[str]` — items and dialogue unlocked by quest steps

### New fields on `PlanetSpec`
- `main_quest_flavor: str = ""` — lore line shown on landing

## Story outline (3 acts)

### Act 0: Prologue — "First Flight"

| Step | Trigger | Giver | Description |
|------|---------|-------|-------------|
| `prologue_launch` | Auto on first launch | None | Garbled transmission on an unknown frequency — "The signal from beyond... the gate at Vega... they found something." Cut off. |
| `prologue_sol` | Talk to Guild Master or Barkeep on Earth/Mars | Guild Master / Barkeep | "Something's happening past Luyten's Star. Start at the Science Port near Alpha Centauri — they study this kind of thing." |

**Reward:** None (sets the hook).

### Act 1: "The Anomaly"

Visit Research Officers at science stations to piece together what the signal is.

| Step | Trigger | Giver | Description |
|------|---------|-------|-------------|
| `research_alpha` | Talk to Research Officer at Alpha Centauri Science Port | Research Officer | "The signal isn't human. The encryption is too clean, too old. Take this datacube to Sirius for analysis." |
| `research_sirius` | Deliver datacube to Sirius Research Officer | Research Officer (Sirius) | "Confirmed. The signal originates beyond Luyten's Star. The blockade officer won't let anyone through — but Vega's old gate is still active." |
| `research_mercury` | Talk to Research Officer on Mercury | Research Officer (Mercury) | "Vega's gate was decommissioned decades ago — officially. Our scans show it's still in use." |
| `research_procyon` | Talk to Research Officer on Procyon C | Research Officer (Procyon) | "To get through, you'll need the nav key. It's in the blockade commander's safe at Luyten's Star." |

**Reward:** Credits, XP, lab faction rep.

**Choice fork:** Diplomatic (build militia rep to Allied), Smuggler (pay the barkeep at Luyten), Combat (fight through).

### Act 2: "The Blockade"

| Step | Trigger | Giver | Description |
|------|---------|-------|-------------|
| `blockade_diplomatic` | Talk to Blockade Officer (militia rep >= 76) | Blockade Officer | "Cleared for passage. The gate beyond has been active for six months. We've lost three scouts." |
| `blockade_smuggler` | Visit bar at Luyten's Star (rep < 76) | Barkeep | "There's a back route through an old debris field. Risky. Costs credits + hull damage." |
| `blockade_combat` | Defeat the blockade in combat | None (auto) | "Blockade Nav Key" drops from the commanding officer's ship. |

**Reward:** Nav key or clearance → unlocks uncharted system beyond Luyten's Star.

### Act 3: "Beyond the Chart"

A dead-star system with an alien structure — the source of the signal.

| Step | Trigger | Giver | Description |
|------|---------|-------|-------------|
| `beyond_arrival` | Enter uncharted system | None (auto) | "The signal is here. A massive alien structure orbits the dead star at the system's heart." |
| `beyond_exploration` | Approach the structure | None (auto) | "Scans show it's dormant — but something inside is still active." |
| `beyond_core` | Board the structure (special encounter) | None | Gauntlet inside: combat with alien constructs ("Ancient Sentinel"). At the core: a data beacon containing the full message — a warning about a threat that returns. The cycle is ending. |
| `beyond_finale` | Survive the gauntlet | None (auto) | "The wave breaks against you. The structure goes dark. You are the first human to stand here and return." |

**Reward:** "Alien Resonator" ship module (unique, powerful). Massive XP. The truth.

## Implementation phases

### Phase 1: Data model + Prologue

- [ ] Add `MainQuestStep` dataclass to `data/main_quest/` module
- [ ] Add `main_quest_progress` and `main_quest_unlocked_items` to `GameContext`
- [ ] Write Act 0 steps as data
- [ ] Wire prologue auto-trigger into `_launch_to_space` (first launch only)
- [ ] Wire prologue NPC dialogue into guild master and barkeep talk modals
- [ ] Smoke test + commit

### Phase 2: Acts 1-3 story data

- [ ] Write Acts 1-3 as data (all steps, triggers, rewards)
- [ ] Wire Research Officer conversations as quest step triggers
- [ ] Wire Blockade Officer and Luyten bar as blockade breach triggers
- [ ] Wire uncharted system entry as Act 3 trigger
- [ ] Add "Ancient Sentinel" NpcShipSpec to `data/npc_ships/core.py` (T4+ challenge)
- [ ] Wire `beyond_core` combat gauntlet
- [ ] Add `main_quest_flavor` to key planets
- [ ] Smoke test + commit

### Phase 3: Main quest log UI

- [ ] Add "Main Quest" section to quest log (Q key) — separate from active missions
- [ ] Show status: completed (checkmark), active (highlighted), locked (grayed)
- [ ] Smoke test + commit

### Phase 4: Rewards + unique items

- [ ] Wire rewards_credits / rewards_xp into step completion
- [ ] Wire rewards_rep into `modify_rep`
- [ ] Add "Alien Resonator" module to `data/modules/systems.py`
- [ ] Add "Blockade Nav Key" as a quest item
- [ ] Smoke test + commit

### Phase 5: Guide + final polish

- [ ] Add main quest section to in-game guide
- [ ] Full playtest: prologue → research → blockade breach → beyond → finale
- [ ] DRY/RNG audit

## Open questions

1. **Main quest steps never appear on mission boards** — only triggered by exploration and NPC conversation.
2. **Game continues after Act 3** — the story loop closes, sandbox continues.
3. **"Ancient Sentinel"** is a unique T4+ enemy type — alien tech, no faction, unyielding.
4. **No fail states** — quest stays available regardless of rep or time.

## Story tone

Mystery-driven. The core question is "What is the signal?" The answer unfolds through exploration, not exposition. The player is "the one who went to look" — not a chosen one, just the person who followed the thread.
