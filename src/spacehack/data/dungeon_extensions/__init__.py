"""Data definitions for reusable themed dungeon extensions.

Runtime behavior lives in :mod:`spacehack.dungeon_extensions`; this package
contains frozen content definitions so future caves, ruins, and stations can
reuse the same extension machinery.
"""

from __future__ import annotations

from dataclasses import dataclass

from ... import dungeon, world
from ...text import get as _t_get


@dataclass(frozen=True)
class EntryFlavor:
    """One-time narrative popup whose prose is authored in the overlay."""

    faction_label_key: str
    title_key: str
    message_key: str

    @property
    def faction_label(self) -> str:
        return _t_get(self.faction_label_key)

    @property
    def title(self) -> str:
        return _t_get(self.title_key)

    @property
    def message(self) -> str:
        return _t_get(self.message_key)


@dataclass(frozen=True)
class ActivationEvent:
    """One exploration-triggered encounter with overlay-backed prose."""

    id: str
    distance_fraction: float
    trigger_radius: int
    enemy_id: str
    count: int
    max_count: int
    faction_label_key: str
    title_key: str
    message_key: str
    # Optional state gate for late-phase events (for example, the escape
    # response after the Floor 5 data extraction).
    required_state: str = ""
    # Route direction used by the progress trigger: ``down`` is the original
    # descent route; ``up`` stages events while climbing back toward Mars.
    route_direction: str = "down"
    # Optional state that suppresses an event after a phase change.
    blocked_state: str = ""

    @property
    def faction_label(self) -> str:
        return _t_get(self.faction_label_key)

    @property
    def title(self) -> str:
        return _t_get(self.title_key)

    @property
    def message(self) -> str:
        return _t_get(self.message_key)

    @property
    def spawned_log(self) -> str:
        return _t_get("runtime.prison.security_spawned_log")

    @property
    def no_deploy_log(self) -> str:
        return _t_get("runtime.prison.security_no_deploy_log")


@dataclass(frozen=True)
class LandmarkVariant:
    """A weighted authored landmark layout candidate."""

    layout_id: str
    weight: float


@dataclass(frozen=True)
class DungeonInteractionSpec:
    """A data-defined interaction with overlay-backed player-facing text."""

    id: str
    char: str
    name_key: str
    action: str = "activate_state"
    state_key: str = ""
    required_state: str = ""
    destination_floor: int = 0
    faction_label_key: str = "runtime.prison.facility_faction"
    popup_title_key: str = "runtime.gate_popup_default_title"
    popup_message_key: str = "runtime.prison.interaction_activated"
    feature_theme: str = ""

    @property
    def name(self) -> str:
        return _t_get(self.name_key)

    @property
    def faction_label(self) -> str:
        return _t_get(self.faction_label_key)

    @property
    def popup_title(self) -> str:
        return _t_get(self.popup_title_key)

    @property
    def popup_message(self) -> str:
        return _t_get(self.popup_message_key).format(name=self.name)
    # When set, activating this interaction also completes the live
    # main-quest step with this objective type (generic — the runtime
    # never hardcodes a step id).
    objective_type: str = ""


@dataclass(frozen=True)
class ExtensionFloorSpec:
    """Procedural generation and activation data for one extension floor."""

    floor: int
    location_name_key: str
    params: dungeon.DungeonParams
    has_down_stairs: bool = False
    feature_theme: str = ""
    landmark_variants: tuple[LandmarkVariant, ...] = ()
    entry_flavor: EntryFlavor | None = None
    activation_events: tuple[ActivationEvent, ...] = ()
    interactions: tuple[DungeonInteractionSpec, ...] = ()
    # Reserve dormant security for the lockdown gauntlet: extra grey
    # units stocked near the floor entry that ALL activate when the
    # data is extracted (doc 30).
    lockdown_extras: int = 0

    @property
    def location_name(self) -> str:
        return _t_get(self.location_name_key)


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
            location_name_key="runtime.prison.floor1_name",
            # The entry narration is data-driven and shown once per run.
            lockdown_extras=8,
            entry_flavor=EntryFlavor(
                faction_label_key="runtime.prison.facility_faction",
                title_key="runtime.prison.entry_f1_title",
                message_key="runtime.prison.entry_f1_message",
            ),
            has_down_stairs=True,
            params=dungeon.DungeonParams(
                width=50,
                height=40,
                min_room_size=5,
                max_room_size=12,
                room_fill_pct=0.65,
                sight_radius=8,
                panel_tile=world.PRISON_PANEL_OFF,
                panel_density=0.02,
                scatter_fungus=False,
            ),
            activation_events=(
                ActivationEvent(
                    id="prison_ascent_f1_sentries",
                    distance_fraction=0.20,
                    trigger_radius=2,
                    enemy_id="sentry_drone",
                    count=2,
                    max_count=2,
                    faction_label_key="runtime.prison.security_faction",
                    title_key="runtime.prison.event.prison_ascent_f1_sentries.title",
                    message_key="runtime.prison.event.prison_ascent_f1_sentries.message",
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
                    faction_label_key="runtime.prison.security_faction",
                    title_key="runtime.prison.event.prison_ascent_f1_final_lockdown.title",
                    message_key="runtime.prison.event.prison_ascent_f1_final_lockdown.message",
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
                    faction_label_key="runtime.prison.security_faction",
                    title_key="runtime.prison.event.prison_floor1_security_alpha.title",
                    message_key="runtime.prison.event.prison_floor1_security_alpha.message",
                    blocked_state="prison_data_extracted",
                ),
                ActivationEvent(
                    id="prison_floor1_security_beta",
                    distance_fraction=0.76,
                    trigger_radius=2,
                    enemy_id="assault_drone",
                    count=1,
                    max_count=1,
                    faction_label_key="runtime.prison.security_faction",
                    title_key="runtime.prison.event.prison_floor1_security_beta.title",
                    message_key="runtime.prison.event.prison_floor1_security_beta.message",
                    blocked_state="prison_data_extracted",
                ),
            ),
        ),
        ExtensionFloorSpec(
            floor=2,
            location_name_key="runtime.prison.floor2_name",
            lockdown_extras=7,
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
                    faction_label_key="runtime.prison.security_faction",
                    title_key="runtime.prison.event.prison_ascent_f2_assault.title",
                    message_key="runtime.prison.event.prison_ascent_f2_assault.message",
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
                    faction_label_key="runtime.prison.security_faction",
                    title_key="runtime.prison.event.prison_ascent_f2_sentries.title",
                    message_key="runtime.prison.event.prison_ascent_f2_sentries.message",
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
                panel_tile=world.PRISON_PANEL_OFF,
                panel_density=0.02,
                scatter_fungus=False,
            ),
        ),
        ExtensionFloorSpec(
            floor=3,
            location_name_key="runtime.prison.floor3_name",
            lockdown_extras=6,
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
                    faction_label_key="runtime.prison.security_faction",
                    title_key="runtime.prison.event.prison_ascent_f3_sentries.title",
                    message_key="runtime.prison.event.prison_ascent_f3_sentries.message",
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
                    faction_label_key="runtime.prison.security_faction",
                    title_key="runtime.prison.event.prison_ascent_f3_heavy.title",
                    message_key="runtime.prison.event.prison_ascent_f3_heavy.message",
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
                panel_tile=world.PRISON_PANEL_OFF,
                panel_density=0.02,
                scatter_fungus=False,
            ),
        ),
        ExtensionFloorSpec(
            floor=4,
            location_name_key="runtime.prison.floor4_name",
            lockdown_extras=5,
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
                    faction_label_key="runtime.prison.security_faction",
                    title_key="runtime.prison.event.prison_ascent_f4_lockdown.title",
                    message_key="runtime.prison.event.prison_ascent_f4_lockdown.message",
                    required_state="prison_data_extracted",
                    route_direction="up",
                ),
            ),
            interactions=(
                DungeonInteractionSpec(
                    id="engineering_console",
                    char="C",
                    name_key="runtime.prison.engineering_name",
                    action="activate_state",
                    state_key="engineering_power",
                    popup_title_key="runtime.prison.engineering_popup_title",
                    popup_message_key="runtime.prison.engineering_popup_message",
                    feature_theme="engineering_room",
                ),
                DungeonInteractionSpec(
                    id="deep_elevator",
                    char="E",
                    name_key="runtime.prison.elevator_name",
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
                panel_tile=world.PRISON_PANEL_OFF,
                panel_density=0.02,
                scatter_fungus=False,
            ),
        ),
        ExtensionFloorSpec(
            floor=5,
            location_name_key="runtime.prison.floor5_name",
            feature_theme="deep_cell",
            lockdown_extras=3,
            landmark_variants=(
                LandmarkVariant("alien_prison_deep_cell", 100.0),
            ),
            entry_flavor=EntryFlavor(
                faction_label_key="runtime.prison.facility_faction",
                title_key="runtime.prison.entry_f5_title",
                message_key="runtime.prison.entry_f5_message",
            ),
            interactions=(
                DungeonInteractionSpec(
                    id="deep_cell_data_terminal",
                    char="T",
                    name_key="runtime.prison.data_terminal_name",
                    action="activate_state",
                    state_key="prison_data_extracted",
                    objective_type="prison",
                    faction_label_key="runtime.prison.facility_faction",
                    popup_title_key="runtime.prison.data_popup_title",
                    popup_message_key="runtime.prison.data_popup_message",
                ),
            ),
            params=dungeon.DungeonParams(
                width=58,
                height=46,
                min_room_size=8,
                max_room_size=18,
                room_fill_pct=0.60,
                sight_radius=11,
                panel_tile=world.PRISON_PANEL_OFF,
                panel_density=0.02,
                scatter_fungus=False,
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
