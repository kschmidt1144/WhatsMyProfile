# Dig 3 — reconciling bits with k-anonymity and differential privacy

**Question.** Our entropy framing and the anonymisation literature describe the
same phenomenon in different vocabularies. Which one is right, and what does
the other one know that we don't?

## The canonical result, and its correction

| Study | Census | Uniquely identified by {5-digit ZIP, sex, full DOB} |
|---|---|---|
| Sweeney 2000 | 1990 | **87%** (216M of 248M) |
| Golle 2006 | 2000 | **63%** |

Same three fields, same country, ten years apart, 24 points of difference. The
87% figure is the one that gets quoted and it shaped HIPAA's de-identification
standard; Golle's re-run on better data is the one that is more nearly correct
and is quoted far less. Cite both or neither.

This is [Dig 1](01-population-baseline.md)'s lesson in a second domain: the
denominator and the sample decide the answer, and a headline number outlives
its correction.

## The vocabulary we were missing

The literature distinguishes three things our `attributes` table calls one
thing, which is exactly why `wmp entropy` reported 0.00 on a complete GitHub
profile:

- **Identifier** — unique *by construction*. A GitHub login, an email, a SSN.
  Saturates the budget on its own. Does not accumulate; there is nothing to add.
- **Quasi-identifier (QI)** — not identifying alone, lethal in combination.
  ZIP, birthdate, sex. This is where the bits arithmetic genuinely applies.
- **Sensitive attribute** — the payload an adversary wants (diagnosis, salary,
  orientation). What k-anonymity is trying to protect, not what it operates on.

**k-anonymity**: a release is k-anonymous if every record is indistinguishable
from at least k−1 others *on the QI columns*. Our `anonymity_set()` is
literally computing k. We had been computing a well-known quantity without
knowing its name or its failure modes.

And it has serious failure modes. A k-anonymous group with no variation in the
sensitive attribute leaks it entirely — the **homogeneity attack** — which is
what **l-diversity** and later **t-closeness** were introduced to patch.

Berke et al. hit this precisely: they frame their demographic-inference result
as a homogeneity attack, noting that users in large anonymity sets look
protected but are not, if the set is demographically uniform. Their conclusion
is worth quoting in full because it inverts the intuition this lab was built on:

> Black users ... may be in larger anonymity sets on average, [and] while this
> might help protect them from unique identification and tracking, it may put
> them at greater risk of demographic inference.

**Identification risk and inference risk can move in opposite directions.** A
bigger crowd protects you from being singled out and exposes you more, if the
crowd looks like you. Our single "bits" number cannot represent that, and
reporting it alone would tell some users they are safe precisely when they are
not.

## Where differential privacy fits

DP differs from k-anonymity in two ways that matter to us:

1. **It is adversary-agnostic.** k-anonymity is a syntactic property of a
   release and falls to adversaries with auxiliary information the publisher
   didn't anticipate. DP bounds what *any* adversary with *any* side knowledge
   can learn.
2. **It composes.** Run queries with budgets ε₁, ε₂, ε₃ and the total loss is
   bounded by ε₁+ε₂+ε₃. k-anonymity has no composition property, which is
   exactly why an adversary can issue several k-anonymous queries, link the
   results, and re-identify.

**Our bits framework composes — additively — which structurally makes it a
privacy-loss accountant like DP, not a release property like k-anonymity.**
That is a genuine strength and it also names our correction precisely:
ε-composition is a worst-case *bound*, whereas our naive sum was being read as
an *estimate*. [Dig 1](01-population-baseline.md) measured the gap: 33.45 bits
summed versus 12.101 jointly. The redundancy discount is the empirical
correction to a bound we were misreading as a measurement.

## Decisions taken

1. **Add `kind` to `Attribute`**: `identifier | quasi_identifier | attribute`.
   Identifiers saturate rather than accumulate; only QIs feed `combine()`. This
   resolves the open question that made `wmp entropy` report 0.00 next to a
   visible username.
2. **Report identification and inference risk separately.** They are different
   quantities that can move in opposite directions. One number is a lie.
3. **Frame the totals as loss bounds, not estimates**, and say so in the output.

## Still open

- Whether to compute an actual ε. Attractive, but our "queries" are
  observations we did not control, so the analogy may not survive contact.
- l-diversity needs the composition of the anonymity set, not just its size —
  which needs population data we do not have for most attributes.

## Sources

- [Sweeney 2000, *Simple Demographics Often Identify People Uniquely*](https://dataprivacylab.org/projects/identifiability/paper1.pdf)
- [Golle 2006, *Revisiting the Uniqueness of Simple Demographics in the US Population* (WPES)](https://crypto.stanford.edu/~pgolle/papers/census.pdf)
- [Domingo-Ferrer et al. 2025, *k-Anonymity and Differential Privacy families*](https://arxiv.org/html/2510.11299)
- [Berke et al. 2025 (PoPETs)](https://petsymposium.org/popets/2025/popets-2025-0038.pdf) §7, §8.3
