# Security Policy

DevDoctor inspects local development environments and prints command plans. The project treats command execution, shell handling, package-manager operations, and report exports as security-sensitive code.

## Supported Versions

Security fixes target the latest released version on `main`.

## Reporting a Vulnerability

Do not open a public issue for a suspected vulnerability.

Use GitHub Security Advisories for this repository:

https://github.com/AxiomNode-lab/DevDoctor/security/advisories/new

If you cannot use GitHub advisories, email the maintainers at info@axiomnode.tech with "DevDoctor security" in the subject.

Include:

- DevDoctor version
- distribution and Python version
- exact command used
- impact
- reproduction steps
- logs or output with secrets removed

## Security Model

- Inventory, search, export, and repair commands are read-only.
- Mutating operations require `--apply`.
- Commands are executed with argument vectors and `shell=False`.
- DevDoctor does not store secrets, tokens, package-manager credentials, or shell history.
- Operation logs store command metadata, exit codes, durations, and bounded verification output.
- Repair suggestions are printed as guidance. They are not executed by the `repair` command.

## Maintainer Checklist

Before merging security-sensitive changes:

- Confirm no new `shell=True` usage.
- Confirm external input is not interpolated into shell strings.
- Confirm file writes are user-requested or confined to DevDoctor state/report paths.
- Confirm subprocess timeouts are bounded where output is captured.
- Confirm tests cover failure paths and non-destructive behavior.
