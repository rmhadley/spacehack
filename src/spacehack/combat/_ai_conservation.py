"""Enemy AI conservation reads (doc 57.2.5) — the five-step logic
check's state layer.

The pure STATE reads the enemy decision loop consults: the power
reserve protecting the next shield divert, the funds check that keeps
sequential volley fire above it, the shield/hull temperament bend,
and the dry-magazine read. GATES stay in ``_ai._member_included``
(cohesion: reads together here, gates at the choke point); a future
unique/boss spec swaps ``regen_reserve`` — the override seam — for
its own decision loop without touching anything else.
"""

from __future__ import annotations

from ._actions import divert_full_cost, weapon_costs

def _effective_aggressiveness(_ei, _esp) -> int:
    """The BEND (doc 57.2.5) — the ONE read the fire-vs-dodge roll
    resolves with: the spec's ``ai_aggressiveness`` temperament as
    the ship's STATE bends it — for the ships the conservation layer
    GOVERNS (the divert carriers, ``shield_regen_rate > 0``; only
    four specs today). Low shields bend it DOWN (while the reserve
    is active, the temperament scales with the shield fraction — a
    tanking warlord fights cautiously); failing hull bends it UP
    multiplicatively (desperation scales the ship's OWN temperament
    up to ×1.5 below half hull — the cornered last stand that
    completes the arc healthy → tanking → desperate and preserves
    the authored personality: a cornered merchant stays sheepish, a
    cornered warlord hits the cap). Everyone else fights to their
    authored dial, nothing to conserve — the probe refereed this
    scope: even a ×1.4 dying SCOUT broke the tutorial's ruled 0.94
    win floor (goal_1 0.94 → 0.89-0.90), and Jack carries no
    divert. Desperation raises the ROLL only, never the reserve
    bench: a cornered ship still will not fire the plasma it cannot
    fund. The curves stay the probe's to calibrate (57.3)."""
    _agg = _esp.ai_aggressiveness
    _governed = _ei.shield_regen_rate > 0 and _ei.max_shields > 0
    if _governed:
        if _regen_reserve(_ei) > 0:
            _agg = _agg * _ei.shields // _ei.max_shields
        _deficit = max(0.0, 0.5 - _ei.hull / max(1, _ei.max_hull))
        if _deficit > 0:
            # The last stand FLOORS the tank read (reviewer minor 1):
            # desperation scales the DIAL up (×0.5..×1.0 as hull fails
            # below half), never the shield product — a fully-stripped
            # carrier still trades as it dies, the ruled arc's stage 3;
            # multiplying the zero would leave it turtle-dying instead.
            _agg = max(_agg, int(_esp.ai_aggressiveness * (0.5 + _deficit)))
    return max(0, min(100, _agg))


def _regen_reserve(_ei) -> int:
    """The conservation reserve (doc 57.2.5): the power the ship
    protects for its next paid shield divert — the divert's full-rate
    cost while shields sit below the spec's own threshold. 0 for
    ships with no shields, no authored divert rate, or healthy
    shields (only four specs carry a paid divert today). THE
    future-override seam: a unique/boss spec swaps this single read
    for its own decision loop — never scatter the reserve logic."""
    if _ei.max_shields <= 0 or _ei.shield_regen_rate <= 0:
        return 0
    if _ei.shields >= _ei.shield_regen_threshold * _ei.max_shields:
        return 0
    return divert_full_cost(_ei)


def _funds_within_reserve(_ei, ws, *, flak: bool) -> bool:
    """Whether paying for one shot of ``ws`` keeps the LIVE power pool
    at or above the active reserve (doc 57.2.5). The ONE read the
    plan-time member gate and the mid-volley re-gate share, so
    sequential fire enforces the floor cumulatively. Flak never pays
    the reserve — point defense IS conservation (a tanking ship
    still shoots down the missile bearing on it)."""
    if flak:
        return True
    _power = weapon_costs(ws)[1]
    return _ei.power_pool - _power >= _regen_reserve(_ei)


def _magazine_dry(_ei, slot: int, ws) -> bool:
    """Whether the slot cannot fund ONE more shot of its ammo weapon
    (doc 57.2.5) — effectively empty; guns and power weapons never
    run dry."""
    _ammo = weapon_costs(ws)[2]
    return _ammo > 0 and _ei.weapon_ammo.get(slot, 0) < _ammo
