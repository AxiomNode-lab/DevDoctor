"""Inventory snapshots and the diff between two of them.

A snapshot is the small, stable part of a scan that is worth comparing later:
per tool, whether it is installed, its health, version, and path; plus the
PATH issue count. `devdoctor` writes one after every full scan and
`devdoctor diff` answers "what changed since then?".
"""

from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from devdoctor.bootstrap import BootstrapInventory
from devdoctor.paths import last_inventory_path

SCHEMA_VERSION = 1  # snapshot file format
DIFF_SCHEMA_VERSION = 1  # `devdoctor diff --json` output

# Order in which kinds of change are reported: problems first.
_KIND_ORDER = {"disappeared": 0, "health": 1, "version": 2, "path": 3, "appeared": 4}


def snapshot_from_inventory(inventory: BootstrapInventory) -> dict[str, Any]:
    """Reduce an inventory to the fields a later diff compares."""

    tools: dict[str, dict[str, Any]] = {}
    for detection in inventory.detections:
        tools[detection.spec.id] = {
            "id": detection.spec.id,
            "title": detection.spec.title,
            "installed": detection.installed,
            "health": detection.health.value,
            "version": detection.version,
            "path": detection.executable_path,
        }
    return {
        "schema_version": SCHEMA_VERSION,
        "generated_at": datetime.now(UTC).isoformat(timespec="seconds"),
        "path_issue_count": int(inventory.system.get("path_issue_count") or 0),
        "tools": tools,
    }


def save(snapshot: Mapping[str, Any]) -> None:
    """Persist a snapshot as the new baseline."""

    path = last_inventory_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(snapshot, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def load() -> dict[str, Any] | None:
    """Return the saved baseline, or None when there is none or it is unreadable."""

    path = last_inventory_path()
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    if not isinstance(payload, dict) or not isinstance(payload.get("tools"), dict):
        return None
    return payload


@dataclass(frozen=True, slots=True)
class DiffEntry:
    """One tool whose recorded state differs between two snapshots."""

    tool_id: str
    title: str
    kind: str  # appeared | disappeared | health | version | path
    before: str | None
    after: str | None

    def to_dict(self) -> dict[str, Any]:
        return {
            "tool_id": self.tool_id,
            "title": self.title,
            "kind": self.kind,
            "before": self.before,
            "after": self.after,
        }


@dataclass(frozen=True, slots=True)
class InventoryDiff:
    """Everything that changed between a baseline and a fresh scan."""

    since: str | None
    entries: tuple[DiffEntry, ...]
    path_issues: tuple[int, int]

    @property
    def changed(self) -> bool:
        return bool(self.entries) or self.path_issues[0] != self.path_issues[1]

    def to_dict(self) -> dict[str, Any]:
        return {
            # Contract: docs/schema/diff.schema.json.
            "schema_version": DIFF_SCHEMA_VERSION,
            "since": self.since,
            "changed": self.changed,
            "path_issues": {"before": self.path_issues[0], "after": self.path_issues[1]},
            "entries": [entry.to_dict() for entry in self.entries],
        }


def compare(before: Mapping[str, Any], after: Mapping[str, Any]) -> InventoryDiff:
    """Diff two snapshots. Tools known on one side only count as appeared/disappeared."""

    old_tools: Mapping[str, Mapping[str, Any]] = before.get("tools", {})
    new_tools: Mapping[str, Mapping[str, Any]] = after.get("tools", {})
    entries: list[DiffEntry] = []

    for tool_id in sorted(set(old_tools) | set(new_tools)):
        old = old_tools.get(tool_id)
        new = new_tools.get(tool_id)
        title = str((new or old or {}).get("title") or tool_id)
        old_installed = bool(old and old.get("installed"))
        new_installed = bool(new and new.get("installed"))

        if new_installed and not old_installed:
            entries.append(DiffEntry(tool_id, title, "appeared", None, _state(new)))
            continue
        if old_installed and not new_installed:
            entries.append(DiffEntry(tool_id, title, "disappeared", _state(old), None))
            continue
        if not (old_installed and new_installed):
            continue  # missing on both sides: nothing to say

        assert old is not None and new is not None
        if old.get("health") != new.get("health"):
            entries.append(
                DiffEntry(tool_id, title, "health", str(old.get("health")), str(new.get("health")))
            )
        elif old.get("version") != new.get("version"):
            entries.append(
                DiffEntry(
                    tool_id, title, "version", _text(old.get("version")), _text(new.get("version"))
                )
            )
        elif old.get("path") != new.get("path"):
            entries.append(
                DiffEntry(tool_id, title, "path", _text(old.get("path")), _text(new.get("path")))
            )

    entries.sort(key=lambda entry: (_KIND_ORDER.get(entry.kind, 9), entry.tool_id))
    return InventoryDiff(
        since=before.get("generated_at"),
        entries=tuple(entries),
        path_issues=(
            int(before.get("path_issue_count") or 0),
            int(after.get("path_issue_count") or 0),
        ),
    )


def _state(tool: Mapping[str, Any]) -> str:
    version = tool.get("version")
    return f"{tool.get('health')} {version}".strip() if version else str(tool.get("health"))


def _text(value: Any) -> str | None:
    return None if value is None else str(value)
