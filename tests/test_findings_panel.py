"""The report opens with what is wrong and what to do — the doctor's note, not the inventory."""

from __future__ import annotations

from pathlib import Path

import pytest
from rich.console import Console

from devdoctor import bootstrap
from devdoctor.bootstrap import BootstrapInventory, ToolSpec
from devdoctor.ui.bootstrap import bootstrap_group, findings_panel
from devdoctor.ui.theme import devdoctor_theme


def _tool(bin_dir: Path, name: str, body: str) -> None:
    bin_dir.mkdir(parents=True, exist_ok=True)
    script = bin_dir / name
    script.write_text(body, encoding="utf-8")
    script.chmod(0o755)


def _inventory(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> BootstrapInventory:
    bin_dir = tmp_path / "bin"
    # git answers --version but has no user.name/user.email configured -> warning
    _tool(bin_dir, "git", '#!/bin/sh\n[ "$1" = config ] && exit 1\necho "git version 2.0.0"\n')
    # pip launcher with a dead interpreter -> broken
    _tool(bin_dir, "pip", "#!/nonexistent/python\n")
    # curl is fine -> ready
    _tool(bin_dir, "curl", '#!/bin/sh\necho "curl 8.0.0"\n')
    monkeypatch.setenv("PATH", str(bin_dir))
    specs = tuple(
        ToolSpec(
            id=n, title=n, category=bootstrap.BootstrapCategory.TERMINAL_UTILITIES, executable=n
        )
        for n in ("git", "pip", "curl")
    )
    system = {"package_managers": [], "path_analysis": {"issues": [], "shadowed_executables": []}}
    detections = bootstrap._enrich_detections(
        bootstrap.detect_tools(specs, system=system), system=system
    )
    return BootstrapInventory(system=system, detections=detections, profiles=())


def _render(renderable: object) -> str:
    console = Console(width=160, record=True, color_system=None, theme=devdoctor_theme())
    console.print(renderable)
    return console.export_text()


def test_findings_panel_lists_problems_with_one_action_each(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    text = _render(findings_panel(_inventory(monkeypatch, tmp_path)))

    assert "Findings" in text
    assert "pip" in text and text.count("broken shebang") == 1  # said once, not per source
    assert "git" in text and "user.name is not configured" in text
    assert "git config --global --edit" in text
    assert "curl" not in text  # healthy tools are not findings


def test_findings_come_before_the_host_panel_in_the_report(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    text = _render(bootstrap_group(_inventory(monkeypatch, tmp_path)))

    assert text.index("Findings") < text.index("Host")


def test_no_findings_is_said_in_one_line(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    bin_dir = tmp_path / "bin"
    _tool(bin_dir, "curl", '#!/bin/sh\necho "curl 8.0.0"\n')
    monkeypatch.setenv("PATH", str(bin_dir))
    spec = ToolSpec(
        id="curl",
        title="curl",
        category=bootstrap.BootstrapCategory.TERMINAL_UTILITIES,
        executable="curl",
    )
    system = {"package_managers": []}
    detections = bootstrap._enrich_detections(
        bootstrap.detect_tools((spec,), system=system), system=system
    )

    text = _render(
        findings_panel(BootstrapInventory(system=system, detections=detections, profiles=()))
    )

    assert "No problems found" in text
    assert "1 installed tool" in text
