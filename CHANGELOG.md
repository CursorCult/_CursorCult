# Changelog

All notable changes to `_CursorCult` and the `cursorcult` CLI are documented here.

This project uses semantic versioning (`vX.Y.Z`).

## v0.2.0

- Added `cursorcult new` to create a new rule repo with standard template files.
- `ccverify` now allows pre‑v0 repos to have no tags; once tags exist, they must follow contiguous `vN` rules.

## v0.1.1

- `cursorcult list` now shows only repos with a `vN` tag (released rules).

## v0.1.2

- `ccverify` now requires a `.github/workflows/ccverify.yml` CI workflow and allows only that extra tracked file.

## v0.1.0

- Initial PyPI‑ready CLI packaging.
