"""Run the hygiene checks and turn their results into issues, scores and fix-list exports."""

from pathlib import Path

import duckdb

from chc.db import run_sql, write_csv

SEVERITY_ORDER = {"high": 0, "medium": 1, "low": 2}

ISSUE_COLUMNS = [
    "check_id",
    "severity",
    "object",
    "record_id",
    "field",
    "current_value",
    "suggested_value",
    "auto_fixable",
]

# The three objects that get a health score, and the table/ID column behind each one.
SCORED_OBJECTS = {
    "contact": ("contacts", "contact_id"),
    "company": ("companies", "company_id"),
    "deal": ("deals", "deal_id"),
}

MERGE_CHECKS = {"H01", "H02"}


def run_checks(con: duckdb.DuckDBPyConnection, settings: dict) -> list[dict]:
    """Run every check in config/checks.yml and return one issue dict per flagged field."""
    issues = []
    for check in settings["checks"]:
        params = {name: settings["params"][name] for name in check.get("params", [])}
        for row in run_sql(con, f"checks/{check['sql']}", **params):
            issues.append({"check_id": check["id"], "severity": check["severity"], **row})
    return issues


def summarize_checks(issues: list[dict], settings: dict) -> list[dict]:
    """Return the check catalog with how many issues and records each check found."""
    summary = []
    for check in settings["checks"]:
        found = [issue for issue in issues if issue["check_id"] == check["id"]]
        summary.append(
            {
                **check,
                "issue_count": len(found),
                "record_count": len({(i["object"], i["record_id"]) for i in found}),
                "auto_fixable_count": sum(1 for i in found if i["auto_fixable"]),
                "issues": found,
            }
        )
    return summary


def top_fixes(check_summary: list[dict], limit: int = 5) -> list[dict]:
    """Pick the checks to fix first: most severe first, then the ones with the most issues."""
    with_issues = [check for check in check_summary if check["issue_count"] > 0]
    ranked = sorted(
        with_issues, key=lambda c: (SEVERITY_ORDER[c["severity"]], -c["issue_count"], c["id"])
    )
    return ranked[:limit]


def severity_counts(issues: list[dict]) -> dict[str, int]:
    """Count issues per severity, always returning high, medium and low in that order."""
    counts = {severity: 0 for severity in SEVERITY_ORDER}
    for issue in issues:
        counts[issue["severity"]] += 1
    return counts


def health_scores(con: duckdb.DuckDBPyConnection, issues: list[dict]) -> list[dict]:
    """Health score per object = % of its records that pass every check (no issues at all)."""
    scores = []
    for object_name, (table, _id_column) in SCORED_OBJECTS.items():
        total = con.execute(f"SELECT count(*) FROM {table}").fetchone()[0]
        flagged = {i["record_id"] for i in issues if i["object"] == object_name}
        passing = total - len(flagged)
        scores.append(
            {
                "object": object_name,
                "label": table,
                "total": total,
                "flagged": len(flagged),
                "score": round(100.0 * passing / total, 1) if total else 100.0,
            }
        )
    return scores


def split_fix_lists(issues: list[dict]) -> dict[str, list[dict]]:
    """Sort issues into the three fix lists: safe auto-fixes, merge reviews, and owner reviews."""
    fixes, merges, review = [], [], []
    for issue in issues:
        if issue["check_id"] in MERGE_CHECKS:
            merges.append(
                {
                    "check_id": issue["check_id"],
                    "object": issue["object"],
                    "duplicate_record_id": issue["record_id"],
                    "keep_record_id": issue["suggested_value"],
                    "matched_value": issue["current_value"],
                }
            )
        elif issue["auto_fixable"] and issue["suggested_value"] is not None:
            fixes.append(
                {
                    "Record ID": issue["record_id"],
                    "Object": issue["object"],
                    "Property": issue["field"],
                    "New Value": issue["suggested_value"],
                }
            )
        else:
            review.append(issue)
    return {"fixes": fixes, "merge_candidates": merges, "needs_owner_review": review}


def write_fix_lists(issues: list[dict], out_dir: Path) -> dict[str, Path]:
    """Write fixes.csv, merge_candidates.csv, needs_owner_review.csv and issues.csv to out_dir."""
    lists = split_fix_lists(issues)
    paths = {
        "fixes": out_dir / "fixes.csv",
        "merge_candidates": out_dir / "merge_candidates.csv",
        "needs_owner_review": out_dir / "needs_owner_review.csv",
        "issues": out_dir / "issues.csv",
    }
    write_csv(paths["fixes"], lists["fixes"], ["Record ID", "Object", "Property", "New Value"])
    write_csv(
        paths["merge_candidates"],
        lists["merge_candidates"],
        ["check_id", "object", "duplicate_record_id", "keep_record_id", "matched_value"],
    )
    write_csv(paths["needs_owner_review"], lists["needs_owner_review"], ISSUE_COLUMNS)
    write_csv(paths["issues"], issues, ISSUE_COLUMNS)
    return paths
