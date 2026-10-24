"""Tests for turning issues into fix lists, scores and summaries."""

import csv

from chc.audit import (
    health_scores,
    run_checks,
    severity_counts,
    split_fix_lists,
    summarize_checks,
    top_fixes,
    write_fix_lists,
)
from tests.conftest import company, contact


def issue(check_id, record_id, auto_fixable, suggested="new", severity="medium", obj="contact"):
    """A minimal issue row."""
    return {
        "check_id": check_id,
        "severity": severity,
        "object": obj,
        "record_id": record_id,
        "field": "f",
        "current_value": "old",
        "suggested_value": suggested,
        "auto_fixable": auto_fixable,
    }


def test_split_fix_lists_routes_every_issue_once():
    issues = [
        issue("H01", "c2", False, suggested="c1"),
        issue("H09", "c3", True, suggested="facebook"),
        issue("H09", "c4", False, suggested=None),
        issue("H03", "c5", False, suggested=None),
    ]
    lists = split_fix_lists(issues)
    assert lists["merge_candidates"] == [
        {
            "check_id": "H01",
            "object": "contact",
            "duplicate_record_id": "c2",
            "keep_record_id": "c1",
            "matched_value": "old",
        }
    ]
    assert lists["fixes"] == [
        {"Record ID": "c3", "Object": "contact", "Property": "f", "New Value": "facebook"}
    ]
    assert [i["record_id"] for i in lists["needs_owner_review"]] == ["c4", "c5"]


def test_write_fix_lists_writes_hubspot_import_header(tmp_path):
    paths = write_fix_lists([issue("H09", "c3", True, suggested="facebook")], tmp_path)
    with open(paths["fixes"], newline="") as handle:
        rows = list(csv.reader(handle))
    assert rows == [
        ["Record ID", "Object", "Property", "New Value"],
        ["c3", "contact", "f", "facebook"],
    ]
    assert paths["merge_candidates"].read_text().startswith("check_id,object,duplicate_record_id")


def test_top_fixes_orders_by_severity_then_count(settings):
    issues = (
        [issue("H09", f"a{n}", True, severity="low") for n in range(9)]
        + [issue("H03", "b1", False, severity="medium")]
        + [issue("H07", f"c{n}", False, severity="high", obj="deal") for n in range(2)]
    )
    ranked = top_fixes(summarize_checks(issues, settings))
    assert [check["id"] for check in ranked] == ["H07", "H03", "H09"]


def test_severity_counts_always_has_three_levels():
    assert severity_counts([issue("H09", "a", True, severity="low")]) == {
        "high": 0,
        "medium": 0,
        "low": 1,
    }


def test_health_scores(make_db, settings):
    con = make_db(companies=[company()], contacts=[contact("c1"), contact("c2", None)])
    scores = {s["object"]: s for s in health_scores(con, run_checks(con, settings))}
    assert scores["contact"]["score"] == 50.0
    assert scores["company"]["score"] == 100.0
    assert scores["deal"] == {
        "object": "deal",
        "label": "deals",
        "total": 0,
        "flagged": 0,
        "score": 100.0,
    }
