"""The transponder / ID layer (doc 40, phase 1).

An ID is an identifier that maps to relations; the game lived in
live mode since day one. Phase 1 covers the state model (live /
dark / spoofed, the worn-face library), persistence + existing-save
migration, the broadcast write rule (live moves ID 1, a worn ID
builds its own record, dark records nothing), and the identity hub.
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


def test_rep_writes_follow_the_broadcast():
    """doc 40 re-cut: rep writes follow the broadcast — live moves ID
    1's sheet, spoofed moves the WORN ID's sheet (a fake builds its
    own record), dark records nothing (crimes unsolved)."""
    from src.spacehack.faction import modify_rep

    ctx = quest_ctx()
    ctx.faction_reputation = {"militia": 10}
    ctx.collected_ids = [dict(_scrub_entry())]
    ctx.broadcast_identity = dict(ctx.collected_ids[0])

    modify_rep(ctx, "militia", 5)  # wearing the scrub: ITS sheet moves
    assert ctx.collected_ids[0]["rep"]["militia"] == 5
    assert ctx.faction_reputation["militia"] == 10  # ID 1 untouched
    assert any("Scrubbed hull" in m.text for m in ctx.log._messages)

    ctx.broadcast_dark = True
    modify_rep(ctx, "militia", -5)  # a crime, unseen
    assert ctx.faction_reputation["militia"] == 10
    assert ctx.collected_ids[0]["rep"]["militia"] == 5

    ctx.broadcast_dark = False
    ctx.broadcast_identity = None  # live again: rep flows to ID 1
    modify_rep(ctx, "militia", 5)
    assert ctx.faction_reputation["militia"] == 15
    assert ctx.collected_ids[0]["rep"]["militia"] == 5


def test_monthly_decay_ignores_the_broadcast_state():
    """Decay is time, not action — it always ages ID 1's sheet."""
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
    hot_scrub = _scrub_entry(rep={"merchant": -40})
    data = {
        "ship_registration": "AB-1234",
        "broadcast_dark": True,
        "broadcast_identity": _pirate_face(),
        "collected_ids": [_pirate_face(), hot_scrub],
        "transponder_cutout": True,
    }
    _restore_quest_and_tutorial(ctx, data)
    assert ctx.ship_registration == "AB-1234"
    assert ctx.broadcast_dark is True
    assert ctx.broadcast_identity["id"] == "KG-8812"
    assert ctx.collected_ids[1]["rep"] == {"merchant": -40}, \
        "a hot ID's sheet round-trips"
    assert ctx.transponder_cutout is True

    legacy = quest_ctx()
    _restore_quest_and_tutorial(legacy, {})
    assert legacy.ship_registration, "legacy saves gain a registration"
    assert legacy.broadcast_dark is False


def test_load_invariant_no_cutout_never_loads_dark():
    """Doc 40 phase 5: a save without a cut-out never loads dark — a
    legacy dark save restores live and says so; cut-out + dark stays
    dark (covered round-trip above)."""
    from src.spacehack.saveload import _restore_quest_and_tutorial

    stranded = quest_ctx()
    _restore_quest_and_tutorial(stranded, {"broadcast_dark": True})
    assert stranded.broadcast_dark is False, "no cut-out ⇒ never dark"
    assert stranded.log.recent()[-1].text == \
        "No cut-out installed - transponder restored to live."

    live = quest_ctx()
    _restore_quest_and_tutorial(live, {})
    assert live.broadcast_dark is False
    assert not any("transponder" in e.text for e in live.log.recent()), \
        "the invariant line only fires when it resets a dark save"


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


def test_faction_rows_resolve_through_the_broadcast():
    """The F screen renders the broadcasting ID's actual sheet (doc 40
    phase 4 — no more approximation rows): the worn ID's values while
    spoofed, all-neutral while dark, the true ratings while live. A
    scrub (all-zero sheet) shows Neutral everywhere."""
    from src.spacehack.pygame_faction import frame_for

    ctx = quest_ctx()
    ctx.faction_reputation = {"pirate": -80, "merchant": 40}
    ctx.collected_ids = [dict(_scrub_entry())]
    ctx.broadcast_identity = dict(ctx.collected_ids[0])

    rows = {r.label: r for r in frame_for(ctx).rows}
    assert all(r.attitude == "Neutral" and r.reputation == 0
               for r in rows.values())

    pirate = _pirate_face()
    pirate["rep"] = {"pirate": 76, "merchant": -40}
    from src.spacehack.identity import collect_id
    collect_id(ctx, pirate)
    ctx.broadcast_identity = dict(pirate)

    rows = {r.label: r for r in frame_for(ctx).rows}
    assert rows["Pirate"].attitude == "Allied"      # the clone's sheet
    assert rows["Merchant"].attitude == "Disliked"  # rides the same sheet
    assert rows["Militia"].attitude == "Neutral"    # absent keys read zero

    ctx.broadcast_dark = True  # nothing resolves — all neutral
    rows = {r.label: r for r in frame_for(ctx).rows}
    assert all(r.attitude == "Neutral" and r.reputation == 0
               for r in rows.values())

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
    """The moment of truth, pure: the answered ID's own sheet decides
    (doc 40 re-cut) — zeros pass, a friendly militia sheet passes, a
    hostile sheet draws fire whatever hull it rides; the true record
    gets its due."""
    from src.spacehack.comms import _judge_identification

    ctx = quest_ctx()
    ctx.faction_reputation = {"militia": 0}
    assert _judge_identification(ctx, None)[0] is True
    assert _judge_identification(ctx, _scrub_entry())[0] is True  # zeros
    mil = {"id": "ML-2231", "kind": "fabricated", "rep": {"militia": 60}}
    assert _judge_identification(ctx, mil)[0] is True
    pirate = {"id": "KG-8812", "kind": "cloned",
              "rep": {"pirate": 76, "militia": -80}}
    assert _judge_identification(ctx, pirate)[0] is False

    # A clone whose roll left militia NEUTRAL passes — the value read,
    # not the name (phase 6's roll profiles own this case).
    lucky = {"id": "KG-9999", "kind": "cloned", "rep": {"militia": 0}}
    assert _judge_identification(ctx, lucky)[0] is True

    ctx.faction_reputation = {"militia": -80}
    assert _judge_identification(ctx, None)[0] is False  # the record's due


def test_pass_lines_are_consistent():
    """Every pass reads the same line — no mechanic lectures (user
    playtest ruling); only the failures name what resolved."""
    from src.spacehack.comms import _judge_identification

    ctx = quest_ctx()
    ctx.faction_reputation = {"militia": 0}
    mil = {"id": "ML-2231", "kind": "fabricated", "rep": {"militia": 60}}
    lines = {
        _judge_identification(ctx, None)[1],
        _judge_identification(ctx, _scrub_entry())[1],
        _judge_identification(ctx, mil)[1],
    }
    assert len(lines) == 1
    assert lines.pop() == "The patrol checks your registration and waves you through."

    pirate = {"id": "KG-8812", "kind": "cloned", "rep": {"militia": -80}}
    assert _judge_identification(ctx, pirate)[1] == (
        "The registration reads hostile: the patrol opens fire!")
    ctx.faction_reputation = {"militia": -80}
    assert _judge_identification(ctx, None)[1] == (
        "The registration reads hostile: the patrol opens fire!")


def test_challenge_body_uses_challenge_lines_not_comms_lines():
    """The challenge modal never shows the cargo-inspection text (user
    playtest bug): authored per militia ship, generic demand as the
    fallback."""
    from src.spacehack.comms import _challenge_body_lines
    from src.spacehack.data.npc_ships import find_npc_ship

    for _pid in (
        "militia_blockade", "militia_patrol_light",
        "militia_patrol", "militia_patrol_heavy",
    ):
        _spec = find_npc_ship(_pid)
        _body = "\n".join(_challenge_body_lines(_spec))
        assert "cargo" not in _body.lower(), _pid
        assert "identify" in _body.lower(), _pid
        assert _body != "\n".join(_spec.comms_lines), _pid

    generic = _challenge_body_lines(object())
    assert generic == (
        "Contact: your transponder is dark. Identify yourself or we open fire.",
    )


def test_identify_ends_dark_and_failure_escalates(monkeypatch):
    """Identifying brings the transponder up broadcasting the answer —
    and the answer is what gets judged: a pass waves you through, a
    fail (and refusing to answer) draws the patrol's fire."""
    from src.spacehack import comms
    from src.spacehack.data.npc_ships import find_npc_ship

    scrub = {"id": "KX-1234", "kind": "scrubbed",
             "label": "Scrubbed hull", "faction": None}
    pirate = {"id": "KG-8812", "kind": "cloned",
              "label": "Warlord face", "faction": "pirate",
              "rep": {"pirate": 76, "militia": -80}}
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


# --- Phase 4: the broadcasting ID's reputation sheet -----------------------


def _scrub_entry(id_="KX-1234", rep=None):
    face = {"id": id_, "kind": "scrubbed",
            "label": "Scrubbed hull", "faction": None}
    if rep is not None:
        face["rep"] = rep
    return face


def test_effective_reputation_resolves_the_broadcasting_sheet():
    """One resolver, one read: live → the true dict's copy; spoofed →
    the worn entry's own sheet; dark → nothing resolves."""
    from src.spacehack import identity

    ctx = quest_ctx()
    ctx.faction_reputation = {"militia": 40, "pirate": -80}
    sheet = identity.effective_reputation(ctx)
    assert sheet == {"militia": 40, "pirate": -80}
    sheet["militia"] = 0  # fresh dict: callers can't touch the true sheet
    assert ctx.faction_reputation["militia"] == 40

    identity.collect_id(ctx, _scrub_entry(rep={"militia": 60, "pirate": -100}))
    identity.cycle_identity(ctx)
    assert identity.effective_reputation(ctx) == {"militia": 60, "pirate": -100}

    # An entry without a rep field (legacy shape) reads all-neutral.
    identity.collect_id(ctx, _scrub_entry("YY-5678"))
    identity.cycle_identity(ctx)
    assert identity.effective_reputation(ctx) == {}

    ctx.broadcast_dark = True  # dark is the master switch: nothing resolves
    assert identity.effective_reputation(ctx) == {}

    # A worn id missing from the library resolves nothing either.
    ctx.broadcast_dark = False
    ctx.broadcast_identity = {"id": "NOPE-000", "label": "ghost"}
    assert identity.effective_reputation(ctx) == {}


def test_scrub_purchase_materializes_a_literal_zero_sheet():
    """A scrubbed ID IS an ID with 0's across the board (user ruling):
    the sheet is written at purchase, not implied by absence."""
    from src.spacehack.faction import _ALL_FACTIONS
    from src.spacehack.identity import buy_scrubbed_id

    ctx = quest_ctx(credits=8_000)
    assert buy_scrubbed_id(ctx, "deadfall_scrubber")
    sheet = ctx.collected_ids[0]["rep"]
    assert sheet == {faction: 0 for faction in _ALL_FACTIONS}
    assert len(sheet) == len(_ALL_FACTIONS) > 0


def _blockade_system():
    """A system with one static militia-blockade spawn at (150, 55)."""
    from types import SimpleNamespace
    from src.spacehack import world

    spawn = SimpleNamespace(
        enemy_id="militia_blockade",
        pos=world.Position(150, 55),
        squad_id="luyt_blockade_picket",
    )
    return SimpleNamespace(id="luyten", enemies=(spawn,))


def _occupied_ctx(faction_reputation):
    """ctx whose map holds one live entity on the spawn's cell."""
    from types import SimpleNamespace
    from src.spacehack import world

    ctx = quest_ctx()
    ctx.faction_reputation = dict(faction_reputation)
    ctx.game_map = SimpleNamespace(entities=(
        world.Entity("M", (100, 200, 255), world.Position(150, 55),
                     npc_ship_id="militia_blockade"),
    ))
    return ctx


def test_gate_engages_truth_table_and_heat_bypass():
    """_gate_engages: engage only on resolved disliked/enemy; charged-
    cell heat bypasses the mask — a heat response, not an identity
    read — so even a blank sheet engages under heat."""
    from src.spacehack import navigation_combat as nc

    assert nc._gate_engages({"militia": 0}, "militia", False) is False
    assert nc._gate_engages({"militia": 50}, "militia", False) is False
    assert nc._gate_engages({"militia": -80}, "militia", False) is True
    assert nc._gate_engages({}, "militia", False) is False
    assert nc._gate_engages({}, "militia", True) is True
    assert nc._gate_engages({"militia": 90}, "militia", True) is True


def test_charged_cell_heat_aggros_through_any_face(monkeypatch):
    """The brief's required case: under charged-cell heat a militia
    static engages through any broadcast — liked, scrubbed, or dark."""
    from src.spacehack import navigation_combat as nc
    from src.spacehack import world

    monkeypatch.setattr(
        nc.main_quest_module, "charged_cell_in_sol", lambda _ctx, _sid: True,
    )
    player = world.Position(151, 55)
    alive = []

    ctx = _occupied_ctx({"militia": 50})  # liked live: heat still aggros
    squads, _ = nc._trigger_static_spawns(
        ctx, player, _blockade_system(), alive)
    assert squads == {"luyt_blockade_picket"}

    ctx = _occupied_ctx({"militia": 50})
    ctx.broadcast_dark = True  # dark changes nothing: heat ignores it
    assert nc._trigger_static_spawns(
        ctx, player, _blockade_system(), alive,
    ) == ({"luyt_blockade_picket"}, set())


def test_static_spawns_gate_on_the_resolved_sheet():
    """Static spawns gate uniformly (user ruling, no exceptions): a
    militia-LIKED live hull sails past the Luyten blockade; hostile
    standing engages; a worn scrub (zeros) and dark stand down."""
    from src.spacehack import identity
    from src.spacehack import navigation_combat as nc
    from src.spacehack import world

    player = world.Position(151, 55)  # inside detect_radius 7
    alive = []

    # Default character: militia +50 (liked) — the blockade stands down.
    ctx = _occupied_ctx({"militia": 50})
    assert nc._trigger_static_spawns(ctx, player, _blockade_system(), alive) == (
        set(), set(),
    )

    # Hostile true record: it engages the whole squad.
    ctx = _occupied_ctx({"militia": -80})
    squads, _solo = nc._trigger_static_spawns(
        ctx, player, _blockade_system(), alive)
    assert squads == {"luyt_blockade_picket"}

    # Wearing a scrub: zeros resolve neutral — stand down.
    ctx = _occupied_ctx({"militia": -80})
    ctx.collected_ids = [dict(_scrub_entry())]
    ctx.broadcast_identity = dict(ctx.collected_ids[0])
    assert nc._trigger_static_spawns(ctx, player, _blockade_system(), alive) == (
        set(), set(),
    )

    # Dark: nothing resolves — stand down (the challenge hail is the
    # eyes exception, not the spawn gate).
    ctx = _occupied_ctx({"militia": -80})
    ctx.broadcast_dark = True
    assert nc._trigger_static_spawns(ctx, player, _blockade_system(), alive) == (
        set(), set(),
    )
    assert identity.broadcast_mode(ctx) == identity.DARK


def test_readers_resolve_the_sheet_space_and_ground():
    """Every reader resolves the broadcasting ID's sheet (doc 40): the
    scan chance, trade attitudes, mission-board pay, and ground
    hostility read the SAME sheet — on foot as under the stars."""
    from types import SimpleNamespace

    from src.spacehack import navigation_combat as nc
    from src.spacehack import trade
    from src.spacehack.faction import spec_is_hostile
    from src.spacehack.mission._board import _faction_pay_pct

    # A hot scrub: merchants distrust this ID; militia is fine with it.
    # (The true record is the reverse — liked merchants, near-neutral
    # militia.)
    ctx = quest_ctx()
    ctx.faction_reputation = {"merchant": 40, "militia": 10}
    ctx.collected_ids = [dict(_scrub_entry(rep={"merchant": -40}))]
    ctx.broadcast_identity = dict(ctx.collected_ids[0])

    assert nc._militia_scan_chance(ctx) == 0.40  # sheet-neutral militia
    assert trade._merchant_attitude(ctx) == "disliked"
    assert _faction_pay_pct(ctx, "merchants") == -15

    merchant = SimpleNamespace(faction="merchant", always_hostile=False)
    militia = SimpleNamespace(faction="militia", always_hostile=False)
    assert spec_is_hostile(ctx, merchant) is True   # hates the scrub
    assert spec_is_hostile(ctx, militia) is False   # neutral to it

    ctx.broadcast_identity = None  # live: the true record returns
    assert trade._merchant_attitude(ctx) == "liked"
    assert _faction_pay_pct(ctx, "merchants") == 10
    assert spec_is_hostile(ctx, merchant) is False


def test_contact_options_read_the_sheet():
    """Comms rows resolve the broadcasting ID's sheet (doc 40): a
    merchant contact offers Open Trade to a liked hull but not to a
    scrub the merchants distrust."""
    from types import SimpleNamespace

    from src.spacehack import comms

    merchant = SimpleNamespace(
        faction="merchant", is_boardable=False, id="trader")
    ctx = quest_ctx()
    ctx.faction_reputation = {"merchant": 40}
    assert "Open Trade" in comms._contact_options(ctx, merchant)

    ctx.collected_ids = [dict(_scrub_entry(rep={"merchant": -40}))]
    ctx.broadcast_identity = dict(ctx.collected_ids[0])
    assert "Open Trade" not in comms._contact_options(ctx, merchant)
