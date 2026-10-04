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

# The player-facing absorb line (SETTLED 45's approved draft, pinned
# verbatim in ONE place — the reword pass at the PROSE checkpoint
# must never miss a copy; the break line lives once in
# :func:`damage_field_tile`).
ABSORB_LINE: str = "The shimmer swallows your shot."


def _mechanics(spec):
    """The row's mechanic dials, or ``None`` for ordinary rows."""
    return getattr(spec, "mechanics", None)


def enemy_turn_start(state, ctx, gei, game_map) -> None:
    """The ancients' per-enemy turn preamble, called at the start of
    each engaged enemy's turn from ``_spend_one_enemy_turn``. The
    Shredder mends; the Watcher shrieks and fixes its stare; the
    Warden re-derives its shell and regenerates it."""
    mend_turn_start(state, ctx, gei)
    gei.ap -= watcher_turn_start(state, ctx, gei, game_map)
    warden_turn_start(gei, game_map)


def enemy_turn_end(gei, game_map) -> None:
    """The per-enemy turn POSTAMBLE: the Warden's shell tracks where
    the body ENDED its turn (the p9 playtest catch — the start-side
    re-derive ran before the movement, so the shimmer trailed the
    body for a full round)."""
    warden_track_position(gei, game_map)


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
    drops, and drop its field if it was the last Warden (the
    player-kill path's twin — a Warden killed by a stare must not
    leave an ownerless shimmer); the player did not attack it — no
    XP, no rep, no counter."""
    from ._actions import spawn_kill_drops

    _ent = gei.entity
    if _ent is not None and _ent in game_map.entities:
        game_map.entities.remove(_ent)
    if _ent is not None and gei.spec:
        maybe_drop_field(game_map, gei.spec)
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


# ---------------------------------------------------------------------------
# The Warden — the force field (doc 48 SETTLED 42)
# ---------------------------------------------------------------------------

# The shell's geometry: a radius-2 Chebyshev ring, one tile thick,
# empty interior (movement is 8-dir; Chebyshev fits the grid).
_FIELD_RADIUS: int = 2


def carries_field(spec) -> bool:
    """Whether the spec projects a force field (the Warden)."""
    _m = _mechanics(spec)
    return _m is not None and _m.field_tile_hp > 0


def shell_cells(game_map, pos) -> tuple[tuple[int, int], ...]:
    """The field's shell cells around ``pos``: in-bounds WALKABLE cells
    at exactly Chebyshev radius 2 — a wall needs no field."""
    _cells = []
    for _dy in range(-_FIELD_RADIUS, _FIELD_RADIUS + 1):
        for _dx in range(-_FIELD_RADIUS, _FIELD_RADIUS + 1):
            if max(abs(_dx), abs(_dy)) != _FIELD_RADIUS:
                continue
            _x, _y = pos.x + _dx, pos.y + _dy
            if game_map.in_bounds(_x, _y) and game_map.is_walkable(_x, _y):
                _cells.append((_x, _y))
    return tuple(_cells)


def ensure_field(game_map, spec, pos) -> None:
    """Stand the shell up at combat entry: a RECENTER around the
    current position — never an add (the p9 baiting catch had each
    re-engagement ADD a ring at the new position while the old cells
    stayed, littering fields across the map). Cells already standing
    keep their wounds (a whittled shell stays whittled through a
    bait cycle); never-seen cells stand at full — it wakes with its
    shield up."""
    _m = _mechanics(spec)
    if _m is None or _m.field_tile_hp <= 0:
        return
    _current = game_map.field_tiles or {}
    _new = _preserve_sibling_shells(game_map, spec, pos, _current)
    for _cell in shell_cells(game_map, pos):
        # 0-HP tombstones (destroyed tiles, pre-ruling saves) are
        # OPEN GROUND, not standing shell — the wake arms them full
        # ("wakes with its shield up"; the live-playtest catch: entry
        # once kept a 0-HP ring and no field spawned at all)
        _new[_cell] = _current.get(_cell, 0) or _m.field_tile_hp
    game_map.field_tiles = _new


def warden_turn_start(gei, game_map) -> None:
    """The Warden's turn preamble (doc 48 SETTLED 42): the shell
    re-derives from its CURRENT position and regenerates
    ``field_regen`` per tile up to full — IN COMBAT (this call site
    is the combat turn path). A destroyed tombstone regrows from 0 —
    a carved hole lives exactly one player volley round; cells newly
    covered by movement stand ARMED FULL (the walking wall). Cells only the acting Warden's OLD shell
    covered drop out; a stationary SIBLING Warden's shell is
    preserved untouched. The body never mends — the field is its
    sustain; self-repair belongs to the Shredder alone."""
    _m = _mechanics(gei.spec)
    if _m is None or _m.field_tile_hp <= 0 or not gei.alive:
        return
    game_map.field_tiles = _rederive_shell(
        game_map, gei.spec, gei.entity.pos, _m.field_regen,
    )


def warden_track_position(gei, game_map) -> None:
    """The turn-END position pass (the p9 playtest catch: "as it
    moves the force field doesn't move with it" — the turn-start
    re-derive ran BEFORE the movement, so the shell trailed the body
    for a full round). Re-derives the shell around where the Warden
    ENDS its turn with NO regen: cells the new ring still covers
    keep their HP, fresh cells ARM FULL (the walking-wall ruling —
    the field never weakens by moving), destroyed tombstones alone
    regrow at turn starts."""
    _m = _mechanics(gei.spec)
    if _m is None or _m.field_tile_hp <= 0 or not gei.alive:
        return
    game_map.field_tiles = _rederive_shell(
        game_map, gei.spec, gei.entity.pos, 0,
    )


def track_field_shells(game_map) -> None:
    """The ambient pass's shell tracker (the p9 baiting catch: a
    baited Warden walked while only its COMBAT turns re-derived —
    each re-engagement's ``ensure_field`` ADDED a ring at the new
    position, so the bait path littered fields across the map).
    Re-centers every awake Warden's shell on its current position
    each tick, regen 0: idempotent when stationary, follows the walk
    when baited (fresh cells armed full — the walking wall), and
    clears stale rings from older saves on the first tick. Only
    destroyed tombstones wait for combat regrowth."""
    from ..data.npc_chars import find_npc_char

    _specs: dict = {}
    for _ent in game_map.entities:
        _eid = getattr(_ent, "npc_char_id", "")
        if not _eid or getattr(_ent, "powered_down", False):
            continue
        if _eid not in _specs:
            try:
                _specs[_eid] = find_npc_char(_eid)
            except KeyError:
                _specs[_eid] = None
        _spec = _specs[_eid]
        if _spec is not None and carries_field(_spec):
            game_map.field_tiles = _rederive_shell(
                game_map, _spec, _ent.pos, 0,
            )


def _rederive_shell(game_map, spec, pos, regen: int) -> dict:
    """The one shell rebuild: preserve sibling coverage, then lay
    this Warden's ring — cells it already covers heal by ``regen``
    (capped; a destroyed 0-HP tombstone regrows only at turn start),
    and cells it newly covers stand ARMED FULL (the p9 ruling: the
    field is a walking wall — movement never weakens it, and the
    trailing-edge 0-HP holes read as uncaused damage in play)."""
    _m = _mechanics(spec)
    _current = game_map.field_tiles or {}
    _new = _preserve_sibling_shells(game_map, spec, pos, _current)
    for _cell in shell_cells(game_map, pos):
        if _cell in _current:
            _new[_cell] = min(
                _m.field_tile_hp, _current[_cell] + regen,
            )
        else:
            _new[_cell] = _m.field_tile_hp
    return _new


def _preserve_sibling_shells(game_map, spec, pos, current) -> dict:
    """Copy every cell a sibling Warden's shell still covers — the
    acting Warden's re-derive owns only its own cells (matched by
    position: the actor itself is excluded by its own ``pos``)."""
    _sibling_cells: set = set()
    for _ent in game_map.entities:
        if getattr(_ent, "powered_down", False):
            continue
        if getattr(_ent, "npc_char_id", "") == spec.id and (
            _ent.pos.x, _ent.pos.y,
        ) != (pos.x, pos.y):
            _sibling_cells.update(shell_cells(game_map, _ent.pos))
    return {
        _cell: _hp for _cell, _hp in current.items()
        if _cell in _sibling_cells
    }


def maybe_drop_field(game_map, spec) -> None:
    """A Warden's death collapses its share of the field: with no
    survivor the whole shimmer dies; with siblings the field
    REBUILDS as the survivors' current rings — the dead one's cells
    clear (the p9 playtest catch: "when I kill the W the force field
    stays" — the merged-survivor rule kept the DEAD ring and the
    survivor's never stood). Dead bodies are already removed by the
    caller's scan order; a dormant Warden projects nothing."""
    if not carries_field(spec):
        return
    _survivor_cells: set = set()
    for _ent in game_map.entities:
        if getattr(_ent, "powered_down", False):
            continue
        if getattr(_ent, "npc_char_id", "") == spec.id:
            _survivor_cells.update(shell_cells(game_map, _ent.pos))
    if not _survivor_cells:
        game_map.field_tiles = None
        return
    _current = game_map.field_tiles or {}
    game_map.field_tiles = {
        _cell: _hp for _cell, _hp in _current.items()
        if _cell in _survivor_cells
    }


def absorb_shot(
    game_map, from_pos, to_pos, *,
    shooter_carries_field: bool,
) -> tuple[int, int] | None:
    """The ONE projectile-absorption read both seams call (doc 48
    SETTLED 42): the first shell tile with HP > 0 on the
    shooter→target line — the SAME Bresenham walk the beam animation
    paints, so what the player SEES cross the shimmer is what blocks.
    Endpoints excluded (a body ON a shell tile is ON the barrier; the
    Warden's own interior cell is never a tile). A field-carrying
    shooter passes its own fire. Returns the absorbing cell or None."""
    if shooter_carries_field or not game_map.field_tiles:
        return None
    from ._animations import _bresenham_line

    _sx, _sy = from_pos.x, from_pos.y
    for _x, _y in _bresenham_line(_sx, _sy, to_pos.x, to_pos.y):
        if (_x, _y) == (_sx, _sy) or (_x, _y) == (to_pos.x, to_pos.y):
            continue  # endpoints never absorb
        if (game_map.field_tiles.get((_x, _y), 0) or 0) > 0:
            return (_x, _y)
    return None


def projectile_damage(weapon_id: str, quality: int = 0) -> int:
    """The pure hit damage a projectile carries into whatever stops
    it (quality-scaled — the same scaling ``ground_damage_raw``
    applies; no armor: a field tile has none, and the strength melee
    bonus never rides a projectile)."""
    from ..data.quality import effective_weapon_spec

    return max(1, effective_weapon_spec(weapon_id, quality).damage)


def damage_field_tile(ctx, game_map, cell, damage: int) -> bool:
    """One tile pays the shot: BINARY blocking means any HP > 0
    absorbs the FULL shot (overflow lost); the tile breaks at 0 and
    the approved break line fires. Returns whether the tile broke."""
    _tiles = game_map.field_tiles
    if not _tiles or cell not in _tiles:
        return False
    _hp = _tiles[cell] - max(1, damage)
    if _hp > 0:
        _tiles[cell] = _hp
        return False
    _tiles[cell] = 0  # destroyed: a 0-HP tombstone — open ground,
    # regrowing +10 at the Warden's turn starts (deleted cells would
    # be indistinguishable from never-existed, which now arms full)
    ctx.log.add_colored(
        "A section of the shimmer breaks apart.", _ml.COLOR_ENEMY_ACTION,
    )
    return True
