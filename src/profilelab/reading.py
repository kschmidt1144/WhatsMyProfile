"""LLM readings — what a model concludes about you, entered as scoreable claims.

Finding 2 is why this exists. Given the raw ad topics, a model read a
"moving house" narrative into nine of them and was wrong on every topic that
actually encoded moving. That reading arrived as prose in a chat window, never
reached the `inferences` table, and was never scored — which made the
instrument's most fluent source of claims its only unaudited one.

So a reading is a connector-shaped act: briefing in, `Inference` rows out,
`inferred_by = <model>`, scored by `wmp score` exactly like a platform's claims.

⚠️ **This is the only part of the lab that sends your profile off-machine.**
Everything else runs locally against files you already have. `wmp read`
transmits the briefing to Anthropic's API, so it asks before doing so.

Two correctness properties the briefing must hold, both enforced by tests:

1. **It never contains verdicts.** Ground truth is the answer key; a briefing
   that leaked it would measure the model's reading comprehension rather than
   its inference.
2. **It never contains prior inferences.** Showing the model what Google
   already concluded turns "what can you derive?" into "do you agree?" — a
   different and much easier question.
"""

from __future__ import annotations

from dataclasses import dataclass

from pydantic import BaseModel, Field

from . import warehouse
from .config import subject
from .model import Collected, Inference
from .sources.base import now

# The skill's default and this project's: latest and most capable.
DEFAULT_MODEL = "claude-opus-5"

SOURCE = "llm_reading"

CATEGORIES = ("location", "employment", "demographics", "interests", "behavior", "other")

PROMPT = """\
Below is a set of signals collected about one person from public and \
platform-exported sources. Each line is an attribute and a value.

Infer what you can about this person. Report only claims you can actually \
support from the signals — for each one, say which signals led you there.

Rules:
- State each claim as a short, checkable proposition, not a hedge. \
"lives in the US Eastern timezone" is checkable; "may have some interest in \
technology" is not.
- Do not restate a signal as a claim. If the data says the person uses \
Python, "uses Python" is an observation, not an inference. Claim what the \
signals imply that they do not state.
- Prefer fewer, better-supported claims over a long speculative list.
- Give an honest confidence. A claim you would bet on at 60% should say 0.6.

Signals:
{briefing}
"""


class Claim(BaseModel):
    """One inference the model is willing to commit to."""

    claim: str = Field(description="A short, checkable proposition about the subject.")
    category: str = Field(description=f"One of: {', '.join(CATEGORIES)}")
    confidence: float = Field(description="0.0 to 1.0 — how strongly the signals support this.")
    basis: str = Field(description="Which signals led to this claim.")


class Reading(BaseModel):
    claims: list[Claim]


@dataclass
class ReadingResult:
    model: str
    collected: Collected
    briefing_lines: int
    refused: bool = False
    detail: str = ""


def briefing(exclude: str | None = None) -> str:
    """Build the profile summary sent to the model.

    Reads the `signals` table only. Never touches `inferences` — which holds
    both prior claims and the subject's verdicts on them — so the answer key
    cannot leak into the question.

    `exclude` drops attributes matching a substring, which is what makes a
    held-out experiment possible: hide the timezone signals, ask the model to
    infer a timezone, and the answer is a measurement rather than a readback.
    """
    frame = warehouse.query(
        """
        SELECT attribute, value, value_num
        FROM signals
        ORDER BY attribute, value
        """
    )
    if frame.empty:
        return ""

    lines: list[str] = []
    for row in frame.itertuples(index=False):
        if exclude and exclude.lower() in str(row.attribute).lower():
            continue
        count = f" (x{int(row.value_num)})" if row.value_num and row.value_num > 1 else ""
        lines.append(f"- {row.attribute}: {row.value}{count}")
    return "\n".join(lines)


def read(model: str = DEFAULT_MODEL, exclude: str | None = None) -> ReadingResult:
    """Ask a model to profile the subject from the collected signals."""
    import anthropic  # imported lazily so the rest of the CLI runs without a key

    text = briefing(exclude=exclude)
    if not text:
        raise RuntimeError("no signals collected yet — run `wmp refresh` first")

    # Do NOT gate on ANTHROPIC_API_KEY being set. The SDK resolves credentials
    # from several sources in order — the env var, ANTHROPIC_AUTH_TOKEN, an
    # `ant auth login` profile on disk, workload identity — so an unset env var
    # does not mean unauthenticated. Construct the client bare and let it
    # resolve; an AuthenticationError is the real signal.
    try:
        client = anthropic.Anthropic()
    except Exception as exc:  # noqa: BLE001 — construction fails only on config
        raise RuntimeError(
            f"could not construct the Anthropic client ({exc}). Set ANTHROPIC_API_KEY "
            "in .env, or run `ant auth login` to store a profile."
        ) from exc
    try:
        response = client.messages.parse(
            model=model,
            max_tokens=16000,
            messages=[{"role": "user", "content": PROMPT.format(briefing=text)}],
            output_format=Reading,
        )
    except anthropic.AuthenticationError as exc:
        raise RuntimeError(
            "no valid Anthropic credentials. Set ANTHROPIC_API_KEY in .env "
            "(see .env.example), or run `ant auth login`."
        ) from exc

    line_count = len(text.splitlines())
    # Safety classifiers can decline; that is a content outcome, not an error.
    if response.stop_reason == "refusal":
        return ReadingResult(model, Collected(), line_count, refused=True,
                             detail="the model declined to profile this briefing")

    me = subject()
    seen = now()
    collected = Collected()
    for claim in response.parsed_output.claims:
        category = claim.category if claim.category in CATEGORIES else "other"
        collected.inferences.append(
            Inference(
                subject=me,
                claim=claim.claim,
                inferred_by=model,
                # Must match the tidy-source name in store(): verdicts are keyed
                # on from_sources, so a mismatch orphans every score.
                from_sources=SOURCE,
                # A model reading public signals was told nothing directly; if
                # it happens to restate something disclosed, scoring catches it.
                disclosed=False,
                verdict="unverifiable",
                # A reading changes nothing on its own — unlike an ad-preference
                # claim, which reached a targeting system by construction.
                effect="none",
                confidence=max(0.0, min(1.0, claim.confidence)),
                method=f"{category}: {claim.basis}",
            )
        )
    return ReadingResult(model, collected, line_count)


def store(result: ReadingResult) -> int:
    """Persist a reading as its own source and rebuild the warehouse."""
    warehouse.write_tidy(SOURCE, result.collected)
    warehouse.build()
    return len(result.collected.inferences)
