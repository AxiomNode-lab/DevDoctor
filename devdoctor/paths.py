"""Application paths managed through platformdirs."""

from __future__ import annotations

from pathlib import Path

from platformdirs import user_state_path


def state_dir() -> Path:
    """Return DevDoctor's per-user state directory."""

    return user_state_path(appname="devdoctor", appauthor=False, ensure_exists=True)


def latest_report_path() -> Path:
    """Return the path used for the optional latest JSON report cache."""

    return state_dir() / "latest-report.json"


def last_inventory_path() -> Path:
    """Return where the last full-scan snapshot is kept for `devdoctor diff`."""

    return state_dir() / "last-inventory.json"


def operation_log_path() -> Path:
    """Return the append-only command operation log path."""

    return state_dir() / "operations.log"
