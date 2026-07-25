"""One-shot script for P3.6.1a scaffolding.

Applies 9 atomic text edits to ``spacehack/src/spacehack/__main__.py``:

1. Insert ``from .game_context import GameContext`` after the
   ``from . import ui`` line.
2. Insert ``ctx = GameContext(...)`` immediately after the
   ``character_info = {...}`` block (BEFORE the cue is consumed
   by the first modal call, so every code path downstream sees
   ``ctx`` populated).
3-9. Add 7 ``ctx.X = local_X`` mutation mirrors at every site in
   ``_run_game`` where a ``GameContext`` field is reassigned.
   Without these mirrors, the freshly-reassigned local (e.g.
   ``game_map`` after a jump) is not reflected in ``ctx`` --
   and the modal bodies that will (post-P3.6.1b) read
   ``ctx.game_map`` would silently operate on the stale
   pre-jump map. Mirrors are inserted AFTER each reassignment
   so subsequent reads see the up-to-date value.

Anchors are deliberately wide (3-7 surrounding lines) so a
single match is unambiguous in the file. Each ``sub`` call
verifies ``count == 1`` before applying; any ambiguity or
missing anchor raises ``SystemExit`` with the offending
sub-string quoted so the contributor can locate it.

**Scope**: ONLY adds the import, the ``ctx`` construction, and
the 7 mirrors. ZERO modal signature changes -- ``_run_game``
and every modal still play identically after this script runs.
Only the dataflow bookkeeping (mutations propagated through
``ctx``) is wired up. The actual rewrite of modal signatures
+ call sites to use ``ctx`` is P3.6.1b, applied by the AST
transformer.
"""
from __future__ import annotations

from pathlib import Path


def sub(text: str, old: str, new: str, expected_count: int = 1) -> str:
    """Apply ``old`` -> ``new`` to ``text`` if anchor matches ``expected_count`` times.

    Raises with full anchor + 300-char slice quoted if the
    anchor count doesn't match -- the contributor can then see
    why the anchor didn't apply.

    Returns the new text (str.replace is non-mutating so the
    caller MUST REASSIGN: ``text = sub(text, ...)``). Failure
    to reassign is the silent-no-op bug the 9 call sites below
    were originally hitting -- file ends up unchanged even
    though the script reports success.
    """
    actual_count = text.count(old)
    if actual_count != expected_count:
        quoted = old[:300].replace("\n", "\\n")
        raise SystemExit(
            f"ANCHOR MISMATCH for expected_count={expected_count}: "
            f"got {actual_count}. anchor={quoted!r}"
        )
    return text.replace(old, new, expected_count)


def apply(base_dir: Path) -> None:
    """Read __main__.py, apply 9 edits in order, write back."""
    target = base_dir / "src" / "spacehack" / "__main__.py"
    text = target.read_text()

    # Edit 1: import after `from . import ui`.
    text = sub(
        text,
        "from . import ui\n",
        "from . import ui\nfrom .game_context import GameContext\n",
    )

    # Edit 2: construct ctx right after `character_info = {...}`,
    # BEFORE `map_w = SCREEN_WIDTH - HUD_WIDTH` (the first
    # non-init local).
    text = sub(
        text,
        (
            '    character_info = {\n'
            '        "species_name": species.name,\n'
            '        "class_name": klass.name,\n'
            '    }\n'
            '\n'
            '    map_w = SCREEN_WIDTH - HUD_WIDTH\n'
        ),
        (
            '    character_info = {\n'
            '        "species_name": species.name,\n'
            '        "class_name": klass.name,\n'
            '    }\n'
            '\n'
            '    ctx = GameContext(\n'
            '        context=context,\n'
            '        character_info=character_info,\n'
            '        log=log,\n'
            '        game_map=game_map,\n'
            '        player=player,\n'
            '        stats=stats,\n'
            '        player_owned_ship=player_owned_ship,\n'
            '        player_active_mission=player_active_mission,\n'
            '    )\n'
            '\n'
            '    map_w = SCREEN_WIDTH - HUD_WIDTH\n'
        ),
    )

    # Edit 3: MISSION-ABORT mirror (player_active_mission = new_active).
    text = sub(
        text,
        (
            '                        mission_module.abort_mission(\n'
            '                            abandoned, player_owned_ship, log,\n'
            '                        )\n'
            '                    player_active_mission = new_active\n'
            '                # BACK: silent (player just closed the overlay).\n'
        ),
        (
            '                        mission_module.abort_mission(\n'
            '                            abandoned, player_owned_ship, log,\n'
            '                        )\n'
            '                    player_active_mission = new_active\n'
            '                    ctx.player_active_mission = new_active\n'
            '                # BACK: silent (player just closed the overlay).\n'
        ),
    )

    # Edit 4: JUMP mirror (game_map = new_game_map; player was
    # also reassigned via tuple unpack from helper -- mirror that
    # too so ctx sees BOTH new values).
    text = sub(
        text,
        (
            '                                new_game_map, player = _jump_to_system(\n'
            '                                    jp=jp,\n'
            '                                    player_owned_ship=player_owned_ship,\n'
            '                                    log=log,\n'
            '                                    target_system_id=target_system_id,\n'
            '                                    target_jp_id=target_jp_id,\n'
            '                                )\n'
            '                                game_map = new_game_map\n'
            '                                continue\n'
            '                            # BACK / IGNORE: fall through to the\n'
        ),
        (
            '                                new_game_map, player = _jump_to_system(\n'
            '                                    jp=jp,\n'
            '                                    player_owned_ship=player_owned_ship,\n'
            '                                    log=log,\n'
            '                                    target_system_id=target_system_id,\n'
            '                                    target_jp_id=target_jp_id,\n'
            '                                )\n'
            '                                game_map = new_game_map\n'
            '                                ctx.game_map = game_map\n'
            '                                ctx.player = player\n'
            '                                continue\n'
            '                            # BACK / IGNORE: fall through to the\n'
        ),
    )

    # Edit 5: RETURN-TO-CITY mirror (game_map + player reassigned).
    text = sub(
        text,
        (
            '                                    city_game_map = new_city_map\n'
            '                                    game_map = new_city_map\n'
            '                                    player = city_player\n'
            '                                    current_city_id = pid\n'
        ),
        (
            '                                    city_game_map = new_city_map\n'
            '                                    game_map = new_city_map\n'
            '                                    player = city_player\n'
            '                                    ctx.game_map = game_map\n'
            '                                    ctx.player = player\n'
            '                                    current_city_id = pid\n'
        ),
    )

    # Edit 6: LAUNCH-TO-SPACE mirror (game_map + player reassigned).
    text = sub(
        text,
        (
            '                                game_map = space_game_map\n'
            '                                player = space_player_entity\n'
            '                                current_mode = "space"\n'
        ),
        (
            '                                game_map = space_game_map\n'
            '                                player = space_player_entity\n'
            '                                ctx.game_map = game_map\n'
            '                                ctx.player = player\n'
            '                                current_mode = "space"\n'
        ),
    )

    # Edit 7: SHIP-BUY mirror (player_owned_ship = OwnedShip(...)).
    # The actual block has a comment paragraph between
    # ``fuel=ship.max_fuel,`` and the closing ``)``, AND a
    # multi-line ``log.add(...)`` after -- so anchor on the
    # comment + closing-paren pattern (unique to ship-buy).
    text = sub(
        text,
        (
            '                                fuel=ship.max_fuel,\n'
            '                                # cargo_used is intentionally NOT\n'
            '                                # passed here: OwnedShip.__post_init__\n'
            '                                # derives it from self.weapons so the\n'
            '                                # cargo HUD and the actual ammo count\n'
            '                                # can never drift. Passing cargo_used\n'
            '                                # would raise TypeError now that the\n'
            '                                # field is init=False.\n'
            '                            )\n'
            '                            log.add(\n'
        ),
        (
            '                                fuel=ship.max_fuel,\n'
            '                                # cargo_used is intentionally NOT\n'
            '                                # passed here: OwnedShip.__post_init__\n'
            '                                # derives it from self.weapons so the\n'
            '                                # cargo HUD and the actual ammo count\n'
            '                                # can never drift. Passing cargo_used\n'
            '                                # would raise TypeError now that the\n'
            '                                # field is init=False.\n'
            '                            )\n'
            '                            ctx.player_owned_ship = player_owned_ship\n'
            '                            log.add(\n'
        ),
    )

    # Edit 8: MISSION-NONE mirror (after DELIVER outcome).
    text = sub(
        text,
        (
            '                        # the message log before the HUD re-renders\n'
            '                        # without an active mission on the next\n'
            '                        # loop iteration.\n'
            '                        player_active_mission = None\n'
            '                    if result is TalkOutcome.WORK:\n'
        ),
        (
            '                        # the message log before the HUD re-renders\n'
            '                        # without an active mission on the next\n'
            '                        # loop iteration.\n'
            '                        player_active_mission = None\n'
            '                        ctx.player_active_mission = None\n'
            '                    if result is TalkOutcome.WORK:\n'
        ),
    )

    # Edit 9: MISSION-ACCEPT mirror (ActiveMission constructor).
    text = sub(
        text,
        (
            '                                    if mission_module.try_accept_mission(\n'
            '                                        picked, player_owned_ship, log,\n'
            '                                    ):\n'
            '                                        player_active_mission = (\n'
            '                                            mission_module.ActiveMission(\n'
            '                                                mission_id=picked.id,\n'
            '                                            )\n'
            '                                        )\n'
            '                    # BACK: silent.\n'
        ),
        (
            '                                    if mission_module.try_accept_mission(\n'
            '                                        picked, player_owned_ship, log,\n'
            '                                    ):\n'
            '                                        player_active_mission = (\n'
            '                                            mission_module.ActiveMission(\n'
            '                                                mission_id=picked.id,\n'
            '                                            )\n'
            '                                        )\n'
            '                                        ctx.player_active_mission = player_active_mission\n'
            '                    # BACK: silent.\n'
        ),
    )

    target.write_text(text)
    print(f"P3.6.1a scaffolding applied: 9 edits in {target}")


if __name__ == "__main__":
    apply(Path(__file__).resolve().parent.parent)
