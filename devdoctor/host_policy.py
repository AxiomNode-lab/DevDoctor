"""Host classification shared by the planner, the CLI, and the legacy policy modules.

Pure functions over already-collected data: nothing here probes the machine, so
the planner can ask "is this an Atomic host?" for every tool without launching a
process each time.
"""

from __future__ import annotations

from collections.abc import Mapping

from devdoctor.models import JsonValue
from devdoctor.package_managers import ATOMIC_VARIANTS

# Managers to try on an image-based host before layering the base image.
ATOMIC_USER_SPACE_ORDER: tuple[str, ...] = (
    "brew",
    "flatpak",
    "nix",
    "cargo",
    "npm",
    "pnpm",
    "pipx",
    "pip",
)

_ATOMIC_MARKERS = (*ATOMIC_VARIANTS, "atomic", "ostree")


def installed_manager_ids(system: Mapping[str, JsonValue]) -> set[str]:
    """Return the ids of package managers the system context recorded as installed."""

    managers = system.get("package_managers", ())
    if not isinstance(managers, list):
        return set()
    return {
        str(manager.get("id"))
        for manager in managers
        if isinstance(manager, Mapping) and manager.get("installed") is True
    }


def release_is_atomic(release: Mapping[str, str]) -> bool:
    """Classify an os-release mapping as an image-based (rpm-ostree) host."""

    distro_id = release.get("ID", "").lower()
    variant_id = release.get("VARIANT_ID", "").lower()
    image_id = release.get("IMAGE_ID", "").lower()
    return (
        distro_id == "bazzite"
        or variant_id in ATOMIC_VARIANTS
        or image_id in ATOMIC_VARIANTS
        or bool(release.get("OSTREE_VERSION"))
    )


def system_is_atomic(system: Mapping[str, JsonValue]) -> bool:
    """Use the persisted host classification instead of re-probing managers per tool.

    A merely present ``rpm-ostree`` executable on mutable Fedora is not evidence;
    the release data or the distribution name has to say so.
    """

    if "atomic_host" in system:
        return system.get("atomic_host") is True

    distro_id = str(system.get("distribution_id", "")).lower()
    if distro_id == "bazzite":
        return True

    if "rpm-ostree" not in installed_manager_ids(system):
        return False

    distribution = str(system.get("distribution", "")).lower()
    if any(marker in distribution for marker in _ATOMIC_MARKERS):
        return True

    return distro_id in {"ublue", "universal-blue"}
