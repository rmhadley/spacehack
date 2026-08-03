"""Act 0 militia chain: "The Incident" — breach charge (mil_q1 → mil_q5).

Physical through-line: requisition cache → inspection → demolition
expert → live-fire test → breach charge.  One classified operation,
escalating clearance, moving through frontier space.

Design doc: docs/design/in_progress/07_DESIGN_MAIN_QUEST.md
"""

from __future__ import annotations

from . import MainQuestStep, QuestDialogue

_MILITIA_CHARGE = "militia_breach_charge"

STEPS: tuple[MainQuestStep, ...] = (
    MainQuestStep(
        id="mil_q1_report",
        title="Report to the Captain",
        description=(
            "Report to the Militia Captain on Earth — off the books, "
            "he admits the patrol saw 'the incident' tech before. The "
            "requisition is buried in a scrubbed cache. Bring him "
            "proof it's intact, and the schematics are yours."
        ),
        trigger_planet_id="earth",
        trigger_system_id="sol",
        requires_step="prologue_seek_help",
        chain="militia",
        objective_type="talk",
        wait_days=60,
        completion_flavor=(
            "The requisition is filed — off the books, no record. "
            "The Captain will contact you when it clears. Once it "
            "does, head to Mercury — the surface caves beneath the "
            "old mining station hold a classified cache."
        ),
        ready_message=(
            "The requisition has cleared. Get to Mercury — the "
            "surface caves beneath the old mining station hold a "
            "classified cache. Secure the ship components and fuel "
            "cells inside before anyone else finds them."
        ),
        dialogues={
            "militia_captain": QuestDialogue(
                npc_id="militia_captain",
                trigger_on_talk=True,
                intro=(
                    "Good. Now you're on the books — my books, which "
                    "is to say no one's. The patrol saw this tech "
                    "before. 'The incident'. The requisition that gets "
                    "you the charge is buried in a scrubbed cache. "
                    "Bring me proof it's intact, and the schematics "
                    "are yours."
                ),
                active=(
                    "The requisition takes time to clear — buried "
                    "paperwork, sealed records. Once it does, get to "
                    "Mercury — the caves beneath the mining station "
                    "hold a cache the official logs scrubbed years "
                    "ago."
                ),
                complete=(
                    "The requisition is secured. We'll be in touch — "
                    "every component needs to be inspected before the "
                    "charge can be built."
                ),
                option_label="Report to the Captain",
                backing_faction="militia",
                dialogue_planet_id="earth",
            ),
        },
        rewards_xp=50,
    ),
    MainQuestStep(
        id="mil_q2_cache",
        title="The Cache",
        description=(
            "The requisition cache is buried deep in the Mercury "
            "surface caves — a classified stockpile the official "
            "logs scrubbed years ago. Descend into the caves and "
            "secure the ship components and fuel cells."
        ),
        trigger_planet_id="mercury",
        trigger_system_id="sol",
        requires_step="mil_q1_report",
        chain="militia",
        objective_type="delve",
        delve_good_ids=(("ship_components", 4), ("fuel_cells", 2)),
        wait_days=80,
        completion_flavor=(
            "The requisition cache is secured. The Captain's "
            "demolition expert needs to inspect every component "
            "before the charge can be assembled. They'll contact "
            "you when the inspection is done."
        ),
        ready_message=(
            "Inspection's complete and every component checks out. "
            "Recruit the demolitions expert at Epsilon Eridani b — "
            "the militia building on the colony. Drop the Captain's "
            "name and he'll sign on."
        ),
        dialogues={
            "militia_captain": QuestDialogue(
                npc_id="militia_captain",
                intro=(
                    "The cache is deep in the Mercury caves — "
                    "a sealed requisition the official logs don't "
                    "show. Ship components, fuel cells, enough to "
                    "build a breach charge that'll crack anything. "
                    "Secure it and bring it back."
                ),
                active=(
                    "The cache is in the Mercury caves — beneath "
                    "the old mining station. Don't draw attention. "
                    "The requisition was scrubbed for a reason."
                ),
                complete=(
                    "The cache is intact. Every component will be "
                    "inspected before the charge can be assembled. "
                    "The expert is at Epsilon Eridani b — drop my "
                    "name and he'll know the work is off the books."
                ),
                backing_faction="militia",
                dialogue_planet_id="earth",
            ),
        },
        rewards_credits=100,
        rewards_xp=80,
    ),
    MainQuestStep(
        id="mil_q3_demolitions",
        title="The Expert",
        description=(
            "Recruit the demolitions expert at Epsilon Eridani b — "
            "the militia building on the frontier colony. Drop the "
            "Captain's name and he'll sign on. The charge needs a "
            "specialist to assemble it."
        ),
        trigger_planet_id="eri_b",
        trigger_system_id="epsilon_eridani",
        requires_step="mil_q2_cache",
        chain="militia",
        objective_type="visit",
        requires_npc_id="demolitions_expert",
        wait_days=120,
        completion_flavor=(
            "The demolitions expert signs on. Building a breach "
            "charge tuned to alien alloy takes time — the Captain "
            "will call when it's ready for a live-fire test. Be "
            "ready for a fight."
        ),
        ready_message=(
            "The charge is built and ready for testing. Clear the "
            "pirate scouts at Cygni b — the Captain wants a live-fire "
            "field test before it touches an alien door. Two scouts, "
            "nothing fancy. Prove the charge works."
        ),
        dialogues={
            "demolitions_expert": QuestDialogue(
                npc_id="demolitions_expert",
                trigger_on_talk=True,
                intro=(
                    "The Captain sent you? Then the work is off the "
                    "books — good, I prefer it that way. Breach "
                    "charges, cutting torches, doors that don't want "
                    "to open. If the requisition checks out, I'll "
                    "build you a charge that'll crack anything."
                ),
                active=(
                    "Building a breach charge takes time — weeks, "
                    "maybe months. Alien alloy isn't something you "
                    "rush. The Captain will call when it's ready."
                ),
                complete=(
                    "The charge is built and ready for testing. "
                    "The Captain wants a live-fire field test before "
                    "it goes near an alien door — report to him on "
                    "Earth for the target."
                ),
                option_label="Ask about the breach charge",
                backing_faction="militia",
            ),
        },
        rewards_xp=60,
    ),
    MainQuestStep(
        id="mil_q4_livefire",
        title="Live-Fire Test",
        description=(
            "The breach charge is built — now it needs a field "
            "test. Clear the pirate scouts at Cygni b. The Captain "
            "wants proof the charge holds under fire before it "
            "touches an alien door."
        ),
        trigger_system_id="cygni",
        requires_step="mil_q3_demolitions",
        chain="militia",
        objective_type="bounty",
        requires_spawn_id="mil_livefire_test",
        bounty_enemy_id="pirate_scout",
        wait_days=80,
        completion_flavor=(
            "Live-fire test complete — the charge holds. The "
            "Captain's ready to assemble the final package. Report "
            "to Earth when you get the word."
        ),
        ready_message=(
            "Well done. The charge held under fire — exactly what "
            "the Captain needed to see. Return to Earth. The breach "
            "charge is assembled and waiting for you."
        ),
        dialogues={
            "militia_captain": QuestDialogue(
                npc_id="militia_captain",
                intro=(
                    "The charge needs a field test before it goes "
                    "near an alien door. Two pirate scouts at Cygni "
                    "b — clear them and prove the charge holds under "
                    "fire. Report back when it's done."
                ),
                active=(
                    "The scouts are at Cygni b. Clear them and "
                    "prove the charge works. This isn't about glory "
                    "— it's about knowing the charge won't fail "
                    "when it matters."
                ),
                complete=(
                    "The charge held. Good — the Captain was right "
                    "about you. The final package is being assembled "
                    "on Earth. Report in when you're ready."
                ),
                backing_faction="militia",
                dialogue_planet_id="earth",
            ),
        },
        rewards_credits=150,
        rewards_xp=120,
    ),
    MainQuestStep(
        id="mil_q5_charge",
        title="The Charge",
        description=(
            "Return to the Militia Captain on Earth. The breach "
            "charge is assembled — tested, proven, and ready to "
            "crack the alien seal on Mars."
        ),
        trigger_planet_id="earth",
        trigger_system_id="sol",
        requires_step="mil_q4_livefire",
        chain="militia",
        objective_type="talk",
        unlocks_step="prologue_open",
        rewards_item=_MILITIA_CHARGE,
        dialogues={
            "militia_captain": QuestDialogue(
                npc_id="militia_captain",
                trigger_on_talk=True,
                intro=(
                    "There it is — the breach charge. Tested, "
                    "proven, and tuned to alien alloy. Take it to "
                    "Mars and open that door. Remember: this "
                    "operation stays off the books. The frontier "
                    "must be held — whatever's inside, we contain "
                    "it. Quietly."
                ),
                active=(
                    "The charge is here when you're ready. After "
                    "that door opens, you report to me what you "
                    "find — nothing leaves the room."
                ),
                complete=(
                    "Take the charge and open that door. The "
                    "frontier must be held — and you're the one "
                    "holding it now. Dismissed."
                ),
                option_label="Collect the charge",
                backing_faction="militia",
                dialogue_planet_id="earth",
            ),
        },
        rewards_credits=200,
        rewards_xp=150,
    ),
)

__all__ = ["STEPS"]
