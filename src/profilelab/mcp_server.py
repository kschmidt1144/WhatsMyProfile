"""MCP server — so any Claude session can ask what your profile looks like.

Every tool is a thin wrapper over a testable `*_impl` function; the wrappers
exist only to be registered. Registered as `profilelab`; entry point `wmp-mcp`.
"""

from __future__ import annotations

from mcp.server.fastmcp import FastMCP

from . import analysis, catalog, warehouse

mcp = FastMCP("profilelab")

_NO_DATA = "No warehouse yet. Run `wmp refresh` in the WhatsMyProfile repo first."


def _frame_to_text(frame, empty: str = "(no rows)") -> str:
    if frame is None or len(frame) == 0:
        return empty
    return frame.to_markdown(index=False)


def coverage_impl() -> str:
    if not warehouse.exists():
        return _NO_DATA
    rows = analysis.coverage()
    if not rows:
        return "Warehouse is empty — no connector has collected anything yet."
    lines = ["| source | signals | attributes | last observed |", "|---|---|---|---|"]
    lines += [
        f"| {r['source']} | {r['signals']} | {r['attributes']} | {r['last_observed']} |" for r in rows
    ]
    return "\n".join(lines)


def entropy_impl(redundancy: float | None = None) -> str:
    if not warehouse.exists():
        return _NO_DATA
    result = analysis.identifiability(redundancy=redundancy)
    lines = [
        result.summary(),
        "",
        f"redundancy {result.redundancy:.0%} ({result.redundancy_source})",
        "Chain: sample-unique -> population-unique -> linkable -> identified. "
        "This measures the first step only; uniqueness is not identification.",
    ]
    if result.identifiers:
        lines += [
            "",
            "IDENTIFIERS PRESENT (unique by construction, so the bits are moot): "
            + ", ".join(result.identifiers),
        ]
    if result.measured:
        lines += ["", "Measured quasi-identifiers (bits, sample n):"]
        lines += [
            f"  {attribute}: {bits:.2f} (n={sample_n:,}"
            + (", AT SAMPLE CEILING" if attribute in result.resolution_limited else "")
            + ")"
            for attribute, bits, sample_n in result.measured
        ]
    if result.resolution_limited:
        lines += [
            "",
            "Figures marked AT SAMPLE CEILING are bounded by log2(sample size) — "
            "the study ran out of resolution, so the true entropy is higher.",
        ]
    if result.unmeasured:
        lines += [
            "",
            f"{len(result.unmeasured)} attribute(s) have no entropy figure and contribute 0 bits, "
            "so the total above is a floor rather than an estimate:",
            "  " + ", ".join(result.unmeasured),
        ]
    return "\n".join(lines)


def inferences_impl(undisclosed_only: bool = False) -> str:
    if not warehouse.exists():
        return _NO_DATA
    rows = analysis.inference_gap()
    if undisclosed_only:
        rows = [r for r in rows if not r["disclosed"]]
    if not rows:
        return "No inferences recorded."
    lines = [
        "| claim | inferred by | disclosed | verdict | effect | confidence | method |",
        "|---|---|---|---|---|---|---|",
    ]
    for r in rows:
        lines.append(
            f"| {r['claim']} | {r['inferred_by']} | {'yes' if r['disclosed'] else 'NO'} | "
            f"{r['verdict']} | {r['effect']} | {r['confidence']:.2f} | {r['method'] or ''} |"
        )
    return "\n".join(lines)


def signals_impl(source: str | None = None, attribute: str | None = None, limit: int = 50) -> str:
    if not warehouse.exists():
        return _NO_DATA
    where, params = [], []
    if source:
        where.append("source = ?")
        params.append(source)
    if attribute:
        where.append("attribute LIKE ?")
        params.append(f"%{attribute}%")
    clause = f"WHERE {' AND '.join(where)}" if where else ""
    frame = warehouse.query(
        f"SELECT source, attribute, value, value_num, confidence FROM signals {clause} "
        f"ORDER BY source, attribute LIMIT {int(limit)}",
        params,
    )
    return _frame_to_text(frame)


def attributes_impl() -> str:
    lines = [
        "| attribute | kind | category | sensitivity | bits | sample n |",
        "|---|---|---|---|---|---|",
    ]
    for entry in catalog.ATTRIBUTES:
        bits = f"{entry.entropy_bits:.2f}" if entry.entropy_bits is not None else "unmeasured"
        lines.append(
            f"| {entry.attribute} | {entry.kind} | {entry.category} | {entry.sensitivity} | "
            f"{bits} | {entry.sample_n or ''} |"
        )
    return "\n".join(lines)


def sql_impl(statement: str) -> str:
    if not warehouse.exists():
        return _NO_DATA
    try:
        return _frame_to_text(warehouse.query(statement))
    except Exception as exc:  # noqa: BLE001 — surface the DB error to the caller
        return f"Query failed: {type(exc).__name__}: {exc}"


@mcp.tool()
def profile_coverage() -> str:
    """What profile evidence has been collected, by source. Call this first to orient."""
    return coverage_impl()


@mcp.tool()
def profile_entropy(redundancy: float = -1.0) -> str:
    """How identifiable the collected evidence makes the subject, in bits.

    redundancy (0-1) discounts for correlation between attributes; 0 assumes
    independence and is an upper bound on identifiability. Pass -1 (default) to
    use the measured per-namespace value. The result is uniqueness, not
    identification — see the chain note in the output.
    """
    return entropy_impl(None if redundancy < 0 else redundancy)


@mcp.tool()
def profile_inferences(undisclosed_only: bool = False) -> str:
    """Claims derived about the subject rather than disclosed by them.

    Set undisclosed_only to see just the inference gap — things concluded that
    the subject never published anywhere.
    """
    return inferences_impl(undisclosed_only)


@mcp.tool()
def profile_signals(source: str = "", attribute: str = "", limit: int = 50) -> str:
    """Collected signals, optionally filtered by source or attribute substring."""
    return signals_impl(source or None, attribute or None, limit)


@mcp.tool()
def profile_attributes() -> str:
    """The attribute registry: what each fact means and what it is worth in bits."""
    return attributes_impl()


@mcp.tool()
def profile_sql(statement: str) -> str:
    """Read-only SQL over the warehouse.

    Tables: signals, attributes, identities, inferences. View: profile
    (signals joined to their attribute metadata).
    """
    return sql_impl(statement)


def main() -> None:
    mcp.run()


if __name__ == "__main__":
    main()
