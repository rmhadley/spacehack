# Interactive Game Guide — `?` key

## Overview

Press `?` at any time to open a **full interactive game guide** — a browsable, spoiler-safe manual for a new player. It explains what to do, what to watch, and how to make practical decisions without exposing implementation details or story progression.

Each topic opens a full-screen page of wrapped explanatory text. Navigate the topic list with arrow keys, open a topic with ENTER, go back with ESC, close the guide entirely with ESC from the topic list. Game state pauses while the guide is open.

**Why a guide, not a keybinding list:** Keybindings are already visible in the HUD sidebar (city/space mode) and embedded in the combat HUD. The `?` guide gives new players a safe starting path, practical survival advice, and short explanations of the systems they encounter.

---

## Philosophy alignment

| Principle | How this design follows it |
|-----------|---------------------------|
| **ctx-first** | The guide reads nothing from `ctx` — all content is static text. No new ctx fields. |
| **Data-first** | The interactive presenter lives in `help.py`; player-facing content lives in the frozen `data/guide/` catalog. |
| **Domains own their flow** | `_run_help_guide()` is a single entry point called from any context. No central dispatcher changes. |
| **Modal pattern** | The guide reuses the shared Pygame screen runner — it blocks the game loop while open and keeps state isolated. |
| **Simplicity / Minimalism** | One small presenter, one content catalog, and one UI pattern (selectable list → page view). |
| **Monitors file size** | `help.py` contains presentation only; long-form manual text belongs in `data/guide/`. |

---

## Architecture

### Interactive presenter: `src/spacehack/help.py`

```python
@dataclass(frozen=True)
class GuideSection:
    title: str
    body: str                   # plain text, word-wrapped at render time

# The player-facing catalog lives in `src/spacehack/data/guide/__init__.py`.
from spacehack.data.guide import GUIDE_SECTIONS
# `help.py` re-exports the catalog for existing contextual callers.
from spacehack.data.guide import GUIDE_SECTIONS
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
      │    Missions                  │
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
      │  Move, choose weapons, and    │     via the shared Pygame screen
      │  watch your shields...        │
      │                              │
      │  ────────────────────────────│
      │  ESC to go back              │
      └─────────────────────────────┘
```

### Presenter contract

The presenter keeps the existing modal contract while leaving all long-form
manual text in the catalog:

```python
from spacehack.data.guide import GUIDE_SECTIONS, GuideSection

_guide_index(topic: str | int | None) -> int | None
_section_frame(section: GuideSection) -> ScreenFrame
_run_pygame_help(ctx: GameContext, initial_topic: str | int | None = None)
_run_help_guide(ctx: GameContext) -> None
_open_context_guide(ctx: GameContext, topic: str) -> None
```

A list frame shows the catalog titles. Selecting a row opens a scrollable
section frame. TAB returns to the topic list, ESC closes the current modal,
and contextual callers open the matching section by title. The shared
Pygame screen pauses the underlying game while the guide is visible.

---

## Content plan — new-player manual

Each section is a concise string of plain text (word-wrapped by the shared Pygame screen). The manual avoids exact formulas, source terminology, developer instructions, and story or dungeon spoilers.

The catalog is organized around the questions a new player asks:

### Start Here
- What to do in the city, how to take a first job, and how to prepare

### Controls & Keybindings
- Common controls for city, space, ground exploration, combat, and menus

### Navigation & Jump Gates
- Go To, planets, ports, jump gates, fuel, and waiting

### Combat
- Turn flow, weapons, shields, movement, and safe decision-making

### Missions
- Finding work, using the quest log, mission cargo, and deadlines

### Ships & Equipment
- Ship roles, repairs, fuel, equipment, ammunition, and upgrades

### Trading & Economy
- Buying, selling, cargo space, and keeping enough credits for survival

### Character & Skills
- Species, classes, skill roles, and spending points

### Ground Exploration
- Fog, auto-explore, equipment, loot, and breaking contact

### NPCs & Factions
- Talking to contacts, comms, reputation, patrols, and restricted cargo

The catalog intentionally does not document story beats, dungeon layouts,
developer switches, exact formulas, or source-level terminology.

---

## Domain changes

### `src/spacehack/help.py`
- Re-export `GuideSection` and `GUIDE_SECTIONS` from the player-facing catalog
- `_guide_index()`, `_section_frame()`, and `_run_pygame_help()` presenter helpers
- `_run_help_guide()` entry point

### `src/spacehack/data/guide/__init__.py`
- Frozen `GuideSection` catalog with concise, spoiler-safe manual sections

### Existing integration

The guide is already wired through the shared input and modal seams. Future
player-facing changes should update the matching catalog section in
``src/spacehack/data/guide/`` and keep the presenter/UI contract unchanged.

---

---

## DRY & maintainability principles

The following rules apply during implementation AND in every future session that touches ``help.py``.

### Content structure — no duplication

- **Content belongs in the catalog.** Manual text lives in ``data/guide/``; ``help.py`` contains no long-form content.
- **Keybindings are practical, not exhaustive.** The manual points players to the HUD footer for menu-specific actions instead of duplicating every label.
- **No implementation or spoiler leakage.** Explain player choices and outcomes without formulas, source names, developer switches, procedural terminology, or unrevealed story details.
- **No content in render functions.** The presenter only turns catalog entries into frames.

### Cohesion — each section is one thing

- Each ``GuideSection`` explains one player concern. Keep bodies concise; if a topic grows beyond roughly 3,000 characters, split it into two sections.
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

1. **Content accuracy** — Do the player-facing explanations match the current mechanics? Read the relevant source file and compare.
2. **DRY violations** — Is any content repeated between guide sections or duplicated as implementation detail from gameplay code?
3. **Import structure** — Does ``help.py`` remain a small presenter, with manual text isolated in ``data/guide/``?
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
| Missions, bounties, delivery flow | "Missions" |
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

- [x] **P1.1** — Create the interactive presenter in ``help.py`` and the player-facing ``GuideSection`` catalog in ``data/guide/``.
- [x] **P1.2** — Implement the Pygame topic-list frame with selectable catalog rows.
- [x] **P1.3** — Implement scrollable section frames with the shared modal footer.
- [x] **P1.4** — Implement ``_run_pygame_help()`` + ``_run_help_guide()`` with contextual topic support.
- [x] **P1.5** — Add ``_is_question_press()`` (checks both ``'QUESTION'`` and ``'SLASH'`` + shift modifier for correct SDL key handling) to ``input_helpers.py``, wire ``?`` into ``__main__.py``'s city/space loop.
- [x] **P1.DRY** — Initial guide wiring review passed. The later catalog rewrite supersedes the original inline content while preserving the public presenter contract.

**PLAYTEST P1**: Start a game in city mode. Press ``?`` → see the new-player topic list. Navigate with ↑↓/jk, select with ENTER → see section content. ESC → back to list. ESC → back to game. Launch to space, press ``?`` → same guide, still works.

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

**PLAYTEST P2**: Enter each modal. Press ``?`` → guide opens. Close it → modal state unchanged, original interaction continues. This remains the regression contract for the shared presenter.

### Phase 3 — Content refinement [x] {3/3}

- [x] **P3.1** — Rewrite the manual for new players, removing implementation detail and story/dungeon spoilers while checking practical advice against current mechanics.
- [x] **P3.2** — Keep the manual focused on safe first-play decisions; omit story, dungeon-layout, developer-mode, and exact-formula detail.
- [x] **P3.3** — Reorganized the manual into concise, player-intent sections with practical headings and spoiler-safe advice.
- [x] **P3.DRY** — Moved content out of the presenter, added catalog maintainability tests, and verified no developer, formula, procedural, or story-spoiler terms appear in the player-facing catalog.

**PLAYTEST P3**: Open each section — content reads as concise new-player guidance with clear paragraph breaks, not implementation notes or spoiler-heavy walls of text.

### Phase 4 — Polish [x] {4/4}

- [x] **P4.1** — Nested modal safety already satisfied by design: the guide's own ``_update`` ignores ``?`` (falls through to IGNORE), and each parent modal returns IGNORE after the guide closes. Guide uses its own console — no state leakage. Verified by inspection.
- [x] **P4.2** — Scrollable section pages preserve the fitted font and support page navigation through the shared Pygame screen.
- [x] **P4.3** — Added ``("?", "Guide")`` to both city-mode and space-mode HUD help lines (``hud.py``). The city HUD shows it after the Q line; the space HUD shows it after Comms, before movement keys.
- [x] **P4.DRY** — Final catalog review passed: content is isolated from presentation, concise, CP437-safe, and free of developer or story-spoiler material. Smoke test passes.

**PLAYTEST P4**: Check that ``("?", "Guide")`` appears in both city and space HUD. Press ``?`` in every modal — guide opens and closes cleanly.

---

## Acceptance criteria

1. **`?` opens the guide from everywhere** — city, space, combat, trade, cargo, comms, mechanic, NPC talk, quest log, ship menu, navigation, planet menu.
2. **Guide has concise topic sections** covering the major questions a new player faces.
3. **Navigation works**: ↑↓/jk navigate topic list, ENTER opens, ESC backs out, ESC from list closes.
4. **Game pauses** while guide is open — no enemy movement, no AP drain, no state changes.
5. **No new ctx fields** — all content is static text.
6. **Content is accurate** — practical advice and keybindings match the current code without exposing formulas or spoilers.
7. **Smoke test passes** after each phase.
8. **Nested modal safe** — `?` from inside a modal's guide doesn't crash or stack overlays.

---

## Open questions (resolved)

1. **Keybindings vs. gameplay explanations?** → Both. "Controls & Keybindings" is one section; the remaining sections answer practical new-player questions. The guide is primarily a gameplay manual with one section dedicated to controls.
2. **Should the HUD hint about `?`?** → Yes (P4.3). Add `("?", "Guide")` to the HUD help lines so new players know the guide exists.
3. **What about modals that already use `?`?** → None currently use `?` for anything.
4. **Multi-page for long sections?** → Yes (P4.2). Scrollable pages using ↑↓ when content exceeds screen height.
5. **Can the guide be opened from the main menu?** → Not in v1. The title splash screen already blocks on any key, and there's no game to explain yet. Phase 5 if needed.
