# Roadmap

DevDoctor is a Linux workstation diagnosis and repair CLI by [AxiomNode](https://axiomnode.tech/). The roadmap favors correctness, distro coverage, and safe local operation over broad automation. Items are ordered by how much they change what a user sees on first run; each names the evidence behind it.

## Done recently

- Correct detection on Debian-family hosts (`python3`, dead launcher shebangs, merged-usr, `ssh -V`) and honest install plans: every catalog package name is verified against apt, dnf, pacman, and zypper in CI.
- Atomic/Bazzite and Nix planning policy built into the planner (no runtime patches).
- Concurrent probing: a full scan in well under a second.
- A Findings panel at the top of every report.
- `install.sh --source git`, a composite GitHub Action, an installable example plugin, AxiomNode attribution.

## Next (in order)

1. **Publish.** PyPI Trusted Publishing for `devdoctor-workstation`, a `v1.2.0` tag whose release carries the correctly named wheel and `SHA256SUMS`, and only then a Homebrew tap and an AUR package. Everything else on this list reaches nobody until `pip install devdoctor-workstation` works. *Owner action; the release workflow already builds and attests the artifacts.*
2. **`devdoctor diff`.** Done.
3. **`devdoctor fix` (guided, still preview-first).** Done as an alias of `repair-apply`, linked from the Findings panel.
4. **Stable JSON schema.** Done: `docs/schema/{inventory,project,diff}.schema.json`, validated in CI, policy in `docs/JSON_SCHEMA.md`.
5. **Recommended versions.** `ToolSpec.recommended_version` exists but is unused. Populate it from the project's own manifests during `devdoctor project`, and from a small curated table for LTS runtimes (Node, Python, Java), so `check` can say "installed 18, project wants 22" without any network access.
6. **More real-host evidence.** Run the distro-integration probe on a Fedora Atomic / Bazzite image with real `rpm-ostree` (not the synthetic os-release), and on Debian stable, Alpine (`apk`), and Void (`xbps`) containers; promote those distros in `docs/SUPPORTED_DISTROS.md` only when the job exists.
7. **Windows Subsystem for Linux and containers as first-class hosts.** Done for privileges (root drops `sudo`; missing sudo is stated) and systemd (service repairs only when it runs). Still open: snap on WSL.
8. **Shell-profile aware PATH repair.** Done: missing and duplicate entries point at the profile lines that set them.
9. **Version-manager awareness.** Done for nvm, pyenv, rbenv, asdf, mise, sdkman, and rustup paths.
10. **Localized output.** The catalog and findings are structured data; a `--lang` switch (Arabic and Turkish first, matching the maintainers) is mostly a strings table.

## Later

- Signed release artifacts (Sigstore attestations already run on tags).
- Snapshot tests for terminal output at narrow and wide widths.
- Package-manager dry-run parsers only where managers expose real dependency or download-size data.
- Enterprise onboarding documentation: a profile file format (`devdoctor.toml` in a repo) so `devdoctor project` can require tools, not just runtime versions.

## Non-goals

- A GUI or dashboard.
- Automatic privileged repair.
- Secret scanning or credential collection.
- Guessing latest versions from the network during local inventory.
- Support for non-Linux target systems. (macOS via Homebrew is the most requested exception; it stays out until the Linux story is complete and released.)
