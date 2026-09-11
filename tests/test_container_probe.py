"""The distro-integration probe must ask each package manager the right question."""

from __future__ import annotations

import importlib.util
import os
from pathlib import Path

import pytest

PROBE = Path(__file__).parent / "integration" / "container_probe.py"


def _load_probe():
    spec = importlib.util.spec_from_file_location("container_probe", PROBE)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def _fake_manager(bin_dir: Path, name: str, known: str) -> None:
    # Exit 0 only when the last argument is the one package the fake "knows".
    bin_dir.mkdir(parents=True, exist_ok=True)
    script = bin_dir / name
    script.write_text(
        "#!/bin/sh\n"
        f'for arg in "$@"; do last="$arg"; done\n'
        f'[ "$last" = "{known}" ] && exit 0\n'
        "exit 1\n",
        encoding="utf-8",
    )
    script.chmod(0o755)


@pytest.mark.parametrize("manager", ["pacman", "zypper"])
def test_package_exists_asks_the_host_manager(
    manager: str, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    bin_dir = tmp_path / "bin"
    _fake_manager(bin_dir, manager, "git")
    monkeypatch.setenv("PATH", f"{bin_dir}{os.pathsep}/usr/bin{os.pathsep}/bin")
    probe = _load_probe()

    assert probe._package_exists(manager, "git") is True
    assert probe._package_exists(manager, "no-such-package") is False


def test_verify_catalog_packages_accepts_pacman_and_zypper() -> None:
    probe = _load_probe()
    parser = probe._build_parser()

    for manager in ("apt", "dnf", "pacman", "zypper"):
        args = parser.parse_args(
            ["--expected-manager", manager, "--verify-catalog-packages", manager]
        )
        assert args.verify_catalog_packages == manager
