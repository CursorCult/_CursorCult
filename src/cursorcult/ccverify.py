#!/usr/bin/env python3

import argparse
import os
import re
import subprocess
import sys
from dataclasses import dataclass
from typing import List, Optional, Set, Tuple

from .constants import TAG_RE, UNLICENSE_TEXT


@dataclass
class CheckResult:
    ok: bool
    errors: List[str]


def run(cmd: List[str], cwd: str) -> str:
    proc = subprocess.run(cmd, cwd=cwd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    if proc.returncode != 0:
        raise RuntimeError(
            f"Command failed: {' '.join(cmd)}\n{proc.stderr.strip() or proc.stdout.strip()}"
        )
    return proc.stdout


def normalize_text(text: str) -> str:
    # Normalize line endings and trailing whitespace for robust comparisons.
    lines = [line.rstrip() for line in text.replace("\r\n", "\n").replace("\r", "\n").split("\n")]
    return "\n".join(lines).strip() + "\n"


def get_repo_name(path: str, override: Optional[str] = None) -> str:
    if override:
        return override
    try:
        origin = run(["git", "remote", "get-url", "origin"], cwd=path).strip()
        m = re.search(r"/([^/]+?)(?:\.git)?$", origin)
        if m:
            name = m.group(1)
            if name.endswith(".git"):
                name = name[: -len(".git")]
            return name
    except Exception:
        pass
    return os.path.basename(os.path.abspath(path))


def check_tracked_files(path: str) -> List[str]:
    errors: List[str] = []
    try:
        files = run(["git", "ls-files"], cwd=path).splitlines()
    except Exception:
        files = [f for f in os.listdir(path) if not f.startswith(".")]

    core = {"LICENSE", "README.md", "RULES.md"}
    ci_paths = {".github/workflows/ccverify.yml", ".github/workflows/ccverify.yaml"}
    tracked = set(files)

    missing = core - tracked
    if missing:
        errors.append(f"Missing required files: {', '.join(sorted(missing))}.")

    has_ci = bool(tracked & ci_paths)
    if not has_ci:
        errors.append(
            "Missing required CI workflow: .github/workflows/ccverify.yml (or .yaml)."
        )

    extra = tracked - core - ci_paths
    if extra:
        errors.append(f"Extra tracked files not allowed: {', '.join(sorted(extra))}.")
    return errors


def check_license(path: str) -> List[str]:
    errors: List[str] = []
    license_path = os.path.join(path, "LICENSE")
    if not os.path.isfile(license_path):
        return ["LICENSE file missing."]
    with open(license_path, "r", encoding="utf-8") as f:
        content = normalize_text(f.read())
    if content != normalize_text(UNLICENSE_TEXT):
        errors.append("LICENSE is not the Unlicense (content mismatch).")
    return errors


def check_readme_install(path: str, repo_name: str) -> List[str]:
    errors: List[str] = []
    readme_path = os.path.join(path, "README.md")
    if not os.path.isfile(readme_path):
        return ["README.md file missing."]
    with open(readme_path, "r", encoding="utf-8") as f:
        readme = f.read()
    if "pipx install cursorcult" not in readme:
        errors.append("README.md must include installation line: 'pipx install cursorcult'.")
    expected_link = f"cursorcult link {repo_name}"
    if expected_link not in readme:
        errors.append(
            f"README.md must include link example: '{expected_link}' (adjust for rule name)."
        )
    return errors


def get_main_commits(path: str) -> List[str]:
    run(["git", "rev-parse", "--verify", "main"], cwd=path)
    out = run(["git", "rev-list", "main"], cwd=path)
    commits = [c for c in out.splitlines() if c]
    return commits


def get_tags(path: str) -> List[Tuple[str, str]]:
    # Returns list of (tag_name, commit_sha).
    out = run(["git", "tag"], cwd=path)
    names = [n.strip() for n in out.splitlines() if n.strip()]
    tags: List[Tuple[str, str]] = []
    for name in names:
        sha = run(["git", "rev-list", "-n", "1", name], cwd=path).strip()
        if sha:
            tags.append((name, sha))
    return tags


def check_tags(path: str, main_commits: List[str]) -> List[str]:
    errors: List[str] = []
    tags = get_tags(path)
    if not tags:
        # Pre‑v0 development is allowed to have no tags. Once tags exist, they must follow vN rules.
        return errors

    tag_names = [t for t, _ in tags]
    for name in tag_names:
        if not TAG_RE.match(name):
            errors.append(f"Invalid tag name '{name}'. Only v0, v1, v2, ... are allowed.")

    # Ensure tags are on main.
    main_set: Set[str] = set(main_commits)
    tag_commits = {sha for _, sha in tags}
    off_main = tag_commits - main_set
    if off_main:
        errors.append("All vN tags must point to commits on main.")

    # Ensure every main commit is tagged.
    untagged = main_set - tag_commits
    if untagged:
        errors.append(
            f"Main has {len(untagged)} untagged commits. Every main commit must have a vN tag."
        )

    # Ensure tags are contiguous starting from v0 with no gaps.
    versions = sorted(int(TAG_RE.match(n).group(1)) for n in tag_names if TAG_RE.match(n))
    if versions:
        expected = list(range(0, max(versions) + 1))
        if versions != expected:
            errors.append(
                f"vN tags must be contiguous from v0. Found: {', '.join('v'+str(v) for v in versions)}."
            )
    return errors


def verify_repo(path: str, name_override: Optional[str] = None) -> CheckResult:
    errors: List[str] = []
    repo_name = get_repo_name(path, name_override)
    errors.extend(check_tracked_files(path))
    errors.extend(check_license(path))
    errors.extend(check_readme_install(path, repo_name))
    try:
        main_commits = get_main_commits(path)
        errors.extend(check_tags(path, main_commits))
    except Exception as e:
        errors.append(f"Git checks failed: {e}")

    return CheckResult(ok=not errors, errors=errors)


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        prog="ccverify",
        description="Verify a CursorCult rules repository follows the required format.",
    )
    parser.add_argument(
        "path",
        nargs="?",
        default=".",
        help="Path to a local clone of a rules repo (default: current directory).",
    )
    parser.add_argument(
        "--name",
        dest="name_override",
        help="Override repo name for README link checks.",
    )

    args = parser.parse_args(argv)
    result = verify_repo(os.path.abspath(args.path), args.name_override)

    if result.ok:
        print("OK: rules repo is valid.")
        return 0

    print("INVALID: rules repo failed validation:")
    for err in result.errors:
        print(f"- {err}")
    return 1


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
