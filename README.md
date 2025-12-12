# CursorCult

CursorCult is a library of small, opinionated Cursor rule packs. Each rule lives in its own repository and is meant to be copied into a codebase that wants to follow it.

## How to use

1. Browse the rule packs below and pick the ones that match your project.
2. Read the pack’s `README.md` to understand when it applies and how it interacts with other rules.
3. Use the pack’s `RULES.md` as your Cursor rules:
   - Copy the file into your project’s Cursor rules location, or
   - Paste its contents into your Cursor rules configuration.
4. If you want multiple packs, merge their `RULES.md` contents into a single ruleset for your project and resolve any conflicts explicitly.

CursorCult doesn’t prescribe *which* rules you must use—only provides clean, composable building blocks.

## Format

Every rule repo follows the same minimal format:

- `RULES.md` — the ruleset itself, written in the modern Cursor style.
- `README.md` — when to use the rule and any credits.
- `LICENSE` — currently The Unlicense (public domain).

Rule repos are intentionally tiny and low‑ceremony. Contributions are via pull requests.

## Discovering rules

CursorCult publishes many small rule repos. Instead of keeping a static list here, use the helper script in this repo:

```sh
python3 cursorcult.py
```

This prints the current rules in the organization, each repo’s one‑line description, latest tag version, and a link to its `README.md`.

To link a rule pack into your project as a git submodule:

```sh
python3 cursorcult.py link <NAME>
python3 cursorcult.py link <NAME>:v<X>
```

`link` expects a `.cursor/rules/` directory at your project root. It adds the chosen rule repo as a submodule under `.cursor/rules/<NAME>` and checks out the requested tag (default: latest `vN`).

## Contributing

- Open a PR against the relevant rule repo.
- Keep changes focused and consistent with the rule’s voice: `RULES.md` is professional/exacting; `README.md` can be cheeky.
