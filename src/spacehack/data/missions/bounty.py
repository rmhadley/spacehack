"""Bounty-hunter guild missions: fugitive retrieval work.

Hand-crafted contracts offered by the Bounty Master NPC (guild `bhguild`).
Each entry pairs a custom target name with an enemy spec, target system,
squad size, and loadout upgrade level.

Procedural bounty generation is in :func:`spacehack.mission.generate_bounty_mission`.
"""

from . import MissionSpec


MISSIONS: tuple[MissionSpec, ...] = (
    # ------------------------------------------------------------------
    # Tier 1 — Solo bounties, low danger
    # ------------------------------------------------------------------
    MissionSpec(
        id="bhguild_sol_scout",
        title="Wanted: Crimson Jack",
        description=(
            "A known pirate scout operating out of Sol. The Bounty Guild "
            "wants Crimson Jack brought in - dead, preferably. "
            "Danger: Low."
        ),
        giver_npc_id="bounty_master",
        faction="bhguild",
        mission_type="bounty",
        tier=1,
        reward_credits=150,
        reward_xp=30,
        deadline_days=30,
        early_bonus_pct=25,
        target_enemy_id="pirate_scout",
        target_system_id="sol",
        bounty_target_name="Crimson Jack",
        bounty_target_squad_size=1,
        bounty_target_loadout_pct=20,
        origin_planet_id="earth",
    ),
    # ------------------------------------------------------------------
    # Tier 2 — Smugglers and fugitive haulers
    # ------------------------------------------------------------------
    MissionSpec(
        id="bhguild_ac_smuggler",
        title="Smuggler's Run",
        description=(
            "An outlawed smuggler has been spotted near Alpha Centauri "
            "running black-market weapons. Bring the smuggler to justice. "
            "Danger: Moderate."
        ),
        giver_npc_id="bounty_master",
        faction="bhguild",
        mission_type="bounty",
        tier=2,
        reward_credits=350,
        reward_xp=60,
        deadline_days=60,
        early_bonus_pct=30,
        target_enemy_id="pirate_raider",        target_system_id="alpha_centauri",
        bounty_target_name="The Smuggler",
        bounty_target_squad_size=1,
        bounty_target_loadout_pct=40,
        origin_planet_id=None,   # floats to any T2+ bounty board
    ),

    MissionSpec(
        id="bhguild_sirius_fugitive",
        title="Fugitive Hauler",
        description=(
            "A fugitive has fled to Sirius in a stolen hauler. "
            "Retrieve or destroy the vessel. "
            "Danger: Moderate."
        ),
        giver_npc_id="bounty_master",
        faction="bhguild",
        mission_type="bounty",
        tier=2,
        reward_credits=300,
        reward_xp=55,
        deadline_days=90,
        early_bonus_pct=25,
        target_enemy_id="pirate_raider",
        target_system_id="sirius",
        bounty_target_name="Fugitive Hauler",
        bounty_target_squad_size=1,
        bounty_target_loadout_pct=30,
        origin_planet_id=None,   # floats to any T2+ bounty board
    ),
    # ------------------------------------------------------------------
    # Tier 3 — Named threats, small squads
    # ------------------------------------------------------------------
    MissionSpec(
        id="bhguild_wolf_marauder",
        title="Wanted: Karrik the Red",
        description=(
            "Karrik the Red is wanted across three systems for piracy "
            "and murder. Last seen in Wolf 359. "
            "Danger: High."
        ),
        giver_npc_id="bounty_master",
        faction="bhguild",
        mission_type="bounty",
        tier=3,
        reward_credits=700,
        reward_xp=120,
        deadline_days=160,
        early_bonus_pct=30,
        target_enemy_id="pirate_raider",
        target_system_id="wolf_359",
        bounty_target_name="Karrik the Red",
        bounty_target_squad_size=1,
        bounty_target_loadout_pct=60,
        origin_planet_id=None,   # floats to any T3+ bounty board
    ),
    MissionSpec(
        id="bhguild_luyten_raider",
        title="The Luyten Raider",
        description=(
            "A heavily-armed raider and crew have been harassing "
            "shipping near Luyten's Star. "
            "Danger: High. Small squad expected."
        ),
        giver_npc_id="bounty_master",
        faction="bhguild",
        mission_type="bounty",
        tier=3,
        reward_credits=900,
        reward_xp=150,
        deadline_days=195,
        early_bonus_pct=30,
        target_enemy_id="pirate_raider",
        target_system_id="luyten_star",
        bounty_target_name="The Luyten Raider",
        bounty_target_squad_size=2,
        bounty_target_loadout_pct=70,
        origin_planet_id=None,   # floats to any T3+ bounty board
    ),
    # ------------------------------------------------------------------
    # Tier 4 — Boss-level, full squad
    # ------------------------------------------------------------------
    MissionSpec(
        id="bhguild_vega_dread",
        title="Wanted: Dread Captain Vol",
        description=(
            "Dread Captain Vol commands a pirate frigate in the Vega "
            "system. The Guild's most wanted - approach with extreme "
            "caution. Danger: Extreme. Full squad present."
        ),
        giver_npc_id="bounty_master",
        faction="bhguild",
        mission_type="bounty",
        tier=4,
        reward_credits=2000,
        reward_xp=350,
        deadline_days=60,
        early_bonus_pct=35,
        target_enemy_id="pirate_captain",
        target_system_id="vega",
        bounty_target_name="Dread Captain Vol",
        bounty_target_squad_size=3,
        bounty_target_loadout_pct=100,
        origin_planet_id=None,   # floats to any T4 bounty board
    ),
    # ------------------------------------------------------------------
    # Tier 4 — beyond the arms: warlords of the deep ends
    # ------------------------------------------------------------------
    MissionSpec(
        id="bhguild_ross_warlord",
        title="Wanted: Zenn the Emberglass",
        description=(
            "Zenn the Emberglass rules the Flare Crown garrison in Ross "
            "154 - the kingdom past Sirius. Every bounty hunter who "
            "crossed the star field to collect has fed the flares. "
            "Danger: Extreme. Warlord frigate, full escort."
        ),
        giver_npc_id="bounty_master",
        faction="bhguild",
        mission_type="bounty",
        tier=4,
        reward_credits=2800,
        reward_xp=450,
        deadline_days=200,
        early_bonus_pct=35,
        target_enemy_id="pirate_warlord",
        target_system_id="ross_154",
        bounty_target_name="Zenn the Emberglass",
        bounty_target_squad_size=4,
        bounty_wingmate_enemy_id="pirate_marauder",
        bounty_target_loadout_pct=100,
        origin_planet_id=None,   # floats to any T4 bounty board
    ),
    MissionSpec(
        id="bhguild_lalande_tollkeeper",
        title="The Tollkeeper of Lalande",
        description=(
            "The Tollkeeper holds the only gate into Lalande 21185 and "
            "charges every soul that passes - cargo, hull, or blood. The "
            "Guild has lost three collectives trying to crack the garrison. "
            "Danger: Extreme. Full marauder squad at his back."
        ),
        giver_npc_id="bounty_master",
        faction="bhguild",
        mission_type="bounty",
        tier=4,
        reward_credits=3000,
        reward_xp=480,
        deadline_days=280,
        early_bonus_pct=35,
        target_enemy_id="pirate_warlord",
        target_system_id="lalande_21185",
        bounty_target_name="The Tollkeeper",
        bounty_target_squad_size=3,
        bounty_wingmate_enemy_id="pirate_marauder",
        bounty_target_loadout_pct=100,
        origin_planet_id=None,   # floats to any T4 bounty board
    ),
)
