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
            "Sign the Guild's contract on Earth. It grants the Guild first access "
            "to anything recovered from the Mars site, and grants you the "
            "cutter that may open it. The first clause sends you to an old "
            "Wolf 359 claim - because every discovery begins with someone "
            "insisting they got there first."
        ),
        trigger_planet_id="earth",
        trigger_system_id="sol",
        requires_step="prologue_seek_help",
        chain="merchants",
        objective_type="talk",
        wait_days=60,
        completion_flavor=(
            "The Guild has filed the deed and transferred the claim into your name. "
            "When the clearance arrives, go to Wolf 359 b and secure the "
            "escrow ore before the rival consortium does. A legal claim is "
            "only as strong as the person standing on it."
        ),
        ready_message=(
            "The claim is cleared. Reach Wolf 359 b and recover the escrow ore from "
            "the caves beneath the listening post. The consortium knows the "
            "deed changed hands; expect them to contest it with more than "
            "paperwork."
        ),
        dialogues={
            "guild_master": QuestDialogue(
                npc_id="guild_master",
                trigger_on_talk=True,
                intro=(
                    "The contract is simple because complicated contracts make people read "
                    "them. The Guild gets first access to salvage and data from "
                    "the Mars site; you get a cutter tuned to the door's stress "
                    "signature. Sign, and we begin with the Wolf 359 escrow ore "
                    "that will pay for the work."
                ),
                active=(
                    "The contract is filed. Give the Guild time to move the deed through "
                    "three offices that all claim not to know us. Once it clears, "
                    "go to Wolf 359 b. The caves beneath the listening post hold "
                    "ore the Guild has been defending on paper for years."
                ),
                complete=(
                    "The deed is yours to enforce. Recover the ore from the Wolf 359 b "
                    "caves before the consortium turns our legal victory into a "
                    "physical one."
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
            "first - clear them out and secure the rare earth "
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
            "The raw ore is loaded into your hold - valuable, disputed, and useless "
            "until it is smelted. The Guild's only specialist for material this "
            "pure works at Tau Ceti b."
        ),
        dialogues={
            "guild_master": QuestDialogue(
                npc_id="guild_master",
                intro=(
                    "The claim has been dormant long enough for everyone to forget who paid for "
                    "it. The ore should still be in the deep cache, unless the "
                    "consortium has decided a neglected deed is an invitation. "
                    "Get down there and secure it before they do."
                ),
                active=(
                    "The claim is at Wolf 359 b. The listening post staff will not ask questions "
                    "because questions are bad for business. The consortium's "
                    "prospectors will ask them anyway."
                ),
                complete=(
                    "You got the ore out. It is raw, but the assay is already making people "
                    "nervous. Take it to the specialist at Tau Ceti b; he can smelt "
                    "it without asking the material to become ordinary."
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
            "The ore is in your mission hold, unrefined and already disputed. Take it "
            "to the Guild's salvage specialist at Tau Ceti b. Rival ships are "
            "watching the route; to them, this is not a delivery but evidence "
            "that the Guild still intends to own the future."
        ),
        trigger_planet_id="tc_b",
        trigger_system_id="tau_ceti",
        requires_step="mer_q2_strike",
        chain="merchants",
        objective_type="smuggle",
        requires_npc_id="salvage_specialist",
        smuggle_good_id="rare_earth_metals",
        smuggle_cargo_size=3,
        smuggle_hot=False,  # ore — never confiscatable (consortium heat is pirates, not scans)
        wait_days=130,
        completion_flavor=(
            "The specialist feeds the ore into the smelter and goes quiet. The assay "
            "returns impossible purity, with traces that do not match any "
            "human mine. 'Give me time,' he says. 'If this is what I think it "
            "is, the cutter will be the least valuable thing we make from it.'"
        ),
        ready_message=(
            "The smelt is complete. The alloy is stronger than anything in the Guild's "
            "catalogue, and it carries a repeating stress pattern like a "
            "recorded pulse. Collect it at Tau Ceti b, then recover calibration "
            "data from a derelict near Vega. The consortium has put raiders on "
            "the wreck; they would rather destroy the evidence than let us "
            "learn what the material can do."
        ),
        dialogues={
            "salvage_specialist": QuestDialogue(
                npc_id="salvage_specialist",
                trigger_on_talk=True,
                intro=(
                    "Word of the abandoned claim reached me months ago. If the Guild finally "
                    "found the ore, I want my cut. Hand it over and I will fire up "
                    "the smelter - assuming it agrees to run."
                ),
                active=(
                    "The smelter is running hot and the readings refuse to settle. Give it time. "
                    "If the alloy behaves, it will be unlike anything the Guild has "
                    "sold before."
                ),
                complete=(
                    "The smelt is complete. The alloy is stronger than anything I have worked "
                    "with, and it keeps returning the same pulse. Take it to Vega "
                    "and recover the calibration data before the consortium strips "
                    "the wreck."
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
            "The smelted alloy is loaded into your hold. The consortium will hunt you "
            "while you carry it to Vega. Fight through the raiders guarding the "
            "derelict, board the wreck, and recover its calibration data before "
            "someone destroys the record."
        ),
        trigger_system_id="vega",
        requires_step="mer_q3_transport",
        chain="merchants",
        objective_type="salvage",
        requires_spawn_id="mer_consortium_leader",
        bounty_enemy_id="pirate_captain",
        bounty_escort_ids=("pirate_raider", "pirate_raider"),
        salvage_wreck_enemy_id="derelict_scout",
        salvage_layout_id="scout_a",
        delve_good_ids=(("calibration_data", 1),),
        smuggle_good_id="rare_earth_metals",
        smuggle_cargo_size=3,
        wait_days=0,
        completion_flavor=(
            "The calibration data is secured. It shows the alloy does not simply cut the "
            "door; it matches a response already present in the material. The "
            "consortium leader is gone, the raiders have scattered, and the "
            "cutter can be assembled."
        ),
        dialogues={
            "salvage_specialist": QuestDialogue(
                npc_id="salvage_specialist",
                trigger_on_talk=True,
                intro=(
                    "There is the alloy. It is worth more than the ore, the claim, and perhaps "
                    "the Guild's entire current catalogue. It is loaded into your "
                    "hold. The cutter needs calibration data from a derelict near "
                    "Vega; the consortium has put raiders on the wreck to keep us "
                    "from learning what we made."
                ),
                active=(
                    "The alloy is in your hold. The wreck is near Vega's observation deck. "
                    "Fight through the consortium raiders, board the derelict, and "
                    "recover the calibration data. Without it, the Guild cannot tell "
                    "whether the cutter is opening a door or answering a call."
                ),
                complete=(
                    "You fought through the raiders and brought back the data. It confirms the "
                    "cutter will not be forcing the door; it will be completing a "
                    "pattern. Take the alloy to Earth. The Guild Master is waiting "
                    "to turn that distinction into a contract clause."
                ),
                option_label="Take the smelted alloy",
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
            "assembled - and the door on Mars can finally be opened."
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
                    "You brought the alloy back. Good. The cutter is assembled around it, "
                    "though the calibration data suggests we are not merely "
                    "cutting a door - we are asking a much older system to "
                    "notice us. Sign the final addendum and the instrument is "
                    "yours."
                ),
                active=(
                    "The cutter is here. After the door opens, the Guild gets first access under "
                    "the contract. If the first thing you find is a warning, send it "
                    "before you send anything else."
                ),
                complete=(
                    "Take the cutter to Mars. Open the door, document what you find, and "
                    "remember that a thing can be priceless without being safe to "
                    "own. Fair trading, pilot."
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
