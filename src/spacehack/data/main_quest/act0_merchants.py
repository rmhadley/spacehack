"""Act 0 merchants chain: "The Contract" — alien-alloy cutter (mer_q1 → mer_q5).

Physical through-line: rare ore → smelted alloy → cutter. One object,
escalating value, moving through contested space.

Design doc: docs/design/in_progress/07_DESIGN_MAIN_QUEST.md
"""

from __future__ import annotations

from . import MainQuestStep, QuestDialogue

_MERCHANT_CUTTER = "merchant_cutter"

STEPS: tuple[MainQuestStep, ...] = (
    MainQuestStep(
        id="mer_q1_contract",
        title="Sign the Contract",
        description=(
            "Sign the contract with the Guild Master on Earth — first "
            "rights to anything inside the door, and the cutter is "
            "yours when the work is done. The first clause stakes the "
            "Wolf 359 claim."
        ),
        trigger_planet_id="earth",
        trigger_system_id="sol",
        requires_step="prologue_seek_help",
        chain="merchants",
        objective_type="talk",
        wait_days=60,
        completion_flavor=(
            "The Guild files the escrow paperwork and transfers the "
            "claim deed. The claim at Wolf 359 is yours to stake — "
            "but the consortium has been sniffing around."
        ),
        ready_message=(
            "The claim is ready. Get to Wolf 359 b and stake it — "
            "the caves beneath the listening post hold the Guild's "
            "abandoned escrow ore. Watch for rival prospectors."
        ),
        dialogues={
            "guild_master": QuestDialogue(
                npc_id="guild_master",
                trigger_on_talk=True,
                intro=(
                    "The contract is simple: the Guild gets first "
                    "rights to anything inside that door — salvage, "
                    "data, whatever it is — and in return the cutter "
                    "is yours when it's ready. Sign, and the first "
                    "clause sends you to the escrow ore we've got "
                    "staked out at Wolf 359."
                ),
                active=(
                    "Contract's filed. We need time to arrange the "
                    "escrow paperwork and transfer the claim deed."
                ),
                complete=(
                    "The claim's yours to stake. The ore is "
                    "down in the Wolf 359 b caves — don't let the "
                    "consortium get there first."
                ),
                option_label="Sign the contract",
                backing_faction="merchants",
                dialogue_planet_id="earth",
            ),
        },
        rewards_xp=50,
    ),
    MainQuestStep(
        id="mer_q2_strike",
        title="The Claim",
        description=(
            "Descend into the Wolf 359 b surface caves and stake "
            "the Guild's abandoned prospecting claim. Rival "
            "prospectors from a competing consortium got there "
            "first — clear them out and secure the rare earth "
            "metals."
        ),
        trigger_planet_id="wolf_b",
        trigger_system_id="wolf_359",
        requires_step="mer_q1_contract",
        chain="merchants",
        objective_type="delve",
        delve_good_ids=(("rare_earth_metals", 3),),
        wait_days=0,
        completion_flavor=(
            "The raw ore is loaded into your hold — valuable but "
            "unrefined. It needs smelting, and the only specialist "
            "who can handle high-grade rare earth is at Tau Ceti b."
        ),
        dialogues={
            "guild_master": QuestDialogue(
                npc_id="guild_master",
                intro=(
                    "The claim's been dormant for years. The ore "
                    "should still be in the deep cache — if the "
                    "consortium hasn't already stripped it. Get "
                    "down there and stake it before they do."
                ),
                active=(
                    "The claim is at Wolf 359 b. The listening post "
                    "staff won't ask questions — the caves are "
                    "unregulated. Watch for rival prospectors."
                ),
                complete=(
                    "You got the ore out? Good — but it's raw. It "
                    "needs smelting, and the guild knows one "
                    "specialist who can handle it. Tau Ceti b."
                ),
                backing_faction="merchants",
            ),
        },
        rewards_credits=100,
        rewards_xp=80,
    ),
    MainQuestStep(
        id="mer_q3_transport",
        title="The Transport",
        description=(
            "The raw ore is loaded into your mission hold — hot "
            "cargo. The consortium knows about the strike. "
            "Transport the ore to the salvage specialist at "
            "Tau Ceti b for smelting. Consortium ships with "
            "pirate escorts patrol the route — every scanner is "
            "a threat."
        ),
        trigger_planet_id="tc_b",
        trigger_system_id="tau_ceti",
        requires_step="mer_q2_strike",
        chain="merchants",
        objective_type="smuggle",
        requires_npc_id="salvage_specialist",
        smuggle_good_id="rare_earth_metals",
        smuggle_cargo_size=3,
        wait_days=130,
        completion_flavor=(
            "The specialist hooks the ore into his smelting rig. "
            "'High-grade stuff — the rare earth content is off the "
            "charts. Give me a few months and I'll call when it's "
            "ready.'"
        ),
        ready_message=(
            "Smelt's done and the alloy is beautiful — stronger "
            "than anything the guild has seen in years. Come pick "
            "it up at Tau Ceti b. The cutter needs calibration "
            "data from a derelict near Vega — but the consortium's "
            "got ships and raiders guarding the wreck. Be ready "
            "for a fight."
        ),
        dialogues={
            "salvage_specialist": QuestDialogue(
                npc_id="salvage_specialist",
                trigger_on_talk=True,
                intro=(
                    "Word of the abandoned claim reached me months "
                    "ago — if that escrow ore's still there, I want "
                    "my cut. You got it? Hand it over and I'll fire "
                    "up the smelting rig."
                ),
                active=(
                    "The smelting rig is running hot. Couple months, "
                    "and I'll have an alloy the guild hasn't seen "
                    "in years."
                ),
                complete=(
                    "Smelt's done. The alloy is stronger than "
                    "anything I've worked in years — the cutter "
                    "will slice through that door like paper. "
                    "Now get to Vega before the consortium strips "
                    "that wreck."
                ),
                option_label="Hand over the ore",
                backing_faction="merchants",
            ),
        },
        rewards_credits=100,
        rewards_xp=90,
    ),
    MainQuestStep(
        id="mer_q4_calibrate",
        title="The Calibration",
        description=(
            "The smelted alloy is ready. Head to Vega — a derelict "
            "near the gas giant holds calibration data the cutter "
            "needs. But the consortium has escalated: a merchant "
            "leader and pirate raiders are guarding the wreck. "
            "Fight through them and recover the data."
        ),
        trigger_system_id="vega",
        requires_step="mer_q3_transport",
        chain="merchants",
        objective_type="bounty",
        requires_spawn_id="mer_consortium_leader",
        bounty_enemy_id="pirate_captain",
        wait_days=0,
        completion_flavor=(
            "The consortium leader's ship breaks apart — the "
            "calibration data is recovered from the wreck. The "
            "cutter is ready."
        ),
        dialogues={
            "salvage_specialist": QuestDialogue(
                npc_id="salvage_specialist",
                intro=(
                    "There she is — the smelted alloy. Worth ten "
                    "times what you dug out of that cave. The "
                    "cutter needs calibration data from a derelict "
                    "near Vega — but the consortium got there first. "
                    "Ships and raiders guarding the wreck. Take the "
                    "alloy and clear them out."
                ),
                active=(
                    "The wreck is near Vega b's observation deck. "
                    "Fight through the consortium blockade and "
                    "recover the calibration data — the cutter "
                    "won't work without it."
                ),
                complete=(
                    "You fought through the blockade? Good. The "
                    "calibration data will dial in the cutter's "
                    "frequency — take the alloy and head back to "
                    "Earth. The Guild Master's waiting."
                ),
                backing_faction="merchants",
            ),
        },
        rewards_credits=150,
        rewards_xp=120,
    ),
    MainQuestStep(
        id="mer_q5_cutter",
        title="The Cutter",
        description=(
            "Return to the Guild Master on Earth with the smelted "
            "alloy and the calibration data. The cutter can be "
            "assembled — and the door on Mars can finally be opened."
        ),
        trigger_planet_id="earth",
        trigger_system_id="sol",
        requires_step="mer_q4_calibrate",
        chain="merchants",
        objective_type="talk",
        unlocks_step="prologue_open",
        rewards_item=_MERCHANT_CUTTER,
        dialogues={
            "guild_master": QuestDialogue(
                npc_id="guild_master",
                trigger_on_talk=True,
                intro=(
                    "You made it — and you brought the alloy. Give "
                    "it here. The cutter's half-assembled already — "
                    "the calibration data will dial it in. Sign the "
                    "final addendum and the cutter is yours."
                ),
                active=(
                    "The cutter's here when you're ready. After "
                    "that door opens, the Guild gets first look "
                    "inside — remember the contract."
                ),
                complete=(
                    "Take the cutter and open that door. The Guild "
                    "wants the first look inside — but whatever "
                    "you find, the contract's fulfilled. Fair "
                    "trading, pilot."
                ),
                option_label="Collect the cutter",
                backing_faction="merchants",
                dialogue_planet_id="earth",
            ),
        },
        rewards_credits=200,
        rewards_xp=150,
    ),
)

__all__ = ["STEPS"]
