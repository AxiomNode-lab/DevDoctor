"""PATH inspection for workstation bootstrap diagnostics."""

from __future__ import annotations

import os
import shutil
from collections import Counter
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path

from devdoctor.models import JsonValue


@dataclass(frozen=True, slots=True)
class PathIssue:
    """A concrete issue found in the current PATH."""

    kind: str
    path: str
    problem: str
    recommendation: str
    export_command: str | None = None

    def to_dict(self) -> dict[str, JsonValue]:
        """Convert the issue to JSON data."""

        return {
            "kind": self.kind,
            "path": self.path,
            "problem": self.problem,
            "recommendation": self.recommendation,
            "export_command": self.export_command,
        }


@dataclass(frozen=True, slots=True)
class ShadowedExecutable:
    """An executable that appears more than once in PATH."""

    executable: str
    primary_path: str
    shadowed_paths: tuple[str, ...]

    def to_dict(self) -> dict[str, JsonValue]:
        """Convert the shadowing record to JSON data."""

        return {
            "executable": self.executable,
            "primary_path": self.primary_path,
            "shadowed_paths": list(self.shadowed_paths),
        }


@dataclass(frozen=True, slots=True)
class PathAnalysis:
    """Full analysis of the current PATH value."""

    entries: tuple[str, ...]
    issues: tuple[PathIssue, ...]
    shadowed_executables: tuple[ShadowedExecutable, ...]
    cleanup_command: str | None = None

    def to_dict(self) -> dict[str, JsonValue]:
        """Convert the analysis to JSON data."""

        return {
            "entries": list(self.entries),
            "issue_count": len(self.issues),
            "issues": [issue.to_dict() for issue in self.issues],
            "shadowed_executables": [shadowed.to_dict() for shadowed in self.shadowed_executables],
            "cleanup_command": self.cleanup_command,
        }


def analyze_path(
    path_value: str | None = None,
    *,
    executables: Iterable[str] = (),
    home: Path | None = None,
) -> PathAnalysis:
    """Analyze PATH entries and executable shadowing without mutating the system."""

    raw_entries = (path_value if path_value is not None else os.environ.get("PATH", "")).split(
        os.pathsep
    )
    home_dir = home or Path.home()
    issues: list[PathIssue] = []
    removable: set[str] = set()
    normalized_entries = tuple(entry for entry in raw_entries if entry)
    counter = Counter(normalized_entries)

    for index, entry in enumerate(raw_entries):
        if not entry:
            issues.append(
                PathIssue(
                    kind="empty_entry",
                    path=".",
                    problem=(
                        "PATH contains an empty entry, which makes the current "
                        "directory searchable."
                    ),
                    recommendation=(
                        "Remove empty PATH segments created by leading, trailing, "
                        "or repeated separators."
                    ),
                )
            )
            continue

        path = Path(entry).expanduser()
        if counter[entry] > 1:
            issues.append(
                PathIssue(
                    kind="duplicate_entry",
                    path=entry,
                    problem="PATH contains this directory more than once.",
                    recommendation="Keep the first occurrence and remove later duplicates.",
                )
            )
        if not path.exists():
            issues.append(
                PathIssue(
                    kind="missing_directory",
                    path=entry,
                    problem="PATH entry does not exist.",
                    recommendation="Create the directory or remove it from PATH.",
                )
            )
            removable.add(entry)
            continue
        if not path.is_dir():
            issues.append(
                PathIssue(
                    kind="not_directory",
                    path=entry,
                    problem="PATH entry exists but is not a directory.",
                    recommendation="Remove the file from PATH.",
                )
            )
            removable.add(entry)
            continue
        if not os.access(path, os.R_OK | os.X_OK):
            issues.append(
                PathIssue(
                    kind="not_searchable",
                    path=entry,
                    problem="PATH directory is not searchable by the current user.",
                    recommendation=f"Review permissions: ls -ld {entry}",
                )
            )
        if index > 0 and raw_entries[index - 1] == entry:
            continue

    for candidate in _common_user_bins(home_dir):
        if candidate.exists() and str(candidate) not in normalized_entries:
            issues.append(
                PathIssue(
                    kind="not_exported",
                    path=str(candidate),
                    problem="Common user binary directory exists but is not exported in PATH.",
                    recommendation="Add the directory to PATH in your shell profile.",
                    export_command=f'export PATH="{candidate}:$PATH"',
                )
            )

    shadowed = tuple(
        shadow
        for executable in sorted(set(executables))
        if (shadow := _shadowed_executable(executable, normalized_entries)) is not None
    )
    return PathAnalysis(
        entries=normalized_entries,
        issues=tuple(issues),
        shadowed_executables=shadowed,
        cleanup_command=_cleanup_export_command(normalized_entries, removable),
    )


def executable_paths(executable: str, path_entries: Iterable[str] | None = None) -> tuple[str, ...]:
    """Return all matching executable paths in PATH order.

    When inspecting the process PATH directly, the primary command lookup is the
    authority: if ``shutil.which`` cannot resolve the command, alternate-path
    scanning must not contradict that result. Explicit ``path_entries`` remain
    independently inspectable for deterministic PATH analysis and tests.
    """

    if path_entries is None and shutil.which(executable) is None:
        return ()

    entries = tuple(path_entries or os.environ.get("PATH", "").split(os.pathsep))
    matches: list[str] = []
    seen: set[str] = set()
    for entry in entries:
        if not entry:
            continue
        candidate = Path(entry) / executable
        executable_exists = candidate.exists() and os.access(candidate, os.X_OK)
        broken_symlink = candidate.is_symlink() and not candidate.exists()
        if executable_exists or broken_symlink:
            rendered = str(candidate)
            identity = os.path.realpath(rendered)
            if identity in seen:
                continue
            matches.append(rendered)
            seen.add(identity)
    return tuple(matches)


def _shadowed_executable(
    executable: str,
    entries: Iterable[str],
) -> ShadowedExecutable | None:
    paths = executable_paths(executable, entries)
    if len(paths) <= 1:
        return None
    return ShadowedExecutable(
        executable=executable,
        primary_path=paths[0],
        shadowed_paths=paths[1:],
    )


def _common_user_bins(home: Path) -> tuple[Path, ...]:
    return (
        home / ".local/bin",
        home / ".cargo/bin",
        home / "go/bin",
        home / ".bun/bin",
        home / ".deno/bin",
    )


def _cleanup_export_command(entries: Iterable[str], removable: set[str]) -> str | None:
    """Return one ``export PATH`` line with dead entries and duplicates dropped."""

    if not removable:
        return None
    kept: list[str] = []
    for entry in entries:
        if entry in removable or entry in kept:
            continue
        kept.append(entry)
    return f'export PATH="{os.pathsep.join(kept) if kept else "${PATH}"}"'
