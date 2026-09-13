"""Confirmation-first repair execution with explicit rollback transactions."""

from __future__ import annotations

import json
import re
import subprocess
import time
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import typer

from devdoctor import bootstrap
from devdoctor.paths import state_dir
from devdoctor.utils import get_username, run_command

_REGISTERED = False
_SAFE_PACKAGE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9+._:@/#=-]{0,255}$")
_MANAGER_ROLLBACK_PREFIXES: dict[str, tuple[str, ...]] = {
    "apt": ("sudo", "apt", "remove"),
    "dnf": ("sudo", "dnf", "remove"),
    "rpm-ostree": ("rpm-ostree", "uninstall"),
    "pacman": ("sudo", "pacman", "-R"),
    "yay": ("yay", "-R"),
    "paru": ("paru", "-R"),
    "zypper": ("sudo", "zypper", "remove"),
    "xbps": ("sudo", "xbps-remove"),
    "apk": ("sudo", "apk", "del"),
    "nix": ("nix", "profile", "remove"),
    "brew": ("brew", "uninstall"),
    "flatpak": ("flatpak", "uninstall"),
    "snap": ("sudo", "snap", "remove"),
    "pipx": ("pipx", "uninstall"),
    "npm": ("npm", "uninstall", "-g"),
    "pnpm": ("pnpm", "remove", "-g"),
    "yarn": ("yarn", "global", "remove"),
    "gem": ("gem", "uninstall"),
    "composer": ("composer", "global", "remove"),
    "rustup": ("rustup", "toolchain", "uninstall"),
    "mise": ("mise", "uninstall"),
    "asdf": ("asdf", "uninstall"),
}
_NIX_CATALOG_KEYS = {"rustc": "rust", "gh": "github_cli"}


@dataclass(frozen=True, slots=True)
class RepairAction:
    tool_id: str
    tool_title: str
    problem: str
    risk: str
    command: tuple[str, ...]
    verification_command: tuple[str, ...] | None
    rollback_command: tuple[str, ...]


def collect_repair_actions(inventory: bootstrap.BootstrapInventory) -> tuple[RepairAction, ...]:
    """Collect only repair recommendations with both executable and rollback commands."""

    actions: list[RepairAction] = []
    for detection in inventory.detections:
        for recommendation in detection.repair_recommendations:
            if recommendation.command is None or recommendation.rollback_command is None:
                continue
            actions.append(
                RepairAction(
                    tool_id=detection.spec.id,
                    tool_title=detection.spec.title,
                    problem=recommendation.problem,
                    risk=recommendation.risk,
                    command=recommendation.command,
                    verification_command=recommendation.verification_command,
                    rollback_command=recommendation.rollback_command,
                )
            )
    return tuple(actions)


def _transactions_dir() -> Path:
    path = state_dir() / "repair-transactions"
    path.mkdir(parents=True, exist_ok=True)
    return path


def _new_transaction_id() -> str:
    timestamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    return f"{timestamp}-{uuid.uuid4().hex[:8]}"


def _transaction_path(transaction_id: str) -> Path:
    if not transaction_id or any(
        character not in "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-_"
        for character in transaction_id
    ):
        raise ValueError("invalid transaction id")
    return _transactions_dir() / f"{transaction_id}.json"


def _render_command(command: tuple[str, ...]) -> str:
    return " ".join(command)


def _write_transaction(path: Path, payload: dict[str, Any]) -> None:
    temporary = path.with_suffix(".tmp")
    temporary.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    temporary.replace(path)


def _spec_for_tool(tool_id: str) -> bootstrap.ToolSpec | None:
    return next((spec for spec in bootstrap.get_bootstrap_tools() if spec.id == tool_id), None)


def _expected_package(spec: bootstrap.ToolSpec, manager: str) -> str | None:
    if manager == "rpm-ostree":
        return spec.packages.get("rpm-ostree") or spec.packages.get("dnf")
    if manager == "nix":
        alias = _NIX_CATALOG_KEYS.get(spec.id, spec.id)
        return spec.packages.get("nix") or {
            "git": "nixpkgs#git",
            "rust": "nixpkgs#rustup",
            "github_cli": "nixpkgs#gh",
        }.get(alias)
    return spec.packages.get(manager)


def _allowed_rollback_command(command: tuple[str, ...], tool_id: str | None = None) -> bool:
    """Validate a complete rollback shape, optionally against the tool catalog."""

    if tool_id == "docker" and command == ("sudo", "systemctl", "stop", "docker"):
        return True
    if (
        tool_id == "docker"
        and len(command) == 5
        and command[:3] == ("sudo", "gpasswd", "-d")
        and command[3] == get_username()
        and command[4] == "docker"
    ):
        return True

    spec = _spec_for_tool(tool_id) if tool_id is not None else None
    for manager, prefix in _MANAGER_ROLLBACK_PREFIXES.items():
        if len(command) != len(prefix) + 1 or command[: len(prefix)] != prefix:
            continue
        package = command[-1]
        if not _SAFE_PACKAGE.fullmatch(package):
            return False
        if spec is None:
            return True
        expected = _expected_package(spec, manager)
        return expected == package
    return False


def _execute_repair_action(
    action: RepairAction,
    *,
    payload: dict[str, Any],
    path: Path,
) -> dict[str, Any]:
    """Persist rollback intent before executing, then atomically record the outcome."""

    record: dict[str, Any] = {
        "tool_id": action.tool_id,
        "tool_title": action.tool_title,
        "problem": action.problem,
        "risk": action.risk,
        "command": list(action.command),
        "rollback_command": list(action.rollback_command),
        "exit_code": None,
        "duration_seconds": None,
        "status": "pending",
        "verification_command": (
            list(action.verification_command) if action.verification_command else None
        ),
        "verification_exit_code": None,
    }
    payload["actions"].append(record)
    _write_transaction(path, payload)

    started = time.perf_counter()
    try:
        completed = subprocess.run(list(action.command), check=False)
    except OSError:
        record["duration_seconds"] = round(time.perf_counter() - started, 3)
        record["status"] = "execution-error"
        _write_transaction(path, payload)
        return record

    record["exit_code"] = completed.returncode
    record["duration_seconds"] = round(time.perf_counter() - started, 3)
    record["status"] = "failed" if completed.returncode else "applied"
    if completed.returncode == 0 and action.verification_command:
        verification = run_command(action.verification_command, timeout=10)
        record["verification_exit_code"] = verification.returncode
        if verification.returncode != 0:
            record["status"] = "verification-failed"
    _write_transaction(path, payload)
    return record


def _validate_tool_ids(tool_ids: tuple[str, ...]) -> None:
    if not tool_ids:
        return
    known = {spec.id for spec in bootstrap.get_bootstrap_tools()}
    unknown = sorted(set(tool_ids) - known)
    if unknown:
        raise typer.BadParameter(f"unknown tool id(s): {', '.join(unknown)}")


def register_repair_transaction_commands(app: typer.Typer) -> None:
    """Register conservative repair execution and rollback commands once."""

    global _REGISTERED
    if _REGISTERED:
        return
    _REGISTERED = True

    @app.command("fix")
    @app.command("repair-apply")
    def repair_apply(
        tools: list[str] | None = typer.Argument(
            None,
            help="Optional tool IDs. Only repairs with a known rollback command are executable.",
        ),
        apply: bool = typer.Option(
            False, "--apply", help="Execute after preview and confirmation."
        ),
        yes: bool = typer.Option(False, "--yes", "-y", help="Skip per-action confirmation."),
    ) -> None:
        """Walk the Findings: preview each rollback-capable repair, apply with --apply."""

        tool_ids = tuple(tools or ())
        _validate_tool_ids(tool_ids)
        inventory = bootstrap.bootstrap_inventory(include_ids=tool_ids or None)
        actions = collect_repair_actions(inventory)
        if not actions:
            typer.echo("No executable rollback-capable repairs found.")
            return

        typer.echo("Repair preview:")
        for action in actions:
            typer.echo(
                f"- {action.tool_id}: {action.problem}\n"
                f"  run: {_render_command(action.command)}\n"
                f"  rollback: {_render_command(action.rollback_command)}\n"
                f"  risk: {action.risk}"
            )
        if not apply:
            typer.echo("No changes made. Use --apply to execute rollback-capable repairs.")
            return

        transaction_id = _new_transaction_id()
        path = _transaction_path(transaction_id)
        payload: dict[str, Any] = {
            "schema_version": 1,
            "transaction_id": transaction_id,
            "created_at": datetime.now(UTC).isoformat(),
            "actions": [],
        }

        for action in actions:
            rendered = _render_command(action.command)
            if not yes and not typer.confirm(f"Run `{rendered}`?"):
                continue
            record = _execute_repair_action(action, payload=payload, path=path)
            if record["status"] != "applied":
                typer.echo(
                    f"Repair stopped with status {record['status']}. "
                    f"Preview rollback with: devdoctor repair-rollback {transaction_id}"
                )
                exit_code = record.get("exit_code")
                raise typer.Exit(code=int(exit_code) if isinstance(exit_code, int) else 1)

        if payload["actions"]:
            typer.echo(f"Repair transaction: {transaction_id}")
            typer.echo(f"Journal: {path}")
            typer.echo(f"Rollback preview: devdoctor repair-rollback {transaction_id}")
        else:
            typer.echo("No repair actions were approved; no transaction was created.")

    @app.command("repair-rollback")
    def repair_rollback(
        transaction_id: str = typer.Argument(..., help="Transaction ID emitted by repair-apply."),
        apply: bool = typer.Option(False, "--apply", help="Execute rollback after preview."),
        yes: bool = typer.Option(False, "--yes", "-y", help="Skip per-command confirmation."),
    ) -> None:
        """Preview or execute validated rollback commands from a repair transaction."""

        try:
            path = _transaction_path(transaction_id)
        except ValueError as exc:
            raise typer.BadParameter(str(exc)) from exc
        if not path.exists():
            raise typer.BadParameter(f"unknown transaction: {transaction_id}")
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError, RecursionError) as exc:
            raise typer.BadParameter("invalid or unreadable transaction journal") from exc
        if (
            not isinstance(payload, dict)
            or payload.get("schema_version") != 1
            or payload.get("transaction_id") != transaction_id
            or not isinstance(payload.get("actions"), list)
        ):
            raise typer.BadParameter("invalid or incompatible transaction journal")

        candidates: list[dict[str, Any]] = []
        rollback_states = {
            "pending",
            "failed",
            "execution-error",
            "verification-failed",
            "applied",
            "rollback-failed",
        }
        for record in reversed(payload["actions"]):
            if not isinstance(record, dict) or record.get("status") not in rollback_states:
                continue
            command = tuple(str(part) for part in record.get("rollback_command", ()))
            tool_id = str(record.get("tool_id", ""))
            if not command or not _allowed_rollback_command(command, tool_id=tool_id):
                typer.echo(f"Blocked invalid rollback command for {tool_id or 'unknown'}.")
                continue
            record["_rollback_tuple"] = command
            candidates.append(record)

        if not candidates:
            typer.echo("No pending validated rollback commands in this transaction.")
            return

        typer.echo("Rollback preview:")
        for record in candidates:
            typer.echo(f"- {_render_command(record['_rollback_tuple'])}")
        if not apply:
            typer.echo("No changes made. Use --apply to execute rollback commands.")
            return

        for record in candidates:
            command = record.pop("_rollback_tuple")
            rendered = _render_command(command)
            if not yes and not typer.confirm(f"Run rollback `{rendered}`?"):
                continue
            completed = subprocess.run(list(command), check=False)
            record["rollback_exit_code"] = completed.returncode
            record["rolled_back_at"] = datetime.now(UTC).isoformat()
            record["status"] = "rolled-back" if completed.returncode == 0 else "rollback-failed"
            _write_transaction(path, payload)
            if completed.returncode != 0:
                raise typer.Exit(code=completed.returncode)
