"""Where the repo folders live, so every module finds sql/, config/ and templates/ the same way."""

from pathlib import Path

# src/chc/paths.py -> repo root is two folders up from src/chc.
ROOT = Path(__file__).resolve().parents[2]
SQL_DIR = ROOT / "sql"
CONFIG_DIR = ROOT / "config"
TEMPLATES_DIR = ROOT / "templates"
DEFAULT_DATA_DIR = ROOT / "data"
DEFAULT_SITE_DIR = ROOT / "site"
