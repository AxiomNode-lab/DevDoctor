"""Version probes run concurrently: a scan should cost about one slow tool, not the sum."""

from __future__ import annotations

import time
from pathlib import Path

import pytest

from devdoctor import bootstrap
from devdoctor.bootstrap import ToolSpec


def _slow_tool(bin_dir: Path, name: str, seconds: float) -> None:
    bin_dir.mkdir(parents=True, exist_ok=True)
    tool = bin_dir / name
    tool.write_text(f"#!/bin/sh\n/bin/sleep {seconds}\necho '{name} 1.0.0'\n", encoding="utf-8")
    tool.chmod(0o755)


def test_detect_tools_probes_versions_in_parallel(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    bin_dir = tmp_path / "bin"
    names = [f"slow{i}" for i in range(6)]
    for name in names:
        _slow_tool(bin_dir, name, 0.4)
    monkeypatch.setenv("PATH", str(bin_dir))
    specs = tuple(
        ToolSpec(
            id=name,
            title=name,
            category=bootstrap.BootstrapCategory.TERMINAL_UTILITIES,
            executable=name,
        )
        for name in names
    )

    started = time.perf_counter()
    detections = bootstrap.detect_tools(specs, system={"package_managers": []})
    elapsed = time.perf_counter() - started

    assert [d.spec.id for d in detections] == names  # catalog order is preserved
    assert all(d.installed and d.version == "1.0.0" for d in detections)
    assert elapsed < 6 * 0.4 * 0.6, f"sequential-looking scan: {elapsed:.2f}s for 6 x 0.4s probes"


def test_enrichment_probes_run_in_parallel(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    # docker -> `docker info`, git -> two `git config` reads, python -> `python -m pip`.
    # Each fake command sleeps 0.4s whatever its arguments.
    bin_dir = tmp_path / "bin"
    for name in ("docker", "git", "python3"):
        _slow_tool(bin_dir, name, 0.4)
    monkeypatch.setenv("PATH", str(bin_dir))
    specs = tuple(
        ToolSpec(
            id=tool_id,
            title=tool_id,
            category=bootstrap.BootstrapCategory.TERMINAL_UTILITIES,
            executable=executable,
        )
        for tool_id, executable in (("docker", "docker"), ("git", "git"), ("python", "python3"))
    )
    system = {"package_managers": []}
    detections = bootstrap.detect_tools(specs, system=system)

    started = time.perf_counter()
    enriched = bootstrap._enrich_detections(detections, system=system)
    elapsed = time.perf_counter() - started

    assert [d.spec.id for d in enriched] == ["docker", "git", "python"]
    assert elapsed < 1.3, f"sequential-looking enrichment: {elapsed:.2f}s (git alone needs 0.8s)"
