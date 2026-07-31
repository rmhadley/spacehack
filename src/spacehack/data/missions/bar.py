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
        # Round trip at starter speed (10 moves/day) is ~41 days:
        # Earth->gate 6d, AC gate->landmark 14d, then back again.
        # Deadline ~2.2x RT so both on-time AND the early bonus
        # (< deadline/2 = 45d) are achievable; faster ships get slack.
        deadline_days=90,
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
        # Round trip to Vega ~32 days at starter speed. Deadline ~2.2x
        # RT: early bonus (< 35d) reachable at starter speed.
        deadline_days=70,
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
        # Round trip to Sirius is 2 hops ~69 days at starter speed
        # (cross Vega gate-to-gate). Deadline ~2.2x RT so the early
        # bonus (< 75d) is achievable; generous for a deep run.
        deadline_days=150,
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
        # Round trip to Luyten's Star is 5 hops ~169 days at starter
        # speed (10 jumps, needs a refuel stop). Deadline ~2.1x RT so
        # the early bonus (< 180d) is achievable; very generous for
        # the deep-space run.
        deadline_days=360,
        early_bonus_pct=30,
        target_enemy_id="merchant_caravan",
        target_system_id="luyten_star",
        bounty_target_squad_size=4,
        bounty_target_loadout_pct=75,
        heist_target_good_id="electronics",
    ),
)
