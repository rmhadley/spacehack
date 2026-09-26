"""Tombstones (doc 53) — format pins, log stripping, writer I/O.

The integration pins (both-theater DEFEAT writes, killer tracking,
non-DEFEAT no-write) live in ``tests/combat/test_tombstone_deaths.py``
on the real-combat harness; this file pins the pure text contract and
the filesystem shell.
"""

import re
import sys
from datetime import datetime
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.spacehack import engine, solar_system, tombstone
from src.spacehack.game_context import PlayerCounters
from src.spacehack.ground_equipment import (
    GroundItemStack,
    GroundWeaponInstance,
    StoredGroundEquipment,
)
from src.spacehack.message_log import MessageLog, with_runs
from src.spacehack.data.quality import quality_mark
from src.spacehack.ship import OwnedShip, StoredEquipment

_NOW = datetime(2026, 9, 26, 14, 5, 3)


def _ctx(**overrides) -> SimpleNamespace:
    """A full-shape read-only ctx: every field the builders read,
    pinned with catalog-real values."""
    ctx = SimpleNamespace(
        character_info={
            "species_id": "human", "species_name": "Human",
            "class_id": "pilot", "class_name": "Pilot",
        },
        player_level=3,
        player_xp=500,
        player_traits=["sharpshooter"],
        player_counters=PlayerCounters(
            total_damage_taken=11, ground_damage_taken=7,
        ),
        stats=SimpleNamespace(gunnery=12, piloting=8, engineering=5),
        ground_stats=SimpleNamespace(reflexes=11, strength=9, stamina=12),
        equipped_ground_weapons=[GroundWeaponInstance("kinetic_pistol", 12, 1)],
        holstered_ground_weapons=[GroundWeaponInstance("mono_blade", None)],
        equipped_ground_armor={
            "head": StoredGroundEquipment("armor", "light_helmet"),
        },
        bandolier={"kinetic_pistol": 24},
        ground_expedition_inventory=[
            StoredGroundEquipment("weapon", "vibroblade"),
        ],
        ground_expedition_items=[GroundItemStack("ammo", "pistol_rounds", 10)],
        player_owned_ship=OwnedShip(
            ship_id="scout",
            display_name="Nice Ship",
            weapons=("light_laser", "heavy_missile"),
            modules=(StoredEquipment("module", "reactor_mk2", quality=1),),
            weapon_ammo={1: 6},
        ),
        game_map=SimpleNamespace(),
        current_city_id="earth",
        time_day=4,
        time_month=2,
        time_year=2201,
        log=MessageLog(),
    )
    for key, value in overrides.items():
        setattr(ctx, key, value)
    return ctx


def _facts() -> tombstone.TombstoneFacts:
    return tombstone.TombstoneFacts(
        killer="Pirate Scout's Light Laser",
        final_state="HP -2/28  AP 0",
    )


def test_header_pins_every_settled_field():
    ctx = _ctx()
    lines = tombstone._header_lines(ctx, _facts(), _NOW)
    assert lines == [
        "=" * 48,
        "  Human Pilot",
        "  Level 3 — died 2026-09-26 14:05",
        "  4/2/2201 — Sol",
        "  Slain by: Pirate Scout's Light Laser",
        "  Damage taken (career): space 11, ground 7",
        f"  Run seed: {engine.INIT_SEED}",
        "  Final state: HP -2/28  AP 0",
        "=" * 48,
    ]


def test_killer_none_renders_the_unknown_causes_line():
    ctx = _ctx()
    facts = tombstone.TombstoneFacts(killer=None)
    assert "  Slain by: unknown causes" in tombstone._header_lines(
        ctx, facts, _NOW,
    )


def test_self_splash_killer_renders_the_settled_line():
    ctx = _ctx()
    facts = tombstone.TombstoneFacts(killer="your own explosives")
    assert "  Slain by: your own explosives" in tombstone._header_lines(
        ctx, facts, _NOW,
    )


def test_location_is_system_only_on_a_space_map():
    lines = tombstone._header_lines(_ctx(), _facts(), _NOW)
    assert "  4/2/2201 — Sol" in lines


def test_location_appends_the_map_name_when_present():
    ctx = _ctx(game_map=SimpleNamespace(location_name="Mars Surface"))
    assert "  4/2/2201 — Sol / Mars Surface" in tombstone._header_lines(
        ctx, _facts(), _NOW,
    )


def test_location_falls_back_to_the_city_on_city_maps():
    ctx = _ctx(game_map=SimpleNamespace(city_transit={}))
    assert "  4/2/2201 — Sol / Earth" in tombstone._header_lines(
        ctx, _facts(), _NOW,
    )


def test_sections_appear_in_the_settled_order():
    text = tombstone.build_tombstone_text(_ctx(), _facts())
    assert text.index("CHAR") < text.index("GEAR")
    assert text.index("GEAR") < text.index("MESSAGE LOG")


def test_kit_lists_sets_armor_bandolier_pack_and_ship():
    text = tombstone.build_tombstone_text(_ctx(), _facts())
    assert "  ACTIVE SET: Modded Kinetic Pistol [12/12]" in text
    assert "  HOLSTERED SET: Mono Blade" in text
    assert "Head Light Helmet" in text
    assert "Hands none" in text
    assert "  Ammo: Pistol Rounds 24" in text
    assert "  Expedition pack: Vibroblade, Pistol Rounds x10" in text
    assert "  SHIP: Nice Ship" in text
    assert "    Weapons: Light Laser, Heavy Missile [6/3]" in text
    assert "    Modules: Modded Reactor Mk. 2" in text


def test_ship_block_omitted_when_no_ship():
    text = tombstone.build_tombstone_text(
        _ctx(player_owned_ship=None), _facts(),
    )
    assert "SHIP:" not in text


def test_log_exports_verbatim_oldest_first_text_only():
    log = MessageLog()
    log.add("first")
    _msg, _runs = with_runs("The ", quality_mark("Kinetic Pistol", 1), " fires.")
    log.add_colored(_msg, (255, 0, 0), runs=_runs)
    log.add_colored("last", (255, 95, 95))
    text = tombstone.build_tombstone_text(_ctx(log=log), _facts())
    assert text.rstrip("\n").endswith(
        "  --- MESSAGE LOG (full, oldest first) ---\n"
        "  first\n"
        "  The Kinetic Pistol fires.\n"
        "  last"
    )
    # No run tuples leak: the coloured entry's payload is text only.
    assert str(_runs) not in text
    assert repr((255, 0, 0)) not in text


def test_writer_creates_file_with_name_pattern(monkeypatch, tmp_path):
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setattr(solar_system, "current_solar_system_id", "sol")
    path = tombstone.write_tombstone(_ctx(), _facts())
    assert path is not None
    assert Path(path).parent == tmp_path / ".spacehack" / "saves" / "tombstones"
    assert re.fullmatch(r"tombstone-\d{8}-\d{6}\.txt", Path(path).name)
    assert "Human Pilot" in Path(path).read_text(encoding="utf-8")


def test_same_second_second_write_gets_the_suffix(monkeypatch, tmp_path):
    monkeypatch.setenv("HOME", str(tmp_path))
    frozen = SimpleNamespace(now=lambda: _NOW)
    monkeypatch.setattr(tombstone, "datetime", frozen)
    first = tombstone.write_tombstone(_ctx(), _facts())
    second = tombstone.write_tombstone(_ctx(), _facts())
    third = tombstone.write_tombstone(_ctx(), _facts())
    assert Path(first).name == "tombstone-20260926-140503.txt"
    assert Path(second).name == "tombstone-20260926-140503-2.txt"
    assert Path(third).name == "tombstone-20260926-140503-3.txt"


def test_write_failure_is_nonfatal(monkeypatch, tmp_path):
    monkeypatch.setenv("HOME", str(tmp_path))
    tombstones = tmp_path / ".spacehack" / "saves" / "tombstones"
    tombstones.parent.mkdir(parents=True)
    tombstones.write_text("a file where the directory belongs")
    assert tombstone.write_tombstone(_ctx(), _facts()) is None


def test_notice_lines_name_the_full_filename_short_path():
    lines = tombstone.notice_lines("/home/p/.spacehack/saves/tombstones/x.txt")
    assert lines == (
        "Tombstone saved: /home/p/.spacehack/saves/tombstones/x.txt",
    )


def test_notice_lines_wrap_a_home_heavy_path():
    path = "/" + "verylonghomedirectory" * 6 + "/.spacehack/saves/tombstones/t.txt"
    lines = tombstone.notice_lines(path)
    assert lines[0] == "Tombstone saved:"
    assert "".join(lines[1:]) == path
    assert all(len(line) <= tombstone._NOTICE_WIDTH for line in lines)


# --- the char dump (doc 53 phase 2) -----------------------------------------


def test_dump_header_pins_the_living_shape():
    lines = tombstone._dump_header_lines(_ctx(), _NOW)
    assert lines == [
        "=" * 48,
        "  Human Pilot",
        "  Level 3 — dumped 2026-09-26 14:05",
        "  4/2/2201 — Sol",
        "  Damage taken (career): space 11, ground 7",
        f"  Run seed: {engine.INIT_SEED}",
        "=" * 48,
    ]


def test_dump_carries_char_gear_log_but_no_death_facts():
    text = tombstone.build_char_dump_text(_ctx())
    assert text.index("CHAR") < text.index("GEAR")
    assert text.index("GEAR") < text.index("MESSAGE LOG")
    assert "Slain by:" not in text
    assert "Final state:" not in text


def test_char_dump_writer_uses_its_own_directory(monkeypatch, tmp_path):
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setattr(solar_system, "current_solar_system_id", "sol")
    frozen = SimpleNamespace(now=lambda: _NOW)
    monkeypatch.setattr(tombstone, "datetime", frozen)
    first = tombstone.write_char_dump(_ctx())
    second = tombstone.write_char_dump(_ctx())
    dumps = tmp_path / ".spacehack" / "saves" / "chardumps"
    assert Path(first).parent == dumps
    assert Path(first).name == "chardump-20260926-140503.txt"
    assert Path(second).name == "chardump-20260926-140503-2.txt"
    # The two artifact families never share a directory.
    tombstone.write_tombstone(_ctx(), _facts())
    tombstones = tmp_path / ".spacehack" / "saves" / "tombstones"
    assert list(dumps.glob("tombstone-*.txt")) == []
    assert list(tombstones.glob("chardump-*.txt")) == []


def test_char_dump_write_failure_is_nonfatal(monkeypatch, tmp_path):
    monkeypatch.setenv("HOME", str(tmp_path))
    dumps = tmp_path / ".spacehack" / "saves" / "chardumps"
    dumps.parent.mkdir(parents=True)
    dumps.write_text("a file where the directory belongs")
    assert tombstone.write_char_dump(_ctx()) is None
