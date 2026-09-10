"""The Line (doc 41, phase 1): sweep resolver, crossing edge, checkpoint.

Covers the sweep table per row, the crossing-edge tripwire (fires
exactly once per crossing, both directions, zero-state stamping),
service-run consumption, the dark path's column scoping, Defy's
interdiction flag at the spawn gate, the GO TO break, and the
luyten_star column data's consistency.
"""

from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pytest

from support.quest_ctx import quest_ctx

from src.spacehack import navigation_line
from src.spacehack import solar_system as solar_system_module
from src.spacehack import world
from src.spacehack.data.solar_systems import find_solar_system
from src.spacehack.data.solar_systems.luyten_star import SYSTEM as LUYTEN
from src.spacehack.navigation_travel import GotoOutcome


@pytest.fixture(autouse=True)
def _fresh_line_state():
    """Every test starts and ends with pristine Line session state."""
    navigation_line.reset_session()
    yield
    navigation_line.reset_session()


@pytest.fixture
def line_system(monkeypatch):
    """The real Luyten system as ``current_system``."""
    monkeypatch.setattr(solar_system_module, "current_system", lambda: LUYTEN)
    return LUYTEN


def _comply(monkeypatch):
    monkeypatch.setattr(
        "src.spacehack.comms._pygame_interaction_outcome",
        lambda *_a, **_k: navigation_line._Checkpoint.COMPLY,
    )


def _defy(monkeypatch):
    monkeypatch.setattr(
        "src.spacehack.comms._pygame_interaction_outcome",
        lambda *_a, **_k: navigation_line._Checkpoint.DEFY,
    )


def _hails(monkeypatch):
    """Record every Line-modal opening instead of running it; the
    reply scripts as COMPLY (challenge) by default."""
    calls: list = []
    monkeypatch.setattr(
        "src.spacehack.comms._pygame_interaction_outcome",
        lambda *_a, **_k: calls.append(1) or navigation_line._Checkpoint.COMPLY,
    )
    return calls


def _modals(monkeypatch, reply):
    """Capture every Line modal's body lines; reply with ``reply``."""
    opened: list = []
    monkeypatch.setattr(
        "src.spacehack.comms._pygame_interaction_outcome",
        lambda _c, _n, _s, _o, contact_entity=None, dispatch=None,
        title=None, lines=None, esc_label=None: opened.append(lines) or reply,
    )
    return opened


def _log_text(ctx) -> str:
    return "\n".join(m.text for m in ctx.log._messages)


def _picket_entities(system, *, kind="thin"):
    """Alive picket entities at ``kind``'s roster stations, stamped
    with their spawn keys (the stamp happens at map build). Default
    thin = the shipped four posts, matching the pre-watch line."""
    from src.spacehack.solar_system import static_spawn_key
    column = getattr(system, "sensor_column", None)
    if column is not None and navigation_line.watch_active(column):
        roster_ys = {s.y for s in navigation_line.roster_for(column, kind)}
    else:
        roster_ys = None  # no watchbill: every row is a standing picket
    return [
        world.Entity("M", (100, 200, 255), _spawn.pos,
                     npc_ship_id=_spawn.enemy_id,
                     static_spawn_key=static_spawn_key(system, _spawn))
        for _spawn in system.enemies
        if roster_ys is None or _spawn.pos.y in roster_ys
    ]


# ---------------------------------------------------------------------------
# The pure sweep table (doc 41 rules table, one test per row)
# ---------------------------------------------------------------------------

def test_resolve_sweep_papers_wave():
    verdict = navigation_line.resolve_sweep(
        dark=False, manifest=True, face_militia_rep=None,
        service=False, rank_rep=80,
    )
    assert verdict is navigation_line.SweepVerdict.PAPERS


def test_resolve_sweep_rank_wave_needs_a_worn_face_at_rank():
    verdict = navigation_line.resolve_sweep(
        dark=False, manifest=False, face_militia_rep=100,
        service=False, rank_rep=80,
    )
    assert verdict is navigation_line.SweepVerdict.RANK
    at_threshold = navigation_line.resolve_sweep(
        dark=False, manifest=False, face_militia_rep=80,
        service=False, rank_rep=80,
    )
    assert at_threshold is navigation_line.SweepVerdict.RANK, (
        "blockade rank is inclusive (>=)"
    )
    below = navigation_line.resolve_sweep(
        dark=False, manifest=False, face_militia_rep=79,
        service=False, rank_rep=80,
    )
    assert below is navigation_line.SweepVerdict.CHALLENGE


def test_resolve_sweep_live_standing_never_ranks():
    """Ruling 8: allied stance with no papers turns back — the true
    hull's own standing is never a face, so face_militia_rep is None."""
    verdict = navigation_line.resolve_sweep(
        dark=False, manifest=False, face_militia_rep=None,
        service=False, rank_rep=80,
    )
    assert verdict is navigation_line.SweepVerdict.CHALLENGE


def test_resolve_sweep_service_wave():
    verdict = navigation_line.resolve_sweep(
        dark=False, manifest=False, face_militia_rep=None,
        service=True, rank_rep=80,
    )
    assert verdict is navigation_line.SweepVerdict.SERVICE


def test_resolve_sweep_dark_blind_even_with_papers():
    verdict = navigation_line.resolve_sweep(
        dark=True, manifest=True, face_militia_rep=None,
        service=True, rank_rep=80,
    )
    assert verdict is navigation_line.SweepVerdict.BLIND


def test_resolve_sweep_precedence_papers_then_rank_then_service():
    """The table reads top-down: manifest beats rank beats service."""
    top = navigation_line.resolve_sweep(
        dark=False, manifest=True, face_militia_rep=100,
        service=True, rank_rep=80,
    )
    assert top is navigation_line.SweepVerdict.PAPERS
    mid = navigation_line.resolve_sweep(
        dark=False, manifest=False, face_militia_rep=100,
        service=True, rank_rep=80,
    )
    assert mid is navigation_line.SweepVerdict.RANK


def test_worn_face_militia_rep_reads_faces_only():
    """LIVE resolves no face (ruling 8); a worn spoofed face does."""
    live = quest_ctx(faction_reputation={"militia": 100})
    assert navigation_line._worn_face_militia_rep(live) is None

    face = {"id": "MIL-0001", "kind": "cloned", "label": "Militia ally",
            "faction": "militia", "rep": {"militia": 100}}
    spoofed = quest_ctx(collected_ids=[face], broadcast_identity=face)
    assert navigation_line._worn_face_militia_rep(spoofed) == 100


# ---------------------------------------------------------------------------
# The crossing edge (positional + symmetric — ruling 5)
# ---------------------------------------------------------------------------

def test_crossing_hails_once_eastbound_and_not_again_past_column(line_system, monkeypatch):
    calls = _hails(monkeypatch)
    ctx = quest_ctx(game_map=SimpleNamespace(entities=_picket_entities(LUYTEN)))

    assert navigation_line.check_crossing(ctx, world.Position(149, 70)) is None
    result = navigation_line.check_crossing(ctx, world.Position(150, 70))
    assert result is not None and result[0] is True
    assert navigation_line.check_crossing(ctx, world.Position(151, 70)) is None
    assert navigation_line.check_crossing(ctx, world.Position(160, 70)) is None
    assert len(calls) == 1, "the hail fires exactly once per crossing"


def test_crossing_hails_the_first_westbound_return(line_system, monkeypatch):
    calls = _hails(monkeypatch)
    ctx = quest_ctx(game_map=SimpleNamespace(entities=_picket_entities(LUYTEN)))

    navigation_line.check_crossing(ctx, world.Position(180, 70))
    assert navigation_line.check_crossing(ctx, world.Position(151, 70)) is None
    result = navigation_line.check_crossing(ctx, world.Position(150, 70))
    assert result is not None and result[0] is True
    # Leaving the column is free — the westbound hull continues home
    # without a second hail.
    assert navigation_line.check_crossing(ctx, world.Position(149, 70)) is None
    assert len(calls) == 1


def test_tripwire_zero_state_stamps_on_first_step(line_system, monkeypatch):
    """After load (fresh session state) the first step stamps the
    side: no re-hail, and the next ACTUAL entry fires once."""
    calls = _hails(monkeypatch)
    ctx = quest_ctx(game_map=SimpleNamespace(entities=_picket_entities(LUYTEN)))

    assert navigation_line.check_crossing(ctx, world.Position(180, 70)) is None
    assert calls == []
    result = navigation_line.check_crossing(ctx, world.Position(150, 70))
    assert result is not None
    assert len(calls) == 1, "the first entry onto the column after load hails"


def test_leaving_the_line_system_resets_the_tracker(monkeypatch):
    """A stale prev-x from the Line's system must not read as a
    crossing after re-entry (the tracker re-stamps)."""
    sol = SimpleNamespace(id="sol", sensor_column=None)
    ctx = quest_ctx(game_map=SimpleNamespace(entities=_picket_entities(LUYTEN)))
    calls = _hails(monkeypatch)

    monkeypatch.setattr(solar_system_module, "current_system", lambda: LUYTEN)
    navigation_line.check_crossing(ctx, world.Position(149, 70))
    monkeypatch.setattr(solar_system_module, "current_system", lambda: sol)
    navigation_line.check_crossing(ctx, world.Position(100, 70))
    monkeypatch.setattr(solar_system_module, "current_system", lambda: LUYTEN)
    assert navigation_line.check_crossing(ctx, world.Position(140, 70)) is None
    result = navigation_line.check_crossing(ctx, world.Position(150, 70))
    assert result is not None
    assert len(calls) == 1, "re-entry stamps, then the first entry hails"


# ---------------------------------------------------------------------------
# The waves (papers / rank / service) and the dark path
# ---------------------------------------------------------------------------

def test_papers_wave_opens_all_clear_comms_and_persists(line_system, monkeypatch):
    opened = _modals(monkeypatch, navigation_line._Checkpoint.ACK)
    ctx = quest_ctx(player_traits=["blockade_manifest"],
                    ship_registration="SC-4471",
                    game_map=SimpleNamespace(entities=_picket_entities(LUYTEN)))

    navigation_line.check_crossing(ctx, world.Position(149, 70))
    result = navigation_line.check_crossing(ctx, world.Position(150, 70))

    assert result == (False, None), "a wave lets the hull through"
    assert len(opened) == 1
    assert "SC-4471" in opened[0][0] and "checks out" in opened[0][0]
    assert "blockade_manifest" in ctx.player_traits
    assert "waves you through" in _log_text(ctx)


def test_service_run_wave_consumes_the_trait(line_system, monkeypatch):
    """One crossing per 100k: the contract is spent at the ack (doc
    39/41 ruling 7). The next crossing — here the westbound
    turn-back — challenges again."""
    calls = _hails(monkeypatch)
    ctx = quest_ctx(player_traits=["blockade_service_run"],
                    ship_registration="SC-4471",
                    game_map=SimpleNamespace(entities=_picket_entities(LUYTEN)))

    navigation_line.check_crossing(ctx, world.Position(149, 70))
    assert navigation_line.check_crossing(ctx, world.Position(150, 70)) == (False, None)
    assert "blockade_service_run" not in ctx.player_traits
    assert "service-run contract is spent" in _log_text(ctx)

    navigation_line.check_crossing(ctx, world.Position(149, 70))  # free retreat
    result = navigation_line.check_crossing(ctx, world.Position(150, 70))
    assert result is not None and result[0] is True
    assert len(calls) == 2, "wave comms + the post-consumption challenge"


def test_rank_wave_addresses_the_worn_face(line_system, monkeypatch):
    """Impersonation: the worn face at blockade rank is waved and the
    comms address THAT ID."""
    opened = _modals(monkeypatch, navigation_line._Checkpoint.ACK)
    face = {"id": "MIL-0001", "kind": "cloned", "label": "Militia ally",
            "faction": "militia", "rep": {"militia": 100}}
    ctx = quest_ctx(collected_ids=[face], broadcast_identity=face,
                    ship_registration="SC-4471",
                    game_map=SimpleNamespace(entities=_picket_entities(LUYTEN)))

    navigation_line.check_crossing(ctx, world.Position(149, 70))
    result = navigation_line.check_crossing(ctx, world.Position(150, 70))

    assert result == (False, None)
    assert "MIL-0001" in opened[0][0], "the wave addresses the worn face"
    assert "SC-4471" not in opened[0][0]


def test_challenge_addresses_the_broadcast_id(line_system, monkeypatch):
    """User wording (2026-09-09): the hail opens with the hull's
    broadcast registration."""
    opened = _modals(monkeypatch, navigation_line._Checkpoint.COMPLY)
    ctx = quest_ctx(ship_registration="SC-4471",
                    game_map=SimpleNamespace(entities=_picket_entities(LUYTEN)))

    navigation_line.check_crossing(ctx, world.Position(149, 70))
    navigation_line.check_crossing(ctx, world.Position(150, 70))

    assert "SC-4471, this is forbidden space." in opened[0][0]
    assert "not on our list" in opened[0][0]


def test_dark_checkpoint_addresses_unidentified_hull(line_system, monkeypatch):
    """A dark hull is never swept — but a picket's physical spot opens
    the same checkpoint, addressed 'Unidentified hull'."""
    opened = _modals(monkeypatch, navigation_line._Checkpoint.DEFY)
    ctx = quest_ctx(broadcast_dark=True, ship_registration="SC-4471",
                    game_map=SimpleNamespace(
                        entities=_picket_entities(LUYTEN)))

    result = navigation_line.line_dark_hail(ctx, ctx.game_map.entities[0])

    assert result is not None
    assert opened[0][0].startswith("Unidentified hull, this is forbidden space.")


def test_dark_hull_is_never_swept(line_system, monkeypatch):
    """Ruling 1: the sweep cannot see dark hulls — no hail on the
    crossing; only physical spotting (the auto-hail pass) opens it."""
    calls = _hails(monkeypatch)
    ctx = quest_ctx(broadcast_dark=True, game_map=SimpleNamespace(entities=_picket_entities(LUYTEN)))

    navigation_line.check_crossing(ctx, world.Position(149, 70))
    assert navigation_line.check_crossing(ctx, world.Position(150, 70)) is None
    assert calls == []


def test_column_supersedes_the_doc39_warning(line_system, monkeypatch):
    """One hail shape at the Line (ruling 3): the doc-39 warning-only
    comms never fire in a column system — the checkpoint is the only
    hail, waved hulls included."""
    from src.spacehack import navigation_combat as nc

    opened: list = []
    monkeypatch.setattr(
        "src.spacehack.comms.open_comms_direct",
        lambda _ctx, _e: opened.append(_e) or None,
    )
    ctx = quest_ctx(militia_scanned=set(),
                    game_map=SimpleNamespace(entities=_picket_entities(LUYTEN)))
    picket = ctx.game_map.entities[0]

    result = nc._auto_hail_entity(
        ctx, "luyten_star", picket, world.Position(149, 55), LUYTEN,
    )

    assert result is None and opened == []


def test_doc39_warning_stands_without_a_column(monkeypatch):
    """Outside column systems the blockade warning is unchanged."""
    from src.spacehack import navigation_combat as nc

    sol = SimpleNamespace(id="sol", sensor_column=None)
    monkeypatch.setattr(solar_system_module, "current_system", lambda: sol)
    monkeypatch.setattr(
        "src.spacehack.comms.open_comms_direct",
        lambda _ctx, _e: None,
    )
    ctx = quest_ctx(militia_scanned=set())
    picket = world.Entity("M", (100, 200, 255), world.Position(40, 30),
                          npc_ship_id="militia_blockade")

    result = nc._spec_distance_hail(
        ctx, "sol", picket, nc.find_npc_ship("militia_blockade"),
        world.Position(41, 30),
    )

    assert result is not None and result[0] is True
    assert nc._entity_hail_key(picket) in ctx.militia_scanned


# ---------------------------------------------------------------------------
# The checkpoint + the interdiction flag (phase-1 teeth)
# ---------------------------------------------------------------------------

def test_defy_converges_the_picket_squad_and_raises_interdiction(line_system, monkeypatch):
    _defy(monkeypatch)
    ctx = quest_ctx(
        faction_reputation={"militia": 100},  # allied — stance is irrelevant
        game_map=SimpleNamespace(entities=_picket_entities(LUYTEN)),
    )

    navigation_line.check_crossing(ctx, world.Position(149, 70))
    result = navigation_line.check_crossing(ctx, world.Position(150, 70))

    assert result is not None and result[0] is True
    specs, positions = result[1]
    assert len(specs) == 4 and len(positions) == 4
    assert navigation_line.interdiction_system() == "luyten_star"


def test_defy_payload_skips_dead_pickets(line_system, monkeypatch):
    _defy(monkeypatch)
    entities = _picket_entities(LUYTEN)[1:]  # the north picket is destroyed
    ctx = quest_ctx(game_map=SimpleNamespace(entities=entities))

    navigation_line.check_crossing(ctx, world.Position(149, 70))
    _hailed, payload = navigation_line.check_crossing(ctx, world.Position(150, 70))
    assert len(payload[0]) == 3


def test_lured_alive_picket_fights_from_its_live_position(line_system, monkeypatch):
    """Identity is the stamped spawn key, not position: a lured-but-
    alive picket is IN the payload at its live position (position
    matching would have called it dead and skipped the fight)."""
    _defy(monkeypatch)
    entities = _picket_entities(LUYTEN)
    entities[0].pos = world.Position(140, 60)  # lured off its post
    ctx = quest_ctx(game_map=SimpleNamespace(entities=entities))

    navigation_line.check_crossing(ctx, world.Position(149, 70))
    _hailed, payload = navigation_line.check_crossing(ctx, world.Position(150, 70))
    assert len(payload[0]) == 4
    assert (140, 60) in [(_p.x, _p.y) for _p in payload[1]]


def test_dead_squad_ends_the_sweep(line_system, monkeypatch):
    """Round-2 ruling: the sweep is manned — with every picket dead
    the Line is dark: no hail, no wave, no defiance. The fight
    method pays (until phase 2's next shift re-mans the column)."""
    calls = _hails(monkeypatch)
    ctx = quest_ctx(faction_reputation={"militia": 100},
                    game_map=SimpleNamespace(entities=[]))

    navigation_line.check_crossing(ctx, world.Position(149, 70))
    assert navigation_line.check_crossing(ctx, world.Position(150, 70)) is None
    assert calls == []
    assert navigation_line.interdiction_system() is None


# ---------------------------------------------------------------------------
# The static-defeat ledger (playtest round 1: dead pickets re-stamped)
# ---------------------------------------------------------------------------

def test_killed_pickets_tombstone_and_never_re_stamp(line_system, monkeypatch):
    """Playtest bug (2026-09-09): beating the blockade then reloading
    resurrected it. A static kill records a tombstone; the next map
    build skips it. The spawn key rides the entity — combat moves
    the hull (AI advance), the key does not. The watch (phase 2)
    keys per tenure: the kill holds for its tenure, the post re-mans
    at the next one."""
    from src.spacehack import solar_system as ss_module
    from src.spacehack.combat._space_kills import mark_static_spawn_defeated

    ctx = quest_ctx(defeated_static_spawns=set())
    dead = world.Entity("B", (130, 230, 220), world.Position(148, 40),
                        npc_ship_id="militia_blockade",
                        static_spawn_key="luyten_star:militia_blockade:150:25:t3")

    mark_static_spawn_defeated(ctx, dead)
    assert ctx.defeated_static_spawns == {
        "luyten_star:militia_blockade:150:25:t3",
    }

    thin_day = navigation_line.total_days(22, 1, 2200)  # run-day 22: tenure 3
    fresh = ss_module.make_solar_system(
        system=LUYTEN, skip_static_spawns=ctx.defeated_static_spawns,
        watch_day=thin_day,
    )
    keys = {_e.static_spawn_key for _e in _watch_pickets(fresh)}
    assert "luyten_star:militia_blockade:150:25:t3" not in keys, (
        "the dead picket does not re-stamp this tenure"
    )

    next_thin_day = navigation_line.total_days(50, 1, 2200)  # tenure 7
    again = ss_module.make_solar_system(
        system=LUYTEN, skip_static_spawns=ctx.defeated_static_spawns,
        watch_day=next_thin_day,
    )
    assert "luyten_star:militia_blockade:150:25:t7" in {
        _e.static_spawn_key for _e in _watch_pickets(again)
    }, "the next tenure's fresh key re-mans the post"


def test_non_static_kills_record_nothing(line_system):
    """Procedural pirates etc. respawn by design — no tombstone."""
    from src.spacehack.combat._space_kills import mark_static_spawn_defeated

    ctx = quest_ctx(defeated_static_spawns=set())
    pirate = world.Entity("p", (255, 80, 80), world.Position(60, 60),
                          npc_ship_id="pirate_scout")
    unlabeled = world.Entity("B", (130, 230, 220), world.Position(150, 25),
                             npc_ship_id="militia_blockade")  # no key stamped

    mark_static_spawn_defeated(ctx, pirate)
    mark_static_spawn_defeated(ctx, unlabeled)
    assert ctx.defeated_static_spawns == set()


def test_load_path_threads_the_ledger_into_the_build():
    """The load chain must honor the tombstones AND the watchbill:
    _build_space_map skips defeated statics and stamps the watch at
    the save's day; a luyten build without the day fails loudly."""
    from src.spacehack.saveload_maps import _build_space_map

    _log = SimpleNamespace(add=lambda _m: None)
    _day1 = navigation_line.total_days(1, 1, 2200)
    _common = ("luyten_star", _log, None, {}, {}, {}, 10, 10)

    built = _build_space_map(
        *_common, ["luyten_star:militia_blockade:150:21:t0"], watch_day=_day1,
    )
    keys = {_e.static_spawn_key for _e in _watch_pickets(built[0])}
    assert "luyten_star:militia_blockade:150:21:t0" not in keys
    assert "luyten_star:militia_blockade:150:7:t0" in keys

    with pytest.raises(ValueError, match="watch_day"):
        _build_space_map(*_common, [])


def test_interdiction_gate_bypasses_stance_for_militia_only(monkeypatch):
    """The flag reads like charged-cell aggro: LINE-scoped, militia
    only, stance-independent (ruling 8's convergence teeth)."""
    from src.spacehack import navigation_combat as nc

    ctx = quest_ctx(faction_reputation={"militia": 100})
    monkeypatch.setattr(solar_system_module, "current_system", lambda: LUYTEN)

    assert not nc._aggro_override(ctx, "luyten_star", "militia"), (
        "without the flag the doc-40 stand-down holds for liked hulls"
    )
    navigation_line._interdiction_system = "luyten_star"
    try:
        assert nc._aggro_override(ctx, "luyten_star", "militia")
        assert not nc._aggro_override(ctx, "luyten_star", "merchants")
        assert not nc._aggro_override(ctx, "sol", "militia")
    finally:
        navigation_line.reset_interdiction()


def test_interdiction_flows_through_the_static_spawn_pass(monkeypatch):
    """Adoption at the state-bearing caller: a LIKED hull inside an
    interdicted system is triggered by the static spawn pass (the
    picket squad engages); without the flag it sails past."""
    from src.spacehack import navigation_combat as nc

    ctx = quest_ctx(
        faction_reputation={"militia": 100},
        game_map=SimpleNamespace(entities=_picket_entities(LUYTEN)),
    )
    monkeypatch.setattr(solar_system_module, "current_system", lambda: LUYTEN)
    player_pos = world.Position(150, 26)  # beside the north picket

    alive: list = []
    _squads, _solos = nc._trigger_static_spawns(ctx, player_pos, LUYTEN, alive)
    assert _squads == set(), "the doc-40 stand-down holds without the flag"

    navigation_line._interdiction_system = "luyten_star"
    try:
        squads, _solos = nc._trigger_static_spawns(
            ctx, player_pos, LUYTEN, alive,
        )
        assert squads == {"luyt_blockade_picket"}
    finally:
        navigation_line.reset_interdiction()


def test_comply_turn_back_is_free_and_recross_hails(line_system, monkeypatch):
    """User playtest bug #1 (2026-09-09, round 2): retreating from a
    hail must NOT re-hail. The sweep fires on entering the column;
    leaving is free; the next entry is a new resolution."""
    calls = _hails(monkeypatch)
    ctx = quest_ctx(game_map=SimpleNamespace(entities=_picket_entities(LUYTEN)))

    navigation_line.check_crossing(ctx, world.Position(149, 70))
    assert navigation_line.check_crossing(ctx, world.Position(150, 70)) is not None
    assert navigation_line.check_crossing(ctx, world.Position(149, 70)) is None, (
        "the turn-back is never re-hailed"
    )
    assert navigation_line.check_crossing(ctx, world.Position(150, 70)) is not None
    assert len(calls) == 2, "each entry is a new resolution; retreats are free"

    # Same from the east side: comply, continue west unmolested.
    navigation_line.reset_session()
    calls.clear()
    navigation_line.check_crossing(ctx, world.Position(180, 70))
    assert navigation_line.check_crossing(ctx, world.Position(150, 70)) is not None
    assert navigation_line.check_crossing(ctx, world.Position(130, 70)) is None
    assert len(calls) == 1


def test_goto_interrupts_on_the_hail(line_system, monkeypatch):
    """The sweep hail breaks GO TO like comms warnings do."""
    ctx = quest_ctx(game_map=SimpleNamespace(entities=_picket_entities(LUYTEN)))
    ship = SimpleNamespace(pos=world.Position(149, 70))
    navigation_line.check_crossing(ctx, ship.pos)

    _comply(monkeypatch)
    ship.pos = world.Position(150, 70)
    assert navigation_travel_goto(ctx, ship) == (GotoOutcome.CANCELLED, None)

    navigation_line.reset_session()
    navigation_line.check_crossing(ctx, world.Position(149, 70))
    _defy(monkeypatch)
    ctx.game_map = SimpleNamespace(entities=_picket_entities(LUYTEN))
    ship.pos = world.Position(150, 70)
    outcome, payload = navigation_travel_goto(ctx, ship)
    assert outcome is GotoOutcome.COMBAT and payload is not None


def test_goto_continues_through_a_wave(line_system, monkeypatch):
    """A waved hull is THROUGH: the all-clear comms run, then auto-nav
    continues — no interrupt (user playtest ruling 2026-09-09)."""
    ctx = quest_ctx(player_traits=["blockade_manifest"],
                    ship_registration="SC-4471",
                    game_map=SimpleNamespace(entities=_picket_entities(LUYTEN)),
                    bounty_spawns={}, militia_scanned=set())
    ship = SimpleNamespace(pos=world.Position(149, 70))
    navigation_line.check_crossing(ctx, ship.pos)

    _modals(monkeypatch, navigation_line._Checkpoint.ACK)
    ship.pos = world.Position(150, 70)
    assert navigation_travel_goto(ctx, ship) is None


def navigation_travel_goto(ctx, ship):
    from src.spacehack.navigation_travel import _goto_step_interrupt
    return _goto_step_interrupt(ctx, ship)


def test_run_combat_loop_hail_owns_the_step(line_system, monkeypatch):
    """A hailed step skips the comms-warning pass; Defy's payload
    reaches combat directly."""
    from src.spacehack import game_flow

    handled: list = []
    monkeypatch.setattr(
        "src.spacehack.combat._handle_combat_encounter",
        lambda _c, _console, data: handled.append(data) or "VICTORY",
    )
    warnings: list = []
    monkeypatch.setattr(
        game_flow, "_check_auto_comms_warning",
        lambda *_a: warnings.append(1),
    )
    ctx = quest_ctx(game_map=SimpleNamespace(entities=_picket_entities(LUYTEN)))
    player = SimpleNamespace(pos=world.Position(149, 70))
    navigation_line.check_crossing(ctx, player.pos)
    _defy(monkeypatch)
    player.pos = world.Position(150, 70)

    outcome = game_flow._run_combat_loop(ctx, object(), player)

    assert outcome == "VICTORY"
    assert len(handled) == 1 and warnings == [], "hailed step skips comms"


def test_run_combat_loop_wave_falls_through(line_system, monkeypatch):
    """A waved step continues normally — both movement-pass consumers
    treat a wave as 'the hull is through' (reviewer round 2)."""
    from src.spacehack import game_flow

    opened = _modals(monkeypatch, navigation_line._Checkpoint.ACK)
    warnings: list = []
    monkeypatch.setattr(
        game_flow, "_check_auto_comms_warning",
        lambda *_a: warnings.append(1),
    )
    monkeypatch.setattr(game_flow, "_detect_combat_encounter", lambda *_a: None)
    ctx = quest_ctx(player_traits=["blockade_manifest"],
                    ship_registration="SC-4471",
                    game_map=SimpleNamespace(entities=_picket_entities(LUYTEN)),
                    militia_scanned=set())
    player = SimpleNamespace(pos=world.Position(149, 70))
    navigation_line.check_crossing(ctx, player.pos)
    player.pos = world.Position(150, 70)

    outcome = game_flow._run_combat_loop(ctx, object(), player)

    assert outcome is None
    assert len(opened) == 1 and warnings, "the wave step keeps the normal pass"


# ---------------------------------------------------------------------------
# The dark path: column-scoped amendment of the doc-40 challenge
# ---------------------------------------------------------------------------

def test_line_dark_hail_scopes_to_picket_spotters(line_system, monkeypatch):
    calls = _hails(monkeypatch)
    ctx = quest_ctx(game_map=SimpleNamespace(entities=_picket_entities(LUYTEN)))
    picket = world.Entity("M", (100, 200, 255), world.Position(150, 55),
                          npc_ship_id="militia_blockade")
    other = world.Entity("M", (100, 200, 255), world.Position(150, 55),
                         npc_ship_id="militia_patrol")

    assert navigation_line.line_dark_hail(ctx, picket) is not None
    assert navigation_line.line_dark_hail(ctx, other) is None
    assert len(calls) == 1


def test_dark_spot_outside_column_keeps_doc40_challenge(monkeypatch):
    """Regression (playtest item 10): a non-picket militia spotter
    (e.g. a Sol patrol) still opens the shipped Identify/Attack."""
    from src.spacehack import navigation_combat as nc

    sol = SimpleNamespace(id="sol", sensor_column=None)
    monkeypatch.setattr(solar_system_module, "current_system", lambda: sol)
    challenged: list = []
    monkeypatch.setattr(
        "src.spacehack.comms.open_challenge_direct",
        lambda _ctx, _e: challenged.append(_e) or None,
    )
    ctx = quest_ctx(broadcast_dark=True, militia_scanned=set())
    patrol = world.Entity("M", (100, 200, 255), world.Position(5, 6),
                          npc_ship_id="militia_patrol")

    result = nc._dark_spot_challenge(
        ctx, patrol, nc.find_npc_ship("militia_patrol"), world.Position(5, 5),
    )

    assert challenged == [patrol]
    assert result is not None and result[0] is True


def test_dark_spot_by_picket_opens_the_line_checkpoint(line_system, monkeypatch):
    from src.spacehack import navigation_combat as nc

    sentinels: list = []
    monkeypatch.setattr(
        navigation_line, "line_dark_hail",
        lambda _ctx, _e: sentinels.append(_e) or (True, None),
    )
    ctx = quest_ctx(broadcast_dark=True, militia_scanned=set())
    picket = world.Entity("M", (100, 200, 255), world.Position(150, 56),
                          npc_ship_id="militia_blockade")

    result = nc._dark_spot_challenge(
        ctx, picket, nc.find_npc_ship("militia_blockade"), world.Position(150, 55),
    )

    assert sentinels == [picket]
    assert result == (True, None)
    assert f"dark:{nc._entity_hail_key(picket)}" in ctx.militia_scanned


# ---------------------------------------------------------------------------
# Data + registry consistency
# ---------------------------------------------------------------------------

def test_luyten_column_matches_its_picket_line():
    column = LUYTEN.sensor_column
    assert column is not None
    assert column.rank_rep > 0 and column.hail_lines
    assert column.manifest_lines and column.rank_lines and column.service_lines
    # Every template carries the {id} placeholder AND formats cleanly —
    # a stray brace in future data would raise at crossing time.
    _templates = (
        *column.hail_lines, *column.manifest_lines,
        *column.rank_lines, *column.service_lines,
    )
    assert all(line.format(id="X") for line in _templates)
    for _spawn in LUYTEN.enemies:
        assert _spawn.pos.x == column.x
        assert _spawn.squad_id == column.squad_id
        assert _spawn.enemy_id == column.picket_enemy_id


def test_line_markers_are_quests_perks_outside_all_traits():
    """Doc 39's tracking ruling: the sweep's markers are never
    milestone picks; ``trait_name`` resolves them for the F-screen."""
    from src.spacehack.data.traits.core import ALL_TRAITS, QUEST_PERKS, trait_name

    all_ids = {t.id for t in ALL_TRAITS}
    for marker in (navigation_line.MANIFEST_TRAIT, navigation_line.SERVICE_TRAIT):
        assert marker in QUEST_PERKS
        assert marker not in all_ids
        assert trait_name(marker) != marker


def test_column_dataclass_is_registered_on_the_catalog():
    """The column rides the system spec — other systems default None."""
    assert find_solar_system("luyten_star").sensor_column is not None
    assert find_solar_system("sol").sensor_column is None


def test_dark_spot_rearms_after_leaving_detect_range(line_system, monkeypatch):
    """Round-2 final bug: complying with a picket's dark challenge made
    that picket immune for the whole visit, so a complying hull could
    blind the line picket by picket. The challenge is positional —
    answered only while the hull stays in detect range; leaving
    re-arms the patrol."""
    from src.spacehack import navigation_combat as nc

    opened = _modals(monkeypatch, navigation_line._Checkpoint.COMPLY)
    ctx = quest_ctx(broadcast_dark=True, militia_scanned=set(),
                    game_map=SimpleNamespace(entities=_picket_entities(LUYTEN)))
    picket = ctx.game_map.entities[0]  # at (150, 25)
    spec = nc.find_npc_ship("militia_blockade")

    near = world.Position(150, 26)
    assert nc._dark_spot_challenge(ctx, picket, spec, near) is not None
    assert nc._dark_spot_challenge(ctx, picket, spec, near) is None, (
        "in sight: already answered"
    )

    nc._dark_spot_challenge(ctx, picket, spec, world.Position(150, 60))
    result = nc._dark_spot_challenge(ctx, picket, spec, near)
    assert result is not None, "the retreat re-arms the patrol"
    assert len(opened) == 2


# ---------------------------------------------------------------------------
# The watchbill (phase 2): pure clock derivations + data consistency
# ---------------------------------------------------------------------------

def test_total_days_is_dense_across_month_and_year_wraps():
    _t = navigation_line.total_days
    assert _t(1, 1, 2200) == 2200 * 360 + 1
    assert _t(30, 1, 2200) + 1 == _t(1, 2, 2200), "month wrap is dense"
    assert _t(29, 12, 2200) + 2 == _t(1, 1, 2201), "year wrap is dense"
    assert navigation_line.clock_total(
        SimpleNamespace(time_day=15, time_month=3, time_year=2200)
    ) == _t(15, 3, 2200)


def test_tenure_boundaries_land_on_days_8_15_22():
    """Epoch-anchored: tenure 0 is the game's first week (a raw
    year*360+… clock would drift boundaries off 8/15/22 — 360
    isn't divisible by 7)."""
    _epoch = navigation_line._EPOCH_DAY
    _run_day = lambda d: navigation_line.tenure_of(_epoch + d - 1, 7)
    assert [_run_day(d) for d in (1, 7, 8, 14, 15, 21, 22, 28, 29)] == [
        0, 0, 1, 1, 2, 2, 3, 3, 4,
    ]
    assert navigation_line.tenure_start(3, 7) == _epoch + 21


def test_tenure_derivation_holds_across_month_and_year_wraps():
    """Independent expressions on both sides of each wrap: the clock
    is dense AND a boundary lands where the epoch math says it does,
    inside the wrap window."""
    _ctx_total = lambda d, m, y: navigation_line.clock_total(
        SimpleNamespace(time_day=d, time_month=m, time_year=y))
    _tenure = lambda d, m, y: navigation_line.tenure_of(_ctx_total(d, m, y), 7)

    assert _ctx_total(30, 12, 2200) + 1 == _ctx_total(1, 1, 2201), (
        "the year wrap is dense"
    )
    assert _tenure(30, 12, 2200) == 51
    assert _tenure(4, 1, 2201) == 51
    assert _tenure(5, 1, 2201) == 52, "a boundary lands inside the year wrap"
    assert _tenure(6, 2, 2200) == 5, "month wrap: the offset-35 boundary"


def test_watch_kind_cycles_full_full_full_thin():
    _kind = navigation_line.watch_kind
    cycle = LUYTEN.sensor_column.watch_cycle
    assert [_kind(t, cycle) for t in range(8)] == [
        "full", "full", "full", "thin", "full", "full", "full", "thin",
    ], "the maintenance watch is every 4th shift (28 days)"


def test_station_launch_day_is_the_lead_before_the_boundary():
    column = LUYTEN.sensor_column
    _epoch = navigation_line._EPOCH_DAY
    north = column.full_watch[0]  # y=7, lead 10
    south = column.full_watch[4]  # y=63, lead 7
    assert navigation_line.station_launch_day(1, north, 7) == _epoch - 3
    assert navigation_line.station_launch_day(4, south, 7) == _epoch + 21


def test_tenure_key_round_trips_and_plain_keys_do_not_parse():
    assert navigation_line.parse_tenure_key("sys:e:150:25:t3") == ((150, 25), 3)
    assert navigation_line.parse_tenure_key("luyten_star:militia_blockade:150:25") is None
    assert navigation_line.parse_tenure_key("sys:e:x:y:t3") is None
    assert navigation_line.parse_tenure_key("") is None
    assert navigation_line.tenure_key("sys:e:150:25", 3) == "sys:e:150:25:t3"


def test_next_boundary_gap_strictly_future():
    _gap = navigation_line.next_boundary_gap
    assert _gap(5, 1, 2200, 7) == 3   # day 5 → boundary day 8
    assert _gap(8, 1, 2200, 7) == 7   # a boundary day jumps the NEXT one
    assert _gap(1, 1, 2200, 7) == 7


def test_station_dock_cell_is_east_of_body_mid_height():
    spec = SimpleNamespace(pos=world.Position(70, 22), width=3, height=3)
    assert navigation_line.station_dock_cell(spec) == (74, 23)


def test_watch_active_and_roster_for_read_the_data():
    from src.spacehack.data.solar_systems import SensorColumn
    column = LUYTEN.sensor_column
    assert navigation_line.watch_active(column)
    assert navigation_line.roster_for(column, "full") is column.full_watch
    assert navigation_line.roster_for(column, "thin") is column.thin_watch
    bare = SensorColumn(x=150, label="x", squad_id="s", picket_enemy_id="e",
                        rank_rep=80, hail_lines=("{id}",))
    assert not navigation_line.watch_active(bare), (
        "empty rosters = no watch: statics stand as placed (phase-1 semantics)"
    )


def test_every_station_launch_day_is_its_lead_before_its_boundary():
    column = LUYTEN.sensor_column
    for t in (0, 1, 2, 4):
        for station in (*column.full_watch, *column.thin_watch):
            assert navigation_line.station_launch_day(t, station, 7) == (
                navigation_line.tenure_start(t, 7) - station.lead_days
            )


# ---------------------------------------------------------------------------
# The watch build (phase 2): tenure-keyed placement + reconciliation
# ---------------------------------------------------------------------------

_EPOCH = navigation_line.total_days(1, 1, 2200)  # run-day N = _EPOCH + N - 1
_BASE_CELLS = {(74, 23), (134, 116)}  # North / South dock cells


def _build_watch(run_day: int, skip=()):
    from src.spacehack import solar_system as ss_module
    return ss_module.make_solar_system(
        system=LUYTEN, skip_static_spawns=frozenset(skip),
        watch_day=_EPOCH + run_day - 1,
    )


def _watch_pickets(game_map):
    return [
        _e for _e in game_map.entities
        if getattr(_e, "npc_ship_id", "") == "militia_blockade"
    ]


def test_full_watch_build_parks_tenure_keyed_pickets():
    """Run-day 1 (tenure 0, full): ten pickets PARKED on station with
    t0 keys — the thin stations never spawn; the reliefs whose launch
    days predate the epoch stamp at their bases to fly in."""
    pickets = _watch_pickets(_build_watch(1))
    parked = [_e for _e in pickets if _e.pos.x == 150]
    at_base = [_e for _e in pickets if (_e.pos.x, _e.pos.y) in _BASE_CELLS]

    assert len(parked) == 10
    assert {(_e.pos.y) for _e in parked} == {
        7, 21, 35, 49, 63, 77, 91, 105, 119, 133,
    }
    assert all(_e.static_spawn_key.endswith(":t0") for _e in parked)
    # Overdue T=1 reliefs at day 1: leads 10 (launch -3) x3 north and
    # lead 9 (launch -2), lead 7 (launch 0) south — mustering at bases.
    assert len(at_base) == 5
    assert all(_e.static_spawn_key.endswith(":t1") for _e in at_base)
    assert len(pickets) == len(parked) + len(at_base)


def test_thin_watch_build_mans_the_shipped_four():
    """Run-day 22 (tenure 3, the maintenance week): the line thins to
    the shipped four stations; the full roster's t3 keys never appear."""
    pickets = _watch_pickets(_build_watch(22))
    parked = [_e for _e in pickets if _e.pos.x == 150]
    reliefs = [_e for _e in pickets if (_e.pos.x, _e.pos.y) in _BASE_CELLS]

    assert {(_e.pos.y) for _e in parked} == {25, 55, 85, 115}
    assert all(_e.static_spawn_key.endswith(":t3") for _e in parked)
    # T=4 reliefs launched by day 22: y7/21/35 (lead 10, day 19),
    # y49 (day 20), y63 (day 22) — five mustering + the standing four.
    assert len(reliefs) == 5
    assert all(_e.static_spawn_key.endswith(":t4") for _e in reliefs)


def test_watch_build_requires_the_day():
    from src.spacehack import solar_system as ss_module
    with pytest.raises(ValueError, match="watch_day"):
        ss_module.make_solar_system(system=LUYTEN)


def test_two_relief_waves_stamp_when_both_are_overdue():
    """Run-day 12 (tenure 1): the T=2 wave is fully airborne on paper
    (every full launch day <= 12) and the thin y25 relief (lead 10,
    launch day 12) joins it — two future tenures' keys coexist."""
    pickets = _watch_pickets(_build_watch(12))
    by_tenure = {}
    for _e in pickets:
        _t = navigation_line.parse_tenure_key(_e.static_spawn_key)[1]
        by_tenure.setdefault(_t, []).append(_e)

    assert len(by_tenure[1]) == 10, "the standing watch"
    assert len(by_tenure[2]) == 10, "the next full wave, all launched"
    assert len(by_tenure[3]) == 1, "the thin vanguard (y25, lead 10)"
    assert all(
        (_e.pos.x, _e.pos.y) in _BASE_CELLS for _e in by_tenure[3]
    )


def test_same_station_stacks_two_waves_at_its_base():
    """Run-day 5: the north stations' T=1 reliefs are overdue AND the
    T=2 wave launches (day 15 - lead 10) — the same station has TWO
    reliefs mustering at the same dock cell, both tolerated."""
    base_keys = [
        _e.static_spawn_key for _e in _watch_pickets(_build_watch(5))
        if (_e.pos.x, _e.pos.y) == (74, 23)  # Blockade Station North
    ]
    for _y in (7, 21, 35):
        assert f"luyten_star:militia_blockade:150:{_y}:t1" in base_keys
        assert f"luyten_star:militia_blockade:150:{_y}:t2" in base_keys


def test_hail_key_is_stable_for_a_moving_picket():
    """A flying picket keeps ONE hail key: the stamped spawn key, not
    its position — the positional dark-spot re-arm must not re-open
    the challenge every step of a flight. Procedural hulls still key
    by squad; keyless statics by position."""
    from src.spacehack import navigation_combat as nc

    flying = world.Entity("M", (100, 200, 255), world.Position(120, 40),
                          npc_ship_id="militia_blockade",
                          static_spawn_key="luyten_star:militia_blockade:150:21:t2")
    key = nc._entity_hail_key(flying)
    flying.pos = world.Position(121, 41)
    flying.pos = world.Position(140, 30)
    assert nc._entity_hail_key(flying) == key

    patrol = world.Entity("M", (100, 200, 255), world.Position(5, 5),
                          npc_ship_id="militia_patrol",
                          procedural_squad_id="patrol_1")
    assert nc._entity_hail_key(patrol) == "patrol_1"

    derelict = world.Entity("D", (150, 150, 150), world.Position(9, 9),
                            npc_ship_id="derelict")
    assert nc._entity_hail_key(derelict) == "derelict:9:9"


# ---------------------------------------------------------------------------
# The watch pass (phase 2): flights, boundaries, silence
# ---------------------------------------------------------------------------

_NORTH_CELL, _SOUTH_CELL = (74, 23), (134, 116)


def _pin_throttle(monkeypatch, probability=0.0):
    """Freeze the flight throttle: 0.0 = every flight steps."""
    from src.spacehack import engine as engine_module
    monkeypatch.setattr(
        engine_module, "RNG",
        SimpleNamespace(random=lambda: probability),
    )


def _watch_ctx(game_map, run_day, **extra):
    _day, _month, _year = _run_day_to_triple(run_day)
    return quest_ctx(
        game_map=game_map, day=_day, month=_month, year=_year, **extra,
    )


def _run_day_to_triple(run_day):
    """(day, month, year) whose total_days is _EPOCH + run_day - 1."""
    from src.spacehack.time import add_days_to_date
    return add_days_to_date(1, 1, 2200, run_day - 1)


def _by_key(game_map):
    return {
        _e.static_spawn_key: _e
        for _e in _watch_pickets(game_map)
    }


def test_boundary_rotates_the_whole_disjoint_roster(line_system, monkeypatch):
    """Run-day 29 (tenure 4, thin->full boundary): the thin four fly
    home, the full watch's reliefs are all airborne by launch/ensure,
    and NOTHING logs (wordless)."""
    _pin_throttle(monkeypatch)
    game_map = _build_watch(24)  # mid-thin; six t4 reliefs already at bases
    ctx = _watch_ctx(game_map, 29, defeated_static_spawns=set(),
                     npc_targets={}, npc_paths={})

    navigation_line.step_watch(ctx)

    thin = [_e for _e in _watch_pickets(game_map)
            if _e.static_spawn_key.endswith(":t3")]
    full = [_e for _e in _watch_pickets(game_map)
            if _e.static_spawn_key.endswith(":t4")]
    assert len(thin) == 4 and len(full) == 10, "the whole line rotates"
    home_cells = {_NORTH_CELL, _SOUTH_CELL}
    for _e in thin:
        _target = ctx.npc_targets[_e.static_spawn_key]
        assert _target in home_cells, "the ended shift is ordered home"
    for _e in full:
        assert ctx.npc_targets[_e.static_spawn_key] == (150, _station_y(_e)), (
            "every relief flies for its station (launched or ordered)"
        )
    assert _log_text(ctx) == "", "launches and departures are silent"


def _station_y(entity):
    return navigation_line.parse_tenure_key(entity.static_spawn_key)[0][1]


def test_displaced_picket_is_never_moved(line_system, monkeypatch):
    """A lured picket held across a boundary stays EXACTLY where it
    is: never ordered home, never despawned (its tenure ended; the
    target discriminates displaced from departing)."""
    _pin_throttle(monkeypatch)
    game_map = _build_watch(24)
    lured = next(
        _e for _e in _watch_pickets(game_map)
        if _e.static_spawn_key == "luyten_star:militia_blockade:150:55:t3"
    )
    lured.pos = world.Position(120, 60)
    ctx = _watch_ctx(game_map, 29, defeated_static_spawns=set(),
                     npc_targets={}, npc_paths={})

    navigation_line.step_watch(ctx)
    navigation_line.step_watch(ctx)

    assert lured.pos == world.Position(120, 60)
    assert ctx.npc_targets.get(lured.static_spawn_key) is None, (
        "a displaced picket is never given a target"
    )


def test_home_arrival_despawns_silently(line_system, monkeypatch):
    _pin_throttle(monkeypatch)
    game_map = _build_watch(24)
    ctx = _watch_ctx(game_map, 29, defeated_static_spawns=set(),
                     npc_targets={}, npc_paths={})
    navigation_line.step_watch(ctx)  # the boundary orders the thin four home

    _home_key = "luyten_star:militia_blockade:150:25:t3"
    _e = _by_key(game_map)[_home_key]
    _e.pos = world.Position(*_NORTH_CELL)  # one cell from landing
    before = len(game_map.entities)

    navigation_line.step_watch(ctx)

    assert _e not in game_map.entities
    assert len(game_map.entities) == before - 1
    assert _home_key not in ctx.npc_targets and _home_key not in ctx.npc_paths
    assert _log_text(ctx) == "", "a relief landing at its base logs nothing"


def test_relief_parks_and_holds_its_station(line_system, monkeypatch):
    """Arrival at the station parks the picket (target popped); early
    arrivals HOLD — later steps never move a parked picket."""
    _pin_throttle(monkeypatch)
    game_map = _build_watch(24)
    ctx = _watch_ctx(game_map, 24, defeated_static_spawns=set(),
                     npc_targets={}, npc_paths={})
    navigation_line.step_watch(ctx)  # the base-stamped t4 reliefs get orders

    _relief_key = "luyten_star:militia_blockade:150:7:t4"
    _e = _by_key(game_map)[_relief_key]
    assert ctx.npc_targets[_relief_key] == (150, 7)
    _e.pos = world.Position(151, 8)  # slipped aside, within a cell of post

    navigation_line.step_watch(ctx)
    assert ctx.npc_targets.get(_relief_key) is None, "arrived: parked"
    _parked_at = _e.pos

    navigation_line.step_watch(ctx)
    navigation_line.step_watch(ctx)
    assert _e.pos == _parked_at, "a parked picket holds its post"
    assert _e in game_map.entities


def test_combat_locked_pickets_are_not_stepped(line_system, monkeypatch):
    _pin_throttle(monkeypatch)
    game_map = _build_watch(24)
    ctx = _watch_ctx(game_map, 24, defeated_static_spawns=set(),
                     npc_targets={}, npc_paths={})
    navigation_line.step_watch(ctx)

    _relief_key = "luyten_star:militia_blockade:150:7:t4"
    _e = _by_key(game_map)[_relief_key]
    _e.combat_locked = True
    _e.pos = world.Position(151, 8)  # within a cell — would park if stepped

    navigation_line.step_watch(ctx)
    assert ctx.npc_targets.get(_relief_key) is not None, (
        "a locked picket neither steps nor arrives"
    )


def test_murdered_relief_stays_dead_for_its_tenure(line_system, monkeypatch):
    """A tombstoned launch key never spawns — killing a relief buys
    one station-tenure of darkness on that station."""
    _pin_throttle(monkeypatch)
    _murdered = "luyten_star:militia_blockade:150:91:t4"
    game_map = _build_watch(29, skip=(_murdered,))
    ctx = _watch_ctx(game_map, 29, defeated_static_spawns={_murdered},
                     npc_targets={}, npc_paths={})

    navigation_line.step_watch(ctx)
    navigation_line.step_watch(ctx)

    keys = _by_key(game_map).keys()
    assert _murdered not in keys
    assert "luyten_star:militia_blockade:150:105:t4" in keys, (
        "the other stations still man"
    )


def test_watch_traffic_never_enters_the_squad_machinery(line_system, monkeypatch):
    """Watch flights carry no procedural_squad_id: move_npcs never
    patrols or despawns them (the schedule is the watch pass's)."""
    _pin_throttle(monkeypatch)
    from src.spacehack import npc_ships

    game_map = _build_watch(24)
    ctx = _watch_ctx(game_map, 29, defeated_static_spawns=set(),
                     npc_targets={}, npc_paths={})
    navigation_line.step_watch(ctx)

    _squads = npc_ships._squad_groups(game_map)
    _picket_ids = {id(_e) for _e in _watch_pickets(game_map)}
    assert all(
        id(_m) not in _picket_ids
        for _members in _squads.values() for _m in _members
    ), "line traffic is invisible to the patrol machinery"


def test_payload_counts_parked_in_flight_and_displaced_by_id():
    """The manned sweep counts EVERY alive picket wherever it stands
    — parked on post, mid-flight, lured aside — and nothing that is
    not the picket id."""
    _mk = lambda key, pos: world.Entity(
        "M", (100, 200, 255), world.Position(*pos),
        npc_ship_id="militia_blockade", static_spawn_key=key,
    )
    ctx = quest_ctx(game_map=SimpleNamespace(entities=[
        _mk("luyten_star:militia_blockade:150:21:t0", (150, 21)),   # parked
        _mk("luyten_star:militia_blockade:150:49:t1", (90, 40)),    # in flight
        _mk("luyten_star:militia_blockade:150:55:t3", (120, 60)),   # displaced
        world.Entity("M", (100, 200, 255), world.Position(150, 22),
                     npc_ship_id="militia_patrol",
                     static_spawn_key="luyten_star:militia_patrol:150:22:t0"),
    ]))
    specs, positions = navigation_line._picket_payload(
        ctx, LUYTEN.sensor_column,
    )
    assert len(specs) == 3 and len(positions) == 3
    assert (120, 60) in [(_p.x, _p.y) for _p in positions]


def test_day_skips_heal_at_the_next_due_day(line_system, monkeypatch):
    """A clock jump past a boundary leaves a stale watch standing
    (displaced-in-time keepers serve until the schedule catches up);
    the next due day launches every overdue relief, and the boundary
    after that sends the stale keepers home."""
    _pin_throttle(monkeypatch)
    game_map = _build_watch(1)  # tenure 0 keepers + t1 vanguard at bases
    ctx = _watch_ctx(game_map, 11, defeated_static_spawns=set(),
                     npc_targets={}, npc_paths={})  # +10 days, no rebuild

    navigation_line.step_watch(ctx)  # run-day 11: y91's t2 launch day

    keys = _by_key(game_map)
    assert "luyten_star:militia_blockade:150:7:t1" in keys, (
        "the skipped tenure's relief launched from its base"
    )
    assert "luyten_star:militia_blockade:150:7:t0" in keys, (
        "the stale keeper serves until the next boundary"
    )
    assert ctx.npc_targets.get("luyten_star:militia_blockade:150:7:t0") is None

    ctx.time_day, ctx.time_month, ctx.time_year = _run_day_to_triple(15)
    navigation_line.step_watch(ctx)  # the tenure-2 boundary
    assert ctx.npc_targets["luyten_star:militia_blockade:150:7:t0"] == _NORTH_CELL, (
        "the stale keeper finally departs at the boundary"
    )


def test_luyten_watchbill_data_consistency():
    column = LUYTEN.sensor_column
    full_ys = [s.y for s in column.full_watch]
    thin_ys = [s.y for s in column.thin_watch]
    station_ids = {s.id for s in LUYTEN.stations}

    assert column.shift_days == 7
    assert set(column.watch_cycle) <= {"full", "thin"}
    # The full watch closes the gaps with ships: spacing 14 = detect x 2.
    assert full_ys == [7, 21, 35, 49, 63, 77, 91, 105, 119, 133]
    from src.spacehack.data.npc_ships import find_npc_ship
    assert find_npc_ship(column.picket_enemy_id).detect_radius * 2 == 14
    # The thin watch is the shipped four; rosters are disjoint.
    assert thin_ys == [25, 55, 85, 115]
    assert not set(full_ys) & set(thin_ys), "every full-thin boundary rotates the whole line"
    # Every roster station names a real base and a real spawn row.
    row_ys = {s.pos.y for s in LUYTEN.enemies}
    for station in (*column.full_watch, *column.thin_watch):
        assert station.lead_days >= 1
        assert station.base_id in station_ids
        assert station.y in row_ys, "every station has an EnemySpawn row"
