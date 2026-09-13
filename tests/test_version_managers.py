"""Several copies of a tool under one version manager are that manager doing its job."""

from __future__ import annotations

from pathlib import Path

import pytest

from devdoctor import bootstrap
from devdoctor.bootstrap import ToolSpec, version_manager_for


def _tool(directory: Path, name: str, version: str) -> Path:
    directory.mkdir(parents=True, exist_ok=True)
    tool = directory / name
    tool.write_text(f"#!/bin/sh\necho '{name} v{version}'\n", encoding="utf-8")
    tool.chmod(0o755)
    return tool


@pytest.mark.parametrize(
    ("relative", "manager"),
    [
        (".nvm/versions/node/v20.20.2/bin/node", "nvm"),
        (".pyenv/versions/3.12.3/bin/python3", "pyenv"),
        (".pyenv/shims/python3", "pyenv"),
        (".rbenv/versions/3.3.0/bin/ruby", "rbenv"),
        (".asdf/installs/nodejs/22.0.0/bin/node", "asdf"),
        (".asdf/shims/node", "asdf"),
        (".local/share/mise/installs/node/22.0.0/bin/node", "mise"),
        (".local/share/mise/shims/node", "mise"),
        (".sdkman/candidates/java/21.0.2-tem/bin/java", "sdkman"),
        (".cargo/bin/cargo", "rustup"),
        (".local/bin/ruff", None),
        ("/usr/bin/git", None),
    ],
)
def test_version_manager_is_recognised_from_the_path(
    relative: str, manager: str | None, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("HOME", str(tmp_path))
    path = relative if relative.startswith("/") else str(tmp_path / relative)

    assert version_manager_for(path) == manager


def test_nvm_versions_in_path_are_one_managed_install_not_duplicates(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("HOME", str(tmp_path))
    active = _tool(tmp_path / ".nvm/versions/node/v20.20.2/bin", "node", "20.20.2")
    _tool(active.parent, "npm", "10.8.2")  # node without npm is a real (separate) warning
    _tool(tmp_path / ".nvm/versions/node/v22.23.1/bin", "node", "22.23.1")
    _tool(tmp_path / ".nvm/versions/node/v24.20.0/bin", "node", "24.20.0")
    monkeypatch.setenv(
        "PATH",
        ":".join(
            str(p)
            for p in (
                active.parent,
                tmp_path / ".nvm/versions/node/v22.23.1/bin",
                tmp_path / ".nvm/versions/node/v24.20.0/bin",
            )
        ),
    )
    specs = tuple(
        ToolSpec(
            id=n, title=n, category=bootstrap.BootstrapCategory.PROGRAMMING_LANGUAGES, executable=n
        )
        for n in ("node", "npm")  # node's enrichment looks npm up in the same inventory
    )
    system = {"package_managers": []}

    detection, _npm = bootstrap._enrich_detections(
        bootstrap.detect_tools(specs, system=system), system=system
    )

    assert detection.installed and detection.version == "20.20.2"
    assert detection.installation_method == "nvm (3 versions installed)"
    assert not any("Duplicate" in r.problem for r in detection.repair_recommendations)
    assert detection.health is bootstrap.HealthState.READY


def test_a_copy_outside_the_manager_is_still_a_duplicate(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("HOME", str(tmp_path))
    managed = _tool(tmp_path / ".nvm/versions/node/v20.20.2/bin", "node", "20.20.2")
    system_copy = _tool(tmp_path / "usr/bin", "node", "18.0.0")
    monkeypatch.setenv("PATH", f"{managed.parent}:{system_copy.parent}")
    spec = ToolSpec(
        id="node",
        title="Node.js",
        category=bootstrap.BootstrapCategory.PROGRAMMING_LANGUAGES,
        executable="node",
    )
    system = {"package_managers": []}

    (detection,) = bootstrap._enrich_detections(
        bootstrap.detect_tools((spec,), system=system), system=system
    )

    duplicate = [r for r in detection.repair_recommendations if "Duplicate" in r.problem]
    assert len(duplicate) == 1
    assert str(system_copy) in duplicate[0].reason
    assert str(managed) not in duplicate[0].reason
