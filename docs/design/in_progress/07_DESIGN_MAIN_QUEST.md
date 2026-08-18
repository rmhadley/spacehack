# DESIGN: Main Quest Storyline

## Overview

A **non-linear main quest** the player follows alongside sandbox play. It begins with the Mars prison, follows the recovered data beyond the Luyten's Star blockade, crosses a dead alien multi-system network, and ends with a space battle against the ancient prisoner that now rests near a black hole.

**Implementation cross-reference:** `24_DESIGN_REUSABLE_QUEST_SYSTEM.md` is the
current implementation contract for the reusable quest system. It owns the
`MainQuestStep` data catalogs, objective-handler registry, faction-heat tags,
scene identifiers, additive quest-NPC presence, JSON text overlay, minimal
validator, and authoring guide. This document remains the narrative and
future-content roadmap; do not create a parallel runtime contract here.

**The premise is a blend of alien mystery, faction politics, and consequence.** The four human factions offer competing interpretations and tools, but none possesses the whole truth. The player keeps making reasonable choices in pursuit of knowledge, survival, wealth, or security — and those choices gradually restore the path that wakes the prisoner. The final encounter is morally ambiguous without softening the creature's monstrous power or the devastation it caused.

## Design decisions (locked with the user)

| Decision | Choice |
|----------|--------|
| **Core premise** | Alien mystery as the outer frame; faction politics and consequence are the engine. Each faction offers a useful but biased interpretation. Investigation and an explicit final choice determine the outcome. |
| **Pacing** | Hybrid: main-quest breadcrumbs are visible in the quest log, but mysteries and faction quests are *dig content* — the player finds them by exploring and talking to the right people. |
| **Ending** | Definitive resolution at the end of Act 3 (a real conclusion), then the sandbox continues. |
| **Time pressure** | None. No deadlines, no fail states — nothing expires. The quest waits forever. Chain steps add a **minimum-wait gate** on the world clock: the next step unlocks only after N days, but ignoring a summon never fails anything. **Gates are tuned so ONE full faction chain spans ~425 in-game days ≈ 14 months — 5× the ~85-day Earth→Luyten one-way trip (locked with the user) — giving the player deep sandbox room to explore, build XP/credits, and gear up between summons.** |

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
- The Act 0 faction choice is a continuing lens and source of support, not the sole owner of the truth
- The prisoner is visibly catastrophic but morally ambiguous: victim, survivor, and destroyer may all be true
- Final resolutions are investigation-gated: knowledge determines what the player understands is possible; equipment affects execution and cost

## Faction politics — the engine of the story

The Act 0 faction choice remains important after the Mars door opens, but it does not make that faction the sole owner of the prison data. The chosen faction gets the first look and supplies the first interpretation. The player can then decide how much to share, whether to seek competing expertise, and who receives the dangerous truth.

| Faction | First interpretation of the prison data | Wants | How they help after Act 1 |
|---------|------------------------------------------|-------|---------------------------|
| **Militia** | "This is a threat warning. The blockade is quarantine." | Containment, secrecy, and control of the frontier. | Classified records, blockade clearance, containment tools, military support. |
| **Merchants** | "This is a map to an abandoned technology network." | Access to alien technology and a profitable new route. | Funding, modules, ship integration, salvage rights, power-system expertise. |
| **Bar / pirates** | "This is a hidden route to the greatest score in history." | Reach the dead network before the militia seals it forever. | Smuggling routes, sabotage, contraband equipment, unconventional escape plans. |
| **Lab / civilians** | "This is a translation problem. Understand it before acting." | Reconstruct the truth and warn humanity. | Translation, signal analysis, alien communication, historical interpretation. |

The player may continue with the Act 0 faction, leak or sell a copy, bring in another faction, or keep the data secret. Faction relationships shape interpretations, equipment, support, and available approaches; they do not dictate a single canonical ending.

The old **"last claim wins"** epilogue rule is superseded. Final outcomes should reflect accumulated investigation, disclosed information, faction support, and a final explicit decision rather than one late claim timestamp.

## Mysteries & dig content

Main-quest breadcrumbs are visible in the quest log. The deeper mysteries are **not** — the player finds them by digging: talking to the right NPC, flying to an odd system, boarding a strange derelict, and comparing contradictory records.

| # | Mystery | How to find it | Payoff |
|---|---------|----------------|--------|
| M1 | **The Jamming** — who has been suppressing the prison signal, and why? | Find a classified militia comms log through the militia route, a lab terminal, or a frontier derelict. | The militia knew about the prison incident and has been hiding the scale of the threat. |
| M2 | **The Lost Scouts** — what did the missing scouts see beyond the Line? | Salvage a frontier derelict and recover its black box. | The scouts found a dead network, not a normal colony or station. |
| M3 | **The Vega Gate** — why was a supposedly decommissioned gate still active? | Follow the Mercury research lead and activate the hidden gate in Vega. | A route beyond the blockade that may itself belong to the old anomaly network. |
| M4 | **The Lost Expedition** — what happened to the merchant-funded science crew? | Unlock through merchant backing or find their abandoned research trail. | The expedition recorded the first evidence of a recurring return path. |
| M5 | **The Foreign Prisoner** — what was the thing in the cell? | Compare prison records, alien observations, and damaged civilian accounts. | The prisoner was foreign to the alien civilization; it was studied, exploited, feared, and imprisoned. |
| M6 | **The Star-by-Star Retreat** — what wiped out the alien civilization? | Explore dead relay, colony, and archive systems. | The aliens severed their own network system by system while the prisoner's route moved toward a place it could survive. |
| M7 | **The Sleeping Refuge** — why does the anomaly terminate near a black hole? | Reach the final dead-star system and reconstruct its sensor history. | The black hole is the prisoner's natural refuge and power source, not its original cell. |

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
    option_label: str = ""                 # menu option text when this dialogue is live
                                             # (e.g. "Tell me about the door"); empty =
                                             # no quest option row shown for this NPC
    backing_faction: str = ""              # faction relationship/support flag planted when this dialogue
                                             # triggers ("militia"/"merchants"/"bar"/"lab")
    unlock_item: str = ""                  # item id added to main_quest_unlocked_items
                                             # when this dialogue triggers (e.g. the
                                             # faction's door-opening tool)
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

**Runtime note (Phase 1a):** the data catalog keys dialogues by
``npc_id`` per step (``step.dialogues`` is a dict), but
``QuestDialogue`` carries the ``npc_id`` for authoring clarity.
The runtime build step flattens them into the per-step dict at
registry-build time (same auto-discovery pattern as the mission
catalog). The live NPC-talk modal shows the resolved dialogue text
as the body AND appends a menu option when ``option_label`` is
non-empty — selecting it triggers the step advancement
(``trigger_on_talk``) and plants ``backing_faction`` +
``unlock_item`` per the dialogue entry.

## Data model

The snippets below describe the narrative-facing fields used by this design.
For the complete current structural contract—including overlay-backed prose,
objective fields, heat tags, scenes, auto-loading, NPC presence, and time
gates—use `src/spacehack/data/main_quest/__init__.py` and the authoring guide at
`src/spacehack/data/main_quest/README.md`. The reusable-system design owns
runtime changes to that contract.

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
    option_label: str = ""
    backing_faction: str = ""
    unlock_item: str = ""

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
    # --- chain objective fields (Act 0 faction chains) ---
    objective_type: str = "talk"       # "talk" | "delve" | "smuggle" | "goods" | "visit" | "bounty" | "salvage" | "bump"
    requires_goods: tuple[tuple[str, int], ...] = ()  # (trade_good_id, qty) — checked + consumed on trigger
    requires_npc_id: str | None = None  # expert NPC to recruit ("visit") or deliver hot cargo to ("smuggle")
    requires_spawn_id: str | None = None  # quest-tagged bounty/salvage spawn id ("bounty"/"salvage" objectives)
    delve_good_ids: tuple[str, ...] = ()   # goods placed in the quest cache ("delve" objectives) —
                                             # the cache yields these; securing it completes the step
    smuggle_good_id: str = ""             # hot cargo id ("smuggle" objectives) — loaded into the mission
                                             # hold like an is_smuggle mission; militia scans can confiscate it
    smuggle_cargo_size: int = 0           # volume of the hot crate ("smuggle") — vs. Smuggler's Hold capacity
    # --- time-gating fields (minimum waits, never deadlines) ---
    wait_days: int = 0                    # world-clock days the faction "works" after this step completes
                                             # before the NEXT step unlocks (0 = no gate)
    completion_flavor: str = ""           # flavor logged when this step completes ("We'll be in touch.")
    ready_message: str = ""               # one-way summon sent when the wait elapses — names the next
                                             # step's system + planet ("Report to Cygni. The Captain waits.")
    dialogues: dict[str, QuestDialogue] = field(default_factory=dict)  # npc_id -> dialogue override
    auto_advance: bool = True                 # false for narrative checkpoints with an explicit scene handoff
    rewards_credits: int = 0
    rewards_xp: int = 0
    rewards_rep: dict[str, int] | None = None
    rewards_item: str | None = None
```

### New fields on `GameContext`
- `main_quest_progress: dict[str, str]` — step_id → `"available"`, `"active"`, `"completed"`
- `main_quest_unlocked_items: set[str]` — items and dialogue unlocked by quest steps
- `main_quest_gate: dict[str, tuple[int, int, int]]` — next_step_id → (day, month, year) when its minimum-wait gate elapses (set on step completion via `time.add_days_to_date`; the per-frame check flips the step to `"available"` + queues the summon). Survives save/load.
- `main_quest_pending_message: str = ""` — queued one-way summon text awaiting delivery at the next safe frame (same overlay as the prologue transmission). Cleared on delivery. Survives save/load.
- `main_quest_chain: str = ""` — the faction chain locked in when the player Accepts a faction's door help (`"militia"` / `"merchants"` / `"bar"` / `"lab"` / `""`). Set by the accept flow; read to close the other factions' offer rows and to gate the faction tool. Survives save/load.
- `main_quest_path: str = ""` — which blockade path was taken (`"diplomatic"` / `"smuggler"` / `"combat"` / `""`), read by the Act 3 epilogue
- `main_quest_backing: set[str]` — shipped faction relationship/support flags planted by Act 0 and backing dialogue; future ending logic may use them as accumulated history, never as a last-claim selector
- `main_quest_complete: bool = False` — set when Act 3 resolves (definitive ending; sandbox continues)

### New fields on `PlanetSpec`
- `main_quest_flavor: str = ""` — lore line shown on landing

## Story outline (3 acts)

### Act 0: Prologue — "The Door on Mars"

The player receives a garbled transmission as they jump out of Sol for the first time. It points to a location on Mars. They explore Mars, find a sealed entrance to *something*, and can't get it open — then they seek help from NPCs across the sector. Act 0 ends when the player returns with the right knowledge/tools and opens the door. Act 1 begins immediately on the other side, with the descent into the prison below Mars.

**The Mars door is alien technology connected to the later network, but it is not the black-hole refuge.** The door is a sealed, dormant prison node that opens only with the chosen faction's tool. The later dead-network systems and black-hole regulators are related infrastructure, but they must not be conflated mechanically: the Mars door is a prison entrance, the anomaly is a transit/return path, and the black hole is the creature's chosen resting place.

**Behind the door: an empty ancient alien prison.** Inside are technologies beyond any known human tech and a cache of layered data that resists immediate translation: routes, warnings, containment records, and fragments of an identity. The cell is **empty** — whatever it held is long gone, or was never there, or got out. This is a deliberate ambiguity the later prisoner reveal pays off. The prison descent is the opening of Act 1; the recovered data becomes the foundation for the later research trail, which branches after the prison objective is complete.

**Opening the door is a faction choice.** The player picks which faction helps them; *how* the door opens changes with that choice (see the table below). Choosing a faction establishes the player's first interpretive lens and relationship, but does not predetermine the final resolution. Consistent with the rest of the game, no faction ever *refuses* to help — standing only changes the flavor and side terms, never access. The authored chains are intentionally different lengths: Militia (6 steps), Merchants (5), Bar (6), and Lab (7).

| Step | Trigger | Giver | Description |
|------|---------|-------|-------------|
| `prologue_signal` | First jump out of Sol | None | A transmission cuts through the static: coordinates folded inside a second pattern, then silence. It points to a location on Mars. The player is the only one who seems to have heard it. **Delivered as a full-screen "INCOMING TRANSMISSION" comms overlay** (ENTER to acknowledge) as the player emerges in the destination system — the signal arrives through the comms, not just log lines. |
| `prologue_mars_unlocked` | Signal received (auto) | None (checkpoint) | **Mars surface exploration unlocks.** (Today Mars is *always* explorable — see the gate note below.) |
| `prologue_mars_entrance` | Explore the Mars surface | Mars (dungeon) | Beyond the red-dust ruins, the player finds a structure that predates every human survey: a seamless alien door with no controls or hinges. It is not damaged. It is waiting. |
| `prologue_seek_help` | Talk to NPCs about the door | Any of several | The player begins looking for help. The Bar offers an old route and a survivor's testimony; the Guild offers a contract and a way to price the unknown; the Militia offers a classified response to the Incident; the Lab offers controlled evidence and resonance analysis. Dialogue is keyed by `npc_id`, so the lead surfaces wherever the relevant NPC appears. |

  **LOCK-IN on accept (user decision):** accepting a faction's help commits the player to that faction's chain — `ctx.main_quest_chain` is set, the faction's tool is NOT yet granted, and the other three factions' "Ask about the Mars door" option rows close (their dialogues resolve to a locked/"you already have a way in" variant; they still offer normal work). Every step in the chosen faction's chain must be completed before the door can open; the paths are not identical in length or emphasis. |
| `prologue_open` | Return to Mars after completing the chosen faction's chain | None (auto) | Act 0 ends when the player completes the faction chain, receives the faction's tool, and opens the entrance. The empty prison is revealed; `act1_prison` becomes available and the chosen faction relationship is recorded. The deeper terminal data is extracted during the Act 1 prison objective. |

**Reward:** The door opens and Act 0 closes. The prison descent becomes the opening Act 1 objective. The prison's data is recovered at the end of that descent, and the chosen faction becomes the player's first interpreter and source of support. The faction fork remains consequential without dictating the ending.

**Faction opening methods — "the player picks who helps them":**

| Faction | How the door opens | What they ask in return | Flavor |
|---------|--------------------|-------------------------|--------|
| **Militia** | Classified schematics + a military breach charge — they've seen this tech before ("the incident"). | Silence. The operation stays off the books. | The public face (Mars Patrol) denies the door exists; the schematics come from a **ranked contact off the books** — the player must first prove they've seen the door (or earn the patrol's trust) before the real lead opens up. |
| **Merchants** | A salvager's cutter tuned to the door's material response. | A trade contract granting first access to recovered material and data. | The Guild treats an unknown discovery as an asset before anyone knows whether it is safe to own. |
| **Bar / pirates** | A rig rebuilt from an old attempt to make a similar door answer. | The truth of what happened, told without an official polish. | The Bar carries the survivor's version of the Incident through rumor, debt, and memory. |
| **Lab** | A resonance key built from the door's material signature and older reference data. | Controlled evidence from inside, not an unrestricted claim. | The Lab insists that a key can open a door without answering why the door was built. |

### Faction quest chains — the seek-help fork becomes 24 authored steps

The tools are not handed out for free anymore. Accepting a faction's help starts that faction's **multi-step chain** (Militia 6 steps, Merchants 5, Bar 6, Lab 7; 24 authored steps total); the tool (and therefore `prologue_open`) unlocks only when the chain is complete. Every chain mixes the mechanics the game already has — **procedural surface dungeons** (cave delves for the materials), distant-planet expert recruitment, space combat (bounty spawns), derelict boarding (salvage interiors), and a final assembly beat. Only the bar chain keeps a small goods payment (a bribe to the old smuggler, not a supply run). Each chain's final step plants the faction tool + makes `prologue_open` available.

**Chain anatomy (variable by faction):** `q1` commitment/lead → `q2` materials (delve: secure a quest cache from a planet's procedural surface cave — the item is *found*, not bought) → `q3+` transport or recruitment (militia: `smuggle` the requisition to the blockade; merchants: `smuggle` — transport the raw ore through contested space to the specialist; bar: `smuggle` — deliver a hot crate to prove yourself; lab: `smuggle` — deliver the door sample) → field test (bounty combat OR derelict salvage, often with faction-specific heat) → final assembly (tool unlocked → door opens). Each chain's mid-game is where the faction's flavor lives: militia is by-the-book (smuggle → visit → live-fire), merchants is economic warfare (smuggle → blockade salvage), bar is criminal heat (smuggle → recharge → charged return run), lab is academic (smuggle → salvage → recorder return).

**Time gating between every step:** each completed step logs faction flavor ("We'll be in touch." / "We need time to research this.") and starts a **minimum-wait gate** (`wait_days`, world clock — see the Time gating section). When the clock passes the gate, the faction sends a **one-way auto-message summoning the player** to the NEXT step's system + planet (each step picks its own location — never a requirement to repeat the previous one). **Chain pacing target (locked): one chain ≈ 425 in-game days total (gates ~340d + travel ~85d) = 5× the 85-day Earth→Luyten one-way trip.**

#### Militia — "The Incident" (breach charge)

| Step | Objective | What the player must do | Rewards |
|------|-----------|-------------------------|---------|
| `mil_q1_report` | talk | Report to the Militia Captain (Earth) — he admits a patrol encountered the material during the Incident, then buried the record. A requisition cache holds the parts for a breach package. | 50 XP |
| `mil_q2_cache` | delve | Descend into the **Mercury** surface caves (procedural dungeon) and secure the classified requisition cache: `ship_components` ×4 + `fuel_cells` ×2 (found, not bought) | 100 credits, 80 XP |
| `mil_q3_inspection` | **smuggle** | Run the requisition to the `blockade_officer` at **Luyten's Star** — five jumps through frontier space. Non-confiscatable (militia's own hardware). | 60 XP |
| `mil_q4_demolitions` | visit | Recruit the `demolitions_expert` at **Epsilon Eridani b** (he signs on when the Captain's name is dropped) | 60 XP |
| `mil_q5_livefire` | bounty | **Live-fire test:** clear **5 pirate captains** at Cygni (quest bounty spawn — the breach-charge prototype is mounted to your ship for this fight) | 150 credits, 120 XP |
| `mil_q6_charge` | talk | Return to the Captain — the breach charge is assembled → `militia_breach_charge` + `prologue_open` | 200 credits, 150 XP |

**Gating (implemented):** q1→q2 60d · q2→q3 0d (auto-advance) · q3→q4 80d · q4→q5 120d · q5→q6 80d (sum 340d). Completion flavor per step in the data. Summons: Mercury (q2), Luyten's Star (q3 — delivery), Epsilon Eridani b (q4), Cygni (q5), Earth (q6).

#### Merchants — "The Contract" (cutter) — REVISED with bar-chain lessons

**Physical through-line:** the rare alloy ore → smelted alloy → cutter. One object, escalating value, moving through contested space. Every step advances the same stake.

**Signature risk — consortium heat:** a competing merchant syndicate wants the Wolf 359 claim. They field merchant ships with **pirate escorts** (squads — the escorts are the teeth, the merchant ships are the flag). During q3 (raw ore transport) and q4 (smelted alloy recovery), consortium-tagged ships spawn in the route systems as quest-tagged BountySpawns. As the ore gains value, the consortium commits heavier forces:

- **q3:** merchant leader + 1-2 pirate scouts per squad (the ore is raw, worth something but not everything)
- **q4:** merchant leader + 2-3 pirate raiders per squad (the smelted alloy is worth 10× more — they're serious now)

Consortium heat mirrors the bar chain's militia heat mechanically (quest-tagged BountySpawns, 30-cell detect radius, 33% A* recompute, drift past 50 cells) but with different flavor: economic warfare, not criminal heat. Rep stakes: -5 merchant per consortium ship killed, -2 pirate per escort killed.

| Step | Objective | What the player must do | Rewards |
|------|-----------|-------------------------|---------|
| `mer_q1_contract` | talk | Sign the contract with the Guild Master (Earth) — the Guild gets first access to recovered material and data, while you receive the cutter. The first clause moves an old Wolf 359 claim into your name. | 50 XP |
| `mer_q2_strike` | delve | The claim is deep in the **Wolf 359** surface caves (procedural dungeon). Rival prospectors from a competing consortium got there first — clear them out (ground combat). Secure quest-tagged `rare_earth_metals` ×3. **Raw ore is now in your hold — valuable but unrefined.** | 100 credits, 80 XP |
| `mer_q3_transport` | **smuggle** | The ore needs smelting. Transport it to the `salvage_specialist` at **Tau Ceti b**. **Consortium ships + pirate escorts patrol the route — they know about the strike and want the ore.** Scan → combat. Deliver the ore → the specialist begins the smelt. | 100 credits, 90 XP |
| `mer_q4_calibrate` | salvage | The specialist finishes the smelt (time gate). **The smelted alloy is loaded into your hold — worth 10× the raw ore.** The cutter needs calibration data from a derelict near **Vega** (`scout_a` layout) — but the consortium has escalated: **ships + pirate raiders are guarding the wreck. Fight through the blockade to board it.** Recover quest-tagged `calibration_data` from the wreck interior. | 150 credits, 120 XP |
| `mer_q5_cutter` | talk | Return to Earth with the smelted alloy + calibration data. The Guild Master assembles the cutter. Sign the final addendum → `merchant_cutter` + `prologue_open`. | 200 credits, 150 XP |

**Risk escalation:**
```
q1: talk      ░░░░  No risk
q2: delve     ██░░  Ground combat (rival prospectors)
q3: smuggle   ████  Space combat + scan risk (consortium ships + pirate escorts en route)
q4: salvage   ████  INTENSE space gauntlet (consortium blockade at wreck) + ground combat (scavengers)
q5: talk      ░░░░  Resolution
```

**Gating (every gate has an in-universe reason):** q1→q2 60d ("The guild needs time to file the escrow paperwork and transfer the claim deed.") · q2→q3 0d (auto-advance — the ore is raw, needs smelting now) · q3→q4 130d ("The specialist hooks the ore into his smelting rig. 'High-grade stuff. Give me a few months — I'll call when it's ready.'") · q4→q5 0d (auto-advance — get the parts back to Earth). Sum 190d gate time (vs. the 340d chain target, giving the player ~150d of sandbox room between summons — slightly faster than the bar chain, reflecting the merchant chain's "time is money" flavor). Completion flavor: "Contract filed. We need time to arrange the escrow." / "The specialist smelts the ore — this takes months." / "The cutter needs calibration data from a derelict near Vega — the consortium's guarding it." / "The cutter is ready." Summons: Wolf 359 (q2), Tau Ceti b (q3 — trigger_planet_id; no gate, auto-advance from q2), Tau Ceti b (q4 — pick up the smelted alloy + head to Vega), Earth (q5).

**q4 intensity detail:** the derelict near Vega is a two-phase gauntlet. Phase 1: space — fight through the consortium blockade (quest-tagged BountySpawn: merchant leader + 2-3 pirate raiders). Phase 2: ground — board the derelict, fight scavengers inside, secure the calibration data. Only the merchant leader counts for objective completion; escorts are bonus kills + rep. This mirrors the salvage rights bar missions but the space patrol is quest-tagged for the chain (no random generation — it's always there while the step is active).

#### Bar — "The Old Hand" (brute rig)

| Step | Objective | What the player must do | Rewards |
|------|-----------|-------------------------|---------|
| `bar_q1_oldhand` | talk | The Barkeep (Earth) names an old smuggler who made a similar door answer and lost a hand for it. Since the Incident, the Militia has watched the old routes for anyone asking the wrong questions. | 50 XP |
| `bar_q2_proof` | smuggle | The old smuggler won't deal with strangers. The Barkeep hands you a **hot crate** — `weapons_blackmarket` ×8, loaded into the mission hold exactly like a smuggling mission (`is_smuggle`). Run it to the `old_smuggler` at **Barnard's Star b**. Every militia patrol on the way can scan it (rep-gated chance; Smuggler's Hold conceals it, mission-first). **Confiscated = the step fails — the Barkeep re-issues his last crate.** | 100 credits, 80 XP, +2 pirate / -5 merchant / -5 civilian / -8 militia |
| `bar_q3_rigparts` | delve | The old smuggler draws the cave where the old job went wrong — the rig's power cell is still there. Descend into the **Barnard's Star b** surface caves (procedural dungeon) and recover it. | 60 XP |
| `bar_q4_blackmarket` | smuggle | **The cell is in your hold and hot.** Run it to the `wolf_barkeep` at the **Wolf 359 listening post** — the only black-market rig that can recharge it. **Confiscated = the Old Smuggler re-issues a spare casing.** | 50 credits, 60 XP |
| `bar_q5_charged` | smuggle | The cell is charged — **hotter than ever.** Collect it from Wolf 359 and run it back to the Earth `barkeep`. **In Sol, every militia patrol actively hunts you while you carry it (auto-aggro).** | 100 credits, 80 XP |
| `bar_q6_rig` | talk | Return to the Barkeep — the rig is assembled → `bar_brute_rig` + `prologue_open`. "The militia will be watching you from here on, friend. Welcome to the family." | 200 credits, 150 XP |

**Militia heat (bar chain signature risk):** while `ctx.main_quest_chain == "bar"` AND the player is holding hot quest cargo (the `bar_q2` crate or the `bar_q4`/`bar_q5` power cell), `_militia_scan_chance()` applies a **+30% floor** (min 60%, capped 80%) on every militia-patrolled system — the militia knows the player is working the old routes. With the **charged** cell (q5) the militia doesn't just scan — they actively hunt the player in Sol (`charged_cell_in_sol`). The hook is one gate in `navigation._militia_scan_chance` on `ctx.main_quest_chain` + a cargo-presence check; it auto-expires at `bar_q6`. Consequences are the real smuggler economy: confiscation (goods lost + fine + -5 militia rep), combat (rep tank), or paying for a Smuggler's Hold to reduce exposure.

**Gating (implemented):** q1→q2 65d · q2→q3 85d · q3→q4 0d (auto-advance) · q4→q5 90d (the recharge) · q5→q6 0d (auto-advance). Completion flavor per step in the data. Summons: Barnard's Star b (q2 — the cave), Wolf 359 (q4 — recharge done), Earth (q6 — rig ready).

#### Lab — "The Resonance" (resonance key)

| Step | Objective | What the player must do | Rewards |
|------|-----------|-------------------------|---------|
| `lab_q1_sample` | bump | Return to Mars and take a controlled material sample from the door (the seal remains intact; the pirate ambush still springs in the door room) | 50 XP |
| `lab_q2_delivery` | **smuggle** | The door sample is in your mission hold. Deliver it to the `research_officer` on **Mercury** for resonance analysis (non-confiscatable). | 50 XP |
| `lab_q3_reference` | delve | The analysis points to **Procyon C** — a sealed research cache in the ice caves holds a reference dataset: quest-tagged `research_data` ×2 | 100 credits, 80 XP |
| `lab_q4_xenolinguist` | **smuggle** | Deliver the dataset to the `xenolinguist` at **Alpha Centauri Science Port** (`ac_station`) — she maps the resonance frequency (non-confiscatable; the Mercury officer re-issues a lost copy) | 60 XP |
| `lab_q5_frequency` | salvage | Recover the `reference_recorder` from a derelict near **Sirius** (`scout_a` — pirate captain + raiders guard the wreck) | 150 credits, 120 XP |
| `lab_q6_return` | **smuggle** | The recorder is in your mission hold. Fly it back to the `research_officer` on **Mercury** — the resonance map is complete (non-confiscatable). | 100 credits, 80 XP |
| `lab_q7_key` | talk | Return to the Mercury Research Officer — the resonance key is forged → `lab_resonance_key` + `prologue_open` | 200 credits, 150 XP |

**Gating (implemented):** q1→q2 0d (bump auto-loads the delivery) · q2→q3 50d (analysis) · q3→q4 0d (auto-advance) · q4→q5 95d (frequency map) · q5→q6 0d (auto-advance) · q6→q7 80d (key forgery). Summons: Mercury (q3), Alpha Centauri Science Port (q4), Mercury (q7).

**Expert NPCs (new catalog entries):** `demolitions_expert` (militia, Epsilon Eridani b), `salvage_specialist` (merchants, Tau Ceti b), `old_smuggler` (bar, Barnard's Star b), `xenolinguist` (lab, ac_station). Each is an additive entry in the global `data/npcs` catalog, placed through the planet's `quest_npc_spots` and activated by the live step's `npc_presence` tag. They stand in the matching guild building without replacing its regular occupant (`militia_captain` / `guild_master` / `barkeep` / `research_officer`). The reusable-system Phase 3a design and playtest define the presence window and save/load behavior.

**Bar-chain lessons applied to the merchant chain:**

| Lesson (from bar implementation) | How the merchant chain applies it |
|------|----------------------------------|
| **Physical through-line is everything.** The bar chain works because ONE object (the power cell) travels through space. | The rare alloy ore → smelted alloy → cutter is the through-line. q2 digs it up, q3 transports it, q4 recovers it post-smelt, q5 delivers it. |
| **The "smuggle" objective type creates real tension.** Hot cargo in the mission hold, scan risk, delivery to a named NPC. | q3 changed from a flat `visit` to a `smuggle`: transport the ore through contested space with consortium ships + pirate escorts. |
| **Every handover NPC needs dialogue entries on BOTH ends.** Missing the Earth Barkeep dialogue on `bar_q5_charged` caused a silent delivery failure. | q3 has `guild_master` (giver) AND `salvage_specialist` (receiver) dialogues. q5 has `guild_master` dialogue. |
| **Smuggle guards must gate giver AND receiver.** Giver closes when crate held; receiver closes when crate NOT held. | Same pattern: the Guild Master's "Take the ore" closes once held; the specialist's "Hand over" only shows when ore is in the hold. |
| **Escalating risk across steps.** Bar: talk → smuggle → delve → smuggle (dangerous system) → return with aggro → resolution. | Merchant: talk → delve → smuggle (consortium en route) → salvage with blockade gauntlet → resolution. |
| **One signature mechanic, not many.** Bar: militia heat (one hook, escalating). | Merchant: consortium heat (one hook — `consortium_heat_active` — escalating from scouts to raiders). |
| **Performance tuning for per-tick NPCs.** 30-cell detect, 33% A* recompute, drift past 50 cells. | Consortium BountySpawns use identical tuning. |
| **Time gates need in-universe reasons.** "The guild files paperwork" (60d), "The specialist smelts the ore" (130d). | Every gate has a world-clock reason the player can read in the completion flavor. |
| **6 steps, not a strict 5.** The bar chain grew organically to 6 steps to support the through-line. | The merchant chain stays at 5 because the smelt happens during a time gate (q3→q4) rather than as a separate step — but if playtesting shows the flow needs a dedicated pickup step, a 6th step can be added (same as the bar chain grew). |

**Objective types** complete steps outside the dialogue path: `delve` (descend into the target planet's **procedural surface cave** and secure the quest-tagged cache — the item is *found*, not bought), `smuggle` (deliver hot cargo to a target NPC — loaded into the mission hold like a `is_smuggle` mission; militia scans can confiscate it and fail the step), `goods` (cargo check + consume on trigger), `visit` (talk to the expert NPC at a target planet → step completes), `bounty` (quest-tagged `BountySpawn` defeated → step completes), `salvage` (quest-tagged loot secured in a derelict interior → step completes), `bump` (door bump variant, e.g. lab sample), and `prison` (complete the Mars prison objective on the themed interaction path). The live handler table and the authoring workflow are defined in `24_DESIGN_REUSABLE_QUEST_SYSTEM.md` and `src/spacehack/data/main_quest/README.md`; this document describes their story use.

**Delve sites (reuse the Mars surface dungeon):** each chain's materials step sends the player into a **procedural surface cave** — the same BSP generator that builds the Mars surface (`dungeon.generate_dungeon` + `PlanetSpec.dungeon_params` with a planet-themed tile set, exactly like `data/planets/mars.py`). The four delve planets (Mercury, Wolf 359, Barnard's Star b, Procyon C) currently lack `dungeon_params` — adding it is **pure data** (the generator, `has_explorable_sites`, and planet-menu "Explore" option already exist). The site persists in `ctx.interiors` keyed `surface:<planet_id>` (same anti-farm rule as the Mars surface + salvage wrecks; `saveload` already serializes the whole cache generically). The quest cache is placed by a generic `prepare_delve_site` pass after generation — **extract `prepare_mars_surface`'s placement logic into a shared helper** (no copy-paste). The planet menu shows "Explore <site>" only while the chain's delve step is active (chain-aware gate, same pattern as the Mars signal gate in `menus/_planet.py`).

**Time gating & one-way summons (the world-clock hook):** every chain step gets `wait_days` (world clock, ~50-120d ≈ 2-4 in-game MONTHS per gate — deliberately long so each gap is a deep sandbox window: missions, trade, XP, ship upgrades). **Target math (locked): Earth→Luyten's Star = 5 hops ≈ 85d one-way at starter speed (Skiff 10 moves/day, per `data/missions/bar.py` Luyten missions). 5× = ~425d per chain. Gates sum ~340d; the ~85d of inter-step travel completes the 425.** Mechanics:

1. **On step completion:** log the `completion_flavor` ("We'll be in touch.", "We need time to research this.") and record a gate date via the pure helper `time.add_days_to_date(ctx.time_day, ctx.time_month, ctx.time_year, wait_days)` into `ctx.main_quest_gate[next_step_id]`.
2. **Per-frame check:** `main_quest.check_quest_gates(ctx)` runs in the main loop (same delivery pattern as militia auto-hails): when `ctx.time_*` >= a gate date, the next step flips to `"available"` and the faction's `ready_message` (one-way summon naming the next step's `trigger_system_id` + `trigger_planet_id`) is queued as a **one-way incoming-comms overlay** (reuse the `show_prologue_transmission` modal — no reply option).
3. **Minimum wait, never a deadline:** the gate only *unlocks* the next step — the player may answer the summon days, weeks, or months later (gates are 50-120d) with zero penalty. Nothing expires, no fail state. The quest log breadcrumb reads "Awaiting word from the <faction>..." while a gate is pending.
4. **Save/load:** `main_quest_gate` + `main_quest_pending_message` serialize/deserialize with the other main-quest fields (contract below) — a summon mid-flight survives a save/quit/continue.

**Mars exploration gate (implementation note):** `data/planets.has_explorable_sites("mars")` returns `["signal"]` (from `PlanetSpec.explorable_site_name`) whenever `dungeon_params` exists, so the planet menu offers "Explore signal" rather than a generic "Explore Surface". Act 0 requires gating this on `prologue_signal`: before the transmission, the Mars planet menu shows no Explore option (or a locked "??" entry). See Phase 1.

### Act 1: "The Prison and the Translation"

Act 1 begins when the Mars door opens and the player descends into the alien prison. The prison is the opening chapter, not a side dungeon or a prelude. The shipped prison content remains the first half of the act: restore power, cross all five floors, reach the giant empty cell, extract the one live terminal's data, and fight back out as the emergency systems wake.

The prison data is the act's hinge. It is not a clean message or a treasure map. It is a damaged, layered archive that humans initially misread:

1. **Navigation layer:** a coordinate sequence pointing beyond the Luyten blockade.
2. **Network layer:** the destination is a linked system of relays, colonies, archives, and dead transit nodes.
3. **Warning layer:** repeated phrases translate approximately as "Do not complete the return," "Do not restore the road," and "The prisoner follows the path."
4. **Identity layer:** the archive uses terms that may mean prisoner, weapon, survivor, or returning one. Human translation cannot settle the meaning immediately.

The player must activate or reconstruct an alien resonance/translation device to read the deeper layers. This is the first major post-prison bad decision: the player believes they are decoding an archive, but the device sends an answering pulse through the old network. The prison's emergency ascent is therefore also the first sign that the player's investigation has changed the state of the facility.

The Act 0 faction remains the first interpreter, not the sole owner of the truth. The player can share the raw data with that faction, leak or sell a copy, bring in another faction's expertise, or keep it secret. The initial interpretation colors later evidence but does not determine it.

**Current Act 1 opening:**

| Step | Trigger | Giver | Description |
|------|---------|-------|-------------|
| `act1_prison` | Enter the alien-prison extension through the opened Mars stairs; complete on Floor 5 extraction | None (auto) | Descend the five-floor facility, restore power to the deep elevator, reach the giant empty cell, extract the data from the one terminal that still works, and survive the emergency security ascent. The prison is empty, the data is layered, and the archive points toward a larger dead network. |

**Post-prison Act 1 branch — first beat implemented:**

The orbit disclosure is a choice-specific handoff. If the player keeps the archive sealed, the complete raw record remains aboard and `research_alpha` becomes available immediately: the next objective is to deliver it to Alpha Centauri's Science Port. The delivery itself is immediate, but the lab's difficult work is not. Once the Research Officer accepts the archive, a 14-day minimum-wait gate begins while the processing cluster segments the alien signal, separates coordinate patterns from containment records and warnings, and performs its first translation pass. `research_alpha_report` unlocks when that work is complete. If the player transmits a diagnostic fragment, the remote analysis still creates a minimum-wait gate before the Alpha Centauri visit. If the player asks for a safe destination, logistics and security create a minimum-wait gate before the destination is confirmed. These waits are never deadlines: the player may continue sandbox play and answer any later summon without penalty.

| Step | Purpose | Description |
|------|---------|-------------|
| `research_alpha` | Archive handoff | After launching from Mars, the archive becomes active in orbit. The player chooses whether to transmit a diagnostic fragment, keep the archive sealed, or ask for a safe destination. Keeping it sealed unlocks the Alpha Centauri delivery immediately; transmitting a fragment or arranging a secure destination creates a justified wait before the lab visit. The Research Officer accepts the raw archive and starts the processing job; this step does not instantly translate the data. |
| `research_alpha_report` | First translation | After the Alpha Centauri processing cluster spends 14 days segmenting and translating the raw alien layers, the player returns to review the first usable result: a route pattern beyond Luyten, with containment records and warnings still incomplete. |
| `research_sirius` | Decode the network | Sirius research links the coordinates into a multi-system transit network and identifies the hidden Vega route. A first translation warns against completing a return. |
| `research_mercury` | Reconstruct the signal | Mercury research determines that the prison data is not passive: the resonance device answered the network and something on the far side noticed. The player learns the blockade may be a quarantine, not simple military control. |
| `research_procyon` | Prepare the crossing | Procyon research reconstructs the navigation key and identifies several equipment signatures that can survive the dead systems. The player chooses what information and technology to carry forward. |
| `research_decision` | Choose disclosure | The player chooses whether to trust the Act 0 faction, share the data with a rival faction, sell a partial copy, or keep the translation secret. This changes support and later scenes, not the existence of the anomaly. |

**Act 1 discoveries, in planned order:**

- The prison was deliberately disconnected, not merely abandoned.
- The empty cell was occupied by something foreign to the alien civilization.
- The aliens observed, studied, exploited, feared, and imprisoned it; no surviving record proves whether it was naturally hostile before that treatment.
- The data points toward a containment/transport network, not a conventional colony or treasure site.
- Activating the translator broadcasts a recognizable prison signature.
- Alien equipment recovered from the prison is powerful, but carrying and using it makes the player more visible to the network.

Act 1 ends when the player has enough translated evidence to make an informed plan for crossing the blockade. The player should understand that the route is dangerous and that the warnings are serious, but should not yet know whether the prisoner is a deliberate exterminator, a traumatized survivor, or both.

### Act 2: "The Blockade and the Plan"

The blockade is a human quarantine line, but its purpose is contested. The player needs a way through and must decide what to disclose before crossing. The existing three approaches remain, but each changes the player's resources and relationship to the danger beyond the Line.

| Path | Access | Cost / consequence | Strategic advantage |
|------|--------|--------------------|---------------------|
| `diplomatic` | Earn sufficient militia trust and negotiate with the Blockade Officer. | Tracker, reporting obligations, restricted technology, and pressure to preserve containment. | Classified records, safer passage, military support, and the clearest account of "the incident." |
| `smuggler` | Use the hidden Vega gate or an old debris-field route through the Bar. | Hull damage, unreliable navigation, no official rescue, and possible equipment loss. | Secrecy, access to suppressed evidence, contraband alien technology, and unconventional routes. |
| `combat` | Fight through the blockade and recover the command ship's black box. | Militia hostility, destroyed intelligence, later patrol pressure, and no rescue network. | Immediate passage, military salvage, and proof of what the blockade was hiding. |

Before departure, the player makes a **crossing plan** rather than merely selecting a key:

- who receives the translated data;
- whether to carry, remove, or spoof a tracker;
- which alien device to install;
- whether to preserve or destroy the blockade's warning network;
- what equipment to prioritize: stealth, power, weapons, or translation;
- and how much of the warning to believe.

These are not good/evil choices. They are competing priorities: safety, knowledge, money, secrecy, speed, and power. Each plan gets the player beyond the Line, but creates a different downstream problem.

### Act 3: "The Dead Network"

Beyond the blockade is not one alien ruin. It is a chain of dead systems that reveal the civilization's collapse in stages. The player follows the restored route because it promises answers, technology, and a way to understand the prisoner's origin. Every step also restores more of the path that the aliens deliberately severed.

#### The relay system

The first system contains a damaged relay, automated defense constructs, and communication records. The player learns that the transit network was shut down from the inside. The alien civilization did not simply vanish; someone or something forced it to cut its own roads.

#### The colony system

The next system contains evacuation shelters, unfinished ships, abandoned settlements, and records of population movements. The aliens knew the threat was moving through the network and tried to retreat ahead of it. Valuable alien technology can be recovered here, but each recovered component may carry a recognizable network signature.

#### The archive/prison system

A deeper system preserves conflicting accounts:

- official records call the prisoner an existential threat;
- research records describe an incomprehensible foreign organism or intelligence;
- military records describe worlds sacrificed to slow it;
- civilian records describe the aliens turning their own infrastructure into a series of desperate barricades.

The player learns that the prisoner escaped and used the alien transit network to reach a place where it could survive. Its route crossed system after system. Whether it intentionally destroyed the civilization or simply destroyed everything that tried to restrain it remains unresolved.

#### The dead-star system

The anomaly terminates near a black hole. The black hole is not the original prison. It is the creature's natural refuge and resting place, where it can draw power from extreme gravitational and accretion conditions, recover, and remain dormant.

The surviving alien systems around it are a monitoring and containment perimeter: regulators, warning arrays, emergency weapons, and a route-locking lattice. They were built after the creature reached the black hole to keep it asleep or prevent its return path from reaching inhabited space.

The player discovers that the creature's sleep is not harmless. Its presence destabilizes the region, and restoring the network has begun to wake it.

### The prisoner: canon and ambiguity

The prisoner came from the vast empty abyss outside the alien civilization's known domain. It was foreign to them too. They encountered a powerful, incomprehensible being and responded by observing, studying, containing, exploiting, and eventually imprisoning it.

The surviving evidence must support two truths at once:

- the aliens wronged and abused a being they did not understand;
- the prisoner's escape caused catastrophic destruction across multiple systems.

The creature should look and behave unmistakably monstrous in play: immense power, lethal defenses, system-scale consequences, and terrifying presence. Moral ambiguity comes from motive and history, not from weakening the threat or pretending the destruction did not happen.

When the player activates the prison resonance system, carries alien equipment into the dead network, and completes the return path, the black-hole refuge recognizes the prison signature. The prisoner wakes because it interprets the player as a possible jailer, recapture attempt, or return of the civilization that imprisoned it.

> The player did not merely find the prisoner. The player announced that the prison had reopened.

### The finale: the black-hole battle

The finale is a multi-stage space encounter, not a single oversized ship:

1. **Approach:** distorted navigation, gravitational movement, debris, and ancient defense constructs.
2. **The refuge:** the player reaches the sleeping creature's surrounding regulators and must decide whether to repair, disable, reroute, or destroy them.
3. **The awakening:** the creature first appears through gravity distortions, projected forms, and impossible weapon arcs before its full presence emerges.
4. **Resolution:** the player acts on the knowledge gathered across the dead systems.

The game supports multiple definitive resolutions. They are investigation-gated: the player must discover what each option means before it becomes available. Equipment affects execution, resource cost, survival, and collateral damage, but a faction choice alone never locks the player out of understanding the truth.

| Resolution | Required investigation | Outcome |
|------------|------------------------|---------|
| **Destroy** | Discover how the creature can be harmed outside the protection of the black-hole environment. | The creature dies, the anomaly collapses, and much alien technology or evidence may be lost. Humanity survives, but the player may destroy the last surviving record of the civilization. |
| **Return to sleep** | Reconstruct the dormant-state regulators and learn how to restore them. | The creature survives and the route is sealed. The player saves inhabited space by becoming the next jailer of a being that may have been abused. |
| **Redirect** | Learn what environment the creature needs and how to create a route to an uninhabited refuge. | The creature leaves the dead systems. It is no longer immediately aimed at humanity, but it is free and may become another civilization's disaster. |
| **Collapse the route** | Understand the network's essential nodes and the consequences of severing the path near the refuge. | The anomaly is destroyed or stranded. The creature may be trapped or weakened, the player may lose the route home, and the outcome can carry a sacrifice cost. |

The final choice should be explicit. The ending should reflect accumulated discoveries, disclosed information, faction support, crossing plan, alien technology used, and the player's final judgment—not a hidden "last claim wins" timestamp.

**Post-finale:** `main_quest_complete = True`; the sandbox continues. The ending records the chosen resolution and changes epilogue text and any safe world-state consequences without removing the completed run.

## Implementation phases

### Phase 1a: Main-quest infrastructure (build first — everything depends on it)

- [x] Add `MainQuestStep` + `QuestDialogue` dataclasses to `data/main_quest/` module (auto-discovered catalog, `find_main_quest_step` / `list_main_quest_steps`)
- [x] Add `main_quest_progress`, `main_quest_unlocked_items`, `main_quest_path`, `main_quest_backing`, `main_quest_complete` to `GameContext` (all defaulted)
- [x] Serialize + deserialize all 5 fields in `saveload._ctx_to_dict()` AND `load_game()` (save/load contract)
- [x] Build `main_quest.py` runtime: step lifecycle (`start_step` / `complete_step` / `advance_step`), `resolve_npc_dialogue`, quest-log objective helper
- [x] Wire quest-aware dialogue into `npc.py`: `TalkOutcome.QUEST`, quest body text + `option_label` menu row in `render_npc_talk`, trigger advancement in `_run_npc_talk`
- [x] Add `main_quest_door` flag to `world.Entity` (sealed-door entity marker)
- [x] Smoke test + commit

**PLAYTEST (1a):** start a new game; open the quest log (Q) — shows "no main quest" state cleanly; talk to a few NPCs — their normal flavor text still works (no quest dialogue should leak). Save → quit → continue — game loads without error.

### Phase 1b: Act 0 steps data + signal trigger + Mars gate

- [x] Write Act 0 steps as data (`prologue_signal` → `prologue_mars_unlocked` → `prologue_mars_entrance` → `prologue_seek_help` → `prologue_open`) with the 4 faction dialogue leads (barkeep / guild_master / militia_captain / research_officer), each with `option_label`, `backing_faction`, and `unlock_item` (the faction's door-opening tool)
- [x] Wire `prologue_signal` auto-trigger into `navigation._jump_to_system` (first jump OUT of Sol — the outgoing system is checked): log the garbled transmission, mark `prologue_signal` + `prologue_mars_unlocked` active. **The signal arrives as a full-screen incoming-comms overlay** (`main_quest.show_prologue_transmission`) as the player emerges in the destination system — same modal interruption pattern as militia auto-hails.
- [x] **Gate Mars exploration** on the signal: planet menu must hide "Explore signal" until the transmission is received (`has_explorable_sites` / menu item filtered by `ctx.main_quest_progress`)
- [x] Smoke test + commit

**PLAYTEST (1b):** fresh game → launch into space from Earth → NO transmission yet (fly around Sol freely). Jump a gate out of Sol → an **INCOMING TRANSMISSION comms overlay** appears as you emerge (signal trace static + "They resolve to somewhere on Mars"), ENTER to acknowledge. Open the quest log (Q) — shows the main quest breadcrumb. Jump back to Sol, fly to Mars and bump it — the planet menu shows NO "Explore signal" option before the signal (verify by loading a pre-jump save), and the option appears after. Save/quit/continue preserves the signal state.

### Phase 1c: The Door on Mars — sealed entrance, seek-help, prologue_open

- [x] Add the authored `data/landmarks/mars_signal_door.layout` landmark to the fresh Mars surface after `generate_dungeon`. Its lower `d` tile is the reachable entrance; stamping carves a protected route from the dungeon spawn to the approach cell and places the `C` door console entity. **The Mars surface dungeon persists across visits** (cached in `ctx.interiors` keyed `surface:mars` — same anti-farm rule as salvage wreck interiors): the landmark stays exactly where it was found, fog stays revealed, and `prepare_mars_surface` runs only on first generation. The legacy `main_quest_door` entity remains load-compatible for old saves.
- [x] Bump interaction on the landmark's `C` console: before `prologue_open` — "sealed, alien make, no mechanism" + start `prologue_mars_entrance`; with the faction tool — opens, reveals the empty prison + data, completes Act 0, and makes `act1_prison` available. **The two quest-beat bumps (discover + open) surface as full-screen overlays** (`main_quest.show_sealed_door_overlay`) — the same `ui.Modal` interruption pattern as the incoming transmission, with alien-rune static and ASCII door art. Repeat bumps stay as log lines only (no modal nag).
- [x] Wire `prologue_seek_help`: each faction NPC's quest dialogue gives its unique lead and (on trigger) records `backing_faction` + unlocks the tool item. **The offer surfaces as its own full-screen modal** (`main_quest.show_help_offer`) when the player picks the "Ask about the Mars door" option row — the talk modal stays short (normal flavor + the option row), and the offer modal shows the NPC's full lead (word-wrapped, never truncated) with **Accept help** / **Keep looking** options. Keep looking loops back to the talk modal; Accept runs `trigger_dialogue`.
- [x] Wire `prologue_open` completion: returning with the right knowledge/tool opens the door, logs the prison reveal, completes Act 0, and makes the Act 1 prison objective available
- [x] Minimal quest-log breadcrumb: "MAIN QUEST" section showing current step title + objective (full UI polish stays in Phase 4)
- [x] Smoke test + commit

**PLAYTEST (1c):** full Act 0 run — receive signal → explore Mars ("Explore signal") → follow the carved path to the landmark's lower `d` entrance → bump the `C` console (can't open — a SEALED ENTRANCE overlay pops up with alien runes + door art, ENTER dismisses) → talk to each faction NPC (talk modal shows normal flavor + the gold "Ask about the Mars door" row — no more truncated/quoted lead in the body; picking the row opens an AN OFFER OF HELP modal with the NPC's full lead, word-wrapped, plus Accept help / Keep looking) → pick Accept on one faction (relationship recorded, chain locked in) → return to Mars → the SAME surface landmark reloads (console and entrance where you left them, fog still revealed) → complete the chosen chain → bump the console → the barrier undulates, splits from the middle, and reveals the green `>` stairs-down marker; THE SEAL GIVES WAY overlay pops up, prison revealed, Act 0 completes, and `act1_prison` becomes available → bump it again (repeat) → log line only, no modal. The stairs now enter the Act 1 prison content. Also test Keep looking on a second faction (returns to the talk modal; you can walk away). Verify quest log (Q) tracks the boundary. Save/quit/continue mid-Act-0 → state preserved (including the persisted surface dungeon and console entity).

### Phase 1d: Chain infrastructure — lock-in, objective types, delve sites

- [x] Add `main_quest_chain` to `GameContext` + serialize/deserialize in `saveload` (save/load contract)
- [x] Add chain objective fields to `MainQuestStep` (`objective_type`, `requires_goods`, `requires_npc_id`, `requires_spawn_id`, `delve_good_ids`)
- [x] Implement objective completion in `main_quest.py`: `delve` (secure the quest cache in the planet's surface dungeon → completes), `goods` (cargo check + consume on trigger), `visit` (talk to expert NPC → completes), `bounty` (quest-tagged spawn defeated → completes), `salvage` (quest-tagged loot secured → completes), `bump` (door bump variant)
- [x] **Delve site generator:** extract `prepare_mars_surface`'s post-generation placement logic into a shared helper (`prepare_delve_site`) that runs after `generate_dungeon` — places the quest cache (a quest-tagged `loot_data` container with `delve_good_ids`) in a deep room, caches the map in `ctx.interiors` keyed `surface:<planet_id>` (DRY — no copy-paste of the Mars placement block)
- [x] Add `dungeon_params` (planet-themed tiles) to the 4 delve planets: Mercury, Wolf 359, Barnard's Star b, Procyon C (pure data, mirroring `data/planets/mars.py`)
- [x] Chain-aware planet-menu gate: "Explore <site>" shows only while the chain's delve step is active (extend the Mars signal gate in `menus/_planet.py` to take the active chain into account)
- [x] Lock-in flow: Accept help in `show_help_offer` sets `main_quest_chain` (instead of unlocking the tool); the other three factions' "Ask about the Mars door" rows close (locked variant dialogue)
- [x] Chain completion: final step's trigger grants the faction tool, records the faction relationship/support history, and makes `prologue_open` available
- [x] **Time-gate infra:** add `wait_days` / `completion_flavor` / `ready_message` to `MainQuestStep`; add `main_quest_gate` + `main_quest_pending_message` to `GameContext` + serialize/deserialize in `saveload`; implement `main_quest.check_quest_gates(ctx)` per-frame hook (fires when `ctx.time_*` passes a gate date → next step `"available"` + queue the one-way summon; deliver via the prologue-transmission overlay pattern). Dev skip-days helper: Shift+D (SPACEHACK_DEV) advances 30 days so gates can be playtested. Quest log shows "Awaiting word from the <faction>..." while a gate is pending.
- [x] **Act 0 dev shortcut:** Shift+O (SPACEHACK_DEV) opens a four-choice faction picker, then skips directly to the Mars door-opening interaction for animation playtesting; it records the selected `main_quest_chain` + backing faction but does not grant faction-chain rewards.
- [x] Add the 4 expert NPCs (`demolitions_expert` / `salvage_specialist` / `old_smuggler` / `xenolinguist`) to `data/npcs` with additive `quest_npc_spots` + `npc_presence`; verify target planets have the guild building (completed in reusable-system Phase 3a)
- [x] Smoke test + commit

**PLAYTEST (1d):** fresh save → discover the door → talk to each faction NPC (all four offers still open, no lock-in yet) → Accept militia help → the other three NPCs now show a locked/"you already have a way in" variant (no quest row) → confirm `main_quest_chain` survives save/quit/continue → start a NEW game and Accept merchants instead (different chain). In a `SPACEHACK_DEV=1` run, press Shift+O → choose each faction in separate runs → verify the selected chain appears in post-prison faction dialogue and a repeated Shift+O cannot replace it; ESC cancels without changing state. Test the `delve` objective end-to-end: while `mil_q2_cache` is active the Mercury planet menu shows "Explore <site>" → descend into the procedurally generated Mercury cave (planet-themed tiles, fog works) → find the quest-tagged cache in a deep room → secure it (cargo gained, step completes) → the cave persists in `ctx.interiors` across save/quit/continue (anti-farm). Test the gate: complete a chain step → flavor "We'll be in touch." logged → dev-mode skip past `wait_days` → one-way summon overlay arrives naming the next step's location → quest log reads "Awaiting word from..." while pending.

### Phase 1e: Militia chain — "The Incident" (breach charge)

- [x] Write `mil_q1_report` → `mil_q6_charge` as step data (talk / delve / **smuggle** / visit / bounty / talk)
- [x] Wire `mil_q2_cache` delve site on Mercury (cache yields `ship_components` ×4 + `fuel_cells` ×2)
- [x] Wire `mil_q3_inspection` **smuggle** — requisition runs to the `blockade_officer` at Luyten's Star (non-confiscatable, 80d gate)
- [x] Wire `mil_q4_demolitions` **visit** — recruit the `demolitions_expert` at Epsilon Eridani b (120d gate)
- [x] Wire `mil_q5_livefire` quest-tagged bounty spawn (Cygni — **5 pirate captains**; breach-charge prototype mounted to the ship for this fight, dismounted after)
- [x] Wire `mil_q6_charge` trigger → grants `militia_breach_charge` + `prologue_open`
- [x] Write the militia gates (`wait_days` 60/0/80/120/80, completion flavor, summons per the chain table)
- [x] Smoke test + commit

**PLAYTEST (1e):** full militia run — report to the Captain → fly to Mercury, descend into the caves, secure the requisition cache (delve completes; goods land in cargo) → recruit the demolitions expert at Epsilon Eridani b (visit completes) → clear the Cygni scout squad (bounty completes; verify it spawns only while the step is active) → return to the Captain → charge granted + door opens. Check quest log (Q) tracks each step; save/quit/continue mid-chain preserves progress (including the persisted Mercury cave).

### Phase 1f: Merchants chain — "The Contract" (cutter, revised per bar-chain lessons)

- [x] Write `mer_q1_contract` → `mer_q5_cutter` as step data (talk / delve / **smuggle** / salvage / talk). q3 is a `smuggle` — the raw ore is loaded into the mission hold (``smuggle_good_id="rare_earth_metals"``, ``smuggle_cargo_size=3``, non-confiscatable) and must be delivered to the ``salvage_specialist`` at Tau Ceti b.
- [x] **Every handover NPC gets dialogue entries on BOTH ends** (bar-chain lesson). q3 has ``guild_master`` dialogue (giver) AND ``salvage_specialist`` dialogue (receiver — "Hand over the ore"). q5 has ``guild_master`` dialogue ("Collect the cutter").
- [x] **Smuggle guards** (bar-chain lesson): the giver's option closes once the crate is held; the receiver's "Hand over" only shows when the crate is in the hold (``_smuggle_crate_held`` giver-receiver pattern).
- [x] Wire `mer_q2_strike` delve site on Wolf 359 (cache yields quest-tagged `rare_earth_metals` ×3)
- [x] Write the merchant gates (`wait_days` 60/0/130/0, completion flavor, summons per the chain table)
- [x] **Consortium heat mechanic:** ``main_quest.consortium_heat_active(ctx)`` returns True while ``main_quest_chain == "merchants"`` and the player is on q3 or q4. Existing pirates auto-aggro and new consortium squads spawn on system entry + per-tick (reuses the BountySpawn infra; 30-cell detect, 33% A* recompute, drift past 50 cells).
- [x] Wire `mer_q4_calibrate` quest-tagged salvage: derelict near Vega (`scout_a` layout, `calibration_data` interior loot) guarded by a consortium blockade (pirate captain + 2 raiders). Only the leader counts for step completion; escorts are bonus kills.
- [x] Wire `mer_q5_cutter` trigger → grants `merchant_cutter` + `prologue_open`
- [x] Smoke test + commit

**PLAYTEST (1f):** full merchant run — sign the contract ("Contract filed. We need time to arrange the escrow." → time gate 60d) → summon: "The claim is ready. Get to Wolf 359" → descend into the claim caves, clear rival prospectors, secure the ore (delve completes) → auto-advance to q3 (no gate): transport the raw ore to Tau Ceti b — **verify consortium ships + pirate escorts spawn and engage en route** → deliver to the salvage specialist (smuggle completes; "The specialist smelts the ore — this takes months." → time gate 130d) → summon: "Smelt's done. Come get the alloy. The cutter needs calibration data from a derelict near Vega — the consortium's guarding it. Be ready." → pick up smelted alloy at Tau Ceti b → fly to Vega → **fight through the consortium blockade at the wreck (merchant + 2-3 pirate raiders)** → board the derelict → fight scavengers → secure `machine_parts` (salvage completes) → auto-advance to q5 → return to Earth → Guild Master assembles the cutter → sign the addendum → cutter granted + door opens. Verify the derelict interior + Wolf 359 cave persist across visits. Verify consortium spawns only trigger while the step is active. Verify the ``guild_master``'s q3 "Take the ore" row closes after accepting (no re-offer) and the ``salvage_specialist``'s "Hand over" row only shows when the ore is actually in the hold.

### Phase 1g: Bar chain — "The Old Hand" (brute rig, blackmarket + militia heat)

- [x] Write `bar_q1_oldhand` → `bar_q6_rig` as step data (talk / smuggle / delve / smuggle / smuggle / talk)
- [x] Implement the `smuggle` objective: hot crate loaded into the mission hold (`is_smuggle` semantics — `smuggle_good_id` + `smuggle_cargo_size`), delivered to a named NPC; militia scan confiscation fails the step (giver re-issues)
- [x] Wire `bar_q3_rigparts` delve site on Barnard's Star b (cache yields `machine_parts` + `electronics` — the rig's power cell)
- [x] Wire `bar_q4_blackmarket` smuggle — power cell to the `wolf_barkeep` at Wolf 359 (90d recharge gate; the Old Smuggler re-issues a lost cell)
- [x] Wire `bar_q5_charged` smuggle — charged cell back to the Earth `barkeep`; **Sol militia auto-aggro while carried**
- [x] **Militia heat hook:** in `navigation._militia_scan_chance`, apply the +30% floor (min 60%, cap 80%) while `ctx.main_quest_chain == "bar"` and hot quest cargo is held; auto-expire at `bar_q6`
- [x] Write the bar gates (`wait_days` 65/85/0/90/0, completion flavor, summons per the chain table)
- [x] Wire `bar_q6_rig` trigger → grants `bar_brute_rig` + `prologue_open`
- [x] Smoke test + commit

**PLAYTEST (1g):** full bar run — the Barkeep names the old smuggler (warns about militia interest) → pick up the hot crate → fly to Barnard's Star b: **militia patrols scan more aggressively than normal** (scan chance floor active — verify vs. a non-bar save) → deliver to the smuggler (smuggle completes) → he draws the cave → descend, recover the power cell (delve completes; cell is hot cargo now) → the Barnard's Star gate is sealed by a **militia patrol** — fight (militia rep tanks) or flee (another scan) → return to the Barkeep → rig granted + door opens. Deliberately fail `bar_q2` once: get scanned, crate confiscated, step fails, Barkeep re-offers his last crate. Barkeep dialogue stays in-character (tall tales, not exposition).

### Phase 1h: Lab chain — "The Resonance" (resonance key)

- [x] Write `lab_q1_sample` → `lab_q7_key` as step data (bump / **smuggle** / delve / **smuggle** / salvage / **smuggle** / talk)
- [x] Wire `lab_q1_sample` chain-aware door bump (chip a sample; does NOT open the door; pirate ambush springs in the door room)
- [x] Wire `lab_q2_delivery` smuggle — door sample to the `research_officer` on Mercury (non-confiscatable)
- [x] Wire `lab_q3_reference` delve site on Procyon C (cache yields quest-tagged `research_data` ×2)
- [x] Wire `lab_q4_xenolinguist` smuggle — dataset to the `xenolinguist` at Alpha Centauri Science Port (non-confiscatable; Mercury officer re-issues a lost copy)
- [x] Wire `lab_q5_frequency` quest-tagged salvage (derelict near Sirius, `scout_a`, `reference_recorder` interior loot, pirate captain + raiders guarding)
- [x] Wire `lab_q6_return` smuggle — recorder back to the Mercury `research_officer` (the fetch has a return leg)
- [x] Wire `lab_q7_key` trigger → grants `lab_resonance_key` + `prologue_open`
- [x] Write the lab gates (`wait_days` 0/50/0/95/0/80, completion flavor, summons per the chain table)
- [x] Smoke test + commit

**PLAYTEST (1h):** full lab run — bump the door to chip the sample (door stays sealed; no tool yet) → fly to Procyon C, descend into the caves, secure the reference dataset (delve completes) → recruit the xenolinguist at Alpha Centauri Science Port (visit) → recover the frequency dataset from the Sirius derelict (salvage) → return to Mercury → key granted + door opens. Verify the sample chip doesn't accidentally open the door early.

### Phase 1i: Act 0 integration + lock-in polish

- [x] Full 4-chain regression: run all four chains end-to-end on separate saves to `prologue_open` (covered by reusable-system Phase 1 playtest)
- [x] Verify lock-in exclusivity: after accepting one faction, the other three offer rows stay closed even across save/load (covered by reusable-system Phase 1 and 3a playtests)
- [x] Verify `prologue_open` completion records the chosen faction relationship, closes Act 0, reveals the prison, and makes `act1_prison` available for ALL four tool types; prison data extraction is verified in the separate prison-content pass
- [ ] Balance pass: delve cache yields vs. early-game cargo capacity; cave size/placement difficulty (cache must be reachable without combat gear); bounty difficulty vs. expected level at that point; gate lengths feel like pacing, not padding
- [x] Smoke test + commit (covered by the reusable-system phase gates)

**PLAYTEST (1i) — COVERED:** The four-chain, lock-in, save/continue, and
four-tool door-opening regression is covered by the reusable-system Phase 1,
Phase 3a, and Phase 4 playtests. The only remaining Phase 1i work is the
explicit balance pass above.

**PLAYTEST (Phase 2 first beat):** extract the Floor 5 data, fight back to Mars, leave the prison via Floor 1 `<` (and separately test returning to the port and launching). Verify the orbit scene appears once on either departure route, shows the current interpretation, and offers the three disclosure outcomes. Verify deeper-floor `<` transitions do not trigger it early. Verify ESC resolves to the sealed-archive outcome and immediately changes the quest log to `The First Reading`, directing delivery to Alpha Centauri with no gate. Verify the diagnostic-fragment and safe-destination outcomes retain their justified 60-day waits, with choice-appropriate wording and no deadline. The Alpha Centauri station should have both the Research Officer and Xenolinguist, and Continue should preserve the disclosure choice and one-time flag.

### Phase 1j: Time gating + one-way summons (full pass)

- [x] Verify every gate fires on schedule (dev-mode skip-days helper): flavor logged on completion → gate date recorded → when the clock passes it the next step flips to `"available"` + the summon overlay arrives (covered by reusable-system Phase 1 playtest)
- [x] Verify the summon names the NEXT step's system + planet (which can differ from the previous step's location — e.g. militia q2 completes on Mercury, q3 summons to Epsilon Eridani b)
- [x] Verify a summon never interrupts combat/dungeon — it queues in `main_quest_pending_message` and delivers at the next safe frame
- [x] Verify ignoring a summon is harmless: days/weeks later the step is still there, nothing failed, no expiry
- [x] Verify save/quit/continue mid-gate: gate date + pending message survive
- [x] Smoke test + commit (covered by the reusable-system phase gates)

**PLAYTEST (1j) — COVERED:** Time-gate scheduling, one-way summons, late
responses, safe-frame delivery, and save/continue behavior are covered by the
reusable-system Phase 1 and Phase 5 validation/regression gates. No separate
runtime contract is maintained here.

### Phase 2: Post-prison Act 1 — translation and disclosure

- [x] Finish and playtest the alien-prison content before extending the post-prison story.
- [x] Write the first post-prison research beat as data; preserve `act1_prison` as the opening step.
- [x] Define the initial layered archive read: reactive carrier, route hypothesis, and unresolved response; preserve network, warning, and identity layers for later translation.
- [x] Wire the Alpha Centauri Research Officer visit and the Act 0 faction's first interpretation. The station keeps the established Xenolinguist slot and adds a separate archive contact.
- [x] Add the first player disclosure choice: transmit a diagnostic fragment, keep the archive sealed, or ask for a safe destination. The larger trust/rival/sale/secret decision remains later in the branch.
- [x] Add an open-world handoff gate after the orbit disclosure: the selected Act 0 faction spends 60 days comparing the archive, `research_alpha` stays locked during the wait, and a late response remains valid with no deadline or failure state.
- [ ] Define the resonance/translation device and its answering pulse through the alien network.
- [ ] Give the player a preparation plan for the blockade crossing.
- [ ] Smoke test + commit

### Phase 3: Act 2 — blockade breach and crossing plan

- [ ] Implement the diplomatic, smuggler, and combat approaches as distinct resource/support paths.
- [ ] Preserve the existing `main_quest_path` field and add explicit crossing-plan state only when the design is settled.
- [ ] Wire Blockade Officer, Luyten Bar, and hidden Vega gate interactions.
- [ ] Define what each path reveals, destroys, or carries across the Line.
- [ ] Add the blockade command black box and the quarantine explanation.
- [ ] Smoke test + commit

### Phase 4: Act 3 — dead network and dig mysteries

- [ ] M1 The Jamming: classified militia comms log.
- [ ] M2 The Lost Scouts: frontier derelict and black box.
- [ ] M3 The Vega Gate: activate the hidden route.
- [ ] M4 The Lost Expedition: merchant-backed expedition records.
- [ ] M5 The Foreign Prisoner: contradictory alien, military, and civilian accounts.
- [ ] M6 The Star-by-Star Retreat: dead relay, colony, and archive systems.
- [ ] M7 The Sleeping Refuge: black-hole sensor history and failed regulators.
- [ ] Add dead-network system content and reusable alien landmark variants.
- [ ] Add alien constructs and a T4+ ancient sentinel encounter where appropriate.
- [ ] Smoke test + commit

### Phase 5: Investigation-gated finale

- [ ] Track discoveries as explicit persistent story flags, not inferred from dialogue text.
- [ ] Define the evidence required for Destroy, Return to Sleep, Redirect, and Collapse the Route.
- [ ] Add alien technology that improves survival while increasing network visibility or risk.
- [ ] Build the multi-stage black-hole approach and regulator encounter.
- [ ] Build the final monster space battle.
- [ ] Present an explicit resolution choice and persist the selected outcome.
- [ ] Replace the old claim-based epilogue logic with accumulated evidence/support plus final choice.
- [ ] Set `main_quest_complete` and confirm the sandbox continues.
- [ ] Smoke test + commit

### Phase 6: Main quest UI, guide, and final polish

- [ ] Add or refine the "Main Quest" section in the quest log — breadcrumbs only; mysteries remain discoverable.
- [ ] Show discovered evidence and available resolutions without spoiling undiscovered interpretations.
- [x] Keep the in-game guide current for the shipped Act 0 chains and Act 1 prison entry.
- [ ] Update the guide for post-prison translation, blockade paths, alien technology risk, and final resolutions.
- [ ] Full playtest: prologue → prison descent/extraction/ascent → translation → disclosure → blockade plan → dead network → black-hole finale.
- [ ] DRY/RNG/save-load audit

## Pre-implementation audit — post-prison story expansion

This audit is the living pre-implementation contract for Phases 2-5. It was completed before writing the next post-prison implementation.

### Existing modules and patterns to reuse

- `src/spacehack/main_quest/` — split core, dialogue, objective, gate, heat, and Act 0 helpers; extend the existing step lifecycle rather than creating a parallel quest system.
- `src/spacehack/data/main_quest/` — frozen data-first step catalogs; add post-prison steps and evidence requirements as data.
- `src/spacehack/game_context.py` + `src/spacehack/saveload.py` — existing persistent quest fields; every new discovery, crossing-plan, resolution, and ending field must be serialized and restored.
- `src/spacehack/npc.py` and `main_quest/_dialogue.py` — quest-aware NPC dialogue and option rows; reuse for Research Officers, Blockade Officer, faction disclosure, and final interpretation scenes.
- `src/spacehack/main_quest/_objectives.py` — existing talk, delve, smuggle, visit, bounty, salvage, and bump objective patterns; extend only when a new objective cannot be expressed by composition.
- `src/spacehack/dungeon_extensions.py` and `src/spacehack/data/dungeon_extensions/` — persistent themed extensions, activation events, landmarks, and data-defined variants; reuse for dead-network interiors and rare landmark variants.
- `src/spacehack/landmark.py` plus `data/landmarks/` — authored landmark stamping into procedural maps; use for relay, archive, regulator, and refuge locations.
- `src/spacehack/npc_ships.py`, `src/spacehack/combat/`, and `data/npc_ships/` — space encounter spawning and combat; add ancient constructs through the existing ship/entity contracts.
- `src/spacehack/navigation.py` and `src/spacehack/solar_system.py` — system entry, hidden gates, static encounters, and route transitions; reuse rather than adding a second travel graph.
- `src/spacehack/help.py` — the in-game guide contract; every shipped player-facing story mechanic needs an accurate section.

### Duplication hotspots and DRY strategy

1. **Post-prison step progression:** Do not create a second research or evidence state machine. Extend `MainQuestStep`, the existing objective helpers, and `main_quest_progress` with data-defined evidence flags.
2. **Alien system/landmark generation:** Do not copy the Mars/prison stamping or surface-delve placement blocks for every dead system. Extract or parameterize shared landmark placement and persistence helpers, with data-defined themes and weighted variants.
3. **Final encounter and faction support:** Do not duplicate blockade, bounty, or combat spawning logic for every faction and resolution. Use a data-defined encounter/requirement table and shared handlers; keep pure resolution eligibility separate from mutation of `GameContext`.

### Guardrails for the next implementation

- New story state goes through `GameContext`, never module-level globals.
- New alien content belongs in frozen `data/` catalogs.
- Pure evidence/eligibility calculations receive explicit inputs and ship tests in the same commit.
- Any mutable discovery, equipment signature, crossing-plan, or resolution state must survive save/load.
- Every new player-facing mechanic updates `_GUIDE_MAIN_QUEST`.
- No implementation begins until the specific Phase 2 step and its playtest checklist are approved.

## Contracts compliance (MANDATORY — see knowledge.md)

- [x] **Save/load:** existing Act 0 and prison fields (`main_quest_progress`, `main_quest_unlocked_items`, `main_quest_chain`, `main_quest_gate`, `main_quest_pending_message`, `main_quest_path`, `main_quest_backing`, `main_quest_complete`) are wired through `_ctx_to_dict()` and `load_game()`; entity flags and prison extension state are persisted. The post-extraction trigger `prison_data_extracted` lives in persisted `DungeonExtensionState.state_flags`, not in `GameContext` or `main_quest_progress`.
- [x] **Game guide:** `_GUIDE_MAIN_QUEST` is current for the shipped Act 0 chains and Act 1 prison descent/ascent.
- [x] **NPC spawns:** existing quest-tagged bounty/salvage spawns use `BountySpawn` with cleanup on completion.
- [x] **Post-prison story state (first beat):** the Mars-orbit disclosure choice (`main_quest_disclosure`) and one-time scene flag (`post_prison_orbit_seen`) are wired through `_ctx_to_dict()` and `load_game()`; the existing `DungeonExtensionState.state_flags` extraction trigger remains canonical.
- [x] **Post-prison guide (first beat):** `_GUIDE_MAIN_QUEST` explains the Mars-orbit response and the three disclosure choices. Translation, blockade-plan consequences, dead-network systems, warnings, and final resolutions remain future work.

## Open questions

1. **Exact translated wording:** what human-readable fragments appear first, and which phrase becomes the recurring warning?
2. **Faction disclosure:** does the player choose one recipient, distribute partial copies, or negotiate different truths with each faction?
3. **Dead-network geography:** how many systems should Act 3 contain before the black-hole refuge, and which systems are mandatory versus dig content?
4. **Alien technology:** which upgrades improve survival while increasing the player's detectable prison/network signature?
5. **Creature communication:** does the player receive direct signals from the sleeping creature, or only infer its perspective from alien records?
6. **Resolution evidence:** what exact discovery unlocks Destroy, Return to Sleep, Redirect, and Collapse the Route?
7. **Ending world-state:** which resolutions alter the blockade, alien technology access, faction reputation, and post-finale sandbox?
8. ~~**What is behind the Mars door?**~~ **RESOLVED:** an empty ancient alien prison with technology beyond human capability and a layered data archive.
9. ~~**What opens the Mars door?**~~ **RESOLVED:** the player chooses a faction in Act 0; militia breach charge, merchant cutter, bar brute-force rig, and lab resonance key each open it differently.
10. ~~**Game continues after Act 3**~~ **RESOLVED:** the story reaches a definitive resolution, then the sandbox continues.
11. ~~**No time pressure or fail states**~~ **RESOLVED:** the quest waits forever; investigation and resolution choices are not deadlines.
