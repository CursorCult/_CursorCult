# CursorCult

## Install (pipx)

```sh
pipx install cursorcult
cursorcult
```

CursorCult is a library of small, opinionated Cursor rule packs. Each rule lives in its own repository and is meant to be copied into a codebase that wants to follow it.

Main organization page (browse all packs): https://github.com/CursorCult

## How to use

1. After installing `cursorcult` (above), run it to see released rule packs and pick the ones that match your project.
2. Read the pack’s `README.md` to understand when it applies and how it interacts with other rules.
3. Add rule packs into your project under `.cursor/rules/`:
   - Preferred: link them as git submodules (keeps you on tagged versions).
   - Optional: copy them in as plain files.
4. Multiple packs coexist as siblings:

```text
.cursor/rules/UNO/
.cursor/rules/Pinocchio/
.cursor/rules/TruthOrSilence/
...
```

CursorCult doesn’t prescribe *which* rules you must use—only provides clean, composable building blocks.

## 🏷️ Versioning Policy

CursorCult follows a strict stability contract based on semantic version tags.

- **`v0` (Volatile):**
    - The "dev/testing" channel.
    - Tags are **mutable** and may be force-pushed.
    - Opting into `v0` means opting into bleeding-edge changes and potential breakage.
    - Tools will aggressively update `v0` pointers to the latest commit.

- **`v1+` (Stable):**
    - The "stable" channel.
    - Tags are **immutable**. Once released, `v1` code never changes.
    - Users on `v1` stay on `v1` until they explicitly upgrade to `v2`.
    - If you are on `v0` and `v1` is released, updates will promote you to `v1`.

## Format

Every rule repo follows the same minimal format:

- `RULE.md` — the ruleset itself, written in the modern Cursor style.
- `README.md` — when to use the rule and any credits.
- `LICENSE` — currently The Unlicense (public domain).

Rule repos are intentionally tiny and low‑ceremony. Contributions are via pull requests.

Cursor rule file format reference: https://cursor.com/docs/context/rules#rulemd-file-format

## Discovering rules

CursorCult publishes many small rule repos. Instead of keeping a static list here, use the `cursorcult` CLI (installed above).

To install directly from GitHub:

```sh
pipx install git+https://github.com/CursorCult/_CursorCult.git
```

**Web Search:** Browse and filter all community rules at [cursorcult.github.io](https://cursorcult.github.io/).

This prints the released rules in the organization (repos with a `vN` tag), each repo’s one‑line description, latest tag version, and a link to its `README.md`. Repos without tags are treated as unreleased and are not listed.

## Linking a ruleset

Rulesets are named lists of rules registered in `CursorCult/_rulesets`.

Rulesets only include rules with a `v0` tag; anything missing that requirement gets pruned.

```sh
cursorcult link --ruleset <RULESET>
```

To link from a local file containing newline- or space-separated rule names:

```sh
cursorcult link --ruleset-file path/to/rules.txt
```

To link a rule pack into your project as a git submodule:

```sh
cursorcult link <NAME>
cursorcult link <NAME>:v<X>
cursorcult link <NAME1> <NAME2> ...
```

`link` expects a `.cursor/rules/` directory at your project root. It adds the chosen rule repo as a submodule under `.cursor/rules/<NAME>` and checks out the requested tag (default: latest `vN`).

If you want to edit the rule pack locally (for example, add `globs` or change apply mode), vendor it with git subtree instead:

```sh
cursorcult link --subtree <NAME>
cursorcult link --subtree <NAME>:v<X>
```

This copies the rule repo’s contents into `.cursor/rules/<NAME>` as normal files. You can update later with `git subtree pull` if desired.

To copy a rule pack into your project without using submodules:

```sh
cursorcult copy <NAME>
cursorcult copy <NAME>:v<X>
cursorcult copy <NAME1> <NAME2> ...
```

`copy` writes the pack’s `LICENSE`, `README.md`, and `RULE.md` into `.cursor/rules/<NAME>` at the requested tag.

Rule repos use simple integer tags (`v0`, `v1`, `v2`, …). The CLI itself is versioned with semantic versioning (`vX.Y.Z`).

## Creating a new rule pack

To propose a new rule pack in the CursorCult org, use the intake repo:

- https://github.com/CursorCult/_intake

Maintainers can initialize a new rule repo with the standard template:

```sh
cursorcult new <NAME> --description "one-line summary"
```

This creates `CursorCult/<NAME>` and initializes:

- `LICENSE` (Unlicense)
- `README.md` (with install section)
- `RULE.md`
- `.github/workflows/ccverify.yml`

Release convention for new rules:

- Develop on `main` with any number of commits while unreleased (no tags).
- When ready for the first release, squash `main` to a single commit and tag it `v0`.
- After any `vN` tags exist, tags must remain contiguous (`v0`, `v1`, `v2`, …). This is what `cursorcult verify` enforces.

## Contributing

- Open a PR against the relevant rule repo.
- Keep changes focused and consistent with the rule’s voice: `RULE.md` is professional/exacting; `README.md` can be cheeky.
- Before tagging a rule release, validate the repo format with `cursorcult verify` from a local clone.
