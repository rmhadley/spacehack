"""Bounty-hunter guild missions: fugitive retrieval work offered by the bounty master.

One functional bounty this iteration — the pirate scout at Barnard's
Star. Add a new bounty by inserting a single :class:`Mission` entry
with ``target_enemy_id`` + ``target_system_id`` set; the runtime
layer auto-completes it on combat VICTORY.
"""
from . import Mission


MISSIONS: tuple[Mission, ...] = (
    # Functional bounty: pirate scout at Barnard's Star.
    # Instantly completes on combat VICTORY — no turn-in needed.
    Mission(
        id="bounty_pirate_scout",
        title="Bounty: pirate scout at Barnard's Star",
        description=(
            "A pirate scout is harassing shipping near Barnard's "
            "Star. Neutralize them. FTL bounty transfer confirmed "
            "on kill."
        ),
        giver_npc_id="bounty_master",
        reward_credits=200,
        reward_xp=40,
        recommended_class_id="bounty_hunter",
        target_enemy_id="pirate_scout",
        target_system_id="barnards_star",
    ),
)