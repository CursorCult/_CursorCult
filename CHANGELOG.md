# Changelog

All notable changes to `_CursorCult` and the `cursorcult` CLI are documented here.

This project uses semantic versioning (`vX.Y.Z`).

## v0.11.2

- `cursorcult link` and `cursorcult link --subtree` now write relative paths (no absolute `.gitmodules` entries).

## v0.11.1

- `cursorcult list` retries unauthenticated on GitHub 403 to avoid bad-token failures.
- README wording clarified for GitHub installs.

## v0.11.0

- `cursorcult link` supports `--subtree` to vendor editable rule packs.
- `cursorcult link` and `cursorcult copy` accept multiple specs in one call.
- Publish workflow disables attestations to avoid Rekor flakiness.

## v0.4.0

- `ccverify` now requires a YAML front matter header in `RULE.md` with `description` and `alwaysApply: true`.
- Front matter `description` is checked against the GitHub repo description when available.
- `cursorcult new` templates include the required front matter.

## v0.5.0

- Added `cursorcult verify` command (alias for `ccverify`).

## v0.6.0

- Added `cursorcult copy` to copy a rule pack into `.cursor/rules/<NAME>` without submodules.
- Documentation updated to reflect multi-pack layout under `.cursor/rules/`.

## v0.7.0

- `cursorcult new` now requires an explicit description and no longer defaults to “Cursor rule pack: …”.

## v0.8.0

- Removed the standalone `ccverify` command; use `cursorcult verify`.

## v0.9.0

- `cursorcult list` output formatting simplified to name/version/description with a README URL line.
- `cursorcult verify` enforces rule repo names <= 20 characters.

## v0.9.1

- Package metadata wording cleanup (no behavioral changes).

## v0.3.0

- Rule packs now use `RULE.md` (not `RULES.md`); `cursorcult new` and `ccverify` enforce this.
- `ccverify` no longer requires every `main` commit to be tagged; it only enforces contiguous `vN` tags on `main`.
- New rule templates include the official Cursor rule file format link.

## v0.2.0

- Added `cursorcult new` to create a new rule repo with standard template files.
- `ccverify` now allows pre‑v0 repos to have no tags; once tags exist, they must follow contiguous `vN` rules.

## v0.2.1

- `ccverify` now enforces `RULE.md` under 5000 characters.

## v0.1.1

- `cursorcult list` now shows only repos with a `vN` tag (released rules).

## v0.1.2

- `ccverify` now requires a `.github/workflows/ccverify.yml` CI workflow and allows only that extra tracked file.

## v0.1.0

- Initial PyPI‑ready CLI packaging.
