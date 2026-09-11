# Support

Use the public issue tracker and discussions for support that does not involve secrets.

## Questions

Open a GitHub Discussion:

https://github.com/AxiomNode-lab/DevDoctor/discussions

Good questions include:

- the command you ran
- DevDoctor version from `devdoctor --version`
- Linux distribution and version
- relevant terminal output

For package-manager and distribution behavior, see [docs/SUPPORTED_DISTROS.md](docs/SUPPORTED_DISTROS.md). The support matrix distinguishes fixture coverage, clean-wheel verification, real host integration, and manual workstation testing.

## Diagnostic export

Prefer the scrubbed diagnostic command when opening a support request:

```sh
devdoctor diagnostics --output devdoctor-diagnostics.json
```

The diagnostic snapshot intentionally omits the hostname, username, raw PATH values, and arbitrary environment-variable values. Review the generated file before attaching it because no diagnostic exporter can infer every locally sensitive identifier.

For executable shadowing or mixed package-manager problems, these read-only commands are useful:

```sh
devdoctor manager-conflicts
devdoctor path-conflicts
```

## Bugs

Use the bug report template:

https://github.com/AxiomNode-lab/DevDoctor/issues/new/choose

Remove secrets, tokens, private paths, and internal hostnames before posting output.

## Security

Use the security policy in [SECURITY.md](SECURITY.md). Do not report vulnerabilities in public issues.

## Scope

DevDoctor is Linux-only. It does not support Windows or macOS as target platforms, although contributors may work on the code from any environment that can run the test suite.
