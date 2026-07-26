"""Merchant guild missions: trade and cargo work offered by the guild master.

The guild master offers the canonical delivery exemplar:
``merchants_supply_run_alpha_centauri``. Read the inline comments
on that mission before adding a new flavor or delivery - they
explain every field on :class:`Mission` so a content author can
copy the exemplar and adapt for new mission types.
"""
from . import Mission


MISSIONS: tuple[Mission, ...] = (
    # =============================================================
    # FUNCTIONAL DELIVERY EXEMPLAR
    # =============================================================
    # Canonical field-by-field reference lives on the :class:`Mission`
    # dataclass docstring (the authoritative contract). The block
    # below is the WORKED EXAMPLE that complements the dataclass
    # reference - keep them in sync if you change either.
    # =============================================================
    # The player accepts cargo on Earth, flies to Alpha Centauri's
    # Science Port, hands it to the Research Officer. The runtime
    # layer wires the full lifecycle:
    #   - try_accept_mission   loads cargo onto the owned hull
    #                           (refuses if the ship is over capacity)
    #   - is_deliverable_at    gates the Deliver NPC-talk option so
    #                           it only appears when the player is on
    #                           ac_station AND bumps research_officer
    #   - complete_mission     drops cargo + grants reward_gold
    #   - abort_mission        releases cargo without granting reward
    #
    # Field-by-field contract (this is the template to copy):
    #   id                         unique catalog key (used by the
    #                              quest log + dispatcher's find_mission
    #                              back-resolve)
    #   title                      short label for the offering modal
    #                              + log lines ("Delivered: <title>.")
    #   description                1-3 sentence blurb in the modal
    #   giver_npc_id               NPC id who offers this work
    #                              (must exist in data/npcs/)
    #   reward_gold                payout on complete (added to stats.gold)
    #   reward_xp                  payout on complete (logged only)
    #   recommended_class_id       optional \"best suited for X\" hint;
    #                              soft hint only, never a hard filter
    #   recommended_ship_min_cargo optional hull-capacity hint for the
    #                              offering modal; soft hint only
    #   required_cargo_size        CARGO LOAD - the units the mission
    #                              takes from the player's hull on
    #                              accept (released on deliver/abandon).
    #                              ZERO for flavor missions. GT zero
    #                              + a delivery target pair below =
    #                              a functional delivery mission.
    #   delivery_target_npc_id     NPC id the player hands cargo to;
    #                              required for delivery, None for flavor
    #   delivery_target_planet_id  planet id the player must be on to
    #                              deliver; required for delivery,
    #                              None for flavor
    # =============================================================
    Mission(
        id="merchants_supply_run_alpha_centauri",
        title="Supply run to Alpha Centauri",
        description=(
            "The research station orbiting Proxima Centauri is low "
            "on resealable research supplies. Ten units of cargo - "
            "calibration gear, biologics, the boring essentials. "
            "Hand them to the Research Officer on arrival."
        ),
        giver_npc_id="guild_master",
        reward_gold=150,
        reward_xp=30,
        recommended_class_id="merchant",
        recommended_ship_min_cargo=10,
        required_cargo_size=10,
        delivery_target_npc_id="research_officer",
        delivery_target_planet_id="ac_station",
    ),
)