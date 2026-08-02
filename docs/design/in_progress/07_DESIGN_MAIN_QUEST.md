# DESIGN: Main Quest Storyline

## Overview

A **non-linear main quest** the player follows alongside sandbox play. Builds toward the blockade at Luyten's Star and what lies beyond: research the anomaly, find a way past the blockade, and discover the truth — a warning that has been broadcasting for a thousand years.

**The premise is a blend of alien mystery and faction politics.** The signal from beyond the blockade is real, ancient, and non-human. But the *story* the player experiences is driven by what the four factions want to do with that discovery — and the player's choices decide who wins.

## Design decisions (locked with the user)

| Decision | Choice |
|----------|--------|
| **Core premise** | Alien mystery as the outer frame; faction politics as the engine. Each faction wants the discovery for its own reasons. Player choices decide who wins. |
| **Pacing** | Hybrid: main-quest breadcrumbs are visible in the quest log, but mysteries and faction quests are *dig content* — the player finds them by exploring and talking to the right people. |
| **Ending** | Definitive resolution at the end of Act 3 (a real conclusion), then the sandbox continues. |
| **Time pressure** | None. No deadlines, no fail states. The quest waits forever. |

### Existing story hooks

- **Blockade Officer** at Luyten's Star: "This is the line. Past Luyten's Star is uncharted space — no patrols, no beacons, no backup. Turn back while you still can."
- **Research Officers** at 5+ science stations (Mercury, Sirius, Alpha Centauri, Procyon C, AC Planet 2)
- **Vega's hidden Sol Gate**: commented in `data/solar_systems/vega.py` — a story-side shortcut
- **The Science Port** at Alpha Centauri (near Proxima) — lab building with research officer
- **Luyten's Star blockade**: the frontier — what lies beyond?
- **Depot Attendant** flavor: "The deep-space run is long — make sure your tanks are topped."

### Design goals

- Discovery-driven, but with enough breadcrumb so the player is never lost
- Mysteries + special quests that the player must *dig* for (talk to the right NPC, fly to the odd place)
- No fail states, no time pressure — story adapts to player choices, never expires
- Replayable: species/class combos + faction allegiances see different angles and endings
- Definitive ending with a real payoff; sandbox continues afterward
- 3-path blockade breach: diplomatic / smuggler / combat

## Faction politics — the engine of the story

Each faction believes the signal is something different, and each wants the player to serve their version. This is the *politics* layer: the alien mystery is the same for everyone, but the factions' competing claims turn it into a story about people.

| Faction | Believes the signal is… | Wants | How they help the player | If they "win" the discovery |
|---------|------------------------|-------|--------------------------|------------------------------|
| **Militia** | A threat beacon. Something is out there and the frontier must be held. | To quarantine it, keep it secret, keep order. | Blockade clearance (diplomatic path). Intel on the "incident." | Ending: the frontier is sealed; the threat is "contained." |
| **Merchants** | The next frontier. Alien tech is the biggest trade route in history. | To exploit it, open the route. | Funding, modules, ship discounts, intel. | Ending: a new trade route opens; the structure is quietly mined for tech. |
| **Bar / pirates** | The motherlode. The militia is just hoarding it. | To plunder it before anyone locks it down. | The back route (smuggler path). Partial intel. | Ending: the structure is stripped; the warning is lost/buried. |
| **Lab / civilians** | The truth. It must be understood before anyone does anything stupid. | To study it, publish it, warn humanity. | The research trail itself — every Research Officer. | Ending: the truth is published; humanity hears the warning. |

The player is never forced to pick a side. They can serve one faction, play all four against each other, or go it alone. The **ending epilogue** reflects who (if anyone) backed the player through the blockade.

## Mysteries & dig content

Main-quest breadcrumbs are visible in the quest log. These mysteries are **not** — the player finds them by digging: talking to the right NPC, flying to the odd system, boarding the strange derelict.

| # | Mystery | How to find it | Payoff |
|---|---------|----------------|--------|
| M1 | **The Jamming** — the signal has been jammed for six months. By whom? | Find a classified militia comms log (derelict, lab terminal, or a trusted captain). | Reveals the militia already knew something was out there — since "the incident." |
| M2 | **The Lost Scouts** — three militia scouts vanished beyond the Line. | Salvage the one derelict still drifting near the frontier (boarding + black box). | The scouts saw the structure. Their black box names it. |
| M3 | **The Vega Gate** — decommissioned decades ago, officially. Still in use. | Fly to Vega's hidden gate (per `vega.py` comment). | A way past the blockade that isn't the Line. |
| M4 | **The Lost Expedition** — a merchant-funded science crew went beyond. Its last transmission mentioned "a door that opens on a cycle." | Unlock via merchant faction questline. | Seeds Act 3's truth: the structure opens on a cycle. |

## Quest-aware NPC dialogue system

### The problem

Currently NPC talk (`npc.py`) shows a static `npc.flavor_text` string and a fixed menu (deliver / work). The main quest needs NPCs that:
- Check `ctx.main_quest_progress` and show different dialogue based on current step
- Reveal new options when certain quest steps are active
- Trigger step advancement on conversation
- Show multi-line dialogue trees, not just one flavor text

### How it works

Quest dialogue lives **on the step**, keyed by NPC id (see `MainQuestStep.dialogues` below). When the player talks to an NPC, the system scans the player's quest progress and finds the first step that has a `QuestDialogue` entry for that NPC. The entry overrides the NPC's `flavor_text` based on quest progress.

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
- `main_quest_path: str = ""` — which blockade path was taken (`"diplomatic"` / `"smuggler"` / `"combat"` / `""`), read by the Act 3 epilogue
- `main_quest_backing: set[str]` — faction claim flags planted by backing quests (see Act 3 epilogue resolution)
- `main_quest_complete: bool = False` — set when Act 3 resolves (definitive ending; sandbox continues)

### New fields on `PlanetSpec`
- `main_quest_flavor: str = ""` — lore line shown on landing

## Story outline (3 acts)

### Act 0: Prologue — "First Flight"

| Step | Trigger | Giver | Description |
|------|---------|-------|-------------|
| `prologue_launch` | Auto on first launch | None | Garbled transmission on an unknown frequency — "…they opened it. The door is…" static, "…this is the last warning…" cut off. The player is the only one who seems to have heard it. |
| `prologue_sol` | Talk to Guild Master, Barkeep, or Captain on Earth | Any of the three | **Breadcrumb** (but each giver shows a DIFFERENT read, seeding the faction fork early): Barkeep: "Half the port says it's militia jamming. The other half says what they're jamming is real." Guild Master: "A signal past the Line? There are people who would pay a fortune for proof." Captain (militia): "There is no signal. Fly safe." |

**Reward:** None (sets the hook + plants the faction choice).

### Act 1: "The Anomaly"

Visit Research Officers at science stations to piece together what the signal is. The research trail is the **breadcrumb**; the faction quests and mysteries are the **dig** content that opens alongside it.

| Step | Trigger | Giver | Description |
|------|---------|-------|-------------|
| `research_alpha` | Talk to Research Officer at Alpha Centauri Science Port | Research Officer | "The signal isn't human. The encryption is too clean, too old. Take this datacube to Sirius for analysis." |
| `research_sirius` | Deliver datacube to Sirius Research Officer | Research Officer (Sirius) | "Confirmed. The signal originates beyond Luyten's Star. The blockade officer won't let anyone through — but Vega's old gate is still active." |
| `research_mercury` | Talk to Research Officer on Mercury | Research Officer (Mercury) | "Vega's gate was decommissioned decades ago — officially. Our scans show it's still in use." |
| `research_procyon` | Talk to Research Officer on Procyon C | Research Officer (Procyon) | "To get through, you'll need the nav key. It's in the blockade commander's safe at Luyten's Star." |

**Alongside the trail (dig content, not in the quest log):**
- **Faction backing (v1 depth: militia + merchants get full questlines; bar + lab are dialogue-only):**
  - Militia (full questline): patrol duty → earns trust → unlocks the diplomatic blockade path + plants a militia claim. Includes the classified comms log (M1).
  - Merchants (full questline): supply run → the Lost Expedition (M4) → unlocks intel on the structure + plants a merchant claim.
  - Bar (dialogue-only): the barkeep offers the smuggler path + plants a bar claim if taken (no separate questline).
  - Lab (dialogue-only): completing the research trail plants a lab claim when the player reports back to any Research Officer (no separate questline).
- **M1 The Jamming** (classified militia comms log, from the militia questline or a lab terminal) — reveals the militia knew about "the incident" six months ago.
- **M2 The Lost Scouts** (salvage derelict + black box) — the scouts saw the structure and named it.
- **M3 The Vega Gate** (dialogue hint from the Mercury officer; fly there to activate) — a way past the blockade that isn't the Line.

**Reward:** Credits, XP, lab faction rep, and the faction-politics fork.

**Choice fork:** Diplomatic (build militia rep to Allied), Smuggler (pay the barkeep at Luyten), Combat (fight through). The chosen path is recorded in `ctx.main_quest_path` and shapes the Act 3 epilogue.

### Act 2: "The Blockade"

| Step | Trigger | Giver | Description |
|------|---------|-------|-------------|
| `blockade_diplomatic` | Talk to Blockade Officer (militia rep >= 76) | Blockade Officer | "Cleared for passage. Whatever's out there, you represent the Line now. The gate beyond has been active for six months. We've lost three scouts." |
| `blockade_smuggler` | Visit bar at Luyten's Star (rep < 76) | Barkeep | "There's a back route through an old debris field. Risky. Costs credits + hull damage." |
| `blockade_combat` | Defeat the blockade in combat | None (auto) | "Blockade Nav Key" drops from the commanding officer's ship. |

**Reward:** Nav key or clearance → unlocks uncharted system beyond Luyten's Star. The blockade path plants its own claim (diplomatic → militia, smuggler → pirates, combat → none).

### Act 3: "The Warning"

A dead-star system with an alien structure — the source of the signal.

| Step | Trigger | Giver | Description |
|------|---------|-------|-------------|
| `beyond_arrival` | Enter uncharted system | None (auto) | "The signal is here. A massive alien structure orbits the dead star at the system's heart." |
| `beyond_exploration` | Approach the structure | None (auto) | "Scans show it's dormant — but something inside is still active. A door that opens on a cycle." |
| `beyond_core` | Board the structure (special encounter) | None | Gauntlet inside: combat with alien constructs ("Ancient Sentinel"). At the core: a data beacon containing the full message — the structure is a **seal**, not a beacon. The signal is the lock failing. Something is trying to come through, and it has been pressing for a thousand years. The builders sealed it knowing the seal would eventually break — and left the warning so someone would be ready. The cycle is ending: the seal is failing now. |
| `beyond_finale` | Survive the gauntlet | None (auto) | The message is delivered. The seal holds — for now — and the structure goes dark, its warning delivered. The player returns through the now-open frontier — the first human to stand there and come back. |

**Reward:** "Alien Resonator" ship module (unique, powerful). Massive XP. The truth. `main_quest_complete = True` — sandbox continues.

**Epilogue resolution — "last claim wins":** Each faction backing quest (Phase 3) plants a claim flag in `ctx.main_quest_backing`; the blockade path plants its own claim (diplomatic → militia, smuggler → pirates, combat → none). At the finale, the **most recently planted claim** wins — so every faction can win, and the player who serves multiple factions gets the ending of whoever they helped last. If no claims were planted, the player goes alone.

**Lab-ending trigger (explicit):** the research trail completes *before* the blockade, so its lab claim is planted early and gets superseded by any later diplomatic/smuggler claim. The lab ending therefore fires via the combat path: **combat path + research complete → lab ending** (the truth-teller publishes it); **combat path + no research → alone** (the player keeps the secret). This is intentional — the "truth-teller goes alone" pairing — and an implementer should not expect the lab ending to be freely reachable.

- Militia claim: the frontier is sealed; the threat is "contained." The militia thanks the player, quietly.
- Merchant claim: a new trade route opens; the structure is quietly mined for tech. The Guild Master offers the player a share.
- Pirate/bar claim: the structure is stripped; the warning is buried in a bar story. The Barkeep raises a glass.
- Lab claim: the truth is published; humanity hears the warning. The Research Officers study the data beacon openly.
- Alone (no claim): the player keeps the secret. The frontier stays open and wild.

## Implementation phases

### Phase 1: Data model + Prologue

- [ ] Add `MainQuestStep` dataclass to `data/main_quest/` module
- [ ] Add `main_quest_progress`, `main_quest_unlocked_items`, `main_quest_path`, `main_quest_complete` to `GameContext`
- [ ] Write Act 0 steps as data
- [ ] Wire prologue auto-trigger into `_launch_to_space` (first launch only)
- [ ] Wire prologue NPC dialogue into guild master, barkeep, and militia captain talk modals (3 faction reads)
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

### Phase 3: Mysteries & faction quests (dig content)

- [ ] M1 The Jamming: classified militia comms log findable via the militia questline / a lab terminal
- [ ] M2 The Lost Scouts: salvage derelict with black box near the frontier
- [ ] M3 The Vega Gate: activate the hidden gate in `vega.py`
- [ ] M4 The Lost Expedition: merchant faction questline
- [ ] Militia backing questline (full): patrol duty + comms log
- [ ] Merchant backing questline (full): supply run + Lost Expedition
- [ ] Bar + lab: dialogue-only backing (claims planted by path choice / research completion)
- [ ] Smoke test + commit

### Phase 4: Main quest log UI

- [ ] Add "Main Quest" section to quest log (Q key) — separate from active missions
- [ ] Show status: completed (checkmark), active (highlighted), locked (grayed)
- [ ] Mysteries are NOT listed — only breadcrumb steps
- [ ] Smoke test + commit

### Phase 5: Rewards + unique items + ending

- [ ] Wire rewards_credits / rewards_xp into step completion
- [ ] Wire rewards_rep into `modify_rep`
- [ ] Add "Alien Resonator" module to `data/modules/systems.py`
- [ ] Add "Blockade Nav Key" as a quest item
- [ ] Wire Act 3 epilogue variants by `main_quest_path`
- [ ] Set `main_quest_complete` and confirm sandbox continues
- [ ] Smoke test + commit

### Phase 6: Guide + final polish

- [ ] Add main quest section to in-game guide
- [ ] Full playtest: prologue → research → mysteries → blockade breach → beyond → finale
- [ ] DRY/RNG audit

## Contracts compliance (MANDATORY — see knowledge.md)

- [ ] **Save/load:** `main_quest_progress`, `main_quest_unlocked_items`, `main_quest_path`, `main_quest_complete` → added to both `_ctx_to_dict()` AND `load_game()`
- [ ] **Game guide:** New main quest overlay → updated `_GUIDE_MISSIONS` or new `_GUIDE_MAIN_QUEST` section
- [ ] **NPC spawns:** Alien sentinel ships → registered in `ctx.procedural_spawns` with matching `squad_id`

## Open questions

1. ~~What exactly is the warning?~~ **RESOLVED:** The structure is a seal. The signal is the lock failing — something is trying to come through, and the seal is breaking. The builders left the warning so someone would be ready.
2. ~~Faction questline depth~~ **RESOLVED:** militia + merchants get full backing questlines in v1; bar + lab are dialogue-only backing (claims still reachable via path choice / research completion).
3. **Ending world-state** — should the epilogues change the world (blockade opens, new trade route, structure mined) or stay text-only?
4. **Main quest steps never appear on mission boards** — only triggered by exploration and NPC conversation.
5. **Game continues after Act 3** — the story loop closes, sandbox continues. Confirmed.
6. **No time pressure, no fail states** — the quest waits forever. Confirmed.
