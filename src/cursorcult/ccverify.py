#!/usr/bin/env python3

import argparse
import json
import os
import re
import subprocess
import sys
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import List, Optional, Set, Tuple

from .constants import MAX_RULES_CHARS, TAG_RE, UNLICENSE_TEXT


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


def http_json(url: str) -> object:
    headers = {"Accept": "application/vnd.github+json", "User-Agent": "ccverify"}
    token = os.getenv("GITHUB_TOKEN") or os.getenv("GH_TOKEN")
    if token:
        headers["Authorization"] = f"Bearer {token}"
    req = urllib.request.Request(url, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        raise RuntimeError(f"GitHub API error {e.code} for {url}") from e
    except urllib.error.URLError as e:
        raise RuntimeError(f"Network error fetching {url}: {e}") from e


def fetch_github_description(repo_name: str) -> str:
    data = http_json(f"https://api.github.com/repos/CursorCult/{repo_name}")
    desc = (data.get("description") or "").strip()
    return desc


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

    core = {"LICENSE", "README.md", "RULE.md"}
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
    # Allow scripts/ directory
    extra = {f for f in extra if not f.startswith("scripts/")}
    if extra:
        errors.append(f"Extra tracked files not allowed: {', '.join(sorted(extra))}.")
    return errors


def check_repo_name_length(repo_name: str) -> List[str]:
    if len(repo_name) > 20:
        return [f"Repo name must be 20 characters or less (found {len(repo_name)})."]
    return []


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


def check_rules_length(path: str) -> List[str]:
    errors: List[str] = []
    rules_path = os.path.join(path, "RULE.md")
    if not os.path.isfile(rules_path):
        return ["RULE.md file missing."]
    with open(rules_path, "r", encoding="utf-8") as f:
        text = f.read()
    if len(text) > MAX_RULES_CHARS:
        errors.append(
            f"RULE.md must be under {MAX_RULES_CHARS} characters (found {len(text)})."
        )
    return errors


def parse_front_matter(text: str) -> Tuple[Optional[str], Optional[str], List[str]]:
    errors: List[str] = []
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        errors.append("RULE.md must start with a YAML front matter block ('---' on first line).")
        return None, None, errors
    end_index = None
    for i in range(1, len(lines)):
        if lines[i].strip() == "---":
            end_index = i
            break
    if end_index is None:
        errors.append("YAML front matter block is not closed with a second '---'.")
        return None, None, errors

    description = None
    always_apply = None
    for line in lines[1:end_index]:
        if ":" not in line:
            continue
        key, value = line.split(":", 1)
        key = key.strip()
        value = value.strip()
        if key == "description":
            if (value.startswith('"') and value.endswith('"')) or (
                value.startswith("'") and value.endswith("'")
            ):
                value = value[1:-1]
            description = value.strip()
        elif key == "alwaysApply":
            always_apply = value.strip()

    if not description:
        errors.append("Front matter must include non-empty description.")
    if always_apply is None:
        errors.append("Front matter must include alwaysApply: true.")
    elif always_apply.lower() != "true":
        errors.append("alwaysApply must be true.")

    return description, always_apply, errors


def check_rule_front_matter(path: str, repo_name: str) -> List[str]:
    errors: List[str] = []
    rules_path = os.path.join(path, "RULE.md")
    if not os.path.isfile(rules_path):
        return ["RULE.md file missing."]
    with open(rules_path, "r", encoding="utf-8") as f:
        text = f.read()
    description, _always_apply, fm_errors = parse_front_matter(text)
    errors.extend(fm_errors)
    if description is None:
        return errors

    token = os.getenv("GITHUB_TOKEN") or os.getenv("GH_TOKEN")
    try:
        gh_desc = fetch_github_description(repo_name)
    except Exception as e:
        if token:
            errors.append(f"Failed to fetch GitHub repo description: {e}")
        return errors
    if description != gh_desc:
        errors.append(
            f"Front matter description must match GitHub repo description. "
            f"Front matter: '{description}' vs GitHub: '{gh_desc}'."
        )
    return errors


def get_main_commits(path: str) -> List[str]:
    ref = "main"
    try:
        run(["git", "rev-parse", "--verify", "main"], cwd=path)
    except RuntimeError:
        run(["git", "rev-parse", "--verify", "origin/main"], cwd=path)
        ref = "origin/main"

    out = run(["git", "rev-list", ref], cwd=path)
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
    errors.extend(check_repo_name_length(repo_name))
    errors.extend(check_tracked_files(path))
    errors.extend(check_license(path))
    errors.extend(check_readme_install(path, repo_name))
    errors.extend(check_rules_length(path))
    errors.extend(check_rule_front_matter(path, repo_name))
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
