"""A gated fixture chain for the rumor resolver/host gate contracts.

The live catalog (``dark_berth``) authors no gates, but the contracts
for attitude floors, trait gates, SPOOFED sheets and DARK-neutral
reads stay pinned. :func:`install` swaps the rumor resolvers onto
this registry for one test — the fixture rows mirror the retired
thin_month gates so the pinned behavior is unchanged.
"""

import sys

from spacehack.data.lore import RumorEntry

_NO_GATE = (None, None, None)

CHAIN: tuple[RumorEntry, ...] = (
    RumorEntry(
        id="gate_probe_1",
        chain="gate_probe",
        tier=1,
        value=1,
        sources=(("blockade_officer", "blockade_south", "militia", 0, None),),
    ),
    RumorEntry(
        id="gate_probe_2",
        chain="gate_probe",
        tier=2,
        requires=("gate_probe_1",),
        value=2,
        sources=(("blockade_officer", "blockade_south", "militia", 0, None),),
    ),
    RumorEntry(
        id="gate_probe_3",
        chain="gate_probe",
        tier=3,
        requires=("gate_probe_2",),
        value=3,
        sources=(("militia_captain", "earth", "militia", 26, "warrant_license"),),
    ),
    # A second chain on the same teller: openers and extensions must
    # coexist as rows in one sub-menu.
    RumorEntry(
        id="side_probe_1",
        chain="side_probe",
        tier=1,
        value=1,
        sources=(("blockade_officer", "blockade_south", "militia", 0, None),),
    ),
)


def install(monkeypatch) -> None:
    """Point every loaded rumor module instance at the fixture.

    The suite imports the package under both top-level names
    (``spacehack`` and ``src.spacehack``) — distinct module objects —
    so the registry seam is patched on each loaded instance.
    """
    reg = {entry.id: entry for entry in CHAIN}
    for name in ("spacehack.rumor", "src.spacehack.rumor"):
        mod = sys.modules.get(name)
        if mod is not None:
            monkeypatch.setattr(mod, "list_rumors", lambda: CHAIN)
            monkeypatch.setattr(mod, "find_rumor", reg.__getitem__)
