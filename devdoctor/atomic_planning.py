"""Atomic Fedora/Bazzite install planning.

The policy itself lives in :mod:`devdoctor.bootstrap` (``install_plan_for_spec``
applies it whenever :func:`devdoctor.host_policy.system_is_atomic` is true) and
in :mod:`devdoctor.host_policy`. This module keeps the names earlier callers and
tests used; nothing here patches other modules any more.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping

from devdoctor import bootstrap
from devdoctor.host_policy import (
    installed_manager_ids as _installed_manager_ids,
)
from devdoctor.host_policy import (
    release_is_atomic as _release_is_atomic,
)
from devdoctor.host_policy import (
    system_is_atomic as _system_is_atomic,
)
from devdoctor.models import JsonValue

__all__ = [
    "_installed_manager_ids",
    "_release_is_atomic",
    "_system_is_atomic",
    "apply_atomic_planning_patch",
    "atomic_install_plan_for_spec",
]

OriginalPlanner = Callable[..., bootstrap.InstallPlan | None]


def atomic_install_plan_for_spec(
    spec: bootstrap.ToolSpec,
    *,
    system: Mapping[str, JsonValue],
    original: OriginalPlanner,
) -> bootstrap.InstallPlan | None:
    """Build a user-space-first Atomic plan, layering only as a final fallback.

    On a mutable host ``original`` is consulted instead; on an Atomic host it is
    never called, so a DNF-based planner cannot leak through.
    """

    if not _system_is_atomic(system):
        return original(spec, system=system)
    return bootstrap._atomic_install_plan(spec, system=system)


def apply_atomic_planning_patch() -> None:
    """No-op kept for compatibility: Atomic planning is built into the planner."""
