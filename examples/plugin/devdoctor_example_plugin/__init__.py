"""Two extra tools for DevDoctor's catalog, contributed by an installable package.

Install next to DevDoctor (`pip install -e examples/plugin`) and the tools show
up in `devdoctor search`, `devdoctor check`, and install planning like any
built-in entry. Detectors are the same as the built-ins: a fast, local,
read-only `--version` probe; DevDoctor never runs anything else for a plugin.
"""

from __future__ import annotations

from devdoctor.bootstrap import BootstrapCategory, ToolSpec


def get_tools() -> tuple[ToolSpec, ...]:
    """Return the catalog entries this plugin contributes."""

    return (
        ToolSpec(
            id="lazygit",
            title="lazygit",
            category=BootstrapCategory.GIT_UTILITIES,
            executable="lazygit",
            description="Terminal UI for git.",
            website="https://github.com/jesseduffield/lazygit",
            # Only name packages a distribution actually ships; Debian/Ubuntu and
            # Fedora have none, so those hosts get "no supported local manager".
            packages={
                "pacman": "lazygit",
                "brew": "lazygit",
                "go": "github.com/jesseduffield/lazygit@latest",
            },
        ),
        ToolSpec(
            id="tldr",
            title="tldr",
            category=BootstrapCategory.TERMINAL_UTILITIES,
            executable="tldr",
            description="Community-maintained simplified man pages.",
            website="https://tldr.sh/",
            packages={
                "apt": "tldr",
                "dnf": "tldr",
                "pacman": "tldr",
                "brew": "tlrc",
                "npm": "tldr",
                "pip": "tldr",
            },
        ),
    )
