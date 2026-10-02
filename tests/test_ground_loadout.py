"""Enemy loadout stamp tests (doc 48 phase 9 build 1, SETTLED 43).

Pins for the stamp's mutation wrappers — the ammo arithmetic the
volley loop will drive (the reviewer's blocking catch: these landed
unloaded in build 1, so their pins land with them).
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.spacehack import ground_loadout
from src.spacehack.data.ground_weapons import find_ground_weapon


def _stamp(ranged=("kinetic_rifle", 0), melee=("combat_knife", 0), **extra):
    """A hand-built stamp with both set keys present (resolved)."""
    base = {
        "ranged": list(ranged) if ranged else None,
        "melee": list(melee) if melee else None,
        "loaded": {"kinetic_rifle": 20} if ranged else {},
        "pool": [["ammo", "rifle_rounds", 3]],
        "active": "ranged",
    }
    base.update(extra)
    return base


# --- sets + swap ---------------------------------------------------------------

def test_active_pair_reads_and_swap_flips():
    stamp = _stamp()
    assert ground_loadout.active_set(stamp) == "ranged"
    assert ground_loadout.active_pair(stamp) == ("kinetic_rifle", 0)

    ground_loadout.swap_active(stamp)
    assert stamp["active"] == "melee"
    assert ground_loadout.active_pair(stamp) == ("combat_knife", 0)
    assert ground_loadout.pair_for(stamp, "ranged") == ("kinetic_rifle", 0)

    ground_loadout.swap_active(stamp)
    assert ground_loadout.active_set(stamp) == "ranged"  # double-toggle


def test_has_any_weapon_on_none_empty_and_weaponless():
    assert not ground_loadout.has_any_weapon(None)
    assert not ground_loadout.has_any_weapon({})
    assert not ground_loadout.has_any_weapon(
        {"ranged": None, "melee": None},
    )
    assert ground_loadout.has_any_weapon(_stamp())
    assert ground_loadout.has_any_weapon(_stamp(ranged=None))


# --- magazine + pool arithmetic -------------------------------------------------

def test_drain_action_consumes_per_shot_and_clamps_at_zero():
    ws = find_ground_weapon("kinetic_rifle")  # ammo_per_shot 1
    stamp = _stamp()

    ground_loadout.drain_action(stamp, ws, shots_fired=3)
    assert stamp["loaded"]["kinetic_rifle"] == 17

    # Overshoot clamps: 20 rounds cannot pay 30 shots.
    ground_loadout.drain_action(stamp, ws, shots_fired=30)
    assert stamp["loaded"]["kinetic_rifle"] == 0


def test_drain_action_ignores_melee_and_energy_weapons():
    knife = find_ground_weapon("combat_knife")
    stamp = _stamp()
    ground_loadout.drain_action(stamp, knife, shots_fired=5)
    assert stamp["loaded"] == {"kinetic_rifle": 20}


def test_can_feed_shot_reads_magazine_then_pool():
    ws = find_ground_weapon("kinetic_rifle")
    dry_pool = _stamp(pool=[])
    dry_pool["loaded"]["kinetic_rifle"] = 0
    assert not ground_loadout.can_feed_shot(dry_pool, ws)

    reloaded_pool = _stamp(pool=[["ammo", "rifle_rounds", 2]])
    reloaded_pool["loaded"]["kinetic_rifle"] = 0
    assert ground_loadout.can_feed_shot(reloaded_pool, ws)  # pool feeds it

    assert ground_loadout.can_feed_shot(_stamp(), ws)  # magazine feeds it
    assert ground_loadout.can_feed_shot(_stamp(), find_ground_weapon("fists"))


def test_needs_reload_only_when_magazine_cannot_pay_a_shot():
    ws = find_ground_weapon("kinetic_rifle")
    assert not ground_loadout.needs_reload(_stamp(), ws)
    dry = _stamp()
    dry["loaded"]["kinetic_rifle"] = 0
    assert ground_loadout.needs_reload(dry, ws)
    # Melee never reloads.
    assert not ground_loadout.needs_reload(
        dry, find_ground_weapon("combat_knife"),
    )


def test_reload_from_pool_fills_to_capacity_bounded_by_pool():
    ws = find_ground_weapon("kinetic_rifle")  # capacity 20
    stamp = _stamp()

    # The enemy reload triggers on a DRY magazine (cannot pay a shot);
    # the fill draws the player's law: toward capacity, bounded by pool.
    stamp["loaded"]["kinetic_rifle"] = 0
    stamp["pool"] = [["ammo", "rifle_rounds", 4]]
    moved = ground_loadout.reload_from_pool(stamp, ws)
    assert moved == 4  # pool-bounded
    assert stamp["loaded"]["kinetic_rifle"] == 4
    assert stamp["pool"] == [["ammo", "rifle_rounds", 0]]

    stamp["loaded"]["kinetic_rifle"] = 0
    stamp["pool"] = [["ammo", "rifle_rounds", 30]]
    assert ground_loadout.reload_from_pool(stamp, ws) == 20  # capacity-bounded
    assert stamp["pool"] == [["ammo", "rifle_rounds", 10]]

    # A magazine that can still pay a shot does not reload mid-volley.
    stamp["loaded"]["kinetic_rifle"] = 3
    assert ground_loadout.reload_from_pool(stamp, ws) == 0
    assert stamp["loaded"]["kinetic_rifle"] == 3
    # A dry magazine with an empty pool no-ops.
    stamp["loaded"]["kinetic_rifle"] = 0
    stamp["pool"] = []
    assert ground_loadout.reload_from_pool(stamp, ws) == 0
    assert stamp["loaded"]["kinetic_rifle"] == 0


def test_pool_rounds_and_entries_read_by_ammo_type():
    stamp = _stamp()
    assert ground_loadout.pool_rounds(stamp, "rifle_round") == 3
    assert ground_loadout.pool_rounds(stamp, "energy_cell") == 0
    stamp["pool"][0][2] = 0
    assert ground_loadout.pool_entries(stamp) == []  # spent entries drop none
    assert ground_loadout.pool_entries(None) == []


# --- migration completion (the reviewer catch) ----------------------------------

def test_migrated_stamp_completes_armed_at_first_engagement(monkeypatch):
    """A legacy pair loads with empty loaded/pool; first engagement
    fills the melee set AND the ranged slot's magazine + pool — the
    migrated gunner reaches the volley economy armed, not knife-locked."""
    from src.spacehack import world

    gunner = world.Entity(
        "e", (90, 120, 200), world.Position(2, 2),
        npc_char_id="consortium_gunner",
    )
    gunner.rolled_loadout = {
        "ranged": ["kinetic_pistol", 1], "loaded": {},
        "pool": [], "active": "ranged",
    }  # melee key absent = migrated

    class _Seq:
        def choice(self, seq):
            return seq[-1]  # melee family's top t1: stun_baton? seq[-1] of t1 ids

        def random(self):
            return 0.99

        def randint(self, lo, hi):
            return lo

    monkeypatch.setattr(ground_loadout, "RNG", _Seq())
    stamp = ground_loadout.ensure_loadout(gunner)

    assert "melee" in stamp
    assert stamp["melee"] is not None
    assert stamp["loaded"]["kinetic_pistol"] == 12  # magazine backfilled
    assert stamp["pool"] == [["ammo", "pistol_rounds", 2]]  # pool backfilled
    # Second ensure never re-rolls or re-arms.
    snapshot = dict(stamp)
    stamp["loaded"]["kinetic_pistol"] = 5
    ground_loadout.ensure_loadout(gunner)
    assert stamp["loaded"]["kinetic_pistol"] == 5
    assert stamp == {**snapshot, "loaded": {"kinetic_pistol": 5}}


def test_resolved_stamp_never_re_arms(monkeypatch):
    """A fully resolved stamp (both keys present) is returned as-is —
    live mid-fight counts are never topped up."""
    from src.spacehack import world

    hunter = world.Entity(
        "p", (255, 100, 100), world.Position(2, 2),
        npc_char_id="dust_prowler",
    )
    hunter.rolled_loadout = _stamp()
    # Mid-fight DRY magazine: 0 is a live count, never topped up.
    hunter.rolled_loadout["loaded"]["kinetic_rifle"] = 0
    hunter.rolled_loadout["pool"] = []

    def _boom(*_a, **_k):
        raise AssertionError("resolved stamps never roll")

    monkeypatch.setattr(ground_loadout, "RNG", _boom)
    assert ground_loadout.ensure_loadout(hunter) is hunter.rolled_loadout


def test_is_dry_is_the_feed_complement():
    """Dry = no ammo anywhere (magazine AND pool) — the dry-switch
    trigger, expressed as can_feed_shot's exact complement."""
    from src.spacehack import ground_scale

    ws = find_ground_weapon("kinetic_rifle")
    fed = _stamp()  # magazine pays
    assert not ground_loadout.is_dry(fed, ws)

    mag_dry_pool_full = _stamp()
    mag_dry_pool_full["loaded"]["kinetic_rifle"] = 0
    assert not ground_loadout.is_dry(mag_dry_pool_full, ws)  # pool feeds it
    assert not ground_loadout.magazine_pays_shot(mag_dry_pool_full, ws)

    dry = _stamp(pool=[])
    dry["loaded"]["kinetic_rifle"] = 0
    assert ground_loadout.is_dry(dry, ws)
    assert not ground_loadout.magazine_pays_shot(dry, ws)
    # Melee is never dry.
    assert not ground_loadout.is_dry(dry, find_ground_weapon("fists"))
    assert ground_scale.ammo_fed(find_ground_weapon("kinetic_rifle"))


def test_magazine_ammo_types_keys_on_magazine_fed_weapons_only():
    """The retirement key: only magazine-fed weapons' types retire the
    authored death-roll — typed-but-infinite (drone_laser) and organic
    weapons author their pool ammo as ordinary loot; unknown ids skip."""
    from src.spacehack import ground_loadout

    fed = _stamp()  # kinetic_rifle: magazine-fed
    assert ground_loadout.magazine_ammo_types(fed) == {"rifle_round"}

    organic = _stamp(ranged=("drone_laser", 0))
    assert ground_loadout.magazine_ammo_types(organic) == set()

    melee_only = _stamp(ranged=None)
    assert ground_loadout.magazine_ammo_types(melee_only) == set()

    unknown = {
        "ranged": ["does_not_exist", 0], "melee": ["kinetic_rifle", 0],
        "loaded": {}, "pool": [], "active": "ranged",
    }
    assert ground_loadout.magazine_ammo_types(unknown) == {"rifle_round"}
    assert ground_loadout.magazine_ammo_types(None) == set()
