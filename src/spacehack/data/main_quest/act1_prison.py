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
            "The door has opened onto a facility built beneath Mars. "
            "Descend the prison floors, restore its power, and reach the "
            "deep cell at the bottom. Extract whatever data the one live "
            "terminal still holds — it is beyond human understanding, but "
            "it is a beginning."
        ),
        trigger_planet_id="mars",
        trigger_system_id="sol",
        objective_type="prison",
        rewards_xp=120,
        completion_flavor=(
            "The data stream ends. Nothing decodes — no language, no "
            "mathematics, no human frame can hold it. But the sheer volume "
            "is proof: something was kept here, and something escaped. "
            "Somewhere, someone will want to study this."
        ),
    ),
)

__all__ = ["STEPS"]
