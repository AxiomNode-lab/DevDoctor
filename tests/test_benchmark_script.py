"""The benchmark budgets the tool's own footprint and the aggregate with its children separately."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent


def _load():
    spec = importlib.util.spec_from_file_location("benchmark", ROOT / "scripts" / "benchmark.py")
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules["benchmark"] = module  # slotted dataclasses need their module registered
    spec.loader.exec_module(module)
    return module


def test_summary_reports_self_and_aggregate_peaks() -> None:
    bench = _load()
    mib = 1024 * 1024
    samples = [
        bench.Sample(seconds=0.2, peak_rss_bytes=190 * mib, peak_self_rss_bytes=70 * mib),
        bench.Sample(seconds=0.3, peak_rss_bytes=150 * mib, peak_self_rss_bytes=80 * mib),
    ]

    summary = bench.summarize(samples)

    assert summary["max_peak_rss_mib"] == 190.0
    assert summary["max_peak_self_rss_mib"] == 80.0


def test_self_budget_is_enforced_independently_of_the_aggregate() -> None:
    bench = _load()
    mib = 1024 * 1024
    summary = bench.summarize(
        [bench.Sample(seconds=0.2, peak_rss_bytes=250 * mib, peak_self_rss_bytes=90 * mib)]
    )

    bench._enforce_memory_budget("scan", summary, 256.0)  # aggregate within budget
    bench._enforce_memory_budget("scan", summary, 128.0, key="max_peak_self_rss_mib")
    with pytest.raises(RuntimeError, match="self"):
        bench._enforce_memory_budget("scan", summary, 64.0, key="max_peak_self_rss_mib")
    with pytest.raises(RuntimeError, match="aggregate"):
        bench._enforce_memory_budget("scan", summary, 192.0)


def test_measurement_separates_the_parent_from_its_children() -> None:
    # A parent that is small itself but spawns a child holding ~40 MiB.
    bench = _load()
    child = "b=bytearray(40*1024*1024); import time; time.sleep(0.4)"
    command = [
        "python3",
        "-c",
        f"import subprocess,sys; subprocess.run([sys.executable,'-c',{child!r}])",
    ]

    sample = bench._measure_process(command)

    assert sample.peak_rss_bytes > sample.peak_self_rss_bytes + 30 * 1024 * 1024
    assert sample.peak_self_rss_bytes < 60 * 1024 * 1024
