# Contributing to DevDoctor

DevDoctor is a Linux CLI for workstation inventory, bootstrap planning, and repair guidance. Contributions should keep that scope tight: local evidence, safe command planning, clear terminal output, and no background services.

The product is `DevDoctor`, the Python distribution is `devdoctor-workstation`, and the import package and executable command are both `devdoctor`. Do not add active install/update instructions for `devdoctor-cli`; that distribution name belongs to another project.

## Development setup

```bash
git clone https://github.com/AxiomNode-lab/DevDoctor.git
cd DevDoctor
python -m pip install -e ".[dev]"
python -m devdoctor --version
```

## Validation

Run these before opening a pull request:

```bash
ruff format --check .
ruff check .
pytest
python -m devdoctor --quiet
python -m devdoctor --json | python -m json.tool
```

For packaging changes, also run:

```bash
python -m build
python -m twine check dist/*
```

Packaging changes must preserve these identities:

```text
project distribution: devdoctor-workstation
wheel prefix:         devdoctor_workstation-
console command:      devdoctor
import package:       devdoctor
```

## Contribution guidelines

- Keep probes fast, local, and safe to run without root privileges.
- Do not use `shell=True`.
- Do not execute package-manager, service, group, or filesystem-changing commands during inventory or ordinary repair scans.
- Report unavailable data as unavailable. Do not guess versions, package ownership, download sizes, installed state, or hardware support.
- Add tests for catalog mappings, package identity, repair checks, parser behavior, CLI output, or export shape when you change them.
- Update README or docs when user-visible behavior changes.
- Do not promote synthetic/container policy tests as real workstation validation.

## Catalog entries

Tool catalog entries should include:

- stable `id`
- display title
- category
- executable name
- official website when available
- package mappings that are known to work on supported managers
- required and optional dependencies only when the relationship is real

Prefer conservative package mappings over broad guesses. If a package requires a vendor repository that DevDoctor cannot configure safely, document the limitation instead of adding a misleading install command.

## Pull requests

Good pull requests are narrow and verifiable. Include:

- what changed
- why it changed
- commands used for validation
- screenshots or terminal output for UI changes
- notes about distro-specific behavior when relevant

Maintainers may ask for changes that keep DevDoctor non-destructive, Linux-focused, and honest about unavailable data.
