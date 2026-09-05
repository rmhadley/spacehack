"""Main-quest save migrations: declared renames and retirements.

The quest catalogs keep their current ids and order; this table is
purely the SAVE/LOAD contract — it maps what old save files carry
onto the live catalog at load, replacing bespoke per-campaign repair
functions (doc 33, Phase 1).

Semantics:

* ``RENAMES[old]`` — a string target renames the id (status and any
  time-gate entry move with it). A tuple target means the old step
  COVERED several steps: a completed status completes every target
  (the work happened, in some prior layout); any other status maps
  onto the first target only, and normal chain scheduling takes over.
* ``RETIRED[old]`` — the id no longer exists. It is dropped from the
  progress and gate maps; the tuple lists ids marked ``completed``
  when the retired id itself was completed (``"{chain}"`` resolves to
  the player's faction chain at migration time).
"""

from __future__ import annotations

RENAMES: dict[str, str | tuple[str, ...]] = {
    # Merchants, 5-step era: calibrate/cutter were q4/q5; the survey
    # run lives on as mer_q6_survey, the cutter as mer_q7_cutter.
    "mer_q4_calibrate": "mer_q6_survey",
    "mer_q5_cutter": "mer_q7_cutter",
    # Merchants, 6-step era: The Survey split into alloy pickup +
    # Vega run — the combined step covered both.
    "mer_q5_calibration": ("mer_q5_alloy", "mer_q6_survey"),
    "mer_q6_cutter": "mer_q7_cutter",
}

# A later step that already ran in a prior layout backfills the steps
# it now depends on — the chain must not strand the player. Fires when
# the key's status is active/completed and a target is missing.
BACKFILLS: dict[str, tuple[str, ...]] = {
    "mer_q6_survey": ("mer_q5_alloy",),
}

# Pre-epilogue field fold: every old disclosure choice was a sharing
# path, so any of them maps onto the delivered disposition.
FIELD_FOLDS: dict[str, tuple[str, str]] = {
    "main_quest_disclosure": ("main_quest_disposition", "delivered"),
}

RETIRED: dict[str, tuple[str, ...]] = {
    # Pre-epilogue research chain (doc 38): a save that reached the
    # first translation counts as a completed delivery, so its
    # chain's reward step completes (the old flow never paid one).
    "research_alpha": (),
    "research_alpha_report": ("epilogue_reward_{chain}",),
}

__all__ = ["RENAMES", "BACKFILLS", "FIELD_FOLDS", "RETIRED"]
