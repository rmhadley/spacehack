"""Ground noise system — weapon-fire hearing and investigation goals.

doc 48 phase 5 (SETTLED 17/22/36/37). Firing emits one event at the
shooter's cell per the weapon's ``noise`` column; explosive impacts
emit a SECOND event at the impact cell — the blast draws entities from
where it lands, not where it was fired. Hearing is a flat Chebyshev
radius check (walls do not block): hostile-reading combatants only —
dormant security stays deaf, engaged entities ignore new noise, and
non-hostile NPCs ignore gunfire entirely.

Heard is never combatant (SETTLED 16 — LOS is the only aggro): a
hearer gains an investigation GOAL at the sound origin (the existing
``last_seen_pos`` attractor slot) and the goal-walker in
:mod:`ground_npcs` moves it until it holds LOS on that area — no tick
memory anywhere (SETTLED 37). Guards are area guardians: they hear
only while the sound sits within their rolled weapon's
``max_range + 2`` (SETTLED 37). Latest event wins — a newer stamp
replaces an older goal; squads follow noise as a unit.

Player-facing feedback is one reaction line per fresh-hearer event
("Something to the {direction} heard that.", SETTLED 36) — the line's
absence is the stealth signal, which is why quiet weapons never log
it even when an adjacent neighbour stirs.
"""

from __future__ import annotations

from . import world
from . import message_log as _ml
from .faction import spec_is_hostile as _spec_is_hostile
from .data.ground_weapons import find_ground_weapon as _find_gw
from .data.npc_chars import find_npc_char as _find_nc

# Weapons at or below this hearing radius never log the reaction line
# (SETTLED 36: "quiet weapons never trigger it"). Hearers within the
# small radius still gain the attractor — the scuffle next door stirs
# a neighbour without announcing itself map-wide.
QUIET_NOISE_MAX: int = 2

# The 8-way compass words, map-relative (screen y grows south).
_DIRECTION_WORDS: tuple[tuple[int, int, str], ...] = (
    (0, -1, "north"), (1, -1, "north-east"), (1, 0, "east"),
    (1, 1, "south-east"), (0, 1, "south"), (-1, 1, "south-west"),
    (-1, 0, "west"), (-1, -1, "north-west"),
)


def direction_word(dx: int, dy: int) -> str:
    """The nearest 8-way compass word for a map delta (y grows south)."""
    if dx == 0 and dy == 0:
        return "north"
    return max(
        _DIRECTION_WORDS,
        key=lambda d: (d[0] * dx + d[1] * dy)
        / ((d[0] * d[0] + d[1] * d[1]) ** 0.5),
    )[2]


def guard_leash(entity: world.Entity, game_map=None) -> int:
    """A guard's hearing/chase leash: its RANGED slot weapon's max + 2
    (SETTLED 18/37) — authority is reach plus reposition room. The key
    is the ranged slot, ALWAYS (doc 48 SETTLED 43): a swapped-to-melee
    guard keeps its authored kingdom.

    Deliberately resolves on first call (idempotent): the loadout MUST
    be stamped by hearing time, so the first-resolution roll lands
    here when a guard hears before it ever fights.
    """
    from . import ground_loadout as _gl

    _stamp = _gl.ensure_loadout(entity, game_map)
    _pair = _gl.pair_for(_stamp, _gl.SET_RANGED) if _stamp else None
    if _pair is None:
        return 3  # weaponless guard: melee reach plus room
    try:
        return _find_gw(_pair[0]).max_range + 2
    except KeyError:
        return 3


def _hears(
    ctx, entity: world.Entity, spec, game_map, origin, radius: int,
) -> bool:
    """Whether one entity hears an event at ``origin`` (flat radius)."""
    if getattr(entity, "powered_down", False):
        return False  # dormant security stays deaf (SETTLED 22)
    if getattr(entity, "combat_locked", False):
        return False  # engaged entities ignore new noise (SETTLED 22)
    if not _spec_is_hostile(ctx, spec, game_map):
        return False  # non-hostile NPCs ignore gunfire (SETTLED 22)
    _dist = max(
        abs(entity.pos.x - origin.x), abs(entity.pos.y - origin.y),
    )
    if _dist > radius:
        return False
    if spec.behavior == "guard":
        # Area guardians hear only within their leash of the sound
        # (SETTLED 37) — a guard is never drawn beyond its reach.
        return _dist <= guard_leash(entity, game_map)
    return True


def _log_reaction_line(ctx, fresh: list, player_pos) -> None:
    """One line naming the nearest fresh hearer's 8-way direction."""
    _nearest = min(
        fresh,
        key=lambda e: max(
            abs(e.pos.x - player_pos.x), abs(e.pos.y - player_pos.y),
        ),
    )
    _word = direction_word(
        _nearest.pos.x - player_pos.x, _nearest.pos.y - player_pos.y,
    )
    ctx.log.add_colored(
        f"Something to the {_word} heard that.", _ml.COLOR_IMPORTANT_EVENT,
    )


def emit(
    ctx, game_map, origin, weapon_id: str, *, by_player: bool,
) -> list:
    """Emit one noise event at ``origin`` for a fired weapon.

    Both sides are symmetric (SETTLED 22): the firing report at the
    shooter's cell (call for every shot) and — for explosives — a
    second blast event at the impact cell (the caller invokes this
    again there). Returns the entities stamped, fresh hearers first
    not required: the list is the full heard set in map order.
    """
    try:
        _radius = _find_gw(weapon_id).noise
    except KeyError:
        return []
    if _radius <= 0:
        return []
    _stamped: list[world.Entity] = []
    _fresh: list[world.Entity] = []
    for _e in game_map.entities:
        _eid = getattr(_e, "npc_char_id", "")
        if not _eid or _e is getattr(ctx, "player", None):
            continue
        try:
            _spec = _find_nc(_eid)
        except KeyError:
            continue
        if not _hears(ctx, _e, _spec, game_map, origin, _radius):
            continue
        if getattr(_e, "last_seen_pos", None) is None:
            _fresh.append(_e)
        _e.last_seen_pos = world.Position(origin.x, origin.y)
        _stamped.append(_e)
    if by_player and _fresh and _radius > QUIET_NOISE_MAX:
        _log_reaction_line(ctx, _fresh, ctx.player.pos)
    return _stamped
