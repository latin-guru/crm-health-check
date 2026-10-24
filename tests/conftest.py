"""Shared test helpers: build a tiny in-memory CRM from a few hand-written rows."""

from datetime import date, datetime

import pytest

from chc.config import load_settings
from chc.db import connect, load_rows

AS_OF = date(2026, 9, 30)


def owner(owner_id="o1", active=True, team="SMB"):
    """An owner row; active by default."""
    return {"owner_id": owner_id, "name": f"Owner {owner_id}", "team": team, "active": active}


def company(company_id="co1", domain="shop.example", owner_id="o1", created_at=None):
    """A clean company row."""
    return {
        "company_id": company_id,
        "name": f"Company {company_id}",
        "domain": domain,
        "industry": "Apparel",
        "team": "SMB",
        "owner_id": owner_id,
        "created_at": created_at or datetime(2025, 1, 1),
    }


def contact(contact_id="c1", email="ana.ruiz@shop.example", company_id="co1", **overrides):
    """A clean contact row; pass keyword overrides to plant a problem."""
    row = {
        "contact_id": contact_id,
        "first_name": "Ana",
        "last_name": "Ruiz",
        "email": email,
        "company_id": company_id,
        "lifecycle_stage": "lead",
        "owner_id": "o1",
        "created_at": datetime(2025, 2, 1),
        "original_source": "PAID_SEARCH",
        "utm_source": "google",
        "utm_medium": "cpc",
        "utm_campaign": "spring-demo",
    }
    row.update(overrides)
    return row


def deal(deal_id="d1", stage="qualifiedtobuy", **overrides):
    """A clean, recently updated open deal; pass keyword overrides to plant a problem."""
    row = {
        "deal_id": deal_id,
        "name": f"Deal {deal_id}",
        "company_id": "co1",
        "primary_contact_id": "c1",
        "owner_id": "o1",
        "pipeline": "default",
        "stage": stage,
        "amount": 12000.0,
        "currency": "USD",
        "term_months": 12,
        "close_date": date(2026, 11, 15),
        "created_at": datetime(2026, 8, 1),
        "last_stage_change_at": datetime(2026, 9, 20),
    }
    row.update(overrides)
    return row


def subscription(subscription_id="sub1", domain="shop.example", **overrides):
    """An active monthly billing subscription worth 1,000 per month."""
    row = {
        "subscription_id": subscription_id,
        "billing_customer_id": f"cus_{subscription_id}",
        "company_domain": domain,
        "plan": "Growth",
        "mrr": 1000.0,
        "currency": "USD",
        "interval": "month",
        "status": "active",
        "started_at": date(2026, 1, 1),
        "canceled_at": None,
    }
    row.update(overrides)
    return row


@pytest.fixture(scope="session")
def settings():
    """The real config files, loaded once."""
    return load_settings()


@pytest.fixture
def make_db(settings):
    """Return a function that builds a DuckDB connection from table rows."""

    def build(**tables):
        tables.setdefault("owners", [owner()])
        con = connect(settings)
        load_rows(con, tables)
        return con

    return build


@pytest.fixture(scope="session")
def generated(tmp_path_factory, settings):
    """Generate the seed-42 demo data once and return (data_dir, manifest)."""
    from chc.generate import generate

    data_dir = tmp_path_factory.mktemp("data")
    manifest = generate(42, data_dir, settings)
    return data_dir, manifest


@pytest.fixture(scope="session")
def generated_db(generated, settings):
    """A connection loaded with the generated CSVs."""
    from chc.db import load_csv_dir

    con = connect(settings)
    load_csv_dir(con, generated[0])
    return con
