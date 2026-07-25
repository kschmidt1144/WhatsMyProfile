"""The attribute registry — what a fact means, and what it is worth in bits.

Entries carry a `kind` (identifier saturates, quasi-identifier accumulates,
attribute is the payload) and, where an entropy figure exists, the `sample_n`
it was measured on. Entropy cannot exceed log2(sample_n), so a figure without
its sample size is uninterpretable.

**Primary reference: Berke et al. 2025 (PoPETs).** 8,400 US participants,
December 2023, recruited through a paid panel rather than self-selection. This
replaced Eckersley 2010 as the default after Dig 1 found that the classic
figures come from volunteer samples of privacy-interested, tech-media readers
and overstate uniqueness badly — 83.6–94.2% unique in Panopticlick and 89.4% in
AmIUnique, against 33.6% when Gómez-Boix et al. measured ordinary traffic.

⚠️ Two caveats travel with every number below.

1. **They are floors.** 8,400 participants cap measurable entropy at 13.04 bits.
   The measured joint fingerprint entropy of 12.101 sits just under that
   ceiling, meaning the instrument ran out of resolution rather than finding
   the answer.
2. **They do not add.** The naive sum of the 13 attributes is 33.45 bits; the
   measured joint entropy is 12.101. See `entropy.MEASURED_REDUNDANCY`.

See docs/research/01-population-baseline.md.
"""

from __future__ import annotations

from .model import Attribute

_BERKE = (
    "Berke et al. 2025, 'How Unique is Whose Web Browser?' (PoPETs 2025(1):720-758), "
    "n=8,400 US panel, Dec 2023 — sample-limited floor, ceiling log2(8400)=13.04 bits"
)
_BERKE_N = 8_400

_ECKERSLEY = (
    "Eckersley 2010, 'How Unique Is Your Web Browser?' (n=470,161) — HISTORICAL: "
    "self-selected privacy-interested sample, superseded by Berke 2025"
)

ATTRIBUTES: tuple[Attribute, ...] = (
    # ── broadcast: the footprint you chose to publish ────────────────────────
    # A login is unique by construction — it is a primary key, not a shared trait.
    Attribute("github/login", "GitHub login", "identity", kind="identifier"),
    Attribute("github/email", "Public email", "contact", kind="identifier", sensitivity="sensitive"),
    Attribute("github/blog", "Linked website", "identity", kind="identifier", unit_type="url"),
    Attribute("github/name", "Display name", "identity"),
    Attribute("github/bio", "Profile bio", "social"),
    Attribute("github/company", "Stated employer", "professional"),
    Attribute("github/location", "Stated location", "location", sensitivity="sensitive"),
    Attribute("github/created_at", "Account created", "identity", unit_type="timestamp"),
    Attribute("github/followers", "Follower count", "social", unit_type="number"),
    Attribute("github/public_repos", "Public repository count", "professional", unit_type="number"),
    Attribute("github/language", "Language used in public code", "professional", unit_type="enum"),
    Attribute("github/push_hour_utc", "Hour of day of a public push (UTC)", "behavior", unit_type="number"),
    # ── ambient: the surface you emit without choosing to ────────────────────
    # Measured values, Berke et al. 2025. Ordered by entropy, descending.
    Attribute(
        "fp/webgl_unmasked_renderer", "WebGL unmasked renderer", "device",
        unit_type="hash", entropy_bits=6.833, sample_n=_BERKE_N, note=_BERKE,
    ),
    Attribute(
        "fp/screen", "Screen resolution", "device",
        entropy_bits=5.510, sample_n=_BERKE_N, note=_BERKE,
    ),
    Attribute(
        "fp/user_agent", "User-Agent string", "device",
        entropy_bits=4.613, sample_n=_BERKE_N,
        note=f"{_BERKE}. Sent in HTTP headers — passive, undetectable by the browser.",
    ),
    Attribute(
        "fp/webgl_unmasked_vendor", "WebGL unmasked vendor", "device",
        entropy_bits=3.313, sample_n=_BERKE_N, note=_BERKE,
    ),
    Attribute(
        "fp/hardware_concurrency", "Logical CPU count", "device",
        unit_type="number", entropy_bits=2.340, sample_n=_BERKE_N, note=_BERKE,
    ),
    Attribute(
        "fp/platform", "Platform string", "device",
        entropy_bits=2.114, sample_n=_BERKE_N,
        note=f"{_BERKE}. Low uniqueness but relatively high mutual information "
             "for gender and age — weak for identification, useful for inference.",
    ),
    Attribute(
        "fp/timezone", "Reported timezone", "location",
        sensitivity="sensitive", entropy_bits=2.064, sample_n=_BERKE_N, note=_BERKE,
    ),
    Attribute(
        "fp/languages", "Accept-Language list", "device",
        entropy_bits=1.730, sample_n=_BERKE_N,
        note=f"{_BERKE}. Higher risk for Hispanic and non-White users: 'es-US' "
             "speakers are 11% of the sample but >45% of that attribute value.",
    ),
    Attribute(
        "fp/device_memory", "Device memory (GB)", "device",
        unit_type="number", entropy_bits=1.611, sample_n=_BERKE_N,
        note=f"{_BERKE}. The API rounds to powers of 2 to REDUCE fingerprinting, "
             "which bucketed users demographically instead: <$50k households are "
             "35% of the sample and >60% of deviceMemory=2.0.",
    ),
    Attribute(
        "fp/touch_points", "Max touch points", "device",
        unit_type="number", entropy_bits=1.463, sample_n=_BERKE_N, note=_BERKE,
    ),
    Attribute(
        "fp/webgl_renderer", "WebGL renderer", "device",
        entropy_bits=0.782, sample_n=_BERKE_N, note=_BERKE,
    ),
    Attribute(
        "fp/color_depth", "Colour depth", "device",
        unit_type="number", entropy_bits=0.616, sample_n=_BERKE_N, note=_BERKE,
    ),
    Attribute(
        "fp/webgl_vendor", "WebGL vendor", "device",
        entropy_bits=0.465, sample_n=_BERKE_N, note=_BERKE,
    ),
    # Historical, retained for comparison only. NPAPI plugins no longer exist;
    # this was the single richest surface in 2010 and is now worth nothing.
    Attribute(
        "fp/plugins", "Browser plugin list (historical)", "device",
        entropy_bits=15.4, sample_n=470_161,
        note=f"{_ECKERSLEY}. DEFUNCT: NPAPI plugins removed from modern browsers.",
    ),
    # Surfaces this lab has not measured. None, never 0.0.
    Attribute("fp/canvas_hash", "Canvas rendering hash", "device", unit_type="hash"),
    Attribute("fp/audio_hash", "AudioContext fingerprint", "device", unit_type="hash"),
    Attribute("fp/fonts", "Installed font list", "device"),
    # ── ad preferences: the platforms' own profile of you ────────────────────
    # These are the payload an adversary wants, not keys used to find you, so
    # they never accumulate into an identifiability total.
    Attribute("adprefs/interest", "Interest attributed to you by a platform", "inferred",
              kind="attribute"),
    Attribute("adprefs/demographic", "Demographic a platform inferred", "inferred",
              kind="attribute", sensitivity="sensitive"),
    Attribute("adprefs/audience", "Audience segment you were placed in", "commercial",
              kind="attribute"),
    Attribute("adprefs/advertiser", "Advertiser holding or targeting your data", "commercial",
              kind="attribute"),
    # ── inferred: the payload, not the key ───────────────────────────────────
    Attribute("inferred/timezone", "Timezone inferred from activity", "inferred",
              kind="attribute", sensitivity="sensitive"),
    Attribute("inferred/employer", "Employer inferred from footprint", "inferred",
              kind="attribute", sensitivity="sensitive"),
    Attribute("inferred/interests", "Interest categories attributed to you", "inferred",
              kind="attribute"),
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


def kind_of(attribute: str) -> str | None:
    entry = BY_ID.get(attribute)
    return entry.kind if entry else None
