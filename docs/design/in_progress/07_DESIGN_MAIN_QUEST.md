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
# After receiving the transmission, player talks to Earth Guild Master:
# ctx.main_quest_progress = {"prologue_mars_entrance": "completed"}
# Guild Master has quest_dialogues for "prologue_seek_help":
#   intro = "Alien tech on Mars? That's the most valuable cargo in history."
#
# NPC talk renders:
#   ┌─────────────────────────────────────────┐
#   │        Guild Master (merchants)          │
#   │                                          │
#   │ "Alien tech on Mars? That's the most     │
#   │  valuable cargo in history. Bring me     │
#   │  proof it's real."                       │
#   │                                          │
#   │ > Tell me about the door <               │
#   │   View available work                    │
#   └─────────────────────────────────────────┘
#
# Player selects "Tell me about the door" -> step "prologue_seek_help" completes
# ctx.main_quest_progress["prologue_seek_help"] = "completed"
# ctx.main_quest_progress["prologue_open"] = "available"
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

### Act 0: Prologue — "The Door on Mars"

The player receives a garbled transmission while flying through Sol. It points to a location on Mars. They explore Mars, find a sealed entrance to *something*, and can't get it open — then they seek help from NPCs across the sector. Act 0 ends when the player returns with the right knowledge/tools to open it.

**The Mars door is alien tech — the same kind as the Act 3 structure, but dormant.** The Act 3 structure is the *active, failing* seal; the Mars door is a *sealed, dormant* example of the same technology. It won't open with any human tool. This seeds the through-line: the player learns how the seal tech works here, and understands (and resolves) the failing seal at the end of the story. The two must NOT be conflated mechanically — the Mars door opens only with the right tool; the Act 3 structure opens on a cycle (M4's "door that opens on a cycle" refers to the Act 3 structure, not the Mars door).

**Behind the door: an empty ancient alien prison.** Inside are technology beyond any known human tech and a cache of data that needs to be translated and studied. The cell is **empty** — whatever it held is long gone, or was never there, or got out. This is a deliberate ambiguity the Act 3 reveal pays off (is what's pressing on the failing seal the same thing the prison was built to hold?). The recovered data is the **fuel for Act 1's research trail** — the player carries it to the science stations, which is why the Research Officers take the player seriously.

**Opening the door is a faction choice.** The player picks which faction helps them; *how* the door opens changes with that choice (see the table below). Choosing a faction plants that faction's claim early (the first claim — non-binding, "last claim wins" still decides the Act 3 epilogue), and colors how the rest of the story treats the player. Consistent with the rest of the game, no faction ever *refuses* to help — standing only changes the flavor and side terms, never access.

| Step | Trigger | Giver | Description |
|------|---------|-------|-------------|
| `prologue_signal` | Auto while flying through Sol (first launch) | None | Garbled transmission on an unknown frequency — static, a burst of coordinates, then cut off. It points to a location on Mars. The player is the only one who seems to have heard it. |
| `prologue_mars_unlocked` | Signal received (auto) | None (checkpoint) | **Mars surface exploration unlocks.** (Today Mars is *always* explorable — see the gate note below.) |
| `prologue_mars_entrance` | Explore the Mars surface | Mars (dungeon) | Among the red-dust ruins the player finds the entrance to something — a sealed door of alien make, no visible mechanism, older than the colony. It will not open. |
| `prologue_seek_help` | Talk to NPCs about the door | Any of several | The player begins looking for help. Each faction NPC gives a DIFFERENT lead (faction fork seeds here): Barkeep (bar): "Heard about the thing in the dust? The militia sealed it — or *someone* did." Trade Marshal (merchants): "Alien tech? That's the most valuable cargo in history. Bring me proof." Mars Patrol (militia): "There is no door. Whatever you saw, forget it." Research Officer (lab): "A sealed structure? I need to study it. Bring me a sample of the material." The lab lead is found at a **science station** (Alpha Centauri Science Port, Mercury, Sirius, Procyon C) — Mars has no lab building, so the lab read is the one that pulls the player off-world (which feeds into Act 1's research trail). Dialogue is keyed by `npc_id`, so seek-help lines surface on whichever planet the player talks to the NPC (Earth or Mars variants of `barkeep`/`guild_master`/`militia_captain` share ids — intended). |
| `prologue_open` | Return to Mars with the chosen faction's key/tool | None (auto) | Act 0 ends when the player returns with the faction-given method and opens the entrance — revealing the empty prison and its data. The chosen faction's claim is planted (first claim). |

**Reward:** The door opens. The prison's data recovered (fuels Act 1). The chosen faction's claim is planted early. Faction fork is seeded (each NPC's lead points a different direction).

**Faction opening methods — "the player picks who helps them":**

| Faction | How the door opens | What they ask in return | Flavor |
|---------|--------------------|-------------------------|--------|
| **Militia** | Classified schematics + a military breach charge — they've seen this tech before ("the incident"). | Silence. The operation stays off the books. | The public face (Mars Patrol) denies the door exists; the schematics come from a **ranked contact off the books** — the player must first prove they've seen the door (or earn the patrol's trust) before the real lead opens up. |
| **Merchants** | A salvager's cutter tuned to alien alloys. | A trade contract — first rights to anything inside. | "Money buys the right tool. Sign here, and the cutter's yours — I want first look at what's inside." |
| **Bar / pirates** | A rig that brute-forces the seal's power feed (an old smuggler cracked a door like this once). | A cut of whatever's valuable — and the story, for the bar. | "There was a guy got a door like that open once. Cost him a hand. Here's how he did it." |
| **Lab** | The resonance key — studying a sample of the door's material produced a frequency that opens it. | A sample from inside, for study. | "We analyzed the material you brought. The door responds to a specific resonance. Take the key." |

**Mars exploration gate (implementation note):** `data/planets.has_explorable_sites("mars")` returns `["Surface"]` whenever `dungeon_params` exists, so the planet menu always offers "Explore Surface". Act 0 requires gating this on `prologue_signal`: before the transmission, the Mars planet menu shows no Explore option (or a locked "??" entry). See Phase 1.

### Act 1: "The Anomaly"

Visit Research Officers at science stations to piece together what the signal is — carrying the **prison data** recovered on Mars, which is what earns the officers' attention. The research trail is the **breadcrumb**; the faction quests and mysteries are the **dig** content that opens alongside it.

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

**Lab-ending trigger (explicit):** there are TWO early lab-claim sources — the research trail (completes before the blockade) and the Act 0 Mars faction choice (pick lab to open the door). Either plants a lab claim early, and under "last claim wins" any later diplomatic/smuggler claim supersedes it. The lab ending therefore fires via the combat path: **combat path + (lab claim from research OR Mars choice) → lab ending** (the truth-teller publishes it); **combat path + no lab claim → alone** (the player keeps the secret). This is intentional — the "truth-teller goes alone" pairing — and an implementer should not expect the lab ending to be freely reachable.

- Militia claim: the frontier is sealed; the threat is "contained." The militia thanks the player, quietly.
- Merchant claim: a new trade route opens; the structure is quietly mined for tech. The Guild Master offers the player a share.
- Pirate/bar claim: the structure is stripped; the warning is buried in a bar story. The Barkeep raises a glass.
- Lab claim: the truth is published; humanity hears the warning. The Research Officers study the data beacon openly.
- Alone (no claim): the player keeps the secret. The frontier stays open and wild.

## Implementation phases

### Phase 1: Data model + Prologue (Act 0 — "The Door on Mars")

- [ ] Add `MainQuestStep` dataclass to `data/main_quest/` module
- [ ] Add `main_quest_progress`, `main_quest_unlocked_items`, `main_quest_path`, `main_quest_backing`, `main_quest_complete` to `GameContext`
- [ ] Write Act 0 steps as data (`prologue_signal` → `prologue_mars_unlocked` → `prologue_mars_entrance` → `prologue_seek_help` → `prologue_open`)
- [ ] Wire `prologue_signal` auto-trigger into `_launch_to_space` (first launch only, in Sol)
- [ ] **Gate Mars exploration** on `prologue_signal`: `has_explorable_sites` / planet menu must hide "Explore Surface" until the transmission is received
- [ ] Add the sealed entrance to the Mars surface (a distinct tile/entity — alien make, unopenable until `prologue_open`). The Mars surface is procedurally generated via `dungeon_params`/`generate_dungeon` (random each visit), so the entrance needs a deterministic placement strategy: e.g. place the sealed-door entity at a fixed position AFTER generation, or tag a landmark room so the player can find it on any run
- [ ] Wire `prologue_seek_help` dialogue into bar / merchant / militia / lab NPCs (4 faction reads)
- [ ] Wire `prologue_open` — returning with the right knowledge/tool opens the door, Act 1 begins
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

- [ ] **Save/load:** `main_quest_progress`, `main_quest_unlocked_items`, `main_quest_path`, `main_quest_backing`, `main_quest_complete` → added to both `_ctx_to_dict()` AND `load_game()`
- [ ] **Game guide:** New main quest overlay → updated `_GUIDE_MISSIONS` or new `_GUIDE_MAIN_QUEST` section
- [ ] **NPC spawns:** Alien sentinel ships → registered in `ctx.procedural_spawns` with matching `squad_id`

## Open questions

1. ~~What exactly is the warning?~~ **RESOLVED:** The structure is a seal. The signal is the lock failing — something is trying to come through, and the seal is breaking. The builders left the warning so someone would be ready.
2. ~~Faction questline depth~~ **RESOLVED:** militia + merchants get full backing questlines in v1; bar + lab are dialogue-only backing (claims still reachable via path choice / research completion).
3. ~~What is behind the Mars door?~~ **RESOLVED:** an empty ancient alien prison — tech beyond any known human tech, and a data cache needing translation/study. The emptiness is deliberate (see Act 0 note).
4. ~~What opens the Mars door?~~ **RESOLVED:** a faction choice — the player picks which faction helps, and each faction opens it differently (militia breach / merchant cutter / bar brute-force rig / lab resonance key). The chosen faction's claim is planted early.
5. **The empty cell** — is the prison's prisoner the same threat the Act 3 seal is failing against? (Story payoff for the Act 3 reveal; needs the user's call at Act 3 writing time — kept ambiguous on purpose for now.)
6. **Ending world-state** — should the epilogues change the world (blockade opens, new trade route, structure mined) or stay text-only?
7. **Main quest steps never appear on mission boards** — only triggered by exploration and NPC conversation.
8. **Game continues after Act 3** — the story loop closes, sandbox continues. Confirmed.
9. **No time pressure, no fail states** — the quest waits forever. Confirmed.
