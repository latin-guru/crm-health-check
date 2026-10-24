"""Create the DuckDB database: load the CSV exports and config tables, then run .sql files."""

import csv
from pathlib import Path

import duckdb

from chc.paths import SQL_DIR

# Column names and types of every input table, in the same order as the CSV headers.
SCHEMA: dict[str, dict[str, str]] = {
    "owners": {"owner_id": "VARCHAR", "name": "VARCHAR", "team": "VARCHAR", "active": "BOOLEAN"},
    "companies": {
        "company_id": "VARCHAR",
        "name": "VARCHAR",
        "domain": "VARCHAR",
        "industry": "VARCHAR",
        "team": "VARCHAR",
        "owner_id": "VARCHAR",
        "created_at": "TIMESTAMP",
    },
    "contacts": {
        "contact_id": "VARCHAR",
        "first_name": "VARCHAR",
        "last_name": "VARCHAR",
        "email": "VARCHAR",
        "company_id": "VARCHAR",
        "lifecycle_stage": "VARCHAR",
        "owner_id": "VARCHAR",
        "created_at": "TIMESTAMP",
        "original_source": "VARCHAR",
        "utm_source": "VARCHAR",
        "utm_medium": "VARCHAR",
        "utm_campaign": "VARCHAR",
    },
    "deals": {
        "deal_id": "VARCHAR",
        "name": "VARCHAR",
        "company_id": "VARCHAR",
        "primary_contact_id": "VARCHAR",
        "owner_id": "VARCHAR",
        "pipeline": "VARCHAR",
        "stage": "VARCHAR",
        "amount": "DOUBLE",
        "currency": "VARCHAR",
        "term_months": "INTEGER",
        "close_date": "DATE",
        "created_at": "TIMESTAMP",
        "last_stage_change_at": "TIMESTAMP",
    },
    "deal_stage_history": {
        "deal_id": "VARCHAR",
        "from_stage": "VARCHAR",
        "to_stage": "VARCHAR",
        "changed_at": "TIMESTAMP",
    },
    "touchpoints": {
        "touchpoint_id": "VARCHAR",
        "contact_id": "VARCHAR",
        "occurred_at": "TIMESTAMP",
        "channel": "VARCHAR",
        "utm_source": "VARCHAR",
        "utm_medium": "VARCHAR",
        "utm_campaign": "VARCHAR",
    },
    "billing_subscriptions": {
        "subscription_id": "VARCHAR",
        "billing_customer_id": "VARCHAR",
        "company_domain": "VARCHAR",
        "plan": "VARCHAR",
        "mrr": "DOUBLE",
        "currency": "VARCHAR",
        "interval": "VARCHAR",
        "status": "VARCHAR",
        "started_at": "DATE",
        "canceled_at": "DATE",
    },
}


def connect(settings: dict) -> duckdb.DuckDBPyConnection:
    """Open an in-memory DuckDB, add the helper macros, and load the config lookup tables."""
    con = duckdb.connect()
    con.execute((SQL_DIR / "macros.sql").read_text(encoding="utf-8"))
    load_config_tables(con, settings)
    return con


def load_config_tables(con: duckdb.DuckDBPyConnection, settings: dict) -> None:
    """Turn the YAML config into small tables (stages, UTM rules, FX rates) so SQL can join them."""
    con.execute(
        "CREATE TABLE stages (stage_id VARCHAR, label VARCHAR, probability DOUBLE,"
        " stage_order INTEGER, is_closed BOOLEAN)"
    )
    for order, stage in enumerate(settings["pipeline"]["stages"], start=1):
        con.execute(
            "INSERT INTO stages VALUES (?, ?, ?, ?, ?)",
            [stage["id"], stage["label"], stage["probability"], order, stage.get("closed", False)],
        )

    con.execute("CREATE TABLE utm_canonical (kind VARCHAR, value VARCHAR)")
    con.execute("CREATE TABLE utm_aliases (kind VARCHAR, alias VARCHAR, canonical VARCHAR)")
    for kind, rules in settings["utm"].items():
        for value in rules["canonical"]:
            con.execute("INSERT INTO utm_canonical VALUES (?, ?)", [kind, value])
            # A canonical value typed in the wrong case ("Google") maps back to itself.
            con.execute("INSERT INTO utm_aliases VALUES (?, ?, ?)", [kind, value.lower(), value])
        for canonical, aliases in rules["aliases"].items():
            for alias in aliases:
                con.execute(
                    "INSERT INTO utm_aliases VALUES (?, ?, ?)", [kind, alias.lower(), canonical]
                )

    con.execute("CREATE TABLE fx_rates (currency VARCHAR, usd_rate DOUBLE)")
    for currency, rate in settings["recon"]["fx_to_usd"].items():
        con.execute("INSERT INTO fx_rates VALUES (?, ?)", [currency, rate])


def load_csv_dir(con: duckdb.DuckDBPyConnection, data_dir: Path) -> None:
    """Load every <table>.csv in data_dir with the column types from SCHEMA (empty cell = NULL)."""
    for table, columns in SCHEMA.items():
        path = Path(data_dir) / f"{table}.csv"
        column_spec = ", ".join(f"'{name}': '{kind}'" for name, kind in columns.items())
        con.execute(
            f"CREATE TABLE {table} AS SELECT * FROM read_csv("
            f"'{path.as_posix()}', header = true, columns = {{{column_spec}}})"
        )


def load_rows(con: duckdb.DuckDBPyConnection, tables: dict[str, list[dict]]) -> None:
    """Create every input table from Python rows (used by tests); tables not given start empty."""
    for table, columns in SCHEMA.items():
        column_defs = ", ".join(f"{name} {kind}" for name, kind in columns.items())
        con.execute(f"CREATE TABLE {table} ({column_defs})")
        placeholders = ", ".join("?" for _ in columns)
        for row in tables.get(table, []):
            values = [row.get(name) for name in columns]
            con.execute(f"INSERT INTO {table} VALUES ({placeholders})", values)


def run_sql(con: duckdb.DuckDBPyConnection, relative_path: str, **params) -> list[dict]:
    """Run one file from sql/ with named $parameters and return the rows as dictionaries."""
    query = (SQL_DIR / relative_path).read_text(encoding="utf-8")
    cursor = con.execute(query, params) if params else con.execute(query)
    names = [column[0] for column in cursor.description]
    return [dict(zip(names, row, strict=True)) for row in cursor.fetchall()]


def write_csv(path: Path, rows: list[dict], columns: list[str]) -> None:
    """Write rows to a CSV file with a fixed column order; None becomes an empty cell."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow(
                {key: ("" if row.get(key) is None else row.get(key)) for key in columns}
            )
