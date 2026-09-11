from __future__ import annotations

import pytest

from devdoctor.utils import parse_version


@pytest.mark.parametrize(
    ("output", "expected"),
    [
        ("git version 2.45.2", "2.45.2"),
        ("node v20.11.1", "20.11.1"),
        ("rustc 1.79.0 (129f3b996 2024-06-10)", "1.79.0"),
        ('openjdk version "21.0.3" 2024-04-16', "21.0.3"),
        ("pnpm 9.4.0", "9.4.0"),
        ("go version go1.22.4 linux/amd64", "1.22.4"),
        (
            "GNU Wget2 2.2.1 - multithreaded downloader\n"
            "+digest +https +ssl/gnutls +ipv6\n"
            "License GPLv3+",
            "2.2.1",
        ),
    ],
)
def test_parse_version_common_outputs(output: str, expected: str) -> None:
    assert parse_version(output) == expected


def test_parse_version_returns_none_for_empty_output() -> None:
    assert parse_version("") is None
