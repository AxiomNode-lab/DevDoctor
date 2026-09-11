"""Rich output for bootstrap inventory commands."""

from __future__ import annotations

from collections.abc import Iterable

from rich import box
from rich.console import Group
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from devdoctor import __version__
from devdoctor.bootstrap import (
    BootstrapCategory,
    BootstrapInventory,
    BootstrapProfile,
    HealthState,
    InstallPlan,
    ToolDetection,
)


def bootstrap_group(
    inventory: BootstrapInventory,
    *,
    show_missing_only: bool = False,
) -> Group:
    """Render a full bootstrap inventory."""

    renderables: list[object] = [
        bootstrap_header(inventory),
        system_context_panel(inventory),
    ]
    path_panel = path_analysis_panel(inventory)
    if path_panel is not None:
        renderables.append(path_panel)

    for category, detections in inventory.categories().items():
        visible = tuple(
            detection
            for detection in detections
            if not show_missing_only or not detection.installed
        )
        if visible:
            renderables.append(category_table(category, visible))

    plans = tuple(
        detection.install_plan
        for detection in inventory.missing
        if detection.install_plan is not None
    )
    if plans:
        renderables.append(install_plans_table(plans))

    needs_attention = inventory.needs_attention
    if needs_attention:
        renderables.append(repair_suggestions_table(needs_attention))

    return Group(*renderables)


def bootstrap_header(inventory: BootstrapInventory) -> Panel:
    """Render the command header and inventory counts."""

    summary = inventory.to_dict()["summary"]
    grid = Table.grid(expand=True)
    grid.add_column(ratio=2)
    grid.add_column(justify="right", no_wrap=True)

    title = Text()
    title.append("Dev", style="brand")
    title.append("Doctor", style="bold white")
    title.append(f"  v{__version__}", style="muted")
    title.append("\nLinux developer workstation bootstrap", style="tagline")

    counts = Text()
    counts.append(f"{summary['installed']} installed", style="success")
    counts.append("  ")
    counts.append(f"{summary['missing']} missing", style="error")
    counts.append("  ")
    counts.append(f"{summary['warnings']} warnings", style="warning")
    counts.append("  ")
    counts.append(f"{summary['broken']} broken", style="error")

    grid.add_row(title, counts)
    return Panel(grid, border_style="bright_cyan", box=box.SIMPLE, padding=(1, 2))


def system_context_panel(inventory: BootstrapInventory) -> Panel:
    """Render detected host context."""

    system = inventory.system
    managers = [
        str(manager.get("id"))
        for manager in system.get("package_managers", ())
        if isinstance(manager, dict) and manager.get("installed") is True
    ]

    table = Table.grid(expand=True, padding=(0, 1))
    table.add_column(style="muted", no_wrap=True)
    table.add_column(ratio=1)
    table.add_column(style="muted", no_wrap=True)
    table.add_column(ratio=1)
    table.add_row(
        "OS", str(system.get("distribution", "unknown")), "Arch", str(system.get("architecture"))
    )
    table.add_row(
        "Shell",
        str(system.get("shell", "unknown")),
        "Desktop",
        str(system.get("desktop_environment")),
    )
    table.add_row(
        "Session",
        str(system.get("session_type", "unknown")),
        "Terminal",
        str(system.get("terminal")),
    )
    table.add_row(
        "Virtualization",
        str(system.get("virtualization")),
        "Container",
        str(system.get("is_container")),
    )
    table.add_row("WSL", str(system.get("is_wsl")), "Sudo", str(system.get("can_sudo")))
    table.add_row(
        "Managers",
        ", ".join(managers) or "none detected",
        "PATH issues",
        str(system.get("path_issue_count", 0)),
    )
    return Panel(table, title="Host", border_style="bright_black", box=box.SIMPLE)


def category_table(
    category: BootstrapCategory,
    detections: Iterable[ToolDetection],
) -> Table:
    """Render tools in one bootstrap category."""

    table = Table(
        title=category.value,
        box=box.SIMPLE,
        border_style="bright_black",
        header_style="bold white",
        expand=True,
        show_lines=False,
    )
    table.add_column("", width=2, no_wrap=True)
    table.add_column("Health", no_wrap=True, ratio=1)
    table.add_column("Tool", min_width=14, ratio=2)
    table.add_column("Version", no_wrap=True, ratio=1)
    table.add_column("Path", ratio=3, overflow="fold")
    table.add_column("Install", ratio=3, overflow="fold")

    for detection in detections:
        table.add_row(
            _status_icon(detection),
            _health_text(detection.health),
            detection.spec.title,
            detection.version or "",
            detection.executable_path or "",
            _plan_text(detection),
        )
    return table


def install_plans_table(plans: Iterable[InstallPlan]) -> Table:
    """Render missing-tool install plans."""

    table = Table(
        title="Install plans",
        box=box.SIMPLE,
        border_style="bright_black",
        header_style="bold white",
        expand=True,
    )
    table.add_column("Tool", min_width=14)
    table.add_column("Manager", no_wrap=True)
    table.add_column("Package", no_wrap=True)
    table.add_column("Risk", ratio=1)
    table.add_column("Command", ratio=3, overflow="fold")
    table.add_column("Why", ratio=3, overflow="fold")
    table.add_column("Dry run", ratio=3, overflow="fold")

    for plan in plans:
        table.add_row(
            plan.tool_title,
            plan.manager,
            plan.package_name,
            plan.risk.split(" - ", 1)[0],
            " ".join(plan.command),
            plan.manager_reason,
            " ".join(plan.dry_run_command) if plan.dry_run_command else "",
        )
    return table


def repair_suggestions_table(detections: Iterable[ToolDetection]) -> Table:
    """Render real repair suggestions for detected local problems."""

    table = Table(
        title="Repair suggestions",
        box=box.SIMPLE,
        border_style="yellow",
        header_style="bold white",
        expand=True,
    )
    table.add_column("Tool", min_width=14, ratio=1)
    table.add_column("Risk", no_wrap=True)
    table.add_column("Details", ratio=4, overflow="fold")
    table.add_column("Repair", ratio=3, overflow="fold")

    for detection in detections:
        for recommendation in detection.repair_recommendations:
            details = "\n".join(
                item
                for item in (
                    recommendation.problem,
                    recommendation.reason,
                    (
                        f"Verify: {' '.join(recommendation.verification_command)}"
                        if recommendation.verification_command
                        else ""
                    ),
                )
                if item
            )
            table.add_row(
                detection.spec.title,
                recommendation.risk,
                details,
                recommendation.command_text,
            )
    return table


def path_analysis_panel(inventory: BootstrapInventory) -> Panel | None:
    """Render PATH analysis when issues or shadowed executables exist."""

    path_analysis = inventory.system.get("path_analysis")
    if not isinstance(path_analysis, dict):
        return None
    issues = path_analysis.get("issues", ())
    shadowed = path_analysis.get("shadowed_executables", ())
    if not issues and not shadowed:
        return None

    table = Table(
        title="PATH analysis",
        box=box.SIMPLE,
        border_style="yellow",
        header_style="bold white",
        expand=True,
    )
    table.add_column("Type", no_wrap=True)
    table.add_column("Path", ratio=2, overflow="fold")
    table.add_column("Problem", ratio=3, overflow="fold")
    table.add_column("Recommendation", ratio=3, overflow="fold")

    if isinstance(issues, list):
        for issue in issues:
            if not isinstance(issue, dict):
                continue
            recommendation = str(issue.get("recommendation") or "")
            export_command = issue.get("export_command")
            if export_command:
                recommendation = f"{recommendation}\n{export_command}"
            table.add_row(
                str(issue.get("kind") or ""),
                str(issue.get("path") or ""),
                str(issue.get("problem") or ""),
                recommendation,
            )
    if isinstance(shadowed, list):
        for record in shadowed:
            if not isinstance(record, dict):
                continue
            table.add_row(
                "shadowed",
                str(record.get("primary_path") or ""),
                f"{record.get('executable')} appears more than once in PATH.",
                ", ".join(str(path) for path in record.get("shadowed_paths", ()) or ()),
            )
    cleanup_command = path_analysis.get("cleanup_command")
    if not cleanup_command:
        return Panel(table, title="PATH", border_style="yellow", box=box.SIMPLE)
    cleanup = Text.assemble(
        ("Cleaned PATH (dead entries and duplicates removed):\n", "bold"),
        (str(cleanup_command), "cyan"),
    )
    return Panel(Group(table, cleanup), title="PATH", border_style="yellow", box=box.SIMPLE)


def search_results_table(
    inventory: BootstrapInventory,
    profiles: Iterable[BootstrapProfile],
) -> Table:
    """Render rich catalog search results."""

    profiles_by_tool: dict[str, list[str]] = {}
    for profile in profiles:
        for tool_id in profile.tool_ids:
            profiles_by_tool.setdefault(tool_id, []).append(profile.id)

    table = Table(
        title="Search results",
        box=box.SIMPLE,
        border_style="bright_black",
        header_style="bold white",
        expand=True,
    )
    table.add_column("Tool", min_width=14, ratio=1)
    table.add_column("Health", no_wrap=True)
    table.add_column("Details", ratio=4, overflow="fold")
    table.add_column("Install", ratio=3, overflow="fold")

    for detection in inventory.detections:
        dependencies = ", ".join(
            f"{status.tool_id}{'' if status.required else ' (optional)'}"
            for status in detection.dependency_status
        )
        details = "\n".join(
            item
            for item in (
                detection.spec.description,
                f"Category: {detection.spec.category.value}",
                f"Version: {detection.version}" if detection.version else "",
                (
                    f"Manager: {detection.installation_method or detection.package_manager}"
                    if detection.installation_method or detection.package_manager
                    else ""
                ),
                f"Profiles: {', '.join(profiles_by_tool.get(detection.spec.id, ()))}",
                f"Dependencies: {dependencies}" if dependencies else "",
                detection.spec.website,
            )
            if item
        )
        table.add_row(
            detection.spec.title,
            detection.health.value,
            details,
            _plan_text(detection),
        )
    return table


def profiles_table(profiles: Iterable[BootstrapProfile]) -> Table:
    """Render available bootstrap profiles."""

    table = Table(
        title="Profiles",
        box=box.SIMPLE,
        border_style="bright_black",
        header_style="bold white",
        expand=True,
    )
    table.add_column("Profile", no_wrap=True)
    table.add_column("Description", ratio=2)
    table.add_column("Tools", ratio=3, overflow="fold")
    for profile in profiles:
        table.add_row(profile.id, profile.description, ", ".join(profile.tool_ids))
    return table


def compact_inventory_status(inventory: BootstrapInventory) -> str:
    """Return a compact one-line inventory summary for scripts."""

    summary = inventory.to_dict()["summary"]
    return (
        f"installed={summary['installed']} missing={summary['missing']} "
        f"warnings={summary['warnings']} broken={summary['broken']} total={summary['total']}"
    )


def compact_plan_status(plans: Iterable[InstallPlan]) -> str:
    """Return install commands as compact script-friendly lines."""

    return "\n".join(f"{plan.tool_id}: {plan.command_text}" for plan in plans)


def _status_icon(detection: ToolDetection) -> Text:
    if detection.health in {HealthState.BROKEN, HealthState.WARNING}:
        return Text("!", style="warning")
    if detection.installed:
        return Text("✓", style="success")
    return Text("✗", style="error")


def _health_text(health: HealthState) -> Text:
    style = {
        HealthState.READY: "success",
        HealthState.MISSING: "error",
        HealthState.WARNING: "warning",
        HealthState.BROKEN: "error",
    }[health]
    return Text(health.value, style=style)


def _plan_text(detection: ToolDetection) -> str:
    if detection.installed:
        return ""
    if detection.install_plan is None:
        if detection.spec.website:
            return f"No supported local manager detected; see {detection.spec.website}"
        return "No supported local manager detected"
    return detection.install_plan.command_text
