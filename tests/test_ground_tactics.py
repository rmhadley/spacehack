"""Ground tactics wave tests (doc 48 phase 5, SETTLED 16-27/36/37).

Build 1: the data layer — per-weapon noise column, per-spec AP, the
detect_radius retirement. Build 2: the noise system — emission,
hearing selectivity, investigation goals, the reaction line.
"""

from __future__ import annotations

from types import SimpleNamespace

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

    while ground_npcs._investigate_step(guard, game_map):
        pass  # walk the goal out (bounded by the map edge)

    assert guard.last_seen_pos is None          # investigation done
    assert guard.guard_post == guard.pos        # guards THERE now
    assert guard.guard_post != world.Position(2, 2)

