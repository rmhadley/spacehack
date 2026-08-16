"""Bar missions — shady pirate contracts offered by the Barkeep.

Intercept missions: track down a merchant vessel, destroy it, loot a
specific good, return to the bar and deliver it to the barkeep.

Smuggling missions: transport contraband cargo to a destination NPC.
The cargo is loaded into the MISSION CARGO hold on accept; militia
cargo scans can confiscate it (the Smuggler's Hold module conceals
cargo from scans).

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
        # Solo target: the hauler flies unescorted. (The mixed-squad
        # escort mechanic stays available for future intercepts via
        # bounty_wingmate_enemy_id — see design doc.)
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
            "components back to me. Watch out - they may have escorts."
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
            "Armed and alert. The cargo is worth a fortune - half for you, "
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
            "experimental electronics. They're armed to the teeth - this is "
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
    # --- Smuggling ---
    # Tier 1 — Mars, same-system hot cargo. 8 units fits a mk1 hold (10).
    MissionSpec(
        id="bar_smuggle_mars_weapons",
        title="Mars Weapons Run",
        description=(
            "A crate of black-market side-arms needs to reach the Mars "
            "Barkeep. The colony patrol scans incoming freight - fly "
            "quiet, or pay the price."
        ),
        giver_npc_id="barkeep",
        faction="bar",
        mission_type="smuggling",
        tier=1,
        reward_credits=150,
        reward_xp=25,
        # Same-system run (~20-30 days at starter speed). Deadline
        # leaves room to orbit past the militia patrol on Mars.
        deadline_days=45,
        early_bonus_pct=25,
        required_cargo_size=8,
        delivery_target_npc_id="barkeep",       # Mars Barkeep override
        delivery_target_planet_id="mars",
        origin_planet_id="earth",
        is_smuggle=True,
        smuggle_good_id="weapons_blackmarket",
    ),
    # Tier 2 — Sirius Station, 2 hops. 15 units fits a mk2 hold (25).
    MissionSpec(
        id="bar_smuggle_sirius_tech",
        title="Sirius Black-Tech",
        description=(
            "Experimental electronics, no questions asked. The Binary "
            "Observer at the research station pays well for hardware that "
            "fell off the back of a freighter. Sirius is patrolled - "
            "mind the scans."
        ),
        giver_npc_id="barkeep",
        faction="bar",
        mission_type="smuggling",
        tier=2,
        reward_credits=350,
        reward_xp=60,
        # 2 hops (~35 days one-way at starter speed) + detour slack.
        deadline_days=90,
        early_bonus_pct=25,
        required_cargo_size=15,
        delivery_target_npc_id="research_officer",  # Binary Observer
        delivery_target_planet_id="sirius_station",
        origin_planet_id=None,   # floats to any T2+ bar
        is_smuggle=True,
        smuggle_good_id="electronics",
    ),
    # Tier 3 — Vega b, 1 hop. 30 units fits a mk3 hold (50).
    MissionSpec(
        id="bar_smuggle_vega_drugs",
        title="Vega Narcotics",
        description=(
            "The Cloud Host on Vega b has clients with expensive tastes. "
            "Ship the luxury goods through the orbital checkpoint - the "
            "station scans everything that docks."
        ),
        giver_npc_id="barkeep",
        faction="bar",
        mission_type="smuggling",
        tier=3,
        reward_credits=700,
        reward_xp=120,
        # 1 hop (~16 days one-way at starter speed) — generous to allow
        # a wide approach that avoids the patrol lanes.
        deadline_days=60,
        early_bonus_pct=25,
        required_cargo_size=30,
        delivery_target_npc_id="barkeep",       # Cloud Host override
        delivery_target_planet_id="vega_b",
        origin_planet_id=None,   # floats to any T3+ bar
        is_smuggle=True,
        smuggle_good_id="luxury_goods",
    ),
    # Tier 4 — Luyten's Star, 5 hops. 55 units overflows a mk3 hold (50)
    # — genuinely at risk without a mk4 (75). Blockade Station is the
    # militia home system: scans are the extreme end of the spectrum.
    MissionSpec(
        id="bar_smuggle_frontier_fuel",
        title="Frontier Fuel Heist",
        description=(
            "Fuel cells - a lot of them - need to reach the Bounty Master "
            "at Blockade Station, the last port before uncharted space. "
            "The blockade runs the tightest scans in the sector. This one "
            "pays like a heist because it is one."
        ),
        giver_npc_id="barkeep",
        faction="bar",
        mission_type="smuggling",
        tier=4,
        reward_credits=1500,
        reward_xp=250,
        # 5 hops (~85 days one-way at starter speed, needs a refuel
        # stop) + wide detour slack around militia patrols.
        deadline_days=200,
        early_bonus_pct=30,
        required_cargo_size=55,
        delivery_target_npc_id="bounty_master",   # Bounty Master on Blockade
        delivery_target_planet_id="blockade",
        origin_planet_id=None,   # floats to any T4 bar
        is_smuggle=True,
        smuggle_good_id="fuel_cells",
    ),
    # --- Salvage rights (boarding-integrated) ---
    # Patrol guards the wreck in space; the mission component hides in
    # the boarded interior. Patrol reuses the bounty fields; the wreck
    # is a separate non-combatant BountySpawn (salvage_wreck_enemy_id +
    # salvage_layout_id). Deadlines are ROUND TRIPS (fly out, clear the
    # patrol, board, fight the crew, fly back) — same 2.1-2.2x RT rule
    # as intercepts, with a small boarding buffer.
    # Tier 1 — Tau Ceti, 3 hops. Solo scout patrol, scout_a interior.
    MissionSpec(
        id="bar_salvage_tau_parts",
        title="Tau Ceti Wreck",
        description=(
            "A pirate crew lost a freighter in Tau Ceti and left a scout "
            "guarding the wreck. Clear the patrol, cut into the hull, and "
            "pull the machine parts out of the cargo hold. Bring them "
            "back here."
        ),
        giver_npc_id="barkeep",
        faction="bar",
        mission_type="salvage",
        tier=1,
        reward_credits=180,
        reward_xp=35,
        # Round trip to Tau Ceti (3 hops) ~100 days at starter speed;
        # deadline ~2.2x RT keeps both on-time and the early bonus
        # (< 110d) achievable.
        deadline_days=220,
        early_bonus_pct=25,
        target_enemy_id="pirate_scout",       # the guard patrol
        target_system_id="tau_ceti",
        bounty_target_squad_size=1,
        heist_target_good_id="machine_parts",  # mission component
        salvage_wreck_enemy_id="derelict_scout",
        salvage_layout_id="scout_a",
    ),
    # Tier 2 — Epsilon Eridani, 1 hop. Two-scout patrol, scout_a interior.
    MissionSpec(
        id="bar_salvage_epsilon_drive",
        title="Epsilon Drive",
        description=(
            "A freighter went down near Epsilon Eridani with a hold of "
            "electronics. Two pirates are picking it clean - and they "
            "won't share. Clear the patrol and board the wreck for the "
            "drive components."
        ),
        giver_npc_id="barkeep",
        faction="bar",
        mission_type="salvage",
        tier=2,
        reward_credits=400,
        reward_xp=70,
        # Round trip to Epsilon Eridani (1 hop) ~35 days; deadline ~2.2x
        # RT with a boarding buffer.
        deadline_days=90,
        early_bonus_pct=25,
        target_enemy_id="pirate_scout",
        target_system_id="epsilon_eridani",
        bounty_target_squad_size=2,
        heist_target_good_id="electronics",
        salvage_wreck_enemy_id="derelict_scout",
        salvage_layout_id="scout_a",
    ),
    # Tier 3 — Procyon, 2 hops. Raider + scout patrol, freightliner interior.
    MissionSpec(
        id="bar_salvage_procyon_core",
        title="Procyon Core",
        description=(
            "A big freighter is dead in the water off Procyon, and a raider "
            "crew with a scout escort has claimed it. The reactor core is "
            "still intact - fuel cells for the taking. Clear the patrol, "
            "board, and strip the engine room."
        ),
        giver_npc_id="barkeep",
        faction="bar",
        mission_type="salvage",
        tier=3,
        reward_credits=850,
        reward_xp=140,
        # Round trip to Procyon (2 hops) ~70 days; deadline ~2.2x RT.
        deadline_days=155,
        early_bonus_pct=25,
        target_enemy_id="pirate_raider",
        target_system_id="procyon",
        bounty_target_squad_size=2,
        bounty_wingmate_enemy_id="pirate_scout",
        heist_target_good_id="fuel_cells",
        salvage_wreck_enemy_id="derelict_freighter",
        salvage_layout_id="freightliner_a",
    ),
    # Tier 4 — Luyten's Star, 5 hops. Captain + 2 raiders, freightliner.
    MissionSpec(
        id="bar_salvage_luyten_blackbox",
        title="Luyten Black Box",
        description=(
            "Deep in Luyten's Star, a pirate captain and his raiders are "
            "guarding a gutted luxury liner. The cargo vault is still "
            "sealed - luxury goods waiting. This one's a full boarding "
            "action: clear the space patrol, then fight the crew inside "
            "deck by deck."
        ),
        giver_npc_id="barkeep",
        faction="bar",
        mission_type="salvage",
        tier=4,
        reward_credits=2000,
        reward_xp=320,
        # Round trip to Luyten's Star (5 hops) ~170 days (10 jumps, needs
        # a refuel stop); deadline ~2.1x RT with a boarding buffer.
        deadline_days=370,
        early_bonus_pct=30,
        target_enemy_id="pirate_captain",
        target_system_id="luyten_star",
        bounty_target_squad_size=3,
        bounty_wingmate_enemy_id="pirate_raider",
        bounty_target_loadout_pct=75,
        heist_target_good_id="luxury_goods",
        salvage_wreck_enemy_id="derelict_freighter",
        salvage_layout_id="freightliner_a",
    ),
    # ------------------------------------------------------------------
    # Tier 4 — beyond the arms: Ross 154 + Lalande 21185
    # ------------------------------------------------------------------
    # Ross 154, 3 hops — the deep-end flagship: a merchant caravan
    # running flare-forged rare earths past the Flare Crown. 3 hops
    # ~100d RT; deadline ~2.2x RT so the early bonus (< 110d) is
    # achievable at starter speed.
    MissionSpec(
        id="bar_intercept_ross_flare",
        title="The Flare Run",
        description=(
            "Past Sirius there's a flare star where the charts go dark - "
            "Ross 154. A caravan is hauling rare earths forged in the "
            "flares, and nobody on the arm will miss them. The run is "
            "deep: hounds, marauders, and maybe the Warlord himself "
            "patrol that road. Bring the rare earths back here."
        ),
        giver_npc_id="barkeep",
        faction="bar",
        mission_type="intercept",
        tier=4,
        reward_credits=2400,
        reward_xp=400,
        # Round trip to Ross 154 is 6 jumps (~100d at starter speed).
        # Deadline ~2.2x RT so the early bonus (< 110d) is achievable.
        deadline_days=220,
        early_bonus_pct=30,
        target_enemy_id="merchant_caravan",
        target_system_id="ross_154",
        bounty_target_squad_size=4,
        bounty_target_loadout_pct=90,
        heist_target_good_id="rare_earth_metals",
    ),
    # Ross 154 — salvage: the Flare Crown guards a gutted freighter.
    # Warlord patrol + hound escort, freightliner interior.
    MissionSpec(
        id="bar_salvage_ross_crown",
        title="The Flare Crown Wreck",
        description=(
            "A big freighter is dead in the dark of Ross 154, and the "
            "Warlord's crew has claimed it - clear the guard, cut in, "
            "and strip the engine room before the hounds come back. "
            "Ship components are stow, and so are you the moment you "
            "power down by that hull."
        ),
        giver_npc_id="barkeep",
        faction="bar",
        mission_type="salvage",
        tier=4,
        reward_credits=2600,
        reward_xp=420,
        # Round trip to Ross 154 (3 hops) ~100d at starter speed + a
        # boarding buffer; deadline ~2.2x RT.
        deadline_days=230,
        early_bonus_pct=30,
        target_enemy_id="pirate_warlord",
        target_system_id="ross_154",
        bounty_target_squad_size=2,
        bounty_wingmate_enemy_id="pirate_hound",
        bounty_target_loadout_pct=100,
        heist_target_good_id="ship_components",
        salvage_wreck_enemy_id="derelict_freighter",
        salvage_layout_id="freightliner_a",
    ),
    # Lalande 21185 — 4 hops. Intercept a caravan carrying stolen
    # research data deeper than anyone is supposed to go.
    MissionSpec(
        id="bar_intercept_lalande_record",
        title="The Dead Road Run",
        description=(
            "A caravan runs research records past the charts to "
            "Lalande 21185 - the star that isn't on any map. Whatever "
            "that data is, the Vault wants it back quietly. The road "
            "there is dead: Tollkeeper garrison, casket raiders, and "
            "a gate that hums in a minor key. Bring the records home."
        ),
        giver_npc_id="barkeep",
        faction="bar",
        mission_type="intercept",
        tier=4,
        reward_credits=2800,
        reward_xp=450,
        # Round trip to Lalande 21185 is 4 hops (~135d at starter
        # speed); deadline ~2.1x RT.
        deadline_days=290,
        early_bonus_pct=30,
        target_enemy_id="merchant_caravan",
        target_system_id="lalande_21185",
        bounty_target_squad_size=5,
        bounty_target_loadout_pct=95,
        heist_target_good_id="research_data",
    ),
    # Lalande 21185 — smuggle pharmaceuticals to the Veiled Registrar
    # on Whisper. There's no militia this deep, but the road crosses
    # every patrolled arm to get there. 65 units needs a mk4 hold (75).
    MissionSpec(
        id="bar_smuggle_lalande_vault",
        title="Whisper's Pharm Run",
        description=(
            "The Vault on Whisper never signs for anything - the Veiled "
            "Registrar pays cash for pharmaceuticals that vanished from "
            "inspection ledgers. Haul them across every scan gate between "
            "here and the dead road, and keep quiet. There is no law on "
            "Whisper, only prices."
        ),
        giver_npc_id="barkeep",
        faction="bar",
        mission_type="smuggling",
        tier=4,
        reward_credits=2200,
        reward_xp=380,
        # One-way run to Lalande 21185 is 4 hops (~67d at starter
        # speed) plus wide berths around patrols; deadline ~2.4x OTY.
        deadline_days=200,
        early_bonus_pct=30,
        required_cargo_size=65,
        delivery_target_npc_id="barkeep",       # Veiled Registrar override
        delivery_target_planet_id="lal_c",
        origin_planet_id=None,   # floats to any T4 bar
        is_smuggle=True,
        smuggle_good_id="pharmaceuticals",
    ),
)
