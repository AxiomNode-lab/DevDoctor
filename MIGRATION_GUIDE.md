# Migration Guide

This page points to version-specific migration notes.

## v1.2.0

DevDoctor v1.2.0 uses these stable identities:

- Product: `DevDoctor`
- Python package: `devdoctor`
- Executable: `devdoctor`
- Python distribution: `devdoctor-workstation`

The v1.2.0 GitHub release includes the wheel, source archive, installer, checksum manifest, and SBOM.

Install the release with the verified installer:

```bash
curl -fsSL -o devdoctor-install.sh https://github.com/AxiomNode-lab/DevDoctor/releases/download/v1.2.0/devdoctor-install.sh
sh devdoctor-install.sh --source github --version 1.2.0
rm devdoctor-install.sh
```

The earlier candidate name `devdoctor-cli` is not the distribution name for this repository.

`devdoctor self-update` targets `devdoctor-workstation`.

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
