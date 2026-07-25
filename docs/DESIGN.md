# Design — What's My Profile

## The question

Not *what did I disclose?* but:

> **How much of me is recoverable, by whom, and how far does what they infer
> exceed what I ever said?**

The gap between those two quantities is the object of study. A data-export
tells you the first. Nothing tells you the second, which is why it has to be
reconstructed from the outside.

## The measure: bits

An attribute value held by a fraction `p` of the population carries
`I = -log₂(p)` bits of identifying information. Independent attributes add. A
population of `N` is worth `log₂(N)` bits — **32.93** for 8.2 billion people —
and the anonymity set after revealing `b` bits is `N / 2^b`.

This is Eckersley's framing from *How Unique Is Your Web Browser?* (2010),
generalised past the browser: any surface that emits attributes can be scored
the same way, whether it is a TLS handshake or a GitHub commit history.

> **A literature pass on 2026-07-25 revised much of what follows.** Eight digs
> are written up in [`research/`](research/); their corrections are folded in
> below and enforced in `entropy.py` rather than left to the reader.

Four deliberate constraints on the arithmetic:

1. **Correlation.** Attributes are not independent, so summing bits overstates
   identifiability. `entropy.combine(bits, redundancy)` interpolates between
   the independent sum (`redundancy=0`, an upper bound) and the fully-correlated
   floor (`redundancy=1`, the largest single attribute). It can never return
   less than that floor, because the strongest attribute already proved that
   much on its own.
2. **Unmeasured ≠ harmless.** `catalog.known_bits()` returns `None` rather than
   `0.0`. Unmeasured attributes are counted and reported separately so the
   headline figure is always explicitly a lower bound.
3. **Entropy is capped by sample size.** You cannot measure more than `log₂(N)`
   bits from a sample of N, so every published figure is a floor set by the
   study's size. `entropy.sample_ceiling()` makes this checkable and
   `Attribute.entropy_bits` cannot be set without its `sample_n`.
   ([Dig 1](research/01-population-baseline.md))
4. **Uniqueness is not identification.** Four results stand in a chain —
   *sample-unique → population-unique → linkable → identified* — with attrition
   at every arrow. This lab measures the first step. Claiming the last one from
   it is the error Sánchez and Domingo-Ferrer levelled at the mobility
   literature, and it was in our code.
   ([Dig 4](research/04-behavioral-traces.md), [Dig 5](research/05-linkage.md))

Direction of error matters more here than magnitude. A profile that says "you
are anonymous" and is wrong is a far worse failure than one that is
pessimistic, so every ambiguity resolves toward *more* exposure, not less.

## The schema

Four tables, mirroring the `obs`/`catalog`/`entities` split that works well in
the World Economy Lab next door.

| Table | Row = | Why it exists |
|---|---|---|
| `signals` | one observed fact about the subject, with evidence | the fact table |
| `attributes` | a kind of fact: category, sensitivity, entropy_bits | what a fact *means* and costs |
| `identities` | an identifier and how it entered the graph | joining is where privacy actually dies |
| `inferences` | a claim derived rather than disclosed | the finding |

`identities` deserves the emphasis. Individually harmless datasets become a
dossier the moment a shared key links them; the identifier graph is the
mechanism of profile assembly, so it is a first-class table rather than a
column.

`attributes.sensitivity` carries `public | sensitive | special`, where
**special** is GDPR Article 9 — race, politics, religion, union membership,
genetics, biometrics, health, sex life or orientation. Inferring one of those
is a categorically different event from inferring a favourite language, and the
schema should not flatten the difference.

`attributes.kind` distinguishes **identifier** (unique by construction —
saturates, never accumulates), **quasi-identifier** (the only kind the bits
arithmetic applies to), and **attribute** (the sensitive payload). Conflating
them is why `wmp entropy` once reported 0.00 bits beside a visible username.
([Dig 3](research/03-k-anonymity-and-dp.md))

`inferences.disclosed` is the load-bearing flag. `disclosed = false` with
`verdict = correct` is the result the project exists to count.

`inferences.effect` is independent of `verdict`. Broker segments are frequently
wrong — male-gender segments measure ~42.5% accurate — and act on you regardless,
so *incorrect + observed* is a real and interesting cell, not a contradiction.
([Dig 7](research/07-consequence.md))

## The four collection modes

**broadcast** — what you published on purpose. GitHub, blogs, package
registries, conference talks, WHOIS, LinkedIn export. Cheap, unambiguous, and
mostly disclosed by definition; its value is as the substrate the inference
layer runs on.

**ambient** — what you emit without choosing to. Fingerprint surfaces (canvas,
WebGL, audio, fonts), tracker graphs from a real browsing session, ad-preference
dumps from Google/Meta/Amazon. This is where the bits arithmetic earns its
keep, and where the 2010 reference priors need re-measuring: NPAPI plugins were
the richest single surface at 15.4 bits and no longer exist, while canvas and
WebGL — which that study predates — now carry much of the load.

**broker** — what the data-brokerage industry holds. Obtained the legitimate
way, by exercising subject-access rights (GDPR Art. 15, CCPA). Slow, manual,
and the most interesting data in the project, because it is the only view of
the profile as the industry itself assembled it. Logged as request → response →
what they actually had.

**inference** — what a frontier model concludes from public text alone. Feed it
only the broadcast half and score what it derives: employer, seniority,
location, interests, and how much of that was never stated. Polling several
models and scoring their agreement (the pattern the World Economy Lab uses for
contested claims) turns divergence into a signal: where models agree on an
undisclosed attribute, the attribute is genuinely recoverable.

## Findings

### Finding 1 — timezone from commit timestamps: right method, wrong constant

Inferred a UTC offset from nothing but the hour-of-day histogram of public
GitHub pushes, a field GitHub does not have. Returned **UTC-7** against a
ground truth of **UTC-4** (n=70 pushes, confidence 0.57).

The quiet window sat at 06:00–14:00 UTC = 02:00–10:00 local. The method reads
the middle of that window as 03:00 local; the subject's actual sleep midpoint
is 06:00, so the estimate landed three hours west — exactly the offset error.

The error is systematic and directional: **night owls resolve west, early
risers east.** What the method actually measures is a sleep midpoint; the
timezone is a chronotype assumption bolted on top. Two consequences:

- The claim is recorded `unverifiable`, not `correct`, and confidence is
  documented to mean "there is a real trough with enough data to see it" —
  never "the offset is right".
- Tuning the 03:00 constant to make this subject come out at UTC-4 would fit
  one person and break everyone else. A real fix needs a population chronotype
  prior, or a second independent signal (issue-comment times against
  business hours, language of README text, event geography) to break the
  degeneracy between "sleeps late" and "lives west".

Worth keeping as the project's first entry precisely because it failed. A
confidently wrong inference is the normal case in this field, and the schema
has to be able to record one.

## Roadmap

Revised after the research pass. The largest change: the inference layer and
the linkage layer were separate phases on the assumption they were separate
attacks. [Dig 6](research/06-inference-gap.md) shows LLM agents outperforming
hand-tuned classical de-anonymization, so they are one phase now.

- **Phase 0 — apparatus.** ✅ Warehouse, entropy engine, connector contract,
  CLI, MCP server, GitHub connector, offline tests.
- **Phase 0.5 — literature pass.** ✅ 2026-07-25. Eight digs, [`research/`](research/).
  Corrections folded into the schema and the entropy engine.
- **Phase 1 — ad-preference connectors.** ✅ Five export-file connectors
  (`x_ads`, `linkedin_ads`, `meta_ads`, `google_ads`, `amazon_ads`), `wmp exports`
  for requesting archives, `wmp agreement` for cross-platform convergence.
  Remaining: load real archives, and normalise demographic keys across
  platforms so "gender = male" and "member gender = Male" compare.
- **Phase 2 — adversary dimension.** `adversaries` table, `signals.visible_to`,
  per-adversary populations and linkage types, so "how many bits" acquires a
  "to whom". Structural, and best done before more data lands.
  ([Dig 2](research/02-adversary-model.md))
- **Phase 3 — broadcast half + identifier graph.** Blogs, package registries,
  WHOIS, LinkedIn export. `identities` gains `link_type`
  (deterministic | probabilistic | inferred), confidence, and decay.
- **Phase 4 — inference and linkage, merged.** Multi-model profiling from
  public text; AUROC against base rate and normalised mutual information as the
  metrics; ground-truth capture so `verdict` becomes measurable.
- **Phase 5 — ambient half.** Local fingerprint probe; re-measure Berke's 2023
  figures on a current sample; tracker graph via Playwright. Traces become
  first-class — a sequence, not N loose signals.
  ([Dig 4](research/04-behavioral-traces.md))
- **Phase 6 — broker half.** Subject-access requests, tracked end to end,
  scored against the measured segment-accuracy priors.
- **Phase 7 — consequence.** Within-subject personalization experiments: does
  the profile change the price? ([Dig 7](research/07-consequence.md))
- **Phase 8 — the report.** Chaptered, every claim computed in-repo.
- **Phase 9 — countermeasures.** The payoff, and the phase most likely to
  produce negative results worth publishing. Every intervention scored on
  *both* axes — identification and inference — because the browser
  `deviceMemory` API is a documented case of a mitigation that lowered one and
  raised the other. ([Dig 8](research/08-countermeasures.md))

## Open questions

**Resolved by the research pass:**

- ~~Identifiers vs attributes.~~ Resolved via the anonymisation literature's
  identifier / quasi-identifier / sensitive-attribute distinction. `Attribute.kind`
  now carries it; identifiers saturate rather than accumulate.
  ([Dig 3](research/03-k-anonymity-and-dp.md))
- ~~Estimating redundancy without a sample of your own.~~ Berke et al. publish
  both the individual and the *joint* entropy of 13 co-measured fingerprint
  attributes — 33.45 summed against 12.101 jointly — which yields a measured
  discount of 0.80. `entropy.MEASURED_REDUNDANCY`, pinned by a test.
  ([Dig 1](research/01-population-baseline.md))

**Still open:**

- **What population do you measure `p` against?** Sharpened rather than solved:
  the denominator is now known to be *adversary-relative*. A stranger needs
  32.93 bits to find you among humanity; an employer needs 8.6 to find you among
  400 staff. Phase 2 makes this explicit; until then the world figure is the
  wrong default and is labelled as such.
- **Should this compute an actual ε?** Our bits compose additively, which makes
  the framework a privacy-loss accountant like differential privacy rather than
  a release property like k-anonymity. Attractive — but our "queries" are
  observations we never controlled, so the analogy may not survive contact.
- **Ground truth is required to score inference, and storing it builds a better
  dossier than the one under study.** Real tension, unresolved. It may argue for
  scoring interactively and never persisting.
- **l-diversity needs the composition of an anonymity set, not just its size.**
  Berke's result — that a larger, more homogeneous crowd can *raise* inference
  risk while lowering identification risk — cannot be represented in the current
  schema at all.
- **Does this repo's own existence change the measurement?** Publishing a public
  repo about your own profile adds signal, and its commit timestamps leak the
  same chronotype Finding 1 was about. The instrument is inside the system.

## Scope

Self-audit only: the subject is the operator, and the data is their own or data
they have a legal right to demand. No third-party enrichment, no identity
resolution against strangers, no bulk collection. The techniques here overlap
with the ones used to profile people without consent — that is exactly why
measuring them on a consenting subject is worth doing, and exactly why the line
stays where it is.
