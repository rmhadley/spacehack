"""Chrome catalog + container pins (doc 102.4.1).

The t1 teach line's data contracts: catalog well-formedness
(unique anatomy keys — the exclusivity axis), the one-pass effect
sums every combat assembly reads, and the install/uninstall
primitives' SWAP semantics (SETTLED 14).
"""

from src.spacehack.chrome import (
    ChromeEffects,
    install_chrome,
    installed_effects,
    uninstall_chrome,
    worn_anatomy_piece,
)
from src.spacehack.data.chrome import find_chrome, list_chrome
from src.spacehack.game_context import GameContext
from types import SimpleNamespace


def test_catalog_six_t1_pieces_with_unique_anatomy():
    pieces = list_chrome()
    assert len(pieces) == 6
    assert len({p.anatomy for p in pieces}) == 6, (
        "one installed piece per anatomy requires unique keys"
    )
    for piece in pieces:
        assert piece.tier == 1
        assert piece.burn == 1
        assert 250 <= piece.price <= 400, "teach-tier calibration band"
        assert piece.name.startswith("Terminus "), "item-name register (SETTLED 10)"


def test_catalog_anatomy_keys_match_the_settled_map():
    keys = {p.id: p.anatomy for p in list_chrome()}
    assert keys == {
        "terminus_optics": "ocular",
        "terminus_piloting_jack": "jack",
        "terminus_neural_stim": "os",
        "terminus_nano_mesh": "dermal",
        "terminus_muscle_fibers": "arm_muscle",
        "terminus_smartlink": "hands",
    }


def test_installed_effects_empty_and_unknown_ids():
    assert installed_effects([]) == ChromeEffects()
    # Stale-save contract: unknown ids skip silently, never raise.
    assert installed_effects(["retired_piece"]) == ChromeEffects()


def test_installed_effects_each_piece_payload():
    assert installed_effects(["terminus_optics"]).crit_chance_space == 15
    jack = installed_effects(["terminus_piloting_jack"])
    assert jack.dodge_tile_bonus == 1 and not jack.has_core
    stim = installed_effects(["terminus_neural_stim"])
    assert stim.has_core and not stim.nano_mesh
    mesh = installed_effects(["terminus_nano_mesh"])
    assert mesh.nano_mesh and not mesh.has_core
    fibers = installed_effects(["terminus_muscle_fibers"])
    assert fibers.crit_chance_melee == 15 and fibers.melee_damage_bonus == 2
    assert installed_effects(["terminus_smartlink"]).crit_chance_ranged == 15


def test_installed_effects_sums_across_all_six():
    worn = installed_effects([p.id for p in list_chrome()])
    assert worn.crit_chance_space == 15
    assert worn.crit_chance_melee == 15
    assert worn.crit_chance_ranged == 15
    assert worn.dodge_tile_bonus == 1
    assert worn.melee_damage_bonus == 2
    assert worn.nano_mesh and worn.has_core


def _ctx_with_chrome(*piece_ids):
    ctx = GameContext(context=None, character_info={}, log=None,
                      game_map=None, player=None, stats=None)
    for piece_id in piece_ids:
        install_chrome(ctx, piece_id)
    return ctx


def test_install_same_anatomy_is_a_swap_never_a_stack():
    ctx = _ctx_with_chrome("terminus_optics")
    replaced = install_chrome(ctx, "terminus_optics")
    assert replaced == "terminus_optics"
    assert ctx.installed_chrome == ["terminus_optics"]


def test_install_different_anatomy_stacks():
    ctx = _ctx_with_chrome("terminus_optics")
    assert install_chrome(ctx, "terminus_neural_stim") == ""
    assert ctx.installed_chrome == ["terminus_optics", "terminus_neural_stim"]
    assert worn_anatomy_piece(ctx.installed_chrome, "ocular") == "terminus_optics"


def test_uninstall_frees_the_anatomy():
    ctx = _ctx_with_chrome("terminus_nano_mesh")
    assert uninstall_chrome(ctx, "terminus_nano_mesh") is True
    assert ctx.installed_chrome == []
    assert uninstall_chrome(ctx, "terminus_nano_mesh") is False


def test_find_chrome_raises_on_unknown_id():
    try:
        find_chrome("no_such_piece")
    except KeyError:
        return
    raise AssertionError("expected KeyError for unknown chrome id")


class TestDevAcquisition:
    """The F7 dev toggle (4.1's acquisition path; the kiosk replaces
    it in 4.2)."""

    def test_toggle_flips_install_state_and_logs(self):
        from src.spacehack.dev_mode import toggle_chrome_dev
        ctx = _ctx_with_chrome()
        ctx.log = SimpleNamespace(
            add=lambda _m, **_k: None,
            add_colored=lambda _m, _c, **_k: None,
        )
        assert toggle_chrome_dev(ctx, "terminus_optics").endswith("installed.")
        assert ctx.installed_chrome == ["terminus_optics"]
        assert toggle_chrome_dev(ctx, "terminus_optics").endswith("uninstalled.")
        assert ctx.installed_chrome == []

    def test_toggle_grants_different_anatomy_pieces_side_by_side(self):
        from src.spacehack.dev_mode import toggle_chrome_dev
        ctx = _ctx_with_chrome("terminus_optics")
        toggle_chrome_dev(ctx, "terminus_neural_stim")  # different anatomy
        assert ctx.installed_chrome == [
            "terminus_optics", "terminus_neural_stim",
        ]

    def test_menu_labels_carry_the_live_install_state(self):
        from src.spacehack.dev_mode import chrome_toggle_menu
        ctx = _ctx_with_chrome("terminus_neural_stim")
        labels = dict(chrome_toggle_menu(ctx).options)
        assert "INSTALLED" in labels["terminus_neural_stim"]
        assert "not installed" in labels["terminus_optics"]

    def test_f7_helper_matches_only_f7_keydowns(self):
        from src.spacehack import pygame_engine
        from src.spacehack.input_helpers import _is_f7_press
        assert _is_f7_press(
            pygame_engine.PygameInputEvent(kind="keydown", key_name="f7"),
        )
        assert not _is_f7_press(
            pygame_engine.PygameInputEvent(kind="keydown", key_name="f6"),
        )


def _ego_ctx(burn=0, pieces=()):
    """A ctx with the ego/skill/stat/log doubles the instruments read."""
    ctx = _ctx_with_chrome(*pieces)
    ctx.player_level = 10
    ctx.ego_burn = burn
    ctx.stats = SimpleNamespace(credits=10_000)
    ctx.ground_stats = SimpleNamespace(reflexes=10, strength=10, stamina=10)
    ctx.current_city_id = ""
    ctx.log = SimpleNamespace(
        add=lambda _m, **_k: None,
        add_colored=lambda _m, _c, **_k: None,
    )
    return ctx


class TestInstallInstrument:
    """The three-check + consent + removal instruments (SETTLED 14,
    prose ledger 7-9)."""

    def test_capacity_blocks_with_the_ruled_message(self):
        from src.spacehack.chrome import install_check
        ctx = _ego_ctx(pieces=tuple(p.id for p in list_chrome()[:6]))
        # pool 9, load 6: a fresh anatomy piece needs 1, room 3 - fine;
        # a full pool blocks via a re-install over every anatomy... use
        # level 1 (pool 6, load 6 -> room 0).
        ctx.player_level = 1
        _msg = install_check(ctx, "terminus_optics")  # self-swap: room 0
        assert _msg == "Install Room 1 required, you have 0."

    def test_t1_passes_the_instrument_clean(self):
        from src.spacehack.chrome import install_check
        assert install_check(_ego_ctx(), "terminus_optics") is None

    def test_consent_body_carries_the_ruled_table(self):
        from src.spacehack.chrome import consent_body
        ctx = _ego_ctx(burn=0)
        body, swap = consent_body(ctx, "terminus_optics")
        assert "Before/After" in body
        assert "Ego:         9/8" in body       # pool 9, burn 0 -> 1
        assert "Burnt Ego:   0/1" in body
        assert "Install Room: 9/8" in body
        # burn 0 -> 1 stays Natural (the dead zone is <= 3).
        assert "State:   Natural" in body
        assert swap is None
        # The fourth teach piece crosses: burn 3 -> 4 Taints.
        ctx.installed_chrome = [
            "terminus_optics", "terminus_neural_stim", "terminus_nano_mesh",
        ]
        ctx.ego_burn = 3
        body, swap = consent_body(ctx, "terminus_muscle_fibers")
        assert "Burnt Ego:   3/4" in body
        assert "State:   Natural/Tainted" in body
        # Within the peak above the dead zone: 4/4, Tainted once.
        ctx.installed_chrome = ["terminus_neural_stim"]
        ctx.ego_burn = 4
        body, swap = consent_body(ctx, "terminus_optics")
        assert "Burnt Ego:   4/4" in body
        assert "State:   Tainted" in body  # unchanged: name once

    def test_consent_swap_line_names_the_replaced_piece(self):
        from src.spacehack.chrome import consent_body
        ctx = _ego_ctx(pieces=("terminus_optics",))
        _body, swap = consent_body(ctx, "terminus_optics")
        assert swap == "Replaces Terminus Optics."

    def test_removal_table_teaches_the_ratchet(self):
        from src.spacehack.chrome import removal_table_lines
        ctx = _ego_ctx(burn=1, pieces=("terminus_optics",))
        assert removal_table_lines(ctx, "terminus_optics") == (
            "Terminus Optics removed.",
            "Ego: 8/8",
            "Burnt Ego: 1/1",
            "Install Room: 8/9",
        )


class TestKioskPriceAndFlow:
    """The kiosk's banded price + the one-step transaction."""

    def test_kiosk_price_rides_the_local_band(self):
        from src.spacehack.menus._kiosk import _kiosk_price
        ctx = _ego_ctx()
        ctx.current_city_id = ""
        assert _kiosk_price(ctx, 100) == 100        # Natural
        ctx.ego_burn = 4
        assert _kiosk_price(ctx, 100) == 105        # Tainted

    def test_install_via_kiosk_charges_and_ratchets(self, monkeypatch):
        import asyncio

        from src.spacehack.menus import _kiosk

        ctx = _ego_ctx()
        ctx.current_city_id = ""

        async def _confirm(*_a, **_k):
            return "CONFIRM"

        monkeypatch.setattr(
            "src.spacehack.game_flow._run_pygame_dungeon_confirm", _confirm,
        )
        asyncio.run(_kiosk._attempt_install(ctx, "terminus_optics"))
        assert ctx.installed_chrome == ["terminus_optics"]
        assert ctx.ego_burn == 1
        assert ctx.stats.credits == 10_000 - 260

    def test_install_declined_leaves_everything_untouched(self, monkeypatch):
        import asyncio

        from src.spacehack.menus import _kiosk

        ctx = _ego_ctx()
        ctx.current_city_id = ""

        async def _decline(*_a, **_k):
            return "BACK"

        monkeypatch.setattr(
            "src.spacehack.game_flow._run_pygame_dungeon_confirm", _decline,
        )
        asyncio.run(_kiosk._attempt_install(ctx, "terminus_optics"))
        assert ctx.installed_chrome == []
        assert ctx.ego_burn == 0
        assert ctx.stats.credits == 10_000

    def test_swap_back_lands_in_armory_storage(self, monkeypatch):
        import asyncio

        from src.spacehack.menus import _kiosk

        ctx = _ego_ctx(pieces=("terminus_optics",), burn=1)
        ctx.current_city_id = ""

        async def _confirm(*_a, **_k):
            return "CONFIRM"

        monkeypatch.setattr(
            "src.spacehack.game_flow._run_pygame_dungeon_confirm", _confirm,
        )
        asyncio.run(_kiosk._attempt_install(ctx, "terminus_optics"))  # self-swap
        _entries = [
            e for e in ctx.ground_armory_storage if e.item_type == "chrome"
        ]
        assert [e.item_id for e in _entries] == ["terminus_optics"]

    def test_removal_via_kiosk_logs_the_full_table(self):
        """The full ruled table through the shipped remover — the
        Install Room row must show 8/9 (the piece still counted),
        not the post-uninstall drift the reviewer caught."""
        from src.spacehack.menus import _kiosk
        ctx = _ego_ctx(burn=1, pieces=("terminus_optics",))
        lines = []
        ctx.log = SimpleNamespace(
            add=lambda _m, **_k: None,
            add_colored=lambda text, _c, **_k: lines.append(text),
        )
        _kiosk._remove(ctx, "terminus_optics")
        assert lines == [
            "Terminus Optics removed.",
            "Ego: 8/8",
            "Burnt Ego: 1/1",
            "Install Room: 8/9",
        ]
        assert ctx.installed_chrome == []






class TestConsortiumGate:
    """The derived gate (SETTLED 5) + the one-time intro (SETTLED 4)."""

    def test_gate_reads_twice_the_birth_pool(self):
        from src.spacehack.chrome import consortium_gate_open
        assert consortium_gate_open(_ego_ctx(burn=11)) is False
        assert consortium_gate_open(_ego_ctx(burn=12)) is True

    def test_intro_fires_once_at_the_crossing(self):
        """Pinned directly: the gate is structurally unreachable in
        v1 (six t1 pieces max burn 6 < the 12 gate; t2 territory per
        SETTLED 5) — the helper fires on the synthetic crossing."""
        from src.spacehack.chrome import maybe_fire_consortium_intro

        ctx = _ego_ctx(burn=12)
        lines = []
        ctx.log = SimpleNamespace(
            add=lambda _m, **_k: None,
            add_colored=lambda text, _c, **_k: lines.append(text),
        )
        ctx.consortium_intro_shown = False

        maybe_fire_consortium_intro(ctx)
        assert lines == [
            "Your Terminus Tech account is now active. We will be in touch.",
        ]
        assert ctx.consortium_intro_shown is True
        # Already shown: never again.
        maybe_fire_consortium_intro(ctx)
        assert len(lines) == 1
        # Gate closed (flag still False): nothing fires, flag stays.
        _closed = _ego_ctx(burn=11)
        _closed.consortium_intro_shown = False
        _closed.log = ctx.log
        maybe_fire_consortium_intro(_closed)
        assert len(lines) == 1
        assert _closed.consortium_intro_shown is False

    def test_f_screen_line_rides_the_gate(self):
        from src.spacehack.pygame_faction import _identity_block
        _closed = _identity_block(_ego_ctx(burn=0))
        assert all("Terminus Tech" not in line for line in _closed)
        _open = _identity_block(_ego_ctx(burn=12))
        assert any(
            line == "Terminus Tech: account active" for line in _open
        )


class TestKioskLoopEntry:
    """The kiosk's split loop executes against the REAL family (a
    runtime-less context raises the guard, never a TypeError — the
    arity class the two launch crashes shared)."""

    def test_kiosk_menu_reaches_the_runtime_guard(self):
        import asyncio

        from src.spacehack.menus import _kiosk
        from src.spacehack.pygame_split import PygameSplitUnavailable

        ctx = _ego_ctx()
        ctx.context = SimpleNamespace()  # no shared runtime attached

        try:
            asyncio.run(_kiosk._run_kiosk_menu(ctx, "earth"))
        except PygameSplitUnavailable:
            return  # the frame built; the call matched the family
        except TypeError as exc:
            raise AssertionError(f"call-arity drift: {exc}")
        raise AssertionError("expected the runtime guard to raise")


class TestKioskSplitFrame:
    """The split redesign (playtest ruling 2026-10-16): left stock,
    right installed, ruled detail lines, TAB between panes."""

    def test_stock_rows_carry_price_bay_and_detail(self):
        from src.spacehack.menus import _kiosk
        ctx = _ego_ctx()
        rows = _kiosk._stock_rows(ctx)
        _optics = rows[0]
        assert _optics.label == "Terminus Optics"
        assert _optics.value == "260$ (Ocular)"
        assert _optics.detail == "Space crit chance 15%."
        assert _optics.action == "INSTALL:terminus_optics"

    def test_installed_pane_lists_removals_and_empty_state(self):
        from src.spacehack.menus import _kiosk
        _empty = _kiosk._installed_rows(_ego_ctx())
        assert _empty[0].label == "[empty]"
        assert _empty[0].selectable is False

        ctx = _ego_ctx(pieces=("terminus_smartlink",))
        _worn = _kiosk._installed_rows(ctx)
        assert _worn[0].action == "REMOVE:terminus_smartlink"
        assert _worn[0].detail == "Ranged crit chance 15%."

    def test_the_frame_reads_available_installed(self):
        from src.spacehack.menus import _kiosk
        frame = _kiosk._kiosk_frame(_ego_ctx(), 0, 0)
        assert frame.title == "TERMINUS TECH"
        assert (frame.left_label, frame.right_label) == (
            "Available", "Installed",
        )
        assert "Ego 9  Burnt Ego 0  Install Room 9" in frame.footer_left
        assert "State: Natural" in frame.footer_right
        assert len(frame.left_rows) == 6
