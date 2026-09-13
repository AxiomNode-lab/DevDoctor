# Example DevDoctor catalog plugin

A minimal installable package that adds two tools (`lazygit`, `tldr`) to DevDoctor's
catalog through the `devdoctor.bootstrap_tools` entry-point group.

```bash
python -m pip install -e examples/plugin
devdoctor search lazygit
devdoctor check lazygit tldr
```

What a plugin provides:

- `ToolSpec` entries: id, title, category, executable name, optional aliases and
  `version_args`, website, and a `packages` mapping keyed by package manager id
  (`apt`, `dnf`, `pacman`, `zypper`, `brew`, `snap`, `flatpak`, `cargo`, `npm`, `pip`, ...).
- Nothing else runs on the host: DevDoctor probes the executable with its version
  arguments, applies the same distro/Atomic planning policy, and never executes
  plugin code with privileges.

Only map package names a distribution really ships; DevDoctor's distro CI verifies
built-in mappings against apt, dnf, pacman, and zypper, and a plugin should hold
itself to the same bar.
