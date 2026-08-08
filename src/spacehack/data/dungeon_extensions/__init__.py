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


@dataclass(frozen=True)
class ExtensionFloorSpec:
    """Procedural generation and activation data for one extension floor."""

    floor: int
    location_name: str
    params: dungeon.DungeonParams
    entry_flavor: EntryFlavor | None = None
    activation_events: tuple[ActivationEvent, ...] = ()


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
                ),
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
