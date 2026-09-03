#!/usr/bin/env python3
"""Smoke test entry points to verify import correctness and signature shapes.

If invoked outside a virtual environment, re-executes via
``.venv/bin/python3`` when that environment exists. Otherwise it uses the
current interpreter, which keeps the gate usable in clean CI environments.

Pass: prints ``PASS: Smoke tests OK.`` and exits 0.
Fail: prints ``FAIL: <reason>`` to stderr and exits 1.

Run from the project root:

    python3 tools/smoke.py

This is the canonical pattern for verifying the supported Pygame runtime
can import the game domain without the retired backend installed.
"""
import os
import subprocess
import sys
from pathlib import Path


def _ensure_venv() -> None:
    """Re-launch using the project venv if not already running in one.

    Compares ``sys.prefix`` against ``sys.base_prefix`` -- they diverge
    when the interpreter is inside a virtualenv. Bare ``python3`` has
    them equal, so we replace the process with the venv Python when
    ``.venv/bin/python3`` exists; otherwise the current interpreter is
    retained for clean-environment and CI use.
    """
    if sys.prefix != sys.base_prefix:
        return
    venv_py = Path(__file__).resolve().parent.parent / ".venv" / "bin" / "python3"
    if venv_py.exists():
        os.execv(str(venv_py), [str(venv_py), __file__, *sys.argv[1:]])


def _assert_backend_independence(root: Path) -> bool:
    """Import the installed package while blocking the retired backend."""
    script = """
import importlib.abc
import sys
blocked_name = "t" + "cod"
class BackendBlocker(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname, path=None, target=None):
        if fullname == blocked_name or fullname.startswith(blocked_name + "."):
            raise ImportError("retired backend blocked")
        return None
sys.meta_path.insert(0, BackendBlocker())
import spacehack.__main__
"""
    environment = os.environ.copy()
    source_path = str(root / "src")
    existing_path = environment.get("PYTHONPATH")
    environment["PYTHONPATH"] = (
        source_path
        if not existing_path
        else os.pathsep.join((source_path, existing_path))
    )
    result = subprocess.run(
        [sys.executable, "-c", script],
        capture_output=True,
        text=True,
        check=False,
        env=environment,
    )
    if result.returncode == 0:
        return True
    detail = (result.stderr or result.stdout).strip()
    print(f"FAIL: clean import check failed: {detail}", file=sys.stderr)
    return False


def smoke_test() -> int:
    _ensure_venv()

    # Make src/ importable regardless of cwd.
    root = Path(__file__).resolve().parent.parent
    sys.path.insert(0, str(root))

    if not _assert_backend_independence(root):
        return 1

    try:
        from src.spacehack import (
            character,
            combat,
            game_context,
            hud,
            main_quest,
            message_log,
            mission,
            npc,
            ship,
            solar_system,
            ui,
            world,
        )
    except ModuleNotFoundError as exc:
        print(f"FAIL: import error during smoke test: {exc}", file=sys.stderr)
        return 1

    # Verify key entry points survived their respective refactors.
    checks = [
        (combat, "_handle_combat_encounter"),
        (combat, "run_combat"),
        (game_context, "GameContext"),
        (world, "GameMap"),
        (world, "MOVE_KEYS"),
    ]
    for mod, attr in checks:
        if not hasattr(mod, attr):
            print(f"FAIL: {mod.__name__}.{attr} is missing.", file=sys.stderr)
            return 1

    # Main quest infra (docs/design/in_progress/07_DESIGN_MAIN_QUEST.md):
    # runtime entry points + the data catalog's step chain integrity.
    _mq_checks = [
        (main_quest, "resolve_npc_dialogue"),
        (main_quest, "trigger_dialogue"),
        (main_quest, "quest_option_for"),
        (main_quest, "maybe_trigger_signal"),
        (main_quest, "show_prologue_transmission"),
        (main_quest, "show_sealed_door_overlay"),
        (main_quest, "show_help_offer"),
        (main_quest, "mars_exploration_unlocked"),
        (main_quest, "prepare_mars_surface"),
        (main_quest, "bump_mars_door"),
        (main_quest, "current_main_quest_objective"),
        (main_quest, "secure_quest_loot"),
        (main_quest, "maybe_complete_visit"),
        (main_quest, "maybe_complete_bounty"),
        (main_quest, "prepare_delve_site"),
        (main_quest, "delve_site_unlocked"),
        (main_quest, "surface_exploration_unlocked"),
        (main_quest, "check_quest_gates"),
        (main_quest, "show_quest_summon"),
        (main_quest, "show_quest_readout"),
        (main_quest, "show_gate_popup"),
        (main_quest, "maybe_continue_chain"),
        (main_quest, "seat_quest_npcs_in_interior"),
        (main_quest, "play_scene"),
        (main_quest, "registered_scene_ids"),
    ]
    for mod, attr in _mq_checks:
        if not hasattr(mod, attr):
            print(f"FAIL: main_quest.{attr} is missing.", file=sys.stderr)
            return 1
    # Dataclass fields with default_factory are NOT set as class
    # attributes, so use dataclasses.fields() rather than hasattr.
    import dataclasses as _dc
    _mq_fields = [
        "main_quest_progress",
        "main_quest_unlocked_items",
        "main_quest_path",
        "main_quest_backing",
        "main_quest_chain",
        "main_quest_gate",
        "main_quest_pending_message",
        "main_quest_complete",
    ]
    _ctx_field_names = {f.name for f in _dc.fields(game_context.GameContext)}
    for _f in _mq_fields:
        if _f not in _ctx_field_names:
            print(
                f"FAIL: GameContext.{_f} is missing (save/load contract).",
                file=sys.stderr,
            )
            return 1
    # Step-chain integrity: every requires_step must exist; every
    # dialogue npc_id must resolve; option rows need trigger_on_talk.
    from src.spacehack.data.main_quest import list_main_quest_steps
    from src.spacehack.data.npcs import find_npc
    _mq_steps = list_main_quest_steps()
    _mq_ids = {s.id for s in _mq_steps}
    if not _mq_steps:
        print("FAIL: main quest catalog is empty.", file=sys.stderr)
        return 1
    for _s in _mq_steps:
        if _s.requires_step and _s.requires_step not in _mq_ids:
            print(
                f"FAIL: main quest step {_s.id!r} requires unknown "
                f"step {_s.requires_step!r}.",
                file=sys.stderr,
            )
            return 1
        if _s.unlocks_step and _s.unlocks_step not in _mq_ids:
            print(
                f"FAIL: main quest step {_s.id!r} unlocks unknown "
                f"step {_s.unlocks_step!r}.",
                file=sys.stderr,
            )
            return 1
        for _npc_id, _d in _s.dialogues.items():
            try:
                find_npc(_npc_id)
            except KeyError:
                print(
                    f"FAIL: main quest step {_s.id!r} dialogue references "
                    f"unknown npc {_npc_id!r}.",
                    file=sys.stderr,
                )
                return 1
            if _d.option_label and not _d.trigger_on_talk:
                # Visit steps are an exception: they use the quest option
                # row but the step is completed inside trigger_dialogue
                # (via the visit/complete path), not via trigger_on_talk.
                if _s.objective_type != "visit":
                    print(
                        f"FAIL: main quest step {_s.id!r} dialogue for "
                        f"{_npc_id!r} has option_label but no trigger_on_talk.",
                        file=sys.stderr,
                    )
                    return 1
            if _d.locks_chain and not _d.backing_faction:
                print(
                    f"FAIL: main quest step {_s.id!r} dialogue for "
                    f"{_npc_id!r} locks_chain without backing_faction.",
                    file=sys.stderr,
                )
                return 1

    # Verify the merged movement table covers vim + arrows + numpad
    # and that each maps to the expected delta.
    _move_checks = {
        "h": (-1, 0), "j": (0, 1), "k": (0, -1), "l": (1, 0),  # vim cardinals
        "y": (-1, -1), "u": (1, -1), "b": (-1, 1), "n": (1, 1),  # vim diagonals
        "up": (0, -1), "down": (0, 1), "left": (-1, 0), "right": (1, 0),  # arrows
        "kp_7": (-1, -1), "kp_8": (0, -1), "kp_9": (1, -1),       # numpad NW/N/NE
        "kp_4": (-1, 0), "kp_6": (1, 0),                            # numpad W/E
        "kp_1": (-1, 1), "kp_2": (0, 1), "kp_3": (1, 1),           # numpad SW/S/SE
    }
    for _key, _expected in _move_checks.items():
        if world.MOVE_KEYS.get(_key) != _expected:
            print(
                f"FAIL: world.MOVE_KEYS[{_key!r}] = "
                f"{world.MOVE_KEYS.get(_key)!r}, expected {_expected!r}.",
                file=sys.stderr,
            )
            return 1

    # Delve-site data (phase 1d): the four delve planets must carry
    # planet-themed dungeon_params (the chain-aware planet-menu gate
    # hides their "Explore caves" option otherwise).
    # Future-proof (vacuous until 1e-1h authors the q2 steps): any
    # ``delve`` step must name its planet via trigger_planet_id and
    # hold well-formed (good_id, qty) delve_good_ids that resolve.
    from src.spacehack.data.trade_goods import find_trade_good as _ftg
    for _s in _mq_steps:
        if _s.objective_type != "delve":
            continue
        if not _s.trigger_planet_id:
            print(
                f"FAIL: delve step {_s.id!r} lacks trigger_planet_id.",
                file=sys.stderr,
            )
            return 1
        for _gid, _qty in _s.delve_good_ids:
            try:
                _ftg(_gid)
            except KeyError:
                print(
                    f"FAIL: delve step {_s.id!r} cache good {_gid!r} "
                    "is not a trade good.",
                    file=sys.stderr,
                )
                return 1
    from src.spacehack.data.planets import find_planet_spec as _fps
    for _pid in ("mercury", "wolf_b", "barnards_b", "proc_planet_2"):
        try:
            _pspec = _fps(_pid)
        except KeyError:
            print(
                f"FAIL: delve planet {_pid!r} missing from planet registry.",
                file=sys.stderr,
            )
            return 1
        if getattr(_pspec, "dungeon_params", None) is None:
            print(
                f"FAIL: delve planet {_pid!r} has no dungeon_params.",
                file=sys.stderr,
            )
            return 1

    # Quest-NPC presence (Phase 3): the faction experts are ADDITIVE
    # city NPCs — every ``npc_presence`` tag must resolve to a catalog
    # NPC AND have a ``quest_npc_spot`` on some planet, and every
    # spot must name an existing guild building. Otherwise a quest
    # NPC never appears (soft-lock: the step's delivery/visit target
    # is unreachable) or spawns nowhere.
    from src.spacehack.data.planets import list_planet_specs as _list_pspecs
    _spotted_npcs: set[str] = set()
    for _pspec in _list_pspecs():
        for _nid, _label in getattr(_pspec, "quest_npc_spots", ()) or ():
            _spotted_npcs.add(_nid)
            if not any(
                b.label == _label and b.npc_id for b in _pspec.buildings
            ):
                print(
                    f"FAIL: planet {_pspec.id!r} quest spot {_nid!r} "
                    f"names {_label!r}, which is not a guild building.",
                    file=sys.stderr,
                )
                return 1
    for _s in _mq_steps:
        for _nid in _s.npc_presence:
            try:
                find_npc(_nid)
            except KeyError:
                print(
                    f"FAIL: quest npc {_nid!r} (presence on {_s.id!r}) "
                    "missing from catalog.",
                    file=sys.stderr,
                )
                return 1
            if _nid not in _spotted_npcs:
                print(
                    f"FAIL: quest npc {_nid!r} (presence on {_s.id!r}) "
                    "has no quest_npc_spot on any planet.",
                    file=sys.stderr,
                )
                return 1

    # Scene ids (Phase 3): every step's ``scene`` must resolve in the
    # scene registry — an unregistered id would raise in-game instead
    # of silently skipping a narrative beat.
    from src.spacehack.main_quest import _scenes as _mq_scenes
    _scene_ids = _mq_scenes.registered_scene_ids()
    for _s in _mq_steps:
        if _s.scene and _s.scene not in _scene_ids:
            print(
                f"FAIL: step {_s.id!r} references unregistered scene "
                f"{_s.scene!r}.",
                file=sys.stderr,
            )
            return 1

    # Time-gate data (phase 1d): every step with a minimum-wait gate
    # must carry the completion flavor + the one-way summon message
    # that names the NEXT step's location (the check_quest_gates hook
    # delivers it).
    for _s in _mq_steps:
        if _s.wait_days > 0:
            if not _s.completion_flavor:
                print(
                    f"FAIL: gated step {_s.id!r} lacks completion_flavor.",
                    file=sys.stderr,
                )
                return 1
            if not _s.ready_message:
                print(
                    f"FAIL: gated step {_s.id!r} lacks ready_message.",
                    file=sys.stderr,
                )
                return 1

    # Mission-integrity (phase 1d): every static mission's giver and
    # delivery-target NPC ids must resolve to the catalog. Slot
    # replacements (expert NPCs) change board keys — a stale
    # giver/delivery id silently orphans the mission or makes it
    # uncompletable, so resolve them all here.
    from src.spacehack.data.missions import list_missions as _list_missions
    for _m in _list_missions():
        for _role, _nid in (("giver", _m.giver_npc_id), ("delivery target", _m.delivery_target_npc_id)):
            if not _nid:
                continue
            try:
                find_npc(_nid)
            except KeyError:
                print(
                    f"FAIL: mission {_m.id!r} {_role} npc {_nid!r} "
                    "missing from catalog.",
                    file=sys.stderr,
                )
                return 1

    # Procedural target-integrity: procedural delivery/smuggle target
    # NPCs are picked from planet building npc_id slots. Every slot
    # must resolve either through the planet's npc_overrides or the
    # global catalog, or generated missions point at NPCs that can
    # never be talked to (soft-lock: cargo reserved forever).
    from src.spacehack.data.planets import list_planet_specs as _list_pspecs
    for _pspec in _list_pspecs():
        _override_ids = [o for o, _n in getattr(_pspec, "npc_overrides", ()) or ()]
        for _b in _pspec.buildings:
            if not _b.npc_id:
                continue
            if _b.npc_id in _override_ids:
                continue  # resolves through a planet-local override
            try:
                find_npc(_b.npc_id)
            except KeyError:
                print(
                    f"FAIL: planet {_pspec.id!r} building slot {_b.npc_id!r} "
                    "resolves to no NPC (no override, not in catalog).",
                    file=sys.stderr,
                )
                return 1

    # Dev skip-days helper (Shift+D) must exist for gate playtests.
    from src.spacehack.input_helpers import _is_shift_d_press
    assert callable(_is_shift_d_press)

    # Validate the jump-gate graph: every gate's connects_to
    # target must exist and be bidirectional.
    from src.spacehack.data.solar_systems import validate_gate_graph
    gate_errors = validate_gate_graph()
    if gate_errors:
        for err in gate_errors:
            print(f"GATE ERROR: {err}", file=sys.stderr)
        print(
            f"FAIL: {len(gate_errors)} gate graph error(s).",
            file=sys.stderr,
        )
        return 1

    print("PASS: Smoke tests OK.")
    return 0


if __name__ == "__main__":
    sys.exit(smoke_test())
