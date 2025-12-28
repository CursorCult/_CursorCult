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
RULESETS_REPO = "_rulesets"
RULESETS_RAW_URL_TEMPLATE = (
    f"https://raw.githubusercontent.com/{ORG}/{RULESETS_REPO}/main/rulesets" + "/{name}.txt"
)


@dataclass
class RepoInfo:
    name: str
    description: str
    tags: List[str]
    default_branch: str = "main"

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
                return {{}}
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
        if r.get("archived"):
            continue
        if r.get("fork"):
            continue
        name = r.get("name", "")
        if not name or name.startswith(".") or name.startswith("_"):
            continue
        if name.endswith(".github.io"):
            continue
        default_branch = r.get("default_branch") or "main"
        description = (r.get("description") or "").strip() or "no description"
        tags_raw = http_json(f"{API_BASE}/repos/{ORG}/{name}/tags?per_page=100")
        tags = [t.get("name", "") for t in tags_raw if t.get("name")]
        repo_info = RepoInfo(
            name=name,
            description=description,
            tags=tags,
            default_branch=default_branch,
        )
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
        indent = " " * 25
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
            f"Command failed: {' '.join(cmd)}\n"
            f"{proc.stderr.strip() or proc.stdout.strip()}"
        )

def get_current_tag(cwd: str) -> str:
    proc = subprocess.run(
        ["git", "describe", "--tags", "--exact-match", "HEAD"],
        cwd=cwd,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    if proc.returncode == 0:
        return proc.stdout.strip()
    return ""

def get_head_sha(cwd: str) -> str:
    proc = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=cwd,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    if proc.returncode == 0:
        return proc.stdout.strip()
    return ""

def canonicalize_rule_path(path: str) -> str:
    target_path = os.path.abspath(path)
    if os.path.isdir(target_path):
        return target_path
    if os.path.sep in path:
        raise RuntimeError(f"Path not found: {path}")
    rules_dir = ensure_rules_dir()
    target_path = os.path.join(rules_dir, path)
    if not os.path.isdir(target_path):
        raise RuntimeError(f"Path not found: {path}")
    return target_path

def is_cursorcult_repo(cwd: str) -> bool:
    proc = subprocess.run(
        ["git", "config", "--get", "remote.origin.url"],
        cwd=cwd,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    if proc.returncode != 0:
        return False
    url = proc.stdout.strip()
    if not url:
        return False
    return (
        f"github.com/{ORG}/" in url
        or f"github.com:{ORG}/" in url
        or f"git@github.com:{ORG}/" in url
        or f"ssh://git@github.com/{ORG}/" in url
    )

def get_latest_remote_tag(name: str) -> Optional[str]:
    """Fetch latest vN tag for a repo from GitHub API."""
    try:
        tags_raw = http_json(f"{API_BASE}/repos/{ORG}/{name}/tags?per_page=100")
        tags = [t.get("name", "") for t in tags_raw if t.get("name")]
        versions = []
        for t in tags:
            m = TAG_RE.match(t)
            if m:
                versions.append((int(m.group(1)), t))
        if not versions:
            return None
        return max(versions, key=lambda x: x[0])[1]
    except Exception:
        return None

def link_rule(spec: str, subtree: bool = False, *, skip_existing: bool = False) -> None:
    name, requested_tag = parse_name_and_tag(spec)
    if not name:
        raise ValueError("Rule name is required.")

    tag = requested_tag
    if not tag:
        tag = get_latest_remote_tag(name)
        if not tag:
             raise RuntimeError(f"Rule '{name}' has no vN tags to link.")

    rules_dir = ensure_rules_dir()
    target_path = os.path.join(rules_dir, name)
    
    if os.path.exists(target_path):
        if skip_existing:
            print(f"Skipping {name}: already exists.")
            return
        
        if os.path.exists(os.path.join(target_path, ".git")):
            print(f"Updating {name} to {tag}...")
            try:
                run(["git", "fetch", "--tags"], cwd=target_path)
                run(["git", "checkout", tag], cwd=target_path)
            except RuntimeError as e:
                print(f"Failed to update {name}: {e}")
            return
        else:
            print(f"Skipping update for {name} (not a submodule).")
            return

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
        return

    prefix = os.path.relpath(target_path, os.getcwd())
    if os.sep != "/":
        prefix = prefix.replace(os.sep, "/")
    run(["git", "submodule", "add", repo_url, prefix])
    run(["git", "-C", prefix, "checkout", tag])

    print(f"Linked {name} at {tag} into {target_path}.")

def _fetch_text(url: str) -> str:
    try:
        with urllib.request.urlopen(url, timeout=20) as resp:
            return resp.read().decode("utf-8")
    except urllib.error.HTTPError as e:
        body = ""
        try:
            body = e.read().decode("utf-8", errors="ignore")
        except Exception:
            body = ""
        raise RuntimeError(f"Failed to fetch {url}: HTTP {e.code} {body or e.reason}") from e
    except urllib.error.URLError as e:
        raise RuntimeError(f"Network error fetching {url}: {e}") from e

def parse_ruleset_names(text: str) -> List[str]:
    names: List[str] = []
    seen = set()
    for raw_line in text.splitlines():
        line = raw_line.split("#", 1)[0].strip()
        if not line:
            continue
        for token in line.split():
            name = token.strip()
            if not name or name.startswith(".") or name.startswith("_"):
                continue
            if name in seen:
                continue
            seen.add(name)
            names.append(name)
    return names

def apply_rulesets(subtree: bool = False) -> None:
    rules_dir = ensure_rules_dir()
    sets_dir = os.path.join(rules_dir, "_ccrulesets")
    if not os.path.isdir(sets_dir):
        return

    requirements: Dict[str, List[Tuple[str, Optional[str]]]] = {}

    for filename in os.listdir(sets_dir):
        if not filename.endswith(".txt"):
            continue
        path = os.path.join(sets_dir, filename)
        content = open(path, "r", encoding="utf-8").read()
        
        specs = parse_ruleset_names(content)
        for spec in specs:
            name, tag = parse_name_and_tag(spec)
            requirements.setdefault(name, []).append((filename, tag))

    for rule, reqs in requirements.items():
        resolved_versions = []
        has_wildcard = False
        
        for src, tag in reqs:
            if tag:
                m = TAG_RE.match(tag)
                if m:
                    resolved_versions.append((int(m.group(1)), tag))
            else:
                has_wildcard = True
        
        if has_wildcard:
            latest = get_latest_remote_tag(rule)
            if latest:
                m = TAG_RE.match(latest)
                if m:
                    resolved_versions.append((int(m.group(1)), latest))
        
        if not resolved_versions:
            print(f"Warning: No valid versions found for {rule} (requested by rulesets). Skipping.")
            continue
            
        max_ver, max_tag = max(resolved_versions, key=lambda x: x[0])
        
        print(f"Enforcing {rule}:{max_tag} (from rulesets)...")
        link_rule(f"{rule}:{max_tag}", subtree=subtree, skip_existing=False)

def link_ruleset(ruleset_name: str, *, subtree: bool = False) -> None:
    if not ruleset_name or "/" in ruleset_name or ".." in ruleset_name:
        raise ValueError("Invalid ruleset name.")
    url = RULESETS_RAW_URL_TEMPLATE.format(name=ruleset_name)
    text = _fetch_text(url)
    
    if not text.strip():
        raise RuntimeError(f"Ruleset '{ruleset_name}' is empty or not found.")

    rules_dir = ensure_rules_dir()
    sets_dir = os.path.join(rules_dir, "_ccrulesets")
    os.makedirs(sets_dir, exist_ok=True)
    
    local_path = os.path.join(sets_dir, f"{ruleset_name}.txt")
    with open(local_path, "w", encoding="utf-8") as f:
        f.write(text)
        
    print(f"Downloaded ruleset definition to {local_path}")
    apply_rulesets(subtree=subtree)

def link_ruleset_file(path: str, *, subtree: bool = False) -> None:
    if not path:
        raise ValueError("Ruleset file path is required.")
    if not os.path.isfile(path):
        raise RuntimeError(f"Ruleset file not found: {path}")
    
    text = open(path, "r", encoding="utf-8").read()
    name = os.path.basename(path).replace(".txt", "")
    
    rules_dir = ensure_rules_dir()
    sets_dir = os.path.join(rules_dir, "_ccrulesets")
    os.makedirs(sets_dir, exist_ok=True)
    
    local_path = os.path.join(sets_dir, f"{name}.txt")
    with open(local_path, "w", encoding="utf-8") as f:
        f.write(text)
        
    print(f"Copied local ruleset to {local_path}")
    apply_rulesets(subtree=subtree)

def copy_rule(spec: str) -> None:
    name, requested_tag = parse_name_and_tag(spec)
    if not name:
        raise ValueError("Rule name is required.")

    tag = requested_tag
    if not tag:
        tag = get_latest_remote_tag(name)
        if not tag:
            raise RuntimeError(f"Rule '{name}' has no vN tags.")

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
    if not name or not re.match(r"^[A-Za-z0-9._-]+", name):
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

    rules_md = f"""
---
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

def register_rule(url: str) -> None:
    if not url.startswith("http") and not url.startswith("git@"):
        raise ValueError("Invalid URL format.")
        
    parts = url.rstrip("/").replace(".git", "").split("/")
    if len(parts) < 2:
        raise ValueError("Cannot parse repo owner/name from URL.")
    
    repo_name = parts[-1]
    owner = parts[-2].split(":")[-1]
    
    print(f"Validating {owner}/{repo_name}...")
    
    with tempfile.TemporaryDirectory(prefix="cursorcult-reg-") as tmp:
        clone_dir = os.path.join(tmp, repo_name)
        try:
            run(["git", "clone", "--depth", "1", url, clone_dir])
        except Exception as e:
            raise RuntimeError(f"Failed to clone {url}: {e}")
            
        if not os.path.isfile(os.path.join(clone_dir, "RULE.md")):
            raise RuntimeError("Repo missing RULE.md. Not a valid CursorCult rule pack.")
            
        license_path = os.path.join(clone_dir, "LICENSE")
        is_unlicense = False
        if os.path.isfile(license_path):
            content = open(license_path, "r", encoding="utf-8").read()
            if "public domain" in content.lower() or "unlicense" in content.lower():
                is_unlicense = True
        
        description = "No description provided."
        rule_content = open(os.path.join(clone_dir, "RULE.md"), "r", encoding="utf-8").read()
        m = re.search(r'^description:\s*["\\]?(.*?)["\\]?$', rule_content, re.MULTILINE)
        if m:
            description = m.group(1)
            
    yaml_content = f"""name: {repo_name}
description: "{description}"
source_url: "{url}"
maintainer: "{owner}"
"""
    
    filename = f"{repo_name}.yml"
    with open(filename, "w", encoding="utf-8") as f:
        f.write(yaml_content)
        
    print(f"\nSUCCESS: Validation passed.")
    if is_unlicense:
        print("License: Unlicense (Eligible for showcase!)")
    else:
        print("License: Not detected as Unlicense (Standard listing)")
        
    print(f"\nSubmission file generated: {filename}")
    print(f"Next step: Open a PR to https://github.com/CursorCult/_intake adding this file to 'submissions/'.")

def update_rules(latest: bool = False, path: Optional[str] = None) -> None:
    apply_rulesets()

    if path:
        target_path = canonicalize_rule_path(path)
    else:
        target_path = ensure_rules_dir()

    if os.path.isdir(os.path.join(target_path, ".git")):
        rules = [(os.path.basename(target_path), target_path)]
        print(f"Checking rule in {target_path}...")
    else:
        print(f"Checking individual rules in {target_path}...")
        rules = []
        for name in sorted(os.listdir(target_path)):
            rule_path = os.path.join(target_path, name)
            if not os.path.isdir(rule_path) or name == "_ccrulesets":
                continue
            rules.append((name, rule_path))

    for name, rule_path in rules:
        if not os.path.exists(os.path.join(rule_path, ".git")):
            continue
        if not is_cursorcult_repo(rule_path):
            print(f"Skipping {name}: not a CursorCult repo.")
            continue

        current_tag = get_current_tag(rule_path)
        try:
            run(["git", "fetch", "--tags"], cwd=rule_path)
        except RuntimeError as e:
            if "would clobber existing tag" in str(e) and current_tag == "v0":
                try:
                    run(["git", "fetch", "--tags", "--force"], cwd=rule_path)
                except RuntimeError:
                    print(f"Skipping {name}: failed to fetch tags.")
                    continue
            else:
                print(f"Skipping {name}: failed to fetch tags.")
                continue

        current_tag = get_current_tag(rule_path)

        proc = subprocess.run(
            ["git", "tag", "-l", "v*"],
            cwd=rule_path,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        tags = [t for t in proc.stdout.splitlines() if TAG_RE.match(t)]
        
        if not tags:
            print(f"{name}: no versions found.")
            continue
            
        parsed_tags = []
        for t in tags:
            m = TAG_RE.match(t)
            if m:
                parsed_tags.append((int(m.group(1)), t))
        
        if not parsed_tags:
            continue
            
        max_ver, max_tag = max(parsed_tags, key=lambda x: x[0])
        
        target_tag = current_tag
        action = "none"
        message = ""
        up_to_date_message = ""

        if not current_tag:
            print(f"{name}: not on a specific version tag. Skipping.")
            continue

        match = TAG_RE.match(current_tag)
        if not match:
            print(f"{name}: current tag '{current_tag}' unknown format. Skipping.")
            continue
            
        current_ver = int(match.group(1))

        if current_ver == 0:
            if max_ver > 0:
                target_tag = max_tag
                action = "update"
                message = f"v0 (volatile) -> {target_tag} (stable)"
                up_to_date_message = f"up-to-date ({target_tag})"
            else:
                target_tag = "v0"
                action = "update"
                message = "refreshing v0"
                up_to_date_message = "up-to-date (v0)"
        else:
            if max_ver > current_ver:
                if latest:
                    target_tag = max_tag
                    action = "update"
                    message = f"{current_tag} -> {max_tag} (forced)"
                    up_to_date_message = f"up-to-date ({max_tag})"
                else:
                    action = "notify"
                    print(f"{name}: update available {current_tag} -> {max_tag}. Use --latest to apply.")
            else:
                up_to_date_message = f"up-to-date ({current_tag})"

        if action == "update":
            before_sha = get_head_sha(rule_path)
            run(["git", "checkout", target_tag], cwd=rule_path)
            after_sha = get_head_sha(rule_path)
            if before_sha and after_sha and before_sha == after_sha:
                if up_to_date_message:
                    print(f"{name}: {up_to_date_message}")
                else:
                    print(f"{name}: up-to-date")
            else:
                print(f"{name}: updated ({message})")
        elif action == "none" and up_to_date_message:
            print(f"{name}: {up_to_date_message}")
