"""One-shot script for P3.6.2.4 application -- consoles + body loose refs.

The P3.6.2 design for `_handle_combat_encounter` was overly aggressive
in dropping parameters -- it removed ``console`` from the signature,
but the body needs ``console`` to thread through to
:func:`_combat.run_combat` (which paints results back to the screen)
and the VICTORY/DEFEAT logging needs ``ctx.log``. As a result the
post-migration runtime hit ``NameError: name 'player_owned_ship' is
not defined`` at line 527 followed by ``NameError: name 'console' is
not defined`` at line 529 if 527 were fixed.

This script:

1. Restores ``console`` to the signature:
   ``_handle_combat_encounter(ctx, console, encounter) -> str``.

2. Fixes the body's bare ``player_owned_ship`` and ``log.add``
   references that the P3.6.2.1 fixup missed:
     - line 527: ``ship_module.find_ship(player_owned_ship.ship_id)``
       -> ``ship_module.find_ship(ctx.player_owned_ship.ship_id)``
     - VICTORY branch: ``log.add(...)`` -> ``ctx.log.add(...)``

3. Updates the 2 callers to pass ``console`` after ``ctx``:
     - line 1982: ``_handle_combat_encounter(ctx, _goto_combat)``
       -> ``_handle_combat_encounter(ctx, console, _goto_combat)``
     - line 1992: ``_handle_combat_encounter(ctx, _encounter)``
       -> ``_handle_combat_encounter(ctx, console, _encounter)``

Keeps the ``_combat.run_combat`` rewrite already applied by P3.6.2.1
-- that line is structurally correct after ``console`` is restored.

**Idempotency**: anchored on POST-P3.6.2.1 text. Second run finds 0
matches and reports no changes.
"""
from __future__ import annotations

import sys
from pathlib import Path


TARGET_PATH = Path("src/spacehack/__main__.py")


def apply_p3_6_2_4_fixup(text: str) -> str:
    # 1. Restore console in the signature.
    text = text.replace(
        "def _handle_combat_encounter(ctx, encounter: tuple[list, list[world.Position]]) -> str:",
        "def _handle_combat_encounter(ctx, console: tcod.console.Console, encounter: tuple[list, list[world.Position]]) -> str:",
    )

    # 2. Fix bare player_owned_ship reference in body (line 527).
    text = text.replace(
        "    _ship_cat = ship_module.find_ship(player_owned_ship.ship_id)",
        "    _ship_cat = ship_module.find_ship(ctx.player_owned_ship.ship_id)",
    )

    # 3. Fix bare log.add references in VICTORY/DEFEAT branches.
    text = text.replace(
        "    _names = ', '.join((_sp.name for _sp in _nearby_specs))\n    log.add(f'You defeated {_names}!')",
        "    _names = ', '.join((_sp.name for _sp in _nearby_specs))\n    ctx.log.add(f'You defeated {_names}!')",
    )
    text = text.replace(
        "    elif _result == 'DEFEAT':\n        log.add('Your ship is destroyed!')",
        "    elif _result == 'DEFEAT':\n        ctx.log.add('Your ship is destroyed!')",
    )

    # 4. Update the 2 callers to pass console (per-call screen).
    text = text.replace(
        "_handle_combat_encounter(ctx, _goto_combat)",
        "_handle_combat_encounter(ctx, console, _goto_combat)",
    )
    text = text.replace(
        "_handle_combat_encounter(ctx, _encounter)",
        "_handle_combat_encounter(ctx, console, _encounter)",
    )

    return text


def main() -> None:
    if not TARGET_PATH.exists():
        raise SystemExit(f"Source missing: {TARGET_PATH}")

    src = TARGET_PATH.read_text()
    out = apply_p3_6_2_4_fixup(src)

    if out == src:
        print("P3.6.2.4 produced no changes -- already applied or anchors mismatched.")
        sys.exit(0)

    TARGET_PATH.write_text(out)
    print(f"P3.6.2.4 applied: {len(src)} -> {len(out)} chars ({len(out) - len(src):+d})")


if __name__ == "__main__":
    main()
