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
