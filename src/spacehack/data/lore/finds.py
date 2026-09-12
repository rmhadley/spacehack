"""Pads that teach (doc 42 phase 3, SETTLED 19).

A pad is a find — dropped beside a kill's loot — that teaches its
authored entry on pickup: knowledge IS the item, nothing goes to the
hold, nothing is sellable. Pads spawn only while their entry is
unheard at spawn time (``loot.maybe_spawn_pad`` reads the keyring).
"""

PADS: tuple[tuple[str, str], ...] = (
    # (enemy npc-ship id, taught rumor id)
    ("pirate_raider", "dark_berth_1"),
    ("derelict_freighter", "dark_berth_1"),
)


def pad_for(enemy_id: str) -> str | None:
    """The rumor id a killed enemy's pad teaches, or None."""
    for _enemy, _rumor_id in PADS:
        if _enemy == enemy_id:
            return _rumor_id
    return None
