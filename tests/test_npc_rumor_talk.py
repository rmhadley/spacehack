"""Host wiring tests for the rumor talk surface (doc 42 phases 1-3).

One Ask around row on the main talk menu (present whenever the NPC
holds an unheard opener or a heard extension); everything askable
lives in the sub-menu. Floors read the RESOLVED sheet the host passes.
Phase 3: the host scopes delivery to the current planet
(ctx.current_city_id); tier 1 is trigger-delivered, so no carrier
holds anything until it has been heard.
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
    assert npc_mod._offers_rumors(
        quest_ctx(), find_npc("guild_master")) is False


def test_no_ask_row_before_discovery(monkeypatch):
    # Phase 2.5: the chain is not askable at spawn — tier 1 arrives
    # by trigger, and tier 2 requires it heard. Even a carrier holds
    # nothing pre-discovery (a non-dealer shows no row at all).
    _sheet(monkeypatch, {})
    assert npc_mod._offers_rumors(
        quest_ctx(city_id="lal_b"), find_npc("deadfall_scrubber")) is False


def _seed_where(predicate):
    """First seed (deterministic) whose live routing satisfies the
    predicate — the host reads engine.INIT_SEED, pinned per test."""
    from src.spacehack import engine as engine_mod
    from src.spacehack import rumor_routing

    seed = next(s for s in range(64) if predicate(rumor_routing, s))
    engine_mod.INIT_SEED = seed
    return seed


def test_carrier_gets_the_ask_row_once_the_opener_is_heard(monkeypatch):
    _sheet(monkeypatch, {})
    from src.spacehack import rumor
    from src.spacehack import rumor_routing

    seed = _seed_where(
        lambda rr, s: ("deadfall_scrubber", "lal_b") in rr.live_routes(s)["dark_berth_2"]
    )
    try:
        ctx = quest_ctx(city_id="lal_b", known_rumors=["dark_berth_1"])
        assert npc_mod._offers_rumors(ctx, find_npc("deadfall_scrubber")) is True
        # ...but only on the carrier's own planet.
        ctx_off = quest_ctx(city_id="wolf_b", known_rumors=["dark_berth_1"])
        assert npc_mod._offers_rumors(ctx_off, find_npc("deadfall_scrubber")) is False
        # ...and only while the seed made the candidate live (dealers
        # keep their row by design — ruling 10 — so probe a non-dealer).
        dead = sorted(
            pair
            for pair in (
                {(s[0], s[1]) for e in rumor.list_rumors()
                 if e.id == "dark_berth_2" for s in e.sources}
                - rumor_routing.live_routes(seed)["dark_berth_2"]
            )
            if not rumor.is_dealer(pair[0])
        )
        if dead:
            dead_npc, dead_planet = dead[0]
            assert npc_mod._offers_rumors(
                quest_ctx(city_id=dead_planet, known_rumors=["dark_berth_1"]),
                find_npc(dead_npc),
            ) is False
    finally:
        from src.spacehack import engine as engine_mod
        engine_mod.INIT_SEED = 0


def test_ask_row_goes_when_the_npc_holds_nothing_more(monkeypatch):
    _sheet(monkeypatch, {})
    # A non-source holds nothing — the row goes...
    assert npc_mod._offers_rumors(quest_ctx(), find_npc("militia_captain")) is False
    _seed_where(
        lambda rr, s: ("ember_tech", "ross_b") in rr.live_routes(s)["dark_berth_2"]
    )
    try:
        # ...the tech extends while tier 2 is unheard (his carrier role)...
        ctx_ross = quest_ctx(city_id="ross_b", known_rumors=["dark_berth_1"])
        assert npc_mod._offers_rumors(ctx_ross, find_npc("ember_tech")) is True
        # ...and once tier 2 is heard the chain leaves the city for
        # comms — NO carrier extends tier 3 (it is hail-delivered).
        ctx_ross_done = quest_ctx(
            city_id="ross_b", known_rumors=["dark_berth_1", "dark_berth_2"])
        assert npc_mod._offers_rumors(ctx_ross_done, find_npc("ember_tech")) is False
    finally:
        from src.spacehack import engine as engine_mod
        engine_mod.INIT_SEED = 0


def test_dealer_keeps_the_ask_row_with_nothing_askable(monkeypatch):
    # Ruling 10: the barkeep extends no tier, but his trade lives in
    # the sub-menu — the row stays.
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
    assert npc_mod._offers_rumors(
        quest_ctx(city_id="blockade_south"), find_npc("blockade_officer")) is False
    _sheet(monkeypatch, {"militia": 30})
    assert npc_mod._offers_rumors(
        quest_ctx(city_id="blockade_south"), find_npc("blockade_officer")) is True


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


def test_ask_around_sitting_hears_the_extension(monkeypatch):
    _readouts = []
    monkeypatch.setattr(
        npc_mod, "_show_rumor_readout",
        lambda ctx, npc, text: _readouts.append(text),
    )
    _seed_where(
        lambda rr, s: ("deadfall_scrubber", "lal_b") in rr.live_routes(s)["dark_berth_2"]
    )
    try:
        # One sitting: tier 1 already heard (the dock trigger), the
        # scrubber delivers tier 2, then the sub-menu is exhausted (a
        # None pick closes it).
        _picks = iter(["ASKTOPIC:dark_berth_2"])
        monkeypatch.setattr(
            npc_mod, "_run_choice_submenu",
            lambda ctx, **kwargs: next(_picks, None),
        )
        ctx = quest_ctx(city_id="lal_b", known_rumors=["dark_berth_1"])
        result = npc_mod._resolve_talk_result(
            ctx, find_npc("deadfall_scrubber"), (npc_mod.TalkOutcome.ASKAROUND, None),
        )
        assert result == (npc_mod.TalkOutcome.BACK, None)
        assert ctx.known_rumors == ["dark_berth_1", "dark_berth_2"]
        assert len(_readouts) == 1
    finally:
        from src.spacehack import engine as engine_mod
        engine_mod.INIT_SEED = 0


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
    # Tiers 1 and 3 have no authored sources — the wolf buys both;
    # tier 2 is his own telling and never shows a Sell row.
    ctx = quest_ctx(
        city_id="wolf_b", known_rumors=["dark_berth_1", "dark_berth_2", "dark_berth_3"],
    )
    result = npc_mod._resolve_talk_result(
        ctx, find_npc("wolf_barkeep"), (npc_mod.TalkOutcome.ASKAROUND, None),
    )
    assert result == (npc_mod.TalkOutcome.BACK, None)
    _actions = [item.action for item in _seen[0]["items"]]
    assert "OFFER:dark_berth_1" in _actions
    assert "OFFER:dark_berth_3" in _actions
    assert "OFFER:dark_berth_2" not in _actions
    assert _seen[0]["body"] == "Favor: 0"
    _earn = [
        item for item in _seen[0]["items"] if item.action == "OFFER:dark_berth_1"
    ]
    assert _earn[0].description == "Earn 1 favor."


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
    assert "Sold Dark ports for 1 favor." in [
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
    _seed_where(lambda rr, s: "wolf_barkeep" in rr.live_holdings(s))
    try:
        ctx = quest_ctx(
            city_id="wolf_b",
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
    finally:
        from src.spacehack import engine as engine_mod
        engine_mod.INIT_SEED = 0


def test_unaffordable_exclusive_shows_no_buy_row(monkeypatch):
    _seen = []
    monkeypatch.setattr(
        npc_mod, "_run_choice_submenu", _capture_submenu(_seen, iter([])),
    )
    _seed_where(lambda rr, s: "wolf_barkeep" in rr.live_holdings(s))
    try:
        ctx = quest_ctx(
            city_id="wolf_b",
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
    finally:
        from src.spacehack import engine as engine_mod
        engine_mod.INIT_SEED = 0


def test_non_dealer_submenu_keeps_the_prompt_body(monkeypatch):
    _seen = []
    monkeypatch.setattr(
        npc_mod, "_run_choice_submenu", _capture_submenu(_seen, iter([])),
    )
    _seed_where(
        lambda rr, s: ("deadfall_scrubber", "lal_b") in rr.live_routes(s)["dark_berth_2"]
    )
    try:
        ctx = quest_ctx(city_id="lal_b", known_rumors=["dark_berth_1"])
        npc_mod._resolve_talk_result(
            ctx, find_npc("deadfall_scrubber"), (npc_mod.TalkOutcome.ASKAROUND, None),
        )
        assert _seen[0]["body"] == '"What do you want to know?"'
        assert not any(
            item.action.startswith(("OFFER:", "BUY:"))
            for item in _seen[0]["items"]
        )
    finally:
        from src.spacehack import engine as engine_mod
        engine_mod.INIT_SEED = 0


# --- doc 42 phase 2.5: the shady tech (the payoff moved outdoors) ----------


def test_shady_tech_prices_the_cutout_gated_on_the_passphrase():
    # The row's keyring gate (playtest ruling 2026-09-12): he is
    # always on the map, but the install row exists only once the
    # chain names him.
    ctx = quest_ctx()
    assert npc_mod._priced_rows(ctx, "shady_tech") == (None, None, None)
    ctx.known_rumors.append("dark_berth_4")
    assert npc_mod._priced_rows(ctx, "shady_tech") == (None, 2000, None)
    assert npc_mod._priced_rows(ctx, "ember_tech") == (None, 2500, None)
    ctx.transponder_cutout = True
    assert npc_mod._priced_rows(ctx, "shady_tech") == (None, None, None)


def test_shady_techs_install_row_is_the_passphrase():
    items = npc_mod._npc_pygame_items(
        find_npc("shady_tech"), [], [], cutout_price=2000,
    )
    _row = next(item for item in items if item.action == "CUTOUT")
    assert _row.label == "The Hush sent me."
    # Every other broker's row is unchanged.
    _plain = npc_mod._npc_pygame_items(
        find_npc("ember_tech"), [], [], cutout_price=2500,
    )
    _plain_row = next(item for item in _plain if item.action == "CUTOUT")
    assert _plain_row.label == "Install a transponder cut-out (2,500cr)"


# --- doc 42 phase 3: holder scatter through the host -----------------------


def test_only_the_live_holder_shows_the_buy_row(monkeypatch):
    from src.spacehack import engine as engine_mod
    from src.spacehack import rumor_routing

    # A seed whose live holder of dark_berth_4 is NOT the wolf.
    seed = next(
        s for s in range(16)
        if "wolf_barkeep" not in rumor_routing.live_holdings(s)
    )
    monkeypatch.setattr(engine_mod, "INIT_SEED", seed)
    _seen = []
    monkeypatch.setattr(
        npc_mod, "_run_choice_submenu", _capture_submenu(_seen, iter([])),
    )
    _both_rich = {
        dealer: {"favor": 9, "earned": []}
        for dealer in ("wolf_barkeep", "barkeep", "research_officer")
    }
    _heard = ["dark_berth_1", "dark_berth_2", "dark_berth_3"]
    npc_mod._resolve_talk_result(
        quest_ctx(city_id="wolf_b", known_rumors=_heard, rumor_favor=dict(_both_rich)),
        find_npc("wolf_barkeep"), (npc_mod.TalkOutcome.ASKAROUND, None),
    )
    assert not any(
        item.action.startswith("BUY:") for item in _seen[0]["items"]
    ), "a non-live candidate shows nothing"
    _holder = next(
        dealer for dealer, rows in rumor_routing.live_holdings(seed).items()
        for _row in rows
    )
    _seen.clear()
    npc_mod._resolve_talk_result(
        quest_ctx(city_id="earth", known_rumors=_heard, rumor_favor=dict(_both_rich)),
        find_npc(_holder), (npc_mod.TalkOutcome.ASKAROUND, None),
    )
    assert "BUY:dark_berth_4:4" in [
        item.action for item in _seen[0]["items"]
    ]
