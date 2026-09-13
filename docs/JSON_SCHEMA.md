# JSON output contract

DevDoctor's machine-readable outputs are described by JSON Schema (draft 2020-12) files in [`docs/schema/`](schema/). CI validates real command output against them, so a change that breaks a consumer breaks the build first.

| Command | Schema | `schema_version` |
| --- | --- | --- |
| `devdoctor --json`, `devdoctor check … --json`, `devdoctor export json` | [`inventory.schema.json`](schema/inventory.schema.json) | 1 |
| `devdoctor project <path> --json` | [`project.schema.json`](schema/project.schema.json) | 1 |
| `devdoctor diff --json` | [`diff.schema.json`](schema/diff.schema.json) | 1 |

## Stability policy

- Every payload carries a top-level integer `schema_version`. It is bumped only for a **breaking** change: a removed or renamed field, a changed type, or a removed enum value.
- **Additions are not breaking.** New enum values, new optional fields, and new keys under `system` (host facts grow as detectors are added) may appear without a bump. Consumers should ignore keys they do not know and treat unknown enum values as "other".
- Everything outside `system` is closed (`additionalProperties: false`) in the schema, so a typo or a rename in DevDoctor itself fails the schema test rather than reaching users.
- Enumerations that mirror a table in the code (package-manager `family`, tool `health`, PATH issue `kind`, project check `status`, diff `kind`) are pinned by tests against that table.

## Validating locally

```bash
python -m pip install jsonschema
devdoctor --json > inventory.json
python -c "import json, jsonschema; jsonschema.validate(json.load(open('inventory.json')), json.load(open('docs/schema/inventory.schema.json')))"
```

The GitHub Action exposes the `project` payload path as its `report` output; it validates against `project.schema.json`.
