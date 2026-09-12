# Changelog

All notable changes to DevDoctor are documented in this file.

The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project uses semantic versioning.

## [Unreleased]

### Fixed

- Python and pip are detected on hosts that only ship `python3`/`pip3` (Debian, Ubuntu): catalog tools can declare alternate command names via `ToolSpec.executable_aliases`.
- A launcher whose shebang points at a missing interpreter (a stale `~/.local/bin/pip`, for example) is reported as `broken` with the interpreter path, instead of `ready` with an OS error message shown as its version.
- Tools that could not be executed, or whose output has no version-shaped token, report no version instead of banner or error text.
- OpenSSH is probed with `ssh -V`; `OpenSSH_9.6p1 …` now parses as `9.6p1` rather than the bundled OpenSSL version.
- `/bin` and `/usr/bin` (and any other directory symlink) no longer count as a duplicate installation or a shadowed executable on merged-usr hosts, which removed a spurious warning on every stock Ubuntu tool.
- A broken symlink, dead interpreter, or missing execute bit is classified `broken` consistently in the row health, the summary counters, and JSON.
- PATH analysis emits one combined `export PATH=…` cleanup line (`cleanup_command`) instead of repeating the full PATH in every missing-directory row.
- Install plans no longer name packages the distribution does not ship: `kubectl`, `helm`, `terraform`, `azure-cli`, `pnpm`, `ruff`, `starship`, and `asdf` on APT; `terraform`, `pnpm`, `starship`, `asdf`, and `cuda-toolkit` on DNF. Docker Compose/Buildx map to `docker-compose-v2`/`docker-buildx` (APT) and `docker-compose`/`docker-buildx` (DNF).
- Classic snaps (`kubectl`, `helm`, `code`, `flutter`, `aws-cli`, `google-cloud-cli`) are planned with `--classic`, which `snap install` requires for them.
- openSUSE Java maps to the `java-devel` capability (found by the Tumbleweed catalog job: there is no `java-latest-openjdk-devel` package on openSUSE).
- Pacman mappings name packages in the official Arch repositories (verified against archlinux.org): `cargo` ships in `rust`, the MySQL client is `mariadb-clients`, `redis-cli` comes from `valkey`, and `asdf` is AUR-only so has no pacman mapping.
- Missing tools with no supported local manager now point at the vendor site in the install column.
- Repository links point at `AxiomNode-lab/DevDoctor`.
- `scripts/install.sh --source git` installs from the repository (`main`, or the `v<VERSION>` tag with `--version`) through the same user-owned environment and rollback layout as the other sources. It is the only installer source that can succeed before a PyPI or GitHub release exists, and README now documents it.

### Added

- A **Findings** panel opens every report: each installed tool that is broken or has a warning, the problem, and the one action to take — the diagnosis before the inventory. When nothing is wrong it says so in one line.

### Changed

- Scans are concurrent: version probes and per-tool checks (`docker info`, `git config`, `python -m pip`) run through an 8-worker pool. A full inventory here dropped from ~1.8s warm / ~10s cold to under a second; results and ordering are unchanged.
- DevDoctor is attributed to AxiomNode everywhere a user reads it: `devdoctor --version` prints the copyright and license, HTML/Markdown reports and the support report carry a footer, the SPDX SBOM names the supplier and copyright, and `pyproject.toml`, `LICENSE`, README, `docs/BRAND.md`, and `SECURITY.md` name the organization (`__author__`, `__copyright__`, `__license__`, `__homepage__` are exported by the package).
- Atomic/Bazzite install planning, the Nix user-profile fallback, and the Atomic update/cache-clean rules are now part of `bootstrap.install_plan_for_spec`, `bootstrap.detect_system_context` (`atomic_host`), and the CLI helpers themselves, backed by the new `devdoctor.host_policy` module. Previously they were monkey-patched onto `bootstrap` and `cli` by the console entry point, so a direct import of the planner planned `dnf` on Silverblue. `apply_atomic_planning_patch`, `apply_fallback_planning_patch`, and `apply_runtime_hardening` are kept as no-ops for compatibility.

### Added

- `entrypoint.build_app()` returns the fully registered console app (built once); `tests/test_cli_commands.py` drives every public command through it on the real machine — JSON shape, exit codes, preview-only mutations, exported files, scrubbed diagnostics — lifting `cli.py` coverage from 31% to 61% and the suite from 62% to 76%.
- `tests/test_native_planning_policy.py` asserts the planner is Atomic-safe and Nix-aware without any runtime patch, and that the legacy patch functions no longer replace planner functions.
- Regression suite `tests/test_detection_accuracy.py` reproducing each of the above on real files and subprocesses.
- The distro integration probe can assert that named tools detect as `ready` (`--expect-ready`) and that every catalog package for the host manager exists (`--verify-catalog-packages apt|dnf|pacman|zypper`); the Ubuntu, Fedora, and Arch jobs run both, and a new openSUSE Tumbleweed job checks the zypper catalog (as names or capabilities).

## [1.2.0rc1] - 2026-08-27

### Added

- Fixture-driven package-manager policy coverage for APT, DNF, rpm-ostree, Pacman, Zypper, Nix, Flatpak, and mixed-manager hosts.
- Distro/container integration workflow for Ubuntu/APT, Fedora/DNF, Arch/Pacman, SUSE/Zypper, Nix, Flatpak, and synthetic Atomic policy checks.
- Fedora Atomic and Bazzite install-planning policy that suppresses DNF host mutation and prefers mapped user-space tooling before rpm-ostree layering.
- `manager-conflicts` command for package-manager overlap and Atomic-host policy conflicts.
- `path-conflicts` command for bounded duplicate executable, version, and package-ownership analysis.
- Privacy-scrubbed `diagnostics` export without hostname, username, raw PATH values, arbitrary environment values, or secret/token values.
- `support` command that renders the scrubbed diagnostic snapshot as copy/paste-ready Markdown for GitHub issues.
- `project` command for read-only comparison of supported project manifests with the current workstation, including JSON output and CI-friendly exit codes.
- Bounded project evidence support for Python, Node, Rust/Cargo, Go, mise/asdf-style version declarations, Devbox, Docker/Compose, Ruby, PHP, and common Java project manifests.
- Conservative project version comparison for common numeric operators including `>=`, `<=`, `!=`, caret, tilde, PEP 440 compatible-release `~=`, wildcards, and `||` alternatives.
- Bash, Zsh, and Fish completion generation without editing shell startup files.
- Dynamic top-level completion discovery from the registered Typer commands and command groups.
- Transaction-journaled repair application and rollback commands with independent confirmation and bounded rollback allowlists.
- Startup/bounded-scan benchmark workflow.
- Python 3.11 through 3.14 clean-wheel installation matrix.
- Release-specific user-space install script that can download the exact GitHub Release wheel and verify it against `SHA256SUMS`.
- Deterministic SPDX 2.3 SBOM generation for release artifacts and declared runtime dependencies.
- GitHub/Sigstore provenance and SBOM attestations for tagged releases.
- PyPI Trusted Publishing path that reuses the exact artifacts produced by the tagged release build.
- Release-candidate notes and evidence-based distribution/readiness documentation.
- Explicit release checks for normalized `devdoctor_workstation` wheel and sdist filenames.
- Bug-report form fields for the privacy-safe support report and project-compatibility output.

### Changed

- Release candidate version is `1.2.0rc1` and is classified as beta until qualification completes.
- Python distribution identifier is `devdoctor-workstation`; the product and executable remain `DevDoctor` and `devdoctor`.
- The previously planned `devdoctor-cli` distribution identifier was abandoned before first publication because it is already used by another public project.
- Atomic-host classification is persisted once in the inventory context from release evidence instead of repeatedly probing package managers while planning each tool.
- Atomic package planning prefers mapped user-space/package-scoped managers before rpm-ostree layering.
- GitHub Actions workflows use current Node 24/ESM-generation official actions where available.
- CI and clean-wheel smoke checks exercise project diagnostics, support reports, and dynamic completions.
- Release tags are rejected when the tag version does not match the package version.
- Release checksum generation is deterministic and excludes the checksum manifest itself.
- README positioning now focuses on diagnosing the existing Linux workstation and repository requirements rather than presenting DevDoctor as another environment manager.
- Documentation distinguishes detection support, fixture verification, container integration, and real-workstation evidence.
- PyPI and Homebrew installation instructions are not presented as available before those external channels are actually published and verified.

### Fixed

- `self-update` now upgrades `devdoctor-workstation` instead of targeting unrelated or occupied package names.
- The user-space installer now resolves `devdoctor_workstation-<version>-py3-none-any.whl` and verifies it against the release checksum manifest.
- The installer preflights Python `venv` support before creating DevDoctor installation directories and gives an actionable Debian/Ubuntu `python3-venv` message when needed.
- Reinstalling the same DevDoctor version now replaces a stale/broken virtual environment with a freshly validated environment through a rollback-safe directory swap.
- Planner patches are applied before importing the CLI so direct planner aliases do not retain an unhardened implementation.
- Package-manager detection is no longer repeated for every missing tool during Atomic planning.
- Mutable Fedora is not classified as Atomic merely because an `rpm-ostree` executable is installed.
- Arbitrary `XDG_SESSION_TYPE` and shell environment values are no longer copied into the privacy diagnostic snapshot; only known normalized values are reported.
- Project metadata tests validate the hardened public console entry point, `devdoctor.entrypoint:main`, and the publication distribution name.
- Hardening tests were reformatted so the CI lint gate can reach the actual test suite.
- PATH alternate probing no longer reports a duplicate installation when the primary command lookup says the executable is missing.

### Security

- `uninstall` now fails closed unless the selected executable's detected package ownership matches the catalog mapping.
- RPM ownership on Atomic/Bazzite hosts is not treated as proof that a package is rpm-ostree layered.
- DNF host mutation is suppressed on confirmed Fedora Atomic/Bazzite policy paths.
- Project diagnosis never executes project hooks/scripts, refuses symlinked supported manifests, bounds parsed files to 1 MB, and converts malformed manifests into warnings.
- Support reports are derived only from privacy-scrubbed diagnostics and neutralize backtick/newline injection in displayed values.
- Repair application and rollback remain preview-first and require explicit apply/confirmation paths.
- Release provenance uses GitHub OIDC/keyless attestations instead of a long-lived signing credential in the repository.
- PyPI publishing uses Trusted Publishing and does not require a long-lived PyPI API token.

## [1.1.0] - 2026-06-28

### Added

- Intelligent tool detection with health states, inferred installation method, alternate executable paths, dependency status, and repair recommendations.
- Dependency graph expansion for selected tools so commands like `devdoctor check flutter` include the related toolchain context.
- Repair recommendations for Docker daemon/socket failures, Git identity configuration, missing SSH public keys, Python without pip, Node.js without npm, Java without `JAVA_HOME`, Cargo PATH gaps, Flutter Android toolchain gaps, broken symlinks, non-executable commands, duplicate executable installations, and missing runtime dependencies.
- PATH analyzer for empty entries, duplicate directories, missing directories, non-directory entries, non-searchable directories, unexported user binary directories, and shadowed executables.
- Richer `devdoctor search` output with category, health, version, installation method, profiles, dependencies, install command, and website.
- Structured JSON Lines operation logging with selected package manager, executed command, exit code, duration, verification command, and verification result.
- Verification-after-execution for install and uninstall plans when the catalog defines a verification command.
- Unit tests for PATH analysis, broken symlink discovery, dependency resolution, repair recommendations, structured operation logs, and command verification logging.

### Changed

- Install plans now show package name, selected package-manager reason, sudo requirement, dependency metadata, verification command, and rollback command when known.
- The bootstrap inventory includes dependency tools in scoped checks and search results, preserving catalog ordering.
- Terminal repair output now explains what happened, why it matters, how to fix it, and how to verify the fix.

### Security

- Mutating command execution remains opt-in through `--apply`, with confirmation unless `--yes` is provided.
- Command execution continues to use argument vectors with `shell=False`.
- Repair suggestions remain read-only and do not modify shell startup files, service state, group membership, or package metadata automatically.

## [1.0.0] - 2026-06-28

### Added

- First stable release of DevDoctor as a Linux developer workstation bootstrap CLI.
- Bootstrap inventory for host context, package managers, developer tools, programming languages, containers, databases, cloud CLIs, DevOps tools, AI tools, security tools, build systems, mobile tooling, game tooling, debuggers, and terminal utilities.
- Distro-aware install plans with dry-run commands, rollback commands, verification commands, and risk labels where the package manager supports them.
- Built-in profiles for general, frontend, backend, Python, Node, Rust, Go, Java, Flutter, Android, data science, AI, security, DevOps, cloud, and game development.
- Safe command execution flow for install, update, uninstall, cache-clean, and self-update operations using explicit `--apply` confirmation.
- JSON, Markdown, and standalone HTML bootstrap inventory exporters.
- Bootstrap catalog extension point through the `devdoctor.bootstrap_tools` entry point group.
- Legacy `devdoctor health` command for non-interactive health reports and JSON/HTML/Markdown/PDF exporters.
- Complete brand asset set with logo, icon, favicon, and GitHub social banner.
- Unit tests for bootstrap install planning, tool detection, PATH repair detection, profile coverage, scoring, version parsing, report generation, package-manager detection, and plugin loading.
- GitHub Actions workflows, issue templates, labels, release template, and pull request template.

### Changed

- `devdoctor` now prints a workstation bootstrap inventory by default.
- `devdoctor --json` now emits bootstrap inventory JSON.
- `devdoctor --quiet` now prints installed, missing, broken, and total counts.
- Project positioning changed from health dashboard to bootstrap and repair CLI.

### Removed

- Removed the Textual dashboard from the public CLI and package dependencies.
- Removed health-score output from the default workflow.

### Security

- Scans are read-only and run as the current user.
- System-changing commands require `--apply` and confirmation unless `--yes` is explicitly provided.
- Command execution uses argument vectors with `shell=False`.
- Operation commands are logged under the user state directory.
