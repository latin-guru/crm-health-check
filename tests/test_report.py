"""Build smoke test: every page exists, every metric carries "Sample data", downloads exist."""

import re

import pytest

from chc.report import PAGES, build_site, money

METRIC_BLOCK = re.compile(r'<figure class="metric" data-metric="[^"]+">(.*?)</figure>', re.S)


@pytest.fixture(scope="module")
def site(generated, settings, tmp_path_factory):
    """Build the site once from the generated demo data."""
    site_dir = tmp_path_factory.mktemp("site")
    build_site(generated[0], site_dir, settings)
    return site_dir


def test_every_page_is_built(site):
    for href in PAGES:
        html = (site / href).read_text()
        assert "<title>" in html
        assert "Bayline Loop" in html


@pytest.mark.parametrize("href", list(PAGES))
def test_every_metric_has_sample_data_label(site, href):
    html = (site / href).read_text()
    blocks = METRIC_BLOCK.findall(html)
    assert len(blocks) == html.count("data-metric=")
    for block in blocks:
        assert "Sample data" in block


def test_metric_pages_have_metrics(site):
    for href in PAGES:
        if href != "methodology.html":
            assert "data-metric=" in (site / href).read_text(), href


def test_downloads_and_assets_exist(site):
    for name in (
        "fixes.csv",
        "merge_candidates.csv",
        "needs_owner_review.csv",
        "issues.csv",
        "reconciliation.csv",
    ):
        assert (site / "downloads" / name).stat().st_size > 0
    assert (site / "assets" / "style.css").exists()
    assert (site / "assets" / "app.js").exists()


def test_chart_js_is_pinned_with_integrity(site):
    html = (site / "index.html").read_text()
    assert re.search(r'chart\.js@\d+\.\d+\.\d+/dist/chart\.umd\.min\.js" integrity="sha384-', html)


def test_methodology_links_to_every_sql_file(site):
    html = (site / "methodology.html").read_text()
    for path in (
        "checks/h01_duplicate_contacts.sql",
        "checks/h09_utm_governance.sql",
        "pipeline/forecast_by_team.sql",
        "attribution/first_last_touch.sql",
        "recon/reconciliation.sql",
        "macros.sql",
    ):
        assert f"/blob/main/sql/{path}" in html


def test_money_format():
    assert money(1234.5) == "$1,234"
    assert money(-50) == "-$50"
    assert money(None) == "-"
