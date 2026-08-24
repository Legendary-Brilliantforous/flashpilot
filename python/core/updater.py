"""Two-tier self-updater for FlashPilot.

Tier 1 (light patch): only python/** changed on GitHub main since the
    installed snapshot -> download the repo tarball (~200 KB), stage the
    python tree, and swap it in with a single pkexec copy. No full .deb
    download, no dependency changes, user data untouched.
Tier 2 (full): Rust bridge / packaging / anything outside python/**
    changed -> fall back to downloading the latest release .deb.

The installed snapshot is tracked by a UPDATE_SHA marker written next to
the application (root-owned when deb-installed) plus a user-cache copy so
non-root runs can still compare.
"""

import hashlib
import json
import os
import shutil
import subprocess
import tempfile

import requests

REPO = "Legendary-Brilliantforous/flashpilot"
API = f"https://api.github.com/repos/{REPO}"
CACHE_DIR = os.path.expanduser("~/.cache/flashpilot")
SHA_MARKER = "UPDATE_SHA"


class UpdateError(RuntimeError):
    pass


def _app_root():
    """Directory containing the installed python package (repo root when
    running from a checkout)."""
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def is_dev_checkout():
    return os.path.isdir(os.path.join(_app_root(), ".git"))


def get_local_sha():
    """SHA of the installed snapshot; None when unknown (dev checkout or
    pre-marker install)."""
    candidates = [
        os.path.join(CACHE_DIR, SHA_MARKER),
        os.path.join(_app_root(), SHA_MARKER),
        os.path.join(_app_root(), "..", SHA_MARKER),
    ]
    for path in candidates:
        try:
            with open(path) as fh:
                sha = fh.read().strip()
                if sha:
                    return sha
        except OSError:
            continue
    return None


def _write_user_sha(sha):
    os.makedirs(CACHE_DIR, exist_ok=True)
    with open(os.path.join(CACHE_DIR, SHA_MARKER), "w") as fh:
        fh.write(sha)


def get_remote_sha(timeout=15):
    r = requests.get(f"{API}/commits/main", timeout=timeout,
                     headers={"Accept": "application/vnd.github+json"})
    r.raise_for_status()
    return r.json()["sha"]


def _changed_files(old_sha, new_sha, timeout=20):
    """Files changed between two SHAs (empty list when old is unknown or
    comparison impossible -> caller must assume 'everything')."""
    if not old_sha:
        return None
    r = requests.get(
        f"{API}/compare/{old_sha}...{new_sha}", timeout=timeout,
        headers={"Accept": "application/vnd.github+json"},
    )
    if r.status_code != 200:
        return None
    return [f["filename"] for f in r.json().get("files", [])]


def check(timeout=15):
    """Compare installed snapshot vs GitHub main.

    Returns {'status': 'up-to-date'|'python'|'full'|'unknown',
             'remote_sha': str, 'local_sha': str|None}
    """
    local = get_local_sha()
    remote = get_remote_sha(timeout=timeout)
    if is_dev_checkout():
        status = "dev"
    elif local == remote:
        status = "up-to-date"
    else:
        files = _changed_files(local, remote)
        if files is None:
            status = "unknown"
        elif files and all(
            f.startswith("python/") or f == SHA_MARKER or
            f.startswith("docs/") or f.endswith(".md")
            for f in files
        ):
            status = "python"
        else:
            status = "full"
    return {"status": status, "remote_sha": remote, "local_sha": local}


def stage_python_patch(new_sha=None):
    """Download the repo tarball for `new_sha` (default: main) and stage the
    python/ tree. Returns (staging_dir, sha_used)."""
    ref = new_sha or "main"
    url = f"https://github.com/{REPO}/archive/{ref}.tar.gz"
    tmpdir = tempfile.mkdtemp(prefix="fp_update_")
    tgz = os.path.join(tmpdir, "main.tar.gz")
    with requests.get(url, stream=True, timeout=60) as r:
        r.raise_for_status()
        with open(tgz, "wb") as fh:
            for chunk in r.iter_content(65536):
                fh.write(chunk)
    # integrity: sha256 recorded for reproducibility
    digest = hashlib.sha256(open(tgz, "rb").read()).hexdigest()

    extract_dir = os.path.join(tmpdir, "x")
    os.makedirs(extract_dir)
    subprocess.run(["tar", "-xzf", tgz, "-C", extract_dir], check=True)
    roots = [d for d in os.listdir(extract_dir)
             if os.path.isdir(os.path.join(extract_dir, d))]
    if len(roots) != 1:
        raise UpdateError("unexpected tarball layout")
    src_root = os.path.join(extract_dir, roots[0])
    py_src = os.path.join(src_root, "python")
    if not os.path.isdir(py_src):
        raise UpdateError("tarball has no python/ tree")

    staging = os.path.join(tmpdir, "staged")
    shutil.copytree(py_src, staging)
    with open(os.path.join(tmpdir, "tarball.sha256"), "w") as fh:
        fh.write(digest)
    return tmpdir, (new_sha or "main")


def apply_python_patch(staging_dir, sha):
    """Swap the staged python tree over the installed one.

    Root-owned installs need privilege escalation: pkexec prompts for the
    password natively (same UX as GNOME Software updates). Dev checkouts
    are skipped entirely."""
    if is_dev_checkout():
        raise UpdateError("running from a dev checkout - nothing applied")
    dst = _app_root()
    cmd = (
        f"cp -a {staging_dir}/staged/. {dst}/python/ && "
        f"chown -R root:root {dst}/python && "
        f"chmod -R a+rX {dst}/python"
    )
    r = subprocess.run(["pkexec", "bash", "-lc", cmd],
                       capture_output=True, text=True, timeout=120)
    if r.returncode != 0:
        raise UpdateError(f"pkexec failed: {r.stderr.strip()[:300]}")
    _write_user_sha(sha)
    return dst
