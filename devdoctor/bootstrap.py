"""Developer workstation bootstrap inventory and install planning."""

from __future__ import annotations

import os
import shutil
from collections import defaultdict
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass, field, replace
from enum import StrEnum
from importlib.metadata import EntryPoint, entry_points
from pathlib import Path

from devdoctor.host_policy import (
    ATOMIC_USER_SPACE_ORDER,
    installed_manager_ids,
    release_is_atomic,
    system_is_atomic,
)
from devdoctor.models import JsonValue
from devdoctor.package_managers import NIX_PACKAGES, detect_package_managers
from devdoctor.path_analysis import analyze_path, executable_paths
from devdoctor.utils import get_hostname, get_username, parse_version, read_os_release, run_command

BOOTSTRAP_TOOL_ENTRY_POINT_GROUP = "devdoctor.bootstrap_tools"


class BootstrapCategory(StrEnum):
    """Developer workstation bootstrap categories."""

    SYSTEM = "System"
    PROGRAMMING_LANGUAGES = "Programming Languages"
    VERSION_MANAGERS = "Version Managers"
    PACKAGE_MANAGERS = "Package Managers"
    EDITORS = "Editors"
    CONTAINERS = "Containers"
    VIRTUALIZATION = "Virtualization"
    DATABASES = "Databases"
    CLOUD_CLIS = "Cloud CLIs"
    DEVOPS = "DevOps"
    AI = "AI"
    SECURITY = "Security"
    NETWORKING = "Networking"
    TERMINAL_UTILITIES = "Terminal Utilities"
    BUILD_SYSTEMS = "Build Systems"
    PACKAGE_REGISTRIES = "Package Registries"
    MOBILE_DEVELOPMENT = "Mobile Development"
    GAME_DEVELOPMENT = "Game Development"
    COMPILERS = "Compilers"
    DEBUGGERS = "Debuggers"
    REVERSE_ENGINEERING = "Reverse Engineering"
    MONITORING = "Monitoring"
    SHELL_ENHANCEMENTS = "Shell Enhancements"
    FONTS = "Fonts"
    GIT_UTILITIES = "Git Utilities"
    SSH = "SSH"
    GPG = "GPG"
    SYSTEM_SERVICES = "System Services"


class HealthState(StrEnum):
    """Normalized workstation health state for a tool."""

    READY = "ready"
    MISSING = "missing"
    WARNING = "warning"
    BROKEN = "broken"


@dataclass(frozen=True, slots=True)
class ToolDependency:
    """A catalog relationship between two workstation tools."""

    tool_id: str
    reason: str
    required: bool = True

    def to_dict(self) -> dict[str, JsonValue]:
        """Convert the dependency metadata to JSON data."""

        return {
            "tool_id": self.tool_id,
            "reason": self.reason,
            "required": self.required,
        }


@dataclass(frozen=True, slots=True)
class RepairRecommendation:
    """A concrete repair recommendation derived from local evidence."""

    problem: str
    reason: str
    risk: str
    command: tuple[str, ...] | None
    verification_command: tuple[str, ...] | None
    rollback_command: tuple[str, ...] | None = None
    manual_action: str | None = None

    @property
    def command_text(self) -> str:
        """Return the command or manual action shown to the user."""

        if self.command:
            return " ".join(self.command)
        return self.manual_action or "Manual review required"

    def to_dict(self) -> dict[str, JsonValue]:
        """Convert the recommendation to JSON data."""

        return {
            "problem": self.problem,
            "reason": self.reason,
            "risk": self.risk,
            "command": list(self.command) if self.command else None,
            "command_text": self.command_text,
            "verification_command": (
                list(self.verification_command) if self.verification_command else None
            ),
            "rollback_command": list(self.rollback_command) if self.rollback_command else None,
            "manual_action": self.manual_action,
        }


@dataclass(frozen=True, slots=True)
class DependencyStatus:
    """Resolved status of a declared tool dependency."""

    tool_id: str
    title: str
    required: bool
    installed: bool
    health: HealthState
    reason: str
    install_plan: InstallPlan | None = None

    def to_dict(self) -> dict[str, JsonValue]:
        """Convert the dependency status to JSON data."""

        return {
            "tool_id": self.tool_id,
            "title": self.title,
            "required": self.required,
            "installed": self.installed,
            "health": self.health.value,
            "reason": self.reason,
            "install_plan": self.install_plan.to_dict() if self.install_plan else None,
        }


@dataclass(frozen=True, slots=True)
class ToolSpec:
    """Catalog metadata for one developer workstation tool."""

    id: str
    title: str
    category: BootstrapCategory
    executable: str
    description: str = ""
    # Other command names the same tool may be installed under (python3 for python).
    executable_aliases: tuple[str, ...] = ()
    version_args: tuple[str, ...] = ("--version",)
    verification_args: tuple[str, ...] | None = None
    website: str = ""
    packages: Mapping[str, str] = field(default_factory=dict)
    config_paths: tuple[str, ...] = ()
    dependencies: tuple[str, ...] = ()
    tool_dependencies: tuple[ToolDependency, ...] = ()
    recommended_version: str | None = None


@dataclass(frozen=True, slots=True)
class ToolDetection:
    """Actual detection result for one tool."""

    spec: ToolSpec
    installed: bool
    executable_path: str | None
    version: str | None
    package_manager: str | None
    package_name: str | None
    config_locations: tuple[str, ...]
    alternate_paths: tuple[str, ...]
    installation_method: str | None
    health: HealthState
    broken_installation: bool
    permission_issues: tuple[str, ...]
    path_issues: tuple[str, ...]
    missing_dependencies: tuple[str, ...]
    dependency_status: tuple[DependencyStatus, ...]
    repair_recommendations: tuple[RepairRecommendation, ...]
    install_plan: InstallPlan | None

    def to_dict(self) -> dict[str, JsonValue]:
        """Convert the detection result to JSON data."""

        return {
            "id": self.spec.id,
            "title": self.spec.title,
            "category": self.spec.category.value,
            "description": self.spec.description,
            "installed": self.installed,
            "version": self.version,
            "executable": self.spec.executable,
            "path": self.executable_path,
            "alternate_paths": list(self.alternate_paths),
            "package_manager": self.package_manager,
            "package_name": self.package_name,
            "installation_method": self.installation_method,
            "config_locations": list(self.config_locations),
            "official_website": self.spec.website,
            "recommended_version": self.spec.recommended_version,
            "health": self.health.value,
            "broken_installation": self.broken_installation,
            "permission_issues": list(self.permission_issues),
            "path_issues": list(self.path_issues),
            "missing_dependencies": list(self.missing_dependencies),
            "dependency_status": [status.to_dict() for status in self.dependency_status],
            "repair_recommendations": [
                recommendation.to_dict() for recommendation in self.repair_recommendations
            ],
            "install_plan": self.install_plan.to_dict() if self.install_plan else None,
        }


@dataclass(frozen=True, slots=True)
class InstallPlan:
    """Safe install plan for a missing bootstrap tool."""

    tool_id: str
    tool_title: str
    manager: str
    command: tuple[str, ...]
    explanation: str
    risk: str
    manager_reason: str = ""
    package_name: str = ""
    requires_sudo: bool = False
    dependencies: tuple[str, ...] = ()
    estimated_download_size: str | None = None
    dry_run_command: tuple[str, ...] | None = None
    verify_command: tuple[str, ...] = ()
    rollback_command: tuple[str, ...] | None = None

    @property
    def command_text(self) -> str:
        """Return a shell-display version of the command."""

        return " ".join(self.command)

    def to_dict(self) -> dict[str, JsonValue]:
        """Convert the install plan to JSON data."""

        return {
            "tool_id": self.tool_id,
            "tool_title": self.tool_title,
            "manager": self.manager,
            "manager_reason": self.manager_reason,
            "package_name": self.package_name,
            "dependencies": list(self.dependencies),
            "command": list(self.command),
            "command_text": self.command_text,
            "explanation": self.explanation,
            "risk": self.risk,
            "requires_sudo": self.requires_sudo,
            "estimated_download_size": self.estimated_download_size,
            "dry_run_command": list(self.dry_run_command) if self.dry_run_command else None,
            "verify_command": list(self.verify_command),
            "rollback_command": list(self.rollback_command) if self.rollback_command else None,
        }


@dataclass(frozen=True, slots=True)
class _CompoundToolProbe:
    """Detection result for commands exposed through another executable."""

    executable_path: str
    version: str | None
    installation_method: str


@dataclass(frozen=True, slots=True)
class BootstrapProfile:
    """Named workstation setup profile."""

    id: str
    title: str
    description: str
    tool_ids: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class BootstrapInventory:
    """Full bootstrap inventory for the local workstation."""

    system: Mapping[str, JsonValue]
    detections: tuple[ToolDetection, ...]
    profiles: tuple[BootstrapProfile, ...]

    @property
    def missing(self) -> tuple[ToolDetection, ...]:
        """Return tools that were not detected."""

        return tuple(detection for detection in self.detections if not detection.installed)

    @property
    def broken(self) -> tuple[ToolDetection, ...]:
        """Return tools with unusable local installations."""

        return tuple(
            detection
            for detection in self.detections
            if detection.health is HealthState.BROKEN
            or detection.permission_issues
            or detection.path_issues
        )

    @property
    def warnings(self) -> tuple[ToolDetection, ...]:
        """Return installed tools with repairable warnings."""

        return tuple(
            detection for detection in self.detections if detection.health is HealthState.WARNING
        )

    @property
    def needs_attention(self) -> tuple[ToolDetection, ...]:
        """Return installed tools with repair recommendations."""

        return tuple(detection for detection in self.detections if detection.repair_recommendations)

    def categories(self) -> Mapping[BootstrapCategory, tuple[ToolDetection, ...]]:
        """Return detections grouped by bootstrap category."""

        grouped: dict[BootstrapCategory, list[ToolDetection]] = defaultdict(list)
        for detection in self.detections:
            grouped[detection.spec.category].append(detection)
        return {category: tuple(items) for category, items in grouped.items()}

    def to_dict(self) -> dict[str, JsonValue]:
        """Convert the inventory to JSON data."""

        return {
            "system": self.system,
            "summary": {
                "total": len(self.detections),
                "installed": sum(1 for detection in self.detections if detection.installed),
                "missing": len(self.missing),
                "broken": len(self.broken),
                "warnings": len(self.warnings),
            },
            "tools": [detection.to_dict() for detection in self.detections],
            "profiles": [
                {
                    "id": profile.id,
                    "title": profile.title,
                    "description": profile.description,
                    "tool_ids": list(profile.tool_ids),
                }
                for profile in self.profiles
            ],
        }


def bootstrap_inventory(
    *,
    include_ids: Iterable[str] | None = None,
    include_optional_dependencies: bool = False,
) -> BootstrapInventory:
    """Detect the local workstation bootstrap inventory."""

    all_specs = get_bootstrap_tools()
    specs = all_specs
    if include_ids is not None:
        wanted = _expand_tool_ids_with_dependencies(
            include_ids,
            all_specs,
            include_optional=include_optional_dependencies,
        )
        specs = tuple(spec for spec in specs if spec.id in wanted)
    system = detect_system_context(specs=all_specs)
    detections = tuple(detect_tool(spec, system=system) for spec in specs)
    detections = _enrich_detections(detections, system=system)
    return BootstrapInventory(system=system, detections=detections, profiles=BOOTSTRAP_PROFILES)


def detect_system_context(*, specs: Iterable[ToolSpec] | None = None) -> Mapping[str, JsonValue]:
    """Detect OS, package manager, virtualization, permissions, and PATH context."""

    release = read_os_release()
    distro_id = release.get("ID", "").lower()
    id_like = tuple(item.lower() for item in release.get("ID_LIKE", "").split())
    managers = detect_package_managers()
    _MANAGER_VERSION_BY_PATH.clear()
    for manager in managers:
        if manager.path and manager.version:
            _MANAGER_VERSION_BY_PATH[manager.path] = manager.version
    catalog = tuple(specs or get_bootstrap_tools())
    path_analysis = analyze_path(executables=(spec.executable for spec in catalog))
    manager_preference = _preferred_manager_order(distro_id=distro_id, distro_like=set(id_like))
    return {
        "distribution": release.get("PRETTY_NAME", "unknown"),
        "distribution_id": distro_id or "unknown",
        "distribution_like": list(id_like),
        "atomic_host": release_is_atomic(release),
        "architecture": os.uname().machine if hasattr(os, "uname") else "unknown",
        "desktop_environment": _first_env(
            "XDG_CURRENT_DESKTOP", "XDG_SESSION_DESKTOP", "DESKTOP_SESSION"
        ),
        "session_type": os.environ.get("XDG_SESSION_TYPE", "unknown") or "unknown",
        "shell": Path(os.environ.get("SHELL", "")).name or "unknown",
        "terminal": _first_env("TERM_PROGRAM", "TERMINAL", "TERM"),
        "is_root": os.geteuid() == 0 if hasattr(os, "geteuid") else False,
        "can_sudo": shutil.which("sudo") is not None,
        "is_wsl": _is_wsl(),
        "is_container": _is_container(),
        "virtualization": _virtualization(),
        "path_entries": list(path_analysis.entries),
        "path_issue_count": len(path_analysis.issues),
        "path_analysis": path_analysis.to_dict(),
        "preferred_package_managers": list(manager_preference),
        "package_managers": [
            {
                "id": manager.id,
                "title": manager.title,
                "installed": manager.installed,
                "path": manager.path,
                "version": manager.version,
                "family": manager.family,
                "command_hint": manager.command_hint,
            }
            for manager in managers
        ],
    }


def detect_tool(spec: ToolSpec, *, system: Mapping[str, JsonValue]) -> ToolDetection:
    """Detect one catalog tool using actual local commands and filesystem state."""

    executable_name, executable_path = _resolve_executable(spec)
    all_paths = executable_paths(executable_name)
    compound_probe = _compound_tool_probe(spec) if executable_path is None else None
    problem_path, path_issues, lookup_permission_issues = (
        _path_lookup_problem(executable_name, executable_path=executable_path)
        if compound_probe is None
        else (None, (), ())
    )
    compound_path = compound_probe.executable_path if compound_probe else None
    path = executable_path or compound_path or problem_path
    version = (
        compound_probe.version
        if compound_probe is not None
        else _tool_version(executable_path, spec.version_args)
    )
    permission_issues = () if compound_probe is not None else _permission_issues(path)
    permission_issues = (*lookup_permission_issues, *permission_issues)
    path_issues = (
        ()
        if compound_probe is not None
        else (*path_issues, *_path_issues(path), *_interpreter_issues(path))
    )
    config_locations = _existing_config_locations(spec.config_paths)
    package_manager, package_name = _owning_package(path)
    missing_dependencies = tuple(
        dependency for dependency in spec.dependencies if shutil.which(dependency) is None
    )
    broken = bool(path and (permission_issues or path_issues or missing_dependencies))
    installed = (executable_path is not None or compound_probe is not None) and not (
        path_issues or permission_issues
    )
    health = _base_health(installed=installed, broken=broken)
    return ToolDetection(
        spec=spec,
        installed=installed,
        executable_path=path,
        version=version,
        package_manager=package_manager,
        package_name=package_name,
        config_locations=config_locations,
        alternate_paths=_alternate_paths(all_paths, executable_path),
        installation_method=(
            compound_probe.installation_method
            if compound_probe is not None
            else _installation_method(path, package_manager=package_manager)
        ),
        health=health,
        broken_installation=broken,
        permission_issues=permission_issues,
        path_issues=path_issues,
        missing_dependencies=missing_dependencies,
        dependency_status=(),
        repair_recommendations=(),
        install_plan=None if installed else install_plan_for_spec(spec, system=system),
    )


def install_plan_for_spec(
    spec: ToolSpec,
    *,
    system: Mapping[str, JsonValue],
) -> InstallPlan | None:
    """Build a safe install plan for one tool on the detected system.

    Image-based hosts (Fedora Atomic, Bazzite) get user-space managers first and
    rpm-ostree layering last, never DNF. Everything else follows the distro's
    manager preference. A validated Nix user-profile mapping is the fallback when
    no other manager applies.
    """

    if system_is_atomic(system):
        plan = _atomic_install_plan(spec, system=system)
    else:
        plan = _standard_install_plan(spec, system=system)
    if plan is None:
        plan = _nix_fallback_plan(spec, system=system)
    return plan


def _standard_install_plan(
    spec: ToolSpec,
    *,
    system: Mapping[str, JsonValue],
) -> InstallPlan | None:
    manager_choice = _preferred_install_manager(spec, system)
    if manager_choice is None:
        return None
    manager, manager_reason = manager_choice
    package = spec.packages.get(manager)
    if package is None:
        return None
    return _plan_for_manager(spec, manager=manager, package=package, reason=manager_reason)


def _atomic_install_plan(
    spec: ToolSpec,
    *,
    system: Mapping[str, JsonValue],
) -> InstallPlan | None:
    installed = installed_manager_ids(system)
    for manager in ATOMIC_USER_SPACE_ORDER:
        if manager not in installed:
            continue
        package = _nix_package(spec) if manager == "nix" else spec.packages.get(manager)
        if package is None:
            continue
        plan = _plan_for_manager(
            spec,
            manager=manager,
            package=package,
            reason=(
                "Atomic/image-based host: prefer a mapped user-space or package-scoped manager "
                "before layering the base image."
            ),
        )
        if plan is not None:
            return plan

    if "rpm-ostree" in installed:
        package = spec.packages.get("rpm-ostree") or spec.packages.get("dnf")
        if package:
            return _plan_for_manager(
                spec,
                manager="rpm-ostree",
                package=package,
                reason=(
                    "Atomic/image-based host: no mapped user-space option is available, so use "
                    "rpm-ostree layering for the Fedora package mapping; DNF host mutation is "
                    "intentionally suppressed."
                ),
            )
    return None


# Bootstrap ids whose Nix catalog key does not follow the `tool.<id>` pattern.
_NIX_CATALOG_KEYS = {"rustc": "tool.rust", "gh": "tool.github_cli"}


def _nix_package(spec: ToolSpec) -> str | None:
    key = _NIX_CATALOG_KEYS.get(spec.id, f"tool.{spec.id}")
    return spec.packages.get("nix") or NIX_PACKAGES.get(key)


def _nix_fallback_plan(
    spec: ToolSpec,
    *,
    system: Mapping[str, JsonValue],
) -> InstallPlan | None:
    """A user-profile Nix plan, only for explicitly validated package mappings."""

    if "nix" not in installed_manager_ids(system):
        return None
    package = _nix_package(spec)
    if package is None:
        return None
    plan = _plan_for_manager(
        spec,
        manager="nix",
        package=package,
        reason=(
            "Nix is installed and DevDoctor has an explicit user-profile mapping for this tool."
        ),
    )
    if plan is None:
        return None
    return replace(
        plan,
        explanation=f"Install {spec.title} in the current Nix profile using `{package}`.",
        requires_sudo=False,
    )


def _plan_for_manager(
    spec: ToolSpec,
    *,
    manager: str,
    package: str,
    reason: str,
) -> InstallPlan | None:
    command, dry_run, rollback = _manager_commands(manager, package)
    if command is None:
        return None
    return InstallPlan(
        tool_id=spec.id,
        tool_title=spec.title,
        manager=manager,
        manager_reason=reason,
        package_name=package,
        command=command,
        dry_run_command=dry_run,
        verify_command=_verification_command(spec),
        rollback_command=rollback,
        explanation=f"Install {spec.title} using {manager} package `{package}`.",
        risk=_install_risk(manager),
        requires_sudo=_requires_sudo(command),
        dependencies=tuple(dependency.tool_id for dependency in spec.tool_dependencies),
    )


def profile_by_id(profile_id: str) -> BootstrapProfile | None:
    """Return a profile by id."""

    return next((profile for profile in BOOTSTRAP_PROFILES if profile.id == profile_id), None)


def specs_for_profile(profile: BootstrapProfile) -> tuple[ToolSpec, ...]:
    """Return catalog specs for a profile."""

    by_id = {spec.id: spec for spec in get_bootstrap_tools()}
    return tuple(by_id[tool_id] for tool_id in profile.tool_ids if tool_id in by_id)


def get_bootstrap_tools() -> tuple[ToolSpec, ...]:
    """Return built-in and external bootstrap tool specs."""

    by_id: dict[str, ToolSpec] = {spec.id: spec for spec in BOOTSTRAP_TOOLS}
    for spec in _external_tool_specs():
        by_id.setdefault(spec.id, spec)
    return tuple(by_id.values())


def _expand_tool_ids_with_dependencies(
    include_ids: Iterable[str],
    specs: Iterable[ToolSpec],
    *,
    include_optional: bool = False,
) -> set[str]:
    """Return selected tool IDs plus their declared dependency graph."""

    by_id = {spec.id: spec for spec in specs}
    expanded = set(include_ids)
    pending = list(expanded)
    while pending:
        tool_id = pending.pop()
        spec = by_id.get(tool_id)
        if spec is None:
            continue
        dependency_ids = {
            *spec.dependencies,
            *(
                dependency.tool_id
                for dependency in spec.tool_dependencies
                if include_optional or dependency.required
            ),
        }
        for dependency_id in dependency_ids:
            if dependency_id in expanded:
                continue
            expanded.add(dependency_id)
            pending.append(dependency_id)
    return expanded


def _external_tool_specs() -> tuple[ToolSpec, ...]:
    specs: list[ToolSpec] = []
    for entry_point in _bootstrap_tool_entry_points():
        try:
            loaded = entry_point.load()
            value = loaded() if callable(loaded) else loaded
        except Exception:
            continue
        if isinstance(value, ToolSpec):
            specs.append(value)
            continue
        if isinstance(value, Iterable) and not isinstance(value, (str, bytes, Mapping)):
            specs.extend(item for item in value if isinstance(item, ToolSpec))
    return tuple(specs)


def _enrich_detections(
    detections: tuple[ToolDetection, ...],
    *,
    system: Mapping[str, JsonValue],
) -> tuple[ToolDetection, ...]:
    by_id = {detection.spec.id: detection for detection in detections}
    enriched: list[ToolDetection] = []
    for detection in detections:
        dependency_status = _dependency_status(detection, by_id=by_id, system=system)
        recommendations = (
            *_generic_repair_recommendations(detection),
            *_tool_specific_repair_recommendations(detection, by_id=by_id, system=system),
            *_dependency_repair_recommendations(detection, dependency_status),
        )
        health = _health_from_recommendations(
            detection,
            dependency_status=dependency_status,
            recommendations=recommendations,
        )
        enriched.append(
            replace(
                detection,
                dependency_status=dependency_status,
                repair_recommendations=recommendations,
                health=health,
                broken_installation=health is HealthState.BROKEN and bool(recommendations),
            )
        )
    return tuple(enriched)


def _dependency_status(
    detection: ToolDetection,
    *,
    by_id: Mapping[str, ToolDetection],
    system: Mapping[str, JsonValue],
) -> tuple[DependencyStatus, ...]:
    statuses: list[DependencyStatus] = []
    for dependency in detection.spec.tool_dependencies:
        dependency_detection = by_id.get(dependency.tool_id)
        if dependency_detection is None:
            continue
        statuses.append(
            DependencyStatus(
                tool_id=dependency.tool_id,
                title=dependency_detection.spec.title,
                required=dependency.required,
                installed=dependency_detection.installed,
                health=dependency_detection.health,
                reason=dependency.reason,
                install_plan=(
                    None
                    if dependency_detection.installed
                    else install_plan_for_spec(dependency_detection.spec, system=system)
                ),
            )
        )
    return tuple(statuses)


def _health_from_recommendations(
    detection: ToolDetection,
    *,
    dependency_status: tuple[DependencyStatus, ...],
    recommendations: tuple[RepairRecommendation, ...],
) -> HealthState:
    if detection.path_issues or detection.permission_issues:
        return HealthState.BROKEN
    if not detection.installed:
        return HealthState.MISSING
    if any(status.required and not status.installed for status in dependency_status):
        return HealthState.WARNING
    if any(recommendation.risk == "high" for recommendation in recommendations):
        return HealthState.BROKEN
    if recommendations:
        return HealthState.WARNING
    return HealthState.READY


def _bootstrap_tool_entry_points() -> tuple[EntryPoint, ...]:
    all_entry_points = entry_points()
    if hasattr(all_entry_points, "select"):
        return tuple(all_entry_points.select(group=BOOTSTRAP_TOOL_ENTRY_POINT_GROUP))
    return tuple(all_entry_points.get(BOOTSTRAP_TOOL_ENTRY_POINT_GROUP, ()))  # type: ignore[union-attr]


# Versions already probed for package managers, keyed by executable path, so a
# tool that is also a manager (pip, npm, cargo, ...) is not probed twice.
_MANAGER_VERSION_BY_PATH: dict[str, str] = {}


def _tool_version(path: str | None, version_args: Sequence[str]) -> str | None:
    if path is None:
        return None
    cached = _MANAGER_VERSION_BY_PATH.get(path)
    if cached is not None:
        return cached
    result = run_command((path, *version_args), timeout=5)
    if result.returncode == 124:
        # run_command's sentinel for "could not start or timed out": the stderr
        # holds an OSError message, not tool output.
        return None
    return parse_version(result.combined_output)


def _compound_tool_probe(spec: ToolSpec) -> _CompoundToolProbe | None:
    probes: Mapping[str, tuple[str, ...]] = {
        "docker-compose": ("compose", "version"),
        "docker-buildx": ("buildx", "version"),
    }
    args = probes.get(spec.id)
    if args is None:
        return None
    docker_path = shutil.which("docker")
    if docker_path is None:
        return None
    result = run_command((docker_path, *args), timeout=5)
    if result.returncode != 0:
        return None
    return _CompoundToolProbe(
        executable_path=docker_path,
        version=parse_version(result.combined_output),
        installation_method="docker CLI plugin",
    )


def _verification_command(spec: ToolSpec) -> tuple[str, ...]:
    if spec.id == "docker-compose":
        return ("docker", "compose", "version")
    if spec.id == "docker-buildx":
        return ("docker", "buildx", "version")
    args = spec.verification_args if spec.verification_args is not None else spec.version_args
    return (spec.executable, *args)


def _requires_sudo(command: Sequence[str]) -> bool:
    return bool(command and command[0] == "sudo")


def _base_health(*, installed: bool, broken: bool) -> HealthState:
    # A command that exists but cannot run (broken symlink, dead interpreter,
    # no execute bit) is broken, not absent: the summary counters, the repair
    # advice, and the install plan all treat it that way.
    if broken:
        return HealthState.BROKEN
    if not installed:
        return HealthState.MISSING
    return HealthState.READY


def _installation_method(path: str | None, *, package_manager: str | None) -> str | None:
    if package_manager:
        return package_manager
    if path is None:
        return None
    normalized = path.lower()
    home = str(Path.home()).lower()
    if ".linuxbrew" in normalized or "/homebrew/" in normalized:
        return "homebrew path"
    if normalized.startswith(f"{home}/.cargo/"):
        return "cargo path"
    if normalized.startswith(f"{home}/.local/"):
        return "user-local path"
    if normalized.startswith(f"{home}/go/"):
        return "go path"
    if normalized.startswith("/usr/") or normalized.startswith("/bin/"):
        return "system path"
    if normalized.startswith("/opt/"):
        return "opt path"
    return "path inferred"


def _generic_repair_recommendations(
    detection: ToolDetection,
) -> tuple[RepairRecommendation, ...]:
    recommendations: list[RepairRecommendation] = []
    for issue in detection.permission_issues:
        recommendations.append(
            RepairRecommendation(
                problem=issue,
                reason=(
                    "DevDoctor found the executable path, but the current user cannot "
                    "execute or read it."
                ),
                risk="medium",
                command=None,
                verification_command=_verification_command(detection.spec),
                manual_action=(
                    f"Review ownership and permissions with: ls -l {detection.executable_path}"
                    if detection.executable_path
                    else "Review executable permissions."
                ),
            )
        )
    for issue in detection.path_issues:
        recommendations.append(
            RepairRecommendation(
                problem=issue,
                reason=(
                    "The command name resolves to a filesystem entry that cannot be used safely."
                ),
                risk="medium",
                command=None,
                verification_command=_verification_command(detection.spec),
                manual_action=(
                    f"Remove or relink stale executable: {detection.executable_path}"
                    if detection.executable_path
                    else "Remove or relink the stale executable."
                ),
            )
        )
    for dependency in detection.missing_dependencies:
        recommendations.append(
            RepairRecommendation(
                problem=f"Missing executable dependency: {dependency}",
                reason=f"{detection.spec.title} declared `{dependency}` as a runtime dependency.",
                risk="low",
                command=None,
                verification_command=(dependency, "--version"),
                manual_action=f"Install `{dependency}` with your preferred package manager.",
            )
        )
    if detection.alternate_paths:
        recommendations.append(
            RepairRecommendation(
                problem="Duplicate installation detected",
                reason=(
                    f"`{detection.spec.executable}` appears in multiple PATH locations: "
                    f"{', '.join(detection.alternate_paths)}"
                ),
                risk="low",
                command=None,
                verification_command=("which", "-a", detection.spec.executable),
                manual_action="Review PATH order and remove obsolete duplicate installations.",
            )
        )
    return tuple(recommendations)


def _dependency_repair_recommendations(
    detection: ToolDetection,
    dependency_status: tuple[DependencyStatus, ...],
) -> tuple[RepairRecommendation, ...]:
    if not detection.installed:
        return ()
    recommendations: list[RepairRecommendation] = []
    for dependency in dependency_status:
        if dependency.installed:
            continue
        plan = dependency.install_plan
        recommendations.append(
            RepairRecommendation(
                problem=f"Missing dependency: {dependency.title}",
                reason=dependency.reason,
                risk="medium" if dependency.required else "low",
                command=plan.command if plan else None,
                verification_command=plan.verify_command if plan else None,
                rollback_command=plan.rollback_command if plan else None,
                manual_action=None if plan else f"Install dependency `{dependency.tool_id}`.",
            )
        )
    return tuple(recommendations)


def _tool_specific_repair_recommendations(
    detection: ToolDetection,
    *,
    by_id: Mapping[str, ToolDetection],
    system: Mapping[str, JsonValue],
) -> tuple[RepairRecommendation, ...]:
    if not detection.installed:
        return ()
    tool_id = detection.spec.id
    if tool_id == "docker":
        return _docker_recommendations(detection)
    if tool_id == "git":
        return _git_recommendations(detection)
    if tool_id == "ssh":
        return _ssh_recommendations(detection)
    if tool_id == "python":
        return _python_recommendations(detection, by_id=by_id)
    if tool_id == "node":
        return _node_recommendations(by_id=by_id)
    if tool_id == "java":
        return _java_recommendations(detection)
    if tool_id == "cargo":
        return _cargo_recommendations(system=system)
    if tool_id == "flutter":
        return _flutter_recommendations(by_id=by_id)
    return ()


def _docker_recommendations(detection: ToolDetection) -> tuple[RepairRecommendation, ...]:
    if detection.executable_path is None:
        return ()
    result = run_command((detection.executable_path, "info"), timeout=5)
    if result.returncode == 0:
        return ()
    output = result.combined_output.lower()
    if "permission denied" in output or "docker.sock" in output:
        username = get_username()
        return (
            RepairRecommendation(
                problem="Docker socket permission issue",
                reason=(
                    "Docker CLI is installed, but the current user cannot access the "
                    "Docker daemon socket."
                ),
                risk="high",
                command=("sudo", "usermod", "-aG", "docker", username),
                verification_command=("docker", "info"),
                rollback_command=("sudo", "gpasswd", "-d", username, "docker"),
                manual_action="Log out and back in after changing Docker group membership.",
            ),
        )
    if shutil.which("systemctl"):
        return (
            RepairRecommendation(
                problem="Docker daemon is not running",
                reason="`docker info` could not reach a running Docker daemon.",
                risk="medium",
                command=("sudo", "systemctl", "start", "docker"),
                verification_command=("docker", "info"),
                rollback_command=("sudo", "systemctl", "stop", "docker"),
            ),
        )
    return (
        RepairRecommendation(
            problem="Docker daemon is unavailable",
            reason=(
                "`docker info` failed, and no systemctl command is available for an "
                "automatic service start."
            ),
            risk="medium",
            command=None,
            verification_command=("docker", "info"),
            manual_action="Start the Docker daemon using your distribution's service manager.",
        ),
    )


def _git_recommendations(detection: ToolDetection) -> tuple[RepairRecommendation, ...]:
    if detection.executable_path is None:
        return ()
    checks = (
        ("user.name", "Git user.name is not configured"),
        ("user.email", "Git user.email is not configured"),
    )
    recommendations: list[RepairRecommendation] = []
    for key, problem in checks:
        result = run_command((detection.executable_path, "config", "--global", "--get", key))
        if result.returncode == 0 and result.combined_output.strip():
            continue
        recommendations.append(
            RepairRecommendation(
                problem=problem,
                reason=f"Git commits use `{key}` to identify the author on this workstation.",
                risk="low",
                command=(detection.executable_path, "config", "--global", "--edit"),
                verification_command=(
                    detection.executable_path,
                    "config",
                    "--global",
                    "--get",
                    key,
                ),
                manual_action=f"Set `{key}` to the real value you want on commits.",
            )
        )
    return tuple(recommendations)


def _ssh_recommendations(detection: ToolDetection) -> tuple[RepairRecommendation, ...]:
    ssh_dir = Path.home() / ".ssh"
    public_keys = tuple(ssh_dir.glob("*.pub")) if ssh_dir.exists() else ()
    if public_keys:
        return ()
    return (
        RepairRecommendation(
            problem="No SSH public key found",
            reason="Git and remote server workflows commonly require a local SSH key.",
            risk="low",
            command=("ssh-keygen", "-t", "ed25519", "-C", f"{get_username()}@{get_hostname()}"),
            verification_command=None,
            manual_action="After generation, add the public key to the services you use.",
        ),
    )


def _python_recommendations(
    detection: ToolDetection,
    *,
    by_id: Mapping[str, ToolDetection],
) -> tuple[RepairRecommendation, ...]:
    if by_id.get("pip") and by_id["pip"].installed:
        return ()
    if detection.executable_path is None:
        return ()
    result = run_command((detection.executable_path, "-m", "pip", "--version"), timeout=5)
    if result.returncode == 0:
        return ()
    return (
        RepairRecommendation(
            problem="Python is installed without pip",
            reason="Python package installation and many bootstrap tools require pip.",
            risk="medium",
            command=(detection.executable_path, "-m", "ensurepip", "--upgrade"),
            verification_command=(detection.executable_path, "-m", "pip", "--version"),
        ),
    )


def _node_recommendations(
    *,
    by_id: Mapping[str, ToolDetection],
) -> tuple[RepairRecommendation, ...]:
    npm = by_id.get("npm")
    if npm is not None and npm.installed:
        return ()
    return (
        RepairRecommendation(
            problem="Node.js is installed without npm",
            reason="npm is the default package registry client for most Node.js workflows.",
            risk="medium",
            command=None,
            verification_command=("npm", "--version"),
            manual_action="Install npm with the same package manager used for Node.js.",
        ),
    )


def _java_recommendations(detection: ToolDetection) -> tuple[RepairRecommendation, ...]:
    if os.environ.get("JAVA_HOME"):
        return ()
    return (
        RepairRecommendation(
            problem="JAVA_HOME is not set",
            reason="Java build tools often require JAVA_HOME in addition to the java executable.",
            risk="low",
            command=None,
            verification_command=("java", "-version"),
            manual_action=(
                "Set JAVA_HOME to the JDK prefix for the java executable reported by "
                f"{detection.executable_path or 'command -v java'}."
            ),
        ),
    )


def _cargo_recommendations(*, system: Mapping[str, JsonValue]) -> tuple[RepairRecommendation, ...]:
    cargo_bin = Path.home() / ".cargo/bin"
    path_entries = {str(entry) for entry in system.get("path_entries", ())}
    if not cargo_bin.exists() or str(cargo_bin) in path_entries:
        return ()
    return (
        RepairRecommendation(
            problem="Cargo binary directory is not in PATH",
            reason="Cargo-installed commands are placed under ~/.cargo/bin.",
            risk="low",
            command=None,
            verification_command=("cargo", "--version"),
            manual_action=f'export PATH="{cargo_bin}:$PATH"',
        ),
    )


def _flutter_recommendations(
    *,
    by_id: Mapping[str, ToolDetection],
) -> tuple[RepairRecommendation, ...]:
    missing = [
        title
        for tool_id, title in (("java", "Java"), ("adb", "Android Debug Bridge"))
        if tool_id not in by_id or not by_id[tool_id].installed
    ]
    if not missing:
        return ()
    return (
        RepairRecommendation(
            problem="Flutter Android toolchain is incomplete",
            reason=f"Flutter Android development requires: {', '.join(missing)}.",
            risk="medium",
            command=None,
            verification_command=("flutter", "doctor"),
            manual_action=(
                "Install the missing Android toolchain dependencies, then run `flutter doctor`."
            ),
        ),
    )


def _permission_issues(path: str | None) -> tuple[str, ...]:
    if path is None:
        return ()
    issues: list[str] = []
    if not os.access(path, os.X_OK):
        issues.append("Executable is not marked executable.")
    if not os.access(path, os.R_OK):
        issues.append("Executable is not readable by the current user.")
    return tuple(issues)


def _path_issues(path: str | None) -> tuple[str, ...]:
    if path is None:
        return ()
    executable = Path(path)
    if executable.is_symlink() and not executable.exists():
        return ("Executable symlink is broken.",)
    return ()


def _resolve_executable(spec: ToolSpec) -> tuple[str, str | None]:
    """Return the first catalog command name found in PATH and its location."""

    for name in (spec.executable, *spec.executable_aliases):
        found = shutil.which(name)
        if found is not None:
            return name, found
    return spec.executable, None


def _alternate_paths(all_paths: Sequence[str], executable_path: str | None) -> tuple[str, ...]:
    """Other PATH locations of the same command that are genuinely different files.

    Merged-usr hosts expose /bin as a symlink to /usr/bin; both spellings resolve
    to one file and are not a duplicate installation.
    """

    if executable_path is None:
        return tuple(all_paths)
    primary = os.path.realpath(executable_path)
    return tuple(
        found
        for found in all_paths
        if found != executable_path and os.path.realpath(found) != primary
    )


def _interpreter_issues(path: str | None) -> tuple[str, ...]:
    """Report a script whose shebang names an interpreter that no longer exists."""

    if path is None:
        return ()
    try:
        with open(path, "rb") as handle:
            head = handle.read(256)
    except OSError:
        return ()
    if not head.startswith(b"#!"):
        return ()
    parts = head.split(b"\n", 1)[0][2:].decode("utf-8", "replace").split()
    if not parts:
        return ()
    interpreter = parts[0]
    if os.path.basename(interpreter) == "env":
        targets = [part for part in parts[1:] if not part.startswith("-")]
        if not targets:
            return ()
        if shutil.which(targets[0]) is None:
            return (f"Executable interpreter `{targets[0]}` is not in PATH (broken shebang).",)
        return ()
    if not os.path.exists(interpreter):
        return (f"Executable interpreter `{interpreter}` does not exist (broken shebang).",)
    return ()


def _path_lookup_problem(
    executable: str,
    *,
    executable_path: str | None,
) -> tuple[str | None, tuple[str, ...], tuple[str, ...]]:
    if executable_path is not None:
        return (None, (), ())

    for entry in os.environ.get("PATH", "").split(os.pathsep):
        if not entry:
            continue
        candidate = Path(entry) / executable
        if not os.path.lexists(candidate):
            continue
        if candidate.is_symlink() and not candidate.exists():
            return (str(candidate), ("Executable symlink is broken.",), ())
        if candidate.exists() and not os.access(candidate, os.X_OK):
            return (
                str(candidate),
                (),
                ("Executable exists in PATH but is not marked executable.",),
            )
    return (None, (), ())


def _existing_config_locations(paths: Iterable[str]) -> tuple[str, ...]:
    home = Path.home()
    existing: list[str] = []
    for raw_path in paths:
        path = Path(raw_path.replace("~", str(home))).expanduser()
        if path.exists():
            existing.append(str(path))
    return tuple(existing)


def _owning_package(path: str | None) -> tuple[str | None, str | None]:
    if path is None:
        return (None, None)
    commands = (
        ("dpkg", ("dpkg", "-S", path)),
        ("rpm", ("rpm", "-qf", path)),
        ("pacman", ("pacman", "-Qo", path)),
    )
    for manager, command in commands:
        if shutil.which(command[0]) is None:
            continue
        result = run_command(command, timeout=3)
        if result.returncode == 0 and result.combined_output:
            return (manager, result.combined_output.splitlines()[0][:160])
    return (None, None)


def _preferred_install_manager(
    spec: ToolSpec,
    system: Mapping[str, JsonValue],
) -> tuple[str, str] | None:
    managers = system.get("package_managers", ())
    installed_manager_ids = {
        str(manager.get("id"))
        for manager in managers
        if isinstance(manager, dict) and manager.get("installed") is True
    }
    distro_id = str(system.get("distribution_id", "")).lower()
    distro_like = {str(item).lower() for item in system.get("distribution_like", ())}
    if system_is_atomic(system):
        for manager in (*ATOMIC_USER_SPACE_ORDER, "rpm-ostree"):
            if manager in installed_manager_ids and manager in spec.packages:
                return (
                    manager,
                    "Atomic/image-based host policy: prefer mapped user-space tooling before "
                    "rpm-ostree layering and never use dnf for host mutation.",
                )
        return None
    candidates = _preferred_manager_order(distro_id=distro_id, distro_like=distro_like)

    for manager in candidates:
        if manager in installed_manager_ids and manager in spec.packages:
            return (manager, _manager_reason(manager, distro_id=distro_id, distro_like=distro_like))
    for manager in spec.packages:
        if manager in installed_manager_ids:
            return (
                manager,
                f"{manager} is installed locally and the catalog has a package mapping.",
            )
    return None


def _preferred_manager_order(
    *,
    distro_id: str,
    distro_like: set[str],
) -> tuple[str, ...]:
    if distro_id == "bazzite":
        return ("brew", "rpm-ostree", "dnf", "flatpak", "cargo", "npm", "pip", "pipx")
    if distro_id in {"ubuntu", "debian", "linuxmint", "pop"} or distro_like.intersection(
        {"ubuntu", "debian"}
    ):
        return ("apt", "snap", "flatpak", "brew", "cargo", "npm", "pip", "pipx")
    if distro_id == "fedora" or "fedora" in distro_like:
        return ("dnf", "flatpak", "brew", "cargo", "npm", "pip", "pipx")
    if distro_id in {"arch", "manjaro"} or "arch" in distro_like:
        return ("pacman", "yay", "paru", "flatpak", "cargo", "npm", "pip", "pipx")
    if distro_id in {"opensuse", "opensuse-tumbleweed", "sles"} or "suse" in distro_like:
        return ("zypper", "flatpak", "brew", "cargo", "npm", "pip", "pipx")
    if distro_id == "void":
        return ("xbps", "flatpak", "brew", "cargo", "npm", "pip", "pipx")
    if distro_id == "alpine":
        return ("apk", "cargo", "npm", "pip", "pipx")
    return ("brew", "nix", "flatpak", "snap", "cargo", "npm", "pip", "pipx")


def _manager_reason(
    manager: str,
    *,
    distro_id: str,
    distro_like: set[str],
) -> str:
    if distro_id == "bazzite" and manager == "brew":
        return "Bazzite is image-based; Homebrew keeps developer tools in user space."
    if distro_id == "bazzite" and manager == "rpm-ostree":
        return (
            "Bazzite uses rpm-ostree for system layering when a user-space option is unavailable."
        )
    if manager == "apt":
        return "APT is the native package manager for Debian and Ubuntu-family systems."
    if manager == "dnf":
        return "DNF is the native package manager for Fedora-family systems."
    if manager == "pacman":
        return "Pacman is the native package manager for Arch-family systems."
    if manager == "zypper":
        return "Zypper is the native package manager for SUSE-family systems."
    if manager == "xbps":
        return "XBPS is the native package manager for Void Linux."
    if manager == "apk":
        return "APK is the native package manager for Alpine Linux."
    if manager in {"yay", "paru"}:
        return f"{manager} is available for Arch-compatible community packages."
    if manager == "brew":
        return "Homebrew is installed locally and can manage developer tools without sudo."
    if manager in {"cargo", "npm", "pnpm", "pip", "pipx", "gem", "composer"}:
        return f"{manager} is the language package manager mapped for this tool."
    if distro_like:
        return f"{manager} is available on this {', '.join(sorted(distro_like))}-like system."
    return f"{manager} is installed locally and mapped for this tool."


def _manager_commands(
    manager: str,
    package: str,
) -> tuple[tuple[str, ...] | None, tuple[str, ...] | None, tuple[str, ...] | None]:
    commands: Mapping[
        str, tuple[tuple[str, ...], tuple[str, ...] | None, tuple[str, ...] | None]
    ] = {
        "apt": (
            ("sudo", "apt", "install", package),
            ("apt", "install", "--dry-run", package),
            ("sudo", "apt", "remove", package),
        ),
        "dnf": (
            ("sudo", "dnf", "install", package),
            ("dnf", "install", "--assumeno", package),
            ("sudo", "dnf", "remove", package),
        ),
        "rpm-ostree": (
            ("rpm-ostree", "install", package),
            None,
            ("rpm-ostree", "uninstall", package),
        ),
        "pacman": (
            ("sudo", "pacman", "-S", package),
            ("pacman", "-Si", package),
            ("sudo", "pacman", "-R", package),
        ),
        "yay": (("yay", "-S", package), ("yay", "-Si", package), ("yay", "-R", package)),
        "paru": (("paru", "-S", package), ("paru", "-Si", package), ("paru", "-R", package)),
        "zypper": (
            ("sudo", "zypper", "install", package),
            ("zypper", "install", "--dry-run", package),
            ("sudo", "zypper", "remove", package),
        ),
        "xbps": (
            ("sudo", "xbps-install", package),
            ("xbps-query", "-Rs", package),
            ("sudo", "xbps-remove", package),
        ),
        "apk": (
            ("sudo", "apk", "add", package),
            ("apk", "info", package),
            ("sudo", "apk", "del", package),
        ),
        "nix": (
            ("nix", "profile", "install", package),
            None,
            ("nix", "profile", "remove", package),
        ),
        "brew": (("brew", "install", package), None, ("brew", "uninstall", package)),
        "flatpak": (
            ("flatpak", "install", "flathub", package),
            ("flatpak", "remote-ls", "flathub", package),
            ("flatpak", "uninstall", package),
        ),
        "snap": (
            (
                ("sudo", "snap", "install", package, "--classic")
                if package in _CLASSIC_SNAPS
                else ("sudo", "snap", "install", package)
            ),
            ("snap", "info", package),
            ("sudo", "snap", "remove", package),
        ),
        "cargo": (("cargo", "install", package), ("cargo", "search", package), None),
        "go": (("go", "install", package), None, None),
        "pip": (
            ("python", "-m", "pip", "install", package),
            None,
            ("python", "-m", "pip", "uninstall", package),
        ),
        "pipx": (("pipx", "install", package), None, ("pipx", "uninstall", package)),
        "npm": (
            ("npm", "install", "-g", package),
            ("npm", "view", package, "version"),
            ("npm", "uninstall", "-g", package),
        ),
        "pnpm": (
            ("pnpm", "add", "-g", package),
            ("pnpm", "view", package, "version"),
            ("pnpm", "remove", "-g", package),
        ),
        "yarn": (
            ("yarn", "global", "add", package),
            ("yarn", "info", package, "version"),
            ("yarn", "global", "remove", package),
        ),
        "gem": (("gem", "install", package), None, ("gem", "uninstall", package)),
        "composer": (
            ("composer", "global", "require", package),
            None,
            ("composer", "global", "remove", package),
        ),
        "sdkman": (("sdk", "install", package), None, ("sdk", "uninstall", package)),
        "rustup": (
            ("rustup", "toolchain", "install", package),
            None,
            ("rustup", "toolchain", "uninstall", package),
        ),
        "flutter": (("flutter", "pub", "global", "activate", package), None, None),
        "mise": (("mise", "use", "-g", package), None, ("mise", "uninstall", package)),
        "asdf": (("asdf", "install", package), None, ("asdf", "uninstall", package)),
    }
    return commands.get(manager, (None, None, None))


def _install_risk(manager: str) -> str:
    if manager in {"apt", "dnf", "pacman", "zypper", "xbps", "apk", "snap"}:
        return "medium - requires system package privileges"
    if manager == "rpm-ostree":
        return "medium - layers an image package and may require reboot"
    if manager in {"pip", "npm", "pnpm", "yarn", "gem", "composer"}:
        return "medium - global language package install"
    return "low - user-space package install"


def _first_env(*names: str) -> str:
    for name in names:
        value = os.environ.get(name)
        if value:
            return value
    return "unknown"


def _is_wsl() -> bool:
    try:
        version = Path("/proc/version").read_text(encoding="utf-8").lower()
    except OSError:
        return False
    return "microsoft" in version or "wsl" in version


def _is_container() -> bool:
    if Path("/.dockerenv").exists() or Path("/run/.containerenv").exists():
        return True
    try:
        cgroup = Path("/proc/1/cgroup").read_text(encoding="utf-8").lower()
    except OSError:
        return False
    return any(marker in cgroup for marker in ("docker", "podman", "kubepods", "containerd"))


def _virtualization() -> str:
    if shutil.which("systemd-detect-virt") is None:
        return "unknown"
    result = run_command(("systemd-detect-virt",), timeout=2)
    if result.returncode == 0 and result.combined_output:
        return result.combined_output.splitlines()[0]
    return "none"


# Snaps published with classic confinement; `snap install` refuses them without --classic.
_CLASSIC_SNAPS: frozenset[str] = frozenset(
    {"kubectl", "helm", "code", "flutter", "aws-cli", "google-cloud-cli"}
)


def _packages(
    *,
    apt: str | None = None,
    dnf: str | None = None,
    rpm_ostree: str | None = None,
    pacman: str | None = None,
    yay: str | None = None,
    paru: str | None = None,
    zypper: str | None = None,
    xbps: str | None = None,
    apk: str | None = None,
    nix: str | None = None,
    brew: str | None = None,
    flatpak: str | None = None,
    snap: str | None = None,
    cargo: str | None = None,
    go: str | None = None,
    pip: str | None = None,
    pipx: str | None = None,
    npm: str | None = None,
    pnpm: str | None = None,
    yarn: str | None = None,
    gem: str | None = None,
    composer: str | None = None,
    sdkman: str | None = None,
    rustup: str | None = None,
    flutter: str | None = None,
    mise: str | None = None,
    asdf: str | None = None,
) -> Mapping[str, str]:
    values = {
        "apt": apt,
        "dnf": dnf,
        "rpm-ostree": rpm_ostree,
        "pacman": pacman,
        "yay": yay,
        "paru": paru,
        "zypper": zypper,
        "xbps": xbps,
        "apk": apk,
        "nix": nix,
        "brew": brew,
        "flatpak": flatpak,
        "snap": snap,
        "cargo": cargo,
        "go": go,
        "pip": pip,
        "pipx": pipx,
        "npm": npm,
        "pnpm": pnpm,
        "yarn": yarn,
        "gem": gem,
        "composer": composer,
        "sdkman": sdkman,
        "rustup": rustup,
        "flutter": flutter,
        "mise": mise,
        "asdf": asdf,
    }
    return {manager: package for manager, package in values.items() if package}


BOOTSTRAP_TOOLS: tuple[ToolSpec, ...] = (
    ToolSpec(
        "git",
        "Git",
        BootstrapCategory.GIT_UTILITIES,
        "git",
        description="Distributed version control used by most source workflows.",
        website="https://git-scm.com/",
        config_paths=("~/.gitconfig", "~/.config/git/config"),
        tool_dependencies=(
            ToolDependency("ssh", "Git over SSH requires an OpenSSH client."),
            ToolDependency("gpg", "Signed commits and tags require GnuPG.", required=False),
        ),
        packages=_packages(
            apt="git", dnf="git", pacman="git", zypper="git", xbps="git", apk="git", brew="git"
        ),
    ),
    ToolSpec(
        "curl",
        "curl",
        BootstrapCategory.NETWORKING,
        "curl",
        website="https://curl.se/",
        packages=_packages(
            apt="curl",
            dnf="curl",
            pacman="curl",
            zypper="curl",
            xbps="curl",
            apk="curl",
            brew="curl",
        ),
    ),
    ToolSpec(
        "wget",
        "wget",
        BootstrapCategory.NETWORKING,
        "wget",
        website="https://www.gnu.org/software/wget/",
        packages=_packages(
            apt="wget",
            dnf="wget",
            pacman="wget",
            zypper="wget",
            xbps="wget",
            apk="wget",
            brew="wget",
        ),
    ),
    ToolSpec(
        "python",
        "Python",
        BootstrapCategory.PROGRAMMING_LANGUAGES,
        "python3",
        executable_aliases=("python",),
        description="Python runtime for automation, backend services, and CLI tooling.",
        website="https://python.org/",
        tool_dependencies=(ToolDependency("pip", "Python package installation requires pip."),),
        packages=_packages(
            apt="python3",
            dnf="python3",
            pacman="python",
            zypper="python3",
            xbps="python3",
            apk="python3",
            brew="python",
            mise="python@latest",
            asdf="python latest",
        ),
    ),
    ToolSpec(
        "pip",
        "pip",
        BootstrapCategory.PACKAGE_REGISTRIES,
        "pip",
        executable_aliases=("pip3",),
        website="https://pip.pypa.io/",
        packages=_packages(
            apt="python3-pip",
            dnf="python3-pip",
            pacman="python-pip",
            zypper="python3-pip",
            xbps="python3-pip",
            apk="py3-pip",
            brew="python",
        ),
    ),
    ToolSpec(
        "pipx",
        "pipx",
        BootstrapCategory.PACKAGE_REGISTRIES,
        "pipx",
        website="https://pypa.github.io/pipx/",
        packages=_packages(apt="pipx", dnf="pipx", pacman="python-pipx", brew="pipx", pip="pipx"),
    ),
    ToolSpec(
        "node",
        "Node.js",
        BootstrapCategory.PROGRAMMING_LANGUAGES,
        "node",
        description="JavaScript runtime for frontend tooling and Node.js services.",
        website="https://nodejs.org/",
        tool_dependencies=(
            ToolDependency("npm", "Node.js projects commonly require npm."),
            ToolDependency("corepack", "corepack manages pnpm and Yarn shims.", required=False),
            ToolDependency("pnpm", "Many modern Node.js projects use pnpm.", required=False),
            ToolDependency("yarn", "Some Node.js projects use Yarn.", required=False),
        ),
        packages=_packages(
            apt="nodejs",
            dnf="nodejs",
            pacman="nodejs",
            zypper="nodejs",
            xbps="nodejs",
            apk="nodejs",
            brew="node",
            mise="node@lts",
            asdf="nodejs latest",
        ),
    ),
    ToolSpec(
        "npm",
        "npm",
        BootstrapCategory.PACKAGE_REGISTRIES,
        "npm",
        description="Default package registry client for Node.js.",
        website="https://www.npmjs.com/",
        config_paths=("~/.npmrc",),
        packages=_packages(
            apt="npm", dnf="npm", pacman="npm", zypper="npm", xbps="nodejs", apk="npm", brew="node"
        ),
    ),
    ToolSpec(
        "corepack",
        "corepack",
        BootstrapCategory.PACKAGE_REGISTRIES,
        "corepack",
        description="Node.js package-manager shim for pnpm and Yarn.",
        website="https://nodejs.org/api/corepack.html",
        packages=_packages(brew="node", npm="corepack"),
    ),
    ToolSpec(
        "pnpm",
        "pnpm",
        BootstrapCategory.PACKAGE_REGISTRIES,
        "pnpm",
        website="https://pnpm.io/",
        config_paths=("~/.npmrc", "~/.config/pnpm/rc"),
        # No pnpm package in Debian/Ubuntu or Fedora repositories.
        packages=_packages(pacman="pnpm", brew="pnpm", npm="pnpm"),
    ),
    ToolSpec(
        "yarn",
        "Yarn",
        BootstrapCategory.PACKAGE_REGISTRIES,
        "yarn",
        website="https://yarnpkg.com/",
        config_paths=("~/.yarnrc", "~/.yarnrc.yml"),
        packages=_packages(apt="yarnpkg", dnf="yarnpkg", pacman="yarn", brew="yarn", npm="yarn"),
    ),
    ToolSpec(
        "bun",
        "Bun",
        BootstrapCategory.PROGRAMMING_LANGUAGES,
        "bun",
        website="https://bun.sh/",
        config_paths=("~/.bunfig.toml",),
        packages=_packages(brew="bun", npm="bun"),
    ),
    ToolSpec(
        "rustc",
        "Rust",
        BootstrapCategory.PROGRAMMING_LANGUAGES,
        "rustc",
        website="https://www.rust-lang.org/",
        packages=_packages(
            apt="rustc",
            dnf="rust",
            pacman="rust",
            zypper="rust",
            xbps="rust",
            apk="rust",
            brew="rust",
            rustup="stable",
        ),
    ),
    ToolSpec(
        "cargo",
        "Cargo",
        BootstrapCategory.PACKAGE_REGISTRIES,
        "cargo",
        website="https://doc.rust-lang.org/cargo/",
        config_paths=("~/.cargo/config.toml", "~/.cargo/config"),
        packages=_packages(
            apt="cargo",
            dnf="cargo",
            pacman="cargo",
            zypper="cargo",
            xbps="cargo",
            apk="cargo",
            brew="rust",
        ),
    ),
    ToolSpec(
        "go",
        "Go",
        BootstrapCategory.PROGRAMMING_LANGUAGES,
        "go",
        version_args=("version",),
        website="https://go.dev/",
        config_paths=("~/.config/go/env",),
        packages=_packages(
            apt="golang-go",
            dnf="golang",
            pacman="go",
            zypper="go",
            xbps="go",
            apk="go",
            brew="go",
            mise="go@latest",
            asdf="golang latest",
        ),
    ),
    ToolSpec(
        "java",
        "Java",
        BootstrapCategory.PROGRAMMING_LANGUAGES,
        "java",
        version_args=("-version",),
        website="https://openjdk.org/",
        packages=_packages(
            apt="default-jdk",
            dnf="java-latest-openjdk-devel",
            pacman="jdk-openjdk",
            zypper="java-latest-openjdk-devel",
            xbps="openjdk",
            apk="openjdk17",
            brew="openjdk",
            sdkman="java",
        ),
    ),
    ToolSpec(
        "dotnet",
        ".NET",
        BootstrapCategory.PROGRAMMING_LANGUAGES,
        "dotnet",
        website="https://dotnet.microsoft.com/",
        packages=_packages(
            apt="dotnet-sdk-8.0", dnf="dotnet-sdk-8.0", pacman="dotnet-sdk", brew="dotnet"
        ),
    ),
    ToolSpec(
        "php",
        "PHP",
        BootstrapCategory.PROGRAMMING_LANGUAGES,
        "php",
        website="https://www.php.net/",
        packages=_packages(
            apt="php-cli",
            dnf="php-cli",
            pacman="php",
            zypper="php8",
            xbps="php",
            apk="php",
            brew="php",
        ),
    ),
    ToolSpec(
        "ruby",
        "Ruby",
        BootstrapCategory.PROGRAMMING_LANGUAGES,
        "ruby",
        website="https://www.ruby-lang.org/",
        packages=_packages(
            apt="ruby",
            dnf="ruby",
            pacman="ruby",
            zypper="ruby",
            xbps="ruby",
            apk="ruby",
            brew="ruby",
            mise="ruby@latest",
            asdf="ruby latest",
        ),
    ),
    ToolSpec(
        "gcc",
        "GCC",
        BootstrapCategory.COMPILERS,
        "gcc",
        website="https://gcc.gnu.org/",
        packages=_packages(
            apt="gcc", dnf="gcc", pacman="gcc", zypper="gcc", xbps="gcc", apk="gcc", brew="gcc"
        ),
    ),
    ToolSpec(
        "clang",
        "Clang",
        BootstrapCategory.COMPILERS,
        "clang",
        website="https://clang.llvm.org/",
        packages=_packages(
            apt="clang",
            dnf="clang",
            pacman="clang",
            zypper="clang",
            xbps="clang",
            apk="clang",
            brew="llvm",
        ),
    ),
    ToolSpec(
        "make",
        "Make",
        BootstrapCategory.BUILD_SYSTEMS,
        "make",
        website="https://www.gnu.org/software/make/",
        packages=_packages(
            apt="make",
            dnf="make",
            pacman="make",
            zypper="make",
            xbps="make",
            apk="make",
            brew="make",
        ),
    ),
    ToolSpec(
        "cmake",
        "CMake",
        BootstrapCategory.BUILD_SYSTEMS,
        "cmake",
        website="https://cmake.org/",
        packages=_packages(
            apt="cmake",
            dnf="cmake",
            pacman="cmake",
            zypper="cmake",
            xbps="cmake",
            apk="cmake",
            brew="cmake",
        ),
    ),
    ToolSpec(
        "ninja",
        "Ninja",
        BootstrapCategory.BUILD_SYSTEMS,
        "ninja",
        website="https://ninja-build.org/",
        packages=_packages(
            apt="ninja-build",
            dnf="ninja-build",
            pacman="ninja",
            zypper="ninja",
            xbps="ninja",
            apk="ninja",
            brew="ninja",
        ),
    ),
    ToolSpec(
        "docker",
        "Docker",
        BootstrapCategory.CONTAINERS,
        "docker",
        description="Docker CLI and engine client for container workflows.",
        verification_args=("info",),
        website="https://docs.docker.com/engine/",
        config_paths=("~/.docker/config.json", "/etc/docker/daemon.json"),
        tool_dependencies=(
            ToolDependency(
                "docker-compose", "Docker Compose is required for compose.yml workflows."
            ),
            ToolDependency(
                "docker-buildx", "Buildx is required for modern multi-platform Docker builds."
            ),
        ),
        packages=_packages(
            apt="docker.io",
            dnf="moby-engine",
            pacman="docker",
            zypper="docker",
            xbps="docker",
            apk="docker",
            brew="docker",
        ),
    ),
    ToolSpec(
        "docker-compose",
        "Docker Compose",
        BootstrapCategory.CONTAINERS,
        "docker-compose",
        description="Compose CLI for multi-container Docker applications.",
        website="https://docs.docker.com/compose/",
        packages=_packages(
            apt="docker-compose-v2",
            dnf="docker-compose",
            pacman="docker-compose",
            zypper="docker-compose",
            brew="docker-compose",
        ),
    ),
    ToolSpec(
        "docker-buildx",
        "Docker Buildx",
        BootstrapCategory.CONTAINERS,
        "docker-buildx",
        description="Docker BuildKit frontend for advanced and multi-platform builds.",
        website="https://docs.docker.com/buildx/working-with-buildx/",
        packages=_packages(
            apt="docker-buildx",
            dnf="docker-buildx",
            pacman="docker-buildx",
            brew="docker-buildx",
        ),
    ),
    ToolSpec(
        "podman",
        "Podman",
        BootstrapCategory.CONTAINERS,
        "podman",
        website="https://podman.io/",
        config_paths=("~/.config/containers/containers.conf", "/etc/containers/containers.conf"),
        packages=_packages(
            apt="podman",
            dnf="podman",
            rpm_ostree="podman",
            pacman="podman",
            zypper="podman",
            xbps="podman",
            apk="podman",
            brew="podman",
        ),
    ),
    ToolSpec(
        "distrobox",
        "Distrobox",
        BootstrapCategory.CONTAINERS,
        "distrobox",
        website="https://distrobox.it/",
        packages=_packages(
            apt="distrobox",
            dnf="distrobox",
            pacman="distrobox",
            zypper="distrobox",
            xbps="distrobox",
            brew="distrobox",
        ),
    ),
    ToolSpec(
        "kubectl",
        "kubectl",
        BootstrapCategory.DEVOPS,
        "kubectl",
        version_args=("version", "--client=true"),
        description="Kubernetes command-line client.",
        website="https://kubernetes.io/docs/tasks/tools/",
        config_paths=("~/.kube/config",),
        tool_dependencies=(
            ToolDependency(
                "helm",
                "Helm is commonly required for Kubernetes package workflows.",
                required=False,
            ),
            ToolDependency(
                "docker",
                "A container runtime is useful for local Kubernetes workflows.",
                required=False,
            ),
            ToolDependency(
                "podman",
                "Podman can provide a local container runtime.",
                required=False,
            ),
        ),
        # Debian/Ubuntu ship no kubectl package; it comes from the Kubernetes apt repo.
        packages=_packages(
            dnf="kubernetes-client", pacman="kubectl", brew="kubectl", snap="kubectl"
        ),
    ),
    ToolSpec(
        "helm",
        "Helm",
        BootstrapCategory.DEVOPS,
        "helm",
        website="https://helm.sh/",
        config_paths=("~/.config/helm/repositories.yaml",),
        # Debian/Ubuntu ship no helm package; it comes from the Helm apt repo or snap.
        packages=_packages(dnf="helm", pacman="helm", brew="helm", snap="helm"),
    ),
    ToolSpec(
        "terraform",
        "Terraform",
        BootstrapCategory.DEVOPS,
        "terraform",
        website="https://developer.hashicorp.com/terraform",
        config_paths=("~/.terraformrc",),
        # Neither Debian/Ubuntu nor Fedora package Terraform; HashiCorp's own repo does.
        packages=_packages(pacman="terraform", brew="terraform"),
    ),
    ToolSpec(
        "ansible",
        "Ansible",
        BootstrapCategory.DEVOPS,
        "ansible",
        website="https://www.ansible.com/",
        config_paths=("~/.ansible.cfg", "/etc/ansible/ansible.cfg"),
        packages=_packages(
            apt="ansible",
            dnf="ansible",
            pacman="ansible",
            zypper="ansible",
            brew="ansible",
            pipx="ansible",
        ),
    ),
    ToolSpec(
        "gh",
        "GitHub CLI",
        BootstrapCategory.CLOUD_CLIS,
        "gh",
        website="https://cli.github.com/",
        config_paths=("~/.config/gh/hosts.yml", "~/.config/gh/config.yml"),
        packages=_packages(apt="gh", dnf="gh", pacman="github-cli", brew="gh"),
    ),
    ToolSpec(
        "aws",
        "AWS CLI",
        BootstrapCategory.CLOUD_CLIS,
        "aws",
        website="https://aws.amazon.com/cli/",
        config_paths=("~/.aws/config", "~/.aws/credentials"),
        packages=_packages(brew="awscli", pipx="awscli", snap="aws-cli"),
    ),
    ToolSpec(
        "az",
        "Azure CLI",
        BootstrapCategory.CLOUD_CLIS,
        "az",
        website="https://learn.microsoft.com/cli/azure/",
        config_paths=("~/.azure/config",),
        # Debian/Ubuntu ship no azure-cli package; it comes from Microsoft's apt repo.
        packages=_packages(dnf="azure-cli", brew="azure-cli"),
    ),
    ToolSpec(
        "gcloud",
        "Google Cloud CLI",
        BootstrapCategory.CLOUD_CLIS,
        "gcloud",
        website="https://cloud.google.com/sdk",
        config_paths=("~/.config/gcloud/configurations",),
        packages=_packages(brew="google-cloud-sdk", snap="google-cloud-cli"),
    ),
    ToolSpec(
        "code",
        "Visual Studio Code",
        BootstrapCategory.EDITORS,
        "code",
        website="https://code.visualstudio.com/",
        config_paths=("~/.config/Code/User/settings.json",),
        packages=_packages(snap="code", flatpak="com.visualstudio.code", brew="visual-studio-code"),
    ),
    ToolSpec(
        "vim",
        "Vim",
        BootstrapCategory.EDITORS,
        "vim",
        website="https://www.vim.org/",
        config_paths=("~/.vimrc", "~/.vim/vimrc"),
        packages=_packages(
            apt="vim",
            dnf="vim-enhanced",
            pacman="vim",
            zypper="vim",
            xbps="vim",
            apk="vim",
            brew="vim",
        ),
    ),
    ToolSpec(
        "nvim",
        "Neovim",
        BootstrapCategory.EDITORS,
        "nvim",
        website="https://neovim.io/",
        config_paths=("~/.config/nvim/init.lua", "~/.config/nvim/init.vim"),
        packages=_packages(
            apt="neovim",
            dnf="neovim",
            pacman="neovim",
            zypper="neovim",
            xbps="neovim",
            apk="neovim",
            brew="neovim",
        ),
    ),
    ToolSpec(
        "psql",
        "PostgreSQL Client",
        BootstrapCategory.DATABASES,
        "psql",
        website="https://www.postgresql.org/",
        packages=_packages(
            apt="postgresql-client",
            dnf="postgresql",
            pacman="postgresql",
            zypper="postgresql",
            brew="libpq",
        ),
    ),
    ToolSpec(
        "mysql",
        "MySQL Client",
        BootstrapCategory.DATABASES,
        "mysql",
        website="https://www.mysql.com/",
        packages=_packages(
            apt="default-mysql-client",
            dnf="mysql",
            pacman="mysql",
            zypper="mysql-client",
            brew="mysql-client",
        ),
    ),
    ToolSpec(
        "sqlite3",
        "SQLite",
        BootstrapCategory.DATABASES,
        "sqlite3",
        website="https://sqlite.org/",
        packages=_packages(
            apt="sqlite3",
            dnf="sqlite",
            pacman="sqlite",
            zypper="sqlite3",
            xbps="sqlite",
            apk="sqlite",
            brew="sqlite",
        ),
    ),
    ToolSpec(
        "redis-cli",
        "Redis CLI",
        BootstrapCategory.DATABASES,
        "redis-cli",
        website="https://redis.io/",
        packages=_packages(
            apt="redis-tools", dnf="redis", pacman="redis", zypper="redis", brew="redis"
        ),
    ),
    ToolSpec(
        "ssh",
        "OpenSSH",
        BootstrapCategory.SSH,
        "ssh",
        version_args=("-V",),
        website="https://www.openssh.com/",
        config_paths=("~/.ssh/config",),
        packages=_packages(
            apt="openssh-client",
            dnf="openssh-clients",
            pacman="openssh",
            zypper="openssh",
            xbps="openssh",
            apk="openssh",
            brew="openssh",
        ),
    ),
    ToolSpec(
        "gpg",
        "GnuPG",
        BootstrapCategory.GPG,
        "gpg",
        website="https://gnupg.org/",
        config_paths=("~/.gnupg/gpg.conf",),
        packages=_packages(
            apt="gnupg",
            dnf="gnupg2",
            pacman="gnupg",
            zypper="gpg2",
            xbps="gnupg2",
            apk="gnupg",
            brew="gnupg",
        ),
    ),
    ToolSpec(
        "ufw",
        "UFW",
        BootstrapCategory.SECURITY,
        "ufw",
        website="https://wiki.ubuntu.com/UncomplicatedFirewall",
        packages=_packages(apt="ufw", pacman="ufw", zypper="ufw"),
    ),
    ToolSpec(
        "nmap",
        "Nmap",
        BootstrapCategory.SECURITY,
        "nmap",
        website="https://nmap.org/",
        packages=_packages(
            apt="nmap",
            dnf="nmap",
            pacman="nmap",
            zypper="nmap",
            xbps="nmap",
            apk="nmap",
            brew="nmap",
        ),
    ),
    ToolSpec(
        "htop",
        "htop",
        BootstrapCategory.MONITORING,
        "htop",
        website="https://htop.dev/",
        packages=_packages(
            apt="htop",
            dnf="htop",
            pacman="htop",
            zypper="htop",
            xbps="htop",
            apk="htop",
            brew="htop",
        ),
    ),
    ToolSpec(
        "glances",
        "Glances",
        BootstrapCategory.MONITORING,
        "glances",
        website="https://nicolargo.github.io/glances/",
        packages=_packages(
            apt="glances", dnf="glances", pacman="glances", brew="glances", pipx="glances"
        ),
    ),
    ToolSpec(
        "jq",
        "jq",
        BootstrapCategory.TERMINAL_UTILITIES,
        "jq",
        website="https://jqlang.github.io/jq/",
        packages=_packages(
            apt="jq", dnf="jq", pacman="jq", zypper="jq", xbps="jq", apk="jq", brew="jq"
        ),
    ),
    ToolSpec(
        "ripgrep",
        "ripgrep",
        BootstrapCategory.TERMINAL_UTILITIES,
        "rg",
        website="https://github.com/BurntSushi/ripgrep",
        packages=_packages(
            apt="ripgrep",
            dnf="ripgrep",
            pacman="ripgrep",
            zypper="ripgrep",
            xbps="ripgrep",
            apk="ripgrep",
            brew="ripgrep",
        ),
    ),
    ToolSpec(
        "fd",
        "fd",
        BootstrapCategory.TERMINAL_UTILITIES,
        "fd",
        website="https://github.com/sharkdp/fd",
        packages=_packages(apt="fd-find", dnf="fd-find", pacman="fd", zypper="fd", brew="fd"),
    ),
    ToolSpec(
        "ruff",
        "Ruff",
        BootstrapCategory.PACKAGE_REGISTRIES,
        "ruff",
        website="https://docs.astral.sh/ruff/",
        # No ruff package in Debian/Ubuntu repositories.
        packages=_packages(dnf="ruff", pacman="ruff", brew="ruff", pipx="ruff", pip="ruff"),
    ),
    ToolSpec(
        "fzf",
        "fzf",
        BootstrapCategory.SHELL_ENHANCEMENTS,
        "fzf",
        website="https://github.com/junegunn/fzf",
        packages=_packages(apt="fzf", dnf="fzf", pacman="fzf", zypper="fzf", brew="fzf"),
    ),
    ToolSpec(
        "starship",
        "Starship",
        BootstrapCategory.SHELL_ENHANCEMENTS,
        "starship",
        website="https://starship.rs/",
        config_paths=("~/.config/starship.toml",),
        # No starship package in Debian/Ubuntu or Fedora repositories.
        packages=_packages(pacman="starship", brew="starship", cargo="starship"),
    ),
    ToolSpec(
        "mise",
        "mise",
        BootstrapCategory.VERSION_MANAGERS,
        "mise",
        website="https://mise.jdx.dev/",
        config_paths=("~/.config/mise/config.toml", "~/.tool-versions"),
        packages=_packages(brew="mise", cargo="mise"),
    ),
    ToolSpec(
        "asdf",
        "asdf",
        BootstrapCategory.VERSION_MANAGERS,
        "asdf",
        website="https://asdf-vm.com/",
        config_paths=("~/.asdfrc", "~/.tool-versions"),
        # No asdf package in Debian/Ubuntu or Fedora repositories.
        packages=_packages(pacman="asdf-vm", brew="asdf"),
    ),
    ToolSpec(
        "flutter",
        "Flutter",
        BootstrapCategory.MOBILE_DEVELOPMENT,
        "flutter",
        description="Flutter SDK command for mobile and cross-platform applications.",
        verification_args=("doctor",),
        website="https://flutter.dev/",
        tool_dependencies=(
            ToolDependency("git", "Flutter uses Git for SDK and package workflows."),
            ToolDependency("java", "Android builds require a Java runtime."),
            ToolDependency("adb", "Android device and emulator workflows require platform tools."),
            ToolDependency(
                "android-sdkmanager", "Android SDK packages are managed with sdkmanager."
            ),
            ToolDependency("code", "VS Code is a common Flutter editor.", required=False),
        ),
        packages=_packages(snap="flutter", brew="flutter", asdf="flutter latest"),
    ),
    ToolSpec(
        "android-sdkmanager",
        "Android SDK Manager",
        BootstrapCategory.MOBILE_DEVELOPMENT,
        "sdkmanager",
        description="Android SDK command-line package manager.",
        website="https://developer.android.com/tools/sdkmanager",
        packages=_packages(brew="android-commandlinetools"),
    ),
    ToolSpec(
        "adb",
        "Android Debug Bridge",
        BootstrapCategory.MOBILE_DEVELOPMENT,
        "adb",
        website="https://developer.android.com/tools/adb",
        packages=_packages(
            apt="adb",
            dnf="android-tools",
            pacman="android-tools",
            zypper="android-tools",
            brew="android-platform-tools",
        ),
    ),
    ToolSpec(
        "ollama",
        "Ollama",
        BootstrapCategory.AI,
        "ollama",
        website="https://ollama.com/",
        config_paths=("~/.ollama",),
        packages=_packages(brew="ollama"),
    ),
    ToolSpec(
        "nvcc",
        "CUDA Compiler",
        BootstrapCategory.AI,
        "nvcc",
        website="https://developer.nvidia.com/cuda-toolkit",
        packages=_packages(apt="nvidia-cuda-toolkit", dnf="cuda-toolkit", pacman="cuda"),
    ),
    ToolSpec(
        "gdb",
        "GDB",
        BootstrapCategory.DEBUGGERS,
        "gdb",
        website="https://sourceware.org/gdb/",
        packages=_packages(
            apt="gdb", dnf="gdb", pacman="gdb", zypper="gdb", xbps="gdb", apk="gdb", brew="gdb"
        ),
    ),
    ToolSpec(
        "strace",
        "strace",
        BootstrapCategory.DEBUGGERS,
        "strace",
        website="https://strace.io/",
        packages=_packages(
            apt="strace",
            dnf="strace",
            pacman="strace",
            zypper="strace",
            xbps="strace",
            apk="strace",
        ),
    ),
    ToolSpec(
        "radare2",
        "radare2",
        BootstrapCategory.REVERSE_ENGINEERING,
        "r2",
        website="https://rada.re/n/",
        packages=_packages(
            apt="radare2", dnf="radare2", pacman="radare2", zypper="radare2", brew="radare2"
        ),
    ),
    ToolSpec(
        "godot",
        "Godot",
        BootstrapCategory.GAME_DEVELOPMENT,
        "godot",
        website="https://godotengine.org/",
        packages=_packages(
            apt="godot3", dnf="godot", pacman="godot", flatpak="org.godotengine.Godot", brew="godot"
        ),
    ),
    ToolSpec(
        "systemctl",
        "systemd",
        BootstrapCategory.SYSTEM_SERVICES,
        "systemctl",
        website="https://systemd.io/",
        packages=_packages(apt="systemd", dnf="systemd", pacman="systemd", zypper="systemd"),
    ),
)


BOOTSTRAP_PROFILES: tuple[BootstrapProfile, ...] = (
    BootstrapProfile(
        "general",
        "General Developer",
        "Core workstation tools for most projects.",
        (
            "git",
            "curl",
            "wget",
            "python",
            "pip",
            "node",
            "npm",
            "docker",
            "docker-compose",
            "vim",
            "jq",
            "ripgrep",
        ),
    ),
    BootstrapProfile(
        "frontend",
        "Frontend",
        "JavaScript and browser-oriented development.",
        ("git", "node", "npm", "corepack", "pnpm", "yarn", "bun", "code", "ripgrep", "fzf"),
    ),
    BootstrapProfile(
        "backend",
        "Backend",
        "API and service development with common databases.",
        (
            "git",
            "python",
            "pipx",
            "node",
            "go",
            "java",
            "docker",
            "docker-compose",
            "psql",
            "mysql",
            "redis-cli",
        ),
    ),
    BootstrapProfile(
        "python",
        "Python",
        "Python application and automation development.",
        ("git", "python", "pip", "pipx", "sqlite3", "ruff", "jq"),
    ),
    BootstrapProfile(
        "node",
        "Node",
        "Node.js service and frontend tooling.",
        ("git", "node", "npm", "corepack", "pnpm", "yarn", "bun"),
    ),
    BootstrapProfile(
        "rust",
        "Rust",
        "Rust compiler, Cargo, and native build tools.",
        ("git", "rustc", "cargo", "gcc", "gdb", "cmake"),
    ),
    BootstrapProfile(
        "go",
        "Go",
        "Go toolchain and common backend utilities.",
        ("git", "go", "docker", "psql", "jq"),
    ),
    BootstrapProfile(
        "java", "Java", "Java runtime and build ecosystem.", ("git", "java", "docker", "psql")
    ),
    BootstrapProfile(
        "flutter",
        "Flutter",
        "Flutter and Android command-line development.",
        ("git", "flutter", "adb", "android-sdkmanager", "java", "code"),
    ),
    BootstrapProfile(
        "android",
        "Android",
        "Android platform tools and Java runtime.",
        ("git", "adb", "android-sdkmanager", "java", "code"),
    ),
    BootstrapProfile(
        "data-science",
        "Data Science",
        "Python, notebooks, and database clients.",
        ("git", "python", "pip", "pipx", "sqlite3", "psql"),
    ),
    BootstrapProfile(
        "ai",
        "AI Engineer",
        "Local AI and GPU-oriented tooling.",
        ("git", "python", "pipx", "ollama", "nvcc", "docker"),
    ),
    BootstrapProfile(
        "security",
        "Cyber Security",
        "Safe local security and reverse-engineering tools.",
        ("git", "nmap", "gpg", "ssh", "strace", "gdb", "radare2"),
    ),
    BootstrapProfile(
        "devops",
        "DevOps",
        "Container, Kubernetes, IaC, and cloud CLI tooling.",
        (
            "git",
            "docker",
            "docker-compose",
            "docker-buildx",
            "podman",
            "kubectl",
            "helm",
            "terraform",
            "ansible",
            "gh",
            "aws",
            "az",
            "gcloud",
        ),
    ),
    BootstrapProfile(
        "cloud",
        "Cloud Engineer",
        "Cloud CLIs and infrastructure tooling.",
        ("git", "gh", "aws", "az", "gcloud", "terraform", "kubectl"),
    ),
    BootstrapProfile(
        "game",
        "Game Developer",
        "Native build tools and Godot.",
        ("git", "gcc", "clang", "cmake", "ninja", "godot"),
    ),
)
