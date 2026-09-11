#!/usr/bin/env python3
"""Generate a small deterministic SPDX SBOM for DevDoctor release artifacts."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
import tomllib
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _created_at() -> str:
    try:
        epoch = int(
            subprocess.check_output(
                ["git", "log", "-1", "--format=%ct"],
                cwd=ROOT,
                text=True,
            ).strip()
        )
    except (OSError, subprocess.CalledProcessError, ValueError):
        epoch = 0
    return datetime.fromtimestamp(epoch, tz=UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def _dependency_name(requirement: str) -> str:
    name = re.split(r"[<>=!~;\[\]\s]", requirement, maxsplit=1)[0]
    return name.strip()


def _spdx_id(name: str) -> str:
    safe = re.sub(r"[^A-Za-z0-9.-]+", "-", name).strip("-")
    return f"SPDXRef-Package-{safe or 'dependency'}"


def generate_sbom(dist_dir: Path) -> dict[str, object]:
    metadata = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    project = metadata["project"]
    name = str(project["name"])
    version = str(project["version"])
    dependencies = sorted({_dependency_name(item) for item in project.get("dependencies", [])})
    artifacts = sorted(
        path
        for path in dist_dir.iterdir()
        if path.suffix == ".whl" or path.name.endswith(".tar.gz")
    )
    artifact_fingerprint = hashlib.sha256()
    for artifact in artifacts:
        artifact_fingerprint.update(artifact.name.encode("utf-8"))
        artifact_fingerprint.update(_sha256(artifact).encode("ascii"))

    root_id = _spdx_id(name)
    packages: list[dict[str, object]] = [
        {
            "name": name,
            "SPDXID": root_id,
            "versionInfo": version,
            "downloadLocation": "NOASSERTION",
            "filesAnalyzed": False,
            "licenseConcluded": "MIT",
            "licenseDeclared": "MIT",
            "copyrightText": "NOASSERTION",
            "externalRefs": [
                {
                    "referenceCategory": "PACKAGE-MANAGER",
                    "referenceType": "purl",
                    "referenceLocator": f"pkg:pypi/{name}@{version}",
                }
            ],
        }
    ]
    relationships: list[dict[str, str]] = [
        {
            "spdxElementId": "SPDXRef-DOCUMENT",
            "relationshipType": "DESCRIBES",
            "relatedSpdxElement": root_id,
        }
    ]

    for dependency in dependencies:
        dependency_id = _spdx_id(dependency)
        packages.append(
            {
                "name": dependency,
                "SPDXID": dependency_id,
                "downloadLocation": "NOASSERTION",
                "filesAnalyzed": False,
                "licenseConcluded": "NOASSERTION",
                "licenseDeclared": "NOASSERTION",
                "copyrightText": "NOASSERTION",
                "externalRefs": [
                    {
                        "referenceCategory": "PACKAGE-MANAGER",
                        "referenceType": "purl",
                        "referenceLocator": f"pkg:pypi/{dependency}",
                    }
                ],
            }
        )
        relationships.append(
            {
                "spdxElementId": root_id,
                "relationshipType": "DEPENDS_ON",
                "relatedSpdxElement": dependency_id,
            }
        )

    return {
        "spdxVersion": "SPDX-2.3",
        "dataLicense": "CC0-1.0",
        "SPDXID": "SPDXRef-DOCUMENT",
        "name": f"{name}-{version}",
        "documentNamespace": (
            "https://github.com/AxiomNode-lab/DevDoctor/sbom/"
            f"{name}/{version}/{artifact_fingerprint.hexdigest()}"
        ),
        "creationInfo": {
            "created": _created_at(),
            "creators": ["Tool: DevDoctor scripts/generate_sbom.py"],
        },
        "packages": packages,
        "relationships": relationships,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dist", type=Path, default=Path("dist"))
    parser.add_argument("--output", type=Path, default=Path("dist/devdoctor.spdx.json"))
    args = parser.parse_args()

    payload = generate_sbom(args.dist)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    serialized = json.dumps(payload, indent=2, sort_keys=True) + "\n"
    args.output.write_text(serialized, encoding="utf-8")
    print(args.output)


if __name__ == "__main__":
    main()
