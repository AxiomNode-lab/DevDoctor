# Project-aware diagnostics

`devdoctor project` compares declarative project requirements with the developer tools visible on the current Linux workstation.

It is intentionally a **diagnostic** command, not an environment manager. It does not install runtimes, activate version managers, evaluate shell code, run project hooks, or execute manifest-defined commands.

## Usage

```bash
devdoctor project .
devdoctor project /path/to/project
devdoctor project . --json
devdoctor project . --json --no-fail
```

Exit behavior:

- `0` when no discovered requirement is missing or incompatible.
- `1` when a required tool is missing or a safely comparable version is incompatible.
- Unknown/unsupported version expressions are reported as `unknown`; they are not guessed into a pass or failure.
- `--no-fail` keeps the report but forces exit code `0`, which is useful while introducing the check into CI.

## Supported project evidence

The current implementation reads these files when they are regular UTF-8 files inside the selected project root:

| Source | Evidence used |
| --- | --- |
| `pyproject.toml` | Python project presence, `project.requires-python`, Poetry Python constraint. |
| `package.json` | Node project presence, `engines`, `packageManager`, Volta versions. |
| `.tool-versions` | Known tool/version declarations. |
| `mise.toml`, `.mise.toml` | Known entries from the `[tools]` table. |
| `Cargo.toml` | Rust/Cargo project presence and `package.rust-version`. |
| `go.mod` | Go project presence and the `go` language version directive. |
| `devbox.json` | Known packages that map to DevDoctor catalog tools. |
| `.nvmrc`, `.node-version` | Node version. |
| `.python-version` | Python version. |
| `.ruby-version` | Ruby version. |
| `.java-version` | Java version. |
| `.go-version` | Go version. |
| `Dockerfile`, Compose filenames | Docker requirement presence. |
| `Gemfile` | Ruby requirement presence. |
| `composer.json` | PHP requirement presence. |
| `pom.xml`, `build.gradle`, `build.gradle.kts` | Java requirement presence. |

A file being supported does not mean DevDoctor interprets every field in that ecosystem. Only the evidence listed above is used.

## Version comparison

The comparator is deliberately bounded. It supports common numeric expressions used by Python, Node, Poetry, mise/asdf-style files, and language manifests:

```text
3.12
22.x
>=3.11
>=20 <23
>=3.11,!=3.12.0
^20.10.0
~3.12
~=3.11.2
>=18 || ^22
```

Unsupported expressions are returned as `unknown` instead of being approximated. For example, the release-candidate parser does not claim full npm SemVer or full PEP 440 compatibility.

`package.json` `packageManager` integrity suffixes such as `pnpm@9.15.0+sha512-...` are stripped before the numeric version is compared.

## Safety boundaries

Project directories can contain attacker-controlled files, so project diagnosis follows stricter rules than ordinary configuration discovery:

- No manifest-defined command is executed.
- Symlinked supported manifests are not followed.
- Each manifest is limited to 1 MB.
- Manifests must decode as UTF-8.
- Invalid JSON/TOML becomes a warning rather than code execution or a guessed requirement.
- The JSON report exposes the selected directory basename, not its absolute path.
- The command does not write into the inspected project.

These boundaries are part of the command contract and should have regression tests whenever new manifest formats are added.

## Example

```text
$ devdoctor project .
DevDoctor project check: example-service
Sources: pyproject.toml, package.json
READY    python     found=3.13.7 required=>=3.12 source=pyproject.toml
MISMATCH node       found=20.19.0 required=>=22 source=package.json
MISSING  pnpm       found=not found required=9.15.0 source=package.json
```

The example illustrates output shape only; it is not a compatibility claim for any specific workstation.

## CI use

A project can use the command as a workstation/onboarding preflight:

```bash
devdoctor project . --json
```

During gradual adoption:

```bash
devdoctor project . --json --no-fail
```

DevDoctor should remain complementary to reproducible environment tools. A project may still use mise, Devbox, containers, Nix, or another environment manager as its source of truth; DevDoctor's job is to explain whether the current workstation matches the declarative requirements it can safely understand.
