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


def _aim_closest(ctx, rules) -> tuple | None:
    """The shared aim preamble: (target, dist) with the closest alive
    enemy selected via TARGET dispatch, ("TARGET", None) while still
    cycling, or None with no enemies."""
    enemies = rules.get_enemies(ctx)
    if not enemies:
        return None
    distances = [_distance(ctx.player.pos, e.pos) for e in enemies]
    closest = distances.index(min(distances))
    if closest != rules._state.target_idx:
        return ("TARGET", None)
    return enemies[closest], int(distances[closest])


async def toggle_sets(ctx, rules):
    """Rung 1.5 of the ground ladder (doc 50 SETTLED 7): the doc-51
    pilot — two weapon sets, swapped through the REAL SWAP_SETS
    dispatch (1 AP mid-turn, magazines ride the instances). NOT
    hold_range-plus-a-rung: the MOVE rung only approaches beyond the
    active max (no LOS-regain, no retreat-inside-min) — the swap is
    the set-policy's answer to bad distance. Dead zone (melee reach
    < d < ranged min) swap-churns at 1 AP per flip, bounded by the
    AP guard — priced into the railgun row's bars."""
    aimed = _aim_closest(ctx, rules)
    if aimed is None:
        return "WAIT"
    if aimed[1] is None:
        return aimed[0]
    target, dist = aimed
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


async def kite(ctx, rules) -> str:
    """The movement-first policy (doc 57.3's crossing-under-movement
    rows): retreat from the nearest enemy while more than 1 AP
    remains, then FIRE what's affordable — the outrun doctrine as an
    instrument (kiting extends flight and raises dodge at arrival,
    doc 57 SETTLED 5). The 1-AP line covers the rows' 1-AP weapons; a
    future 2-AP-volley row should widen it to the volley's cost.
    Space rows' instrument; on the ground it is simply
    hold-range-with-retreat-priority."""
    aimed = _aim_closest(ctx, rules)
    if aimed is None:
        return "WAIT"
    if aimed[1] is None:
        return aimed[0]
    target, _dist = aimed
    if rules.player_ap(ctx) > 1:
        step = _retreat_step(ctx, ctx.game_map, target)
        if step is not None:
            return f"MOVE:{_MOVE_KEY_BY_DELTA[step]}"
    slots = _fire_slots(ctx, rules)
    if any(rules.can_fire(slot, ctx)[0] for slot in slots):
        return "FIRE"
    return "WAIT"


def find_ship_weapon_range(weapon_id: str) -> int:
    """One ship weapon's catalog max range (the flak escort's reach
    read; unknown ids read 0)."""
    from src.spacehack.data.weapons import find_weapon

    try:
        return find_weapon(weapon_id).max_range
    except KeyError:
        return 0


async def flak_escort(ctx, rules) -> str:
    """The manual-flak rhythm (doc 57 SETTLED 6/8 as policy): cycle
    the merged target onto a hostile inbound and FIRE at it while
    guns are affordable; otherwise fire everything at the nearest
    ship — "deactivate the heavies, TAB to the inbound, F". The
    doc-57.3 suppression rows' instrument; rules without a merged
    targeting space (ground) fall through to plain fire."""
    _targets = rules.targetables(ctx) if hasattr(rules, "targetables") else []
    _inbound = [m for m in _targets if getattr(m, "side", None) == "enemy"]
    slots = _fire_slots(ctx, rules)
    _guns_ok = any(rules.can_fire(slot, ctx)[0] for slot in slots)
    _state = getattr(rules, "_state", None)
    _current = (
        _targets[_state.target_idx]
        if _state is not None and 0 <= _state.target_idx < len(_targets)
        else None
    )
    if _inbound:
        if _current in _inbound:
            if _guns_ok:
                return "FIRE"      # on the inbound, guns read for it
        elif _guns_ok:
            # Chase the inbound ONLY when this action would fire at
            # it: guns ready now, a gun that catalog-reaches it, LOS
            # to it. Any weaker gate AP-free loops the cycle (TARGET
            # spends nothing; the ship-aim branch bounces straight
            # back — the harness's stuck-stance guard caught two such
            # cuts before this one).
            _nearest = min(
                _inbound, key=lambda m: _distance(ctx.player.pos, m.pos),
            )
            _reach = max(
                (find_ship_weapon_range(_wid)
                 for _wid in rules.player_weapons(ctx)),
                default=0,
            )
            _clear = _has_los(
                ctx.game_map, ctx.player.pos.x, ctx.player.pos.y,
                _nearest.pos.x, _nearest.pos.y,
            )
            if _distance(ctx.player.pos, _nearest.pos) <= _reach and _clear:
                return "TARGET"
    aimed = _aim_closest(ctx, rules)
    if aimed is None:
        return "WAIT"
    if aimed[1] is None:
        return aimed[0]
    if _guns_ok:
        return "FIRE"
    return "WAIT"


# Stance vocabulary: name -> async (ctx, rules) -> one action string.
# One action per await — the same call shape as the loop's own
# ``_combat_action`` input seam. New stances join when a scenario
# needs one (SETTLED 3); nothing ships here unused. Stances are the
# measurement INSTRUMENT — frozen once landed; a policy change is a
# benchmark revision that re-measures and re-rules its rows in the
# same commit (SETTLED 6).
async def baton_lockdown(ctx, rules) -> str:
    """The control-melee policy (the user's baton game, doc 50
    re-ruling 2026-10-04): the kit wins by LOCKDOWN — each landed
    stun-baton hit drains the target's AP — so play the discipline,
    not the slugfest: never stand with two enemies adjacent (step
    out of the surround), swing only at the one in reach, kite
    otherwise so the pack queues. One enemy in reach at a time, or
    the strategy isn't happening."""
    enemies = rules.get_enemies(ctx)
    if not enemies:
        return "WAIT"
    adjacent = [
        e for e in enemies
        if max(abs(e.pos.x - ctx.player.pos.x), abs(e.pos.y - ctx.player.pos.y)) <= 1
    ]
    if len(adjacent) >= 2:
        # break the surround: step to a free cell minimizing adjacency
        game_map = ctx.game_map
        best, best_score = None, None
        for dx in (-1, 0, 1):
            for dy in (-1, 0, 1):
                if not (dx or dy):
                    continue
                nx, ny = ctx.player.pos.x + dx, ctx.player.pos.y + dy
                if not game_map.in_bounds(nx, ny):
                    continue
                if not game_map.tiles[ny][nx].walkable:
                    continue
                if game_map.blocking_entity_at(nx, ny, exclude=ctx.player):
                    continue
                score = sum(
                    1 for e in enemies
                    if max(abs(e.pos.x - nx), abs(e.pos.y - ny)) <= 1
                )
                if best_score is None or score < best_score:
                    best, best_score = (dx, dy), score
        if best is not None and best_score < len(adjacent):
            return f"MOVE:{_MOVE_KEY_BY_DELTA[best]}"
        return "WAIT"  # pinned: eat the surround, keep swinging below
    if len(adjacent) == 1:
        # lock the one in reach: aim + swing every AP
        target = adjacent[0]
        idx = next(
            (i for i, e in enumerate(enemies) if e is target), None,
        )
        if idx is not None and rules._state.target_idx != idx:
            return "TARGET"
        slots = _fire_slots(ctx, rules)
        if any(rules.can_fire(slot, ctx)[0] for slot in slots):
            return "FIRE"
    # nobody in reach: HOLD — the pack queues on its own collision
    # (bodies can't stack), arrivals land adjacent one at a time.
    # Kiting on this geometry retreats out of the sight grid and
    # disengages the fight before the lockdown ever happens.
    return "WAIT"


STANCES = {
    "baton_lockdown": baton_lockdown,
    "stand_and_trade": stand_and_trade,
    "hold_range": hold_range,
    "posted_hold": posted_hold,
    "toggle_sets": toggle_sets,
    "kite": kite,
    "flak_escort": flak_escort,
}
