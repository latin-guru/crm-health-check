"""The three CLI commands run end to end."""

from typer.testing import CliRunner

from chc.cli import app

runner = CliRunner()


def test_generate_audit_build(tmp_path):
    data, exports, site = tmp_path / "data", tmp_path / "exports", tmp_path / "site"

    result = runner.invoke(app, ["generate", "--seed", "42", "--out", str(data)])
    assert result.exit_code == 0, result.output
    assert (data / "defects_manifest.json").exists()

    result = runner.invoke(app, ["audit", "--data", str(data), "--out", str(exports)])
    assert result.exit_code == 0, result.output
    assert "high:" in result.output
    assert (exports / "fixes.csv").exists()

    result = runner.invoke(app, ["build", "--data", str(data), "--site", str(site)])
    assert result.exit_code == 0, result.output
    assert (site / "index.html").exists()
