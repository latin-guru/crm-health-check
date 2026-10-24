"""Unit tests for the normalization macros in sql/macros.sql."""

import pytest

from chc.config import load_settings
from chc.db import connect


@pytest.fixture(scope="module")
def con():
    """A connection with the macros loaded and no data."""
    return connect(load_settings())


def scalar(con, expression, *args):
    """Evaluate one SQL expression and return its value."""
    return con.execute(f"SELECT {expression}", list(args)).fetchone()[0]


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("Ana.Ruiz@Shop.example", "ana.ruiz@shop.example"),
        ("  ana.ruiz@shop.example ", "ana.ruiz@shop.example"),
        ("ana.ruiz+promo@shop.example", "ana.ruiz@shop.example"),
        (None, None),
    ],
)
def test_normalize_email(con, raw, expected):
    assert scalar(con, "normalize_email(?)", raw) == expected


@pytest.mark.parametrize(
    ("raw", "valid"),
    [
        ("ana.ruiz@shop.example", True),
        ("ANA@SHOP.EXAMPLE", True),
        ("ana.ruiz@", False),
        ("ana.ruiz.shop.example", False),
        ("ana ruiz@shop.example", False),
        ("ana@@shop.example", False),
        ("ana@shop", False),
        (None, False),
    ],
)
def test_is_valid_email(con, raw, valid):
    assert scalar(con, "is_valid_email(?)", raw) is valid


@pytest.mark.parametrize(
    "raw",
    [
        "shop.example",
        "SHOP.example",
        "www.shop.example",
        "https://www.Shop.example/",
        "http://shop.example/pricing",
        " shop.example/ ",
    ],
)
def test_normalize_domain(con, raw):
    assert scalar(con, "normalize_domain(?)", raw) == "shop.example"


@pytest.mark.parametrize(
    ("amount", "term", "expected"),
    [(12000, 12, 12000), (24000, 24, 12000), (36000, 36, 12000), (6000, None, 6000)],
)
def test_annualize_deal(con, amount, term, expected):
    assert scalar(con, "annualize_deal(?, ?)", amount, term) == pytest.approx(expected)


@pytest.mark.parametrize(
    ("price", "interval", "expected"),
    [(100, "month", 1200), (1200, "year", 1200), (100, "Month", 1200), (100, "week", None)],
)
def test_annualize_billing(con, price, interval, expected):
    assert scalar(con, "annualize_billing(?, ?)", price, interval) == expected


def test_utm_aliases_are_loaded_from_config(con):
    rows = con.execute(
        "SELECT alias, canonical FROM utm_aliases"
        " WHERE kind = 'source' AND alias IN ('fb', 'google')"
    ).fetchall()
    assert dict(rows) == {"fb": "facebook", "google": "google"}


def test_fx_rates_are_loaded_from_config(con):
    assert scalar(con, "usd_rate FROM fx_rates WHERE currency = 'CAD'") == pytest.approx(0.73)
