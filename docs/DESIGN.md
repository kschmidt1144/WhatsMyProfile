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

Two deliberate constraints on the arithmetic:

1. **Correlation.** Attributes are not independent, so summing bits overstates
   identifiability. `entropy.combine(bits, redundancy)` interpolates between
   the independent sum (`redundancy=0`, an upper bound) and the fully-correlated
   floor (`redundancy=1`, the largest single attribute). It can never return
   less than that floor, because the strongest attribute already proved that
   much on its own.
2. **Unmeasured ≠ harmless.** `catalog.known_bits()` returns `None` rather than
   `0.0`. Unmeasured attributes are counted and reported separately so the
   headline figure is always explicitly a lower bound.

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

`inferences.disclosed` is the load-bearing flag. `disclosed = false` with
`verdict = correct` is the result the project exists to count.

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

- **Phase 0 — apparatus.** ✅ Warehouse, entropy engine, connector contract,
  CLI, MCP server, GitHub connector, 33 offline tests.
- **Phase 1 — broadcast half.** More connectors: blogs/writing, package
  registries, WHOIS, search-engine footprint, LinkedIn export. Build the
  identifier graph across them.
- **Phase 2 — inference layer.** Multi-model profiling from public text only.
  Measure the inference gap; use inter-model agreement as a recoverability
  score. Add ground-truth capture so `verdict` can be scored rather than
  assumed.
- **Phase 3 — ambient half.** A local fingerprint probe page; re-measure the
  2010 priors against a current population; tracker graph from a real session
  via Playwright; ad-preference exports.
- **Phase 4 — broker half.** Subject-access requests, tracked end to end.
- **Phase 5 — the report.** Chaptered, every claim computed in-repo.
- **Phase 6 — countermeasures.** The payoff: measure what actually reduces
  bits. Most privacy advice is folklore, and some of it (rare browser
  configurations, unusual fonts) demonstrably *raises* identifiability by
  making you more distinctive. Test it instead of repeating it.

## Open questions

- **Identifiers are not attributes, and the engine currently conflates them.**
  `wmp entropy` reports 0.00 bits on a fully-collected GitHub profile, because
  no broadcast attribute has a measured entropy figure yet — correct under the
  "unmeasured is not zero" rule, and obviously wrong to a reader who can see a
  username sitting in the table. A GitHub login is unique *by construction*: it
  is a primary key, worth the entire budget on its own, not a value shared with
  some fraction of a population. The catalog needs to distinguish identifiers
  (saturating) from attributes (accumulating) before any headline figure means
  what it appears to mean.
- What population do you measure `p` against? World population is the honest
  denominator for a global attribute and badly wrong for a local one; the
  anonymity set that matters is usually a subgroup, not humanity.
- How do you estimate redundancy between attributes without a population
  sample of your own? Literature covariances, or measure it in-repo?
- Does the inference layer need the subject's ground truth to score itself, and
  does storing that ground truth create a worse artifact than the one being
  studied?

## Scope

Self-audit only: the subject is the operator, and the data is their own or data
they have a legal right to demand. No third-party enrichment, no identity
resolution against strangers, no bulk collection. The techniques here overlap
with the ones used to profile people without consent — that is exactly why
measuring them on a consenting subject is worth doing, and exactly why the line
stays where it is.
