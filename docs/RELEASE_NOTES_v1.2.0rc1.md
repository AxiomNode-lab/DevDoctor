> Historical pre-release notes. The candidate described here was superseded by the published v1.2.0 release.

# DevDoctor v1.2.0rc1

`v1.2.0rc1` is a release candidate focused on safer workstation mutations, evidence-backed Linux package-manager support, and a verifiable release pipeline.

It is intentionally marked as a release candidate rather than stable. The release should be promoted only after the full CI matrix, distro integration jobs, clean-wheel installation checks, and release workflow pass on the tagged commit.

## Distribution identity

The product remains **DevDoctor** and the installed command remains `devdoctor`.

The Python distribution for this release is **`devdoctor-workstation`**. The previously planned name `devdoctor-cli` is already used by another public project, so this candidate changes the distribution identifier before first publication rather than risk publishing or updating the wrong package.

## Highlights

- Fedora Atomic and Bazzite planning suppresses DNF host mutation and prefers mapped user-space tooling before rpm-ostree layering.
- APT, DNF, rpm-ostree, Pacman, Zypper, Nix, Flatpak, and mixed-manager policy have deterministic fixtures; container integration provides additional evidence for selected distro families.
- `manager-conflicts` and `path-conflicts` expose suspicious package-manager and PATH overlap without modifying the workstation.
- `repair-apply` and `repair-rollback` use explicit confirmation, bounded allowlists, and transaction records.
- `diagnostics` exports a privacy-scrubbed support snapshot without hostname, username, raw PATH values, arbitrary environment values, or tokens.
- Bash, Zsh, and Fish completion scripts can be generated without editing shell startup files.
- `self-update` targets `devdoctor-workstation` and is regression-tested against the occupied legacy candidate name.
- `uninstall` fails closed unless the selected executable's package ownership can be matched to the catalog. Atomic RPM ownership alone is not treated as proof that a package is rpm-ostree layered.
- Python 3.11 through 3.14 are included in the CI and clean-wheel installation matrix.
- Tagged releases generate SHA-256 checksums and an SPDX 2.3 SBOM, then create GitHub/Sigstore provenance and SBOM attestations.
- PyPI publishing is designed to use the exact artifacts produced by the tagged release job through Trusted Publishing rather than a second rebuild.
- The release workflow verifies the normalized `devdoctor_workstation` wheel and sdist filenames before publication.

## Safety invariants

DevDoctor remains preview-first:

- Inventory, search, diagnostics, conflict analysis, and ordinary repair inspection are read-only.
- Install, update, uninstall, cache cleanup, self-update, repair application, and rollback require explicit mutation paths.
- Privileged commands are not run merely because DevDoctor detected a problem.
- `--yes` is an explicit opt-in and is not implied by detection confidence.
- Ambiguous package ownership causes uninstall to refuse rather than guess.
- Fedora Atomic/Bazzite planning does not fall back to DNF host mutation.

## Evidence levels

Support documentation distinguishes four levels instead of treating every detected package manager as equally validated:

1. Unit/fixture verified.
2. Clean-wheel verified.
3. Host/container integration verified.
4. Manual workstation verification.

Synthetic Fedora Atomic/Bazzite containers test policy. They are not represented as real workstation or bare-metal compatibility evidence.

## Release artifacts

A qualified tag is expected to produce:

- `devdoctor_workstation-1.2.0rc1-py3-none-any.whl`
- `devdoctor_workstation-1.2.0rc1.tar.gz`
- `devdoctor-install.sh`
- `devdoctor.spdx.json`
- `SHA256SUMS`

The workflow validates that the Git tag version matches the package version and that the expected distribution filenames exist before creating a GitHub release.

## External release setup still required

The repository contains the Trusted Publishing workflow, but PyPI must still be configured with a trusted publisher for **`devdoctor-workstation`**, this repository, and the `pypi` GitHub environment. The repository variable `PYPI_TRUSTED_PUBLISHING_ENABLED` must be set to `true` only after that setup is complete.

Do not configure or document `devdoctor-cli` as this project's PyPI package.

The Homebrew formula remains a readiness template. Do not advertise a Homebrew install command until a tap exists and its clean installation job passes.

## Promotion criteria

Do not promote this release candidate to `v1.2.0` stable unless:

- CI, code quality, distro integration, and release qualification are green on the final commit.
- The clean wheel runs from a new virtual environment on every advertised Python version.
- The generated checksum manifest verifies successfully.
- Provenance and SBOM attestations are created for the release artifacts.
- At least one real workstation test is recorded for any distro promoted beyond synthetic/container evidence.
- No high-severity regression remains in install, update, uninstall, repair, rollback, self-update, installer behavior, or package identity.
