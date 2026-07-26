"""Subject-access requests — asking holders what they have, and recording what happens.

The point of this module is not that requests succeed. Most will not. The
subject is in Ohio, which has **no comprehensive privacy law**, so there is no
state right to access, correct, or delete. And even where a right exists,
brokers' own CPPA filings show denial rates of 45–97%, while EFF found over 40%
of registered brokers never respond at all.

So the refusals are the finding. A tracker that records *asked → refused /
ignored / complied*, with the basis claimed and the reason given, measures what
the right to know is actually worth to someone the law does not cover. That is
a result whether or not a single broker complies.

**The one right that does reach Ohio is federal.** FCRA §609(a)
(15 U.S.C. §1681g) requires a consumer reporting agency to disclose, on request
and proper identification, all information in the consumer's file and its
sources, plus who accessed it. §1681j makes one disclosure free every 12 months
from nationwide and nationwide-specialty CRAs, and specialty CRAs must respond
within 15 days. That applies in every state — which makes the CRAs the highest
-yield targets by a wide margin, and the reason this module distinguishes bases
rather than sending one generic letter.

⚠️ Records here contain the subject's real name, address, and correspondence —
the most identifying material in the project. `data/sar/` is gitignored, and a
test asserts it.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from datetime import date, timedelta

from .config import DATA

STORE = DATA / "sar" / "requests.json"

# What you can actually claim, and how long they get.
BASES = {
    "fcra_609": (
        "FCRA §609(a) / 15 U.S.C. §1681g — full file disclosure from a consumer "
        "reporting agency. Federal, so it reaches Ohio.",
        15,
    ),
    "fcra_611": (
        "FCRA §611 / 15 U.S.C. §1681i — dispute and reinvestigation of inaccurate "
        "file contents.",
        30,
    ),
    "voluntary": (
        "No statutory right in Ohio — the company extends access as policy. "
        "Refusal here is lawful and is itself the datum.",
        45,
    ),
    "none": ("No basis and no published policy. Sent to measure the response.", 45),
}

STATUSES = ("drafted", "sent", "acknowledged", "complied", "partial", "refused", "ignored")


@dataclass(frozen=True)
class Target:
    name: str
    basis: str
    route: str
    note: str = ""


# Curated rather than generated. The registry names 581 brokers, but the ones
# worth writing to are decided by legal basis and published route, not by volume.
TARGETS: tuple[Target, ...] = (
    # ── federal right, applies in Ohio, 15-day clock ─────────────────────────
    Target("LexisNexis Risk Solutions", "fcra_609", "consumer.risk.lexisnexis.com",
           "Public records, addresses, liens, judgments. Owns SageStream."),
    Target("SageStream, LLC", "fcra_609", "sagestreamllc.com",
           "Alternative credit data. One free report every 12 months."),
    Target("Innovis", "fcra_609", "innovis.com", "Fourth nationwide credit bureau."),
    Target("ChexSystems", "fcra_609", "chexsystems.com", "Banking and deposit-account history."),
    Target("Early Warning Services", "fcra_609", "earlywarning.com",
           "Bank-owned; deposit accounts and Zelle."),
    Target("The Work Number (Equifax Workforce)", "fcra_609", "theworknumber.com",
           "Employment and income history."),
    Target("CoreLogic Teletrack", "fcra_609", "consumers.corelogic.com",
           "Rental, property, and alternative credit."),
    Target("NCTUE", "fcra_609", "nctue.com", "Utility and telecom account history."),
    # ── voluntary policy, no Ohio right ──────────────────────────────────────
    Target("Acxiom LLC", "voluntary", "acxiom.com/privacy/us/",
           "Extends access to all US consumers. Denied 45% of 324 requests in its own filing."),
    Target("LiveRamp", "voluntary", "liveramp.com/privacy/my-privacy-choices/",
           "Identity graph; owns the Acxiom marketing-data lineage."),
    # ── controls: high published denial rates, no obligation to Ohio ─────────
    Target("Zeta Global", "none", "zetaglobal.com",
           "Denied 2,045 of 2,556 requests (80%). Collects sexual orientation, "
           "gender identity, precise geolocation."),
    Target("Epsilon Data Management", "none", "epsilon.com",
           "Denied 808 of 1,544 (52%)."),
    Target("DealerX Partners LLC", "none", "dealerx.com",
           "Denied 11,157 of 11,541 (97%) — the highest rate in the registry."),
)

_FCRA_TEMPLATE = """\
{target}

Re: Request for full file disclosure under the Fair Credit Reporting Act

To whom it may concern,

Under Section 609(a) of the Fair Credit Reporting Act (15 U.S.C. §1681g), I \
request disclosure of all information in my consumer file at the time of this \
request, including:

  1. All information in the file, whatever its source;
  2. The sources of that information;
  3. Each person that procured a consumer report on me — for employment \
purposes within the past two years, and for any other purpose within the past \
one year;
  4. Any consumer score you hold on me, together with the key factors that \
adversely affected it.

I am requesting this as my free annual file disclosure under 15 U.S.C. §1681j. \
I understand a nationwide specialty consumer reporting agency must respond \
within 15 days of receiving a request.

Identifying information:
  Full name:        {name}
  Current address:  {address}
  Previous address: {previous}
  Date of birth:    {dob}
  SSN:              {ssn}

Please send the disclosure to the address above. If you contend you are not a \
consumer reporting agency subject to §1681g, please say so in writing and \
state the basis.

Sincerely,
{name}
"""

_VOLUNTARY_TEMPLATE = """\
{target}

Re: Request for access to personal information you hold about me

To whom it may concern,

I am requesting a copy of the personal information you hold about me, together \
with:

  1. The categories of personal information you have collected;
  2. The sources from which it was collected;
  3. The categories of third parties to whom you have sold, shared, or \
otherwise disclosed it;
  4. Any inferences, scores, or audience segments you have derived about me;
  5. The business or commercial purpose for collecting it.

I am a resident of Ohio, which has not enacted a comprehensive consumer privacy \
statute. I am aware you may have no statutory obligation to respond to me. I am \
asking on the basis of your published privacy policy, which extends access \
rights beyond the states that mandate them.

Identifying information:
  Full name:       {name}
  Current address: {address}
  Email:           {email}

If you decline, I would be grateful for a written response saying so and \
stating the reason — including simply that I am not a covered resident. A \
recorded refusal is a complete answer for my purposes.

Sincerely,
{name}
"""


@dataclass
class Request:
    """One request, and whatever came back."""

    target: str
    basis: str
    route: str
    sent_on: str = ""
    due_on: str = ""
    status: str = "drafted"
    outcome: str = ""
    notes: str = ""

    def __post_init__(self) -> None:
        if self.basis not in BASES:
            raise ValueError(f"unknown basis {self.basis!r}; expected one of {sorted(BASES)}")
        if self.status not in STATUSES:
            raise ValueError(f"unknown status {self.status!r}; expected one of {STATUSES}")

    @property
    def overdue(self) -> bool:
        """Past its deadline with nothing back — the measurable form of ignored."""
        if self.status not in {"sent", "acknowledged"} or not self.due_on:
            return False
        return date.fromisoformat(self.due_on) < date.today()


def draft(target: Target, identity: dict[str, str]) -> str:
    """Render the request text. Identity fields are the subject's to fill in."""
    fields = {
        "target": target.name,
        "name": identity.get("name", "[YOUR FULL NAME]"),
        "address": identity.get("address", "[YOUR CURRENT ADDRESS]"),
        "previous": identity.get("previous", "[PREVIOUS ADDRESS, IF ANY]"),
        "dob": identity.get("dob", "[DATE OF BIRTH]"),
        "ssn": identity.get("ssn", "[SSN — required by CRAs to locate your file]"),
        "email": identity.get("email", "[YOUR EMAIL]"),
    }
    template = _FCRA_TEMPLATE if target.basis.startswith("fcra") else _VOLUNTARY_TEMPLATE
    return template.format(**fields)


def load() -> list[Request]:
    if not STORE.exists():
        return []
    try:
        payload = json.loads(STORE.read_text())
    except json.JSONDecodeError:
        return []
    return [Request(**row) for row in payload.get("requests", [])]


def save(requests: list[Request]) -> None:
    STORE.parent.mkdir(parents=True, exist_ok=True)
    STORE.write_text(
        json.dumps(
            {
                "version": 1,
                "note": (
                    "Subject-access request log. Contains the subject's identity and "
                    "correspondence — never commit, never share."
                ),
                "requests": [asdict(r) for r in requests],
            },
            indent=2,
        )
    )


def record(target: Target, sent_on: str | None = None, status: str = "sent") -> Request:
    """Log a request as sent, computing its deadline from the claimed basis."""
    sent = sent_on or date.today().isoformat()
    _, days = BASES[target.basis]
    request = Request(
        target=target.name,
        basis=target.basis,
        route=target.route,
        sent_on=sent,
        due_on=(date.fromisoformat(sent) + timedelta(days=days)).isoformat(),
        status=status,
    )
    requests = [r for r in load() if r.target != target.name]
    requests.append(request)
    save(requests)
    return request


def update(target_name: str, status: str, outcome: str = "", notes: str = "") -> Request | None:
    requests = load()
    for i, request in enumerate(requests):
        if request.target.casefold() == target_name.casefold():
            requests[i] = Request(
                target=request.target, basis=request.basis, route=request.route,
                sent_on=request.sent_on, due_on=request.due_on, status=status,
                outcome=outcome or request.outcome, notes=notes or request.notes,
            )
            save(requests)
            return requests[i]
    return None


def target_by_name(name: str) -> Target | None:
    for target in TARGETS:
        if target.name.casefold().startswith(name.casefold()):
            return target
    return None
