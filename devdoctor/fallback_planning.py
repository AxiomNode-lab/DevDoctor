"""Conservative Nix fallback plans.

The fallback is applied by :func:`devdoctor.bootstrap.install_plan_for_spec`
itself once every other manager has declined. This module keeps the public
name earlier callers used; it no longer patches the planner.
"""

from __future__ import annotations

from collections.abc import Mapping

from devdoctor import bootstrap
from devdoctor.models import JsonValue


def nix_plan_for_spec(
    spec: bootstrap.ToolSpec,
    *,
    system: Mapping[str, JsonValue],
) -> bootstrap.InstallPlan | None:
    """Return a user-profile Nix plan only for explicitly validated package mappings."""

    return bootstrap._nix_fallback_plan(spec, system=system)


def apply_fallback_planning_patch() -> None:
    """No-op kept for compatibility: the Nix fallback is built into the planner."""
