"""Act 0: Prologue — "The Door on Mars".

Story beats (see docs/design/in_progress/07_DESIGN_MAIN_QUEST.md):

    1. ``prologue_signal``     — garbled transmission received while
                                 flying through Sol (first launch).
                                 Auto-triggered by
                                 :func:`spacehack.main_quest.maybe_trigger_signal`.
    2. ``prologue_mars_unlocked`` — checkpoint: Mars surface exploration
                                 unlocks once the signal is received.
                                 Auto-advanced by
                                 :func:`spacehack.main_quest.prepare_mars_surface`.
    3. ``prologue_mars_entrance`` — the player finds the sealed alien
                                 door in the Mars ruins. Completed by
                                 bumping the door (see
                                 :func:`spacehack.main_quest.bump_mars_door`).
    4. ``prologue_seek_help``   — the faction fork seeds here. Each
                                 faction NPC gives a DIFFERENT lead and
                                 offers to open the door their way.
                                 Accepting one LOCKS IN that faction's
                                 chain (``locks_chain`` — sets
                                 ``ctx.main_quest_chain``); the other
                                 three offer rows close. The tool is
                                 NOT granted on accept — it comes from
                                 the chain's final step.
    4a. ``<fac>_q1_*``          — the 4 chain-start steps (one per
                                 faction) unlocked by the lock-in.
    5. ``prologue_open``        — the player returns to Mars after
                                 completing the chosen faction's 5-step
                                 chain and opens the door: an empty
                                 ancient alien prison + a data cache
                                 (fuels Act 1). Unlocked only by the
                                 chain's final step (``unlocks_step``).

No time pressure, no fail states. The quest waits forever.
"""

from __future__ import annotations

from . import MainQuestStep, QuestDialogue

# Faction door-opening tools (see the design doc's opening-methods
# table). Unlocked by the CHAIN's final step (q5) via rewards_item —
# accepting help no longer grants the tool (lock-in redesign).
_MILITIA_BREACH = "militia_breach_charge"
_MERCHANT_CUTTER = "merchant_cutter"
_BAR_RIG = "bar_brute_rig"
_LAB_KEY = "lab_resonance_key"

_ASK_LABEL = "Ask about the Mars door"

STEPS: tuple[MainQuestStep, ...] = (
    MainQuestStep(
        id="prologue_signal",
        title="The Signal",
        description=(
            "A garbled transmission broke through the static — a burst "
            "of coordinates, then silence. They resolve to somewhere on "
            "Mars."
        ),
        trigger_planet_id="mars",
        trigger_system_id="sol",
    ),
    MainQuestStep(
        id="prologue_mars_unlocked",
        title="Mars",
        description=(
            "The transmission's coordinates point to a location on "
            "Mars. The surface is explorable — see what's out there."
        ),
        trigger_planet_id="mars",
        trigger_system_id="sol",
        requires_step="prologue_signal",
    ),
    MainQuestStep(
        id="prologue_mars_entrance",
        title="The Door",
        description=(
            "Among the red-dust ruins you find a sealed door of alien "
            "make. No visible mechanism, older than the colony. It will "
            "not open with any human tool."
        ),
        trigger_planet_id="mars",
        trigger_system_id="sol",
        requires_step="prologue_mars_unlocked",
    ),
    MainQuestStep(
        id="prologue_seek_help",
        title="Seek Help",
        description=(
            "The door won't open with any human tool. Ask around — the "
            "factions each have their own way in. Choose who helps you; "
            "that choice will echo."
        ),
        requires_step="prologue_mars_entrance",
        dialogues={
            "barkeep": QuestDialogue(
                npc_id="barkeep",
                trigger_on_talk=True,
                intro=(
                    "Heard about the thing in the dust? The militia "
                    "sealed it — or someone did. There was a guy got a "
                    "door like that open once. Cost him a hand. Here's "
                    "how he did it."
                ),
                active=(
                    "Still stuck on that door? The rig's yours when "
                    "you want it — a cut of whatever's inside, and the "
                    "story for the bar."
                ),
                complete=(
                    "So we've got a deal? Good. The old hand who "
                    "cracked that door — I'll make the introduction. "
                    "Come back with the story, and the bar pays in "
                    "drinks."
                ),
                locked=(
                    "You've already got a way in, friend. The bar "
                    "still wants the story when you're done."
                ),
                option_label=_ASK_LABEL,
                backing_faction="bar",
                locks_chain=True,
            ),
            "guild_master": QuestDialogue(
                npc_id="guild_master",
                trigger_on_talk=True,
                intro=(
                    "Alien tech on Mars? That's the most valuable "
                    "cargo in history. A salvager's cutter tuned to "
                    "alien alloys — sign the contract and it's yours. "
                    "First rights to what's inside."
                ),
                active=(
                    "The cutter's waiting. Sign here — first look at "
                    "anything inside, and the tool's yours."
                ),
                complete=(
                    "Contract signed, then. The cutter comes when the "
                    "work's done — first rights to what's inside, "
                    "remember."
                ),
                locked=(
                    "You've found another way in, then. A pity — the "
                    "guild pays handsomely for a look."
                ),
                option_label=_ASK_LABEL,
                backing_faction="merchants",
                locks_chain=True,
            ),
            "militia_captain": QuestDialogue(
                npc_id="militia_captain",
                trigger_on_talk=True,
                intro=(
                    "There is no door. Whatever you saw out there, "
                    "forget it. ...Quietly, off the books, the patrol "
                    "has seen this tech before. The 'incident'. We have "
                    "schematics and a breach charge that will open it. "
                    "You say nothing. Understood?"
                ),
                active=(
                    "The schematics are ready. One condition: this "
                    "never happened. Bring back proof of what's behind "
                    "it, and the patrol remembers nothing."
                ),
                complete=(
                    "Understood. The work has begun — report when "
                    "it's done, and we never speak of this again."
                ),
                locked=(
                    "You've made your choice, then. Keep it off the "
                    "books — the patrol has no part in this."
                ),
                option_label=_ASK_LABEL,
                backing_faction="militia",
                locks_chain=True,
            ),
            "research_officer": QuestDialogue(
                npc_id="research_officer",
                trigger_on_talk=True,
                intro=(
                    "A sealed structure on Mars? I need to study it. "
                    "Bring me a sample of the door's material — we'll "
                    "analyze it, and the resonance key it unlocks will "
                    "open the way."
                ),
                active=(
                    "The material analysis is promising. Bring the "
                    "sample back and the key is yours — we want a "
                    "specimen from inside for study."
                ),
                complete=(
                    "The work has begun, then. Return to Mars and chip "
                    "a sample off the door — we'll take it from there. "
                    "The truth deserves to be published, not buried."
                ),
                locked=(
                    "You've found other help. Very well — if you "
                    "recover anything, the station will study it."
                ),
                option_label=_ASK_LABEL,
                backing_faction="lab",
                locks_chain=True,
            ),
            # The Science Port lab slot hosts the xenolinguist (Act 0
            # lab-chain expert) — the lab seek-help lead keys off the
            # expert id so it still surfaces at Alpha Centauri.
            "xenolinguist": QuestDialogue(
                npc_id="xenolinguist",
                trigger_on_talk=True,
                intro=(
                    "A sealed structure on Mars? The signal isn't "
                    "human — and that door may be the same make. Bring "
                    "me a sample of its material. A resonance key "
                    "from the analysis would open it."
                ),
                active=(
                    "The material analysis is promising. Bring the "
                    "sample back and the key is yours — we want a "
                    "specimen from inside for study."
                ),
                complete=(
                    "The work has begun, then. Return to Mars and chip "
                    "a sample off the door — we'll take it from there. "
                    "The truth deserves to be published, not buried."
                ),
                locked=(
                    "You've found other help. Very well — if you "
                    "recover anything, the station will study it."
                ),
                option_label=_ASK_LABEL,
                backing_faction="lab",
                locks_chain=True,
            ),
        },
        rewards_xp=20,
    ),
    # --- Chain-start steps (one per faction, unlocked by the lock-in) ---
    # Accepting a faction's help (``locks_chain`` on the seek_help
    # dialogue) sets ``ctx.main_quest_chain``; the chain-aware
    # auto-advance then makes ONLY that faction's q1 available (all
    # four require ``prologue_seek_help`` — the chain filter in
    # ``main_quest_step_after`` picks the locked one). The remaining
    # chain steps (q2-q5) are authored per-faction in phases 1e-1h;
    # the final step sets ``unlocks_step="prologue_open"``.
    MainQuestStep(
        id="mil_q1_report",
        title="Report to the Captain",
        description=(
            "Report to the Militia Captain on Earth — off the books, "
            "he admits the patrol saw 'the incident' tech before. The "
            "requisition is buried in a scrubbed cache."
        ),
        trigger_planet_id="earth",
        trigger_system_id="sol",
        requires_step="prologue_seek_help",
        chain="militia",
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
                    "The scrubbed cache isn't going anywhere. Bring me "
                    "proof the requisition is intact."
                ),
                complete=(
                    "The requisition is secured. We'll be in touch — "
                    "it takes time to clear."
                ),
                option_label="Report to the Captain",
                backing_faction="militia",
            ),
        },
        rewards_xp=50,
    ),
    MainQuestStep(
        id="mer_q1_contract",
        title="Sign the Contract",
        description=(
            "Sign the contract with the Guild Master on Earth — first "
            "rights to anything inside the door, and the cutter is "
            "yours when the work is done."
        ),
        trigger_planet_id="earth",
        trigger_system_id="sol",
        requires_step="prologue_seek_help",
        chain="merchants",
        dialogues={
            "guild_master": QuestDialogue(
                npc_id="guild_master",
                trigger_on_talk=True,
                intro=(
                    "The contract is simple: the Guild gets first "
                    "rights to anything inside that door — salvage, "
                    "data, whatever it is — and in return the cutter "
                    "is yours when it's ready. Sign, and the first "
                    "clause sends you to escrow ore we've got staked "
                    "out."
                ),
                active=(
                    "The contract's waiting. Sign, and the first "
                    "clause points you at the escrow ore."
                ),
                complete=(
                    "Contract filed. We need time to arrange the "
                    "escrow."
                ),
                option_label="Sign the contract",
                backing_faction="merchants",
            ),
        },
        rewards_xp=50,
    ),
    MainQuestStep(
        id="bar_q1_oldhand",
        title="The Old Hand",
        description=(
            "The Barkeep names the old smuggler who cracked a door "
            "like that once — cost him a hand. He warns the militia "
            "has been sniffing around the old routes since 'the "
            "incident'."
        ),
        trigger_planet_id="earth",
        trigger_system_id="sol",
        requires_step="prologue_seek_help",
        chain="bar",
        objective_type="talk",
        wait_days=65,
        completion_flavor="Word's been sent to Barnard's Star. The old man is cagey — give him time to come around.",
        ready_message=(
            "The old man will see you for the right price. Come by the "
            "bar first — I've got a crate that'll get you in the door. "
            "Then run it to Barnard's Star b."
        ),
        dialogues={
            "barkeep": QuestDialogue(
                npc_id="barkeep",
                trigger_on_talk=True,
                intro=(
                    "The old hand who cracked a door like that once? "
                    "Cost him a hand. He's retired on Barnard's Star b, "
                    "and he don't see just anyone. But he owes the bar "
                    "a favor — I'll send word ahead. Fair warning: the "
                    "militia's been sniffing around the old routes "
                    "since 'the incident'. Keep your head down."
                ),
                active=(
                    "Word's ahead to the old man. Go see him on "
                    "Barnard's Star b — and watch the patrols."
                ),
                complete=(
                    "The old man is cagey — he'll see you for the "
                    "right price."
                ),
                option_label="Ask about the old smuggler",
                backing_faction="bar",
                dialogue_planet_id="earth",
            ),
        },
        rewards_xp=50,
    ),
    MainQuestStep(
        id="bar_q2_proof",
        title="The Proof Run",
        description=(
            "The old smuggler won't deal with strangers. See the "
            "Barkeep on Earth — he has a hot crate to get you in the "
            "door. Then run it to Barnard's Star b. Every militia "
            "patrol on the way can scan it."
        ),
        trigger_planet_id="barnards_b",
        trigger_system_id="barnards_star",
        requires_step="bar_q1_oldhand",
        chain="bar",
        objective_type="smuggle",
        requires_npc_id="old_smuggler",
        smuggle_good_id="weapons_blackmarket",
        smuggle_cargo_size=8,
        wait_days=85,
        completion_flavor="The old man needs time to survey the dig site. His hand doesn't work like it used to.",
        ready_message=(
            "He drew the cave where the old job went wrong — the rig's "
            "power cell is still down there. Meet him at the dig on "
            "Barnard's Star b."
        ),
        dialogues={
            "barkeep": QuestDialogue(
                npc_id="barkeep",
                trigger_on_talk=True,
                intro=(
                    "The old man won't deal with strangers — but he "
                    "owes the bar. I've got one crate left: black-market "
                    "weapons, hot as they come. Run it to him at "
                    "Barnard's Star b and he'll draw you the cave."
                ),
                active=(
                    "The crate's in your hold. Get it to the old man "
                    "on Barnard's Star b before a patrol sniffs it."
                ),
                complete=(
                    "He took the crate, then? Good — now he's got to "
                    "draw you the cave. The story's worth a round when "
                    "you're back."
                ),
                locked=(
                    "Already running that crate, are you? The old man "
                    "is a patient sort. So's the militia."
                ),
                option_label="You asked to see me?",
                backing_faction="bar",
                dialogue_planet_id="earth",
            ),
            "old_smuggler": QuestDialogue(
                npc_id="old_smuggler",
                trigger_on_talk=True,
                intro=(
                    "The bar sent word. You got the crate, or are we "
                    "wasting both our times?"
                ),
                active=(
                    "Crate's here, good. Now the part you came for: the "
                    "cave where the old job went wrong is up the ridge. "
                    "The rig's power cell is still down there. Fetch it, "
                    "and the bar gets its story."
                ),
                complete=(
                    "Cell's out, then? Good. The militia's got a nose "
                    "for that hardware — don't let them catch you "
                    "carrying it."
                ),
                option_label="Hand over the crate",
                backing_faction="bar",
            ),
        },
        rewards_credits=100,
        rewards_xp=80,
        rewards_rep={"pirate": +2, "merchant": -5, "civilian": -5, "militia": -8},
    ),
    MainQuestStep(
        id="bar_q3_rigparts",
        title="The Power Cell",
        description=(
            "The old smuggler drew the cave where the old job went "
            "wrong. Descend into the Barnard's Star b surface caves "
            "and recover the rig's power cell — decades-old "
            "militia-issue hardware."
        ),
        trigger_planet_id="barnards_b",
        trigger_system_id="barnards_star",
        requires_step="bar_q2_proof",
        chain="bar",
        objective_type="delve",
        delve_good_ids=(("machine_parts", 1), ("electronics", 1)),
        # No time gate — auto-advances to the delivery step.
        wait_days=0,
        completion_flavor=(
            "The power cell is decades old and unstable. It needs "
            "a recharge — and there's only one black-market rig "
            "that can handle it: the Wolf 359 listening post."
        ),
        dialogues={
            "old_smuggler": QuestDialogue(
                npc_id="old_smuggler",
                intro=(
                    "The cave's up the ridge, past the old dig markers. "
                    "The cell is down in the dark — watch your step, "
                    "and watch the sky. The militia's been circling."
                ),
                active=(
                    "The cave's up the ridge. The power cell is down "
                    "in the dark — and the militia knows you're "
                    "looking for it."
                ),
                complete=(
                    "You got it out? Good. That cell's older than "
                    "both of us — it needs a recharge before it'll "
                    "power anything. There's a black-market rig at "
                    "the Wolf 359 listening post. Pirate country — "
                    "no militia, no questions. Run it there."
                ),
                backing_faction="bar",
            ),
        },
        rewards_xp=60,
    ),
    MainQuestStep(
        id="bar_q4_blackmarket",
        title="Black-Market Recharge",
        description=(
            "The power cell is in your hold — unstable and hot. "
            "Take it to the Wolf 359 listening post. The black-market "
            "operator there has the only rig that can recharge it."
        ),
        trigger_planet_id="wolf_b",
        trigger_system_id="wolf_359",
        requires_step="bar_q3_rigparts",
        chain="bar",
        objective_type="smuggle",
        requires_npc_id="wolf_barkeep",
        smuggle_good_id="power_cell",
        smuggle_cargo_size=5,
        wait_days=90,
        completion_flavor=(
            "The operator hooks the cell up to the rig. 'This "
            "thing's been sitting in the dark since before the "
            "incident. Give me a few months — I'll call when "
            "it's charged.'"
        ),
        ready_message=(
            "The cell's charged and ready. Come pick it up at the "
            "Wolf 359 bar — and be careful on the way back. Every "
            "militia scanner between here and Earth will light up "
            "the moment you jump into Sol."
        ),
        dialogues={
            "wolf_barkeep": QuestDialogue(
                npc_id="wolf_barkeep",
                trigger_on_talk=True,
                intro=(
                    "You got something for me, or are you just "
                    "thirsty? ...That's militia-issue. Old model, "
                    "but the serial's still clean. I can recharge "
                    "it — no questions — but it'll take time."
                ),
                active=(
                    "The cell's on the rig now. Couple months, "
                    "maybe less. I'll send word."
                ),
                complete=(
                    "Cell's charged. Word's ahead — the Earth "
                    "barkeep knows you're coming. Watch the "
                    "militia on the way back."
                ),
                option_label="Hand over the power cell",
                backing_faction="bar",
            ),
        },
        rewards_credits=50,
        rewards_xp=60,
    ),
    MainQuestStep(
        id="bar_q5_charged",
        title="The Return Run",
        description=(
            "The cell is charged and hot — every militia scanner "
            "in Sol will hunt you. Return to the Wolf 359 bar, "
            "collect the charged cell, and run it back to the "
            "Barkeep on Earth."
        ),
        trigger_planet_id="earth",
        trigger_system_id="sol",
        requires_step="bar_q4_blackmarket",
        chain="bar",
        objective_type="smuggle",
        requires_npc_id="barkeep",
        smuggle_good_id="power_cell_charged",
        smuggle_cargo_size=5,
        wait_days=0,
        completion_flavor=(
            "The cell is back on Earth. The rig can be assembled now."
        ),
        dialogues={
            "wolf_barkeep": QuestDialogue(
                npc_id="wolf_barkeep",
                trigger_on_talk=True,
                intro=(
                    "There it is — fully charged and hot enough to "
                    "melt a scanner. Take it back to the Earth "
                    "barkeep. And stay sharp in Sol — every militia "
                    "patrol will be on you the moment you jump in."
                ),
                active=(
                    "The cell's in your hold. Run it to Earth — "
                    "the militia won't give you a choice."
                ),
                complete=(
                    "The cell made it. The Earth barkeep will have "
                    "the rig ready."
                ),
                option_label="Take the charged cell",
                backing_faction="bar",
            ),
            "barkeep": QuestDialogue(
                npc_id="barkeep",
                trigger_on_talk=True,
                intro=(
                    "You made it — and you brought the cell. "
                    "Give it here. The rig's half-assembled already."
                ),
                active=(
                    "There she is — the charged cell. Hand it over. "
                    "The rig is waiting."
                ),
                complete=(
                    "Cell's in, rig's on. One more step and that "
                    "door comes open."
                ),
                option_label="Hand over the charged cell",
                backing_faction="bar",
                dialogue_planet_id="earth",
            ),
        },
        rewards_credits=100,
        rewards_xp=80,
    ),
    MainQuestStep(
        id="bar_q6_rig",
        title="The Rig",
        description=(
            "Return to the Barkeep on Earth. The rig is assembled."
        ),
        trigger_planet_id="earth",
        trigger_system_id="sol",
        requires_step="bar_q5_charged",
        chain="bar",
        objective_type="talk",
        unlocks_step="prologue_open",
        rewards_item=_BAR_RIG,
        dialogues={
            "barkeep": QuestDialogue(
                npc_id="barkeep",
                trigger_on_talk=True,
                intro=(
                    "There she is — the brute-force rig. Cracks the "
                    "seal's power feed, just like the old man's door. "
                    "The militia will be watching you from here on, "
                    "friend. Welcome to the family."
                ),
                active=(
                    "The rig's here when you're ready. After that door "
                    "opens, the story's worth a round."
                ),
                complete=(
                    "Take the rig and open that door. The bar wants "
                    "the story when you're done — and the militia will "
                    "be watching."
                ),
                option_label="Collect the rig",
                backing_faction="bar",
                dialogue_planet_id="earth",
            ),
        },
        rewards_credits=200,
        rewards_xp=150,
    ),
    MainQuestStep(
        id="lab_q1_sample",
        title="The Sample",
        description=(
            "Return to Mars and chip a material sample off the door's "
            "surface — the door stays sealed. Bring the sample to the "
            "Research Officer."
        ),
        trigger_planet_id="mars",
        trigger_system_id="sol",
        requires_step="prologue_seek_help",
        chain="lab",
        objective_type="bump",  # chain-aware door bump (C3) — chips a sample, door stays sealed
        dialogues={
            "research_officer": QuestDialogue(
                npc_id="research_officer",
                intro=(
                    "Return to Mars and chip a hand-sized fragment off "
                    "the door's material. The door itself stays sealed "
                    "— we only need the surface."
                ),
                active=(
                    "A hand-sized fragment of the door's material is "
                    "all we need. The door stays sealed."
                ),
                complete=(
                    "Sample received. We need time to analyze it."
                ),
                backing_faction="lab",
            ),
        },
        rewards_xp=50,
    ),
    MainQuestStep(
        id="prologue_open",
        title="The Door Opens",
        description=(
            "Return to Mars with the means to open the door. The "
            "coordinates still hold a secret."
        ),
        trigger_planet_id="mars",
        trigger_system_id="sol",
        # NOT auto-advanced from ``prologue_seek_help`` anymore: the
        # door only opens after the chosen faction's full chain. Each
        # chain's q5 sets ``unlocks_step="prologue_open"`` (and grants
        # its door tool via ``rewards_item``) — see phases 1e-1h.
        rewards_xp=30,
    ),
)

__all__ = ["STEPS"]
