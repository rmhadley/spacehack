"""Bar missions: city rumours and odd jobs offered by the barkeep.

The barkeep is the lowest-stakes quest-giver - his missions are
flavor/filler for this iteration. They pay small gold/xp, have no
cargo, and don't gate on class or ship. Future iterations can
extend these into a real bar-room rumor tree (e.g. a follow-up
delivery or a multi-step investigation) without touching the
data model - just add :attr:`Mission.delivery_target_*` fields
and the runtime layer will pick the mission up.
"""
from . import Mission


MISSIONS: tuple[Mission, ...] = (
    # ----- Flavor: a routine delivery (mentioned by the barkeep as
    #          \"a small but time-sensitive cargo drop\" but no cargo
    #          actually loads - just flavor text + reward).
    Mission(
        id="bar_routine_delivery",
        title="A routine delivery",
        description=(
            "A small but time-sensitive cargo drop across the next "
            "system. No escort, no danger - just don't be late."
        ),
        giver_npc_id="barkeep",
        reward_gold=60,
        reward_xp=10,
        recommended_class_id=None,
        recommended_ship_min_cargo=20,
    ),
    # ----- Flavor: a back-alley debt dispute (dialogue-only).
    Mission(
        id="bar_back_alley_dispute",
        title="A back-alley dispute",
        description=(
            "Two regulars are arguing over a debt. Talk to both, "
            "settle it quietly, keep it out of the militia's ears."
        ),
        giver_npc_id="barkeep",
        reward_gold=40,
        reward_xp=15,
        recommended_class_id=None,
    ),
)