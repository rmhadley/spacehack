"""Ground tactics wave tests (doc 48 phase 5, SETTLED 16-27/36/37).

Build 1: the data layer — per-weapon noise column, per-spec AP, the
detect_radius retirement. Build 2: the noise system — emission,
hearing selectivity, investigation goals, the reaction line.
"""

from __future__ import annotations

from types import SimpleNamespace

from tests.support.asyncutil import run

import pytest

from src.spacehack import noise, world
from src.spacehack.data.ground_weapons import list_ground_weapons
from src.spacehack.data.npc_chars import NpcCharSpec, find_npc_char
from src.spacehack.data.npc_ships import NpcShipSpec


def _floor_map(*entities: world.Entity) -> world.GameMap:
    """10x5 open floor with optional wall columns stamped per test."""
    tiles = [
        [world.DUNGEON_FLOOR for _ in range(10)]
        for _ in range(5)
    ]
    return world.GameMap(10, 5, tiles, list(entities))


def _wide_map(*entities: world.Entity) -> world.GameMap:
    """20x12 open floor — room for out-of-radius entities."""
    tiles = [
        [world.DUNGEON_FLOOR for _ in range(20)]
        for _ in range(12)
    ]
    return world.GameMap(20, 12, tiles, list(entities))


def _ctx(player, log=None):
    """A ctx double with a recording log (fresh per call)."""
    lines: list[tuple[str, tuple]] = []

    class _Log:
        def add_colored(self, text, color):
            lines.append((text, color))

        def add(self, text):
            lines.append((text, None))

    return SimpleNamespace(
        player=player, faction_reputation={}, log=log or _Log(),
    ), lines


# --- weapon noise column (SETTLED 17) ---------------------------------------

# The authored leans, pinned id-by-id so a new weapon FAILS until its
# hearing radius is authored (registry completeness). Playtest-tunable:
# edits update this table in the same commit.
EXPECTED_NOISE: dict[str, int] = {
    # melee 1-2 — knife kills stay quiet
    "fists": 1, "combat_knife": 1, "stun_baton": 2, "survival_axe": 2,
    "vibroblade": 2, "mono_blade": 2, "power_fist": 2,
    # pistols/SMG 5-6; energy rides the quiet lever at 4
    "laser_pistol": 4, "kinetic_pistol": 5, "smg": 6, "laser_carbine": 4,
    # kinetic rifles 8; energy rifles quiet
    "laser_rifle": 4, "kinetic_rifle": 8, "shotgun": 8, "battle_rifle": 8,
    "railgun": 8, "ion_blaster": 4,
    # plasma 4 — the energy lever
    "plasma_pistol": 4, "plasma_rifle": 4, "plasma_caster": 4,
    # explosives 12
    "grenade_launcher": 12, "rocket_launcher": 12,
    # organic monster parts 4-5
    "monster_claws": 4, "drone_laser": 4, "frost_bolt": 5,
    "parasite_mandibles": 4,
}


def test_every_ground_weapon_carries_authored_noise():
    catalog = {w.id: w.noise for w in list_ground_weapons()}
    assert catalog == EXPECTED_NOISE


@pytest.mark.parametrize("wid,noise", sorted(EXPECTED_NOISE.items()))
def test_noise_values_stay_in_playable_band(wid, noise):
    assert 1 <= noise <= 12, f"{wid} noise {noise} outside [1, 12]"


# --- per-spec AP (SETTLED 27) ----------------------------------------------

def test_authored_speed_axis_aps():
    assert find_npc_char("dust_prowler").ap == 6
    for hunter in ("ice_worm", "rock_scavenger", "hull_parasite"):
        assert find_npc_char(hunter).ap == 5
    for anchor in ("assault_drone", "pirate_brute"):
        assert find_npc_char(anchor).ap == 3


def test_humanoids_and_sentry_default_to_four_ap():
    for spec_id in (
        "pirate_raider", "pirate_rifleman", "militia_marine",
        "militia_sniper", "militia_trooper", "consortium_enforcer",
        "consortium_gunner", "civilian_bystander", "sentry_drone",
        "frost_spitter",
    ):
        assert find_npc_char(spec_id).ap == 4


# --- detect_radius retirement (SETTLED 36) ---------------------------------

def test_ground_detect_radius_is_retired():
    with pytest.raises(TypeError):
        NpcCharSpec(
            id="x", name="X", char="x", fg=(1, 2, 3), faction="pirate",
            detect_radius=5,
        )


def test_ship_detect_radius_stays_live():
    """The retirement is ground-only — NpcShipSpec keeps its field."""
    assert NpcShipSpec.__dataclass_fields__["detect_radius"].default == 0


# --- noise: hearing selectivity (SETTLED 22) --------------------------------

def test_emit_stamps_only_hostile_unengaged_combatants():
    """Dormant deaf, engaged skip, bystanders ignore, out of radius
    deaf — only hostile-reading un-engaged combatants hear."""
    player = world.Entity("@", (255, 255, 255), world.Position(5, 2))
    hearer = world.Entity(
        "p", (255, 100, 100), world.Position(2, 2), npc_char_id="dust_prowler",
    )
    dormant = world.Entity(
        "d", (200, 180, 110), world.Position(3, 2),
        npc_char_id="sentry_drone", powered_down=True,
    )
    engaged = world.Entity(
        "s", (205, 170, 120), world.Position(4, 2),
        npc_char_id="rock_scavenger",
    )
    engaged.combat_locked = True  # transient runtime flag by contract
    bystander = world.Entity(
        "c", (235, 215, 175), world.Position(5, 3),
        npc_char_id="civilian_bystander",
    )
    far = world.Entity(
        "p", (255, 100, 100), world.Position(18, 10), npc_char_id="dust_prowler",
    )
    game_map = _wide_map(player, hearer, dormant, engaged, bystander, far)
    ctx, _ = _ctx(player)

    stamped = noise.emit(
        ctx, game_map, player.pos, "kinetic_rifle", by_player=True,
    )

    assert stamped == [hearer]  # radius 8: in-range hostile hunter only
    assert hearer.last_seen_pos == world.Position(5, 2)
    assert dormant.last_seen_pos is None      # dormant stays deaf
    assert engaged.last_seen_pos is None      # engaged ignore noise
    assert bystander.last_seen_pos is None    # non-hostile ignore gunfire
    assert far.last_seen_pos is None          # radius 8 < distance 9


def test_emit_latest_wins_and_fresh_drives_the_line():
    """A newer event re-stamps investigators; the reaction line fires
    only for FRESH hearers (no active goal)."""
    player = world.Entity("@", (255, 255, 255), world.Position(5, 2))
    hunter = world.Entity(
        "p", (255, 100, 100), world.Position(2, 2), npc_char_id="dust_prowler",
    )
    game_map = _floor_map(player, hunter)
    ctx, lines = _ctx(player)

    noise.emit(ctx, game_map, player.pos, "kinetic_rifle", by_player=True)
    assert len(lines) == 1  # fresh hearer -> one line

    noise.emit(ctx, game_map, world.Position(6, 3), "shotgun", by_player=True)
    assert hunter.last_seen_pos == world.Position(6, 3)  # latest wins
    assert len(lines) == 1  # not fresh anymore -> no second line


def test_emit_quiet_weapons_never_log_the_line():
    """Melee noise (1) may stamp an adjacent neighbour but never logs
    the reaction line (SETTLED 36 — the stealth signal)."""
    player = world.Entity("@", (255, 255, 255), world.Position(5, 2))
    hunter = world.Entity(
        "p", (255, 100, 100), world.Position(6, 2), npc_char_id="dust_prowler",
    )
    game_map = _floor_map(player, hunter)
    ctx, lines = _ctx(player)

    stamped = noise.emit(ctx, game_map, player.pos, "combat_knife", by_player=True)

    assert stamped == [hunter]
    assert hunter.last_seen_pos == world.Position(5, 2)
    assert lines == []  # quiet: no line even with a fresh hearer


def test_emit_enemy_fire_never_logs_the_line():
    player = world.Entity("@", (255, 255, 255), world.Position(5, 2))
    shooter = world.Entity(
        "R", (220, 120, 80), world.Position(2, 2),
        npc_char_id="pirate_rifleman",
    )
    shooter.combat_locked = True  # the engaged shooter ignores noise
    hunter = world.Entity(
        "p", (255, 100, 100), world.Position(8, 2), npc_char_id="dust_prowler",
    )
    game_map = _floor_map(player, shooter, hunter)
    ctx, lines = _ctx(player)

    stamped = noise.emit(
        ctx, game_map, shooter.pos, "battle_rifle", by_player=False,
    )

    assert stamped == [hunter]  # third parties converge on the fight
    assert lines == []          # enemy fire never logs the reaction line


def test_reaction_line_names_nearest_fresh_hearer_direction():
    """8-way player-relative direction to the NEAREST fresh hearer."""
    player = world.Entity("@", (255, 255, 255), world.Position(5, 2))
    near_ne = world.Entity(
        "p", (255, 100, 100), world.Position(7, 1), npc_char_id="dust_prowler",
    )
    far_w = world.Entity(
        "p", (255, 100, 100), world.Position(0, 2), npc_char_id="dust_prowler",
    )
    game_map = _floor_map(player, near_ne, far_w)
    ctx, lines = _ctx(player)

    noise.emit(ctx, game_map, player.pos, "kinetic_rifle", by_player=True)

    assert len(lines) == 1
    assert lines[0][0] == "Something to the north-east heard that."


def test_direction_word_covers_all_eight_ways():
    assert noise.direction_word(0, -1) == "north"
    assert noise.direction_word(1, -1) == "north-east"
    assert noise.direction_word(1, 0) == "east"
    assert noise.direction_word(1, 1) == "south-east"
    assert noise.direction_word(0, 1) == "south"
    assert noise.direction_word(-1, 1) == "south-west"
    assert noise.direction_word(-1, 0) == "west"
    assert noise.direction_word(-1, -1) == "north-west"


# --- guards hear leash-gated (SETTLED 37) -----------------------------------

def test_guard_hears_only_within_rolled_weapon_reach():
    """A guard is an area guardian: it gains the stamp only while the
    sound sits within max_range + 2 of its position."""
    player = world.Entity("@", (255, 255, 255), world.Position(9, 4))
    guard = world.Entity(
        "d", (200, 180, 110), world.Position(2, 2),
        npc_char_id="sentry_drone",
    )
    game_map = _floor_map(player, guard)
    ctx, _ = _ctx(player)
    # Pin the guard's rolled weapon: drone_laser max_range 6 -> leash 8.
    guard.rolled_weapon = ("drone_laser", 0)

    # Rocket (noise 12) 8 cells away: radius passes, leash passes.
    noise.emit(
        ctx, game_map, world.Position(2 + 8, 2), "rocket_launcher",
        by_player=True,
    )
    assert guard.last_seen_pos == world.Position(10, 2)

    # Rocket 9 cells away: the radius still passes but the LEASH is
    # the binding gate — the guard does not come.
    guard.last_seen_pos = None
    noise.emit(
        ctx, game_map, world.Position(2 + 9, 2), "rocket_launcher",
        by_player=True,
    )
    assert guard.last_seen_pos is None


def test_hunter_hears_beyond_any_leash():
    """Hunters are unbound — plain radius check, no leash gate."""
    player = world.Entity("@", (255, 255, 255), world.Position(9, 4))
    hunter = world.Entity(
        "p", (255, 100, 100), world.Position(0, 0), npc_char_id="dust_prowler",
    )
    game_map = _floor_map(player, hunter)
    ctx, _ = _ctx(player)
    hunter.rolled_weapon = ("monster_claws", 0)  # tiny weapon, no gate

    noise.emit(
        ctx, game_map, world.Position(9, 0), "rocket_launcher",
        by_player=True,  # radius 12 reaches the hunter at distance 9
    )
    assert hunter.last_seen_pos == world.Position(9, 0)


# --- rolled-weapon persistence (SETTLED 37) ---------------------------------

def test_ensure_rolled_weapon_is_idempotent():
    """First resolution rolls + stamps; later calls return the stamp
    and never re-roll (re-engagement keeps the same weapon)."""
    hunter = world.Entity(
        "p", (255, 100, 100), world.Position(2, 2), npc_char_id="dust_prowler",
    )
    first = noise.ensure_rolled_weapon(hunter)
    stamped = hunter.rolled_weapon
    assert stamped is not None and stamped[0] == first

    again = noise.ensure_rolled_weapon(hunter)
    assert again == first
    assert hunter.rolled_weapon == stamped  # untouched second call


def test_fixed_rows_roll_their_authored_weapons():
    """Rows without families keep their fixed organic weapons."""
    worm = world.Entity(
        "w", (185, 220, 245), world.Position(2, 2), npc_char_id="ice_worm",
    )
    assert noise.ensure_rolled_weapon(worm) == "monster_claws"
    assert noise.rolled_weapon_quality("monster_claws", 4) == 0  # never rolls


# --- combat-time movement + stepwise LOS join (SETTLED 17/25/36) -------------

def _approach_fixture():
    """A hunter at the west end of a row, its goal far east behind
    walls (LOS blocked, path detours), the player's fog sightline
    opening at x=4 — the walker must stop there mid-approach."""
    player = world.Entity("@", (255, 255, 255), world.Position(7, 2))
    hunter = world.Entity(
        "p", (255, 100, 100), world.Position(0, 2),
        npc_char_id="dust_prowler",  # ap 6
    )
    hunter.last_seen_pos = world.Position(19, 2)
    game_map = _wide_map(player, hunter)
    game_map.tiles[2][10] = world.DUNGEON_WALL  # goal out of sight:
    game_map.tiles[2][11] = world.DUNGEON_WALL  # path detours via row 1
    game_map.visible = [
        [x >= 4 for x in range(game_map.width)]
        for _ in range(game_map.height)
    ]
    game_map.seen = [row[:] for row in game_map.visible]
    return player, hunter, game_map


def test_combat_time_investigator_walks_ap_and_stops_at_sight(monkeypatch):
    """During a live fight an un-engaged hunter walks its spec AP in
    tiles — and STOPS the moment it enters the player's sight, never
    overshooting past LOS (SETTLED 17)."""
    from src.spacehack import ground_npcs

    player, hunter, game_map = _approach_fixture()
    ctx, _ = _ctx(player)
    monkeypatch.setattr(ground_npcs, "_ground_fight_live", lambda _ctx: True)

    ground_npcs.move_ground_npcs(ctx, game_map)

    assert hunter.pos == world.Position(4, 2)  # stopped AT the sightline
    assert hunter.pos.x < 6  # AP left unspent — no overshoot
    assert hunter.last_seen_pos == world.Position(19, 2)  # goal holds


def test_peace_time_movement_stays_one_tile(monkeypatch):
    """No live fight: everything strolls one tile per tick (SETTLED 25)."""
    from src.spacehack import ground_npcs

    player, hunter, game_map = _approach_fixture()
    ctx, _ = _ctx(player)
    monkeypatch.setattr(ground_npcs, "_ground_fight_live", lambda _ctx: False)

    ground_npcs.move_ground_npcs(ctx, game_map)

    assert hunter.pos == world.Position(1, 2)  # the stroll: one tile


def test_combat_time_solo_patrol_walks_ap(monkeypatch):
    """A solo hostile without a goal patrols its AP in tiles during a
    live fight (SETTLED 17) — the path head pops per step — and one
    tile in peace."""
    from src.spacehack import ground_npcs

    player = world.Entity("@", (255, 255, 255), world.Position(10, 10))
    hunter = world.Entity(
        "p", (255, 100, 100), world.Position(0, 2),
        npc_char_id="dust_prowler",  # ap 6
    )
    game_map = _wide_map(player, hunter)
    game_map.visible = [  # never sighted: the patrol keeps its budget
        [False for _ in range(game_map.width)]
        for _ in range(game_map.height)
    ]
    ctx, _ = _ctx(player)
    monkeypatch.setattr(
        ground_npcs, "_patrol_path",
        lambda _sid, e, _map, cache=None: [
            (x, e.pos.y) for x in range(e.pos.x + 1, 20)
        ],
    )

    monkeypatch.setattr(ground_npcs, "_ground_fight_live", lambda _ctx: True)
    ground_npcs.move_ground_npcs(ctx, game_map)
    assert hunter.pos == world.Position(6, 2)  # full AP along the path

    monkeypatch.setattr(ground_npcs, "_ground_fight_live", lambda _ctx: False)
    monkeypatch.setattr(ground_npcs, "_MOVE_CHANCE", 1.0)
    ground_npcs.move_ground_npcs(ctx, game_map)
    assert hunter.pos == world.Position(7, 2)  # one tile per tick


def test_combat_time_squad_patrol_marches_leader_pace(monkeypatch):
    """A patrolling squad marches its cached path at the LEADER's AP in
    combat time — a unit moves together (SETTLED 17/37)."""
    from src.spacehack import ground_npcs

    player = world.Entity("@", (255, 255, 255), world.Position(10, 10))
    members = [
        world.Entity("p", (255, 100, 100), world.Position(0, 2),
                     npc_char_id="dust_prowler", squad_id="pack"),  # ap 6
        world.Entity("p", (255, 100, 100), world.Position(0, 3),
                     npc_char_id="dust_prowler", squad_id="pack"),
    ]
    game_map = _wide_map(player, *members)
    game_map.visible = [
        [False for _ in range(game_map.width)]
        for _ in range(game_map.height)
    ]
    ctx, _ = _ctx(player)
    ground_npcs._paths.pop("pack", None)
    monkeypatch.setattr(
        ground_npcs, "_patrol_path",
        lambda _sid, e, _map, cache=None: [(e.pos.x + 1, e.pos.y)],
    )
    monkeypatch.setattr(ground_npcs, "_ground_fight_live", lambda _ctx: True)

    ground_npcs.move_ground_npcs(ctx, game_map)

    assert members[0].pos == world.Position(6, 2)  # leader's AP: the pace


# --- range management + leash (SETTLED 18/26) --------------------------------

def _open_map(*entities, width: int = 20, height: int = 12) -> world.GameMap:
    tiles = [
        [world.DUNGEON_FLOOR for _ in range(width)]
        for _ in range(height)
    ]
    return world.GameMap(width, height, tiles, list(entities))


def test_back_off_restores_min_range():
    """A hugger inside min_range buys distance until the band restores
    (SETTLED 26 — the inert-rifleman exploit dies)."""
    from src.spacehack.combat._ai_ground import _back_off_step
    from src.spacehack.data.ground_weapons import find_ground_weapon

    player = world.Entity("@", (255, 255, 255), world.Position(5, 6))
    rifleman = world.Entity(
        "R", (220, 120, 80), world.Position(5, 5),
        npc_char_id="pirate_rifleman",
    )
    game_map = _open_map(player, rifleman)
    _ews = find_ground_weapon("kinetic_rifle")  # band [2..7]

    stepped = run(_back_off_step(
        None, None, None, game_map, rifleman, player.pos, _ews,
    ))

    assert stepped is True
    _new = max(
        abs(rifleman.pos.x - player.pos.x), abs(rifleman.pos.y - player.pos.y),
    )
    assert _new >= 2  # min_range restored


def test_pinned_rifleman_is_inert():
    """A ranged face cornered with no qualifying cell does nothing —
    cornering is the counter-play, by design (SETTLED 26)."""
    from src.spacehack.combat._ai_ground import _back_off_step
    from src.spacehack.data.ground_weapons import find_ground_weapon

    player = world.Entity("@", (255, 255, 255), world.Position(5, 5))
    rifleman = world.Entity(
        "R", (220, 120, 80), world.Position(5, 4),
        npc_char_id="pirate_rifleman",
    )
    game_map = _open_map(player, rifleman)
    # Dead-end pocket: wall the rifleman's back and both flanks so the
    # only free cells sit AT or BEHIND the player (distance never grows).
    for _x, _y in ((4, 3), (5, 3), (6, 3), (4, 4), (6, 4)):
        game_map.tiles[_y][_x] = world.DUNGEON_WALL
    _ews = find_ground_weapon("kinetic_rifle")  # min_range 2

    stepped = run(_back_off_step(
        None, None, None, game_map, rifleman, player.pos, _ews,
    ))

    assert stepped is False
    assert rifleman.pos == world.Position(5, 4)  # inert


def test_melee_never_backs_off_or_dances():
    """Melee band [1..1]: adjacency is always in-band — no back-off,
    and a fired melee face holds (no knife-dancers, SETTLED 26)."""
    from src.spacehack.combat._ai_ground import _range_step
    from src.spacehack.data.ground_weapons import find_ground_weapon

    player = world.Entity("@", (255, 255, 255), world.Position(5, 5))
    brute = world.Entity(
        "R", (220, 120, 80), world.Position(5, 6),
        npc_char_id="pirate_brute",
    )
    game_map = _open_map(player, brute)
    _claws = find_ground_weapon("monster_claws")  # band [1..1]

    # Adjacent + fired + LOS: hold — not a reposition, not a back-off.
    _stepped, *_path_state = run(_range_step(
        None, None, None, game_map, brute, player.pos,
        _claws, 1.0, True, True, None, None,
    ))
    assert _stepped is False
    assert brute.pos == world.Position(5, 6)


def test_fired_rifleman_repositions_within_band():
    """Leftover AP after the one-shot cap buys the skirmisher dance: a
    random in-band, LOS-keeping step (SETTLED 26)."""
    from src.spacehack.combat._ai_ground import _reposition_step
    from src.spacehack.data.ground_weapons import find_ground_weapon

    player = world.Entity("@", (255, 255, 255), world.Position(5, 5))
    rifleman = world.Entity(
        "R", (220, 120, 80), world.Position(5, 8),
        npc_char_id="pirate_rifleman",
    )
    game_map = _open_map(player, rifleman)
    _ews = find_ground_weapon("kinetic_rifle")  # band [2..7]

    stepped = run(_reposition_step(
        None, None, None, game_map, rifleman, player.pos, _ews,
    ))

    assert stepped is True
    _new = max(
        abs(rifleman.pos.x - player.pos.x), abs(rifleman.pos.y - player.pos.y),
    )
    assert 2 <= _new <= 7  # still in band
    assert rifleman.pos != world.Position(5, 8)  # it danced


def test_guard_leash_derives_from_the_rolled_weapon():
    """The leash is per-instance: max_range + 2 of the entity's rolled
    weapon (SETTLED 18/37) — the hardcoded 8 is gone."""
    from src.spacehack import noise

    guard = world.Entity(
        "d", (200, 180, 110), world.Position(2, 2),
        npc_char_id="sentry_drone",
    )
    guard.rolled_weapon = ("drone_laser", 0)  # max_range 6
    assert noise.guard_leash(guard) == 8

    guard.rolled_weapon = ("railgun", 0)  # max_range 9 — a sniper's kingdom
    assert noise.guard_leash(guard) == 11


def _turn_ctx(player):
    """ctx double for run_ground_enemy_turn with a recording log."""
    lines: list[str] = []

    class _Log:
        def add(self, text):
            lines.append(text)

        def add_colored(self, text, _color):
            lines.append(text)

    return SimpleNamespace(
        player=player, faction_reputation={}, log=_Log(), lines=lines,
        ground_stats=SimpleNamespace(reflexes=10, strength=10, stamina=10),
    ), lines


def test_distant_enemy_closes_one_step_per_ap(monkeypatch):
    """Beyond max range: one A* step per AP — the close leg of range
    management (SETTLED 26); nothing fires."""
    from src.spacehack.combat import _ai_ground
    from src.spacehack.data.npc_chars import find_npc_char

    player = world.Entity("@", (255, 255, 255), world.Position(2, 6))
    rifleman = world.Entity(
        "R", (220, 120, 80), world.Position(16, 6),
        npc_char_id="pirate_rifleman",
    )
    game_map = _open_map(player, rifleman)  # kinetic_rifle band [2..7]; dist 14
    ctx, lines = _turn_ctx(player)
    monkeypatch.setattr(_ai_ground, "RNG", SimpleNamespace(
        randint=lambda *_a: 100, choice=lambda seq: seq[0],
    ))

    _remaining, _damage, _fired = run(_ai_ground.run_ground_enemy_turn(
        ctx, enemy_weapon_id="kinetic_rifle",
        enemy_spec=find_npc_char("pirate_rifleman"),
        enemy_stats=SimpleNamespace(reflexes=10, strength=10, stamina=10),
        enemy_ap=4, player_pos=player.pos, enemy_entity=rifleman,
        game_map=game_map, armor_defense=0,
    ))

    assert _fired is False
    assert _remaining == 0  # every AP bought a step
    assert abs(rifleman.pos.x - player.pos.x) == 14 - 4  # closed one per AP
    assert any("moves into position" in _l for _l in lines)


def test_one_shot_per_turn_then_the_dance(monkeypatch):
    """In band with LOS: exactly ONE shot per turn (the cap stands) —
    leftover AP repositions within the band (SETTLED 26)."""
    from src.spacehack.combat import _ai_ground
    from src.spacehack.data.npc_chars import find_npc_char

    player = world.Entity("@", (255, 255, 255), world.Position(10, 6))
    rifleman = world.Entity(
        "R", (220, 120, 80), world.Position(10, 2),
        npc_char_id="pirate_rifleman",
    )
    game_map = _open_map(player, rifleman)  # dist 4, in band [2..7]
    ctx, lines = _turn_ctx(player)
    monkeypatch.setattr(_ai_ground, "RNG", SimpleNamespace(
        randint=lambda *_a: 1,  # every shot hits
        choice=lambda seq: seq[0],
    ))

    _remaining, _damage, _fired = run(_ai_ground.run_ground_enemy_turn(
        ctx, enemy_weapon_id="kinetic_rifle",
        enemy_spec=find_npc_char("pirate_rifleman"),
        enemy_stats=SimpleNamespace(reflexes=10, strength=10, stamina=10),
        enemy_ap=4, player_pos=player.pos, enemy_entity=rifleman,
        game_map=game_map, armor_defense=0,
    ))

    assert _fired is True
    assert _damage > 0
    assert sum("Kinetic Rifle" in _l for _l in lines) == 1  # ONE shot only
    assert _remaining == 0  # 2 AP on the shot, 2 on the dance
    assert rifleman.pos != world.Position(10, 2)  # it danced


def test_bystanders_panic_scatter_at_ap_during_a_fight(monkeypatch):
    """Non-combatants join combat-time movement (SETTLED 36): a
    bystander wanders its AP in tiles while a fight is live, ignoring
    gunfire (no attractor), one tile in peace."""
    from src.spacehack import ground_npcs

    player = world.Entity("@", (255, 255, 255), world.Position(15, 2))
    bystander = world.Entity(
        "c", (235, 215, 175), world.Position(5, 5),
        npc_char_id="civilian_bystander",  # ap 4, non-hostile: wanders
    )
    game_map = _wide_map(player, bystander)
    ctx, _ = _ctx(player)
    monkeypatch.setattr(
        ground_npcs, "_random_adjacent",
        lambda _e, _map: (_e.pos.x + 1, _e.pos.y),  # flee east, deterministically
    )

    monkeypatch.setattr(ground_npcs, "_ground_fight_live", lambda _ctx: True)
    ground_npcs.move_ground_npcs(ctx, game_map)
    assert bystander.pos.x == 5 + 4  # AP tiles of panic

    monkeypatch.setattr(ground_npcs, "_ground_fight_live", lambda _ctx: False)
    monkeypatch.setattr(ground_npcs, "_MOVE_CHANCE", 1.0)
    ground_npcs.move_ground_npcs(ctx, game_map)
    assert bystander.pos.x == 5 + 4 + 1  # back to the 1-tick stroll


# --- squads follow noise as a unit (SETTLED 37) ------------------------------

def test_squad_follows_any_members_goal():
    """One hearing member draws the squad: the goalless LEADER walks
    toward the second member's goal (leader-keyed pursuit would leave
    it patrolling); LOS aggro stays individual."""
    from src.spacehack import ground_npcs

    leader = world.Entity(
        "p", (255, 100, 100), world.Position(5, 10),
        npc_char_id="dust_prowler", squad_id="pack",
    )
    hearer = world.Entity(
        "p", (255, 100, 100), world.Position(6, 10),
        npc_char_id="dust_prowler", squad_id="pack",
    )
    hearer.last_seen_pos = world.Position(15, 10)
    tiles = [
        [world.DUNGEON_FLOOR for _ in range(20)]
        for _ in range(20)
    ]
    tiles[10][10] = world.DUNGEON_WALL  # blocks LOS on the goal
    game_map = world.GameMap(20, 20, tiles, [leader, hearer])

    ground_npcs._move_squad(
        [leader, hearer], game_map, is_hostile=True, squad_id="pack",
    )

    assert leader.pos != world.Position(5, 10)  # drawn by the hearer
    assert hearer.pos != world.Position(6, 10)  # walks its own goal
    assert hearer.last_seen_pos == world.Position(15, 10)  # goal holds


# --- guards settle where the search ends (SETTLED 37) ------------------------

def test_guard_re_perches_where_its_investigation_ends():
    """On completing a goal (LOS gained) a guard holds where the search
    ended — guard_post re-stamps to the new perch."""
    from src.spacehack import ground_npcs

    guard = world.Entity(
        "d", (200, 180, 110), world.Position(2, 2),
        npc_char_id="sentry_drone",
    )
    guard.guard_post = world.Position(2, 2)
    guard.last_seen_pos = world.Position(8, 2)
    game_map = _floor_map()
    game_map.tiles[2][5] = world.DUNGEON_WALL  # LOS blocked until walked

    while ground_npcs._investigate_walk(guard, game_map):
        pass  # walk the goal out (bounded by the map edge)

    assert guard.last_seen_pos is None          # investigation done
    assert guard.guard_post == guard.pos        # guards THERE now
    assert guard.guard_post != world.Position(2, 2)



# --- AP derivation + enemy consumables (SETTLED 27/36) -----------------------

def _instance(entity, **over):
    """A GroundEnemyInstance built straight from an entity (no combat
    session) — the consumable-effect test harness."""
    from src.spacehack.combat._rules_ground import GroundEnemyInstance
    from src.spacehack.data.npc_chars import find_npc_char

    _fields = dict(
        entity=entity, spec=find_npc_char(entity.npc_char_id),
        weapon_id="fists", hp=30, max_hp=30, ap=4, ap_total=4,
    )
    _fields.update(over)
    return GroundEnemyInstance(**_fields)


def test_enemy_ap_derives_from_spec():
    """Instance AP is the spec's authored base (SETTLED 27): predators
    fast, anchors slow, humanoids 4."""
    from src.spacehack.combat._rules_ground import _build_enemy_instance

    for spec_id, expected in (
        ("dust_prowler", 6), ("pirate_brute", 3), ("assault_drone", 3),
        ("pirate_raider", 4), ("civilian_bystander", 4),
    ):
        _e = world.Entity(
            "x", (255, 0, 0), world.Position(2, 2), npc_char_id=spec_id,
        )
        _inst = _build_enemy_instance(_e, _open_map(_e))
        assert _inst.ap_total == expected, spec_id
        assert _inst.ap == expected


def test_carried_stamp_resolves_once():
    """The consumable pre-roll is idempotent: a second instance build
    keeps the first stamp (SETTLED 36 — no re-roll)."""
    from src.spacehack.combat._rules_ground import _build_enemy_instance

    raider = world.Entity(
        "r", (220, 120, 80), world.Position(2, 2),
        npc_char_id="pirate_raider",  # pool: pistol_rounds + med_pack
    )
    _open_map(raider)
    _first = _build_enemy_instance(raider)
    _stamped = list(raider.carried_items)
    _second = _build_enemy_instance(raider)
    assert raider.carried_items == _stamped
    assert _second.hp == _first.hp


def test_med_pack_at_half_health():
    """The wounded carrier uses a Med Pack (ANY carrier — SETTLED 36):
    heal now, regen queued, one charge consumed, approved line logged."""
    from src.spacehack.combat._ground_effects import use_carried_consumable

    player = world.Entity("@", (255, 255, 255), world.Position(8, 8))
    prowler = world.Entity(
        "p", (255, 100, 100), world.Position(2, 2),
        npc_char_id="dust_prowler",
    )
    prowler.carried_items = [["consumable", "med_pack", 2]]
    game_map = _open_map(player, prowler)
    inst = _instance(prowler, hp=8, max_hp=30)  # <= 50%
    ctx, lines = _ctx(player)

    spent = use_carried_consumable(ctx, inst, game_map, player.pos)

    assert spent == 1  # use_ap_cost
    assert inst.hp == 13  # +5 heal
    assert inst.regen_turns == 3 and inst.regen_amount == 2
    assert prowler.carried_items == [["consumable", "med_pack", 1]]
    assert lines == [("Dust Prowler uses a Med Pack.", (255, 95, 95))]


def test_stim_requires_los_and_lasts_three_rounds():
    """A stim fires only with LOS (SETTLED 36) and grants +1 AP for
    three round starts (SETTLED 27's mirror)."""
    from src.spacehack.combat._ground_effects import (
        advance_enemy_effects, use_carried_consumable,
    )

    player = world.Entity("@", (255, 255, 255), world.Position(8, 2))
    raider = world.Entity(
        "r", (220, 120, 80), world.Position(2, 2),
        npc_char_id="pirate_raider",
    )
    raider.carried_items = [["consumable", "stim", 1]]
    game_map = _open_map(player, raider)
    game_map.tiles[2][5] = world.DUNGEON_WALL  # blocks the LOS ray
    inst = _instance(raider)
    ctx, lines = _ctx(player)

    # No LOS: the stim does not fire.
    assert use_carried_consumable(ctx, inst, game_map, player.pos) == 0
    assert lines == []

    game_map.tiles[2][5] = world.DUNGEON_FLOOR  # sightline opens
    assert use_carried_consumable(ctx, inst, game_map, player.pos) == 1
    assert lines == [("Pirate Raider injects a Combat Stim.", (255, 95, 95))]
    assert inst.stim_turns == 3
    assert raider.carried_items == []  # last charge consumed

    assert [advance_enemy_effects(inst) for _ in range(4)] == [1, 1, 1, 0]


def test_death_drop_reads_the_carried_stamp():
    """Unused charges drop at their remainder; a spent stack never
    drops; ammo entries keep their death-time roll (SETTLED 36)."""
    from src.spacehack.combat._actions import spawn_kill_drops
    from src.spacehack.data.npc_chars import find_npc_char
    from src.spacehack import engine

    player = world.Entity("@", (255, 255, 255), world.Position(8, 8))
    game_map = _open_map(player)
    spec = find_npc_char("pirate_raider")  # pool: pistol_rounds + med_pack

    engine.RNG.seed(4242)
    spawn_kill_drops(
        game_map, world.Position(5, 5), spec, _ctx(player)[0],
        carried=[["consumable", "med_pack", 1]],
    )
    payloads = [e.loot_data for e in game_map.entities if e.loot_data]

    meds = [p for p in payloads if p.get("item_id") == "med_pack"]
    assert meds and all(p["quantity"] == 1 for p in meds)
    stims = [p for p in payloads if p.get("item_id") == "stim"]
    assert stims == []  # the raider's stim was USED before death


def test_carried_stamp_survives_save_load():
    """The carried stamp round-trips — a fight interrupted mid-use keeps
    the remainder (doc 48 SETTLED 36 save contract)."""
    from src.spacehack import saveload

    hunter = world.Entity(
        "p", (255, 100, 100), world.Position(2, 2),
        npc_char_id="dust_prowler",
    )
    hunter.carried_items = [["consumable", "med_pack", 2]]
    game_map = _floor_map(hunter)

    saved = saveload._dungeon_to_dict(game_map, None)
    restored, _ = saveload._dungeon_from_dict(saved)

    assert restored.entities[0].carried_items == [
        ["consumable", "med_pack", 2],
    ]


def test_dead_enemies_do_not_regenerate():
    """An instance killed inside its regen window stays dead — the
    round-start tick never resurrects (review catch, doc 48 phase 5)."""
    from src.spacehack.combat._ground_effects import advance_enemy_effects

    inst = _instance(world.Entity(
        "r", (220, 120, 80), world.Position(2, 2), npc_char_id="pirate_raider",
    ), hp=0, max_hp=30, regen_turns=1, regen_amount=2)

    assert advance_enemy_effects(inst) == 0
    assert inst.hp == 0
    assert not inst.alive


def test_empty_carried_stamp_survives_and_mints_nothing():
    """A resolved-empty stamp (rolled zero, or used the last charge)
    round-trips as [] — never re-rolled into fresh charges."""
    from src.spacehack import saveload

    hunter = world.Entity(
        "p", (255, 100, 100), world.Position(2, 2),
        npc_char_id="dust_prowler",
    )
    hunter.carried_items = []
    game_map = _floor_map(hunter)

    saved = saveload._dungeon_to_dict(game_map, None)
    assert saved["entities"][0]["carried_items"] == []
    restored, _ = saveload._dungeon_from_dict(saved)
    assert restored.entities[0].carried_items == []


def test_corrupt_carried_entries_skip_individually():
    """A malformed carried row is dropped, the load never crashes, and
    valid siblings survive (corrupt-save tolerance, the stamp twin)."""
    from src.spacehack import saveload

    game_map = _floor_map()
    saved = saveload._dungeon_to_dict(game_map, None)
    saved["entities"] = [{
        "char": "p", "fg_r": 255, "fg_g": 100, "fg_b": 100,
        "x": 2, "y": 2, "npc_char_id": "dust_prowler",
        "carried_items": [
            ["consumable", "med_pack", "two"],   # bad qty
            ["consumable"],                       # short row
            ["consumable", "stim", 1],            # valid
        ],
    }]

    restored, _ = saveload._dungeon_from_dict(saved)
    assert restored.entities[0].carried_items == [["consumable", "stim", 1]]
