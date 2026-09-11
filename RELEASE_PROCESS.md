# Release Process

This is the public release checklist for DevDoctor maintainers.

## Identity

The release identity must remain consistent:

- GitHub/project name: `DevDoctor`
- Python import package: `devdoctor`
- Installed command: `devdoctor`
- Python distribution: `devdoctor-workstation`

`devdoctor-cli` is not this project's publication name and must not appear in active installation, self-update, artifact, or PyPI publishing instructions.

## Prepare

1. Confirm `pyproject.toml` and `devdoctor/__init__.py` contain the same version.
2. Confirm `pyproject.toml` uses distribution name `devdoctor-workstation`.
3. Confirm `[project.scripts]` exposes `devdoctor = "devdoctor.entrypoint:main"`.
4. Update `CHANGELOG.md`.
5. Add or update release notes under `docs/`.
6. Review README commands, screenshots, badges, and links.
7. Confirm release-critical workflows target the current package identity.
8. Confirm the current PR head is the commit being qualified.

## Validate

```bash
ruff format --check .
ruff check .
pytest
python -m devdoctor --version
python -m devdoctor --quiet
python -m devdoctor --json | python -m json.tool
python -m devdoctor search docker --no-color
python -m devdoctor repair docker --no-color
python -m build
python -m twine check dist/*
```

Validate normalized artifact names:

```bash
VERSION="$(python -c 'from devdoctor import __version__; print(__version__)')"
test -f "dist/devdoctor_workstation-${VERSION}-py3-none-any.whl"
test -f "dist/devdoctor_workstation-${VERSION}.tar.gz"
```

## Fresh environment check

```bash
python -m venv /tmp/devdoctor-release-check
/tmp/devdoctor-release-check/bin/python -m pip install --no-cache-dir dist/*.whl
/tmp/devdoctor-release-check/bin/devdoctor --version
/tmp/devdoctor-release-check/bin/devdoctor diagnostics --stdout | python -m json.tool
/tmp/devdoctor-release-check/bin/devdoctor self-update
```

The self-update preview must contain `devdoctor-workstation`.

## PyPI Trusted Publishing

Before enabling publication:

1. Create or confirm the PyPI pending publisher/project named `devdoctor-workstation`.
2. Configure repository `AxiomNode-lab/DevDoctor`.
3. Configure workflow `.github/workflows/release.yml`.
4. Configure GitHub environment `pypi`.
5. Confirm PyPI metadata links back to this repository.
6. Set `PYPI_TRUSTED_PUBLISHING_ENABLED=true` only after this setup is complete.

Do not configure `devdoctor-cli` for this repository and do not use a long-lived PyPI token for the prepared workflow.

## Publish

1. Require final-head CI, code quality, distro integration, and release qualification to pass.
2. Merge the qualified release PR.
3. Create the version tag only on the qualified merged commit.
4. Push the tag and let `.github/workflows/release.yml` build the release once.
5. Verify GitHub Release contains the wheel, sdist, installer, SBOM, and checksum manifest.
6. Verify attestations and `SHA256SUMS`.
7. If PyPI publishing is enabled, verify the public package from a clean environment:

```bash
python -m venv /tmp/devdoctor-pypi-check
/tmp/devdoctor-pypi-check/bin/python -m pip install devdoctor-workstation
/tmp/devdoctor-pypi-check/bin/devdoctor --version
```

## Homebrew

Homebrew is not a publication channel until a real tap and clean installation CI exist. Do not advertise a `brew install` command before then.
