"""Named chat sessions for the AI advisor.

A session is just a :class:`ChatHistory` stored under its own file in
``~/.local/share/flashpilot/ai_sessions/``. :class:`SessionManager` keeps the
list of sessions, the active one, and handles create/rename/delete without
losing data.
"""

from __future__ import annotations

import os
import re

from .history import ChatHistory, default_path


def sessions_dir() -> str:
    base = os.environ.get("XDG_DATA_HOME") or os.path.expanduser("~/.local/share")
    return os.path.join(base, "flashpilot", "ai_sessions")


def _safe_name(name: str) -> str:
    name = (name or "").strip()
    name = re.sub(r"[^A-Za-z0-9 _-]", "", name)
    name = re.sub(r"\s+", " ", name).strip()
    if not name:
        name = "Untitled"
    return name[:60]


class SessionManager:
    def __init__(self, active: str | None = None):
        self._dir = sessions_dir()
        os.makedirs(self._dir, exist_ok=True)
        self._sessions: dict[str, ChatHistory] = {}
        self._active: str | None = None
        # Migrate a legacy single transcript into "Default" on first run.
        legacy = default_path()
        default_file = os.path.join(self._dir, "Default.json")
        if os.path.exists(legacy) and not os.path.exists(default_file):
            try:
                import shutil
                shutil.copy2(legacy, default_file)
            except OSError:
                pass
        names = self.list_names()
        if not names:
            names = ["Default"]
            # Materialise an empty transcript so list_names() sees it.
            try:
                with open(default_file, "w", encoding="utf-8") as fh:
                    fh.write('{\"version\": 1, \"messages\": []}')
            except OSError:
                pass
        if active and active in names:
            self._active = active
        else:
            self._active = names[0]
        self._load(self._active)

    def _path_for(self, name: str) -> str:
        return os.path.join(self._dir, _safe_name(name) + ".json")

    def list_names(self) -> list[str]:
        try:
            entries = sorted(os.listdir(self._dir))
        except OSError:
            return []
        names = []
        for entry in entries:
            if entry.endswith(".json"):
                names.append(entry[:-5])
        return names

    def _load(self, name: str) -> ChatHistory:
        name = _safe_name(name)
        if name not in self._sessions:
            self._sessions[name] = ChatHistory(self._path_for(name))
        self._active = name
        return self._sessions[name]

    @property
    def active_name(self) -> str:
        return self._active or "Default"

    @property
    def active(self) -> ChatHistory:
        return self._load(self.active_name)

    def switch(self, name: str) -> ChatHistory:
        return self._load(name)

    def create(self, name: str = "New chat") -> str:
        name = _safe_name(name)
        # Avoid collisions.
        base = name
        i = 2
        while name in self.list_names() or os.path.exists(self._path_for(name)):
            name = f"{base} {i}"
            i += 1
        history = ChatHistory(self._path_for(name))
        # Materialise the file so list_names() sees it.
        try:
            if not os.path.exists(self._path_for(name)):
                with open(self._path_for(name), "w", encoding="utf-8") as fh:
                    fh.write('{"version": 1, "messages": []}')
        except OSError:
            pass
        self._sessions[name] = history
        self._active = name
        return name

    def rename(self, old: str, new: str) -> str:
        old = _safe_name(old)
        new = _safe_name(new)
        if old == new:
            return old
        if old not in self.list_names():
            return old
        if new in self.list_names() and new != old:
            new = new + " 2"
        src = self._path_for(old)
        dst = self._path_for(new)
        try:
            if os.path.exists(src):
                os.replace(src, dst)
        except OSError:
            pass
        self._sessions.pop(old, None)
        self._sessions[new] = ChatHistory(dst)
        if self._active == old:
            self._active = new
        return new

    def delete(self, name: str) -> None:
        name = _safe_name(name)
        names = self.list_names()
        if len(names) <= 1:
            return  # never delete the last session
        path = self._path_for(name)
        try:
            if os.path.exists(path):
                os.remove(path)
        except OSError:
            pass
        self._sessions.pop(name, None)
        if self._active == name:
            remaining = [n for n in names if n != name]
            self._active = remaining[0] if remaining else "Default"
            self._load(self._active)

    def export_markdown(self, name: str | None = None) -> str:
        history = self._load(name) if name else self.active
        lines = [f"# {name or self.active_name}", ""]
        for message in history.messages:
            role = "You" if message["role"] == "user" else "Advisor"
            lines.append(f"## {role}")
            lines.append("")
            lines.append(message["content"])
            lines.append("")
        return "\n".join(lines)
