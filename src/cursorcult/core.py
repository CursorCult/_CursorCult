import json
import os
import re
import subprocess
import tempfile
import shutil
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

from .constants import CCVERIFY_WORKFLOW_YML, TAG_RE, UNLICENSE_TEXT


ORG = "CursorCult"
API_BASE = "https://api.github.com"
REPO_URL_TEMPLATE = f"https://github.com/{ORG}" + "/{name}.git"
README_URL_TEMPLATE = f"https://github.com/{ORG}" + "/{name}/blob/main/README.md"


@dataclass
class RepoInfo:
    name: str
    description: str
    tags: List[str]

    @property
    def latest_tag(self) -> Optional[str]:
        versions = []
        for t in self.tags:
            m = TAG_RE.match(t)
            if m:
                versions.append((int(m.group(1)), t))
        if not versions:
            return None
        return max(versions, key=lambda x: x[0])[1]


def http_json(url: str) -> object:
    token = os.getenv("GITHUB_TOKEN") or os.getenv("GH_TOKEN")

    def fetch(with_token: bool) -> object:
        headers = {"Accept": "application/vnd.github+json", "User-Agent": "cursorcult"}
        if with_token and token:
            headers["Authorization"] = f"Bearer {token}"
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req, timeout=15) as resp:
            return json.loads(resp.read().decode("utf-8"))

    try:
        return fetch(with_token=True)
    except urllib.error.HTTPError as e:
        # If a user has a mis-scoped/SSO-blocked token in env, GitHub can 403 even for public data.
        # Retry unauthenticated to allow public access in that case.
        if e.code == 403 and token:
            try:
                return fetch(with_token=False)
            except Exception:
                pass
        body = ""
        try:
            body = e.read().decode("utf-8", errors="ignore")
        except Exception:
            body = ""
        hint = ""
        if "rate limit" in body.lower():
            hint = " (rate limit exceeded; set GH_TOKEN from `gh auth token` or wait)"
        raise RuntimeError(f"GitHub API error {e.code} for {url}{hint}: {body or e.reason}") from e
    except urllib.error.URLError as e:
        raise RuntimeError(f"Network error fetching {url}: {e}") from e


def github_request(method: str, url: str, data: Optional[Dict[str, Any]] = None) -> object:
    headers = {"Accept": "application/vnd.github+json", "User-Agent": "cursorcult"}
    token = os.getenv("GITHUB_TOKEN") or os.getenv("GH_TOKEN")
    if not token:
        raise RuntimeError("Missing GITHUB_TOKEN or GH_TOKEN for GitHub API request.")
    headers["Authorization"] = f"Bearer {token}"
    body = None
    if data is not None:
        body = json.dumps(data).encode("utf-8")
        headers["Content-Type"] = "application/json"
    req = urllib.request.Request(url, data=body, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=20) as resp:
            raw = resp.read()
            if not raw:
                return {}
            return json.loads(raw.decode("utf-8"))
    except urllib.error.HTTPError as e:
        msg = e.read().decode("utf-8", errors="ignore")
        raise RuntimeError(f"GitHub API error {e.code} for {url}: {msg}") from e
    except urllib.error.URLError as e:
        raise RuntimeError(f"Network error fetching {url}: {e}") from e


def list_repos(include_untagged: bool = False) -> List[RepoInfo]:
    repos_raw = http_json(f"{API_BASE}/orgs/{ORG}/repos?per_page=200&type=public")
    repos: List[RepoInfo] = []
    for r in repos_raw:
        name = r.get("name", "")
        if not name or name.startswith("."):
            continue
        if name == "_CursorCult":
            continue
        description = (r.get("description") or "").strip() or "no description"
        tags_raw = http_json(f"{API_BASE}/repos/{ORG}/{name}/tags?per_page=100")
        tags = [t.get("name", "") for t in tags_raw if t.get("name")]
        repo_info = RepoInfo(name=name, description=description, tags=tags)
        if not include_untagged and repo_info.latest_tag is None:
            continue
        repos.append(repo_info)
    repos.sort(key=lambda x: x.name.lower())
    return repos


def print_repos(repos: List[RepoInfo]) -> None:
    for repo in repos:
        latest = repo.latest_tag or "v?"
        version_field = latest.rjust(3) if len(latest) < 3 else latest
        readme_url = README_URL_TEMPLATE.format(name=repo.name)
        line1 = f"{repo.name:<20} {version_field} {repo.description}"
        indent = " " * 25  # 20 (name) + 1 + 3 (version) + 1
        line2 = f"{indent}{readme_url}"
        print(line1)
        print(line2)


def parse_name_and_tag(spec: str) -> Tuple[str, Optional[str]]:
    if ":" in spec:
        name, tag = spec.split(":", 1)
        name = name.strip()
        tag = tag.strip()
        if not TAG_RE.match(tag):
            raise ValueError(f"Invalid tag '{tag}'. Use v0, v1, v2, ...")
        return name, tag
    return spec.strip(), None


def ensure_rules_dir() -> str:
    rules_dir = os.path.join(os.getcwd(), ".cursor", "rules")
    if not os.path.isdir(rules_dir):
        raise RuntimeError(
            "No .cursor/rules directory found at project root. Create it first."
        )
    return rules_dir


def run(cmd: List[str], cwd: Optional[str] = None) -> None:
    proc = subprocess.run(
        cmd, cwd=cwd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True
    )
    if proc.returncode != 0:
        raise RuntimeError(
            f"Command failed: {' '.join(cmd)}\n{proc.stderr.strip() or proc.stdout.strip()}"
        )


def link_rule(spec: str, subtree: bool = False) -> None:
    name, requested_tag = parse_name_and_tag(spec)
    if not name:
        raise ValueError("Rule name is required.")

    repos = {r.name: r for r in list_repos(include_untagged=True)}
    if name not in repos:
        available = ", ".join(sorted(repos.keys()))
        raise RuntimeError(f"Unknown rule '{name}'. Available: {available}")

    repo = repos[name]
    tag = requested_tag or repo.latest_tag
    if tag is None:
        raise RuntimeError(f"Rule '{name}' has no vN tags to link.")

    rules_dir = ensure_rules_dir()
    target_path = os.path.join(rules_dir, name)
    if os.path.exists(target_path):
        raise RuntimeError(
            f"Target path already exists: {target_path}. Remove it or choose another name."
        )

    repo_url = REPO_URL_TEMPLATE.format(name=name)
    if subtree:
        prefix = os.path.relpath(target_path, os.getcwd())
        if os.sep != "/":
            prefix = prefix.replace(os.sep, "/")
        try:
            run(["git", "subtree", "add", "--prefix", prefix, repo_url, tag, "--squash"])
        except RuntimeError as e:
            raise RuntimeError(
                f"git subtree add failed. Ensure git-subtree is installed. Original error:\n{e}"
            ) from e
        print(f"Vendored {name} at {tag} into {target_path} using git subtree.")
        print("Next: commit the new rule directory in your repo.")
        return

    prefix = os.path.relpath(target_path, os.getcwd())
    if os.sep != "/":
        prefix = prefix.replace(os.sep, "/")
    run(["git", "submodule", "add", repo_url, prefix])
    run(["git", "-C", prefix, "checkout", tag])

    print(f"Linked {name} at {tag} into {target_path}.")
    print("Next: commit .gitmodules and the submodule directory in your repo.")


def copy_rule(spec: str) -> None:
    name, requested_tag = parse_name_and_tag(spec)
    if not name:
        raise ValueError("Rule name is required.")

    repos = {r.name: r for r in list_repos(include_untagged=True)}
    if name not in repos:
        available = ", ".join(sorted(repos.keys()))
        raise RuntimeError(f"Unknown rule '{name}'. Available: {available}")

    repo = repos[name]
    tag = requested_tag or repo.latest_tag
    if tag is None:
        raise RuntimeError(f"Rule '{name}' has no vN tags to copy.")

    rules_dir = ensure_rules_dir()
    target_path = os.path.join(rules_dir, name)
    if os.path.exists(target_path):
        raise RuntimeError(
            f"Target path already exists: {target_path}. Remove it or choose another name."
        )

    repo_url = REPO_URL_TEMPLATE.format(name=name)

    with tempfile.TemporaryDirectory(prefix="cursorcult-copy-") as tmp:
        clone_dir = os.path.join(tmp, name)
        run(["git", "clone", "--depth", "1", "--branch", tag, repo_url, clone_dir])

        os.makedirs(target_path, exist_ok=False)
        for filename in ("LICENSE", "README.md", "RULE.md"):
            src = os.path.join(clone_dir, filename)
            if not os.path.isfile(src):
                raise RuntimeError(f"Source repo missing {filename} at tag {tag}.")
            shutil.copy2(src, os.path.join(target_path, filename))

    print(f"Copied {name} at {tag} into {target_path}.")
    print("Next: commit the copied rule directory in your repo.")


def new_rule_repo(name: str, description: Optional[str] = None) -> None:
    if not name or not re.match(r"^[A-Za-z0-9._-]+$", name):
        raise ValueError(
            "Invalid repo name. Use only letters, numbers, '.', '_', and '-'."
        )
    if os.path.exists(name):
        raise RuntimeError(f"Path already exists: {name}")

    if not description:
        raise ValueError("Description is required for new rule repos.")
    repo_description = description
    create_payload = {
        "name": name,
        "description": repo_description,
        "private": False,
        "has_issues": False,
        "has_projects": False,
        "has_wiki": False,
        "has_discussions": False,
    }
    github_request("POST", f"{API_BASE}/orgs/{ORG}/repos", create_payload)

    repo_url = REPO_URL_TEMPLATE.format(name=name)
    run(["git", "clone", repo_url, name])

    workflow_path = os.path.join(name, ".github", "workflows")
    os.makedirs(workflow_path, exist_ok=True)
    with open(os.path.join(workflow_path, "ccverify.yml"), "w", encoding="utf-8") as f:
        f.write(CCVERIFY_WORKFLOW_YML)

    with open(os.path.join(name, "LICENSE"), "w", encoding="utf-8") as f:
        f.write(UNLICENSE_TEXT)

    readme = f"""# {name}

TODO: one‑line description.

**Install**

```sh
pipx install cursorcult
cursorcult link {name}
```

Rule file format reference: https://cursor.com/docs/context/rules#rulemd-file-format

**When to use**

- TODO

**What it enforces**

- TODO

**Credits**

- Developed by Will Wieselquist. Anyone can use it.
"""
    with open(os.path.join(name, "README.md"), "w", encoding="utf-8") as f:
        f.write(readme)

    rules_md = f"""---
description: "{repo_description}"
alwaysApply: true
---

# {name} Rule

TODO: Describe the rule precisely.
"""
    with open(os.path.join(name, "RULE.md"), "w", encoding="utf-8") as f:
        f.write(rules_md)

    run(["git", "-C", name, "checkout", "-B", "main"])
    run(
        [
            "git",
            "-C",
            name,
            "add",
            "LICENSE",
            "README.md",
            "RULE.md",
            ".github/workflows/ccverify.yml",
        ]
    )
    run(
        [
            "git",
            "-C",
            name,
            "commit",
            "-m",
            f"Initialize {name} rule pack",
        ]
    )
    run(["git", "-C", name, "push", "origin", "main"])

    print(f"Created {ORG}/{name} and initialized template.")
    print(
        "Convention: develop on main until ready for v0, then squash commits and tag v0."
    )
