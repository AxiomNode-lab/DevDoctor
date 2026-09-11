"""Public console entry point."""

from __future__ import annotations

import typer

_APP: typer.Typer | None = None


def build_app() -> typer.Typer:
    """Return the console app with every command group registered, built once.

    This is exactly what the ``devdoctor`` command runs; tests use it too so
    the extra command groups and the release-safety wrappers are exercised.
    """

    global _APP
    if _APP is not None:
        return _APP

    from devdoctor.cli import app
    from devdoctor.hardening import register_hardening_commands
    from devdoctor.path_conflicts import register_path_conflict_command
    from devdoctor.privacy_hardening import apply_privacy_hardening
    from devdoctor.project_diagnostics import register_project_diagnostics_command
    from devdoctor.release_safety import apply_release_safety
    from devdoctor.repair_transactions import register_repair_transaction_commands

    apply_privacy_hardening()

    # Import after the shared diagnostic function has been privacy-hardened so
    # support_report binds the same normalized snapshot used by `diagnostics`.
    from devdoctor.support_report import register_support_report_command

    register_hardening_commands(app)
    register_path_conflict_command(app)
    register_repair_transaction_commands(app)
    register_project_diagnostics_command(app)
    register_support_report_command(app)
    apply_release_safety(app)
    _APP = app
    return app


def main() -> None:
    """Run DevDoctor."""

    build_app()()
