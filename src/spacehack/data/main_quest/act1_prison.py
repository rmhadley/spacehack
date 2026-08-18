"""Act 1: the prison descent — the research trail begins with the facility itself.

Act 0 ends with the Mars door opening. Act 1 starts there: the player
descends the alien prison, reaches the deep cell, and extracts data that
is incomprehensible to human science — the seed of the later research
trail. Step data lives here so the progression is data-driven.

Structure only — titles, descriptions, and dialogue text live in
``src/spacehack/data/text/`` (see ``_apply_text_overlay``).

Design doc: docs/design/in_progress/07_DESIGN_MAIN_QUEST.md
"""

from __future__ import annotations

from . import MainQuestStep

STEPS: tuple[MainQuestStep, ...] = (
    MainQuestStep(
        id="act1_prison",
        trigger_planet_id="mars",
        trigger_system_id="sol",
        objective_type="prison",
        auto_advance=False,
        wait_days=60,
        rewards_xp=120,
        # The first-reading disclosure plays once, on the confirmed
        # departure after the prison completes (see _act1.py).
        scene="orbit_disclosure",
    ),
)

__all__ = ["STEPS"]
