"""Tiles used only by authored planetary city maps."""

from .world import Tile


CITY_BUILDING_WALL = Tile(
    "city_building_wall", "#", False, (155, 185, 215), (45, 55, 70),
    blocked_message="The building wall blocks your path.",
)
CITY_BUILDING_ROOF = Tile(
    "city_building_roof", " ", False, (220, 200, 150), (88, 62, 40),
    blocked_message="The building roof blocks your path.",
)
CITY_BUILDING_FLOOR = Tile("city_building_floor", ".", True, (210, 220, 205), (70, 78, 68))
CITY_BUILDING_DOOR = Tile("city_building_door", "+", True, (100, 230, 255), (25, 65, 80))
CITY_PLAZA = Tile("city_plaza", ".", True, (235, 235, 220), (120, 132, 120))
CITY_FOUNTAIN = Tile("city_fountain", "*", True, (120, 235, 255), (36, 104, 122))
CITY_ORNAMENT = Tile("city_ornament", "o", True, (255, 220, 90), (92, 70, 30))
CITY_WATER = Tile(
    "city_water", "~", False, (80, 190, 235), (22, 82, 110),
    blocked_message="The water blocks your path.",
)
CITY_SHORE = Tile("city_shore", ".", True, (220, 205, 150), (100, 90, 55))
CITY_BRIDGE = Tile("city_bridge", "=", True, (220, 190, 115), (80, 62, 38))
