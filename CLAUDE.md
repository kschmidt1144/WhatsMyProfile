# CLAUDE.md — WhatsMyProfile (Profile Lab)

Research instrument that measures the profile of a person which exists
**outside their control**: what surveillance infrastructure infers, and what a
public footprint gives away. Everything is scored in **bits of identifying
information**. Design + roadmap: `docs/DESIGN.md`.

Sibling of `../WorldEconomy` and deliberately built on the same bones (uv +
DuckDB warehouse + connector contract + `*_impl`-backed MCP server), so the
patterns transfer directly.

## Commands (uv-managed, Python 3.12+)

```bash
uv sync
uv run wmp sources                    # connectors + whether each is configured
uv run wmp refresh                    # collect all -> tidy parquet -> warehouse
uv run wmp refresh -s github --force  # one source, re-download
uv run wmp coverage                   # what's collected, by source
uv run wmp entropy [-r 0.3]           # identifiability in bits (-r = redundancy discount)
uv run wmp inferences --undisclosed   # the inference gap
uv run wmp signals -a location        # filter by attribute substring
uv run wmp attributes                 # the registry + reference entropies
uv run wmp sql "SELECT ..."           # read-only; tables below
uv run pytest                         # 33 tests, no network
```

## Architecture

- `data/raw/<source>/` — immutable downloads + `_manifest.json` (url, sha256).
  Gitignored, reproducible via `wmp refresh`.
- `data/tidy/<source>/{signals,attributes,identities,inferences}.parquet` →
  `data/warehouse.duckdb` (rebuilt artifact — delete freely).
- **Four tables.** `signals` (atomic observed facts + evidence), `attributes`
  (registry: category, sensitivity, entropy_bits), `identities` (the identifier
  graph — the join keys that let two datasets become one profile),
  `inferences` (claims *derived* rather than disclosed). View `profile` joins
  signals to their attribute metadata.
- `src/profilelab/sources/<name>.py` — connector contract: `SOURCE`, `TITLE`,
  `MODE` (broadcast|ambient|broker|inference), `available()`, `fetch(force)`,
  `parse() -> Collected`. Shared helpers live in `sources/base.py`, **not** in
  `sources/__init__.py` — the `__init__` imports connectors to build the
  registry, so importing from it inside a connector is a circular import.
- `entropy.py` is the spine; `analysis.py` turns signals into an
  `Identifiability`; `mcp_server.py` wraps testable `*_impl` functions.

## ⚠️ Gotchas

- **This repo is public and holds personal data.** `data/`, `exports/`,
  `subject-access/`, `*.har`, `*.mbox`, `report/figures/*.png` and `.env` are
  gitignored, and `tests/test_sanity.py` asserts it. Run
  `git check-ignore -v <path>` before adding anything new. A figure derived
  from one person's data can be identifying even when it looks aggregate.
- **`known_bits()` returns None, never 0.0**, for an unmeasured attribute.
  Defaulting it to zero would silently understate every identifiability total.
  Callers must handle None and report it as a floor.
- **Never sum bits across correlated attributes without a discount.**
  `entropy.combine(bits, redundancy)` exists for this; `redundancy=0` is an
  upper bound on identifiability, not a neutral default.
- **The stray `~/Repos/.env`** would be swallowed by a bare `load_dotenv()`
  walking up the tree (see `~/Repos/CLAUDE.md`). `config.py` loads this repo's
  `.env` by explicit path — keep it that way.
- **`config.env()` treats blank as absent**, because `.env.example` ships every
  key present-but-empty and a connector must not authenticate with `""`.
- **GitHub timezone inference is chronotype-biased** — it assumes your quiet
  window is centred on 03:00 local, and resolves night owls too far west
  (measured: returned UTC-7 against a true UTC-4). Its claims are recorded
  `unverifiable` on purpose. Do not tune the constant to fit one subject.
- **Connector `parse()` must not touch the network** — it reads only what
  `fetch()` wrote. That is what keeps the suite offline and CI green.

## Scope

Self-audit only: the subject is the operator. No third-party enrichment, no
identity resolution against strangers, no bulk collection. Keep new connectors
inside that line.
