"""Load the YAML files in config/ into one settings dictionary."""

from pathlib import Path

import yaml

from chc.paths import CONFIG_DIR


def load_yaml(name: str, config_dir: Path = CONFIG_DIR) -> dict:
    """Read one YAML file from config/ (for example "pipeline.yml") and return it as a dict."""
    with open(config_dir / name, encoding="utf-8") as handle:
        return yaml.safe_load(handle)


def load_settings(config_dir: Path = CONFIG_DIR) -> dict:
    """Read every config file once so the rest of the code gets settings from a single place."""
    report = load_yaml("report.yml", config_dir)
    pipeline = load_yaml("pipeline.yml", config_dir)
    recon = load_yaml("reconciliation.yml", config_dir)
    return {
        "report": report,
        "pipeline": pipeline,
        "utm": load_yaml("utm_governance.yml", config_dir),
        "recon": recon,
        "checks": load_yaml("checks.yml", config_dir)["checks"],
        # Values that SQL files receive as $parameters.
        "params": {
            "as_of": report["as_of"],
            "stale_days": pipeline["stale_days"],
            "tolerance_usd": recon["tolerance_usd"],
        },
    }
