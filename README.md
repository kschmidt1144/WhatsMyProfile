# What's My Profile

> There are two of you on the internet. One you wrote. The other was written
> about you. This measures the second one — in bits.

A research instrument for auditing the profile of yourself that exists outside
your control. It collects the evidence, scores how identifiable it makes you,
and — the part that matters — counts the things about you that were **inferred
rather than disclosed**.

## The premise

Ask what a company knows about you and you get a data-export: the fields you
filled in. That is the least interesting half. The valuable half is derived —
your timezone from your commit times, your employer from your network, your
household income from your postcode, your mood from your typing speed. Nobody
exports that, because it was never a field.

So the question this repo asks is not *what did I disclose?* It is:

**How much of me is recoverable, by whom, and how far does what they infer
exceed what I ever said?**

Every claim in this repo is computed from evidence collected in this repo, and
every observation traces back to the bytes it came from — a manifest with a URL
and a sha256. No secondhand statistics.

## Measuring in bits

Everything reduces to one quantity. An attribute value held by a fraction `p`
of the population carries `-log₂(p)` bits of identifying information, and
independent attributes add. The world population is worth **log₂(8.2×10⁹) =
32.93 bits** — accumulate that much and the set of people who match is you.

A 1-in-1000 font list is 9.97 bits. A timezone is about 3. Put them together
and 8.2 billion people become roughly 200,000. That is the whole arithmetic,
and `wmp entropy` reports it against everything collected so far.

Four honesties are wired into the implementation, three of them added after a
[literature pass](docs/research/) found the naive version overstates exposure:

- **Independence is a lie.** Naively summing bits overstates identifiability.
  How badly is measurable: 13 browser attributes sum to 33.45 bits and jointly
  carry 12.10 — a factor of 2.6 million in anonymity-set terms. `combine()`
  takes a redundancy discount whose default, 0.80, is derived from exactly that
  measurement and pinned by a test.
- **Unmeasured is not zero.** An attribute with no entropy figure contributes
  nothing and is reported separately, so the total is always a floor.
- **Entropy is capped by sample size.** You cannot measure more than log₂(N)
  bits from a sample of N. Every published fingerprint entropy is a floor set
  by the study's size, and figures sitting at their ceiling are flagged.
- **Uniqueness is not identification.** Four results stand in a chain —
  *sample-unique → population-unique → linkable → identified* — with attrition
  at every step. This lab measures the first and says so.

## The four halves

| Mode | What it collects | Status |
|---|---|---|
| **broadcast** | The footprint you published: GitHub, writing, package registries, WHOIS | GitHub live |
| **ambient** | The surface you emit without choosing to: fingerprint entropy, tracker graphs, ad-preference dumps | planned |
| **broker** | What the data-brokerage industry sells about you, obtained via subject-access requests | planned |
| **inference** | What a frontier model concludes about you from public text alone | planned |

## Quickstart

```bash
uv sync
cp .env.example .env          # set WMP_GITHUB_LOGIN
uv run wmp sources            # what's configured
uv run wmp refresh            # collect -> tidy parquet -> warehouse
uv run wmp coverage           # what landed
uv run wmp entropy            # how identifiable that makes you
uv run wmp inferences --undisclosed   # what was derived, not disclosed
uv run wmp sql "SELECT * FROM profile WHERE sensitivity != 'public'"
uv run pytest                 # 33 tests, offline
```

## Finding 1: the method was wrong, and wrong in a useful direction

The first run inferred a timezone from nothing but the timestamps on public
GitHub pushes — a field GitHub does not have and the author never entered
anywhere. It returned **UTC-7**. The true answer is **UTC-4**.

The miss is the interesting part. The method reads the middle of your quiet
window as 03:00 local; the author's actual sleep window is 02:00–10:00, and a
sleep midpoint three hours late resolves three hours too far west. The error is
systematic and directional — night owls resolve west, early risers east — which
means it is a *chronotype detector* wearing a timezone's clothes, and that a
tuned constant would fix this one person while breaking everyone else.

So the claim is recorded with `verdict = unverifiable` and the bias is written
down. Inference that is confidently wrong is the normal case in this field, and
a lab that only records its hits is not measuring anything.

## Scope and ethics

**The subject is yourself.** This is a self-audit instrument: you point it at
your own accounts, your own exports, your own subject-access rights. It is
deliberately not built to profile anyone else — no third-party enrichment, no
identity resolution against strangers, no bulk collection.

The repository is public; the data never is. Everything collected lands under
`data/`, which is gitignored several ways over, and the test suite asserts that
those paths are actually ignored — because for a public repo about personal
data, that is the one mistake a later commit cannot undo.

## Status

Phase 0 (apparatus) is done: warehouse, entropy engine, connector contract,
CLI, MCP server, one live connector.

Phase 0.5 is a literature pass — [eight digs](docs/research/) into the
population-baseline problem, adversary modelling, k-anonymity and differential
privacy, behavioural traces, record linkage, LLM inference, personalization
consequence, and countermeasures. It corrected three live errors in the code
and merged two roadmap phases, on the finding that LLM agents now outperform
hand-tuned classical de-anonymization — which makes the linkage half and the
inference half one attack rather than two.

Design and roadmap in [`docs/DESIGN.md`](docs/DESIGN.md).

## Licence

MIT.
