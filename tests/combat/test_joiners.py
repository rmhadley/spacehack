"""Mid-fight joiners (doc 48 phase 7, SETTLED 21).

Ambient ships that aggro into a live fight build from their OWN spec
through the one enemy construction path — the old player-hull reads
fed a discarded player state and could drop legitimate joiners.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from src.spacehack import world
from src.spacehack.combat import _space_reinforce
from src.spacehack.data.npc_ships import find_npc_ship


def test_joiner_builds_from_its_own_spec_never_none():
    spec = find_npc_ship("pirate_hound")
    enemy = _space_reinforce._build_reinforcement_enemy(
        spec, world.Position(2, 2),
    )
    assert enemy is not None
    assert enemy.spec_id == "pirate_hound"
    assert enemy.name == spec.name
    assert enemy.band == spec.band
    assert enemy.hull > 0 and enemy.max_hull == enemy.hull
