"""Every reconciliation status, plus ARR and currency normalization, on hand-built accounts."""

from datetime import date

import pytest

from chc.metrics import reconciliation_report, waterfall_steps
from tests.conftest import company, contact, deal, subscription

WON = {"stage": "closedwon", "close_date": date(2026, 1, 1)}


def account(n, amount=12000.0, term=12, currency="USD"):
    """A company with one contact and one closed-won deal: ARR = amount x 12 / term."""
    domain = f"brand{n}.example"
    return (
        company(f"co{n}", domain),
        contact(f"c{n}", f"a@{domain}", company_id=f"co{n}", lifecycle_stage="customer"),
        deal(
            f"d{n}",
            company_id=f"co{n}",
            primary_contact_id=f"c{n}",
            amount=amount,
            term_months=term,
            currency=currency,
            **WON,
        ),
    )


def recon_for(make_db, accounts, subscriptions):
    """Build the tables and return {domain: row} from the reconciliation."""
    companies, contacts, deals = (list(part) for part in zip(*accounts, strict=True))
    con = make_db(
        companies=companies, contacts=contacts, deals=deals, billing_subscriptions=subscriptions
    )
    report = reconciliation_report(con, tolerance_usd=1.0)
    return report, {row["domain"]: row for row in report["rows"]}


def test_matched_after_term_and_interval_normalization(make_db):
    # 24-month deal worth 24,000 = 12,000/yr; yearly plan at 12,000 = 12,000/yr.
    _, rows = recon_for(
        make_db,
        [account(1, 24000.0, 24)],
        [subscription("s1", "https://www.Brand1.example/", mrr=12000.0, interval="year")],
    )
    assert rows["brand1.example"]["status"] == "Matched"
    assert rows["brand1.example"]["delta"] == 0


def test_matched_in_non_usd_currency(make_db):
    _, rows = recon_for(
        make_db,
        [account(1, currency="CAD")],
        [subscription("s1", "brand1.example", currency="CAD")],
    )
    assert rows["brand1.example"]["status"] == "Matched"
    assert rows["brand1.example"]["crm_arr"] == pytest.approx(12000 * 0.73)


def test_crm_only_without_subscription(make_db):
    _, rows = recon_for(make_db, [account(1)], [])
    assert rows["brand1.example"]["status"] == "CRM-only"
    assert "no subscription" in rows["brand1.example"]["explanation"]


def test_crm_only_with_canceled_subscription(make_db):
    _, rows = recon_for(
        make_db,
        [account(1)],
        [subscription("s1", "brand1.example", status="canceled", canceled_at=date(2026, 9, 10))],
    )
    assert rows["brand1.example"]["status"] == "CRM-only"
    assert "2026-09-10" in rows["brand1.example"]["explanation"]


def test_billing_only_unknown_domain_and_known_company(make_db):
    lost = account(2)
    lost[2]["stage"] = "closedlost"
    _, rows = recon_for(
        make_db,
        [account(1), lost],
        [
            subscription("s1", "brand1.example"),
            subscription("s2", "brand2.example"),
            subscription("s3", "selfserve.example"),
        ],
    )
    assert rows["selfserve.example"]["status"] == "Billing-only"
    assert rows["selfserve.example"]["company_id"] is None
    assert "not in the CRM" in rows["selfserve.example"]["explanation"]
    assert rows["brand2.example"]["status"] == "Billing-only"
    assert "no closed-won deal" in rows["brand2.example"]["explanation"]


def test_amount_mismatch(make_db):
    _, rows = recon_for(make_db, [account(1)], [subscription("s1", "brand1.example", mrr=850.0)])
    row = rows["brand1.example"]
    assert row["status"] == "Amount mismatch"
    assert row["delta"] == pytest.approx(-1800)
    assert "lower" in row["explanation"]


def test_amount_mismatch_from_missing_deal_amount(make_db):
    _, rows = recon_for(make_db, [account(1, amount=None)], [subscription("s1", "brand1.example")])
    assert rows["brand1.example"]["status"] == "Amount mismatch"
    assert "H07" in rows["brand1.example"]["explanation"]


def test_term_mismatch_both_directions(make_db):
    _, rows = recon_for(
        make_db,
        [account(1, amount=1000.0), account(2)],
        [
            subscription("s1", "brand1.example"),  # CRM has the monthly price as the amount
            subscription("s2", "brand2.example", interval="year"),
        ],  # yearly plan, monthly price
    )
    assert rows["brand1.example"]["status"] == "Term mismatch"
    assert "monthly price" in rows["brand1.example"]["explanation"]
    assert rows["brand2.example"]["status"] == "Term mismatch"
    assert "yearly interval" in rows["brand2.example"]["explanation"]


def test_currency_mismatch(make_db):
    _, rows = recon_for(
        make_db, [account(1)], [subscription("s1", "brand1.example", currency="EUR")]
    )
    row = rows["brand1.example"]
    assert row["status"] == "Currency mismatch"
    assert "USD" in row["explanation"] and "EUR" in row["explanation"]


def test_totals_summary_and_waterfall_add_up(make_db):
    report, _ = recon_for(
        make_db,
        [account(1), account(2)],
        [subscription("s1", "brand1.example"), subscription("s2", "brand2.example", mrr=1100.0)],
    )
    assert report["gap"] == pytest.approx(report["billing_total"] - report["crm_total"])
    steps = report["waterfall"]
    assert steps[0]["end"] == report["crm_total"]
    assert steps[-2]["end"] == pytest.approx(report["billing_total"])
    assert steps[-1] == {
        "label": "Billing ARR",
        "start": 0.0,
        "end": report["billing_total"],
        "kind": "total",
    }


def test_waterfall_skips_empty_categories_and_marks_direction():
    summary = [
        {"status": "Matched", "accounts": 5, "delta": 0.0},
        {"status": "CRM-only", "accounts": 1, "delta": -500.0},
        {"status": "Billing-only", "accounts": 0, "delta": 0.0},
        {"status": "Amount mismatch", "accounts": 2, "delta": 200.0},
    ]
    steps = waterfall_steps(1000.0, summary, 700.0)
    assert [s["label"] for s in steps] == ["CRM ARR", "CRM-only", "Amount mismatch", "Billing ARR"]
    assert steps[1]["kind"] == "decrease" and steps[2]["kind"] == "increase"
    assert steps[2]["end"] == 700.0
