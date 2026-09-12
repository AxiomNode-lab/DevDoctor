"""examples/plugin is a working third-party catalog plugin, not a sketch."""

from __future__ import annotations

import importlib.util
import tomllib
from pathlib import Path

from devdoctor.bootstrap import BOOTSTRAP_TOOL_ENTRY_POINT_GROUP, ToolSpec

EXAMPLE = Path(__file__).resolve().parent.parent / "examples" / "plugin"


def test_example_plugin_declares_the_bootstrap_tools_entry_point() -> None:
    project = tomllib.loads((EXAMPLE / "pyproject.toml").read_text(encoding="utf-8"))["project"]

    entry_points = project["entry-points"][BOOTSTRAP_TOOL_ENTRY_POINT_GROUP]
    assert entry_points == {"example": "devdoctor_example_plugin:get_tools"}


def test_example_plugin_returns_valid_tool_specs() -> None:
    spec = importlib.util.spec_from_file_location(
        "devdoctor_example_plugin", EXAMPLE / "devdoctor_example_plugin" / "__init__.py"
    )
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)

    tools = module.get_tools()

    assert tools and all(isinstance(tool, ToolSpec) for tool in tools)
    assert {tool.id for tool in tools} == {"lazygit", "tldr"}
    assert all(tool.packages for tool in tools)  # every example tool has an install mapping
    assert all(tool.website for tool in tools)
