"""Turning collected signals into the numbers the project is about.

Three corrections from the research pass are enforced here rather than left to
the reader (see docs/research/):

- **Identifiers saturate, quasi-identifiers accumulate.** A username is a
  primary key; adding bits to it is meaningless. Only QIs feed `combine()`.
- **Entropy is capped by sample size.** Any figure near log2(sample_n) is
  resolution-limited and flagged.
- **Uniqueness is not identification.** The reported number is the first link
  in a four-step chain, and the wording says so.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field

from . import catalog, entropy, warehouse
from .config import WORLD_POPULATION


@dataclass
class Identifiability:
    """How identifiable the collected evidence makes the subject.

    Always a **lower bound on a bound**. `unmeasured` counts attributes with no
    entropy figure — they contribute nothing even though they plainly leak
    something. And the total itself is a composition bound, not an estimate:
    real attributes correlate, which is what `redundancy` corrects for.
    """

    bits: float
    anonymity_set: float
    budget: float
    redundancy: float
    redundancy_source: str
    population: int
    # Identifiers found in the evidence. Any one of these ends the question
    # independently of how many bits the quasi-identifiers add up to.
    identifiers: list[str] = field(default_factory=list)
    measured: list[tuple[str, float, int]] = field(default_factory=list)
    unmeasured: list[str] = field(default_factory=list)
    resolution_limited: list[str] = field(default_factory=list)

    @property
    def saturated(self) -> bool:
        """Whether a unique-by-construction identifier is present."""
        return bool(self.identifiers)

    @property
    def unique(self) -> bool:
        return self.saturated or entropy.is_unique(self.bits, self.population)

    def summary(self) -> str:
        if self.saturated:
            names = ", ".join(self.identifiers)
            return (
                f"Identified by construction: {names}. "
                f"Quasi-identifiers add {self.bits:.2f} bits on top, which is "
                f"redundant once a primary key is public."
            )
        line = entropy.describe(self.bits, self.population)
        if self.unmeasured:
            line += f" — floor only, {len(self.unmeasured)} attribute(s) unmeasured"
        return line


def _resolve_redundancy(attributes: list[str]) -> tuple[float, str]:
    """Pick a correlation discount, preferring a measured one over a guess.

    The 0.80 figure was measured on browser-fingerprint attributes observed
    together; applying it to attributes from a different surface would be
    borrowing a constant that was never measured there.
    """
    namespaces = {a.split("/", 1)[0] for a in attributes}
    if len(namespaces) == 1:
        only = next(iter(namespaces))
        if only in entropy.NAMESPACE_REDUNDANCY:
            return entropy.NAMESPACE_REDUNDANCY[only], f"measured for '{only}/' attributes"
    return 0.0, "assumed independent (upper bound — no measured value for this mix)"


def identifiability(
    redundancy: float | None = None, population: int = WORLD_POPULATION
) -> Identifiability:
    """Score every distinct attribute collected so far, in bits."""
    frame = warehouse.query("SELECT DISTINCT attribute FROM signals ORDER BY attribute")
    attributes = list(frame["attribute"]) if not frame.empty else []

    identifiers: list[str] = []
    measured: list[tuple[str, float, int]] = []
    unmeasured: list[str] = []
    limited: list[str] = []

    for attribute in attributes:
        entry = catalog.get(attribute)
        if entry is None:
            unmeasured.append(attribute)
            continue
        if entry.kind == "identifier":
            identifiers.append(attribute)
            continue
        if entry.kind == "attribute":
            continue  # payload, not a key — never accumulated
        if entry.entropy_bits is None or not entry.sample_n:
            unmeasured.append(attribute)
            continue
        measured.append((attribute, entry.entropy_bits, entry.sample_n))
        if entropy.resolution_limited(entry.entropy_bits, entry.sample_n):
            limited.append(attribute)

    resolved, source = (
        (redundancy, "caller-supplied")
        if redundancy is not None
        else _resolve_redundancy([a for a, _, _ in measured])
    )
    total = entropy.combine([b for _, b, _ in measured], redundancy=resolved)

    return Identifiability(
        bits=total,
        anonymity_set=entropy.anonymity_set(total, population),
        budget=entropy.population_bits(population),
        redundancy=resolved,
        redundancy_source=source,
        population=population,
        identifiers=sorted(identifiers),
        measured=sorted(measured, key=lambda row: row[1], reverse=True),
        unmeasured=unmeasured,
        resolution_limited=limited,
    )


@dataclass
class Dossier:
    """What is out there, who holds it, what it says, and what it is used for.

    The lab's primary view. Note what it deliberately does not report: whether
    any of it is *correct*. Accuracy is a separate and much narrower question —
    a profile that is wrong is still held, still sold, and still acted on, so
    an inventory that only counted the true parts would understate the thing
    being inventoried.
    """

    disclosed: list[dict] = field(default_factory=list)
    held: list[dict] = field(default_factory=list)
    holders: list[dict] = field(default_factory=list)
    claims: list[dict] = field(default_factory=list)
    dark: list[dict] = field(default_factory=list)

    @property
    def disclosed_count(self) -> int:
        return sum(row["signals"] for row in self.disclosed)

    @property
    def held_count(self) -> int:
        return sum(row["signals"] for row in self.held)


def _source_modes() -> dict[str, str]:
    """source -> collection mode, from the connector registry."""
    from . import reading, sources

    modes = {name: module.MODE for name, module in sources.REGISTRY.items()}
    modes[reading.SOURCE] = "inference"
    return modes


def dossier() -> Dossier:
    """Assemble the inventory."""
    modes = _source_modes()
    by_source = warehouse.query(
        """
        SELECT source, attribute, COUNT(*) AS signals
        FROM signals GROUP BY 1, 2 ORDER BY 1, 3 DESC
        """
    )

    result = Dossier()
    for row in by_source.to_dict("records"):
        row["mode"] = modes.get(row["source"], "unknown")
        # `broadcast` is what you published yourself; every other mode is
        # something a system assembled about you.
        (result.disclosed if row["mode"] == "broadcast" else result.held).append(row)

    # Who holds it. Advertisers are the only holders the data names directly;
    # the platform that exported them is a holder by construction.
    advertisers = warehouse.query(
        """
        SELECT source, value AS holder
        FROM signals WHERE attribute = 'adprefs/advertiser' ORDER BY value
        """
    ).to_dict("records")
    platforms = warehouse.query(
        "SELECT DISTINCT source FROM signals ORDER BY source"
    ).to_dict("records")
    result.holders = [
        {"holder": p["source"], "via": "collected directly", "kind": "platform"} for p in platforms
    ] + [
        {"holder": a["holder"], "via": f"reached you via {a['source']}", "kind": "advertiser"}
        for a in advertisers
    ]

    # What it says about you.
    result.claims = warehouse.query(
        """
        SELECT inferred_by, claim, disclosed, effect, confidence
        FROM inferences ORDER BY inferred_by, claim
        """
    ).to_dict("records")

    # What is still dark — surfaces the lab knows about but has not collected.
    collected = {p["source"] for p in platforms}
    for name, mode in sorted(modes.items()):
        if name not in collected:
            result.dark.append({"source": name, "mode": mode})
    return result


def coverage() -> "list[dict]":
    """What has been collected, by source."""
    frame = warehouse.query(
        """
        SELECT source,
               COUNT(*)                    AS signals,
               COUNT(DISTINCT attribute)   AS attributes,
               MAX(observed_at)            AS last_observed
        FROM signals GROUP BY source ORDER BY signals DESC
        """
    )
    return frame.to_dict("records")


# Measured accuracy of commercial interest segments across 19 data brokers —
# the yardstick a platform's own inferences should be judged against.
# See docs/research/07-consequence.md.
INDUSTRY_INTEREST_ACCURACY = 0.80


@dataclass
class Scorecard:
    """How well the inferences held up against the subject's own judgement."""

    total: int
    scored: int
    correct: int
    incorrect: int
    unverifiable: int
    undisclosed_correct: int
    by_source: list[dict] = field(default_factory=list)

    @property
    def unscored(self) -> int:
        return self.total - self.scored

    @property
    def decided(self) -> int:
        return self.correct + self.incorrect

    @property
    def accuracy(self) -> float | None:
        """Correct as a share of claims actually decided.

        Unverifiable claims are excluded rather than counted as failures — a
        claim nobody can adjudicate says nothing about the inferrer. Returns
        None when nothing has been decided, instead of a misleading 0.0.
        """
        return self.correct / self.decided if self.decided else None

    @property
    def accuracy_interval(self) -> tuple[float, float] | None:
        """95% Wilson interval on the accuracy.

        Load-bearing, not decoration. A first sitting scores a couple of dozen
        claims, and at that size the interval spans thirty-odd points — wide
        enough that a point estimate sitting above a published benchmark means
        nothing at all. Reporting the estimate alone invites exactly the
        overclaim this project exists to avoid.
        """
        if not self.decided:
            return None
        return wilson_interval(self.correct, self.decided)


def wilson_interval(successes: int, trials: int, z: float = 1.96) -> tuple[float, float]:
    """Wilson score interval — well-behaved at small n, unlike the normal approximation."""
    if trials <= 0:
        raise ValueError("trials must be positive")
    p = successes / trials
    denominator = 1 + z**2 / trials
    centre = (p + z**2 / (2 * trials)) / denominator
    margin = (z / denominator) * math.sqrt(p * (1 - p) / trials + z**2 / (4 * trials**2))
    return max(0.0, centre - margin), min(1.0, centre + margin)


def scorecard() -> Scorecard:
    """Score the inference gap against recorded ground truth."""
    frame = warehouse.query(
        """
        SELECT from_sources, disclosed, verdict, scored
        FROM inferences
        """
    )
    if frame.empty:
        return Scorecard(0, 0, 0, 0, 0, 0)

    scored = frame[frame["scored"]]
    by_source = warehouse.query(
        """
        SELECT from_sources AS source,
               COUNT(*)                                          AS total,
               SUM(CASE WHEN scored THEN 1 ELSE 0 END)           AS scored,
               SUM(CASE WHEN scored AND verdict = 'correct'   THEN 1 ELSE 0 END) AS correct,
               SUM(CASE WHEN scored AND verdict = 'incorrect' THEN 1 ELSE 0 END) AS incorrect
        FROM inferences GROUP BY 1 ORDER BY total DESC
        """
    ).to_dict("records")

    return Scorecard(
        total=len(frame),
        scored=len(scored),
        correct=int((scored["verdict"] == "correct").sum()),
        incorrect=int((scored["verdict"] == "incorrect").sum()),
        unverifiable=int((scored["verdict"] == "unverifiable").sum()),
        # The headline: claims that were right AND never disclosed by the
        # subject. This is the quantity the whole project exists to count.
        undisclosed_correct=int(
            ((scored["verdict"] == "correct") & (~scored["disclosed"].astype(bool))).sum()
        ),
        by_source=by_source,
    )


def unscored_inferences(source: str | None = None, undisclosed_only: bool = True) -> "list[dict]":
    """Claims awaiting the subject's judgement, for `wmp score`."""
    where = ["NOT scored"]
    params: list = []
    if source:
        where.append("from_sources = ?")
        params.append(source)
    if undisclosed_only:
        where.append("NOT disclosed")
    frame = warehouse.query(
        f"SELECT claim, inferred_by, from_sources, disclosed, method "
        f"FROM inferences WHERE {' AND '.join(where)} ORDER BY from_sources, claim",
        params,
    )
    return frame.to_dict("records")


def platform_agreement(min_platforms: int = 1) -> "list[dict]":
    """Ad-preference topics, ranked by how many platforms independently assert them.

    The comparison is the point. A topic several platforms converge on
    independently is genuinely recoverable from behaviour; one that appears on a
    single platform is either that platform's private observation or its
    private mistake. Given the measured accuracy of commercial segments — male
    gender at ~42.5% — divergence is the expected case, not the anomaly.
    """
    frame = warehouse.query(
        """
        SELECT LOWER(value)                  AS topic,
               COUNT(DISTINCT source)        AS platforms,
               STRING_AGG(DISTINCT source, ', ') AS sources,
               MIN(attribute)                AS facet
        FROM signals
        WHERE attribute LIKE 'adprefs/%'
        GROUP BY 1
        HAVING COUNT(DISTINCT source) >= ?
        ORDER BY platforms DESC, topic
        """,
        [min_platforms],
    )
    return frame.to_dict("records")


def inference_gap() -> "list[dict]":
    """Claims derived about the subject, undisclosed ones first.

    `verdict` and `effect` are independent: a claim can be wrong and still have
    changed a price, an ad, or an offer. Undisclosed-and-correct is the finding
    this lab exists to count; incorrect-and-operative is the one the industry
    would rather not discuss.
    """
    frame = warehouse.query(
        """
        SELECT claim, inferred_by, from_sources, disclosed, verdict, effect,
               confidence, method
        FROM inferences ORDER BY disclosed ASC, confidence DESC
        """
    )
    return frame.to_dict("records")
