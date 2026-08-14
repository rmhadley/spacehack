"""Temporary research tool: estimate split-terminal font sizes.

Builds the REAL terminal frames (real catalogs, real starter ship) and asks
pygame_split._fit_font which point size it would pick, using a fake font
that approximates DejaVu Sans Mono metrics (linesize ~= 1.2*size,
advance ~= 0.6*size). No pygame needed.

Run from the project root:  python3 tools/_font_estimate.py
"""

from __future__ import annotations

import os
import sys
from types import SimpleNamespace

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


class FakeFont:
    def __init__(self, size: int):
        self.point_size = size

    def get_linesize(self) -> int:
        return int(self.point_size * 1.2) + 1

    def size(self, text: str) -> tuple[int, int]:
        return int(len(text) * self.point_size * 0.6), self.point_size


class FakePygame:
    class font:
        @staticmethod
        def match_font(_family):
            return None

        @staticmethod
        def Font(_path, size):
            return FakeFont(size)


def estimate(frame, label: str) -> None:
    from src.spacehack import pygame_split

    fake = FakePygame()
    font = pygame_split._fit_font(fake, frame, 1600, 960)
    left = len(frame.left_rows)
    right = len(frame.right_rows)
    div_l = sum(1 for r in frame.left_rows if r.divider)
    div_r = sum(1 for r in frame.right_rows if r.divider)
    # Worst-case wrapped detail lines at the CHOSEN size.
    width = (1600 - 64 - 20) // 2
    measure = lambda t: FakeFont(font.point_size).size(t)[0]
    from src.spacehack import pygame_ui

    rows = (*frame.left_rows, *frame.right_rows)
    detail_lines = pygame_ui.max_wrapped_lines(
        (r.detail for r in rows if not r.divider),
        width - 68,
        measure,
    )
    height = pygame_split._frame_height(font, frame, 1600)
    print(
        f"{label:<28} font={font.point_size:>2}px  "
        f"left={left:>2} rows ({div_l} div)  right={right:>2} rows ({div_r} div)  "
        f"detail_lines={detail_lines}  height={height}"
    )


def main() -> None:
    from src.spacehack import ship as ship_module
    from src.spacehack.ship import OwnedShip

    owned = OwnedShip(
        ship_id="starter",
        weapons=("light_laser",),
        modules=(),
        fuel=12,
        hull_damage_pct=0,
    )
    base_ctx = SimpleNamespace(
        player_owned_ship=owned,
        stats=SimpleNamespace(credits=1000),
        economy_state={},
        faction_reputation={},
        log=SimpleNamespace(add=lambda _m: None),
        equipped_ground_weapons=[],
        equipped_ground_armor={},
    )

    # --- Mechanic Ship Loadout (real Earth mechanic inventory) ---
    from src.spacehack.menus import _loadout
    from src.spacehack.data.planets import resolve_mech_inventory
    from src.spacehack.data.modules import list_modules
    from src.spacehack.data.weapons import list_weapons

    weapon_ids, module_ids = resolve_mech_inventory("earth", 1)
    print(
        f"earth mech inventory: {len(weapon_ids)} weapons, {len(module_ids)} modules "
        f"(full catalog: {len(list_weapons())} weapons, {len(list_modules())} modules)"
    )
    estimate(
        _loadout._pygame_loadout_frame(base_ctx, "earth", weapon_ids, module_ids),
        "loadout (earth)",
    )
    # Full-catalog loadout (any planet without a fixed set can roll large).
    estimate(
        _loadout._pygame_loadout_frame(
            base_ctx, "earth",
            tuple(w.id for w in list_weapons()),
            tuple(m.id for m in list_modules()),
        ),
        "loadout (full catalog)",
    )

    # --- Armory ---
    from src.spacehack.menus import _armory

    estimate(_armory._pygame_armory_frame(base_ctx, "earth"), "armory (earth)")

    # --- Station Trade (Earth) ---
    from src.spacehack import trade
    from src.spacehack.data.planets import find_planet_spec
    from src.spacehack.data.trade_goods import neutral_goods

    spec = find_planet_spec("earth")
    goods: list[str] = []
    seen: set[str] = set()
    for gid, _t in spec.produces:
        if gid not in seen:
            goods.append(gid)
            seen.add(gid)
    for gid, _t in spec.demands:
        if gid not in seen:
            goods.append(gid)
            seen.add(gid)
    for gid in neutral_goods(spec):
        if gid not in seen:
            goods.append(gid)
            seen.add(gid)

    # Seed economy like open_trade does.
    trade._seed_economy(base_ctx, "earth")

    # Patch pricing so we don't need full ctx wiring.
    orig_unit = trade._unit_price
    orig_sell = trade._sell_price
    trade._unit_price = lambda _ctx, _planet, gid: find_trade_good_price(gid)
    trade._sell_price = lambda _ctx, _planet, gid: find_trade_good_price(gid)

    def find_trade_good_price(gid: str) -> int:
        from src.spacehack.data.trade_goods import find_trade_good

        return find_trade_good(gid).base_price

    estimate(trade._pygame_trade_frame(base_ctx, "earth", goods), "trade-earth")

    # --- NPC trade ---
    npc = SimpleNamespace(name="Trader")
    npc_stock = {gid: 3 for gid in goods[:6]}
    estimate(
        trade._pygame_npc_trade_frame(base_ctx, npc, npc_stock, 1.2, 0.5),
        "trade-npc",
    )

    trade._unit_price = orig_unit
    trade._sell_price = orig_sell

    # --- Selectable menu (mission board with a full contract list) ---
    from src.spacehack import pygame_menu, pygame_ui

    def estimate_menu() -> None:
        fake = FakePygame()
        frame = pygame_menu.MenuFrame(
            title="Guild Master - available work",
            body="Select a contract to review its details.",
            items=tuple(
                pygame_menu.MenuItem(
                    f"[Delivery] Deliver to {name}",
                    "Food crates for the colony. Cargo: 8 units, 12 days.",
                    str(index),
                )
                for index, name in enumerate((
                    "Mars", "Sirius", "Vega", "Procyon", "Wolf 359",
                    "Tau Ceti", "Barnard's Star", "Luyten",
                    "Groombridge", "Alpha Centauri",
                ))
            ),
            hints=(pygame_ui.modal_hint(
                pygame_ui.NAV_HINT, "ENTER accept", "ESC walk away",
                pygame_ui.GUIDE_HINT,
            ),),
            selected=0,
        )
        font = pygame_menu._fit_font(fake, (frame,), 1600, 960, reserve_log=True)
        height = pygame_menu._frame_height(
            font, frame, pygame_menu._content_width(1600),
        )
        label = "menu (mission board)"
        print(
            f"{label:<28} font={font.point_size:>2}px  "
            f"items={len(frame.items):>2}  "
            f"height={height}"
        )

    estimate_menu()

    # --- Text screen (cargo-like long list) ---
    from src.spacehack import pygame_screen

    def estimate_screen() -> None:
        fake = FakePygame()
        frame = pygame_screen.ScreenFrame(
            title="CARGO - SCOUT A",
            body=("Select an item to inspect it.",),
            rows=tuple(
                pygame_screen.ScreenRow(
                    f"Food Rations x{index}",
                    "Sustenance units. Edible.",
                    f"ROW:{index}",
                )
                for index in range(20)
            ),
            footer=(pygame_ui.modal_hint(
                pygame_ui.NAV_HINT, "ENTER use", "ESC back",
                pygame_ui.GUIDE_HINT,
            ),),
            selected=0,
        )
        font = pygame_screen._fit_font(fake, frame, 1600, 960, reserve_log=True)
        height = pygame_screen._layout_height(font, frame, 1520)
        label = "screen (cargo 20)"
        print(
            f"{label:<28} font={font.point_size:>2}px  "
            f"rows={len(frame.rows):>2}  "
            f"height={height}"
        )

    estimate_screen()

    # --- Reference: what row budget yields 24px? ---
    from src.spacehack import pygame_split

    for cap in (8, 9, 10, 11, 12):
        line = FakeFont(24).get_linesize()
        rows_h = cap * (line + 14)
        total = 150 + rows_h + 1 * (line + 2)
        print(f"24px budgeted frame height at {cap} visible rows/panel: {total}")


if __name__ == "__main__":
    main()
