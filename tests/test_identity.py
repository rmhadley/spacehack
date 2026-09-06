"""The transponder / ID layer (doc 40, phase 1).

An ID is an identifier that maps to relations; the game lived in
live mode since day one. Phase 1 covers the state model (live /
dark / spoofed, the worn-face library), persistence + existing-save
migration, the rep-routing gate (actions under a fake ID cannot
alter the true ID), and the F-screen identity hub.
"""

from __future__ import annotations

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))

from support.quest_ctx import quest_ctx


def _pirate_face(id_: str = "KG-8812"):
    return {
        "id": id_, "kind": "cloned",
        "label": "Warlord face", "faction": "pirate",
    }


def test_state_machine_live_dark_spoofed():
    from src.spacehack import identity

    ctx = quest_ctx()
    ctx.broadcast_dark = False
    ctx.broadcast_identity = None
    ctx.collected_ids = []
    assert identity.broadcast_mode(ctx) == identity.LIVE
    assert identity.resolved_identity(ctx)["kind"] == "true"
    identity.ensure_registration(ctx)
    assert ctx.ship_registration

    identity.toggle_dark(ctx)
    assert identity.broadcast_mode(ctx) == identity.DARK
    assert identity.resolved_identity(ctx) is None

    identity.toggle_dark(ctx)  # back to live, then wear the face
    identity.collect_id(ctx, _pirate_face())
    identity.cycle_identity(ctx)
    assert identity.broadcast_mode(ctx) == identity.SPOOFED
    worn = identity.resolved_identity(ctx)
    assert worn["id"] == "KG-8812" and worn["faction"] == "pirate"

    # Dark is the master switch: the face stays filed, nothing broadcasts.
    identity.toggle_dark(ctx)
    assert identity.broadcast_mode(ctx) == identity.DARK
    identity.toggle_dark(ctx)
    assert identity.broadcast_mode(ctx) == identity.SPOOFED

    identity.cycle_identity(ctx)  # off the end of the library = no face
    assert identity.broadcast_mode(ctx) == identity.LIVE


def test_cycle_wraps_through_the_library():
    from src.spacehack import identity

    ctx = quest_ctx()
    identity.collect_id(ctx, _pirate_face())
    identity.collect_id(ctx, {"id": "YY-5678", "kind": "scrubbed",
                              "label": "Blank hull", "faction": None})

    identity.cycle_identity(ctx)
    assert identity.resolved_identity(ctx)["id"] == "KG-8812"
    identity.cycle_identity(ctx)
    assert identity.resolved_identity(ctx)["id"] == "YY-5678"
    identity.cycle_identity(ctx)
    assert identity.broadcast_mode(ctx) == identity.LIVE


def test_collect_id_rejects_duplicates():
    from src.spacehack import identity

    ctx = quest_ctx()
    assert identity.collect_id(ctx, _pirate_face()) is True
    assert identity.collect_id(ctx, _pirate_face()) is False
    assert len(ctx.collected_ids) == 1


def test_masked_actions_cannot_alter_true_ratings():
    """THE doc 40 twist: rep moves only while live. The mask cuts
    both ways — no losses, and no gains either."""
    from src.spacehack.faction import modify_rep

    ctx = quest_ctx()
    ctx.faction_reputation = {"militia": 10}

    ctx.broadcast_dark = True
    modify_rep(ctx, "militia", -5)  # a crime, unseen
    modify_rep(ctx, "militia", 5)   # a good deed, unrecorded
    assert ctx.faction_reputation["militia"] == 10

    ctx.broadcast_dark = False
    ctx.broadcast_identity = _pirate_face()
    modify_rep(ctx, "militia", 5)
    assert ctx.faction_reputation["militia"] == 10

    ctx.broadcast_identity = None  # live again: rep flows
    modify_rep(ctx, "militia", 5)
    assert ctx.faction_reputation["militia"] == 15


def test_in_person_events_bypass_the_broadcast_gate():
    """Face-to-face dealings (quest rewards, NPC talks) don't ride
    the ship's transponder — they always touch the true ratings."""
    from src.spacehack.faction import modify_rep

    ctx = quest_ctx()
    ctx.faction_reputation = {"militia": 10}
    ctx.broadcast_dark = True

    modify_rep(ctx, "militia", 5, in_person=True)
    assert ctx.faction_reputation["militia"] == 15


def test_monthly_decay_ignores_the_broadcast_state():
    """Decay is time, not action — it writes directly."""
    from src.spacehack.faction import apply_monthly_decay

    ctx = quest_ctx()
    ctx.faction_reputation = {"militia": 40}  # liked: decays toward neutral
    ctx.broadcast_dark = True

    apply_monthly_decay(ctx)
    assert ctx.faction_reputation["militia"] == 38  # liked drift -2, gate-free


def test_registration_generates_once_and_migrates_saves():
    from src.spacehack import identity

    ctx = quest_ctx()
    first = identity.ensure_registration(ctx)
    assert first == identity.ensure_registration(ctx)  # stable
    assert ctx.ship_registration

    fresh = quest_ctx()  # an existing save: empty field, one field only
    reg = identity.ensure_registration(fresh)
    assert reg and reg == fresh.ship_registration


def test_save_round_trip_carries_the_identity_state():
    """Restore reads the identity fields back (the full save→load
    round trip is covered in test_saveload) and a legacy save with no
    keys migrates: a registration is generated on restore."""
    from src.spacehack.saveload import _restore_quest_and_tutorial

    ctx = quest_ctx()
    data = {
        "ship_registration": "AB-1234",
        "broadcast_dark": True,
        "broadcast_identity": _pirate_face(),
        "collected_ids": [_pirate_face()],
    }
    _restore_quest_and_tutorial(ctx, data)
    assert ctx.ship_registration == "AB-1234"
    assert ctx.broadcast_dark is True
    assert ctx.broadcast_identity["id"] == "KG-8812"
    assert ctx.collected_ids[0]["id"] == "KG-8812"

    legacy = quest_ctx()
    _restore_quest_and_tutorial(legacy, {})
    assert legacy.ship_registration, "legacy saves gain a registration"
    assert legacy.broadcast_dark is False


def test_faction_frame_shows_the_broadcast_block():
    from src.spacehack.pygame_faction import frame_for

    ctx = quest_ctx()
    frame = frame_for(ctx)
    assert frame.identity_lines
    assert "LIVE" in frame.identity_lines[0]
    assert ctx.ship_registration in frame.identity_lines[0]
    assert "[1/1]" in frame.identity_lines[0]
    assert "Reputation moves only" not in " ".join(frame.identity_lines)
    assert "nothing resolves" not in " ".join(frame.identity_lines)

    dark = quest_ctx()
    dark.broadcast_dark = True
    assert "DARK" in frame_for(dark).identity_lines[0]

    masked = quest_ctx()
    masked.collected_ids = [_pirate_face()]
    masked.broadcast_identity = _pirate_face()
    lines = frame_for(masked).identity_lines
    assert "[2/2]" in lines[0]
    assert "SPOOFED" in lines[0] and "KG-8812" in lines[0]
    # One line: the count rides the ID, no summary line under it.
    assert len(lines) == 1
    assert "collected ID(s)" not in lines[0]


def test_library_position_counts_the_true_registration_as_slot_one():
    """[x/y]: slot 1 is the true registration, each collected ID one
    more; the position tracks the queued face even while dark."""
    from src.spacehack.identity import library_position

    ctx = quest_ctx()
    assert library_position(ctx) == (1, 1)  # no library: just you

    ctx.collected_ids = [_pirate_face()]
    assert library_position(ctx) == (1, 2)  # nothing worn: slot 1

    ctx.broadcast_identity = _pirate_face()
    assert library_position(ctx) == (2, 2)

    ctx.broadcast_dark = True  # queued face still holds its slot
    assert library_position(ctx) == (2, 2)


def test_npc_broadcasts_carry_registration_codes(monkeypatch):
    """Each NPC hull broadcasts its own registration (doc 40: NPCs
    broadcast — a hail reads a hull number, same flavor as yours)."""
    from types import SimpleNamespace
    from src.spacehack import identity
    from src.spacehack.comms import _contact_broadcast_line

    issued = iter(("AA-1111", "BB-2222"))
    monkeypatch.setattr(identity, "generate_registration", lambda: next(issued))

    patrol_a = SimpleNamespace(npc_ship_id="militia_blockade")
    patrol_b = SimpleNamespace(npc_ship_id="militia_blockade")
    first = identity.npc_identity(patrol_a)
    assert first["id"] == "AA-1111"
    assert first["kind"] == "npc"
    assert first["label"] == "Militia Blockade"
    # Stable for the hull's life; a second hull its own number.
    assert identity.npc_identity(patrol_a)["id"] == "AA-1111"
    assert identity.npc_identity(patrol_b)["id"] == "BB-2222"
    assert identity.npc_identity(SimpleNamespace()) is None

    assert _contact_broadcast_line(patrol_a) == "Broadcast: AA-1111 - militia"


def test_scrub_broker_purchase_and_gating():
    """The first acquisition vector: a priced scrub at Deadfall
    (rare and involved per doc 40 Q6 — 6,000cr, one hull number,
    no rep required; fabricating militia rank stays quest content)."""
    from src.spacehack.identity import buy_scrubbed_id, scrub_price

    assert scrub_price("deadfall_scrubber") == 6000
    assert scrub_price("barkeep") is None

    poor = quest_ctx(credits=5_999)
    assert not buy_scrubbed_id(poor, "deadfall_scrubber")
    assert poor.collected_ids == []

    rich = quest_ctx(credits=8_000)
    assert buy_scrubbed_id(rich, "deadfall_scrubber")
    assert rich.stats.credits == 2_000
    face = rich.collected_ids[0]
    assert face["kind"] == "scrubbed" and face["faction"] is None
    assert face["id"] != face["id"].lower()  # registration format


def test_dark_suppresses_auto_hail(monkeypatch):
    """A dark transponder is not hailable — the scan hail never
    fires (dark is countered by eyes, not electronics)."""
    from src.spacehack import navigation_combat as nc
    from src.spacehack import world

    fired = []
    monkeypatch.setattr(
        nc, "_fire_warning",
        lambda _ctx, _sys, _e: fired.append(_e) or (True, None),
    )
    # The militia scan is a chance roll — pin it so the LIVE case
    # deterministically hails (an unseeded RNG flakes this ~60%).
    from src.spacehack import engine
    monkeypatch.setattr(engine.RNG, "random", lambda: 0.0)
    ctx = quest_ctx()
    ctx.militia_scanned = set()
    ctx.player = world.Entity("@", (255, 255, 255), world.Position(5, 5))
    patrol = world.Entity(
        "M", (100, 200, 255), world.Position(5, 6),
        npc_ship_id="militia_patrol",
    )

    # Live: the hail fires — the warning opens comms.
    spec = nc.find_npc_ship("militia_patrol")
    nc._spec_distance_hail(ctx, "sol", patrol, spec, ctx.player.pos)
    assert fired == [patrol]

    # Dark: the hail never happens.
    ctx.broadcast_dark = True
    nc._auto_hail_entity(ctx, "sol", patrol, ctx.player.pos, object())
    assert fired == [patrol], "dark ships are not hailable"


def test_scrubbed_face_masks_every_faction_row():
    """A factionless face (the scrubbed hull a broker sells) resolves
    nothing for any reader — wearing it must mask ALL rows, not fall
    through to the true ratings."""
    from src.spacehack.pygame_faction import frame_for

    ctx = quest_ctx()
    ctx.faction_reputation = {"pirate": -80, "merchant": 40}
    ctx.collected_ids = [{
        "id": "KX-1234", "kind": "scrubbed",
        "label": "Scrubbed hull", "faction": None,
    }]
    ctx.broadcast_identity = ctx.collected_ids[0]

    rows = {r.label: r for r in frame_for(ctx).rows}
    for row in rows.values():
        assert row.attitude == "No Data"
        assert row.reputation == 0

    ctx.broadcast_identity = None
    rows = {r.label: r for r in frame_for(ctx).rows}
    assert rows["Pirate"].attitude == "Enemy"      # true ratings back
    assert rows["Merchant"].attitude == "Liked"


def test_faction_rows_resolve_through_the_broadcast():
    """Masked standings show what READERS see, always tagged: the
    worn face's faction reads Friendly (Faked); everything else No
    Data; dark resolves nothing (doc 40: the mask cuts both ways)."""
    from src.spacehack.pygame_faction import frame_for

    ctx = quest_ctx()
    ctx.faction_reputation = {"pirate": -80, "merchant": 40}
    from src.spacehack.identity import collect_id
    collect_id(ctx, _pirate_face())
    ctx.broadcast_identity = _pirate_face()

    rows = {r.label: r for r in frame_for(ctx).rows}
    assert rows["Pirate"].attitude == "Friendly (Faked)"
    assert rows["Merchant"].attitude == "No Data"
    assert rows["Militia"].attitude == "No Data"

    ctx.broadcast_dark = True
    rows = {r.label: r for r in frame_for(ctx).rows}
    assert rows["Pirate"].attitude == "No Data (Dark)"
    assert rows["Merchant"].attitude == "No Data (Dark)"

    ctx.broadcast_dark = False
    ctx.broadcast_identity = None
    rows = {r.label: r for r in frame_for(ctx).rows}
    assert rows["Pirate"].attitude == "Enemy"         # true ratings back
    assert rows["Merchant"].attitude == "Liked"


def _dark_dock_ctx():
    ctx = quest_ctx()
    ctx.broadcast_dark = True
    return ctx


def test_dark_dock_gate_port_classes():
    """Doc 40 3a: the whitelist IS the dark_berth data opt-ins —
    whitelisted ports berth a dark hull; lawful AND neutral ports
    refuse (trust is the gate, not patrols)."""
    from src.spacehack.game_interactions import _dark_dock_refusal

    for pid in ("lal_b", "lal_c", "ross_b", "wolf_b"):
        assert _dark_dock_refusal(_dark_dock_ctx(), pid) is None, pid
    lawful = _dark_dock_refusal(_dark_dock_ctx(), "earth")
    neutral = _dark_dock_refusal(_dark_dock_ctx(), "ross_c")
    assert lawful == "Docking request denied: transponder not responding."
    assert neutral == lawful  # one uniform port line, every refusing port


def test_dark_dock_gate_spares_scrubbed_and_live():
    """Blank paper complies — a scrubbed hull (and a live one) never
    triggers the refusal; compliance is what the 6,000cr buys."""
    from src.spacehack.game_interactions import _dark_dock_refusal

    scrubbed = quest_ctx()
    scrubbed.collected_ids = [{
        "id": "KX-1234", "kind": "scrubbed",
        "label": "Scrubbed hull", "faction": None,
    }]
    scrubbed.broadcast_identity = scrubbed.collected_ids[0]
    assert _dark_dock_refusal(scrubbed, "earth") is None
    assert _dark_dock_refusal(quest_ctx(), "earth") is None  # live


def test_dark_refusal_precedes_cargo_scan_and_never_builds_city(monkeypatch):
    """The refusal happens in space: the scan never runs, the city map
    is never built, and the mode stays 'space'."""
    from types import SimpleNamespace
    from src.spacehack import game_interactions

    scanned = []
    monkeypatch.setattr(
        game_interactions, "_run_cargo_scan", lambda _c, _p: scanned.append(_p)
    )
    messages = []
    ctx = SimpleNamespace(
        militia_scanned=[], ground_hp=23, ground_max_hp=23,
        broadcast_dark=True,
    )
    state = SimpleNamespace(
        ctx=ctx, console=object(), log=SimpleNamespace(add=messages.append),
        game_map=object(), current_mode="space",
    )

    result = game_interactions.land_at_city(state, "earth")

    assert result == "CONTINUE"
    assert state.current_mode == "space"
    assert scanned == [], "the refusal precedes the cargo scan"
    assert messages == ["Docking request denied: transponder not responding."]


def test_dark_refusal_keeps_the_current_system(monkeypatch):
    """A refused teleport must not switch the module-level system —
    the player never left the old system's map."""
    from src.spacehack import game_interactions, solar_system as solar_module
    from support.landing import landing_state

    monkeypatch.setattr(
        solar_module, "current_solar_system_id",
        solar_module.current_solar_system_id,
    )
    before = solar_module.current_solar_system_id

    result = game_interactions.land_at_city(
        landing_state(broadcast_dark=True), "earth"
    )

    assert result == "CONTINUE"
    assert solar_module.current_solar_system_id == before


def test_dark_hull_berths_at_whitelisted_port(monkeypatch):
    """End to end through the production landing path: a dark hull
    lands at Deadfall (lal_b) — city mode, ids synced."""
    from src.spacehack import game_interactions, solar_system as solar_module
    from support.landing import landing_state

    monkeypatch.setattr(
        solar_module, "current_solar_system_id",
        solar_module.current_solar_system_id,
    )
    monkeypatch.setattr(game_interactions, "_run_cargo_scan", lambda _c, _p: None)
    state = landing_state(broadcast_dark=True)

    result = game_interactions.land_at_city(state, "lal_b")

    assert result == "CONTINUE"
    assert state.current_mode == "city"
    assert state.current_city_id == "lal_b"


def _space_ctx(**extra):
    """A space ctx with the player one cell from a spawned patrol."""
    from src.spacehack import world

    ctx = quest_ctx(**extra)
    ctx.militia_scanned = set()
    ctx.player = world.Entity("@", (255, 255, 255), world.Position(5, 5))
    return ctx


def _patrol(npc_ship_id="militia_patrol", pos=(5, 6)):
    from src.spacehack import world

    return world.Entity(
        "M", (100, 200, 255), world.Position(*pos), npc_ship_id=npc_ship_id,
    )


def test_dark_hull_is_challenged_by_militia_on_spot(monkeypatch):
    """Doc 40 3b: a militia ship that PHYSICALLY spots a dark hull
    (detect radius — eyes, not electronics) challenges it: identify
    or attack. One-shot per patrol."""
    from src.spacehack import navigation_combat as nc

    challenged = []
    monkeypatch.setattr(
        "src.spacehack.comms.open_challenge_direct",
        lambda _ctx, _e: challenged.append(_e) or None,
    )
    ctx = _space_ctx(broadcast_dark=True)
    patrol = _patrol()

    result = nc._auto_hail_entity(ctx, "sol", patrol, ctx.player.pos, object())

    assert challenged == [patrol]
    assert result is not None and result[0] is True
    assert nc._entity_hail_key(patrol) in ctx.militia_scanned
    # One-shot: the same patrol does not re-challenge every tick.
    assert nc._auto_hail_entity(ctx, "sol", patrol, ctx.player.pos, object()) is None


def test_challenge_is_militia_only_and_outside_detect_radius():
    """Pirates never challenge (silence in Ross is business as usual);
    a militia ship that hasn't physically spotted the hull doesn't
    either."""
    from src.spacehack import navigation_combat as nc

    ctx = _space_ctx(broadcast_dark=True)
    pirate = _patrol(npc_ship_id="pirate_scout")
    assert nc._dark_spot_challenge(ctx, pirate, nc.find_npc_ship("pirate_scout"), ctx.player.pos) is None

    far = _patrol(pos=(5 + 8, 6))  # beyond militia detect_radius 7
    assert nc._dark_spot_challenge(ctx, far, nc.find_npc_ship("militia_patrol"), ctx.player.pos) is None


def test_broadcasting_hulls_keep_the_normal_hail_path(monkeypatch):
    """Scrubbed and live broadcasts never trigger the challenge —
    blank paper complies; the electronic hail path is unchanged."""
    from src.spacehack import navigation_combat as nc

    challenged = []
    monkeypatch.setattr(
        "src.spacehack.comms.open_challenge_direct",
        lambda _ctx, _e: challenged.append(_e) or None,
    )
    hailed = []
    monkeypatch.setattr(nc, "_spec_distance_hail", lambda *_a: hailed.append(_a) or None)

    scrubbed = _space_ctx()
    scrubbed.collected_ids = [{
        "id": "KX-1234", "kind": "scrubbed",
        "label": "Scrubbed hull", "faction": None,
    }]
    scrubbed.broadcast_identity = scrubbed.collected_ids[0]
    patrol = _patrol()
    nc._auto_hail_entity(scrubbed, "sol", patrol, scrubbed.player.pos, object())
    assert challenged == [], "a broadcasting hull is not challenged"
    assert hailed, "the normal electronic hail path still runs"

    live = _space_ctx()
    nc._auto_hail_entity(live, "sol", patrol, live.player.pos, object())
    assert challenged == []


def test_identification_judgement_per_broadcast_face():
    """The moment of truth, pure: blank paper passes; a militia
    registration outranks the reader; a wrong face gets that face's
    trouble; the true record gets its due."""
    from src.spacehack.comms import _judge_identification

    ctx = quest_ctx()
    ctx.faction_reputation = {"militia": 0}
    assert _judge_identification(ctx, None)[0] is True
    scrub = {"id": "KX-1234", "kind": "scrubbed", "faction": None}
    assert _judge_identification(ctx, scrub)[0] is True
    mil = {"id": "ML-2231", "kind": "fabricated", "faction": "militia"}
    assert _judge_identification(ctx, mil)[0] is True
    pirate = {"id": "KG-8812", "kind": "cloned", "faction": "pirate"}
    assert _judge_identification(ctx, pirate)[0] is False

    ctx.faction_reputation = {"militia": -80}
    assert _judge_identification(ctx, None)[0] is False  # the record's due


def test_identify_ends_dark_and_failure_escalates(monkeypatch):
    """Identifying brings the transponder up broadcasting the answer —
    and the answer is what gets judged: a pass waves you through, a
    fail (and refusing to answer) draws the patrol's fire."""
    from src.spacehack import comms
    from src.spacehack.data.npc_ships import find_npc_ship

    scrub = {"id": "KX-1234", "kind": "scrubbed",
             "label": "Scrubbed hull", "faction": None}
    pirate = {"id": "KG-8812", "kind": "cloned",
              "label": "Warlord face", "faction": "pirate"}
    spec = find_npc_ship("militia_patrol")
    patrol = _patrol()

    ctx = quest_ctx()
    ctx.faction_reputation = {"militia": 10}
    ctx.broadcast_dark = True
    ctx.broadcast_identity = None
    ctx.collected_ids = [dict(scrub)]
    assert comms.resolve_identification(ctx, scrub) is True
    assert ctx.broadcast_dark is False
    assert ctx.broadcast_identity["id"] == "KX-1234"

    # A worn pirate face fails the challenge: the patrol opens fire
    # and its whole squad joins.
    fail_ctx = quest_ctx()
    fail_ctx.faction_reputation = {"militia": 10}
    fail_ctx.broadcast_dark = True
    fail_ctx.collected_ids = [dict(pirate)]
    monkeypatch.setattr(
        comms, "_identify_face_result", lambda _ctx: ("face", dict(pirate)),
    )
    payload = comms._handle_challenge(
        fail_ctx, comms._InteractionOutcome.IDENTIFY,
        "Militia Patrol", spec, patrol,
    )
    assert payload is not None
    assert fail_ctx.broadcast_identity["faction"] == "pirate"
    assert fail_ctx.broadcast_dark is False

    # Refusing to answer (BACK) is an answer too — no run.
    back_ctx = quest_ctx()
    back_ctx.faction_reputation = {"militia": 10}
    back_ctx.broadcast_dark = True
    payload = comms._handle_challenge(
        back_ctx, comms._InteractionOutcome.BACK,
        "Militia Patrol", spec, patrol,
    )
    assert payload is not None
    assert back_ctx.broadcast_dark is True  # never answered, still dark


def test_identify_choice_without_a_library_never_opens_a_modal():
    """No collected IDs: the only answer to a challenge is yourself —
    the face-choice modal never runs."""
    from src.spacehack import comms

    ctx = quest_ctx()
    ctx.collected_ids = []
    assert comms._identify_choice(ctx) == ("true", None)


def test_challenge_attack_reuses_the_escalation_and_the_mask():
    """ATTACK on the challenge escalates through the normal comms
    path — and while dark the unprovoked-attack rep deltas route
    nowhere (the mask cuts both ways)."""
    from src.spacehack import comms
    from src.spacehack.data.npc_ships import find_npc_ship

    spec = find_npc_ship("militia_patrol")
    ctx = quest_ctx()
    ctx.faction_reputation = {"militia": 10, "merchant": 5}
    ctx.broadcast_dark = True

    payload = comms._handle_challenge(
        ctx, comms._InteractionOutcome.ATTACK,
        "Militia Patrol", spec, _patrol(),
    )
    assert payload is not None
    assert ctx.faction_reputation == {"militia": 10, "merchant": 5}
