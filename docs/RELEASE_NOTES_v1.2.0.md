# DevDoctor v1.2.0

Released 2026-09-13 by [AxiomNode](https://axiomnode.tech/). The first published DevDoctor release.

## Install

```bash
curl -fsSL -o devdoctor-install.sh https://raw.githubusercontent.com/AxiomNode-lab/DevDoctor/main/scripts/install.sh
sh devdoctor-install.sh --source github --version 1.2.0   # verified wheel from this release
sh devdoctor-install.sh --source git                       # or straight from the repository
```

`pip install devdoctor-workstation` follows once the PyPI Trusted Publisher is configured.

## Highlights

- **Correct on Debian-family hosts.** Python is found as `python3`, a dead launcher shebang is `broken` (not `ready` with an error as its version), `/bin` and `/usr/bin` are one file, `ssh -V` parses.
- **Honest install plans.** 20 package names the distributions do not ship were removed or corrected, and CI now asks apt, dnf, pacman, and zypper whether every catalog package exists.
- **A Findings panel opens every report**, and `devdoctor fix` walks the repairs with a preview and per-action confirmation.
- **`devdoctor diff`** shows what changed since the last full scan.
- **Sub-second scans** (concurrent probes), version-manager awareness (`nvm (6 versions installed)` instead of duplicate warnings), root/no-sudo/systemd-aware plans, and PATH issues that name the profile line that set them.
- **A GitHub Action**, an example catalog plugin, and JSON Schemas with a stability policy for every machine-readable output.
- Atomic/Bazzite and Nix planning policy is part of the planner; no more runtime monkey-patching.

## Release payload

```text
devdoctor_workstation-1.2.0-py3-none-any.whl
devdoctor_workstation-1.2.0.tar.gz
devdoctor-install.sh
devdoctor.spdx.json
SHA256SUMS
```

Provenance and SBOM attestations are published with the release; verify with `gh attestation verify devdoctor_workstation-1.2.0-py3-none-any.whl --repo AxiomNode-lab/DevDoctor`.

## Full changelog

The first published DevDoctor release. Everything listed here was verified on a real Ubuntu 24.04 host and by CI on Ubuntu, Fedora, Arch, and openSUSE containers; `1.2.0rc1` below was never published.

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

- JSON output contract: `docs/schema/{inventory,project,diff}.schema.json` (draft 2020-12) with a stability policy in `docs/JSON_SCHEMA.md`; inventory and diff payloads now carry `schema_version: 1` like `project` already did. Tests validate real command output against each schema and pin the enums to the code's tables — the schema immediately surfaced that install-plan `risk` is a level plus reason (`"medium - requires system package privileges"`), which is now documented as such.
- `devdoctor fix`: alias of `repair-apply`, and the Findings panel now ends with the hint to run it; the guided, preview-first walk through repairs is discoverable from the diagnosis itself.
- `devdoctor diff`: every full scan records a snapshot (`last-inventory.json` in the user state directory); `diff` rescans and reports tools that appeared or disappeared, health flips, version and path changes, and the PATH issue count, problems first. `--json`, `--exit-code`, `--keep-baseline`, and `--tools a,b` (scoped rescan that updates only those baseline entries). A read-only home never breaks a scan.
- `examples/plugin`: an installable example catalog plugin (`devdoctor.bootstrap_tools` entry point) contributing `lazygit` and `tldr`, verified end to end in a clean environment.
- `action.yml`: a composite GitHub Action (`uses: AxiomNode-lab/DevDoctor@main`) that runs `devdoctor project` against the caller's repository, writes the result to the job summary, exposes the JSON report path as an output, and honors `fail-on-mismatch`. The repository dogfoods it in `.github/workflows/project-check.yml`.
- A **Findings** panel opens every report: each installed tool that is broken or has a warning, the problem, and the one action to take — the diagnosis before the inventory. When nothing is wrong it says so in one line.

### Changed

- Scans are concurrent: version probes and per-tool checks (`docker info`, `git config`, `python -m pip`) run through a small worker pool (default 4; `DEVDOCTOR_PROBE_WORKERS=1` for a sequential scan, up to 16). A full inventory here dropped from ~1.8s warm / ~10s cold to about a second; results and ordering are unchanged. Every probe alive at once adds its own memory, which is why the default stays small.
- PATH issues name their source: for a missing or duplicate entry, the recommendation ends with the shell profile lines that set it (`~/.bashrc:45`, `/etc/environment:1`, …; `$HOME` and `~` spellings included) and the JSON carries `sources: [{file, line}]`. Files are only read, never edited.
- Plans fit the host they are shown on: when already root (most containers), install, rollback, update, and cache-clean commands drop the `sudo` prefix that would fail where sudo is not installed; when not root and sudo is absent the plan says so; the Docker daemon repair offers `systemctl start docker` only when systemd is actually running (`/run/systemd/system`), and explains the container/WSL case otherwise.
- Version managers are recognised (nvm, pyenv, rbenv, asdf, mise, sdkman, rustup): other versions of a tool under the same manager are reported as "nvm (6 versions installed)" instead of a "Duplicate installation" warning; a copy outside the manager is still flagged. On a workstation with six nvm Node versions in PATH this removed five spurious warnings.
- The benchmark reports and budgets DevDoctor's own peak RSS (`max_peak_self_rss_mib`, budget 128 MiB) separately from the aggregate with every concurrently running probe child (budget 256 MiB, was 192 for a sequential scan). The tool's own footprint is unchanged (~30 MiB for a bounded scan); the aggregate now scales with `DEVDOCTOR_PROBE_WORKERS`.
- DevDoctor is attributed to AxiomNode everywhere a user reads it: `devdoctor --version` prints the copyright and license, HTML/Markdown reports and the support report carry a footer, the SPDX SBOM names the supplier and copyright, and `pyproject.toml`, `LICENSE`, README, `docs/BRAND.md`, and `SECURITY.md` name the organization (`__author__`, `__copyright__`, `__license__`, `__homepage__` are exported by the package).
- Atomic/Bazzite install planning, the Nix user-profile fallback, and the Atomic update/cache-clean rules are now part of `bootstrap.install_plan_for_spec`, `bootstrap.detect_system_context` (`atomic_host`), and the CLI helpers themselves, backed by the new `devdoctor.host_policy` module. Previously they were monkey-patched onto `bootstrap` and `cli` by the console entry point, so a direct import of the planner planned `dnf` on Silverblue. `apply_atomic_planning_patch`, `apply_fallback_planning_patch`, and `apply_runtime_hardening` are kept as no-ops for compatibility.

### Added

- `entrypoint.build_app()` returns the fully registered console app (built once); `tests/test_cli_commands.py` drives every public command through it on the real machine — JSON shape, exit codes, preview-only mutations, exported files, scrubbed diagnostics — lifting `cli.py` coverage from 31% to 61% and the suite from 62% to 76%.
- `tests/test_native_planning_policy.py` asserts the planner is Atomic-safe and Nix-aware without any runtime patch, and that the legacy patch functions no longer replace planner functions.
- Regression suite `tests/test_detection_accuracy.py` reproducing each of the above on real files and subprocesses.
- The distro integration probe can assert that named tools detect as `ready` (`--expect-ready`) and that every catalog package for the host manager exists (`--verify-catalog-packages apt|dnf|pacman|zypper`); the Ubuntu, Fedora, and Arch jobs run both, and a new openSUSE Tumbleweed job checks the zypper catalog (as names or capabilities).
