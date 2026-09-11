"""Typer command-line interface for DevDoctor."""

from __future__ import annotations

import subprocess
import sys
import time
from collections.abc import Iterable, Mapping, Sequence
from datetime import UTC, datetime
from pathlib import Path
from typing import Annotated

import typer
from rich.console import Console

from devdoctor import __copyright__, __license__, __version__
from devdoctor.bootstrap import (
    BOOTSTRAP_PROFILES,
    BootstrapCategory,
    BootstrapInventory,
    BootstrapProfile,
    InstallPlan,
    ToolSpec,
    bootstrap_inventory,
    get_bootstrap_tools,
    install_plan_for_spec,
    profile_by_id,
    specs_for_profile,
)
from devdoctor.doctor import DevDoctor
from devdoctor.exporters.bootstrap import (
    render_bootstrap_json,
    render_bootstrap_markdown,
    write_bootstrap_html,
    write_bootstrap_json,
    write_bootstrap_markdown,
)
from devdoctor.exporters.html import write_html_report
from devdoctor.exporters.json import render_json, write_json_report
from devdoctor.exporters.markdown import write_markdown_report
from devdoctor.exporters.pdf import write_pdf_report
from devdoctor.host_policy import system_is_atomic
from devdoctor.models import HealthReport
from devdoctor.operations import OperationLogRecord, append_operation_log
from devdoctor.paths import latest_report_path, operation_log_path
from devdoctor.ui.bootstrap import (
    bootstrap_group,
    compact_inventory_status,
    compact_plan_status,
    profiles_table,
    repair_suggestions_table,
    search_results_table,
)
from devdoctor.ui.logo import banner
from devdoctor.ui.progress import create_progress
from devdoctor.ui.table import compact_status, report_group
from devdoctor.ui.theme import create_console
from devdoctor.utils import run_command

app = typer.Typer(
    name="devdoctor",
    help=(
        "[bold cyan]DevDoctor[/bold cyan] prepares and repairs Linux developer "
        "workstations with real local inventory and safe install plans."
    ),
    epilog=(
        "Examples:\n"
        "  devdoctor\n"
        "  devdoctor check --profile devops\n"
        "  devdoctor install git docker --dry-run\n"
        "  devdoctor repair docker\n"
        "  devdoctor search docker\n"
        "  devdoctor list profiles\n"
        "  devdoctor export json --output inventory.json"
    ),
    add_completion=False,
    invoke_without_command=True,
    rich_markup_mode="rich",
    context_settings={"help_option_names": ["-h", "--help"]},
)
list_app = typer.Typer(help="List catalog data.", rich_markup_mode="rich")
cache_app = typer.Typer(help="Inspect and clean local development caches.", rich_markup_mode="rich")
app.add_typer(list_app, name="list")
app.add_typer(cache_app, name="cache")


@app.callback(invoke_without_command=True)
def main(
    ctx: typer.Context,
    version: Annotated[
        bool,
        typer.Option("--version", help="Show the DevDoctor version and exit."),
    ] = False,
    profile: Annotated[
        str | None,
        typer.Option("--profile", "-p", help="Limit inventory to a bootstrap profile."),
    ] = None,
    category: Annotated[
        str | None,
        typer.Option("--category", "-c", help="Limit inventory to a category name."),
    ] = None,
    output_json: Annotated[
        bool,
        typer.Option("--json", help="Print the bootstrap inventory as JSON."),
    ] = False,
    json_file: Annotated[
        Path | None,
        typer.Option("--json-file", help="Write bootstrap JSON inventory to this path."),
    ] = None,
    markdown_file: Annotated[
        Path | None,
        typer.Option("--markdown-file", help="Write bootstrap Markdown inventory to this path."),
    ] = None,
    html_file: Annotated[
        Path | None,
        typer.Option("--html-file", help="Write standalone bootstrap HTML inventory to this path."),
    ] = None,
    missing_only: Annotated[
        bool,
        typer.Option("--missing", help="Show only missing tools in terminal output."),
    ] = False,
    quiet: Annotated[
        bool,
        typer.Option("--quiet", "-q", help="Print only a compact final status line."),
    ] = False,
    no_color: Annotated[
        bool,
        typer.Option("--no-color", help="Disable terminal colors."),
    ] = False,
) -> None:
    """Run the default workstation bootstrap inventory."""

    console = create_console(no_color=no_color)
    if version:
        console.print(f"devdoctor {__version__}")
        console.print(f"{__copyright__}. {__license__} License.", style="dim")
        raise typer.Exit(code=0)

    if ctx.invoked_subcommand is not None:
        return

    _run_bootstrap_report(
        profile_id=profile,
        category_name=category,
        tool_ids=(),
        output_json=output_json,
        json_file=json_file,
        markdown_file=markdown_file,
        html_file=html_file,
        missing_only=missing_only,
        quiet=quiet,
        console=console,
    )


@app.command()
def check(
    tools: Annotated[
        list[str] | None,
        typer.Argument(help="Optional tool IDs to inspect, for example git docker node."),
    ] = None,
    profile: Annotated[
        str | None,
        typer.Option("--profile", "-p", help="Limit inventory to a bootstrap profile."),
    ] = None,
    category: Annotated[
        str | None,
        typer.Option("--category", "-c", help="Limit inventory to a category name."),
    ] = None,
    output_json: Annotated[
        bool,
        typer.Option("--json", help="Print the bootstrap inventory as JSON."),
    ] = False,
    missing_only: Annotated[
        bool,
        typer.Option("--missing", help="Show only missing tools in terminal output."),
    ] = False,
    quiet: Annotated[
        bool,
        typer.Option("--quiet", "-q", help="Print only a compact final status line."),
    ] = False,
    no_color: Annotated[
        bool,
        typer.Option("--no-color", help="Disable terminal colors."),
    ] = False,
) -> None:
    """Inspect workstation tools and package-manager install plans."""

    _run_bootstrap_report(
        profile_id=profile,
        category_name=category,
        tool_ids=tuple(tools or ()),
        output_json=output_json,
        json_file=None,
        markdown_file=None,
        html_file=None,
        missing_only=missing_only,
        quiet=quiet,
        console=create_console(no_color=no_color),
    )


@app.command()
def doctor(
    tools: Annotated[
        list[str] | None,
        typer.Argument(help="Optional tool IDs to inspect."),
    ] = None,
    profile: Annotated[
        str | None,
        typer.Option("--profile", "-p", help="Limit inventory to a bootstrap profile."),
    ] = None,
    no_color: Annotated[
        bool,
        typer.Option("--no-color", help="Disable terminal colors."),
    ] = False,
) -> None:
    """Alias for a full bootstrap check."""

    _run_bootstrap_report(
        profile_id=profile,
        category_name=None,
        tool_ids=tuple(tools or ()),
        output_json=False,
        json_file=None,
        markdown_file=None,
        html_file=None,
        missing_only=False,
        quiet=False,
        console=create_console(no_color=no_color),
    )


@app.command()
def verify(
    tools: Annotated[
        list[str] | None,
        typer.Argument(help="Optional tool IDs to verify."),
    ] = None,
    profile: Annotated[
        str | None,
        typer.Option("--profile", "-p", help="Verify all tools in a profile."),
    ] = None,
    quiet: Annotated[
        bool,
        typer.Option("--quiet", "-q", help="Print a compact status line."),
    ] = False,
    no_color: Annotated[
        bool,
        typer.Option("--no-color", help="Disable terminal colors."),
    ] = False,
) -> None:
    """Verify selected tools and exit non-zero when any are missing, warning, or broken."""

    console = create_console(no_color=no_color)
    inventory = _inventory_for(profile_id=profile, category_name=None, tool_ids=tuple(tools or ()))
    if quiet:
        console.print(compact_inventory_status(inventory))
    else:
        console.print(bootstrap_group(inventory))
    if inventory.missing or inventory.warnings or inventory.broken:
        raise typer.Exit(code=1)


@app.command()
def profiles(
    output_json: Annotated[
        bool,
        typer.Option("--json", help="Print profiles as JSON-compatible inventory data."),
    ] = False,
    no_color: Annotated[
        bool,
        typer.Option("--no-color", help="Disable terminal colors."),
    ] = False,
) -> None:
    """List built-in workstation profiles."""

    console = create_console(no_color=no_color)
    if output_json:
        inventory = bootstrap_inventory(include_ids=())
        sys.stdout.write(render_bootstrap_json(inventory))
        sys.stdout.write("\n")
        return
    console.print(profiles_table(BOOTSTRAP_PROFILES))


@app.command()
def search(
    query: Annotated[str, typer.Argument(help="Tool, category, package, or website text.")],
    no_color: Annotated[
        bool,
        typer.Option("--no-color", help="Disable terminal colors."),
    ] = False,
) -> None:
    """Search the local bootstrap catalog."""

    console = create_console(no_color=no_color)
    matches = tuple(_search_specs(query))
    if not matches:
        console.print(f"[error]No catalog tools matched '{query}'.[/error]")
        raise typer.Exit(code=1)
    inventory = bootstrap_inventory(
        include_ids=(spec.id for spec in matches),
        include_optional_dependencies=True,
    )
    console.print(search_results_table(inventory, BOOTSTRAP_PROFILES))


@app.command()
def install(
    tools: Annotated[
        list[str] | None,
        typer.Argument(help="Tool IDs to install, for example git docker node."),
    ] = None,
    profile: Annotated[
        str | None,
        typer.Option("--profile", "-p", help="Install missing tools from a profile."),
    ] = None,
    dry_run: Annotated[
        bool,
        typer.Option("--dry-run", help="Run package-manager simulation commands when available."),
    ] = False,
    apply: Annotated[
        bool,
        typer.Option("--apply", help="Execute install commands after confirmation."),
    ] = False,
    yes: Annotated[
        bool,
        typer.Option("--yes", "-y", help="Do not ask for per-command confirmation."),
    ] = False,
    quiet: Annotated[
        bool,
        typer.Option("--quiet", "-q", help="Print only install commands."),
    ] = False,
    no_color: Annotated[
        bool,
        typer.Option("--no-color", help="Disable terminal colors."),
    ] = False,
) -> None:
    """Preview or execute safe package-manager install plans."""

    console = create_console(no_color=no_color)
    inventory = _inventory_for(profile_id=profile, category_name=None, tool_ids=tuple(tools or ()))
    plans = tuple(
        detection.install_plan
        for detection in inventory.missing
        if detection.install_plan is not None
    )
    if quiet:
        console.print(compact_plan_status(plans))
    else:
        console.print(bootstrap_group(inventory, show_missing_only=True))

    if not plans:
        if not quiet:
            console.print(
                "[success]All selected tools are already installed or have no safe plan.[/success]"
            )
        return
    if not apply and not dry_run:
        if not quiet:
            console.print(
                "[muted]No changes made. Use --dry-run or --apply to execute commands.[/muted]"
            )
        return

    _execute_plans(plans, dry_run=dry_run, yes=yes, console=console)


@app.command()
def repair(
    tools: Annotated[
        list[str] | None,
        typer.Argument(help="Optional tool IDs to inspect for repair suggestions."),
    ] = None,
    profile: Annotated[
        str | None,
        typer.Option("--profile", "-p", help="Inspect all tools in a profile."),
    ] = None,
    no_color: Annotated[
        bool,
        typer.Option("--no-color", help="Disable terminal colors."),
    ] = False,
) -> None:
    """Show real repair suggestions for selected tools."""

    console = create_console(no_color=no_color)
    inventory = _inventory_for(profile_id=profile, category_name=None, tool_ids=tuple(tools or ()))
    if not inventory.needs_attention:
        console.print("[success]No repair suggestions for the selected tools.[/success]")
        return
    console.print(repair_suggestions_table(inventory.needs_attention))


@app.command()
def uninstall(
    tools: Annotated[
        list[str],
        typer.Argument(help="Tool IDs to remove using their detected package-manager plan."),
    ],
    apply: Annotated[
        bool,
        typer.Option("--apply", help="Execute rollback commands after confirmation."),
    ] = False,
    yes: Annotated[
        bool,
        typer.Option("--yes", "-y", help="Do not ask for per-command confirmation."),
    ] = False,
    no_color: Annotated[
        bool,
        typer.Option("--no-color", help="Disable terminal colors."),
    ] = False,
) -> None:
    """Preview or execute uninstall commands for catalog tools."""

    console = create_console(no_color=no_color)
    inventory = bootstrap_inventory(include_ids=())
    system = inventory.system
    specs = _resolve_tool_specs(tuple(tools))
    rollback_plans: list[InstallPlan] = []
    for spec in specs:
        plan = install_plan_for_spec(spec, system=system)
        if plan is not None and plan.rollback_command is not None:
            rollback_plans.append(
                InstallPlan(
                    tool_id=plan.tool_id,
                    tool_title=plan.tool_title,
                    manager=plan.manager,
                    command=plan.rollback_command,
                    explanation=f"Remove {plan.tool_title} using {plan.manager}.",
                    risk=plan.risk,
                    verify_command=(),
                )
            )

    if not rollback_plans:
        console.print("[error]No rollback commands are available for the selected tools.[/error]")
        raise typer.Exit(code=1)
    console.print(compact_plan_status(rollback_plans))
    if apply:
        _execute_plans(
            tuple(rollback_plans),
            dry_run=False,
            yes=yes,
            console=console,
            operation="uninstall",
        )
    else:
        console.print("[muted]No changes made. Use --apply to execute rollback commands.[/muted]")


@app.command()
def update(
    apply: Annotated[
        bool,
        typer.Option("--apply", help="Execute package-manager update commands after confirmation."),
    ] = False,
    yes: Annotated[
        bool,
        typer.Option("--yes", "-y", help="Do not ask for per-command confirmation."),
    ] = False,
    no_color: Annotated[
        bool,
        typer.Option("--no-color", help="Disable terminal colors."),
    ] = False,
) -> None:
    """Preview or run update commands for detected package managers."""

    console = create_console(no_color=no_color)
    inventory = bootstrap_inventory(include_ids=())
    commands = _update_commands(inventory)
    if not commands:
        console.print("[error]No supported package manager update command detected.[/error]")
        raise typer.Exit(code=1)
    for command in commands:
        console.print(" ".join(command))
    if apply:
        _execute_commands(commands, yes=yes, console=console, operation="update")
    else:
        console.print("[muted]No changes made. Use --apply to execute update commands.[/muted]")


@app.command("self-update")
def self_update(
    apply: Annotated[
        bool,
        typer.Option("--apply", help="Run the self-update command after confirmation."),
    ] = False,
    yes: Annotated[
        bool,
        typer.Option("--yes", "-y", help="Do not ask for confirmation."),
    ] = False,
    no_color: Annotated[
        bool,
        typer.Option("--no-color", help="Disable terminal colors."),
    ] = False,
) -> None:
    """Preview or run a Python package self-update."""

    console = create_console(no_color=no_color)
    command = (sys.executable, "-m", "pip", "install", "--upgrade", "devdoctor")
    console.print(" ".join(command))
    if apply:
        _execute_commands((command,), yes=yes, console=console, operation="self-update")
    else:
        console.print("[muted]No changes made. Use --apply to execute the self-update.[/muted]")


@app.command()
def export(
    format: Annotated[
        str,
        typer.Argument(help="Export format: json or markdown."),
    ],
    output: Annotated[
        Path | None,
        typer.Option("--output", "-o", help="Write to a file instead of stdout."),
    ] = None,
    profile: Annotated[
        str | None,
        typer.Option("--profile", "-p", help="Export inventory for one profile."),
    ] = None,
    no_color: Annotated[
        bool,
        typer.Option("--no-color", help="Disable terminal colors."),
    ] = False,
) -> None:
    """Export a bootstrap inventory."""

    console = create_console(no_color=no_color)
    inventory = _inventory_for(profile_id=profile, category_name=None, tool_ids=())
    normalized = format.lower()
    if normalized == "json":
        if output:
            console.print(f"[success]Wrote {write_bootstrap_json(inventory, output)}[/success]")
        else:
            sys.stdout.write(render_bootstrap_json(inventory))
            sys.stdout.write("\n")
        return
    if normalized in {"markdown", "md"}:
        if output:
            console.print(f"[success]Wrote {write_bootstrap_markdown(inventory, output)}[/success]")
        else:
            sys.stdout.write(render_bootstrap_markdown(inventory))
        return
    console.print("[error]Unsupported export format. Use json or markdown.[/error]")
    raise typer.Exit(code=2)


@list_app.command("profiles")
def list_profiles(
    no_color: Annotated[
        bool,
        typer.Option("--no-color", help="Disable terminal colors."),
    ] = False,
) -> None:
    """List available bootstrap profiles."""

    create_console(no_color=no_color).print(profiles_table(BOOTSTRAP_PROFILES))


@list_app.command("tools")
def list_tools(
    category: Annotated[
        str | None,
        typer.Option("--category", "-c", help="Limit tools to a category."),
    ] = None,
    no_color: Annotated[
        bool,
        typer.Option("--no-color", help="Disable terminal colors."),
    ] = False,
) -> None:
    """List catalog tools without probing the system."""

    console = create_console(no_color=no_color)
    specs = _specs_for_category(category) if category else get_bootstrap_tools()
    for spec in specs:
        console.print(f"{spec.id}\t{spec.category.value}\t{spec.title}")


@list_app.command("categories")
def list_categories(
    no_color: Annotated[
        bool,
        typer.Option("--no-color", help="Disable terminal colors."),
    ] = False,
) -> None:
    """List bootstrap categories."""

    console = create_console(no_color=no_color)
    for category in BootstrapCategory:
        console.print(category.value)


@cache_app.command("clean")
def cache_clean(
    apply: Annotated[
        bool,
        typer.Option("--apply", help="Execute detected cache-clean commands after confirmation."),
    ] = False,
    yes: Annotated[
        bool,
        typer.Option("--yes", "-y", help="Do not ask for per-command confirmation."),
    ] = False,
    no_color: Annotated[
        bool,
        typer.Option("--no-color", help="Disable terminal colors."),
    ] = False,
) -> None:
    """Preview or clean known local package caches."""

    console = create_console(no_color=no_color)
    inventory = bootstrap_inventory(include_ids=())
    commands = _cache_clean_commands(inventory)
    if not commands:
        console.print("[success]No supported package cache cleaners detected.[/success]")
        return
    for command in commands:
        console.print(" ".join(command))
    if apply:
        _execute_commands(commands, yes=yes, console=console, operation="cache-clean")
    else:
        console.print("[muted]No changes made. Use --apply to clean caches.[/muted]")


@app.command()
def health(
    output_json: Annotated[
        bool,
        typer.Option("--json", help="Print the legacy health report as JSON."),
    ] = False,
    json_file: Annotated[
        Path | None,
        typer.Option("--json-file", help="Write a legacy JSON health report to this path."),
    ] = None,
    html_file: Annotated[
        Path | None,
        typer.Option("--html-file", help="Write a legacy standalone HTML health report."),
    ] = None,
    markdown_file: Annotated[
        Path | None,
        typer.Option("--markdown-file", help="Write a legacy Markdown health report."),
    ] = None,
    pdf_file: Annotated[
        Path | None,
        typer.Option("--pdf-file", help="Write a compact legacy PDF health report."),
    ] = None,
    save_latest: Annotated[
        bool,
        typer.Option("--save-latest", help="Save the latest legacy JSON report."),
    ] = False,
    no_progress: Annotated[
        bool,
        typer.Option("--no-progress", help="Disable progress bars."),
    ] = False,
    no_color: Annotated[
        bool,
        typer.Option("--no-color", help="Disable terminal colors."),
    ] = False,
    network_timeout: Annotated[
        float,
        typer.Option("--network-timeout", min=0.5, max=30.0, help="Network timeout in seconds."),
    ] = 3.0,
    fail_under: Annotated[
        int | None,
        typer.Option("--fail-under", min=0, max=100, help="Exit 1 if legacy score is below this."),
    ] = None,
    quiet: Annotated[
        bool,
        typer.Option("--quiet", "-q", help="Print only a compact status line."),
    ] = False,
) -> None:
    """Run the legacy health report and exporters."""

    console = create_console(no_color=no_color)
    report = _run_health_scan(
        network_timeout=network_timeout,
        output_json=output_json,
        no_progress=no_progress or quiet,
        show_banner=not quiet,
        console=console,
    )

    if json_file:
        written = write_json_report(report, json_file)
        if not output_json and not quiet:
            console.print(f"[success]JSON report written:[/success] [path]{written}[/path]")
    if html_file:
        written = write_html_report(report, html_file)
        if not output_json and not quiet:
            console.print(f"[success]HTML report written:[/success] [path]{written}[/path]")
    if markdown_file:
        written = write_markdown_report(report, markdown_file)
        if not output_json and not quiet:
            console.print(f"[success]Markdown report written:[/success] [path]{written}[/path]")
    if pdf_file:
        written = write_pdf_report(report, pdf_file)
        if not output_json and not quiet:
            console.print(f"[success]PDF report written:[/success] [path]{written}[/path]")
    if save_latest:
        write_json_report(report, latest_report_path())

    if output_json:
        sys.stdout.write(render_json(report))
        sys.stdout.write("\n")
    elif quiet:
        console.print(compact_status(report))
    else:
        console.print(report_group(report))

    if fail_under is not None and report.score < fail_under:
        if not output_json:
            Console(stderr=True).print(
                f"[bold red]Health score {report.score} is below threshold {fail_under}.[/bold red]"
            )
        raise typer.Exit(code=1)


def _run_bootstrap_report(
    *,
    profile_id: str | None,
    category_name: str | None,
    tool_ids: Sequence[str],
    output_json: bool,
    json_file: Path | None,
    markdown_file: Path | None,
    html_file: Path | None,
    missing_only: bool,
    quiet: bool,
    console: Console,
) -> BootstrapInventory:
    inventory = _inventory_for(
        profile_id=profile_id, category_name=category_name, tool_ids=tool_ids
    )

    if json_file:
        written = write_bootstrap_json(inventory, json_file)
        if not output_json and not quiet:
            console.print(f"[success]JSON inventory written:[/success] [path]{written}[/path]")
    if markdown_file:
        written = write_bootstrap_markdown(inventory, markdown_file)
        if not output_json and not quiet:
            console.print(f"[success]Markdown inventory written:[/success] [path]{written}[/path]")
    if html_file:
        written = write_bootstrap_html(inventory, html_file)
        if not output_json and not quiet:
            console.print(f"[success]HTML inventory written:[/success] [path]{written}[/path]")

    if output_json:
        sys.stdout.write(render_bootstrap_json(inventory))
        sys.stdout.write("\n")
    elif quiet:
        console.print(compact_inventory_status(inventory))
    else:
        console.print(bootstrap_group(inventory, show_missing_only=missing_only))
    return inventory


def _inventory_for(
    *,
    profile_id: str | None,
    category_name: str | None,
    tool_ids: Sequence[str],
) -> BootstrapInventory:
    specs = _selected_specs(profile_id=profile_id, category_name=category_name, tool_ids=tool_ids)
    return bootstrap_inventory(include_ids=tuple(spec.id for spec in specs))


def _selected_specs(
    *,
    profile_id: str | None,
    category_name: str | None,
    tool_ids: Sequence[str],
) -> tuple[ToolSpec, ...]:
    selected: tuple[ToolSpec, ...] = get_bootstrap_tools()
    if profile_id:
        profile = _resolve_profile(profile_id)
        selected = specs_for_profile(profile)
    if category_name:
        category_ids = {spec.id for spec in _specs_for_category(category_name)}
        selected = tuple(spec for spec in selected if spec.id in category_ids)
    if tool_ids:
        explicit_ids = {spec.id for spec in _resolve_tool_specs(tool_ids)}
        selected = tuple(spec for spec in selected if spec.id in explicit_ids)
    return selected


def _resolve_profile(profile_id: str) -> BootstrapProfile:
    profile = profile_by_id(profile_id)
    if profile is None:
        typer.echo(f"Unknown profile: {profile_id}", err=True)
        raise typer.Exit(code=2)
    return profile


def _resolve_tool_specs(tool_ids: Sequence[str]) -> tuple[ToolSpec, ...]:
    by_id = {spec.id: spec for spec in get_bootstrap_tools()}
    missing = [tool_id for tool_id in tool_ids if tool_id not in by_id]
    if missing:
        typer.echo(f"Unknown tool ID: {', '.join(missing)}", err=True)
        raise typer.Exit(code=2)
    return tuple(by_id[tool_id] for tool_id in tool_ids)


def _specs_for_category(category_name: str) -> tuple[ToolSpec, ...]:
    category = _resolve_category(category_name)
    return tuple(spec for spec in get_bootstrap_tools() if spec.category is category)


def _resolve_category(category_name: str) -> BootstrapCategory:
    normalized = category_name.strip().lower().replace("_", "-").replace(" ", "-")
    for category in BootstrapCategory:
        aliases = {
            category.name.lower().replace("_", "-"),
            category.value.lower().replace(" ", "-"),
        }
        if normalized in aliases:
            return category
    typer.echo(f"Unknown category: {category_name}", err=True)
    raise typer.Exit(code=2)


def _search_specs(query: str) -> Iterable[ToolSpec]:
    needle = query.lower()
    for spec in get_bootstrap_tools():
        haystack = " ".join(
            (
                spec.id,
                spec.title,
                spec.category.value,
                spec.executable,
                spec.website,
                " ".join(spec.packages.values()),
            )
        ).lower()
        if needle in haystack:
            yield spec


def _execute_plans(
    plans: Sequence[InstallPlan],
    *,
    dry_run: bool,
    yes: bool,
    console: Console,
    operation: str = "install",
) -> None:
    commands: list[tuple[str, ...]] = []
    metadata: dict[tuple[str, ...], tuple[str, str | None, tuple[str, ...] | None]] = {}
    for plan in plans:
        if dry_run:
            if plan.dry_run_command is None:
                console.print(
                    f"[warning]No dry-run command for {plan.tool_title}; skipped.[/warning]"
                )
                continue
            commands.append(plan.dry_run_command)
            metadata[plan.dry_run_command] = ("dry-run", plan.manager, None)
        else:
            commands.append(plan.command)
            metadata[plan.command] = (operation, plan.manager, plan.verify_command)
    if not commands:
        console.print("[muted]No executable commands selected.[/muted]")
        return
    _execute_commands(
        tuple(commands),
        yes=yes or dry_run,
        console=console,
        operation_metadata=metadata,
    )


def _execute_commands(
    commands: Sequence[tuple[str, ...]],
    *,
    yes: bool,
    console: Console,
    operation: str = "command",
    operation_metadata: Mapping[tuple[str, ...], tuple[str, str | None, tuple[str, ...] | None]]
    | None = None,
) -> None:
    log_path = operation_log_path()
    metadata = operation_metadata or {}
    for command in commands:
        rendered = " ".join(command)
        if not yes and not typer.confirm(f"Run `{rendered}`?"):
            console.print(f"[muted]Skipped {rendered}[/muted]")
            continue
        operation_name, manager, verification_command = metadata.get(
            command, (operation, None, None)
        )
        started_at = time.perf_counter()
        completed = subprocess.run(list(command), check=False)
        duration = time.perf_counter() - started_at
        verification_exit_code: int | None = None
        verification_output: str | None = None
        if completed.returncode == 0 and verification_command:
            verification = run_command(verification_command, timeout=10)
            verification_exit_code = verification.returncode
            verification_output = verification.combined_output[:500] or None
        append_operation_log(
            log_path,
            OperationLogRecord(
                timestamp=datetime.now(UTC),
                operation=operation_name,
                selected_package_manager=manager,
                command=command,
                exit_code=completed.returncode,
                duration_seconds=duration,
                verification_command=verification_command,
                verification_exit_code=verification_exit_code,
                verification_output=verification_output,
            ),
        )
        if completed.returncode != 0:
            console.print(f"[error]Command failed with exit code {completed.returncode}.[/error]")
            console.print(f"[muted]Log: {log_path}[/muted]")
            raise typer.Exit(code=completed.returncode)
    console.print(f"[success]Command log:[/success] [path]{log_path}[/path]")


def _update_commands(inventory: BootstrapInventory) -> tuple[tuple[str, ...], ...]:
    managers = _installed_manager_ids(inventory)
    commands: list[tuple[str, ...]] = []
    if system_is_atomic(inventory.system):
        # Image-based host: the base image is upgraded as a whole; DNF must not run.
        if "rpm-ostree" in managers:
            commands.append(("rpm-ostree", "upgrade"))
        if "flatpak" in managers:
            commands.append(("flatpak", "update"))
        if "brew" in managers:
            commands.extend((("brew", "update"), ("brew", "upgrade")))
        return tuple(commands)
    if "apt" in managers:
        commands.extend((("sudo", "apt", "update"), ("sudo", "apt", "upgrade")))
    if "dnf" in managers:
        commands.append(("sudo", "dnf", "upgrade"))
    if "pacman" in managers:
        commands.append(("sudo", "pacman", "-Syu"))
    if "zypper" in managers:
        commands.extend((("sudo", "zypper", "refresh"), ("sudo", "zypper", "update")))
    if "flatpak" in managers:
        commands.append(("flatpak", "update"))
    if "snap" in managers:
        commands.append(("sudo", "snap", "refresh"))
    if "brew" in managers:
        commands.extend((("brew", "update"), ("brew", "upgrade")))
    return tuple(commands)


def _cache_clean_commands(inventory: BootstrapInventory) -> tuple[tuple[str, ...], ...]:
    managers = _installed_manager_ids(inventory)
    commands: list[tuple[str, ...]] = []
    if "apt" in managers:
        commands.append(("sudo", "apt", "clean"))
    if "dnf" in managers and not system_is_atomic(inventory.system):
        commands.append(("sudo", "dnf", "clean", "all"))
    if "pacman" in managers:
        commands.append(("sudo", "pacman", "-Sc"))
    if "flatpak" in managers:
        commands.append(("flatpak", "uninstall", "--unused"))
    if "npm" in managers:
        commands.append(("npm", "cache", "clean", "--force"))
    if "pnpm" in managers:
        commands.append(("pnpm", "store", "prune"))
    if "pip" in managers:
        commands.append(("python", "-m", "pip", "cache", "purge"))
    return tuple(commands)


def _installed_manager_ids(inventory: BootstrapInventory) -> set[str]:
    return {
        str(manager.get("id"))
        for manager in inventory.system.get("package_managers", ())
        if isinstance(manager, dict) and manager.get("installed") is True
    }


def _run_health_scan(
    *,
    network_timeout: float,
    output_json: bool,
    no_progress: bool,
    show_banner: bool,
    console: Console,
) -> HealthReport:
    """Run legacy checks with an optional Rich progress bar."""

    doctor = DevDoctor.default(network_timeout=network_timeout)
    if show_banner and not output_json:
        console.print(banner(__version__))

    if output_json or no_progress:
        return doctor.run()

    with create_progress(console) as progress:
        task_id = progress.add_task("Starting checks", total=len(doctor.checks))

        def update(description: str, index: int, total: int) -> None:
            progress.update(task_id, description=description, completed=index - 1, total=total)

        report = doctor.run(progress=update)
        progress.update(task_id, description="Complete", completed=len(doctor.checks))
    return report
