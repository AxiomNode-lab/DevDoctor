# DevDoctor vX.Y.Z

## Highlights

- Summarize user-visible changes only after they are validated on the release commit.
- Distinguish fixture/container evidence from real workstation verification.
- Call out any migration, package-manager, installer, or security behavior changes.

## Installation

Product: `DevDoctor`  
Python distribution: `devdoctor-workstation`  
Command: `devdoctor`

Do not publish an install command for `devdoctor-cli`; that is not this project's distribution.

After the public PyPI release is verified:

```bash
python -m pip install --upgrade devdoctor-workstation
devdoctor --version
```

For a GitHub release asset:

```bash
sh devdoctor-install.sh
```

## Compatibility and evidence

- Inventory: `devdoctor`
- JSON: `devdoctor --json`
- Search: `devdoctor search docker`
- Repair suggestions: `devdoctor repair docker`
- Privacy diagnostics: `devdoctor diagnostics --stdout`
- Legacy health reports: `devdoctor health`

List only distribution/workstation support demonstrated by the release's actual qualification evidence.

## Validation

- [ ] Final release commit matches the qualified commit.
- [ ] `ruff format --check .`
- [ ] `ruff check .`
- [ ] full `pytest`
- [ ] Python 3.11 clean wheel
- [ ] Python 3.12 clean wheel
- [ ] Python 3.13 clean wheel
- [ ] Python 3.14 clean wheel
- [ ] package-manager fixture matrix
- [ ] distro integration matrix
- [ ] `python -m build`
- [ ] `python -m twine check dist/*`
- [ ] `devdoctor self-update` targets `devdoctor-workstation`
- [ ] installer syntax and release-wheel checksum path
- [ ] `SHA256SUMS` verification
- [ ] SPDX SBOM
- [ ] provenance attestation
- [ ] SBOM attestation

## Security notes

DevDoctor does not execute supported install, update, uninstall, cache, self-update, repair-apply, or rollback operations without an explicit apply path. Document any exception as a release blocker.

## Artifacts

For `v1.2.0` the expected Python artifacts are:

- `devdoctor_workstation-1.2.0.tar.gz`
- `devdoctor_workstation-1.2.0-py3-none-any.whl`

Also include:

- `devdoctor-install.sh`
- `devdoctor.spdx.json`
- `SHA256SUMS`

Run checksum and attestation verification before promoting a release candidate to stable.
