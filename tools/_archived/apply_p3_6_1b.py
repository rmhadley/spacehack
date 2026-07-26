"""One-shot script for P3.6.1b application.

Reads the AST-transformer dry-run output at ``/tmp/migrated_main.py``,
applies 10 BLOCKER hand-fixes the AST transformer closed in
P3.6.1c can't handle, then copies the result over
``spacehack/src/spacehack/__main__.py``.

**10 BLOCKER hand-fixes** (in apply order):

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
   cause as Fix 1.

3a. ``_run_pick`` reverted to take raw
   ``context: tcod.context.Context`` instead of ``ctx:
   GameContext``. Its caller (:func:`run`) is the character-creation
   dispatcher which fires BEFORE :func:`_run_game` constructs the
   main ``ctx`` -- so a ``ctx`` argument would be None at call time.

3b. Same as 3a for ``_run_confirm``.

3c. Revert ``_run_pick``'s internal ``ui.Modal(ctx.context, console)``
   call back to ``ui.Modal(context, console)`` -- since its
   parameter is now named ``context`` again.

3d. Same as 3c for ``_run_confirm``. Anchor tightened to the
   unique ``action = ui.update_confirm(event)`` + adjacent return
   pattern so it ONLY matches ``_run_confirm``.

4. ``_animate_jump(ctx, ...)`` -> ``_animate_jump(ctx.context, ...)``.
   ``_animate_jump`` is called from inside ``_run_jump_menu``'s
   body (TARGET_FUNCTIONS), so its call-site ``context`` arg got
   renamed to ``ctx`` -- but ``_animate_jump``'s signature is
   unchanged. Re-pair the call site with ``ctx.context.``.

5. ``_run_pick(ctx, ...)`` and ``_run_confirm(ctx, ...)`` call-sites
   in :func:`run` reverted to ``(context, ...)`` to match the
   reverted signatures from 3a+3b (the AST transformer's cross-modal
   call-site rewrite fires UNCONDITIONALLY for any ``_XXX`` whose
   name is in ``TARGET_FUNCTIONS``, including from ``run()`` which
   has no ``ctx`` in scope).

6. ``render_navigation(console, ...)`` -> ``render_navigation(console, ctx, ...)``.
   New render_X signatures took ``(console, ctx, *, ...)`` but the
   call site didn't have ``ctx`` inserted.

7. ``render_jump_menu(console, jp, target_system_id, ...)`` ->
   ``render_jump_menu(console, ctx, jp, target_system_id, ...)``.
   Same root cause as 6.

9. ``render_npc_talk(console, npc, ...)`` ->
   ``render_npc_talk(console, ctx, npc, ...)``. Same as 6.

10. ``render_mission_offerings(console, npc, offerings, selected, ...)`` ->
    ``render_mission_offerings(console, ctx, npc, offerings, selected, ...)``.
    Same as 6.

14. ``render_planet_menu(console, planet_obj, has_port=has_port)`` ->
    ``render_planet_menu(console, ctx, planet_obj, has_port=has_port)``.
    Same as 6.

**Obsolete after P3.6.1c migrator amend** (kept here for traceability
of the migration history; the patterns below are no-ops in current
state because the amend drops them at the transformer source):

* OLD Fix 8: ``render_ship_buy(console, ship, ctx.stats, ...)`` -> drop
  ``ctx.stats`` -- obsoleted by LOOSE_ARG_NAMES widening in
  :meth:`tools.migrate_modal_to_ctx.ContextTransformer.visit_Call`.
* OLD Fix 11: ``render_quest_log(console, ctx.player_active_mission, ...)``
  -> drop ctx.player_active_mission -- obsoleted by the
  ``ast.Attribute`` arm in visit_Call.
* OLD Fix 12: ``render_ship_menu(console, ship, ctx.player_owned_ship, ...)``
  -> drop ctx.player_owned_ship -- same reason.
* OLD Fix 13: ``render_ship_view(console, ship, ctx.player_owned_ship, ...)``
  -> drop ctx.player_owned_ship -- same reason.
* OLD Fix 15: ``_run_quest_log(ctx, player_active_mission)`` ->
  ``(ctx,)`` -- obsoleted by LOOSE_ARG_NAMES values-side widening.
* OLD Fix 16: ``_run_ship_menu(ctx, ship, player_owned_ship)`` ->
  ``(ctx, ship)`` -- same reason.
* OLD Fix 17: ``_run_ship_view(ctx, ship, ctx.player_owned_ship, ctx.log)``
  -> ``(ctx, ship)`` -- obsoleted by Attribute-arm.

**Known NOT-handled** (deferred to future P#s):

- P3.6.2: replace remaining ``_run_game`` locals with ``ctx.X``
  references -- covers fields the migrator doesn't reach:
  ``_handle_combat_encounter``, ``_jump_to_system``,
  ``_launch_to_space``, ``_return_to_city``,
  ``_detect_combat_encounter``, ``_animate_jump``.
- P3 finish: ``_run_goto`` TODO(P3) -- extract the Bresenham/A*
  animation phase into a ``_animate_auto_nav`` helper so the menu
  phase can be migrated to ``ui.Modal``.
- Auto-nav vs ``update_X`` callback migration -- deferred.

**External render_X calls NOT touched**:
``message_log.render_message_log``, ``world.render_world_view``,
``world.render_world``, ``hud.render_hud`` -- their signatures
live in modules outside TARGET_FUNCTIONS, were not migrated, and
still take ``(console, log, ...)`` / ``(console, game_map, ...)``
unchanged. Calls that pass ``ctx.log`` / ``ctx.game_map`` bind
correctly to those unchanged sig slots (just changing the source
of the value).
"""
from __future__ import annotations

from pathlib import Path


DRY_RUN_PATH = Path("/tmp/migrated_main.py")
TARGET_PATH = Path("src/spacehack/__main__.py")


def apply_hand_fixes(text: str) -> str:
    """Apply the 10 BLOCKER hand-fixes to the dry-run output."""
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
    text = text.replace(
        "outcome = ui.Modal(ctx.context, console).run(_render, _update)\n    if outcome is Outcome.CONFIRM:",
        "outcome = ui.Modal(context, console).run(_render, _update)\n    if outcome is Outcome.CONFIRM:",
    )

    # Fix 3d: revert the ui.Modal call inside _run_confirm ONLY.
    # Tightened to a multi-line anchor that includes _run_confirm's
    # unique ``action = ui.update_confirm(event)``, the closing
    # ``return Outcome.IGNORE`` line, and the adjacent
    # ``return ui.Modal(...)`` call (no blank line between them, vs
    # _run_pick which has a blank line + ``outcome = ui.Modal(...)``).
    text = text.replace(
        "action = ui.update_confirm(event)\n"
        "        if action is ui.MenuAction.CONFIRM:\n"
        "            return Outcome.CONFIRM\n"
        "        if action is ui.MenuAction.BACK:\n"
        "            return Outcome.BACK\n"
        "        return Outcome.IGNORE\n"
        "    return ui.Modal(ctx.context, console).run(_render, _update)",
        "action = ui.update_confirm(event)\n"
        "        if action is ui.MenuAction.CONFIRM:\n"
        "            return Outcome.CONFIRM\n"
        "        if action is ui.MenuAction.BACK:\n"
        "            return Outcome.BACK\n"
        "        return Outcome.IGNORE\n"
        "    return ui.Modal(context, console).run(_render, _update)",
    )

    # Fix 4: ``_animate_jump`` is called from inside ``_run_jump_menu``'s
    # body, so visit_Name rewrote the call's ``context`` arg to ``ctx``.
    # But ``_animate_jump``'s signature is unchanged -- still raw
    # ``tcod.context.Context``. Re-pair with ``ctx.context.``.
    text = text.replace("_animate_jump(ctx, ", "_animate_jump(ctx.context, ")

    # Fix 5: revert _run_pick / _run_confirm call site arg name
    # (cross-modal call rewrite fired from run() scope which has
    # no ctx).
    text = text.replace("_run_pick(ctx, ", "_run_pick(context, ")
    text = text.replace("_run_confirm(ctx, ", "_run_confirm(context, ")

    # Fixes 6, 7, 9, 10, 14: render_X ctx insertion.
    # The AST transformer rewrote render_X signatures to insert ctx as
    # 2nd positional, but does NOT auto-insert ctx at the call sites.
    # Only the FIXES for call sites whose arg list DOESN'T transitively
    # pass ctx are still needed here -- the ones where the old shape
    # had a ctx.stats/ctx.player_owned_ship/etc. Attribute were
    # obsoleted by P3.6.1c's migrator amend (KeyError-style visit_Call
    # drop + Attribute arm + LOOSE_ARG_NAMES widening).

    # Fix 6: render_navigation -- INSERT ctx after console.
    text = text.replace(
        "render_navigation(console, screen_width=SCREEN_WIDTH, screen_height=SCREEN_HEIGHT, ship_pos=ship_pos)",
        "render_navigation(console, ctx, screen_width=SCREEN_WIDTH, screen_height=SCREEN_HEIGHT, ship_pos=ship_pos)",
    )

    # Fix 7: render_jump_menu -- INSERT ctx after console.
    text = text.replace(
        "render_jump_menu(console, jp, target_system_id",
        "render_jump_menu(console, ctx, jp, target_system_id",
    )

    # Fix 9: render_npc_talk -- INSERT ctx after console.
    text = text.replace(
        "render_npc_talk(console, npc, screen_width=SCREEN_WIDTH, screen_height=SCREEN_HEIGHT, deliver_mission=deliver_mission, selected=selected)",
        "render_npc_talk(console, ctx, npc, screen_width=SCREEN_WIDTH, screen_height=SCREEN_HEIGHT, deliver_mission=deliver_mission, selected=selected)",
    )

    # Fix 10: render_mission_offerings -- INSERT ctx after console.
    text = text.replace(
        "render_mission_offerings(console, npc, offerings, selected, screen_width=SCREEN_WIDTH, screen_height=SCREEN_HEIGHT)",
        "render_mission_offerings(console, ctx, npc, offerings, selected, screen_width=SCREEN_WIDTH, screen_height=SCREEN_HEIGHT)",
    )

    # Fix 14: render_planet_menu -- INSERT ctx after console.
    text = text.replace(
        "render_planet_menu(console, planet_obj, has_port=has_port)",
        "render_planet_menu(console, ctx, planet_obj, has_port=has_port)",
    )

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
