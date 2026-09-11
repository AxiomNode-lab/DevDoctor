# Migration Guide

This page points to version-specific migration notes.

## v1.2.0 release candidate

The GitHub project remains `DevDoctor`, the import package remains `devdoctor`, and the executable command remains `devdoctor`.

The Python distribution prepared for publication is now `devdoctor-workstation`.

The earlier candidate name `devdoctor-cli` is already used by another public project. It must not be used to install or update this repository. If you installed a package named `devdoctor-cli`, do not assume it came from `AxiomNode-lab/DevDoctor`; inspect its package metadata and source before removing or changing it.

Before the first verified PyPI release, use the repository installation path:

```bash
python -m pip install "git+https://github.com/AxiomNode-lab/DevDoctor.git"
devdoctor --version
```

After `devdoctor-workstation` is published and verified, the intended PyPI command will be:

```bash
python -m pip install --upgrade devdoctor-workstation
devdoctor --version
```

`devdoctor self-update` follows the same distribution identity.

## v1.1.0

DevDoctor v1.1.0 keeps the v1.0 CLI shape and adds richer detection data:

- health states: `ready`, `missing`, `warning`, `broken`
- dependency status
- repair recommendations
- PATH analysis
- structured operation logs

Script users should note that `devdoctor --quiet` includes a `warnings=` field:

```text
installed=33 missing=31 warnings=2 broken=0 total=64
```

Use `devdoctor --json` for a stable machine-readable inventory.

## v1.0.0

See [docs/MIGRATION_v1.0.0.md](docs/MIGRATION_v1.0.0.md).
