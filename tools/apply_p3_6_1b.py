"""One-shot script for P3.6.1b application.

Reads the AST-transformer dry-run output at ``/tmp/migrated_main.py``,
applies 14 BLOCKER hand-fixes the dry-run couldn't handle, then
copies the result over ``spacehack/src/spacehack/__main__.py``.

**17 BLOCKER hand-fixes** (in apply order):

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

3a. ``_run_pick`` reverted to take raw
   ``context: tcod.context.Context`` instead of ``ctx:
   GameContext``. Its caller (:func:`run`) is the character-creation
   dispatcher which fires BEFORE :func:`_run_game` constructs the
   main ``ctx`` -- so a ``ctx`` argument would be None.

3b. Same as 3a for ``_run_confirm``.

3c. Revert ``_run_pick``'s internal ``ui.Modal(ctx.context, console)``
   call back to ``ui.Modal(context, console)`` -- since its
   parameter is now named ``context`` again.

3d. Same as 3c for ``_run_confirm``.

4. ``_animate_jump(ctx, ...)`` -> ``_animate_jump(ctx.context, ...)``.
   ``_animate_jump`` is called from inside ``_run_jump_menu``'s
   body (TARGET_FUNCTIONS), so its call-site ``context`` arg got
   renamed to ``ctx`` -- but ``_animate_jump``'s signature is
   unchanged. Re-pair the call site.

5. ``_run_pick(ctx, ...)`` and ``_run_confirm(ctx, ...)``
   call-sites in :func:`run` reverted to ``(context, ...)`` so
   they match the reverted signatures from 3a+3b. The AST
   transformer's cross-modal call-site rewrite fires UNCONDITIONALLY
   for any ``_XXX`` whose name is in ``TARGET_FUNCTIONS``, so
   even call-sites in non-TARGET bodies like :func:`run` got the
   rename. THIS was the bug the user hit on first launch:
   ``NameError: name 'ctx' is not defined`` at the first
   ``_run_pick(ctx, ui.species_menu())`` call.

6. ``render_navigation(console, ...)`` -> ``render_navigation(console, ctx, ...)``.
   ``render_navigation``'s signature was rewritten to
   ``(console, ctx, *, screen_width, screen_height, ship_pos, ...)``
   but the call site inside ``_run_navigation``'s ``_render``
   closure was only dropped of loose args -- ``ctx`` was NOT
   inserted. Insert it.

7. ``render_jump_menu(console, ...)`` -> ``render_jump_menu(console, ctx, ...)``.
   Same problem as 6 for ``render_jump_menu``. The new sig is
   ``(console, ctx, jp, target_system_id, *, ...)``.

8. ``render_ship_buy(console, ship, ctx.stats, ...)`` ->
   ``render_ship_buy(console, ctx, ship, ...)``.
   Two-part fix:
   a) Insert ``ctx`` (new sig is ``(console, ctx, ship, *, ...)``).
   b) Remove the now-orphan ``ctx.stats`` positional -- the new
      body reads ``ctx.stats`` internally instead of receiving it
      as an arg.

9. ``render_npc_talk(console, ...)`` -> ``render_npc_talk(console, ctx, ...)``.
   Same problem as 6 for ``render_npc_talk``.

10. ``render_mission_offerings(console, ...)`` ->
    ``render_mission_offerings(console, ctx, ...)``. Same as 6.

11. ``render_quest_log(console, ctx.player_active_mission, ...)`` ->
    ``render_quest_log(console, ctx, ...)``. Insert ``ctx`` AND
    drop the orphan ``ctx.player_active_mission`` positional --
    the new body reads ``ctx.player_active_mission`` internally.

12. ``render_ship_menu(console, ship, ctx.player_owned_ship, ...)`` ->
    ``render_ship_menu(console, ctx, ship, ...)``. Insert ``ctx``
    AND drop orphan ``ctx.player_owned_ship`` -- new body reads
    it via ``ctx``.

13. ``render_ship_view(console, ship, ctx.player_owned_ship, ...)`` ->
    ``render_ship_view(console, ctx, ship, ...)``. Same dual fix
    as 12.

14. ``render_planet_menu(console, planet_obj, has_port=has_port)`` ->
    ``render_planet_menu(console, ctx, planet_obj, has_port=has_port)``.
    Just insert ``ctx``.

15. ``_run_quest_log(ctx, player_active_mission)`` ->
    ``_run_quest_log(ctx,)``. The ``player_active_mission`` positional
    is dropped because the new ``_run_quest_log`` signature is just
    ``(ctx)`` (the ``active`` arg was renamed to ``ctx.player_active_mission``
    inside the body). The AST transformer doesn't drop args at
    non-TARGET call sites whose ids are PARAM_MAPPING *values* (rather
    than keys) -- THIS is the gap that surfaces here.

16. ``_run_ship_menu(ctx, ship, player_owned_ship)`` ->
    ``_run_ship_menu(ctx, ship)``. Same gap: ``player_owned_ship``
    is a PARAM_MAPPING value (from ``owned_ship`` or ``owned`` key),
    not a key, so the call-site ``visit_Call`` doesn't drop it.

17. ``_run_ship_view(ctx, ship, ctx.player_owned_ship, ctx.log)`` ->
    ``_run_ship_view(ctx, ship)``. Same gap PLUS a second-order
    issue: ``ctx.player_owned_ship`` and ``ctx.log`` are
    ``ast.Attribute`` nodes (not ``ast.Name``), and the call-site
    drop check is key-only, so neither gets dropped.

**Known NOT-handled**:

- P3.6.2 (replace remaining ``_run_game`` locals with ``ctx.X``
  references) -- deferred to a follow-up commit so this one stays
  scoped.

- ``update_X`` callback migration -- deferred; their signatures
  stay loose-parameter and the call sites still close over
  ``ctx.X`` from the outer modal scope.

**External render_X calls NOT touched**:
``message_log.render_message_log``, ``world.render_world_view``,
``world.render_world``, ``hud.render_hud`` -- their signatures
live in external modules that are NOT in TARGET_FUNCTIONS, so
they were not migrated. Calls that pass ``ctx.log`` /
``ctx.game_map`` bind correctly to those unchanged external
sig slots (just changing the source of the value).
"""
from __future__ import annotations

from pathlib import Path


DRY_RUN_PATH = Path("/tmp/migrated_main.py")
TARGET_PATH = Path("src/spacehack/__main__.py")


def apply_hand_fixes(text: str) -> str:
    """Apply the 14 BLOCKER hand-fixes to the dry-run output."""
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

    # Fix 3d: revert the ui.Modal call inside _run_confirm ONLY.
    # Tightened to a multi-line anchor that includes _run_confirm's
    # unique ``action = ui.update_confirm(event)`` (no other modal
    # uses that helper), the closing ``return Outcome.IGNORE`` line,
    # and the adjacent ``return ui.Modal(...)`` call (no blank line
    # between them, vs _run_pick which has a blank line + ``outcome =
    # ui.Modal(...)``).
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
    # body (which IS in TARGET_FUNCTIONS), so visit_Name rewrites the
    # ``_animate_jump(context, ...)`` call to ``_animate_jump(ctx, ...)``.
    # But ``_animate_jump``'s signature is unchanged (NOT in TARGETS)
    # and still takes raw ``context: tcod.context.Context`` -- so we
    # need to prefix with ``ctx.context.`` on every call site:
    text = text.replace("_animate_jump(ctx, ", "_animate_jump(ctx.context, ")

    # Fix 5: ``_run_pick`` + ``_run_confirm`` were reverted to take raw
    # ``context`` in their signatures (Fixes 3a + 3b), but the AST
    # transformer's cross-modal call-site rewrite also renamed every
    # CALLER's ``_run_pick(context, ...)`` to ``_run_pick(ctx, ...)``
    # regardless of which function is the caller's body -- because
    # ``visit_Call`` fires for any ``_XXX`` whose name is in
    # ``TARGET_FUNCTIONS``, even from ``run()`` (NOT in TARGETS).
    text = text.replace("_run_pick(ctx, ", "_run_pick(context, ")
    text = text.replace("_run_confirm(ctx, ", "_run_confirm(context, ")

    # Fixes 6-14: render_X call-site ctx insertion.
    # The AST transformer rewrote 9 __main__-internal render_X
    # function signatures to insert ``ctx: GameContext`` as 2nd
    # positional, but at every call site (inside ``_render``
    # closures) it ONLY dropped loose-param args (renaming
    # ``stats`` -> ``ctx.stats``, etc.) -- it did NOT insert the
    # new ``ctx`` positional. Result: arguments slide rightward
    # by one slot, so ``ctx.stats`` lands as a stray positional
    # arg and crashes with "missing positional" /
    # "got multiple values" / "HudStats has no attribute 'name'"
    # (the HudStats.name crash surfaced at the ship-buy modal).

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

    # Fix 8: render_ship_buy -- INSERT ctx + REMOVE ctx.stats
    # (the new sig drops `stats`; body reads ctx.stats internally).
    text = text.replace(
        "render_ship_buy(console, ship, ctx.stats, screen_width=SCREEN_WIDTH, screen_height=SCREEN_HEIGHT)",
        "render_ship_buy(console, ctx, ship, screen_width=SCREEN_WIDTH, screen_height=SCREEN_HEIGHT)",
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

    # Fix 11: render_quest_log -- INSERT ctx + REMOVE ctx.player_active_mission
    # (new sig drops that positional; body reads ctx.player_active_mission).
    text = text.replace(
        "render_quest_log(console, ctx.player_active_mission, confirm_abandon=confirm_abandon, screen_width=SCREEN_WIDTH, screen_height=SCREEN_HEIGHT)",
        "render_quest_log(console, ctx, confirm_abandon=confirm_abandon, screen_width=SCREEN_WIDTH, screen_height=SCREEN_HEIGHT)",
    )

    # Fix 12: render_ship_menu -- INSERT ctx + REMOVE ctx.player_owned_ship
    # (new sig drops that positional; body reads ctx.player_owned_ship).
    text = text.replace(
        "render_ship_menu(console, ship, ctx.player_owned_ship, selected=selected, screen_width=SCREEN_WIDTH, screen_height=SCREEN_HEIGHT)",
        "render_ship_menu(console, ctx, ship, selected=selected, screen_width=SCREEN_WIDTH, screen_height=SCREEN_HEIGHT)",
    )

    # Fix 13: render_ship_view -- INSERT ctx + REMOVE ctx.player_owned_ship.
    text = text.replace(
        "render_ship_view(console, ship, ctx.player_owned_ship, screen_width=SCREEN_WIDTH, screen_height=SCREEN_HEIGHT)",
        "render_ship_view(console, ctx, ship, screen_width=SCREEN_WIDTH, screen_height=SCREEN_HEIGHT)",
    )

    # Fix 14: render_planet_menu -- INSERT ctx after console.
    text = text.replace(
        "render_planet_menu(console, planet_obj, has_port=has_port)",
        "render_planet_menu(console, ctx, planet_obj, has_port=has_port)",
    )

    # Fixes 15-17: _run_X call sites passing orphan positional args
    # the migration didn't drop. Root cause in the AST transformer:
    # ``visit_Call`` only drops args whose id is in
    # :data:`PARAM_MAPPING` *keys* (``log``, ``stats``, ``owned_ship``,
    # ``owned``, ``active``, ``character_info``, ``game_map``). It
    # does NOT drop args whose id is a *value* of PARAM_MAPPING
    # (``player_owned_ship``, ``player_active_mission``) -- the
    # transformation only renames these in TARGET bodies, not at
    # cross-modal call sites in CALL_SITE_CONTAINER bodies like
    # :func:`_run_game`. And it does NOT drop ``ast.Attribute``
    # nodes like ``ctx.player_owned_ship`` at all (those passed
    # through unchanged thanks to P3.6.1 manual refactors which
    # already pre-converted some loose-arg references in
    # :func:`_run_game` body to ``ctx.X`` access).
    #
    # All 3 anchors verified unique: each matches exactly 1 call
    # site in src/spacehack/__main__.py.

    # Fix 15: _run_quest_log -- DROP orphan player_active_mission.
    text = text.replace(
        "_run_quest_log(ctx, player_active_mission)",
        "_run_quest_log(ctx,)",
    )

    # Fix 16: _run_ship_menu -- DROP orphan player_owned_ship.
    text = text.replace(
        "_run_ship_menu(ctx, ship, player_owned_ship)",
        "_run_ship_menu(ctx, ship)",
    )

    # Fix 17: _run_ship_view -- DROP both orphan ctx.player_owned_ship
    # AND ctx.log. (The dry-run text shows ``ctx.player_owned_ship``
    # because :func:`_run_ship_view` is invoked twice -- once with
    # the freshly-built cross-modal ``ctx`` and once from the
    # in-body call where ``ctx`` is already in scope. Either path
    # lands here as ``ctx.X`` Attribute args that visit_Call didn't
    # drop.)
    text = text.replace(
        "_run_ship_view(ctx, ship, ctx.player_owned_ship, ctx.log)",
        "_run_ship_view(ctx, ship)",
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
