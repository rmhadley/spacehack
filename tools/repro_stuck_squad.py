"""Watch the tau_ceti squad flow after the cohesion fix.

Squad proc_solo_tau_ceti_pirate_scout_80919 (from the user's save):
4 pirate scouts at (135,102), (135,103), (135,101), (154,102),
target (58,46). Runs move_npcs ticks and prints positions so the
former freeze (3 healthy members + 1 wedged against planet tc_d)
is visibly resolved.
"""
import sys
sys.path.insert(0, ".")
from types import SimpleNamespace

from src.spacehack import npc_ships, solar_system as ss, world
from src.spacehack.data.npc_ships import find_npc_ship as _find_npc_ship
from src.spacehack.data.solar_systems import find_solar_system
from src.spacehack.engine import RNG

SPEC = find_solar_system("tau_ceti")
SQUAD = "proc_solo_tau_ceti_pirate_scout_80919"
POSITIONS = [(135, 102), (135, 103), (135, 101), (154, 102)]
TARGET = (58, 46)
PLAYER = (144, 119)


def build_state() -> tuple[world.GameMap, SimpleNamespace]:
    ss.set_current_solar_system("tau_ceti")
    game_map = ss.make_solar_system(system=SPEC)
    spec = _find_npc_ship("pirate_scout")
    for x, y in POSITIONS:
        game_map.entities.append(world.Entity(
            char=spec.char, fg=spec.fg, pos=world.Position(x, y),
            name=spec.name, width=1, height=1,
            npc_ship_id=spec.id,
            procedural_squad_id=SQUAD,
        ))
    player = world.Entity(
        "@", (255, 255, 255), world.Position(*PLAYER),
        "Player", owned=True,
    )
    game_map.entities.append(player)
    ctx = SimpleNamespace(
        player=player,
        log=SimpleNamespace(add=lambda _m: None, add_colored=lambda _m, _c: None),
        procedural_spawns={"tau_ceti": []},
        npc_targets={SQUAD: TARGET},
        npc_paths={},
        npc_flash_events=[],
    )
    return game_map, ctx


def members(game_map):
    return [
        e for e in game_map.entities
        if getattr(e, "procedural_squad_id", "") == SQUAD
    ]


def main() -> None:
    RNG.seed(1234)
    npc_ships.main_quest_module = SimpleNamespace(
        consortium_heat_active=lambda _ctx: False,
        charged_cell_in_sol=lambda _ctx, _sid: False,
    )
    game_map, ctx = build_state()
    print("tick  positions                        centre")
    ms = members(game_map)
    for t in range(26):
        pos = [(m.pos.x, m.pos.y) for m in ms]
        cx = sum(p[0] for p in pos) // len(pos)
        cy = sum(p[1] for p in pos) // len(pos)
        print(f"{t:4d}  {pos}  ({cx},{cy})")
        if t < 25:
            npc_ships.move_npcs(ctx, game_map)


if __name__ == "__main__":
    main()
