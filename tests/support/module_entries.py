"""Shared ship-module test fixtures (doc 47 phase 3).

``OwnedShip.modules`` and ``EnemyInstance.modules`` hold
``StoredEquipment`` entries; tests build them through this one
helper instead of copy-pasting the constructor.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from src.spacehack.ship import StoredEquipment


def module_entry(module_id: str, quality: int = 0) -> StoredEquipment:
    """One installed/flown module entry (the OwnedShip.modules shape)."""
    return StoredEquipment("module", module_id, quality=quality)
