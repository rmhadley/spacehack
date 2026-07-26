"""Bar missions: city rumours and odd jobs offered by the barkeep.

No functional bar missions this iteration — stripped after the first
working delivery and bounty missions proved the system. Add a new
mission by inserting a single :class:`Mission` entry below; the
runtime layer picks it up automatically. See :mod:`merchants` for
the canonical delivery exemplar.
"""
from . import Mission


MISSIONS: tuple[Mission, ...] = ()