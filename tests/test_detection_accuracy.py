"""Regression tests for detection results observed on a real Ubuntu 24.04 host.

Every test here reproduces a wrong answer DevDoctor gave on a stock Debian-family
workstation. They use real files and real subprocesses; no detector is mocked.
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest
from rich.console import Console

from devdoctor import bootstrap
from devdoctor.bootstrap import (
    BOOTSTRAP_TOOLS,
    BootstrapInventory,
    HealthState,
    ToolSpec,
    detect_tool,
    install_plan_for_spec,
)
from devdoctor.path_analysis import analyze_path
from devdoctor.ui.bootstrap import _plan_text, path_analysis_panel
from devdoctor.utils import parse_version


def _write_tool(directory: Path, name: str, body: str) -> Path:
    directory.mkdir(parents=True, exist_ok=True)
    tool = directory / name
    tool.write_text(body, encoding="utf-8")
    tool.chmod(0o755)
    return tool


def _spec(executable: str, **overrides: object) -> ToolSpec:
    return ToolSpec(
        id=executable,
        title=executable,
        category=bootstrap.BootstrapCategory.PROGRAMMING_LANGUAGES,
        executable=executable,
        **overrides,  # type: ignore[arg-type]
    )


def _catalog(tool_id: str) -> ToolSpec:
    return next(spec for spec in BOOTSTRAP_TOOLS if spec.id == tool_id)


NO_MANAGERS = {"package_managers": []}


# --- python vs python3 -------------------------------------------------------


def test_detect_tool_uses_alias_when_primary_executable_is_absent(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    bin_dir = tmp_path / "bin"
    python3 = _write_tool(bin_dir, "python3", "#!/bin/sh\necho 'Python 3.12.3'\n")
    monkeypatch.setenv("PATH", str(bin_dir))

    detection = detect_tool(_spec("python", executable_aliases=("python3",)), system=NO_MANAGERS)

    assert detection.installed is True
    assert detection.executable_path == str(python3)
    assert detection.version == "3.12.3"


def test_catalog_python_is_detected_on_python3_only_hosts(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    # Debian and Ubuntu ship python3 without a `python` alias.
    bin_dir = tmp_path / "bin"
    _write_tool(bin_dir, "python3", "#!/bin/sh\necho 'Python 3.12.3'\n")
    monkeypatch.setenv("PATH", str(bin_dir))

    detection = detect_tool(_catalog("python"), system=NO_MANAGERS)

    assert detection.installed is True
    assert detection.version == "3.12.3"


def test_catalog_pip_is_detected_as_pip3(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    bin_dir = tmp_path / "bin"
    _write_tool(
        bin_dir, "pip3", "#!/bin/sh\necho 'pip 24.0 from /usr/lib/python3/dist-packages/pip'\n"
    )
    monkeypatch.setenv("PATH", str(bin_dir))

    detection = detect_tool(_catalog("pip"), system=NO_MANAGERS)

    assert detection.installed is True
    assert detection.version == "24.0"


# --- error text reported as a version -----------------------------------------


def test_detect_tool_reports_broken_interpreter_as_broken(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    # A pip launcher whose shebang points at a Python that no longer exists.
    bin_dir = tmp_path / "bin"
    launcher = _write_tool(bin_dir, "pip", "#!/nonexistent/python\nprint('unreachable')\n")
    monkeypatch.setenv("PATH", str(bin_dir))

    detection = detect_tool(_spec("pip"), system=NO_MANAGERS)

    assert detection.version is None
    assert detection.installed is False
    assert detection.broken_installation is True
    assert detection.health is HealthState.BROKEN
    assert detection.executable_path == str(launcher)
    assert any("interpreter" in issue.lower() for issue in detection.path_issues)


def test_broken_launcher_stays_broken_after_enrichment(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    bin_dir = tmp_path / "bin"
    _write_tool(bin_dir, "pip", "#!/nonexistent/python\n")
    monkeypatch.setenv("PATH", str(bin_dir))
    detection = detect_tool(_spec("pip"), system=NO_MANAGERS)

    (enriched,) = bootstrap._enrich_detections((detection,), system=NO_MANAGERS)

    assert enriched.health is HealthState.BROKEN


@pytest.mark.parametrize(
    "output",
    [
        "unknown option -- -",
        "[Errno 2] No such file or directory: '/home/user/.local/bin/pip'",
        "custom build\nextra",
    ],
)
def test_parse_version_returns_none_when_no_version_token_exists(output: str) -> None:
    assert parse_version(output) is None


# --- ssh ----------------------------------------------------------------------


def test_catalog_ssh_probes_version_with_dash_v() -> None:
    assert _catalog("ssh").version_args == ("-V",)


def test_parse_version_prefers_openssh_token_over_openssl() -> None:
    output = "OpenSSH_9.6p1 Ubuntu-3ubuntu13.18, OpenSSL 3.0.13 30 Jan 2024"
    assert parse_version(output) == "9.6p1"


# --- merged-usr: /bin -> /usr/bin --------------------------------------------


def test_detect_tool_ignores_alternate_paths_that_resolve_to_the_same_file(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    usr_bin = tmp_path / "usr" / "bin"
    _write_tool(usr_bin, "git", "#!/bin/sh\necho 'git version 2.43.0'\n")
    (tmp_path / "bin").symlink_to(usr_bin, target_is_directory=True)
    monkeypatch.setenv("PATH", f"{usr_bin}{os.pathsep}{tmp_path / 'bin'}")

    detection = detect_tool(_spec("git"), system=NO_MANAGERS)

    assert detection.installed is True
    assert detection.alternate_paths == ()


def test_path_analysis_does_not_report_shadowing_through_merged_usr_symlink(
    tmp_path: Path,
) -> None:
    usr_bin = tmp_path / "usr" / "bin"
    _write_tool(usr_bin, "git", "#!/bin/sh\n")
    (tmp_path / "bin").symlink_to(usr_bin, target_is_directory=True)

    analysis = analyze_path(
        f"{usr_bin}{os.pathsep}{tmp_path / 'bin'}", executables=("git",), home=tmp_path
    )

    assert analysis.shadowed_executables == ()


# --- PATH table: one cleanup command, not one per row ------------------------


def test_missing_directory_issues_share_one_cleanup_command(tmp_path: Path) -> None:
    good = tmp_path / "good"
    good.mkdir()
    missing_a = tmp_path / "missing-a"
    missing_b = tmp_path / "missing-b"

    analysis = analyze_path(
        os.pathsep.join((str(good), str(missing_a), str(missing_b), str(good))),
        executables=(),
        home=tmp_path,
    )

    missing = [issue for issue in analysis.issues if issue.kind == "missing_directory"]
    assert len(missing) == 2
    assert all(issue.export_command is None for issue in missing)
    assert analysis.cleanup_command == f'export PATH="{good}"'
    assert analysis.to_dict()["cleanup_command"] == analysis.cleanup_command


def test_path_panel_prints_cleanup_command_once(tmp_path: Path) -> None:
    good = tmp_path / "good"
    good.mkdir()
    path_value = os.pathsep.join((str(good), str(tmp_path / "m1"), str(tmp_path / "m2")))
    analysis = analyze_path(path_value, executables=(), home=tmp_path)
    inventory = BootstrapInventory(
        system={"path_analysis": analysis.to_dict()},
        detections=(),
        profiles=(),
    )

    console = Console(width=200, record=True, color_system=None)
    console.print(path_analysis_panel(inventory))
    rendered = console.export_text()

    assert rendered.count("export PATH=") == 1


# --- install plans that cannot succeed ---------------------------------------


@pytest.mark.parametrize(
    "tool_id", ["kubectl", "helm", "terraform", "az", "pnpm", "ruff", "starship", "asdf"]
)
def test_tools_absent_from_debian_repos_do_not_claim_an_apt_package(tool_id: str) -> None:
    # Verified with `apt-cache policy` on ubuntu:24.04: none of these exist.
    assert "apt" not in _catalog(tool_id).packages


@pytest.mark.parametrize("tool_id", ["terraform", "pnpm", "starship", "asdf"])
def test_tools_absent_from_fedora_repos_do_not_claim_a_dnf_package(tool_id: str) -> None:
    # Verified against src.fedoraproject.org: no source package under these names.
    assert "dnf" not in _catalog(tool_id).packages


def test_docker_cli_plugins_use_distro_package_names() -> None:
    compose = _catalog("docker-compose").packages
    buildx = _catalog("docker-buildx").packages
    assert compose["apt"] == "docker-compose-v2"
    assert compose["dnf"] == "docker-compose"
    assert buildx["apt"] == "docker-buildx"
    assert buildx["dnf"] == "docker-buildx"


@pytest.mark.parametrize("tool_id", ["kubectl", "helm", "code", "flutter", "aws", "gcloud"])
def test_classic_snaps_are_installed_with_classic_confinement(tool_id: str) -> None:
    system = {
        "distribution_id": "ubuntu",
        "distribution_like": ["debian"],
        "package_managers": [{"id": "snap", "installed": True}],
    }

    plan = install_plan_for_spec(_catalog(tool_id), system=system)

    assert plan is not None
    assert plan.manager == "snap"
    assert plan.command[-1] == "--classic"


def test_missing_tool_without_a_local_manager_points_at_the_vendor_site(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("PATH", str(tmp_path))
    detection = detect_tool(_catalog("kubectl"), system=NO_MANAGERS)

    text = _plan_text(detection)

    assert detection.installed is False
    assert "No supported local manager" in text
    assert "https://kubernetes.io/docs/tasks/tools/" in text
