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

## Rule packs

- UNO — one file == one definitional unit: https://github.com/CursorCult/UNO.git
- EzGrep — search‑first naming for grep/ack workflows: https://github.com/CursorCult/EzGrep.git
- PUTT PUTT — total coverage via public‑only tests: https://github.com/CursorCult/PUTTPUTT.git
- UMP — underscore means private everywhere: https://github.com/CursorCult/UMP.git
- HEDGE_CLIPPERS — no hedged defaults; explicitness over fallbacks: https://github.com/CursorCult/HEDGE_CLIPPERS.git
- DRY — do not repeat yourself: https://github.com/CursorCult/DRY.git
- RAII — resource acquisition is initialization: https://github.com/CursorCult/RAII.git
- Pinocchio — avoid documentation that could become lies: https://github.com/CursorCult/Pinocchio.git
- TruthOrSilence — internal prose must be true or deleted: https://github.com/CursorCult/TruthOrSilence.git
- NoDeadCode — no dead, unused, or unreachable code: https://github.com/CursorCult/NoDeadCode.git

## Contributing

- Open a PR against the relevant rule repo.
- Keep changes focused and consistent with the rule’s voice: `RULES.md` is professional/exacting; `README.md` can be cheeky.
