"""A dead or duplicate PATH entry is only fixable if you know which file put it there."""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from devdoctor.path_analysis import analyze_path, path_entry_sources


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def test_entry_sources_name_file_and_line_for_literal_home_and_variable_spellings(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    home = tmp_path / "home"
    monkeypatch.setenv("HOME", str(home))
    _write(home / ".bashrc", "alias ll='ls -l'\nexport PATH=\"$HOME/.old-tools/bin:$PATH\"\n")
    _write(home / ".zshrc", "path+=(~/.old-tools/bin)\n")
    _write(home / ".profile", f'PATH="{home}/.old-tools/bin:$PATH"\n')
    _write(home / ".config/fish/config.fish", "fish_add_path $HOME/.other/bin\n")

    sources = path_entry_sources(str(home / ".old-tools/bin"), home=home)

    assert sources == (
        (str(home / ".profile"), 1),
        (str(home / ".bashrc"), 2),
        (str(home / ".zshrc"), 1),
    )


def test_entry_sources_are_empty_when_nothing_mentions_the_entry(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    home = tmp_path / "home"
    monkeypatch.setenv("HOME", str(home))
    _write(home / ".bashrc", "export EDITOR=vim\n")

    assert path_entry_sources("/opt/nowhere/bin", home=home) == ()


def test_missing_directory_issue_carries_its_source(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    home = tmp_path / "home"
    monkeypatch.setenv("HOME", str(home))
    good = tmp_path / "good"
    good.mkdir()
    dead = home / ".old-tools/bin"
    _write(home / ".bashrc", f'export PATH="{dead}:$PATH"\n')

    analysis = analyze_path(os.pathsep.join((str(good), str(dead))), executables=(), home=home)

    (issue,) = [i for i in analysis.issues if i.kind == "missing_directory"]
    assert issue.sources == ((str(home / ".bashrc"), 1),)
    assert f"{home / '.bashrc'}:1" in issue.recommendation
    assert issue.to_dict()["sources"] == [{"file": str(home / ".bashrc"), "line": 1}]
