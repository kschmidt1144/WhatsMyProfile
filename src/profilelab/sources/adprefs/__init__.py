"""Ad-preference connectors — the platforms' own inferred profiles of you.

Five platforms will hand you their profile of you on request. Comparing them is
the point: where several independently converge on an undisclosed attribute,
that attribute is genuinely recoverable rather than one system's guess; where
they diverge, at least one of them is selling something wrong.

Shared machinery in `base.py`; one module per platform.
"""

from . import amazon, google, linkedin, meta, x

PLATFORMS = (x, linkedin, meta, google, amazon)

__all__ = ["PLATFORMS", "amazon", "google", "linkedin", "meta", "x"]
