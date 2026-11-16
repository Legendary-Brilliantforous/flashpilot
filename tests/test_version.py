"""The release version has one source of truth: ``pyproject.toml``.

The .deb build reads the version from ``pyproject.toml``, while the GUI shows
``python.core.APP_VERSION`` — installed builds take it from package metadata,
source checkouts use the fallback constant. ``python.core.core.__version__``
mirrors it for older call sites. If those drift, an installed app can display
a different version than the package it came from, which makes bug reports
useless. Keep them in lockstep; bump all of them together.
"""
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _pyproject_version():
    text = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
    match = re.search(r'^version\s*=\s*"([^"]+)"', text, re.MULTILINE)
    assert match, "pyproject.toml has no [project] version"
    return match.group(1)


def _constant(relative, name):
    text = (ROOT / relative).read_text(encoding="utf-8")
    match = re.search(rf'^{name}\s*=\s*"([^"]+)"', text, re.MULTILINE)
    assert match, f"{relative} has no {name}"
    return match.group(1)


def test_version_constants_match_pyproject():
    canonical = _pyproject_version()
    assert _constant("python/core/core.py", "__version__") == canonical
    # The source-checkout fallback in the package __init__ (two branches).
    fallbacks = set(
        re.findall(
            r'APP_VERSION\s*=\s*"([^"]+)"',
            (ROOT / "python" / "core" / "__init__.py").read_text(encoding="utf-8"),
        )
    )
    assert fallbacks == {canonical}, fallbacks


def test_version_is_a_plain_release_triple():
    """BETA builds append a suffix, but the package version stays numeric.

    ``_display_version``/``_is_beta_version`` understand ``1.2.1`` and
    ``1.2.1-beta.1``; anything else (e.g. a stray ``v``) renders oddly.
    """
    version = _pyproject_version()
    assert re.fullmatch(r"\d+\.\d+\.\d+(?:-[0-9A-Za-z.\-]+)?", version), version


def test_app_version_matches_the_canonical_version():
    """`APP_VERSION` comes from package metadata when installed, else the
    source fallback. Either way it must agree with what the build ships."""
    from importlib.metadata import PackageNotFoundError, version

    from python.core import APP_VERSION

    assert APP_VERSION
    try:
        installed = version("flashpilot")
    except PackageNotFoundError:
        installed = None
    if installed is not None:
        assert APP_VERSION == installed
    else:
        assert APP_VERSION == _pyproject_version()
