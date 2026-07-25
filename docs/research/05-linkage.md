# Dig 5 — linkage as the dossier mechanism

**Question.** How many bits does it take to *link* two datasets, versus to
*identify* you outright? And why does our `identities` table have one row?

## Linkage is a separate, necessary step

[Dig 4](04-behavioral-traces.md)'s critique makes the point sharply: a unique
record identifies nobody until it is joined to an *identified* source. Bits of
uniqueness are necessary and not sufficient. LINDDUN ([Dig 2](02-adversary-model.md))
encodes the same insight by making Linkability its own threat category, distinct
from Identifiability.

The reverse also holds and is less obvious: **linking is often much cheaper than
identifying.** An adversary who joins your sessions across forty sites into one
coherent profile — without ever learning your name — has built a dossier. For
ad-tech that is the entire product; the name is unnecessary overhead.

So there are two thresholds, not one:

- **Linkage threshold** — enough shared signal to join two records with
  acceptable error. Low, and falling.
- **Identification threshold** — enough to pin the joined record to a person.
  Higher, and requires an identified source that linkage does not.

We model neither.

## The classical attack

Narayanan and Shmatikov (2008) de-anonymised the Netflix Prize dataset — 500k
subscribers' ratings — using auxiliary information from public IMDb profiles.
The properties that made it work generalise well beyond movies:

- **Sparsity.** High-dimensional preference data is nearly empty, so small
  overlaps are decisive (same mechanism as [Dig 4](04-behavioral-traces.md)).
- **Robustness to error.** The attack tolerates perturbation in the data *and*
  mistakes in the adversary's background knowledge. Approximate auxiliary
  information suffices — which is why "we fuzzed it" is not a defence.
- **Very little is needed.** An adversary who knows "a little bit" about a
  subscriber finds their record.

## What the industry actually built

The identity-graph business is linkage productised:

- **Deterministic** — anchored on a verified shared key: a login, a hashed email
  (HEM) tied to a mobile advertising ID (MAID). Accurate, limited in scale.
- **Probabilistic** — inferred from behaviour: repeated dwell time at an IP
  suggests a household; devices co-located nightly belong together. Broader
  reach, lower certainty.
- **Hybrid, in practice** — deterministic links anchor the graph and *train the
  probabilistic model*, which then extends coverage. The accurate data's main
  job is to make the guesses better.

Scale constraint worth noting: ID5 reported fewer than 30% of publisher users
logged in as of 2025. So most real-world linkage is probabilistic — i.e. most of
your dossier is assembled by inference, not observation. That is the same
finding as [Dig 6](06-inference-gap.md) arriving from the commercial side.

## Fingerprint instability cuts both ways

Vastel et al. (2018), cited by Berke: **50% of browser instances changed
fingerprint within 5 days, 80% within 10 days.** A fingerprint is not a stable
key; linkage decays and must be continually re-established. This is why
deterministic anchors are commercially precious, and it means a static bits
measurement describes a moment, not a state.

## Decisions taken

1. **Model linkage as its own measurement**, not a byproduct of identification.
   `identities` gains `link_type` (deterministic | probabilistic | inferred),
   `confidence`, and `evidence`.
2. **Implement the attrition chain** from [Dig 4](04-behavioral-traces.md):
   sample-unique → population-unique → linkable → identified.
3. **Add a decay dimension.** A linkage claim without a timestamp and a
   half-life overstates itself.
4. Treat "what identified source could this be joined against?" as a required
   field on any identification claim. If the answer is "none", the claim is
   about uniqueness, not identification, and must say so.

## Still open

- Measuring one's *own* linkability requires knowing what auxiliary data exists
  about you — partly answerable via subject-access requests (Phase 4).
- Cross-device linkage is the case where a self-audit can genuinely test the
  probabilistic method: do platforms in fact join your phone and laptop? Testable.

## Sources

- [Narayanan & Shmatikov 2008, *Robust De-anonymization of Large Sparse Datasets* (IEEE S&P)](https://dl.acm.org/doi/10.1109/SP.2008.33)
- [Piwik PRO, *What is an ID graph?*](https://piwik.pro/blog/what-is-an-id-graph-and-how-can-it-benefit-cross-device-tracking/)
- [Unacast, identity data providers 2025](https://www.unacast.com/post/identity-data-providers)
- Vastel et al. 2018, fingerprint instability — via [Berke et al. 2025](https://petsymposium.org/popets/2025/popets-2025-0038.pdf) §3.1
