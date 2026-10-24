"""Save README screenshots of the built site (Overview, Data Health, Reconciliation).

Usage: python scripts/screenshots.py [--site site] [--out docs/screenshots]
Needs Playwright's Chromium (`playwright install chromium`). CI runs this after `chc build`.
"""

import argparse
from pathlib import Path

from playwright.sync_api import sync_playwright

CHART_JS_URL = "https://cdn.jsdelivr.net/npm/chart.js@4.5.1/dist/chart.umd.min.js"

SHOTS = {
    "overview.png": "index.html",
    "data-health.png": "data-health.html",
    "reconciliation.png": "reconciliation.html",
}


def main() -> None:
    """Open each page in headless Chromium at desktop width and save a screenshot."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--site", type=Path, default=Path("site"))
    parser.add_argument("--out", type=Path, default=Path("docs/screenshots"))
    parser.add_argument(
        "--chartjs-file",
        type=Path,
        help="Serve Chart.js from this local copy instead of the CDN (for offline machines).",
    )
    args = parser.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch()
        page = browser.new_page(viewport={"width": 1280, "height": 1500}, color_scheme="light")
        if args.chartjs_file:
            body = args.chartjs_file.read_bytes()
            page.route(
                CHART_JS_URL,
                lambda route: route.fulfill(body=body, content_type="application/javascript"),
            )
        for filename, page_name in SHOTS.items():
            page.goto((args.site / page_name).resolve().as_uri())
            page.wait_for_load_state("networkidle")
            page.screenshot(path=str(args.out / filename))
            print(f"saved {args.out / filename}")
        browser.close()


if __name__ == "__main__":
    main()
