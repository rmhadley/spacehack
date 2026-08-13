"""Tutorial mode: a scripted first run for new players.

Chosen from the title menu (``Tutorial``), it forces a Human Merchant
start on Earth and walks the player through their first bounty, first
ship loadout, first space combat, first loot pickup, first jump (which
triggers the main-quest signal), gearing up for Mars, and their first
ground combat — via dismiss-only modal popups fired exactly when each
beat is reached.

State lives on :class:`GameContext` (``tutorial_mode`` /
``tutorial_steps`` / ``tutorial_complete``) and survives save/continue
like everything else, so Continue resumes a tutorial run mid-script.

Design doc: ``docs/design/in_progress/14_DESIGN_TUTORIAL_MODE.md``
"""

from __future__ import annotations

from typing import Any, Callable

# The only mission offered while the scripted tutorial flow is live
# (Earth's bounty board shows nothing else; other boards stay empty
# until the finale sets ``tutorial_complete`` and lifts the suppression
# in mission.fill_empty_slots).
TUTORIAL_MISSION_IDS = frozenset({"bhguild_sol_scout"})

# Extra credits granted at tutorial start. Merchant starts with 75$;
# the scripted shopping list (2nd light laser 30$ + Shield Mk.1 60$ +
# kinetic rifle 80$ = 170$) needs a comfortable margin on top.
TUTORIAL_CREDIT_BONUS = 250


# ---------------------------------------------------------------------------
# Setup
# ---------------------------------------------------------------------------


def setup_tutorial(ctx) -> None:
    """Apply tutorial-mode starting state to a fresh GameContext.

    Called during new-game setup (Human Merchant) before the game loop
    starts. Grants the credit bonus and pre-seeds Earth's bounty board
    so only Crimson Jack is ever offered there.
    """
    ctx.tutorial_mode = True
    ctx.stats.credits += TUTORIAL_CREDIT_BONUS
    from .mission import ensure_board
    _board = ensure_board(ctx, "bounty_master", max_slots=5, planet_id="earth")
    _board.slots = ["bhguild_sol_scout", None, None, None, None]
    _board.last_refresh_month = ctx.time_month
    ctx.log.add("[TUTORIAL] Human Merchant start - follow the popups.")


# ---------------------------------------------------------------------------
# Step copy
# ---------------------------------------------------------------------------

_STEP_TITLES: dict[str, str] = {
    "intro": "WELCOME, RECRUIT",
    "first_move": "FIRST STOP",
    "accepted_crimson": "CONTRACT ACCEPTED",
    "equipped_loadout": "READY TO FLY",
    "launched": "ORBIT REACHED",
    "space_combat_intro": "SPACE COMBAT 101",
    "loot_dropped": "LOOT",
    "picked_up_loot": "JUMPING BETWEEN STARS",
    "signal_triggered": "SIGNAL RECEIVED",
    "earth_armory": "GROUND GEAR",
    "armed_ground": "HEAD TO MARS",
    "mars_ground_combat_intro": "GROUND COMBAT 101",
    "level_up": "LEVEL UP",
    "finale": "YOU'RE READY",
}

_STEP_BODIES: dict[str, str] = {
    "intro": (
        "Welcome to spacehack! This guided run teaches the core loop: "
        "missions, ship loadout, space combat, loot, jumping, and ground "
        "combat.\n\n"
        "Move with ARROW KEYS, vim keys (h/j/k/l), or the numpad - "
        "diagonals use y/u/b/n. '?' opens the game guide at any time, "
        "and ESC quits to the title (the game autosaves).\n\n"
        "Your first job: the Bounty Master (D) in the guild hall "
        "southeast of the plaza."
    ),
    "first_move": (
        "The city is your home base: space port (NW), merchant guild "
        "(SW), bar (plaza), militia + bounty guild (SE).\n\n"
        "Walk into the bounty guild hall and bump the Bounty Master (D) "
        "to talk. Choose 'Find work' to see contracts - there's one "
        "waiting for you."
    ),
    "accepted_crimson": (
        "Wanted: Crimson Jack - a pirate scout in Sol, near Mercury. "
        "'Q' opens your quest log whenever you want to review active "
        "work.\n\n"
        "Before you launch, visit the Mechanic terminal (the '%' icon "
        "just outside the space port door). Buy a second Light Laser "
        "and a Shield Mk. 1 from the Loadout screen - you have enough "
        "credits. A shield and a spare laser make your first fight much "
        "safer."
    ),
    "equipped_loadout": (
        "Nice loadout - two lasers and a shield generator. Your ship is "
        "docked at the space port.\n\n"
        "Walk up to it and bump it, then choose Launch to lift off."
    ),
    "launched": (
        "You're in space around Sol. The bounty target message is in "
        "the log - Crimson Jack is lurking near Mercury.\n\n"
        "Press 'G' for auto-navigation and select Mercury from the "
        "list. Your ship will fly itself there - the pirate is holed "
        "up nearby."
    ),
    "space_combat_intro": (
        "Combat is turn-based. Each turn you have AP (action points) "
        "that decide how much you can do before the enemy moves. "
        "Moving always costs 1 AP.\n\n"
        "FIRE: select a weapon and a target. Firing costs the MAX AP "
        "of the weapons you enable - four light lasers still cost just "
        "1 AP, not 4. But every weapon that fires pays its full power "
        "cost, so firing everything every turn burns through your "
        "energy fast.\n\n"
        "MOVEMENT: moving is good beyond positioning - each cell you "
        "travel raises your dodge chance.\n\n"
        "SHIELDS: press 'S' to cycle how much power your shields drain "
        "for regen each turn.\n\n"
        "AP, energy, shields, and movement are all finite - it's a "
        "balancing act. Spend them wisely and defeat Crimson Jack."
    ),
    "loot_dropped": (
        "Crimson Jack was destroyed - and dropped loot (%).\n\n"
        "Fly onto (or next to) the loot and press 'P' to pick it up. "
        "'P' works in space and on the ground, and it reaches loot on "
        "diagonal squares too."
    ),
    "picked_up_loot": (
        "Loot secured. Now try a jump: press 'G' for auto-navigation "
        "and fly to the 61 Cygni Gate. Bump it and choose to jump to "
        "the connected system.\n\n"
        "Each jump costs 10 fuel - keep an eye on the fuel gauge in the "
        "HUD. Jumping out of Sol triggers the main quest: a strange "
        "signal with coordinates to Mars. After the transmission, jump "
        "back and land on Earth."
    ),
    "signal_triggered": (
        "The garbled transmission resolves to coordinates on MARS - "
        "that's your main quest.\n\n"
        "Head back to Sol and land on Earth. Before the red planet, "
        "gear up for ground combat at the Armory terminal (the 'A' "
        "icon, left of the mechanic terminal outside the space port)."
    ),
    "earth_armory": (
        "Mars has hostile wildlife and raiders - bring a weapon. Visit "
        "the Armory terminal (the 'A' icon, left of the mechanic "
        "terminal outside the space port) and buy a Shotgun.\n\n"
        "It's two-handed, so it fills both weapon slots. Equip it from "
        "your ground loadout."
    ),
    "armed_ground": (
        "Armed and ready. Launch your ship and press 'G' to "
        "auto-navigate to Mars.\n\n"
        "Approach Mars and choose Explore to investigate the signal "
        "source."
    ),
    "mars_ground_combat_intro": (
        "Ground combat is turn-based like space combat. You have AP to "
        "spend on moving, aiming, and firing.\n\n"
        "Range and line of sight matter: weapons have min/max ranges "
        "and you can only hit what you can see. Your weapon slots are "
        "shown in the HUD - swap between them with the indicated "
        "keys.\n\n"
        "Win this fight and the tutorial's core is done - the galaxy "
        "is yours."
    ),
    "level_up": (
        "Victory! That fight pushed you to the next level - you "
        "earned skill points.\n\n"
        "Press 'C' to open your character screen and spend them. "
        "Points boost your ship skills (Gunnery, Piloting, "
        "Engineering) or your ground stats (Reflexes, Strength, "
        "Stamina) - +1 per point, capped at 100.\n\n"
        "Spend your points, and the tutorial wraps up."
    ),
    "finale": (
        "That's the tutorial! You know the core loop: take missions, "
        "equip, fight, loot, jump, explore.\n\n"
        "A few parting tips: trade goods between planets for profit "
        "('I' opens cargo), visit the other guilds for different work, "
        "and '?' is always there for details. Death is permanent in "
        "this game - fly smart.\n\n"
        "Good hunting, pilot."
    ),
}


# ---------------------------------------------------------------------------
# Step plumbing
# ---------------------------------------------------------------------------


def _active(ctx) -> bool:
    """True while the scripted flow is live (tutorial, not finished)."""
    return bool(
        getattr(ctx, "tutorial_mode", False)
        and not getattr(ctx, "tutorial_complete", False)
    )


def _show_step(ctx, step_id: str) -> None:
    """Show step's popup (dismiss-only, gate-popup style) and mark done."""
    from .main_quest import show_gate_popup
    show_gate_popup(
        ctx,
        "TUTORIAL",
        _STEP_BODIES[step_id],
        title=_STEP_TITLES[step_id],
    )
    ctx.tutorial_steps.add(step_id)


def mark_step(ctx, step_id: str) -> None:
    """Mark a step complete without showing its popup (tests)."""
    if step_id in _STEP_TITLES:
        ctx.tutorial_steps.add(step_id)


# ---------------------------------------------------------------------------
# Conditions
# ---------------------------------------------------------------------------


def _has_crimson(ctx) -> bool:
    """True when the player holds the tutorial's Crimson Jack contract."""
    return any(
        getattr(_m, "mission_id", "") == "bhguild_sol_scout"
        for _m in ctx.player_active_missions
    )


def _has_loadout(owned_ship) -> bool:
    """True when the ship carries 2+ energy weapons and a shield module.

    Pure predicate — the tutorial's \"buy a 2nd laser + shield\" beat.
    Energy slot covers light/medium/heavy lasers (and any other energy
    weapon); shield modules are those granting a max-shield bonus.
    """
    if owned_ship is None:
        return False
    from .data.weapons import find_weapon
    _energy_weapons = 0
    for _wid in owned_ship.weapons or ():
        try:
            if find_weapon(_wid).slot_type == "energy":
                _energy_weapons += 1
        except KeyError:
            continue
    if _energy_weapons < 2:
        return False
    from .data.modules import find_module
    for _mid in owned_ship.modules or ():
        try:
            if find_module(_mid).max_shield_bonus > 0:
                return True
        except KeyError:
            continue
    return False


def _any_loot(ctx) -> bool:
    """True when the current map holds at least one loot entity."""
    if getattr(ctx, "game_map", None) is None:
        return False
    return any(
        getattr(_e, "loot_data", None) is not None
        for _e in ctx.game_map.entities
    )


# Ordered tick-evaluated steps. ``tick`` fires the FIRST unfinished step
# whose condition holds, so the script follows the player's actual
# progress (accept mission → equip → launch → loot → signal → armory).
_TICK_STEPS: tuple[tuple[str, Callable[[Any, str], bool]], ...] = (
    ("intro", lambda ctx, mode: True),
    ("accepted_crimson", lambda ctx, mode: _has_crimson(ctx)),
    (
        "equipped_loadout",
        lambda ctx, mode: (
            "accepted_crimson" in ctx.tutorial_steps
            and _has_loadout(ctx.player_owned_ship)
        ),
    ),
    (
        "launched",
        lambda ctx, mode: (
            "equipped_loadout" in ctx.tutorial_steps
            and mode == "space"
        ),
    ),
    (
        "loot_dropped",
        lambda ctx, mode: (
            mode == "space"
            and "space_combat_intro" in ctx.tutorial_steps
            and _any_loot(ctx)
        ),
    ),
    (
        "picked_up_loot",
        lambda ctx, mode: (
            mode == "space"
            and "space_combat_intro" in ctx.tutorial_steps
            and not _any_loot(ctx)
        ),
    ),
    (
        "signal_triggered",
        lambda ctx, mode: (
            "picked_up_loot" in ctx.tutorial_steps
            and ctx.main_quest_progress.get("prologue_signal") == "completed"
        ),
    ),
    (
        "earth_armory",
        lambda ctx, mode: (
            "signal_triggered" in ctx.tutorial_steps
            and mode == "city"
            and ctx.current_city_id == "earth"
        ),
    ),
    (
        "armed_ground",
        lambda ctx, mode: (
            "earth_armory" in ctx.tutorial_steps
            and bool(ctx.equipped_ground_weapons)
        ),
    ),
    (
        "finale",
        lambda ctx, mode: (
            "level_up" in ctx.tutorial_steps
            and getattr(ctx, "player_skill_points", 0) <= 0
        ),
    ),
)


def tick(ctx, mode: str = "city") -> None:
    """Evaluate tutorial step conditions once per game-loop frame.

    Fires at most one popup per call and returns immediately when not
    in a tutorial run or after completion. ``mode`` mirrors
    ``_run_game``'s ``current_mode`` so steps react to city/space
    transitions.
    """
    if not getattr(ctx, "tutorial_mode", False):
        return
    if ctx.tutorial_complete:
        return
    for _step_id, _condition in _TICK_STEPS:
        if _step_id in ctx.tutorial_steps:
            continue
        if _condition(ctx, mode):
            _show_step(ctx, _step_id)
            if _step_id == "finale":
                ctx.tutorial_complete = True
                # Boards visited during the tutorial are marked refreshed
                # this month; unlock them so every board repopulates on
                # its next visit (the suppression lift in
                # mission.fill_empty_slots then applies).
                for _board in getattr(ctx, "mission_boards", {}).values():
                    _board.last_refresh_month = 0
            return


# ---------------------------------------------------------------------------
# Event hooks (fired from gameplay sites — see __main__.py / combat)
# ---------------------------------------------------------------------------


def notify_move(ctx) -> None:
    """First city move — point the player at the bounty guild."""
    if _active(ctx) and "first_move" not in ctx.tutorial_steps:
        _show_step(ctx, "first_move")


def notify_pickup(ctx) -> None:
    """Space loot was cleared by pickup — teach jumping next.

    Fires only once the space map holds no loot (the player actually
    took it), matching the script's "after picking up loot" beat.
    """
    if (
        _active(ctx)
        and "picked_up_loot" not in ctx.tutorial_steps
        and "space_combat_intro" in ctx.tutorial_steps
        and not _any_loot(ctx)
    ):
        _show_step(ctx, "picked_up_loot")


def maybe_space_combat_intro(ctx) -> None:
    """First space combat — fired before the combat UI takes over."""
    if _active(ctx) and "space_combat_intro" not in ctx.tutorial_steps:
        _show_step(ctx, "space_combat_intro")


def maybe_ground_combat_intro(ctx) -> None:
    """First ground combat — fired before the combat UI takes over."""
    if _active(ctx) and "mars_ground_combat_intro" not in ctx.tutorial_steps:
        _show_step(ctx, "mars_ground_combat_intro")


def notify_ground_combat_ended(ctx) -> None:
    """First ground combat resolved — guarantee a level-up, then teach
    the character screen (C + skill points).

    The finale is a tick step gated on the player having spent their
    points, so the script ends only after the leveling lesson lands.
    """
    if (
        _active(ctx)
        and "level_up" not in ctx.tutorial_steps
        and "mars_ground_combat_intro" in ctx.tutorial_steps
    ):
        _ensure_level_up(ctx)
        _show_step(ctx, "level_up")


def _ensure_level_up(ctx) -> None:
    """Guarantee the player reaches level 2 after the first ground combat.

    Level 2 needs 90 XP; a single Mars cave fight may not reach it, so
    the tutorial tops the player up so the skill-point lesson is real.
    """
    if getattr(ctx, "player_level", 1) >= 2:
        return
    from .xp import add_xp, xp_for_level
    _needed = xp_for_level(2) - getattr(ctx, "player_xp", 0)
    if _needed > 0:
        add_xp(ctx, _needed)
