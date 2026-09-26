"""The stance vocabulary (doc 50 SETTLED 3/6) — the player policies.

A stance is a frozen measurement INSTRUMENT, not a player model: one
async (ctx, rules) -> action-string per await, driven through the
loop's real dispatch by the harness runner. Never mutates combat
state except via the returned keyboard action; a policy change to a
landed stance is a benchmark revision that re-measures and re-rules
its rows in the same commit (SETTLED 6).

The ground ladder (SETTLED 6): ``hold_range`` = rung 0, the
open-floor baseline; ``posted_hold`` = rung 1, the geometry ceiling.
"""

from __future__ import annotations

from src.spacehack import world
from src.spacehack.combat import _ground_charger, _loop
from src.spacehack.combat._animations import _has_los
from src.spacehack.combat._stats import _distance
from src.spacehack.data.ground_weapons import find_ground_weapon
from src.spacehack.ground_equipment import reserve_ammo_count
from src.spacehack.ground_weapon_sets import weapon_set


async def stand_and_trade(ctx, rules) -> str:
    """The tutorial-honest policy: fire everything affordable at the
    current target, never move, end the turn when nothing can fire.

    Reads affordability through the real rules — AP, power, LOS — so
    the stance flies exactly what the keyboard's FIRE key would.
    """
    if any(rules.can_fire(slot, ctx)[0] for slot in _fire_slots(ctx, rules)):
        return "FIRE"
    return "WAIT"


# (dx, dy) -> a MOVE key name the dispatch accepts, vim letters first
# so the choice is deterministic.
_MOVE_KEY_BY_DELTA: dict[tuple[int, int], str] = {}
for _name, _delta in (
    *world.VIM_DELTAS.items(),
    *world.ARROW_DELTAS.items(),
    *world.NUMPAD_DELTAS.items(),
):
    _MOVE_KEY_BY_DELTA.setdefault(_delta, _name)


def _fire_slots(ctx, rules) -> list[int]:
    """Active slot indexes through the real rules' own helpers."""
    return _loop._fire_slot_indexes(
        rules.player_weapons(ctx), rules.active_weapons(ctx),
    )


def _dry_reloadable_slot(ctx, rules, slots) -> int | None:
    """The first active slot whose magazine cannot feed a shot, with a
    matching reserve remaining and an affordable reload — a RELOAD the
    dispatch cannot perform would loop forever, so the AP gate lives
    in the stance too. NOTE: the dispatch's reload picks the first
    slot with ROOM (a partial magazine tops off), not the first dry
    one — identical weapons converge (every shipped row); a future
    mixed-reload-cost row could livelock here until ACTION_CAP raises,
    loudly."""
    instances = ctx.equipped_ground_weapons
    for slot in slots:
        if slot >= len(instances):
            continue
        instance = instances[slot]
        if instance.loaded_ammo is None:
            continue  # infinite-ammo weapon is never dry
        spec = find_ground_weapon(instance.weapon_id)
        if instance.loaded_ammo >= spec.ammo_per_shot:
            continue
        if reserve_ammo_count(ctx.bandolier, spec.ammo_type) <= 0:
            continue
        if rules.player_ap(ctx) < spec.reload_ap_cost:
            continue
        return slot
    return None


def _validated_step(ctx, game_map, dx: int, dy: int) -> tuple[int, int] | None:
    """One candidate step, checked through the real movement collision."""
    from src.spacehack.combat._actions import move_entity

    _new_pos, ok = move_entity(
        ctx.player.pos, dx, dy, game_map, exclude=ctx.player,
    )
    return (dx, dy) if ok else None


def _approach_step(ctx, game_map, target) -> tuple[int, int] | None:
    """A step toward the reference target via the real A* pathfinder
    (goal = the cells beside the target — it is occupied)."""
    from src.spacehack.world_path import find_path

    goals = {
        (target.pos.x + dx, target.pos.y + dy)
        for dx in (-1, 0, 1) for dy in (-1, 0, 1)
        if (dx, dy) != (0, 0)
    }
    path = find_path(
        (ctx.player.pos.x, ctx.player.pos.y), goals, game_map,
        exclude_entity=ctx.player,
    )
    if not path:
        return None
    # find_path's path EXCLUDES the start cell — path[0] is the step.
    step = (path[0][0] - ctx.player.pos.x, path[0][1] - ctx.player.pos.y)
    return _validated_step(ctx, game_map, *step)


def _retreat_step(ctx, game_map, target) -> tuple[int, int] | None:
    """A step away from the reference target (max distance gain,
    deterministic by delta order) — the back-off inside min range."""
    here = (ctx.player.pos.x, ctx.player.pos.y)
    target_dist = _distance(ctx.player.pos, target.pos)
    best, best_gain = None, 0.0
    for dx, dy in _MOVE_KEY_BY_DELTA:
        step = _validated_step(ctx, game_map, dx, dy)
        if step is None:
            continue
        moved = world.Position(here[0] + dx, here[1] + dy)
        gain = _distance(moved, target.pos) - target_dist
        if gain > best_gain:
            best, best_gain = step, gain
    return best


def _band_step(ctx, rules, target, slots) -> tuple[int, int] | None:
    """The SETTLED-4 band rule against the reference target: approach
    when beyond the reference weapon's max range or without LOS; back
    off inside its min range (the doc 48 SETTLED-26 mirror). Band
    numbers come from the same ``weapon_range`` ``can_fire`` enforces.
    """
    reference = rules.player_weapons(ctx)[slots[0]]
    min_range, max_range = _ground_charger.weapon_range(
        reference, ctx, rules.player_ap(ctx),
    )
    dist = int(_distance(ctx.player.pos, target.pos))
    game_map = ctx.game_map
    los = _has_los(
        game_map,
        ctx.player.pos.x, ctx.player.pos.y,
        target.pos.x, target.pos.y,
    )
    if dist > max_range or not los:
        return _approach_step(ctx, game_map, target)
    if dist < min_range:
        return _retreat_step(ctx, game_map, target)
    return None  # inside the band — hold


async def hold_range(ctx, rules) -> str:
    """The ground policy (SETTLED 4+5): aim at the closest alive enemy,
    FIRE while any active slot passes the real ``can_fire``, RELOAD a
    dry slot with reserve, MOVE one step per the band rule, else WAIT.
    Every action is a keyboard string through the real dispatch — the
    stance never calls rules internals to mutate state."""
    enemies = rules.get_enemies(ctx)
    if not enemies:
        return "WAIT"
    distances = [_distance(ctx.player.pos, e.pos) for e in enemies]
    closest = distances.index(min(distances))
    if closest != rules._state.target_idx:
        return "TARGET"
    slots = _fire_slots(ctx, rules)
    if any(rules.can_fire(slot, ctx)[0] for slot in slots):
        return "FIRE"
    if _dry_reloadable_slot(ctx, rules, slots) is not None:
        return "RELOAD"
    if rules.player_ap(ctx) > 0:
        step = _band_step(ctx, rules, enemies[closest], slots)
        if step is not None:
            return f"MOVE:{_MOVE_KEY_BY_DELTA[step]}"
    return "WAIT"


async def posted_hold(ctx, rules) -> str:
    """Rung 1 of the ground ladder (doc 50 SETTLED 6): a pilot posted
    in a 1-wide lane. Aim at the closest alive enemy, FIRE while any
    active slot passes the real ``can_fire``, and NEVER move — the
    geometry does the work (one approach lane, entity collision queues
    the pack, arrivERs spent their AP closing). Measures the geometry
    ceiling against hold_range's open-floor baseline."""
    enemies = rules.get_enemies(ctx)
    if not enemies:
        return "WAIT"
    distances = [_distance(ctx.player.pos, e.pos) for e in enemies]
    closest = distances.index(min(distances))
    if closest != rules._state.target_idx:
        return "TARGET"
    slots = _fire_slots(ctx, rules)
    if any(rules.can_fire(slot, ctx)[0] for slot in slots):
        return "FIRE"
    if _dry_reloadable_slot(ctx, rules, slots) is not None:
        return "RELOAD"
    return "WAIT"


async def toggle_sets(ctx, rules):
    """Rung 1.5 of the ground ladder (doc 50 SETTLED 7): the doc-51
    pilot — two weapon sets, swapped through the REAL SWAP_SETS
    dispatch (1 AP mid-turn, magazines ride the instances). Hold
    range's ladder with the swap rung after FIRE: draw the melee set
    when the active ranged set is inside its min range, draw the
    ranged set when nothing is in melee reach."""
    enemies = rules.get_enemies(ctx)
    if not enemies:
        return "WAIT"
    distances = [_distance(ctx.player.pos, e.pos) for e in enemies]
    closest = distances.index(min(distances))
    if closest != rules._state.target_idx:
        return "TARGET"
    target = enemies[closest]
    dist = int(_distance(ctx.player.pos, target.pos))
    slots = _fire_slots(ctx, rules)
    reference = rules.player_weapons(ctx)[slots[0]]
    min_r, max_r = _ground_charger.weapon_range(
        reference, ctx, rules.player_ap(ctx),
    )
    if any(rules.can_fire(slot, ctx)[0] for slot in slots) and dist >= min_r:
        return "FIRE"
    if rules.player_ap(ctx) >= 1:
        active_class = weapon_set(reference)
        if (active_class == "ranged" and dist < min_r) or (
            active_class == "melee" and dist > min_r
        ):
            return "SWAP_SETS"
    if _dry_reloadable_slot(ctx, rules, slots) is not None:
        return "RELOAD"
    if rules.player_ap(ctx) > 0 and dist > max_r:
        step = _approach_step(ctx, ctx.game_map, target)
        if step is not None:
            return f"MOVE:{_MOVE_KEY_BY_DELTA[step]}"
    return "WAIT"


# Stance vocabulary: name -> async (ctx, rules) -> one action string.
# One action per await — the same call shape as the loop's own
# ``_combat_action`` input seam. New stances join when a scenario
# needs one (SETTLED 3); nothing ships here unused. Stances are the
# measurement INSTRUMENT — frozen once landed; a policy change is a
# benchmark revision that re-measures and re-rules its rows in the
# same commit (SETTLED 6).
STANCES = {
    "stand_and_trade": stand_and_trade,
    "hold_range": hold_range,
    "posted_hold": posted_hold,
    "toggle_sets": toggle_sets,
}
