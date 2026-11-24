#!/usr/bin/env python3
"""Auto-detect and strip unused PyQt6/Qt components from a staged venv.

The application imports only a handful of PyQt6 modules (QtCore, QtGui, QtSvg,
QtWidgets today). Shipping the whole PyQt6/Qt stack wastes ~100 MB. This
script scans the shipped source tree for ``PyQt6.<Module>`` references, keeps
only those modules plus their transitive Qt library dependencies, and removes
everything else. The .deb smoke test in build-deb.sh verifies the GUI still
constructs after stripping.

Usage: strip_pyqt.py <venv_dir> <source_root>
"""
import argparse
import ast
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

BASELINE_KEEP = {"QtCore", "QtGui", "QtSvg", "QtWidgets"}

CORE_PLUGINS = {
    "platforms", "platformthemes", "platforminputcontexts",
    "imageformats", "iconengines", "generic",
    "tls", "networkinformation",
    "wayland-decoration-client", "wayland-graphics-integration-client",
    "wayland-shell-integration", "xcbglintegrations", "egldeviceintegrations",
}


def collect_used_modules(src_root: Path) -> set:
    used = set(BASELINE_KEEP)
    roots = [src_root / "python", src_root / "scripts"]
    paths = []
    for r in roots:
        if r.exists():
            paths.extend(r.rglob("*.py"))
    mp = src_root / "main.py"
    if mp.exists():
        paths.append(mp)
    for path in paths:
        try:
            text = path.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        try:
            tree = ast.parse(text)
        except SyntaxError:
            tree = None
        if tree is not None:
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    for alias in node.names:
                        if alias.name.startswith("PyQt6."):
                            used.add(alias.name.split(".")[1])
                elif isinstance(node, ast.ImportFrom):
                    if node.module == "PyQt6":
                        for alias in node.names:
                            if alias.name and alias.name[0].isupper():
                                used.add(alias.name)
                    elif node.module and node.module.startswith("PyQt6."):
                        used.add(node.module.split(".")[1])
        for m in re.finditer(r"PyQt6\.([A-Za-z][A-Za-z0-9_]*)", text):
            name = m.group(1)
            if name and name[0].isupper():
                used.add(name)
    return used


def ldd_closure(seed_sos):
    needed = set()
    visited = set()
    stack = [p for p in seed_sos if p and Path(p).exists()]
    while stack:
        so = stack.pop()
        if str(so) in visited:
            continue
        visited.add(str(so))
        try:
            out = subprocess.check_output(
                ["ldd", str(so)], stderr=subprocess.DEVNULL, text=True)
        except (OSError, subprocess.CalledProcessError):
            continue
        for line in out.splitlines():
            m = re.search(r"=>\s*(\S+)", line)
            if not m:
                continue
            p = m.group(1)
            if not p or p == "not":
                continue
            base = os.path.basename(p)
            if base.startswith("libQt"):
                needed.add(base)
                if os.path.exists(p) and p not in visited:
                    visited.add(p)
                    stack.append(Path(p))
    return needed


def strip(venv: Path, src_root: Path) -> int:
    sp_candidates = list((venv / "lib").glob("python*/site-packages"))
    if not sp_candidates:
        print("strip_pyqt: no site-packages found", file=sys.stderr)
        return 1
    sp = sp_candidates[0]
    pyqt6 = sp / "PyQt6"
    qt6lib = pyqt6 / "Qt6" / "lib"
    plugins_dir = pyqt6 / "Qt6" / "plugins"

    if not pyqt6.exists():
        print("strip_pyqt: PyQt6 not found, nothing to do")
        return 0

    used = collect_used_modules(src_root)
    print(f"strip_pyqt: keeping modules {sorted(used)}")

    removed_mods = []
    for so in sorted(pyqt6.glob("Qt*.abi3.so")):
        mod = so.name.split(".")[0]
        if mod in used:
            continue
        so.unlink(missing_ok=True)
        removed_mods.append(mod)
        for suffix in (".py", ".pyi"):
            p = pyqt6 / (mod + suffix)
            if p.exists():
                p.unlink()
    for d in list(pyqt6.iterdir()):
        if d.is_dir() and d.name.startswith("Qt") and d.name not in used and d.name != "Qt6":
            shutil.rmtree(d, ignore_errors=True)
            removed_mods.append(d.name + "/")
    print(f"strip_pyqt: removed {len(removed_mods)} binding modules")

    if qt6lib.exists():
        seed = []
        for mod in used:
            p = pyqt6 / f"{mod}.abi3.so"
            if p.exists():
                seed.append(p)
        kept_plugins = set()
        if plugins_dir.exists():
            for name in os.listdir(plugins_dir):
                if name in CORE_PLUGINS:
                    kept_plugins.add(name)
        for pname in kept_plugins:
            pd = plugins_dir / pname
            if pd.exists():
                for root, _, files in os.walk(pd):
                    for f in files:
                        if f.endswith(".so"):
                            seed.append(Path(root) / f)
        needed_libs = ldd_closure(seed)
        for mod in used:
            needed_libs.add(f"libQt6{mod[2:]}.so.6")
        for core in ("libQt6Core.so.6", "libQt6Gui.so.6", "libQt6Widgets.so.6",
                     "libQt6Svg.so.6", "libQt6Network.so.6", "libQt6DBus.so.6",
                     "libQt6OpenGL.so.6", "libQt6XcbQpa.so.6"):
            needed_libs.add(core)

        removed_libs = 0
        for lib in sorted(qt6lib.glob("libQt6*.so*")):
            m = re.match(r"libQt6([A-Za-z0-9]+)\.so", lib.name)
            if not m:
                continue
            modname = m.group(1)
            versioned = f"libQt6{modname}.so.6"
            if versioned in needed_libs or lib.name in needed_libs:
                continue
            lib.unlink(missing_ok=True)
            removed_libs += 1
        print(f"strip_pyqt: removed {removed_libs} Qt shared libs")

    if plugins_dir.exists():
        removed_plugins = []
        for name in os.listdir(plugins_dir):
            p = plugins_dir / name
            if not p.is_dir():
                continue
            if name in CORE_PLUGINS:
                continue
            shutil.rmtree(p, ignore_errors=True)
            removed_plugins.append(name)
        print(f"strip_pyqt: removed {len(removed_plugins)} optional plugins")

    for root, dirs, files in os.walk(venv):
        for d in list(dirs):
            if d == "__pycache__":
                shutil.rmtree(Path(root) / d, ignore_errors=True)
                dirs.remove(d)
        for f in files:
            if f.endswith(".pyc"):
                (Path(root) / f).unlink(missing_ok=True)

    print("strip_pyqt: done")
    return 0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("venv_dir")
    ap.add_argument("src_root")
    args = ap.parse_args()
    return strip(Path(args.venv_dir), Path(args.src_root))


if __name__ == "__main__":
    sys.exit(main())
