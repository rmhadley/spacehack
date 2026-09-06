"""The transponder / ID layer (doc 40, phase 1).

An ID is an identifier that maps to relations; the game lived in
live mode since day one. Phase 1 covers the state model (live /
dark / spoofed, the worn-face library), persistence + existing-save
migration, the rep-routing gate (actions under a fake ID cannot
alter the true ID), and the F-screen identity hub.
"""

from __future__ import annotations

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))

from support.quest_ctx import quest_ctx


def _pirate_face(id_: str = "KG-8812"):
    return {
        "id": id_, "kind": "cloned",
        "label": "Warlord face", "faction": "pirate",
    }


def test_state_machine_live_dark_spoofed():
    from src.spacehack import identity

    ctx = quest_ctx()
    ctx.broadcast_dark = False
    ctx.broadcast_identity = None
    ctx.collected_ids = []
    assert identity.broadcast_mode(ctx) == identity.LIVE
    assert identity.resolved_identity(ctx)["kind"] == "true"
    identity.ensure_registration(ctx)
    assert ctx.ship_registration

    identity.toggle_dark(ctx)
    assert identity.broadcast_mode(ctx) == identity.DARK
    assert identity.resolved_identity(ctx) is None

    identity.toggle_dark(ctx)  # back to live, then wear the face
    identity.collect_id(ctx, _pirate_face())
    identity.cycle_identity(ctx)
    assert identity.broadcast_mode(ctx) == identity.SPOOFED
    worn = identity.resolved_identity(ctx)
    assert worn["id"] == "KG-8812" and worn["faction"] == "pirate"

    # Dark is the master switch: the face stays filed, nothing broadcasts.
    identity.toggle_dark(ctx)
    assert identity.broadcast_mode(ctx) == identity.DARK
    identity.toggle_dark(ctx)
    assert identity.broadcast_mode(ctx) == identity.SPOOFED

    identity.cycle_identity(ctx)  # off the end of the library = no face
    assert identity.broadcast_mode(ctx) == identity.LIVE


def test_cycle_wraps_through_the_library():
    from src.spacehack import identity

    ctx = quest_ctx()
    identity.collect_id(ctx, _pirate_face())
    identity.collect_id(ctx, {"id": "YY-5678", "kind": "scrubbed",
                              "label": "Blank hull", "faction": None})

    identity.cycle_identity(ctx)
    assert identity.resolved_identity(ctx)["id"] == "KG-8812"
    identity.cycle_identity(ctx)
    assert identity.resolved_identity(ctx)["id"] == "YY-5678"
    identity.cycle_identity(ctx)
    assert identity.broadcast_mode(ctx) == identity.LIVE


def test_collect_id_rejects_duplicates():
    from src.spacehack import identity

    ctx = quest_ctx()
    assert identity.collect_id(ctx, _pirate_face()) is True
    assert identity.collect_id(ctx, _pirate_face()) is False
    assert len(ctx.collected_ids) == 1


def test_masked_actions_cannot_alter_true_ratings():
    """THE doc 40 twist: rep moves only while live. The mask cuts
    both ways — no losses, and no gains either."""
    from src.spacehack.faction import modify_rep

    ctx = quest_ctx()
    ctx.faction_reputation = {"militia": 10}

    ctx.broadcast_dark = True
    modify_rep(ctx, "militia", -5)  # a crime, unseen
    modify_rep(ctx, "militia", 5)   # a good deed, unrecorded
    assert ctx.faction_reputation["militia"] == 10

    ctx.broadcast_dark = False
    ctx.broadcast_identity = _pirate_face()
    modify_rep(ctx, "militia", 5)
    assert ctx.faction_reputation["militia"] == 10

    ctx.broadcast_identity = None  # live again: rep flows
    modify_rep(ctx, "militia", 5)
    assert ctx.faction_reputation["militia"] == 15


def test_in_person_events_bypass_the_broadcast_gate():
    """Face-to-face dealings (quest rewards, NPC talks) don't ride
    the ship's transponder — they always touch the true ratings."""
    from src.spacehack.faction import modify_rep

    ctx = quest_ctx()
    ctx.faction_reputation = {"militia": 10}
    ctx.broadcast_dark = True

    modify_rep(ctx, "militia", 5, in_person=True)
    assert ctx.faction_reputation["militia"] == 15


def test_monthly_decay_ignores_the_broadcast_state():
    """Decay is time, not action — it writes directly."""
    from src.spacehack.faction import apply_monthly_decay

    ctx = quest_ctx()
    ctx.faction_reputation = {"militia": 40}  # liked: decays toward neutral
    ctx.broadcast_dark = True

    apply_monthly_decay(ctx)
    assert ctx.faction_reputation["militia"] == 38  # liked drift -2, gate-free


def test_registration_generates_once_and_migrates_saves():
    from src.spacehack import identity

    ctx = quest_ctx()
    first = identity.ensure_registration(ctx)
    assert first == identity.ensure_registration(ctx)  # stable
    assert ctx.ship_registration

    fresh = quest_ctx()  # an existing save: empty field, one field only
    reg = identity.ensure_registration(fresh)
    assert reg and reg == fresh.ship_registration


def test_save_round_trip_carries_the_identity_state():
    """The identity fields persist and a legacy save (no keys)
    migrates: a registration is generated on restore."""
    from src.spacehack.saveload import _restore_quest_and_tutorial

    ctx = quest_ctx()
    data = {
        "ship_registration": "AB-1234",
        "broadcast_dark": True,
        "broadcast_identity": None,
        "collected_ids": [_pirate_face()],
    }
    _restore_quest_and_tutorial(ctx, data)
    assert ctx.ship_registration == "AB-1234"
    assert ctx.broadcast_dark is True
    assert ctx.collected_ids[0]["id"] == "KG-8812"

    legacy = quest_ctx()
    _restore_quest_and_tutorial(legacy, {})
    assert legacy.ship_registration, "legacy saves gain a registration"
    assert legacy.broadcast_dark is False


def test_faction_frame_shows_the_broadcast_block():
    from src.spacehack.pygame_faction import frame_for

    ctx = quest_ctx()
    frame = frame_for(ctx)
    assert frame.identity_lines
    assert "LIVE" in frame.identity_lines[0]
    assert ctx.ship_registration in frame.identity_lines[0]
    assert "Reputation moves only" not in " ".join(frame.identity_lines)
    assert "nothing resolves" not in " ".join(frame.identity_lines)
    assert "Reputation moves only" not in " ".join(frame.identity_lines)

    dark = quest_ctx()
    dark.broadcast_dark = True
    assert "DARK" in frame_for(dark).identity_lines[0]

    masked = quest_ctx()
    masked.collected_ids = [_pirate_face()]
    masked.broadcast_identity = _pirate_face()
    lines = frame_for(masked).identity_lines
    assert "SPOOFED" in lines[0] and "KG-8812" in lines[0]
    assert "1 collected ID(s)" in lines[2]
