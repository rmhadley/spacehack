"""Bar missions — shady pirate contracts offered by the Barkeep.

Intercept missions: track down a merchant vessel, destroy it, loot a
specific good, return to the bar and deliver it to the barkeep.

These are hand-crafted static missions. Procedural bar mission
generation is deferred to a later phase.
"""

from . import MissionSpec


MISSIONS: tuple[MissionSpec, ...] = (
    # Tier 1 — Alpha Centauri, easy merchant hauler
    MissionSpec(
        id="bar_intercept_earth_ac",
        title="The AC Run",
        description=(
            "A merchant hauler runs electronics between Earth and Alpha Centauri. "
            "Hit them in the AC system, grab their cargo, and bring it back here. "
            "Nobody will miss one hauler."
        ),
        giver_npc_id="barkeep",
        faction="bar",
        mission_type="intercept",
        tier=1,
        reward_credits=200,
        reward_xp=40,
        deadline_days=30,
        early_bonus_pct=25,
        target_enemy_id="merchant_hauler",
        target_system_id="alpha_centauri",
        heist_target_good_id="electronics",
    ),
    # Tier 2 — Vega, tougher hauler
    MissionSpec(
        id="bar_intercept_vega_components",
        title="Vega Components",
        description=(
            "A hauler in Vega is shipping machine parts to a militia outpost. "
            "We could use those parts ourselves. Intercept them, bring the "
            "components back to me. Watch out — they may have escorts."
        ),
        giver_npc_id="barkeep",
        faction="bar",
        mission_type="intercept",
        tier=2,
        reward_credits=400,
        reward_xp=70,
        deadline_days=40,
        early_bonus_pct=25,
        target_enemy_id="merchant_hauler",
        target_system_id="vega",
        bounty_target_squad_size=2,
        heist_target_good_id="machine_parts",
    ),
    # Tier 3 — Sirius, armed freighter
    MissionSpec(
        id="bar_intercept_sirius_luxury",
        title="Sirius Luxury",
        description=(
            "A merchant freighter running luxury goods through Sirius Station. "
            "Armed and alert. The cargo is worth a fortune — half for you, "
            "half for me. Bring back the luxury goods."
        ),
        giver_npc_id="barkeep",
        faction="bar",
        mission_type="intercept",
        tier=3,
        reward_credits=800,
        reward_xp=140,
        deadline_days=50,
        early_bonus_pct=25,
        target_enemy_id="merchant_freighter",
        target_system_id="sirius",
        bounty_target_squad_size=3,
        heist_target_good_id="luxury_goods",
    ),
    # Tier 4 — Luyten's Star, heavily armed caravan
    MissionSpec(
        id="bar_intercept_frontier_tech",
        title="Frontier Tech",
        description=(
            "Deep in Luyten's Star, a merchant caravan is transporting "
            "experimental electronics. They're armed to the teeth — this is "
            "the big one. Pull this off and you'll be set for months."
        ),
        giver_npc_id="barkeep",
        faction="bar",
        mission_type="intercept",
        tier=4,
        reward_credits=1800,
        reward_xp=300,
        deadline_days=60,
        early_bonus_pct=30,
        target_enemy_id="merchant_caravan",
        target_system_id="luyten_star",
        bounty_target_squad_size=4,
        bounty_target_loadout_pct=75,
        heist_target_good_id="electronics",
    ),
)
