"""Trade goods catalog: the initial goods for v1.

Each entry is a :class:`TradeGood` frozen dataclass. Goods are grouped
by category: biological, industrial, raw_material, luxury, tech, contraband.
"""

from . import TradeGood


TRADE_GOODS: tuple[TradeGood, ...] = (
    # --- Biological ---
    TradeGood(
        id="food_rations",
        name="Food Rations",
        description="Packed, preserved, and ready for deep-space transit.",
        base_price=20,
        category="biological",
        volume=1,
        rarity=0.6,
    ),
    TradeGood(
        id="medical_supplies",
        name="Medical Supplies",
        description="Bandages, antiseptics, and emergency field kits.",
        base_price=60,
        category="biological",
        volume=1,
        rarity=0.4,
    ),
    TradeGood(
        id="pharmaceuticals",
        name="Pharmaceuticals",
        description="Advanced gene-tailored therapeutics and performance enhancers.",
        base_price=90,
        category="biological",
        volume=1,
        rarity=0.3,
    ),
    # --- Industrial ---
    TradeGood(
        id="electronics",
        name="Consumer Electronics",
        description="Comms gear, nav computers, and everyday consumer tech.",
        base_price=80,
        category="industrial",
        volume=1,
        rarity=0.5,
    ),
    TradeGood(
        id="machine_parts",
        name="Machine Parts",
        description="Replacement spools, gaskets, filters - the industrial backbone.",
        base_price=50,
        category="industrial",
        volume=2,
        rarity=0.5,
    ),
    TradeGood(
        id="ship_components",
        name="Ship Components",
        description="Structural panels, conduits, and drive-assembly spares.",
        base_price=110,
        category="industrial",
        volume=2,
        rarity=0.4,
    ),
    TradeGood(
        id="textiles",
        name="Textiles",
        description="Bolts of synthetic fabric and weatherproof weaves.",
        base_price=35,
        category="industrial",
        volume=2,
        rarity=0.6,
    ),
    # --- Raw Materials ---
    TradeGood(
        id="scrap_metal",
        name="Scrap Metal",
        description="Salvaged hull plating, wiring, and structural debris.",
        base_price=10,
        category="raw_material",
        volume=1,
        rarity=0.8,
    ),
    TradeGood(
        id="fuel_cells",
        name="Fuel Cells",
        description="Standardised hydrogen cells for jump drives and reactors.",
        base_price=40,
        category="raw_material",
        volume=1,
        rarity=0.6,
    ),
    TradeGood(
        id="ore_processed",
        name="Processed Ore",
        description="Refined metal ingots, ready for fabrication.",
        base_price=30,
        category="raw_material",
        volume=2,
        rarity=0.7,
    ),
    # --- Luxury ---
    TradeGood(
        id="luxury_goods",
        name="Luxury Goods",
        description="Fine spirits, silks, jewellery - the spoils of civilisation.",
        base_price=150,
        category="luxury",
        volume=1,
        rarity=0.3,
    ),
    TradeGood(
        id="rare_earth_metals",
        name="Rare Earth Metals",
        description="Exotic elements essential for high-end manufacturing.",
        base_price=200,
        category="luxury",
        volume=1,
        rarity=0.2,
    ),
    # --- Tech ---
    TradeGood(
        id="research_data",
        name="Research Data",
        description="Encrypted datacubes from long-baseline stellar surveys.",
        base_price=120,
        category="tech",
        volume=1,
        rarity=0.3,
    ),
    TradeGood(
        id="reference_recorder",
        name="Data Recorder",
        description=(
            "A data recorder recovered from a derelict scout near Sirius - "
            "the missing dataset the lab needs to finish the console work."
        ),
        base_price=200,
        category="tech",
        volume=1,
        rarity=0.1,
    ),
    TradeGood(
        id="alien_device",
        name="Ancient Alien Device",
        description=(
            "An alien device recovered from a sealed Procyon C cache. Its "
            "surface carries the same undulation as the Mars console."
        ),
        base_price=200,
        category="tech",
        volume=1,
        rarity=0.1,
    ),
    TradeGood(
        id="calibration_data",
        name="Cutter Calibration Data",
        description=(
            "Frequency-alignment telemetry recovered from a derelict "
            "near Vega - the last thing the cutter needs before it "
            "can be assembled."
        ),
        base_price=250,
        category="tech",
        volume=1,
        rarity=0.1,
    ),
    # --- Contraband ---
    TradeGood(
        id="weapons_blackmarket",
        name="Black Market Weapons",
        description="Unregistered side-arms and mil-spec ordnance - hot, illegal, lucrative.",
        base_price=250,
        category="contraband",
        volume=1,
        rarity=0.1,
    ),
)
