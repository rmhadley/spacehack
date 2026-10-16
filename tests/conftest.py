"""Shared test fixtures.

The ground-session leak guard: several files drive
``_rules_ground.init()`` (or set ``_state``) without restoring it,
which reroutes later stateless callers through a stale session's ctx
(surfaced by the Nano Mesh's per-hit soak read, doc 102.4.1). One
autouse restore closes the class for every current and future
``init()`` caller.
"""

from __future__ import annotations

import pytest


@pytest.fixture(autouse=True)
def _restore_ground_session_state():
    """Restore the ground combat session state after every test."""
    from src.spacehack.combat import _rules_ground

    _old = _rules_ground._state
    yield
    _rules_ground._state = _old
