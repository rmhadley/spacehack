"""Quest-chain linter: authoring rules as a commit-time diagnostic.

The doc-33 lesson applied to quests (the city-audit lesson before it):
rules learned by failing gates or playtests one at a time belong in a
trusted report that runs on every chain at once, at commit time
instead of playtest time. check_main_quest.py keeps the hard contract
(handlers, refs, tags, required text); this file carries the softer
authoring surface.

Usage: ``python3 tools/quest_lint.py`` — exit 1 on any ERROR
(must fix), 0 with WARNINGs allowed. ``make check`` runs it.
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src.spacehack.data.main_quest import (  # noqa: E402
    find_main_quest_step,
    list_main_quest_steps,
)
from src.spacehack.data.planets import find_planet_spec  # noqa: E402
from src.spacehack.data.trade_goods import find_trade_good  # noqa: E402
from src.spacehack.text import overlay  # noqa: E402

# Steps that exist to be scheduled by code, not the chain walk; their
# Q text arrives via bespoke breadcrumbs.
_UNSUMMONED = frozenset({"prologue_open"})

_SALVAGE_TYPES = frozenset({"salvage"})
_DELVE_TYPES = frozenset({"delve"})


def _overlay_text(step_id: str, suffix: str) -> str:
    return overlay().get(f"step.{step_id}.{suffix}", "")


def _check_two_text_gates(errors: list[str]) -> None:
    """Every wait-gated step carries the flavor + ready pair."""
    for step in list_main_quest_steps():
        if step.id in _UNSUMMONED or step.wait_days <= 0:
            continue
        if not _overlay_text(step.id, "completion_flavor"):
            errors.append(
                f"gated step {step.id!r} has no completion_flavor "
                f"(the wait shows nothing)"
            )
        if not _overlay_text(step.id, "ready_message"):
            errors.append(
                f"gated step {step.id!r} has no ready_message "
                f"(the gate clears silently)"
            )


def _check_trigger_dialogue_labels(errors: list[str]) -> None:
    """A trigger_on_talk dialogue renders an option row: it needs the
    option_label key."""
    for step in list_main_quest_steps():
        for npc_id, dlg in step.dialogues.items():
            if not getattr(dlg, "trigger_on_talk", False):
                continue
            if not _overlay_text(step.id, f"dialogue.{npc_id}.option_label"):
                errors.append(
                    f"step {step.id!r} dialogue {npc_id!r} is "
                    f"trigger_on_talk but has no option_label"
                )


def _check_smuggle_active_texts(errors: list[str]) -> None:
    """Two-ended smuggle steps: while the crate is in flight the giver
    AND receiver show their active variant."""
    for step in list_main_quest_steps():
        if step.objective_type != "smuggle":
            continue
        for npc_id in step.dialogues:
            if not _overlay_text(step.id, f"dialogue.{npc_id}.active"):
                errors.append(
                    f"smuggle step {step.id!r} is missing "
                    f"dialogue.{npc_id}.active (the en-route variant)"
                )


def _check_quest_cargo(errors: list[str]) -> None:
    """Quest cargo is named quest goods or virtual mission cargo —
    never market goods (the recorder standard, enforced at authoring
    time instead of only in tests)."""
    for step in list_main_quest_steps():
        good_ids = [gid for gid, _qty in step.delve_good_ids]
        if step.smuggle_good_id:
            good_ids.append(step.smuggle_good_id)
        good_ids += [gid for gid, _qty in step.rewards_goods]
        for gid in good_ids:
            try:
                good = find_trade_good(gid)
            except KeyError:
                continue  # virtual mission cargo
            if good.rarity > 0.1:
                errors.append(
                    f"step {step.id!r} hands out market good "
                    f"{gid!r} (rarity {good.rarity}) — quest cargo is "
                    f"named quest goods or virtual"
                )


def _check_crate_size_reconciliation(errors: list[str]) -> None:
    """A step's delve loot that feeds the NEXT step's crate must match
    its size: the texts say 'the cell', the crate carries one."""
    for step in list_main_quest_steps():
        if not step.requires_step:
            continue
        try:
            prev = find_main_quest_step(step.requires_step)
        except KeyError:
            continue
        if prev.objective_type not in _DELVE_TYPES:
            continue
        for gid, qty in prev.delve_good_ids:
            if step.smuggle_good_id == gid:
                if step.smuggle_cargo_size != qty:
                    errors.append(
                        f"step {step.id!r} crates {gid} x{step.smuggle_cargo_size} "
                        f"but {prev.id!r} delves x{qty} — the recovered "
                        f"goods ARE the crate; sizes must match"
                    )


def _check_delve_camp_guardians(errors: list[str]) -> None:
    """A step with an authored delve layout owns its guardians
    in-layout (ENEMY: markers); the planet pool stays for layout-less
    delves only."""
    for step in list_main_quest_steps():
        if not step.delve_layout_id or not step.trigger_planet_id:
            continue
        try:
            params = find_planet_spec(step.trigger_planet_id).dungeon_params
        except (KeyError, AttributeError):
            continue
        if params and params.cache_guardian_pool:
            errors.append(
                f"step {step.id!r} has delve_layout_id "
                f"{step.delve_layout_id!r} but {step.trigger_planet_id!r} "
                f"still declares a cache_guardian_pool — guardians are "
                f"authored in the layout"
            )


def _orphaned_step_keys() -> list[str]:
    known = {f"step.{step.id}" for step in list_main_quest_steps()}
    return sorted(
        key for key in overlay()
        if key.startswith("step.") and key.split(".")[1] not in
        {k.split(".", 2)[1] for k in known} | {k.rsplit(".", 2)[1] for k in known}
    )


def _check_orphaned_text(errors: list[str]) -> None:
    """Overlay step.* keys whose step id matches nothing in the
    catalog (renames/removals that left text behind)."""
    _known_ids = {step.id for step in list_main_quest_steps()}
    for key in sorted(overlay()):
        if not key.startswith("step."):
            continue
        step_id = key.split(".")[1]
        if step_id not in _known_ids:
            errors.append(f"orphaned text key {key!r} (no such step id)")


def _cadence_report() -> list[str]:
    lines = []
    chains: dict[str, list] = {}
    for step in list_main_quest_steps():
        chains.setdefault(step.chain or "prologue", []).append(step)
    for chain, steps in sorted(chains.items()):
        waits = sum(s.wait_days for s in steps)
        gated = sum(1 for s in steps if s.wait_days > 0)
        lines.append(
            f"  {chain:10s} {len(steps):2d} steps, {gated} waits, "
            f"{waits:3d} gate-days"
        )
    return lines


def main() -> int:
    errors: list[str] = []
    _check_two_text_gates(errors)
    _check_trigger_dialogue_labels(errors)
    _check_smuggle_active_texts(errors)
    _check_quest_cargo(errors)
    _check_crate_size_reconciliation(errors)
    _check_delve_camp_guardians(errors)
    _check_orphaned_text(errors)

    print("quest lint — cadence per chain:")
    for line in _cadence_report():
        print(line)
    if errors:
        print(f"\nFAIL: {len(errors)} quest lint error(s):")
        for error in errors:
            print(f"  - {error}")
        return 1
    print("\nPASS: quest lint OK.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
