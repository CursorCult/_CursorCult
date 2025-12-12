import json
import os
import re
import subprocess
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import List, Optional, Tuple


ORG = "CursorCult"
API_BASE = "https://api.github.com"
REPO_URL_TEMPLATE = f"https://github.com/{ORG}" + "/{name}.git"
README_URL_TEMPLATE = f"https://github.com/{ORG}" + "/{name}/blob/main/README.md"

TAG_RE = re.compile(r"^v(\d+)$")


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
    headers = {"Accept": "application/vnd.github+json", "User-Agent": "cursorcult"}
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


def list_repos() -> List[RepoInfo]:
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
        repos.append(RepoInfo(name=name, description=description, tags=tags))
    repos.sort(key=lambda x: x.name.lower())
    return repos


def print_repos(repos: List[RepoInfo]) -> None:
    for repo in repos:
        latest = repo.latest_tag or "no tags"
        readme_url = README_URL_TEMPLATE.format(name=repo.name)
        print(f"{repo.name} — {repo.description} — latest {latest} — {readme_url}")


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


def link_rule(spec: str) -> None:
    name, requested_tag = parse_name_and_tag(spec)
    if not name:
        raise ValueError("Rule name is required.")

    repos = {r.name: r for r in list_repos()}
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
    run(["git", "submodule", "add", repo_url, target_path])
    run(["git", "-C", target_path, "checkout", tag])

    print(f"Linked {name} at {tag} into {target_path}.")
    print("Next: commit .gitmodules and the submodule directory in your repo.")

