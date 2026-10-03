"""Ancient-machine combat machinery (doc 48 phase 9 build 2, SETTLED 42).

One home for the trio's per-machine mechanics, all keyed off the
row-authored :class:`~spacehack.data.npc_chars.MachineMechanics`
dials (an ordinary row with ``mechanics=None`` no-ops everything
here):

* the Shredder's **mend** — in-combat, start of its own turn, no
  out-of-combat tick (wounds persist between fights);
* the Watcher's **shriek + stare** — the alarm as its FIRST AP, the
  3x3 graded zone fixed on the player's cell at enemy phase, the
  eruption at the end of the player's following turn (combat-scoped:
  disengage defuses);
* the Warden's **force field** (build E).

The machines run the standard build-1 volley loop — no carve-outs;
this module is the per-turn preamble and the mechanic resolution,
never a second AI.
"""

from __future__ import annotations

from .. import message_log as _ml
from .. import noise
from ..dungeon_fov import cell_in_sight

# The eruption's hearing radius (doc 48 SETTLED 42): blast-class —
# the explosive column's neighborhood, at the fixed cell.
ERUPTION_NOISE_RADIUS: int = 10


def _mechanics(spec):
    """The row's mechanic dials, or ``None`` for ordinary rows."""
    return getattr(spec, "mechanics", None)


def enemy_turn_start(state, ctx, gei, game_map) -> None:
    """The ancients' per-enemy turn preamble, called at the start of
    each engaged enemy's turn from ``_spend_one_enemy_turn``. The
    Shredder mends; the Watcher shrieks and fixes its stare."""
    mend_turn_start(state, ctx, gei)
    gei.ap -= watcher_turn_start(state, ctx, gei, game_map)


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


# ---------------------------------------------------------------------------
# The Watcher — shriek + stare (doc 48 SETTLED 42)
# ---------------------------------------------------------------------------


def _sees_player(game_map, gei, player_pos) -> bool:
    """The enemy-side sight read (the 09-02 symmetry): the Watcher's
    own cell must sit in the player's sight grid."""
    return cell_in_sight(
        game_map, gei.entity.pos.x, gei.entity.pos.y,
        player_pos.x, player_pos.y,
    )


def watcher_turn_start(state, ctx, gei, game_map) -> int:
    """The Watcher's turn preamble (doc 48 SETTLED 42): a seeing
    Watcher fixes the stare zone on the player's cell (FREE — the
    marking, not an attack), then spends its FIRST AP on the shriek
    (a LEAD ACTION, never a weapon — the drift must not pay for the
    alarm). Returns the AP spent."""
    _m = _mechanics(gei.spec)
    if _m is None or _m.stare_core <= 0 or not gei.alive:
        return 0
    _player_pos = ctx.player.pos
    if not _sees_player(game_map, gei, _player_pos):
        return 0
    _mark_stare_zone(state, ctx, gei, game_map, _player_pos)
    if gei.ap < 1:
        return 0
    ctx.log.add_colored(
        "The Watcher lets out a piercing shriek.", _ml.COLOR_ENEMY_ACTION,
    )
    noise.emit_radius(
        ctx, game_map, gei.entity.pos, _m.shriek_radius,
    )
    return 1


def _mark_stare_zone(state, ctx, gei, game_map, player_pos) -> None:
    """Fix the 3x3 graded zone on the player's cell and say so (the
    user-drafted lines, verbatim): the look reads every round it
    re-fixes; the glow line stacks — ``brighter`` on a live zone,
    ``begins`` on a fresh one. Stacked Watchers COINCIDE: every
    marker on the same cell, damage stacking by count."""
    if game_map.stare_zones is None:
        game_map.stare_zones = {}
    _cell = (player_pos.x, player_pos.y)
    _markers = _live_markers(state, game_map, _cell)
    ctx.log.add_colored(
        "The Watcher turns and looks at you, its eye flashing red.",
        _ml.COLOR_ENEMY_ACTION,
    )
    if _markers:
        ctx.log.add_colored(
            "The floor beneath you glows brighter.", _ml.COLOR_ENEMY_ACTION,
        )
    else:
        ctx.log.add_colored(
            "The floor beneath you begins to glow.", _ml.COLOR_ENEMY_ACTION,
        )
    _markers.append(id(gei.entity))
    game_map.stare_zones[_cell] = _markers


def _live_markers(state, game_map, cell) -> list[int]:
    """The zone's markers whose Watcher still fights — a dead
    Watcher's zones fade (its marker prunes at every read)."""
    _zones = game_map.stare_zones or {}
    _alive = {
        id(_gei.entity) for _gei in state.enemies
        if _gei.alive and _gei.entity is not None
    }
    _markers = [
        _mid for _mid in _zones.get(cell, ())
        if _mid in _alive
    ]
    if not _markers:
        _zones.pop(cell, None)
    else:
        _zones[cell] = _markers
    return _markers


def fade_stare_zones(game_map) -> None:
    """Combat-scoped stare (doc 48 p9): breaking LOS ends the fight
    and pending zones FADE with it — disengage defuses. Called from
    every combat-end path."""
    if game_map.stare_zones:
        game_map.stare_zones = {}
    else:
        game_map.stare_zones = None


def _zone_cells(cell) -> tuple[tuple[int, int], ...]:
    """The graded 3x3 around the fixed cell (core = the cell)."""
    _x, _y = cell
    return tuple(
        (_x + _dx, _y + _dy)
        for _dy in (-1, 0, 1)
        for _dx in (-1, 0, 1)
    )


def resolve_stare_eruptions(state, ctx, game_map) -> str | None:
    """End of the player's turn (doc 48 SETTLED 42): every pending
    zone ERUPTS — anything in the 9 cells takes the graded damage
    (core full, ring half pre-soak; stacks multiply; full soak; no
    to-hit roll). The first enemy-vs-enemy damage vector: victims
    beyond the player resolve through the instance-build path — an
    eruption kill lands the victim's own drops but grants NO player
    XP/rep. Returns ``"DEFEAT"`` when the player dies to a zone."""
    _zones = game_map.stare_zones or {}
    for _cell in sorted(_zones):
        _markers = _live_markers(state, game_map, _cell)
        if not _markers:
            continue
        _marker_gei = _marker_spec(state, _markers[0])
        _m = _mechanics(_marker_gei.spec) if _marker_gei is not None else None
        if _m is None or _m.stare_core <= 0:
            continue
        if not _erupt_zone(
            state, ctx, game_map, _cell, _m.stare_core, len(_markers),
            _marker_gei.name,
        ):
            ctx.log.add_colored(
                "The floor erupts in a violent explosion.",
                _ml.COLOR_COMBAT_EVENT,
            )
        noise.emit_radius(
            ctx, game_map, _cell_pos(_cell), ERUPTION_NOISE_RADIUS,
        )
    fade_stare_zones(game_map)  # every zone spent its beat
    if state.player_hp <= 0:
        return "DEFEAT"
    return None


def _cell_pos(cell):
    from .. import world

    return world.Position(cell[0], cell[1])


def _marker_spec(state, marker_id: int):
    """The dial of one marker's Watcher (stacked Watchers share the
    authored dial), and the instance it belongs to."""
    for _gei in state.enemies:
        if _gei.alive and id(_gei.entity) == marker_id:
            return _gei
    return None


def _erupt_zone(
    state, ctx, game_map, cell, core: int, stacks: int, killer_name: str,
) -> bool:
    """One zone's victims: ``(any_victim?)`` — the per-victim line is
    the user draft (``causing X damage to Y``); the player pays the
    doc-49 per-event reduction like every enemy damage source, and a
    stare death tombstones the MARKING Watcher (the mechanic is never
    named — wordless doctrine; the machine is)."""
    from ..xp import apply_ground_damage_reduction as _reduce

    _any = False
    for _victim_cell in _zone_cells(cell):
        _is_core = _victim_cell == cell
        _pre = core * stacks if _is_core else (core * stacks) // 2
        for _gei, _is_player in _cell_victims(state, ctx, game_map,
                                               _victim_cell):
            if _is_player:
                _dmg = _reduce(ctx, max(1, _pre - state.armor_defense))
                if hasattr(ctx, "player_counters"):
                    ctx.player_counters.ground_damage_taken += _dmg
                state.player_hp -= _dmg
                state.last_attacker = killer_name
                _label = "you"
            else:
                _dmg = _stare_victim_damage(ctx, game_map, _gei, _pre)
                _label = _gei.name
            ctx.log.add_colored(
                f"The floor erupts in a violent explosion "
                f"causing {_dmg} damage to {_label}.",
                _ml.COLOR_COMBAT_EVENT,
            )
            _any = True
    return _any


def _stare_victim_damage(ctx, game_map, gei, pre: int) -> int:
    """One enemy victim's share: armor soaks (full), hp stamped on
    demand through the instance-build path; an eruption kill runs the
    death handling — drops land, NO player XP/rep, no kill counter."""
    _armor = gei.spec.armor if gei.spec else 0
    _dmg = max(1, pre - _armor)
    gei.hp -= _dmg
    if gei.entity is not None:
        gei.entity.hp = max(0, gei.hp)
    if not gei.alive:
        gei.stare_killed = True  # never a defeated_list entry (no rep)
        _eruption_kill(game_map, gei, ctx)
    return _dmg


def _eruption_kill(game_map, gei, ctx) -> None:
    """The eruption's death tail: remove the body, land its OWN
    drops; the player did not attack it — no XP, no rep, no counter."""
    from ._actions import spawn_kill_drops

    _ent = gei.entity
    if _ent is not None and _ent in game_map.entities:
        game_map.entities.remove(_ent)
    if _ent is not None and gei.spec:
        spawn_kill_drops(
            game_map, _ent.pos, gei.spec, ctx,
            loadout=getattr(_ent, "rolled_loadout", None),
            band=gei.band,
            carried=getattr(_ent, "carried_items", None),
        )
    gei.hp = 0


def _cell_victims(state, ctx, game_map, cell) -> list:
    """Who stands on one zone cell: the player plus every
    ground-combat entity — machines stay oblivious to marked cells,
    so a machine in the zone takes it (the baiting vector)."""
    _victims: list = []
    _player = getattr(ctx, "player", None)
    if _player is not None and (_player.pos.x, _player.pos.y) == cell:
        _victims.append((None, True))
    _by_id = {id(_gei.entity): _gei for _gei in state.enemies}
    for _ent in game_map.entities:
        if not getattr(_ent, "npc_char_id", "") or _ent.loot_data is not None:
            continue
        if (_ent.pos.x, _ent.pos.y) != cell:
            continue
        if id(_ent) in _by_id:
            _victims.append((_by_id[id(_ent)], False))
        else:
            from ._rules_ground import _build_enemy_instance

            _inst = _build_enemy_instance(_ent, game_map)
            if _inst is not None:
                _victims.append((_inst, False))
    return _victims
