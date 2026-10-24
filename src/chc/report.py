"""Build the static report site: run the audit and metrics, then render Jinja2 templates."""

import shutil
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape

from chc.audit import (
    health_scores,
    run_checks,
    severity_counts,
    split_fix_lists,
    summarize_checks,
    top_fixes,
    write_fix_lists,
)
from chc.db import connect, load_csv_dir, write_csv
from chc.metrics import attribution_report, pipeline_report, reconciliation_report
from chc.paths import TEMPLATES_DIR

# Output file -> (template, nav label). The order here is the order of the nav bar.
PAGES = {
    "index.html": ("overview.html", "Overview"),
    "data-health.html": ("data_health.html", "Data Health"),
    "fix-list.html": ("fix_list.html", "Fix List"),
    "pipeline.html": ("pipeline.html", "Pipeline & Forecast"),
    "attribution.html": ("attribution.html", "Attribution"),
    "reconciliation.html": ("reconciliation.html", "Reconciliation"),
    "methodology.html": ("methodology.html", "Methodology"),
}

RECON_COLUMNS = [
    "company_id",
    "company_name",
    "domain",
    "crm_arr",
    "billing_arr",
    "delta",
    "status",
    "explanation",
]


def money(value: float | None) -> str:
    """Format a number as whole US dollars, e.g. 1234.5 -> "$1,235" and -50 -> "-$50"."""
    if value is None:
        return "-"
    sign = "-" if value < 0 else ""
    return f"{sign}${abs(value):,.0f}"


def make_environment() -> Environment:
    """Jinja2 setup: templates from templates/, HTML auto-escaping, and the money filter."""
    env = Environment(
        loader=FileSystemLoader(TEMPLATES_DIR),
        autoescape=select_autoescape(["html"]),
        trim_blocks=True,
        lstrip_blocks=True,
    )
    env.filters["money"] = money
    return env


def collect_report_data(data_dir: Path, settings: dict) -> dict:
    """Load the CSVs once and compute everything the pages need."""
    con = connect(settings)
    load_csv_dir(con, data_dir)
    issues = run_checks(con, settings)
    checks = summarize_checks(issues, settings)
    fix_lists = split_fix_lists(issues)
    return {
        "issues": issues,
        "checks": checks,
        "top_fixes": top_fixes(checks),
        "severity": severity_counts(issues),
        "scores": health_scores(con, issues),
        "fix_counts": {name: len(rows) for name, rows in fix_lists.items()},
        "fix_lists": fix_lists,
        "pipeline": pipeline_report(con),
        "attribution": attribution_report(con),
        "recon": reconciliation_report(con, settings["params"]["tolerance_usd"]),
    }


def chart_specs(report: dict) -> dict:
    """Describe each chart as plain data; templates/assets/app.js turns it into a Chart.js chart.

    Colors are named by role (series-1, status-high, ...) and resolved from CSS variables,
    so light and dark mode each get their own validated colors.
    """
    pipeline, attribution, recon = report["pipeline"], report["attribution"], report["recon"]
    return {
        "severity": {
            "labels": ["High", "Medium", "Low"],
            "series": [
                {
                    "name": "Issues",
                    "values": list(report["severity"].values()),
                    "colors": ["status-high", "status-medium", "status-low"],
                }
            ],
        },
        "stage-funnel": {
            "horizontal": True,
            "money": True,
            "labels": [row["stage"] for row in pipeline["by_stage"]],
            "series": [
                {
                    "name": "Open amount",
                    "values": [row["amount_usd"] for row in pipeline["by_stage"]],
                    "color": "series-1",
                },
                {
                    "name": "Weighted",
                    "values": [row["weighted_usd"] for row in pipeline["by_stage"]],
                    "color": "series-2",
                },
            ],
        },
        "forecast-team": {
            "money": True,
            "labels": [row["team"] for row in pipeline["by_team"]],
            "series": [
                {
                    "name": "Open amount",
                    "values": [row["amount_usd"] for row in pipeline["by_team"]],
                    "color": "series-1",
                },
                {
                    "name": "Weighted forecast",
                    "values": [row["weighted_usd"] for row in pipeline["by_team"]],
                    "color": "series-2",
                },
            ],
        },
        "days-in-stage": {
            "labels": [row["stage"] for row in pipeline["days_in_stage"]],
            "series": [
                {
                    "name": "Average days",
                    "values": [row["avg_days"] for row in pipeline["days_in_stage"]],
                    "color": "series-1",
                }
            ],
        },
        "attribution-before": attribution_chart(attribution["before"]),
        "attribution-after": attribution_chart(attribution["after"]),
        "recon-waterfall": {
            "money": True,
            "floating": True,
            "min": waterfall_axis_min(recon["waterfall"]),
            "labels": [step["label"] for step in recon["waterfall"]],
            "series": [
                {
                    "name": "ARR (USD)",
                    "values": [[step["start"], step["end"]] for step in recon["waterfall"]],
                    "colors": [f"waterfall-{step['kind']}" for step in recon["waterfall"]],
                }
            ],
        },
    }


def waterfall_axis_min(steps: list[dict]) -> float:
    """Start the waterfall's value axis just below the lowest running total.

    The category deltas are small next to total ARR; starting at zero would flatten them.
    """
    values = [step["end"] for step in steps] + [
        step["start"] for step in steps if step["kind"] != "total"
    ]
    low, high = min(values), max(values)
    padding = max((high - low) * 0.5, 1000)
    return max(0, (low - padding) // 10000 * 10000)


def attribution_chart(rows: list[dict]) -> dict:
    """Horizontal grouped bars: first-touch and last-touch won deals per source."""
    return {
        "horizontal": True,
        "labels": [row["source"] for row in rows],
        "series": [
            {
                "name": "First touch",
                "values": [row["first_touch_deals"] for row in rows],
                "color": "series-1",
            },
            {
                "name": "Last touch",
                "values": [row["last_touch_deals"] for row in rows],
                "color": "series-2",
            },
        ],
    }


def build_site(data_dir: Path, site_dir: Path, settings: dict) -> list[Path]:
    """Write every page, the CSS/JS assets and the CSV downloads into site_dir."""
    site_dir = Path(site_dir)
    report = collect_report_data(Path(data_dir), settings)
    downloads = site_dir / "downloads"
    write_fix_lists(report["issues"], downloads)
    write_csv(downloads / "reconciliation.csv", report["recon"]["rows"], RECON_COLUMNS)
    shutil.copytree(TEMPLATES_DIR / "assets", site_dir / "assets", dirs_exist_ok=True)

    charts = chart_specs(report)
    env = make_environment()
    nav = [{"href": href, "label": label} for href, (_template, label) in PAGES.items()]
    written = []
    for href, (template, label) in PAGES.items():
        html = env.get_template(template).render(
            settings=settings,
            report=report,
            nav=nav,
            current=href,
            page_title=label,
            sql_url=f"{settings['report']['repo_url']}/blob/main/sql/",
            charts=charts,
        )
        path = site_dir / href
        path.write_text(html, encoding="utf-8")
        written.append(path)
    return written
