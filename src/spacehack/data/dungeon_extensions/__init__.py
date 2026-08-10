"""Data definitions for reusable themed dungeon extensions.

Runtime behavior lives in :mod:`spacehack.dungeon_extensions`; this package
contains frozen content definitions so future caves, ruins, and stations can
reuse the same extension machinery.
"""

from __future__ import annotations

from dataclasses import dataclass

from ... import dungeon


@dataclass(frozen=True)
class EntryFlavor:
    """One-time narrative popup shown on first entry to a floor."""

    faction_label: str
    title: str
    message: str


@dataclass(frozen=True)
class ActivationEvent:
    """One exploration-triggered dormant encounter."""

    id: str
    distance_fraction: float
    trigger_radius: int
    enemy_id: str
    count: int
    max_count: int
    faction_label: str
    title: str
    message: str
    # Optional state gate for late-phase events (for example, the escape
    # response after the Floor 5 data extraction).
    required_state: str = ""
    # Route direction used by the progress trigger: ``down`` is the original
    # descent route; ``up`` stages events while climbing back toward Mars.
    route_direction: str = "down"
    # Optional state that suppresses an event after a phase change.
    blocked_state: str = ""


@dataclass(frozen=True)
class LandmarkVariant:
    """A weighted authored landmark layout candidate."""

    layout_id: str
    weight: float


@dataclass(frozen=True)
class DungeonInteractionSpec:
    """A data-defined interaction stamped into an extension floor."""

    id: str
    char: str
    name: str
    action: str = "activate_state"
    state_key: str = ""
    required_state: str = ""
    destination_floor: int = 0
    faction_label: str = "ALIEN FACILITY"
    popup_title: str = "SYSTEM UPDATE"
    popup_message: str = "A dormant system responds."
    feature_theme: str = ""
    # When set, activating this interaction also completes the live
    # main-quest step with this objective type (generic — the runtime
    # never hardcodes a step id).
    objective_type: str = ""


@dataclass(frozen=True)
class ExtensionFloorSpec:
    """Procedural generation and activation data for one extension floor."""

    floor: int
    location_name: str
    params: dungeon.DungeonParams
    has_down_stairs: bool = False
    feature_theme: str = ""
    landmark_variants: tuple[LandmarkVariant, ...] = ()
    entry_flavor: EntryFlavor | None = None
    activation_events: tuple[ActivationEvent, ...] = ()
    interactions: tuple[DungeonInteractionSpec, ...] = ()


@dataclass(frozen=True)
class DungeonExtensionSpec:
    """A reusable themed multi-floor dungeon definition."""

    id: str
    floors: tuple[ExtensionFloorSpec, ...]

    def floor(self, floor_number: int) -> ExtensionFloorSpec:
        """Return a floor by number, raising ``KeyError`` when absent."""
        for floor_spec in self.floors:
            if floor_spec.floor == floor_number:
                return floor_spec
        raise KeyError(f"unknown floor {floor_number} for extension {self.id!r}")


_ALIEN_PRISON = DungeonExtensionSpec(
    id="mars_alien_prison",
    floors=(
        ExtensionFloorSpec(
            floor=1,
            location_name="Alien Prison F1",
            # The entry narration is data-driven and shown once per run.
            entry_flavor=EntryFlavor(
                faction_label="ALIEN FACILITY",
                title="THE PRISON BELOW",
                message=(
                    "The stairs descend into a facility built beneath Mars. "
                    "The walls are seamless, the air is still, and every "
                    "surface suggests a technology humanity never reached. "
                    "There are no voices. No prisoners. Only dormant systems "
                    "waiting in the dark."
                ),
            ),
            has_down_stairs=True,
            params=dungeon.DungeonParams(
                width=50,
                height=40,
                min_room_size=5,
                max_room_size=12,
                room_fill_pct=0.65,
                sight_radius=8,
            ),
            activation_events=(
                ActivationEvent(
                    id="prison_ascent_f1_sentries",
                    distance_fraction=0.20,
                    trigger_radius=2,
                    enemy_id="sentry_drone",
                    count=2,
                    max_count=2,
                    faction_label="ALIEN SECURITY",
                    title="SURFACE SECURITY AWAKENS",
                    message=(
                        "The upper staging floor is no longer dormant. Sentry drones "
                        "drop from ceiling rails and cut off the last quiet route "
                        "to the Mars surface."
                    ),
                    required_state="prison_data_extracted",
                    route_direction="up",
                ),
                ActivationEvent(
                    id="prison_ascent_f1_final_lockdown",
                    distance_fraction=0.68,
                    trigger_radius=2,
                    enemy_id="assault_drone",
                    count=3,
                    max_count=3,
                    faction_label="ALIEN SECURITY",
                    title="TOTAL FACILITY LOCKDOWN",
                    message=(
                        "Warning glyphs ignite across the walls. Three assault frames "
                        "advance through the intake halls - the prison's final "
                        "response before it lets you see the sky again."
                    ),
                    required_state="prison_data_extracted",
                    route_direction="up",
                ),
                ActivationEvent(
                    id="prison_floor1_security_alpha",
                    distance_fraction=0.42,
                    trigger_radius=2,
                    enemy_id="sentry_drone",
                    count=1,
                    max_count=1,
                    faction_label="ALIEN SECURITY",
                    title="SECURITY POWER RISING",
                    message=(
                        "A buried current ripples through the facility. "
                        "Panels brighten in the distance, then a dormant "
                        "security frame unfolds with a sound like breaking ice. "
                        "Something is bringing this place back online."
                    ),
                    blocked_state="prison_data_extracted",
                ),
                ActivationEvent(
                    id="prison_floor1_security_beta",
                    distance_fraction=0.76,
                    trigger_radius=2,
                    enemy_id="assault_drone",
                    count=1,
                    max_count=1,
                    faction_label="ALIEN SECURITY",
                    title="DEEPER SYSTEMS AWAKEN",
                    message=(
                        "The prison's deeper security lattice answers the first "
                        "signal. Heavy footsteps echo through the corridors. "
                        "Whatever is waking below is more prepared than the "
                        "surface systems."
                    ),
                    blocked_state="prison_data_extracted",
                ),
            ),
        ),
        ExtensionFloorSpec(
            floor=2,
            location_name="Alien Prison F2",
            has_down_stairs=True,
            feature_theme="prisoner_quarters",
            activation_events=(
                ActivationEvent(
                    id="prison_ascent_f2_assault",
                    distance_fraction=0.24,
                    trigger_radius=2,
                    enemy_id="assault_drone",
                    count=2,
                    max_count=2,
                    faction_label="ALIEN SECURITY",
                    title="QUARTERS LOCKDOWN",
                    message=(
                        "The prisoner quarters seal in sequence. Two heavy frames "
                        "force their way through the cell blocks as the dormant "
                        "security grid learns your route."
                    ),
                    required_state="prison_data_extracted",
                    route_direction="up",
                ),
                ActivationEvent(
                    id="prison_ascent_f2_sentries",
                    distance_fraction=0.72,
                    trigger_radius=2,
                    enemy_id="sentry_drone",
                    count=2,
                    max_count=2,
                    faction_label="ALIEN SECURITY",
                    title="CELL BLOCK PURSUIT",
                    message=(
                        "The cell doors flash awake behind you. Sentry drones pour "
                        "from the observation posts, driving you toward the upper "
                        "stairs."
                    ),
                    required_state="prison_data_extracted",
                    route_direction="up",
                ),
            ),
            params=dungeon.DungeonParams(
                width=50,
                height=40,
                min_room_size=4,
                max_room_size=10,
                room_fill_pct=0.58,
                sight_radius=8,
                monster_pool=("hull_parasite", "rock_scavenger"),
                monster_density=1.8,
            ),
        ),
        ExtensionFloorSpec(
            floor=3,
            location_name="Alien Prison F3",
            has_down_stairs=True,
            feature_theme="defensive_layer",
            activation_events=(
                ActivationEvent(
                    id="prison_ascent_f3_sentries",
                    distance_fraction=0.28,
                    trigger_radius=2,
                    enemy_id="sentry_drone",
                    count=2,
                    max_count=2,
                    faction_label="ALIEN SECURITY",
                    title="DEFENSIVE LATTICE ONLINE",
                    message=(
                        "The defensive layer wakes in sections. Two sentry drones "
                        "slide from the walls and triangulate your position. "
                        "Every corridor is becoming a firing lane."
                    ),
                    required_state="prison_data_extracted",
                    route_direction="up",
                ),
                ActivationEvent(
                    id="prison_ascent_f3_heavy",
                    distance_fraction=0.78,
                    trigger_radius=2,
                    enemy_id="assault_drone",
                    count=1,
                    max_count=1,
                    faction_label="ALIEN SECURITY",
                    title="DEFENSES ESCALATE",
                    message=(
                        "The sentries' signal summons something heavier. An assault "
                        "drone unfolds in the corridor ahead, sealing the climb "
                        "with bronze armor and cutting limbs."
                    ),
                    required_state="prison_data_extracted",
                    route_direction="up",
                ),
            ),
            params=dungeon.DungeonParams(
                width=50,
                height=40,
                min_room_size=5,
                max_room_size=11,
                room_fill_pct=0.62,
                sight_radius=8,
                monster_pool=("sentry_drone", "hull_parasite", "assault_drone"),
                monster_density=2.0,
            ),
        ),
        ExtensionFloorSpec(
            floor=4,
            location_name="Alien Prison F4",
            has_down_stairs=True,
            feature_theme="high_risk_quarters",
            activation_events=(
                ActivationEvent(
                    id="prison_ascent_f4_lockdown",
                    distance_fraction=0.25,
                    trigger_radius=2,
                    enemy_id="assault_drone",
                    count=1,
                    max_count=1,
                    faction_label="ALIEN SECURITY",
                    title="HIGH-RISK LOCKDOWN",
                    message=(
                        "The high-risk cells unlock behind you. A heavy security "
                        "frame tears itself from a charging cradle and blocks "
                        "the route upward. The prison is hunting you now."
                    ),
                    required_state="prison_data_extracted",
                    route_direction="up",
                ),
            ),
            interactions=(
                DungeonInteractionSpec(
                    id="engineering_console",
                    char="C",
                    name="Engineering Console",
                    action="activate_state",
                    state_key="engineering_power",
                    popup_title="ENGINEERING POWER RESTORED",
                    popup_message=(
                        "A buried engineering lattice surges awake. Power flows "
                        "through the high-risk quarters, and the deep elevator "
                        "unlocks below."
                    ),
                    feature_theme="engineering_room",
                ),
                DungeonInteractionSpec(
                    id="deep_elevator",
                    char="E",
                    name="Deep Elevator",
                    action="transition_floor",
                    required_state="engineering_power",
                    destination_floor=5,
                ),
            ),
            params=dungeon.DungeonParams(
                width=52,
                height=42,
                min_room_size=6,
                max_room_size=14,
                room_fill_pct=0.64,
                sight_radius=9,
                monster_pool=("sentry_drone", "assault_drone", "hull_parasite"),
                monster_density=2.4,
            ),
        ),
        ExtensionFloorSpec(
            floor=5,
            location_name="Alien Prison F5",
            feature_theme="deep_cell",
            landmark_variants=(
                LandmarkVariant("alien_prison_deep_cell", 100.0),
            ),
            entry_flavor=EntryFlavor(
                faction_label="ALIEN FACILITY",
                title="THE DEEP CELL",
                message=(
                    "The elevator opens onto a chamber so vast it swallows "
                    "the light. A prison cell built for something enormous - "
                    "and the doors that once held it have been torn from "
                    "their frames. Terminals dot the floor, dark and silent. "
                    "Somewhere in the dark, one of them still answers."
                ),
            ),
            interactions=(
                DungeonInteractionSpec(
                    id="deep_cell_data_terminal",
                    char="T",
                    name="Data Terminal",
                    action="activate_state",
                    state_key="prison_data_extracted",
                    objective_type="prison",
                    faction_label="ALIEN FACILITY",
                    popup_title="DATA STREAM",
                    popup_message=(
                        "The terminal floods the cell with light. A torrent of "
                        "data pours out - coordinates, schematics, structures "
                        "built for something far larger than a human frame. "
                        "None of it decodes. The data is alien beyond any "
                        "human language or logic, but the sheer volume is "
                        "proof enough: something was here, and it escaped. "
                        "Then the dark panels flare white. Emergency power "
                        "surges through the facility. The prison is fully awake. "
                        "The route back to Mars will not be quiet."
                    ),
                ),
            ),
            params=dungeon.DungeonParams(
                width=58,
                height=46,
                min_room_size=8,
                max_room_size=18,
                room_fill_pct=0.60,
                sight_radius=11,
            ),
        ),
    ),
)


_BY_ID: dict[str, DungeonExtensionSpec] = {
    _ALIEN_PRISON.id: _ALIEN_PRISON,
}


def find_extension(extension_id: str) -> DungeonExtensionSpec:
    """Look up a themed dungeon extension by stable ID."""
    try:
        return _BY_ID[extension_id]
    except KeyError:
        raise KeyError(f"unknown dungeon extension id: {extension_id!r}") from None
