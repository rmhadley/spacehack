"""Bounty-hunter guild missions: fugitive retrieval work offered by the bounty master.

Both entries are flavor/filler for this iteration. Combat-flavored
flavor missions (no actual bounty hooks wired yet) keep the
standard shape: ``required_cargo_size=0`` and no delivery target.
A future combat-hook mission type would add new fields to
:class:`Mission` and a new runtime helper in :mod:`spacehack.mission`.
"""
from . import Mission


MISSIONS: tuple[Mission, ...] = (
    # ----- Flavor: a smuggler chase (combat hook TBD).
    Mission(
        id="bounty_smuggler_at_large",
        title="Bounty: a smuggler at large",
        description=(
            "A repeat offender is using the outer belt to dodge "
            "duties. Bring them in. Alive preferred, not required."
        ),
        giver_npc_id="bounty_master",
        reward_gold=180,
        reward_xp=30,
        recommended_class_id="bounty_hunter",
    ),
    # ----- Flavor: a deserter hunt (combat hook TBD).
    Mission(
        id="bounty_deserter",
        title="Bounty: locate the deserter",
        description=(
            "A former crewmember skipped on a debt. Find them. "
            "Recover the mark or the money - whichever is cleaner."
        ),
        giver_npc_id="bounty_master",
        reward_gold=120,
        reward_xp=35,
        recommended_class_id="bounty_hunter",
    ),
)