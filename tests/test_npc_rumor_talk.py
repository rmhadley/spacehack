"""Host wiring tests for the rumor talk surface (doc 42 phase 1).

One Ask around row on the main talk menu (present whenever the NPC
holds an unheard opener or a heard extension); everything askable
lives in the sub-menu. Floors read the RESOLVED sheet the host passes.
"""

from tests.support.quest_ctx import quest_ctx

from src.spacehack import npc as npc_mod
from src.spacehack.data.npcs import find_npc


def _sheet(monkeypatch, rep):
    """Pin the resolved-sheet read the host must use (dark -> {})."""
    monkeypatch.setattr(
        "src.spacehack.identity.effective_reputation", lambda ctx: rep,
    )


def test_non_source_npc_gets_no_ask_row(monkeypatch):
    _sheet(monkeypatch, {})
    assert npc_mod._offers_rumors(quest_ctx(), find_npc("guild_master")) is False


def test_source_npc_gets_the_ask_row_pre_hear(monkeypatch):
    _sheet(monkeypatch, {})
    assert npc_mod._offers_rumors(quest_ctx(), find_npc("barkeep")) is True


def test_ask_row_goes_when_the_npc_holds_nothing_more(monkeypatch):
    _sheet(monkeypatch, {})
    ctx = quest_ctx(known_rumors=["derelict_line_1", "thin_month_1"])
    # The barkeep offered both openers and extends neither chain —
    # with both heard he holds nothing, so his row goes...
    assert npc_mod._offers_rumors(ctx, find_npc("barkeep")) is False
    # ...while the witness still extends the derelict chain.
    assert npc_mod._offers_rumors(ctx, find_npc("depot_attendant")) is True


def test_floor_withholds_the_ask_row(monkeypatch):
    # The host passes the RESOLVED sheet: a worn face at militia liked
    # (30) clears the neutral floor the true hostile sheet (-5) fails.
    _sheet(monkeypatch, {"militia": -5})
    assert npc_mod._offers_rumors(quest_ctx(), find_npc("blockade_officer")) is False
    _sheet(monkeypatch, {"militia": 30})
    assert npc_mod._offers_rumors(quest_ctx(), find_npc("blockade_officer")) is True


def test_items_builder_carries_exactly_one_ask_row():
    items = npc_mod._npc_pygame_items(
        find_npc("barkeep"), [], [], ask_around=True,
    )
    _actions = [item.action for item in items]
    assert _actions.count("ASKAROUND") == 1
    assert not any(a.startswith("RUMOR:") for a in _actions)


def test_result_mapping_maps_askaround():
    assert npc_mod._map_pygame_npc_result(
        "SELECT", "ASKAROUND", []) == (npc_mod.TalkOutcome.ASKAROUND, None)


def test_ask_around_sitting_hears_opener_then_extension(monkeypatch):
    _readouts = []
    monkeypatch.setattr(
        npc_mod, "_show_rumor_readout",
        lambda ctx, npc, text: _readouts.append(text),
    )
    # One sitting: pick the opener, then the extension, then the
    # sub-menu is exhausted (a None pick closes it).
    _picks = iter(["ASKTOPIC:derelict_line_1", "ASKTOPIC:derelict_line_2"])
    monkeypatch.setattr(
        npc_mod, "_run_choice_submenu",
        lambda ctx, **kwargs: next(_picks, None),
    )
    ctx = quest_ctx()
    result = npc_mod._resolve_talk_result(
        ctx, find_npc("depot_attendant"), (npc_mod.TalkOutcome.ASKAROUND, None),
    )
    assert result == (npc_mod.TalkOutcome.BACK, None)
    assert ctx.known_rumors == ["derelict_line_1", "derelict_line_2"]
    assert len(_readouts) == 2


def test_ask_around_closes_when_the_npc_is_out_of_rumors(monkeypatch):
    _opened = []
    monkeypatch.setattr(
        npc_mod, "_run_choice_submenu",
        lambda ctx, **kwargs: _opened.append(1) or None,
    )
    ctx = quest_ctx()
    result = npc_mod._resolve_talk_result(
        ctx, find_npc("guild_master"), (npc_mod.TalkOutcome.ASKAROUND, None),
    )
    assert result == (npc_mod.TalkOutcome.BACK, None)
    assert _opened == [], "nothing askable never opens the sub-menu"
    assert ctx.known_rumors == []


def test_ask_around_quits_propagate(monkeypatch):
    monkeypatch.setattr(
        npc_mod, "_run_choice_submenu", lambda ctx, **kwargs: "QUIT",
    )
    ctx = quest_ctx()
    result = npc_mod._resolve_talk_result(
        ctx, find_npc("barkeep"), (npc_mod.TalkOutcome.ASKAROUND, None),
    )
    assert result == (npc_mod.TalkOutcome.QUIT, None)
    assert ctx.known_rumors == [], "QUIT hears nothing"


def test_full_talk_flow_surfaces_the_ask_row(monkeypatch):
    _sheet(monkeypatch, {})
    _seen = {}

    def _fake_talk(ctx, npc_obj, body, missions, options=(), scrub=None,
                   cutout=None, rig=None, sell_ids=None, items=None):
        _seen["actions"] = [item.action for item in items]
        return (npc_mod.TalkOutcome.BACK, None)

    monkeypatch.setattr(npc_mod, "_run_pygame_npc_talk", _fake_talk)
    npc_mod._run_npc_talk(quest_ctx(), find_npc("barkeep"))
    assert "ASKAROUND" in _seen["actions"]
    assert not any(a.startswith("RUMOR:") for a in _seen["actions"])
