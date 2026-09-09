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


def _picket_entities(system):
    """Alive picket entities stamped at the system's spawn positions
    (with their tombstone keys — the stamp happens at map build)."""
    from src.spacehack.solar_system import static_spawn_key
    return [
        world.Entity("M", (100, 200, 255), _spawn.pos,
                     npc_ship_id=_spawn.enemy_id,
                     static_spawn_key=static_spawn_key(system, _spawn))
        for _spawn in system.enemies
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
    the hull (AI advance), the key does not."""
    from src.spacehack import solar_system as ss_module
    from src.spacehack.combat._space_kills import mark_static_spawn_defeated

    ctx = quest_ctx(defeated_static_spawns=set())
    dead = world.Entity("B", (130, 230, 220), world.Position(148, 40),
                        npc_ship_id="militia_blockade",
                        static_spawn_key="luyten_star:militia_blockade:150:25")

    mark_static_spawn_defeated(ctx, dead)
    assert ctx.defeated_static_spawns == {
        "luyten_star:militia_blockade:150:25",
    }

    fresh = ss_module.make_solar_system(
        system=LUYTEN, skip_static_spawns=ctx.defeated_static_spawns,
    )
    _stamped = [
        _e for _e in fresh.entities
        if getattr(_e, "npc_ship_id", "") == "militia_blockade"
    ]
    assert len(_stamped) == 3, "the dead picket does not re-stamp"
    assert all(_e.static_spawn_key for _e in _stamped), "builds stamp keys"

    untouched = ss_module.make_solar_system(system=LUYTEN)
    assert sum(
        1 for _e in untouched.entities
        if getattr(_e, "npc_ship_id", "") == "militia_blockade"
    ) == 4


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
    """The load chain must honor the tombstones, not just restore the
    ctx field: _build_space_map skips defeated statics."""
    from src.spacehack.saveload_maps import _build_space_map

    _log = SimpleNamespace(add=lambda _m: None)
    _common = ("luyten_star", _log, None, {}, {}, {}, 10, 10)

    built = _build_space_map(*_common, ["luyten_star:militia_blockade:150:25"])
    _map, _player = built
    assert sum(
        1 for _e in _map.entities
        if getattr(_e, "npc_ship_id", "") == "militia_blockade"
    ) == 3

    built_full = _build_space_map(*_common, [])
    assert sum(
        1 for _e in built_full[0].entities
        if getattr(_e, "npc_ship_id", "") == "militia_blockade"
    ) == 4


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
    assert nc._entity_hail_key(picket) in ctx.militia_scanned


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
