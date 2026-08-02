"""Merchant guild missions: trade and cargo work offered by the guild master.

All missions are delivery-type this iteration. Tiers 1-3, spanning
Earth, Mars, Alpha Centauri, Tau Ceti, Vega, Sirius, and Wolf 359.
"""
from . import MissionSpec


MISSIONS: tuple[MissionSpec, ...] = (
    # =============================================================
    # TIER 1 — Local deliveries (short hops, small cargo, quick turnaround)
    # =============================================================

    # Earth → Mars (same system, 0 jumps, beginner-friendly)
    MissionSpec(
        id="merchants_delivery_earth_mars",
        title="Deliver to Mars in Sol",
        description=(
            "The Mars colony is short on Earth-grown food rations. "
            "Five crates of hydroponic produce — load them up and "
            "run them to the Mars Barkeep. Same system, quick turnaround."
        ),
        giver_npc_id="guild_master",
        faction="merchants",
        mission_type="delivery",
        tier=1,
        reward_credits=100,
        reward_xp=20,
        deadline_days=30,
        early_bonus_pct=30,
        required_cargo_size=5,
        delivery_target_npc_id="barkeep",
        delivery_target_planet_id="mars",
        origin_planet_id="earth",
        recommended_class_id="merchant",
        recommended_ship_min_cargo=5,
    ),

    # Earth → AC Station (2 jumps, tier 1 difficulty since it's a well-traveled route)
    MissionSpec(
        id="merchants_delivery_earth_ac",
        title="Deliver to Science Port in Alpha Centauri",
        description=(
            "The Science Port at Alpha Centauri needs calibration "
            "gear and biologics. Ten crates — hand them to the "
            "xenolinguist on arrival. A two-jump trip through "
            "Barnard's Star."
        ),
        giver_npc_id="guild_master",
        faction="merchants",
        mission_type="delivery",
        tier=1,
        reward_credits=180,
        reward_xp=35,
        deadline_days=50,
        early_bonus_pct=25,
        required_cargo_size=10,
        delivery_target_npc_id="xenolinguist",
        delivery_target_planet_id="ac_station",
        origin_planet_id="earth",
        recommended_class_id="merchant",
        recommended_ship_min_cargo=10,
    ),

    # Earth → Barnard's Star b (1 jump, tier 1)
    MissionSpec(
        id="merchants_delivery_earth_barnards",
        title="Deliver to Barnard b in Barnard's Star",
        description=(
            "The mining outpost at Barnard's Star needs machine parts "
            "and filtration units. Eight crates, one jump. The depot "
            "attendant will sign for them."
        ),
        giver_npc_id="guild_master",
        faction="merchants",
        mission_type="delivery",
        tier=1,
        reward_credits=150,
        reward_xp=28,
        deadline_days=80,
        early_bonus_pct=25,
        required_cargo_size=8,
        delivery_target_npc_id="depot_attendant",
        delivery_target_planet_id="barnards_b",
        origin_planet_id="earth",
        recommended_class_id="merchant",
        recommended_ship_min_cargo=8,
    ),

    # =============================================================
    # TIER 2 — Regional deliveries (multi-hop, larger cargo, longer deadlines)
    # =============================================================

    # Earth → Sirius Station (3+ jumps, tier 2)
    MissionSpec(
        id="merchants_delivery_earth_sirius",
        title="Deliver to Binary Station in Sirius",
        description=(
            "The research station at Sirius needs precision instruments "
            "from Earth — fifteen crates of spectrometers, lenses, and "
            "vacuum-sealed electronics. A long haul through multiple "
            "systems. The Research Officer is expecting you."
        ),
        giver_npc_id="guild_master",
        faction="merchants",
        mission_type="delivery",
        tier=2,
        reward_credits=400,
        reward_xp=80,
        deadline_days=80,
        early_bonus_pct=25,
        required_cargo_size=15,
        delivery_target_npc_id="research_officer",
        delivery_target_planet_id="sirius_station",
        origin_planet_id="earth",
        recommended_class_id="merchant",
        recommended_ship_min_cargo=15,
    ),

    # Tau Ceti b → Vega b (tier 2, multi-hop)
    MissionSpec(
        id="merchants_delivery_tau_ceti_vega",
        title="Deliver to Vega b in Vega",
        description=(
            "The Cloud Host at Vega b has ordered luxury goods from "
            "the Tau Ceti guild — twelve crates of rare botanicals and "
            "artisan electronics. The floating platform above the gas "
            "giant is a long but rewarding run."
        ),
        giver_npc_id="salvage_specialist",
        faction="merchants",
        mission_type="delivery",
        tier=2,
        reward_credits=350,
        reward_xp=70,
        deadline_days=80,
        early_bonus_pct=25,
        required_cargo_size=12,
        delivery_target_npc_id="barkeep",
        delivery_target_planet_id="vega_b",
        origin_planet_id="tc_b",
        recommended_class_id="merchant",
        recommended_ship_min_cargo=12,
    ),

    # =============================================================
    # TIER 3 — Sector deliveries (long haul, heavy cargo, big payout)
    # =============================================================

    # Tau Ceti b → Wolf 359 b (long haul, tier 3)
    MissionSpec(
        id="merchants_delivery_tau_ceti_wolf",
        title="Deliver to Wolf 359 b in Wolf 359",
        description=(
            "The listening post at Wolf 359 is running critically low "
            "on food rations, fuel cells, and medical supplies. "
            "Twenty-five crates — the biggest haul the guild offers. "
            "The Frontier Operator will be grateful. Long trip, big payout."
        ),
        giver_npc_id="salvage_specialist",
        faction="merchants",
        mission_type="delivery",
        tier=3,
        reward_credits=650,
        reward_xp=130,
        deadline_days=60,
        early_bonus_pct=25,
        required_cargo_size=25,
        delivery_target_npc_id="depot_attendant",
        delivery_target_planet_id="wolf_b",
        origin_planet_id="tc_b",
        recommended_class_id="merchant",
        recommended_ship_min_cargo=25,
    ),
)
