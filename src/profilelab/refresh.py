"""Collect from connectors, write tidy parquet, rebuild the warehouse."""

from __future__ import annotations

from dataclasses import dataclass

from . import sources, warehouse
from .config import ensure_dirs


@dataclass
class SourceResult:
    source: str
    status: str  # collected | skipped | failed
    signals: int = 0
    inferences: int = 0
    detail: str = ""


def refresh(only: list[str] | None = None, force: bool = False) -> list[SourceResult]:
    """Run every configured connector (or just `only`) and rebuild the warehouse.

    A connector that is unconfigured is skipped, and one that fails is recorded
    and stepped over — a single dead source must not cost you the whole
    collection run.
    """
    ensure_dirs()
    names = only or sorted(sources.REGISTRY)
    results: list[SourceResult] = []

    for name in names:
        module = sources.get(name)
        if not module.available():
            results.append(SourceResult(name, "skipped", detail="not configured — see .env.example"))
            continue
        try:
            module.fetch(force=force)
            collected = module.parse()
            warehouse.write_tidy(name, collected)
            results.append(
                SourceResult(name, "collected", len(collected.signals), len(collected.inferences))
            )
        except Exception as exc:  # noqa: BLE001 — one bad source must not abort the run
            results.append(SourceResult(name, "failed", detail=f"{type(exc).__name__}: {exc}"))

    if any(r.status == "collected" for r in results) or warehouse.exists():
        warehouse.build()
    return results
