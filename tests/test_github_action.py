"""`uses: AxiomNode-lab/DevDoctor@main` must run `devdoctor project` on the caller's repo."""

from __future__ import annotations

from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
ACTION = ROOT / "action.yml"


def _action() -> dict:
    return yaml.safe_load(ACTION.read_text(encoding="utf-8"))


def test_action_is_a_composite_action_with_documented_inputs() -> None:
    action = _action()

    assert action["runs"]["using"] == "composite"
    assert set(action["inputs"]) >= {"path", "fail-on-mismatch", "ref"}
    assert action["inputs"]["path"]["default"] == "."
    assert action["inputs"]["fail-on-mismatch"]["default"] == "true"
    assert action["inputs"]["ref"]["default"] == "main"
    assert action["branding"]["icon"] and action["branding"]["color"]


def test_action_installs_from_the_repository_and_runs_project_check() -> None:
    steps = _action()["runs"]["steps"]
    commands = "\n".join(step.get("run", "") for step in steps)

    assert "git+https://github.com/AxiomNode-lab/DevDoctor.git@${{ inputs.ref }}" in commands
    assert "devdoctor project" in commands
    assert "--json" in commands
    assert "--no-fail" in commands  # used when fail-on-mismatch is false
    assert "GITHUB_STEP_SUMMARY" in commands
    assert all(step.get("shell") == "bash" for step in steps if "run" in step)


def test_repository_dogfoods_the_action() -> None:
    workflow = yaml.safe_load(
        (ROOT / ".github/workflows/project-check.yml").read_text(encoding="utf-8")
    )
    uses = [step.get("uses") for job in workflow["jobs"].values() for step in job["steps"]]

    assert "./" in uses
