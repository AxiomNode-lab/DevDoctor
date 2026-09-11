# Release Process

This checklist is for maintainers cutting a DevDoctor release.

## Distribution identity

- Product: `DevDoctor`
- Console command: `devdoctor`
- Import package: `devdoctor`
- PyPI distribution: `devdoctor-workstation`

Do not publish, install, or configure Trusted Publishing for `devdoctor-cli`; that distribution name is used by another project.

## Before tagging

- Confirm `pyproject.toml` and `devdoctor/__init__.py` use the same version.
- Confirm the Python distribution name is `devdoctor-workstation`.
- Confirm the executable entry point remains `devdoctor = devdoctor.entrypoint:main`.
- Confirm the expected normalized wheel prefix is `devdoctor_workstation-`.
- Update `CHANGELOG.md`.
- Update the release notes for the new version.
- Check README commands, asset paths, and documentation links.
- Run validation from a clean checkout.
- Require the final commit, not an older commit, to pass the release gates.

## Validation

```bash
ruff format --check .
ruff check .
pytest
python -m devdoctor --quiet
python -m devdoctor --json | python -m json.tool
python -m devdoctor check git --quiet
python -m devdoctor search docker --no-color
python -m devdoctor repair docker --no-color
python -m build
python -m twine check dist/*
```

Check the artifact identity:

```bash
VERSION="$(python -c 'from devdoctor import __version__; print(__version__)')"
test -f "dist/devdoctor_workstation-${VERSION}-py3-none-any.whl"
test -f "dist/devdoctor_workstation-${VERSION}.tar.gz"
```

## PyPI setup

Before the first publication:

- Create or confirm the `devdoctor-workstation` pending publisher/project on PyPI.
- Configure Trusted Publishing for `AxiomNode-lab/DevDoctor` and `.github/workflows/release.yml`.
- Use the GitHub environment `pypi`.
- Confirm PyPI project metadata points to this repository.
- Only then enable `PYPI_TRUSTED_PUBLISHING_ENABLED=true`.

Do not use a long-lived PyPI token for the prepared release path.

## Publication

1. Push the release commit and require all final-head CI checks to pass.
2. Push the version tag only after the PR is qualified and merged.
3. Let `.github/workflows/release.yml` build the release payload once.
4. Verify `SHA256SUMS`, SBOM, attestations, wheel install, and GitHub prerelease payload.
5. If Trusted Publishing is enabled, publish the exact tested wheel and sdist artifact to PyPI without rebuilding.
6. Verify the public package in a temporary virtual environment:

```bash
python -m venv /tmp/devdoctor-pypi-check
/tmp/devdoctor-pypi-check/bin/python -m pip install devdoctor-workstation
/tmp/devdoctor-pypi-check/bin/devdoctor --version
```

Do not add a Homebrew command to release notes until a tap exists and its clean install CI passes.

## After publication

- Confirm badges render on GitHub.
- Confirm PyPI renders the README correctly and links to this repository.
- Verify `devdoctor --version`, `devdoctor --json`, `devdoctor diagnostics --stdout`, and `devdoctor self-update` from a clean installation.
- Confirm `devdoctor self-update` targets `devdoctor-workstation`.
