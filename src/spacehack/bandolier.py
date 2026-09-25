"""The bandolier — per-caliber tracked ammo reserves (doc 52).

Ammo never occupies Expedition Pack slots: each caliber (weapon-side
``ammo_type``) carries its own current/cap pool in
``GameContext.bandolier``. Pickups and restock refill it (overflow
ignored, SETTLED 2); reload draws it down through
:mod:`spacehack.ground_weapon_ammo`. Phase 1 ships the base caps; the
future armor/cybernetics pass feeds ``effective_cap`` its bonus term
(SETTLED 4 — the seam, never the fold).
"""

from __future__ import annotations

_SPECS_BY_AMMO_TYPE: dict[str, object] | None = None


def _spec_by_ammo_type() -> dict[str, object]:
    """The ammo catalog keyed by weapon-side caliber (one spec each)."""
    global _SPECS_BY_AMMO_TYPE
    if _SPECS_BY_AMMO_TYPE is None:
        from .data.ground_items import list_ground_ammo

        _SPECS_BY_AMMO_TYPE = {spec.ammo_type: spec for spec in list_ground_ammo()}
    return _SPECS_BY_AMMO_TYPE


def effective_cap(ammo_type: str, bonus: int = 0) -> int:
    """Carry cap for one caliber: catalog cap + gear bonus (phase-4 seam).

    Raises :class:`KeyError` for unknown calibers — callers parsing
    untrusted data skip on that signal.
    """
    return _spec_by_ammo_type()[ammo_type].carry_cap + bonus


def space_remaining(bandolier: dict[str, int], ammo_type: str, cap: int) -> int:
    """Rounds a caliber can still take before its cap."""
    return max(0, cap - bandolier.get(ammo_type, 0))


def add_rounds(
    bandolier: dict[str, int], ammo_type: str, rounds: int, cap: int,
) -> dict[str, int]:
    """The pool after refilling one caliber, clamped at ``cap`` (pure).

    Overflow past the cap is ignored (SETTLED 2); derive the accepted
    count from the before/after difference.
    """
    accepted = max(0, min(rounds, space_remaining(bandolier, ammo_type, cap)))
    if accepted <= 0:
        return dict(bandolier)
    return {**bandolier, ammo_type: bandolier.get(ammo_type, 0) + accepted}


def refill(ctx, ammo_type: str, rounds: int) -> int:
    """Refill ``ctx``'s bandolier at the caliber's effective cap.

    The one mutation path shared by pickups, restock, and migration;
    returns the rounds actually added (0 = at cap, nothing changed).
    """
    before = ctx.bandolier.get(ammo_type, 0)
    ctx.bandolier = add_rounds(
        ctx.bandolier, ammo_type, rounds, effective_cap(ammo_type),
    )
    return ctx.bandolier.get(ammo_type, 0) - before
