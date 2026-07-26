"""Militia missions: patrol and retrieval work offered by the militia captain.

No functional militia missions this iteration — stripped after the
first working delivery and bounty missions proved the system. Add
a new mission by inserting a single :class:`Mission` entry below;
the runtime layer picks it up automatically. See :mod:`merchants`
for the canonical delivery exemplar.
"""
from . import Mission


MISSIONS: tuple[Mission, ...] = ()