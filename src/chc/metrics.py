"""Reporting metrics: pipeline and forecast, attribution, and CRM-vs-billing reconciliation.

The math lives in sql/; these functions only run the SQL and shape the rows for the report.
"""

import duckdb

from chc.db import run_sql

RECON_STATUSES = [
    "Matched",
    "CRM-only",
    "Billing-only",
    "Amount mismatch",
    "Term mismatch",
    "Currency mismatch",
]


def pipeline_report(con: duckdb.DuckDBPyConnection) -> dict:
    """Open pipeline by stage/owner/team, weighted forecast, conversion and days in stage."""
    by_stage = run_sql(con, "pipeline/open_pipeline_by_stage.sql")
    conversion = [row for row in run_sql(con, "pipeline/stage_conversion.sql") if row["next_stage"]]
    return {
        "by_stage": by_stage,
        "by_owner": run_sql(con, "pipeline/open_pipeline_by_owner.sql"),
        "by_team": run_sql(con, "pipeline/forecast_by_team.sql"),
        "conversion": conversion,
        "days_in_stage": run_sql(con, "pipeline/days_in_stage.sql"),
        "total_open_usd": sum(row["amount_usd"] for row in by_stage),
        "total_weighted_usd": sum(row["weighted_usd"] for row in by_stage),
        "open_deals": sum(row["deals"] for row in by_stage),
    }


def attribution_report(con: duckdb.DuckDBPyConnection) -> dict:
    """First- vs last-touch source counts for won deals, before and after UTM normalization."""
    rows = run_sql(con, "attribution/first_last_touch.sql")
    before = [row for row in rows if row["view"] == "before"]
    after = [row for row in rows if row["view"] == "after"]
    return {
        "before": before,
        "after": after,
        "distinct_before": len(before),
        "distinct_after": len(after),
        "deals": sum(row["first_touch_deals"] for row in after),
    }


def reconciliation_report(con: duckdb.DuckDBPyConnection, tolerance_usd: float) -> dict:
    """Row-level recon plus totals, a count/delta summary per status, and waterfall steps."""
    rows = run_sql(con, "recon/reconciliation.sql", tolerance_usd=tolerance_usd)
    summary = []
    for status in RECON_STATUSES:
        matching = [row for row in rows if row["status"] == status]
        summary.append(
            {
                "status": status,
                "accounts": len(matching),
                "delta": round(sum(row["delta"] for row in matching), 2),
            }
        )
    crm_total = round(sum(row["crm_arr"] for row in rows), 2)
    billing_total = round(sum(row["billing_arr"] for row in rows), 2)
    return {
        "rows": rows,
        "summary": summary,
        "crm_total": crm_total,
        "billing_total": billing_total,
        "gap": round(billing_total - crm_total, 2),
        "waterfall": waterfall_steps(crm_total, summary, billing_total),
    }


def waterfall_steps(crm_total: float, summary: list[dict], billing_total: float) -> list[dict]:
    """Bars for a waterfall chart: start at CRM ARR, add each status's delta, end at billing.

    Each step has a start and end value; Chart.js draws it as a floating bar.
    """
    steps = [{"label": "CRM ARR", "start": 0.0, "end": crm_total, "kind": "total"}]
    running = crm_total
    for item in summary:
        # Matched accounts are within tolerance; skip them unless they still move the total.
        if item["accounts"] == 0 or abs(item["delta"]) < 0.01:
            continue
        end = round(running + item["delta"], 2)
        kind = "increase" if item["delta"] >= 0 else "decrease"
        steps.append({"label": item["status"], "start": running, "end": end, "kind": kind})
        running = end
    steps.append({"label": "Billing ARR", "start": 0.0, "end": billing_total, "kind": "total"})
    return steps
