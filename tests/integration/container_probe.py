#!/usr/bin/env python3
"""Assertions executed inside Linux package-manager integration containers."""

from __future__ import annotations

import argparse
import subprocess

from devdoctor import bootstrap
from devdoctor.atomic_planning import apply_atomic_planning_patch
from devdoctor.fallback_planning import apply_fallback_planning_patch
from devdoctor.hardening import apply_runtime_hardening
from devdoctor.package_managers import (
    detect_package_managers,
    package_manager_conflicts,
)
from devdoctor.utils import read_os_release


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--expected-manager", required=True)
    parser.add_argument("--expected-plan-manager")
    parser.add_argument("--forbid-plan-manager")
    parser.add_argument("--expected-conflict", action="append", default=[])
    parser.add_argument(
        "--expect-ready",
        action="append",
        default=[],
        metavar="TOOL_ID",
        help="Catalog tool that must detect as installed with no repair advice.",
    )
    parser.add_argument(
        "--verify-catalog-packages",
        choices=("apt", "dnf"),
        help="Ask the host package manager whether every catalog package for it exists.",
    )
    args = parser.parse_args()

    apply_atomic_planning_patch()
    apply_fallback_planning_patch()
    apply_runtime_hardening()

    managers = detect_package_managers()
    installed = {manager.id for manager in managers if manager.installed}
    if args.expected_manager not in installed:
        raise AssertionError(
            f"expected manager {args.expected_manager!r}; detected {sorted(installed)!r}"
        )

    conflicts = {
        conflict.kind for conflict in package_manager_conflicts(managers, read_os_release())
    }
    missing_conflicts = set(args.expected_conflict) - conflicts
    if missing_conflicts:
        raise AssertionError(
            f"missing expected conflicts {sorted(missing_conflicts)!r}; got {sorted(conflicts)!r}"
        )

    if args.expected_plan_manager or args.forbid_plan_manager:
        system = bootstrap.detect_system_context(specs=bootstrap.get_bootstrap_tools())
        git_spec = next(spec for spec in bootstrap.get_bootstrap_tools() if spec.id == "git")
        plan = bootstrap.install_plan_for_spec(git_spec, system=system)
        if args.expected_plan_manager:
            if plan is None:
                raise AssertionError(
                    f"expected plan manager {args.expected_plan_manager!r}, got no plan"
                )
            if plan.manager != args.expected_plan_manager:
                raise AssertionError(
                    f"expected plan manager {args.expected_plan_manager!r}, got {plan.manager!r}"
                )
        if (
            args.forbid_plan_manager
            and plan is not None
            and plan.manager == args.forbid_plan_manager
        ):
            raise AssertionError(f"forbidden plan manager selected: {plan.manager!r}")

    if args.expect_ready:
        _assert_ready(args.expect_ready)

    if args.verify_catalog_packages:
        _assert_catalog_packages_exist(args.verify_catalog_packages)

    print(
        "integration probe ok:",
        args.expected_manager,
        f"plan={args.expected_plan_manager or 'not-asserted'}",
        f"ready={','.join(args.expect_ready) or 'not-asserted'}",
        f"packages={args.verify_catalog_packages or 'not-asserted'}",
    )
    return 0


def _assert_ready(tool_ids: list[str]) -> None:
    """Fail when a tool that is installed in the container is not reported as ready.

    This is the check a stock Ubuntu image would have failed before python3 was
    recognised and before /bin -> /usr/bin stopped counting as a duplicate.
    """

    inventory = bootstrap.bootstrap_inventory(include_ids=tuple(tool_ids))
    by_id = {detection.spec.id: detection for detection in inventory.detections}
    problems: list[str] = []
    for tool_id in tool_ids:
        detection = by_id.get(tool_id)
        if detection is None:
            problems.append(f"{tool_id}: not in catalog")
            continue
        if detection.health is not bootstrap.HealthState.READY:
            advice = "; ".join(item.problem for item in detection.repair_recommendations)
            problems.append(
                f"{tool_id}: health={detection.health} path={detection.executable_path} "
                f"version={detection.version} issues={detection.path_issues} advice={advice}"
            )
    if problems:
        raise AssertionError("tools expected ready:\n  " + "\n  ".join(problems))


def _assert_catalog_packages_exist(manager: str) -> None:
    """Fail when a catalog package name is unknown to the host package manager."""

    unknown: list[str] = []
    for spec in bootstrap.get_bootstrap_tools():
        package = spec.packages.get(manager)
        if package is None:
            continue
        if not _package_exists(manager, package):
            unknown.append(f"{spec.id} -> {manager}:{package}")
    if unknown:
        raise AssertionError(
            f"{manager} does not know these catalog packages:\n  " + "\n  ".join(unknown)
        )


def _package_exists(manager: str, package: str) -> bool:
    if manager == "apt":
        result = subprocess.run(
            ["apt-cache", "policy", package], capture_output=True, text=True, check=False
        )
        # apt-cache prints nothing for an unknown package and "Candidate: (none)"
        # for one that is known but not installable.
        return "Candidate:" in result.stdout and "Candidate: (none)" not in result.stdout
    result = subprocess.run(
        ["dnf", "-q", "info", package], capture_output=True, text=True, check=False
    )
    return result.returncode == 0


if __name__ == "__main__":
    raise SystemExit(main())
