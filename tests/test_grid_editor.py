"""Doc 56 phase 3: the fitting-grid editor's pure state machine,
letter presentation, and POWER footer.

The pure layer is catalog-free plain ints; these tests pin cursor
bounds, pick/place semantics, ghost legality (bounds + overlap +
POWER, each red), the vacated-origin rule, determinism, and — the
reuse contract — that ghost legality is exactly ``fitting``'s
geometry + power composed, never a re-derived copy.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.spacehack import fitting
from src.spacehack.menus import _grid_editor as ge


def _state(**kwargs):
    return ge.EditorState(grid_w=4, grid_h=3, **kwargs)


class TestCursor:
    def test_moves_clamped_inside_grid(self):
        state = _state(cursor=(0, 0))
        assert ge.move_cursor(state, -3, -2).cursor == (0, 0)
        assert ge.move_cursor(state, 99, 99).cursor == (3, 2)
        assert ge.move_cursor(_state(cursor=(2, 1)), 1, 1).cursor == (3, 2)

    def test_move_preserves_hand(self):
        part = ge.HeldPart(1, 1)
        state = ge.hold_part(_state(cursor=(1, 1)), part)
        moved = ge.move_cursor(state, 1, 0)
        assert moved.held == part and moved.cursor == (2, 1)


class TestHand:
    def test_pickup_snaps_cursor_to_origin(self):
        part = ge.HeldPart(2, 2, origin=(2, 0))
        state = ge.hold_part(_state(cursor=(0, 0)), part)
        assert state.cursor == (2, 0)

    def test_handoff_keeps_cursor(self):
        part = ge.HeldPart(3, 3, upkeep=-4, origin=None)
        state = ge.hold_part(_state(cursor=(1, 2)), part)
        assert state.cursor == (1, 2)

    def test_release_empties_hand_keeps_cursor(self):
        part = ge.HeldPart(1, 1, origin=(1, 1))
        state = ge.release(ge.hold_part(_state(), part))
        assert state.held is None and state.cursor == (1, 1)


class TestGhostLegality:
    """drop_refusal: room (bounds + overlap) then power — the phase-2
    gate's rule composed with the vacated-origin exception."""

    def test_bounds_refusal(self):
        # A 2x2 part at the right edge cannot fit: x+2 > 4.
        state = _state(cursor=(3, 0), held=ge.HeldPart(2, 2))
        assert ge.drop_refusal(state, set(), 10, []) == "room"

    def test_overlap_refusal(self):
        occupied = fitting.footprint(1, 1, 2, 1)  # cells (1,1),(2,1)
        state = _state(cursor=(0, 1), held=ge.HeldPart(2, 1))
        assert ge.drop_refusal(state, occupied, 10, []) == "room"

    def test_vacated_origin_never_blocks(self):
        # The picked-up part's own origin cells are not blockers.
        origin = fitting.footprint(0, 0, 2, 2)
        state = _state(cursor=(0, 0), held=ge.HeldPart(2, 2, origin=(0, 0)))
        assert ge.drop_refusal(state, set(origin), 10, []) is None

    def test_power_refusal_after_geometry(self):
        # Handed-over part: geometry fine, resting grid negative.
        state = _state(cursor=(0, 0), held=ge.HeldPart(1, 1, upkeep=-4))
        assert ge.drop_refusal(state, set(), 3, [-4]) == "power"

    def test_power_exactly_zero_is_legal(self):
        state = _state(cursor=(0, 0), held=ge.HeldPart(3, 3, upkeep=-4))
        assert ge.drop_refusal(state, set(), 4, [-4]) is None

    def test_picked_up_rearrangement_never_power_red(self):
        # SETTLED 6: held-in-hand counts as fitted — the bonuses are the
        # tuple's own list, so a LEGAL resting grid stays drop-legal at
        # every cursor; only geometry can refuse a rearrangement.
        part = ge.HeldPart(2, 2, upkeep=-4, origin=(0, 0))
        for cursor in ((0, 0), (2, 1), (2, 0)):
            probe = ge.EditorState(4, 3, cursor, part)
            assert ge.drop_refusal(probe, set(), 7, [-4, 3]) is None

    def test_determinism(self):
        state = _state(cursor=(1, 1), held=ge.HeldPart(2, 2, -2, (0, 0)))
        occupied = fitting.footprint(2, 0, 2, 1)
        results = {
            ge.drop_refusal(state, occupied, 5, [-2])
            for _ in range(5)
        }
        assert results == {ge.drop_refusal(state, occupied, 5, [-2])}


class TestReusePins:
    """Ghost legality IS fitting's geometry + power — pinned so a
    re-derived copy inside the editor fails loudly."""

    def test_geometry_matches_fitting_placement_legal(self):
        occupied = fitting.footprint(2, 2, 1, 1)
        part = ge.HeldPart(2, 2)
        for x in range(-1, 5):
            for y in range(-1, 4):
                state = _state(cursor=(x, y), held=part)
                expected = fitting.placement_legal(4, 3, occupied, x, y, 2, 2)
                refused = ge.drop_refusal(state, occupied, 10, []) == "room"
                assert refused != expected, (x, y)

    def test_power_matches_fitting_net_power(self):
        state = _state(cursor=(0, 0), held=ge.HeldPart(1, 1, upkeep=-2))
        for base in (0, 1, 2, 5):
            for extra in ([], [3], [-1], [-1, 5]):
                expected = fitting.net_power(base, [*extra, -2]) >= 0
                assert (
                    ge.drop_refusal(state, set(), base, [*extra, -2]) is None
                ) == expected


class TestPowerFooter:
    def test_sign_conditional_components(self):
        assert ge.power_footer(4, [3, -2]) == "POWER: +7 gen / -2 upkeep / +5 net"

    def test_zero_components_render_bare(self):
        # Base 0, no modules: never "-0".
        assert ge.power_footer(0, []) == "POWER: 0 gen / 0 upkeep / 0 net"
        assert ge.power_footer(4, [-4]) == "POWER: +4 gen / -4 upkeep / 0 net"
        assert ge.power_footer(1, [-4]) == "POWER: +1 gen / -4 upkeep / -3 net"

    def test_parts_split_reactors_from_upkeep(self):
        assert ge.power_parts(6, [3, -1, -2]) == (9, -3, 6)
        assert ge.power_parts(4, [-4]) == (4, -4, 0)

    def test_ascii_hyphen_only(self):
        footer = ge.power_footer(2, [-5])
        assert "-" in footer and "\u2212" not in footer


def _piece(key, x, y, w, h, color=None):
    return ge.GridPiece(key=key, item_id="shield_mk1", x=x, y=y, w=w, h=h,
                        color=color)


class TestPaneRows:
    def test_letters_at_anchors_with_cursor_bracket(self):
        pieces = (_piece("module:0", 0, 0, 2, 2),)
        rows = ge.pane_rows(_state(cursor=(2, 0)), pieces, set(), 10, [])
        assert rows[0][0] == " S  S [.] ."
        assert rows[1][0] == " S  S  .  ."
        assert rows[2][0] == " .  .  .  ."

    def test_cursor_bracket_never_shifts_the_glyph_column(self):
        # Playtest 2026-09-30: brackets must WRAP the glyph — every
        # glyph centers in its 3-char cell, cursor or not, so columns
        # stay put as the cursor moves.
        pieces = (_piece("module:0", 0, 0, 4, 1),)  # a full row of S
        rows = ge.pane_rows(_state(cursor=(2, 0)), pieces, set(), 10, [])
        assert rows[0][0] == " S  S [S] S"
        assert [
            index for index, char in enumerate(rows[0][0]) if char == "S"
        ] == [1, 4, 7, 10]

    def test_runs_text_equals_row_text(self):
        pieces = (_piece("module:0", 0, 0, 2, 2, color=(1, 2, 3)),)
        for text, runs in ge.pane_rows(_state(), pieces, set(), 10, []):
            assert "".join(part for part, _c in runs) == text

    def test_hovered_piece_highlights_whole_footprint_in_accent(self):
        # Playtest 2026-09-30: hover reads the PIECE, not the cell —
        # every letter of the piece under the cursor goes accent
        # (overriding the tier colour, like the ghost's legality
        # colour does); empty cells stay plain.
        from src.spacehack import pygame_ui

        palette = pygame_ui.DEFAULT_PALETTE
        pieces = (_piece("module:0", 0, 0, 2, 2, color=(9, 9, 9)),)
        rows = ge.pane_rows(_state(cursor=(1, 1)), pieces, set(), 10, [])
        assert [color for _t, color in rows[0][1]] == [
            palette.accent, palette.accent, None, None,
        ]
        assert rows[1][1] == (
            (" S ", palette.accent), ("[S]", palette.accent),
            (" . ", None), (" .", None),
        )
        # Hovering only applies empty-handed: while holding, the ghost
        # colour governs and untouched piece letters keep their tier.
        part = ge.HeldPart(1, 1)
        rows = ge.pane_rows(
            _state(cursor=(3, 2), held=part), pieces, set(), 10, [],
            held_letter="L",
        )
        assert all(
            color == (9, 9, 9)
            for text, color in rows[0][1] if text.strip() == "S"
        )

    def test_ghost_legality_colour_overrides_tier(self):
        from src.spacehack import pygame_ui

        palette = pygame_ui.DEFAULT_PALETTE
        pieces = (_piece("module:0", 0, 0, 2, 2, color=(9, 9, 9)),)
        part = ge.HeldPart(2, 2)
        # Red ghost: dropping on the occupied corner overlaps.
        state = ge.EditorState(4, 3, (0, 0), part)
        rows = ge.pane_rows(
            state, (), fitting.footprint(0, 0, 2, 2), 10, [], held_letter="S",
        )
        assert [color for _t, color in rows[0][1]] == [
            palette.negative, palette.negative, None, None,
        ]
        # Green ghost: an empty corner — legality overrides the tier
        # colour the placed letters keep.
        state = ge.EditorState(4, 3, (2, 1), part)
        rows = ge.pane_rows(
            state, pieces, fitting.footprint(0, 0, 2, 2), 10, [], held_letter="S",
        )
        assert [color for _t, color in rows[1][1]] == [
            (9, 9, 9), (9, 9, 9), palette.positive, palette.positive,
        ]

    def test_held_piece_cells_vacate(self):
        # The picked-up piece is omitted from pieces by the HOST; the
        # pane paints '.' there — pinned so the omission contract holds.
        pieces = ()  # host omitted the held piece
        part = ge.HeldPart(1, 1, origin=(0, 0))
        state = ge.EditorState(4, 3, (1, 0), part)
        rows = ge.pane_rows(state, pieces, set(), 10, [], held_letter="L")
        assert rows[0][0] == " . [L] .  ."


class TestLetters:
    def test_every_registered_item_has_a_letter(self):
        from src.spacehack.data.modules import list_modules
        from src.spacehack.data.weapons import list_weapons

        ids = {spec.id for spec in (*list_weapons(), *list_modules())}
        missing = ids - set(ge.LETTERS)
        assert not missing, f"letters missing for: {sorted(missing)}"

    def test_unknown_id_fails_loudly(self):
        try:
            ge.letter("no_such_item")
        except KeyError:
            pass
        else:
            raise AssertionError("unknown ids must fail loudly")

    def test_glyphs_are_cp437_safe(self):
        allowed = set("LSRTGCAHLMPEB.[] ")
        rendered = set(
            char
            for row in ge.pane_rows(ge.EditorState(4, 3), (), set(), 5, [])
            for char in row[0]
        )
        assert rendered <= allowed


class TestPieceAt:
    def test_finds_containing_piece_only(self):
        pieces = (_piece("module:0", 1, 1, 2, 1),)
        assert ge.piece_at(pieces, (1, 1)).key == "module:0"
        assert ge.piece_at(pieces, (2, 1)).key == "module:0"
        # Lexicographic traps: same column-bounds, wrong row.
        assert ge.piece_at(pieces, (1, 2)) is None
        assert ge.piece_at(pieces, (1, 0)) is None
        assert ge.piece_at((), (0, 0)) is None


def test_footprint_lines_draw_the_shape_in_family_letters():
    """The shopping footprint (ruling 2026-09-30): the part's grid
    shape as bracketed letter-block rows — one row per grid H, one
    [X] per grid W, in the SETTLED-15 family letter."""
    from src.spacehack.menus._grid_editor import footprint_lines

    assert footprint_lines("light_laser", 1, 1) == ("[L]",)
    assert footprint_lines("plasma_cannon", 2, 3) == ("[P][P]",) * 3
    assert footprint_lines("reactor_mk4", 3, 3) == ("[R][R][R]",) * 3
    assert footprint_lines("smuggler_hold_mk1", 2, 1) == ("[H][H]",)


def test_footprint_lines_are_cp437_safe():
    from src.spacehack.menus._grid_editor import footprint_lines

    for line in footprint_lines("shield_mk4", 3, 3):
        assert all(ch in "[]SRTGCARHL MPEB" for ch in line)


def test_weapon_detail_hover_line():
    """Playtest 2026-09-30: terse, with the firing costs — AP plus
    power for energy/plasma, the rack for missiles (no Pow segment:
    missiles pay ammo, not watts)."""
    from src.spacehack.data.weapons import find_weapon

    assert ge._weapon_detail(find_weapon("medium_laser")) == (
        "Dmg 6  Acc 72%  Rng 1-5  AP 1  Pow 1"
    )
    assert ge._weapon_detail(find_weapon("plasma_cannon")) == (
        "Dmg 24  Acc 70%  Rng 1-8  AP 2  Pow 4"
    )
    detail = ge._weapon_detail(find_weapon("light_missile"))
    assert detail == "Dmg 14  Acc 72%  Rng 2-9  AP 2  Ammo 4/4"
    assert "Pow" not in detail


def test_hover_readout_is_name_plus_stats():
    """Playtest 2026-09-30: the tooltip shows the tiered name and the
    IMPORTANT stats — the effective stat line at the instance's tier,
    not the authored prose."""
    from src.spacehack.ship import StoredEquipment

    base = ge._entry_detail(StoredEquipment("module", "shield_mk2"))
    assert base == "Shield Mk. 2 - Power: -2  Shields: +45"
    raised = ge._entry_detail(
        StoredEquipment("module", "shield_mk2", quality=2),
    )
    assert raised == "Overclocked Shield Mk. 2 - Power: -3  Shields: +59"
