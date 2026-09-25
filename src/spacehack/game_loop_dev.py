"""Dev-mode Shift-key shortcuts for the main gameplay loop.

Extracted from game_loop (doc 51 phase 2's ratchet payment): the
Shift-key dev table and its handlers live here; game_loop re-imports
``_handle_dev_shift_keys`` (called from ``_handle_dev_event``) and
``_is_dev``. Import direction is one-way — game_loop imports this
module; nothing here may import game_loop.
"""
from __future__ import annotations
from .input_helpers import _is_shift_x_press, _is_shift_t_press, _is_shift_s_press, _is_shift_r_press, _is_shift_d_press, _is_shift_l_press, _is_shift_g_press, _is_shift_k_press, _is_shift_j_press, _is_shift_b_press, _is_shift_n_press, _is_shift_m_press, _is_shift_y_press, _is_shift_v_press, _is_shift_p_press, _is_shift_c_press, _is_shift_w_press
from .dev_mode import dump_ground_weapon_sets
from .xp import add_xp as _add_xp


def _is_dev():
    """Return True when the SPACEHACK_DEV env var is set."""
    import os as _os
    return bool(_os.environ.get('SPACEHACK_DEV'))


def _reveal_all_fog(game_map, log):
    """Reveal every cell in the fog-of-war arrays."""
    if game_map.seen is not None:
        for row in game_map.seen:
            for i in range(len(row)):
                row[i] = True
    if game_map.visible is not None:
        for row in game_map.visible:
            for i in range(len(row)):
                row[i] = True
    log.add('Dev: fog of war fully revealed.')


async def _dev_city_teleport(state) -> None:
    """Dev-only: pick any port city from a menu and land there (Shift+T)."""
    from .dev_mode import choose_city_teleport as _choose
    _outcome, _pid = await _choose(state.ctx.context)
    if _pid is None:
        state.log.add('Dev: city teleport cancelled.')
        return
    from .game_interactions import land_at_city as _land
    await _land(state, _pid)
    if state.current_mode == 'city':
        state.log.add(f'[DEV MODE] Teleported to {_pid}.')


async def _dev_add_xp(state):
    """Shift+X: 200 XP."""
    await _add_xp(state.ctx, 200)


async def _dev_reroll_seed(state):
    """Shift+S: reroll the run seed mid-session."""
    from .engine import reroll_run_seed
    state.log.add(f'[DEV MODE] Run seed rerolled: {reroll_run_seed()}')


async def _dev_reveal_fog(state):
    """Shift+R: reveal all dungeon fog (dungeon mode only)."""
    if state.current_mode == 'dungeon':
        _reveal_all_fog(state.game_map, state.log)


async def _dev_skip_days(state):
    """Shift+D: skip 30 days of world clock."""
    from .time import advance_time as _adv_time
    _adv_time(state.ctx, 30)
    state.log.add('Dev: skipped 30 days.')


async def _dev_grant_manifest(state):
    """Shift+L: grant the blockade manifest marker (doc 41)."""
    from .dev_mode import apply_dev_blockade_manifest as _grant
    _grant(state.ctx)


async def _dev_grant_service_run(state):
    """Shift+K: grant the service-run marker (doc 41)."""
    from .dev_mode import apply_dev_service_run as _grant
    _grant(state.ctx)


async def _dev_grant_warrant_license(state):
    """Shift+G: grant the warrant-license perk (doc 42 playtest)."""
    from .dev_mode import apply_dev_warrant_license as _grant
    _grant(state.ctx)


async def _dev_advance_to_boundary(state):
    """Shift+J: advance the clock to the next shift boundary (doc 41)."""
    from .dev_mode import advance_to_shift_boundary as _advance
    _advance(state.ctx)


async def _dev_toggle_cutout(state):
    """Shift+B: toggle the transponder cut-out (doc 42 playtest)."""
    from .dev_mode import toggle_dev_cutout as _toggle
    _toggle(state.ctx)


async def _dev_log_rumor_routing(state):
    """Shift+N: log the run's live rumor routing (doc 42 phase 3)."""
    from .dev_mode import log_rumor_routing as _log_routes
    _log_routes(state.ctx)


async def _dev_reveal_dig_site(state):
    """Shift+M: force-reveal a dig site (doc 42 phase 4 checklist)."""
    from .dev_mode import reveal_dev_dig_site
    await reveal_dev_dig_site(state.ctx)


async def _dev_grant_tinker_kit(state):
    """Shift+Y: grant a full tinker-kit stack (doc 47 phase 5)."""
    from .dev_mode import apply_dev_tinker_kit
    apply_dev_tinker_kit(state.ctx)


async def _dev_spawn_enemy_faces(state):
    """Shift+V: spawn the phase-4 faces beside the player (doc 48.4)."""
    from .dev_mode import spawn_dev_enemy_faces
    if state.current_mode == 'dungeon':
        spawn_dev_enemy_faces(
            state.ctx, state.game_map, state.player.pos,
        )


async def _dev_spawn_pirate_ship(state):
    """Shift+P: spawn the next pirate spec beside the player (doc 48.7)."""
    from .dev_mode import spawn_dev_pirate
    if state.current_mode == 'space':
        spawn_dev_pirate(
            state.ctx, state.game_map, state.player.pos,
        )


async def _dev_spawn_consumable_carriers(state):
    """Shift+C: spawn pre-stamped consumable carriers (doc 48.5)."""
    from .dev_mode import spawn_dev_consumable_carriers
    if state.current_mode == 'dungeon':
        spawn_dev_consumable_carriers(
            state.ctx, state.game_map, state.player.pos,
        )


# Table-driven dispatch (knowledge.md guardrail): matcher -> action.
# Every action runs SPACEHACK_DEV-gated; mode guards live in the action.
_DEV_SHIFT_KEYS = (
    (_is_shift_x_press, _dev_add_xp),
    (_is_shift_t_press, _dev_city_teleport),
    (_is_shift_s_press, _dev_reroll_seed),
    (_is_shift_r_press, _dev_reveal_fog),
    (_is_shift_d_press, _dev_skip_days),
    (_is_shift_l_press, _dev_grant_manifest),
    (_is_shift_g_press, _dev_grant_warrant_license),
    (_is_shift_k_press, _dev_grant_service_run),
    (_is_shift_j_press, _dev_advance_to_boundary),
    (_is_shift_b_press, _dev_toggle_cutout),
    (_is_shift_n_press, _dev_log_rumor_routing),
    (_is_shift_m_press, _dev_reveal_dig_site),
    (_is_shift_y_press, _dev_grant_tinker_kit),
    (_is_shift_v_press, _dev_spawn_enemy_faces),
    (_is_shift_p_press, _dev_spawn_pirate_ship),
    (_is_shift_c_press, _dev_spawn_consumable_carriers),
    (_is_shift_w_press, dump_ground_weapon_sets),
)


async def _handle_dev_shift_keys(state, event):
    """Shift-key dev shortcuts; ``None`` when the key is not one of ours."""
    for _matches, _action in _DEV_SHIFT_KEYS:
        if _matches(event):
            if _is_dev():
                await _action(state)
            return 'HANDLED'
    return None
