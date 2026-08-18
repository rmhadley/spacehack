# DESIGN: Reusable Quest System — data-driven chains + objective handler registry

> **Goal (user-stated):** "I would love to be able to quickly build out these
> quest chains myself through simple data edits." The main quest should be
> authored as pure data that chains together; the runtime becomes a small set
> of generic handlers, so a new chain is a data file and new story text —
> zero runtime edits.

## Overview

The main quest already moved most of the way toward data-driven authoring:
every step is a frozen `MainQuestStep` dataclass chained by `requires_step`,
auto-discovered from `data/main_quest/*.py`, with prose in the JSON overlay.
The four Act-0 faction chains (24 steps) are permutations of ~9 objective
types (`talk`, `delve`, `smuggle`, `goods`, `visit`, `bounty`, `salvage`,
`bump`, `prison`).

What is **not** data-driven is the runtime *dispatch*: each objective type's
behavior is implemented as if/elif chains and inline special-cases scattered
across `main_quest/_dialogue.py`, `_objectives.py`, `_spawns.py`, `_act0.py`,
and step ids are hard-coded in `_heat.py`, `_gates.py`, `_breadcrumb.py`, and
`_act1.py`. Adding a new chain today means editing runtime modules, not just
data.

This design completes the data-first story:

1. A single **objective handler registry** replaces every if/elif dispatch —
   each objective type is one cohesive handler behind one table.
2. The hard-coded **step flags** (faction heat, scene triggers, auto-load
   behavior) move onto the step data.
3. **Scene triggering** moves into quest data (a scene identifier); the scene
   implementations themselves stay in code.
4. **Quest text** (breadcrumbs, completion log lines) migrates into the JSON
   overlay, completing the migration that currently stops at Act 0.
5. A **minimal chain validator** makes bad data edits fail loudly instead of
   silently breaking a quest line (strictness deferred until the quests are
   fleshed out).

After this lands, the authoring loop for a new chain is: write a step tuple in
`data/main_quest/`, add story text to the JSON overlay, run `make check` — done.

## Status snapshot (2026-08-18)

- [x] Phase 1 — objective handler registry implemented and open regression
      playtest complete.
- [x] Phase 2 — faction heat data-ified and open heat playtest complete.
- [x] Phase 3 — scene triggering and remaining step flags data-ified; open
      scene-triggering playtest complete.
- [x] Phase 3a — quest-NPC presence data-ified; open NPC-presence playtest
      complete.
- [x] Phase 4 — quest and Mars-prison text migration plus full playtest complete.
- [x] Phase 5 — minimal validator, authoring guide, and validator playtest complete.
- [ ] Phase 6 — guide/docs review and final acceptance.

The open playtests for the completed phases (1, 2, 3, 3a, 4, and 5) are now
complete, user-confirmed. No failures or new edge cases were reported in this
update. The design remains in `in_progress/` because Phase 6 and the final
acceptance criteria are still outstanding.

## Current state (the motivation)

### Already data-driven (keep as-is)

- `MainQuestStep` / `QuestDialogue` frozen dataclasses (`data/main_quest/__init__.py`)
- Auto-discovery: drop a `.py` exporting `STEPS` into `data/main_quest/`
- Chaining via `requires_step` + `main_quest_step_after()`
- Generic lifecycle: `start_step` / `complete_step` (rewards, flavor, next-step
  scheduling, gates) in `main_quest/_core.py`
- Generic completion hooks: `_active_objective_step` / `complete_step_by_type`
- Step prose lives in the JSON overlay (`data/text/`) through Act 1 — the
  extractor (`tools/extract_act0_text.py`) syncs `step.<id>.*` keys, `runtime.*`
  keys, `disclosure.*` keys, NPC flavor, and trade-good names
- The mission hold is already a standardized subsystem (`mission/_models.py`
  `ActiveMission`: `required_cargo_size`, `delivery_target_npc_id`,
  `delivery_target_planet_id`, `target_system_id`, `is_smuggle`,
  `smuggle_good_id`, `main_quest_step_id`), and the smuggle handler
  (`_core._trigger_smuggle_crate` / `_complete_smuggle_handover`) already
  reads everything from step data — what's in the hold, how much space, who to
  deliver to, where, and whether it's confiscatable (`smuggle_hot`).

### Scattered dispatch (the problem)

| Location | What it hard-codes |
|----------|--------------------|
| `main_quest/_dialogue.py::trigger_dialogue` | if/elif over `goods` / `smuggle` / `salvage` / `visit` / `bump` / default |
| `main_quest/_dialogue.py::resolve_npc_dialogue` + `quest_option_for` | inline giver/receiver crate-gating for `smuggle` |
| `main_quest/_objectives.py::secure_quest_loot` | special-cases `delve` / `salvage` + salvage spawn cleanup |
| `main_quest/_spawns.py::ensure_quest_spawns` | special-cases `bounty` / `salvage` |
| `main_quest/_act0.py::bump_mars_door` | the `bump` beats + prologue door chain |
| `main_quest/_heat.py` | step ids `bar_q2_proof`, `bar_q4_blackmarket`, `bar_q5_charged`, `bar_q6_rig`, `mer_q3_transport`, `mer_q4_calibrate`, `mer_q5_cutter` |
| `main_quest/_gates.py` | step ids `research_alpha`, `research_alpha_report` + save migrations |
| `main_quest/_breadcrumb.py` | step ids `research_alpha_report`, `research_alpha`, `act1_prison`, `post_prison_orbit_seen`, `main_quest_complete` + hard-coded breadcrumb strings |
| `main_quest/_act0.py` | step ids `prologue_seek_help`, `lab_q1_sample` (ambush), `prologue_open`, `prologue_mars_entrance` |
| `main_quest/_act1.py` | the whole bespoke orbit-disclosure scene |

### Quest text still hard-coded in Python (the migration gap)

Step prose (titles, descriptions, dialogue, completion flavor, ready messages)
is fully in the JSON overlay through Act 1. What is **not**:

| Location | Hard-coded player-facing text |
|----------|-------------------------------|
| `main_quest/_core.py` | `"[MAIN QUEST] {title} - complete."` and `"+{N}$ reward."` completion log lines |
| `main_quest/_act0.py` | `"[MAIN QUEST] Act 1: The Prison Below - descend the facility."` prison-start log |
| `main_quest/_breadcrumb.py` | quest-log objective strings: "Awaiting word from the {faction}...", "Leave Mars", "Awaiting the first translation...", "Deliver the sealed archive", the fallback handoff text, "The faction will contact you when they're ready." |

## Design decisions (locked with the user)

| Decision | Choice |
|----------|--------|
| **Objective dispatch** | A single handler registry (`main_quest/handlers.py`): `objective_type → ObjectiveHandler`, a frozen dataclass of optional hook callables. Dispatch is a table lookup, never an if/elif chain. |
| **Handler hooks** | Uniform optional hooks: `on_trigger`, `on_complete`, `prepare_site`, `ensure_spawns`, `find_step_for_spawn`, `option_gating`, `heat`, `breadcrumb`. A handler implements only the hooks its type needs; `None` = unsupported. |
| **Faction heat** | A tuple of tags on the step, e.g. `heat=("militia_scan", "militia_aggro")` or `heat=("consortium",)`. `_heat.py` becomes a data-driven filter over `_iter_known_steps`. Expiry is implicit: the final chain step carries no heat tag. |
| **Scenes** | Scenes always need custom code, but **triggering is configured in quest data** via a scene identifier. A scene must be written in code first; the quest data names it and the runtime plays it at the step's beat. |
| **Save/load** | No shape changes. `main_quest_progress`, `main_quest_gate`, `main_quest_pending_message`, `main_quest_chain`, `main_quest_backing`, `main_quest_disclosure`, `post_prison_orbit_seen` keep their exact serialized forms. New fields are static step data (never serialized). |
| **Validator** | Minimal for now — only what prevents a broken chain (unknown objective type / unresolved `requires_step` / missing story text). No strictness (chain-termination, reward balance) until the quests are fleshed out. |
| **Quest text** | Continue the JSON migration: breadcrumbs and completion log lines move into `runtime.*` overlay keys (synced by the existing extractor). |
| **No inheritance** | Handlers are frozen dataclasses of injected callables (composition), not a class hierarchy. |

## Data model

### Extended `MainQuestStep` (new fields)

```python
@dataclass(frozen=True)
class MainQuestStep:
    # ... existing fields unchanged ...
    objective_type: str = "talk"

    # NEW — data-ified runtime flags
    heat: tuple[str, ...] = ()      # heat behavior tags, e.g. ("militia_scan",)
                                    # / ("militia_scan", "militia_aggro") / ("consortium",).
                                    # Empty = no heat. Consumed by the generic heat handler.
    scene: str = ""                 # scene identifier played at this step's primary beat
                                    # (bump / trigger / completion). Implementation lives in
                                    # main_quest/_scenes.py keyed by id — a scene must be
                                    # written in code before data can trigger it.
    auto_load_next_smuggle: bool = True  # False = do NOT auto-load the next step's crate
                                    # when it is a smuggle (currently always-on in _core).
```

### Objective handler registry

```python
# main_quest/handlers.py
@dataclass(frozen=True)
class ObjectiveHandler:
    name: str
    on_trigger: Callable[[GameContext, MainQuestStep], bool] | None = None
    on_complete: Callable[[GameContext, MainQuestStep], None] | None = None
    prepare_site: Callable[[GameContext, MainQuestStep, GameMap, Position], bool] | None = None
    ensure_spawns: Callable[[GameContext, MainQuestStep, str], bool] | None = None
    find_step_for_spawn: Callable[[GameContext, str], MainQuestStep | None] | None = None
    option_gating: Callable[[GameContext, MainQuestStep, str], bool] | None = None
    heat: Callable[[GameContext, MainQuestStep], bool] | None = None
    breadcrumb: Callable[[GameContext, MainQuestStep], tuple[str, str] | None] | None = None

_HANDLERS: dict[str, ObjectiveHandler] = {h.name: h for h in (_TALK, _DELVE, _SMUGGLE, ...)}

def handler_for(objective_type: str) -> ObjectiveHandler | None: ...
```

Dispatch sites become table lookups:

```python
def trigger_dialogue(ctx, npc_id, step_id):
    step = find_main_quest_step(step_id)
    ...
    handler = handler_for(step.objective_type)
    if handler is None or handler.on_trigger is None:
        return complete_step(ctx, step_id)          # talk default
    return handler.on_trigger(ctx, step)
```

The existing implementation functions move *unchanged* into handler modules:
`_trigger_smuggle_crate` / `_complete_smuggle_handover` → smuggle `on_trigger`;
`secure_quest_loot` → delve + salvage `on_complete`; `maybe_complete_visit` →
visit `on_trigger`; `maybe_complete_bounty` → bounty `on_complete`;
`_complete_bump_objective` → bump `on_trigger`; `prepare_delve_site` → delve
`prepare_site`; `ensure_quest_spawns` → bounty/salvage `ensure_spawns`;
`find_salvage_step_for_spawn` → salvage `find_step_for_spawn`.

### Scene registry

```python
# main_quest/_scenes.py
# Scenes are bespoke presentations written in code FIRST, then triggered by
# quest data via the step's ``scene`` identifier. A scene id with no
# implementation fails loudly (smoke/validator), never silently no-ops.
_SCENES: dict[str, Callable[[GameContext, MainQuestStep], None]] = {
    "sealed_door_discover": _play_sealed_door_discover,   # from _act0.py
    "sealed_door_open": _play_sealed_door_open,           # from _act0.py
    "help_offer": _play_help_offer,                       # from _act0.py
    "prologue_transmission": _play_prologue_transmission, # from _act0.py
    "orbit_disclosure": _play_orbit_disclosure,           # from _act1.py
}
```

The handler decides *when* the step's scene plays (bump handler plays it after
the bump completes; dialogue trigger plays it after the offer). The scene
identifier is data; the presentation is code.

## Authoring a new chain (the payoff)

After this lands, adding a new faction chain (or an Act-2 research chain) is:

1. **A data file** `data/main_quest/act2_<name>.py` — a `STEPS` tuple of
   `MainQuestStep(...)` entries (objective, location, `requires_step`, rewards,
   dialogues, `wait_days`, `heat` tags, `scene` id). No imports of runtime modules.
2. **Story text** in the JSON overlay (`data/text/`): titles, descriptions,
   dialogue variants, completion flavor, ready messages.
3. **NPC placement** (only if the chain introduces a new NPC): one entry in
   `data/npcs/`, a `PlanetSpec.quest_npc_spots` row naming its guild building,
   and `npc_presence=("<npc_id>",)` tags on the steps that need the NPC
   present — pure data, same as the four expert NPCs. The NPC appears
   additively only while those steps are live and vanishes after.
4. **A scene** (only if the chain needs a new cutscene): write the scene in
   `main_quest/_scenes.py` first, then reference it by id.

**What does NOT change:** no `main_quest/*.py` runtime edits (unless the chain
needs a brand-new objective type → one handler module + one registry row), no
`_heat.py`, no `_breadcrumb.py`, no `_gates.py`, no `_act0.py` edits, no
save/load changes.

Worked example — a hypothetical 5th chain, "The Cultists" (talk → delve →
smuggle → bounty → talk):

```python
# data/main_quest/act1_cult.py
STEPS: tuple[MainQuestStep, ...] = (
    MainQuestStep(id="cul_q1_lead", requires_step="prologue_seek_help",
                  chain="cult", objective_type="talk", wait_days=60,
                  trigger_planet_id="earth", trigger_system_id="sol",
                  dialogues={"guild_master": QuestDialogue(...)},
                  rewards_xp=50),
    MainQuestStep(id="cul_q2_shrine", requires_step="cul_q1_lead",
                  chain="cult", objective_type="delve",
                  delve_good_ids=(("cult_reliquary", 1),),
                  trigger_planet_id="proc_planet_3", trigger_system_id="procyon", ...),
    MainQuestStep(id="cul_q3_haul", requires_step="cul_q2_shrine",
                  chain="cult", objective_type="smuggle",
                  requires_npc_id="cult_priest", smuggle_good_id="cult_reliquary",
                  smuggle_cargo_size=2, smuggle_hot=False,
                  npc_presence=("cult_priest",),
                  trigger_planet_id="tc_c", trigger_system_id="tau_ceti", ...),
    MainQuestStep(id="cul_q4_gauntlet", requires_step="cul_q3_haul",
                  chain="cult", objective_type="bounty",
                  requires_spawn_id="cul_gauntlet", bounty_enemy_id="pirate_captain",
                  bounty_escort_ids=("pirate_raider", "pirate_raider"),
                  trigger_system_id="vega", heat=("consortium",), ...),
    MainQuestStep(id="cul_q5_key", requires_step="cul_q4_gauntlet",
                  chain="cult", objective_type="talk",
                  unlocks_step="prologue_open", rewards_item="cult_key", ...),
)
```

## Implementation phases

### Phase 1: Objective handler registry (dispatch only — no behavior change)

- [x] Add `main_quest/handlers.py` with `ObjectiveHandler` + `handler_for()` table
- [x] Move `trigger_dialogue`'s if/elif into handler `on_trigger` hooks
      (talk default, goods, smuggle, salvage, visit, bump)
- [x] Move `secure_quest_loot`'s delve/salvage special-casing into `on_complete`
      hooks (incl. salvage spawn cleanup + `_maybe_auto_trigger_next_smuggle`)
- [x] Move `ensure_quest_spawns`' bounty/salvage special-casing into
      `ensure_spawns` hooks
- [x] Move `quest_option_for` / `resolve_npc_dialogue` smuggle gating into the
      smuggle handler's `option_gating` hook
- [x] Dispatch sites become table lookups; delete the old if/elif chains
- [x] Registry lookup is a pure function → new pytest in the same commit
      (unknown type → `None`; every cataloged `objective_type` resolves)
- [x] `make check` green; all existing quest tests pass unchanged
- [x] Open playtest complete (user-confirmed)

**PLAYTEST (1) — COMPLETE:** full regression — one save per faction chain to `prologue_open`
(Act 0), plus the post-prison research beat. Verify every objective type
(talk/delve/smuggle/visit/bounty/salvage/bump/prison) still completes through
its normal route: dialogue option, cache secure, crate handover, bounty defeat,
wreck boarding, door bump. Save/quit/continue mid-chain preserves progress.
No visible behavior change expected — this phase is structural.

### Phase 2: Data-ify faction heat (tuple of tags)

- [x] Add `heat: tuple[str, ...]` to `MainQuestStep`
- [x] Rewrite `_heat.py` as a data-driven filter over `_iter_known_steps`
      (tag → behavior: `militia_scan` = scan floor, `militia_aggro` = auto-aggro
      while crate held, `consortium` = pirate heat)
- [x] Tag the bar steps (`bar_q2_proof` scan, `bar_q4`/`bar_q5` scan + aggro) and
      merchant steps (`mer_q3`/`mer_q4`) in their data files
- [x] Delete the hard-coded step ids from `_heat.py`
- [x] Heat-filter helpers are pure → new pytest in the same commit
- [x] `make check` green
- [x] Open playtest complete (user-confirmed)

**PLAYTEST (2) — COMPLETE:** bar chain — while carrying the power cell, militia auto-aggro
in Sol fires (q5) and the scan floor holds (q2–q5); both expire at `bar_q6_rig`.
Merchant chain — consortium squads spawn during q3/q4 and stop at `mer_q5_cutter`.
Save/quit/continue mid-heat preserves the behavior.

### Phase 3: Scene triggering via data + remaining step flags

- [x] Add `scene: str` to `MainQuestStep`; add `main_quest/_scenes.py` with a
      `_SCENES` id → implementation registry (lazy imports, like `handlers.py`)
- [x] Move the sealed-door beats (discover/open), help offer, prologue
      transmission, and orbit disclosure *wiring* behind `scene` ids on their
      steps; keep the presentation code in `_act0.py` / `_act1.py`
- [x] Add `auto_load_next_smuggle` to `MainQuestStep`; `_core._maybe_auto_trigger_next_smuggle`
      reads it instead of always-on
- [x] `_breadcrumb.py`: keep the bespoke post-prison breadcrumbs (translation
      wait, departure objective) as documented special cases for now — text
      migration happens in Phase 4, and they are Act-1 narrative, not chain-generic
- [x] `_gates.py`: keep the `_repair_*` save migrations untouched (they are
      save-compat, explicitly allowed to name step ids)
- [x] New pure helpers ship pytest in the same commit
- [x] `make check` green
- [x] Open playtest complete (user-confirmed)

**Architecture debt paid (this phase):** the scene wiring touched
`navigation.py` (prologue transmission fires from `_jump_to_system`) and
`game_flow.py` (orbit disclosure fires from the launch/exit paths), which the
ratchet flagged for their pre-existing over-limit debt. `navigation.py` was
split into a re-export hub over five focused sibling modules —
`navigation_render` (overlay + AOI), `navigation_spawns` (bounty/intercept
placement), `navigation_combat` (encounter detection + auto-comms),
`navigation_scan` (militia cargo scan), and `navigation_travel` (GO TO, jump
gate, jump animation, system transition) — with every function ≤40 lines and
the full `from .navigation import ...` surface preserved. `game_flow.py`'s
three oversized functions (`_run_ground_combat_tick`, `_complete_ship_purchase`,
`_leave_dungeon_to_space`) were split into focused helpers.

**PLAYTEST (3) — COMPLETE:** lab chain — bump sample still auto-loads the Mercury delivery;
a step with `auto_load_next_smuggle=False` (add a temporary test step) does not.
Sealed-door discover/open overlays, the help-offer modal, and the orbit
disclosure all still fire at exactly their current triggers — now driven by the
step's `scene` id. A `scene` id with no registered implementation fails loudly
in smoke, not silently in-game.

### Phase 3a: Data-ify quest-NPC presence (additive experts)

Audit finding (pre-Phase-3): the four faction experts were a mix of static
`npc_overrides` that REPLACED guild faces (demolitions expert on Epsilon Eri b,
salvage specialist on Tau Ceti b, xenolinguist on Alpha Centauri — always
present, even before their quests start) and one dynamic spawn (old smuggler)
with a hard-coded `(38, 10)` position, a second copy inside surface dungeons,
and a loose presence window. Decision: all four experts are additive city NPCs
standing in their guild building only while their step is live.

- [x] Add `npc_presence: tuple[str, ...]` to `MainQuestStep` (which NPCs the
      step needs present while it is live)- [x] Add `quest_npc_spots: tuple[(npc_id, building_label), ...]` to
      `PlanetSpec` (where each additive NPC stands — one tile EAST of
      the building's interior center, clear of the regular occupant
      who stands at the center; the old dynamic spawn's magic
      `(38, 10)` was secretly center+1, which is why it worked)
- [x] Rewrite `_act0.py` spawning as a data filter over `_iter_known_steps`:
      live step + locked chain ⇒ NPC present on every planet with its spot;
      delete `_quest_npc_for_planet`, `_wall_adjacent_tile`, and the
      `spawn_pos` parameter (no more dungeon copies, no magic coordinates)
- [x] Tag presence: `bar_q2`/`q3`/`q4` → old smuggler, `mer_q3`/`q4` → salvage
      specialist, `mil_q4` → demolitions expert, `lab_q4` → xenolinguist
- [x] Remove the three replacing `npc_overrides` from `eri_b` / `tc_b` /
      `ac_station`; add their `quest_npc_spots`; the guild faces return (the
      seek-help fork again surfaces at any guild captain/master/officer)
- [x] Drop the dead `prologue_seek_help` xenolinguist dialogue entry + its
      JSON keys (the lab seek-help lead keys off the regular research officer)
- [x] Retarget static missions off the quest NPCs: Earth→AC delivery to
      `research_officer`; the two Tau Ceti deliveries offered by the specialist
      move to the always-present `guild_master`
- [x] City-only spawning: remove the dungeon call site in `game_interactions.py`
- [x] Smoke validator checks every `npc_presence` tag resolves + has a spot,
      and every spot names an existing guild building
- [x] New pytest (`test_main_quest_npc_presence.py`) in the same commit;
      `make check` green
- [x] Open playtest complete (user-confirmed)

**PLAYTEST (3a) — COMPLETE:** the four experts appear ONLY in their windows — old smuggler
at Barnard b (bar q2–q4), specialist at Tau Ceti b (q3–q4), demolitions expert
at Epsilon Eri b (mil_q4), xenolinguist at Alpha Centauri (lab_q4) — and are
absent before/after; the guild faces they used to replace are present as usual;
no expert copy inside surface dungeons; save/quit/continue mid-window keeps
them placed.

### Phase 4: Migrate quest and Mars-prison text to the JSON overlay

**Expanded scope:** this is the complete player-facing text pass for the Mars
prison arc, not only the quest-log breadcrumbs and completion logs. It covers
the full path from opening the Mars prison door, through the five-floor descent
and Floor 5 extraction, through the ascent and final departure from Mars.

- [x] Add `runtime.*` keys to `text.py` for the remaining quest breadcrumbs:
      gated-title ("Awaiting word from the {faction}..."), gated-fallback
      ("The faction will contact you when they're ready."), departure title/body
      ("Leave Mars" / "Return to your ship and launch from Mars..."),
      sealed-archive title/body, first-translation title/body, and fallback-handoff
      title/body.
- [x] Add `runtime.*` keys for the complete prison text inventory:
      - **Opening:** sealed-door discovery/open/blocked/chip/ambush overlays and
        logs, including the transition from the opened door to the prison stairs.
      - **Descent:** Floor 1 and Floor 5 entry flavor; all Floor 1–4 security
        activation and lockdown popup text; engineering-console power-restored
        text; and the blocked/available deep-elevator messages.
      - **Bottom and extraction:** deep-cell terminal text, alien-data extraction
        result, emergency-power state, `act1_prison` start/completion logs, and
        any extraction-related quest readout text.
      - **Ascent and departure:** post-extraction security responses on Floors
        4–1, prison exit/return-to-orbit logs, the `Leave Mars` breadcrumb, and
        the first-reading/orbit disclosure and handoff text.
- [x] Update every relevant call site to resolve through `t_get(...)` rather
      than embedding player-facing prose: `_breadcrumb.py`, `_core.py`,
      `_act0.py`, `_act1.py`, `dungeon_extensions.py`, its prison data catalog,
      and `game_flow.py`. Existing step titles/descriptions/dialogue already in
      the `step.*` JSON overlay remain covered by the same regression pass.
- [x] Run `tools/extract_act0_text.py` so the complete key set lands in
      `00_runtime.json` and writer edits remain the source of truth.
- [x] Confirm the text inventory has no missed hard-coded prison prose; only
      non-player-facing diagnostics, layout/art strings, and intentional Python
      defaults may remain outside the overlay.
- [x] `make check` green; the extractor's key-set sync still passes.
- [x] Full prison text playtest complete (user-confirmed).

**PLAYTEST (4) — COMPLETE:** run the complete prison text path, not just the quest log:

1. Open the Mars prison door and verify the discovery, opening, blocked/chip,
   and ambush text at their applicable beats; descend through the revealed
   stairs.
2. Traverse Floors 1–4 and verify each floor-entry/security popup, lockdown
   response, engineering-console message, and elevator blocked/unblocked
   message. Reach Floor 5 and verify the deep-cell entry and data-terminal
   extraction text.
3. Save/Continue during the descent and after extraction. Climb back through
   the staged security responses, leave the prison, launch from Mars, and verify
   the departure and first-reading/orbit handoff text.
4. Edit representative opening, descent, extraction, and departure keys in
   `00_runtime.json`, relaunch or press F5, and confirm the changed wording
   appears without a code edit. Confirm no prison text disappears, falls back
   unexpectedly, or changes save/load behavior.

**Playtest result:** User confirmed the complete prison text path passed,
including door opening, descent, extraction, ascent, and departure. No failures
or new edge cases were reported.

### Phase 5: Minimal validator + authoring guide + acceptance

- [x] Add `tools/check_main_quest.py` (or extend the smoke gate) that fails only
      on: unknown `objective_type` (no handler), unresolved `requires_step`,
      dangling `unlocks_step`, unknown `heat` tags, missing story text, and a
      `scene` id with no registered implementation. No chain-termination or
      balance strictness (deferred until the quests are fleshed out)
- [x] Wire it into `make check`
- [x] Write the authoring guide at
      `src/spacehack/data/main_quest/README.md` (dev-facing): how to add a
      chain, an objective type, a scene, an NPC — with the worked example above
- [x] Add pure validator regression tests covering each deliberate invalid-data
      class and the valid production catalog
- [x] `make check` green

**Phase 5 implementation status:** complete. The validator is pure and
unit-testable, the production catalog passes it, and `make check` runs it
before the architecture/lint/test stages.

**PLAYTEST (5) — COMPLETE:** User confirmed the deliberate invalid-data checks
and the temporary data-only chain exercise passed. Unknown objective types,
dangling prerequisites, and unregistered scenes fail clearly; corrected data
passes, and the throwaway chain was removed.

### Phase 6: Guide, docs, acceptance — NEXT

- [ ] Update `_GUIDE_MAIN_QUEST` if any player-facing wording changed (Phases
      1–4 are behavior-preserving, so this should be a no-op review)
- [ ] Update `docs/design/` reference if the module map in `main_quest/__init__.py`
      changes (new `handlers.py` / `_scenes.py` + handler modules)
- [ ] Full regression: all four Act-0 chains + post-prison research beat + prison
      descent, across save/load
- [ ] `make check` green
- [ ] Ask the user: "Move this to complete?" per the doc lifecycle

## Acceptance criteria

- [ ] Adding a new chain = a `data/main_quest/` file + JSON overlay + (only if
      new NPCs) `data/npcs/` + a planet `quest_npc_spots` row + `npc_presence`
      tags on the steps. Zero runtime edits.
- [ ] Adding a new objective type = one handler module + one registry row.
      No edits to `_dialogue.py` / `_objectives.py` / `_spawns.py` / `_act0.py`.
- [ ] Adding a new scene = one scene in `main_quest/_scenes.py` + a `scene` id
      on the step. Triggering is data; presentation is code.
- [ ] No hard-coded step ids remain in `main_quest/` runtime modules, except
      the explicitly-allowed save migrations in `_gates.py` (documented).
- [ ] No hard-coded player-facing quest or prison text remains in Python:
      breadcrumbs, completion logs, door scenes, prison entry/security/
      interaction/extraction/ascent text, and Mars-departure/orbit text all
      resolve through `t_get()` / the JSON overlay.
- [ ] Dispatch is table-driven everywhere (guardrail: state tables over
      conditional logic — no 3+ branch if/elif for objective routing).
- [ ] All existing quest tests pass unchanged; new registry/heat/scene/validator
      tests ship in their commits.
- [ ] Save/load shape unchanged; an old save loads identically.
- [ ] `make check` green at every commit.

## Pre-implementation audit

### Existing modules to extend or reuse

- `data/main_quest/__init__.py` — `MainQuestStep` / `QuestDialogue`, auto-discovery,
  `_apply_text_overlay`, `_build_registry`, `main_quest_step_after`. The whole
  data layer stays as-is.
- `main_quest/_core.py` — lifecycle (`start_step` / `complete_step` /
  `_schedule_next_step`) + smuggle crate mechanics become handler implementations.
- `main_quest/_dialogue.py` — `resolve_npc_dialogue` / `quest_option_for` /
  `trigger_dialogue`; dispatch moves behind the registry.
- `main_quest/_objectives.py` — delve/salvage/visit/bounty completion +
  `complete_step_by_type` / `_active_objective_step` become handler implementations.
- `main_quest/_spawns.py` — bounty/salvage spawn management becomes the
  `ensure_spawns` hook.
- `main_quest/_act0.py` / `_act1.py` — the sealed-door, help-offer, transmission,
  and orbit-disclosure presentations become `_scenes.py` implementations.
- `data/dungeon_extensions/__init__.py` — `EntryFlavor`, `ActivationEvent`, and
  `DungeonInteractionSpec` currently hold the prison's entry, security,
  engineering, elevator, deep-cell, and extraction prose; keep the structural
  definitions but move their player-facing values behind overlay keys.
- `dungeon_extensions.py` / `game_flow.py` — `_show_first_entry_flavor`,
  `tick_activation`, interaction feedback, prison exit, and Mars-orbit handoff
  are the runtime seams that must resolve the prison text catalog.
- `mission/_models.py` + `mission/_helpers.py` — the standardized mission hold
  (`ActiveMission`, delivery matching) the smuggle handler reuses, unchanged.
- `text.py` + `tools/extract_act0_text.py` — the overlay + extractor already
  manage `runtime.*` keys; Phase 4 adds breadcrumb/log keys through the same
  mechanism.
- `main_quest/__init__.py` — the public re-export surface stays stable so
  external callers (`npc.py`, `navigation.py`, `npc_ships.py`, `game_loop.py`,
  `game_flow.py`, `game_interactions.py`, `menus/_planet.py`,
  `dungeon_extensions.py`) keep working untouched.
- `tools/smoke.py` — already asserts the `main_quest` entry points and validates
  step `requires_step`/`unlocks_step`/dialogue references; extend it for the
  minimal validator.

### Three potential duplication hotspots

1. **Objective dispatch re-implemented in every module.** `trigger_dialogue`
   (dialogue), `secure_quest_loot` (objectives), `ensure_quest_spawns`
   (spawns), and `bump_mars_door` (act0) each re-implement type routing with
   their own if/elif. **DRY:** one `handlers.py` table; every site becomes
   `handler_for(type)` lookup. Guardrail: state tables over conditional logic.
2. **Step-status scanning loops.** `_iter_known_steps` + `_active_objective_step`
   patterns recur in `_heat.py`, `_breadcrumb.py`, `_gates.py`, `_spawns.py`,
   `_objectives.py`. **DRY:** the shared `_iter_known_steps` already exists;
   heat/breadcrumb/gate lookups become data-field filters over it, not new loops.
3. **Hard-coded step ids + hard-coded text.** `_heat.py` (7 ids), `_gates.py`
   (2 ids + migrations), `_breadcrumb.py` (4 ids + 6 hard-coded strings),
   `_act0.py` (3 ids + 1 log string), `_core.py` (2 log strings), and the
   prison extension catalog's entry/activation/interaction prose. **DRY:**
   move ids onto step data (`heat`, `scene`, `auto_load_next_smuggle`) and all
   player-facing prose into namespaced `runtime.*` overlay keys (including
   `runtime.prison.*`); allow only structural data, diagnostics, layout/art
   strings, and documented save migrations outside the overlay.

## Contracts compliance (MANDATORY — see knowledge.md)

- [ ] **Save/load:** no new `GameContext` fields; `main_quest_progress`,
      `main_quest_gate`, `main_quest_pending_message`, `main_quest_pending_objective`,
      `main_quest_chain`, `main_quest_backing`, `main_quest_disclosure`,
      `post_prison_orbit_seen`, `main_quest_complete` keep their exact serialized
      shapes. New fields are static step data (not serialized). Sniff test after
      each phase: reach new state → save → quit → Continue → verify identical.
- [ ] **Game guide:** Phases 1–4 are behavior-preserving; review `_GUIDE_MAIN_QUEST`
      for wording drift and update if any changed. No new player-facing mechanic
      is introduced by this design.
- [ ] **Pure function test contract:** registry lookup, heat filtering, scene-id
      resolution, and the validator are pure → each ships pytest in its commit.
- [ ] **Module-level state:** none added; the existing `current_solar_system_id`
      / `RNG` globals are untouched.
- [ ] **Architecture ratchet:** `handlers.py`, `_scenes.py`, and each handler
      module stay under 1000 lines; every function under 40 lines. The refactor
      should *reduce* sprawl in `_dialogue.py` / `_objectives.py` / `_act0.py`.

## Open questions

1. **Scene event model:** one `scene` id played at "the step's primary beat" is
   the simplest contract. If a step ever needs scenes at *different* events
   (e.g. an intro cutscene on trigger AND a completion cutscene), do we add a
   `scenes: dict[event, id]` mapping, or keep one id per step and let the scene
   implementation branch internally?
2. **Breadcrumb key namespacing:** `runtime.*` keys (flat, matches the existing
   overlay) vs per-step fields (e.g. `step.<id>.waiting_title`)? `runtime.*`
   is the repo-consistent choice and the extractor already syncs it.
3. **`objective_type` as string vs Enum:** string is friendlier for data authoring
   (the repo already uses strings for `main_quest_path`); an Enum is safer. Keep
   string + validator, or introduce an Enum?
4. **Registry extensibility:** static table (matches the repo's `find_*`/`_BY_ID`
   catalogs) vs runtime registration (future mod support)? Static is the
   repo-consistent choice.
5. **Validator strictness (deferred):** when the quests are fleshed out, should
   every chain be required to terminate in the ending, or allow intentionally
   dead-end dig content? Not enforced now per the locked decision.
