import argparse
import sys
from typing import List, Optional

from .ccverify import verify_repo
from .core import copy_rule, link_rule, list_repos, new_rule_repo, print_repos


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        prog="cursorcult",
        description="List and link CursorCult rule packs.",
    )
    subparsers = parser.add_subparsers(dest="command")

    subparsers.add_parser("list", help="List rule packs (default).")
    link_parser = subparsers.add_parser(
        "link", help="Link a rule pack (submodule by default)."
    )
    link_parser.add_argument(
        "specs",
        nargs="+",
        help="One or more rule specs: NAME or NAME:tag (e.g., UNO or UNO:v1).",
    )
    link_parser.add_argument(
        "--subtree",
        action="store_true",
        help="Vendor the rule using git subtree instead of a submodule (editable).",
    )
    copy_parser = subparsers.add_parser(
        "copy", help="Copy a rule pack into .cursor/rules without submodules."
    )
    copy_parser.add_argument(
        "specs",
        nargs="+",
        help="One or more rule specs: NAME or NAME:tag (e.g., UNO or UNO:v1).",
    )
    new_parser = subparsers.add_parser("new", help="Create a new rule pack repo.")
    new_parser.add_argument("name", help="New rule repo name (e.g., MyRule).")
    new_parser.add_argument(
        "--description",
        required=True,
        help="One-line GitHub repo description (must match RULE.md description).",
    )
    verify_parser = subparsers.add_parser(
        "verify", help="Verify a CursorCult rules repo follows required format."
    )
    verify_parser.add_argument(
        "path",
        nargs="?",
        default=".",
        help="Path to a local clone of a rules repo (default: current directory).",
    )
    verify_parser.add_argument(
        "--name",
        dest="name_override",
        help="Override repo name for README/front matter checks.",
    )

    args = parser.parse_args(argv)

    try:
        if args.command in (None, "list"):
            repos = list_repos()
            print_repos(repos)
            return 0
        if args.command == "link":
            for spec in args.specs:
                link_rule(spec, subtree=args.subtree)
            return 0
        if args.command == "copy":
            for spec in args.specs:
                copy_rule(spec)
            return 0
        if args.command == "new":
            new_rule_repo(args.name, args.description)
            return 0
        if args.command == "verify":
            result = verify_repo(args.path, args.name_override)
            if result.ok:
                print("OK: rules repo is valid.")
                return 0
            print("INVALID: rules repo failed validation:")
            for err in result.errors:
                print(f"- {err}")
            return 1
        parser.print_help()
        return 1
    except Exception as e:
        print(f"error: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
