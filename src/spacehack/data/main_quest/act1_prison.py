"""Act 1: the prison descent — the research trail begins with the facility itself.

Act 0 ends with the Mars door opening. Act 1 starts there: the player
descends the alien prison, reaches the deep cell, and extracts data that
is incomprehensible to human science — the seed of the later research
trail. Step data lives here so the progression is data-driven.

Design doc: docs/design/in_progress/07_DESIGN_MAIN_QUEST.md
"""

from __future__ import annotations

from . import MainQuestStep

STEPS: tuple[MainQuestStep, ...] = (
    MainQuestStep(
        id="act1_prison",
        title="The Prison Below",
        description=(
            "The door has opened onto a facility built beneath Mars. Descend through "
            "the silent prison, restore the systems that still answer, and reach "
            "the deep cell at the bottom. The cell is empty, but one terminal is "
            "alive. Extract its data; it may tell you whether the prisoner left "
            "by choice, by force, or long before anyone on Mars knew this place "
            "existed."
        ),
        trigger_planet_id="mars",
        trigger_system_id="sol",
        objective_type="prison",
        auto_advance=False,
        wait_days=60,
        ready_message=(
            "Your faction's preliminary archive review is complete. The first pass "
            "did not produce a translation, but it identified a coordinate layer "
            "worth testing. Take the recovered archive to the Research Officer at "
            "Alpha Centauri's Science Port for an independent reading. The work "
            "will wait for you; the signal will not become clearer on its own."
        ),
        rewards_xp=120,
        completion_flavor=(
            "The data stream ends before it becomes a translation. No language, no "
            "mathematics, and no human model can hold the whole of it. But the "
            "archive is not random: routes, containment records, warnings, and "
            "fragments of an identity are buried together in the noise. The cell "
            "was built for something. It is empty now. And the terminal has sent "
            "the first answer back into the dark."
        ),
    ),
)

__all__ = ["STEPS"]
