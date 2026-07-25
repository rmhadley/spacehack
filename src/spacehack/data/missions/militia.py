"""Militia missions: patrol and retrieval work offered by the militia captain.

Both entries are flavor/filler for this iteration. Future combat
flavor (e.g. \"escort a cargo convoy\") would set
``required_cargo_size > 0`` plus ``delivery_target_*`` and inherit
the supply-run exemplar's behavior.
"""
from . import Mission


MISSIONS: tuple[Mission, ...] = (
    # ----- Flavor: a beat patrol (walk around and log unusual sights).
    Mission(
        id="militia_beat_patrol",
        title="Beat patrol",
        description=(
            "Walk a route through the lower wards, log anything "
            "unusual, report back. Pays quietly and on time."
        ),
        giver_npc_id="militia_captain",
        reward_gold=50,
        reward_xp=15,
        recommended_class_id="bounty_hunter",
    ),
    # ----- Flavor: lost property retrieval (a fetch quest flavor).
    Mission(
        id="militia_lost_property",
        title="Lost property retrieval",
        description=(
            "A crate of supplies vanished en route to a militia "
            "outpost. Find it. Return it. No questions asked."
        ),
        giver_npc_id="militia_captain",
        reward_gold=70,
        reward_xp=20,
        recommended_class_id="bounty_hunter",
    ),
)