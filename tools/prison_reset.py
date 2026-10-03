"""Copy a reference save with the alien prison reset for a re-run.

The playtest instrument for doc 48 phase 9's machines checkpoint: the
two reference saves are POST-prison, so their five cached prison
floors were generated before the machine re-pin (they still hold the
sentry/assault drones) and the extension state says the data is
already extracted. This copies the save with:

* ``dungeon_extension`` nulled — ``enter_extension`` builds a fresh
  state (no fired events, no ``prison_data_extracted`` /
  ``engineering_power`` flags, floor-1 entry, one-time entry flavor
  popups re-armed);
* every ``extension:mars_alien_prison:floor:*`` cache evicted — the
  floors regenerate through the live pipeline with the machines.

Untouched on purpose: the quest (``act1_prison`` stays completed —
``start_prison_objective`` no-ops, so no quest UI re-tracks; the
Floor 5 terminal re-completes an already-complete step on the copy),
the cached Mars surface (the revealed stairs ARE the way back in),
the epilogue orbit flag, and everything else on the sheet.

Usage:
    python3 tools/prison_reset.py saves/grid_labs_sirian_bountyhunter.json
    python3 tools/prison_reset.py SAVE --out SAVE_PRISON_RESET.json
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

_PRISON_PREFIX = "extension:mars_alien_prison:floor:"


def reset_prison(data: dict) -> dict:
    """Return the save dict with the prison reset in place."""
    ext = data.get("dungeon_extension")
    if ext is not None and ext.get("extension_id") != "mars_alien_prison":
        raise SystemExit(
            f"refusing: dungeon_extension is {ext.get('extension_id')!r}, "
            "not the alien prison"
        )
    interiors = data.get("interiors") or {}
    evicted = sorted(k for k in interiors if k.startswith(_PRISON_PREFIX))
    for key in evicted:
        del interiors[key]
    data["dungeon_extension"] = None
    data["interiors"] = interiors
    print(f"dungeon_extension: reset ({len(ext.get('activated_events', []))} "
          f"fired events, flags {ext.get('state_flags')})")
    print(f"evicted {len(evicted)} cached prison floors: {evicted}")
    kept = [k for k in interiors if "mars" in k]
    print(f"mars caches kept: {sorted(kept)}")
    return data


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("save", help="the savegame to copy from")
    parser.add_argument("--out", default="",
                        help="output path (default: <stem>_prison_reset.json)")
    args = parser.parse_args()

    src = Path(args.save)
    if not src.is_file():
        raise SystemExit(f"no such save: {src}")
    out = Path(args.out) if args.out else src.with_name(
        f"{src.stem}_prison_reset{src.suffix}",
    )
    data = reset_prison(json.loads(src.read_text()))
    out.write_text(json.dumps(data))
    print(f"wrote {out} ({out.stat().st_size:,} bytes)")


if __name__ == "__main__":
    main()
