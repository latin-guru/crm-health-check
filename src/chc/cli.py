"""Command line: `chc generate`, `chc audit` and `chc build`."""

from pathlib import Path

import typer

from chc.audit import run_checks, severity_counts, write_fix_lists
from chc.config import load_settings
from chc.db import connect, load_csv_dir
from chc.generate import generate as generate_data
from chc.paths import DEFAULT_DATA_DIR, DEFAULT_SITE_DIR

app = typer.Typer(
    help="CRM Health Check: audit a HubSpot-style CRM export (fictional data).",
    no_args_is_help=True,
)


@app.command()
def generate(
    seed: int = typer.Option(42, help="Random seed; the same seed always gives the same data."),
    out: Path = typer.Option(DEFAULT_DATA_DIR, help="Folder to write the CSV exports to."),
) -> None:
    """Write fake CRM + billing CSVs with planted defects and a defects manifest."""
    manifest = generate_data(seed, out, load_settings())
    typer.echo(f"Wrote fake data to {out} ({len(manifest['defects'])} planted defects).")


@app.command()
def audit(
    data: Path = typer.Option(DEFAULT_DATA_DIR, help="Folder with the CSV exports."),
    out: Path = typer.Option(Path("exports"), help="Folder to write the fix lists to."),
) -> None:
    """Run the hygiene checks, print a summary and write the fix-list CSVs."""
    settings = load_settings()
    con = connect(settings)
    load_csv_dir(con, data)
    issues = run_checks(con, settings)
    for severity, count in severity_counts(issues).items():
        typer.echo(f"{severity:>6}: {count} issues")
    for name, path in write_fix_lists(issues, out).items():
        typer.echo(f"wrote {name}: {path}")


@app.command()
def build(
    data: Path = typer.Option(DEFAULT_DATA_DIR, help="Folder with the CSV exports."),
    site: Path = typer.Option(DEFAULT_SITE_DIR, help="Folder to write the static site to."),
) -> None:
    """Build the static report site (all pages, charts and CSV downloads)."""
    from chc.report import build_site

    pages = build_site(data, site, load_settings())
    typer.echo(f"Built {len(pages)} pages in {site}.")
