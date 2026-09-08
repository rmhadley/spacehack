"""Tests for the silhouette→rect decomposition (doc 40 phase 6c).

The seal-phantom contract: walkable-by-parse void inside a row span
that 8-touches the hull fills hull-solid (corner-cut entries); void
outside the row spans is true space and must never fill. The escape
flood is the no-diag rule: 0 escapes means sealed.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

TOOLS = Path(__file__).resolve().parent.parent / "tools"
sys.path.insert(0, str(TOOLS))

from rect_from_silhouette import (  # noqa: E402
    LayoutEscapeError,
    _fill_enclosed_void,
    _quantize,
    _seal_phantom_entries,
    escape_flood,
    process,
)

# nub floats above the hull (prong-tip analogue); the channel between
# the two masses is open to the top border — an escape unless sealed.
# Grid is quantum-exact: each 3 mask columns/rows sample one quantum.
NUB_AND_CHANNEL = [
    "..................#########..............",
    "..................#########..............",
    ".........................................",
    "##########..........##########...........",
    "##########..........##########...........",
    "##########..........##########...........",
    "##########################################",
    "##########################################",
    "##########################################",
]


def _quantized() -> tuple[list[list[bool]], int, int]:
    w = max(len(r) for r in NUB_AND_CHANNEL)
    mask = [[(x < len(r) and r[x] == "#") for x in range(w)]
            for r in NUB_AND_CHANNEL]
    q, qw, qh = _quantize(mask, w, len(mask), 5, False)
    _fill_enclosed_void(q, qw, qh)
    return q, qw, qh


def test_channel_is_an_escape_before_seal():
    q, qw, qh = _quantized()
    assert escape_flood(q, qw, qh) > 0


def test_seal_fills_in_span_channel_only():
    q, qw, qh = _quantized()
    sealed = _seal_phantom_entries(q, qw, qh)
    assert sealed > 0
    assert escape_flood(q, qw, qh) == 0
    # channel fused: the hull row is solid across its whole span
    assert all(q[1][x] for x in range(0, 10))
    # the void beside the floating nub is outside its row span — true
    # space, never fills despite 8-touching the hull below
    assert not q[0][9]


def test_process_fails_unsealed_and_passes_sealed(tmp_path):
    src = tmp_path / "hull.txt"
    src.write_text("\n".join(NUB_AND_CHANNEL) + "\n")
    with pytest.raises(LayoutEscapeError):
        process(src)
    art, qw, qh = process(src, seal_phantom=True)
    rows = art.rstrip("\n").split("\n")
    assert len(rows) == qh * 3
