"""One positive and one negative case for every hygiene check, using tiny hand-built tables."""

from datetime import date, datetime

from chc.audit import run_checks
from tests.conftest import company, contact, deal, owner


def found(con, settings, check_id):
    """Run all checks and return the (record_id, field) pairs flagged by one check."""
    return {
        (issue["record_id"], issue["field"])
        for issue in run_checks(con, settings)
        if issue["check_id"] == check_id
    }


def issue_for(con, settings, check_id, record_id):
    """Return the single issue a check raised for one record."""
    matches = [
        i
        for i in run_checks(con, settings)
        if i["check_id"] == check_id and i["record_id"] == record_id
    ]
    assert len(matches) == 1
    return matches[0]


def test_clean_data_has_no_issues(make_db, settings):
    con = make_db(companies=[company()], contacts=[contact()], deals=[deal()])
    assert run_checks(con, settings) == []


# H01 duplicate contacts -------------------------------------------------------------


def test_h01_flags_newer_contact_with_same_normalized_email(make_db, settings):
    con = make_db(
        companies=[company()],
        contacts=[
            contact("c1", "ana.ruiz@shop.example"),
            contact("c2", " Ana.Ruiz+promo@Shop.example ", created_at=datetime(2025, 6, 1)),
        ],
    )
    issue = issue_for(con, settings, "H01", "c2")
    assert issue["suggested_value"] == "c1"
    assert issue["auto_fixable"] is False


def test_h01_ignores_different_emails(make_db, settings):
    con = make_db(
        companies=[company()],
        contacts=[contact("c1", "ana.ruiz@shop.example"), contact("c2", "ana.ruiz@other.example")],
    )
    assert found(con, settings, "H01") == set()


# H02 duplicate companies ------------------------------------------------------------


def test_h02_flags_newer_company_with_same_normalized_domain(make_db, settings):
    con = make_db(
        companies=[
            company("co1", "shop.example"),
            company("co2", "https://www.Shop.example/", created_at=datetime(2025, 5, 1)),
        ]
    )
    issue = issue_for(con, settings, "H02", "co2")
    assert issue["suggested_value"] == "co1"


def test_h02_ignores_different_domains(make_db, settings):
    con = make_db(companies=[company("co1", "shop.example"), company("co2", "shop2.example")])
    assert found(con, settings, "H02") == set()


# H03 missing or invalid email -------------------------------------------------------


def test_h03_flags_missing_and_invalid_emails(make_db, settings):
    con = make_db(
        companies=[company()],
        contacts=[
            contact("c1", None),
            contact("c2", "ana.ruiz@"),
            contact("c3", "ana ruiz@shop.example"),
            contact("c4", "ana.ruiz@shop"),
        ],
    )
    assert {record for record, _ in found(con, settings, "H03")} == {"c1", "c2", "c3", "c4"}


def test_h03_accepts_valid_email(make_db, settings):
    con = make_db(companies=[company()], contacts=[contact("c1", "Ana.Ruiz@Shop.example")])
    assert found(con, settings, "H03") == set()


# H04 lifecycle stage ----------------------------------------------------------------


def test_h04_fills_missing_stage_from_deals(make_db, settings):
    con = make_db(
        companies=[company()],
        contacts=[contact("c1", lifecycle_stage=None)],
        deals=[deal(stage="closedwon", close_date=date(2026, 3, 1))],
    )
    issue = issue_for(con, settings, "H04", "c1")
    assert issue["suggested_value"] == "customer"
    assert issue["auto_fixable"] is True


def test_h04_suggests_opportunity_or_lead_for_missing_stage(make_db, settings):
    con = make_db(
        companies=[company("co1"), company("co2", "shop2.example")],
        contacts=[
            contact("c1", lifecycle_stage=None),
            contact("c2", "b@shop2.example", company_id="co2", lifecycle_stage=None),
        ],
        deals=[deal()],
    )
    assert issue_for(con, settings, "H04", "c1")["suggested_value"] == "opportunity"
    assert issue_for(con, settings, "H04", "c2")["suggested_value"] == "lead"


def test_h04_flags_customer_without_won_deal_for_review(make_db, settings):
    con = make_db(companies=[company()], contacts=[contact("c1", lifecycle_stage="customer")])
    issue = issue_for(con, settings, "H04", "c1")
    assert issue["suggested_value"] is None
    assert issue["auto_fixable"] is False


def test_h04_accepts_customer_with_won_deal(make_db, settings):
    con = make_db(
        companies=[company()],
        contacts=[contact("c1", lifecycle_stage="customer")],
        deals=[deal(stage="closedwon", close_date=date(2026, 3, 1))],
    )
    assert found(con, settings, "H04") == set()


# H05 deal associations --------------------------------------------------------------


def test_h05_flags_missing_company_or_contact(make_db, settings):
    con = make_db(
        companies=[company()],
        contacts=[contact()],
        deals=[
            deal("d1", company_id=None),
            deal("d2", primary_contact_id=None),
            deal("d3", company_id=None, primary_contact_id=None),
        ],
    )
    assert found(con, settings, "H05") == {
        ("d1", "company_id"),
        ("d2", "primary_contact_id"),
        ("d3", "company_id, primary_contact_id"),
    }


def test_h05_accepts_fully_associated_deal(make_db, settings):
    con = make_db(companies=[company()], contacts=[contact()], deals=[deal()])
    assert found(con, settings, "H05") == set()


# H06 stale open deals ---------------------------------------------------------------


def test_h06_flags_past_close_date_and_old_stage_change(make_db, settings):
    con = make_db(
        companies=[company()],
        contacts=[contact()],
        deals=[
            deal("d1", close_date=date(2026, 9, 1)),
            deal("d2", last_stage_change_at=datetime(2026, 8, 1)),
        ],
    )
    assert found(con, settings, "H06") == {("d1", "close_date"), ("d2", "last_stage_change_at")}


def test_h06_ignores_fresh_and_closed_deals(make_db, settings):
    con = make_db(
        companies=[company()],
        contacts=[contact()],
        deals=[
            deal("d1"),
            deal("d2", stage="closedlost", close_date=date(2026, 1, 1)),
        ],
    )
    assert found(con, settings, "H06") == set()


# H07 closed-won incomplete ----------------------------------------------------------


def test_h07_flags_each_missing_field(make_db, settings):
    won = {"stage": "closedwon", "close_date": date(2026, 3, 1)}
    con = make_db(
        companies=[company()],
        contacts=[contact(lifecycle_stage="customer")],
        deals=[
            deal("d1", **{**won, "amount": None}),
            deal("d2", **{**won, "close_date": None}),
            deal("d3", **{**won, "term_months": None}),
        ],
    )
    assert found(con, settings, "H07") == {
        ("d1", "amount"),
        ("d2", "close_date"),
        ("d3", "term_months"),
    }


def test_h07_ignores_complete_won_and_open_deals(make_db, settings):
    con = make_db(
        companies=[company()],
        contacts=[contact(lifecycle_stage="customer")],
        deals=[deal("d1", stage="closedwon", close_date=date(2026, 3, 1)), deal("d2", amount=None)],
    )
    assert found(con, settings, "H07") == set()


# H08 owner --------------------------------------------------------------------------


def test_h08_flags_inactive_missing_and_unknown_owners(make_db, settings):
    con = make_db(
        owners=[owner("o1"), owner("o9", active=False)],
        companies=[company("co1"), company("co2", "shop2.example", owner_id="o9")],
        contacts=[contact("c1", owner_id="o9")],
        deals=[deal("d1", owner_id=None), deal("d2", owner_id="ghost")],
    )
    flagged = {(i["object"], i["record_id"]): i for i in run_checks(con, settings)}
    assert flagged[("contact", "c1")]["suggested_value"] == "o1"
    assert flagged[("deal", "d1")]["auto_fixable"] is True
    assert flagged[("deal", "d2")]["suggested_value"] == "o1"
    assert flagged[("company", "co2")]["auto_fixable"] is False


def test_h08_ignores_active_owners(make_db, settings):
    con = make_db(companies=[company()], contacts=[contact()], deals=[deal()])
    assert found(con, settings, "H08") == set()


# H09 UTM governance -----------------------------------------------------------------


def test_h09_maps_aliases_and_flags_unknown_values(make_db, settings):
    con = make_db(
        companies=[company()],
        contacts=[
            contact("c1", utm_source="FB"),
            contact("c2", "b@shop.example", utm_medium="Paid Social "),
            contact("c3", "c@shop.example", utm_source="Google"),
            contact("c4", "d@shop.example", utm_source="tiktok-test"),
        ],
    )
    issues = {(i["record_id"], i["field"]): i for i in run_checks(con, settings)}
    assert issues[("c1", "utm_source")]["suggested_value"] == "facebook"
    assert issues[("c3", "utm_source")]["suggested_value"] == "google"
    assert issues[("c4", "utm_source")]["auto_fixable"] is False
    assert issues[("c4", "utm_source")]["suggested_value"] is None
    assert ("c2", "utm_medium") in issues


def test_h09_accepts_canonical_and_empty_values(make_db, settings):
    con = make_db(
        companies=[company()],
        contacts=[contact("c1"), contact("c2", "b@shop.example", utm_source=None, utm_medium=None)],
    )
    assert found(con, settings, "H09") == set()
