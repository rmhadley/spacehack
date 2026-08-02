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
    option_label: str = ""                 # menu option text when this dialogue is live
                                             # (e.g. "Tell me about the door"); empty =
                                             # no quest option row shown for this NPC
    backing_faction: str = ""              # faction claim planted when this dialogue
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
    dialogues: tuple[QuestDialogue, ...] = ()  # per-NPC dialogue overrides
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
- `main_quest_backing: set[str]` — faction claim flags planted by backing quests (see Act 3 epilogue resolution)
- `main_quest_complete: bool = False` — set when Act 3 resolves (definitive ending; sandbox continues)

### New fields on `PlanetSpec`
- `main_quest_flavor: str = ""` — lore line shown on landing

## Story outline (3 acts)

### Act 0: Prologue — "The Door on Mars"

The player receives a garbled transmission as they jump out of Sol for the first time. It points to a location on Mars. They explore Mars, find a sealed entrance to *something*, and can't get it open — then they seek help from NPCs across the sector. Act 0 ends when the player returns with the right knowledge/tools to open it.

**The Mars door is alien tech — the same kind as the Act 3 structure, but dormant.** The Act 3 structure is the *active, failing* seal; the Mars door is a *sealed, dormant* example of the same technology. It won't open with any human tool. This seeds the through-line: the player learns how the seal tech works here, and understands (and resolves) the failing seal at the end of the story. The two must NOT be conflated mechanically — the Mars door opens only with the right tool; the Act 3 structure opens on a cycle (M4's "door that opens on a cycle" refers to the Act 3 structure, not the Mars door).

**Behind the door: an empty ancient alien prison.** Inside are technology beyond any known human tech and a cache of data that needs to be translated and studied. The cell is **empty** — whatever it held is long gone, or was never there, or got out. This is a deliberate ambiguity the Act 3 reveal pays off (is what's pressing on the failing seal the same thing the prison was built to hold?). The recovered data is the **fuel for Act 1's research trail** — the player carries it to the science stations, which is why the Research Officers take the player seriously.

**Opening the door is a faction choice.** The player picks which faction helps them; *how* the door opens changes with that choice (see the table below). Choosing a faction plants that faction's claim early (the first claim — non-binding, "last claim wins" still decides the Act 3 epilogue), and colors how the rest of the story treats the player. Consistent with the rest of the game, no faction ever *refuses* to help — standing only changes the flavor and side terms, never access.

| Step | Trigger | Giver | Description |
|------|---------|-------|-------------|
| `prologue_signal` | First jump out of Sol | None | Garbled transmission on an unknown frequency — static, a burst of coordinates, then cut off. It points to a location on Mars. The player is the only one who seems to have heard it. **Delivered as a full-screen "INCOMING TRANSMISSION" comms overlay** (ENTER to acknowledge) as the player emerges in the destination system — the signal arrives through the comms, not just log lines. |
| `prologue_mars_unlocked` | Signal received (auto) | None (checkpoint) | **Mars surface exploration unlocks.** (Today Mars is *always* explorable — see the gate note below.) |
| `prologue_mars_entrance` | Explore the Mars surface | Mars (dungeon) | Among the red-dust ruins the player finds the entrance to something — a sealed door of alien make, no visible mechanism, older than the colony. It will not open. |
| `prologue_seek_help` | Talk to NPCs about the door | Any of several | The player begins looking for help. Each faction NPC gives a DIFFERENT lead (faction fork seeds here): Barkeep (bar): "Heard about the thing in the dust? The militia sealed it — or *someone* did." Trade Marshal (merchants): "Alien tech? That's the most valuable cargo in history. Bring me proof." Mars Patrol (militia): "There is no door. Whatever you saw, forget it." Research Officer (lab): "A sealed structure? I need to study it. Bring me a sample of the material." The lab lead is found at a **science station** (Alpha Centauri Science Port, Mercury, Sirius, Procyon C) — Mars has no lab building, so the lab read is the one that pulls the player off-world (which feeds into Act 1's research trail). Dialogue is keyed by `npc_id`, so seek-help lines surface on whichever planet the player talks to the NPC (Earth or Mars variants of `barkeep`/`guild_master`/`militia_captain` share ids — intended).

  **LOCK-IN on accept (user decision):** accepting a faction's help commits the player to that faction's chain — `ctx.main_quest_chain` is set, the faction's tool is NOT yet granted, and the other three factions' "Ask about the Mars door" option rows close (their dialogues resolve to a locked/"you already have a way in" variant; they still offer normal work). The chain's 5 steps must ALL be completed before the door can open. |
| `prologue_open` | Return to Mars after completing the chosen faction's 5-step chain | None (auto) | Act 0 ends when the player completes the faction chain (final step unlocks the faction's tool) and opens the entrance — revealing the empty prison and its data. The chosen faction's claim is planted (first claim). |

**Reward:** The door opens. The prison's data recovered (fuels Act 1). The chosen faction's claim is planted early. Faction fork is seeded (each NPC's lead points a different direction).

**Faction opening methods — "the player picks who helps them":**

| Faction | How the door opens | What they ask in return | Flavor |
|---------|--------------------|-------------------------|--------|
| **Militia** | Classified schematics + a military breach charge — they've seen this tech before ("the incident"). | Silence. The operation stays off the books. | The public face (Mars Patrol) denies the door exists; the schematics come from a **ranked contact off the books** — the player must first prove they've seen the door (or earn the patrol's trust) before the real lead opens up. |
| **Merchants** | A salvager's cutter tuned to alien alloys. | A trade contract — first rights to anything inside. | "Money buys the right tool. Sign here, and the cutter's yours — I want first look at what's inside." |
| **Bar / pirates** | A rig that brute-forces the seal's power feed (an old smuggler cracked a door like this once). | A cut of whatever's valuable — and the story, for the bar. | "There was a guy got a door like that open once. Cost him a hand. Here's how he did it." |
| **Lab** | The resonance key — studying a sample of the door's material produced a frequency that opens it. | A sample from inside, for study. | "We analyzed the material you brought. The door responds to a specific resonance. Take the key." |

### Faction quest chains — the seek-help fork becomes 20 quests

The tools are not handed out for free anymore. Accepting a faction's help starts that faction's **5-step chain**; the tool (and therefore `prologue_open`) unlocks only when the chain is complete. Every chain mixes the mechanics the game already has — **procedural surface dungeons** (cave delves for the materials), distant-planet expert recruitment, space combat (bounty spawns), derelict boarding (salvage interiors), and a final assembly beat. Only the bar chain keeps a small goods payment (a bribe to the old smuggler, not a supply run). Each chain's final step plants the faction tool + makes `prologue_open` available.

**Chain anatomy (5 steps each):** `q1` commitment/lead → `q2` materials (delve: secure a quest cache from a planet's procedural surface cave — the item is *found*, not bought) → `q3` expert recruitment (new NPC on a distant planet) → `q4` field test (bounty combat OR derelict salvage) → `q5` assembly (tool unlocked → door opens).

**Time gating between every step:** each completed step logs faction flavor ("We'll be in touch." / "We need time to research this.") and starts a **minimum-wait gate** (`wait_days`, world clock — see the Time gating section). When the clock passes the gate, the faction sends a **one-way auto-message summoning the player** to the NEXT step's system + planet (each step picks its own location — never a requirement to repeat the previous one). **Chain pacing target (locked): one chain ≈ 425 in-game days total (gates ~340d + travel ~85d) = 5× the 85-day Earth→Luyten one-way trip.**

#### Militia — "The Incident" (breach charge)

| Step | Objective | What the player must do | Rewards |
|------|-----------|-------------------------|---------|
| `mil_q1_report` | talk | Report to the Militia Captain (Earth) — off the books, he admits the patrol saw "the incident" tech before. The requisition is buried in a scrubbed cache. | 50 XP |
| `mil_q2_cache` | delve | Descend into the **Mercury** surface caves (procedural dungeon) and secure the classified requisition cache: `ship_components` ×4 + `fuel_cells` ×2 (found, not bought) | 100 credits, 80 XP |
| `mil_q3_demolitions` | visit | Recruit the `demolitions_expert` at **Epsilon Eridani b** (he signs on when the Captain's name is dropped) | 60 XP |
| `mil_q4_livefire` | bounty | Clear the pirate scout squad in Cygni (quest bounty spawn, 2 scouts) to prove the charge works | 150 credits, 120 XP |
| `mil_q5_charge` | talk | Return to the Captain — the breach charge is assembled → `militia_breach_charge` + `prologue_open` | 200 credits, 150 XP |

**Gating:** q1→q2 60d · q2→q3 80d · q3→q4 120d · q4→q5 80d (sum 340d ≈ 5× the 85d Earth→Luyten trip incl. travel; see Time gating). Completion flavor: "We'll be in touch. Requisition takes time to clear." / "Inspection underway." / "The charge needs a live-fire test." / "Return to base — the charge is assembled." Summons: Mercury (q2), Epsilon Eridani b (q3), Cygni (q4), Earth (q5).

#### Merchants — "The Contract" (cutter)

| Step | Objective | What the player must do | Rewards |
|------|-----------|-------------------------|---------|
| `mer_q1_contract` | talk | Sign the contract with the Guild Master (Earth) — first rights to what's inside | 50 XP |
| `mer_q2_strike` | delve | The escrow ore is in the Guild's abandoned prospecting claim — descend into the **Wolf 359** surface caves (procedural dungeon) and secure quest-tagged `rare_earth_metals` ×3 | 100 credits, 80 XP |
| `mer_q3_specialist` | visit | Recruit the `salvage_specialist` at **Tau Ceti b** (he signs after the claim rumor reaches him) | 60 XP |
| `mer_q4_calibration` | salvage | Calibration run: board a derelict near Vega (`scout_a` layout), recover the quest-tagged `machine_parts` | 150 credits, 120 XP |
| `mer_q5_cutter` | talk | Return to the Guild Master — the cutter is ready → `merchant_cutter` + `prologue_open` | 200 credits, 150 XP |

**Gating:** q1→q2 60d · q2→q3 90d · q3→q4 110d · q4→q5 80d (sum 340d ≈ 5× the 85d Earth→Luyten trip incl. travel; see Time gating). Completion flavor: "Contract filed. We need time to arrange the escrow." / "Ore appraised. The specialist wants to hear it from you." / "The cutter needs a calibration run." / "The cutter is ready." Summons: Wolf 359 (q2), Tau Ceti b (q3), Vega (q4), Earth (q5).

#### Bar — "The Old Hand" (brute rig)

| Step | Objective | What the player must do | Rewards |
|------|-----------|-------------------------|---------|
| `bar_q1_oldhand` | talk | The Barkeep (Earth) names the old smuggler who cracked a door "once. Cost him a hand." **He warns: the militia has been sniffing around the old routes since "the incident" — work with the smuggler and you'll be on their radar.** | 50 XP |
| `bar_q2_proof` | smuggle | The old smuggler won't deal with strangers. The Barkeep hands you a **hot crate** — `weapons_blackmarket` ×8, loaded into the mission hold exactly like a smuggling mission (`is_smuggle`). Run it to the `old_smuggler` at **Barnard's Star b**. Every militia patrol on the way can scan it (rep-gated chance; Smuggler's Hold conceals it, mission-first). **Confiscated = the step fails — return to the Barkeep to re-claim his last crate (he grumbles).** | 100 credits, 80 XP, +2 pirate / -5 merchant / -5 civilian / -8 militia |
| `bar_q3_rigparts` | delve | The old smuggler draws the cave where the old job went wrong — the rig's power cell is still there. Descend into the **Barnard's Star b** surface caves (procedural dungeon) and recover it. **MILITIA HEAT (see below): while the cell is in your hold it counts as contraband and scan chance is elevated — it's militia-issue hardware.** | 60 XP |
| `bar_q4_gauntlet` | bounty | **The militia seals the Barnard's Star gate** — you can't jump out clean with the cell. A militia patrol intercepts you (quest-tagged spawn): fight (destroying militia ships = **-12 militia rep each**) or flee (another scan roll). Survive → the cell's power feed is proven to hold. | 150 credits, 120 XP |
| `bar_q5_rig` | talk | Return to the Barkeep — the rig is assembled → `bar_brute_rig` + `prologue_open`. "The militia will be watching you from here on, friend. Welcome to the family." | 200 credits, 150 XP |

**Militia heat (bar chain signature risk):** while `ctx.main_quest_chain == "bar"` AND the player is holding hot quest cargo (the `bar_q2` crate or the `bar_q3` cell), `_militia_scan_chance()` applies a **+30% floor** (min 60%, capped 80%) on every militia-patrolled system — the militia knows the player is working the old routes. The hook is one gate in `navigation._militia_scan_chance` on `ctx.main_quest_chain` + a cargo-presence check; it auto-expires at `bar_q5`. Consequences are the real smuggler economy: confiscation (goods lost + fine + -5 militia rep), combat (rep tank), or paying for a Smuggler's Hold to reduce exposure.

**Gating:** q1→q2 65d · q2→q3 85d · q3→q4 110d · q4→q5 80d (sum 340d ≈ 5× the 85d Earth→Luyten trip incl. travel; see Time gating). Completion flavor: "The old man is cagey — he'll see you for the right price." / "He drew the cave. Meet him at the dig." / "The militia is sealing the gate. Run now." / "The rig's assembled. Come raise a glass." Summons: Barnard's Star b (q2), Barnard's Star b — the caves (q3), Barnard's Star gate (q4), Earth (q5).

#### Lab — "The Resonance" (resonance key)

| Step | Objective | What the player must do | Rewards |
|------|-----------|-------------------------|---------|
| `lab_q1_sample` | bump | Return to Mars and chip a material sample off the door (chain-aware door bump — the door stays sealed) | 50 XP |
| `lab_q2_reference` | delve | The Mercury officer needs a reference resonance dataset — it's in a sealed research cache in the **Procyon C** surface caves (procedural dungeon); descend and secure quest-tagged `research_data` ×2 | 100 credits, 80 XP |
| `lab_q3_xenolinguist` | visit | Recruit the `xenolinguist` at **Alpha Centauri Science Port** (`ac_station`) | 60 XP |
| `lab_q4_frequency` | salvage | Recover the reference-frequency dataset (`research_data`) from a derelict near Sirius (`scout_a`) | 150 credits, 120 XP |
| `lab_q5_key` | talk | Return to the Mercury Research Officer — the resonance key is forged → `lab_resonance_key` + `prologue_open` | 200 credits, 150 XP |

**Gating:** q1→q2 50d · q2→q3 115d · q3→q4 95d · q4→q5 80d (sum 340d ≈ 5× the 85d Earth→Luyten trip incl. travel; see Time gating). Completion flavor: "Sample received. We need time to analyze it." / "Reference dataset locked. The linguist wants in." / "The frequency map is incomplete — one more dataset." / "The key is forged." Summons: Mercury (q2), Alpha Centauri Science Port (q3), Sirius (q4), Mercury (q5).

**Expert NPCs (new catalog entries):** `demolitions_expert` (militia, Epsilon Eridani b), `salvage_specialist` (merchants, Tau Ceti b), `old_smuggler` (bar, Barnard's Star b), `xenolinguist` (lab, ac_station). Each is a new entry in the global `data/npcs` catalog placed via `PlanetSpec.npc_overrides` on a planet that already has the matching guild building (`militia_captain` / `guild_master` / `barkeep` / `research_officer` slot) — the override's `id` differs from the replaced slot so quest dialogue keys off the expert id. Verify the target planet has the required guild building (add a `CityBuilding` to the spec if not).

**New objective types** complete steps outside the dialogue path: `delve` (descend into the target planet's **procedural surface cave** and secure the quest-tagged cache — the item is *found*, not bought), `smuggle` (deliver hot cargo to a target NPC — loaded into the mission hold like a `is_smuggle` mission; militia scans can confiscate it and fail the step), `goods` (cargo check + consume on trigger), `visit` (talk to the expert NPC at a target planet → step completes), `bounty` (quest-tagged `BountySpawn` defeated → step completes), `salvage` (quest-tagged loot secured in a derelict interior → step completes), `bump` (door bump variant, e.g. lab sample). See the data-model section below.

**Delve sites (reuse the Mars surface dungeon):** each chain's materials step sends the player into a **procedural surface cave** — the same BSP generator that builds the Mars surface (`dungeon.generate_dungeon` + `PlanetSpec.dungeon_params` with a planet-themed tile set, exactly like `data/planets/mars.py`). The four delve planets (Mercury, Wolf 359, Barnard's Star b, Procyon C) currently lack `dungeon_params` — adding it is **pure data** (the generator, `has_explorable_sites`, and planet-menu "Explore" option already exist). The site persists in `ctx.interiors` keyed `surface:<planet_id>` (same anti-farm rule as the Mars surface + salvage wrecks; `saveload` already serializes the whole cache generically). The quest cache is placed by a generic `prepare_delve_site` pass after generation — **extract `prepare_mars_surface`'s placement logic into a shared helper** (no copy-paste). The planet menu shows "Explore <site>" only while the chain's delve step is active (chain-aware gate, same pattern as the Mars signal gate in `menus/_planet.py`).

**Time gating & one-way summons (the world-clock hook):** every chain step gets `wait_days` (world clock, ~50-120d ≈ 2-4 in-game MONTHS per gate — deliberately long so each gap is a deep sandbox window: missions, trade, XP, ship upgrades). **Target math (locked): Earth→Luyten's Star = 5 hops ≈ 85d one-way at starter speed (Skiff 10 moves/day, per `data/missions/bar.py` Luyten missions). 5× = ~425d per chain. Gates sum ~340d; the ~85d of inter-step travel completes the 425.** Mechanics:

1. **On step completion:** log the `completion_flavor` ("We'll be in touch.", "We need time to research this.") and record a gate date via the pure helper `time.add_days_to_date(ctx.time_day, ctx.time_month, ctx.time_year, wait_days)` into `ctx.main_quest_gate[next_step_id]`.
2. **Per-frame check:** `main_quest.check_quest_gates(ctx)` runs in the main loop (same delivery pattern as militia auto-hails): when `ctx.time_*` >= a gate date, the next step flips to `"available"` and the faction's `ready_message` (one-way summon naming the next step's `trigger_system_id` + `trigger_planet_id`) is queued as a **one-way incoming-comms overlay** (reuse the `show_prologue_transmission` modal — no reply option).
3. **Minimum wait, never a deadline:** the gate only *unlocks* the next step — the player may answer the summon days, weeks, or months later (gates are 50-120d) with zero penalty. Nothing expires, no fail state. The quest log breadcrumb reads "Awaiting word from the <faction>..." while a gate is pending.
4. **Save/load:** `main_quest_gate` + `main_quest_pending_message` serialize/deserialize with the other main-quest fields (contract below) — a summon mid-flight survives a save/quit/continue.

**Mars exploration gate (implementation note):** `data/planets.has_explorable_sites("mars")` returns `["signal"]` (from `PlanetSpec.explorable_site_name`) whenever `dungeon_params` exists, so the planet menu offers "Explore signal" rather than a generic "Explore Surface". Act 0 requires gating this on `prologue_signal`: before the transmission, the Mars planet menu shows no Explore option (or a locked "??" entry). See Phase 1.

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

- [x] Add the sealed entrance to the Mars surface (deterministic placement AFTER `generate_dungeon` — e.g. farthest walkable cell from spawn, or a landmark room). The door is a `main_quest_door` entity: alien make, unopenable until the player holds the right tool. **The Mars surface dungeon persists across visits** (cached in `ctx.interiors` keyed `surface:mars` — same anti-farm rule as salvage wreck interiors): the door stays exactly where it was found, fog stays revealed, and `prepare_mars_surface` runs only on first generation.
- [x] Bump interaction on the door: before `prologue_open` — "sealed, alien make, no mechanism" + start `prologue_mars_entrance`; with the faction tool — opens, reveals the empty prison + data, plants the claim, Act 1 begins. **The two quest-beat bumps (discover + open) surface as full-screen overlays** (`main_quest.show_sealed_door_overlay`) — the same `ui.Modal` interruption pattern as the incoming transmission, with alien-rune static and ASCII door art. Repeat bumps stay as log lines only (no modal nag).
- [x] Wire `prologue_seek_help`: each faction NPC's quest dialogue gives its unique lead and (on trigger) plants `backing_faction` + unlocks the tool item. **The offer surfaces as its own full-screen modal** (`main_quest.show_help_offer`) when the player picks the "Ask about the Mars door" option row — the talk modal stays short (normal flavor + the option row), and the offer modal shows the NPC's full lead (word-wrapped, never truncated) with **Accept help** / **Keep looking** options. Keep looking loops back to the talk modal; Accept runs `trigger_dialogue`.
- [x] Wire `prologue_open` completion: returning with the right knowledge/tool opens the door, logs the prison reveal
- [x] Minimal quest-log breadcrumb: "MAIN QUEST" section showing current step title + objective (full UI polish stays in Phase 4)
- [x] Smoke test + commit

**PLAYTEST (1c):** full Act 0 run — receive signal → explore Mars ("Explore signal") → find the sealed door (bump it, can't open — a SEALED ENTRANCE overlay pops up with alien runes + door art, ENTER dismisses) → talk to each faction NPC (talk modal shows normal flavor + the gold "Ask about the Mars door" row — no more truncated/quoted lead in the body; picking the row opens an AN OFFER OF HELP modal with the NPC's full lead, word-wrapped, plus Accept help / Keep looking) → pick Accept on one faction (claim planted, tool unlocked) → return to Mars → the SAME surface map reloads (door where you left it, fog still revealed) → bump the door → THE SEAL GIVES WAY overlay pops up, prison revealed, Act 1 seeds → bump it again (repeat) → log line only, no modal. Also test Keep looking on a second faction (returns to the talk modal; you can walk away). Verify quest log (Q) tracks each step. Save/quit/continue mid-Act-0 → state preserved (including the persisted surface dungeon).

### Phase 1d: Chain infrastructure — lock-in, objective types, delve sites

- [x] Add `main_quest_chain` to `GameContext` + serialize/deserialize in `saveload` (save/load contract)
- [x] Add chain objective fields to `MainQuestStep` (`objective_type`, `requires_goods`, `requires_npc_id`, `requires_spawn_id`, `delve_good_ids`)
- [x] Implement objective completion in `main_quest.py`: `delve` (secure the quest cache in the planet's surface dungeon → completes), `goods` (cargo check + consume on trigger), `visit` (talk to expert NPC → completes), `bounty` (quest-tagged spawn defeated → completes), `salvage` (quest-tagged loot secured → completes), `bump` (door bump variant)
- [x] **Delve site generator:** extract `prepare_mars_surface`'s post-generation placement logic into a shared helper (`prepare_delve_site`) that runs after `generate_dungeon` — places the quest cache (a quest-tagged `loot_data` container with `delve_good_ids`) in a deep room, caches the map in `ctx.interiors` keyed `surface:<planet_id>` (DRY — no copy-paste of the Mars placement block)
- [x] Add `dungeon_params` (planet-themed tiles) to the 4 delve planets: Mercury, Wolf 359, Barnard's Star b, Procyon C (pure data, mirroring `data/planets/mars.py`)
- [x] Chain-aware planet-menu gate: "Explore <site>" shows only while the chain's delve step is active (extend the Mars signal gate in `menus/_planet.py` to take the active chain into account)
- [x] Lock-in flow: Accept help in `show_help_offer` sets `main_quest_chain` (instead of unlocking the tool); the other three factions' "Ask about the Mars door" rows close (locked variant dialogue)
- [x] Chain completion: final step's trigger grants the faction tool + makes `prologue_open` available
- [x] **Time-gate infra:** add `wait_days` / `completion_flavor` / `ready_message` to `MainQuestStep`; add `main_quest_gate` + `main_quest_pending_message` to `GameContext` + serialize/deserialize in `saveload`; implement `main_quest.check_quest_gates(ctx)` per-frame hook (fires when `ctx.time_*` passes a gate date → next step `"available"` + queue the one-way summon; deliver via the prologue-transmission overlay pattern). Dev skip-days helper: Shift+D (SPACEHACK_DEV) advances 30 days so gates can be playtested. Quest log shows "Awaiting word from the <faction>..." while a gate is pending.
- [x] Add the 4 expert NPCs (`demolitions_expert` / `salvage_specialist` / `old_smuggler` / `xenolinguist`) to `data/npcs` + `PlanetSpec.npc_overrides`; verify target planets have the guild building
- [x] Smoke test + commit

**PLAYTEST (1d):** fresh save → discover the door → talk to each faction NPC (all four offers still open, no lock-in yet) → Accept militia help → the other three NPCs now show a locked/"you already have a way in" variant (no quest row) → confirm `main_quest_chain` survives save/quit/continue → start a NEW game and Accept merchants instead (different chain). Test the `delve` objective end-to-end: while `mil_q2_cache` is active the Mercury planet menu shows "Explore <site>" → descend into the procedurally generated Mercury cave (planet-themed tiles, fog works) → find the quest-tagged cache in a deep room → secure it (cargo gained, step completes) → the cave persists in `ctx.interiors` across save/quit/continue (anti-farm). Test the gate: complete a chain step → flavor "We'll be in touch." logged → dev-mode skip past `wait_days` → one-way summon overlay arrives naming the next step's location → quest log reads "Awaiting word from..." while pending.

### Phase 1e: Militia chain — "The Incident" (breach charge)

- [ ] Write `mil_q1_report` → `mil_q5_charge` as step data (talk / delve / visit / bounty / talk)
- [ ] Wire `mil_q2_cache` delve site on Mercury (cache yields `ship_components` ×4 + `fuel_cells` ×2)
- [ ] Write the militia gates (`wait_days` 60/80/120/80, completion flavor, summons per the chain table)
- [ ] Wire `mil_q4_livefire` quest-tagged bounty spawn (Cygni scout squad, 2 scouts)
- [ ] Wire `mil_q5_charge` trigger → grants `militia_breach_charge` + `prologue_open`
- [ ] Smoke test + commit

**PLAYTEST (1e):** full militia run — report to the Captain → fly to Mercury, descend into the caves, secure the requisition cache (delve completes; goods land in cargo) → recruit the demolitions expert at Epsilon Eridani b (visit completes) → clear the Cygni scout squad (bounty completes; verify it spawns only while the step is active) → return to the Captain → charge granted + door opens. Check quest log (Q) tracks each step; save/quit/continue mid-chain preserves progress (including the persisted Mercury cave).

### Phase 1f: Merchants chain — "The Contract" (cutter)

- [ ] Write `mer_q1_contract` → `mer_q5_cutter` as step data (talk / delve / visit / salvage / talk)
- [ ] Wire `mer_q2_strike` delve site on Wolf 359 (cache yields quest-tagged `rare_earth_metals` ×3)
- [ ] Write the merchant gates (`wait_days` 60/90/110/80, completion flavor, summons per the chain table)
- [ ] Wire `mer_q4_calibration` quest-tagged salvage (derelict near Vega, `scout_a` layout, `machine_parts`)
- [ ] Wire `mer_q5_cutter` trigger → grants `merchant_cutter` + `prologue_open`
- [ ] Smoke test + commit

**PLAYTEST (1f):** full merchant run — sign the contract → fly to Wolf 359, descend into the claim caves, secure the escrow ore (delve completes) → recruit the salvage specialist at Tau Ceti b (visit) → board the Vega derelict, secure the tagged `machine_parts` (salvage completes) → return → cutter granted + door opens. Verify the derelict interior + Wolf 359 cave both persist across visits (anti-farm rule) and the tagged loot only appears while the step is active.

### Phase 1g: Bar chain — "The Old Hand" (brute rig, blackmarket + militia heat)

- [ ] Write `bar_q1_oldhand` → `bar_q5_rig` as step data (talk / smuggle / delve / bounty / talk)
- [ ] Implement the `smuggle` objective: hot crate loaded into the mission hold (`is_smuggle` semantics — `smuggle_good_id` + `smuggle_cargo_size`), delivered to the `old_smuggler` NPC; militia scan confiscation fails the step (re-claim from the Barkeep)
- [ ] Wire `bar_q3_rigparts` delve site on Barnard's Star b (cache yields `machine_parts` + `electronics` — the rig's power cell, flagged as contraband while carried)
- [ ] Write the bar gates (`wait_days` 65/85/110/80, completion flavor, summons per the chain table)
- [ ] **Militia heat hook:** in `navigation._militia_scan_chance`, apply the +30% floor (min 60%, cap 80%) while `ctx.main_quest_chain == "bar"` and hot quest cargo is held; auto-expire at `bar_q5`
- [ ] Wire `bar_q4_gauntlet` quest-tagged **militia patrol** spawn (not pirate — rep stakes are the point: -12 militia per kill; flee keeps the scan risk)
- [ ] Wire `bar_q5_rig` trigger → grants `bar_brute_rig` + `prologue_open`
- [ ] Smoke test + commit

**PLAYTEST (1g):** full bar run — the Barkeep names the old smuggler (warns about militia interest) → pick up the hot crate → fly to Barnard's Star b: **militia patrols scan more aggressively than normal** (scan chance floor active — verify vs. a non-bar save) → deliver to the smuggler (smuggle completes) → he draws the cave → descend, recover the power cell (delve completes; cell is hot cargo now) → the Barnard's Star gate is sealed by a **militia patrol** — fight (militia rep tanks) or flee (another scan) → return to the Barkeep → rig granted + door opens. Deliberately fail `bar_q2` once: get scanned, crate confiscated, step fails, Barkeep re-offers his last crate. Barkeep dialogue stays in-character (tall tales, not exposition).

### Phase 1h: Lab chain — "The Resonance" (resonance key)

- [ ] Write `lab_q1_sample` → `lab_q5_key` as step data (bump / delve / visit / salvage / talk)
- [ ] Wire `lab_q1_sample` chain-aware door bump (chip a sample; does NOT open the door)
- [ ] Wire `lab_q2_reference` delve site on Procyon C (cache yields quest-tagged `research_data` ×2)
- [ ] Write the lab gates (`wait_days` 50/115/95/80, completion flavor, summons per the chain table)
- [ ] Wire `lab_q4_frequency` quest-tagged salvage (derelict near Sirius, `scout_a`, `research_data`)
- [ ] Wire `lab_q5_key` trigger → grants `lab_resonance_key` + `prologue_open`
- [ ] Smoke test + commit

**PLAYTEST (1h):** full lab run — bump the door to chip the sample (door stays sealed; no tool yet) → fly to Procyon C, descend into the caves, secure the reference dataset (delve completes) → recruit the xenolinguist at Alpha Centauri Science Port (visit) → recover the frequency dataset from the Sirius derelict (salvage) → return to Mercury → key granted + door opens. Verify the sample chip doesn't accidentally open the door early.

### Phase 1i: Act 0 integration + lock-in polish

- [ ] Full 4-chain regression: run all four chains end-to-end on separate saves to `prologue_open`
- [ ] Verify lock-in exclusivity: after accepting one faction, the other three offer rows stay closed even across save/load
- [ ] Verify `prologue_open` completion plants the claim + recovers the prison data (existing 1c behavior) on ALL four tool types
- [ ] Balance pass: delve cache yields vs. early-game cargo capacity; cave size/placement difficulty (cache must be reachable without combat gear); bounty difficulty vs. expected level at that point; gate lengths feel like pacing, not padding
- [ ] Smoke test + commit

**PLAYTEST (1i):** one save per faction, full chain runs. Then the cross-check: accept a chain, save, quit, continue — lock-in holds, chain step still active. Open the door with each tool — same reveal overlay, claim planted. Then ask the user: "Move Phase 1 to complete?" per the doc lifecycle.

### Phase 1j: Time gating + one-way summons (full pass)

- [ ] Verify every gate fires on schedule (dev-mode skip-days helper): flavor logged on completion → gate date recorded → when the clock passes it the next step flips to `"available"` + the summon overlay arrives
- [ ] Verify the summon names the NEXT step's system + planet (which can differ from the previous step's location — e.g. militia q2 completes on Mercury, q3 summons to Epsilon Eridani b)
- [ ] Verify a summon never interrupts combat/dungeon — it queues in `main_quest_pending_message` and delivers at the next safe frame
- [ ] Verify ignoring a summon is harmless: days/weeks later the step is still there, nothing failed, no expiry
- [ ] Verify save/quit/continue mid-gate: gate date + pending message survive
- [ ] Smoke test + commit

**PLAYTEST (1j):** complete militia q1 → "We'll be in touch. Requisition takes time to clear." in the log → quest log reads "Awaiting word from the Militia..." → skip 60+ days (dev-mode) → a one-way comms overlay arrives: "Report to Mercury. The cache is mapped." → q2 unlocks and the Mercury delve site appears. Deliberately ignore a summon for 200+ days on a separate save → nothing fails; answering late works normally — the long gate (2-4 in-game months) should cover several sandbox sessions. Save during a pending gate → continue → gate intact, summon re-delivers. 

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

- [ ] **Save/load:** `main_quest_progress`, `main_quest_unlocked_items`, `main_quest_chain`, `main_quest_gate`, `main_quest_pending_message`, `main_quest_path`, `main_quest_backing`, `main_quest_complete` → added to both `_ctx_to_dict()` AND `load_game()`
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
