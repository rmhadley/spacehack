"""Host wiring tests for the rumor talk surface (doc 42 phase 1).

Pins the talk-modal contract: chain-opener hearing rows, Ask Around
post-hear only, floors read the RESOLVED sheet the host passes, and
the RUMOR:/ASKAROUND dispatch records on the keyring.
"""

from tests.support.quest_ctx import quest_ctx

from src.spacehack import npc as npc_mod
from src.spacehack.data.npcs import find_npc


def _sheet(monkeypatch, rep):
    """Pin the resolved-sheet read the host must use (dark -> {})."""
    monkeypatch.setattr(
        "src.spacehack.identity.effective_reputation", lambda ctx: rep,
    )


def test_non_source_npc_offers_no_rumor_rows(monkeypatch):
    _sheet(monkeypatch, {})
    rows, ask_around = npc_mod._rumor_surface(quest_ctx(), find_npc("guild_master"))
    assert rows == []
    assert ask_around is False


def test_source_npc_offers_chain_openers(monkeypatch):
    _sheet(monkeypatch, {})
    rows, ask_around = npc_mod._rumor_surface(quest_ctx(), find_npc("barkeep"))
    assert "derelict_line_1" in dict(rows).values()
    assert "thin_month_1" in dict(rows).values()
    assert ask_around is False


def test_ask_around_appears_only_post_hear(monkeypatch):
    _sheet(monkeypatch, {})
    ctx = quest_ctx(known_rumors=["derelict_line_1"])
    # The witness who holds tier 2 offers Ask Around...
    _rows, _ask = npc_mod._rumor_surface(ctx, find_npc("depot_attendant"))
    assert _ask is True
    # ...but the barkeep (who cannot deliver tier 2) does not, and his
    # derelict opener is gone now that the chain is in progress — other
    # chains' openers still surface.
    _rows, _ask = npc_mod._rumor_surface(ctx, find_npc("barkeep"))
    assert _ask is False
    assert "derelict_line_1" not in dict(_rows).values()
    assert "thin_month_1" in dict(_rows).values()


def test_floor_blocks_the_row_at_host_level(monkeypatch):
    # The host passes the RESOLVED sheet: a worn face at militia liked
    # (30) clears the neutral floor the true hostile sheet (-5) fails.
    _sheet(monkeypatch, {"militia": -5})
    rows, _ = npc_mod._rumor_surface(quest_ctx(), find_npc("blockade_officer"))
    assert rows == []
    _sheet(monkeypatch, {"militia": 30})
    rows, _ = npc_mod._rumor_surface(quest_ctx(), find_npc("blockade_officer"))
    assert "thin_month_1" in dict(rows).values()


def test_items_builder_carries_rumor_rows():
    items = npc_mod._npc_pygame_items(
        find_npc("barkeep"), [], [],
        rumor_options=[("Ask about the derelict line", "derelict_line_1")],
        ask_around=True,
    )
    _actions = [item.action for item in items]
    assert "RUMOR:derelict_line_1" in _actions
    assert "ASKAROUND" in _actions


def test_result_mapping_parses_rumor_actions():
    _mapped = npc_mod._map_pygame_npc_result(
        "SELECT", "RUMOR:derelict_line_1", [])
    assert _mapped == (npc_mod.TalkOutcome.RUMOR, "derelict_line_1")
    assert npc_mod._map_pygame_npc_result(
        "SELECT", "ASKAROUND", []) == (npc_mod.TalkOutcome.ASKAROUND, None)


def test_hear_row_records_and_shows_readout(monkeypatch):
    _readouts = []
    monkeypatch.setattr(
        npc_mod, "_show_rumor_readout",
        lambda ctx, npc, text: _readouts.append(text),
    )
    ctx = quest_ctx()
    result = npc_mod._resolve_talk_result(
        ctx, find_npc("barkeep"),
        (npc_mod.TalkOutcome.RUMOR, "derelict_line_1"),
    )
    assert result == (npc_mod.TalkOutcome.BACK, None)
    assert ctx.known_rumors == ["derelict_line_1"]
    assert len(_readouts) == 1
    assert _readouts[0] == "Folks think the derelicts drift wherever they died. " \
        "They don't. Plot a hundred wrecks and two lines come out - old " \
        "convoy routes. Whatever those convoys were escorting never arrived."


def test_ask_around_loop_records_then_closes(monkeypatch):
    _readouts = []
    monkeypatch.setattr(
        npc_mod, "_show_rumor_readout",
        lambda ctx, npc, text: _readouts.append(text),
    )
    _picks = iter(["ASKTOPIC:derelict_line_2"])
    monkeypatch.setattr(
        npc_mod, "_run_choice_submenu",
        lambda ctx, **kwargs: next(_picks),
    )
    ctx = quest_ctx(known_rumors=["derelict_line_1"])
    result = npc_mod._resolve_talk_result(
        ctx, find_npc("depot_attendant"), (npc_mod.TalkOutcome.ASKAROUND, None),
    )
    assert result == (npc_mod.TalkOutcome.BACK, None)
    assert ctx.known_rumors == ["derelict_line_1", "derelict_line_2"]
    assert len(_readouts) == 1


def test_ask_around_quits_propagate(monkeypatch):
    monkeypatch.setattr(
        npc_mod, "_run_choice_submenu", lambda ctx, **kwargs: "QUIT",
    )
    ctx = quest_ctx(known_rumors=["derelict_line_1"])
    result = npc_mod._resolve_talk_result(
        ctx, find_npc("depot_attendant"), (npc_mod.TalkOutcome.ASKAROUND, None),
    )
    assert result == (npc_mod.TalkOutcome.QUIT, None)
    assert ctx.known_rumors == ["derelict_line_1"], "QUIT hears nothing"


def test_full_talk_flow_surfaces_the_hearing_row(monkeypatch):
    _sheet(monkeypatch, {})
    _seen = {}

    def _fake_talk(ctx, npc_obj, body, missions, options=(), scrub=None,
                   cutout=None, rig=None, sell_ids=None, items=None):
        _seen["actions"] = [item.action for item in items]
        return (npc_mod.TalkOutcome.BACK, None)

    monkeypatch.setattr(npc_mod, "_run_pygame_npc_talk", _fake_talk)
    npc_mod._run_npc_talk(quest_ctx(), find_npc("barkeep"))
    assert "RUMOR:derelict_line_1" in _seen["actions"]
    assert "RUMOR:thin_month_1" in _seen["actions"]
    assert "ASKAROUND" not in _seen["actions"]
