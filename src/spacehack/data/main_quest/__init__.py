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

from dataclasses import dataclass, field


@dataclass(frozen=True)
class QuestDialogue:
    """One NPC's dialogue override for a specific quest step.

    The live NPC-talk modal (:func:`spacehack.npc.render_npc_talk`)
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
        backing_faction: faction claim planted when this dialogue
            triggers (militia / merchants / bar / lab). Read by the
            Act 3 epilogue ("last claim wins").
        unlock_item: item id added to ``main_quest_unlocked_items``
            when this dialogue triggers (e.g. a quest-granted tool).
            NOTE (Act 0 chains): the seek-help fork no longer grants
            the faction's door tool on accept — the tool comes from
            the chain's final step (``rewards_item`` on the q5 step).
        locks_chain: True = accepting this dialogue locks the player
            into ``backing_faction``'s chain (``ctx.main_quest_chain``)
            and closes the other factions' offer rows. Used by the
            Act 0 seek-help fork. Requires ``backing_faction``.
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


@dataclass(frozen=True)
class MainQuestStep:
    """One story step in the main quest line.

    Steps are never listed on mission boards — they trigger from
    exploration and NPC conversation (see ``trigger_*`` fields).

    Attributes:
        id: registry key, e.g. ``"prologue_signal"``.
        title: display title shown in the quest log + log lines.
        description: 1-3 sentence objective shown in the quest log.
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
            chain-final steps (q5) to make ``prologue_open`` available
            — each faction's q5 sets ``unlocks_step="prologue_open"``
            and grants its door tool via ``rewards_item``.
    """

    id: str
    title: str
    description: str
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
    delve_good_ids: tuple[str, ...] = ()  # goods placed in the quest cache ("delve") — cache yields these
    smuggle_good_id: str = ""  # hot cargo id ("smuggle")
    smuggle_cargo_size: int = 0  # volume of the hot crate ("smuggle")
    # --- Time-gating fields (minimum waits, never deadlines) ---
    wait_days: int = 0  # world-clock days the faction "works" after this step
                        # completes before the NEXT step unlocks (0 = no gate)
    completion_flavor: str = ""  # flavor logged on completion ("We'll be in touch.")
    ready_message: str = ""  # one-way summon sent when the wait elapses — names
                              # the next step's system + planet


def _build_registry() -> dict[str, MainQuestStep]:
    """Auto-discover every step catalog under this package.

    Every module exporting a ``STEPS`` tuple is automatically
    registered — just drop a new ``.py`` in ``data/main_quest/`` and
    it's picked up without touching any registry code. Each step's
    ``dialogues`` field is authored as a dict keyed by ``npc_id``
    (see :class:`QuestDialogue`), so the runtime looks up by
    ``npc_id`` directly.
    """
    import importlib
    import pkgutil

    combined: dict[str, MainQuestStep] = {}
    for _finder, name, _ispkg in pkgutil.iter_modules(__path__):
        if name.startswith("_"):
            continue
        mod = importlib.import_module(f"{__name__}.{name}")
        if not hasattr(mod, "STEPS"):
            continue
        for _raw in mod.STEPS:
            combined[_raw.id] = _raw
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
    "main_quest_step_after",
]
