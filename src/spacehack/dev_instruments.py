"""Playtest instruments (doc 103 Build B): the F8 picker.

The burn-band dial (ctx.ego_burn set directly, the ratchet's playtest
override) and the enemy-baton arming hook (every enemy built at the
ENGAGED sites wields a Stun Baton while the flag lives). Split from
dev_mode when that module crossed the architecture line — one dev
surface per module, the dev_mode acquisition/override split
precedent.
"""

from __future__ import annotations

from . import pygame_ui, ui
from .dev_mode import Outcome, _menu_frames, _option_ids, _run_pygame_menu_pick
from .game_context import GameContext


# ---------------------------------------------------------------------------
# Playtest instruments (doc 103 Build B) — the F8 picker: the burn dial
# + the enemy-baton arming toggle. Unlike F7's chrome grants (burn-
# neutral by design), the dial moves ctx.ego_burn DIRECTLY — it exists
# to exercise the susceptibility seam's bands in live fights.
# ---------------------------------------------------------------------------

# One representative burn per band (chrome._BAND_MAX_BURN = 3/7/11):
# the dead zone, then the shallow end of each band past it.
_BURN_DIAL: tuple[tuple[str, int], ...] = (
    ("natural", 0), ("tainted", 5), ("chromed", 9), ("psycho", 13),
)


def set_dev_burn(ctx: GameContext, dial_id: str) -> str:
    """Set Burnt Ego to a band's representative value; returns the log
    line. The ratchet's playtest override — the game's own ratchet
    (ratchet_install) never moves backwards, but the dial sets
    whatever the seam test needs."""
    from .chrome import band, band_name
    _burn = dict(_BURN_DIAL)[dial_id]
    ctx.ego_burn = _burn
    return f"[DEV MODE] Burnt Ego set to {_burn} ({band_name(band(_burn))})."


def arm_enemy_batons(instances) -> str:
    """Rewrite every instance's loadout to a lone Stun Baton (melee
    set armed, ranged emptied, active melee): the doc 103 Build B
    playtest hook that makes 'an enemy staggers me' reliably
    encounterable. The stamp is the entity's persisted truth — the
    rewrite survives re-engagement while the flag lives (the F8
    toggle owns its lifetime); the instance's wielded pair re-syncs
    here so the very first turn already swings it. (Scope: the two
    ENGAGED build sites — fight init and joins; stare-eruption zone
    victims never join the fight and keep their authored stamps.)"""
    from . import ground_loadout

    for gei in instances:
        _stamp = ground_loadout.ensure_loadout(gei.entity, None, gei.spec)
        _stamp[ground_loadout.SET_MELEE] = ["stun_baton", 0]
        _stamp[ground_loadout.SET_RANGED] = None
        _stamp["active"] = ground_loadout.SET_MELEE
        gei.weapon_id = "stun_baton"
        gei.weapon_quality = 0
    return f"[DEV MODE] Enemy batons armed ({len(instances)} wielders)."


def playtest_instruments_menu(ctx: GameContext) -> ui.MenuScreen:
    """The F8 picker: the burn dial + the arming toggle, live state in
    the labels (the chrome picker's shape)."""
    from .chrome import band, band_name
    options = tuple(
        (f"burn_{dial_id}", f"Burnt Ego -> {burn} ({band_name(band(burn))})")
        for dial_id, burn in _BURN_DIAL
    ) + (
        ("arm_batons", f"Enemy batons: "
         f"{'ARMED' if getattr(ctx, 'dev_enemy_batons', False) else 'off'}"),
    )
    return ui.MenuScreen(
        title="Playtest (dev)",
        instruction=pygame_ui.modal_hint(
            pygame_ui.NAV_HINT, "ENTER apply", "ESC close",
        ),
        options=options,
        descriptions={option_id: "" for option_id, _label in options},
    )


async def choose_playtest_instruments(context, ctx: GameContext) -> str | None:
    """Run the F8 picker until ESC (each pick applies and the menu
    rebuilds with live state); returns "QUIT" when the window closes."""
    while True:
        menu = playtest_instruments_menu(ctx)
        result = await _run_pygame_menu_pick(
            context, _menu_frames(
                menu,
                "Burn-band dial + enemy-baton arming for the staggered "
                "debut's playtest (doc 103 Build B).",
            ),
            caption="spacehack - playtest (dev)",
            valid_ids=_option_ids(menu),
        )
        if result is None:
            return None
        outcome, option_id = result
        if outcome is Outcome.QUIT:
            return "QUIT"
        if outcome is not Outcome.CONFIRM or option_id is None:
            return None
        if option_id == "arm_batons":
            ctx.dev_enemy_batons = not getattr(ctx, "dev_enemy_batons", False)
            ctx.log.add(
                "[DEV MODE] Enemy batons armed." if ctx.dev_enemy_batons
                else "[DEV MODE] Enemy batons disarmed."
            )
        else:
            ctx.log.add(set_dev_burn(ctx, option_id.removeprefix("burn_")))


