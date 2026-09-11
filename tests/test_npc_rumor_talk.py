"""Host wiring tests for the rumor talk surface (doc 42 phase 1).

One Ask around row on the main talk menu (present whenever the NPC
holds an unheard opener or a heard extension); everything askable
lives in the sub-menu. Floors read the RESOLVED sheet the host passes.
"""

from tests.support.quest_ctx import quest_ctx
from tests.support.rumor_fixture import install

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
    assert npc_mod._offers_rumors(
        quest_ctx(), find_npc("deadfall_scrubber")) is True


def test_ask_row_goes_when_the_npc_holds_nothing_more(monkeypatch):
    _sheet(monkeypatch, {})
    ctx = quest_ctx(known_rumors=["dark_berth_1", "dark_berth_2"])
    # A non-source holds nothing — the row goes...
    assert npc_mod._offers_rumors(quest_ctx(), find_npc("militia_captain")) is False
    # ...and so does a source who is out of chain (the scrubber told
    # tiers 1-2)...
    assert npc_mod._offers_rumors(ctx, find_npc("deadfall_scrubber")) is False
    # ...while the tech still extends the chain.
    assert npc_mod._offers_rumors(ctx, find_npc("ember_tech")) is True


def test_dealer_keeps_the_ask_row_with_nothing_askable(monkeypatch):
    # Ruling 10: the barkeep extends no tier (he sources none), but his
    # trade lives in the sub-menu — the row stays.
    _sheet(monkeypatch, {})
    ctx = quest_ctx(known_rumors=["dark_berth_1"])
    assert npc_mod._offers_rumors(ctx, find_npc("barkeep")) is True


def test_floor_withholds_the_ask_row(monkeypatch):
    # The host passes the RESOLVED sheet: a worn face at militia liked
    # (30) clears the neutral floor the true hostile sheet (-5) fails.
    # The gated rows ride the fixture registry — the live chain
    # authors no floors.
    install(monkeypatch)
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
    _picks = iter(["ASKTOPIC:dark_berth_1", "ASKTOPIC:dark_berth_2"])
    monkeypatch.setattr(
        npc_mod, "_run_choice_submenu",
        lambda ctx, **kwargs: next(_picks, None),
    )
    ctx = quest_ctx()
    result = npc_mod._resolve_talk_result(
        ctx, find_npc("deadfall_scrubber"), (npc_mod.TalkOutcome.ASKAROUND, None),
    )
    assert result == (npc_mod.TalkOutcome.BACK, None)
    assert ctx.known_rumors == ["dark_berth_1", "dark_berth_2"]
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


# --- doc 42 phase 2: the dealer's side of the sub-menu --------------------


def _capture_submenu(seen, picks):
    """Record every sub-menu pass; play scripted picks, then None."""
    def _run(ctx, **kwargs):
        seen.append(kwargs)
        return next(picks, None)
    return _run


def test_dealer_submenu_shows_sell_rows_and_favor_line(monkeypatch):
    _seen = []
    monkeypatch.setattr(
        npc_mod, "_run_choice_submenu", _capture_submenu(_seen, iter([])),
    )
    # dark_berth_2 heard: the wolf doesn't know it (the scrubber's
    # telling), so it's sellable — dark_berth_1 (his own telling) is
    # not.
    ctx = quest_ctx(known_rumors=["dark_berth_1", "dark_berth_2"])
    result = npc_mod._resolve_talk_result(
        ctx, find_npc("wolf_barkeep"), (npc_mod.TalkOutcome.ASKAROUND, None),
    )
    assert result == (npc_mod.TalkOutcome.BACK, None)
    _actions = [item.action for item in _seen[0]["items"]]
    assert "OFFER:dark_berth_2" in _actions
    assert "OFFER:dark_berth_1" not in _actions
    assert _seen[0]["body"] == "Favor: 0"
    _earn = [
        item for item in _seen[0]["items"] if item.action == "OFFER:dark_berth_2"
    ]
    assert _earn[0].description == "Earn 2 favor."


def test_selling_updates_favor_and_retires_the_row(monkeypatch):
    _seen = []
    monkeypatch.setattr(
        npc_mod,
        "_run_choice_submenu",
        _capture_submenu(_seen, iter(["OFFER:dark_berth_1"])),
    )
    ctx = quest_ctx(known_rumors=["dark_berth_1"])
    npc_mod._resolve_talk_result(
        ctx, find_npc("barkeep"), (npc_mod.TalkOutcome.ASKAROUND, None),
    )
    assert ctx.rumor_favor["barkeep"]["favor"] == 1
    # Second pass rebuilt live (sell-menu idiom): the sold row is
    # gone and the Favor line moved — no per-transaction modal.
    assert "OFFER:dark_berth_1" not in [
        item.action for item in _seen[1]["items"]
    ]
    assert _seen[1]["body"] == "Favor: 1"
    assert "Sold The dark berths for 1 favor." in [
        entry.text for entry in ctx.log.history()
    ]


def test_buy_row_when_affordable_and_buy_flows(monkeypatch):
    from src.spacehack import rumor as rumor_module

    _readouts = []
    monkeypatch.setattr(
        npc_mod, "_show_rumor_readout",
        lambda ctx, npc, text: _readouts.append(text),
    )
    _seen = []
    monkeypatch.setattr(
        npc_mod,
        "_run_choice_submenu",
        _capture_submenu(_seen, iter(["BUY:dark_berth_4:4"])),
    )
    ctx = quest_ctx(
        known_rumors=["dark_berth_1", "dark_berth_2", "dark_berth_3"],
        rumor_favor={"wolf_barkeep": {"favor": 4, "earned": []}},
    )
    npc_mod._resolve_talk_result(
        ctx, find_npc("wolf_barkeep"), (npc_mod.TalkOutcome.ASKAROUND, None),
    )
    assert "BUY:dark_berth_4:4" in [
        item.action for item in _seen[0]["items"]
    ]
    _cost = [
        item for item in _seen[0]["items"] if item.action == "BUY:dark_berth_4:4"
    ]
    assert _cost[0].description == "Costs 4 favor."
    assert "dark_berth_4" in ctx.known_rumors
    assert ctx.rumor_favor["wolf_barkeep"]["favor"] == 0
    # Bought knowledge reads canonically — no witness variant.
    assert _readouts == [rumor_module.entry_text("dark_berth_4")]


def test_unaffordable_exclusive_shows_no_buy_row(monkeypatch):
    _seen = []
    monkeypatch.setattr(
        npc_mod, "_run_choice_submenu", _capture_submenu(_seen, iter([])),
    )
    ctx = quest_ctx(
        known_rumors=["dark_berth_1", "dark_berth_2", "dark_berth_3"],
        rumor_favor={"wolf_barkeep": {"favor": 3, "earned": []}},
    )
    npc_mod._resolve_talk_result(
        ctx, find_npc("wolf_barkeep"), (npc_mod.TalkOutcome.ASKAROUND, None),
    )
    assert not any(
        item.action.startswith("BUY:") for item in _seen[0]["items"]
    )
    assert _seen[0]["body"] == "Favor: 3"


def test_non_dealer_submenu_keeps_the_prompt_body(monkeypatch):
    _seen = []
    monkeypatch.setattr(
        npc_mod, "_run_choice_submenu", _capture_submenu(_seen, iter([])),
    )
    ctx = quest_ctx(known_rumors=["dark_berth_1"])
    npc_mod._resolve_talk_result(
        ctx, find_npc("deadfall_scrubber"), (npc_mod.TalkOutcome.ASKAROUND, None),
    )
    assert _seen[0]["body"] == '"What do you want to know?"'
    assert not any(
        item.action.startswith(("OFFER:", "BUY:"))
        for item in _seen[0]["items"]
    )


# --- doc 42 phase 2: the knowledge-gated vendor ----------------------------


def test_knowledge_gated_vendor_hides_rows_until_heard():
    # The Whisper berth keeper's storefront exists only for someone
    # who knows the berth; ungated ember_tech is unaffected either way.
    ctx = quest_ctx()
    assert npc_mod._priced_rows(ctx, "berth_keeper") == (None, None, None)
    assert npc_mod._priced_rows(ctx, "ember_tech") == (None, 2500, None)
    ctx.known_rumors.append("dark_berth_4")
    assert npc_mod._priced_rows(ctx, "berth_keeper") == (None, 2000, None)
    assert npc_mod._priced_rows(ctx, "ember_tech") == (None, 2500, None)
