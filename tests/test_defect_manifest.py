"""The key test: on generated data, the checks find exactly the planted defects.

No misses (every planted defect is found) and no false positives (no clean record is
flagged). The same is true for reconciliation: planted accounts get the planted status and
every other account is Matched.
"""

import json

from chc.audit import run_checks
from chc.generate import generate
from chc.metrics import reconciliation_report


def test_every_planted_defect_is_found_and_nothing_else(generated, generated_db, settings):
    _data_dir, manifest = generated
    planted = {(d["check_id"], d["record_id"]) for d in manifest["defects"]}
    found = {(i["check_id"], i["record_id"]) for i in run_checks(generated_db, settings)}
    assert planted - found == set(), "missed planted defects"
    assert found - planted == set(), "flagged records that were clean"


def test_every_check_has_planted_defects(generated):
    _data_dir, manifest = generated
    checks_with_defects = {d["check_id"] for d in manifest["defects"]}
    assert checks_with_defects == {f"H0{n}" for n in range(1, 10)}


def test_reconciliation_statuses_match_the_manifest(generated, generated_db, settings):
    _data_dir, manifest = generated
    expected = {r["domain"]: r["expected_status"] for r in manifest["reconciliation"]}
    rows = reconciliation_report(generated_db, settings["params"]["tolerance_usd"])["rows"]
    actual = {row["domain"]: row["status"] for row in rows}
    assert set(expected) <= set(actual)
    for domain, status in actual.items():
        assert status == expected.get(domain, "Matched"), domain
    assert {
        "CRM-only",
        "Billing-only",
        "Amount mismatch",
        "Term mismatch",
        "Currency mismatch",
    } <= set(expected.values())


def test_generation_is_deterministic(generated, tmp_path, settings):
    data_dir, manifest = generated
    again = generate(42, tmp_path, settings)
    assert again == manifest
    for name in ("contacts.csv", "deals.csv", "billing_subscriptions.csv"):
        assert (tmp_path / name).read_text() == (data_dir / name).read_text()


def test_manifest_file_is_written(generated):
    data_dir, manifest = generated
    on_disk = json.loads((data_dir / "defects_manifest.json").read_text())
    assert on_disk == manifest
    assert on_disk["company"] == "Bayline Loop"


def test_data_volume_is_close_to_the_spec(generated_db):
    def count(table):
        return generated_db.execute(f"SELECT count(*) FROM {table}").fetchone()[0]

    assert 300 <= count("companies") <= 320
    assert 1100 <= count("contacts") <= 1300
    assert count("deals") == 500
    assert count("deal_stage_history") > count("deals")
    assert count("touchpoints") > 0
    assert count("billing_subscriptions") > 100
