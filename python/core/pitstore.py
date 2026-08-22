"""PIT cache store - FlashPilot's smart PIT memory.

Auto-fetched device PITs are stored under ~/.cache/flashpilot/pit/ keyed by
model + content hash, so subsequent sessions skip the USB dump when the same
model is connected (and dry-run validation works offline).

Index layout (~/.cache/flashpilot/pit/index.json):
    { "entries": [ {model, sha256, file, size, ts, source}, ... ] }
"""

import hashlib
import json
import os
import time

CACHE_DIR = os.path.join(
    os.path.expanduser("~"), ".cache", "flashpilot", "pit"
)


def _ensure_dir():
    os.makedirs(CACHE_DIR, exist_ok=True)


def _index_path():
    return os.path.join(CACHE_DIR, "index.json")


def _load_index():
    try:
        with open(_index_path()) as fh:
            return json.load(fh)
    except (OSError, ValueError):
        return {"entries": []}


def _save_index(idx):
    _ensure_dir()
    with open(_index_path(), "w") as fh:
        json.dump(idx, fh, indent=1)


def sha256_hex(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _slug(model: str) -> str:
    keep = [c if (c.isalnum() or c in "-_") else "_" for c in (model or "unknown")]
    return "".join(keep)[:40] or "unknown"


def store(model: str, raw: bytes, source: str = "device"):
    """Persist a fetched PIT; returns the metadata dict. Storing an identical
    blob twice is a no-op refresh (same key)."""
    digest = sha256_hex(raw)
    fname = f"{_slug(model)}-{digest[:16]}.pit"
    path = os.path.join(CACHE_DIR, fname)
    _ensure_dir()
    if not os.path.exists(path):
        tmp = path + ".tmp"
        with open(tmp, "wb") as fh:
            fh.write(raw)
        os.replace(tmp, path)

    idx = _load_index()
    entries = idx.setdefault("entries", [])
    for ent in entries:
        if ent.get("sha256") == digest and ent.get("model") == model:
            ent["ts"] = time.time()
            ent["source"] = source
            break
    else:
        entries.append({
            "model": model,
            "sha256": digest,
            "file": fname,
            "size": len(raw),
            "ts": time.time(),
            "source": source,
        })
    # keep index bounded: newest 32 entries
    idx["entries"] = sorted(entries, key=lambda e: -e["ts"])[:32]
    _save_index(idx)
    return {"sha256": digest, "file": path, "model": model}


def load_latest(model: str):
    """Return the newest cached PIT bytes for a model, or None."""
    idx = _load_index()
    best = None
    for ent in idx.get("entries", []):
        if ent.get("model") == model:
            if best is None or ent["ts"] > best["ts"]:
                best = ent
    if best is None:
        return None
    path = os.path.join(CACHE_DIR, best["file"])
    try:
        with open(path, "rb") as fh:
            return fh.read()
    except OSError:
        return None


def lookup(model: str, raw: bytes):
    """True if this exact blob is already cached for the model."""
    digest = sha256_hex(raw)
    idx = _load_index()
    return any(
        e.get("model") == model and e.get("sha256") == digest
        for e in idx.get("entries", [])
    )


def stats():
    """Small summary for GUI/About display."""
    idx = _load_index()
    entries = idx.get("entries", [])
    models = sorted({e.get("model", "?") for e in entries})
    total = sum(e.get("size", 0) for e in entries)
    return {"count": len(entries), "models": models,
            "dir": CACHE_DIR, "total_bytes": total}
