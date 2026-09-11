"""Every public command through the real console app, on the real machine.

These run the same Typer app `devdoctor` runs (extra command groups registered,
release-safety wrappers applied), scoped to one or two catalog tools so the
whole file stays fast. They assert on behaviour a user sees: exit codes, JSON
shape, files written, and that preview commands change nothing.
"""

from __future__ import annotations

import getpass
import json
import socket
from pathlib import Path

import pytest
from typer.testing import CliRunner

from devdoctor import __copyright__, entrypoint
from devdoctor.bootstrap import HealthState

runner = CliRunner(env={"NO_COLOR": "1", "TERM": "dumb", "COLUMNS": "200"})


@pytest.fixture(scope="module")
def app():
    return entrypoint.build_app()


def _invoke(app, *args: str):
    return runner.invoke(app, list(args))


def test_build_app_is_idempotent_and_registers_extra_command_groups() -> None:
    first = entrypoint.build_app()
    second = entrypoint.build_app()
    names = {command.name for command in first.registered_commands}

    assert first is second
    assert {"diagnostics", "support", "project", "path-conflicts", "repair-apply"} <= names


def test_check_json_has_the_documented_shape(app) -> None:
    result = _invoke(app, "check", "git", "curl", "--json")

    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert set(payload) >= {"system", "summary", "tools", "profiles"}
    assert {tool["id"] for tool in payload["tools"]} >= {"git", "curl"}
    assert all(tool["health"] in set(HealthState) for tool in payload["tools"])
    assert isinstance(payload["system"]["atomic_host"], bool)


def test_verify_exits_non_zero_when_a_selected_tool_is_missing(app) -> None:
    result = _invoke(app, "verify", "godot", "--quiet")

    assert result.exit_code == 1
    assert "missing=1" in result.output


def test_install_dry_run_previews_without_changing_anything(app) -> None:
    result = _invoke(app, "install", "godot", "--dry-run")

    assert result.exit_code == 0, result.output
    assert "godot" in result.output.lower()
    assert "--apply" not in result.output or "No changes" in result.output


@pytest.mark.parametrize("command", [("update",), ("cache", "clean"), ("self-update",)])
def test_mutating_commands_preview_by_default(app, command: tuple[str, ...]) -> None:
    result = _invoke(app, *command)

    assert result.exit_code == 0, result.output
    assert "No changes made" in result.output


def test_uninstall_unknown_tool_is_an_error(app) -> None:
    result = _invoke(app, "uninstall", "no-such-tool")

    assert result.exit_code != 0


def test_export_json_writes_a_parseable_inventory(app, tmp_path: Path) -> None:
    target = tmp_path / "inventory.json"

    result = _invoke(app, "export", "json", "--output", str(target))

    assert result.exit_code == 0, result.output
    assert set(json.loads(target.read_text(encoding="utf-8"))) >= {"tools", "summary"}


def test_markdown_and_html_files_carry_the_footer(app, tmp_path: Path) -> None:
    markdown = tmp_path / "inventory.md"
    html = tmp_path / "inventory.html"

    result = _invoke(app, "--markdown-file", str(markdown), "--html-file", str(html), "--quiet")

    assert result.exit_code == 0, result.output
    assert __copyright__ in markdown.read_text(encoding="utf-8")
    assert __copyright__ in html.read_text(encoding="utf-8")


def test_diagnostics_stdout_is_scrubbed_json(app) -> None:
    result = _invoke(app, "diagnostics", "--stdout")

    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    rendered = json.dumps(payload)
    assert payload["privacy"]["hostname_included"] is False
    assert payload["privacy"]["username_included"] is False
    assert payload["privacy"]["raw_path_included"] is False
    assert socket.gethostname() not in rendered
    assert getpass.getuser() not in rendered


def test_support_stdout_is_markdown_naming_the_project(app) -> None:
    result = _invoke(app, "support", "--stdout")

    assert result.exit_code == 0, result.output
    assert result.output.startswith("# DevDoctor support report")
    assert "AxiomNode" in result.output


def test_project_check_reads_pyproject_and_exits_zero_when_satisfied(app) -> None:
    root = Path(__file__).resolve().parent.parent

    result = _invoke(app, "project", str(root), "--json")

    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert "pyproject.toml" in json.dumps(payload)


@pytest.mark.parametrize("shell", ["bash", "zsh", "fish"])
def test_completion_lists_registered_commands(app, shell: str) -> None:
    result = _invoke(app, "completion", shell)

    assert result.exit_code == 0, result.output
    for name in ("check", "project", "support", "repair-rollback"):
        assert name in result.output


def test_search_finds_catalog_tools(app) -> None:
    result = _invoke(app, "search", "docker")

    assert result.exit_code == 0
    assert "Docker" in result.output


def test_repair_rollback_rejects_unknown_transaction(app) -> None:
    result = _invoke(app, "repair-rollback", "no-such-transaction")

    assert result.exit_code != 0
