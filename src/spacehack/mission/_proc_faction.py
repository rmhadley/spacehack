"""Faction-contract generators: militia warrants and lab contracts.

The Act 0 epilogue perks (doc 38) unlock these boards. Both reuse the
established generator families with faction theming — warrants are
bounties posted by the Militia; lab contracts alternate specimen
transport (delivery) with site recovery (salvage). The tier floor that
makes them worth the unlock lives in ``_board._faction_tier_band``.
"""

from __future__ import annotations

import dataclasses
import random

from ..data.missions import MissionSpec
from ._proc_bar import _generate_bar_salvage
from ._proc_bounty import generate_bounty_mission
from ._proc_delivery import generate_delivery_mission


def _reflag(spec: MissionSpec, *, faction: str, title: str) -> MissionSpec:
    return dataclasses.replace(spec, faction=faction, title=title)


def generate_warrant_mission(
    origin_planet_id: str,
    max_tier: int,
    rng: random.Random,
    counter: int = 0,
    giver_npc_id: str = "",
) -> MissionSpec | None:
    """A Militia warrant: bounty work posted by the captain's board."""
    _spec = generate_bounty_mission(
        origin_planet_id=origin_planet_id, max_tier=max_tier,
        rng=rng, counter=counter, giver_npc_id=giver_npc_id,
    )
    if _spec is None:
        return None
    return _reflag(
        _spec, faction="militia",
        title=_spec.title.replace("Wanted:", "Warrant:", 1),
    )


def generate_lab_mission(
    origin_planet_id: str,
    max_tier: int,
    rng: random.Random,
    counter: int = 0,
    giver_npc_id: str = "",
) -> MissionSpec | None:
    """A lab contract: specimen transport or derelict-site recovery."""
    if rng.random() < 0.5:
        _spec = generate_delivery_mission(
            origin_planet_id=origin_planet_id, max_tier=max_tier,
            rng=rng, counter=counter, giver_npc_id=giver_npc_id,
        )
        if _spec is not None:
            return _reflag(
                _spec, faction="lab",
                title=_spec.title.replace("Deliver to", "Specimen run to", 1),
            )
        return None
    _spec = _generate_bar_salvage(
        origin_planet_id, max_tier, rng, counter, giver_npc_id,
    )
    if _spec is None:
        return None
    return _reflag(
        _spec, faction="lab",
        title=_spec.title.replace("Salvage:", "Recovery:", 1),
    )


__all__ = ["generate_warrant_mission", "generate_lab_mission"]
