# Interactive Game Guide — `?` key

## Overview

Press `?` at any time to open a **full interactive game guide** — a browsable menu of topic sections explaining every system in spacehack. This is not a keybinding cheat sheet; it's an in-game manual that explains **how things work**: combat formulas, trade mechanics, mission flow, ship systems, navigation, and more.

Each topic opens a full-screen page of wrapped explanatory text. Navigate the topic list with arrow keys, open a topic with ENTER, go back with ESC, close the guide entirely with ESC from the topic list. Game state pauses while the guide is open.

**Why a guide, not a keybinding list:** Keybindings are already visible in the HUD sidebar (city/space mode) and embedded in the combat HUD. What's missing is *any* place to learn how game systems work — hit chance math, fuel costs, shield regen, faction reputation, trade price fluctuations, cargo scanning, etc. The `?` guide fills that gap.

---

## Philosophy alignment

| Principle | How this design follows it |
|-----------|---------------------------|
| **ctx-first** | The guide reads nothing from `ctx` — all content is static text. No new ctx fields. |
| **Data-first** | Each section is a constant tuple entry. Content lives in its own module (`help.py`). |
| **Domains own their flow** | `_run_help_guide()` is a single entry point called from any context. No central dispatcher changes. |
| **Modal pattern** | The guide reuses `ui.Modal` — blocks game loop, zero state leakage. |
| **Simplicity / Minimalism** | One new module, one UI pattern (selectable list → page view), ~250 lines. No new classes beyond a small dataclass. |
| **Monitors file size** | If `help.py` approaches 500 lines from content, extract long-form text into a `data/guide/` catalog. |

---

## Architecture

### New module: `src/spacehack/help.py`

```python
@dataclass(frozen=True)
class GuideSection:
    title: str
    body: str                   # plain text, word-wrapped at render time

# Module-level catalog — all guide content lives here.
GUIDE_SECTIONS: tuple[GuideSection, ...] = (
    GuideSection("Game Overview", ...),
    GuideSection("Controls & Keybindings", ...),
    GuideSection("Combat System", ...),
    GuideSection("Trading & Economy", ...),
    GuideSection("Missions & Bounties", ...),
    GuideSection("Ships & Equipment", ...),
    GuideSection("Navigation & Jump Gates", ...),
    GuideSection("Character & Skills", ...),
    GuideSection("NPCs & Factions", ...),
)
```

### UI flow

```
      ┌─────────────────────────────┐
      │      GAME GUIDE              │
      │                              │
      │  > Game Overview             │  ← navigable topic list
      │    Controls & Keybindings    │     (reuses render_selectable_list
      │    Combat System             │      or a dedicated renderer)
      │    Trading & Economy         │
      │    Missions & Bounties       │
      │    Ships & Equipment         │
      │    Navigation & Jump Gates   │
      │    Character & Skills        │
      │    NPCs & Factions           │
      │                              │
      │  ↑↓ navigate  ENTER open     │
      │  ESC to close                │
      └─────────────────────────────┘

                │ ENTER on a section
                ▼
      ┌─────────────────────────────┐
      │    COMBAT SYSTEM             │  ← section title
      │                              │
      │  Combat in spacehack is      │
      │  turn-based...               │
      │                              │  ← body text, word-wrapped
      │  Hit chance = weapon.accuracy│     via ui.wrap_text()
      │  + gunnery * 0.5...          │
      │                              │
      │  ────────────────────────────│
      │  ESC to go back              │
      └─────────────────────────────┘
```

### Functions

```python
def render_guide_list(
    console: tcod.console.Console,
    screen_width: int,
    screen_height: int,
    sections: tuple[GuideSection, ...],
    selected: int,
) -> None:
    """Paint the topic list. Clears console first."""

def render_guide_page(
    console: tcod.console.Console,
    screen_width: int,
    screen_height: int,
    section: GuideSection,
    page_offset: int = 0,              # for future multi-page sections
) -> None:
    """Paint a single section's body text, word-wrapped. Clears console first."""

def update_guide(
    event: tcod.event.Event,
    sections: tuple[GuideSection, ...],
    selected: int,
    viewing: GuideSection | None,       # None = topic list, not-None = reading page
) -> GuideOutcome:
    """Handle input. Returns GuideOutcome closed / viewing / navigating."""

class GuideOutcome(Enum):
    IGNORE = auto()
    CLOSED = auto()     # guide dismissed entirely
    OPEN_SECTION = auto()   # opened a section (carries the index)
    BACK_TO_LIST = auto()   # from a page back to the topic list
```

### Entry point

```python
def _run_help_guide(ctx: GameContext) -> None:
    """Open the game guide as a modal. Returns when the player closes it.

    Called from __main__.py's city/space loop and from any modal's
    update function. Pauses game state while open.
    """
    console = make_console()
    selected = 0
    viewing: GuideSection | None = None
    page_offset = 0

    def _render() -> None:
        if viewing is not None:
            render_guide_page(console, SCREEN_WIDTH, SCREEN_HEIGHT, viewing, page_offset)
        else:
            render_guide_list(console, SCREEN_WIDTH, SCREEN_HEIGHT, GUIDE_SECTIONS, selected)

    def _update(event) -> GuideOutcome:
        nonlocal selected, viewing, page_offset
        # ... navigation logic
        return outcome

    ui.Modal(ctx.context, console).run(_render, _update)
```

---

## Content plan — each section's explanation

Each section is a single string of plain text (word-wrapped by `ui.wrap_text()` at render time). Content below is the *plan* — actual text written during implementation.

### 1. Game Overview
- The year 2156 setting, jump gates, frontier
- What you do: trade, bounty hunt, explore
- Core loop: city → buy ship → space → missions → combat → profit

### 2. Controls & Keybindings
- Full keybinding table for ALL modes (city, space, combat, trade, etc.)
- Presented as a two-column table, not scattered lines
- The only section that's pure keybinding data

### 3. Combat System
- Turn structure: AP, power gen, shields regen per turn
- Hit chance formula: accuracy + gunnery/2 + range bonuses - dodge
- Damage formula: weapon damage × quality roll × variance
- Movement dodge bonus: +5%/cell moved (cap 30%)
- Shield regen: proportional cost, engineering discount
- Flee formula: base 30% + piloting diff + desperation bonus + attempts stacking
- Weapon types: energy (power cost) vs missile (ammo)
- How to win: reduce all enemy hull to 0

### 4. Trading & Economy
- Finding trade terminals (= on city map)
- Buying/selling goods at terminals
- Price fluctuation based on planet economy
- Cargo capacity limits what you can carry
- Profit margin = buy low on production worlds, sell high on consumption worlds

### 5. Missions & Bounties
- Finding work: talk to NPCs in guild halls
- Mission types: delivery (take item to NPC), bounty (destroy target)
- Single active mission slot — must abandon or complete before taking another
- Bounty targets: marked in target system, visible on space map
- Completing: delivery → talk to target NPC, bounty → destroy enemy in combat
- Abandoning: Q opens quest log, A to abandon, ENTER to confirm

### 6. Ships & Equipment
- Ship stats: hull, fuel, cargo, weapon slots, module slots
- Buying a ship at the spaceport (walk into it)
- Weapons: light/heavy lasers (energy), light/heavy/EMP missiles
- Modules: engines (+power), systems (+shields, +gunnery, +cargo, etc.)
- Mechanic terminal (% on map): refuel and repair

### 7. Navigation & Jump Gates
- Space maps: each solar system is a scrollable 2D map
- Jump gates: fly into one to travel between systems (costs fuel)
- G (Go To): auto-nav with combat detection
- M (Map): system overlay showing planets, gates, your position
- . (wait): advance time one turn (pirates move, shields regen)
- Planets: fly into them to land (if they have a port)

### 8. Character & Skills
- Species choice: human, martian, etc. — stat bonuses
- Class choice: pirate, merchant, bounty hunter — different bonuses
- Three skills: Gunnery (hit chance), Piloting (AP/turn, dodge), Engineering (power efficiency, shield discount)
- Skills start at 30 + species bonus + class bonus

### 9. NPCs & Factions
- Guild halls in cities: merchant guild, militia, bounty guild, bar
- Faction reputation: pirate (-100), merchant (0), civilian (0), militia (50)
- Reputation changes based on actions (combat, missions)
- Comms panel (T in space): hail nearby ships

---

## Domain changes

### `src/spacehack/help.py` (NEW)
- `GuideSection` frozen dataclass
- `GUIDE_SECTIONS` tuple with all 9 sections
- `render_guide_list()`, `render_guide_page()`, `update_guide()`
- `_run_help_guide()` entry point
- `GuideOutcome` enum

### `src/spacehack/input_helpers.py`
- Add `_is_question_press(event)` predicate.

### `src/spacehack/__main__.py`
- In the top-level city/space event loop, add a `?` branch before vim dispatch:
  ```python
  if _is_question_press(event):
      _run_help_guide(ctx)
      continue
  ```

### Each modal sub-screen (trade, cargo, combat, comms, mechanic, NPC talk, quest log, etc.)
- In each `_update` function, add a `?` branch:
  ```python
  if _is_question_press(event):
      _run_help_guide(ctx)
      return Outcome.IGNORE  # modal re-renders on next frame
  ```

---

---

## DRY & maintainability principles

The following rules apply during implementation AND in every future session that touches ``help.py``.

### Content structure — no duplication

- **A single source of truth for keybindings.** The "Controls & Keybindings" section should NOT duplicate every key binding inline. Instead, import the shared binding tuples from ``hud.py`` (if they exist) or reference a single module-level constant. If a binding changes, there's one edit site, not two (HUD + guide).
- **Formulas are not copy-pasted.** When explaining a formula (e.g. hit chance, flee chance), the guide text must NOT duplicate the actual formula from ``combat.py``. Use descriptive text that paraphrases the formula so it naturally requires a human to update both if the formula changes. A code agent changing ``calc_hit_chance`` should need to *think* about whether the guide text needs updating — not just blindly search-and-replace a copy-pasted expression.
- **No content in render functions.** All guide text lives in module-level ``GuideSection`` constants, not inside render functions. This makes it easy to review and edit without touching rendering logic.

### Cohesion — each section is one thing

- Each ``GuideSection`` explains exactly one game system. If a section grows beyond ~40 lines of wrapped text, split it into two sections (e.g. "Combat Basics" and "Advanced Combat").
- Cross-system references use plain english ("see Trading & Economy"), not code references.

### Maintenance gates during implementation

Each phase checkbox MUST pass a mini-DRY review before being marked complete:

1. **No duplicated text patterns** — scan the content you just added for repeated phrases or explanations that could be shared.
2. **No dead code** — unused imports, unused helper functions, or leftover ``# TODO`` markers.
3. **No formula copy-paste** — every numeric explanation is paraphrased, not lifted from the source module.
4. **Smoke test passes** — ``python3 tools/smoke.py``.
5. **Commit message describes the DRY decision** — e.g. "imported binding tuples from hud.py instead of duplicating" or "paraphrased combat formula to avoid copy-paste drift".

### Code reviewer checklist (for this feature)

When the code-reviewer-deepseek-flash is spawned during implementation, it MUST check:

1. **Content accuracy** — Do the guide explanations match the actual game mechanics? Read the relevant source file (combat.py, trade.py, mission.py, etc.) and compare.
2. **DRY violations** — Is any content repeated between guide sections? Between the guide and HUD help lines? Between the guide and a formula in combat.py?
3. **Import structure** — Does ``help.py`` import from too many places? It should import ``ui`` for ``wrap_text``, ``Modal``, and ``centered_x`` — nothing from domain modules except typing stubs.
4. **Nested modal safety** — Does the ``?`` handler in each modal properly return IGNORE so the parent modal doesn't advance state while the guide is open?
5. **Edge cases** — What happens when ``?`` is pressed during a flee confirmation? During the animation between combat turns? During an NPC dialog that has a "?" in its flavor text (is that possible)?

---

## Post-completion: guide sync contract

Once the guide is implemented and all phases are complete, the following process becomes part of every feature agent's workflow.

### The "game-guide pass" rule

Any agent making a feature change that affects a player-facing game system MUST also review and update the corresponding guide section. This is not optional — it is a required step in the implementation plan, gated before the final smoke test and commit.

### When to update the guide

| If you change... | Update this guide section |
|---|---|
| Combat formulas, weapons, enemy AI | "Combat System" |
| Trade prices, cargo, terminals | "Trading & Economy" |
| Missions, bounties, delivery flow | "Missions & Bounties" |
| Ship stats, weapons, modules, buying | "Ships & Equipment" |
| Navigation, jump gates, auto-nav | "Navigation & Jump Gates" |
| Species, classes, skill formulas | "Character & Skills" |
| NPCs, factions, reputation, comms | "NPCs & Factions" |
| Any keybinding or modal interaction | "Controls & Keybindings" |
| Anything not covered above | Check if a new section is needed |

### The guide-update checklist (added to every feature implementation plan)

1. **Identify affected sections** — Which guide sections describe the system being changed?
2. **Read current section content** — What does the guide currently say?
3. **Update or add content** — Does the change add a new mechanic, remove one, or modify an existing one?
4. **No stale information** — Does the update remove any now-inaccurate text?
5. **Add a new section if needed** — Is the change introducing a new game system that the guide doesn't cover? Add a new ``GuideSection`` to ``GUIDE_SECTIONS``.
6. **Remove sections if needed** — Is a system being removed entirely? Remove its section from ``GUIDE_SECTIONS``.
7. **Smoke test** — Verify the guide still opens and renders correctly.

### What the guide-update checklist looks like in a design doc

New feature design docs that add, remove, or change a game system MUST include this sub-step in their implementation plan:

```
- [ ] **Guide sync** — Update the "System Name" section in ``help.py`` to reflect the new mechanic.
```

If the design doc doesn't include this step, the implementing agent MUST add it before starting work.

### What happens if an agent skips the guide pass

The smoke test won't catch it (the guide is just strings — it always imports fine). The code reviewer (code-reviewer-deepseek-flash) is the gate. The reviewer's checklist includes:

> "Did this change affect any game system documented in the ``?`` guide? If so, was ``help.py`` updated?"

If the answer is "no" and "should have been", the reviewer blocks the commit.

---

## Phased implementation plan

### Phase 1 — Core module + city/space hook [x] {5/5}

- [x] **P1.1** — Create ``help.py`` with ``GuideSection`` dataclass, ``GuideOutcome`` enum, and all 9 section content strings as ``GUIDE_SECTIONS``.
- [x] **P1.2** — Implement ``render_guide_list()`` (topic list, dedicated renderer with centered titles and selection markers).
- [x] **P1.3** — Implement ``render_guide_page()`` (body text with ``ui.wrap_text()``, title, divider, ESC hint, multi-page scroll hint).
- [x] **P1.4** — Implement ``update_guide()`` + ``_run_help_guide()`` entry point with scroll support.
- [x] **P1.5** — Add ``_is_question_press()`` (checks both ``'QUESTION'`` and ``'SLASH'`` + shift modifier for correct SDL key handling) to ``input_helpers.py``, wire ``?`` into ``__main__.py``'s city/space loop.
- [x] **P1.DRY** — Mini-DRY review passed: no dead imports, formulas paraphrased not copy-pasted, Controls section references key categories rather than duplicating HUD binding tuples. Reviewer flagged ``'SLASH'`` inclusion — fixed before merge. Commit ``d16e0d8``.

**PLAYTEST P1**: Start a game in city mode. Press ``?`` → see 9-section topic list. Navigate with ↑↓/jk, select with ENTER → see section content. ESC → back to list. ESC → back to game. Launch to space, press ``?`` → same guide, still works.

### Phase 2 — Modal sub-screen plumbing [x] {8/8}

Wire ``?`` into every modal update function:

- [x] **P2.1** — Combat (``combat.py``)
- [x] **P2.2** — Trade terminal (``trade.py``)
- [x] **P2.3** — Cargo menu (``trade.py``)
- [x] **P2.4** — Comms panel (``comms.py``)
- [x] **P2.5** — Mechanic terminal (``menus.py``)
- [x] **P2.6** — NPC talk (``npc.py``)
- [x] **P2.7** — Quest log / ship menu / ship buy (``menus.py``)
- [x] **P2.8** — Navigation / goto / jump menu / planet menu (``navigation.py``, ``menus.py``)
- [x] **P2.DRY** — After Phase 2 completion, a codebase-wide DRY review found the 4-line ``?`` handler pattern repeated 16× across 7 files with an unnecessary lazy import (``help.py`` has no circular dependencies with any modal module). Refactored: extracted ``_try_open_guide(event, ctx) -> bool`` helper into ``input_helpers.py``, moved all lazy imports to module-level, reducing each call site from 4 lines to 2. Smoke test passes. (This session, awaiting commit.)

**PLAYTEST P2**: Enter each modal. Press ``?`` → guide opens. Close it → modal state unchanged, original interaction continues.

### Phase 3 — Content refinement [x] {3/3}

- [x] **P3.1** — Review all section text for accuracy against current game mechanics. Read combat.py, trade.py, mission.py, etc. and compared with corresponding guide sections. No drift found — formulas paraphrased correctly.
- [x] **P3.2** — Add edge-case info. Added: cargo scan on landing, contraband rules, abandon mission flow, jettison cargo, auto-nav interruption by combat.
- [x] **P3.3** — Restructured all 9 sections from dense paragraphs into scannable bullet lists with sub-headers, formula blocks, and proper paragraph breaks. Also fixed ``ui.wrap_text()`` to preserve intentional ``\n`` line breaks (was collapsing all whitespace via ``text.split()``).
- [x] **P3.DRY** — Mini-DRY review: No content duplication across sections. One minor fix: ``JUMP_FUEL_COST`` code constant leaked into user-facing text — replaced with plain English. Formulas are paraphrased (not copy-pasted from combat.py). No dead imports. Smoke test passes.

**PLAYTEST P3**: Open each section — content reads as structured lists with clear paragraph breaks, not walls of text.

### Phase 4 — Polish [x] {4/4}

- [x] **P4.1** — Nested modal safety already satisfied by design: the guide's own ``_update`` ignores ``?`` (falls through to IGNORE), and each parent modal returns IGNORE after the guide closes. Guide uses its own console — no state leakage. Verified by inspection.
- [x] **P4.2** — Multi-page scroll (↑↓/jk scrolling with page counter in hint) was implemented in Phase 1. Also added PageUp/PageDown for full-page jumps during layout polish.
- [x] **P4.3** — Added ``("?", "Guide")`` to both city-mode and space-mode HUD help lines (``hud.py``). The city HUD shows it after the Q line; the space HUD shows it after Comms, before movement keys.
- [x] **P4.DRY** — Final DRY review: full scan across all 8 modified files. No duplication, no dead code, formulas paraphrased (not copy-pasted). One minor fix: ``JUMP_FUEL_COST`` code constant leaked into user-facing text — replaced with plain English. Smoke test passes.

**PLAYTEST P4**: Check that ``("?", "Guide")`` appears in both city and space HUD. Press ``?`` in every modal — guide opens and closes cleanly.

---

## Acceptance criteria

1. **`?` opens the guide from everywhere** — city, space, combat, trade, cargo, comms, mechanic, NPC talk, quest log, ship menu, navigation, planet menu.
2. **Guide has 9 topic sections** covering all major game systems.
3. **Navigation works**: ↑↓/jk navigate topic list, ENTER opens, ESC backs out, ESC from list closes.
4. **Game pauses** while guide is open — no enemy movement, no AP drain, no state changes.
5. **No new ctx fields** — all content is static text.
6. **Content is accurate** — formulas, keybindings, and flow descriptions match the current code.
7. **Smoke test passes** after each phase.
8. **Nested modal safe** — `?` from inside a modal's guide doesn't crash or stack overlays.

---

## Open questions (resolved)

1. **Keybindings vs. gameplay explanations?** → Both. "Controls & Keybindings" is one section; the other 8 sections explain gameplay. The guide is primarily a gameplay manual with one section dedicated to controls.
2. **Should the HUD hint about `?`?** → Yes (P4.3). Add `("?", "Guide")` to the HUD help lines so new players know the guide exists.
3. **What about modals that already use `?`?** → None currently use `?` for anything.
4. **Multi-page for long sections?** → Yes (P4.2). Scrollable pages using ↑↓ when content exceeds screen height.
5. **Can the guide be opened from the main menu?** → Not in v1. The title splash screen already blocks on any key, and there's no game to explain yet. Phase 5 if needed.
