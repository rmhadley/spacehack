"""Crew role tables + hostile boarded interiors (doc 48 phase 6).

Covers the SETTLED 28/38 mechanism: role-token ENEMY markers resolve
through CREW_ROLES per faction (raw ids pass through; omitted roles
skip), the security-drone dial scales its role's chances, and every
capture/derelict interior is hostile on entry regardless of faction
rep — through the one uniform seam (``spec_is_hostile``'s game_map
param), serialized with the dungeon payload.
"""

from pathlib import Path
from types import SimpleNamespace

import pytest

from src.spacehack.dungeon_layout import load_layout

_CREW_LAYOUT = """\
MAP
##########
#P......l#
#k......w#
#x......Q#
##########
ENDMAP
TILE: # = DUNGEON_WALL
TILE: . = DUNGEON_FLOOR
ENEMY: l = line@1.0#1-1
ENEMY: k = marksman@1.0#1-1
ENEMY: w = heavy@1.0#1-1
ENEMY: Q = security_drone@1.0#1-1
ENEMY: x = stowaway@1.0#1-1
"""

_RAW_ID_LAYOUT = """\
MAP
######
#P..c#
######
ENDMAP
TILE: # = DUNGEON_WALL
TILE: . = DUNGEON_FLOOR
ENEMY: c = consortium_enforcer@1.0#1-1
"""


def _layout_dir(tmp_path: Path, text: str) -> Path:
    (tmp_path / "roles_a.layout").write_text(text, encoding="utf-8")
    return tmp_path


def _crew_ids(game_map) -> set[str]:
    return {
        e.npc_char_id for e in game_map.entities if getattr(e, "npc_char_id", "")
    }


def test_crew_roles_table_shape():
    from src.spacehack.data.npc_chars.crew_roles import (
        CREW_ROLES,
        CREW_ROLE_TOKENS,
    )

    assert set(CREW_ROLES["pirate"]) == CREW_ROLE_TOKENS
    assert set(CREW_ROLES["militia"]) == CREW_ROLE_TOKENS - {"stowaway"}
    assert set(CREW_ROLES["merchant"]) == CREW_ROLE_TOKENS
    assert set(CREW_ROLES["consortium"]) == CREW_ROLE_TOKENS - {"heavy"}


def test_crew_roles_cells_are_live_specs():
    from src.spacehack.data.npc_chars import find_npc_char
    from src.spacehack.data.npc_chars.crew_roles import CREW_ROLES

    for _faction, table in CREW_ROLES.items():
        for _role, spec_id in table.items():
            assert find_npc_char(spec_id).id == spec_id, (
                f"dangling CREW_ROLES cell {_faction}.{_role} -> "
                f"{spec_id!r}: no such npc char"
            )


def test_roles_resolve_per_faction_at_load(tmp_path):
    game_map, _spawn = load_layout(
        "roles_a", layout_dir=_layout_dir(tmp_path, _CREW_LAYOUT),
        crew_faction="pirate",
    )
    assert _crew_ids(game_map) == {
        "pirate_raider", "pirate_rifleman", "pirate_brute",
        "sentry_drone", "hull_parasite",
    }

    game_map, _spawn = load_layout(
        "roles_a", layout_dir=_layout_dir(tmp_path, _CREW_LAYOUT),
        crew_faction="militia",
    )
    # militia omits stowaway (SETTLED 38): the marker skips at load.
    assert _crew_ids(game_map) == {
        "militia_trooper", "militia_sniper", "militia_marine",
        "sentry_drone",
    }

    game_map, _spawn = load_layout(
        "roles_a", layout_dir=_layout_dir(tmp_path, _CREW_LAYOUT),
        crew_faction="merchant",
    )
    # SETTLED 38: merchant defense is droids across the roles — light
    # crew plus machines, no humanoid heavies or marksmen.
    assert _crew_ids(game_map) == {
        "merchant", "assault_drone", "sentry_drone", "hull_parasite",
    }


def test_merchant_row_shape():
    from src.spacehack.data.npc_chars import find_npc_char

    spec = find_npc_char("merchant")
    assert spec.name == "Merchant"
    assert spec.char == "h"
    assert spec.fg == (100, 220, 140)
    assert spec.faction == "merchant"
    assert spec.weapons == ("kinetic_pistol", "combat_knife")
    assert spec.loot_pool == ("food_rations", "textiles")
    assert spec.loot_count == (1, 1)
    assert spec.stat_weights == (0.0,) * 6  # band-exempt (SETTLED 38)
    assert spec.hp == 16
    assert spec.ap == 4
    assert spec.xp_reward == 12


def test_raw_spec_ids_pass_through_with_crew_faction(tmp_path):
    game_map, _spawn = load_layout(
        "roles_a", layout_dir=_layout_dir(tmp_path, _RAW_ID_LAYOUT),
        crew_faction="pirate",
    )
    assert _crew_ids(game_map) == {"consortium_enforcer"}


def test_role_token_without_faction_raises(tmp_path):
    with pytest.raises(ValueError, match="crew faction"):
        load_layout(
            "roles_a", layout_dir=_layout_dir(tmp_path, _CREW_LAYOUT),
        )


def test_unknown_crew_faction_raises(tmp_path):
    with pytest.raises(ValueError, match="crew faction"):
        load_layout(
            "roles_a", layout_dir=_layout_dir(tmp_path, _CREW_LAYOUT),
            crew_faction="civilian",
        )


def test_security_drone_dial_scales_role_chances(tmp_path):
    dial_layout = _CREW_LAYOUT.replace(
        "ENEMY: Q = security_drone@1.0#1-1",
        "ENEMY: Q = security_drone@0.5#1-1",
    )
    boosted, _spawn = load_layout(
        "roles_a", layout_dir=_layout_dir(tmp_path, dial_layout),
        crew_faction="pirate", security_drones=2.0,
    )
    assert "sentry_drone" in _crew_ids(boosted)  # 0.5 x 2.0 caps at 1.0

    emptied, _spawn = load_layout(
        "roles_a", layout_dir=_layout_dir(tmp_path, dial_layout),
        crew_faction="pirate", security_drones=0.0,
    )
    assert "sentry_drone" not in _crew_ids(emptied)


def _rep_ctx(rep: dict) -> SimpleNamespace:
    return SimpleNamespace(
        broadcast_dark=False,
        broadcast_identity=None,
        faction_reputation=dict(rep),
    )


def test_hostile_interior_overrides_rep_reading():
    from src.spacehack.data.npc_chars import find_npc_char
    from src.spacehack.faction import spec_is_hostile

    ctx = _rep_ctx({"militia": 50})  # liked: militia reads non-hostile
    trooper = find_npc_char("militia_trooper")
    plain_map = SimpleNamespace(hostile_interior=False)
    boarded_map = SimpleNamespace(hostile_interior=True)

    assert spec_is_hostile(ctx, trooper) is False
    assert spec_is_hostile(ctx, trooper, plain_map) is False
    assert spec_is_hostile(ctx, trooper, boarded_map) is True


def test_hostile_interior_round_trips_save_load(tmp_path):
    from src.spacehack.saveload_maps import (
        _apply_dungeon_attributes,
        _dungeon_to_dict,
    )

    game_map, _spawn = load_layout(
        "roles_a", layout_dir=_layout_dir(tmp_path, _CREW_LAYOUT),
        crew_faction="pirate",
    )
    assert game_map.hostile_interior is False  # the loader never stamps it

    game_map.hostile_interior = True
    restored = SimpleNamespace(entities=[])
    _apply_dungeon_attributes(restored, _dungeon_to_dict(game_map, None))
    assert restored.hostile_interior is True

    game_map.hostile_interior = False
    restored = SimpleNamespace(entities=[])
    _apply_dungeon_attributes(restored, _dungeon_to_dict(game_map, None))
    assert restored.hostile_interior is False


def test_landmark_interiors_stay_rep_read():
    # SETTLED 38: the override is capture/derelict only — an authored
    # landmark deck loads without the flag.
    landmark_dir = (
        Path(__file__).resolve().parent.parent
        / "src" / "spacehack" / "data" / "landmarks"
    )
    game_map, _spawn = load_layout(
        "wolf_camp", layout_dir=landmark_dir, require_spawn=False,
    )
    assert game_map.hostile_interior is False
