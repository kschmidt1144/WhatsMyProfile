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
    def accuracy(self) -> float | None:
        """Correct as a share of claims actually decided.

        Unverifiable claims are excluded rather than counted as failures — a
        claim nobody can adjudicate says nothing about the inferrer. Returns
        None when nothing has been decided, instead of a misleading 0.0.
        """
        decided = self.correct + self.incorrect
        return self.correct / decided if decided else None


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
