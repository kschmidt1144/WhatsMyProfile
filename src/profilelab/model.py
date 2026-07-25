"""The four tables everything reduces to.

`signals` is the fact table — one row per atomic thing some system knows or
could know about the subject. `attributes` is its catalog (what the fact means,
how sensitive it is, what it is worth in bits). `identities` is the identifier
graph — the join keys that let two datasets become one profile, which is where
most real privacy loss happens. `inferences` is the finding: claims about the
subject that were *derived* rather than disclosed.

The distinction between the last two and the first is the whole thesis. A
signal is something you emitted. An inference is something someone concluded.
The gap between them is what this lab measures.
"""

from __future__ import annotations

from dataclasses import dataclass, field

# An attribute's category — what surface of a life it describes.
CATEGORIES = frozenset(
    {
        "identity", "contact", "device", "location", "behavior", "social",
        "professional", "inferred",
        # Commercial relationships and targeting: who holds your data, which
        # audiences you were placed in, what you were sold as.
        "commercial",
    }
)

# Sensitivity tiers. "special" is GDPR Article 9 — race, politics, religion,
# union membership, genetics, biometrics, health, sex life or orientation.
# These are flagged separately because inferring one is a different kind of
# event from inferring a favourite programming language.
SENSITIVITIES = frozenset({"public", "sensitive", "special"})

UNIT_TYPES = frozenset({"string", "number", "hash", "bool", "enum", "timestamp", "url"})

# The distinction the anonymisation literature makes and this schema originally
# did not — see docs/research/03-k-anonymity-and-dp.md.
#
#   identifier       unique by construction (a login, an email). SATURATES the
#                    budget on its own; there is nothing to accumulate.
#   quasi_identifier not identifying alone, lethal in combination (ZIP + DOB +
#                    sex). This is the only kind the bits arithmetic applies to.
#   attribute        the sensitive payload an adversary wants, not the key they
#                    use to find you.
#
# Conflating these is why `wmp entropy` once reported 0.00 bits while a
# uniquely-identifying username sat in the table.
KINDS = frozenset({"identifier", "quasi_identifier", "attribute"})

# Whether a derived claim had a real downstream effect — independent of whether
# it was correct. Broker segments are frequently wrong and operative anyway
# (male-gender segments measured ~42.5% accurate), so accuracy alone does not
# capture harm. See docs/research/07-consequence.md.
EFFECTS = frozenset({"observed", "plausible", "none", "unknown"})

# How a connector obtained its evidence. The four collection modes are the four
# halves of the project (see docs/DESIGN.md).
MODES = frozenset({"broadcast", "ambient", "broker", "inference"})

# Whether a derived claim held up when checked against ground truth.
VERDICTS = frozenset({"correct", "incorrect", "unverifiable"})


@dataclass(frozen=True)
class Attribute:
    """A kind of fact, and what it costs you to leak it."""

    attribute: str  # namespaced: "github/login", "fp/canvas_hash"
    title: str
    category: str
    kind: str = "quasi_identifier"
    sensitivity: str = "public"
    unit_type: str = "string"
    # Bits of surprisal this attribute carries in the general population.
    # None means unmeasured — never silently treated as zero.
    entropy_bits: float | None = None
    # Size of the sample the entropy figure was measured on. Entropy cannot
    # exceed log2(sample_n), so this is what makes a figure interpretable as a
    # floor rather than a fact. See docs/research/01-population-baseline.md.
    sample_n: int | None = None
    # Where an entropy figure came from, when it is a literature value rather
    # than something this lab measured. Load-bearing for honesty.
    note: str | None = None

    def __post_init__(self) -> None:
        if self.category not in CATEGORIES:
            raise ValueError(f"{self.attribute}: unknown category {self.category!r}")
        if self.kind not in KINDS:
            raise ValueError(f"{self.attribute}: unknown kind {self.kind!r}")
        if self.sensitivity not in SENSITIVITIES:
            raise ValueError(f"{self.attribute}: unknown sensitivity {self.sensitivity!r}")
        if self.unit_type not in UNIT_TYPES:
            raise ValueError(f"{self.attribute}: unknown unit_type {self.unit_type!r}")
        if self.entropy_bits is not None and self.entropy_bits < 0:
            raise ValueError(f"{self.attribute}: entropy_bits must be non-negative")
        if self.entropy_bits is not None and not self.sample_n:
            raise ValueError(f"{self.attribute}: entropy_bits requires sample_n")


@dataclass(frozen=True)
class Signal:
    """One observed fact about the subject, with its evidence."""

    subject: str
    identity: str  # which identifier this attaches to
    source: str
    attribute: str
    value: str
    observed_at: str  # ISO 8601
    evidence: str  # url, file path, or probe reference
    value_num: float | None = None
    confidence: float = 1.0

    def __post_init__(self) -> None:
        if not 0.0 <= self.confidence <= 1.0:
            raise ValueError(f"confidence must be in [0, 1], got {self.confidence!r}")


@dataclass(frozen=True)
class Identity:
    """A key that joins datasets together — the mechanism of profile assembly."""

    identity: str  # "gh:octocat", "email:...", "device:<hash>"
    kind: str  # handle | email | device | domain | phone | account | person
    subject: str
    linked_via: str  # how this identifier entered the graph


@dataclass(frozen=True)
class Inference:
    """A claim about the subject that someone derived rather than was told."""

    subject: str
    claim: str
    inferred_by: str  # "github-activity", "meta-ads", "claude-opus-5"
    from_sources: str
    # Did the subject ever state this publicly? An undisclosed-but-correct
    # inference is the finding this whole project exists to count.
    disclosed: bool
    verdict: str = "unverifiable"
    # Independent of `verdict`: did this claim change anything downstream?
    # `incorrect` + `observed` is the interesting cell, not a contradiction.
    effect: str = "unknown"
    confidence: float = 0.5
    method: str | None = None

    def __post_init__(self) -> None:
        if self.verdict not in VERDICTS:
            raise ValueError(f"unknown verdict {self.verdict!r}")
        if self.effect not in EFFECTS:
            raise ValueError(f"unknown effect {self.effect!r}")
        if not 0.0 <= self.confidence <= 1.0:
            raise ValueError(f"confidence must be in [0, 1], got {self.confidence!r}")


@dataclass
class Collected:
    """What a connector's `parse()` hands back."""

    attributes: list[Attribute] = field(default_factory=list)
    signals: list[Signal] = field(default_factory=list)
    identities: list[Identity] = field(default_factory=list)
    inferences: list[Inference] = field(default_factory=list)

    def extend(self, other: Collected) -> None:
        self.attributes.extend(other.attributes)
        self.signals.extend(other.signals)
        self.identities.extend(other.identities)
        self.inferences.extend(other.inferences)
