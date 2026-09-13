"""`devdoctor diff`: what changed on this machine since the last full scan."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from typer.testing import CliRunner

from devdoctor import entrypoint, paths, snapshots

runner = CliRunner(env={"NO_COLOR": "1", "TERM": "dumb", "COLUMNS": "200"})


def _tool(
    tool_id: str,
    *,
    installed: bool = True,
    health: str = "ready",
    version: str | None = "1.0",
    path: str | None = "/usr/bin/x",
) -> dict:
    return {
        "id": tool_id,
        "title": tool_id.title(),
        "installed": installed,
        "health": health,
        "version": version,
        "path": path,
    }


def _snapshot(*tools: dict, path_issues: int = 0, at: str = "2026-01-01T00:00:00+00:00") -> dict:
    return {
        "schema_version": 1,
        "generated_at": at,
        "path_issue_count": path_issues,
        "tools": {t["id"]: t for t in tools},
    }


# --- comparison ---------------------------------------------------------------


def test_compare_reports_nothing_when_nothing_changed() -> None:
    snap = _snapshot(_tool("git"), _tool("node", version="20.1"))

    diff = snapshots.compare(snap, snap)

    assert diff.changed is False
    assert diff.entries == ()


def test_compare_reports_appeared_disappeared_health_and_version_changes() -> None:
    before = _snapshot(
        _tool("git", version="2.43.0"),
        _tool("node", version="20.1"),
        _tool("docker", installed=False, health="missing", version=None, path=None),
        _tool("pip", health="broken"),
        path_issues=3,
    )
    after = _snapshot(
        _tool("git", version="2.45.0"),
        _tool("node", installed=False, health="missing", version=None, path=None),
        _tool("docker", version="27.0"),
        _tool("pip", health="ready"),
        path_issues=1,
    )

    diff = snapshots.compare(before, after)

    kinds = {entry.tool_id: entry.kind for entry in diff.entries}
    assert kinds == {"git": "version", "node": "disappeared", "docker": "appeared", "pip": "health"}
    git = next(e for e in diff.entries if e.tool_id == "git")
    assert (git.before, git.after) == ("2.43.0", "2.45.0")
    pip = next(e for e in diff.entries if e.tool_id == "pip")
    assert (pip.before, pip.after) == ("broken", "ready")
    assert diff.path_issues == (3, 1)
    assert diff.changed is True


def test_compare_orders_problems_first() -> None:
    before = _snapshot(
        _tool("a"), _tool("b", version="1"), _tool("c", installed=False, health="missing")
    )
    after = _snapshot(
        _tool("a", installed=False, health="missing", version=None),
        _tool("b", version="2"),
        _tool("c"),
    )

    kinds = [entry.kind for entry in snapshots.compare(before, after).entries]

    assert kinds == ["disappeared", "version", "appeared"]


def test_compare_tolerates_tools_only_known_on_one_side() -> None:
    # A catalog/plugin change should not crash a diff.
    before = _snapshot(_tool("git"))
    after = _snapshot(_tool("git"), _tool("lazygit"))

    diff = snapshots.compare(before, after)

    assert [e.tool_id for e in diff.entries] == ["lazygit"]
    assert diff.entries[0].kind == "appeared"


def test_diff_to_dict_is_json_serialisable() -> None:
    diff = snapshots.compare(
        _snapshot(_tool("git", version="1")), _snapshot(_tool("git", version="2"))
    )

    payload = json.loads(json.dumps(diff.to_dict()))

    assert payload["changed"] is True
    assert payload["entries"][0] == {
        "tool_id": "git",
        "title": "Git",
        "kind": "version",
        "before": "1",
        "after": "2",
    }


# --- persistence ----------------------------------------------------------------


def test_snapshot_lives_in_the_state_directory(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("XDG_STATE_HOME", str(tmp_path))

    assert paths.last_inventory_path() == tmp_path / "devdoctor" / "last-inventory.json"


def test_snapshot_roundtrip(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("XDG_STATE_HOME", str(tmp_path))
    snap = _snapshot(_tool("git"))

    snapshots.save(snap)

    assert snapshots.load() == snap


def test_load_returns_none_without_a_snapshot(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("XDG_STATE_HOME", str(tmp_path))

    assert snapshots.load() is None


# --- command --------------------------------------------------------------------


@pytest.fixture()
def state(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Path:
    monkeypatch.setenv("XDG_STATE_HOME", str(tmp_path))
    return tmp_path / "devdoctor"


def test_first_diff_records_a_baseline_and_says_so(state: Path) -> None:
    app = entrypoint.build_app()

    result = runner.invoke(app, ["diff", "--tools", "git,curl"])

    assert result.exit_code == 0, result.output
    assert "baseline" in result.output.lower()
    assert (state / "last-inventory.json").exists()


def test_diff_reports_changes_against_the_saved_snapshot(state: Path) -> None:
    app = entrypoint.build_app()
    runner.invoke(app, ["diff", "--tools", "git,curl"])
    saved = json.loads((state / "last-inventory.json").read_text(encoding="utf-8"))
    saved["tools"]["git"]["version"] = "0.0.1"  # pretend git was older last time
    saved["tools"]["curl"]["installed"] = False  # and curl was missing
    saved["tools"]["curl"]["health"] = "missing"
    (state / "last-inventory.json").write_text(json.dumps(saved), encoding="utf-8")

    result = runner.invoke(app, ["diff", "--tools", "git,curl", "--json"])

    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    kinds = {entry["tool_id"]: entry["kind"] for entry in payload["entries"]}
    assert kinds == {"git": "version", "curl": "appeared"}
    assert payload["since"] == saved["generated_at"]


def test_diff_exit_code_flag_signals_changes(state: Path) -> None:
    app = entrypoint.build_app()
    runner.invoke(app, ["diff", "--tools", "git"])
    saved = json.loads((state / "last-inventory.json").read_text(encoding="utf-8"))
    saved["tools"]["git"]["version"] = "0.0.1"
    (state / "last-inventory.json").write_text(json.dumps(saved), encoding="utf-8")

    changed = runner.invoke(app, ["diff", "--tools", "git", "--exit-code"])
    unchanged = runner.invoke(app, ["diff", "--tools", "git", "--exit-code"])

    assert changed.exit_code == 1
    assert "0.0.1" in changed.output
    assert unchanged.exit_code == 0
    assert "No changes" in unchanged.output


def test_full_report_updates_the_baseline_but_a_scoped_check_does_not(state: Path) -> None:
    app = entrypoint.build_app()

    runner.invoke(app, ["check", "git", "--quiet"])
    assert not (state / "last-inventory.json").exists()

    result = runner.invoke(app, ["--profile", "java", "--quiet"])
    assert result.exit_code == 0, result.output
    assert not (state / "last-inventory.json").exists()  # a profile is still a subset

    result = runner.invoke(app, ["--quiet"])
    assert result.exit_code == 0, result.output
    snap = json.loads((state / "last-inventory.json").read_text(encoding="utf-8"))
    assert len(snap["tools"]) >= 60  # the whole catalog
