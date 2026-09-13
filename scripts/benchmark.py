#!/usr/bin/env python3
"""Measure DevDoctor latency and peak resident memory in fresh subprocesses."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from statistics import mean

import psutil

_MIB = 1024 * 1024


@dataclass(frozen=True, slots=True)
class Sample:
    seconds: float
    peak_rss_bytes: int  # DevDoctor plus every child alive at the same instant
    peak_self_rss_bytes: int  # DevDoctor's own process only


def _measure_process(command: list[str], *, timeout: float = 20.0) -> Sample:
    started = time.perf_counter()
    process = subprocess.Popen(
        command,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.PIPE,
        text=True,
    )
    observed = psutil.Process(process.pid)
    peak_rss = 0
    peak_self_rss = 0
    deadline = started + timeout

    while process.poll() is None:
        if time.perf_counter() > deadline:
            process.kill()
            process.wait()
            raise RuntimeError(f"benchmark command timed out after {timeout:.0f}s")
        try:
            self_rss = observed.memory_info().rss
            rss = self_rss
            for child in observed.children(recursive=True):
                try:
                    rss += child.memory_info().rss
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    continue
            peak_self_rss = max(peak_self_rss, self_rss)
            peak_rss = max(peak_rss, rss)
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            pass
        time.sleep(0.005)

    stderr = process.stderr.read() if process.stderr is not None else ""
    elapsed = time.perf_counter() - started
    if process.returncode != 0:
        raise RuntimeError(stderr.strip() or "DevDoctor benchmark command failed")
    return Sample(seconds=elapsed, peak_rss_bytes=peak_rss, peak_self_rss_bytes=peak_self_rss)


def measure_startup(iterations: int) -> list[Sample]:
    command = [sys.executable, "-m", "devdoctor", "--version"]
    return [_measure_process(command) for _ in range(iterations)]


def measure_scan(iterations: int) -> list[Sample]:
    command = [
        sys.executable,
        "-m",
        "devdoctor",
        "check",
        "git",
        "python",
        "node",
        "--quiet",
    ]
    return [_measure_process(command) for _ in range(iterations)]


def summarize(samples: list[Sample]) -> dict[str, object]:
    seconds = [sample.seconds for sample in samples]
    rss = [sample.peak_rss_bytes / _MIB for sample in samples]
    self_rss = [sample.peak_self_rss_bytes / _MIB for sample in samples]
    ordered_seconds = sorted(seconds)
    ordered_rss = sorted(rss)
    p95_index = max(0, min(len(samples) - 1, round((len(samples) - 1) * 0.95)))
    return {
        "samples_seconds": [round(value, 4) for value in seconds],
        "min_seconds": round(min(seconds), 4),
        "mean_seconds": round(mean(seconds), 4),
        "p95_seconds": round(ordered_seconds[p95_index], 4),
        "max_seconds": round(max(seconds), 4),
        "samples_peak_rss_mib": [round(value, 2) for value in rss],
        "mean_peak_rss_mib": round(mean(rss), 2),
        "p95_peak_rss_mib": round(ordered_rss[p95_index], 2),
        "max_peak_rss_mib": round(max(rss), 2),
        "samples_peak_self_rss_mib": [round(value, 2) for value in self_rss],
        "max_peak_self_rss_mib": round(max(self_rss), 2),
    }


def _enforce_memory_budget(
    section: str,
    summary: dict[str, object],
    limit_mib: float,
    *,
    key: str = "max_peak_rss_mib",
) -> None:
    peak = float(summary[key])
    what = "self" if "self" in key else "aggregate"
    if peak > limit_mib:
        raise RuntimeError(
            f"{section} peak {what} RSS {peak:.2f} MiB exceeds budget {limit_mib:.2f} MiB"
        )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--iterations", type=int, default=5)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--max-startup-rss-mib", type=float, default=128.0)
    parser.add_argument("--max-scan-rss-mib", type=float, default=256.0)
    parser.add_argument("--max-scan-self-rss-mib", type=float, default=128.0)
    args = parser.parse_args()
    if args.iterations < 1:
        parser.error("--iterations must be >= 1")
    if min(args.max_startup_rss_mib, args.max_scan_rss_mib, args.max_scan_self_rss_mib) <= 0:
        parser.error("memory budgets must be > 0")

    startup = summarize(measure_startup(args.iterations))
    bounded_scan = summarize(measure_scan(args.iterations))
    _enforce_memory_budget("startup", startup, args.max_startup_rss_mib)
    _enforce_memory_budget("bounded scan", bounded_scan, args.max_scan_rss_mib)
    _enforce_memory_budget(
        "bounded scan", bounded_scan, args.max_scan_self_rss_mib, key="max_peak_self_rss_mib"
    )

    result = {
        "schema_version": 2,
        "iterations": args.iterations,
        "startup": startup,
        "bounded_scan": bounded_scan,
        "memory_budgets_mib": {
            "startup": args.max_startup_rss_mib,
            "bounded_scan": args.max_scan_rss_mib,
            "bounded_scan_self": args.max_scan_self_rss_mib,
        },
        "notes": [
            "Startup executes `python -m devdoctor --version` in a fresh subprocess.",
            "Bounded scan executes the hardened CLI for git, python, and node.",
            "Package-manager versions are reused for matching executable paths.",
            "Peak RSS includes observed child processes and is sampled every 5 ms.",
            "Peak self RSS is DevDoctor's own process; probes run concurrently, so the "
            "aggregate rises with the number of probe workers while self RSS does not.",
            "CI results are regression budgets, not workstation memory guarantees.",
        ],
    }
    rendered = json.dumps(result, indent=2, sort_keys=True) + "\n"
    if args.output:
        args.output.write_text(rendered, encoding="utf-8")
    sys.stdout.write(rendered)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
