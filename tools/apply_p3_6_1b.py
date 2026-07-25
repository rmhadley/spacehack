"""One-shot script for P3.6.1b application.

Reads the AST-transformer dry-run output at ``/tmp/migrated_main.py``,
applies 3 BLOCKER hand-fixes the dry-run couldn't handle, then
copies the result over ``spacehack/src/spacehack/__main__.py``.

**3 BLOCKER hand-fixes**:

1. ``ctx.present(console)`` -> ``ctx.context.present(console)``
   in modal bodies that bypass ``ui.Modal`` (currently just
   ``_run_goto`` which uses raw SDL pathway). The AST transformer
   mechanically renames ``context`` -> ``ctx`` everywhere, so a
   raw call like ``context.present(console)`` becomes
   ``ctx.present(console)`` -- but ``ctx`` is a
   :class:`~spacehack.game_context.GameContext` whose ``present``
   attribute doesn't exist. Hand-fix prefixes with ``ctx.context.``

2. ``ctx.convert_event(event)`` -> ``ctx.context.convert_event(event)``
   inside ``_run_jump_menu``'s ``_update`` closure. Same root
   cause: ``Context.convert_event`` is a tcod API on the
   ``tcod.context.Context``, not on ``GameContext``. After
   migration the call becomes ``ctx.convert_event(event)`` --
   prefix with ``ctx.context.``.

3. ``_run_pick`` and ``_run_confirm`` reverted to take raw
   ``context: tcod.context.Context`` instead of ``ctx:
   GameContext``. Their call sites are in the character-creation
   loop (``_run`` dispatcher) which fires BEFORE :func:`_run_game`
   constructs the main ``ctx`` -- so a ``ctx`` argument would be
   None. Easiest fix is to carve these two functions out of
   transformation: revert their signatures back to ``(context,
   menu)`` and ``(context, species_id, class_id)`` and update
   their internal ``ui.Modal(ctx.context, console)`` calls to
   ``ui.Modal(context, console)``.

**Known NOT-handled**:

- P3.6.2 (replace remaining ``_run_game`` locals with ``ctx.X``
  references) -- deferred to a follow-up commit so this one stays
  scoped.

- ``update_X`` callback migration -- deferred; their signatures
  stay loose-parameter and the call sites still close over
  ``ctx.X`` from the outer modal scope.
"""
from __future__ import annotations

from pathlib import Path


DRY_RUN_PATH = Path("/tmp/migrated_main.py")
TARGET_PATH = Path("src/spacehack/__main__.py")


def apply_hand_fixes(text: str) -> str:
    """Apply the 3 BLOCKER hand-fixes to the dry-run output."""
    # Fix 1 + 2: ctx.present / ctx.convert_event -> ctx.context.X
    # Apply globally; these patterns only appear in modal bodies
    # that use raw Context APIs (NOT through ui.Modal).
    text = text.replace("ctx.present(", "ctx.context.present(")
    text = text.replace("ctx.convert_event(", "ctx.context.convert_event(")

    # Fix 3a: revert _run_pick signature.
    text = text.replace(
        "def _run_pick(ctx, menu: ui.MenuScreen)",
        "def _run_pick(context: tcod.context.Context, menu: ui.MenuScreen)",
    )

    # Fix 3b: revert _run_confirm signature.
    text = text.replace(
        "def _run_confirm(ctx, species_id: str, class_id: str)",
        "def _run_confirm(context: tcod.context.Context, species_id: str, class_id: str)",
    )

    # Fix 3c: revert the ui.Modal call inside _run_pick.
    # This is inside the _run_pick body so the ctx.context was just
    # an artifact of the transformer renaming ``context`` -> ``ctx``
    # within modal bodies. Now that the parameter is named
    # ``context`` again, the call should pass ``context`` directly.
    text = text.replace(
        "outcome = ui.Modal(ctx.context, console).run(_render, _update)\n    if outcome is Outcome.CONFIRM:",
        "outcome = ui.Modal(context, console).run(_render, _update)\n    if outcome is Outcome.CONFIRM:",
    )

    # Fix 3d: revert the ui.Modal call inside _run_confirm.
    text = text.replace(
        "return ui.Modal(ctx.context, console).run(_render, _update)",
        "return ui.Modal(context, console).run(_render, _update)",
    )

    # Fix 4: ``_animate_jump`` is called from inside ``_run_jump_menu``'s
    # body (which IS in TARGET_FUNCTIONS), so visit_Name rewrites the
    # ``_animate_jump(context, ...)`` call to ``_animate_jump(ctx, ...)``.
    # But ``_animate_jump``'s signature is unchanged (NOT in TARGETS)
    # and still takes raw ``context: tcod.context.Context`` -- so we
    # need to prefix with ``ctx.context.`` on every call site:
    text = text.replace("_animate_jump(ctx, ", "_animate_jump(ctx.context, ")

    return text


def main() -> None:
    if not DRY_RUN_PATH.exists():
        raise SystemExit(
            f"Dry-run output missing: {DRY_RUN_PATH}. "
            "Re-run transformer: "
            "python3 -c 'from tools.migrate_modal_to_ctx import migrate_source; print(migrate_source(open(\"src/spacehack/__main__.py\").read()))' "
            "> /tmp/migrated_main.py"
        )

    dry_run_text = DRY_RUN_PATH.read_text()
    fixed_text = apply_hand_fixes(dry_run_text)

    TARGET_PATH.write_text(fixed_text)
    print(
        f"P3.6.1b applied: {len(dry_run_text)} -> {len(fixed_text)} chars "
        f"({len(fixed_text) - len(dry_run_text):+d})"
    )


if __name__ == "__main__":
    main()
