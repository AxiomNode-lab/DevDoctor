"""Public console entry point."""

from __future__ import annotations


def main() -> None:
    """Run DevDoctor with the extra command groups registered."""

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
    app()
