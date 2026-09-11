# DevDoctor v1.1.0 Release Notes

DevDoctor v1.1.0 turns the bootstrap inventory into an intelligent detection and repair engine while keeping the CLI read-only by default.

## Historical packaging correction

These notes originally planned to use the Python distribution name `devdoctor-cli`. That name is used by another public project and is **not** the publication identity of `AxiomNode-lab/DevDoctor`.

Do not use `pip install devdoctor-cli` to install this repository. Current release work uses the distribution name `devdoctor-workstation` while preserving the `devdoctor` executable command.

## Highlights

- Tool health states: `ready`, `missing`, `warning`, and `broken`.
- Dependency-aware checks for Docker, Flutter, Git, Python, Node.js, Java, Cargo, kubectl, and related toolchains.
- Repair recommendations with problem, reason, risk, command or manual action, verification command, and rollback command when known.
- PATH analysis for duplicate entries, missing directories, unexported user binary directories, broken executable symlinks, and shadowed commands.
- Search results include category, health, version, installation method, profiles, dependencies, install command, and website.
- Install plans explain why a package manager was selected and whether sudo is required.
- Executed operations are logged as JSON Lines with command results and verification results.

## Compatibility

The public CLI shape remains compatible with v1.0.0:

```bash
devdoctor
devdoctor check --profile devops
devdoctor install git docker --dry-run
devdoctor repair docker
devdoctor search docker
devdoctor export json --output inventory.json
```

The legacy health report remains available through `devdoctor health`.

## Safety

Inventory, search, and repair commands do not modify the system. Commands that change packages, caches, or DevDoctor itself require explicit mutation paths and confirmation according to the version being used.

Repair recommendations are intentionally conservative. DevDoctor prints shell exports, service commands, and manual actions, but it does not edit shell startup files, start services, change group membership, or remove packages from the ordinary `repair` command.

## Installation note

For current development builds use the repository source until the `devdoctor-workstation` PyPI project is published and verified:

```bash
python -m pip install "git+https://github.com/AxiomNode-lab/DevDoctor.git"
devdoctor --version
```

See [RELEASE_DISTRIBUTION.md](RELEASE_DISTRIBUTION.md) for the current publication identity and release process.

## Validation

This release line was prepared with formatting, lint, pytest, CLI smoke, build, and package metadata checks. Current release candidates add a larger Python matrix, clean-wheel checks, distro integration, checksums, SBOM, and attestations.
