import argparse
import sys
from typing import List, Optional

from .core import link_rule, list_repos, print_repos


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        prog="cursorcult",
        description="List and link CursorCult rule packs.",
    )
    subparsers = parser.add_subparsers(dest="command")

    subparsers.add_parser("list", help="List rule packs (default).")
    link_parser = subparsers.add_parser("link", help="Link a rule pack as a submodule.")
    link_parser.add_argument("spec", help="Rule name or name:tag (e.g., UNO or UNO:v1).")

    args = parser.parse_args(argv)

    try:
        if args.command in (None, "list"):
            repos = list_repos()
            print_repos(repos)
            return 0
        if args.command == "link":
            link_rule(args.spec)
            return 0
        parser.print_help()
        return 1
    except Exception as e:
        print(f"error: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())

