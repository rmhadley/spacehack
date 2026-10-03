"""Ancient-machine combat machinery (doc 48 phase 9 build 2, SETTLED 42).

One home for the trio's per-machine mechanics, all keyed off the
row-authored :class:`~spacehack.data.npc_chars.MachineMechanics`
dials (an ordinary row with ``mechanics=None`` no-ops everything
here):

* the Shredder's **mend** — in-combat, start of its own turn, no
  out-of-combat tick (wounds persist between fights);
* the Watcher's **shriek + stare** (build D);
* the Warden's **force field** (build E).

The machines run the standard build-1 volley loop — no carve-outs;
this module is the per-turn preamble and the mechanic resolution,
never a second AI.
"""

from __future__ import annotations

from .. import message_log as _ml


def _mechanics(spec):
    """The row's mechanic dials, or ``None`` for ordinary rows."""
    return getattr(spec, "mechanics", None)


def enemy_turn_start(state, ctx, gei, game_map) -> None:
    """The ancients' per-enemy turn preamble, called at the start of
    each engaged enemy's turn from ``_spend_one_enemy_turn``. The
    Shredder mends; later builds add the Watcher's shriek + stare
    mark and the Warden's field re-derive + regen."""
    mend_turn_start(state, ctx, gei)


def mend_turn_start(state, ctx, gei) -> None:
    """The Shredder's in-combat mend (doc 48 SETTLED 42): heals its
    ``mend_rate`` at the START of its turn, IN COMBAT ONLY — the
    call site is the combat turn path, so no out-of-combat tick
    exists (wounds persist between fights; it mends only while
    fighting). The line fires on the first successful mend per
    engagement, wordless thereafter (the target card carries it)."""
    _m = _mechanics(gei.spec)
    if _m is None or _m.mend_rate <= 0 or not gei.alive:
        return
    if gei.hp >= gei.max_hp:
        return  # unwounded: nothing to mend, nothing to say
    gei.hp = min(gei.max_hp, gei.hp + _m.mend_rate)
    if gei.entity is not None:
        gei.entity.hp = gei.hp
    if id(gei.entity) not in state.mend_told:
        state.mend_told.add(id(gei.entity))
        ctx.log.add_colored(
            f"The {gei.name}'s wounds begin to mend.",
            _ml.COLOR_ENEMY_ACTION,
        )
