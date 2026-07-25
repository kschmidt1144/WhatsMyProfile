"""The attribute registry — what a fact means, and what it is worth in bits.

Two kinds of entry live here. Most are **structural**: they describe a fact a
connector can emit, with entropy left `None` until this lab measures it.
A few are **reference priors** from the fingerprinting literature, carried so
that the ambient half has something to calibrate against on day one.

⚠️ The reference priors are from Eckersley's 2010 Panopticlick sample and are
carried as *history, not truth*. The browser landscape they describe is gone:
NPAPI plugins were the single richest surface at 15.4 bits and are now extinct,
while canvas, WebGL and audio fingerprinting — which that study predates
entirely — carry much of the load today. Re-measuring these against a current
population is Phase 3 work; until then, any figure sourced from them must be
labelled as a 2010 estimate wherever it appears.
"""

from __future__ import annotations

from .model import Attribute

_ECKERSLEY = "Eckersley 2010, 'How Unique Is Your Web Browser?' (n≈470k) — 2010 sample, see module docstring"

ATTRIBUTES: tuple[Attribute, ...] = (
    # ── broadcast: the footprint you chose to publish ────────────────────────
    Attribute("github/login", "GitHub login", "identity", unit_type="string"),
    Attribute("github/name", "Display name", "identity", unit_type="string"),
    Attribute("github/bio", "Profile bio", "social", unit_type="string"),
    Attribute("github/company", "Stated employer", "professional", unit_type="string"),
    Attribute("github/location", "Stated location", "location", sensitivity="sensitive"),
    Attribute("github/blog", "Linked website", "identity", unit_type="url"),
    Attribute("github/email", "Public email", "contact", sensitivity="sensitive"),
    Attribute("github/created_at", "Account created", "identity", unit_type="timestamp"),
    Attribute("github/followers", "Follower count", "social", unit_type="number"),
    Attribute("github/public_repos", "Public repository count", "professional", unit_type="number"),
    Attribute("github/language", "Language used in public code", "professional", unit_type="enum"),
    Attribute("github/push_hour_utc", "Hour of day of a public push (UTC)", "behavior", unit_type="number"),
    # ── ambient: the surface you emit without choosing to ────────────────────
    # Reference priors — see the warning above before quoting any of these.
    Attribute(
        "fp/user_agent", "User-Agent string", "device",
        unit_type="string", entropy_bits=10.0, note=_ECKERSLEY,
    ),
    Attribute(
        "fp/plugins", "Browser plugin list", "device",
        unit_type="string", entropy_bits=15.4,
        note=f"{_ECKERSLEY}. Historical: NPAPI plugins no longer exist in modern browsers.",
    ),
    Attribute(
        "fp/fonts", "Installed font list", "device",
        unit_type="string", entropy_bits=13.9, note=_ECKERSLEY,
    ),
    Attribute(
        "fp/screen", "Screen resolution and colour depth", "device",
        unit_type="string", entropy_bits=4.83, note=_ECKERSLEY,
    ),
    Attribute(
        "fp/timezone", "Reported timezone", "location",
        unit_type="string", entropy_bits=3.04, sensitivity="sensitive", note=_ECKERSLEY,
    ),
    Attribute(
        "fp/supercookies", "Supercookie support", "device",
        unit_type="string", entropy_bits=2.12, note=_ECKERSLEY,
    ),
    Attribute(
        "fp/cookies_enabled", "Cookies enabled", "device",
        unit_type="bool", entropy_bits=0.353, note=_ECKERSLEY,
    ),
    # Surfaces that postdate the 2010 study — entropy to be measured here.
    Attribute("fp/canvas_hash", "Canvas rendering hash", "device", unit_type="hash"),
    Attribute("fp/webgl_hash", "WebGL renderer hash", "device", unit_type="hash"),
    Attribute("fp/audio_hash", "AudioContext fingerprint", "device", unit_type="hash"),
    # ── inferred: what was concluded, not disclosed ──────────────────────────
    Attribute("inferred/timezone", "Timezone inferred from activity", "inferred", sensitivity="sensitive"),
    Attribute("inferred/employer", "Employer inferred from footprint", "inferred", sensitivity="sensitive"),
    Attribute("inferred/interests", "Interest categories attributed to you", "inferred"),
)

BY_ID: dict[str, Attribute] = {a.attribute: a for a in ATTRIBUTES}


def get(attribute: str) -> Attribute | None:
    return BY_ID.get(attribute)


def known_bits(attribute: str) -> float | None:
    """Reference entropy for an attribute, or None if this lab has not measured it.

    Callers must handle None rather than defaulting to 0.0 — an unmeasured
    attribute is unknown, not harmless, and treating it as zero would quietly
    understate every identifiability total in the project.
    """
    entry = BY_ID.get(attribute)
    return entry.entropy_bits if entry else None
