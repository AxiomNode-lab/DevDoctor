"""Planning policy must not depend on which runtime patch ran first.

Before this suite existed, Atomic-host planning, the Nix fallback, and the
Atomic update/cache rules only took effect after ``entrypoint.main`` had
monkey-patched ``bootstrap`` and ``cli`` in the right order. Importing the
planner directly (a plugin, a test, ``python -c``) got different answers.
"""

from __future__ import annotations

import pytest

from devdoctor import atomic_planning, bootstrap, cli, fallback_planning, hardening
from devdoctor.bootstrap import BootstrapInventory


def _spec(tool_id: str) -> bootstrap.ToolSpec:
    return next(spec for spec in bootstrap.get_bootstrap_tools() if spec.id == tool_id)


def _managers(*ids: str) -> list[dict[str, object]]:
    return [{"id": manager_id, "installed": True} for manager_id in ids]


SILVERBLUE = {
    "atomic_host": True,
    "distribution": "Fedora Linux 42 (Silverblue)",
    "distribution_id": "fedora",
    "distribution_like": [],
    "package_managers": _managers("dnf", "rpm-ostree", "flatpak"),
}


def test_install_plan_never_chooses_dnf_on_an_atomic_host_without_patches() -> None:
    plan = bootstrap.install_plan_for_spec(_spec("git"), system=SILVERBLUE)

    assert plan is not None
    assert plan.manager == "rpm-ostree"
    assert plan.command == ("rpm-ostree", "install", "git")


def test_install_plan_prefers_mapped_user_space_manager_on_atomic_host() -> None:
    system = {**SILVERBLUE, "package_managers": _managers("dnf", "rpm-ostree", "brew")}

    plan = bootstrap.install_plan_for_spec(_spec("git"), system=system)

    assert plan is not None
    assert plan.manager == "brew"


def test_install_plan_falls_back_to_nix_mapping_without_patches() -> None:
    system = {"distribution_id": "unknown", "package_managers": _managers("nix")}

    plan = bootstrap.install_plan_for_spec(_spec("git"), system=system)

    assert plan is not None
    assert plan.manager == "nix"
    assert plan.requires_sudo is False


def test_detect_system_context_classifies_atomic_host_natively(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        bootstrap,
        "read_os_release",
        lambda: {"ID": "fedora", "VARIANT_ID": "silverblue", "OSTREE_VERSION": "42.1"},
    )

    context = bootstrap.detect_system_context(specs=())

    assert context["atomic_host"] is True


def test_detect_system_context_does_not_call_mutable_fedora_atomic(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(bootstrap, "read_os_release", lambda: {"ID": "fedora"})

    context = bootstrap.detect_system_context(specs=())

    assert context["atomic_host"] is False


def test_update_and_cache_commands_skip_dnf_on_atomic_host_without_patches() -> None:
    inventory = BootstrapInventory(system=SILVERBLUE, detections=(), profiles=())

    update = cli._update_commands(inventory)
    cache = cli._cache_clean_commands(inventory)

    assert ("rpm-ostree", "upgrade") in update
    assert not any("dnf" in command for command in update)
    assert not any("dnf" in command for command in cache)


def test_legacy_patch_entry_points_no_longer_replace_planner_functions() -> None:
    planner = bootstrap.install_plan_for_spec
    context = bootstrap.detect_system_context
    version = bootstrap._tool_version
    preferred = bootstrap._preferred_install_manager
    update = cli._update_commands

    atomic_planning.apply_atomic_planning_patch()
    fallback_planning.apply_fallback_planning_patch()
    hardening.apply_runtime_hardening()

    assert bootstrap.install_plan_for_spec is planner
    assert bootstrap.detect_system_context is context
    assert bootstrap._tool_version is version
    assert bootstrap._preferred_install_manager is preferred
    assert cli._update_commands is update
