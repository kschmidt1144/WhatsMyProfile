"""`wmp` — the command line for Profile Lab."""

from __future__ import annotations

import typer
from rich.console import Console
from rich.table import Table

from rich.prompt import Confirm, Prompt

from . import analysis, catalog, entropy, reading, refresh as refresh_mod, sources, truth, warehouse
from .sources import adprefs
from .sources.adprefs import base as adprefs_base

app = typer.Typer(
    no_args_is_help=True,
    add_completion=False,
    help="What's My Profile — measure the profile of yourself that exists outside your control.",
)
console = Console()


def _print(frame, title: str, empty: str = "nothing collected yet — run `wmp refresh`") -> None:
    if frame is None or len(frame) == 0:
        console.print(f"[yellow]{empty}[/yellow]")
        return
    table = Table(title=title, header_style="bold")
    for column in frame.columns:
        table.add_column(str(column))
    for row in frame.itertuples(index=False):
        table.add_row(*["" if value is None else str(value) for value in row])
    console.print(table)


@app.command("sources")
def list_sources() -> None:
    """List connectors and whether each is configured."""
    table = Table(title="connectors", header_style="bold")
    for column in ("source", "mode", "title", "configured"):
        table.add_column(column)
    for name in sorted(sources.REGISTRY):
        module = sources.get(name)
        ready = module.available()
        table.add_row(
            name,
            module.MODE,
            module.TITLE,
            "[green]yes[/green]" if ready else "[yellow]no[/yellow]",
        )
    console.print(table)


@app.command()
def refresh(
    source: list[str] = typer.Option(None, "-s", "--source", help="Only these sources (repeatable)."),
    force: bool = typer.Option(False, "--force", help="Re-download instead of using cached raw artifacts."),
) -> None:
    """Collect from every configured connector and rebuild the warehouse."""
    results = refresh_mod.refresh(only=list(source) if source else None, force=force)
    table = Table(title="refresh", header_style="bold")
    for column in ("source", "status", "signals", "inferences", "detail"):
        table.add_column(column)
    colours = {"collected": "green", "skipped": "yellow", "failed": "red"}
    for result in results:
        table.add_row(
            result.source,
            f"[{colours[result.status]}]{result.status}[/{colours[result.status]}]",
            str(result.signals or ""),
            str(result.inferences or ""),
            result.detail,
        )
    console.print(table)
    if any(r.status == "failed" for r in results):
        raise typer.Exit(1)


def _require_warehouse() -> None:
    if not warehouse.exists():
        console.print("[yellow]no warehouse yet — run `wmp refresh` (and see `wmp sources`)[/yellow]")
        raise typer.Exit(1)


@app.command()
def exports() -> None:
    """Where to request each platform's profile of you, and what has landed."""
    root = adprefs_base.exports_root()
    console.print(f"\n[bold]exports directory[/bold] [dim]{root}[/dim]")
    console.print("[dim]override with WMP_EXPORTS_DIR · gitignored — never commit an archive[/dim]\n")

    for module in adprefs.PLATFORMS:
        found = adprefs_base.find_files(module.PLATFORM)
        status = f"[green]{len(found)} file(s)[/green]" if found else "[yellow]not found[/yellow]"
        console.print(f"[bold]{module.SOURCE}[/bold] — {module.TITLE}  {status}")
        for path in found:
            console.print(f"    [dim]{path}[/dim]")
        if not found:
            console.print(f"    [dim]{module.PLATFORM.how_to}[/dim]")
            console.print(f"    [dim]looks for: {', '.join(module.PLATFORM.candidates)}[/dim]")
        console.print()


@app.command()
def agreement(
    min_platforms: int = typer.Option(
        2, "-m", "--min-platforms", help="Only topics asserted by at least this many platforms."
    ),
) -> None:
    """Cross-platform agreement on what you are interested in."""
    _require_warehouse()
    rows = analysis.platform_agreement(min_platforms=min_platforms)
    if not rows:
        console.print(
            "[yellow]no ad-preference data yet[/yellow] [dim]— see `wmp exports`. "
            "Cross-platform comparison needs at least two platforms loaded.[/dim]"
        )
        return
    table = Table(title=f"topics asserted by ≥{min_platforms} platform(s)", header_style="bold")
    for column in ("topic", "platforms", "sources", "facet"):
        table.add_column(column)
    for row in rows:
        table.add_row(str(row["topic"]), str(row["platforms"]), str(row["sources"]), str(row["facet"]))
    console.print(table)
    console.print(
        "[dim]Convergence across platforms means an attribute is genuinely recoverable "
        "from behaviour. Divergence means at least one of them is wrong — which, given "
        "measured segment accuracy, is the expected case.[/dim]"
    )


@app.command()
def read(
    model: str = typer.Option(reading.DEFAULT_MODEL, "-m", "--model"),
    exclude: str = typer.Option(
        None, "-x", "--exclude", help="Drop attributes matching this substring (held-out test)."
    ),
    yes: bool = typer.Option(False, "--yes", help="Skip the confirmation prompt."),
    dry_run: bool = typer.Option(False, "--dry-run", help="Print the briefing and send nothing."),
) -> None:
    """Ask a model to profile you from the collected signals.

    Its claims land in the inferences table like any platform's, and are scored
    the same way — the point of Finding 2.
    """
    _require_warehouse()
    text = reading.briefing(exclude=exclude)
    if not text:
        console.print("[yellow]no signals collected yet — run `wmp refresh`[/yellow]")
        raise typer.Exit(1)

    lines = len(text.splitlines())
    if dry_run:
        console.print(text)
        console.print(f"\n[dim]{lines} signal(s) — nothing sent[/dim]")
        return

    console.print(
        f"\n[bold red]This sends your profile off-machine.[/bold red] "
        f"[dim]Everything else in this lab runs locally; this transmits "
        f"{lines} collected signal(s) to the Anthropic API as {model}.[/dim]"
    )
    console.print("[dim]Preview it first with `wmp read --dry-run`.[/dim]\n")
    if not yes and not Confirm.ask("Send the briefing?", default=False):
        console.print("[dim]cancelled — nothing sent[/dim]")
        return

    try:
        result = reading.read(model=model, exclude=exclude)
    except Exception as exc:  # noqa: BLE001 — surface the API error plainly
        console.print(f"[red]reading failed:[/red] {type(exc).__name__}: {exc}")
        raise typer.Exit(1) from exc

    if result.refused:
        console.print(f"[yellow]{result.detail}[/yellow]")
        return

    stored = reading.store(result)
    console.print(f"[green]{stored} claim(s) recorded[/green] [dim]as {model}[/dim]")
    console.print(
        f"[dim]score them with `wmp score -s {reading.SOURCE}`, then `wmp scorecard`[/dim]"
    )


@app.command()
def score(
    source: str = typer.Option(None, "-s", "--source", help="Only score claims from this source."),
    limit: int = typer.Option(20, "-n", "--limit", help="How many to score in this sitting."),
    include_disclosed: bool = typer.Option(
        False, "--include-disclosed", help="Also score claims you did disclose."
    ),
) -> None:
    """Judge what was inferred about you — the ground truth the gap is measured against.

    Answers are saved after each one, so quitting mid-way keeps your progress.
    """
    _require_warehouse()
    pending = analysis.unscored_inferences(source=source, undisclosed_only=not include_disclosed)
    if not pending:
        console.print("[green]nothing left to score[/green] [dim]— see `wmp scorecard`[/dim]")
        return

    console.print(
        f"\n[bold]{len(pending)} claim(s) awaiting judgement[/bold] "
        f"[dim]· scoring up to {limit} now[/dim]"
    )
    console.print(
        "[dim]Your answers are stored in data/truth/, apart from everything else, and are "
        "more sensitive than the claims they judge. `wmp forget-truth` deletes them all.[/dim]\n"
    )

    recorded = 0
    for index, row in enumerate(pending[:limit], start=1):
        console.print(f"[dim]{index}/{min(limit, len(pending))}[/dim] [bold]{row['claim']}[/bold]")
        console.print(f"    [dim]inferred by {row['inferred_by']}[/dim]")
        answer = Prompt.ask(
            "    true of you? [green]y[/green]es / [red]n[/red]o / "
            "[dim]u[/dim]nverifiable / [dim]s[/dim]kip / [dim]q[/dim]uit",
            choices=["y", "n", "u", "s", "q"],
            default="s",
            show_choices=False,
            show_default=False,
        )
        if answer == "q":
            break
        if answer == "s":
            console.print()
            continue
        verdict = {"y": "correct", "n": "incorrect", "u": "unverifiable"}[answer]
        truth.record(row["from_sources"], row["claim"], verdict)
        recorded += 1
        console.print()

    console.print(f"[green]recorded {recorded} verdict(s)[/green]")
    if recorded:
        warehouse.build()  # fold the new verdicts into the warehouse
        console.print("[dim]warehouse rebuilt — run `wmp scorecard`[/dim]")


@app.command()
def scorecard() -> None:
    """How well the inferences held up, and how many were right but undisclosed."""
    _require_warehouse()
    card = analysis.scorecard()
    if not card.total:
        console.print("[yellow]no inferences recorded yet[/yellow]")
        return

    console.print(f"\n[bold]{card.scored} of {card.total} claim(s) scored[/bold]")
    if not card.scored:
        console.print("[dim]run `wmp score` to judge them[/dim]")
        return

    table = Table(title="verdicts", header_style="bold")
    for column in ("verdict", "count"):
        table.add_column(column)
    table.add_row("[green]correct[/green]", str(card.correct))
    table.add_row("[red]incorrect[/red]", str(card.incorrect))
    table.add_row("[dim]unverifiable[/dim]", str(card.unverifiable))
    console.print(table)

    if card.by_source and len(card.by_source) > 1:
        per = Table(title="by source", header_style="bold")
        for column in ("source", "scored", "correct", "incorrect", "accuracy"):
            per.add_column(column)
        for row in card.by_source:
            # DuckDB SUM() comes back as float through pandas; these are counts.
            correct, incorrect = int(row["correct"] or 0), int(row["incorrect"] or 0)
            dec = correct + incorrect
            per.add_row(
                str(row["source"]), str(int(row["scored"] or 0)), str(correct),
                str(incorrect), f"{correct / dec:.0%}" if dec else "—",
            )
        console.print(per)
        console.print(
            "[dim]Read the per-source rows, not the total. Blending a commercial ad profile "
            "with a one-off heuristic averages two unrelated things.[/dim]"
        )

    if card.accuracy is not None:
        industry = analysis.INDUSTRY_INTEREST_ACCURACY
        lo, hi = card.accuracy_interval
        console.print(
            f"\n[bold]accuracy {card.accuracy:.0%}[/bold] "
            f"[dim]on {card.decided} decided claim(s), 95% CI [{lo:.0%}, {hi:.0%}][/dim]"
        )
        # Only claim a difference the interval actually supports.
        if lo > industry:
            comparison = f"[green]above[/green] the {industry:.0%} industry benchmark"
        elif hi < industry:
            comparison = f"[red]below[/red] the {industry:.0%} industry benchmark"
        else:
            comparison = (
                f"[yellow]indistinguishable[/yellow] from the {industry:.0%} industry benchmark "
                f"— the interval contains it, so this sample cannot tell them apart"
            )
        console.print(f"[dim]{comparison} (19 data brokers' interest segments)[/dim]")
    console.print(
        f"\n[bold]{card.undisclosed_correct} claim(s) correct AND never disclosed by you.[/bold]"
    )
    console.print(
        "[dim]That is the inference gap: things a system worked out that you never told it.[/dim]"
    )
    if card.unscored:
        console.print(f"\n[yellow]{card.unscored} still unscored[/yellow] [dim]— `wmp score`[/dim]")


@app.command("forget-truth")
def forget_truth(
    yes: bool = typer.Option(False, "--yes", help="Skip the confirmation prompt."),
) -> None:
    """Delete every recorded ground-truth verdict."""
    stored = len(truth.load())
    if not stored:
        console.print("[dim]no verdicts stored[/dim]")
        return
    if not yes and not Confirm.ask(f"Delete all {stored} recorded verdict(s)?", default=False):
        console.print("[dim]kept[/dim]")
        return
    console.print(f"[green]deleted {truth.clear()} verdict(s)[/green]")
    if warehouse.exists():
        warehouse.build()


@app.command()
def coverage() -> None:
    """What has been collected, by source."""
    _require_warehouse()
    rows = analysis.coverage()
    table = Table(title="coverage", header_style="bold")
    for column in ("source", "signals", "attributes", "last observed"):
        table.add_column(column)
    if not rows:
        console.print("[yellow]nothing collected yet — run `wmp refresh`[/yellow]")
        return
    for row in rows:
        table.add_row(row["source"], str(row["signals"]), str(row["attributes"]), str(row["last_observed"]))
    console.print(table)


@app.command()
def attributes() -> None:
    """The attribute registry: what each fact means and what it costs in bits."""
    table = Table(title="attributes", header_style="bold")
    for column in ("attribute", "kind", "category", "sensitivity", "bits", "sample n"):
        table.add_column(column)
    for entry in catalog.ATTRIBUTES:
        bits = f"{entry.entropy_bits:.2f}" if entry.entropy_bits is not None else "[dim]unmeasured[/dim]"
        sensitivity = entry.sensitivity
        if sensitivity != "public":
            sensitivity = f"[red]{sensitivity}[/red]"
        kind = entry.kind
        if kind == "identifier":
            kind = f"[red]{kind}[/red]"
        table.add_row(
            entry.attribute, kind, entry.category, sensitivity, bits,
            f"{entry.sample_n:,}" if entry.sample_n else "",
        )
    console.print(table)


@app.command()
def signals(
    source: str = typer.Option(None, "-s", "--source"),
    attribute: str = typer.Option(None, "-a", "--attribute"),
    limit: int = typer.Option(50, "-n", "--limit"),
) -> None:
    """Show collected signals."""
    _require_warehouse()
    where, params = [], []
    if source:
        where.append("source = ?")
        params.append(source)
    if attribute:
        where.append("attribute LIKE ?")
        params.append(f"%{attribute}%")
    clause = f"WHERE {' AND '.join(where)}" if where else ""
    frame = warehouse.query(
        f"SELECT source, attribute, value, value_num, confidence, evidence "
        f"FROM signals {clause} ORDER BY source, attribute LIMIT {int(limit)}",
        params,
    )
    _print(frame, "signals")


@app.command()
def inferences(
    undisclosed: bool = typer.Option(False, "--undisclosed", help="Only claims you never disclosed."),
) -> None:
    """Claims derived about you rather than stated by you."""
    _require_warehouse()
    rows = analysis.inference_gap()
    if undisclosed:
        rows = [row for row in rows if not row["disclosed"]]
    if not rows:
        console.print("[yellow]no inferences recorded yet[/yellow]")
        return
    table = Table(title="inference gap", header_style="bold")
    for column in ("claim", "inferred by", "disclosed", "verdict", "effect", "confidence", "method"):
        table.add_column(column)
    for row in rows:
        disclosed = "yes" if row["disclosed"] else "[red]no[/red]"
        effect = str(row["effect"])
        if effect == "observed":
            effect = f"[red]{effect}[/red]"
        table.add_row(
            str(row["claim"]),
            str(row["inferred_by"]),
            disclosed,
            str(row["verdict"]),
            effect,
            f"{row['confidence']:.2f}",
            str(row["method"] or ""),
        )
    console.print(table)


@app.command("entropy")
def entropy_cmd(
    redundancy: float = typer.Option(
        None, "-r", "--redundancy", help="Correlation discount in [0,1]. Omit to use the measured default."
    ),
) -> None:
    """How identifiable the collected evidence makes you, in bits."""
    _require_warehouse()
    result = analysis.identifiability(redundancy=redundancy)
    console.print(f"\n[bold]{result.summary()}[/bold]")
    console.print(
        f"[dim]budget {result.budget:.2f} bits (population {result.population:,}) · "
        f"redundancy {result.redundancy:.0%} ({result.redundancy_source})[/dim]"
    )
    console.print(
        "[dim]chain: sample-unique → population-unique → linkable → identified. "
        "This measures the first step only.[/dim]\n"
    )
    if result.identifiers:
        console.print(
            "[red]identifiers present[/red] [dim]— unique by construction, so the bits below "
            "are moot for anyone who can read them:[/dim]"
        )
        console.print("[dim]  " + ", ".join(result.identifiers) + "[/dim]\n")
    if result.measured:
        table = Table(title="measured quasi-identifiers", header_style="bold")
        table.add_column("attribute")
        table.add_column("bits", justify="right")
        table.add_column("sample n", justify="right")
        table.add_column("ceiling", justify="right")
        for attribute, bits, sample_n in result.measured:
            ceiling = f"{entropy.sample_ceiling(sample_n):.2f}"
            if attribute in result.resolution_limited:
                ceiling = f"[yellow]{ceiling} ⚠[/yellow]"
            table.add_row(attribute, f"{bits:.2f}", f"{sample_n:,}", ceiling)
        console.print(table)
    if result.resolution_limited:
        console.print(
            "[yellow]⚠ at the sample ceiling[/yellow] [dim]— log2(n) bounds what a sample can "
            "measure, so these are floors set by the study's size, not findings.[/dim]"
        )
    if result.unmeasured:
        console.print(
            f"\n[yellow]{len(result.unmeasured)} attribute(s) carry no entropy figure yet[/yellow] "
            "[dim]— they contribute 0 bits above, so the total is a floor, not an estimate:[/dim]"
        )
        console.print("[dim]  " + ", ".join(result.unmeasured) + "[/dim]")


@app.command()
def sql(statement: str = typer.Argument(..., help="Read-only SQL over the warehouse.")) -> None:
    """Query the warehouse: tables signals, attributes, identities, inferences; view profile."""
    _require_warehouse()
    _print(warehouse.query(statement), "query")


if __name__ == "__main__":
    app()
