# Changelog

All notable changes to `_CursorCult` and the `cursorcult` CLI are documented here.

This project uses semantic versioning (`vX.Y.Z`).

## v0.4.0

- `ccverify` now requires a YAML front matter header in `RULE.md` with `description` and `alwaysApply: true`.
- Front matter `description` is checked against the GitHub repo description when available.
- `cursorcult new` templates include the required front matter.

## v0.5.0

- Added `cursorcult verify` command (alias for `ccverify`).

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
