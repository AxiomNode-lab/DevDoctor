"""The JSON outputs are a contract: real output validates, and drift is caught."""

from __future__ import annotations

import json
from pathlib import Path

import jsonschema
import pytest
from typer.testing import CliRunner

from devdoctor import entrypoint

ROOT = Path(__file__).resolve().parent.parent
SCHEMAS = ROOT / "docs" / "schema"
runner = CliRunner(env={"NO_COLOR": "1", "TERM": "dumb", "COLUMNS": "200"})


def _schema(name: str) -> dict:
    return json.loads((SCHEMAS / f"{name}.schema.json").read_text(encoding="utf-8"))


def _validator(name: str) -> jsonschema.Draft202012Validator:
    schema = _schema(name)
    jsonschema.Draft202012Validator.check_schema(schema)
    return jsonschema.Draft202012Validator(schema)


@pytest.fixture(scope="module")
def app():
    return entrypoint.build_app()


def _json(app, *args: str) -> dict:
    result = runner.invoke(app, list(args))
    assert result.exit_code == 0, result.output
    return json.loads(result.output)


def test_inventory_output_validates(app) -> None:
    payload = _json(app, "check", "git", "docker", "python", "--json")

    assert payload["schema_version"] == 1
    _validator("inventory").validate(payload)


def test_export_json_uses_the_same_inventory_schema(app, tmp_path: Path) -> None:
    target = tmp_path / "inventory.json"
    result = runner.invoke(app, ["export", "json", "--profile", "java", "--output", str(target)])
    assert result.exit_code == 0, result.output

    _validator("inventory").validate(json.loads(target.read_text(encoding="utf-8")))


def test_project_output_validates(app) -> None:
    payload = _json(app, "project", str(ROOT), "--json")

    _validator("project").validate(payload)


def test_diff_output_validates(app, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("XDG_STATE_HOME", str(tmp_path))
    _json(app, "diff", "--tools", "git", "--json")  # baseline

    payload = _json(app, "diff", "--tools", "git", "--json")

    _validator("diff").validate(payload)


def test_schema_rejects_a_renamed_tool_field(app) -> None:
    payload = _json(app, "check", "git", "--json")
    tool = payload["tools"][0]
    tool["healthy"] = tool.pop("health")

    with pytest.raises(jsonschema.ValidationError):
        _validator("inventory").validate(payload)


def test_schema_rejects_an_unknown_health_value(app) -> None:
    payload = _json(app, "check", "git", "--json")
    payload["tools"][0]["health"] = "fine"

    with pytest.raises(jsonschema.ValidationError):
        _validator("inventory").validate(payload)


def test_every_schema_declares_its_id_and_version() -> None:
    for name in ("inventory", "project", "diff"):
        schema = _schema(name)
        assert schema["$schema"] == "https://json-schema.org/draft/2020-12/schema"
        assert schema["$id"].endswith(f"/docs/schema/{name}.schema.json")
        assert schema["properties"]["schema_version"]["const"] == 1


def test_schema_family_enum_matches_the_package_manager_table() -> None:
    from devdoctor.package_managers import PACKAGE_MANAGERS

    families = _schema("inventory")["$defs"]["package_manager"]["properties"]["family"]["enum"]

    assert set(families) == {manager[3] for manager in PACKAGE_MANAGERS}
