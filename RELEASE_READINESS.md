# Release Readiness

Date: 2026-08-27  
Candidate: `1.2.0rc1`  
Repository: `AxiomNode-lab/DevDoctor`  
Python distribution: `devdoctor-workstation`  
Executable: `devdoctor`

## Current decision

**Do not tag `v1.2.0rc1` yet.**

The release-candidate code and release pipeline are prepared, but the final PR head must run through the complete GitHub Actions matrix before a tag is created. Passing workflows from earlier commits remain useful evidence, but they do not qualify the current release commit after distribution metadata, installer, project diagnostics, support reporting, safety tests, memory budgets, and release workflow changed.

The distribution name was changed before first publication because `devdoctor-cli` is already used by another public project. DevDoctor keeps its product name and `devdoctor` console command; only the Python distribution identifier changes to `devdoctor-workstation`.

This document intentionally contains no self-assigned readiness percentage. Release status is determined by reproducible checks and external publication state.

## Implemented in the candidate

- Python 3.11 through 3.14 CI matrix.
- Clean-wheel installation matrix.
- APT, DNF, rpm-ostree, Pacman, Zypper, Nix, Flatpak, and mixed-manager policy fixtures.
- Distro/container integration workflow for selected package managers.
- Persisted Atomic-host classification from release evidence rather than per-tool package-manager probing.
- Fedora Atomic/Bazzite policy that suppresses DNF host mutation and prefers mapped user-space/package-scoped managers before rpm-ostree layering.
- Package-manager conflict and PATH ownership/version diagnostics.
- Read-only project-aware diagnosis for bounded declarative manifests with JSON output and CI exit semantics.
- Project-manifest reads are capped at 1,000,000 bytes/characters and discovered requirements are capped at 128.
- Privacy-scrubbed diagnostic export with allowlisted session/shell values.
- Privacy-safe Markdown support report intended for GitHub issues.
- Bash, Zsh, and Fish completion generation from registered CLI commands/groups.
- Transaction-journaled repair application and rollback paths.
- User-space installer with venv preflight, fresh-environment validation, same-version replacement, and rollback-safe activation.
- Behavioral installer tests that do not require network access.
- `self-update` targets `devdoctor-workstation`.
- Ownership-verified, fail-closed uninstall planning.
- Peak-RSS performance workflow using fresh subprocesses and child-process accounting.
- Startup RSS regression budget of 128 MiB and bounded scan budget of 192 MiB.
- Python-allocation regression test for a near-limit project manifest.
- Release tag/package-version consistency check.
- Distribution filename checks for the normalized `devdoctor_workstation` wheel and sdist.
- One-build release pipeline: tested artifacts are reused for GitHub Release and optional PyPI publication.
- SHA-256 release manifest.
- SPDX 2.3 SBOM generation.
- GitHub/Sigstore provenance and SBOM attestations.
- PyPI Trusted Publishing job gated by a repository variable and protected `pypi` environment.

## Memory evidence

The first Peak-RSS CI baseline on commit `5c32d792e768109465a9a5fe7e3bc3cc9d1d22da` measured:

- `devdoctor --version`: max Peak RSS **27.27 MiB** across five fresh subprocesses.
- bounded `git/python/node` inventory: max Peak RSS **124.96 MiB** across five fresh subprocesses, including observed child processes.

Those measurements passed the 128 MiB startup and 192 MiB bounded-scan budgets. They are regression evidence from a GitHub-hosted Ubuntu runner, not workstation-wide memory guarantees. The final tag still requires the same memory workflow to pass on the exact release commit.

## Required qualification gates

The exact commit that will be tagged must satisfy all of these gates.

### Source and package quality

- [ ] `ruff format --check .`
- [ ] `ruff check .`
- [ ] Full `pytest` suite.
- [ ] Package build with `python -m build`.
- [ ] `twine check dist/*`.
- [ ] Project version equals package `__version__`.
- [ ] Distribution name equals `devdoctor-workstation`.
- [ ] Console entry point resolves to `devdoctor.entrypoint:main`.
- [ ] Project-manifest parser positive/negative fixtures pass.
- [ ] Support-report privacy/escaping tests pass.

### Performance and memory

- [ ] `Performance and memory baseline` succeeds on the exact release commit.
- [ ] Fresh-process startup Peak RSS remains at or below 128 MiB.
- [ ] Bounded `git/python/node` inventory Peak RSS remains at or below 192 MiB, including observed children.
- [ ] Near-limit project-manifest parsing remains below the 16 MiB Python-allocation regression threshold used by the test suite.
- [ ] No memory threshold is raised merely to make CI pass; a regression must be investigated first.

### Clean installation

- [ ] Wheel installs in a fresh Python 3.11 environment.
- [ ] Wheel installs in a fresh Python 3.12 environment.
- [ ] Wheel installs in a fresh Python 3.13 environment.
- [ ] Wheel installs in a fresh Python 3.14 environment.
- [ ] Installed `devdoctor --version` works.
- [ ] Installed completion generation works and includes registered groups/new commands.
- [ ] Installed privacy diagnostics produce valid JSON.
- [ ] Installed `devdoctor support --stdout` produces the expected Markdown header.
- [ ] Installed `devdoctor project . --json --no-fail` produces valid JSON.
- [ ] Installed `self-update` preview targets `devdoctor-workstation`.

### Installer safety

- [ ] POSIX shell syntax validation passes.
- [ ] Missing Python venv support fails before creating DevDoctor state directories.
- [ ] A freshly installed environment is validated before activation.
- [ ] Reinstalling the same version replaces the stale environment only after fresh validation.
- [ ] Activation failure restores the previous same-version environment.
- [ ] Activation failure restores the previous command symlink target.
- [ ] Interrupted/failed installation cleans temporary replacement directories.

### Package-manager and mutation safety

- [ ] Fixture matrix passes.
- [ ] Ubuntu/APT integration passes.
- [ ] Fedora/DNF integration passes.
- [ ] Arch/Pacman integration passes.
- [ ] SUSE/Zypper integration passes on the pinned official BCI image.
- [ ] Nix and Flatpak detection integration passes.
- [ ] Synthetic Fedora Atomic policy test passes without DNF host planning.
- [ ] Synthetic Bazzite policy test passes without DNF host planning.
- [ ] Atomic mapped user-space/package-scoped managers are considered before rpm-ostree layering.
- [ ] Mutable Fedora is not classified as Atomic only because `rpm-ostree` exists on PATH.
- [ ] Ambiguous uninstall ownership fails closed.
- [ ] Atomic RPM ownership is not treated as proof of rpm-ostree layering.
- [ ] Repair rollback allowlist/invariant tests pass.

### Project and privacy safety

- [ ] Supported project manifests are read without executing project hooks or commands.
- [ ] Symlinked supported manifests are refused.
- [ ] Oversized/invalid manifests fail to warnings rather than execution or guessed requirements.
- [ ] Project requirement accumulation is bounded.
- [ ] Long/untrusted version strings and terminal escape sequences are bounded/sanitized before display or comparison.
- [ ] Unsupported version expressions become `unknown`, not forced pass/fail.
- [ ] Arbitrary `XDG_SESSION_TYPE` and shell values are not copied to diagnostic output.
- [ ] Support Markdown neutralizes control delimiters used by its rendered fields.

### Release artifacts

- [ ] Tag version matches package version.
- [ ] `devdoctor_workstation-1.2.0rc1-py3-none-any.whl` is produced.
- [ ] `devdoctor_workstation-1.2.0rc1.tar.gz` is produced.
- [ ] Wheel and sdist are generated once by the release build job.
- [ ] Clean-wheel validation uses the generated wheel.
- [ ] Release wheel runs `project`, `support`, diagnostics, completion, self-update, and uninstall smoke checks.
- [ ] Release workflow rechecks the Peak-RSS budgets before artifact publication.
- [ ] `devdoctor-install.sh` is added to the release payload.
- [ ] SPDX SBOM is generated successfully.
- [ ] `SHA256SUMS` verifies successfully.
- [ ] Provenance attestation succeeds.
- [ ] SBOM attestation succeeds.
- [ ] GitHub prerelease contains the expected payload.

## External setup gates

These cannot be proven by repository code alone.

### PyPI

Before setting `PYPI_TRUSTED_PUBLISHING_ENABLED=true`:

- [ ] Create or confirm the `devdoctor-workstation` project/pending publisher on PyPI.
- [ ] Configure the trusted publisher for `AxiomNode-lab/DevDoctor` and `.github/workflows/release.yml`.
- [ ] Configure the GitHub environment named `pypi`.
- [ ] Add the desired environment reviewer/protection policy.
- [ ] Confirm the tagged release workflow has `id-token: write` only where required.
- [ ] Confirm the public PyPI project resolves to this repository before documenting a PyPI install command.

Do not configure a publisher for `devdoctor-cli`; that distribution name belongs to another project. The repository does not use a long-lived PyPI API token for this release path.

### Stable-release repository protection

Before promoting the candidate to stable:

- [ ] Protect `main` with required CI/code-quality checks or an equivalent repository ruleset.
- [ ] Prevent direct merges that bypass release-critical checks.
- [ ] Prefer automatic deletion of merged feature branches.

### Homebrew

Homebrew is not a blocker for the release candidate. It must not be advertised as supported until:

- [ ] A real tap exists.
- [ ] Formula URLs and hashes reference immutable release artifacts.
- [ ] Formula installation passes in a clean Homebrew CI environment.

## Evidence policy

DevDoctor distinguishes:

- **Unit/fixture verified** — deterministic policy covered by tests.
- **Clean-wheel verified** — built package installs and starts in a new environment.
- **Host/container integration verified** — CI exercised a real distro/container package manager.
- **Memory regression verified** — an exact CI run stayed under explicit Peak-RSS/allocation budgets.
- **Manual workstation verified** — behavior was tested on an actual workstation/image.

Synthetic Fedora Atomic and Bazzite containers validate policy only. They are not evidence of real Bazzite workstation, desktop, hardware, reboot, or rpm-ostree deployment behavior.

Project-manifest support similarly means only the documented fields/formats are parsed. It does not imply complete compatibility with npm SemVer, PEP 440, mise, Devbox, Cargo, Go, Docker Compose, or any other full ecosystem specification.

## Promotion rule

`v1.2.0rc1` may be tagged only when the current commit's required automated gates are green.

`v1.2.0` stable requires the same gates plus review of release-candidate feedback and no unresolved high-severity regression in install, update, uninstall, repair, rollback, self-update, project diagnosis, privacy reporting, memory behavior, or package-manager selection.
