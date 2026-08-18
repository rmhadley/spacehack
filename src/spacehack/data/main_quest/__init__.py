"""Main quest catalog: the storyline steps the player follows alongside sandbox play.

Each :class:`MainQuestStep` is a frozen dataclass describing one story
beat — its trigger, prerequisites, per-NPC dialogue overrides, and
rewards. Adding a step is one entry in a per-act tuple (e.g.
``act0.py``) — no if/else chains, no dispatcher rewrites.

The runtime layer (step lifecycle, ``resolve_npc_dialogue``, quest-log
objective lookup) lives in :mod:`spacehack.main_quest` so this package
stays focused on static data. Design doc:
``docs/design/in_progress/07_DESIGN_MAIN_QUEST.md``.
"""

from __future__ import annotations

from dataclasses import dataclass, field, replace


@dataclass(frozen=True)
class QuestDialogue:
    """One NPC's dialogue override for a specific quest step.

    The live NPC-talk flow (:func:`spacehack.npc._run_npc_talk`)
    resolves the player's current step status to one of the four
    variant strings and shows it INSTEAD of the NPC's default
    ``flavor_text``. When ``option_label`` is non-empty AND the step
    is in a triggerable state, the modal also appends a menu option
    row; selecting it advances the step (``trigger_on_talk``) and
    plants ``backing_faction`` + ``unlock_item`` per the entry.

    Attributes:
        npc_id: NPC whose talk this dialogue overrides (bar / merchant
            / militia / lab faces share ids across planets — intended,
            the same lead surfaces on Earth and Mars variants).
        trigger_on_talk: True = selecting the option advances the step.
        intro: shown when the step is available (not yet started).
        active: shown while the step is in progress.
        complete: shown after the step is completed (post-completion
            variant — "you're back? what did you learn?").
        locked: shown if prerequisites are not met.
        option_label: menu row text when this dialogue is live
            (e.g. "Tell me about the door"). Empty = no quest option.
        backing_faction: faction relationship/support flag planted when this
            dialogue triggers (militia / merchants / bar / lab). It records
            accumulated history for later investigation and endings; it is
            not a last-claim selector.
        unlock_item: item id added to ``main_quest_unlocked_items``
            when this dialogue triggers (e.g. a quest-granted tool).
            NOTE (Act 0 chains): the seek-help fork no longer grants
            the faction's door tool on accept — the tool comes from
            the chain's final step (``rewards_item`` on the final step).
        locks_chain: True = accepting this dialogue locks the player
            into ``backing_faction``'s chain (``ctx.main_quest_chain``)
            and closes the other factions' offer rows. Used by the
            Act 0 seek-help fork. Requires ``backing_faction``.
        dialogue_planet_id: when non-empty, this dialogue only
            resolves when the player is on the named planet
            (checked against ``ctx.current_city_id``). Empty =
            available on any planet the NPC appears on.
    """

    npc_id: str
    trigger_on_talk: bool = False
    intro: str = ""
    active: str = ""
    complete: str = ""
    locked: str = ""
    option_label: str = ""
    backing_faction: str = ""
    unlock_item: str = ""
    locks_chain: bool = False
    dialogue_planet_id: str = ""


@dataclass(frozen=True)
class MainQuestStep:
    """One story step in the main quest line.

    Steps are never listed on mission boards — they trigger from
    exploration and NPC conversation (see ``trigger_*`` fields).

    Attributes:
        id: registry key, e.g. ``"prologue_signal"``.
        title: display title shown in the quest log + log lines.
            Authored in the story-text JSON (``step.<id>.title``).
        description: 1-3 sentence objective shown in the quest log.
            Authored in the story-text JSON (``step.<id>.description``).
        description_required: True = the build fails if ``description``
            is empty after the overlay (steps like ``prologue_signal``
            that never render a breadcrumb set this False).
        trigger_npc_id: which NPC gives this step (None = auto /
            exploration trigger).
        trigger_planet_id / trigger_system_id: location context for
            the objective (quest-log breadcrumb display).
        requires_step: step id that must be completed first.
        requires_level / requires_rep: optional gates (level, and
            per-faction reputation floor).
        dialogues: per-NPC dialogue overrides keyed by npc_id.
        rewards_credits / rewards_xp: payout on completion.
        rewards_rep: per-faction rep deltas applied on completion.
        rewards_item: item id added to ``main_quest_unlocked_items``
            on completion.
        unlocks_step: step id made available when this step completes,
            in addition to the ``requires_step`` auto-advance. Used by
            chain-final steps and narrative handoffs.
        auto_advance: whether completion should automatically resolve the
            next ``requires_step`` branch. Narrative checkpoints can set
            this false when a separate scene chooses the handoff.
            chain-final steps (q5–q7) to make ``prologue_open``
            available — each faction's final step sets
            ``unlocks_step="prologue_open"`` and grants its door tool
            via ``rewards_item``.
    """

    id: str
    # Prose is NOT authored here — the story-text JSON overlay is the
    # single source of truth (see _apply_text_overlay). Empty after the
    # overlay means a missing key, which _validate_step_prose rejects.
    title: str = ""
    description: str = ""
    description_required: bool = True
    trigger_npc_id: str | None = None
    trigger_planet_id: str | None = None
    trigger_system_id: str | None = None
    requires_step: str | None = None
    requires_level: int = 1
    requires_rep: dict[str, int] | None = None
    dialogues: dict[str, QuestDialogue] = field(default_factory=dict)
    rewards_credits: int = 0
    rewards_xp: int = 0
    rewards_rep: dict[str, int] | None = None
    rewards_item: str | None = None
    unlocks_step: str | None = None
    # False for narrative checkpoints whose next branch is chosen by a
    # separate scene rather than auto-advanced on completion.
    auto_advance: bool = True

    # --- Act 0 faction-chain fields (Phase 1d) ---
    # Faction chain this step belongs to ("militia" / "merchants" /
    # "bar" / "lab"). Empty = not part of a chain. The lock-in flow
    # sets ``ctx.main_quest_chain`` to the chosen faction's id; the
    # chain's q1 step is identified by ``chain == main_quest_chain``.
    chain: str = ""
    # How the step completes outside the dialogue path:
    #   "talk"    — dialogue trigger (default, existing behaviour)
    #   "delve"   — secure the quest cache in the planet's surface
    #               dungeon (see :func:`spacehack.main_quest.prepare_delve_site`)
    #   "smuggle" — deliver hot cargo to a target NPC (mission-hold
    #               semantics; militia scans can confiscate + fail it)
    #   "goods"   — cargo check + consume on trigger
    #   "visit"   — talk to the expert NPC at the target planet
    #   "bounty"  — quest-tagged spawn defeated -> completes
    #   "salvage" — quest-tagged loot secured in a derelict interior
    #   "bump"    — door-bump variant (e.g. lab sample chip)
    objective_type: str = "talk"
    requires_goods: tuple[tuple[str, int], ...] = ()  # (good_id, qty) checked + consumed on trigger
    requires_npc_id: str | None = None  # expert NPC to recruit ("visit") or hot-cargo delivery target ("smuggle")
    requires_spawn_id: str | None = None  # quest-tagged bounty/salvage spawn id ("bounty"/"salvage")
    bounty_enemy_id: str = ""  # enemy ship id for the quest-tagged "bounty" spawn
                                # (e.g. "militia_patrol" — the bar chain's gauntlet)
    bounty_escort_ids: tuple[str, ...] = ()  # extra enemy_ids for escort spawns
                                # alongside the leader (e.g. ("pirate_raider", "pirate_raider"))
                                # — escorts don't trigger step completion
    salvage_wreck_enemy_id: str = ""  # NpcShipSpec id for the boarded wreck ("salvage")
                                # (e.g. "derelict_scout") — non-combatant, boardable
    salvage_layout_id: str = ""  # interior layout for the wreck ("salvage")
                                # (e.g. "scout_a") — quest-tagged loot placed inside
    # (good_id, qty) pairs placed in the quest cache ("delve") — the
    # cache yields these. ``trigger_planet_id`` names the delve planet.
    delve_good_ids: tuple[tuple[str, int], ...] = ()
    smuggle_good_id: str = ""  # hot cargo id ("smuggle")
    smuggle_cargo_size: int = 0  # volume of the hot crate ("smuggle")
    smuggle_hot: bool = True  # True = militia scans can confiscate the
                              # crate (bar chain: every patrol is a
                              # risk). False = plain mission cargo that
                              # must NEVER be confiscatable (lab
                              # datasets, militia requisition, merchant
                              # ore) — a single scan would softlock the
                              # chain, since the receiver's quest option
                              # is suppressed while the crate isn't held
                              # and a confiscated crate had no re-issue
                              # path.
    # Faction-heat behavior tags consumed by the generic heat handler
    # (main_quest/_heat.py). Empty = no heat. Expiry is implicit: the
    # final chain step carries no tag, so once it is the only live step
    # the heat filters naturally return False.
    heat: tuple[str, ...] = ()  # e.g. ("militia_scan", "militia_aggro") / ("consortium",)
    # Quest-NPC presence (Phase 3): quest NPC ids that appear on the
    # step's ``trigger_planet_id`` while this step is live (status
    # available/active) — then vanish once it completes. The NPC is
    # placed additively at the planet's matching ``quest_npc_spot``
    # (see PlanetSpec), never replacing the building's regular NPC.
    # Chain-gated by the runtime: only applies when
    # ``ctx.main_quest_chain`` matches this step's ``chain``.
    npc_presence: tuple[str, ...] = ()  # e.g. ("old_smuggler",)
    # Scene identifier (Phase 3): names the cutscene that plays at
    # this step's beat, resolved through main_quest/_scenes.py. The
    # presentation is always written in code FIRST; the step data
    # only declares WHICH scene triggers. Empty = no cutscene at this
    # beat (generic log/readout flows only). An id with no registered
    # implementation fails loudly in smoke, never silently in-game.
    scene: str = ""  # e.g. "prologue_transmission" / "sealed_door_open"
    # Whether this step's crate auto-loads into the mission hold the
    # moment the step becomes available right after a completion
    # (delve/bump/salvage → next smuggle). Default True keeps the
    # existing chains' flow (bar_q3 → bar_q4, lab_q5 → lab_q6_return,
    # ...); set False when the load must be player-initiated.
    auto_load_next_smuggle: bool = True
    # --- Time-gating fields (minimum waits, never deadlines) ---
    wait_days: int = 0  # world-clock days the faction "works" after this step
                        # completes before the NEXT step unlocks (0 = no gate)
    completion_flavor: str = ""  # flavor logged on completion ("We'll be in touch.")
    ready_message: str = ""  # one-way summon sent when the wait elapses — names
                              # the next step's system + planet


def _apply_text_overlay(_step: MainQuestStep) -> MainQuestStep:
    """Resolve one step's prose from the story-text JSON overlay.

    Step data in this package is structural only — titles,
    descriptions, completion flavor, and dialogue text live in the
    JSON files under ``src/spacehack/data/text/``. Each lookup is a
    ``step.<id>.<field>`` / ``step.<id>.dialogue.<npc>.<variant>``
    key; a missing key leaves the field empty, which the build-time
    validation in :func:`_build_registry` rejects.
    """
    from ...text import overlay as _text_overlay
    _text = _text_overlay()
    _changes: dict[str, object] = {}
    for _field in ("title", "description", "completion_flavor", "ready_message"):
        _key = f"step.{_step.id}.{_field}"
        if _key in _text:
            _changes[_field] = _text[_key]
    _dialogues: dict[str, QuestDialogue] = {}
    for _npc_id, _dialogue in _step.dialogues.items():
        _replace: dict[str, str] = {}
        for _variant in ("intro", "active", "complete", "locked", "option_label"):
            _key = f"step.{_step.id}.dialogue.{_npc_id}.{_variant}"
            if _key in _text:
                _replace[_variant] = _text[_key]
        _dialogues[_npc_id] = replace(_dialogue, **_replace) if _replace else _dialogue
    if _dialogues:
        _changes["dialogues"] = _dialogues
    return replace(_step, **_changes) if _changes else _step


def _iter_raw_steps():
    """Yield every step catalog module's raw (pre-overlay) steps."""
    import importlib
    import pkgutil

    for _finder, name, _ispkg in pkgutil.iter_modules(__path__):
        if name.startswith("_"):
            continue
        mod = importlib.import_module(f"{__name__}.{name}")
        if not hasattr(mod, "STEPS"):
            continue
        yield from mod.STEPS


def list_raw_main_quest_steps() -> tuple[MainQuestStep, ...]:
    """All registered steps WITHOUT the text overlay applied.

    Structural only (ids, triggers, rewards, dialogue NPC keys) — prose
    fields are empty. Used by the extractor/validator, which must not
    trigger the overlay build.
    """
    return tuple(_iter_raw_steps())


def _validate_step_prose(_step: MainQuestStep) -> None:
    """Fail loudly when a step is missing required story text.

    Prose lives only in the JSON overlay, so an empty title (or an
    empty description on a step that requires one) means a key is
    missing from ``src/spacehack/data/text/``. Raise instead of
    silently rendering blank text.
    """
    if not _step.title:
        raise ValueError(
            f"main quest step {_step.id!r} is missing its title; add "
            f"step.{_step.id}.title to the story-text JSON."
        )
    if _step.description_required and not _step.description:
        raise ValueError(
            f"main quest step {_step.id!r} is missing its description; add "
            f"step.{_step.id}.description to the story-text JSON."
        )


def _build_registry() -> dict[str, MainQuestStep]:
    """Resolve every step's prose from the overlay and validate it.

    Every module exporting a ``STEPS`` tuple is auto-discovered — drop
    a new ``.py`` in ``data/main_quest/`` and it's picked up without
    touching any registry code. The JSON overlay is applied here, so
    every lookup sees the overlaid strings, then each step is checked
    for missing required text.
    """
    combined: dict[str, MainQuestStep] = {}
    for _raw in _iter_raw_steps():
        _step = _apply_text_overlay(_raw)
        _validate_step_prose(_step)
        combined[_step.id] = _step
    return combined


_BY_ID: dict[str, MainQuestStep] | None = None


def _registry() -> dict[str, MainQuestStep]:
    global _BY_ID
    if _BY_ID is None:
        _BY_ID = _build_registry()
    return _BY_ID


def find_main_quest_step(step_id: str) -> MainQuestStep:
    """Look up a :class:`MainQuestStep` by id; raises :class:`KeyError` on miss."""
    try:
        return _registry()[step_id]
    except KeyError:
        raise KeyError(f"unknown main quest step id: {step_id!r}") from None


def list_main_quest_steps() -> tuple[MainQuestStep, ...]:
    """All registered main quest steps, in registry order."""
    return tuple(_registry().values())


def reload_text_overlay() -> None:
    """Re-parse the text overlay and rebuild the registry (dev F5)."""
    global _BY_ID
    from ...text import reload as _reload_text
    _reload_text()
    _BY_ID = None


def main_quest_step_after(step_id: str, *, chain: str = "") -> MainQuestStep | None:
    """Return the next step that requires ``step_id`` (for auto-advance).

    With ``chain`` set (the locked faction), steps belonging to a
    DIFFERENT faction chain are skipped — so after the seek-help fork
    completes, only the locked chain's q1 step advances even though
    all four q1 steps require ``prologue_seek_help``.
    """
    for _step in _registry().values():
        if _step.requires_step == step_id:
            if chain and _step.chain and _step.chain != chain:
                continue
            return _step
    return None


__all__ = [
    "QuestDialogue",
    "MainQuestStep",
    "find_main_quest_step",
    "list_main_quest_steps",
    "list_raw_main_quest_steps",
    "main_quest_step_after",
    "reload_text_overlay",
]
