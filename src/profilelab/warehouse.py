"""The DuckDB warehouse: tidy parquet in, four queryable tables out.

`data/tidy/<source>/{signals,attributes,identities,inferences}.parquet` are the
durable artifacts; `data/warehouse.duckdb` is a rebuilt view over them and can
be deleted at any time without losing anything.
"""

from __future__ import annotations

from dataclasses import fields
from pathlib import Path

import duckdb
import pandas as pd

from . import catalog
from .config import TIDY, WAREHOUSE, ensure_dirs
from .model import Attribute, Collected, Identity, Inference, Signal

TABLES = {
    "signals": Signal,
    "attributes": Attribute,
    "identities": Identity,
    "inferences": Inference,
}


def _frame(rows: list, cls) -> pd.DataFrame:
    """Rows to a DataFrame with the dataclass's columns, even when empty.

    The explicit column list matters: a source that emits no inferences must
    still produce a parquet file with the right schema, or the union at build
    time would fail on whichever source happens to be read first.
    """
    columns = [f.name for f in fields(cls)]
    if not rows:
        return pd.DataFrame(columns=columns)
    return pd.DataFrame([{c: getattr(row, c) for c in columns} for row in rows], columns=columns)


def write_tidy(source: str, collected: Collected) -> Path:
    """Persist one connector's output as parquet under data/tidy/<source>/."""
    out = TIDY / source
    out.mkdir(parents=True, exist_ok=True)
    for table, cls in TABLES.items():
        rows = getattr(collected, table)
        _frame(rows, cls).to_parquet(out / f"{table}.parquet", index=False)
    return out


def _read_all(table: str, cls) -> pd.DataFrame:
    frames = [pd.read_parquet(path) for path in sorted(TIDY.glob(f"*/{table}.parquet"))]
    frames = [f for f in frames if not f.empty]
    if not frames:
        return _frame([], cls)
    return pd.concat(frames, ignore_index=True)


def build() -> Path:
    """Rebuild warehouse.duckdb from every source's tidy parquet."""
    ensure_dirs()
    frames = {table: _read_all(table, cls) for table, cls in TABLES.items()}

    # The static catalog is authoritative; connector-declared attributes fill
    # in anything it does not cover yet.
    declared = _frame(list(catalog.ATTRIBUTES), Attribute)
    frames["attributes"] = pd.concat([declared, frames["attributes"]], ignore_index=True).drop_duplicates(
        subset=["attribute"], keep="first"
    )

    if WAREHOUSE.exists():
        WAREHOUSE.unlink()
    con = duckdb.connect(str(WAREHOUSE))
    try:
        for table, frame in frames.items():
            con.register(f"_{table}", frame)
            con.execute(f"CREATE TABLE {table} AS SELECT * FROM _{table}")
        con.execute(
            """
            CREATE VIEW profile AS
            SELECT s.*, a.title, a.category, a.sensitivity, a.entropy_bits
            FROM signals s LEFT JOIN attributes a USING (attribute)
            """
        )
    finally:
        con.close()
    return WAREHOUSE


def connect(read_only: bool = True) -> duckdb.DuckDBPyConnection:
    if not WAREHOUSE.exists():
        raise RuntimeError("no warehouse yet — run `wmp refresh` first")
    return duckdb.connect(str(WAREHOUSE), read_only=read_only)


def query(sql: str, params: list | None = None) -> pd.DataFrame:
    """Run a read-only query. The connection is read-only at the engine level,
    so a mutating statement fails in DuckDB rather than relying on us to spot it."""
    con = connect(read_only=True)
    try:
        return con.execute(sql, params or []).df()
    finally:
        con.close()


def exists() -> bool:
    return WAREHOUSE.exists()
