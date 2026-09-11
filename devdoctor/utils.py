"""Shared utilities for process execution, version parsing, and formatting."""

from __future__ import annotations

import getpass
import os
import re
import socket
import subprocess
import time
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True, slots=True)
class CommandResult:
    """Result of a subprocess execution."""

    command: tuple[str, ...]
    returncode: int
    stdout: str
    stderr: str
    duration_seconds: float

    @property
    def combined_output(self) -> str:
        """Return stdout and stderr as one trimmed string."""

        return "\n".join(part for part in (self.stdout.strip(), self.stderr.strip()) if part)


def run_command(command: Sequence[str], timeout: float = 5.0) -> CommandResult:
    """Run a command without a shell and capture output."""

    started_at = time.perf_counter()
    try:
        completed = subprocess.run(
            list(command),
            capture_output=True,
            check=False,
            text=True,
            timeout=timeout,
        )
        return CommandResult(
            command=tuple(command),
            returncode=completed.returncode,
            stdout=completed.stdout,
            stderr=completed.stderr,
            duration_seconds=time.perf_counter() - started_at,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        return CommandResult(
            command=tuple(command),
            returncode=124,
            stdout="",
            stderr=str(exc),
            duration_seconds=time.perf_counter() - started_at,
        )


def parse_version(output: str) -> str | None:
    """Extract a human-readable version token from command output."""

    normalized = output.strip().replace("\x00", "")
    if not normalized:
        return None

    patterns = (
        r"(?i)\bversion\s+v?([0-9]+(?:\.[0-9A-Za-z][0-9A-Za-z.+-]*)*)",
        r"(?i)\bgo([0-9]+(?:\.[0-9A-Za-z][0-9A-Za-z.+-]*)*)",
        r"(?i)\bv([0-9]+\.[0-9A-Za-z][0-9A-Za-z.+-]*)",
        # OpenSSH_9.6p1 style: the product name is glued to the version with "_".
        r"(?<=_)([0-9]+\.[0-9A-Za-z][0-9A-Za-z.+-]*)",
        r"\b([0-9]+(?:\.[0-9A-Za-z][0-9A-Za-z.+-]*){1,})\b",
    )
    lines = [line.strip() for line in normalized.splitlines() if line.strip()]
    for candidate in (*lines[:3], normalized):
        for pattern in patterns:
            match = re.search(pattern, candidate)
            if match:
                return match.group(1)
    # No version-shaped token: report nothing rather than an error message or
    # banner text masquerading as a version.
    return None


def format_bytes(value: int | float) -> str:
    """Format bytes using binary units."""

    size = float(value)
    units = ("B", "KiB", "MiB", "GiB", "TiB", "PiB")
    for unit in units:
        if abs(size) < 1024.0 or unit == units[-1]:
            return f"{size:.1f} {unit}"
        size /= 1024.0
    return f"{size:.1f} PiB"


def format_duration(seconds: int | float) -> str:
    """Format seconds as a concise uptime string."""

    total = int(seconds)
    days, remainder = divmod(total, 86_400)
    hours, remainder = divmod(remainder, 3_600)
    minutes, _ = divmod(remainder, 60)
    parts: list[str] = []
    if days:
        parts.append(f"{days}d")
    if hours:
        parts.append(f"{hours}h")
    if minutes or not parts:
        parts.append(f"{minutes}m")
    return " ".join(parts)


def read_os_release(path: Path = Path("/etc/os-release")) -> Mapping[str, str]:
    """Read os-release data without raising on malformed files."""

    data: dict[str, str] = {}
    try:
        for line in path.read_text(encoding="utf-8").splitlines():
            stripped = line.strip()
            if not stripped or stripped.startswith("#") or "=" not in stripped:
                continue
            key, value = stripped.split("=", 1)
            data[key] = value.strip().strip('"')
    except OSError:
        return {}
    return data


def get_username() -> str:
    """Return the current username with fallbacks for unusual environments."""

    try:
        return getpass.getuser()
    except OSError:
        return os.environ.get("USER") or os.environ.get("LOGNAME") or "unknown"


def get_hostname() -> str:
    """Return the current hostname."""

    try:
        return socket.gethostname()
    except OSError:
        return "unknown"


def measure_tcp_latency(host: str, port: int, timeout: float) -> float | None:
    """Measure TCP connect latency in milliseconds."""

    started_at = time.perf_counter()
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return (time.perf_counter() - started_at) * 1000
    except OSError:
        return None
