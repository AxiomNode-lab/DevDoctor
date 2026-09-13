"""Plans must be runnable where they are shown: root containers, no-sudo hosts, no systemd."""

from __future__ import annotations

from pathlib import Path

import pytest

from devdoctor import bootstrap, cli
from devdoctor.bootstrap import BootstrapInventory, ToolSpec, install_plan_for_spec


def _spec(tool_id: str) -> ToolSpec:
    return next(spec for spec in bootstrap.get_bootstrap_tools() if spec.id == tool_id)


def _ubuntu(**overrides: object) -> dict[str, object]:
    system: dict[str, object] = {
        "distribution_id": "ubuntu",
        "distribution_like": ["debian"],
        "package_managers": [
            {"id": "apt", "installed": True},
            {"id": "flatpak", "installed": True},
        ],
        "is_root": False,
        "can_sudo": True,
        "is_container": False,
    }
    system.update(overrides)
    return system


def test_root_plans_do_not_prefix_sudo() -> None:
    plan = install_plan_for_spec(_spec("git"), system=_ubuntu(is_root=True, can_sudo=False))

    assert plan is not None
    assert plan.command == ("apt", "install", "git")
    assert plan.rollback_command == ("apt", "remove", "git")
    assert plan.requires_sudo is False


def test_non_root_plans_keep_sudo() -> None:
    plan = install_plan_for_spec(_spec("git"), system=_ubuntu())

    assert plan is not None
    assert plan.command == ("sudo", "apt", "install", "git")
    assert plan.requires_sudo is True


def test_plan_without_sudo_on_host_says_so() -> None:
    plan = install_plan_for_spec(_spec("git"), system=_ubuntu(can_sudo=False))

    assert plan is not None
    assert plan.requires_sudo is True
    assert "sudo is not available" in plan.explanation


def test_root_update_and_cache_commands_drop_sudo() -> None:
    inventory = BootstrapInventory(system=_ubuntu(is_root=True), detections=(), profiles=())

    assert ("apt", "update") in cli._update_commands(inventory)
    assert not any(command[0] == "sudo" for command in cli._update_commands(inventory))
    assert not any(command[0] == "sudo" for command in cli._cache_clean_commands(inventory))


def test_docker_daemon_repair_needs_a_running_systemd(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    docker = (
        "#!/bin/sh\n"
        '[ "$1" = info ] && { echo "Cannot connect to the Docker daemon" >&2; exit 1; }\n'
        "echo 'Docker version 27.0'\n"
    )
    for name, body in (("docker", docker), ("systemctl", "#!/bin/sh\nexit 0\n")):
        (bin_dir / name).write_text(body, encoding="utf-8")
        (bin_dir / name).chmod(0o755)
    monkeypatch.setenv("PATH", str(bin_dir))
    spec = ToolSpec(
        id="docker",
        title="Docker",
        category=bootstrap.BootstrapCategory.CONTAINERS,
        executable="docker",
    )
    system = {"package_managers": [], "is_root": False, "can_sudo": True}

    monkeypatch.setattr(bootstrap, "_systemd_running", lambda: False)
    (without_systemd,) = bootstrap._enrich_detections(
        bootstrap.detect_tools((spec,), system=system), system=system
    )
    monkeypatch.setattr(bootstrap, "_systemd_running", lambda: True)
    (with_systemd,) = bootstrap._enrich_detections(
        bootstrap.detect_tools((spec,), system=system), system=system
    )

    assert all("systemctl" not in (r.command or ()) for r in without_systemd.repair_recommendations)
    assert any("systemd" in r.reason for r in without_systemd.repair_recommendations)
    assert any(r.command and "systemctl" in r.command for r in with_systemd.repair_recommendations)
