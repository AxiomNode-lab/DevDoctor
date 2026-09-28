# Release Evidence — v1.2.0

Release: `1.2.0`  
Tag: `v1.2.0`  
Repository: `AxiomNode-lab/DevDoctor`  
Python distribution: `devdoctor-workstation`  
Executable: `devdoctor`

## Release status

DevDoctor v1.2.0 is published as a GitHub Release.

The release payload contains:

- `devdoctor_workstation-1.2.0-py3-none-any.whl`
- `devdoctor_workstation-1.2.0.tar.gz`
- `devdoctor-install.sh`
- `devdoctor.spdx.json`
- `SHA256SUMS`

The release is a stable GitHub Release, not a draft or prerelease.

## Qualification scope

The v1.2.0 release process covered:

- Python 3.11–3.14 clean-wheel installation.
- Unit and integration tests.
- APT, DNF, Pacman, and Zypper package-catalog validation.
- Atomic/Bazzite and Nix planning policy tests.
- Installer safety and rollback behavior.
- Project-manifest parsing and privacy-scrubbed diagnostics.
- Package identity and normalized wheel/sdist filename checks.
- Release checksums, SPDX SBOM generation, and GitHub/Sigstore attestations.

The repository distinguishes fixture validation, clean-wheel validation, container integration, memory regression checks, and real-workstation evidence. Synthetic Atomic/Bazzite tests are not presented as hardware or real-workstation compatibility evidence.

## External distribution

The GitHub release is the verified distribution channel documented for v1.2.0.

PyPI Trusted Publishing remains a separate external configuration step. Until that channel is independently verified, installation documentation should use the GitHub release installer rather than claim a PyPI package is available.

Homebrew is not advertised as an installation channel until a real tap and clean installation CI exist.

## Release identity

The stable project identity is:

- Product: `DevDoctor`
- Import package: `devdoctor`
- Console command: `devdoctor`
- Python distribution: `devdoctor-workstation`

The previous candidate name `devdoctor-cli` is not used by this repository.
