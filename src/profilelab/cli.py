"""`wmp` — the command line for Profile Lab."""

from __future__ import annotations

import typer
from rich.console import Console
from rich.table import Table

from . import analysis, catalog, refresh as refresh_mod, sources, warehouse
from .config import WORLD_POPULATION

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
    for column in ("attribute", "category", "sensitivity", "bits"):
        table.add_column(column)
    for entry in catalog.ATTRIBUTES:
        bits = f"{entry.entropy_bits:.2f}" if entry.entropy_bits is not None else "[dim]unmeasured[/dim]"
        sensitivity = entry.sensitivity
        if sensitivity != "public":
            sensitivity = f"[red]{sensitivity}[/red]"
        table.add_row(entry.attribute, entry.category, sensitivity, bits)
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
    for column in ("claim", "inferred by", "disclosed", "verdict", "confidence", "method"):
        table.add_column(column)
    for row in rows:
        disclosed = "yes" if row["disclosed"] else "[red]no[/red]"
        table.add_row(
            str(row["claim"]),
            str(row["inferred_by"]),
            disclosed,
            str(row["verdict"]),
            f"{row['confidence']:.2f}",
            str(row["method"] or ""),
        )
    console.print(table)


@app.command("entropy")
def entropy_cmd(
    redundancy: float = typer.Option(
        0.0, "-r", "--redundancy", help="Correlation discount in [0,1]; 0 assumes independence."
    ),
) -> None:
    """How identifiable the collected evidence makes you, in bits."""
    _require_warehouse()
    result = analysis.identifiability(redundancy=redundancy)
    console.print(f"\n[bold]{result.summary()}[/bold]")
    console.print(
        f"[dim]budget {result.budget:.2f} bits (world population {WORLD_POPULATION:,}) · "
        f"redundancy discount {result.redundancy:.0%}[/dim]\n"
    )
    if result.measured:
        table = Table(title="measured attributes", header_style="bold")
        table.add_column("attribute")
        table.add_column("bits", justify="right")
        for attribute, bits in result.measured:
            table.add_row(attribute, f"{bits:.2f}")
        console.print(table)
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
