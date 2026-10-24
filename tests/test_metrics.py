"""Pipeline, forecast and attribution metrics on hand-built deals and touchpoints."""

from datetime import datetime

import pytest

from chc.metrics import attribution_report, pipeline_report
from tests.conftest import company, contact, deal, owner


def history(deal_id, *steps):
    """Stage history rows from (stage, datetime) pairs in order."""
    rows, previous = [], None
    for stage, when in steps:
        rows.append(
            {"deal_id": deal_id, "from_stage": previous, "to_stage": stage, "changed_at": when}
        )
        previous = stage
    return rows


def test_pipeline_weighted_forecast_and_fx(make_db):
    con = make_db(
        owners=[owner("o1", team="SMB"), owner("o2", team="Mid-Market")],
        companies=[company()],
        contacts=[contact()],
        deals=[
            deal("d1", stage="qualifiedtobuy", amount=10000.0),  # 20% -> 2,000
            deal("d2", stage="contractsent", amount=10000.0, currency="CAD", owner_id="o2"),
            deal("d3", stage="closedwon", amount=99999.0),  # closed: not in pipeline
        ],
    )
    report = pipeline_report(con)
    by_stage = {row["stage"]: row for row in report["by_stage"]}
    assert by_stage["Qualified"]["weighted_usd"] == pytest.approx(2000)
    assert by_stage["Contract sent"]["amount_usd"] == pytest.approx(7300)
    assert by_stage["Contract sent"]["weighted_usd"] == pytest.approx(7300 * 0.8)
    assert by_stage["Discovery"]["deals"] == 0
    assert report["open_deals"] == 2
    assert report["total_weighted_usd"] == pytest.approx(2000 + 5840)
    teams = {row["team"]: row["weighted_usd"] for row in report["by_team"]}
    assert teams == pytest.approx({"SMB": 2000, "Mid-Market": 5840})


def test_unassigned_owner_in_pipeline(make_db):
    con = make_db(companies=[company()], contacts=[contact()], deals=[deal(owner_id=None)])
    report = pipeline_report(con)
    assert report["by_owner"][0]["owner"] == "Unassigned"
    assert report["by_team"][0]["team"] == "Unassigned"


def test_stage_conversion_and_days_in_stage(make_db):
    d1 = history(
        "d1",
        ("appointmentscheduled", datetime(2026, 1, 1)),
        ("qualifiedtobuy", datetime(2026, 1, 11)),
    )
    d2 = history(
        "d2",
        ("appointmentscheduled", datetime(2026, 2, 1)),
        ("qualifiedtobuy", datetime(2026, 2, 5)),
        ("closedlost", datetime(2026, 2, 9)),
    )
    d3 = history("d3", ("appointmentscheduled", datetime(2026, 3, 1)))
    con = make_db(
        companies=[company()],
        contacts=[contact()],
        deals=[
            deal("d1"),
            deal("d2", stage="closedlost"),
            deal("d3", stage="appointmentscheduled"),
        ],
        deal_stage_history=d1 + d2 + d3,
    )
    report = pipeline_report(con)
    conversion = {row["stage"]: row for row in report["conversion"]}
    assert conversion["Discovery"]["deals_reached"] == 3
    assert conversion["Discovery"]["next_reached"] == 2
    assert conversion["Discovery"]["conversion_pct"] == pytest.approx(66.7)
    days = {row["stage"]: row for row in report["days_in_stage"]}
    # Discovery: 10 days (d1) and 4 days (d2); d3 is still there, so it doesn't count yet.
    assert days["Discovery"]["avg_days"] == pytest.approx(7.0)
    assert days["Discovery"]["completed_visits"] == 2
    assert days["Qualified"]["avg_days"] == pytest.approx(4.0)


def touch(touchpoint_id, when, source, contact_id="c1"):
    """A touchpoint row for the attribution tests."""
    return {
        "touchpoint_id": touchpoint_id,
        "contact_id": contact_id,
        "occurred_at": when,
        "channel": "paid_social",
        "utm_source": source,
        "utm_medium": None,
        "utm_campaign": None,
    }


def test_first_and_last_touch_before_and_after_normalization(make_db):
    won = deal("d1", stage="closedwon", created_at=datetime(2026, 5, 1))
    con = make_db(
        companies=[company()],
        contacts=[contact()],
        deals=[won],
        touchpoints=[
            touch("t1", datetime(2026, 3, 1), "FB"),
            touch("t2", datetime(2026, 4, 1), "google"),
            touch("t3", datetime(2026, 4, 20), "Facebook"),
            touch("t4", datetime(2026, 6, 1), "linkedin"),  # after the deal opened: ignored
        ],
    )
    report = attribution_report(con)
    before = {
        (r["source"]): (r["first_touch_deals"], r["last_touch_deals"]) for r in report["before"]
    }
    after = {
        (r["source"]): (r["first_touch_deals"], r["last_touch_deals"]) for r in report["after"]
    }
    assert before == {"FB": (1, 0), "Facebook": (0, 1)}
    assert after == {"facebook": (1, 1)}
    assert report["distinct_before"] == 2 and report["distinct_after"] == 1
    assert report["deals"] == 1


def test_unknown_and_missing_utm_sources_stay_visible(make_db):
    con = make_db(
        companies=[company()],
        contacts=[contact()],
        deals=[deal("d1", stage="closedwon", created_at=datetime(2026, 5, 1))],
        touchpoints=[
            touch("t1", datetime(2026, 3, 1), "tiktok-test"),
            touch("t2", datetime(2026, 4, 1), None),
        ],
    )
    after = {r["source"] for r in attribution_report(con)["after"]}
    assert after == {"(unmapped) tiktok-test", "(no UTM)"}
