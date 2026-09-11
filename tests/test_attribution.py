"""DevDoctor is an AxiomNode project; every surface a user reads should say so."""

from __future__ import annotations

import importlib.util
import tomllib
from pathlib import Path

from typer.testing import CliRunner

import devdoctor
from devdoctor.bootstrap import BootstrapInventory
from devdoctor.cli import app
from devdoctor.exporters.bootstrap import render_bootstrap_html, render_bootstrap_markdown

ROOT = Path(__file__).resolve().parent.parent
COPYRIGHT = "Copyright (c) 2026 AxiomNode"


def _empty_inventory() -> BootstrapInventory:
    return BootstrapInventory(system={"package_managers": []}, detections=(), profiles=())


def test_package_declares_author_and_copyright() -> None:
    assert devdoctor.__author__ == "AxiomNode"
    assert devdoctor.__copyright__ == COPYRIGHT
    assert devdoctor.__license__ == "MIT"


def test_version_flag_names_the_copyright_holder_and_license() -> None:
    result = CliRunner().invoke(app, ["--version", "--no-color"])

    assert result.exit_code == 0
    assert f"devdoctor {devdoctor.__version__}" in result.output
    assert COPYRIGHT in result.output
    assert "MIT" in result.output


def test_html_report_footer_carries_attribution() -> None:
    html = render_bootstrap_html(_empty_inventory())

    assert "<footer" in html
    assert COPYRIGHT in html
    assert "https://axiomnode.tech/" in html


def test_markdown_report_footer_carries_attribution() -> None:
    markdown = render_bootstrap_markdown(_empty_inventory())

    assert markdown.rstrip().endswith(f"{COPYRIGHT}. MIT License.")


def test_pyproject_names_axiomnode() -> None:
    project = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))["project"]

    assert {"name": "AxiomNode", "email": "info@axiomnode.tech"} in project["authors"]
    assert project["urls"]["Organization"] == "https://axiomnode.tech/"


def test_license_file_names_axiomnode() -> None:
    assert COPYRIGHT in (ROOT / "LICENSE").read_text(encoding="utf-8")


def test_sbom_root_package_carries_copyright_and_supplier(tmp_path: Path) -> None:
    spec = importlib.util.spec_from_file_location(
        "generate_sbom", ROOT / "scripts/generate_sbom.py"
    )
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    dist = tmp_path / "dist"
    dist.mkdir()
    (dist / "devdoctor_workstation-0.0.0-py3-none-any.whl").write_bytes(b"wheel")

    document = module.build_sbom(ROOT / "pyproject.toml", dist)

    root = document["packages"][0]
    assert root["copyrightText"] == COPYRIGHT
    assert root["supplier"] == "Organization: AxiomNode"
    assert "Organization: AxiomNode" in document["creationInfo"]["creators"]


def test_legacy_health_exporters_carry_attribution() -> None:
    from datetime import UTC, datetime

    from devdoctor.exporters.html import render_html
    from devdoctor.exporters.markdown import render_markdown
    from devdoctor.models import HealthReport

    report = HealthReport(
        generated_at=datetime(2026, 1, 1, tzinfo=UTC),
        duration_seconds=0.1,
        score=100,
        results=(),
        recommendations=(),
    )

    assert COPYRIGHT in render_html(report)
    assert COPYRIGHT in render_markdown(report)


def test_support_report_names_the_project_owner() -> None:
    from devdoctor.support_report import render_support_markdown

    assert "AxiomNode" in render_support_markdown({"platform": {}, "path": {}})
