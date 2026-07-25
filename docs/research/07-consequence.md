# Dig 7 — consequence versus accuracy

**Question.** `verdict` records whether an inference is *correct*. Does that
capture the harm?

No. And the gap is larger than expected, because the industry's profiles are
substantially wrong and act on you anyway.

## Data broker profiles are frequently inaccurate

Field tests across **90+ third-party audience segments from 19 data brokers**:

| Measure | Result |
|---|---|
| Gender segments classifying males | **42.5% accurate** |
| Age tier | **incorrect in 77% of cases** |
| Interest segments | 80% correct |
| Ads reaching the intended demographic | **59%** |
| Improvement over random audience selection | **0–77%**, varying by segment |

A male-gender segment at 42.5% is worse than a coin flip. Some segments provide
no measurable benefit over choosing at random. And the quality shows **no
improvement over measurements taken eight years earlier** — this is a stable
property of the market, not a teething problem.

## Wrong and operative are independent

This is the finding that breaks the schema's assumption. A profile does not
need to be true to determine:

- which ads and offers you see,
- what price you are quoted,
- which jobs and housing are shown to you,
- what a downstream model infers from "similar" users.

Berke et al. supply the documented cases: Cambridge Analytica's alleged use of
Facebook for a voter-suppression campaign targeting a disproportionately Black
group of users; Facebook sued in 2018 for allegedly enabling Fair Housing Act
violations; research showing employment ads still reaching protected categories
after platforms prohibited it.

None of that turns on whether the segment was *accurate*. An incorrect
inference with real effect is a harm the `verdict` field currently records as
`incorrect` — i.e. as a non-event.

There is a further twist worth keeping: an inaccurate profile is *harder to
contest*. Subject-access rights let you see and correct data held about you, but
a probabilistic segment that is merely wrong is not obviously "incorrect
personal data" in a way most processes will act on.

## The measurable version: personalization audits

The methodology is established. Sandvig et al. (2014) set out the audit designs
for detecting discrimination in algorithmic systems; the **sock-puppet audit**
is the workhorse — programmatic personas with controlled attributes, querying a
platform and recording what comes back.

- Trade-off: precise control over persona behaviour, at the cost of ecological
  validity. Sock-puppet results may not replicate with real humans.
- Findings are real: price steering or discrimination detected on **9 of 16**
  analysed e-commerce sites in one study.
- Most directly relevant here: work on **price differentiation based on system
  fingerprints** closes the loop from the ambient half to consequence. The
  fingerprint is not merely identifying — it is an input to your price.

For a self-audit lab the honest version is narrower than a sock-puppet study:
vary one factor (logged-in vs not, fresh profile vs aged, VPN region) and record
what changes. That is a within-subject experiment, not a population audit, and
should be labelled as such.

## Decisions taken

1. **Split the axes.** `verdict` (correct | incorrect | unverifiable) stays;
   add `effect` (observed | plausible | none | unknown). A claim can be
   `incorrect` and `observed` — that is the interesting cell, not a
   contradiction.
2. **Add an `effects` concept**: what changed downstream — price quoted, ad
   category, offer shown — with the counterfactual it was compared against.
3. **Report segment accuracy as a prior.** When a broker asserts a segment, the
   base rates above are the expected reliability. A broker saying you are male
   is worth about 0.9 bits, not certainty.

## Still open

- Price experiments on real accounts risk terms-of-service violations and
  polluting your own profile with test signals. Design carefully; prefer
  read-only observation.
- Distinguishing personalization from A/B tests, inventory changes, and plain
  noise needs repetition and controls that a single-subject lab struggles to
  supply. Under-powered results should be reported as anecdotes, not findings.

## Sources

- [*'Junk inferences' by data brokers*, The Record](https://therecord.media/junk-inferences-data-brokers)
- [INFORMS, *Lifting the curtain behind the "black box" of data broker records*](https://www.informs.org/News-Room/INFORMS-Releases/News-Releases/Researchers-Lift-the-Curtain-Behind-the-Black-Box-of-Data-Broker-Records-New-Study-Reveals-Key-Strengths-and-Weaknesses-of-Data-Records)
- [Sandvig et al. 2014, *Auditing Algorithms: Research Methods for Detecting Discrimination*](https://ai.equineteurope.org/system/files/2022-02/ICA2014-Sandvig.pdf)
- [*An Empirical Study on Price Differentiation Based on System Fingerprints*](https://arxiv.org/pdf/1712.03031)
- [Berke et al. 2025 (PoPETs)](https://petsymposium.org/popets/2025/popets-2025-0038.pdf) §7.1
