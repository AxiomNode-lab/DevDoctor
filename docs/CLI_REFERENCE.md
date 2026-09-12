# CLI Reference

This reference covers DevDoctor commands as implemented by the Typer CLI. Use `devdoctor --help` and `devdoctor COMMAND --help` for the exact option list installed on your system.

## `devdoctor`

Runs the default bootstrap inventory.

```bash
devdoctor
devdoctor --quiet
devdoctor --json
devdoctor --json-file inventory.json
devdoctor --markdown-file inventory.md
devdoctor --html-file inventory.html
```

Exit code: `0` unless argument parsing fails.

Related commands: `check`, `project`, `export`, `health`.

## `devdoctor check`

Inspects selected tools, a profile, or a category.

```bash
devdoctor check git docker node
devdoctor check --profile devops
devdoctor check --category containers
devdoctor check --missing
devdoctor check --json
```

Exit code: `0` unless argument parsing fails or an unknown profile, category, or tool ID is requested.

Related commands: `verify`, `project`, `install`, `repair`.

## `devdoctor doctor`

Alias for a full bootstrap check.

```bash
devdoctor doctor
devdoctor doctor git docker
devdoctor doctor --profile backend
```

Exit code: `0` unless argument parsing fails.

Related command: `check`.

## `devdoctor project`

Reads supported project manifests and compares their tool/version requirements with the current workstation.

```bash
devdoctor project .
devdoctor project /path/to/project
devdoctor project . --json
devdoctor project . --json --no-fail
```

The command is read-only. It does not execute project hooks, shell code, package scripts, or version-manager activation commands. Supported manifests are bounded to 1 MB, must be UTF-8, and symlinked manifests are not followed.

Exit code: `0` when no discovered requirement is missing or incompatible. Exit code: `1` when a required tool is missing or a safely comparable version is incompatible. Unsupported version expressions are reported as `unknown`, not guessed into pass/fail. `--no-fail` keeps the report while forcing exit code `0`.

See [Project-aware diagnostics](PROJECT_DIAGNOSTICS.md) for the supported manifest/evidence matrix and version-comparison boundaries.

Related commands: `check`, `verify`, `support`.

## `devdoctor verify`

Checks selected tools and exits non-zero if any selected tool is missing, warning, or broken.

```bash
devdoctor verify --profile general
devdoctor verify git python docker --quiet
```

Exit code: `0` when selected tools are ready. Exit code: `1` when selected tools are not ready.

Related commands: `check`, `project`, `install`, `repair`.

## `devdoctor profiles`

Lists built-in profiles.

```bash
devdoctor profiles
devdoctor profiles --json
```

Exit code: `0`.

Related command: `list profiles`.

## `devdoctor search`

Searches the local bootstrap catalog.

```bash
devdoctor search docker
devdoctor search python
```

Exit code: `0` when matches exist. Exit code: `1` when no catalog entries match.

Related commands: `list tools`, `check`.

## `devdoctor install`

Previews or executes safe install plans for missing tools.

```bash
devdoctor install git docker
devdoctor install git docker --dry-run
devdoctor install --profile frontend --dry-run
devdoctor install --profile frontend --apply
```

Exit code: `0` when plans are printed or commands complete. A failed executed command exits with that command's exit code.

Notes:

- Package installation is preview-first; `--apply` is required for real mutation.
- `--dry-run` runs package-manager simulation commands when available.
- Managers without a trustworthy simulation command are skipped rather than given a fake dry-run.
- `--yes` skips confirmation prompts and should only be used in controlled scripts.
- Fedora Atomic/Bazzite host planning suppresses DNF host mutation.
- Atomic planning prefers a mapped user-space/package-scoped manager before rpm-ostree layering.

Related commands: `check`, `verify`, `uninstall`.

## `devdoctor repair`

Shows read-only repair suggestions for selected tools.

```bash
devdoctor repair
devdoctor repair docker
devdoctor repair --profile flutter
```

Exit code: `0`. Repair suggestions are not executed by this command.

Related commands: `repair-apply`, `check`, `install`, `verify`.

## `devdoctor repair-apply`

Previews or executes only repair recommendations that have both an executable command and a known rollback command.

```bash
devdoctor repair-apply docker
devdoctor repair-apply docker --apply
devdoctor repair-apply docker --apply --yes
```

Default behavior is preview-only. `--apply` is required to execute. Per-action confirmation is still required unless the caller explicitly supplies `--yes`.

Successful applied actions are recorded in a local repair transaction journal. If a command or its verification fails, execution stops and the journal remains available for a separately confirmed rollback.

Related commands: `repair`, `repair-rollback`.

## `devdoctor repair-rollback`

Previews or executes rollback commands from a DevDoctor repair transaction.

```bash
devdoctor repair-rollback TRANSACTION_ID
devdoctor repair-rollback TRANSACTION_ID --apply
```

The command accepts transaction IDs, not arbitrary journal paths. Persisted rollback commands must match DevDoctor's rollback allowlist. `--apply` and confirmation are independent from the original repair approval; no privileged rollback is automatic.

Related command: `repair-apply`.

## `devdoctor uninstall`

Previews or executes an uninstall only when DevDoctor can prove that the selected executable is owned by the catalog package through a supported ownership probe.

```bash
devdoctor uninstall docker
devdoctor uninstall docker --apply
```

Ambiguous ownership fails closed. DevDoctor does not choose a removal package manager merely because that manager would be preferred for a fresh installation. On Atomic hosts, ordinary RPM ownership is not treated as proof that a package was layered with rpm-ostree.

Exit code: `0` when ownership-verified plans are printed or commands complete. Exit code: `1` when no safe ownership-verified uninstall plan is available.

Related commands: `install`, `update`.

## `devdoctor update`

Previews or runs update commands for detected package managers.

```bash
devdoctor update
devdoctor update --apply
```

On Fedora Atomic/Bazzite, host update policy uses rpm-ostree rather than DNF. The command remains preview-only unless `--apply` is supplied.

Exit code: `0` when commands are printed or complete. Exit code: `1` when no supported package manager update command is detected.

Related commands: `cache clean`, `self-update`.

## `devdoctor self-update`

Previews or runs an update of the Python distribution backing DevDoctor.

```bash
devdoctor self-update
devdoctor self-update --apply
```

The release-candidate distribution name is `devdoctor-workstation`; the console command remains `devdoctor`.

Exit code: `0` when the command is printed or completes.

Related command: `update`.

## `devdoctor export`

Exports bootstrap inventory as JSON or Markdown.

```bash
devdoctor export json
devdoctor export json --output inventory.json
devdoctor export markdown --output inventory.md
```

Exit code: `0` for supported formats. Exit code: `2` for unsupported formats.

Related commands: `devdoctor --json`, `devdoctor --markdown-file`.

## `devdoctor diagnostics`

Exports a support-oriented JSON snapshot that deliberately excludes hostname, username, raw PATH values, arbitrary environment-variable values, and secret/token values.

```bash
devdoctor diagnostics
devdoctor diagnostics --output devdoctor-diagnostics.json
devdoctor diagnostics --stdout
```

Session type and shell name are normalized to small known allowlists; arbitrary custom environment values are not copied into those fields. Review generated diagnostics before sharing them because package/version names can still reveal local environment details.

Related commands: `support`, `manager-conflicts`, `path-conflicts`.

## `devdoctor support`

Creates a copy/paste-ready Markdown support report from the privacy-scrubbed diagnostic snapshot.

```bash
devdoctor support
devdoctor support --output devdoctor-support.md
devdoctor support --stdout
```

The report includes bounded platform facts, package-manager state/conflicts, and a PATH summary. It intentionally omits hostname, username, raw PATH values, arbitrary environment values, shell history, and credentials. Review the report before posting it publicly.

The repository's bug-report form asks for this output when available so maintainers receive consistent diagnostic evidence.

Related commands: `diagnostics`, `project`.

## `devdoctor manager-conflicts`

Reports package-manager overlap and Atomic-host policy conflicts without modifying the system.

```bash
devdoctor manager-conflicts
```

Examples include DNF being present on an Atomic host, multiple native system managers on PATH, and overlapping Node global package managers.

## `devdoctor path-conflicts`

Inspects duplicate executable paths, version shadowing, and dpkg/rpm/pacman ownership where available.

```bash
devdoctor path-conflicts
devdoctor path-conflicts python node git
```

This command is read-only and does not remove or relink executables.

## `devdoctor completion`

Prints a shell completion script. DevDoctor does not modify shell profile files automatically.

```bash
devdoctor completion bash
devdoctor completion zsh
devdoctor completion fish
```

Top-level completion names are derived from the registered Typer commands and command groups, so newly registered commands do not require a second hand-maintained command list.

Redirect the output to the shell's normal completion location according to your local shell configuration.

## `devdoctor benchmark`

Measures a bounded local scan without applying changes.

```bash
devdoctor benchmark
devdoctor benchmark --iterations 5
```

For release/CI startup measurements, the repository also contains `scripts/benchmark.py`, which measures fresh-process startup and a bounded inventory scan.

## `devdoctor list`

Lists catalog data.

```bash
devdoctor list profiles
devdoctor list tools
devdoctor list tools --category terminal-utilities
devdoctor list categories
```

Exit code: `0` unless an unknown category is requested.

Related commands: `profiles`, `search`.

## `devdoctor cache clean`

Previews or runs supported package-cache cleanup commands.

```bash
devdoctor cache clean
devdoctor cache clean --apply
```

On Fedora Atomic/Bazzite, DNF cache mutation is suppressed by the host policy.

Exit code: `0`.

Related command: `update`.

## `devdoctor health`

Runs the legacy non-interactive health report.

```bash
devdoctor health
devdoctor health --quiet
devdoctor health --json
devdoctor health --html-file health.html
devdoctor health --pdf-file health.pdf
devdoctor health --quiet --fail-under 80
```

Exit code: `0` unless `--fail-under` is set and the legacy score is below the threshold.

Related command: `devdoctor`.

## Environment variables

| Variable | Effect |
| --- | --- |
| `DEVDOCTOR_PROBE_WORKERS` | How many version probes and per-tool checks run at once during a scan. Default `4`; `1` makes the scan sequential (lowest peak memory); values above `16` are capped. |
| `NO_COLOR` | Disable terminal colors (also `--no-color`). |
